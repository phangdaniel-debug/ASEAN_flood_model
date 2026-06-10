"""Fix limitation #16: regenerate ONLY the pluvial rows of the 3 stale KL scenario
CSVs (ssp245_2050, ssp585_2050, ssp245_2100) that carry a ~8x-too-high pre-IDF-
recalibration pluvial baseline (cap violations + the ssp245_2100>ssp585_2100 inversion).

Correct method (matches the clean ssp585_2100 / present-day pair): scale the clean
present-day pluvial baseline by the documented GEV-CC factor. For pluvial the factor
is the LINEAR Clausius-Clapeyron rescale alpha = (1 + cc_rate * delta_T) — exactly
`build_hazard_levels._gev_cc_factor(..., hydraulic_exponent=1.0)`, since scaling both
GEV mu and sigma by alpha rescales every return level by alpha. Fluvial + coastal rows
are already correct and consistent -> left UNTOUCHED.
"""
import re, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_hazard_levels import _gev_cc_factor

BASE = "data/kuala_lumpur/hazard_levels_ssp585_2020.csv"   # delta_T=0 clean baseline
TARGETS = ["ssp245_2050", "ssp585_2050", "ssp245_2100"]
# Plausibility cap (the guard's threshold) — sanity assert only, NOT a tuning knob.
CAP = 0.50

def parse_dt_cc(note_method):
    dt = float(re.search(r"delta_T=([0-9.]+)", note_method).group(1))
    cc = float(re.search(r"cc_rate=([0-9.]+)", note_method).group(1))
    return dt, cc

base = pd.read_csv(BASE)
base_pluv = base[base.hazard_type == "pluvial"].set_index("return_period")["water_level_m"]

# Sanity: reproduce the CLEAN ssp585_2100 from the baseline (delta_T=4.0) before touching anything.
ref = pd.read_csv("data/kuala_lumpur/hazard_levels_ssp585_2100.csv")
ref_pluv = ref[ref.hazard_type == "pluvial"].set_index("return_period")["water_level_m"]
for rp in base_pluv.index:
    f = _gev_cc_factor(0.2, 50.0, 20.0, float(rp), delta_T=4.0, cc_rate=0.07, hydraulic_exponent=1.0)
    got = base_pluv[rp] * f
    assert abs(got - ref_pluv[rp]) < 1e-4, f"sanity fail RP{rp}: {got:.5f} vs clean {ref_pluv[rp]:.5f}"
print("sanity OK: baseline x GEV-CC(delta_T=4.0) reproduces the clean ssp585_2100 pluvial")

for tag in TARGETS:
    path = f"data/kuala_lumpur/hazard_levels_{tag}.csv"
    df = pd.read_csv(path)
    pmask = df.hazard_type == "pluvial"
    dt, cc = parse_dt_cc(str(df[pmask].iloc[0].get("scaling_method", "")))
    for i in df[pmask].index:
        rp = float(df.at[i, "return_period"])
        f = _gev_cc_factor(0.2, 50.0, 20.0, rp, delta_T=dt, cc_rate=cc, hydraulic_exponent=1.0)
        new = round(float(base_pluv[int(rp)]) * f, 6)
        assert new <= CAP + 1e-9, f"{tag} RP{rp}: {new} still over cap — baseline wrong?"
        df.at[i, "water_level_m"] = new
    if "source_note" in df.columns:
        df.loc[pmask, "source_note"] = df.loc[pmask, "source_note"].astype(str) + \
            f"; PLUVIAL REGEN (#16 fix): baseline ssp585_2020 x GEV-CC(delta_T={dt},cc_rate={cc},exp=1.0)=x{1+cc*dt:.3f}"
    df.to_csv(path, index=False)
    print(f"{tag}: pluvial regenerated (delta_T={dt}, x{1+cc*dt:.3f}); RP100={float(base_pluv[100])*(1+cc*dt):.4f}")
