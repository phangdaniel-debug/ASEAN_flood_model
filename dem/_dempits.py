import rasterio, numpy as np
from scipy import ndimage
p=r"D:\GPTs\Projects\flood-v3.0\dem\bangkok\dem_bareearth_bangkok_present.tif"
with rasterio.open(p) as s:
    a=s.read(1).astype("float64"); nod=s.nodata
m=np.isfinite(a)&(a!=nod)
print("elev min/p1/med/p99/max:", round(float(np.nanmin(a[m])),2), round(float(np.percentile(a[m],1)),2), round(float(np.median(a[m])),2), round(float(np.percentile(a[m],99)),2), round(float(np.nanmax(a[m])),2))
# local median (5x5) and residual to find pits
med=ndimage.median_filter(np.where(m,a,np.nan),size=5)
resid=a-med
deep=m&(resid<-3)
print("cells >3m below local median (pits):", int(deep.sum()), "min resid:", round(float(np.nanmin(resid[m])),2))
print("cells < -5m elev:", int((m&(a<-5)).sum()), " < -10m:", int((m&(a<-10)).sum()))
