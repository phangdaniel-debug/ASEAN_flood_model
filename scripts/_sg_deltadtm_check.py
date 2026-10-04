"""Can DeltaDTM serve as Singapore's bare-earth? Test it against the SAME held-out
ICESat-2 points the model DEM was validated on, and report coverage."""
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

DD = r"D:\GPTs\Projects\flood-v3.0\dem\singapore\auxdata\deltadtm_singapore.tif"
PTS = r"D:\GPTs\Projects\flood-v3.0\dem\singapore\calib\points_sampled.parquet"
DSM = r"D:\GPTs\Projects\flood-v2.0\data\singapore\copernicus_dem_utm48n.tif"

df = pd.read_parquet(PTS)
ho = df[df["split"] == "holdout"].copy()

with rasterio.open(DD) as r:
    crs = r.crs; nod = r.nodata
    arr = r.read(1).astype("float64")
    if nod is not None:
        valid = arr != nod
    else:
        valid = np.isfinite(arr)
    cov = int(valid.sum()); tot = arr.size
    ev = arr[valid]
    tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    xs, ys = tf.transform(ho["lon"].values, ho["lat"].values)
    rows, cols = [], []
    for x, y in zip(xs, ys):
        rr, cc = r.index(x, y)
        rows.append(rr); cols.append(cc)
    rows = np.array(rows); cols = np.array(cols)
    inb = (rows >= 0) & (rows < r.height) & (cols >= 0) & (cols < r.width)
    samp = np.full(len(ho), np.nan)
    samp[inb] = arr[rows[inb], cols[inb]]
    if nod is not None:
        samp[samp == nod] = np.nan

ho["dd"] = samp
m = np.isfinite(ho["dd"].values)
resid = ho["dd"].values[m] - ho["h_egm2008"].values[m]
print(f"DeltaDTM coverage: {cov:,}/{tot:,} cells ({100*cov/tot:.1f}% of grid)")
print(f"  DeltaDTM elev (covered): min={ev.min():.1f} median={np.median(ev):.1f} "
      f"p95={np.percentile(ev,95):.1f} max={ev.max():.1f} m")
print(f"held-out points: {len(ho)} total, {int(m.sum())} fall on DeltaDTM coverage")
print(f"DeltaDTM vs held-out ICESat-2: bias={resid.mean():+.2f} mae={np.abs(resid).mean():.2f} "
      f"rmse={np.sqrt((resid**2).mean()):.2f} m")
# per zone
for z in sorted(ho["zone"].dropna().unique()):
    mm = m & (ho["zone"].values == z)
    if mm.sum() > 0:
        rz = ho["dd"].values[mm] - ho["h_egm2008"].values[mm]
        print(f"  {z:13} n={int(mm.sum()):4} bias={rz.mean():+.2f} mae={np.abs(rz).mean():.2f}")
