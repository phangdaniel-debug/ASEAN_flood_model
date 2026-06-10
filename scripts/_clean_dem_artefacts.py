"""
One-off DEM artefact-spike cleanup.

The GLO-30 TanDEM-X DEM occasionally contains spurious very-negative pixel
values where radar coherence was low or processing produced outliers.  In
HCMC the raw DEM has 3,691 land pixels below −5 m and ~822 below −50 m
(min −83 m), none of which correspond to real terrain — documented HCMC
subsidence reaches at most ~−3 m even in worst-case Phu My Hung / District 7
polder cells.  These spikes are invisible in the default ``clamp_negative_land``
mode (they are clamped to 0) but propagate as ~80 m flood depths when
``--no-clamp-negative-land`` is enabled.

This script replaces each spike pixel with the **median of its 7×7
neighbourhood**, excluding nodata and other spike pixels.  The result is a
DEM that is locally smooth across the artefacts but otherwise identical to
the input.  Sea pixels are passed through unchanged (the sea mask is built
later and does not depend on the negative-z spikes).

Inputs / outputs:
  - input:   raw Copernicus DEM (e.g. data/<city>/copernicus_dem_<utm>.tif)
  - output:  overwrites the input in place; the original is preserved as
             ``*_uncleaned.tif`` next to it before the first cleanup pass

After cleanup, re-run apply_subsidence_correction.py (or the full
``run_city_pipeline.py``) to refresh downstream artefacts.

Usage::

    python scripts/_clean_dem_artefacts.py --dem data/hcmc/copernicus_dem_utm48n.tif
    python scripts/_clean_dem_artefacts.py --dem ... --floor -5.0 --window 7
    python scripts/_clean_dem_artefacts.py --dem ... --dry-run

The script is idempotent: if the input already contains no spike pixels
below the floor, no changes are written.
"""
from __future__ import annotations

from pathlib import Path

import click
import numpy as np
import rasterio
from scipy.ndimage import generic_filter


def _local_median_at_spikes(
    dem: np.ndarray,
    spike_mask: np.ndarray,
    valid_mask: np.ndarray,
    window: int,
) -> np.ndarray:
    """Replace each spike pixel with the median of its window neighbours.

    The median is computed over neighbours that are (a) valid (finite, not
    nodata) and (b) **not themselves spike pixels**, so clusters of
    adjacent artefacts do not contaminate each other's replacement value.
    Sea cells are excluded from the eligible neighbour set when a sea mask
    is supplied via ``valid_mask``.
    """
    half = window // 2
    out = dem.copy()
    rows, cols = np.where(spike_mask)
    h, w = dem.shape
    for r, c in zip(rows, cols):
        r0, r1 = max(0, r - half), min(h, r + half + 1)
        c0, c1 = max(0, c - half), min(w, c + half + 1)
        block = dem[r0:r1, c0:c1]
        eligible = valid_mask[r0:r1, c0:c1] & ~spike_mask[r0:r1, c0:c1]
        if eligible.any():
            out[r, c] = float(np.median(block[eligible]))
        # else: leave the pixel unchanged (entire window is spike/invalid)
    return out


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--dem", "dem_path", type=click.Path(path_type=Path, exists=True),
              required=True, help="Raw DEM GeoTIFF to clean in place.")
@click.option("--floor", type=float, default=-5.0, show_default=True,
              help="Land pixels with z below this threshold (m) are treated as "
                   "artefact spikes and replaced.  −5 m is conservative for "
                   "tropical-delta cities (documented subsidence-driven polder "
                   "minima are around −3 m).")
@click.option("--window", type=int, default=7, show_default=True,
              help="Side length of the square neighbourhood window used for "
                   "median replacement.  Must be odd.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Report what would change without writing the cleaned DEM.")
def main(dem_path: Path, floor: float, window: int, dry_run: bool) -> None:
    if window < 3 or window % 2 == 0:
        raise click.BadParameter("--window must be an odd integer ≥ 3")

    with rasterio.open(dem_path) as ds:
        dem = ds.read(1).astype(np.float64)
        profile = ds.profile.copy()
        nodata = ds.nodata

    valid = np.isfinite(dem) & (dem > -1e4)
    if nodata is not None:
        valid &= dem != nodata
    spike = valid & (dem < floor)
    n_spike = int(spike.sum())
    if n_spike == 0:
        click.echo(f"  {dem_path.name}: no spike pixels below {floor:g} m — nothing to do.")
        return

    z_spike = dem[spike]
    click.echo(
        f"  {dem_path.name}: {n_spike:,d} spike pixels below {floor:g} m  "
        f"(range {z_spike.min():.2f} to {z_spike.max():.2f} m; "
        f"median {np.median(z_spike):.2f} m)"
    )

    if dry_run:
        click.echo("  --dry-run: not writing.")
        return

    cleaned = _local_median_at_spikes(dem, spike, valid, window)

    # Verify cleanup
    new_spike = (cleaned < floor) & valid
    click.echo(
        f"  after cleanup: {int(new_spike.sum()):,d} pixels still below {floor:g} m "
        f"(should be 0 unless surrounded by spikes); replacement values: "
        f"min {cleaned[spike].min():.2f}, max {cleaned[spike].max():.2f}, "
        f"median {np.median(cleaned[spike]):.2f}"
    )

    backup_path = dem_path.with_name(dem_path.stem + "_uncleaned.tif")
    if not backup_path.exists():
        click.echo(f"  saving backup of original: {backup_path.name}")
        with rasterio.open(backup_path, "w", **profile) as ds:
            ds.write(dem.astype(profile["dtype"]), 1)
    else:
        click.echo(f"  backup already exists — not overwriting: {backup_path.name}")

    with rasterio.open(dem_path, "w", **profile) as ds:
        ds.write(cleaned.astype(profile["dtype"]), 1)
    click.echo(f"  wrote cleaned DEM in place: {dem_path}")


if __name__ == "__main__":
    main()
