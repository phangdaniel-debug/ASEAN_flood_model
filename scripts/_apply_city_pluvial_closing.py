"""Bridge-only morphological closing on the 4 cities' pluvial layers (all cells).
Spec + pre-registered gates: flood-v5.0/docs/technical/duration-layer-methodology.md
(Addendum 2). Gate measurement (RP100/2020): extent x1.20-1.28, HR/CRR byte-identical.

CRITICAL: *.orig sidecars hold the PRE-canal-HAND pluvial — do NOT read them here.
This script backs up the CURRENT raster to *.preclose (once) and closes that.
Bridge-only: NO single-pixel deletion (city point-gates showed small ponds carry hits).
Bridged cells get 0.10 m nominal depth + a pluvial_bridged_*.tif sidecar for the
duration demotion rule (donor class - 1).
"""
import glob
import os
import shutil

import numpy as np
import rasterio
from scipy import ndimage

S8 = np.ones((3, 3), bool)
BRIDGE_DEPTH = 0.10

n_done = 0
for pl in sorted(glob.glob("outputs/_fixed_atlas/*/pluvial/rp_*/pluvial_depth_*.tif")):
    pre = pl + ".preclose"
    src = pre if os.path.exists(pre) else pl
    if not os.path.exists(pre):
        shutil.copy2(pl, pre)
    with rasterio.open(src) as ds:
        d = ds.read(1)
        prof = ds.profile
    dd = np.where(np.isfinite(d), d, 0.0).astype("float32")
    wet = dd >= 0.1
    closed = ndimage.binary_closing(wet, structure=S8)
    bridged = closed & ~wet
    new = dd.copy()
    new[bridged] = BRIDGE_DEPTH
    new[~np.isfinite(d) & ~bridged] = np.nan
    oprof = {**prof, "compress": "deflate"}
    for k in ("blockxsize", "blockysize", "tiled", "interleave"):
        oprof.pop(k, None)
    with rasterio.open(pl, "w", **oprof) as o:
        o.write(new, 1)
    bprof = {**oprof, "dtype": "uint8", "nodata": 0}
    bpath = os.path.join(os.path.dirname(pl),
                         os.path.basename(pl).replace("pluvial_depth", "pluvial_bridged"))
    with rasterio.open(bpath, "w", **bprof) as o:
        o.write(bridged.astype(np.uint8), 1)
    n_done += 1
    if n_done % 15 == 0:
        print(f"  {n_done} cells...", flush=True)
print(f"DONE: {n_done} pluvial cells closed (backups *.preclose, bridged sidecars written)")
