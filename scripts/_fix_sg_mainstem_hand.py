"""Fix SG fluvial over-prediction: rebuild the Singapore HAND against a
MAIN-STEM drainage network (flow-accumulation threshold) instead of the dense
v2 canal network. Sweeps thresholds, reports channel density + fluvial extent
at the RP10/RP100 stages, and writes the chosen HAND.

The hybrid DEM (DeltaDTM low + DSM hills) is reused so the high-ground HAND fix
is preserved; only the drainage reference changes (dense -> main-stem).

Out: dem/_hand/singapore_hand_v3_mainstem.tif
"""
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.flood_depth_model import load_dem  # noqa: E402
from model.hand_model import compute_hand, derive_drainage_mask_from_accumulation  # noqa: E402

HYBRID = ROOT / "dem/_hand/singapore_hybrid_dem.tif"
SEAMASK = ROOT / "data/singapore/sea_mask_utm48n.tif"
OUT = ROOT / "dem/_hand/singapore_hand_v3_mainstem.tif"
HIGH_GROUND_M = 30.0
PX_KM2 = 0.0009  # 30 m pixel
# candidate main-stem thresholds in km2 -> pixels
CANDIDATES_KM2 = [50]
CHOSEN_KM2 = 50  # main-stem for a small island: Kallang/Singapore R. trunks only


def fluvial_km2(hand, land, stage):
    return float(((hand < stage) & land).sum()) * PX_KM2


def main():
    hybrid, profile = load_dem(str(HYBRID))
    hybrid = np.asarray(hybrid, dtype="float64")
    with rasterio.open(SEAMASK) as r:
        sm = r.read(1)
    land = (sm == 1) & np.isfinite(hybrid)

    print("threshold sweep (fluvial extent at RP10 stage 1.67m / RP100 stage 2.15m):")
    chosen_hand = None
    for km2 in CANDIDATES_KM2:
        thr = int(round(km2 / PX_KM2))
        drainage = derive_drainage_mask_from_accumulation(hybrid, profile, acc_threshold=thr)
        drainage = drainage & (hybrid <= HIGH_GROUND_M)
        chan_km2 = float(drainage.sum()) * PX_KM2
        hand = compute_hand(hybrid, drainage, profile)
        f10 = fluvial_km2(hand, land, 1.67)
        f100 = fluvial_km2(hand, land, 2.15)
        print(f"  >= {km2:3d} km2 ({thr:,}px): channel={chan_km2:5.1f} km2  "
              f"fluvial RP10={f10:5.1f}  RP100={f100:5.1f} km2")
        if km2 == CHOSEN_KM2:
            chosen_hand = hand
    print("  (current dense network: channel 96.5 km2 -> fluvial RP100 ~180 km2)")

    hprof = profile.copy()
    hprof.update(dtype="float32", nodata=float("nan"), compress="deflate", predictor=2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(OUT, "w", **hprof) as dst:
        dst.write(chosen_hand.astype("float32"), 1)
    print(f"\nwrote {OUT} (main-stem >= {CHOSEN_KM2} km2)")


if __name__ == "__main__":
    main()
