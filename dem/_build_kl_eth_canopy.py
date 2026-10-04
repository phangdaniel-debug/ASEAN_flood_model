"""Mosaic the two ETH GlobalCanopyHeight 10m tiles covering KL (N03E099 + N00E099,
since the KL DEM straddles 3 deg N) onto the KL 30 m GLO-30 grid -> a drop-in
canopy_eth_2020_kl.tif replacement for canopy_meta_chm_kl.tif. Warp each tile with
WarpedVRT (average) and overlay (fill NaN); rasterio.merge crashes in this env.
ETH nodata = 255.
"""
from pathlib import Path

import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling

AUX = Path(r"D:\GPTs\Projects\flood-v3.0\dem\kl\auxdata")
DEM = r"D:\GPTs\Projects\flood-v3.0\dem\kl\glo30_dsm_utm47n.tif"
TILES = [AUX / "ETH_GlobalCanopyHeight_10m_2020_N03E099_Map.tif",
         AUX / "ETH_GlobalCanopyHeight_10m_2020_N00E099_Map.tif"]
OUT = AUX / "canopy_eth_2020_kl.tif"

with rasterio.open(DEM) as dem:
    H, W = dem.height, dem.width
    prof = dem.profile.copy()
    out = np.full((H, W), np.nan, dtype="float32")
    for t in TILES:
        with rasterio.open(t) as src:
            with WarpedVRT(src, crs=dem.crs, transform=dem.transform,
                           width=W, height=H, resampling=Resampling.average) as vrt:
                a = vrt.read(1).astype("float32")
                nod = vrt.nodata if vrt.nodata is not None else src.nodata
        if nod is not None:
            a = np.where(a == nod, np.nan, a)
        a = np.where(a >= 255, np.nan, a)  # ETH 255 = nodata
        fill = np.isnan(out) & np.isfinite(a)
        out[fill] = a[fill]
        print(f"{t.name}: filled {int(fill.sum()):,} cells")

n_cov = int(np.isfinite(out).sum())
out_w = np.where(np.isfinite(out), out, 255).astype("float32")
prof.update(dtype="float32", count=1, nodata=255, compress="deflate")
with rasterio.open(OUT, "w", **prof) as d:
    d.write(out_w, 1)
v = out[np.isfinite(out)]
print(f"coverage {n_cov:,}/{H*W:,} ({100*n_cov/(H*W):.1f}%)")
print(f"canopy m: min/med/mean/max = {v.min():.2f}/{np.median(v):.2f}/{v.mean():.2f}/{v.max():.2f}")
print(f"wrote {OUT}")
