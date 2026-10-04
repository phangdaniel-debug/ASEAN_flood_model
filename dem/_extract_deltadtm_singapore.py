"""Extract Singapore's DeltaDTM 1-deg tile(s) from the remote Asia.zip via HTTP range reads.
SG bbox lon 103.57-104.10, lat 1.15-1.50 -> 1-deg tiles N01E103 and N01E104.
DeltaDTM is coastal-only (clips ~10m MSL); SG is a coastal city-state so expect good
coverage. Output is warped onto the SG GLO-30 UTM grid for validate_dem.py's coastal
x-check and the FALL-BACK compose. Tiles absent from the zip are skipped."""
import fsspec, zipfile, rasterio, numpy as np
from rasterio.io import MemoryFile
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling

URL = "https://data.4tu.nl/file/1da2e70f-6c4d-4b03-86bd-b53e789cc629/672eba4c-1334-44c6-8119-8879ded25912"
DEM = r"D:\GPTs\Projects\flood-v2.0\data\singapore\copernicus_dem_utm48n.tif"
OUT = r"D:\GPTs\Projects\flood-v3.0\dem\singapore\auxdata\deltadtm_singapore.tif"
CAND = ["DeltaDTM_v1_1_N01E103.tif", "DeltaDTM_v1_1_N01E104.tif"]

zf = zipfile.ZipFile(fsspec.filesystem("http").open(URL))
names = set(zf.namelist())
def find(tile):
    for n in names:
        if n.endswith(tile):
            return n
    return None

present = [(t, find(t)) for t in CAND]
present = [(t, n) for t, n in present if n]
print("tiles present in zip:", [t for t, _ in present], flush=True)
if not present:
    print("NO SG DeltaDTM tiles in zip. Skipping deltadtm — x-check will be omitted.", flush=True)
    raise SystemExit(0)

with rasterio.open(DEM) as dem:
    H, W = dem.height, dem.width
    prof = dem.profile.copy()
    out = np.full((H, W), np.nan, dtype="float32")
    for t, n in present:
        data = None
        for attempt in range(6):
            try:
                data = zf.read(n)
                break
            except Exception as e:
                print(f"  read {t} attempt {attempt+1} failed: {type(e).__name__} {str(e)[:80]}", flush=True)
        if data is None:
            print(f"  GIVING UP on {t} after retries", flush=True)
            continue
        print(f"read {t}: {len(data)/1e6:.1f} MB", flush=True)
        with MemoryFile(data) as mf, mf.open() as ds:
            nod = ds.nodata
            with WarpedVRT(ds, crs=dem.crs, transform=dem.transform, width=W, height=H,
                           resampling=Resampling.bilinear, src_nodata=nod) as vrt:
                a = vrt.read(1).astype("float32")
                vnod = vrt.nodata if vrt.nodata is not None else nod
        if vnod is not None:
            a = np.where(a == vnod, np.nan, a)
        fill = np.isnan(out) & np.isfinite(a)
        out[fill] = a[fill]
        print(f"  filled {int(fill.sum()):,} cells", flush=True)

n = int(np.isfinite(out).sum())
prof.update(dtype="float32", count=1, nodata=-9999.0, compress="deflate")
with rasterio.open(OUT, "w", **prof) as d:
    d.write(np.where(np.isfinite(out), out, -9999.0).astype("float32"), 1)
print(f"valid cells in SG grid: {n:,} ({100*n/(H*W):.2f}%)", flush=True)
if n:
    v = out[np.isfinite(out)]
    print(f"elev m min/med/max = {v.min():.2f}/{np.median(v):.2f}/{v.max():.2f}", flush=True)
print(f"wrote {OUT}", flush=True)
print("DELTADTM DONE", flush=True)
