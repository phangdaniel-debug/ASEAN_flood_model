"""Diagnose DSM artefact depressions across cities.

For each city, loads the primary DEM + sea mask, runs fill_depressions, and
builds a depression inventory WITHOUT the new area filter.  Reports count and
area by size bucket so we can see how many artefact pits exist per city.

Usage:
    python scripts/diagnose_depression_artefacts.py
"""
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from model.hand_model import fill_depressions
from model.pluvial_model import MIN_DEPRESSION_DEPTH_M, MAX_DEPRESSION_DEPTH_M

# (city_name, dem_path, sea_mask_path)
CITIES = [
    ("Singapore",  "data/singapore/copernicus_dem_utm48n.tif",
                   "data/singapore/sea_mask_utm48n.tif"),
    ("Jakarta",    "data/jakarta/copernicus_dem_utm48s_subsidence_corrected.tif",
                   "data/jakarta/sea_mask_utm48s.tif"),
    ("Bangkok",    "data/bangkok/copernicus_dem_utm47n_subsidence_corrected.tif",
                   "data/bangkok/sea_mask_utm47n.tif"),
    ("HCMC",       "data/hcmc/copernicus_dem_utm48n_subsidence_corrected.tif",
                   "data/hcmc/sea_mask_utm48n.tif"),
    ("Manila",     "data/manila/copernicus_dem_utm51n_subsidence_corrected.tif",
                   "data/manila/sea_mask_utm51n.tif"),
]

MIN_AREA = 9  # cells — the new filter threshold

SIZE_BUCKETS = [
    (1,  1,  "1 cell  (single pixel)"),
    (2,  4,  "2–4 cells"),
    (5,  8,  "5–8 cells"),
    (9,  24, "9–24 cells"),
    (25, 99, "25–99 cells"),
    (100, 10_000_000, "100+ cells"),
]


def analyse_city(name: str, dem_path: Path, sea_mask_path: Path) -> None:
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    if not dem_path.exists():
        print(f"  [skip] DEM not found: {dem_path}")
        return
    if not sea_mask_path.exists():
        print(f"  [skip] Sea mask not found: {sea_mask_path}")
        return

    # Load DEM
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float64)
        profile = src.profile
        nodata = src.nodata

    if nodata is not None:
        dem[dem == nodata] = np.nan

    # Load sea mask and null-out sea/ocean pixels
    with rasterio.open(sea_mask_path) as src:
        sm = src.read(1)

    land_pixels = (sm == 1)
    dem_land = np.where(land_pixels, dem, np.nan)

    tr = profile["transform"]
    cell_area_m2 = abs(tr.a * tr.e)
    cell_side_m  = abs(tr.a)

    print(f"  DEM shape  : {dem_land.shape}  ({cell_side_m:.0f} m pixels)")
    print(f"  Land cells : {int(np.count_nonzero(land_pixels)):,}")
    print(f"  Cell area  : {cell_area_m2:,.0f} m²")

    # Fill depressions
    print("  Filling depressions...", end=" ", flush=True)
    filled = fill_depressions(dem_land, profile).astype(np.float64)
    print("done")

    # Build raw connected components of depth > 0
    depth = filled - dem_land
    raw_labels, n_raw = ndimage.label(depth > 0.0,
                                      structure=np.ones((3, 3), dtype=int))
    print(f"  Raw connected depth>0 components : {n_raw:,}")

    # Classify each component
    n_depth_fail = 0
    n_depth_pass = 0
    buckets_all  = {lo: 0 for lo, _, _ in SIZE_BUCKETS}
    buckets_pass = {lo: 0 for lo, _, _ in SIZE_BUCKETS}  # pass depth filter

    for raw in range(1, n_raw + 1):
        mask  = raw_labels == raw
        n_cells = int(mask.sum())
        d_max = float(depth[mask].max())

        for lo, hi, _ in SIZE_BUCKETS:
            if lo <= n_cells <= hi:
                buckets_all[lo] += 1
                break

        if d_max < MIN_DEPRESSION_DEPTH_M or d_max > MAX_DEPRESSION_DEPTH_M:
            n_depth_fail += 1
        else:
            n_depth_pass += 1
            for lo, hi, _ in SIZE_BUCKETS:
                if lo <= n_cells <= hi:
                    buckets_pass[lo] += 1
                    break

    print(f"\n  After DEPTH filter ({MIN_DEPRESSION_DEPTH_M}–{MAX_DEPRESSION_DEPTH_M} m): "
          f"{n_depth_pass:,} depressions remain  "
          f"({n_depth_fail:,} dropped by depth)")

    print(f"\n  Size distribution of DEPTH-FILTERED depressions:")
    print(f"  {'Size bucket':<22} {'Count':>8}  {'% of total':>10}  {'Flag'}")
    print(f"  {'-'*22} {'-'*8}  {'-'*10}  {'-'*10}")
    artefact_count = 0
    kept_count = 0
    for lo, hi, label in SIZE_BUCKETS:
        cnt = buckets_pass[lo]
        pct = 100 * cnt / n_depth_pass if n_depth_pass else 0
        flag = "<-- ARTEFACT (removed by new filter)" if lo < MIN_AREA else ""
        if lo < MIN_AREA:
            artefact_count += cnt
        else:
            kept_count += cnt
        print(f"  {label:<22} {cnt:>8,}  {pct:>9.1f}%  {flag}")

    pct_artefact = 100 * artefact_count / n_depth_pass if n_depth_pass else 0
    print(f"\n  => Artefact pits removed by MIN_AREA={MIN_AREA}: "
          f"{artefact_count:,} / {n_depth_pass:,} ({pct_artefact:.1f}%)")
    print(f"  => Real depressions kept              : "
          f"{kept_count:,} / {n_depth_pass:,} ({100-pct_artefact:.1f}%)")


def main() -> None:
    print("Depression artefact diagnostic — GLO-30 DSM cities")
    print(f"Depth filter: {MIN_DEPRESSION_DEPTH_M}–{MAX_DEPRESSION_DEPTH_M} m")
    print(f"New area filter threshold: {MIN_AREA} cells = "
          f"{MIN_AREA * 900:,} m² (~{int(MIN_AREA**0.5 * 30)}m × {int(MIN_AREA**0.5 * 30)}m)")

    for name, dem_rel, sm_rel in CITIES:
        dem_path = PROJECT_ROOT / dem_rel
        sm_path  = PROJECT_ROOT / sm_rel
        analyse_city(name, dem_path, sm_path)

    print("\n\nDone.")


if __name__ == "__main__":
    main()
