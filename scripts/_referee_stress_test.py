"""Adversarial referee stress-test of the validation gate.

1. Exact statistics: Fisher exact p (2x2), Clopper-Pearson 95% CIs on HR and CRR
   separately (the bootstrap can flatter a degenerate all-correct control stratum).
2. Hazard-layer sensitivity: gate re-scored with (a) all hazards, (b) pluvial
   EXCLUDED, (c) pluvial ONLY -- quantifies how much of each verdict rides on the
   handfill/fill-spill layer.
3. Control difficulty: bare-earth elevation of dry controls vs positives -- are the
   controls trivially high ground?
"""
import sys, glob
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import numpy as np
import pandas as pd
from scipy import stats
import rasterio
from rasterio.warp import transform as wtransform
from scripts.hotspot_scoring import Hotspot, hit_vectors, skill_scores, bootstrap_tss_ci
from scripts.combine_hazard_depth import combine_depth_rasters

CITIES = {
    "kuala_lumpur": dict(out="outputs/_fixed_atlas/kuala_lumpur_ssp585_2020_rp100",
                         dem="dem/kl/dem_bareearth_kl_eth_present_conditioned.tif"),
    "bangkok":      dict(out="outputs/_fixed_atlas/bangkok_ssp585_2020_rp100_polder",
                         dem="dem/bangkok/dem_bareearth_bangkok_present_conditioned.tif"),
    "jakarta":      dict(out="outputs/_fixed_atlas/jakarta_ssp585_2020_rp100",
                         dem="dem/jakarta/dem_bareearth_jakarta_present_conditioned.tif"),
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
                           documented_depth_m=None, anchor_rp=0,
                           source=str(r.get("source", "")).strip(),
                           georef_confidence=str(r.get("confidence", "")).strip()))
    return out


def rasters_for(out_dir, include):
    found = []
    for hz in include:
        g = glob.glob(f"{out_dir}/{hz}/rp_100/{hz}_depth_*_rp100.tif")
        if g:
            found.append(Path(g[0]))
    return found


def cp_ci(x, n):
    lo = stats.beta.ppf(0.025, x, n - x + 1) if x > 0 else 0.0
    hi = stats.beta.ppf(0.975, x + 1, n - x) if x < n else 1.0
    return lo, hi


def score(slug, cfg, include, tag):
    rs = rasters_for(cfg["out"], include)
    if not rs:
        print(f"  {tag:12s}: no rasters"); return None
    comb = combine_depth_rasters(rs, Path(cfg["out"]) / "_validation" / f"combined_stress_{tag}.tif")
    hs = load_expanded(slug)
    fh, dh = hit_vectors(hs, comb, radius_m=50.0, depth_threshold_m=0.10)
    res = skill_scores(fh, dh)
    tss, lo, hi = bootstrap_tss_ci(fh, dh)
    hits, n_pos = sum(fh), len(fh)
    fa, n_dry = sum(dh), len(dh)   # false alarms = wet controls
    # Fisher exact on [[hits, misses],[false alarms, correct rejects]]
    _, p = stats.fisher_exact([[hits, n_pos - hits], [fa, n_dry - fa]], alternative="greater")
    hr_lo, hr_hi = cp_ci(hits, n_pos)
    crr_lo, crr_hi = cp_ci(n_dry - fa, n_dry)
    print(f"  {tag:12s}: HR {res.hit_rate:.2f} [{hr_lo:.2f},{hr_hi:.2f}]  "
          f"CRR {res.correct_reject_rate:.2f} [{crr_lo:.2f},{crr_hi:.2f}]  "
          f"TSS {tss:.2f} [{lo:.2f},{hi:.2f}]  Fisher p={p:.4f}")
    return dict(hr=res.hit_rate, crr=res.correct_reject_rate, tss=tss, p=p)


def control_difficulty(slug, cfg):
    hs = load_expanded(slug)
    with rasterio.open(cfg["dem"]) as r:
        lons = [h.lon for h in hs]; lats = [h.lat for h in hs]
        xs, ys = wtransform("EPSG:4326", r.crs, lons, lats)
        vals = [v[0] for v in r.sample(zip(xs, ys))]
    z = np.array(vals, dtype="float64"); z[z <= -1000] = np.nan
    pos = np.array([zz for h, zz in zip(hs, z) if h.cls == "flood"])
    dry = np.array([zz for h, zz in zip(hs, z) if h.cls == "dry"])
    print(f"  elevation: positives median {np.nanmedian(pos):6.1f} m (p90 {np.nanpercentile(pos,90):5.1f})"
          f"   dry controls median {np.nanmedian(dry):6.1f} m (min {np.nanmin(dry):5.1f})")
    print(f"  low dry controls (<5 m): {int(np.nansum(dry < 5))}/{len(dry)}   (<15 m): {int(np.nansum(dry < 15))}/{len(dry)}")


for slug, cfg in CITIES.items():
    print(f"===== {slug} =====")
    score(slug, cfg, ("pluvial", "fluvial", "coastal"), "ALL")
    score(slug, cfg, ("fluvial", "coastal"), "NO-PLUVIAL")
    score(slug, cfg, ("pluvial",), "PLUVIAL-ONLY")
    control_difficulty(slug, cfg)
    print()
