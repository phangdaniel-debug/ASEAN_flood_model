import pathlib
import numpy as np
import rasterio

def rd(p):
    with rasterio.open(p) as r:
        a = r.read(1).astype("float64")
        if r.nodata is not None:
            a[a == r.nodata] = np.nan
        return a, r.profile

c2, _ = rd(r"D:\GPTs\Projects\flood-v2.0\data\kuala_lumpur\copernicus_dem_utm47n_conditioned.tif")
rg2, _ = rd(r"D:\GPTs\Projects\flood-v2.0\data\kuala_lumpur\copernicus_dem_utm47n_raingrid.tif")
v3, prof = rd(r"D:\GPTs\Projects\flood-v3.0\dem\kl\dem_bareearth_kl_eth_present_conditioned.tif")

delta = np.where(np.isfinite(rg2 - c2), rg2 - c2, 0.0)
rg3 = v3 + delta
nod = -9999.0
rg3 = np.where(np.isfinite(rg3), rg3, nod)
prof.update(dtype="float32", nodata=nod, compress="deflate", predictor=2)
out = r"D:\GPTs\Projects\flood-v2.0\outputs_v3dem\_dem\kl_raingrid_v3eth.tif"
pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
with rasterio.open(out, "w", **prof) as d:
    d.write(rg3.astype("float32"), 1)
print(f"wrote {out}  burn cells {int((np.abs(delta) > 1e-6).sum()):,}")
