"""Plan-9 DIAGNOSTIC (not the primary gate): score the 12 systematic model-blind
hard-negative controls (kind=dry_diagnostic) against the combined pluvial∨fluvial
field, and report which the model floods.

These are a documented diagnostic, NOT the scored gate: KL's low-lying areas are so
pervasively flood-prone that even "valley sites >1 km from documented floods" are
contaminated by mislabels (e.g. Semarak and Jinjang are documented flood areas — the
model is CORRECT to flood them). So this set's CRR is a CONTAMINATED LOWER BOUND on
specificity, not a clean over-extent measure. Use it to (a) bound specificity below
and (b) flag any clearly-non-floodplain over-extent for follow-up — never as a gate.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from scripts.hotspot_scoring import sample_score

RP, R, THR = 100, 50.0, 0.10
PLUV = f"outputs/kuala_lumpur_ssp585_2020/pluvial/rp_{RP}/pluvial_depth_SSP5-8.5_2020_rp{RP}.tif"
FL = f"outputs/kuala_lumpur_ssp585_2020/fluvial/rp_{RP}/fluvial_depth_SSP5-8.5_2020_rp{RP}.tif"
# Independently-documented flood history among the diagnostic set (NOT from the model):
KNOWN_FLOOD = {
    "Semarak": "2020 KL flash flood worst-hit (Jln Gurney/San Ah Wing); Sg Bunus retention project",
    "Jinjang": "KL flood-retention ponds (Jinjang/Kepong); 258 mm in 2021-22",
    "Taman OUG": "OUG documented flash-flood history",
    "Bandar Puchong Jaya": "Puchong district flash-flood history",
}


def main():
    reg = pd.read_csv("data/kuala_lumpur/manifest/hotspots.csv")
    diag = reg[reg["kind"] == "dry_diagnostic"]
    print(f"Plan-9 systematic-hard DIAGNOSTIC — {len(diag)} controls @ RP{RP}\n")
    wet = 0
    mislabel_wet = 0
    for _, r in diag.iterrows():
        d = max(sample_score(PLUV, r.lon, r.lat, radius_m=R),
                sample_score(FL, r.lon, r.lat, radius_m=R))
        is_wet = d >= THR
        wet += is_wet
        base = str(r["name"]).replace(" (sys)", "")
        known = next((v for k, v in KNOWN_FLOOD.items() if k in base), None)
        tag = "WET" if is_wet else "dry"
        note = f"  [MISLABEL: {known}]" if (is_wet and known) else ""
        if is_wet and known:
            mislabel_wet += 1
        print(f"  {base[:30]:30s} depth={d:5.2f}m  {tag}{note}")
    n = len(diag)
    print(f"\n  raw CRR (contaminated)         : {n-wet}/{n} = {(n-wet)/n:.2f}")
    print(f"  of the {wet} model-wet, >= {mislabel_wet} are DOCUMENTED flood areas (model correct, mislabel)")
    print(f"  -> contaminated lower bound; clean specificity is the elevated-set gate (CRR 0.86).")


if __name__ == "__main__":
    main()
