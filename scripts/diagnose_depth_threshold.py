"""Sensitivity of Singapore pluvial fill-spill to MIN_DEPRESSION_DEPTH_M.

For each candidate depth threshold (with the 9-cell area filter held fixed),
report:
  - number of depressions
  - total depression footprint (km2)
  - fraction of RP100 runoff that is RECAPTURED into depressions
    (vs lost to sea/river via D8)
  - depth distribution of the kept depressions

This isolates whether the sparse Singapore result is caused by the 0.5 m
depth filter discarding the shallow broad concavities where flash-flood
ponding actually occurs.
"""
import sys
from pathlib import Path

import numpy as np
import rasterio

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from model.flood_depth_model import load_dem
from model.hand_model import fill_depressions
from model.pluvial_model import (build_depression_inventory, compute_catchment_supply,
                                  d8_flow_direction)

DEM_PATH = PROJECT_ROOT / "data/singapore/copernicus_dem_utm48n.tif"
SEA_PATH = PROJECT_ROOT / "data/singapore/sea_mask_utm48n.tif"
RC_PATH  = PROJECT_ROOT / "data/singapore/runoff_coeff_utm48n.tif"

EXCESS_RP100_M = 0.063491   # current 50mm-drain RP100 excess after CC (m)
THRESHOLDS = [0.05, 0.10, 0.15, 0.20, 0.30, 0.50]
AREA_CELLS = 9
MAX_DEPTH = 3.0


def main() -> None:
    dem, profile = load_dem(str(DEM_PATH))
    with rasterio.open(SEA_PATH) as src:
        sm = src.read(1)
    dem_land = np.where(sm == 1, dem, np.nan).astype(np.float64)

    with rasterio.open(RC_PATH) as src:
        rc = src.read(1).astype(float)
        rc[rc == src.nodata] = np.nan
    rc = np.where(np.isfinite(dem_land) & np.isfinite(rc), rc, 0.0)

    tr = profile["transform"]
    cell_area_m2 = abs(tr.a * tr.e)
    land_km2 = np.isfinite(dem_land).sum() * cell_area_m2 / 1e6

    print(f"Singapore land area: {land_km2:.0f} km2")
    print("Filling depressions once (threshold-independent)...", flush=True)
    filled = fill_depressions(dem_land, profile).astype(np.float64)
    fdir = d8_flow_direction(dem_land)

    runoff_volume = EXCESS_RP100_M * rc * cell_area_m2
    total_runoff = float(np.nansum(runoff_volume))

    print(f"\nRP100 total land runoff: {total_runoff/1e6:.2f} Mm3")
    print(f"(area filter held at >={AREA_CELLS} cells; max depth {MAX_DEPTH} m)\n")
    print(f"{'depth_min':>9}  {'n_depr':>7}  {'footprint_km2':>13}  "
          f"{'recaptured':>11}  {'to_sea':>8}  {'median_depth_m':>14}")
    print("-" * 80)

    for thr in THRESHOLDS:
        inv = build_depression_inventory(
            dem_land, filled, cell_area_m2,
            min_depression_depth_m=thr,
            max_depression_depth_m=MAX_DEPTH,
            min_depression_area_cells=AREA_CELLS,
        )
        footprint = int((inv.labels > 0).sum()) * cell_area_m2 / 1e6
        supply = compute_catchment_supply(dem_land, fdir, inv, runoff_volume)
        recaptured = float(supply.sum())
        frac_rec = 100 * recaptured / total_runoff if total_runoff else 0
        # depth distribution
        depth = filled - dem_land
        med_depth = np.nan
        if inv.n > 0:
            maxd = []
            for d in range(inv.n):
                cells = inv.labels == (d + 1)
                if cells.any():
                    maxd.append(float(depth[cells].max()))
            med_depth = float(np.median(maxd)) if maxd else np.nan
        print(f"{thr:>9.2f}  {inv.n:>7,}  {footprint:>13.1f}  "
              f"{frac_rec:>10.1f}%  {100-frac_rec:>7.1f}%  {med_depth:>14.2f}")

    print("\nInterpretation: 'recaptured' is the fraction of excess rainfall that")
    print("ponds in a depression rather than draining to sea. Higher = more")
    print("flash-flood ponding captured. The 0.50 m row is the current model.")


if __name__ == "__main__":
    main()
