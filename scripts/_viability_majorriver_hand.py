"""Viability test: accumulation-derived (major-river-only) HAND.
Does it raise Federal Hill's HAND (stop spurious flood) while keeping the
true floodplain spots low-HAND (preserve Old Klang Road + main-stem positives)?"""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio, math
from rasterio.warp import transform as rio_transform
from model.hand_model import compute_hand, derive_drainage_mask_from_accumulation
from scripts.city_manifest import load_hotspots_from_manifest

with rasterio.open("data/kuala_lumpur/copernicus_dem_utm47n.tif") as ds:
    dem=ds.read(1).astype(np.float32); profile=ds.profile; transform=ds.transform; crs=ds.crs
    nod=ds.nodata
if nod is not None: dem=np.where(dem==nod, np.nan, dem)

hs={h.label:h for h in load_hotspots_from_manifest("kuala_lumpur")}
def fuzzy(name):
    for k,v in hs.items():
        if name in k: return v
    return None
spots={
 "FederalHill(dry)":fuzzy("Bukit Persekutuan"),
 "OldKlangRd(+)":fuzzy("Old Klang Road"),
 "MasjidJamek(+)":fuzzy("Masjid Jamek"),
 "JlnTunRazak(+)":fuzzy("Jalan Tun Razak"),
 "Kampung Baru(+)":fuzzy("Kampung Baru"),
 "Segambut(+)":fuzzy("Segambut"),
}
def hand_at(hand, lon, lat, R=50.0):
    xs,ys=rio_transform("EPSG:4326",crs,[lon],[lat]); col_f,row_f=~transform*(xs[0],ys[0])
    row,col=int(row_f),int(col_f); rr=int(math.ceil(R/abs(transform.e))); rc=int(math.ceil(R/abs(transform.a)))
    r0,r1=max(0,row-rr),min(dem.shape[0],row+rr+1); c0,c1=max(0,col-rc),min(dem.shape[1],col+rc+1)
    b=hand[r0:r1,c0:c1]; fin=np.isfinite(b)
    return float(np.nanmin(b)) if fin.any() else float('nan')

OVERBANK=6.06  # corrected RP100 stage
for thr in [2000, 10000, 50000]:
    mask=derive_drainage_mask_from_accumulation(dem, profile, acc_threshold=thr)
    hand=compute_hand(dem, mask, profile)
    print(f"\n=== acc_threshold={thr} ({thr*900/1e6:.2f} km2)  drainage cells={int(mask.sum())} ===")
    for name,h in spots.items():
        hm=hand_at(hand,h.lon,h.lat)
        floods = "FLOODS" if hm < OVERBANK else "dry"
        print(f"  {name:18s} HAND_min(50m)={hm:6.2f}  @overbank6.06 -> {floods}")
