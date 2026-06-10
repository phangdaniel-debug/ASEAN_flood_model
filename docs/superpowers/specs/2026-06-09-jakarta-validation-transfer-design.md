# Jakarta J1 — Foundation + First Validation (Design)

**Date:** 2026-06-09
**Status:** Approved (brainstorming) → ready for implementation plan
**Project line:** ASEAN flood-v2.0 multi-city transfer. KL (production-complete) → Bangkok
(B1+B2 complete, honest structural ceiling) → **Jakarta (this spec, sub-project J1)**.

---

## 1. Goal & guiding principle

Transfer the validated KL/Bangkok template to **Jakarta** and produce the **first honest
validation verdict** on the **existing** Jakarta model — **no model changes**. Build the
four-manifest contract + a model-blind hotspot register, generate the present-day baseline,
run the gate (hotspot-primary + elevated JKT2020 extent-CSI support), and **diagnose**.
Model fixes (coastal solver, multi-river fluvial, …) are deliberately deferred to
evidence-driven follow-on plans (J2+), exactly as Bangkok B1 → B2.

**Cardinal discipline (unchanged across the project line):**
- **Done is a number, not a feeling.** Every parameter anchored to a documented fact; the
  gate is a consistency check, never a tuning target.
- **Homogeneous & transferable.** Reuse the generalized engine; keep KL + Bangkok
  regression-locked.
- **Model-blind register**; **flooded dry controls STAY** (cardinal rule, SG #15 / KL #21).

This sub-project is the **Bangkok-B1 analog**: validation-first reveals the exact, documented
fixes Jakarta needs rather than pre-supposing them.

## 2. Why Jakarta is different (the three contrasts that shape the design)

1. **Coastal is a first-class, dominant hazard for the first time.** North Jakarta is
   subsiding polders *below* sea level (zone-based subsidence correction already applied:
   −1.44 m north / −0.72 m central / −0.24 m south; `…_subsidence_corrected.tif`), with
   annual *rob* tidal flooding and the **lowest coastal bathtub bias of any city (1.7×)**
   because the unprotected-polder bathtub assumption is near-physical there. **But** the
   coastal forcing is explicitly **qualitative** — no UHSLC gauge in Jakarta Bay; Muis et al.
   (2016) screening values, ±0.2–0.3 m at RP100. Any rob-hotspot result carries this
   documented confidence caveat.
2. **Extent-CSI becomes viable for the first time.** Jakarta has a real Sentinel-1 SAR flood
   extent — `data/jakarta/flood_obs/JKT2020` (EOS-ARIA-SG 2020-01-02, Indonesia Floods
   v1.5). KL was SAR-blind (#17, ~345 px); Bangkok's THA2011 was MODIS (WARN). A prior
   bathtub run scored CSI 0.10 / H 0.34 / FAR 0.87 (over-prediction); the inertial solver
   should reduce that bias.
3. **Fluvial is less out-of-domain than Bangkok, but multi-river-limited.** GloFAS is
   anchored at **Ciliwung-Depok** (−6.35 N, 106.84 E — a sub-basin point near the southern
   domain edge, like KL's Shah Alam), so the Bangkok out-of-domain ceiling (#22) is *less*
   severe. But it captures only the Ciliwung; Jakarta's other ~12 rivers (Pesanggrahan,
   Angke, Sunter, …) are single-reach-unrepresented.

Domain: 50 × 61 km ≈ 3,053 km² (DKI core), EPSG:32748, 30 m.

## 3. Components

Almost everything is reuse; the only **new** code is the register builder + the Jakarta
manifests + the CSI-support wiring into the dossier.

| Component | Status | Notes |
|---|---|---|
| `scripts/validate_hotspots.py --city jakarta` | **reuse** | already generalized (unions existing pluvial∨fluvial∨coastal); KL+Bangkok regression-locked |
| `scripts/city_manifest.py` (`validate_manifest`, `load_hotspots_from_manifest`) | **reuse** | scores positive + dry only |
| `scripts/hotspot_scoring.py`, `scripts/combine_hazard_depth.py` | **reuse** | HR/CRR/TSS + bootstrap CI; depth-max union |
| `scripts/build_jakarta_hotspot_register.py` | **new** | model-blind seed list → geocode (Nominatim) → DEM-verify → write `data/jakarta/manifest/hotspots.csv`; mirrors `build_bangkok_hotspot_register.py` |
| `data/jakarta/manifest/{forcing_anchors,gates,observed_events,hotspots}.csv` | **new** | the four-manifest contract for Jakarta |
| `scripts/validate_historical_events.py` (JKT2020 CSI) | **reuse** | already configured for JKT2020; elevate from diagnostic → reported support gate |
| `tests/test_jakarta_register.py` | **new** | pure-logic guards (shape/provenance) + `validate_manifest('jakarta')==[]` |

## 4. The register (model-blind)

**Positives — recurrent, multi-event, mechanism-spanning** (documented across the 2007 /
2013 / 2020 floods; sourced from BPBD DKI, academic + news records, *before* reading the
model):
- **Ciliwung-corridor fluvial:** Kampung Melayu, Bukit Duri, Kampung Pulo, Cawang, Rawajati.
- **Monsoon pluvial:** chronically-ponding kelurahan away from the main rivers.
- **North Jakarta rob / coastal-subsidence:** Penjaringan, Pluit, Muara Baru, Kalibaru,
  Cilincing.

**Dry controls:** Jakarta's genuinely-**elevated south** (real elevation gradient toward
Depok — so elevated negatives are *geographically appropriate* here, unlike KL's all-hill
confound #21) **+ documented-dry central levee areas** (e.g. Menteng on the historical
natural levee). Geocoded + DEM-verified per #6b; **never hand-pinned by eye**. The JKT2020
SAR gives an independent, negative-set-free specificity check (FAR) alongside CRR.

**Geocoding/terrain discipline:** any point that fails a DEM elevation sanity check or
geocodes outside the 3,053 km² domain is dropped + documented (cf. Bangkok's Nava Nakorn).
Targets: ≥ 15 positives, ≥ 7 dry controls.

## 5. The gate

**Primary (numeric):** hotspot **HR / CRR / TSS** with bootstrap CI, at **RP100**, threshold
0.10 m, radius 50 m (KL/Bangkok precedent; radius anchored to Nominatim precision, not the
gate). Floors in `data/jakarta/manifest/gates.csv`: HR ≥ 0.70, CRR ≥ 0.70 (Singapore
methodology precedent). Per-hazard breakdown (pluvial / fluvial / coastal) reported.

**Elevated support (reported gate):** **JKT2020 extent-CSI** via
`validate_historical_events.py --event JKT2020` — H / FAR / CSI vs the EOS-ARIA Sentinel-1
polygon, with reported WARN (CSI < 0.30) / FAIL (CSI < 0.15) thresholds. Reported alongside
the hotspot gate (not subordinate to it), because Jakarta is the first city where the SAR
reference is trustworthy.

**RP rationale:** RP100 keeps cross-city homogeneity; the Jan-2020 event was ~RP50–100
locally. RP100-only is sufficient for the verdict; the full 9-RP baseline is deferred (the
inertial coastal solver is ~50 min/RP — same perf note as Bangkok; `--raingrid-workers`
parallelization carries over for the pluvial path).

## 6. Baseline generation

Run the **existing committed Jakarta config** present-day (SSP5-8.5 / 2020), **no changes**:
subsidence-corrected DEM, the config's existing pluvial + coastal (+ Ciliwung HAND fluvial)
settings, reusing the committed `data/jakarta/hazard_levels_ssp585_2020.csv` and the AR6
`--offline` cache (`data/_ar6_lsl_cache.json`). The exact `run_multihazard` flag set
(DEM variant, sea-mask, coastal seeds/MSL offset, inertial vs bathtub, `--fluvial-bankfull-rp
0` per #20) is pinned at plan-time from `run_city_pipeline.py`'s Jakarta block, mirroring the
Bangkok B1 approach. Output → `outputs/jakarta_ssp585_2020/{pluvial,fluvial,coastal}/rp_100/`.

## 7. Anticipated diagnoses (to CONFIRM with evidence, not pre-fix)

These are hypotheses the gate will test; each, if confirmed, becomes a documented J2+ fix:
- **(a) Bathtub coastal over-prediction** — prior JKT2020 FAR 0.87. If the existing config
  uses bathtub coastal, expect over-extent in the north → evidence for the **inertial coastal
  solver** (already proven for Bangkok) in J2.
- **(b) Single-reach Ciliwung fluvial** — the other ~12 rivers unrepresented → HR misses in
  their corridors → evidence for additional GloFAS reaches / a multi-river HAND in J2.
- **(c) Coastal forcing is qualitative** — Muis screening, no gauge; any rob result is
  reported with this documented low-confidence caveat (a sourcing limit, not a model defect).

## 8. Testing

- `tests/test_jakarta_register.py`: `SEED` list shape (≥15 positives, ≥7 dry, every entry
  carries provenance, kinds ∈ {positive, dry}) + `validate_manifest('jakarta') == []` when
  the geocoded `hotspots.csv` is present (skipped otherwise).
- **Regression lock:** the full suite (currently 235 passed / 1 skipped) stays green; KL +
  Bangkok gates unchanged (the validator generalization is already in place — Jakarta only
  *adds* a city slug + data).

## 9. Deliverable & exit

A **Jakarta J1 validation dossier** (`docs/superpowers/runs/2026-06-09-jakarta-validation-dossier.md`):
method, the numeric hotspot gate (HR/CRR/TSS + CI), the JKT2020 CSI support gate, per-hazard
+ per-spot diagnosis, the honest verdict (expected: a cleanly-diagnosed first gate, like
Bangkok B1), and the documented, evidence-driven J2+ fix list. Update `limitations_register.md`
+ memory. Finish the branch.

## 10. Out of scope (explicit)

Model changes (coastal solver swap, multi-river fluvial, discharge re-anchoring); the full
9-RP baseline; future-scenario products (SSP futures); any gate-tuning. All are J2+
follow-ons gated on the J1 evidence.
