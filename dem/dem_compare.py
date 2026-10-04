"""Head-to-head: v2.0 DEM (subsidence-corrected GLO-30 DSM) vs v3.0 bare-earth,
scored against HELD-OUT ICESat-2 ground truth (the points the v3.0 f-fit never saw).
Lower |bias| + MAE/RMSE = closer to true ground = better flood terrain."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, r"D:\GPTs\Projects\flood-v3.0\dem")
from raster_utils import sample_points
from pyproj import Transformer

V2 = r"D:\GPTs\Projects\flood-v3.0\dem\bangkok\glo30_subsidence_corrected_utm47n.tif"   # v2.0 terrain (DSM)
V3 = r"D:\GPTs\Projects\flood-v3.0\dem\bangkok\dem_bareearth_bangkok_present_conditioned.tif"  # v3.0 bare-earth
PTS = r"D:\GPTs\Projects\flood-v3.0\dem\bangkok\calib\points_sampled.parquet"

df = pd.read_parquet(PTS)
df = df[df["split"] == "holdout"].copy()          # fair: never used to fit f
to = Transformer.from_crs("EPSG:4326", "EPSG:32647", always_xy=True)
x, y = to.transform(df["lon"].values, df["lat"].values)
truth = df["h_egm2008"].values
df["v2"] = sample_points(V2, x, y)
df["v3"] = sample_points(V3, x, y)
m = np.isfinite(df["v2"]) & np.isfinite(df["v3"]) & np.isfinite(truth)
df = df[m]; truth = df["h_egm2008"].values

def stats(resid):
    r = resid[np.isfinite(resid)]
    return dict(bias=round(float(r.mean()),3), mae=round(float(np.abs(r).mean()),3),
                rmse=round(float(np.sqrt((r**2).mean())),3), n=len(r))

print(f"held-out ground points: {len(df)}\n")
print(f"{'zone':14s}{'n':>7s} | {'v2.0 DSM bias/MAE':>22s} | {'v3.0 bare bias/MAE':>22s} | winner(MAE)")
for z in ["coastal_flat","urban_core","vegetated","other","ALL"]:
    sub = df if z=="ALL" else df[df["zone"]==z]
    if not len(sub): continue
    s2 = stats(sub["v2"].values - sub["h_egm2008"].values)
    s3 = stats(sub["v3"].values - sub["h_egm2008"].values)
    win = "v3.0" if s3["mae"] < s2["mae"] else "v2.0"
    print(f"{z:14s}{s2['n']:>7d} | {s2['bias']:+7.2f} / {s2['mae']:5.2f}         | {s3['bias']:+7.2f} / {s3['mae']:5.2f}         | {win}")
