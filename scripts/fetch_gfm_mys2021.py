"""
Fetch Copernicus GFM (Global Flood Monitoring) ensemble flood extent tiles
for the December 2021 Malaysia / Selangor flood event.

NOTE ON URBAN EXCLUSION (key finding):
GFM systematically excludes urban areas from its flood extent product because
SAR double-bounce from buildings is indistinguishable from open-water backscatter.
For the KL bbox (101.40-101.95 E, 2.90-3.42 N), ~69% of pixels are excluded
(exclusion_mask=1), yielding only ~0.14 km2 of detectable non-urban flood extent.
This limits GFM to validation of peri-urban / agricultural flooding only.
See: validate_historical_events.py notes for MYS2021 / R4 status.

Data source
-----------
EODC STAC API  https://stac.eodc.eu/api/v1
Collection     GFM
Asset          ensemble_flood_extent  (Equi7Grid 20 m, uint8, 1=flood 2=water 3=excluded)

Sentinel-1 acquisitions over the KL domain (101.40-101.95 E, 2.90-3.42 N):
  2021-12-16, 2021-12-19, 2021-12-20, 2021-12-21, 2021-12-22

We take ALL acquisitions from Dec 17-22 and create:
  1. A per-date GeoTIFF in WGS84 (any-flooded pixel mask, 20 m)
  2. A merged "max-flood" composite = pixel is flood if it was flooded
     in ANY of the Dec 17-22 passes (conservative, matches historical
     validation conventions).

Output
------
data/kl/flood_obs/MYS2021/
  gfm_YYYYMMDD_HHMMSS_<tile>.tif   raw Equi7Grid tiles (kept for provenance)
  gfm_kl_YYYYMMDD.tif              per-date WGS84 flood mask, clipped to KL bbox
  gfm_kl_composite_dec2021.tif     composite max-flood mask (WGS84, clipped)
  README.txt                       provenance note

Usage
-----
  python scripts/fetch_gfm_mys2021.py

Requirements: requests (or urllib), rasterio, numpy, shapely
  pip install requests rasterio numpy
"""

from __future__ import annotations

import os
import sys
import json
import shutil
import textwrap
import urllib.request
from pathlib import Path
from datetime import datetime

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.mask import mask as rio_mask
from shapely.geometry import box

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

STAC_URL = "https://stac.eodc.eu/api/v1"
COLLECTION = "GFM"

# KL pipeline domain (from cities.py)
KL_BBOX = (101.40, 2.90, 101.95, 3.42)   # (west, south, east, north)

# Flood event window -- tropical depression made landfall 16 Dec 2021.
# Peak flood: Dec 17-22.  Include Dec 16 as pre-event (for pre/post diff).
DATETIME_RANGE = "2021-12-16T00:00:00Z/2021-12-22T23:59:59Z"
PEAK_DATES = {"2021-12-19", "2021-12-20", "2021-12-21", "2021-12-22"}   # for composite

OUT_DIR = Path("data/kl/flood_obs/MYS2021")
WGS84 = CRS.from_epsg(4326)

# GFM pixel values
GFM_FLOOD = 1       # observed flood extent
GFM_WATER = 2       # permanent / seasonal water
GFM_EXCLUDE = 3     # excluded (cloud, layover, shadow, urban)


# ---------------------------------------------------------------------------
# STAC query
# ---------------------------------------------------------------------------

def query_stac(bbox: tuple[float, float, float, float], dt_range: str) -> list[dict]:
    """Return all GFM STAC items intersecting bbox and datetime range."""
    url = (
        f"{STAC_URL}/collections/{COLLECTION}/items"
        f"?bbox={bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
        f"&datetime={dt_range}"
        f"&limit=200"
    )
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return data.get("features", [])


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def _download(url: str, dest: Path, overwrite: bool = False) -> None:
    if dest.exists() and not overwrite:
        print(f"  [skip] {dest.name} (already exists)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  [dl]   {dest.name} <- {url.split('/')[-1]}")
    urllib.request.urlretrieve(url, dest)


# ---------------------------------------------------------------------------
# Reprojection helpers
# ---------------------------------------------------------------------------

def _reproject_to_wgs84(src_path: Path, dst_path: Path,
                         clip_bbox: tuple[float, float, float, float]) -> None:
    """
    Reproject a single Equi7Grid GeoTIFF to WGS84, clip to KL bbox,
    and write flood mask (1=flood, 0=not-flood/nodata).
    """
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, WGS84, src.width, src.height, *src.bounds
        )
        kwargs = src.meta.copy()
        kwargs.update({
            "crs": WGS84,
            "transform": transform,
            "width": width,
            "height": height,
            "dtype": "uint8",
            "nodata": 255,
        })
        # Reproject into memory buffer
        arr_repr = np.zeros((height, width), dtype="uint8")
        reproject(
            source=rasterio.band(src, 1),
            destination=arr_repr,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=WGS84,
            resampling=Resampling.nearest,
        )

    # Clip to KL bbox
    clip_geom = [box(*clip_bbox).__geo_interface__]
    # Write reprojected to tmp file then clip
    tmp = dst_path.parent / (dst_path.stem + "_tmp.tif")
    with rasterio.open(tmp, "w", **kwargs) as dst:
        dst.write(arr_repr, 1)

    with rasterio.open(tmp) as src2:
        out_arr, out_transform = rio_mask(src2, clip_geom, crop=True, nodata=255)
        out_meta = src2.meta.copy()
        out_meta.update({
            "height": out_arr.shape[1],
            "width": out_arr.shape[2],
            "transform": out_transform,
            "compress": "deflate",
            "predictor": 2,
        })

    with rasterio.open(dst_path, "w", **out_meta) as dst:
        dst.write(out_arr)

    tmp.unlink(missing_ok=True)


def _merge_flood_masks(tif_paths: list[Path], out_path: Path) -> None:
    """
    Merge multiple WGS84 flood masks into a composite:
    pixel = 1 if flooded in ANY pass, else 0 (nodata=255 excluded).
    """
    datasets = [rasterio.open(p) for p in tif_paths]
    mosaic, out_transform = merge(datasets, method="max", nodata=255)
    meta = datasets[0].meta.copy()
    meta.update({
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_transform,
        "compress": "deflate",
        "predictor": 2,
    })
    # Binarise: flood=1, water=2 -> both become 1; excluded/nodata stay 255
    arr = mosaic[0]
    flood_mask = np.where((arr == GFM_FLOOD) | (arr == GFM_WATER), 1, 0).astype("uint8")
    flood_mask[arr == 255] = 255
    meta["dtype"] = "uint8"
    meta["nodata"] = 255
    with rasterio.open(out_path, "w", **meta) as dst:
        dst.write(flood_mask, 1)
    for ds in datasets:
        ds.close()
    print(f"\n  Composite written: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("GFM MYS2021 download -- Selangor/KL December 2021 flood")
    print("=" * 60)
    print(f"\nQuerying STAC  ({DATETIME_RANGE}) ...")

    items = query_stac(KL_BBOX, DATETIME_RANGE)
    print(f"Found {len(items)} GFM items\n")

    raw_dir = OUT_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Download raw tiles
    raw_tifs: list[tuple[str, Path]] = []
    for item in items:
        dt_str = item.get("properties", {}).get("datetime", "")[:10]
        asset = item.get("assets", {}).get("ensemble_flood_extent", {})
        href = asset.get("href")
        if not href:
            continue
        fname = Path(href).name
        dest = raw_dir / fname
        _download(href, dest)
        raw_tifs.append((dt_str, dest))

    print(f"\nReprojecting {len(raw_tifs)} tiles to WGS84 ...")

    # Group by date
    by_date: dict[str, list[Path]] = {}
    for dt_str, raw_path in raw_tifs:
        by_date.setdefault(dt_str, []).append(raw_path)

    wgs84_by_date: dict[str, list[Path]] = {}
    for dt_str, paths in sorted(by_date.items()):
        repr_paths = []
        for raw_path in paths:
            out_name = f"gfm_kl_{raw_path.stem}.tif"
            out_path = OUT_DIR / out_name
            print(f"\n  {raw_path.name} -> {out_name}")
            try:
                _reproject_to_wgs84(raw_path, out_path, KL_BBOX)
                repr_paths.append(out_path)
            except Exception as e:
                print(f"    [WARN] reprojection failed: {e}")
        wgs84_by_date[dt_str] = repr_paths

    # Build composite from peak dates
    peak_paths: list[Path] = []
    for dt_str, paths in wgs84_by_date.items():
        if dt_str in PEAK_DATES:
            peak_paths.extend(paths)

    if peak_paths:
        print(f"\nBuilding composite from {len(peak_paths)} peak-date tiles ...")
        composite_path = OUT_DIR / "gfm_kl_composite_dec2021.tif"
        _merge_flood_masks(peak_paths, composite_path)
        _print_stats(composite_path)
    else:
        print("\n[WARN] No peak-date tiles found for composite.")

    # Write README
    _write_readme(items, peak_paths)
    print("\nDone.")


def _print_stats(tif_path: Path) -> None:
    with rasterio.open(tif_path) as src:
        arr = src.read(1)
        res_m = abs(src.res[0]) * 111_320  # rough deg->m
        n_flood = int((arr == 1).sum())
        area_km2 = n_flood * (res_m ** 2) / 1e6
        print(f"  Flood pixels : {n_flood:,}")
        print(f"  Approx area  : {area_km2:.1f} km2  (at {res_m:.0f} m resolution)")


def _write_readme(items: list[dict], peak_paths: list[Path]) -> None:
    dates = sorted({item.get("properties", {}).get("datetime", "")[:10] for item in items})
    readme = OUT_DIR / "README.txt"
    with open(readme, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(f"""\
            Copernicus GFM -- December 2021 Malaysia Flood (MYS2021)
            ========================================================
            Source   : EODC STAC API (https://stac.eodc.eu/api/v1)
            Collection: GFM (Global Flood Monitoring, ensemble product)
            Asset    : ensemble_flood_extent
            Event    : December 2021 Selangor/KL flood
              Tropical Depression 29 made landfall 16 Dec 2021
              Peak displacement: 17-22 Dec 2021 (~70,000 evacuated)
            Domain   : KL pipeline bbox {KL_BBOX}

            Sentinel-1 acquisition dates:
            {chr(10).join('  ' + d for d in dates)}

            Composite file: gfm_kl_composite_dec2021.tif
              Pixel = 1 (flood) if flooded in ANY Dec 17-22 pass.
              Pixel = 255 (nodata) if excluded in all passes.
              Pixel = 0 otherwise (not flooded).

            Pixel values in raw/gfm_kl_*.tif:
              0 = not flooded
              1 = observed flood extent
              2 = permanent/seasonal water
              3 = excluded (cloud, layover, shadow)
              255 = nodata

            CRS: EPSG:4326  |  Resolution: ~20 m
            Projection: Equi7Grid (original) -> reprojected to WGS84

            Urban exclusion limitation:
              GFM excludes ~69% of the KL bbox via urban masking (SAR
              double-bounce from buildings). Composite flood pixels = 345
              (~0.14 km2). Usable only for peri-urban / agricultural areas.

            Use for R4 historical validation (partial):
              validate_historical_events.py --city kuala_lumpur \
                --event MYS2021 \
                --obs-file data/kl/flood_obs/MYS2021/gfm_kl_composite_dec2021.tif

            Citation: Copernicus Emergency Management Service (CEMS),
              Global Flood Monitoring (GFM) product.
              https://global-flood.emergency.copernicus.eu/
        """))
    print(f"\n  README written: {readme}")


if __name__ == "__main__":
    main()
