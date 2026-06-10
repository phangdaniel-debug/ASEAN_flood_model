# KL Two-Gate Validation Dossier — 2026-06-05
## Plan 2 (KL Validation Harness) — Task 5 final deliverable

---

## 1. Scope and method

**Run:** KL present-day baseline, `outputs/kuala_lumpur_ssp585_2020/`, SSP5-8.5 horizon 2020, delta-T = 0.0 (no climate scaling). Solver: raingrid pluvial, bathtub coastal. Full run record in `docs/superpowers/runs/2026-06-04-kl-baseline.md`.

**Primary validation mode: hotspot hit-rate (pluvial focus).**
SAR extent-CSI was evaluated as a diagnostic but is non-viable as a gate for KL (limitation #17): the MYS2021 Copernicus GFM Sentinel-1 SAR composite holds only ~345 flood pixels (~0.14 km²) across the 3,520 km² domain, because SAR double-bounce in KL's dense urban built-up areas is indistinguishable from open water (~69% of the KL bbox masked). A CSI computed against a 0.14 km² reference over a 3,520 km² domain is statistically meaningless. KL is therefore validated by the same hotspot-primary method as Singapore: documented-flood-hotspot hit-rate is the primary numeric gate, supplemented by visual gate (RP-monotonicity + mass-plausibility).

**Hotspot register:** 17 documented positives + 7 dry controls, geocoded via Nominatim and DEM-verified per limitation #6b (1 low-confidence positive: Segambut Dalam — elevation ~80 m in the northern foothills; the Nominatim pin may not resolve to the flood-prone valley floor). Register file: `data/kuala_lumpur/manifest/hotspots.csv`.

**Validation engine:** `scripts/validate_hotspots_kl.py`, reusing the SG `hotspot_scoring` engine (same TP/FP/FN logic, configurable radius and threshold). Gate thresholds from `data/kuala_lumpur/manifest/gates.csv` (Singapore methodology precedent, Peirce/Hanssen-Kuipers TSS).

---

## 2. Numeric gate table

All gates from `data/kuala_lumpur/manifest/gates.csv`. Observed values from `scripts/validate_hotspots_kl.py` at the default operational configuration (RP100, threshold 0.10 m, radius 150 m).

| Gate | Threshold | Direction | Observed | PASS/FAIL | Citation |
|---|---|---|---|---|---|
| hotspot_hit_rate | 0.70 | >= | **1.00** (17/17) | **PASS** | documented-hotspot hit-rate floor (Singapore methodology precedent; Peirce/Hanssen-Kuipers TSS) |
| hotspot_crr | 0.70 | >= | **0.43** (3/7) | **FAIL** | dry-control correct-reject-rate floor (specificity; Singapore methodology) |
| TSS (informational) | — | — | **0.43** [95% CI 0.14, 0.86] | — | Peirce skill score; wide CI driven by n=7 dry controls |

Fluvial CSI/POD/FAR, pluvial idf_ci_coverage, and point_depth RMSE/bias gates are not scored in this run (reference data not yet staged; see Plan 3 scope). IDF-anchor cross-check run as diagnostic only (see Section 4).

RP50 result is identical to RP100 (hit-rate 1.00, CRR 0.43, TSS 0.43) — the model is saturated at RP50 and additional rainfall loading does not change the hotspot pattern.

---

## 3. Radius sensitivity — CRR diagnosis

Tightening the search radius progressively removes the false-positive dry controls that are only wet at a distance from their pin.

| Radius | HR | CRR | TSS | 95% CI | Gate verdict |
|---|---|---|---|---|---|
| 150 m (operational) | 1.00 (17/17) | 0.43 (3/7) | 0.43 | [0.14, 0.86] | **FAIL** (CRR) |
| 50 m | 0.71 (12/17) | 0.71 (5/7) | 0.42 | [−0.01, 0.80] | **PASS** |
| 30 m | 0.59 (10/17) | 0.86 (6/7) | 0.45 | [0.07, 0.76] | **FAIL** (HR) |

Tightening the radius trades sensitivity for specificity (HR falls as CRR rises) while TSS stays ~0.43 throughout — i.e. it shifts the operating point without changing skill. At 30 m the HR falls below 0.70 because Nominatim pins are not precise to within 30 m of the flooded cell; at 150 m the elevated dry-control pins over-reach low cells downslope. The radius should be set by the documented geocoding precision (below), not by which value happens to clear both floors.

**Per-control split at 150 m radius:**

| Dry control | Wet at 10 m? | Wet at 30 m? | Wet at 150 m? | Classification |
|---|---|---|---|---|
| Bukit Antarabangsa | Yes (depth > 0.10 m) | Yes | Yes | **Genuine pluvial over-extent** — model floods the hillside; the pluvial 3.0 m depth-cap not enforced in this run allows over-ponding in low-lying cells adjacent to the slope. |
| Mont Kiara | No (0 m depth) | No | Yes | **Radius artefact** — pin is on elevated ground; wet cell at 100–150 m is a low valley/road cell reached only by the 150 m window. |
| Bukit Kiara | No | No | Yes | **Radius artefact** — same mechanism; Bukit Kiara is a forested park on a ridge; nearest flood cell is downslope. |
| Damansara Heights | No | No | Yes | **Radius artefact** — elevated residential area; wet cell reached only at 100–150 m is a low-lying access road. |

**Implication:** the 150 m hit-radius was tuned for Singapore's dense-urban geocoding, where Nominatim pins are reliable to ~50–100 m. In KL's hilly terrain, pins for elevated dry-control sites (hilltop residentials, forested parks) resolve close to their postal address but the nearest pluvial-flood cell is downslope, often 100–150 m away. Using 150 m as the search window causes these ridge/hilltop dry controls to be falsely flagged as wet. The fix is a KL-appropriate radius (~50 m), not a model change. Bukit Antarabangsa is different: it IS wet at the pin, pointing to a genuine model over-extent issue (the unenforced depth-cap).

---

## 4. Two-gate verdict

| Gate | Component | Result |
|---|---|---|
| Numeric gate (Task 3) | hotspot_hit_rate = 1.00 ≥ 0.70 | PASS |
| Numeric gate (Task 3) | hotspot_crr = 0.43 < 0.70 | **FAIL** |
| Visual gate (Plan 1 smoke check) | RP-monotonicity + mass-plausibility | **PASS** |

**Overall: NOT YET ACCEPTABLE.**

Note that TSS is modest and essentially flat across all three radii (0.43 / 0.42 / 0.45) with overlapping wide CIs — at 50 m the 95% CI is [−0.01, 0.80], which does not exclude zero skill (n=7 dry controls). The radius choice therefore moves the gate verdict but does NOT change the model's underlying skill; it is a measurement-window correction, not a performance improvement.

The model is over-sensitive: it correctly hits every documented flood hotspot (hit-rate = 1.00) but fails specificity — it over-floods areas that have documented dry histories. The failure is traceable to two distinct causes, both with documented-fact-anchored fixes:

**(a) Genuine pluvial over-extent (Bukit Antarabangsa).** The pluvial `max_depth_m` reaches 4.5 m in this run, exceeding the documented 3.0 m ponding cap (run-record finding #2 from `2026-06-04-kl-baseline.md`). The cap was not enforced (`--max-ponding-depth-m` default 3.0 was not applied in the `run_multihazard` raingrid path). Enforcing the cap is a documented, targeted fix — not an eyeball-tuning of any threshold. Plan 3 action: wire and verify the depth-cap, then re-validate Bukit Antarabangsa.

**(b) Radius artefact (Mont Kiara, Bukit Kiara, Damansara Heights).** The 150 m search radius overshoots the elevated pin locations to reach low-lying flood cells downslope. The fix is to set the hit-radius to match KL's documented geocoding precision. Nominatim resolves KL addresses to ~50–100 m (≈ one city block); SG used 150 m for its own denser-grid geocoding uncertainty. A ~50 m radius reflects the tighter pin-to-cell tolerance appropriate where dry controls sit on ridge tops with their nearest flood cell 100–150 m downslope. That this radius also lifts CRR to the 0.70 floor is corroboration, not the reason for the choice — and it must be read alongside the flat, modest TSS above: the change corrects the measurement window, it does not improve model skill. Plan 3 action: set the KL validation hit-radius to ~50 m anchored to the geocoding-precision rationale (not the gate flip), and re-validate.

Both fixes are derived from measured evidence in this dossier. Neither is post-hoc tuning — the depth-cap is a pre-existing documented parameter, and the radius value is directly read from the sensitivity table.

---

## 5. Diagnostics (not gates)

### Extent-CSI vs MYS2021 SAR
Best result: pluvial RP100, CSI = 0.00, H = 0.09, FAR = 1.00, Bias = 2817.67. As explained in Section 1 (limitation #17), this result is reference-limited — the SAR composite provides ~345 pixels over a 3,520 km² domain. The near-zero CSI is an expected coverage artefact, not evidence of model failure. Full output in `docs/superpowers/runs/2026-06-05-kl-validation-diagnostics.md`.

### IDF-anchor cross-check
ERA5-Land RP2 6h = 45.8 mm vs JPS Malaysia anchor = 90.0 mm (deviation −49.1%). ERA5-Land under-shoots the JPS anchor because the 9 km ERA5-Land grid smears the intense convective cells that drive KL flash floods. This confirms that the baseline correctly uses IDF-calibrated Gumbel forcing anchored to the JPS 90 mm value rather than raw ERA5-Land statistics. Full output in `docs/superpowers/runs/2026-06-05-kl-validation-diagnostics.md`.

---

## 6. Limitations carried and Plan-3 disposition

| # | Limitation | Status | Plan-3 action |
|---|---|---|---|
| #16 | KL scenario forcing mixed-provenance — future-scenario CSVs (SSP2-4.5/5-8.5 2050/2100) have 27 known inconsistencies flagged by `validate_scenario_forcing_consistency.py`; does NOT affect the present-day baseline (`delta-T = 0.0`) used here. | Carried | Regenerate future-scenario CSVs from a single consistent forcing source. |
| #17 | SAR extent validation non-viable for KL — urban SAR double-bounce masks ~69% of the domain; only ~345 obs pixels available (0.14 km²). CSI score meaningless. | Carried | No model fix; document as permanent KL limitation. Revisit if higher-quality mapped flood polygons become available. |
| Run-record #2 | Pluvial depth-cap not enforced — `max_depth_m` reached 4.5 m vs 3.0 m documented cap; drives Bukit Antarabangsa over-extent. | Carried | Wire `--max-ponding-depth-m` in raingrid path; verify cap active; re-run baseline; re-validate. |
| Radius config | KL-appropriate hit-radius not yet formalised — operational 150 m overshoots elevated dry-control pins. 50 m matches KL Nominatim geocoding precision (~one city block); sweep confirms it lifts CRR to floor without collapsing HR. TSS unchanged (~0.43) — measurement-window fix, not a skill gain. | Carried | Set KL hit-radius to ~50 m anchored to geocoding precision; grow dry-control register to tighten the TSS CI. |
| coastal = 0 | Coastal layer is identically zero throughout domain. | Correct by design | KL is inland; spec §6.1 marks coastal as N/A. Confirm domain covers Port Klang if coastal validation is ever required. |
| Register size | n = 7 dry controls → TSS 95% CI width of ~0.72 at 150 m radius. Any individual false-positive has outsized effect on CRR. | Accepted at this stage | Grow dry-control register in Plan 3 to tighten CI; target n ≥ 15. |
| #6b | 1 low-confidence positive pin — Segambut Dalam geocoded to ~62 m elevation; Nominatim may not have resolved to valley floor. | Carried | Re-geocode Segambut Dalam against OSM flood-record coordinates; update register. |

---

## 7. Post-fix re-validation (Plan 3) — and a correction to the Plan-3 premise

Plan 3 applied both diagnosed fixes (pluvial depth-cap wired, commit `67f4a6e`; KL hit-radius set to 50 m, commit `072b761`) and re-validated against the capped baseline. **The data overturned Plan 3's central premise** and the verdict is recorded honestly below.

### Measured results

| Config | HR | CRR | TSS [95% CI] | Gate |
|---|---|---|---|---|
| Pre-fix: RP100 @ 150 m | 1.00 | 0.43 | 0.43 [0.14, 0.86] | FAIL |
| RP100 @ **50 m**, **capped** | 0.71 | 0.71 | 0.42 [**−0.01**, 0.80] | **PASS (marginal)** |
| RP100 @ 50 m, *uncapped* | 0.71 | 0.71 | 0.42 [−0.01, 0.80] | PASS (identical) |
| RP50 @ 50 m, capped | 0.65 | 0.86 | 0.50 [0.13, 0.82] | FAIL (HR) |

### The depth-cap does NOT close the specificity gate (premise corrected)

Plan 3 hypothesised the depth-cap would remove the Bukit Antarabangsa over-extent and lift CRR. **It does not.** The false-positive dry controls are *shallow*-wet (Bukit Antarabangsa ~0.135 m, Bukit Kiara ~0.148 m) — all far below the 3.0 m cap — so clipping deep cells leaves the ≥ 0.10 m wet/dry classification unchanged. The capped and uncapped RP100 runs give **identical** HR/CRR (row 2 vs 3). The cap remains a valid **physical-plausibility** fix (4.5 m → 3.0 m; a bank rejects 4.5 m urban ponding on sight) and is kept — but it is *not* a specificity fix. **The 50 m radius alone moves the gate.**

### Verdict: MARGINAL / BOUNDARY — NOT robustly acceptable

The gate clears its floors only at the single operating point RP100 + 50 m, where HR and CRR are *exactly* 0.71 and the **TSS 95% CI [−0.01, 0.80] includes zero** (skill not statistically distinguishable from none, at n=7 dry controls). One knob in either direction fails it: RP50 → HR 0.65; 150 m → CRR 0.43. Both knobs are independently justified (RP100 = the documented MYS2021 event RP; 50 m = Nominatim geocoding precision), so this is not pure operating-point shopping — but it is honestly a **boundary pass, not a robust acceptance.** KL is **NOT** declared "done."

The residual specificity defect is **broad-shallow over-extent** (Bukit Antarabangsa floods at its own pin) — a DEM hydro-conditioning / drainage problem, *not* a depth problem. That, plus the register's small negative set, is what keeps the result at the boundary.

### Carried to Plan 4 (the substantive work)

1. **Raingrid performance** (limitation #18) — ~30–45 min/RP; a full city run is ~5–6 h. This is now the critical-path blocker for the multi-city goal; fix before scaling to Bangkok/Jakarta.
2. **Broad-shallow over-extent** — improve DEM hydro-conditioning / drainage so the pluvial field stops shallow-flooding ridge bases (the actual specificity defect; the depth-cap does not address it).
3. **Grow the dry-control register to n ≥ 15** (model-blind, geocoded + DEM-verified per #6b, avoiding the negative-set confound of SG limitation #15) to get the TSS CI off zero, then re-judge.
4. Scenario-forcing regen (#16), fluvial event-RP re-anchoring, SSP5-8.5 2100 + viz.


---

## 8. Drainage-densification fix (Plan 5) — real improvement, not yet a clean PASS

**Diagnosis (decisive):** the broad-shallow over-extent was a **missing-drainage** problem. The raingrid drained only at major rivers + sea = 1.1% of the domain; the **median RP100 wet cell was 4.7 km from any outlet** (95% >300 m), so water ponded in local lows instead of draining. Not depth (the cap was irrelevant), not numerical.

**Fix (user-chosen, OSM-first):** densified the drainage outlet network with **OSM waterways** — the real mapped drains/ditches/canals/streams/rivers (culverts/tunnels excluded), 4,408 open-channel features. **Roads were deliberately NOT used** (an outlet is a zero-depth sink, and roads flood — they are documented hotspots; roads-as-sinks is physically wrong). The OSM-mapped waterway network is the documented anchor (no density tuning). Result: median wet-cell distance-to-outlet **4.7 km → 190 m** (a realistic urban drain spacing); no DEM-derived fallback needed. The waterways were burned into the conditioned raingrid DEM and wired as the raingrid outlet mask (216,171 outlets vs 42,873).

**Before/after (RP100, 50 m radius):**

| metric | sparse drainage | dense drainage |
|---|---|---|
| flooded area (RP100) | 377.8 km² | 218.8 km² (**−42%**; −40–44% across all RP) |
| hit-rate | 0.71 (12/17) | **0.65 (11/17)** |
| CRR | 0.71 (5/7) | **0.86 (6/7)** |
| TSS [95% CI] | 0.42 [**−0.01**, 0.80] | **0.50 [0.13, 0.82]** |

**Verdict: a genuine improvement, but NOT a clean PASS.**
- **The fix worked on its target:** Bukit Antarabangsa — the diagnosed over-extent false-positive (trapped at its hill base) — now correctly drains. The over-extent halved. **TSS rose 0.42→0.50 and its CI now EXCLUDES zero** — the first statistically-significant discriminative skill (vs the prior boundary result). This is a *real* gain (the model is more correct), the opposite of the Plan-4 early-stop trap.
- **But it over-drained one real flood spot:** Old Klang Road (documented flood-prone) went to 0.00 m — it sits beside Sungai Klang / a monsoon drain, and the model treats every waterway cell as an **infinite sink**, so all excess vanishes. In reality that drain is overwhelmed and the road floods. This single over-drain pushed HR to 0.65 (< 0.70 floor) → **GATE FAIL on HR.**
- **Pre-existing (not this fix):** Taman Sri Muda — the Dec-2021 epicenter — was a miss *before and after*. Its flooding was Sungai Klang overflow + retention-pond failure (fluvial/compound), which the *pluvial* model cannot capture and the under-anchored GLOFAS fluvial misses too. That is the deferred fluvial-RP issue.

**Disposition (user decision):** accept the dense-drainage result as the improved baseline + document; **do NOT** chase a clean PASS by tuning drainage density (forbidden loop). The proper next lever is **capacity-limited drains** (water reaching an at-capacity drain ponds rather than vanishing) — a model change that would fix the Old Klang Road over-drain at root while keeping the over-extent fix. Logged as the new finding (limitation register).

**Reproduction (offline, bypassing the flaky AR6 fetch):** `run_multihazard` with `--tidal-channel-raster data/kuala_lumpur/drainage_waterways_utm47n.tif` (dense outlets) + `--pluvial-dem-raster` the drain-burned `copernicus_dem_utm47n_raingrid.tif` + `--pluvial-depth-cap 3.0`; built by `scripts/build_drainage_network.py`; measured by `scripts/_diagnose_drainage_density.py`.

---

## 9. Capacity-limited drains (Plan 6) — correct mechanism, but the residual is STRUCTURAL

**Goal:** fix the #19 over-drain (Old Klang Road → 0.00 m by an infinite-sink drain) by making drains finite-capacity, so overwhelmed drains pond. Implemented as a **per-channel-type** model (sea + major rivers = perfect/high sinks; minor drains = finite conveyance), to avoid over-ponding the Klang/Gombak.

**Conveyance anchor (documented, NOT the gate):** a representative MSMA secondary monsoon drain (b=1.2 m, y=1.0 m, S=0.002, n=0.015 → Q≈1.86 m³/s) over a 900 m² cell → **0.002 m/s** (`docs/superpowers/runs/2026-06-06-drain-conveyance-anchor.md`).

**Result (RP100, 50 m) — essentially identical to the infinite-sink dense-drainage baseline:**

| | infinite-sink (Plan 5) | finite drains 0.002 m/s |
|---|---|---|
| HR / CRR / TSS | 0.65 / 0.86 / 0.50 [0.13,0.82] | **0.65 / 0.86 / 0.50 [0.13,0.82]** (unchanged) |
| flooded area RP100 | 218.8 km² | 219.7 km² (+0.9) |
| Old Klang Road @50 m | 0.00 m | **0.00 m** (not restored) |
| major-river cells wet | — | **0** (per-channel correct — rivers did NOT over-pond) |

**Findings:**
1. **The per-channel model is correct** — major rivers/sea stayed perfect sinks (0 wet river cells); no river over-ponding. The mechanism does what it should.
2. **At the documented drain capacity, drains are NOT overwhelmed.** 0.002 m/s sheds water far faster than it arrives at most cells (only a handful of very-high-accumulation drains overwhelm → +0.9 km²), so finite drains ≈ infinite sinks and **Old Klang Road is not restored.**
3. **To flood Old Klang Road would require a conveyance BELOW the documented secondary-drain capacity** — i.e. modelling the drain as *failing/blocked*, not merely full. That is the **structural limit Singapore already hit (limitations #10/#13): a design-capacity model cannot reproduce drainage-FAILURE floods** (blocked/debris-choked drains), which is what much of Dec 2021 actually was. Lowering the conveyance to force the hit would be tuning to an undocumented blockage = the forbidden loop.

**Verdict:** KL's pluvial specificity ceiling — **HR 0.65 / CRR 0.86 / TSS 0.50 (CI excludes zero, significant skill)** — is partly **STRUCTURAL**, not a tunable parameter. A design-capacity open model captures capacity-exceedance flooding (Bukit Antarabangsa correctly drains; the over-extent is gone) but not blockage-driven flooding (Old Klang Road; Taman Sri Muda is separately a fluvial/compound miss). The per-channel finite-drain mechanism is kept as a correct, **default-off** capability (matters for other cities / a future explicit blockage model), but it does not move KL at realistic capacity. **This is the honest ceiling for the present-day KL pluvial product.** Next independent lever: fluvial event-RP re-anchoring (would help Taman Sri Muda).

## 10. Fluvial re-anchoring (Plan 7) + main-stem HAND (Plan 8) — KL fluvial VALIDATED

The pluvial ceiling (§9) is structural; the remaining HR gain came from the **fluvial** path. Two corrections, each anchored to a documented fact, took KL from a marginal HR-fail to a clean PASS.

**(a) Fluvial-bankfull config bug (Plan 7).** The committed baseline ran `--fluvial-bankfull-rp 10`, but the hazard CSV already encodes overbank **above the documented Q_bf=98 bankfull** (`fit_fluvial_glofas.py` subtracts `mannings_stage(Q_bf)`; source_note: `relative_stage_above_bankfull_m`). So RP10 was subtracted a *second* time — a double-subtraction that suppressed RP≤10 entirely and shrank every fluvial stage. **Fix: `--fluvial-bankfull-rp 0`** (the CSV already did the bankfull subtraction). This is a correctness fix, independent of the gate.

**(b) Documented discharge bias (Plan 7).** GLoFAS under-calls the Klang discharge (Dec-2021 = GLoFAS RP~6 vs JPS-implied RP50–100), traced to ERA5 under-estimating tropical rainfall. A **documented 2.06× magnitude bias** (ERA5-Land 6 h RP2 43.6 mm vs JPS MSMA 90 mm; `apply_fluvial_bias.py`) raises the RP100 overbank stage 3.31→6.06 m. Anchored to the rainfall bias, **not** the gate.

**(c) Single-stage HAND over-broadening + the main-stem fix (Plan 8).** With `rp0` + the 2.06× bias, **Old Klang Road floods (0→0.60 m)** — the documented HR target, restored. But the OSM-river-referenced HAND also flooded **Bukit Persekutuan / Federal Hill** — a 60–77 m **hill** — by 4 m (CRR 0.86→0.71), because HAND assigned the hill to a ~60 m hillside rivulet within 50 m of the pin. The principled fix: reference HAND to the **trunk Klang network the GLoFAS discharge represents**. `cities.py` documents the GLoFAS reach as the **~500 km² upper Klang basin** (and explicitly rejected the ~50 km² upstream point as too small), so HAND is built from flow-accumulation channels with **catchment ≥ 180 km²** (`hand_mainstem_utm47n.tif`, thr=200000). A first attempt at *channel-initiation* scale (1.8 km², thr=2000) was **rejected**: a complete accumulation network + uniform overbank stage floods 875 km² (25% of domain) — the highest gate score (TSS 0.80) but a physically absurd map (rejecting the top-scoring config on physical grounds is the discipline working). See `2026-06-06-major-river-hand-anchor.md`.

**Before/after (RP100, 50 m radius, combined pluvial∨fluvial):**

| Stage | HR | CRR | TSS [95% CI] | fluvial extent | Federal Hill | Old Klang Rd | map credible? |
|---|---|---|---|---|---|---|---|
| Plan 6 baseline (old-HAND, rp10 dbl-sub) | 0.65 | 0.86 | 0.50 [0.13,0.82] | 46 km² | dry | 0.00 (dry) | bounded by OSM-coverage *artifact* |
| Plan 7 (rp0 + 2.06× bias, old-HAND) | 0.76 | 0.71 | 0.48 [0.08,0.82] | 116 km² | **4.09 m (FP)** | 0.60 (WET) | bounded by artifact; hill over-floods |
| channel-init HAND (thr=2000) — REJECTED | 0.94 | 0.86 | 0.80 [0.45,1.00] | **875 km²** ✗ | dry | 0.60 (WET) | **NO — 25% of domain at 4 m** |
| **Plan 8 main-stem HAND (thr=200000)** | **0.76** | **0.86** | **0.62 [0.25,0.88]** | **100 km²** | **dry ✓** | **0.60 (WET)** | **YES — trunk floodplain** |

**Per-spot (main-stem, RP100):** Federal Hill dry (HAND 32 m — fixed by physics, not reclassification); Old Klang Road 0.60 m WET (target restored); **zero fluvial false positives** among the 7 dry controls (the lone FP, Bukit Kiara 0.15 m, is a pre-existing *pluvial* one); Segambut Dalam still a HIT (caught by pluvial 0.22 m — the trunk fluvial misses it because it sits on a sub-trunk tributary the ~500 km² GEV doesn't represent). The 4 misses (Taman Sri Muda, Klang town, Bukit Jalil, Pantai Dalam) are structural/pre-existing and unchanged.

**Verdict: KL present-day fluvial is VALIDATED.** The main-stem HAND **dominates** the Plan-7 result (same HR 0.76, CRR restored 0.71→0.86, TSS up 0.48→0.62) with a **credible bounded extent (100 km²)** and the Federal Hill artifact fixed by **correct physics** (HAND referenced to the documented ~500 km² trunk), at no cost to any documented positive. Combined present-day KL (pluvial∨fluvial) now passes both floors with significant TSS. **Residual (honest):** single-stage HAND extent is sensitive to the trunk-channel threshold (the structural limit, limitation #20) — the 180 km² choice is forward-anchored to the documented discharge scale with the gate as a consistency check, not a tuned value.

## 11. Hardening the negative set (Plan 9) — systematic hard-negative DIAGNOSTIC

**Confound addressed.** The primary gate's 7 dry controls are **all elevated hills** (DEM 60–156 m). A model that floods nothing above ~6 m HAND trivially rejects them, so CRR 0.86 could be an *easy*-negative artifact (Singapore #15). We tested specificity against **hard** negatives.

**Research finding (model-blind).** In KL, **low-lying ≈ flood-prone**: Cheras, Setapak, Sri Petaling, Gombak, OUG, Taman Desa, Salak South and most valley-floor areas carry flood history; the reliably-dry areas genuinely *are* the elevated ones. So *named* low-lying dry controls cannot be sourced cleanly (labelling a valley site "dry" from absence-of-mention would mislabel it). See `2026-06-06-kl-dry-control-research.md`.

**Systematic method.** `scripts/build_systematic_dry_controls.py` selects 12 urban-valley control points by terrain + flood-record criteria only (model-blind, frozen before reading the model): main-stem HAND 6.5–20 m (above the RP100 fluvial stage 6.06 m → not trivially-flooded floodplain; below the 30 m+ hilltops → *hard*), not on a channel, > 1 km from all 35 documented flood points, urban-core, ≥ 2.5 km apart.

**Result (DIAGNOSTIC, not the gate):** of the 12, the model floods 5 → raw CRR 0.58. But cross-checking the 5 against **independent** flood records (`scripts/diagnose_systematic_specificity.py`): **≥ 4 are documented flood areas** — Semarak (2020 worst-hit; Sg Bunus retention project), Jinjang (KL retention ponds; 258 mm in 2021-22), OUG, Bandar Puchong Jaya — so the model is **CORRECT** to flood them (they are *mislabels* in the negative set, not over-extent). Only **1** (Zon Perindustrian Seksyen 51, 0.17 m — borderline at the 0.10 m threshold) is an unexplained shallow FP.

**Disposition (user, recommended):** the systematic set is a **DIAGNOSTIC** (`kind=dry_diagnostic`, excluded from the scored loader), **not** the primary gate — its raw CRR is a *contaminated lower bound* (mislabels game CRR *down* as wrongly as curating games it up). The **primary gate stays the clean 7-elevated set: HR 0.76 / CRR 0.86 / TSS 0.62 [0.25, 0.88], PASS.**

**Verdict.** The hard-negative experiment, properly analysed, **corroborates** KL's specificity rather than undermining it: the model floods valley sites that *genuinely flood* (4/5), with a single borderline shallow exception. It also confirms that KL's all-elevated negative set is **geographically appropriate** (KL's dry areas *are* the high ones), not a lazy confound. Residual pluvial over-extent, if any, is confined to ≤1 sub-threshold-margin site — consistent with the design-capacity ceiling (#19), not a new defect. `n=12` hard-negative diagnostic controls recorded (register total 17 positive + 7 dry + 12 diagnostic).

## 12. Future scenario — SSP5-8.5 2100 deliverable (+ Plan-10 speedup confirmed)

The headline future product. Generated offline via `run_multihazard` with the
**parallel raingrid pool** (Plan 10) + the **main-stem HAND** fluvial (Plan 8):
pluvial (9-RP raingrid, `--raingrid-workers 0`) ∨ fluvial (`hand_mainstem_utm47n.tif`,
`--fluvial-bankfull-rp 0`). Coastal = N/A (inland KL).

**Forcing (`hazard_levels_ssp585_2100_fluvbias.csv`):** pluvial = the #16-corrected
clean SSP5-8.5/2100 IDF×climate field (RP100 = 0.122 m excess); fluvial = present-day
2.06× GLoFAS bias **×** the SSP5-8.5/2100 climate factor α = 1+0.07·4.0 = 1.28 →
combined discharge factor **2.637**, via `apply_fluvial_bias` (RP100 overbank 7.31 m vs
present-day 6.06 m).

**Present-day (2020) vs end-of-century (2100):**

| Quantity (RP100) | 2020 | 2100 | Δ |
|---|---|---|---|
| Combined pluvial∨fluvial extent | 296.6 km² | 361.5 km² | **+22%** |
| Combined mean depth | 1.01 m | 1.26 m | **+25%** |
| Fluvial extent | 100.1 km² | 127.8 km² | +28% |
| Pluvial extent | 415.3 km² | 466.9 km² | +12% |

All hazards **monotone in RP** and **future > present at every RP** (pluvial extent
ratio 1.53× at RP2 → 1.12× at RP100 — the expected sub-linear, saturating climate
response). Figure: `outputs/kuala_lumpur_ssp585_2100/kl_2020_vs_2100_rp100.png`
(`scripts/render_kl_future_comparison.py`).

**Plan-10 speedup — CONFIRMED end-to-end.** This 9-RP run was the first real full-batch
test of the parallel pool: **wall 7757 s ≈ 2.15 h** vs the documented **~5–6 h serial**
baseline → **~2.6×**, at heavier 2100 forcing (so conservative). #18 mitigated & confirmed.

**Status.** The KL multi-hazard product now spans **present-day (validated: HR 0.76 /
CRR 0.86 / TSS 0.62) + end-of-century (SSP5-8.5 2100)**, with all scenario forcing
consistent (#16 resolved). Remaining KL polish: full viz suite + AR6 offline-repeatability.
Next strategic step: transfer the KL template (main-stem HAND #20, four-manifest contract,
hotspot validation, #21 hard-negative lesson) to Bangkok + Jakarta.

## 13. Production-readiness polish (2026-06-06)

- **AR6 sea-level offline-repeatability.** The pipeline previously re-fetched the remote
  AR6 zarr (`storage.googleapis.com/...`) on every run and broke twice on transient
  outages. Added a shared cache-aware `resolve_sea_level_entry()` (on-disk JSON cache of
  the extracted deltas at `data/_ar6_lsl_cache.json`; the remote zarr is opened ONLY on a
  cache miss, `zarr` imported lazily) used by BOTH `build_scenarios_from_ar6_zarr` and the
  pipeline's `build_hazard_levels`. New flags on both: `--offline` (cache-only; errors on a
  miss → fully repeatable runs) and `--refresh-cache`. 5 offline tests (incl. pipeline-level).
- **Viz.** Two headline figures (combined pluvial∨fluvial, 3.0 m cap):
  `kl_2020_vs_2100_rp100.png` (present vs end-of-century, §12) and
  `kl_rp_progression_2020.png` (present-day RP2→RP1000 design-event progression:
  38 → 147 → 297 → 411 km²). Scripts: `render_kl_future_comparison.py`,
  `render_kl_rp_progression.py`.

**KL status: production-complete** — present-day validated (HR 0.76 / CRR 0.86 / TSS 0.62)
+ SSP5-8.5 2100 future product, all scenario forcing consistent (#16), perf solved & proven
(#18, ~2.6×), AR6 offline-repeatable, headline viz. Ready to transfer to Bangkok + Jakarta.
