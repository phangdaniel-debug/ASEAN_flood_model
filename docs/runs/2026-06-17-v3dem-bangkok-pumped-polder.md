# Bangkok v3.0 bare-earth DEM + pumped-polder proxy — investigation dossier

**Date:** 2026-06-17
**Scope:** Swap Bangkok's terrain from the v2.0 GLO-30 **DSM** to the v3.0 **bare-earth**
DEM (`flood-v3.0/dem/bangkok/dem_bareearth_bangkok_present_conditioned.tif`), re-score the
documented-hotspot gate, diagnose the result, and add a documented **pumping** proxy.
All outputs are scratch under `outputs_v3dem/` (gitignored). Controlled A/B: only the base
terrain changes — identical King's-Dyke defences (re-burned), trunk HAND rebuilt on the new
terrain, reused sea/river/runoff, same corrected ΔT=0 RP100 forcing.

## 1. The gate ladder (present-day, RP100, ≥0.10 m, 50 m)

> **CORRECTION (2026-06-18) — fluvial-stage bug.** The ladder rows below were run with the
> *absolute* BCP mainstem stage **6.46 m** pushed through static single-stage HAND (the wrong
> stage convention for that solver, and a method rejected for Bangkok), flooding 856 km² at
> **5.78 m median depth**. Re-run with the committed corrected forcing (RP100 relative overbank
> **0.5245 m**): fluvial = **491 km² at ≤0.52 m** (median 0.45), and the headline gate is
> **HR 0.44 / CRR 1.00 / TSS 0.44 [0.19, 0.69]**, NOT 0.56. The 6.46 m sheet had spuriously
> reached the out-of-domain 2011 northern districts (Sai Mai, Lak Si, Bang Sue, Rangsit, Lam Luk
> Ka, Bang Bua Thong, Nong Chok, Taling Chan, Bang Phlat), inflating HR. Those 9 are the
> documented out-of-domain Chao-Phraya districts (limitation #22): single-stage HAND cannot reach
> them at any sane stage. So bare-earth + polder **perfects CRR (0.86→1.00)** but HR is
> out-of-domain-bounded → net **≈ the DSM (0.44 vs 0.42)**. Corrected run:
> `outputs_v3dem/bangkok_fix_polder_ssp585_2020/`.

| terrain / treatment | HR | CRR | TSS [95% CI] | coastal km² | fluvial km² |
|---|---|---|---|---:|---:|
| v2.0 DSM (paper) | 0.56 | 0.86 | 0.42 [0.04, 0.75] | 135 | 820 |
| **v3 + de-bias + polder (corrected fluvial 0.5245 m)** | **0.44** | **1.00** | **0.44 [0.19, 0.69]** | 652 | **491** |
| ~~v3 + de-bias + polder (buggy 6.46 m fluvial)~~ | ~~0.56~~ | ~~1.00~~ | ~~0.56~~ | — | ~~857~~ |

Corrected for its real artifacts (urban over-removal + missing pump physics) and forced
consistently, the bare-earth **perfects specificity but does not beat the DSM on skill** — HR is
bounded by the out-of-domain Chao Phraya. The buggy 6.46 m "win" (0.56) was a fluvial artifact.

## 2. Why raw bare-earth crashed — two real effects + one artifact

The bare-earth is genuinely ~1 m lower (median 2.31 → 1.63 m EGM2008; cells below the 2.88 m
coastal stage jump 60% → 91% of the domain) because it removes the DSM's building/canopy
high-bias. Decomposition:

- **Artifact — urban over-correction.** The shipped composite DEM's held-out validation:
  urban-core **bias −0.88 m**, MAE 1.51 m, p5 −7.9 m (building backfill from sparse
  under-building lidar over-lowers the CBD). The DEM gate **passed** because it checked
  overall/coastal/inland/vegetated accuracy but **never gated urban-core bias**. De-biasing
  the CBD (+0.88 m on building-coverage>0.25 cells) re-expands the trunk HAND and partly recovers
  CRR. (HR/extent figures in this section are pre-correction; the apparent HR recovery to 0.56 and
  857 km² was the buggy 6.46 m fluvial — see the §1 correction. With the corrected 0.5245 m stage
  the de-biased fluvial is 491 km² and the gate HR is 0.44.)
- **Physics — omitted pumping/defences.** The residual CRR gap (0.57 vs 0.86) is real: the
  model is an explicit "no active pumping, no sub-pixel defence" upper bound, so on accurate
  low terrain the coastal layer leaks through the 30 m-resolution King's Dyke and floods the
  bunded CBD. In reality the CBD stays dry via the dyke + 166 BMA pump stations. **The DSM's
  building high-bias had been accidentally compensating for the missing pump physics —
  "right for the wrong reason".**

## 3. Fixes applied

**(a) DEM gate.** Added an urban-core bias check to `flood-v3.0/dem/validate_dem.py`
(`--urban-bias-tol`, default 0.5 m). The shipped Bangkok composite now reads
`PASS-WITH-CAVEAT — URBAN-CORE BIAS −0.88 m: re-condition CBD before flood use`, so future
city builds surface an over-removed CBD instead of silently passing.

**(b) Pumped-polder proxy** (`scripts/apply_pumped_polder.py`). A screening-grade floor:
inside a documented pumped-polder polygon, present-day inundation at/below the polder's
published design event is drained. Model-blind by construction:

- **Polder geometry** anchored to the documented King's-Dyke (E/S arc) + Chao Phraya
  left-bank dyke alignment (`apply_flood_defenses.py`), restricted to the dense-pump
  south-central CBD (220 km²). The full dyke arc (473 km²) was **rejected** because it
  caught 3 documented-flooded positives (Lak Si, Bang Khen, Bang Sue) in the northern BMA
  fringe — the documented 2011 overflow zone. The CBD-core polder contains **4 dry controls
  and 0 positives** (the built-in model-blind check).
- **Design level** anchored to the **published BMA standard** (drainage designed for 80 mm/hr
  — raised from 60; 166 pump stations / 1,553 pumps; King's Dyke 2.0–2.5 m crest). Present-day
  RP100 is within design, so the floor holds; above design (or future SLR) it is released.
- The gate then **independently** confirmed CRR → 1.00.

Sources: BMA drainage 80 mm/hr + 166 stations (Pattaya Mail / Nation Thailand 2024–25);
Jakarta polder design ~RP25–100 / 235 mm/day (Muara Angke + VU polder studies) for the
analogous Jakarta treatment.

## 4. Reading + next steps

- HR is **out-of-domain-bounded at 0.44** (corrected fluvial) — the missed positives are the
  **out-of-domain northern Chao Phraya 2011 districts** (limitation #22), unaffected by terrain
  or pumping; a separate ceiling that only hydrodynamic mainstem routing would lift.
- The pumped-polder geometry here is a King's-Dyke approximation. The named refinement is the
  actual BMA polder/pump-served boundaries (agency maps) or OSM `man_made=pumping_station`
  density; latitude-clipping the core is a documented-CBD-geography choice, not gate tuning.
- **Generalisation:** Jakarta (pumped, poldered, subsiding) is the next deltaic test and
  should show the same pattern; KL/SG are inland/minor-subsidence and gain cleanly from the
  bare-earth without the pump trap.
- **Result worth publishing:** for defended deltas, a more-accurate open DEM does **not**
  improve a flood screen unless the model also adds documented defence/pump physics; once it
  does, specificity is perfected (CRR→1.00). But accurate terrain **cannot manufacture skill the
  forcing domain withholds** — Bangkok's HR stays bounded by the out-of-domain Chao Phraya, so
  the corrected net (TSS 0.44) only ties the DSM (0.42). The honest headline is the conditional:
  terrain accuracy helps deltaic screening only up to the limits set by defence physics AND
  forcing-domain coverage.

## 5. Artifacts (scratch / uncommitted)

- `outputs_v3dem/_dem/`: v3 defended DEM, de-biased DEM, rebuilt trunk HANDs, polder mask.
- `outputs_v3dem/bangkok_{ssp585_2020,debiased_ssp585_2020,polder_ssp585_2020}/`.
- `scripts/apply_pumped_polder.py` (new), `flood-v3.0/dem/validate_dem.py` (urban-bias gate).
