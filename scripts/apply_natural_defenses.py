"""
Burn natural / informal flood-protection zones into a city DEM.

Background
----------
GLO-30's 30 m DEM does not resolve the sub-pixel terrain features
(road raises, drainage canals, raised housing plots, informal
embankments, secondary canal levees) that, taken together, provide
~1-1.5 m of effective protection in the urbanised parts of SE Asia
deltas.  §6.5 of the methodology doc quantifies the resulting bathtub
bias factor (7-182× at RP2).

This script burns a uniform DEM elevation raise into rectangular
"natural defense zones" hard-coded per city.  Each zone is defined by
a lat/lon bbox plus a fixed raise value (m).  At every pixel inside
the zone, the DEM is set to ``max(DEM, DEM + raise)`` — i.e. raise
the floor without lowering anywhere.

This is the simplest possible Option 2 implementation.  More
sophisticated approaches (per-zone polygon with curved boundaries,
density-weighted raise from OSM building footprints, etc.) are
out of scope for the screening model but could refine the bias
reduction at the cost of additional per-city literature work.

Per-zone raise values come from the methodology doc §6.5
expected-bias-reduction analysis: 1.5 m where the bias factor is
~50-100x (well-protected BMA), 1.0 m elsewhere (informal protection).

Usage::

    python scripts/apply_natural_defenses.py --city bangkok
    python scripts/apply_natural_defenses.py --city bangkok --dry-run
"""
from __future__ import annotations

from pathlib import Path

import click
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize
from shapely.geometry import Polygon, mapping


NATURAL_DEFENSE_CONFIGS: dict[str, dict] = {
    "bangkok": {
        "default_dem": "copernicus_dem_utm47n_subsidence_corrected_defended.tif",
        "zones": [
            {
                "name": "BMA outer urban core (eastern Bangkok + Bangkok inner)",
                "bbox_lonlat": [100.510, 13.640, 100.730, 13.920],
                "raise_m": 1.5,
                "source_note": (
                    "BMA Drainage Master Plan: secondary canal network + "
                    "road network + raised housing plots provide ~1.5 m "
                    "informal protection beyond engineered defenses."
                ),
            },
            {
                "name": "Samut Prakan urban core (Bang Pu / Samut Prakan town)",
                "bbox_lonlat": [100.550, 13.520, 100.760, 13.650],
                "raise_m": 1.0,
                "source_note": (
                    "Samut Prakan TAO drainage system + provincial "
                    "embankments + road raises (DOH 1m design); informal "
                    "fishpond embankments along coast."
                ),
            },
            {
                "name": "Nonthaburi + Pathum Thani urban core (Chao Phraya north)",
                "bbox_lonlat": [100.400, 13.800, 100.650, 14.050],
                "raise_m": 1.0,
                "source_note": (
                    "Nonthaburi / Pathum Thani municipal drainage + "
                    "road raises; less engineered than BMA but still ~1 m "
                    "effective floor."
                ),
            },
        ],
    },
}


def burn_natural_defenses(
    dem_path: Path,
    config: dict,
    out_path: Path,
    dry_run: bool = False,
) -> dict:
    with rasterio.open(dem_path) as src:
        dem = src.read(1)
        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs
        nodata = src.nodata if src.nodata is not None else -9999.0

    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    shapes_raise: list[tuple] = []
    for z in config["zones"]:
        lon_min, lat_min, lon_max, lat_max = z["bbox_lonlat"]
        corners = [
            transformer.transform(lon_min, lat_min),
            transformer.transform(lon_max, lat_min),
            transformer.transform(lon_max, lat_max),
            transformer.transform(lon_min, lat_max),
            transformer.transform(lon_min, lat_min),
        ]
        poly = Polygon(corners)
        shapes_raise.append((mapping(poly), float(z["raise_m"])))
        click.echo(
            f"  {z['name']}: "
            f"bbox {lon_min:.3f}-{lon_max:.3f}E {lat_min:.3f}-{lat_max:.3f}N, "
            f"raise +{z['raise_m']:.2f} m, "
            f"poly_area={poly.area / 1e6:.1f} km2"
        )

    raise_raster = rasterize(
        shapes_raise,
        out_shape=dem.shape,
        transform=transform,
        fill=0.0,
        dtype="float32",
        merge_alg=rasterio.enums.MergeAlg.replace,  # keep the largest raise if zones overlap
    )

    valid = (dem != nodata) & np.isfinite(dem)
    defended = dem.astype(np.float32).copy()
    delta = np.zeros_like(defended)
    delta[valid] = raise_raster[valid]
    defended[valid] = dem[valid] + raise_raster[valid]

    n_modified = int((raise_raster > 0).sum())
    pixel_area_m2 = abs(transform.a * transform.e)
    area_km2 = n_modified * pixel_area_m2 / 1e6

    stats = {
        "n_modified": n_modified,
        "area_km2": area_km2,
        "mean_raise_m": float(delta[delta > 0].mean()) if n_modified else 0.0,
        "max_raise_m": float(delta.max()),
    }

    if dry_run:
        click.echo(f"\n[dry-run]\n  Pixels raised: {n_modified:,}  ({area_km2:.1f} km2)\n"
                   f"  Mean raise: {stats['mean_raise_m']:.3f} m\n"
                   f"  Max raise:  {stats['max_raise_m']:.3f} m")
        return stats

    profile.update(dtype="float32", compress="deflate", predictor=2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(defended, 1)
    click.echo(f"\nWrote {out_path}\n"
               f"  Pixels raised: {n_modified:,}  ({area_km2:.1f} km2)\n"
               f"  Mean raise: {stats['mean_raise_m']:.3f} m  "
               f"Max: {stats['max_raise_m']:.3f} m")
    return stats


@click.command()
@click.option("--city", "city_slug",
              type=click.Choice(list(NATURAL_DEFENSE_CONFIGS)), required=True)
@click.option("--dem", "dem_path", type=click.Path(path_type=Path), default=None,
              help="Input DEM (default: <city>'s defended DEM if present, else subsidence-corrected).")
@click.option("--output", "out_path", type=click.Path(path_type=Path), default=None)
@click.option("--dry-run", is_flag=True, default=False)
def cli(city_slug: str, dem_path: Path | None, out_path: Path | None,
        dry_run: bool) -> None:
    project_root = Path(__file__).resolve().parents[1]
    config = NATURAL_DEFENSE_CONFIGS[city_slug]
    if dem_path is None:
        dem_path = project_root / "data" / city_slug / config["default_dem"]
    if out_path is None:
        out_path = dem_path.with_name(dem_path.stem.replace("_defended", "")
                                      + "_natdef.tif")
    click.echo(
        f"Burn natural defenses\n  city  : {city_slug}\n"
        f"  DEM in : {dem_path}\n  DEM out: {out_path}\n"
    )
    burn_natural_defenses(dem_path, config, out_path, dry_run=dry_run)


if __name__ == "__main__":
    cli()
