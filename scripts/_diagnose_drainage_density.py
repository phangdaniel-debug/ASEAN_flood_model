"""Drainage density diagnostic — distance-to-nearest-outlet distribution.

Measures how far land cells (and wet cells from a flood simulation) are from
any drainage outlet.  Used to diagnose pluvial over-flooding caused by sparse
outlet networks.

Usage:
    python scripts/_diagnose_drainage_density.py \\
        --drainage data/kuala_lumpur/river_mask_utm47n.tif \\
        --sea data/kuala_lumpur/sea_mask_utm47n.tif \\
        --dem data/kuala_lumpur/copernicus_dem_utm47n_raingrid.tif \\
        [--wet outputs/kuala_lumpur_ssp585_2020/pluvial/rp_100/pluvial_depth_SSP5-8.5_2020_rp100.tif]
"""
from __future__ import annotations

from pathlib import Path

import click
import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt


def summarize_distance(
    outlet_mask: np.ndarray,
    land_mask: np.ndarray,
    wet_mask: np.ndarray | None = None,
    cell_size_m: float = 30.0,
) -> dict:
    """Compute distance-to-nearest-outlet summary statistics.

    Parameters
    ----------
    outlet_mask:
        Boolean array; True = drainage outlet cell.
    land_mask:
        Boolean array; True = valid land cell (finite DEM elevation).
    wet_mask:
        Optional boolean array; True = flooded cell (depth >= threshold).
        If None, wet statistics are omitted.
    cell_size_m:
        Pixel size in metres.  Used to scale EDT from pixels to metres.

    Returns
    -------
    dict with keys:
        outlet_count, land_count, pct_of_land,
        land_median_m, land_p90_m, land_max_m,
        wet_count (if wet_mask provided),
        wet_median_m, wet_p90_m, wet_max_m (if wet_mask provided).
    """
    # Distance in pixels, then scale to metres.
    dist_px = distance_transform_edt(~outlet_mask)
    dist_m = dist_px * cell_size_m

    outlet_count = int(np.sum(outlet_mask))
    land_count = int(np.sum(land_mask))
    pct_of_land = 100.0 * outlet_count / land_count if land_count > 0 else 0.0

    land_dist = dist_m[land_mask]
    result: dict = {
        "outlet_count": outlet_count,
        "land_count": land_count,
        "pct_of_land": pct_of_land,
        "land_median_m": float(np.median(land_dist)) if land_dist.size > 0 else np.nan,
        "land_p90_m": float(np.percentile(land_dist, 90)) if land_dist.size > 0 else np.nan,
        "land_max_m": float(land_dist.max()) if land_dist.size > 0 else np.nan,
    }

    if wet_mask is not None:
        wet_dist = dist_m[wet_mask & land_mask]
        result["wet_count"] = int(np.sum(wet_mask & land_mask))
        result["wet_median_m"] = float(np.median(wet_dist)) if wet_dist.size > 0 else np.nan
        result["wet_p90_m"] = float(np.percentile(wet_dist, 90)) if wet_dist.size > 0 else np.nan
        result["wet_max_m"] = float(wet_dist.max()) if wet_dist.size > 0 else np.nan

    return result


@click.command()
@click.option(
    "--drainage", "drainage_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="River/drainage mask raster (1 = drainage channel, 0 = not).",
)
@click.option(
    "--sea", "sea_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Sea mask raster (1 = LAND, 0 = SEA).",
)
@click.option(
    "--dem", "dem_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="DEM raster; used to identify valid (finite-elevation) land cells.",
)
@click.option(
    "--wet", "wet_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    required=False,
    help="Flood depth raster; wet cells are those with depth >= 0.10 m.",
)
@click.option(
    "--wet-threshold", "wet_threshold",
    type=float,
    default=0.10,
    show_default=True,
    help="Depth threshold (m) for classifying a cell as wet.",
)
def cli(
    drainage_path: Path,
    sea_path: Path,
    dem_path: Path,
    wet_path: Path | None,
    wet_threshold: float,
) -> None:
    """Report drainage outlet density and distance-to-outlet distribution."""
    click.echo("Loading rasters...")

    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float32)
        nodata = src.nodata
        transform = src.transform
        cell_size_m = abs(transform.a)

    if nodata is not None:
        dem[dem == nodata] = np.nan

    with rasterio.open(sea_path) as src:
        sea = src.read(1)

    with rasterio.open(drainage_path) as src:
        drainage = src.read(1)

    # land = sea mask says land AND DEM has finite elevation
    land_mask = (sea == 1) & np.isfinite(dem)

    # outlet = sea cell (sea==0) OR drainage/river cell
    # Restrict to cells that exist in the raster (allow sea cells even if DEM is nan)
    outlet_mask = (sea == 0) | (drainage > 0)

    # Restrict outlet to cells inside the raster extent (both sea and drainage)
    # We do NOT restrict outlets to land_mask — sea is a valid outlet even off-land.

    wet_mask: np.ndarray | None = None
    if wet_path is not None:
        with rasterio.open(wet_path) as src:
            depth = src.read(1).astype(np.float32)
            depth_nodata = src.nodata
        if depth_nodata is not None:
            depth[depth == depth_nodata] = np.nan
        wet_mask = np.isfinite(depth) & (depth >= wet_threshold) & land_mask

    click.echo(f"Cell size: {cell_size_m:.1f} m")
    click.echo(f"Grid shape: {dem.shape}")
    click.echo("Computing distance transform (may take a few seconds)...")

    stats = summarize_distance(outlet_mask, land_mask, wet_mask, cell_size_m=cell_size_m)

    click.echo("")
    click.echo("=" * 55)
    click.echo("DRAINAGE DENSITY DIAGNOSTIC")
    click.echo("=" * 55)
    click.echo(f"  Outlet cells     : {stats['outlet_count']:>10,}")
    click.echo(f"  Land cells       : {stats['land_count']:>10,}")
    click.echo(f"  Outlets % of land: {stats['pct_of_land']:>10.2f}%")
    click.echo("")
    click.echo("  Distance-to-outlet over LAND cells:")
    click.echo(f"    Median : {stats['land_median_m']:>10,.1f} m")
    click.echo(f"    P90    : {stats['land_p90_m']:>10,.1f} m")
    click.echo(f"    Max    : {stats['land_max_m']:>10,.1f} m")

    if wet_mask is not None:
        click.echo("")
        click.echo(f"  Wet cells (depth >= {wet_threshold:.2f} m): {stats['wet_count']:>10,}")
        click.echo("  Distance-to-outlet over WET cells:")
        click.echo(f"    Median : {stats['wet_median_m']:>10,.1f} m")
        click.echo(f"    P90    : {stats['wet_p90_m']:>10,.1f} m")
        click.echo(f"    Max    : {stats['wet_max_m']:>10,.1f} m")

    click.echo("=" * 55)


if __name__ == "__main__":
    cli()
