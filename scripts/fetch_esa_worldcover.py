"""
Fetch ESA WorldCover 2021 v200 (10 m global land cover) for a city DEM
bounding box and derive a per-cell runoff coefficient raster aligned to
the DEM grid.

ESA WorldCover is CC-BY 4.0, hosted as Cloud-Optimized GeoTIFFs on AWS
S3 (public, no credentials).  The 11 land-cover classes are mapped to
rational-method runoff coefficients, then the 10 m coefficient grid is
resampled (averaged) to the 30 m DEM grid so a partially-paved cell
receives an intermediate coefficient — sub-grid impervious weighting.

Usage
-----
    python scripts/fetch_esa_worldcover.py \\
        --dem data/bangkok/copernicus_dem_utm47n.tif \\
        --output data/bangkok/runoff_coeff_utm47n.tif
"""
from __future__ import annotations

from pathlib import Path

import click
import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import Resampling, reproject, transform_bounds

# ESA WorldCover v200 class code -> rational-method runoff coefficient.
WORLDCOVER_RUNOFF_COEFF: dict[int, float] = {
    10: 0.20,   # tree cover
    20: 0.30,   # shrubland
    30: 0.25,   # grassland
    40: 0.35,   # cropland
    50: 0.90,   # built-up
    60: 0.50,   # bare / sparse vegetation
    70: 0.10,   # snow and ice (absent in ASEAN domains)
    80: 1.00,   # permanent water bodies
    90: 0.60,   # herbaceous wetland
    95: 0.55,   # mangroves
    100: 0.30,  # moss and lichen
}
FALLBACK_RUNOFF_COEFF: float = 0.40


def class_to_runoff_coeff(classes: np.ndarray) -> np.ndarray:
    """Map an array of WorldCover class codes to runoff coefficients."""
    coeff = np.full(classes.shape, FALLBACK_RUNOFF_COEFF, dtype=np.float32)
    for code, value in WORLDCOVER_RUNOFF_COEFF.items():
        coeff[classes == code] = value
    return coeff


_S3_BASE = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
)


def _tile_name(lat: float, lon: float) -> str:
    """WorldCover tile covering (lat, lon); tiles start at 3-degree multiples."""
    tlat = int(np.floor(lat / 3.0) * 3)
    tlon = int(np.floor(lon / 3.0) * 3)
    ns = f"N{tlat:02d}" if tlat >= 0 else f"S{-tlat:02d}"
    ew = f"E{tlon:03d}" if tlon >= 0 else f"W{-tlon:03d}"
    return f"ESA_WorldCover_10m_2021_v200_{ns}{ew}_Map.tif"


@click.command()
@click.option("--dem", "dem_path", type=click.Path(exists=True, path_type=Path),
              required=True, help="City DEM GeoTIFF (defines grid + CRS).")
@click.option("--output", "output_path", type=click.Path(path_type=Path),
              required=True, help="Output runoff-coefficient GeoTIFF.")
def cli(dem_path: Path, output_path: Path) -> None:
    """Build a DEM-aligned runoff-coefficient raster from ESA WorldCover."""
    if output_path.exists() and output_path.stat().st_size > 0:
        click.echo(f"[skip] runoff-coefficient raster already exists: {output_path}")
        return
    with rasterio.open(dem_path) as dem_src:
        dem_crs = dem_src.crs
        dem_transform = dem_src.transform
        dem_w, dem_h = dem_src.width, dem_src.height
        dem_bounds = dem_src.bounds

    wgs84 = rasterio.crs.CRS.from_epsg(4326)
    lon0, lat0, lon1, lat1 = transform_bounds(dem_crs, wgs84, *dem_bounds)
    tiles = sorted({
        _tile_name(la, lo) for la in (lat0, lat1) for lo in (lon0, lon1)
    })
    click.echo(f"WorldCover tiles needed: {tiles}")

    srcs = []
    try:
        for t in tiles:
            try:
                srcs.append(rasterio.open(f"{_S3_BASE}/{t}"))
            except Exception as exc:
                raise click.ClickException(
                    f"Could not open ESA WorldCover tile {t} from S3: {exc}"
                ) from exc
        mosaic, mosaic_transform = merge(srcs, bounds=(lon0, lat0, lon1, lat1))
    finally:
        for s in srcs:
            s.close()
    coeff_wgs = class_to_runoff_coeff(mosaic[0])

    coeff_dem = np.full((dem_h, dem_w), np.nan, dtype=np.float32)
    reproject(
        source=coeff_wgs,
        destination=coeff_dem,
        src_transform=mosaic_transform,
        src_crs=wgs84,
        dst_transform=dem_transform,
        dst_crs=dem_crs,
        resampling=Resampling.average,
        dst_nodata=np.nan,
    )

    profile = {
        "driver": "GTiff", "dtype": "float32", "count": 1,
        "width": dem_w, "height": dem_h, "crs": dem_crs,
        "transform": dem_transform, "compress": "deflate", "nodata": np.nan,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(coeff_dem, 1)
    click.echo(
        f"Wrote runoff-coefficient raster: {output_path}  "
        f"(mean={np.nanmean(coeff_dem):.3f})"
    )


if __name__ == "__main__":
    cli()
