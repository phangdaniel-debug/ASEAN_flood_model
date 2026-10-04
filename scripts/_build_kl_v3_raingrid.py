"""Build the KL v3 raingrid DEM by transferring the EXACT v2 drain-burn delta
onto the v3 conditioned bare-earth terrain. This keeps the OSM-waterway drain
geometry identical to v2 (terrain-independent) and changes only the base terrain
— the controlled A/B variable.

  raingrid_v3 = v3_conditioned + (v2_raingrid - v2_conditioned)

The burn delta is ~0 everywhere except burned drain cells, where it is the v2
sink depth; adding it to v3 reproduces the same sinks on the new terrain.
"""
from pathlib import Path

import numpy as np
import rasterio

V2_COND = r"D:\GPTs\Projects\flood-v2.0\data\kuala_lumpur\copernicus_dem_utm47n_conditioned.tif"
V2_RG = r"D:\GPTs\Projects\flood-v2.0\data\kuala_lumpur\copernicus_dem_utm47n_raingrid.tif"
V3_COND = r"D:\GPTs\Projects\flood-v3.0\dem\kl\dem_bareearth_kl_present_conditioned.tif"
OUT = r"D:\GPTs\Projects\flood-v2.0\outputs_v3dem\_dem\kl_raingrid_v3.tif"


def read(p):
    with rasterio.open(p) as r:
        a = r.read(1).astype("float64")
        return a, r.profile, r.nodata


c2, _, n_c2 = read(V2_COND)
rg2, _, n_rg2 = read(V2_RG)
v3, prof, n_v3 = read(V3_COND)

for a, n in [(c2, n_c2), (rg2, n_rg2), (v3, n_v3)]:
    if n is not None:
        a[a == n] = np.nan

if not (c2.shape == rg2.shape == v3.shape):
    raise SystemExit(f"shape mismatch {c2.shape} {rg2.shape} {v3.shape}")

delta = rg2 - c2                     # burn delta (0 except at drain cells)
delta = np.where(np.isfinite(delta), delta, 0.0)
burned = np.count_nonzero(np.abs(delta) > 1e-6)
print(f"burn-delta cells: {burned:,}  min={np.nanmin(delta):.2f}  max={np.nanmax(delta):.2f}  "
      f"mean(nonzero)={delta[np.abs(delta)>1e-6].mean():.2f}")

rg3 = v3 + delta
nod = -9999.0
rg3 = np.where(np.isfinite(rg3), rg3, nod)

prof_out = prof.copy()
prof_out.update(dtype="float32", nodata=nod, compress="deflate", predictor=2)
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
with rasterio.open(OUT, "w", **prof_out) as dst:
    dst.write(rg3.astype("float32"), 1)
fin = rg3 != nod
print(f"wrote {OUT}")
print(f"  v3 raingrid: min={rg3[fin].min():.2f} median={np.median(rg3[fin]):.2f} max={rg3[fin].max():.2f}")
