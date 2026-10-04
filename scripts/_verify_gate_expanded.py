"""Verify the paper's Table 3 gate scores reproduce from the EXPANDED registers."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import pandas as pd
from scripts.hotspot_scoring import Hotspot, hit_vectors, skill_scores, bootstrap_tss_ci
from scripts.combine_hazard_depth import combine_depth_rasters


def load_expanded(slug):
    df = pd.read_csv(f"data/{slug}/manifest/hotspots_expanded.csv",
                     encoding="utf-8", encoding_errors="replace")
    out = []
    for _, r in df.iterrows():
        if pd.isna(r["lon"]) or pd.isna(r["lat"]) or str(r["lon"]).strip() == "":
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


def rasters(d, rp=100, scen="SSP5-8.5", hor=2020):
    found = []
    for hz in ("pluvial", "fluvial", "coastal"):
        p = Path(d) / hz / f"rp_{rp}" / f"{hz}_depth_{scen}_{hor}_rp{rp}.tif"
        if p.exists():
            found.append(p)
    return found


# Reference scores: KL/BKK/JKT = paper Table 3 (pre-2026-07-04 pluvial updates; KL and Jakarta
# were re-baselined by the canal-HAND pluvial — see docs/runs/2026-07-04-*canal-hand-pluvial.md).
# Singapore's register was imported 2026-07-04 from flood-v2.0 (PUB Flood-Prone Areas Nov 2025,
# 38 positive / 20 dry); its reference is the shipped-product baseline, not a paper row.
CITIES = [("kuala_lumpur", "outputs/_fixed_atlas/kuala_lumpur_ssp585_2020_rp100", "0.71/0.92/0.63 post-canal-HAND (paper 0.65/1.00/0.65)"),
          ("bangkok", "outputs/_fixed_atlas/bangkok_ssp585_2020_rp100_polder", "0.34/1.00/0.34"),
          ("jakarta", "outputs/_fixed_atlas/jakarta_ssp585_2020_rp100", "0.85/0.92/0.77 post-canal-HAND (paper 0.76/1.00/0.76)"),
          ("singapore", "outputs/_fixed_atlas/singapore_ssp585_2020_rp100", "0.71/0.90/0.61 baseline (register imported 2026-07-04)")]
print("city           pos/dry  HR   CRR  TSS   [paper HR/CRR/TSS]")
for slug, d, paper in CITIES:
    rs = rasters(d)
    combined = combine_depth_rasters(rs, Path(d) / "_validation" / "combined_rp100_expanded.tif")
    hs = load_expanded(slug)
    fh, dh = hit_vectors(hs, combined, radius_m=50.0, depth_threshold_m=0.10)
    res = skill_scores(fh, dh)
    tss, lo, hi = bootstrap_tss_ci(fh, dh)
    print(f"{slug:14s} {len(fh):2d}/{len(dh):<2d}   {res.hit_rate:.2f} {res.correct_reject_rate:.2f} {tss:.2f}  [{paper}]")
