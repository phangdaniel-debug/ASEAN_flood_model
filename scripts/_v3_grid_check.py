import sys
import numpy as np
import rasterio

paths = [
    ("v2 subs-corrected", r"D:\GPTs\Projects\flood-v2.0\data\jakarta\copernicus_dem_utm48s_subsidence_corrected.tif"),
    ("v3 conditioned",    r"D:\GPTs\Projects\flood-v3.0\dem\jakarta\dem_bareearth_jakarta_present_conditioned.tif"),
    ("v2 hand_utm48s",    r"D:\GPTs\Projects\flood-v2.0\data\jakarta\hand_utm48s.tif"),
]
for tag, p in paths:
    with rasterio.open(p) as r:
        a = r.read(1).astype("float64")
        nod = r.nodata
        v = a[a != nod] if nod is not None else a.ravel()
        print(f"{tag:18} crs={r.crs} size={r.width}x{r.height} res={tuple(round(x,2) for x in r.res)} nod={nod}")
        print(f"   bounds={tuple(round(b,1) for b in r.bounds)} "
              f"min={float(np.nanmin(v)):.2f} max={float(np.nanmax(v)):.2f} median={float(np.nanmedian(v)):.2f}")
