"""Hydrologically condition a bare-earth DEM to suppress GLO-30 noise pits
that over-segment the rain-on-grid pluvial output.

Steps (in order):
  1. Burn the open drainage network (OSM canals/rivers) down by a fixed depth
     so overland flow concentrates along real channels rather than ponding in
     noise hollows beside them.
  2. Moderate median smoothing to remove cell-scale vertical noise.
  3. Shallow-pit fill: fill any closed depression whose maximum depth is below
     the DEM vertical-noise floor (default 0.5 m).  These are noise artefacts,
     not real ponding basins; genuine deeper basins are preserved.

Output: <dem_stem>_conditioned.tif, for rain-on-grid pluvial routing.
"""
import sys
from pathlib import Path

import click
import numpy as np
import rasterio
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model.hand_model import fill_depressions  # noqa: E402


def depit_dem(dem, profile, finite, *, noise_pit_depth_m=0.5,
              deep_pit_depth_m=None, sea_level_m=0.0):
    """Classify enclosed depressions and fill a selected subset.

    Always fills shallow noise pits (max depth < ``noise_pit_depth_m``).
    When ``deep_pit_depth_m`` is not None (raingrid mode), ALSO fills any
    depression whose floor elevation < ``sea_level_m`` (DSM artifact) or whose
    max depth >= ``deep_pit_depth_m`` (unphysical). Genuine shallow hollows
    (floor >= sea level, depth in [noise, deep)) are preserved.

    Returns (out_dem float64, stats dict).
    """
    work = np.where(finite, dem, np.nan)
    filled = fill_depressions(work, profile).astype(np.float64)
    pit_depth = np.where(finite, filled - dem, 0.0)
    pit_depth[~np.isfinite(pit_depth)] = 0.0

    labels, n = ndimage.label(pit_depth > 0.0, structure=np.ones((3, 3), dtype=int))
    out = dem.copy()
    stats = {"n_depressions": int(n), "n_shallow": 0, "n_artifact": 0, "n_deep": 0,
             "n_filled_cells": 0}
    if n:
        idx = range(1, n + 1)
        max_depth = np.asarray(ndimage.maximum(pit_depth, labels, idx))
        floor = np.asarray(ndimage.minimum(dem, labels, idx))
        shallow = max_depth < noise_pit_depth_m
        fill = shallow.copy()
        stats["n_shallow"] = int(shallow.sum())
        if deep_pit_depth_m is not None:
            artifact = floor < sea_level_m
            deep = max_depth >= deep_pit_depth_m
            fill = shallow | artifact | deep
            stats["n_artifact"] = int(artifact.sum())
            stats["n_deep"] = int(deep.sum())
        fill_labels = np.flatnonzero(fill) + 1
        mask = np.isin(labels, fill_labels)
        out = np.where(mask, filled, dem)
        stats["n_filled_cells"] = int(mask.sum())
    return out, stats


@click.command()
@click.option("--dem", "dem_path", type=click.Path(exists=True, path_type=Path),
              required=True, help="Bare-earth DEM GeoTIFF.")
@click.option("--drainage-raster", "drain_path",
              type=click.Path(exists=True, path_type=Path), default=None,
              help="OSM river/canal raster (>0 = channel).")
@click.option("--sea-mask", "sea_path",
              type=click.Path(exists=True, path_type=Path), default=None,
              help="Sea mask (1=land, 0=sea); conditioning is applied on land only.")
@click.option("--output", "output_path", type=click.Path(path_type=Path),
              required=True, help="Output conditioned DEM GeoTIFF.")
@click.option("--drainage-burn-m", type=float, default=1.5, show_default=True,
              help="Lower channel cells by this depth (m).")
@click.option("--median-size", type=int, default=5, show_default=True,
              help="Median-filter window (cells); 1 = disabled.")
@click.option("--noise-pit-depth-m", type=float, default=0.5, show_default=True,
              help="Fill closed depressions shallower than this (m).")
@click.option("--raingrid-out", "raingrid_out", type=click.Path(path_type=Path),
              default=None,
              help="If set, also emit a surgically de-pitted DEM for rain-on-grid "
                   "(fills artifact + deep depressions; keeps shallow real hollows).")
@click.option("--deep-pit-depth-m", type=float, default=3.0, show_default=True,
              help="Raingrid: fill depressions whose max depth >= this (m). "
                   "Anchored to the validate_pluvial_singapore engineering cap.")
@click.option("--sea-level-m", type=float, default=0.0, show_default=True,
              help="Raingrid: fill depressions whose floor elevation < this (m, "
                   "sub-sea-level land = DSM artifact).")
def cli(dem_path: Path, drain_path: Path, sea_path: Path, output_path: Path,
        drainage_burn_m: float, median_size: int, noise_pit_depth_m: float,
        raingrid_out: Path, deep_pit_depth_m: float, sea_level_m: float) -> None:
    """Produce a hydrologically conditioned DEM for pluvial routing."""
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float64)
        profile = src.profile
        nodata = src.nodata
    finite = np.isfinite(dem)
    if nodata is not None:
        finite &= dem != nodata

    land = finite
    if sea_path:
        with rasterio.open(sea_path) as s:
            sm = s.read(1)
        land = finite & (sm == 1)

    # 1. Burn drainage network down.
    if drain_path:
        with rasterio.open(drain_path) as s:
            dr = s.read(1)
        chan = (dr > 0) & finite
        dem[chan] -= drainage_burn_m
        click.echo(f"Burned {int(chan.sum()):,} channel cells down {drainage_burn_m} m")

    # 2. Median smoothing on land.
    if median_size and median_size > 1:
        med = ndimage.median_filter(dem, size=median_size)
        dem = np.where(land, med, dem)
        click.echo(f"Applied {median_size}x{median_size} median over land")

    # 3. Shallow-pit fill (conditioned output): fill only noise pits.
    dem, stats = depit_dem(dem, profile, finite,
                           noise_pit_depth_m=noise_pit_depth_m, deep_pit_depth_m=None)
    click.echo(
        f"Conditioned: filled {stats['n_filled_cells']:,} cells in "
        f"{stats['n_shallow']:,}/{stats['n_depressions']:,} shallow noise pits "
        f"(<{noise_pit_depth_m} m); kept {stats['n_depressions'] - stats['n_shallow']:,} basins")

    out = dem.astype(np.float32)
    if nodata is not None:
        out[~finite] = nodata

    profile.update(dtype="float32", compress="deflate")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(out, 1)
    if raingrid_out is not None:
        # Surgical de-pitting for rain-on-grid: start from the conditioned dem
        # (shallow already filled) and additionally fill artifact + deep pits.
        rg, rg_stats = depit_dem(dem, profile, finite,
                                 noise_pit_depth_m=noise_pit_depth_m,
                                 deep_pit_depth_m=deep_pit_depth_m,
                                 sea_level_m=sea_level_m)
        rg_out = rg.astype(np.float32)
        if nodata is not None:
            rg_out[~finite] = nodata
        Path(raingrid_out).parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(raingrid_out, "w", **profile) as dst:
            dst.write(rg_out, 1)
        click.echo(
            f"Wrote raingrid DEM: {raingrid_out} "
            f"(filled {rg_stats['n_artifact']:,} artifact + {rg_stats['n_deep']:,} deep "
            f"depressions; deep>= {deep_pit_depth_m} m, floor< {sea_level_m} m)")
    click.echo(f"Wrote conditioned DEM: {output_path}")


if __name__ == "__main__":
    cli()
