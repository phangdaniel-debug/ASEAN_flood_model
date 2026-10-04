"""Singapore bare-earth from DeltaDTM.

ICESat-2 cannot validate (or calibrate) bare-earth over dense, reclaimed Singapore:
the held-out ATL08 'ground' is building/canopy-contaminated (DeltaDTM, validated at
~0.45 m globally, disagrees with ATL08 by the same ~2 m, with urban bias -2.6 m -->
the lidar is the noisy reference, not the DEM). So Singapore's bare-earth is taken
from DeltaDTM (CC-BY, validated bare-earth DTM) where it has coverage -- which is the
entire flood-relevant low terrain (<=30 m, ~91% of held-out points) -- and filled with
the ICESat-2-calibrated bare-earth only for the high interior (>30 m, non-flood).

  SG_bareearth = DeltaDTM where valid, else ICESat-2 bare-earth (canopy-removed).

Output is a drop-in for the v2.0 Singapore terrain (EGM2008 / UTM48N / 30 m grid).
"""
from pathlib import Path

import numpy as np
import rasterio

BASE = Path(r"D:\GPTs\Projects\flood-v3.0\dem\singapore")
DD = BASE / "auxdata" / "deltadtm_singapore.tif"            # validated bare-earth DTM
FILL = BASE / "dem_bareearth_singapore.tif"                 # ICESat-2 bare-earth (high-interior fill)
OUT = BASE / "dem_bareearth_singapore_deltadtm.tif"

with rasterio.open(DD) as r:
    dd = r.read(1).astype("float64")
    prof = r.profile.copy()
    dd_nod = r.nodata
with rasterio.open(FILL) as r:
    fill = r.read(1).astype("float64")
    fill_nod = r.nodata

dd_valid = np.isfinite(dd) & (dd != dd_nod)
fill_valid = np.isfinite(fill) & (fill != fill_nod)

out = np.where(dd_valid, dd, np.where(fill_valid, fill, -9999.0))
n_dd = int(dd_valid.sum())
n_fill = int((~dd_valid & fill_valid).sum())
n_gap = int((~dd_valid & ~fill_valid).sum())
land = out != -9999.0
print(f"DeltaDTM cells (authoritative): {n_dd:,}")
print(f"ICESat-2 fill cells (>30 m / gaps): {n_fill:,}")
print(f"remaining nodata: {n_gap:,}")
if land.any():
    v = out[land]
    print(f"composite elev: min={v.min():.1f} median={np.median(v):.1f} max={v.max():.1f} m")

prof.update(dtype="float32", nodata=-9999.0, compress="deflate", predictor=2, count=1)
with rasterio.open(OUT, "w", **prof) as d:
    d.write(out.astype("float32"), 1)
print(f"wrote {OUT}")
