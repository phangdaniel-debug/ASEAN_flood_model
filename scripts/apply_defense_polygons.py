"""
Apply polygon-based flood-defense protection as a post-process step.

Background
----------
The line-based DEM burn-in in scripts/apply_flood_defenses.py only weakly
reduces bathtub-solver flood extents because BFS connectivity routes water
through sea-masked river channels that pierce the defended area (e.g. the
Chao Phraya inside the BMA).  This script implements **polygon-based**
protection as a post-process step: for each defended polygon and each RP
flood depth raster, if the polygon's defense crest exceeds the modelled
water level, the depth inside the polygon is zeroed out.

This is a screening-grade representation of "the documented defense ring
holds at crest height X" — not an engineering overtopping model.  When
WL > crest the polygon is left unprotected (defense overtops, full
inundation), which is the conservative-but-defensible engineering bound.

Per-city polygon configs hard-coded here from the same BMA / RID
literature as scripts/apply_flood_defenses.py.

Usage::

    python scripts/apply_defense_polygons.py --city bangkok \\
        --scenario SSP2-4.5 --horizon 2050

The script reads ``outputs/<slug>_<scenario>_<horizon>_defended/`` and
writes a parallel ``..._defended_polygons/`` directory with protected
depth rasters.  Falls back to the no-defense outputs directory when the
``_defended`` variant is absent.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import click
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize
from shapely.geometry import Polygon, mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]

POLYGON_CONFIGS: dict[str, dict] = {
    "bangkok": {
        "msl_to_egm2008_offset": 1.1785,
        "polygons": [
            {
                "name": "Inner BMA inside King's Dyke + Chao Phraya banks",
                "crest_msl_m": 2.0,   # binding crest = lowest of King's Dyke (2.5)
                                       # vs Chao Phraya banks (2.0)
                "vertices_lonlat": [
                    [100.510, 13.920],   # NW (Nonthaburi border on left bank)
                    [100.610, 13.920],   # N (Don Mueang inner edge)
                    [100.700, 13.860],   # NE (Khlong Sam Wa)
                    [100.720, 13.760],   # E (Saphan Sung)
                    [100.700, 13.700],   # SE (Prawet)
                    [100.640, 13.660],   # SE (Bangna inner)
                    [100.605, 13.640],   # S (Bangna coast)
                    [100.555, 13.700],   # SW (Khlong Toei waterfront)
                    [100.510, 13.860],   # W (Chao Phraya left bank Dusit)
                    [100.510, 13.920],   # close
                ],
                "source_note": (
                    "Approximate envelope of the BMA core protected by "
                    "King's Dyke (east) + Chao Phraya left-bank dyke (west). "
                    "Binding crest = lowest of the perimeter dykes."
                ),
            },
            {
                "name": "Bang Krachao peninsula (polder ring)",
                "crest_msl_m": 3.0,
                "vertices_lonlat": [
                    [100.545, 13.690],
                    [100.560, 13.690],
                    [100.570, 13.680],
                    [100.570, 13.670],
                    [100.560, 13.660],
                    [100.545, 13.655],
                    [100.535, 13.665],
                    [100.535, 13.680],
                    [100.545, 13.690],
                ],
                "source_note": "RID Bang Krachao polder ring (~3 m crest).",
            },
        ],
    },
}


def _build_polygon_mask(
    config: dict,
    depth_path: Path,
):
    """Return (poly_mask, crest_raster) on the depth-raster grid.

    poly_mask[i,j] = True if pixel is inside any defended polygon.
    crest_raster[i,j] = highest defense crest (EGM2008) covering that pixel,
                       or NaN outside polygons.
    """
    with rasterio.open(depth_path) as ds:
        shape = ds.shape
        transform = ds.transform
        crs = ds.crs

    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    shapes_crest: list[tuple] = []
    for p in config["polygons"]:
        crest_egm = float(p["crest_msl_m"]) + float(config["msl_to_egm2008_offset"])
        verts_xy = [transformer.transform(lon, lat) for lon, lat in p["vertices_lonlat"]]
        poly = Polygon(verts_xy)
        shapes_crest.append((mapping(poly), crest_egm))

    crest_raster = rasterize(
        shapes_crest,
        out_shape=shape,
        transform=transform,
        fill=np.nan,
        dtype="float32",
    )
    poly_mask = np.isfinite(crest_raster)
    return poly_mask, crest_raster


def apply_polygons_to_raster(
    depth_path: Path,
    out_path: Path,
    water_level_m: float,
    config: dict,
    overtop_attenuation: float = 1.0,
) -> tuple[int, float]:
    """Zero out depth inside polygons where crest >= water_level_m.

    Where crest < water_level_m, the polygon is treated as overtopped and
    its depth is multiplied by ``overtop_attenuation`` (default 1.0, i.e.
    no attenuation — defense overtopped means full inundation).

    Returns (n_pixels_protected, area_protected_km2).
    """
    poly_mask, crest_raster = _build_polygon_mask(config, depth_path)

    with rasterio.open(depth_path) as src:
        depth = src.read(1)
        profile = src.profile.copy()
        pixel_area_m2 = abs(src.res[0] * src.res[1])

    # Where the polygon holds (crest >= WL), set depth to 0
    protected = poly_mask & (crest_raster >= water_level_m)
    overtopped = poly_mask & (crest_raster < water_level_m)

    new_depth = depth.astype(np.float32).copy()
    new_depth[protected] = 0.0
    if overtop_attenuation != 1.0:
        new_depth[overtopped] = depth[overtopped].astype(np.float32) * overtop_attenuation

    out_path.parent.mkdir(parents=True, exist_ok=True)
    profile.update(dtype="float32", compress="deflate", predictor=2)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(new_depth, 1)

    n_protected = int((protected & (depth > 0.01)).sum())
    area_km2 = n_protected * pixel_area_m2 / 1e6
    return n_protected, area_km2


@click.command()
@click.option("--city", "city_slug",
              type=click.Choice(list(POLYGON_CONFIGS)), required=True)
@click.option("--scenario", required=True)
@click.option("--horizon", type=int, required=True)
@click.option("--source-suffix", default="",
              help="Suffix on the source output dir (e.g. '_defended').")
@click.option("--out-suffix", default="_defended_polygons",
              help="Suffix on the destination output dir.")
@click.option("--overtop-attenuation", type=float, default=1.0,
              help=("Multiplier applied to depth inside polygons that are "
                    "overtopped (crest < WL).  Default 1.0 = no attenuation."))
def cli(city_slug: str, scenario: str, horizon: int,
        source_suffix: str, out_suffix: str, overtop_attenuation: float) -> None:
    config = POLYGON_CONFIGS[city_slug]
    sce_slug = scenario.lower().replace("-", "").replace(".", "")
    src_dir = PROJECT_ROOT / "outputs" / f"{city_slug}_{sce_slug}_{horizon}{source_suffix}"
    dst_dir = PROJECT_ROOT / "outputs" / f"{city_slug}_{sce_slug}_{horizon}{out_suffix}"

    if not src_dir.exists():
        click.echo(f"[error] source dir not found: {src_dir}", err=True)
        sys.exit(2)

    summary_csv = src_dir / f"summary_{scenario}_{horizon}.csv"
    if not summary_csv.exists():
        click.echo(f"[error] summary CSV not found: {summary_csv}", err=True)
        sys.exit(2)

    import pandas as pd
    df = pd.read_csv(summary_csv)

    dst_dir.mkdir(parents=True, exist_ok=True)
    click.echo(
        f"Apply defense polygons\n"
        f"  city  : {city_slug}\n"
        f"  source: {src_dir}\n"
        f"  output: {dst_dir}\n"
    )

    # Process every depth raster
    n_polys = len(config["polygons"])
    click.echo(f"Polygons ({n_polys}):")
    for p in config["polygons"]:
        crest_egm = p["crest_msl_m"] + config["msl_to_egm2008_offset"]
        click.echo(f"  - {p['name']}: crest {p['crest_msl_m']:.2f} m MSL "
                   f"-> {crest_egm:.4f} m EGM2008")
    click.echo()

    rows = []
    for hazard in ("coastal", "fluvial", "pluvial"):
        for rp_dir in sorted((src_dir / hazard).glob("rp_*"),
                             key=lambda d: int(d.name.split("_")[1])):
            rp = int(rp_dir.name.split("_")[1])
            depth_paths = list(rp_dir.glob(f"{hazard}_depth_*.tif"))
            if not depth_paths:
                continue
            depth_path = depth_paths[0]
            dst_rp = dst_dir / hazard / f"rp_{rp}"
            dst_rp.mkdir(parents=True, exist_ok=True)
            out_path = dst_rp / depth_path.name

            # Look up WL from summary CSV
            row = df[(df.hazard_type == hazard) & (df.return_period == rp)]
            if row.empty:
                shutil.copy2(depth_path, out_path)
                continue
            wl = float(row.water_level_m.iloc[0])
            n_prot, area_prot = apply_polygons_to_raster(
                depth_path, out_path, wl, config, overtop_attenuation
            )
            rows.append((hazard, rp, wl, n_prot, area_prot))

    click.echo(f"\n{'Hazard':<8} {'RP':>5}  {'WL (m)':>7}  {'Protected px':>12}  {'Area km²':>9}")
    click.echo("-" * 48)
    for h, rp, wl, n, a in rows:
        click.echo(f"{h:<8} {rp:>5}  {wl:>7.3f}  {n:>12,}  {a:>9.2f}")

    click.echo(f"\nWrote {len(rows)} depth rasters to {dst_dir}")


if __name__ == "__main__":
    cli()
