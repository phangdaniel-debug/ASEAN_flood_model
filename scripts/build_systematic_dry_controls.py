"""Systematic model-blind hard-negative sampler for KL specificity validation (Plan 9).

Selects 'dry' control points by TERRAIN + flood-RECORD criteria only (never the
model's flood output): urban-core land cells that are ABOVE the RP100 fluvial stage
(main-stem HAND 6-20 m -> not trivially-flooded floodplain, but lower than the 30m+
hilltop controls = HARD), not on a channel, and >1 km from EVERY documented flood
location (17 positives + 18 extra flood-prone areas). Tests whether the model
spuriously floods terrain-plausible NON-floodplain sites (residual pluvial over-
extent / HAND artifact). Mislabel risk (undocumented flood) biases CRR DOWN
(conservative). See docs/superpowers/runs/2026-06-06-kl-dry-control-research.md.
"""
import sys, json, time, math, urllib.parse, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio
from rasterio.warp import transform as T
import pandas as pd

HAND_LO, HAND_HI = 6.5, 20.0     # above RP100 fluvial stage (6.06); below hilltop controls
EXCL_KM = 1.0                    # min distance to any documented flood location
MIN_SEP_KM = 2.5                # min separation between selected controls
N_TARGET = 12
# Urban-core bbox (lon_min, lat_min, lon_max, lat_max) — where the model is active
BBOX = (101.62, 3.05, 101.75, 3.22)

hand_ds = rasterio.open("data/kuala_lumpur/hand_mainstem_utm47n.tif")
dem_ds  = rasterio.open("data/kuala_lumpur/copernicus_dem_utm47n.tif")
drn_ds  = rasterio.open("data/kuala_lumpur/drainage_waterways_utm47n.tif")
hand = hand_ds.read(1).astype(float); 
if hand_ds.nodata is not None: hand = np.where(hand==hand_ds.nodata, np.nan, hand)
dem = dem_ds.read(1).astype(float)
if dem_ds.nodata is not None: dem = np.where(dem==dem_ds.nodata, np.nan, dem)
drn = drn_ds.read(1)
crs = hand_ds.crs; tr = hand_ds.transform; H, W = hand_ds.shape

# Exclusion coords (lon,lat): 17 positives + 18 geocoded extras
reg = pd.read_csv("data/kuala_lumpur/manifest/hotspots.csv")
pos = reg[reg.kind=="positive"][["lon","lat"]].dropna().values.tolist()
extra = [(d["lon"],d["lat"]) for d in json.loads(Path("data/kuala_lumpur/_flood_exclusions.json").read_text())]
excl_ll = pos + extra
# project exclusions to raster CRS (metres)
ex_x, ex_y = T("EPSG:4326", crs, [c[0] for c in excl_ll], [c[1] for c in excl_ll])
excl_xy = np.column_stack([ex_x, ex_y])
print(f"Exclusion set: {len(pos)} positives + {len(extra)} extra = {len(excl_xy)} documented flood points")

# bbox -> raster window (row/col)
bx0,by0 = T("EPSG:4326", crs, [BBOX[0]],[BBOX[3]]); bx1,by1 = T("EPSG:4326", crs, [BBOX[2]],[BBOX[1]])
c0,r0 = ~tr*(bx0[0],by0[0]); c1,r1 = ~tr*(bx1[0],by1[0])
r0,r1=int(max(0,min(r0,r1))),int(min(H,max(r0,r1))); c0,c1=int(max(0,min(c0,c1))),int(min(W,max(c0,c1)))

# candidate mask in bbox
cand = []
res = abs(tr.a)
excl_m = EXCL_KM*1000; sep_m = MIN_SEP_KM*1000
for rr in range(r0, r1, 3):       # stride 3 cells (~90 m) for speed
    for cc in range(c0, c1, 3):
        h = hand[rr,cc]
        if not (HAND_LO <= h <= HAND_HI): continue
        if not np.isfinite(dem[rr,cc]): continue
        if drn[rr,cc] > 0: continue                 # not on a channel
        x,y = tr*(cc+0.5, rr+0.5)
        d = np.hypot(excl_xy[:,0]-x, excl_xy[:,1]-y).min()
        if d < excl_m: continue                     # >1 km from any documented flood
        cand.append((x,y,float(h),float(dem[rr,cc]),d))
print(f"Candidate cells (HAND {HAND_LO}-{HAND_HI} m, not channel, >{EXCL_KM} km from flood, in urban bbox): {len(cand)}")

# greedy spatial thinning: sort by distance-to-flood DESC (safest first), enforce min separation
cand.sort(key=lambda t: -t[4])
sel=[]
for x,y,h,d_dem,dflood in cand:
    if all(math.hypot(x-sx, y-sy) >= sep_m for sx,sy,_,_,_ in sel):
        sel.append((x,y,h,d_dem,dflood))
    if len(sel)>=N_TARGET: break
print(f"Selected {len(sel)} hard-negative controls (min separation {MIN_SEP_KM} km)\n")

# reverse-geocode names
def rgeo(lon,lat):
    p={"lat":lat,"lon":lon,"format":"json","zoom":16}
    url="https://nominatim.openstreetmap.org/reverse?"+urllib.parse.urlencode(p)
    req=urllib.request.Request(url,headers={"User-Agent":"flood-v2-validation/1.0"})
    try:
        r=json.load(urllib.request.urlopen(req,timeout=25)); a=r.get("address",{})
        for k in ("suburb","neighbourhood","quarter","residential","city_district","village","town"):
            if a.get(k): return a[k]
        return (r.get("display_name","") or "unknown").split(",")[0]
    except Exception: return "unknown"

rows=[]
for x,y,h,d_dem,dflood in sel:
    lon,lat = T(crs,"EPSG:4326",[x],[y]); lon,lat=lon[0],lat[0]
    name=rgeo(lon,lat); time.sleep(1.1)
    rows.append({"name":name,"lon":round(lon,5),"lat":round(lat,5),"hand_m":round(h,1),
                 "dem_m":round(d_dem,1),"km_to_flood":round(dflood/1000,2)})
    print(f"  {name[:30]:30s} ({lat:.4f},{lon:.4f}) HAND={h:.1f}m DEM={d_dem:.1f}m  {dflood/1000:.2f}km from flood")
Path("data/kuala_lumpur/_systematic_dry_controls.json").write_text(json.dumps(rows,indent=1))
print(f"\nWrote {len(rows)} -> data/kuala_lumpur/_systematic_dry_controls.json")
