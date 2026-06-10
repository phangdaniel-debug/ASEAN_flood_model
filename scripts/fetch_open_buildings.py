"""Fetch Google Open Buildings v3 footprints and rasterise to a building-
coverage fraction aligned to a city DEM.

Commercial licensing
---------------------
Google Open Buildings v3 is dual-licensed; we elect **CC BY-4.0**, which
permits commercial use with attribution (no share-alike).  Attribution
required in any product: "Building footprints (c) Google, CC BY-4.0,
Open Buildings dataset v3".

Data source
-----------
Tiles index : https://openbuildings-public-dot-gweb-research.uw.r.appspot.com/public/tiles.geojson
Polygons    : https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_4_gzip/{tile}_buildings.csv.gz
CSV columns : latitude, longitude, area_in_meters, confidence, geometry (WKT), full_plus_code

Output
------
A single-band float32 GeoTIFF on the DEM grid giving the fraction of each
30 m cell covered by building footprints (0-1).  Consumed by
``scripts/build_bareearth_dem.py`` to mask + infill building-contaminated cells.

Usage
-----
    python scripts/fetch_open_buildings.py \
        --dem data/singapore/copernicus_dem_utm48n.tif \
        --output data/singapore/building_coverage_utm48n.tif
"""
from pathlib import Path

import click
import numpy as np
import rasterio
import requests
from rasterio.features import rasterize
from rasterio.warp import transform_bounds
from shapely import wkt as shapely_wkt
from shapely.geometry import box

TILES_INDEX_URL = (
    "https://openbuildings-public-dot-gweb-research.uw.r.appspot.com/public/tiles.geojson"
)
POLY_URL = (
    "https://storage.googleapis.com/open-buildings-data/v3/"
    "polygons_s2_level_4_gzip/{tile}_buildings.csv.gz"
)
# Fraction of the DEM cell size at which buildings are rasterised before being
# block-averaged back to the DEM grid.  3 -> 10 m sub-cells for a 30 m DEM.
SUBSAMPLE = 3


def _intersecting_tiles(bbox_wgs84: tuple) -> list[str]:
    """Return the Open Buildings S2-L4 tile ids intersecting a WGS84 bbox."""
    import json
    resp = requests.get(TILES_INDEX_URL, timeout=120)
    resp.raise_for_status()
    gj = json.loads(resp.text)
    qbox = box(*bbox_wgs84)
    tiles = []
    for feat in gj["features"]:
        geom = shapely_wkt.loads(_geojson_to_wkt(feat["geometry"]))
        if geom.intersects(qbox):
            props = feat["properties"]
            # tile id key varies; try common names
            tile_id = (props.get("tile_id") or props.get("tile")
                       or props.get("id") or props.get("name"))
            if tile_id:
                tiles.append(str(tile_id))
    return tiles


def _geojson_to_wkt(geom: dict) -> str:
    from shapely.geometry import shape
    return shape(geom).wkt


def _download_tile(tile: str) -> Path | None:
    """Stream one tile CSV.gz to a local cache; return its path (or None on 404)."""
    cache_dir = Path("cache") / "openbuildings"
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{tile}_buildings.csv.gz"
    if dest.exists() and dest.stat().st_size > 0:
        click.echo(f"  [cache] reusing {dest} ({dest.stat().st_size//(1024*1024)} MB)")
        return dest
    url = POLY_URL.format(tile=tile)
    click.echo(f"  downloading tile {tile} -> {dest} ...", nl=False)
    with requests.get(url, stream=True, timeout=1200) as r:
        if r.status_code == 404:
            click.echo(" (404, skip)")
            return None
        r.raise_for_status()
        n = 0
        with open(dest, "wb") as f:
            for block in r.iter_content(chunk_size=8 * 1024 * 1024):
                f.write(block); n += len(block)
    click.echo(f" {n//(1024*1024)} MB")
    return dest


def _load_tile_polygons(tile: str, bbox_wgs84: tuple, min_conf: float):
    """Cache + read one tile CSV.gz, return shapely polygons within bbox.

    Filters cheaply on the latitude/longitude centroid columns BEFORE parsing
    the (expensive) WKT geometry, so dense tiles covering large regions stay
    tractable.  The Open Buildings ``polygons_s2_level_4_gzip`` files carry a
    header row, so we read it directly and select columns by name.
    """
    import pandas as pd
    path = _download_tile(tile)
    if path is None:
        return []

    lon0, lat0, lon1, lat1 = bbox_wgs84
    polys = []
    reader = pd.read_csv(
        path, compression="gzip", header=0,
        usecols=["latitude", "longitude", "confidence", "geometry"],
        dtype={"latitude": "float64", "longitude": "float64",
               "confidence": "float64", "geometry": "string"},
        chunksize=500_000, low_memory=False,
    )
    for chunk in reader:
        m = (
            (chunk.latitude >= lat0) & (chunk.latitude <= lat1)
            & (chunk.longitude >= lon0) & (chunk.longitude <= lon1)
            & (chunk.confidence >= min_conf)
        )
        for g in chunk.loc[m, "geometry"]:
            try:
                polys.append(shapely_wkt.loads(g))
            except Exception:
                pass
    click.echo(f"  -> {len(polys):,} polygons in bbox (conf>={min_conf})")
    return polys


@click.command()
@click.option("--dem", "dem_path", type=click.Path(exists=True, path_type=Path),
              required=True, help="City DEM GeoTIFF (defines grid + CRS).")
@click.option("--output", "output_path", type=click.Path(path_type=Path),
              required=True, help="Output building-coverage GeoTIFF (0-1).")
@click.option("--min-confidence", type=float, default=0.65, show_default=True,
              help="Drop Open Buildings polygons below this confidence.")
def cli(dem_path: Path, output_path: Path, min_confidence: float) -> None:
    """Rasterise Google Open Buildings footprints to a DEM-aligned coverage fraction."""
    if output_path.exists() and output_path.stat().st_size > 0:
        click.echo(f"[skip] building-coverage raster already exists: {output_path}")
        return

    with rasterio.open(dem_path) as src:
        dem_crs = src.crs
        dem_transform = src.transform
        dem_w, dem_h = src.width, src.height
        dem_bounds = src.bounds

    wgs84 = rasterio.crs.CRS.from_epsg(4326)
    lon0, lat0, lon1, lat1 = transform_bounds(dem_crs, wgs84, *dem_bounds)
    bbox_wgs84 = (lon0, lat0, lon1, lat1)
    click.echo(f"DEM bbox (WGS84): {bbox_wgs84}")

    tiles = _intersecting_tiles(bbox_wgs84)
    click.echo(f"Open Buildings tiles intersecting bbox: {tiles}")
    if not tiles:
        raise click.ClickException("No Open Buildings tiles found for this bbox.")

    polys_wgs = []
    for t in tiles:
        polys_wgs.extend(_load_tile_polygons(t, bbox_wgs84, min_confidence))
    if not polys_wgs:
        raise click.ClickException("No building polygons found in bbox.")
    click.echo(f"Total footprints: {len(polys_wgs):,}")

    # Reproject polygons WGS84 -> DEM CRS
    import geopandas as gpd
    gdf = gpd.GeoDataFrame(geometry=polys_wgs, crs=wgs84).to_crs(dem_crs)

    # Rasterise on a SUBSAMPLE-finer grid, then block-average to DEM resolution
    # to obtain a per-cell coverage fraction.
    from rasterio.transform import Affine
    fine_transform = dem_transform * Affine.scale(1.0 / SUBSAMPLE, 1.0 / SUBSAMPLE)
    fine_w, fine_h = dem_w * SUBSAMPLE, dem_h * SUBSAMPLE
    click.echo(f"Rasterising {len(gdf):,} footprints at {SUBSAMPLE}x ({fine_h}x{fine_w}) ...")
    fine = rasterize(
        ((geom, 1) for geom in gdf.geometry),
        out_shape=(fine_h, fine_w),
        transform=fine_transform,
        fill=0,
        all_touched=False,
        dtype="uint8",
    )
    # Block-average SUBSAMPLE x SUBSAMPLE -> coverage fraction at DEM resolution
    coverage = (
        fine.reshape(dem_h, SUBSAMPLE, dem_w, SUBSAMPLE)
            .mean(axis=(1, 3))
            .astype(np.float32)
    )

    profile = {
        "driver": "GTiff", "dtype": "float32", "count": 1,
        "width": dem_w, "height": dem_h, "crs": dem_crs,
        "transform": dem_transform, "compress": "deflate", "nodata": np.nan,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(coverage, 1)
    built = float((coverage > 0.25).mean()) * 100
    click.echo(
        f"Wrote building-coverage raster: {output_path}  "
        f"(mean cover={coverage.mean():.3f}; {built:.1f}% of cells >25% built)"
    )


if __name__ == "__main__":
    cli()
