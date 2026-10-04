import os, rasterio, numpy as np
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"]="EMPTY_DIR"
os.environ["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"]=".tif,.zip"
url="https://data.4tu.nl/file/1da2e70f-6c4d-4b03-86bd-b53e789cc629/672eba4c-1334-44c6-8119-8879ded25912"
tile="DeltaDTM_v1_1_N13E100.tif"
vp=f"/vsizip/{{/vsicurl/{url}}}/{tile}"
print("opening", vp, flush=True)
with rasterio.open(vp) as s:
    print("shape",s.shape,"crs",s.crs,"res",s.res,"bounds",s.bounds,"nodata",s.nodata, flush=True)
    a=s.read(1)
    prof=s.profile.copy()
print("elev valid", int(np.isfinite(a).sum()), "min/med/max", float(np.nanmin(a)), float(np.nanmedian(a)), float(np.nanmax(a)), flush=True)
prof.update(driver="GTiff", compress="deflate")
out=r"D:\GPTs\Projects\flood-v3.0\dem\bangkok\auxdata\deltadtm_N13E100.tif"
with rasterio.open(out,"w",**prof) as d: d.write(a,1)
print("wrote", out, flush=True)
