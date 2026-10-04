"""Jakarta main-stem HAND: rebuild HAND against a main-stem drainage network
(flow-accumulation threshold) instead of the dense v3 network (21.7% of land is
channel -> fluvial floods 349 km2 deep). Keeps the real rivers (Ciliwung + 12
others) but drops the minor drains, so the deep GloFAS stage stays on the river
corridors; the broad near-minor-drainage monsoon flooding moves to handfill pluvial.

Out: dem/_hand/jakarta_hand_v3_mainstem.tif
"""
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.flood_depth_model import load_dem  # noqa: E402
from model.hand_model import compute_hand, derive_drainage_mask_from_accumulation  # noqa: E402

DEM = ROOT / "dem/jakarta/dem_bareearth_jakarta_present_conditioned.tif"
SEAMASK = ROOT / "data/jakarta/sea_mask_utm48s.tif"
OUT = ROOT / "dem/_hand/jakarta_hand_v3_mainstem.tif"
PX_KM2 = 0.0009
CANDIDATES_KM2 = [50, 100]
CHOSEN_KM2 = 50  # keep Ciliwung + major rivers


def main():
    dem, profile = load_dem(str(DEM))
    dem = np.asarray(dem, dtype="float64")
    with rasterio.open(SEAMASK) as r:
        sm = r.read(1)
    land = (sm == 1) & np.isfinite(dem)
    print("threshold sweep (channel density; lower km2 = denser):")
    chosen = None
    for km2 in CANDIDATES_KM2:
        thr = int(round(km2 / PX_KM2))
        drainage = derive_drainage_mask_from_accumulation(dem, profile, acc_threshold=thr)
        chan_km2 = float((drainage & land).sum()) * PX_KM2
        hand = compute_hand(dem, drainage, profile)
        print(f"  >= {km2:3d} km2: channel={chan_km2:5.1f} km2 "
              f"({100*float((drainage&land).sum())/max(1,land.sum()):.1f}% of land)")
        if km2 == CHOSEN_KM2:
            chosen = hand
    print("  (dense v3 network: channel 174 km2 = 21.7% of land)")
    hprof = profile.copy()
    hprof.update(dtype="float32", nodata=float("nan"), compress="deflate", predictor=2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(OUT, "w", **hprof) as dst:
        dst.write(chosen.astype("float32"), 1)
    print(f"\nwrote {OUT} (main-stem >= {CHOSEN_KM2} km2)")


if __name__ == "__main__":
    main()
