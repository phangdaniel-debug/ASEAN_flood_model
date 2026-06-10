"""
Generic multi-hazard flood pipeline runner.

Runs the full pipeline — ERA5 baseline fits, DEM download, sea mask,
hazard-level table, flood model, combined maps, street overlay — for any
city defined in scripts/cities.py.

Usage
-----
    # Run with all defaults (SSP5-8.5, 2100, median)
    python scripts/run_city_pipeline.py --city kuala_lumpur

    # Run for Bangkok, SSP2-4.5, 2050, 95th-percentile sea-level
    python scripts/run_city_pipeline.py \\
        --city bangkok --scenario SSP2-4.5 --horizon 2050 --percentile 95

    # Skip the ERA5 download step (reuse cached precipitation)
    python scripts/run_city_pipeline.py --city jakarta --no-fit-era5

    # List all configured cities
    python scripts/run_city_pipeline.py --list-cities

Singapore can also be run through this script; it produces identical output
to run_singapore_pipeline.py (which is kept for backward compatibility).

Output layout
-------------
    outputs/<city_slug>_<scenario_slug>_<horizon>/
        coastal/rp_N/coastal_depth_*.tif
        fluvial/rp_N/fluvial_depth_*.tif
        pluvial/rp_N/pluvial_depth_*.tif
        map_combined_*.png
        street_overlay/map_combined_streets_*.png

    data/<city_slug>/
        copernicus_dem_<utm_zone>.tif
        sea_mask_<utm_zone>.tif
        hand_<utm_zone>.tif           (if OSM river data available)
        hazard_baseline_template.csv  (pre-populated; updated by ERA5 fits)
        hazard_levels_<scenario>_<horizon>.csv
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.cities import CITIES, CityConfig

# Warming deltas (°C, near-term/long-term temperature change relative to
# 1995-2014) from IPCC AR6 WGI Table SPM.1 / Cross-Chapter Box 11.1 and
# the AR6 Interactive Atlas (https://interactive-atlas.ipcc.ch).  Values
# are mid-range central estimates rounded to 0.1 °C; the 1995-2014 → 2020
# increment (~0.05 °C) is treated as negligible and absorbed into the
# user-facing 2020 baseline.
#
# Two regional tables are provided:
#
#   GSAT (default) — global mean surface air temperature, AR6 SPM:
#     SSP2-4.5: 2021-2040 ≈ +1.0; 2081-2100 ≈ +2.1
#     SSP5-8.5: 2021-2040 ≈ +1.5; 2081-2100 ≈ +4.0
#
#   SEA — AR6 Atlas Southeast Asia region (land + ocean), median CMIP6:
#     SSP2-4.5: 2021-2040 ≈ +0.9; 2081-2100 ≈ +1.9
#     SSP5-8.5: 2021-2040 ≈ +1.3; 2081-2100 ≈ +3.5
#   (SE Asia warms ~85-90 % of GSAT due to tropical-maritime damping.)
#
# Pass --delta-T-region SEA to opt into the regional values, or supply
# --delta-T directly for full control.
_DELTA_T_TABLE_GSAT: dict[tuple[str, int], float] = {
    ("SSP2-4.5", 2050): 1.0,
    ("SSP2-4.5", 2100): 2.1,
    ("SSP5-8.5", 2050): 1.5,
    ("SSP5-8.5", 2100): 4.0,
}
_DELTA_T_TABLE_SEA: dict[tuple[str, int], float] = {
    ("SSP2-4.5", 2050): 0.9,
    ("SSP2-4.5", 2100): 1.9,
    ("SSP5-8.5", 2050): 1.3,
    ("SSP5-8.5", 2100): 3.5,
}
_DELTA_T_TABLES: dict[str, dict[tuple[str, int], float]] = {
    "GSAT": _DELTA_T_TABLE_GSAT,
    "SEA": _DELTA_T_TABLE_SEA,
}
# Backward-compat alias (existing code paths reference _DELTA_T_TABLE).
_DELTA_T_TABLE = _DELTA_T_TABLE_GSAT


def _run(cmd: list[str]) -> None:
    click.echo(f"\nRunning: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise click.ClickException(
            f"Command failed (exit {result.returncode}): {' '.join(cmd)}"
        )


def _scenario_slug(scenario: str) -> str:
    """'SSP5-8.5' → 'ssp585'  (safe for directory names)."""
    return scenario.lower().replace("-", "").replace(".", "")


def _utm_tag(crs: str) -> str:
    """'EPSG:32648' → 'utm48n'  (used in default file names)."""
    code = crs.split(":")[-1]
    zone_num = int(code[-2:])
    hemisphere = "s" if int(code) >= 32700 else "n"
    return f"utm{zone_num}{hemisphere}"


@click.command()
@click.option(
    "--city",
    "city_slug",
    required=False,
    default=None,
    help="City slug to run (see --list-cities for options).",
)
@click.option("--list-cities", is_flag=True, default=False, help="Print available cities and exit.")
@click.option("--scenario", default="SSP5-8.5", show_default=True, help="Climate scenario.")
@click.option("--horizon", type=int, default=2100, show_default=True, help="Climate horizon year.")
@click.option("--percentile", type=float, default=50.0, show_default=True,
              help="Sea-level projection percentile (0–100).")
@click.option("--baseline-year", type=int, default=2020, show_default=True)
@click.option(
    "--delta-T", "delta_T", type=float, default=None,
    help="Warming (°C) for GEV-CC scaling.  Inferred from AR6 table when omitted.",
)
@click.option(
    "--delta-T-region",
    "delta_T_region",
    type=click.Choice(["GSAT", "SEA"], case_sensitive=False),
    default="GSAT",
    show_default=True,
    help=(
        "Reference table for AR6 warming deltas: "
        "GSAT = global mean SAT (Table SPM.1); "
        "SEA = AR6 Atlas Southeast Asia regional median (recommended for "
        "tropical-maritime ASEAN cities)."
    ),
)
@click.option(
    "--fit-era5/--no-fit-era5", "fit_era5", default=True, show_default=True,
    help="Download ERA5 precipitation and refit both pluvial and fluvial baselines.  "
         "Disable to reuse cached data.  Overridden by --fit-pluvial/--fit-fluvial.",
)
@click.option(
    "--fit-pluvial/--no-fit-pluvial", "fit_pluvial_override", default=None,
    help="Override --fit-era5 for pluvial only.  "
         "Defaults to --fit-era5 value when not specified.",
)
@click.option(
    "--fit-fluvial/--no-fit-fluvial", "fit_fluvial_override", default=None,
    help="Override --fit-era5 for fluvial only.  "
         "Defaults to --fit-era5 value when not specified.  "
         "Fluvial baseline now uses ERA5-Land via Open-Meteo (same source as pluvial).",
)
@click.option(
    "--fit-glofas/--no-fit-glofas", "fit_glofas_override", default=None,
    help=(
        "Fetch GloFAS discharge and fit fluvial baseline (replaces ERA5 fluvial). "
        "Auto-enabled when city.glofas_lat is set. Disable with --no-fit-glofas."
    ),
)
@click.option(
    "--fit-coastal/--no-fit-coastal", "fit_coastal", default=True, show_default=True,
    help=(
        "Fetch UHSLC tide-gauge data and refit coastal baseline.  "
        "Disabled automatically when uhslc_id is None for the city.  "
        "Disable manually to reuse existing coastal rows in the template CSV."
    ),
)
@click.option(
    "--connectivity-neighbors",
    type=click.Choice(["4", "8"]),
    default="8",
    show_default=True,
)
@click.option("--target-resolution", type=float, default=30.0, show_default=True,
              help="DEM and flood model grid resolution (m).")
@click.option(
    "--out-root", type=click.Path(path_type=Path), default=Path("outputs"),
    show_default=True,
    help="Root directory for all output folders.",
)
@click.option(
    "--data-root", type=click.Path(path_type=Path), default=Path("data"),
    show_default=True,
    help="Root directory for per-city data files.",
)
@click.option(
    "--fluvial-factor", type=float, default=1.10, show_default=True,
    help="Uniform fluvial scaling factor (fallback when GEV columns absent).",
)
@click.option(
    "--pluvial-factor", type=float, default=1.15, show_default=True,
    help="Uniform pluvial scaling factor (fallback when GEV columns absent).",
)
@click.option(
    "--seed-water-raster", type=click.Path(path_type=Path), default=None,
    help="Optional pre-built water mask raster (>0 = open water).",
)
@click.option(
    "--sea-mask/--no-sea-mask", "build_sea_mask", default=True, show_default=True,
)
@click.option(
    "--coastal-solver",
    "coastal_solver",
    type=click.Choice(["inertial", "bathtub"]),
    default="inertial",
    show_default=True,
    help="Coastal flood solver. 'bathtub' is much faster; 'inertial' is more accurate.",
)
@click.option(
    "--inertial-t-end",
    "inertial_t_end",
    type=float,
    default=28_800.0,
    show_default=True,
    help="Inertial solver duration in seconds (default 8 h). Reduce to 14400 for ~2x speedup.",
)
@click.option(
    "--inertial-convergence-tol",
    "inertial_convergence_tol",
    type=float,
    default=1e-3,
    show_default=True,
    help="Inertial solver early-stop tolerance (m). Default 1e-3 m (1 mm) is "
         "required when the boundary condition is a time-varying surge "
         "hydrograph: looser tolerances trigger spurious early-stops during "
         "the slow ramp-up phase before the surge peak.  "
         "is 150 mm so sub-mm accuracy does not change any outputs.  Tighten "
         "to 1e-4 only when precision of the final water surface matters.",
)
@click.option(
    "--gev-xi-max",
    "gev_xi_max",
    type=float,
    default=0.30,
    show_default=True,
    help="Maximum GEV shape xi for pluvial and fluvial fits. 0.30 caps the Frechet tail "
         "to prevent unrealistic RP200-1000 ponding depths while preserving RP10-100 accuracy.",
)
@click.option(
    "--max-ponding-depth-m",
    "max_ponding_depth_m",
    type=float,
    default=3.0,
    show_default=True,
    help="Physical cap on pluvial ponding depth (m). Prevents unrealistic values from GEV extrapolation.",
)
@click.option(
    "--max-stage-m",
    "max_stage_m",
    type=float,
    default=8.0,
    show_default=True,
    help="Physical cap on fluvial channel stage (m). Prevents unrealistic Manning's depths on flat catchments.",
)
@click.option(
    "--build-river-raster/--no-build-river-raster", "build_river_raster",
    default=True, show_default=True,
    help="Download OSM rivers and build a river mask raster for HAND calculation.",
)
@click.option(
    "--street-overlay/--no-street-overlay", "make_street_overlay",
    default=True, show_default=True,
    help="Generate street-overlay visualisations after the flood maps.",
)
@click.option(
    "--subsidence-correction/--no-subsidence-correction",
    "subsidence_correction",
    default=False,
    show_default=True,
    help=(
        "Apply a zone-based land-subsidence correction to the GLO-30 DEM before "
        "running the flood model.  The corrected DEM is saved alongside the "
        "original as copernicus_dem_<utm>_subsidence_corrected.tif.  "
        "Currently implemented for Jakarta only (zone rates from published "
        "InSAR/GPS literature; see scripts/apply_subsidence_correction.py).  "
        "Has no effect for cities without a subsidence config."
    ),
)
@click.option(
    "--clamp-negative-land/--no-clamp-negative-land",
    "clamp_negative_land",
    default=True,
    show_default=True,
    help=(
        "Clamp below-zero land pixels (radar-shadow / processing artefacts) to "
        "0.0 m before flood routing.  Pass --no-clamp-negative-land when running "
        "a --subsidence-correction config for a city whose polders are genuinely "
        "below MSL (Manila Bay, North Jakarta, HCMC) — clamping zeroes out those "
        "real below-sea-level pixels and substantially under-predicts coastal "
        "flood extent and depth."
    ),
)
@click.option(
    "--flood-defenses/--no-flood-defenses",
    "flood_defenses",
    default=False,
    show_default=True,
    help=(
        "Burn engineered flood-defense crest elevations (dykes, sea walls, "
        "polder rings) into the DEM before running the flood model.  Has no "
        "effect for cities without a defense config in scripts/apply_flood_defenses.py.  "
        "When combined with --subsidence-correction the defenses are burned on "
        "top of the subsidence-corrected DEM.  Output suffix: _defended."
    ),
)
@click.option(
    "--pluvial-model",
    "pluvial_model",
    type=click.Choice(["fillspill", "legacy", "raingrid"]),
    default="fillspill",
    show_default=True,
    help="Pluvial solver passed through to run_multihazard.py.  'raingrid' "
         "additionally builds a bare-earth + hydro-conditioned DEM (Open "
         "Buildings) and routes 2D rain-on-grid flash-flood ponding.",
)
def cli(
    city_slug: str | None,
    list_cities: bool,
    scenario: str,
    horizon: int,
    percentile: float,
    baseline_year: int,
    delta_T: float | None,
    delta_T_region: str,
    fit_era5: bool,
    fit_pluvial_override: bool | None,
    fit_fluvial_override: bool | None,
    fit_glofas_override: bool | None,
    fit_coastal: bool,
    connectivity_neighbors: str,
    target_resolution: float,
    out_root: Path,
    data_root: Path,
    fluvial_factor: float,
    pluvial_factor: float,
    seed_water_raster: Path | None,
    build_sea_mask: bool,
    coastal_solver: str,
    inertial_t_end: float,
    inertial_convergence_tol: float,
    gev_xi_max: float,
    max_ponding_depth_m: float,
    max_stage_m: float,
    build_river_raster: bool,
    make_street_overlay: bool,
    subsidence_correction: bool,
    clamp_negative_land: bool,
    flood_defenses: bool,
    pluvial_model: str,
) -> None:
    if list_cities:
        click.echo("Available cities:")
        for slug, cfg in CITIES.items():
            flag = "" if cfg.uhslc_id else "  [no coastal gauge]"
            click.echo(f"  {slug:20s}  {cfg.name}{flag}")
            if cfg.notes:
                first_line = cfg.notes.split(".")[0] + "."
                click.echo(f"    {first_line}")
        return

    if city_slug is None:
        raise click.UsageError("Provide --city <slug> or use --list-cities.")

    if city_slug not in CITIES:
        available = ", ".join(sorted(CITIES))
        raise click.UsageError(
            f"Unknown city {city_slug!r}.  Available: {available}"
        )

    city: CityConfig = CITIES[city_slug]
    py = sys.executable

    # ------------------------------------------------------------------
    # Derived paths
    # ------------------------------------------------------------------
    utm_tag    = _utm_tag(city.utm_crs)
    scen_slug  = _scenario_slug(scenario)
    city_data  = data_root / city.slug
    out_suffix = "_defended" if flood_defenses else ""
    out_dir    = out_root / f"{city.slug}_{scen_slug}_{horizon}{out_suffix}"
    baseline_csv  = city_data / "hazard_baseline_template.csv"
    dem_path      = city_data / f"copernicus_dem_{utm_tag}.tif"
    hazard_csv    = city_data / f"hazard_levels_{scen_slug}_{horizon}.csv"
    era5_cache_pluvial = Path("cache") / f"era5land_{city.slug}_pluvial.parquet"
    era5_cache_fluvial = Path("cache") / f"era5land_{city.slug}_fluvial.parquet"

    city_data.mkdir(parents=True, exist_ok=True)

    if not baseline_csv.exists():
        raise click.ClickException(
            f"Baseline template not found: {baseline_csv}\n"
            f"Create it by copying data/singapore_hazard_baseline_template.csv "
            f"and adjusting the coastal placeholder rows, or run "
            f"fetch_uhslc_gauge.py first."
        )

    click.echo(f"\n{'='*60}")
    click.echo(f"  City      : {city.name}")
    click.echo(f"  Scenario  : {scenario}  Horizon: {horizon}  P{percentile:.0f}")
    click.echo(f"  Output    : {out_dir}")
    click.echo(f"{'='*60}")

    if city.notes:
        # Encode to stdout safely on Windows cp1252 terminals by replacing
        # unmappable Unicode characters (e.g. ≈ U+2248, → U+2192) with '?'.
        notes_safe = city.notes.encode(
            "ascii", errors="replace"
        ).decode("ascii")
        click.echo(f"\n[city notes] {notes_safe}\n")

    # ------------------------------------------------------------------
    # 0. Coastal tide-gauge baseline
    # ------------------------------------------------------------------
    if fit_coastal and city.uhslc_id is not None:
        click.echo("\n=== Step 0: Fetch coastal tide-gauge baseline ===")
        _run([
            py, str(PROJECT_ROOT / "scripts" / "fetch_uhslc_gauge.py"),
            "--dataset",      city.uhslc_dataset,
            "--uhslc-id",     str(city.uhslc_id),
            "--gauge-name",   city.uhslc_gauge_name,
            "--start-year",   str(city.uhslc_start_year),
            "--end-year",     str(city.uhslc_end_year),
            "--msl-to-egm2008-offset", str(city.msl_to_egm2008_offset),
            "--output",       str(baseline_csv),
        ])
    elif city.uhslc_id is None:
        click.echo(
            "\n[skip] No UHSLC station configured for this city.  "
            "Coastal rows in the baseline CSV will be used as-is.  "
            "Populate them manually from national tide-gauge data if required."
        )
    else:
        click.echo("\n[skip] --no-fit-coastal: reusing existing coastal rows.")

    # Resolve per-hazard fit flags.
    # --fit-pluvial/--no-fit-pluvial overrides --fit-era5 for pluvial.
    # --fit-fluvial/--no-fit-fluvial overrides --fit-era5 for fluvial.
    # Both now default to fit_era5 after the ERA5-Land fluvial migration.
    do_fit_pluvial = fit_era5 if fit_pluvial_override is None else fit_pluvial_override
    # GloFAS: auto-enable when coordinates configured; supersedes ERA5 fluvial.
    do_fit_glofas = (city.glofas_lat is not None) if fit_glofas_override is None else fit_glofas_override
    # ERA5 fluvial is suppressed when GloFAS runs (unless user forces --fit-fluvial).
    do_fit_fluvial = fit_era5 if fit_fluvial_override is None else fit_fluvial_override
    if do_fit_glofas and fit_fluvial_override is None:
        do_fit_fluvial = not do_fit_glofas  # suppress ERA5 fluvial when GloFAS is active

    # ------------------------------------------------------------------
    # 0a. Pluvial baseline (ERA5-Land via Open-Meteo)
    # ------------------------------------------------------------------
    if do_fit_pluvial:
        click.echo("\n=== Step 0a: Fit pluvial baseline (ERA5-Land) ===")
        _run([
            py, str(PROJECT_ROOT / "scripts" / "fit_pluvial_baseline_era5.py"),
            "--lat",                       str(city.era5_lat),
            "--lon",                       str(city.era5_lon),
            "--drain-capacity-mm",         str(city.drain_capacity_mm),
            "--runoff-coeff",              str(city.runoff_coeff),
            "--depression-area-fraction",  str(city.depression_area_fraction),
            "--xi-max",                    str(gev_xi_max),
            "--max-ponding-depth-m",       str(max_ponding_depth_m),
            "--cache-precip",              str(era5_cache_pluvial),
            "--output",                    str(baseline_csv),
        ])
    else:
        click.echo("\n[skip] --no-fit-pluvial: reusing existing pluvial baseline rows.")

    # ------------------------------------------------------------------
    # 0b. Fluvial baseline (ERA5-Land via Open-Meteo)
    # ------------------------------------------------------------------
    if do_fit_fluvial:
        click.echo("\n=== Step 0b: Fit fluvial baseline (ERA5-Land) ===")
        _run([
            py, str(PROJECT_ROOT / "scripts" / "fit_fluvial_baseline_era5.py"),
            "--lat",            str(city.era5_lat),
            "--lon",            str(city.era5_lon),
            "--curve-number",   str(city.cn),
            "--catchment-km2",  str(city.catchment_km2),
            "--time-of-conc",   str(city.time_of_conc_h),
            "--channel-width",  str(city.channel_width_m),
            "--mannings-n",     str(city.mannings_n),
            "--channel-slope",  str(city.channel_slope),
            "--xi-max",         str(gev_xi_max),
            "--max-stage-m",    str(max_stage_m),
            "--cache-precip",   str(era5_cache_fluvial),
            "--output",         str(baseline_csv),
        ])
    else:
        click.echo("\n[skip] --no-fit-fluvial: reusing existing fluvial baseline rows.")

    # ------------------------------------------------------------------
    # 0c. GloFAS fluvial baseline (cities with glofas_lat configured)
    # ------------------------------------------------------------------
    if do_fit_glofas:
        if city.glofas_lat is None:
            click.echo(
                "\n[skip] --fit-glofas: no glofas_lat configured for "
                f"'{city.slug}'. Add coordinates to CityConfig first."
            )
        else:
            click.echo("\n=== Step 0c: Fit fluvial baseline (GloFAS via Open-Meteo) ===")
            glofas_cmd = [
                py, str(PROJECT_ROOT / "scripts" / "fit_fluvial_glofas.py"),
                "--city",        city.slug,
                "--xi-max",      str(gev_xi_max),
                "--max-stage-m", str(max_stage_m),
                "--output",      str(baseline_csv),
            ]
            if city.glofas_discharge_scale != 1.0:
                glofas_cmd += ["--discharge-scale", str(city.glofas_discharge_scale)]
            if city.glofas_bankfull_discharge_m3s is not None:
                glofas_cmd += ["--bankfull-discharge", str(city.glofas_bankfull_discharge_m3s)]
            _run(glofas_cmd)
    else:
        if city.glofas_lat is not None:
            click.echo("\n[skip] --no-fit-glofas: reusing existing GloFAS fluvial rows.")

    if not do_fit_pluvial and not do_fit_fluvial:
        click.echo("\n[skip] --no-fit-era5: reusing all existing ERA5 baseline rows.")

    # ------------------------------------------------------------------
    # 1. Fetch Copernicus DEM
    # ------------------------------------------------------------------
    click.echo("\n=== Step 1: Fetch Copernicus GLO-30 DEM ===")
    _run([
        py, str(PROJECT_ROOT / "scripts" / "fetch_copernicus_dem.py"),
        "--min-lon", str(city.min_lon),
        "--min-lat", str(city.min_lat),
        "--max-lon", str(city.max_lon),
        "--max-lat", str(city.max_lat),
        "--target-crs",        city.utm_crs,
        "--target-resolution", str(target_resolution),
        "--output",            str(dem_path),
    ])

    # ------------------------------------------------------------------
    # 1a. Subsidence correction (optional, Jakarta only for now)
    # ------------------------------------------------------------------
    # Slugs that have a zone config in apply_subsidence_correction.py.
    _SUBSIDENCE_SUPPORTED = {
        "jakarta", "tangerang", "bekasi_depok",
        "manila", "hcmc",
        "bangkok", "bangkok_chao_phraya",
    }

    # Cities that must use the bathtub coastal solver.
    # Manila Bay and HCMC's Mekong Delta coast are fully enclosed within the
    # DEM domain: the NaN-boundary sea-mask cells are surrounded by z >= 2 m
    # terrain and have no continuous z <= 0 path to the bay/delta.  The inertial
    # solver's wall-condition (zero flux across NaN cell interfaces) therefore
    # prevents any surge from reaching the coastal flood zone, yielding 0 km²
    # for every return period.  The bathtub + BFS model propagates through
    # the z < water_level interior correctly and is used instead.
    _BATHTUB_COASTAL_CITIES = {"manila", "hcmc"}

    # Cities with open-water bodies enclosed within the DEM domain that a
    # boundary-seeded BFS cannot reach.  Two separate uses:
    #
    # _SEA_MASK_SEEDS -> build_sea_mask.py --seed-latlon (Step 3).  Each entry
    #   classifies a water body as sea so it is excluded from ALL hazards.
    #   "lat,lon"         = enclosed sea basin (<=0 m), e.g. Manila Bay.
    #   "lat,lon,maxelev" = elevated inland lake, e.g. Laguna de Bay (~1.0 m
    #                       surface; GLO-30 stores it above MSL so no 0-m
    #                       pass reaches it -- a dedicated dem<=maxelev BFS
    #                       fills its well-bounded ~395 km² component).
    #
    # _COASTAL_SEED_LATLON -> run_multihazard.py --coastal-seed-latlon.  Only
    #   true sea basins belong here (the coastal solver propagates surge from
    #   these seeds); a freshwater lake must NOT seed coastal surge, so Laguna
    #   appears in _SEA_MASK_SEEDS only.  Entries are strictly "lat,lon".
    _SEA_MASK_SEEDS: dict[str, list[str]] = {
        "manila": [
            "14.5,120.9",          # interior of Manila Bay (enclosed sea)
            "14.41,121.15,2.0",    # Laguna de Bay (elevated freshwater lake)
        ],
        "hcmc": [
            # Saigon/Nha Be/Soai Rap delta tidal-channel network: the main
            # <=0 m water body (~122 km²) is enclosed within the domain --
            # the open sea lies south of the southern edge, so no <=0 m
            # path reaches a raster boundary.
            "10.66780,106.79134",  # main Saigon-Nha Be delta channel network
            "10.64732,106.45205",  # western Vam Co distributary channels
        ],
    }
    _COASTAL_SEED_LATLON: dict[str, list[str]] = {
        "manila": ["14.5,120.9"],   # interior of Manila Bay (within DEM extents)
    }
    if subsidence_correction and city.slug in _SUBSIDENCE_SUPPORTED:
        click.echo("\n=== Step 1a: Apply land-subsidence correction to DEM ===")
        corrected_dem_path = city_data / f"copernicus_dem_{utm_tag}_subsidence_corrected.tif"
        _run([
            py, str(PROJECT_ROOT / "scripts" / "apply_subsidence_correction.py"),
            "--dem",    str(dem_path),
            "--city",   city.slug,
            "--output", str(corrected_dem_path),
        ])
        dem_path = corrected_dem_path
        click.echo(f"[info] Downstream steps will use corrected DEM: {dem_path}")
    elif subsidence_correction and city.slug not in _SUBSIDENCE_SUPPORTED:
        click.echo(
            f"\n[skip] --subsidence-correction: no zone config for '{city.slug}'. "
            "Using original GLO-30 DEM."
        )

    # The sea mask answers "what is ocean" — a geographic fact unaffected by
    # engineered defenses.  Capture the pre-defense DEM (subsidence-corrected
    # if that step ran) so Step 3 derives the sea mask from it.  Deriving the
    # sea mask from the defended DEM lets a burned dyke / tide-gate ridge sever
    # a tidal channel from the open sea in the BFS, flipping that water
    # sea -> land and producing spurious below-MSL "flooding" at every RP.
    sea_mask_dem_path = dem_path

    # ------------------------------------------------------------------
    # 1b. Flood-defense crest burn-in (optional, per-city config)
    # ------------------------------------------------------------------
    if flood_defenses:
        # Lazy import to avoid loading shapely/pyproj when not needed.
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        try:
            from apply_flood_defenses import DEFENSE_CONFIGS as _DEF_CFGS
        except Exception as exc:
            click.echo(f"[error] could not import apply_flood_defenses: {exc}", err=True)
            sys.exit(2)
        if city.slug in _DEF_CFGS:
            click.echo("\n=== Step 1b: Apply flood-defense crest burn-in ===")
            defended_dem_path = dem_path.with_name(dem_path.stem + "_defended.tif")
            _run([
                py, str(PROJECT_ROOT / "scripts" / "apply_flood_defenses.py"),
                "--city",   city.slug,
                "--dem",    str(dem_path),
                "--output", str(defended_dem_path),
            ])
            dem_path = defended_dem_path
            click.echo(f"[info] Downstream steps will use defended DEM: {dem_path}")
        else:
            click.echo(
                f"\n[skip] --flood-defenses: no defense config for '{city.slug}' "
                "in scripts/apply_flood_defenses.py."
            )

    # ------------------------------------------------------------------
    # 2. Build scenario hazard levels (applies climate delta)
    # ------------------------------------------------------------------
    click.echo("\n=== Step 2: Build scenario hazard levels ===")
    region_key = (delta_T_region or "GSAT").upper()
    region_table = _DELTA_T_TABLES.get(region_key, _DELTA_T_TABLE_GSAT)
    effective_delta_T = (
        delta_T if delta_T is not None else region_table.get((scenario, horizon))
    )
    if delta_T is None and effective_delta_T is not None:
        click.echo(
            f"[info] delta_T source: AR6 {region_key} table "
            f"({scenario}/{horizon}) = {effective_delta_T} °C."
        )
    build_levels_cmd = [
        py, str(PROJECT_ROOT / "scripts" / "build_hazard_levels.py"),
        "--baseline-hazards", str(baseline_csv),
        "--scenario",         scenario,
        "--horizon",          str(horizon),
        "--lat",              str(city.era5_lat),
        "--lon",              str(city.era5_lon),
        "--percentile",       str(percentile),
        "--baseline-year",    str(baseline_year),
        "--fluvial-factor",   str(fluvial_factor),
        "--pluvial-factor",   str(pluvial_factor),
        "--output",           str(hazard_csv),
    ]
    if effective_delta_T is not None:
        click.echo(f"[info] Using delta_T={effective_delta_T} °C for GEV-CC scaling.")
        build_levels_cmd.extend(["--delta-T", str(effective_delta_T)])
    _run(build_levels_cmd)

    # ------------------------------------------------------------------
    # 3. Sea mask
    # ------------------------------------------------------------------
    _default_sea_mask = city_data / f"sea_mask_{utm_tag}.tif"
    sea_mask_raster: Path | None = None
    if build_sea_mask:
        click.echo("\n=== Step 3: Build sea mask ===")
        sea_mask_raster = _default_sea_mask
        build_sea_cmd = [
            py, str(PROJECT_ROOT / "scripts" / "build_sea_mask.py"),
            # Pre-defense DEM: defenses must not redefine what is ocean.
            "--dem",    str(sea_mask_dem_path),
            "--output", str(sea_mask_raster),
        ]
        # Cities with a bay/lake enclosed inside the DEM domain need interior
        # BFS seeds so the enclosed open water is classified as sea (otherwise
        # it is mis-labelled land -> spurious coastal/pluvial flooding over
        # the water body).
        for _seed_latlon in _SEA_MASK_SEEDS.get(city.slug, []):
            build_sea_cmd.extend(["--seed-latlon", _seed_latlon])
        _run(build_sea_cmd)
    elif _default_sea_mask.exists():
        click.echo(f"[info] Reusing pre-built sea mask: {_default_sea_mask}")
        sea_mask_raster = _default_sea_mask

    # ------------------------------------------------------------------
    # 3b. ESA WorldCover runoff-coefficient raster (for fill-spill pluvial)
    # ------------------------------------------------------------------
    runoff_coeff_raster: Path | None = None
    if pluvial_model in ("fillspill", "raingrid"):
        runoff_coeff_raster = city_data / f"runoff_coeff_{utm_tag}.tif"
        if runoff_coeff_raster.exists():
            click.echo(f"[info] Reusing runoff-coeff raster: {runoff_coeff_raster}")
        else:
            click.echo("\n=== Step 3b: Fetch ESA WorldCover runoff coefficient ===")
            _run([
                py, str(PROJECT_ROOT / "scripts" / "fetch_esa_worldcover.py"),
                "--dem",    str(dem_path),
                "--output", str(runoff_coeff_raster),
            ])

    # ------------------------------------------------------------------
    # 4. OSM river raster + HAND
    # ------------------------------------------------------------------
    river_raster: Path | None = None
    hand_raster: Path | None = None
    # HAND is derived from the (defended) DEM, so defended and undefended runs
    # produce different HAND rasters.  Suffix the defended one (out_suffix is
    # "_defended" when --flood-defenses is set, "" otherwise) so the two
    # scenarios do not overwrite each other in data/.  sea_mask, river_mask and
    # runoff_coeff are scenario-independent — sea_mask is built from the
    # pre-defense DEM, and the other two do not depend on DEM elevations — so
    # they stay unsuffixed and shared between scenarios.
    default_hand = city_data / f"hand_{utm_tag}{out_suffix}.tif"

    _default_river_mask = city_data / f"river_mask_{utm_tag}.tif"
    if build_river_raster:
        click.echo("\n=== Step 4a: Build OSM river raster ===")
        river_raster = _default_river_mask
        # Use city.osm_query_name when set (e.g. "Metro Manila" for Manila,
        # where city.name resolves to Manila City proper, not the full NCR).
        # Fall back to city.name for cities where the display name resolves
        # correctly via Nominatim.
        osm_place = city.osm_query_name if city.osm_query_name else city.name
        _run([
            py, str(PROJECT_ROOT / "scripts" / "build_river_raster_from_osm.py"),
            "--dem",    str(dem_path),
            "--place",  osm_place,
            "--output", str(river_raster),
        ])
    elif _default_river_mask.exists():
        click.echo(f"[info] Reusing pre-built river mask: {_default_river_mask}")
        river_raster = _default_river_mask

    if river_raster is not None and river_raster.exists():
        click.echo("\n=== Step 4b: Build HAND raster ===")
        hand_raster = default_hand
        _run([
            py, str(PROJECT_ROOT / "scripts" / "build_hand_raster.py"),
            "--dem",          str(dem_path),
            "--river-raster", str(river_raster),
            "--output",       str(hand_raster),
        ])
    elif default_hand.exists():
        click.echo(f"[info] Reusing pre-built HAND raster: {default_hand}")
        hand_raster = default_hand

    # ------------------------------------------------------------------
    # 4c. Bare-earth + hydro-conditioned DEM (rain-on-grid pluvial only)
    # ------------------------------------------------------------------
    # GLO-30 is a DSM: in dense urban areas buildings create elevation noise
    # and inter-building voids that fragment any pluvial model into spurious
    # micro-pits.  For rain-on-grid we route on a bare-earth DEM (buildings
    # removed via Open Buildings) that is then hydrologically conditioned
    # (drainage burned, noise pits filled, lightly smoothed).  Used for pluvial
    # only; coastal/fluvial stay on the GLO-30 DEM.
    pluvial_dem_raster: Path | None = None
    if pluvial_model == "raingrid":
        building_cov = city_data / f"building_coverage_{utm_tag}.tif"
        if building_cov.exists():
            click.echo(f"[info] Reusing building-coverage raster: {building_cov}")
        else:
            click.echo("\n=== Step 4c: Fetch Open Buildings coverage ===")
            _run([
                py, str(PROJECT_ROOT / "scripts" / "fetch_open_buildings.py"),
                "--dem",    str(dem_path),
                "--output", str(building_cov),
            ])
        bareearth_dem = dem_path.with_name(dem_path.stem + "_bareearth.tif")
        click.echo("\n=== Step 4d: Build bare-earth DEM ===")
        _run([
            py, str(PROJECT_ROOT / "scripts" / "build_bareearth_dem.py"),
            "--dem",               str(dem_path),
            "--building-coverage", str(building_cov),
            "--output",            str(bareearth_dem),
        ])
        pluvial_dem_raster = dem_path.with_name(dem_path.stem + "_conditioned.tif")
        raingrid_dem = dem_path.with_name(dem_path.stem + "_raingrid.tif")
        click.echo("\n=== Step 4e: Hydro-condition DEM for pluvial routing ===")
        cond_cmd = [
            py, str(PROJECT_ROOT / "scripts" / "build_conditioned_dem.py"),
            "--dem",     str(bareearth_dem),
            "--output",  str(pluvial_dem_raster),
            "--raingrid-out", str(raingrid_dem),
        ]
        if sea_mask_raster is not None:
            cond_cmd.extend(["--sea-mask", str(sea_mask_raster)])
        if river_raster is not None and river_raster.exists():
            cond_cmd.extend(["--drainage-raster", str(river_raster)])
        _run(cond_cmd)
        # Rain-on-grid uses the surgically de-pitted DEM (artifact + >=3 m pits
        # filled) to prevent unbounded ponding in DSM holes; fill-spill keeps the
        # _conditioned DEM. See specs/2026-05-31-raingrid-depressionless-dem-design.md
        if raingrid_dem.exists():
            pluvial_dem_raster = raingrid_dem

    # ------------------------------------------------------------------
    # 5. Run flood model
    # ------------------------------------------------------------------
    # Override coastal solver for cities where the inertial solver cannot work
    # (bay / delta fully enclosed inside the DEM domain, no NaN-adjacent path).
    if city.slug in _BATHTUB_COASTAL_CITIES and coastal_solver == "inertial":
        click.echo(
            f"[info] {city.name}: switching coastal solver to 'bathtub' — "
            "Manila Bay / Mekong Delta are enclosed within the DEM domain; "
            "the inertial solver's wall condition prevents surge propagation. "
            "Pass --coastal-solver inertial to override."
        )
        coastal_solver = "bathtub"

    click.echo("\n=== Step 5: Run multi-hazard flood model ===")
    run_model_cmd = [
        py, str(PROJECT_ROOT / "scripts" / "run_multihazard.py"),
        "--dem",            str(dem_path),
        "--hazard-levels",  str(hazard_csv),
        "--scenario",       scenario,
        "--horizon",        str(horizon),
        "--out-dir",        str(out_dir),
        "--connectivity-neighbors", connectivity_neighbors,
    ]
    if seed_water_raster is not None:
        run_model_cmd.extend(["--seed-water-raster", str(seed_water_raster)])
    if hand_raster is not None:
        run_model_cmd.extend(["--fluvial-hand-raster", str(hand_raster)])
    if sea_mask_raster is not None:
        run_model_cmd.extend(["--sea-mask-raster", str(sea_mask_raster)])
    if river_raster is not None:
        run_model_cmd.extend([
            "--tidal-channel-raster", str(river_raster),
            "--tidal-burn-elevation", "2.0",
        ])
    for _seed_latlon in _COASTAL_SEED_LATLON.get(city.slug, []):
        run_model_cmd.extend(["--coastal-seed-latlon", _seed_latlon])
    run_model_cmd.extend([
        "--coastal-solver",           coastal_solver,
        "--inertial-t-end",           str(inertial_t_end),
        "--inertial-convergence-tol", str(inertial_convergence_tol),
    ])
    # Permanent still-water floor for the inertial surge recession = MSL + SLR.
    # Passing the city's MSL→EGM2008 offset stops the hydrograph receding below
    # mean sea level and draining the permanent SLR component.
    _msl_egm2008 = getattr(city, "msl_to_egm2008_offset", 0.0) or 0.0
    run_model_cmd.extend(["--coastal-msl-egm2008", str(_msl_egm2008)])
    run_model_cmd.extend(["--pluvial-model", pluvial_model])
    # Forward the pluvial ponding depth cap to run_multihazard's raingrid path.
    # Without this the cap defaulted to None (uncapped) — the root cause of the
    # KL baseline pluvial over-extent (max 4.5 m > 3.0 m cap; Plan-2 finding #2).
    run_model_cmd.extend(["--pluvial-depth-cap", str(max_ponding_depth_m)])
    if pluvial_dem_raster is not None and pluvial_dem_raster.exists():
        run_model_cmd.extend(["--pluvial-dem-raster", str(pluvial_dem_raster)])
    run_model_cmd.extend(["--runoff-coeff", str(city.runoff_coeff)])
    if not clamp_negative_land:
        run_model_cmd.append("--no-clamp-negative-land")
    if runoff_coeff_raster is not None and runoff_coeff_raster.exists():
        run_model_cmd.extend(["--runoff-coeff-raster", str(runoff_coeff_raster)])
    _run(run_model_cmd)

    # ------------------------------------------------------------------
    # 6. Combined flood maps
    # ------------------------------------------------------------------
    click.echo("\n=== Step 6: Generate combined flood maps ===")
    _run([
        py, str(PROJECT_ROOT / "scripts" / "make_combined_flood_maps.py"),
        "--out-dir",   str(out_dir),
        "--scenario",  scenario,
        "--horizon",   str(horizon),
        "--city-name", city.name,
    ])

    # ------------------------------------------------------------------
    # 7. Street-overlay visualisation
    # ------------------------------------------------------------------
    if make_street_overlay:
        click.echo("\n=== Step 7: Generate street-overlay visualisations ===")
        _run([
            py, str(PROJECT_ROOT / "scripts" / "overlay_street_maps.py"),
            "--out-dir",   str(out_dir),
            "--scenario",  scenario,
            "--horizon",   str(horizon),
            "--city-name", city.name,
        ])

    click.echo(f"\n{'='*60}")
    click.echo(f"  {city.name} pipeline complete.")
    click.echo(f"  Outputs: {out_dir}")
    click.echo(f"{'='*60}\n")


if __name__ == "__main__":
    cli()
