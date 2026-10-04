"""Extract Bangkok's coastal DeltaDTM tile (N13E100) from the remote 17GB Asia.zip
via HTTP range reads - no full download. EGM2008 orthometric, coastal-only, CC-BY 4.0."""
import fsspec, zipfile, rasterio, numpy as np
from rasterio.io import MemoryFile

URL="https://data.4tu.nl/file/1da2e70f-6c4d-4b03-86bd-b53e789cc629/672eba4c-1334-44c6-8119-8879ded25912"
TILE="DeltaDTM_v1_1_N13E100.tif"
OUT=r"D:\GPTs\Projects\flood-v3.0\dem\bangkok\auxdata\deltadtm_bangkok.tif"

zf=zipfile.ZipFile(fsspec.filesystem("http").open(URL))
data=zf.read(TILE)
print(f"read {TILE}: {len(data)/1e6:.1f} MB", flush=True)
with MemoryFile(data) as mf, mf.open() as ds:
    a=ds.read(1); prof=ds.profile.copy(); nod=ds.nodata
    print(f"{ds.shape} crs={ds.crs} bounds={tuple(round(x,2) for x in ds.bounds)} nodata={nod}", flush=True)
    prof.update(driver="GTiff", compress="deflate")
    with rasterio.open(OUT,"w",**prof) as d: d.write(a,1)
v=a[(a!=nod)&np.isfinite(a)]
print(f"wrote {OUT}: valid={v.size} ({100*v.size/a.size:.0f}% - coastal-only) elev min/med/max={v.min():.2f}/{np.median(v):.2f}/{v.max():.2f} m", flush=True)
