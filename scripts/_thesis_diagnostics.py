"""Read-only diagnostics for the thesis question (model vs naive-TWI at present-day).
No model runs, no parameter tuning — just interrogating the ssp585_2020 field."""
import glob, math
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import transform as rio_transform
from scripts.hotspot_scoring import load_hotspots

ROOT = Path(__file__).resolve().parents[1]
hotspots = load_hotspots(ROOT / "data/singapore/flood_obs/hotspots/sg_pluvial_hotspots.csv")
pos = [h for h in hotspots if h.cls == "flood"]
dry = [h for h in hotspots if h.cls == "dry"]
RPS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]
TWI = ROOT / "cache/baselines/naive_twi_sg.tif"


def rpath(scn, rp):
    fs = glob.glob(str(ROOT / f"outputs/singapore_{scn}/pluvial/rp_{rp}/pluvial_depth_*.tif"))
    return fs[0] if fs else None


def smax(path, lon, lat, radius_m=150.0):
    with rasterio.open(path) as ds:
        xs, ys = rio_transform("EPSG:4326", ds.crs, [lon], [lat])
        col_f, row_f = ~ds.transform * (xs[0], ys[0])
        row, col = int(math.floor(row_f)), int(math.floor(col_f))
        rpx = int(math.ceil(radius_m / abs(ds.transform.e)))
        cpx = int(math.ceil(radius_m / abs(ds.transform.a)))
        h, w = ds.height, ds.width
        if not (0 <= row < h and 0 <= col < w):
            return float("nan")
        r0, r1 = max(0, row - rpx), min(h, row + rpx + 1)
        c0, c1 = max(0, col - cpx), min(w, col + cpx + 1)
        b = ds.read(1, window=((r0, r1), (c0, c1))).astype(np.float64)
        nod = ds.nodata
        if nod is not None and not (isinstance(nod, float) and math.isnan(nod)):
            b = np.where(b == nod, np.nan, b)
    return float(np.nanmax(b)) if np.isfinite(b).any() else float("nan")


print("=== 1. Model hit-rate RP-sweep (ssp585_2020, hit = >=0.10 m within 150 m) ===")
for rp in RPS:
    p = rpath("ssp585_2020", rp)
    if not p:
        continue
    hits = sum((smax(p, h.lon, h.lat) or 0) >= 0.10 for h in pos)
    drywet = sum((smax(p, h.lon, h.lat) or 0) >= 0.10 for h in dry)
    hr = hits / len(pos); crr = 1 - drywet / len(dry); tss = hr + crr - 1
    print(f"  RP{rp:>4}: hit {hits:>2}/{len(pos)} = {hr:.2f}   CRR {crr:.2f}   TSS {tss:+.2f}")

print("\n=== 2. Per-hotspot: model depth @RP50 (2020) vs TWI flag ===")
r50 = rpath("ssp585_2020", 50)
n_near = 0
for h in pos:
    md = smax(r50, h.lon, h.lat); tw = smax(str(TWI), h.lon, h.lat)
    mflag = "HIT " if md >= 0.10 else ("near" if md >= 0.05 else "MISS")
    if mflag == "near":
        n_near += 1
    tflag = "HIT" if (tw or 0) >= 0.10 else "miss"
    print(f"  {h.label[:36]:<36} model {md:>5.3f} m [{mflag}]  TWI [{tflag}]  georef={h.georef_confidence}")
print(f"  -> model near-misses (0.05-0.10 m): {n_near}")

print("\n=== 3. ROC-style: model hit-rate vs correct-reject as depth threshold varies (RP50, 2020) ===")
print("     (lower threshold = more sensitive; the model's full operating curve)")
md_pos = [smax(r50, h.lon, h.lat) for h in pos]
md_dry = [smax(r50, h.lon, h.lat) for h in dry]
for thr in [0.02, 0.05, 0.075, 0.10, 0.15, 0.25]:
    hr = sum((d or 0) >= thr for d in md_pos) / len(pos)
    crr = 1 - sum((d or 0) >= thr for d in md_dry) / len(dry)
    print(f"  thr {thr:.3f} m: hit {hr:.2f}  CRR {crr:.2f}  TSS {hr+crr-1:+.2f}")
print("  TWI baseline (fixed, RP-independent): hit 0.80  CRR 0.67  TSS +0.47")
