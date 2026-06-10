"""Make-or-break test: trunk-only HAND (acc>=100000, excludes CBD khlongs) on the
DEFENDED DEM (King's Dyke burned). Does the dyke break the flow path so the southern
CBD dry controls go dry while the northern 2011 positives flood?"""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio, csv, collections
from pyproj import Transformer
from model.hand_model import compute_hand, derive_drainage_mask_from_accumulation

DEM = "data/bangkok/copernicus_dem_utm47n_subsidence_corrected_defended.tif"
THR = 100000
HEAD = 3.0
OUT = "data/bangkok/hand_trunk_defended_utm47n.tif"

with rasterio.open(DEM) as ds:
    z = ds.read(1).astype(np.float32); prof = ds.profile; nod = ds.nodata; T = ds.transform; crs = ds.crs
zf = np.where(z == nod, np.nan, z) if nod is not None else z
zf = np.where(np.isfinite(zf) & (zf < -3.0), -3.0, zf)   # artifact clamp (same as runner)
src = derive_drainage_mask_from_accumulation(zf.astype(np.float32), prof, acc_threshold=THR)
src = src & np.isfinite(zf)
print(f"trunk channel cells (acc>={THR}): {int(src.sum()):,}")
hand = compute_hand(zf.astype(np.float32), src, prof)
fin = np.isfinite(hand)
print(f"HAND finite cells: {fin.sum():,}  NaN(disconnected): {(~fin).sum():,}")
for h in (2.0, 2.5, 3.0):
    wet = fin & (hand < h)
    print(f"  head={h}: wet={wet.sum()*900/1e6:5.0f} km2 ({100*wet.sum()/np.isfinite(zf).sum():.1f}% of domain)")

# write the trunk-HAND raster for reuse
op = prof.copy(); op.update(dtype="float32", count=1, nodata=np.nan)
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
with rasterio.open(OUT, "w", **op) as d:
    d.write(hand.astype(np.float32), 1)
print(f"wrote {OUT}")

# sample register
rows = list(csv.DictReader(open("data/bangkok/manifest/hotspots.csv", encoding="utf-8")))
tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
def samp(A, x, y, r=2):
    c, rr = ~T * (x, y); c, rr = int(c), int(rr)
    return A[max(0, rr-r):rr+r+1, max(0, c-r):c+r+1]
agg = collections.Counter()
print(f"\n{'name':28s} {'kind':8s} {'lat':>7s} {'HANDmin':>8s} {'wet@3m':>7s}")
for row in rows:
    name = row['name'][:27]; kind = row['kind']
    x, y = tf.transform(float(row['lon']), float(row['lat']))
    h = samp(hand, x, y)
    hmin = np.nanmin(h) if np.isfinite(h).any() else np.nan
    wet = np.isfinite(hmin) and hmin < HEAD
    agg[(kind, "WET" if wet else "dry")] += 1
    print(f"{name:28s} {kind:8s} {float(row['lat']):7.3f} {hmin:8.2f} {'WET' if wet else 'dry':>7s}")
a = dict(agg)
npos = a.get(('positive','WET'),0); ndry_wet = a.get(('dry','WET'),0)
tot_pos = sum(v for (k,_),v in agg.items() if k=='positive'); tot_dry = sum(v for (k,_),v in agg.items() if k=='dry')
print(f"\nsummary: {a}")
print(f"HR={npos}/{tot_pos}={npos/tot_pos:.2f}  CRR={tot_dry-ndry_wet}/{tot_dry}={(tot_dry-ndry_wet)/tot_dry:.2f}")
