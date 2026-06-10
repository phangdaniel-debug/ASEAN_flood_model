"""Fetch dense OSM drainage network for KL and rasterize onto the raingrid DEM.

Fetches:
  (a) ALL waterway line features (drain, ditch, canal, stream, river, etc.)
  (b) ALL highway line features (roads — urban storm drains follow road ROW)

Rasterizes the union onto the raingrid DEM grid (EPSG:32647, 30 m,
shape 1924×2045) → data/kuala_lumpur/drainage_osm_dense_utm47n.tif

Usage:
    python scripts/_fetch_osm_dense_drainage.py \\
        --dem data/kuala_lumpur/copernicus_dem_utm47n_raingrid.tif \\
        --output data/kuala_lumpur/drainage_osm_dense_utm47n.tif

Network note: wraps Overpass API calls with retries.
"""
from __future__ import annotations

import time
from pathlib import Path

import click
import numpy as np
import rasterio
from rasterio.features import rasterize
import osmnx as ox

# KL bounding box (WGS84)
KL_BBOX = dict(min_lon=101.40, min_lat=2.90, max_lon=101.95, max_lat=3.42)

# Buffer radius around line features before rasterization (metres, in UTM CRS)
BUFFER_M = 15.0

MAX_RETRIES = 3
RETRY_DELAY_S = 15


def _fetch_with_retries(
    bbox: dict,
    tags: dict,
    label: str,
    max_retries: int = MAX_RETRIES,
    retry_delay_s: float = RETRY_DELAY_S,
):
    """Fetch OSM features by bbox with retry logic.

    Returns a GeoDataFrame, or raises RuntimeError after all retries.
    """
    north = bbox["max_lat"]
    south = bbox["min_lat"]
    east  = bbox["max_lon"]
    west  = bbox["min_lon"]

    for attempt in range(1, max_retries + 1):
        try:
            click.echo(
                f"  [{label}] Attempt {attempt}/{max_retries}: "
                f"querying Overpass API..."
            )
            # osmnx 2.x bbox order: (left, bottom, right, top) = (west, south, east, north)
            gdf = ox.features_from_bbox(
                bbox=(west, south, east, north), tags=tags
            )
            click.echo(f"  [{label}] Fetched {len(gdf):,} features.")
            return gdf
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  [{label}] Attempt {attempt} failed: {exc}")
            if attempt < max_retries:
                click.echo(f"  [{label}] Retrying in {retry_delay_s}s...")
                time.sleep(retry_delay_s)
            else:
                raise RuntimeError(
                    f"NEEDS_CONTEXT: OSM fetch for '{label}' failed after "
                    f"{max_retries} attempts.  Last error: {exc}"
                ) from exc


def _lines_only(gdf):
    """Keep only LineString / MultiLineString geometries."""
    return gdf[gdf.geometry.type.isin(["LineString", "MultiLineString"])].copy()


@click.command()
@click.option(
    "--dem", "dem_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Reference DEM raster (sets CRS, transform, shape for output).",
)
@click.option(
    "--output", "output_path",
    type=click.Path(path_type=Path),
    default="data/kuala_lumpur/drainage_osm_dense_utm47n.tif",
    show_default=True,
    help="Output dense drainage mask raster.",
)
@click.option(
    "--buffer-m", "buffer_m",
    type=float,
    default=BUFFER_M,
    show_default=True,
    help="Buffer radius (m) around line features before rasterization.",
)
@click.option(
    "--no-roads", "include_roads",
    is_flag=True,
    default=True,
    flag_value=False,
    help="Skip fetching highway features (roads).",
)
def cli(
    dem_path: Path,
    output_path: Path,
    buffer_m: float,
    include_roads: bool,
) -> None:
    """Fetch dense OSM drainage (waterways + roads) for KL and rasterize."""
    with rasterio.open(dem_path) as src:
        dem_crs = src.crs
        dem_transform = src.transform
        dem_shape = (src.height, src.width)
        profile = src.profile.copy()

    click.echo(f"DEM CRS   : {dem_crs}")
    click.echo(f"DEM shape : {dem_shape}  transform: {dem_transform}")
    click.echo(f"KL bbox   : {KL_BBOX}")

    # ------------------------------------------------------------------
    # 1. Fetch waterway features (all types)
    # ------------------------------------------------------------------
    click.echo("\nFetching waterway features...")
    waterway_tags = {"waterway": True}
    gdf_ww = _fetch_with_retries(KL_BBOX, waterway_tags, label="waterway")
    gdf_ww = _lines_only(gdf_ww)
    click.echo(f"  Waterway line features: {len(gdf_ww):,}")

    # ------------------------------------------------------------------
    # 2. Fetch highway features (roads — storm drains follow road ROW)
    # ------------------------------------------------------------------
    all_line_gdfs = [gdf_ww]
    if include_roads:
        click.echo("\nFetching highway (road) features...")
        highway_tags = {"highway": True}
        gdf_hw = _fetch_with_retries(KL_BBOX, highway_tags, label="highway")
        gdf_hw = _lines_only(gdf_hw)
        click.echo(f"  Highway line features : {len(gdf_hw):,}")
        all_line_gdfs.append(gdf_hw)

    # ------------------------------------------------------------------
    # 3. Project to DEM CRS, buffer, collect geometries
    # ------------------------------------------------------------------
    click.echo(f"\nProjecting to {dem_crs} and buffering by {buffer_m} m...")
    shapes = []  # list of (buffered_geom, 1) pairs for rasterize
    for gdf in all_line_gdfs:
        gdf_proj = gdf.to_crs(dem_crs)
        for geom in gdf_proj.geometry:
            if geom is None or geom.is_empty:
                continue
            buffered = geom.buffer(buffer_m)
            if buffered is not None and not buffered.is_empty:
                shapes.append((buffered, 1))

    if not shapes:
        raise click.ClickException("No valid geometries to rasterize.")

    click.echo(f"  Total buffered geometries: {len(shapes):,}")

    # ------------------------------------------------------------------
    # 4. Rasterize all buffered geometries in a single rasterize call.
    #
    # rasterio.features.rasterize iterates the shapes list internally
    # without merging them into a single huge polygon.  This avoids the
    # memory/time cost of unary_union on 300K+ polygons.
    # ------------------------------------------------------------------
    click.echo("Rasterizing all geometries (this may take a few minutes)...")
    mask = rasterize(
        shapes,
        out_shape=dem_shape,
        transform=dem_transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )

    n_drainage = int(np.sum(mask > 0))
    n_total = dem_shape[0] * dem_shape[1]
    click.echo(f"  Drainage cells: {n_drainage:,} / {n_total:,} ({100.0*n_drainage/n_total:.2f}%)")

    # ------------------------------------------------------------------
    # 5. Write output
    # ------------------------------------------------------------------
    profile.update(
        dtype="uint8",
        count=1,
        nodata=0,
        compress="deflate",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(mask, 1)
    click.echo(f"\nWrote dense drainage raster: {output_path}")


if __name__ == "__main__":
    cli()
