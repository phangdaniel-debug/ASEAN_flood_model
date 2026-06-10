"""
Build a Height Above Nearest Drainage (HAND) raster from a DEM and a drainage mask.

Typical usage (OSM river mask, recommended):

    python scripts/build_hand_raster.py \
      --dem data/singapore/copernicus_dem_utm48n.tif \
      --river-raster data/singapore/river_mask_osm_utm48n.tif \
      --output data/singapore/hand_utm48n.tif

Accumulation-based drainage (requires pysheds, slower):

    python scripts/build_hand_raster.py \
      --dem data/singapore/copernicus_dem_utm48n.tif \
      --acc-threshold 500 \
      --output data/singapore/hand_utm48n.tif
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import numpy as np
import rasterio

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.flood_depth_model import load_dem
from model.hand_model import compute_hand, derive_drainage_mask_from_accumulation


@click.command()
@click.option(
    "--dem",
    "dem_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Input DEM GeoTIFF (projected CRS, units: metres).",
)
@click.option(
    "--river-raster",
    "river_raster_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help=(
        "River/drainage mask raster aligned to the DEM (pixels > 0 = drainage cell). "
        "Generate with scripts/build_river_raster_from_osm.py. "
        "If omitted, a drainage mask is derived from flow accumulation via pysheds."
    ),
)
@click.option(
    "--acc-threshold",
    type=int,
    default=500,
    show_default=True,
    help=(
        "Flow-accumulation threshold (pixels) used when --river-raster is not provided. "
        "At 30 m resolution, 500 pixels ≈ 0.45 km² contributing area."
    ),
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    required=True,
    help="Output HAND GeoTIFF (float32, metres, DEFLATE-compressed).",
)
def cli(
    dem_path: Path,
    river_raster_path: Path | None,
    acc_threshold: int,
    output_path: Path,
) -> None:
    dem, profile = load_dem(dem_path)

    if river_raster_path is not None:
        with rasterio.open(river_raster_path) as src:
            river = src.read(1)
            if river.shape != dem.shape:
                raise click.ClickException(
                    f"River raster shape {river.shape} does not match DEM shape {dem.shape}."
                )
            if src.crs != profile["crs"]:
                raise click.ClickException(
                    f"River raster CRS {src.crs} does not match DEM CRS {profile['crs']}."
                )
            if src.transform != profile["transform"]:
                raise click.ClickException(
                    "River raster transform does not match DEM — rasters are not spatially aligned."
                )
        drainage_mask = np.isfinite(river.astype(float)) & (river > 0)
        n_drain = int(np.count_nonzero(drainage_mask))
        click.echo(f"Loaded OSM river mask: {n_drain:,} drainage cells ({river_raster_path})")
    else:
        click.echo(
            f"Deriving drainage network from flow accumulation "
            f"(threshold = {acc_threshold} pixels) ..."
        )
        drainage_mask = derive_drainage_mask_from_accumulation(dem, profile, acc_threshold)
        n_drain = int(np.count_nonzero(drainage_mask))
        click.echo(f"Derived drainage mask: {n_drain:,} cells")

    click.echo("Computing HAND raster (D8 flow-path routing via pysheds) ...")
    hand = compute_hand(dem, drainage_mask, profile)

    profile_out = profile.copy()
    profile_out.update(
        dtype="float32",
        count=1,
        compress="deflate",
        predictor=2,
        nodata=np.nan,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile_out) as dst:
        dst.write(hand, 1)

    finite = np.isfinite(hand)
    click.echo(
        f"Wrote HAND raster : {output_path}\n"
        f"  shape           : {hand.shape[0]} rows × {hand.shape[1]} cols\n"
        f"  valid cells     : {int(np.count_nonzero(finite)):,}\n"
        f"  mean HAND       : {float(np.nanmean(hand)):.2f} m\n"
        f"  max HAND        : {float(np.nanmax(hand)):.2f} m"
    )


if __name__ == "__main__":
    cli()
