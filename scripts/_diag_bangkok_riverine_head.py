"""Sanity-check the riverine source head before the full inertial run.
Reports bed elevations at the Chao Phraya mainstem source cells vs the floodplain,
so the chosen overbank head (BCP RP100 = 7.11 m above bed) can be judged physical."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio
from model.hand_model import derive_drainage_mask_from_accumulation

DEM = "data/bangkok/copernicus_dem_utm47n_subsidence_corrected.tif"
THR = 100000
OVERBANK = 7.11

with rasterio.open(DEM) as ds:
    z = ds.read(1).astype(np.float64); prof = ds.profile; nod = ds.nodata
if nod is not None:
    z = np.where(z == nod, np.nan, z)
src = derive_drainage_mask_from_accumulation(z.astype(np.float32), prof, acc_threshold=THR)
src = src & np.isfinite(z)

zb = z[src]
zf = z[np.isfinite(z) & ~src]
fp = np.isfinite(z) & ~src
dom_km2 = fp.sum() * 900 / 1e6
print(f"source cells: {int(src.sum()):,}  (acc>={THR})")
print(f"  bed z at source  : min={np.nanmin(zb):.2f} p25={np.nanpercentile(zb,25):.2f} "
      f"median={np.nanmedian(zb):.2f} p75={np.nanpercentile(zb,75):.2f} max={np.nanmax(zb):.2f}")
print(f"  floodplain z     : min={np.nanmin(zf):.2f} p25={np.nanpercentile(zf,25):.2f} "
      f"median={np.nanmedian(zf):.2f} p75={np.nanpercentile(zf,75):.2f} max={np.nanmax(zf):.2f}")
print(f"  domain (non-source, finite): {dom_km2:.0f} km2")
# Connectivity-NAIVE upper bound on reach for a range of sustained channel heads.
# (The real hydrodynamic routing + ridges/King's-Dyke will cut this down; equilibrium
#  floodplain depth ~ head on a near-flat delta, so head should ~ the documented 1.5-3 m
#  2011 inundation depth, NOT the HAND-convention 7.11 m RP100 Manning-stage.)
zb_med = float(np.nanmedian(zb))
print(f"\n  head |  src WSE(med) | floodplain-below-WSE (naive upper bound on extent)")
for head in (2.0, 2.5, 3.0, 4.68, 7.11):
    wse_med = zb_med + head
    below = fp & (z < wse_med)
    print(f"  {head:4.2f} | {wse_med:11.2f}  | {below.sum()*900/1e6:5.0f} km2  ({100*below.sum()/fp.sum():4.1f}% of domain)")
