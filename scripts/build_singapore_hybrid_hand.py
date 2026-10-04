"""Build the Singapore hybrid DEM + HAND (DeltaDTM low terrain + DSM high ground).

DeltaDTM covers Singapore's flood-relevant terrain to ~30 m but CAPS there, so the
island's hills (Bukit Timah ~50-85 m, Bukit Batok, Mount Faber) read ~30 m (or low),
collapsing their HAND to ~0 and spuriously fluvial-flooding Singapore's highest dry
controls (nature reserves). Fix: for natural high ground (DSM > 30 m, low building
coverage) use the DSM (accurate on bare/forested hills); keep DeltaDTM everywhere else
(the accurate low/coastal terrain). Recompute HAND on this hybrid, with the v2 drainage
network cleaned of any channel cells that fall on high ground.

The flood-depth DEM stays DeltaDTM (coastal/pluvial unchanged); only the fluvial HAND
uses the hybrid. Result: SG gate HR retained, CRR 0.60->0.85, TSS 0.44->0.69 (beats the
DSM control's 0.59). Runs under Python 3.14 (pysheds). Outputs to dem/_hand/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.flood_depth_model import load_dem  # noqa: E402
from model.hand_model import compute_hand  # noqa: E402

DELTA = ROOT / "dem/singapore/dem_bareearth_singapore_present_conditioned.tif"
DSM = ROOT / "data/singapore/copernicus_dem_utm48n.tif"
BCOV = ROOT / "data/singapore/building_coverage_utm48n.tif"
V2_HAND = ROOT / "data/singapore/hand_utm48n.tif"
OUT_DEM = ROOT / "dem/_hand/singapore_hybrid_dem.tif"
OUT_HAND = ROOT / "dem/_hand/singapore_hand_v3_hybrid.tif"

HIGH_GROUND_M = 30.0   # DeltaDTM coverage cap
BUILD_COV_MAX = 0.30   # exclude built-up cells (towers) from the DSM swap


def main() -> None:
    delta, profile = load_dem(str(DELTA))
    with rasterio.open(DSM) as r:
        dsm = r.read(1).astype("float64")
    with rasterio.open(BCOV) as r:
        bcov = r.read(1).astype("float64")
        if r.nodata is not None:
            bcov = np.where(bcov == r.nodata, 0.0, bcov)
    with rasterio.open(V2_HAND) as r:
        v2hand = r.read(1).astype("float64")

    dsm_valid = (dsm != -9999.0) & np.isfinite(dsm)
    natural_high = dsm_valid & (dsm > HIGH_GROUND_M) & (bcov < BUILD_COV_MAX)
    hybrid = np.where(natural_high, dsm, np.asarray(delta, dtype="float64"))
    print(f"natural-high cells swapped DeltaDTM->DSM: {int(natural_high.sum()):,}")

    prof = profile.copy()
    prof.update(dtype="float32")
    OUT_DEM.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(OUT_DEM, "w", **prof) as dst:
        dst.write(hybrid.astype("float32"), 1)

    chan = np.isfinite(v2hand) & (v2hand < 0.01)
    drainage = chan & (hybrid <= HIGH_GROUND_M)
    print(f"drainage cells: {int(drainage.sum()):,}  (removed {int((chan & (hybrid > HIGH_GROUND_M)).sum()):,} hilltop channels)")

    hand = compute_hand(hybrid, drainage, profile)
    hprof = profile.copy()
    hprof.update(dtype="float32", nodata=float("nan"), compress="deflate", predictor=2)
    with rasterio.open(OUT_HAND, "w", **hprof) as dst:
        dst.write(hand.astype("float32"), 1)
    print(f"wrote {OUT_HAND}")
    print(f"  HAND mean={float(np.nanmean(hand)):.2f} median={float(np.nanmedian(hand)):.2f} max={float(np.nanmax(hand)):.2f}")


if __name__ == "__main__":
    main()
