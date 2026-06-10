"""Build an approximate bare-earth DEM from Copernicus GLO-30 by removing
building-contaminated cells and infilling ground beneath them.

This is a commercial-safe, open-data substitute for FABDEM (which is
CC BY-NC-SA, non-commercial only).  Inputs:

  * Copernicus GLO-30 DEM        — ESA, free for commercial use
  * Building-coverage fraction   — derived from Google Open Buildings v3
                                   (CC BY-4.0; see fetch_open_buildings.py)

Method (FABDEM-like)
--------------------
1. Flag cells whose building-coverage fraction exceeds a threshold.  These
   carry the DSM's building bias (raised roofs) and the artificial
   inter-building voids that create the spurious micro-pits breaking the
   pluvial model.
2. Remove the flagged cells and infill the ground surface from the
   surrounding open (road / park / water) cells by inverse-distance
   interpolation (``rasterio.fill.fillnodata``).  A dense urban road grid
   guarantees nearby open cells, so the fill is well constrained.
3. Optionally apply a light final smoothing to suppress residual
   cell-to-cell DSM noise.

The output is written as ``<dem_stem>_bareearth.tif`` and is intended for
pluvial rain-on-grid routing (and is available to coastal/fluvial later).

Usage
-----
    python scripts/build_bareearth_dem.py \
        --dem data/singapore/copernicus_dem_utm48n.tif \
        --building-coverage data/singapore/building_coverage_utm48n.tif \
        --output data/singapore/copernicus_dem_utm48n_bareearth.tif
"""
from pathlib import Path

import click
import numpy as np
import rasterio
from rasterio.fill import fillnodata
from scipy import ndimage


@click.command()
@click.option("--dem", "dem_path", type=click.Path(exists=True, path_type=Path),
              required=True, help="Copernicus GLO-30 DEM GeoTIFF.")
@click.option("--building-coverage", "cov_path",
              type=click.Path(exists=True, path_type=Path), required=True,
              help="Building-coverage fraction raster (from fetch_open_buildings.py).")
@click.option("--output", "output_path", type=click.Path(path_type=Path),
              required=True, help="Output bare-earth DEM GeoTIFF.")
@click.option("--coverage-threshold", type=float, default=0.25, show_default=True,
              help="Cells with building coverage above this are infilled.")
@click.option("--max-search-distance", type=float, default=50.0, show_default=True,
              help="fillnodata IDW search radius (cells).")
@click.option("--smoothing-iterations", type=int, default=2, show_default=True,
              help="fillnodata post-fill smoothing passes.")
@click.option("--final-median-size", type=int, default=3, show_default=True,
              help="Size of the final median filter over land (1 = disabled).")
def cli(dem_path: Path, cov_path: Path, output_path: Path,
        coverage_threshold: float, max_search_distance: float,
        smoothing_iterations: int, final_median_size: int) -> None:
    """Construct a bare-earth DEM from GLO-30 + Open Buildings coverage."""
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float32)
        profile = src.profile
        dem_nodata = src.nodata
    with rasterio.open(cov_path) as src:
        cov = src.read(1).astype(np.float32)

    if cov.shape != dem.shape:
        raise click.ClickException(
            f"coverage shape {cov.shape} != DEM shape {dem.shape}")

    finite = np.isfinite(dem)
    if dem_nodata is not None:
        finite &= dem != dem_nodata
    cov = np.where(np.isfinite(cov), cov, 0.0)

    built = (cov > coverage_threshold) & finite
    n_built = int(built.sum())
    click.echo(
        f"Built cells (coverage>{coverage_threshold}): {n_built:,} "
        f"({100*n_built/max(1,int(finite.sum())):.1f}% of land)")

    # fillnodata: validity mask uses 1 = keep, 0 = interpolate.
    fill_mask = (finite & ~built).astype(np.uint8)
    work = dem.copy()
    work[~finite] = 0.0  # placeholder; restored to nodata at the end

    click.echo(f"Infilling {n_built:,} built cells (IDW, search={max_search_distance}) ...")
    filled = fillnodata(
        work, mask=fill_mask,
        max_search_distance=max_search_distance,
        smoothing_iterations=smoothing_iterations,
    )

    # Light median over land to suppress residual DSM cell noise.
    if final_median_size and final_median_size > 1:
        click.echo(f"Final {final_median_size}x{final_median_size} median over land ...")
        med = ndimage.median_filter(filled, size=final_median_size)
        filled = np.where(finite, med, filled)

    # Restore genuine nodata.
    out = filled.astype(np.float32)
    if dem_nodata is not None:
        out[~finite] = dem_nodata

    # Report how much we changed the surface on land.
    diff = out[finite] - dem[finite]
    click.echo(
        f"Bare-earth vs GLO-30 on land: mean d={diff.mean():+.2f} m  "
        f"median d={np.median(diff):+.2f} m  "
        f"p5/p95 d={np.percentile(diff,5):+.2f}/{np.percentile(diff,95):+.2f} m")

    profile.update(dtype="float32", compress="deflate")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(out, 1)
    click.echo(f"Wrote bare-earth DEM: {output_path}")


if __name__ == "__main__":
    cli()
