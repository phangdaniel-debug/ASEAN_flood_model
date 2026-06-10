"""Diagnostic: pluvial-only | fluvial-only | combined+hotspots at RP100 (2020),
to judge geographic reasonableness of each hazard layer."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio
from rasterio.warp import transform as T
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

YR,SCN,RP=2020,"SSP5-8.5",100
base=f"outputs/kuala_lumpur_ssp585_{YR}"
def load(p):
    with rasterio.open(p) as d:
        a=d.read(1).astype(float); a=np.where(np.isfinite(a),a,np.nan); b=d.bounds; crs=d.crs
    return a,(b.left,b.right,b.bottom,b.top),crs
pl,ext,crs=load(f"{base}/pluvial/rp_{RP}/pluvial_depth_{SCN}_{YR}_rp{RP}.tif")
fl,_,_=load(f"{base}/fluvial/rp_{RP}/fluvial_depth_{SCN}_{YR}_rp{RP}.tif")
comb=np.fmax(np.nan_to_num(pl,nan=0),np.nan_to_num(fl,nan=0)); comb=np.where(comb>0,comb,np.nan)
def km2(a): w=a[np.isfinite(a)&(a>0.1)]; return w.size*900/1e6
cmap=LinearSegmentedColormap.from_list("f",["#c6e2ff","#3b82f6","#1e3a8a","#4c1d95"])
# hotspots
reg=pd.read_csv("data/kuala_lumpur/manifest/hotspots.csv")
def to_xy(df):
    if len(df)==0: return [],[]
    xs,ys=T("EPSG:4326",crs,df.lon.tolist(),df.lat.tolist()); return xs,ys
pos=reg[reg.kind=="positive"]; dry=reg[reg.kind=="dry"]
px,py=to_xy(pos); dx,dy=to_xy(dry)
fig,axes=plt.subplots(1,3,figsize=(21,8),constrained_layout=True)
for ax,(a,ttl) in zip(axes,[(pl,f"PLUVIAL only  ·  {km2(pl):.0f} km²"),
                            (fl,f"FLUVIAL only  ·  {km2(fl):.0f} km²"),
                            (comb,f"COMBINED + hotspots  ·  {km2(comb):.0f} km²")]):
    ax.imshow(np.where(a>0.1,a,np.nan),extent=ext,cmap=cmap,vmin=0,vmax=3,interpolation="nearest")
    ax.set_title(ttl,fontsize=13); ax.set_xticks([]); ax.set_yticks([])
axes[2].scatter(px,py,c="red",s=28,edgecolor="k",lw=0.5,label=f"positives (n={len(pos)})",zorder=5)
axes[2].scatter(dx,dy,c="yellow",s=28,marker="^",edgecolor="k",lw=0.5,label=f"dry controls (n={len(dry)})",zorder=5)
axes[2].legend(loc="upper right",fontsize=9)
fig.suptitle("KL RP100 (2020) hazard-layer reasonableness — pluvial vs fluvial vs combined",fontsize=15,weight="bold")
out=Path(f"{base}/_diag_hazard_layers_rp100.png"); fig.savefig(out,dpi=120,bbox_inches="tight")
print("wrote",out)
print(f"pluvial {km2(pl):.0f} km2, fluvial {km2(fl):.0f} km2, combined {km2(comb):.0f} km2")
