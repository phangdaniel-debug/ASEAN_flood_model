"""Controlled A/B HAND for Jakarta v3: reuse the v2 drainage network (channel cells
from hand_utm48s.tif where HAND~=0), recompute HAND on the v3 bare-earth terrain.

This isolates the single variable under test (terrain), keeping the drainage-network
topology identical to v2 (the dense single-stage Ciliwung network).
"""
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.flood_depth_model import load_dem
from model.hand_model import compute_hand

V2_HAND = r"D:\GPTs\Projects\flood-v2.0\data\jakarta\hand_utm48s.tif"
V3_DEM = r"D:\GPTs\Projects\flood-v3.0\dem\jakarta\dem_bareearth_jakarta_present_conditioned.tif"
OUT = ROOT / "outputs_v3dem" / "_dem" / "jakarta_hand_v3.tif"

with rasterio.open(V2_HAND) as r:
    h2 = r.read(1).astype("float64")
drainage_mask = np.isfinite(h2) & (h2 < 0.01)
print(f"v2 drainage network: {int(drainage_mask.sum()):,} channel cells")

dem, profile = load_dem(V3_DEM)
if dem.shape != drainage_mask.shape:
    raise SystemExit(f"shape mismatch dem {dem.shape} vs mask {drainage_mask.shape}")

print("Computing HAND on v3 bare-earth terrain (same drainage cells) ...")
hand = compute_hand(dem, drainage_mask, profile)

prof = profile.copy()
prof.update(dtype="float32", count=1, compress="deflate", predictor=2, nodata=np.nan)
OUT.parent.mkdir(parents=True, exist_ok=True)
with rasterio.open(OUT, "w", **prof) as dst:
    dst.write(hand.astype("float32"), 1)

fin = np.isfinite(hand)
print(f"wrote {OUT}")
print(f"  valid={int(fin.sum()):,}  mean={float(np.nanmean(hand)):.2f}  "
      f"median={float(np.nanmedian(hand)):.2f}  max={float(np.nanmax(hand)):.2f}")
# compare to v2 HAND distribution
print(f"  v2 HAND mean={float(np.nanmean(h2)):.2f} median={float(np.nanmedian(h2)):.2f}")
