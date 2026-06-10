"""Propagate the #16 scenario-pluvial fix to the delta cities (Bangkok / Jakarta).

The committed ssp245_2050 / ssp585_2050 / ssp245_2100 pluvial rows for these configs carry
the pre-IDF-recalibration baseline (~0.4-0.8 m RP100, ~5x too high, with the
ssp245_2100>ssp585_2100 inversion). KL was fixed (_regen_kl_scenario_pluvial.py) but the
delta cities were not.

Generalization of the KL fix: instead of KL's hardcoded cc_rate=0.07 (which does NOT reproduce
these cities' gentler climate response), interpolate each config's OWN documented anchor pair —
present-day baseline (delta_T=0) and its clean ssp585_2100 (delta_T=4.0) — linearly at each
scenario's delta_T:

    new_pluv[RP] = base[RP] * (1 + (ref[RP]/base[RP] - 1) * (delta_T / delta_T_ref))

This is anchor-exact (reproduces base at dt=0 and ref at dt=dt_ref), per-RP, and leaves the
clean ssp585_2100 (used by the paper's Table II) UNTOUCHED. Fluvial/coastal rows untouched.
The ref/base ratio was verified constant across RP (= linear-CC), so the linear form is exact.
"""
import re, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ["bangkok", "bangkok_chao_phraya", "jakarta"]
TARGETS = ["ssp245_2050", "ssp585_2050", "ssp245_2100"]
CAP = 0.50  # the guard's plausibility cap — sanity assert, NOT a tuning knob


def pluv(path):
    df = pd.read_csv(path)
    m = df.hazard_type == "pluvial"
    return df, m, df[m].set_index("return_period")["water_level_m"]


def delta_T(note):
    x = re.search(r"delta_T=([0-9.]+)", str(note))
    return float(x.group(1)) if x else None


for cfg in CONFIGS:
    cdir = ROOT / "data" / cfg
    _, _, base = pluv(cdir / "hazard_levels_ssp585_2020.csv")
    ref_df, ref_m, ref = pluv(cdir / "hazard_levels_ssp585_2100.csv")
    dt_ref = delta_T(ref_df[ref_m].iloc[0]["scaling_method"])
    # additive linear anchor interpolation (handles base=0 at low RP where pluvial excess is 0);
    # identical to the multiplicative form where base>0 since ref/base is constant across RP.
    print(f"\n{cfg}: dt_ref={dt_ref}  (base RP100={base[100]:.4f} -> clean585_2100 {ref[100]:.4f})")

    for tag in TARGETS:
        path = cdir / f"hazard_levels_{tag}.csv"
        if not path.exists():
            print(f"  {tag}: (absent, skip)"); continue
        df, pmask, _ = pluv(path)
        dt = delta_T(df[pmask].iloc[0]["scaling_method"])
        before = float(df.loc[pmask].set_index("return_period").loc[100, "water_level_m"])
        for i in df[pmask].index:
            rp = int(df.at[i, "return_period"])
            new = round(float(base[rp]) + (float(ref[rp]) - float(base[rp])) * (dt / dt_ref), 6)
            assert 0.0 <= new <= CAP + 1e-9, f"{cfg}/{tag} RP{rp}: {new} out of [0,{CAP}]"
            df.at[i, "water_level_m"] = new
        # monotone-in-RP check on the regenerated pluvial column
        reg = df[pmask].sort_values("return_period")["water_level_m"].values
        assert all(reg[k] <= reg[k+1] + 1e-9 for k in range(len(reg)-1)), f"{cfg}/{tag} non-monotone"
        if "source_note" in df.columns:
            df.loc[pmask, "source_note"] = df.loc[pmask, "source_note"].astype(str) + (
                f"; PLUVIAL REGEN (#16 delta-city fix): additive anchor-interp of baseline"
                f" ssp585_2020 -> clean ssp585_2100 at dt={dt}/dt_ref={dt_ref}")
        df.to_csv(path, index=False)
        after = float(df.loc[pmask].set_index("return_period").loc[100, "water_level_m"])
        print(f"  {tag} (dt={dt}): RP100 {before:.4f} -> {after:.4f}")
print("\nDONE. Verify with: python scripts/validate_scenario_forcing_consistency.py")
