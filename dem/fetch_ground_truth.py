"""
Phase 1 ground-truth fetch: ICESat-2 ATL08 + GEDI L2A over a city domain.

Heights are WGS84-ellipsoidal; reconcile to EGM2008 (dem/datum_reconcile.py)
before any differencing against GLO-30.

Modes:
  --count            search only; report granule counts + total size (no download)
  --download         download granules into <outdir>/<product>/
  --product atl08|gedi|both

Bbox is derived from the reference DEM (reprojected to lon/lat) + a small buffer.
"""
from __future__ import annotations
import argparse
from pathlib import Path

import rasterio
from rasterio.warp import transform_bounds
import earthaccess

ATL08 = "ATL08"        # NSIDC; land/veg along-track terrain height (h_te_best_fit)
GEDI = "GEDI02_A"      # ORNL; footprint ground elevation (elev_lowestmode)


def dem_bbox_lonlat(dem_path: Path, buffer_deg: float = 0.02):
    with rasterio.open(dem_path) as src:
        b = src.bounds
        lon_min, lat_min, lon_max, lat_max = transform_bounds(
            src.crs, "EPSG:4326", b.left, b.bottom, b.right, b.top
        )
    return (round(lon_min - buffer_deg, 5), round(lat_min - buffer_deg, 5),
            round(lon_max + buffer_deg, 5), round(lat_max + buffer_deg, 5))


def search(short_name, bbox, temporal):
    return earthaccess.search_data(
        short_name=short_name, bounding_box=bbox, temporal=temporal
    )


def total_size_mb(results):
    tot = 0.0
    for r in results:
        try:
            tot += float(r.size())  # MB (earthaccess reports MB)
        except Exception:
            pass
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default=r"D:\GPTs\Projects\flood-v3.0\dem\bangkok\glo30_dsm_utm47n.tif")
    ap.add_argument("--outdir", default=r"D:\GPTs\Projects\flood-v3.0\dem\bangkok\ground_truth")
    ap.add_argument("--product", choices=["atl08", "gedi", "both"], default="both")
    ap.add_argument("--start", default="2019-01-01")
    ap.add_argument("--end", default="2023-12-31")
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--max-granules", type=int, default=0, help="0 = no cap")
    args = ap.parse_args()

    earthaccess.login(strategy="netrc")
    bbox = dem_bbox_lonlat(Path(args.dem))
    temporal = (args.start, args.end)
    print(f"DEM bbox (lon/lat): {bbox}")
    print(f"temporal: {temporal}")

    products = []
    if args.product in ("atl08", "both"):
        products.append((ATL08, "atl08"))
    if args.product in ("gedi", "both"):
        products.append((GEDI, "gedi"))

    for short_name, tag in products:
        res = search(short_name, bbox, temporal)
        mb = total_size_mb(res)
        print(f"\n{short_name:10s}: {len(res)} granules, ~{mb:,.0f} MB total "
              f"(~{mb/1024:,.1f} GB)")
        if args.download and res:
            sub = res[: args.max_granules] if args.max_granules else res
            outdir = Path(args.outdir) / tag
            outdir.mkdir(parents=True, exist_ok=True)
            print(f"  downloading {len(sub)} granules -> {outdir}")
            earthaccess.download(sub, str(outdir))


if __name__ == "__main__":
    main()
