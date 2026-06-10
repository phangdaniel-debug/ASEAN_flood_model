"""Bangkok main-stem HAND viability sweep (Plan B2 Task 1) — mirrors KL Plan 8.
At each accumulation threshold: RP100 mainstem-fluvial extent (HAND<7.11m) + HAND_min at
the defended-CBD dry controls (want NOT flooded) and the missed-2011 positives (want reached)."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio, math
from rasterio.warp import transform as T
from model.hand_model import compute_hand, derive_drainage_mask_from_accumulation
import pandas as pd

with rasterio.open("data/bangkok/copernicus_dem_utm47n_subsidence_corrected.tif") as ds:
    dem=ds.read(1).astype(np.float32); profile=ds.profile; transform=ds.transform; crs=ds.crs; nod=ds.nodata
if nod is not None: dem=np.where(dem==nod,np.nan,dem)
land=np.isfinite(dem); land_km2=land.sum()*900/1e6
MAINSTEM_RP100=7.11
reg=pd.read_csv("data/bangkok/manifest/hotspots.csv").set_index("name")
SPOTS={
 "Silom(dry)":"Silom","Sathorn(dry)":"Sathorn","Sukhumvit(dry)":"Sukhumvit (Watthana)",
 "SaiMai(+miss)":"Sai Mai","BangBuaThong(+miss)":"Bang Bua Thong",
 "PakKret(+miss)":"Pak Kret","MuangNon(+miss)":"Mueang Nonthaburi",
}
def hmin(hand,name,R=50.0):
    r=reg.loc[name]; xs,ys=T("EPSG:4326",crs,[r.lon],[r.lat]); cf,rf=~transform*(xs[0],ys[0])
    row,col=int(rf),int(cf); rr=int(math.ceil(R/abs(transform.e))); rc=int(math.ceil(R/abs(transform.a)))
    b=hand[max(0,row-rr):min(hand.shape[0],row+rr+1),max(0,col-rc):min(hand.shape[1],col+rc+1)]
    return float(np.nanmin(b)) if np.isfinite(b).any() else float('nan')
print(f"land={land_km2:.0f} km2; mainstem RP100 stage={MAINSTEM_RP100} m\n")
hdr="thr      chan   ext<7.11   ext%  " + "  ".join(k.split('(')[0][:8] for k in SPOTS)
print(hdr)
for thr in [20000,200000,1000000,3000000]:
    mask=derive_drainage_mask_from_accumulation(dem,profile,acc_threshold=thr)
    hand=compute_hand(dem,mask,profile)
    ext=int(np.nansum(hand<MAINSTEM_RP100)); extkm=ext*900/1e6
    vals=[hmin(hand,n) for n in SPOTS.values()]
    print(f"{thr:>8d} {int(mask.sum()):>6d} {extkm:>7.0f}km2 {100*ext/land.sum():>4.0f}%  "+"  ".join(f"{v:7.1f}" for v in vals))
