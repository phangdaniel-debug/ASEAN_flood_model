from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

import click
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import Affine


@dataclass(frozen=True)
class ScenarioLevel:
    scenario: str
    horizon: int
    water_level_m: float


def load_dem(dem_path: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float32)
        profile = src.profile.copy()
        nodata = src.nodata

    if nodata is not None:
        dem = np.where(dem == nodata, np.nan, dem)
    return dem, profile


def read_scenario_levels(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    required = {"scenario", "horizon", "water_level_m"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in scenarios CSV: {sorted(missing)}")
    return df


def select_water_level(df: pd.DataFrame, scenario: str, horizon: int) -> ScenarioLevel:
    hit = df[(df["scenario"] == scenario) & (df["horizon"] == horizon)]
    if hit.empty:
        raise ValueError(
            f"No row found for scenario={scenario!r}, horizon={horizon}. "
            "Add it to the scenarios CSV."
        )
    row = hit.iloc[0]
    return ScenarioLevel(
        scenario=row["scenario"],
        horizon=int(row["horizon"]),
        water_level_m=float(row["water_level_m"]),
    )


def flood_depth_bathtub(
    dem: np.ndarray,
    water_level_m: float,
    mask_lowest_to_zero: bool = False,
) -> np.ndarray:
    """
    Compute flood depth by simple bathtub method:
    depth = max(0, water_level - ground_elevation).

    DEM and ``water_level_m`` must be expressed in the same vertical datum
    (e.g. both relative to EGM2008 or both relative to local MSL).

    If ``mask_lowest_to_zero`` is True the DEM is shifted so its minimum finite
    value becomes 0, reinterpreting ``water_level_m`` as a depth above the
    lowest terrain point rather than an absolute datum value. This is incorrect
    when ``water_level_m`` comes from an absolute projection (e.g. IPCC AR6)
    and should only be used when working in a purely relative reference frame.
    """
    dem_work = dem.copy()
    if mask_lowest_to_zero:
        finite = np.isfinite(dem_work)
        if np.any(finite):
            dem_work[finite] = dem_work[finite] - np.nanmin(dem_work[finite])

    depth = np.maximum(0.0, water_level_m - dem_work)
    depth[~np.isfinite(dem_work)] = np.nan
    return depth.astype(np.float32)


def _neighbor_offsets(connectivity: int) -> list[tuple[int, int]]:
    if connectivity == 4:
        return [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if connectivity == 8:
        return [
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
        ]
    raise ValueError("connectivity must be 4 or 8")


def _seed_from_boundary(mask: np.ndarray) -> np.ndarray:
    seeds = np.zeros_like(mask, dtype=bool)
    if mask.size == 0:
        return seeds
    seeds[0, :] = mask[0, :]
    seeds[-1, :] = mask[-1, :]
    seeds[:, 0] = mask[:, 0]
    seeds[:, -1] = mask[:, -1]
    return seeds


def connected_flood_mask(
    flood_mask: np.ndarray,
    connectivity: int = 8,
    seed_mask: np.ndarray | None = None,
) -> np.ndarray:
    """
    Keep only flood cells connected to seeds.

    If seed_mask is not provided, border flood cells are used as seeds
    (typical for coastal open-boundary screening).
    """
    active = flood_mask.astype(bool)
    if seed_mask is None:
        seeds = _seed_from_boundary(active)
    else:
        if seed_mask.shape != active.shape:
            raise ValueError("seed_mask shape must match flood raster shape")
        seeds = active & seed_mask.astype(bool)

    visited = np.zeros_like(active, dtype=bool)
    q: deque[tuple[int, int]] = deque()

    seed_rows, seed_cols = np.where(seeds)
    for r, c in zip(seed_rows.tolist(), seed_cols.tolist()):
        visited[r, c] = True
        q.append((r, c))

    offsets = _neighbor_offsets(connectivity)
    rows, cols = active.shape
    while q:
        r, c = q.popleft()
        for dr, dc in offsets:
            rr, cc = r + dr, c + dc
            if rr < 0 or rr >= rows or cc < 0 or cc >= cols:
                continue
            if visited[rr, cc] or not active[rr, cc]:
                continue
            visited[rr, cc] = True
            q.append((rr, cc))
    return visited


def flood_depth_hand(hand: np.ndarray, stage_m: float) -> np.ndarray:
    """
    Compute flood depth from a HAND raster and a bankfull stage.

        depth(x, y) = max(0, stage_m - hand(x, y))

    ``stage_m`` is the water-surface elevation *above the channel floor*,
    not an absolute datum value.  For fluvial hazard, ``water_level_m``
    from the hazard CSV is interpreted as this relative stage: how deep the
    water rises above the channel bed at a given return period.

    Cells with HAND < stage_m are flooded; cells with HAND >= stage_m are dry.
    The depth is largest at the channel (HAND ≈ 0) and decreases with
    distance/elevation from the nearest drainage cell.

    Parameters
    ----------
    hand : float32 array
        Height Above Nearest Drainage in metres (>= 0, NaN = nodata).
    stage_m : float
        Bankfull stage in metres above the channel floor.

    Returns
    -------
    depth : float32 array
        Flood depth in metres (>= 0).  NaN where hand is NaN.
    """
    depth = np.maximum(0.0, stage_m - hand)
    depth[~np.isfinite(hand)] = np.nan
    return depth.astype(np.float32)


def apply_connectivity_filter(
    depth: np.ndarray,
    connectivity: int = 8,
    seed_water_mask: np.ndarray | None = None,
) -> np.ndarray:
    flooded = np.isfinite(depth) & (depth > 0)
    connected = connected_flood_mask(
        flooded,
        connectivity=connectivity,
        seed_mask=seed_water_mask,
    )
    out = depth.copy()
    out[flooded & ~connected] = 0.0
    return out


def _bfs_with_extra_seeds(
    active: np.ndarray,
    connectivity: int,
    extra_seeds: np.ndarray | None,
) -> np.ndarray:
    """Connectivity-filter ``active`` seeded from its raster boundary, plus
    optional interior ``extra_seeds``.

    When ``extra_seeds`` is None this is identical to the legacy
    boundary-only ``connected_flood_mask(active, seed_mask=None)``.  When
    supplied, the interior seeds are unioned with the boundary seeds; a
    seed only takes effect where it coincides with an ``active`` pixel.
    """
    if extra_seeds is None:
        return connected_flood_mask(active, connectivity=connectivity, seed_mask=None)
    if extra_seeds.shape != active.shape:
        raise ValueError("extra_seeds shape must match DEM shape")
    seeds = _seed_from_boundary(active) | (active & extra_seeds.astype(bool))
    return connected_flood_mask(active, connectivity=connectivity, seed_mask=seeds)


def derive_sea_mask(
    dem: np.ndarray,
    connectivity: int = 8,
    nan_bfs: bool = True,
    extra_seeds: np.ndarray | None = None,
    elevated_water_seeds: list[tuple[np.ndarray, float]] | None = None,
) -> np.ndarray:
    """
    Identify ocean/sea pixels in a Copernicus DEM.

    The Copernicus GLO-30 DEM represents open ocean in two ways depending
    on the acquisition geometry:

    * Most coastal areas: open sea stored as exactly **0.0 m** (the
      approximate EGM2008 ocean surface).
    * Some coastal bays and delta coastlines (e.g. Manila Bay, HCMC delta):
      open sea stored as **NaN (nodata, −9999)** because low coherence during
      TanDEM-X acquisition caused the water surface to be masked out rather
      than set to zero.

    When ``nan_bfs=True`` (default) the function handles both cases by
    combining two BFS passes:

    1. **NaN-BFS** — seeds from boundary NaN pixels (open-water nodata),
       propagates through all 4/8-connected NaN pixels.  Captures coastal
       bays and delta coasts stored as nodata.
    2. **0-m BFS** — seeds from boundary pixels where ``dem <= 0.0 m``
       (the standard GLO-30 ocean representation), propagates through all
       connected pixels at or below 0 m.

    The union of both passes is the sea mask.

    When ``nan_bfs=False`` only the 0-m BFS is run (legacy behaviour,
    appropriate only when the domain is known to have no NaN-dominated
    coastlines).

    A third optional pass (``elevated_water_seeds``) captures permanent
    inland water bodies whose surface sits above 0 m — e.g. Laguna de Bay
    — which neither boundary pass can reach.

    Reclaimed land at 0.0 m enclosed by higher terrain is NOT labelled sea
    because it cannot be reached from the boundary.

    Parameters
    ----------
    dem : float32 array
        DEM in metres (NaN = nodata).
    connectivity : int
        4- or 8-connected BFS neighbourhood.
    nan_bfs : bool
        If True (default), also seed the BFS from boundary NaN pixels to
        handle GLO-30 tiles where open ocean is stored as nodata rather
        than 0.0 m.  Set False only to reproduce legacy behaviour.
    extra_seeds : bool array | None
        Optional additional BFS seed pixels (True where seed).  Required
        when an open-water body is fully enclosed within the DEM domain
        and does not touch the raster boundary — e.g. Manila Bay, which the
        clipped GLO-30 tile stores as a ~335 km² connected region of <=0 m
        pixels with no continuous <=0 m path to the raster edge.  A purely
        boundary-seeded BFS never reaches such a basin and mis-classifies
        it as land.  Seeds are unioned with the boundary-derived seeds for
        both the 0-m and NaN passes; a seed only promotes a pixel that is
        itself a sea candidate (<=0 m for the 0-m pass, NaN for the NaN
        pass), so a seed on land activates nothing.
    elevated_water_seeds : list[(bool array, float)] | None
        Optional interior seeds for permanent inland water bodies whose
        surface sits **above** 0 m and so cannot be reached by the 0-m
        pass — e.g. Laguna de Bay, the freshwater lake south-east of
        Manila, stored at ~1.0 m in GLO-30.  Each entry is a
        ``(seed_array, max_elev_m)`` pair: a dedicated BFS propagates from
        the seed pixels through all connected pixels with ``dem <=
        max_elev_m``.  Unlike the 0-m / NaN passes this pass is seeded
        **only** from the interior seed (never the raster boundary), so a
        permissive ``max_elev_m`` cannot flood-fill the domain from its
        edge.  The result is unioned into the sea mask, so the lake is
        excluded from flood modelling exactly like open sea.

    Returns
    -------
    sea_mask : bool array
        True where the pixel is classified as open sea.
    """
    nan_mask = ~np.isfinite(dem)

    # Pass 1: standard 0-m BFS (handles most GLO-30 coastal pixels)
    candidate_zero = np.isfinite(dem) & (dem <= 0.0)
    sea_zero = _bfs_with_extra_seeds(
        candidate_zero, connectivity=connectivity, extra_seeds=extra_seeds
    )
    sea = sea_zero

    # Pass 2: NaN-BFS — seed from boundary NaN pixels, propagate through
    # all connected NaN pixels.  These represent open-water nodata in GLO-30.
    if nan_bfs:
        sea_nan = _bfs_with_extra_seeds(
            nan_mask, connectivity=connectivity, extra_seeds=extra_seeds
        )
        sea = sea | sea_nan

    # Pass 3: elevated inland water bodies (lakes above MSL).  Interior-seeded
    # only — each lake floods through its own dem <= max_elev component.
    if elevated_water_seeds:
        for seed_arr, max_elev in elevated_water_seeds:
            if seed_arr.shape != dem.shape:
                raise ValueError(
                    "elevated_water_seeds seed shape must match DEM shape"
                )
            candidate = np.isfinite(dem) & (dem <= max_elev)
            seeds = candidate & seed_arr.astype(bool)
            lake = connected_flood_mask(
                candidate, connectivity=connectivity, seed_mask=seeds
            )
            sea = sea | lake

    return sea


def derive_tidal_channel_seeds(
    sea_mask: np.ndarray,
    channel_mask: np.ndarray,
    max_elevation_m: float,
    dem: np.ndarray,
    connectivity: int = 8,
) -> np.ndarray:
    """
    Find river/drain pixels that are hydrologically connected to the sea.

    Starting from every sea pixel, the BFS propagates through adjacent
    *channel* pixels whose DEM elevation is at or below ``max_elevation_m``.
    The result is the set of channel pixels reachable from open water —
    i.e. tidal channels — which can serve as additional coastal BFS seeds
    so that the flood model can propagate inland along those corridors.

    Parameters
    ----------
    sea_mask : bool array
        True where the pixel is classified as open sea.
    channel_mask : bool array
        True where the pixel is a river/drain cell (e.g. from an OSM raster).
    max_elevation_m : float
        Maximum DEM elevation for a channel pixel to be included.
        Keeps only near-sea tidal portions; inland channels at higher
        elevation are ignored.
    dem : float32 array
        Ground elevation in metres (NaN = nodata).
    connectivity : int
        4- or 8-connected BFS.

    Returns
    -------
    tidal_seeds : bool array
        True at every channel pixel reachable from sea.
    """
    # Eligible channel pixels: must be a channel, on land, within elevation limit
    eligible = channel_mask & ~sea_mask & np.isfinite(dem) & (dem <= max_elevation_m)

    visited = np.zeros(sea_mask.shape, dtype=bool)
    offsets = _neighbor_offsets(connectivity)
    rows, cols = sea_mask.shape

    from collections import deque
    q: deque[tuple[int, int]] = deque()

    # Seed: eligible channel pixels adjacent to any sea pixel
    sea_r, sea_c = np.where(sea_mask)
    for r, c in zip(sea_r.tolist(), sea_c.tolist()):
        for dr, dc in offsets:
            rr, cc = r + dr, c + dc
            if 0 <= rr < rows and 0 <= cc < cols:
                if eligible[rr, cc] and not visited[rr, cc]:
                    visited[rr, cc] = True
                    q.append((rr, cc))

    # BFS along channel network
    while q:
        r, c = q.popleft()
        for dr, dc in offsets:
            rr, cc = r + dr, c + dc
            if 0 <= rr < rows and 0 <= cc < cols:
                if eligible[rr, cc] and not visited[rr, cc]:
                    visited[rr, cc] = True
                    q.append((rr, cc))

    return visited


def flood_depth_pluvial_ponding(
    dem: np.ndarray,
    water_level_m: float,
    profile: dict,
) -> np.ndarray:
    """
    Compute pluvial flood depth using a depression-filling ponding model.

    For each topographic depression the maximum ponding depth is:

        max_ponding(x, y) = filled_dem(x, y) - dem(x, y)

    where ``filled_dem`` is the depression-filled DEM (every enclosed
    hollow raised to its pour-point elevation).  The return-period
    ``water_level_m`` acts as the ponding fill level: depressions fill
    up to whichever is shallower — their physical capacity or the
    available water depth.

        depth(x, y) = min(water_level_m, max_ponding(x, y))

    This correctly represents pluvial flooding as local surface ponding
    in terrain lows, rather than the physically incoherent flat water
    surface assumed by the bathtub method.

    ``water_level_m`` for pluvial is interpreted as an equivalent uniform
    ponding depth in metres: small at low return periods (only shallow
    depressions fill), larger at high return periods (deeper hollows
    fill too).

    Parameters
    ----------
    dem : float32 array
        Ground elevation in metres.  Sea pixels should already be set to
        NaN so they do not form spurious depressions.
    water_level_m : float
        Return-period ponding level (metres).
    profile : dict
        Rasterio profile for the DEM (passed to pysheds backend).

    Returns
    -------
    depth : float32 array
    """
    from model.hand_model import fill_depressions

    filled = fill_depressions(dem, profile)
    max_ponding = np.maximum(0.0, filled - dem)
    depth = np.minimum(float(water_level_m), max_ponding)
    depth[~np.isfinite(dem)] = np.nan
    return depth.astype(np.float32)


def write_depth_raster(depth: np.ndarray, profile: dict, out_path: Path) -> None:
    profile_out = profile.copy()
    profile_out.update(
        dtype="float32",
        count=1,
        compress="deflate",
        predictor=2,
        nodata=np.nan,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(out_path, "w", **profile_out) as dst:
        dst.write(depth, 1)


def pixel_area_m2(transform: Affine, crs) -> float:
    if not crs.is_projected:
        raise ValueError(
            f"DEM CRS {crs} is geographic (units: degrees). "
            "Reproject to a projected CRS with metre units before computing areas."
        )
    return float(abs(transform.a * transform.e))


def summarize_depth(depth: np.ndarray, transform: Affine, crs) -> dict[str, float]:
    wet = np.isfinite(depth) & (depth > 0)
    wet_count = int(np.count_nonzero(wet))
    pa = pixel_area_m2(transform, crs)
    flooded_area_m2 = wet_count * pa
    mean_depth_m = float(np.nanmean(depth[wet])) if wet_count else 0.0
    max_depth_m = float(np.nanmax(depth[wet])) if wet_count else 0.0
    return {
        "flooded_area_m2": flooded_area_m2,
        "flooded_area_km2": flooded_area_m2 / 1_000_000.0,
        "mean_depth_m": mean_depth_m,
        "max_depth_m": max_depth_m,
        "wet_pixels": wet_count,
    }


@click.command()
@click.option("--dem", "dem_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--scenarios",
    "scenarios_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--scenario", required=True, help="e.g. SSP5-8.5")
@click.option("--horizon", type=int, required=True, help="e.g. 2050 or 2100")
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    required=True,
    help="Output flood depth GeoTIFF",
)
@click.option(
    "--summary-csv",
    "summary_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Optional CSV with depth summary metrics",
)
@click.option(
    "--connectivity/--no-connectivity",
    "use_connectivity",
    default=True,
    show_default=True,
    help="Filter inundation to cells connected to seed water/boundary.",
)
@click.option(
    "--connectivity-neighbors",
    type=click.Choice(["4", "8"]),
    default="8",
    show_default=True,
    help="Connectivity rule used in flood-fill filter.",
)
@click.option(
    "--seed-water-raster",
    "seed_water_raster_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Optional raster where >0 marks permanent/open water seed cells.",
)
def cli(
    dem_path: Path,
    scenarios_path: Path,
    scenario: str,
    horizon: int,
    output_path: Path,
    summary_path: Path | None,
    use_connectivity: bool,
    connectivity_neighbors: str,
    seed_water_raster_path: Path | None,
) -> None:
    df = read_scenario_levels(scenarios_path)
    level = select_water_level(df, scenario, horizon)

    dem, profile = load_dem(dem_path)
    depth = flood_depth_bathtub(dem, level.water_level_m)
    if use_connectivity:
        seed_mask = None
        if seed_water_raster_path is not None:
            with rasterio.open(seed_water_raster_path) as seed_src:
                seed = seed_src.read(1)
                if seed.shape != depth.shape:
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
        depth = apply_connectivity_filter(
            depth,
            connectivity=int(connectivity_neighbors),
            seed_water_mask=seed_mask,
        )
    write_depth_raster(depth, profile, output_path)

    with rasterio.open(dem_path) as src:
        summary = summarize_depth(depth, src.transform, src.crs)

    summary.update({"scenario": level.scenario, "horizon": level.horizon, "water_level_m": level.water_level_m})
    summary_df = pd.DataFrame([summary])
    if summary_path:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_df.to_csv(summary_path, index=False)

    click.echo(f"Wrote depth raster: {output_path}")
    click.echo(summary_df.to_string(index=False))


if __name__ == "__main__":
    cli()
