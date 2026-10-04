"""Referee stress-test part 2.

A. Elevation-null baseline: best single bare-earth elevation threshold on the
   register (optimistic, in-sample null). If a DEM contour matches the model's
   TSS, the register cannot distinguish the model from trivial topography.
B. Jakarta handfill-stage sensitivity: from the shipped pluvial depth raster,
   how many pluvial hits survive a stage reduction of D (depth>=0.1+D, with
   cap cells given their arithmetic headroom)? Overall gate HR(D) = union with
   fluvial+coastal hits -> the D at which Jakarta's PASS (HR>=0.70) breaks.
"""
import sys, glob
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform as wtransform
from scripts.hotspot_scoring import Hotspot, hit_vectors
from scripts.combine_hazard_depth import combine_depth_rasters

CITIES = {
    "kuala_lumpur": dict(out="outputs/_fixed_atlas/kuala_lumpur_ssp585_2020_rp100",
                         dem="dem/kl/dem_bareearth_kl_eth_present_conditioned.tif", model_tss=0.65),
    "bangkok":      dict(out="outputs/_fixed_atlas/bangkok_ssp585_2020_rp100_polder",
                         dem="dem/bangkok/dem_bareearth_bangkok_present_conditioned.tif", model_tss=0.34),
    "jakarta":      dict(out="outputs/_fixed_atlas/jakarta_ssp585_2020_rp100",
                         dem="dem/jakarta/dem_bareearth_jakarta_present_conditioned.tif", model_tss=0.76),
}


def load_expanded(slug):
    df = pd.read_csv(f"data/{slug}/manifest/hotspots_expanded.csv",
                     encoding="utf-8", encoding_errors="replace")
    out = []
    for _, r in df.iterrows():
        if pd.isna(r["lon"]) or pd.isna(r["lat"]):
            continue
        kind = str(r["kind"]).strip()
        if kind not in {"positive", "dry"}:
            continue
        out.append(Hotspot(label=str(r["name"]).strip(), lon=float(r["lon"]), lat=float(r["lat"]),
                           cls="flood" if kind == "positive" else "dry",
                           documented_depth_m=None, anchor_rp=0, source="", georef_confidence=""))
    return out


print("=== A. elevation-null (best in-sample threshold) vs model TSS ===")
for slug, cfg in CITIES.items():
    hs = load_expanded(slug)
    with rasterio.open(cfg["dem"]) as r:
        xs, ys = wtransform("EPSG:4326", r.crs, [h.lon for h in hs], [h.lat for h in hs])
        z = np.array([v[0] for v in r.sample(zip(xs, ys))], dtype="float64")
    z[z <= -1000] = np.nan
    is_pos = np.array([h.cls == "flood" for h in hs])
    pos, dry = z[is_pos], z[~is_pos]
    best_t, best_tss = None, -9
    for t in np.unique(z[np.isfinite(z)]):
        tss = np.nanmean(pos <= t) + np.nanmean(dry > t) - 1
        if tss > best_tss:
            best_tss, best_t = tss, t
    print(f"  {slug:14s}: null TSS {best_tss:.2f} @ z<={best_t:.1f} m   (model TSS {cfg['model_tss']:.2f})"
          f"   pos max z {np.nanmax(pos):.1f}  dry min z {np.nanmin(dry):.1f}")

print()
print("=== B. Jakarta handfill-stage sensitivity (stage 2.5 m, cap 1.0 m) ===")
slug, cfg = "jakarta", CITIES["jakarta"]
hs = load_expanded(slug)
pos_hs = [h for h in hs if h.cls == "flood"]
# per-point pluvial max depth within the 50 m hit window
pl = glob.glob(f"{cfg['out']}/pluvial/rp_100/pluvial_depth_*_rp100.tif")[0]
with rasterio.open(pl) as r:
    xs, ys = wtransform("EPSG:4326", r.crs, [h.lon for h in pos_hs], [h.lat for h in pos_hs])
    arr = r.read(1)
    px = abs(r.transform.a)
    dmax = []
    for x, y in zip(xs, ys):
        c, rr = ~r.transform * (x, y)
        c, rr = int(c), int(rr)
        w = arr[max(0, rr - 2):rr + 3, max(0, c - 2):c + 3]
        w = w[np.isfinite(w)]
        dmax.append(float(w.max()) if w.size else 0.0)
dmax = np.array(dmax)
# fluvial+coastal hits per point (stage-independent)
fc = [Path(p) for hz in ("fluvial", "coastal")
      for p in glob.glob(f"{cfg['out']}/{hz}/rp_100/{hz}_depth_*_rp100.tif")]
comb = combine_depth_rasters(fc, Path(cfg["out"]) / "_validation" / "combined_stress_fc.tif")
fh, _ = hit_vectors(hs, comb, radius_m=50.0, depth_threshold_m=0.10)
fc_hit = np.array(fh, dtype=bool)  # flood_hits is already positives-only, register order
CAP = 1.0
for D in (0.0, 0.25, 0.5, 0.75, 1.0, 1.5):
    pl_hit = (dmax >= 0.10 + D) | ((dmax >= CAP - 1e-3) & (D <= 2.5 - 0.10 - (2.5 - CAP)))
    hr = np.mean(pl_hit | fc_hit)
    print(f"  stage 2.5 -> {2.5-D:.2f} m (D={D:.2f}):  pluvial hits {int(pl_hit.sum())}/{len(pl_hit)}"
          f"   overall HR {hr:.2f}  {'PASS' if hr >= 0.70 else 'sub-PASS'}")
