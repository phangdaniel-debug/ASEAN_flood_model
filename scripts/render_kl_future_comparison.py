"""Headline KL viz: present-day (2020) vs SSP5-8.5 2100 combined pluvial∨fluvial
RP100 flood depth, side-by-side with a shared colour scale."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

def load(yr):
    p=f"outputs/kuala_lumpur_ssp585_{yr}/_validation/combined_rp100.tif"
    with rasterio.open(p) as d:
        a=d.read(1).astype(float); a=np.where(np.isfinite(a),a,np.nan)
        b=d.bounds
    return a,(b.left,b.right,b.bottom,b.top)

a20,ext=load(2020); a100,_=load(2100)
def stats(a):
    w=a[np.isfinite(a)&(a>0.1)]; return w.size*900/1e6, (w.mean() if w.size else 0)
e20,m20=stats(a20); e100,m100=stats(a100)

cmap=LinearSegmentedColormap.from_list("flood",["#c6e2ff","#3b82f6","#1e3a8a","#4c1d95"])
vmax=3.0
fig,axes=plt.subplots(1,2,figsize=(15,8),constrained_layout=True)
for ax,a,(yr,e,m) in zip(axes,[a20,a100],[(2020,e20,m20),(2100,e100,m100)]):
    disp=np.where(a>0.1,a,np.nan)
    im=ax.imshow(disp,extent=ext,cmap=cmap,vmin=0,vmax=vmax,interpolation="nearest")
    ax.set_title(f"KL {yr} {'(present-day)' if yr==2020 else '(SSP5-8.5)'}\nRP100 combined  ·  {e:.0f} km²  ·  mean {m:.2f} m",
                 fontsize=13)
    ax.set_xticks([]); ax.set_yticks([])
cb=fig.colorbar(im,ax=axes,shrink=0.7,location="bottom",pad=0.02,aspect=40)
cb.set_label("Flood depth (m), capped at 3.0 m",fontsize=11)
fig.suptitle("Kuala Lumpur — present-day vs end-of-century (SSP5-8.5 2100) RP100 flood hazard\n"
             f"pluvial∨fluvial; +{100*(e100/e20-1):.0f}% extent, +{100*(m100/m20-1):.0f}% mean depth",
             fontsize=15,weight="bold")
out=Path("outputs/kuala_lumpur_ssp585_2100/kl_2020_vs_2100_rp100.png")
fig.savefig(out,dpi=130,bbox_inches="tight"); print("wrote",out)
