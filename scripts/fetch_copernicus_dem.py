from __future__ import annotations

from pathlib import Path

import click
import numpy as np
import planetary_computer
import rasterio
from pystac_client import Client
from rasterio.io import DatasetReader
from rasterio.merge import merge
from rasterio.warp import Resampling, calculate_default_transform, reproject

PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COP_DEM_COLLECTION = "cop-dem-glo-30"


def _open_dem_sources(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> list[DatasetReader]:
    client = Client.open(PC_STAC_URL)
    search = client.search(
        collections=[COP_DEM_COLLECTION],
        bbox=[min_lon, min_lat, max_lon, max_lat],
    )
    items = list(search.items())
    if not items:
        raise ValueError("No Copernicus DEM items found for the provided bbox.")

    sources: list[DatasetReader] = []
    for item in items:
        signed_item = planetary_computer.sign(item)
        if "data" not in signed_item.assets:
            continue
        href = signed_item.assets["data"].href
        src = rasterio.open(href)
        sources.append(src)

    if not sources:
        raise ValueError("Found items but no readable 'data' assets for Copernicus DEM.")
    return sources


def _reproject_array(
    data,
    src_transform,
    src_crs,
    dst_crs: str,
    nodata,
    resolution: float | None,
):
    src_height, src_width = data.shape
    left, bottom, right, top = rasterio.transform.array_bounds(src_height, src_width, src_transform)
    dst_transform, dst_width, dst_height = calculate_default_transform(
        src_crs,
        dst_crs,
        src_width,
        src_height,
        left,
        bottom,
        right,
        top,
        resolution=resolution,
    )
    dst_nodata = nodata if nodata is not None else -9999.0
    out = np.full((dst_height, dst_width), dst_nodata, dtype=data.dtype)
    reproject(
        source=data,
        destination=out,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        src_nodata=nodata,
        dst_nodata=dst_nodata,
        resampling=Resampling.bilinear,
    )
    return out, dst_transform, dst_crs, dst_nodata


@click.command()
@click.option("--min-lon", type=float, required=True)
@click.option("--min-lat", type=float, required=True)
@click.option("--max-lon", type=float, required=True)
@click.option("--max-lat", type=float, required=True)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    required=True,
    help="Output DEM GeoTIFF",
)
@click.option(
    "--target-crs",
    type=str,
    default=None,
    help="Optional target CRS, e.g. EPSG:32618",
)
@click.option(
    "--target-resolution",
    type=float,
    default=None,
    help="Optional target pixel size (in target CRS units).",
)
def cli(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    output_path: Path,
    target_crs: str | None,
    target_resolution: float | None,
) -> None:
    if not (min_lon < max_lon and min_lat < max_lat):
        raise ValueError("Invalid bbox: require min < max for lon/lat.")

    # Skip-if-exists: the GLO-30 DEM is static (TanDEM-X 2011-2015 acquisition);
    # re-downloading via Planetary Computer is wasteful and fragile against
    # transient STAC API timeouts.
    if output_path.exists() and output_path.stat().st_size > 1_000_000:
        click.echo(
            f"[skip] Output DEM already exists ({output_path}, "
            f"{output_path.stat().st_size / 1e6:.1f} MB).  "
            "Delete the file to force re-fetch."
        )
        return

    sources = _open_dem_sources(min_lon, min_lat, max_lon, max_lat)
    try:
        mosaic, out_transform = merge(
            sources=sources,
            bounds=(min_lon, min_lat, max_lon, max_lat),
        )
        arr = mosaic[0]
        first = sources[0]
        crs = first.crs
        nodata = first.nodata if first.nodata is not None else -9999.0
        arr = arr.astype("float32")
        arr[arr == nodata] = nodata

        if target_crs:
            arr, out_transform, crs, nodata = _reproject_array(
                data=arr,
                src_transform=out_transform,
                src_crs=crs,
                dst_crs=target_crs,
                nodata=nodata,
                resolution=target_resolution,
            )

        profile = first.profile.copy()
        profile.update(
            driver="GTiff",
            height=arr.shape[0],
            width=arr.shape[1],
            count=1,
            dtype="float32",
            crs=crs,
            transform=out_transform,
            nodata=nodata,
            compress="deflate",
            predictor=2,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(arr, 1)
    finally:
        for src in sources:
            src.close()

    click.echo(f"Wrote clipped Copernicus DEM: {output_path}")


if __name__ == "__main__":
    cli()
