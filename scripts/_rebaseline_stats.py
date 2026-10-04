"""Post-retrofit (2026-07-04 canal-HAND) referee statistics for the paper re-baseline:
bootstrap TSS CI, one-sided Fisher exact p, and the no-pluvial decomposition, per city."""
import sys, glob
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import numpy as np
import pandas as pd
from scipy import stats
from scripts.hotspot_scoring import Hotspot, hit_vectors, skill_scores, bootstrap_tss_ci
from scripts.combine_hazard_depth import combine_depth_rasters

CITIES = {
    "kuala_lumpur": "outputs/_fixed_atlas/kuala_lumpur_ssp585_2020_rp100",
    "bangkok":      "outputs/_fixed_atlas/bangkok_ssp585_2020_rp100_polder",
    "jakarta":      "outputs/_fixed_atlas/jakarta_ssp585_2020_rp100",
    "singapore":    "outputs/_fixed_atlas/singapore_ssp585_2020_rp100",
}


def load(slug):
    df = pd.read_csv(f"data/{slug}/manifest/hotspots_expanded.csv",
                     encoding="utf-8", encoding_errors="replace")
    out = []
    for _, r in df.iterrows():
        if pd.isna(r["lon"]) or pd.isna(r["lat"]):
            continue
        k = str(r["kind"]).strip()
        if k not in {"positive", "dry"}:
            continue
        out.append(Hotspot(label=str(r["name"]).strip(), lon=float(r["lon"]), lat=float(r["lat"]),
                           cls="flood" if k == "positive" else "dry",
                           documented_depth_m=None, anchor_rp=0, source="", georef_confidence=""))
    return out


def rasters(d, include):
    return [Path(g[0]) for hz in include
            if (g := glob.glob(f"{d}/{hz}/rp_100/{hz}_depth_*_rp100.tif"))]


for slug, d in CITIES.items():
    hs = load(slug)
    print(f"===== {slug} =====")
    for tag, inc in (("ALL", ("pluvial", "fluvial", "coastal")), ("NO-PLUVIAL", ("fluvial", "coastal"))):
        comb = combine_depth_rasters(rasters(d, inc), Path(d) / "_validation" / f"rebase_{tag}.tif")
        fh, dh = hit_vectors(hs, comb, radius_m=50.0, depth_threshold_m=0.10)
        res = skill_scores(fh, dh)
        tss, lo, hi = bootstrap_tss_ci(fh, dh)
        hits, npos, fa, ndry = sum(fh), len(fh), sum(dh), len(dh)
        _, p = stats.fisher_exact([[hits, npos - hits], [fa, ndry - fa]], alternative="greater")
        print(f"  {tag:11s}: {hits}/{npos} pos, {ndry-fa}/{ndry} dry  "
              f"HR {res.hit_rate:.2f} CRR {res.correct_reject_rate:.2f} "
              f"TSS {tss:.2f} [{lo:.2f},{hi:.2f}]  Fisher p={p:.2e}")
