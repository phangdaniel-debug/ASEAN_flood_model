"""Per-spot fluvial-bias diagnostic: before (backup) vs after (corrected) fluvial."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.city_manifest import load_hotspots_from_manifest
from scripts.hotspot_scoring import sample_score

RP = 100
PLUV = f"outputs/kuala_lumpur_ssp585_2020/pluvial/rp_{RP}/pluvial_depth_SSP5-8.5_2020_rp{RP}.tif"
FL_AFTER = f"outputs/kl_fluvbias_corrected/fluvial/rp_{RP}/fluvial_depth_SSP5-8.5_2020_rp{RP}.tif"
FL_BEFORE = f"outputs/_ref_fluvbias_pre/fluvial/rp_{RP}/fluvial_depth_SSP5-8.5_2020_rp{RP}.tif"
R = 50.0; THR = 0.10

hs = load_hotspots_from_manifest("kuala_lumpur")
print(f"{'label':28s} {'cls':5s} {'pluv':>6s} {'flBEF':>6s} {'flAFT':>6s} {'cmbBEF':>7s} {'cmbAFT':>7s}  {'BEF':>4s} {'AFT':>4s}  chg")
for h in sorted(hs, key=lambda x: x.cls):
    p = sample_score(PLUV, h.lon, h.lat, radius_m=R)
    fb = sample_score(FL_BEFORE, h.lon, h.lat, radius_m=R)
    fa = sample_score(FL_AFTER, h.lon, h.lat, radius_m=R)
    cb = max(p, fb); ca = max(p, fa)
    hit_b = "WET" if cb >= THR else "dry"
    hit_a = "WET" if ca >= THR else "dry"
    chg = ""
    if hit_b != hit_a:
        chg = "<<< FLIP " + ("gained" if hit_a=="WET" else "lost")
    print(f"{h.label[:28]:28s} {h.cls:5s} {p:6.2f} {fb:6.2f} {fa:6.2f} {cb:7.2f} {ca:7.2f}  {hit_b:>4s} {hit_a:>4s}  {chg}")
