"""
Sentinel-1 SAR change-detection flood map for December 2021 KL / Selangor
using the Google Earth Engine Python API.

Bypasses GFM's urban exclusion mask by doing raw backscatter comparison
between a pre-flood baseline and the peak flood window.

Algorithm
---------
1. Load S-1 GRD IW VV images for the KL bbox.
2. Split into:
     - baseline : Oct 15 - Dec 15 2021  (pre-flood; avoids early Dec rain)
     - flood    : Dec 17 - Dec 22 2021  (peak event)
   Process ASCENDING and DESCENDING orbits separately (different incidence
   angles give different absolute backscatter levels; always diff within
   same pass direction).
3. Per pass direction: compute median baseline, median flood composite.
4. Difference = flood_dB - baseline_dB.  Flooded pixels show a DECREASE
   in backscatter (open water = specular reflector, low sigma0).
5. Apply Otsu threshold on the negative-difference image to binarise.
   Fixed fallback: -3 dB (robust across urban/rural mix, per lit. review).
6. Merge ASC + DESC flood masks (union: flood if either pass detects it).
7. Download as GeoTIFF to:
     data/kl/flood_obs/MYS2021/s1_kl_flood_dec2021.tif

Setup (one-time)
----------------
    pip install earthengine-api
    earthengine authenticate          # opens browser, copies token
    # OR for service-account auth: set GOOGLE_APPLICATION_CREDENTIALS

Usage
-----
    python scripts/gee_s1_flood_mys2021.py

    # Export to Google Drive instead of direct download (for large areas):
    python scripts/gee_s1_flood_mys2021.py --drive

    # Adjust dB threshold (default -3.0):
    python scripts/gee_s1_flood_mys2021.py --threshold -4.0

Notes
-----
- Sentinel-1B went offline 2021-12-23; all Dec 17-22 data is Sentinel-1A.
- Urban areas will still have noise (double-bounce from buildings does not
  always go down when flooded), but we get detections in suburban/peri-urban
  areas that GFM excludes.
- Output pixel value: 1 = flood detected, 0 = not flooded, 255 = nodata.
- CRS: EPSG:4326 at ~20 m (0.00018 deg) native GEE export resolution.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import zipfile
from pathlib import Path

import numpy as np

try:
    import ee
except ImportError:
    print("ERROR: earthengine-api not installed.  Run: pip install earthengine-api")
    sys.exit(1)

try:
    import requests
except ImportError:
    import urllib.request as _urllib
    requests = None

try:
    import rasterio
    from rasterio.transform import from_bounds
except ImportError:
    print("ERROR: rasterio not installed.  Run: pip install rasterio")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KL_BBOX = (101.40, 2.90, 101.95, 3.42)          # west, south, east, north
BASELINE_START = "2021-10-15"
BASELINE_END   = "2021-12-15"
FLOOD_START    = "2021-12-17"
FLOOD_END      = "2021-12-23"

EXPORT_SCALE   = 20        # metres -- matches GFM resolution
DEFAULT_THRESH = -3.0      # dB; negative = backscatter decrease = flood

OUT_DIR  = Path("data/kl/flood_obs/MYS2021")
OUT_FILE = OUT_DIR / "s1_kl_flood_dec2021.tif"

DRIVE_FOLDER = "GEE_exports"
DRIVE_FNAME  = "s1_kl_flood_dec2021"


# ---------------------------------------------------------------------------
# GEE helpers
# ---------------------------------------------------------------------------

def init_ee() -> None:
    """Initialise Earth Engine (uses cached credentials from `earthengine authenticate`)."""
    try:
        ee.Initialize()
        print("[ee] Initialised (project/default credentials)")
    except Exception:
        try:
            ee.Authenticate()
            ee.Initialize()
            print("[ee] Authenticated + initialised")
        except Exception as exc:
            print(f"ERROR: Cannot initialise Earth Engine: {exc}")
            print("  Run: earthengine authenticate")
            sys.exit(1)


def _s1_collection(aoi: ee.Geometry, start: str, end: str,
                   pass_dir: str) -> ee.ImageCollection:
    return (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.eq("orbitProperties_pass", pass_dir))
        .select("VV")
    )


def _otsu_threshold(image: ee.Image, aoi: ee.Geometry, scale: int = 200) -> float:
    """
    Compute Otsu threshold client-side: pull histogram via getInfo(), then
    run standard Otsu in numpy.  Falls back to DEFAULT_THRESH on any failure.
    """
    try:
        band = image.bandNames().getInfo()[0]
        hist_dict = image.reduceRegion(
            reducer=ee.Reducer.histogram(maxBuckets=200),
            geometry=aoi,
            scale=scale,
            maxPixels=1e8,
            bestEffort=True,
        ).getInfo()
        h = hist_dict.get(band)
        if h is None or not h.get("histogram"):
            return DEFAULT_THRESH
        counts = np.array(h["histogram"], dtype=float)
        edges  = np.array(h["bucketMeans"], dtype=float)
        if counts.sum() == 0:
            return DEFAULT_THRESH
        # Standard Otsu between-class variance
        total    = counts.sum()
        w_b      = np.cumsum(counts) / total          # weight background
        w_f      = 1.0 - w_b                          # weight foreground
        mu_b     = np.cumsum(counts * edges) / (np.cumsum(counts) + 1e-12)
        mu_total = (counts * edges).sum() / total
        mu_f     = np.where(w_f > 1e-12,
                            (mu_total - w_b * mu_b) / (w_f + 1e-12), 0.0)
        sigma2   = w_b * w_f * (mu_b - mu_f) ** 2
        idx      = int(np.argmax(sigma2))
        thresh   = float(edges[idx])
        print(f"  [Otsu] threshold = {thresh:.2f} dB")
        return thresh
    except Exception as exc:
        print(f"  [Otsu] failed ({exc}); using fixed {DEFAULT_THRESH} dB")
        return DEFAULT_THRESH


def build_flood_mask(aoi: ee.Geometry, threshold_db: float | None) -> ee.Image:
    """
    Build a binary flood mask (1=flood, 0=dry) for the KL bbox.

    Processes ASCENDING and DESCENDING orbits separately (different
    incidence angles -> different absolute dB levels; always diff within
    same pass direction), then takes their union.

    If a collection has no images, its median() is all-masked; after
    .unmask(0) those pixels become 0 (not flooded) -- no explicit null
    check needed.
    """
    flood_images = []

    for pass_dir in ("ASCENDING", "DESCENDING"):
        base_col  = _s1_collection(aoi, BASELINE_START, BASELINE_END, pass_dir)
        flood_col = _s1_collection(aoi, FLOOD_START, FLOOD_END, pass_dir)

        # Client-side size check -- getInfo() is cheap (single number)
        n_base  = base_col.size().getInfo()
        n_flood = flood_col.size().getInfo()
        print(f"  {pass_dir}: baseline={n_base} imgs, flood={n_flood} imgs")

        if n_base == 0 or n_flood == 0:
            print(f"  {pass_dir}: skipped (no images)")
            continue

        baseline_img = base_col.median()
        flood_img    = flood_col.median()
        diff_img     = flood_img.subtract(baseline_img).rename("VV")

        # Determine threshold: Otsu (client-side numpy) or fixed
        thresh = threshold_db if threshold_db is not None \
                 else _otsu_threshold(diff_img, aoi)

        # lt(thresh): 1 where diff < thresh (backscatter dropped = flood)
        flood_mask = diff_img.lt(thresh).unmask(0).rename("flood")
        flood_images.append(flood_mask)

    if not flood_images:
        raise RuntimeError(
            "No Sentinel-1 images found for either orbit direction. "
            "Check KL_BBOX and date range."
        )

    if len(flood_images) == 1:
        combined = flood_images[0]
    else:
        # Union: flooded if either pass detects it
        combined = flood_images[0].Or(flood_images[1]).rename("flood")

    return combined.uint8().clip(aoi)


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def download_image(image: ee.Image, aoi: ee.Geometry, out_path: Path) -> None:
    """Download via getDownloadURL (direct, no Drive needed for <~50 MB)."""
    print("\nRequesting download URL from GEE ...")
    url = image.getDownloadURL({
        "name": "s1_flood",
        "bands": ["flood"],
        "region": aoi,
        "scale": EXPORT_SCALE,
        "crs": "EPSG:4326",
        "format": "GEO_TIFF",
        "filePerBand": False,
    })
    print(f"  URL obtained, downloading ...")

    if requests:
        resp = requests.get(url, stream=True)
        resp.raise_for_status()
        raw = resp.content
    else:
        import urllib.request
        with urllib.request.urlopen(url) as r:
            raw = r.read()

    # GEE returns either a raw GeoTIFF or a zip containing one
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if raw[:2] == b"PK":   # ZIP magic bytes
        zf = zipfile.ZipFile(io.BytesIO(raw))
        tif_names = [n for n in zf.namelist() if n.endswith(".tif")]
        if not tif_names:
            raise RuntimeError("ZIP from GEE contains no .tif files")
        out_path.write_bytes(zf.read(tif_names[0]))
    else:
        out_path.write_bytes(raw)

    print(f"  Written: {out_path}")


def export_to_drive(image: ee.Image, aoi: ee.Geometry) -> None:
    """Export to Google Drive (for large areas or if direct download fails)."""
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=DRIVE_FNAME,
        folder=DRIVE_FOLDER,
        fileNamePrefix=DRIVE_FNAME,
        region=aoi,
        scale=EXPORT_SCALE,
        crs="EPSG:4326",
        maxPixels=1e9,
        fileFormat="GeoTIFF",
    )
    task.start()
    print(f"\nExport task submitted to Google Drive folder '{DRIVE_FOLDER}'.")
    print(f"  File: {DRIVE_FNAME}.tif")
    print("  Check progress: https://code.earthengine.google.com/tasks")
    print("  Download from Google Drive when complete.")


def print_stats(tif_path: Path) -> None:
    with rasterio.open(tif_path) as src:
        arr = src.read(1)
        n_flood   = int((arr == 1).sum())
        n_dry     = int((arr == 0).sum())
        n_nodata  = int((arr == 255).sum())
        res_deg   = abs(src.res[0])
        res_m     = res_deg * 111_320
        area_km2  = n_flood * (res_m ** 2) / 1e6
        print(f"\n  Flood pixels : {n_flood:,}")
        print(f"  Dry pixels   : {n_dry:,}")
        print(f"  Nodata       : {n_nodata:,}")
        print(f"  Approx flood area: {area_km2:.1f} km2  (at {res_m:.0f} m/px)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--drive", action="store_true",
                        help="Export to Google Drive instead of direct download")
    parser.add_argument("--threshold", type=float, default=None,
                        help=f"Fixed dB threshold (default: Otsu; fallback {DEFAULT_THRESH} dB)")
    args = parser.parse_args()

    print("=" * 60)
    print("Sentinel-1 SAR flood mapping -- KL Dec 2021")
    print("=" * 60)

    init_ee()

    aoi = ee.Geometry.Rectangle(list(KL_BBOX))   # [west, south, east, north]

    print(f"\nBaseline : {BASELINE_START} -> {BASELINE_END}")
    print(f"Flood    : {FLOOD_START} -> {FLOOD_END}")
    print(f"BBox     : {KL_BBOX}")
    print(f"Threshold: {'Otsu' if args.threshold is None else f'{args.threshold} dB'}")
    print("\nBuilding flood mask ...")

    flood_img = build_flood_mask(aoi, args.threshold)

    if args.drive:
        export_to_drive(flood_img, aoi)
    else:
        try:
            download_image(flood_img, aoi, OUT_FILE)
            print_stats(OUT_FILE)
        except Exception as exc:
            print(f"\n  Direct download failed: {exc}")
            print("  Falling back to Drive export ...")
            export_to_drive(flood_img, aoi)

    print("\nDone.")


if __name__ == "__main__":
    main()
