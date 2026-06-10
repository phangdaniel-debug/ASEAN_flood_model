from __future__ import annotations

from pathlib import Path

import click
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_geom
from shapely.geometry import shape
from shapely.ops import unary_union

import osmnx as ox


def _is_underground(row) -> bool:
    """
    Return True if an OSM waterway feature is culverted, tunnelled, or
    otherwise flows underground.

    Checked tags:
      tunnel   : culvert | yes | covered | building_passage
      covered  : yes
      layer    : any negative integer (below street level)

    Underground waterways are excluded from the HAND drainage mask because:
    (1) The DEM records road/building surface elevation above the pipe, not
        the actual channel invert, so HAND values around culverts are
        underestimated and cause false surface flooding.
    (2) Culvert hydraulic capacity is not represented — the model would
        predict flooding whenever stage exceeds HAND, ignoring the pipe's
        ability to convey flow without any surface expression.
    (3) D8 flow routing on a flat road surface does not follow the
        underground pipe path, distorting watershed delineation.
    """
    tunnel = str(row.get("tunnel") or "").strip().lower()
    if tunnel in ("culvert", "yes", "covered", "building_passage"):
        return True
    covered = str(row.get("covered") or "").strip().lower()
    if covered == "yes":
        return True
    try:
        layer = int(row.get("layer") or 0)
        if layer < 0:
            return True
    except (ValueError, TypeError):
        pass
    return False


@click.command()
@click.option("--dem", "dem_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--place",
    type=str,
    default=None,
    show_default=True,
    help=(
        "Place query passed to OSM Nominatim.  Resolves to the OSM administrative "
        "boundary for that name.  Use --bbox instead for large metro areas where "
        "the city name resolves to only the core municipality (e.g. 'Manila' resolves "
        "to Manila City proper, not Metro Manila)."
    ),
)
@click.option("--min-lon", "min_lon", type=float, default=None, help="Bounding box west edge (deg).")
@click.option("--min-lat", "min_lat", type=float, default=None, help="Bounding box south edge (deg).")
@click.option("--max-lon", "max_lon", type=float, default=None, help="Bounding box east edge (deg).")
@click.option("--max-lat", "max_lat", type=float, default=None, help="Bounding box north edge (deg).")
@click.option(
    "--buffer-m",
    type=float,
    default=20.0,
    show_default=True,
    help="Buffer around river centerlines before rasterization.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    required=True,
    help="Output river mask raster (>0 means river).",
)
@click.option(
    "--include-underground/--exclude-underground",
    "include_underground",
    default=False,
    show_default=True,
    help=(
        "Include culverted/tunnelled waterways in the drainage mask. "
        "Default is False: underground channels are excluded because the DEM "
        "records surface (road/building) elevation above the pipe rather than "
        "the true channel invert, causing HAND underestimation and false flooding."
    ),
)
def cli(
    dem_path: Path,
    place: str | None,
    min_lon: float | None,
    min_lat: float | None,
    max_lon: float | None,
    max_lat: float | None,
    buffer_m: float,
    output_path: Path,
    include_underground: bool,
) -> None:
    with rasterio.open(dem_path) as src:
        dem_crs = src.crs
        dem_transform = src.transform
        dem_shape = (src.height, src.width)
        profile = src.profile.copy()
        dem_bounds = src.bounds

    # Validate input: must provide either --place or all four --bbox coords.
    has_bbox = all(v is not None for v in (min_lon, min_lat, max_lon, max_lat))
    if not has_bbox and place is None:
        raise click.UsageError(
            "Provide either --place <name> or all four of "
            "--min-lon / --min-lat / --max-lon / --max-lat."
        )
    if has_bbox and place is not None:
        raise click.UsageError("--place and --bbox options are mutually exclusive.")

    tags = {"waterway": True}
    if has_bbox:
        # Query by bounding box — avoids Nominatim misresolution of city names
        # (e.g. 'Manila' → Manila City proper rather than Metro Manila).
        click.echo(
            f"Querying OSM waterways by bbox: "
            f"N={max_lat} S={min_lat} E={max_lon} W={min_lon}"
        )
        # osmnx 2.x expects bbox=(left, bottom, right, top) = (W, S, E, N).
        gdf = ox.features_from_bbox(
            bbox=(min_lon, min_lat, max_lon, max_lat), tags=tags
        )
    else:
        click.echo(f"Querying OSM waterways by place: '{place}'")
        gdf = ox.features_from_place(place, tags=tags)
    if gdf.empty:
        raise click.ClickException("No OSM waterway features found for place query.")

    # Keep linear waterways suitable for fluvial seeding.
    gdf = gdf[gdf.geometry.type.isin(["LineString", "MultiLineString"])]
    if gdf.empty:
        raise click.ClickException("No line-based waterway features found in OSM query.")

    # Filter out underground/culverted channels unless explicitly requested.
    n_total = len(gdf)
    if not include_underground:
        underground_mask = gdf.apply(_is_underground, axis=1)
        n_underground = int(underground_mask.sum())
        gdf = gdf[~underground_mask]
        click.echo(
            f"Filtered out {n_underground:,} underground/culverted features "
            f"({100 * n_underground / n_total:.1f}% of {n_total:,} total). "
            f"{len(gdf):,} open-channel features retained."
        )
        if gdf.empty:
            raise click.ClickException(
                "No open-channel waterway features remain after filtering. "
                "Use --include-underground to override."
            )
    else:
        click.echo(f"Including all {n_total:,} waterway features (underground not filtered).")

    # Work in projected CRS for buffer in meters.
    gdf_proj = gdf.to_crs(dem_crs)
    buffered = gdf_proj.buffer(buffer_m)
    merged = unary_union([geom for geom in buffered if geom is not None and not geom.is_empty])
    if merged.is_empty:
        raise click.ClickException("Buffered river geometry is empty.")

    # Ensure geometry is expressed in DEM CRS.
    geom = merged
    if gdf_proj.crs != dem_crs:
        geom_json = transform_geom(str(gdf_proj.crs), str(dem_crs), geom.__geo_interface__)
        geom = shape(geom_json)

    mask = rasterize(
        [(geom, 1)],
        out_shape=dem_shape,
        transform=dem_transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )

    profile.update(
        dtype="uint8",
        count=1,
        nodata=0,
        compress="deflate",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(mask, 1)
    click.echo(f"Wrote river raster: {output_path}")


if __name__ == "__main__":
    cli()
