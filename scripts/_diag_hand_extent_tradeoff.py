"""Extent vs accumulation-threshold trade-off for single-stage HAND fluvial."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio, math
from rasterio.warp import transform as rio_transform
from model.hand_model import compute_hand, derive_drainage_mask_from_accumulation
from scripts.city_manifest import load_hotspots_from_manifest

with rasterio.open("data/kuala_lumpur/copernicus_dem_utm47n.tif") as ds:
    dem=ds.read(1).astype(np.float32); profile=ds.profile; transform=ds.transform; crs=ds.crs; nod=ds.nodata
if nod is not None: dem=np.where(dem==nod,np.nan,dem)
land=np.isfinite(dem); land_km2=land.sum()*900/1e6
hs={h.label:h for h in load_hotspots_from_manifest("kuala_lumpur")}
def fz(n):
    for k,v in hs.items():
        if n in k: return v
spots={"FederalHill(dry)":fz("Bukit Persekutuan"),"OldKlangRd(+)":fz("Old Klang Road"),
       "Segambut(+)":fz("Segambut"),"MasjidJamek(+)":fz("Masjid Jamek"),"KampungBaru(+)":fz("Kampung Baru")}
def hmin(hand,h,R=50.0):
    xs,ys=rio_transform("EPSG:4326",crs,[h.lon],[h.lat]);cf,rf=~transform*(xs[0],ys[0])
    row,col=int(rf),int(cf);rr=int(math.ceil(R/abs(transform.e)));rc=int(math.ceil(R/abs(transform.a)))
    b=hand[max(0,row-rr):row+rr+1,max(0,col-rc):col+col+rc+1-col]
    b=hand[max(0,row-rr):min(hand.shape[0],row+rr+1),max(0,col-rc):min(hand.shape[1],col+rc+1)]
    return float(np.nanmin(b)) if np.isfinite(b).any() else float('nan')
OB=6.06
print(f"land area={land_km2:.0f} km2\n")
print(f"{'thr':>8s} {'chan':>7s} {'finite%':>7s} {'ext<6.06':>9s} {'ext%':>5s}  FedHill OldKR  Segambut MasjidJ KgBaru")
for thr in [2000,10000,50000,200000]:
    mask=derive_drainage_mask_from_accumulation(dem,profile,acc_threshold=thr)
    hand=compute_hand(dem,mask,profile)
    fin=np.isfinite(hand); ext=int(np.nansum(hand<OB)); extkm=ext*900/1e6
    vals={n:hmin(hand,h) for n,h in spots.items()}
    def f(v): return "FLD" if v<OB else "dry"
    print(f"{thr:>8d} {int(mask.sum()):>7d} {100*fin.sum()/land.sum():>6.0f}% {extkm:>7.0f}km2 {100*ext/land.sum():>4.0f}%  "
          f"{vals['FederalHill(dry)']:>5.1f}{f(vals['FederalHill(dry)']):>4s} {f(vals['OldKlangRd(+)']):>4s} {f(vals['Segambut(+)']):>6s} {f(vals['MasjidJamek(+)']):>6s} {f(vals['KampungBaru(+)']):>5s}")
