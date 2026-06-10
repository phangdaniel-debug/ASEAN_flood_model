"""
Clip a sea-mask raster to documented tidal reaches.

Background
----------
The default `build_sea_mask.py` performs a BFS from the NaN raster
boundary through all pixels with DEM ≤ 0 m.  In delta cities the BFS
extends far upstream along the main river channel (which has bed
elevation below MSL), so the sea_mask covers the **entire tidal +
fluvial channel network up to the watershed divide** — not just the
true tidal limit.

The bathtub flood solver uses sea_mask as the BFS source.  When the
sea_mask includes upstream fluvial channel pixels, seawater
"propagates" upstream regardless of channel slope, friction, or
backwater attenuation — producing the bathtub-bias-factor problem
documented in §6.5 of the methodology doc (RP2 bias 7-182× across
cities).

This script applies a **lat-bounded restriction**: pixels in the
sea_mask whose latitude exceeds the documented tidal limit are
reset to non-sea.  The resulting "restricted" sea_mask captures
only the truly tidal reach.

Per-city tidal-limit latitudes are documented from regional
hydrology references.

Usage::

    python scripts/restrict_sea_mask.py --city bangkok
    python scripts/restrict_sea_mask.py --city bangkok --dry-run
"""
from __future__ import annotations

from pathlib import Path

import click
import numpy as np
import rasterio
from pyproj import Transformer


RESTRICTION_CONFIGS: dict[str, dict] = {
    "bangkok": {
        # Chao Phraya tidal limit: ~13.85°N (~just upstream of Nonthaburi,
        # before the channel narrows enough to attenuate astronomical tides
        # to below 0.1 m amplitude).
        # Reference: BMA Drainage Master Plan; Surekha et al. 2018 on
        # tidal characteristics of the lower Chao Phraya.
        "tidal_limit_lat": 13.85,
        "default_sea_mask": "sea_mask_utm47n.tif",
        "rationale": (
            "Chao Phraya tidal limit ~13.85°N (~Nonthaburi south).  Above this "
            "the channel is fluvial-dominated; bathtub seawater propagation "
            "is unphysical."
        ),
    },
}


def restrict_sea_mask(
    sea_mask_path: Path,
    tidal_limit_lat: float,
    out_path: Path,
    dry_run: bool = False,
) -> dict:
    with rasterio.open(sea_mask_path) as src:
        mask = src.read(1)
        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs
        height, width = src.shape

    # For each pixel row, compute its WGS84 latitude (centre of row)
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    # Use the column centre as representative x
    x_centre = transform.c + (width / 2) * transform.a
    ys = np.array([transform.f + (r + 0.5) * transform.e for r in range(height)])
    xs = np.full(height, x_centre)
    _lons, lats = transformer.transform(xs, ys)

    above_tidal_limit = lats > tidal_limit_lat  # rows whose centre is north of limit
    n_rows_clipped = int(above_tidal_limit.sum())

    restricted = mask.copy()
    n_before = int((mask > 0).sum())
    # Zero out sea-mask pixels north of tidal limit
    for r in np.where(above_tidal_limit)[0]:
        restricted[r, :] = 0
    n_after = int((restricted > 0).sum())
    n_removed = n_before - n_after
    pixel_area_m2 = abs(transform.a * transform.e)
    area_removed_km2 = n_removed * pixel_area_m2 / 1e6

    stats = {
        "rows_clipped": n_rows_clipped,
        "pixels_before": n_before,
        "pixels_after": n_after,
        "pixels_removed": n_removed,
        "area_removed_km2": area_removed_km2,
    }
    click.echo(
        f"  Tidal limit  : {tidal_limit_lat:.3f}°N\n"
        f"  Rows clipped : {n_rows_clipped:,} of {height:,} "
        f"({n_rows_clipped/height*100:.1f}%)\n"
        f"  Sea-mask px before: {n_before:>10,}\n"
        f"  Sea-mask px after : {n_after:>10,}\n"
        f"  Removed     : {n_removed:>10,}  ({area_removed_km2:.1f} km²)"
    )

    if dry_run:
        click.echo("\n[dry-run] Output not written.")
        return stats

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(restricted, 1)
    click.echo(f"\nWrote {out_path}")
    return stats


@click.command()
@click.option("--city", "city_slug",
              type=click.Choice(list(RESTRICTION_CONFIGS)), required=True)
@click.option("--sea-mask", "sea_mask_path", type=click.Path(path_type=Path), default=None,
              help="Input sea-mask raster (default: data/<city>/<default_sea_mask>).")
@click.option("--output", "out_path", type=click.Path(path_type=Path), default=None,
              help="Output path (default: <stem>_restricted.tif next to input).")
@click.option("--dry-run", is_flag=True, default=False)
def cli(city_slug: str, sea_mask_path: Path | None, out_path: Path | None,
        dry_run: bool) -> None:
    project_root = Path(__file__).resolve().parents[1]
    config = RESTRICTION_CONFIGS[city_slug]
    if sea_mask_path is None:
        sea_mask_path = project_root / "data" / city_slug / config["default_sea_mask"]
    if out_path is None:
        out_path = sea_mask_path.with_name(sea_mask_path.stem + "_restricted.tif")
    click.echo(
        f"Restrict sea mask to documented tidal reach\n"
        f"  city  : {city_slug}\n"
        f"  in    : {sea_mask_path}\n"
        f"  out   : {out_path}\n"
        f"  ratio : {config['rationale']}\n"
    )
    restrict_sea_mask(sea_mask_path, config["tidal_limit_lat"], out_path, dry_run)


if __name__ == "__main__":
    cli()
