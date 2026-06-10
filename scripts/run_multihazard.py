"""
Multi-hazard flood depth runner (coastal + fluvial + pluvial).

Originally written for Singapore; now invoked generically for every city
in scripts/cities.py.  See docs/hazard_methodology_comparison.{md,html}
for the full open methodology, public data sources, replicability audit
(R1-R8) and ASEAN coverage roadmap.

Compound-hazard caveat
----------------------
This runner produces *per-driver* depth rasters (coastal, fluvial,
pluvial) and the downstream `make_combined_flood_maps.py` step composites
them via a pixel-wise depth maximum.  This is **not** a true joint /
compound flood model: it does not capture coincident storm-surge +
riverine peaks, backwater interaction at river mouths, or rainfall-on-
surge effects.  Treat compound depths as an upper-bound envelope and
flag explicit joint analysis in any downstream risk product.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import numpy as np
import pandas as pd
import rasterio

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.flood_depth_model import (
    apply_connectivity_filter,
    derive_sea_mask,
    derive_tidal_channel_seeds,
    flood_depth_bathtub,
    flood_depth_hand,
    flood_depth_pluvial_ponding,
    load_dem,
    summarize_depth,
    write_depth_raster,
)
from model.inertial_wave_model import run_inertial
from model.pluvial_model import build_pluvial_topography, route_pluvial_rp
from model.pluvial_rain_model import run_rain_on_grid, denoise_min_cluster, apply_depth_floor

def _surge_hydrograph(
    peak_wse: float,
    floor_wse: float = 0.0,
    ramp_s: float = 10_800.0,
    hold_s: float = 3_600.0,
    recession_s: float = 7_200.0,
):
    """
    Return a wl_fn(t_s) callable for a synthetic triangular storm-surge that
    rides on top of a *permanent* still-water level (``floor_wse``).

    Profile (default: 3 h ramp, 1 h peak, 2 h recession), ASYMMETRIC:
        0 → ramp_s             : linear ramp from 0 to peak_wse (gentle start
                                  from dry bed, as the local-inertial scheme
                                  requires to avoid a cold-start shock)
        ramp_s → +hold_s       : constant at peak_wse
        +hold_s → +recession_s : linear decay from peak_wse back to floor_wse
                                  (NOT to 0 — preserves permanent SLR floor)

    ``floor_wse`` is the permanent still-water elevation (mean sea level + sea-
    level rise, in the DEM datum).  The transient surge component recedes only
    down to the floor; the permanent floor does NOT recede further, so sea-
    connected land below floor_wse stays inundated after the surge withdraws,
    as it physically must under SLR.

    The asymmetry is deliberate: starting the BC at the floor (symmetric profile)
    creates a sustained Dirichlet shock against a dry bed that destabilises the
    inertial solver.  Starting from 0 lets the solver track the BC smoothly; only
    the *recession* stops at the floor.  The legacy default ``floor_wse=0``
    reproduces the old behaviour (recede to datum zero) and under-fills SLR.

    The total surge window is ramp_s + hold_s + recession_s = 21,600 s (6 h).
    The simulation should run somewhat longer (t_end) so peak_depth stabilises.
    """
    # Guard: if the floor meets or exceeds the peak (degenerate / very low RP),
    # hold a static level at the floor.
    floor = max(0.0, min(floor_wse, peak_wse))

    def wl_fn(t: float) -> float:
        if t <= ramp_s:
            return peak_wse * (t / ramp_s)              # gentle 0 -> peak
        elif t <= ramp_s + hold_s:
            return peak_wse                              # hold at peak
        else:
            frac = (t - ramp_s - hold_s) / recession_s
            return floor + (peak_wse - floor) * max(0.0, 1.0 - frac)  # peak -> floor
    return wl_fn


REQUIRED_COLUMNS = {
    "hazard_type",
    "return_period",
    "scenario",
    "horizon",
    "water_level_m",
}


def read_hazard_levels(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in hazard CSV: {sorted(missing)}")
    hazards = set(df["hazard_type"].astype(str).str.lower())
    expected = {"coastal", "fluvial", "pluvial"}
    if not expected.issubset(hazards):
        raise ValueError("hazard_type must include coastal, fluvial, and pluvial rows.")
    return df


def classify_depth_severity(depth: np.ndarray) -> np.ndarray:
    """
    Severity classes:
      0: no flood (<=0)
      1: minor   (0 - 0.15 m]
      2: moderate(0.15 - 0.50 m]
      3: major   (0.50 - 1.00 m]
      4: severe  (>1.00 m)
      255: nodata
    """
    out = np.full(depth.shape, 255, dtype=np.uint8)
    finite = np.isfinite(depth)
    out[finite & (depth <= 0.0)] = 0
    out[finite & (depth > 0.0) & (depth <= 0.15)] = 1
    out[finite & (depth > 0.15) & (depth <= 0.50)] = 2
    out[finite & (depth > 0.50) & (depth <= 1.00)] = 3
    out[finite & (depth > 1.00)] = 4
    return out


def write_severity_raster(severity: np.ndarray, profile: dict, out_path: Path) -> None:
    profile_out = profile.copy()
    profile_out.update(
        dtype="uint8",
        count=1,
        compress="deflate",
        nodata=255,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile_out) as dst:
        dst.write(severity, 1)


def severity_area_stats(severity: np.ndarray, transform, crs) -> dict[str, float]:
    if not crs.is_projected:
        raise ValueError(
            f"DEM CRS {crs} is geographic (units: degrees). "
            "Reproject to a projected CRS with metre units before computing areas."
        )
    pixel_area = float(abs(transform.a * transform.e))
    out: dict[str, float] = {}
    for value, label in [
        (1, "minor"),
        (2, "moderate"),
        (3, "major"),
        (4, "severe"),
    ]:
        count = int(np.count_nonzero(severity == value))
        out[f"{label}_area_km2"] = (count * pixel_area) / 1_000_000.0
    return out


@click.command()
@click.option("--dem", "dem_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--hazard-levels",
    "hazard_levels_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="CSV with hazard_type, return_period, scenario, horizon, water_level_m",
)
@click.option("--scenario", required=True, help="e.g. SSP5-8.5")
@click.option("--horizon", type=int, required=True, help="e.g. 2100")
@click.option(
    "--out-dir",
    "out_dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Root output folder for Singapore assessment products.",
)
@click.option(
    "--seed-water-raster",
    "seed_water_raster_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Optional permanent/open water seed raster aligned to DEM.",
)
@click.option(
    "--connectivity-neighbors",
    type=click.Choice(["4", "8"]),
    default="8",
    show_default=True,
)
@click.option(
    "--fluvial-hand-raster",
    "fluvial_hand_raster_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help=(
        "Pre-computed HAND raster aligned to the DEM.  When provided, fluvial "
        "inundation is computed as depth = max(0, water_level_m - HAND) instead "
        "of the bathtub method.  water_level_m for fluvial rows is treated as a "
        "stage above the channel floor (relative), not an absolute datum level.  "
        "Generate with scripts/build_hand_raster.py."
    ),
)
@click.option(
    "--sea-mask-raster",
    "sea_mask_raster_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help=(
        "Land/sea mask raster aligned to the DEM (1=land, 0=sea, 255=nodata). "
        "When provided: (1) sea pixels are excluded from the DEM before all "
        "processing, eliminating spurious ocean flooding; (2) sea pixels seed "
        "coastal connectivity instead of raster boundary cells; (3) pluvial "
        "inundation uses a depression-filling ponding model instead of bathtub. "
        "Generate with scripts/build_sea_mask.py."
    ),
)
@click.option(
    "--tidal-channel-raster",
    "tidal_channel_raster_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help=(
        "River/drain mask raster aligned to the DEM (>0 = channel cell). "
        "When provided alongside --sea-mask-raster, tidal channel pixels "
        "reachable from the sea via the channel network are added as extra "
        "BFS seeds for coastal connectivity.  Resolves the sub-30m seawall-gap "
        "problem by letting the model propagate flood water along tidal drains "
        "that are too narrow to resolve at 30 m resolution. "
        "Generate the channel raster with scripts/build_river_raster_from_osm.py."
    ),
)
@click.option(
    "--tidal-burn-elevation",
    "tidal_burn_elevation",
    type=float,
    default=2.0,
    show_default=True,
    help=(
        "Maximum DEM elevation (m) for a channel pixel to be used as a tidal "
        "seed.  Only affects coastal BFS; has no effect without "
        "--tidal-channel-raster."
    ),
)
@click.option(
    "--coastal-seed-latlon",
    "coastal_seed_latlon",
    multiple=True,
    default=[],
    help=(
        "Additional BFS seed point(s) for coastal connectivity, as 'lat,lon' "
        "strings (WGS84 decimal degrees).  Can be specified multiple times.  "
        "Use this when the target water body (e.g. Manila Bay) is fully "
        "enclosed within the DEM domain and cannot be reached from the NaN "
        "sea-mask boundary via z < water_level terrain.  Each point is "
        "projected to the DEM CRS and its pixel is added to the BFS seed "
        "mask alongside sea_mask and tidal channel seeds."
    ),
)
@click.option(
    "--fluvial-bankfull-rp",
    "fluvial_bankfull_rp",
    type=int,
    default=10,
    show_default=True,
    help=(
        "Return period (years) used as the bankfull (full-channel) stage when "
        "applying the HAND flood model.  The overbank stage fed to HAND is "
        "max(0, stage_RP - stage_bankfull_RP), so flooding only occurs when the "
        "event exceeds the bankfull capacity.  Set to 0 to disable subtraction "
        "and pass the raw stage directly (original behaviour). "
        "Default 2 (RP2 = annual bankfull) is appropriate for Singapore's "
        "urban drains; use 5 or 10 for better-designed infrastructure."
    ),
)
@click.option(
    "--coastal-solver",
    "coastal_solver",
    type=click.Choice(["inertial", "bathtub"]),
    default="inertial",
    show_default=True,
    help=(
        "Solver for coastal inundation. 'inertial' runs the full 2D shallow-water "
        "inertial solver (accurate, slow). 'bathtub' uses a static depth = "
        "max(0, water_level - DEM) approach (fast, no dynamics). "
        "Use 'bathtub' for quick screening runs."
    ),
)
@click.option(
    "--coastal-msl-egm2008",
    "coastal_msl_egm2008",
    type=float,
    default=0.0,
    show_default=True,
    help="Mean-sea-level elevation in the DEM datum (EGM2008 m).  The inertial "
         "surge hydrograph recedes to this level plus the row's SLR delta "
         "(coastal_delta_m) — the PERMANENT still-water level — instead of to 0, "
         "so SLR-driven inundation of connected low land persists.  Pass the "
         "city's msl_to_egm2008_offset.  Default 0 reproduces legacy behaviour.",
)
@click.option(
    "--inertial-t-end",
    "inertial_t_end",
    type=float,
    default=28_800.0,
    show_default=True,
    help="Inertial solver simulation duration in seconds (default 8 h = 28800 s). "
         "Reduce to e.g. 14400 (4 h) for faster runs with acceptable accuracy.",
)
@click.option(
    "--inertial-dt-max",
    "inertial_dt_max",
    type=float,
    default=30.0,
    show_default=True,
    help="Inertial solver maximum timestep in seconds. Larger values are faster "
         "but less stable. Default 30 s is safe for 30 m grids.",
)
@click.option(
    "--inertial-convergence-tol",
    "inertial_convergence_tol",
    type=float,
    default=1e-3,
    show_default=True,
    help="Inertial solver early-stop tolerance (mean depth change in metres). "
         "Default 1e-3 m (1 mm) is sufficient for flood-map applications where "
         "the minimum meaningful severity threshold is 150 mm.  Tighten to 1e-4 "
         "only when sub-millimetre accuracy of the final water surface is required.",
)
@click.option(
    "--clamp-negative-land/--no-clamp-negative-land",
    "clamp_negative_land",
    default=True,
    show_default=True,
    help="Clamp sub-zero land pixels to 0 m (default: on).  Disable when the DEM "
         "has been subsidence-corrected and below-sea-level land pixels represent "
         "real terrain rather than radar artefacts.  With --no-clamp-negative-land "
         "these pixels show flood depth = water_level - DEM_elevation, correctly "
         "representing areas of chronic inundation.",
)
@click.option(
    "--only-hazard-types",
    "only_hazard_types",
    type=str,
    default=None,
    show_default=True,
    help=(
        "Comma-separated list of hazard types to run (e.g. 'fluvial' or "
        "'coastal,fluvial').  When set, only those hazard types are computed "
        "and written; other types are skipped.  Useful for re-running a single "
        "hazard after fixing the HAND raster without repeating the slow coastal "
        "inertial solver."
    ),
)
@click.option(
    "--pluvial-model",
    "pluvial_model",
    type=click.Choice(["fillspill", "legacy", "raingrid"]),
    default="fillspill",
    show_default=True,
    help="Pluvial solver: 'raingrid' = 2D rain-on-grid local-inertial "
         "(flash-flood ponding from drainage-capacity exceedance; recommended, "
         "use with a bare-earth conditioned --pluvial-dem-raster); "
         "'fillspill' = catchment-routed fill-and-spill cascade (depression "
         "storage only); 'legacy' = lumped depression-fill (frozen extent).",
)
@click.option(
    "--pluvial-dem-raster",
    "pluvial_dem_raster_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="DEM used for rain-on-grid pluvial routing (bare-earth + hydro-"
         "conditioned).  Must match the main DEM grid.  Defaults to --dem.",
)
@click.option(
    "--manning-raster",
    "manning_raster_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Per-cell Manning's n GeoTIFF aligned to the DEM (rain-on-grid only). "
         "When omitted, n is derived from the runoff-coeff raster, else uniform 0.05.",
)
@click.option(
    "--rain-storm-hours", "rain_storm_hours", type=float, default=1.0,
    show_default=True, help="Rain-on-grid storm duration (h); matches the IDF window.",
)
@click.option(
    "--rain-total-hours", "rain_total_hours", type=float, default=1.5,
    show_default=True, help="Rain-on-grid total simulated time (h) incl. settling.",
)
@click.option("--pluvial-depth-cap", "pluvial_depth_cap", type=float, default=None,
              help="If set, clip rain-on-grid peak depth to this max (m) — a physical "
                   "life-safety bound on residual solver overshoot (default: off).")
@click.option("--drain-conveyance-m-s", "drain_conveyance_m_s", type=float, default=None,
              help="Finite drain conveyance (m/s of depth shed per outlet cell per second). "
                   "Omit for perfect-sink drains. Calibrated to documented drain capacity (limitation #19).")
@click.option("--raingrid-workers", "raingrid_workers", type=int, default=0, show_default=True,
              help="Parallel worker processes for the per-RP raingrid pluvial solves "
                   "(0=auto=min(cores,#RPs); 1=serial). 1 numba thread/worker. "
                   "Bit-identical to serial; ~2.5-3x faster on the 9-RP batch (limitation #18).")
@click.option("--major-river-raster", "major_river_raster_path",
              type=click.Path(exists=True, path_type=Path), default=None,
              help="Major-river mask (1=river). With --drain-conveyance-m-s, these cells "
                   "(plus sea) stay perfect sinks (high conveyance); only the minor drains "
                   "in --tidal-channel-raster get the finite conveyance. Limitation #19.")
@click.option(
    "--runoff-coeff-raster",
    "runoff_coeff_raster_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="WorldCover-derived per-cell runoff-coefficient GeoTIFF aligned to "
         "the DEM.  When omitted a uniform scalar of 0.75 is used.",
)
@click.option(
    "--runoff-coeff",
    "runoff_coeff",
    type=float,
    default=0.75,
    show_default=True,
    help="Uniform runoff coefficient for the fill-spill pluvial model, used "
         "when --runoff-coeff-raster is not supplied.  Pass the city's "
         "configured runoff_coeff here so per-city values are honoured.",
)
def cli(
    dem_path: Path,
    hazard_levels_path: Path,
    scenario: str,
    horizon: int,
    out_dir: Path,
    seed_water_raster_path: Path | None,
    connectivity_neighbors: str,
    fluvial_hand_raster_path: Path | None,
    sea_mask_raster_path: Path | None,
    tidal_channel_raster_path: Path | None,
    tidal_burn_elevation: float,
    coastal_seed_latlon: tuple[str, ...],
    fluvial_bankfull_rp: int,
    coastal_solver: str,
    coastal_msl_egm2008: float,
    inertial_t_end: float,
    inertial_dt_max: float,
    inertial_convergence_tol: float,
    clamp_negative_land: bool,
    only_hazard_types: str | None,
    pluvial_model: str,
    pluvial_dem_raster_path: Path | None,
    manning_raster_path: Path | None,
    rain_storm_hours: float,
    rain_total_hours: float,
    pluvial_depth_cap: float | None,
    drain_conveyance_m_s: float | None,
    raingrid_workers: int,
    major_river_raster_path: Path | None,
    runoff_coeff_raster_path: Path | None,
    runoff_coeff: float,
) -> None:
    levels = read_hazard_levels(hazard_levels_path)
    levels = levels[(levels["scenario"] == scenario) & (levels["horizon"] == horizon)].copy()
    if levels.empty:
        raise ValueError(f"No hazard rows found for scenario={scenario}, horizon={horizon}")

    # Optional hazard-type filter (e.g. re-run only fluvial after HAND rebuild).
    if only_hazard_types is not None:
        allowed = {h.strip().lower() for h in only_hazard_types.split(",")}
        levels = levels[levels["hazard_type"].str.lower().isin(allowed)].copy()
        if levels.empty:
            raise ValueError(
                f"No hazard rows remain after filtering to --only-hazard-types={only_hazard_types!r}. "
                f"Available types: coastal, fluvial, pluvial."
            )
        click.echo(f"[filter] Running only hazard type(s): {', '.join(sorted(allowed))}")

    levels["return_period"] = levels["return_period"].astype(int)
    levels = levels.sort_values(["hazard_type", "return_period"]).reset_index(drop=True)

    # Bankfull stage for HAND overbank calculation
    fluvial_bankfull_m: float = 0.0
    if fluvial_bankfull_rp > 0:
        bankfull_rows = levels[
            (levels["hazard_type"] == "fluvial")
            & (levels["return_period"] == fluvial_bankfull_rp)
        ]
        if bankfull_rows.empty:
            click.echo(
                f"[warn] --fluvial-bankfull-rp={fluvial_bankfull_rp} not found in hazard "
                "levels — bankfull subtraction disabled.",
                err=True,
            )
        else:
            fluvial_bankfull_m = float(bankfull_rows["water_level_m"].iloc[0])
            click.echo(
                f"Fluvial bankfull stage (RP{fluvial_bankfull_rp}): "
                f"{fluvial_bankfull_m:.3f} m  "
                f"(overbank = stage - {fluvial_bankfull_m:.3f} m)"
            )

    dem, profile = load_dem(dem_path)

    # --- Sea mask -----------------------------------------------------------
    # dem_land: sea pixels set to NaN — used for fluvial and pluvial so ocean
    #           pixels never generate false depth values.
    # dem_orig: original DEM retained — used for coastal so that sea pixels
    #           have positive bathtub depth and can act as BFS connectivity
    #           seeds (flooding enters land from the sea surface).
    # After connectivity, sea pixel depths are zeroed in the final output.
    sea_mask: np.ndarray | None = None
    dem_land = dem.copy()   # will be overwritten below if mask provided
    if sea_mask_raster_path is not None:
        with rasterio.open(sea_mask_raster_path) as sm_src:
            if sm_src.shape != dem.shape:
                raise ValueError(
                    f"Sea mask shape {sm_src.shape} does not match DEM shape {dem.shape}"
                )
            if sm_src.crs != profile["crs"]:
                raise ValueError(
                    f"Sea mask CRS {sm_src.crs} does not match DEM CRS {profile['crs']}"
                )
            if sm_src.transform != profile["transform"]:
                raise ValueError(
                    "Sea mask transform does not match DEM — rasters are not aligned"
                )
            sm_arr = sm_src.read(1)
        land_pixels = (sm_arr == 1)
        sea_pixels  = (sm_arr == 0)
        dem_land = np.where(land_pixels, dem, np.nan)
        sea_mask = sea_pixels.astype(bool)
        n_sea  = int(np.count_nonzero(sea_pixels))
        n_land = int(np.count_nonzero(land_pixels))
        click.echo(
            f"Sea mask applied: {n_sea:,} sea pixels masked, "
            f"{n_land:,} land pixels retained"
        )

        # Clamp isolated negative-elevation artefacts on land.
        # ~1,500 Copernicus GLO-30 pixels carry sub-zero elevations but are
        # not reachable from the coast via the sea-mask BFS — they are DEM
        # artefacts (often caused by radar shadowing or water body filling).
        # Left unclamped they produce depth = wse − (−Xm) >> wse in the
        # bathtub model.  Setting them to 0.0 m is conservative: they become
        # indistinguishable from sea-level land rather than phantom deep holes.
        #
        # When --no-clamp-negative-land is set (e.g. subsidence-corrected DEM
        # paired with the original sea mask), negative land pixels represent real
        # below-sea-level terrain and should NOT be clamped — their depth will
        # equal water_level - DEM_elevation, correctly showing chronic inundation.
        neg_land = land_pixels & np.isfinite(dem) & (dem < 0.0)
        n_clamped = int(neg_land.sum())
        if n_clamped:
            if clamp_negative_land:
                dem      = np.where(neg_land, 0.0, dem)
                dem_land = np.where(neg_land, 0.0, dem_land)
                click.echo(f"Clamped {n_clamped:,} negative-elevation land artefacts to 0.0 m")
            else:
                click.echo(
                    f"Retaining {n_clamped:,} negative-elevation land pixels "
                    f"(--no-clamp-negative-land; range "
                    f"{dem[neg_land].min():.2f} to {dem[neg_land].max():.2f} m) "
                    f"-- these represent subsidence-corrected below-sea-level terrain."
                )

    # Tidal channel seeds: river/drain pixels reachable from sea along the channel
    # network, up to tidal_burn_elevation.  Added to coastal BFS seeds so that
    # the model can propagate flood water along tidal drains that are too narrow
    # to resolve at 30 m pixel size (sub-pixel seawall gaps).
    tidal_seeds: np.ndarray | None = None
    if tidal_channel_raster_path is not None and sea_mask is not None:
        with rasterio.open(tidal_channel_raster_path) as tc_src:
            if tc_src.shape != dem.shape:
                raise ValueError(
                    f"Tidal channel raster shape {tc_src.shape} does not match "
                    f"DEM shape {dem.shape}"
                )
            if tc_src.crs != profile["crs"]:
                raise ValueError(
                    f"Tidal channel CRS {tc_src.crs} does not match DEM CRS {profile['crs']}"
                )
            if tc_src.transform != profile["transform"]:
                raise ValueError(
                    "Tidal channel raster transform does not match DEM — not aligned"
                )
            channel_arr = tc_src.read(1)
        channel_mask = (channel_arr > 0)
        tidal_seeds = derive_tidal_channel_seeds(
            sea_mask=sea_mask,
            channel_mask=channel_mask,
            max_elevation_m=tidal_burn_elevation,
            dem=dem,
            connectivity=int(connectivity_neighbors),
        )
        n_tidal = int(tidal_seeds.sum())
        click.echo(
            f"Tidal channel seeds: {n_tidal:,} channel pixels reachable from sea "
            f"(DEM <= {tidal_burn_elevation} m)"
        )

    # Explicit coastal BFS seed pixels from lat/lon coordinates.
    # Used for cities (e.g. Manila) where the target water body is fully
    # enclosed within the DEM domain and the NaN sea-mask boundary has no
    # z < water_level path to the bay — so the normal sea_mask | tidal_seeds
    # BFS cannot propagate inward to seed coastal flooding.
    latlon_seed_mask: np.ndarray | None = None
    if coastal_seed_latlon and sea_mask is not None:
        from rasterio.warp import transform as _warp_transform
        from rasterio.transform import rowcol as _rowcol
        wgs84_crs = rasterio.crs.CRS.from_epsg(4326)
        latlon_seed_mask = np.zeros(dem.shape, dtype=bool)
        for _latlon_str in coastal_seed_latlon:
            _lat_s, _lon_s = _latlon_str.split(",")
            _lat, _lon = float(_lat_s.strip()), float(_lon_s.strip())
            _xs, _ys = _warp_transform(wgs84_crs, profile["crs"], [_lon], [_lat])
            _row, _col = _rowcol(profile["transform"], _xs[0], _ys[0])
            _row, _col = int(_row), int(_col)
            if 0 <= _row < dem.shape[0] and 0 <= _col < dem.shape[1]:
                latlon_seed_mask[_row, _col] = True
                click.echo(
                    f"Coastal seed point: lat={_lat}, lon={_lon} "
                    f"-> pixel row={_row}, col={_col} "
                    f"(DEM elev={dem[_row, _col]:.3f} m)"
                )
            else:
                click.echo(
                    f"[warn] Coastal seed lat={_lat}, lon={_lon} "
                    f"-> pixel ({_row}, {_col}) is outside DEM bounds - skipped",
                    err=True,
                )
        n_latlon = int(latlon_seed_mask.sum())
        click.echo(f"Coastal lat/lon seeds: {n_latlon:,} pixel(s) added to BFS seed mask")

    hand_array: np.ndarray | None = None
    if fluvial_hand_raster_path is not None:
        with rasterio.open(fluvial_hand_raster_path) as hand_src:
            if hand_src.shape != dem.shape:
                raise ValueError(
                    f"HAND raster shape {hand_src.shape} does not match DEM shape {dem.shape}"
                )
            if hand_src.crs != profile["crs"]:
                raise ValueError(
                    f"HAND raster CRS {hand_src.crs} does not match DEM CRS {profile['crs']}"
                )
            if hand_src.transform != profile["transform"]:
                raise ValueError(
                    "HAND raster transform does not match DEM transform — rasters are not aligned"
                )
            hand_array = hand_src.read(1).astype(np.float32)
            hand_nodata = hand_src.nodata
        if hand_nodata is not None:
            hand_array = np.where(hand_array == hand_nodata, np.nan, hand_array)
        click.echo(f"Loaded HAND raster: {fluvial_hand_raster_path} — fluvial will use HAND method")

    seed_mask = None
    if seed_water_raster_path is not None:
        with rasterio.open(seed_water_raster_path) as seed_src:
            seed = seed_src.read(1)
            if seed.shape != dem.shape:
                raise ValueError("seed water raster shape must match DEM shape")
            if seed_src.crs != profile["crs"]:
                raise ValueError(
                    f"Seed raster CRS {seed_src.crs} does not match DEM CRS {profile['crs']}"
                )
            if seed_src.transform != profile["transform"]:
                raise ValueError(
                    "Seed raster transform does not match DEM transform — "
                    "rasters are not spatially aligned"
                )
        seed_mask = np.isfinite(seed) & (seed > 0)

    with rasterio.open(dem_path) as src:
        transform = src.transform
        crs = src.crs

    # Pre-compute steady-state initial depth for below-sea-level land pixels.
    # When --no-clamp-negative-land is active (subsidence-corrected DEM + original
    # sea mask), negative-elevation land cells represent areas already below MSL.
    # Starting the inertial solver from a dry bed forces dt → 0.1 s for hundreds
    # of steps as the shock dissipates.  Pre-flooding these cells to MSL (depth =
    # -DEM_elevation) eliminates the shock and restores normal CFL behaviour.
    # For clamp_negative_land=True the subsea array is all-zeros (no effect).
    if sea_mask is not None and not clamp_negative_land:
        subsea_init = np.where(
            land_pixels & (dem < 0.0),
            np.maximum(0.0, -dem.astype(np.float64)),
            0.0,
        ).astype(np.float64)
        n_subsea = int((subsea_init > 0).sum())
        click.echo(
            f"Pre-flood init: {n_subsea:,} below-sea-level land pixels "
            f"set to steady-state MSL depth (max depth "
            f"{subsea_init.max():.2f} m)."
        )
    else:
        subsea_init = None

    # Runoff coefficient for the fill-spill pluvial model: per-cell raster
    # when supplied, else a uniform scalar.
    runoff_coeff_arr: np.ndarray | float
    if runoff_coeff_raster_path is not None:
        with rasterio.open(runoff_coeff_raster_path) as rc_src:
            if rc_src.shape != dem.shape:
                raise ValueError(
                    f"runoff-coeff raster shape {rc_src.shape} does not match DEM shape {dem.shape}"
                )
            if rc_src.crs != profile["crs"]:
                raise ValueError(
                    f"runoff-coeff raster CRS {rc_src.crs} does not match DEM CRS {profile['crs']}"
                )
            if rc_src.transform != profile["transform"]:
                raise ValueError(
                    "runoff-coeff raster is not aligned to the DEM (CRS/transform mismatch)"
                )
            runoff_coeff_arr = rc_src.read(1).astype(np.float64)
    else:
        runoff_coeff_arr = runoff_coeff

    # River mask for the fill-spill pluvial model: channel pixels act as sinks
    # so that runoff draining to the channel network escapes rather than ponding.
    # Guard mirrors the condition under which channel_mask is assigned above —
    # referencing channel_mask outside that guard would be a NameError.
    pluvial_river_mask = (
        channel_mask if (tidal_channel_raster_path is not None and sea_mask is not None)
        else np.zeros(dem.shape, dtype=bool)
    )

    # Build the RP-independent pluvial topography once when fill-spill is on.
    pluvial_topo = None
    if pluvial_model == "fillspill" and sea_mask is not None:
        pluvial_topo = build_pluvial_topography(
            dem_land, sea_mask, pluvial_river_mask, profile,
        )

    # ---- Rain-on-grid precompute (RP-independent inputs) -------------------
    # The rain-on-grid solver needs: a bed where sea cells are FINITE outlets
    # (not NaN walls), an outlet mask (sea + open channels = free-drainage
    # sinks), and a per-cell Manning's n.  All are built once here.
    raingrid_z = None
    raingrid_outlet = None
    raingrid_n = None
    if pluvial_model == "raingrid" and sea_mask is not None:
        # Pluvial routing DEM: the bare-earth + hydro-conditioned DEM if given,
        # else the main DEM.  Must share the DEM grid.
        if pluvial_dem_raster_path is not None:
            with rasterio.open(pluvial_dem_raster_path) as pdem_src:
                if pdem_src.shape != dem.shape or pdem_src.transform != profile["transform"]:
                    raise ValueError(
                        "--pluvial-dem-raster is not aligned to the main DEM "
                        "(shape/transform mismatch)")
                praw = pdem_src.read(1).astype(np.float64)
                pnod = pdem_src.nodata
            if pnod is not None:
                praw[praw == pnod] = np.nan
        else:
            praw = dem.astype(np.float64)
        # Sea cells -> finite bed at MSL (0 m) so they drain freely.
        raingrid_z = np.where(sea_mask, 0.0, praw)
        # Genuine nodata stays NaN (wall).
        raingrid_z[~np.isfinite(praw) & ~sea_mask] = np.nan
        # Outlets: sea + open channel network.
        raingrid_outlet = sea_mask | pluvial_river_mask
        # Perfect-sink mask: sea + major rivers convey freely regardless of
        # drain_conveyance_m_s; only minor drains get the finite conveyance.
        # If no major-river raster is given, only sea cells are perfect sinks.
        if major_river_raster_path is not None:
            with rasterio.open(major_river_raster_path) as mr_src:
                if mr_src.shape != dem.shape or mr_src.transform != profile["transform"]:
                    raise ValueError(
                        "--major-river-raster is not aligned to the main DEM "
                        "(shape/transform mismatch)")
                mr_raw = mr_src.read(1)
            major_river_mask = (mr_raw > 0) & np.isfinite(dem)
        else:
            major_river_mask = np.zeros(dem.shape, dtype=bool)
        raingrid_perfect_sink = sea_mask | major_river_mask
        # Manning's n: explicit raster > derived-from-runoff > uniform 0.05.
        if manning_raster_path is not None:
            with rasterio.open(manning_raster_path) as mn_src:
                if mn_src.shape != dem.shape or mn_src.transform != profile["transform"]:
                    raise ValueError("--manning-raster is not aligned to the DEM")
                raingrid_n = mn_src.read(1).astype(np.float64)
        elif runoff_coeff_raster_path is not None:
            # Impervious (high runoff coeff) -> low n; vegetated -> high n.
            raingrid_n = np.clip(0.11 - 0.08 * runoff_coeff_arr, 0.03, 0.10)
        else:
            raingrid_n = np.full(dem.shape, 0.05, dtype=np.float64)
        click.echo(
            f"Rain-on-grid pluvial: DEM={'conditioned' if pluvial_dem_raster_path else 'main'}, "
            f"outlets={int(raingrid_outlet.sum()):,}, "
            f"n=[{float(np.nanmin(raingrid_n)):.3f},{float(np.nanmax(raingrid_n)):.3f}]"
        )

    # ---- Pre-solve all raingrid pluvial RPs in a process pool (limitation #18) --
    # The per-RP solves are independent; the solver is memory-bandwidth-bound and
    # scales poorly with threads (~1.73x at 6), so 1-thread workers in parallel
    # reclaim the wasted cores (~2.5-3x). The prange loops are element-wise, so the
    # peak depth is BIT-IDENTICAL to the serial solve. The serial branch below reads
    # this cache when present.  --raingrid-workers 1 keeps the old serial path.
    pluvial_peak_cache: dict[int, np.ndarray] = {}
    if pluvial_model == "raingrid" and sea_mask is not None:
        pluvial_rp_levels = [
            (int(r.return_period), float(r.water_level_m))
            for r in levels.itertuples(index=False)
            if str(r.hazard_type).lower() == "pluvial"
        ]
        if pluvial_rp_levels and raingrid_workers != 1:
            from model.raingrid_parallel import solve_rps_parallel

            _mw = None if raingrid_workers == 0 else raingrid_workers
            click.echo(
                f"Raingrid: pre-solving {len(pluvial_rp_levels)} pluvial RP(s) "
                f"in a process pool (workers={_mw or 'auto'}, 1 thread/worker)…"
            )
            pluvial_peak_cache = solve_rps_parallel(
                raingrid_z, raingrid_outlet, raingrid_n, pluvial_rp_levels,
                solver_kwargs=dict(
                    storm_duration_s=rain_storm_hours * 3600.0,
                    total_duration_s=rain_total_hours * 3600.0,
                    dx=abs(profile["transform"].a),
                    dy=abs(profile["transform"].e),
                    progress_interval=600, verbose=False,
                    peak_depth_cap_m=pluvial_depth_cap,
                    drain_conveyance_m_s=drain_conveyance_m_s,
                ),
                perfect_sink=raingrid_perfect_sink,
                runoff_coeff=runoff_coeff_arr,
                max_workers=_mw,
            )

    # Warm-start: reuse previous coastal RP depth as initial condition for the
    # next RP.  Successive return periods have similar solutions; starting from
    # the prior solution cuts convergence steps by 3–5× (per solver docstring).
    _prev_coastal_depth: np.ndarray | None = None

    summary_rows: list[dict] = []
    for row in levels.itertuples(index=False):
        hazard = str(row.hazard_type).lower()
        rp = int(row.return_period)
        level_m = float(row.water_level_m)

        # --- Depth computation (hazard-specific) ----------------------------
        if hazard == "fluvial" and hand_array is not None:
            # HAND: depth = max(0, overbank_stage - HAND).
            # Overbank stage = max(0, stage_RP - bankfull_stage) so that only
            # the excess above the channel's design capacity causes inundation.
            overbank_m = max(0.0, level_m - fluvial_bankfull_m)
            depth = flood_depth_hand(hand_array, overbank_m)
            # Drainage channels are conveyance, not flood hazard.  HAND is 0 on
            # the burned channel network, so every channel cell floods on any
            # overbank — but a canal carrying water is not inundation.  Many of
            # these cells are below-grade (engineered canal beds), which makes
            # the fluvial map appear to flood "underground".  Mask channel cells
            # out (mirrors the pluvial model treating channels as sinks).  No-op
            # when no channel raster was supplied (pluvial_river_mask is all-False).
            depth = np.where(pluvial_river_mask, 0.0, depth)

        elif hazard == "pluvial" and sea_mask is not None:
            if pluvial_model == "raingrid":
                # 2D rain-on-grid local-inertial: net excess rain
                # (= excess_depth_m * runoff_coeff) applied over the storm,
                # routed under shallow-water dynamics; sea + channels drain.
                assert raingrid_z is not None
                if level_m <= 0.0:
                    depth = np.zeros(dem.shape, dtype=np.float32)
                    depth[~np.isfinite(dem)] = np.nan
                else:
                    if rp in pluvial_peak_cache:
                        # Pre-solved in the process pool (bit-identical; #18).
                        peak = pluvial_peak_cache[rp]
                    else:
                        # Serial path (--raingrid-workers 1).
                        net_rain = np.where(
                            raingrid_outlet, 0.0, level_m * runoff_coeff_arr)
                        peak = run_rain_on_grid(
                            raingrid_z, raingrid_outlet, net_rain, raingrid_n,
                            storm_duration_s=rain_storm_hours * 3600.0,
                            total_duration_s=rain_total_hours * 3600.0,
                            dx=abs(profile["transform"].a),
                            dy=abs(profile["transform"].e),
                            progress_interval=600, verbose=True,
                            peak_depth_cap_m=pluvial_depth_cap,
                            drain_conveyance_m_s=drain_conveyance_m_s,
                            perfect_sink_mask=raingrid_perfect_sink,
                        )["peak_depth"]
                    # Drop sub-0.5 ha noise speckle; keep coherent pools.
                    depth = denoise_min_cluster(
                        peak, wet_threshold_m=0.05,
                        min_cluster_cells=6).astype(np.float32)
                    # Depth-aware floor: strip cells below the wet threshold so a
                    # spatially CONTINUOUS sub-5cm sheet (which survives cluster
                    # denoise on a flat delta) cannot inflate wet-area summaries
                    # (limitations #2). No-op on steep terrain (KL/SG).
                    depth = apply_depth_floor(depth, floor_m=0.05)
            elif pluvial_model == "fillspill":
                # `level_m` for pluvial rows is excess_depth_m (m).
                assert pluvial_topo is not None, (
                    "pluvial_topo must be built before routing — the build "
                    "guard and dispatch guard have diverged"
                )
                depth = route_pluvial_rp(pluvial_topo, level_m, runoff_coeff_arr)
            else:
                # Depression-filling ponding model (legacy).
                # Sea pixels are NaN in dem_land so the ocean does not form a
                # spurious mega-depression.  No BFS filter is applied because the
                # depression geometry already constrains each ponding cell to its
                # enclosed hollow.
                depth = flood_depth_pluvial_ponding(dem_land, level_m, profile)

        elif hazard == "coastal" and sea_mask is not None and coastal_solver == "inertial":
            # 2D local inertia solver with time-varying surge hydrograph BC.
            # The synthetic surge ramps to peak over 3 h, holds for 1 h, then
            # recedes over 2 h.
            #
            # Warm-start strategy (two stacked initialisers):
            #   1. subsea_init   — pre-floods below-sea-level land pixels to MSL
            #      so the solver starts from steady state rather than a dry shock.
            #   2. _prev_coastal_depth — reuses the prior RP's peak depth so the
            #      solver only needs to resolve the incremental surge increment.
            # Either or both may be None (falls back to cold-start).
            if _prev_coastal_depth is not None:
                # Combine: prior RP depth as base, elevated by subsea baseline
                # where applicable.  Take element-wise max so neither source
                # reduces a cell that the other already filled.
                init_depth = np.maximum(
                    _prev_coastal_depth.astype(np.float64),
                    subsea_init if subsea_init is not None else 0.0,
                )
                start_label = "warm-start (prev RP + subsea pre-flood)"
            elif subsea_init is not None:
                init_depth = subsea_init
                start_label = "warm-start (subsea pre-flood)"
            else:
                init_depth = None
                start_label = "cold-start"

            dx = abs(profile["transform"].a)
            dy = abs(profile["transform"].e)
            # Permanent still-water floor = MSL + SLR (this row's coastal_delta_m).
            # The surge recedes to this floor, not to 0, so SLR inundation persists.
            slr_m = float(getattr(row, "coastal_delta_m", 0.0) or 0.0)
            coastal_floor = coastal_msl_egm2008 + slr_m
            wl_fn = _surge_hydrograph(level_m, floor_wse=coastal_floor)
            click.echo(
                f"  Running inertial solver for coastal RP{rp} "
                f"(peak_wl={level_m:.3f} m, floor_wl={coastal_floor:.3f} m "
                f"[MSL {coastal_msl_egm2008:.2f} + SLR {slr_m:.2f}], surge hydrograph, "
                f"t_end={inertial_t_end/3600:.1f}h, dt_max={inertial_dt_max}s, "
                f"{start_label}) ..."
            )
            # When the asymmetric floor hydrograph is active (floor > 0), force
            # the solver to run to t_end by disabling early convergence: the
            # gentle ramp produces sub-tol per-step changes that would trigger
            # premature exit before the surge ramp or the SLR-floor recession
            # have happened — the solver would just inherit the warm-start
            # state and never simulate the new BC.
            _use_floor = coastal_floor > 1e-6
            _conv_window = 1_000_000 if _use_floor else 100
            result = run_inertial(
                z=dem.astype(np.float64),
                sea_mask=sea_mask,
                wl_boundary=wl_fn,
                initial_depth=init_depth,
                n=0.06,
                dx=dx,
                dy=dy,
                t_end=inertial_t_end,
                dt_max=inertial_dt_max,
                convergence_tol=inertial_convergence_tol,
                convergence_window=_conv_window,
                progress_interval=1000,
                compute_velocity=False,    # peak_velocity unused here; skip for speed
            )
            depth = result["peak_depth"]
            # Post-hoc physical cap: in the local-inertial scheme, narrow inlets
            # and sharp coastal gradients can produce localised numerical wave
            # amplification during the sustained peak hold, leaving a few cells
            # with depths exceeding the physical maximum (peak_WSE - bed).  Cap
            # at peak_WSE - max(0, bed) plus a small velocity-head margin (0.2 m
            # ≈ 0.5*v²/g for v=2 m/s).  Removes the artefacts without altering
            # the bulk extent or genuine physical depths.
            _bed = np.where(np.isfinite(dem), dem.astype(np.float32), 0.0)
            _phys_cap = np.maximum(0.0, float(level_m) - np.maximum(0.0, _bed)) + 0.2
            depth = np.minimum(depth, _phys_cap.astype(np.float32))
            depth[~np.isfinite(dem)] = np.nan
            _prev_coastal_depth = depth  # seed next RP warm-start

        elif hazard == "coastal":
            # Bathtub fallback: used when (a) no sea mask is available, or
            # (b) --coastal-solver bathtub is specified (fast screening mode).
            if sea_mask is not None and coastal_solver == "bathtub":
                click.echo(
                    f"  Coastal RP{rp}: bathtub solver "
                    f"(peak_wl={level_m:.3f} m) ..."
                )
            depth = flood_depth_bathtub(dem, level_m)

        else:
            # Fluvial bathtub (no HAND raster).
            # Use the original DEM (sea cells at z≈0) so that sea pixels carry
            # positive depth (level_m − 0 = level_m) and act as valid BFS seeds.
            # Using dem_land (sea=NaN) gives NaN depth at sea cells, making
            # them inactive in the flooded mask and leaving the BFS with no seeds.
            depth = flood_depth_bathtub(dem, level_m)

        # --- Connectivity filter --------------------------------------------
        # Coastal (inertial) : solver handles connectivity intrinsically — skip BFS.
        # Coastal (bathtub)  : BFS required to remove isolated inland cells not
        #   hydraulically connected to the sea.  Seeds from sea_mask | tidal_seeds.
        # Fluvial (HAND) : skip — D8 flow-path topology guarantees connectivity.
        #   BFS would fail because HAND is only defined within the watershed,
        #   leaving boundary cells as NaN with no valid seeds.
        # Fluvial (bathtub, sea_mask) : seed from sea pixels.  dem_land has sea
        #   cells set to NaN so raster-boundary seeds are all NaN-depth and
        #   invalid; using sea_mask as seeds restores the pre-sea-mask behaviour
        #   where coastal cells at z≈0 seeded the bathtub flood propagation.
        # Fluvial (bathtub, no sea_mask) : fall back to raster boundary seeds or
        #   a user-supplied seed raster.
        # Pluvial (ponding) : skip — depression geometry is self-contained.
        skip_bfs = (
            (hazard == "coastal" and sea_mask is not None and coastal_solver == "inertial")
            or (hazard == "pluvial" and sea_mask is not None)
            or (hazard == "fluvial" and hand_array is not None)
        )
        if not skip_bfs:
            if hazard == "coastal" and sea_mask is not None:
                # Combine sea pixels, tidal channel seeds, and any explicit
                # lat/lon seed points (e.g. Manila Bay) so BFS propagates from
                # all hydraulically-relevant sources.
                effective_seed = sea_mask
                if tidal_seeds is not None:
                    effective_seed = effective_seed | tidal_seeds
                if latlon_seed_mask is not None:
                    effective_seed = effective_seed | latlon_seed_mask
            elif hazard == "fluvial" and sea_mask is not None and seed_mask is None:
                # Bathtub fluvial with sea mask: seed from sea pixels so BFS can
                # propagate inland.  Without this, all boundary cells are NaN in
                # dem_land and the BFS finds no valid seeds.
                effective_seed = sea_mask
            else:
                effective_seed = seed_mask  # user raster or None → boundary
            depth = apply_connectivity_filter(
                depth,
                connectivity=int(connectivity_neighbors),
                seed_water_mask=effective_seed,
            )

        # Zero out sea pixel depths so ocean does not appear in outputs
        if sea_mask is not None:
            depth = np.where(sea_mask, 0.0, depth)

        severity = classify_depth_severity(depth)

        hazard_dir = out_dir / hazard / f"rp_{rp}"
        depth_path = hazard_dir / f"{hazard}_depth_{scenario}_{horizon}_rp{rp}.tif"
        sev_path = hazard_dir / f"{hazard}_severity_{scenario}_{horizon}_rp{rp}.tif"
        write_depth_raster(depth, profile, depth_path)
        write_severity_raster(severity, profile, sev_path)

        depth_stats = summarize_depth(depth, transform, crs)
        sev_stats = severity_area_stats(severity, transform, crs)
        summary_rows.append(
            {
                "hazard_type": hazard,
                "return_period": rp,
                "scenario": scenario,
                "horizon": horizon,
                "water_level_m": level_m,
                "depth_raster": str(depth_path),
                "severity_raster": str(sev_path),
                **depth_stats,
                **sev_stats,
            }
        )
        click.echo(f"Wrote {hazard} RP{rp}: {depth_path}")

    summary_df = pd.DataFrame(summary_rows).sort_values(["hazard_type", "return_period"])
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = out_dir / f"summary_{scenario}_{horizon}.csv"
    summary_df.to_csv(summary_csv, index=False)
    click.echo(f"Wrote summary: {summary_csv}")


if __name__ == "__main__":
    cli()
