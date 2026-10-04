"""KL aux fetch: warp+clip ESA WorldCover 2021 (2 x 3-deg tiles N00E099 + N03E099)
onto the KL GLO-30 grid as a single categorical GeoTIFF. Avoids rasterio.merge
(native crash in this env); reads each remote COG via WarpedVRT onto the DEM grid
and overlays non-nodata cells. nearest resampling (categorical land cover)."""
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling

DEM = r"D:\GPTs\Projects\flood-v3.0\dem\kl\glo30_dsm_utm47n.tif"
OUT = r"D:\GPTs\Projects\flood-v3.0\dem\kl\auxdata\worldcover_2021_N00E099.tif"
S3 = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
TILES = ["ESA_WorldCover_10m_2021_v200_N00E099_Map.tif",
         "ESA_WorldCover_10m_2021_v200_N03E099_Map.tif"]

with rasterio.open(DEM) as dem:
    prof = dem.profile.copy()
    H, W = dem.height, dem.width
    out = np.zeros((H, W), dtype="uint8")  # 0 = nodata/unfilled
    for t in TILES:
        url = f"{S3}/{t}"
        print(f"opening {t} ...", flush=True)
        with rasterio.open(url) as src:
            nod = src.nodata if src.nodata is not None else 0
            with WarpedVRT(src, crs=dem.crs, transform=dem.transform,
                           width=W, height=H, resampling=Resampling.nearest,
                           src_nodata=nod, nodata=0) as vrt:
                a = vrt.read(1)
        fill = (out == 0) & (a != 0)
        out[fill] = a[fill]
        print(f"  filled {int(fill.sum()):,} cells from {t}", flush=True)

prof.update(dtype="uint8", count=1, nodata=0, compress="deflate")
with rasterio.open(OUT, "w", **prof) as d:
    d.write(out, 1)
vals, cnts = np.unique(out, return_counts=True)
print("class histogram:", dict(zip(vals.tolist(), cnts.tolist())), flush=True)
print(f"wrote {OUT}", flush=True)
