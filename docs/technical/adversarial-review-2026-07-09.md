# Adversarial Methodology Review — Round 3 (2026-07-09)

**Scope.** One further adversarial round on (a) the underlying flood-model methodology and
(b) the claims in `docs/paper/ieee-kse2026.tex`, with specific attention to *why each
approach was chosen* and to *heterogeneity across the four cities* and its justification.
Builds on Round 1 (`scripts/_referee_stress_test.py`: exact Fisher/Clopper–Pearson
statistics, hazard-layer ablations, control-difficulty audit) and Round 2
(`scripts/_referee_stress_test2.py`: elevation-null baseline, Jakarta handfill-stage
sensitivity). This round covers what those did not: the forcing chain, coastal-solver
design choices, the cross-city configuration register, and paper–code consistency.
Every factual claim below was verified against the code, the release script
(`repro/run_atlas_fixed.sh`), or a measured output; nothing is argued from memory.

**Verdict key.** DEFENSIBLE — choice is anchored and documented; no action.
DISCLOSED — defensible but only because the limitation is (now) stated; keep disclosure.
FIXED — challenge found a wrong or stale claim; corrected this round.
OPEN — defensible as screening-grade, but a named follow-up test would materially
strengthen it.

---

## 1. Summary of outcomes

| # | Challenge | Verdict |
|---|-----------|---------|
| C1 | Mitigation-delta mechanism in the paper ("difference of two inflated extents is itself inflated") | **FIXED — claim was empirically false** |
| C2 | Abstract: DSM high bias "drives coastal over-prediction" | **FIXED — wrong mechanism** |
| C3 | Limitations: pluvial "heterogeneous… explains residual specificity loss" | **FIXED — stale (pre-dated regime-matching)** |
| C4 | Methods: KL described as handfill-only | **FIXED — released KL layer is a union** |
| C5 | Uniform coastal Manning n = 0.06, hardcoded | **CLOSED 2026-07-12 — parametrized, re-cited, sensitivity measured (n 0.06→0.10: −6.1% extent, IoU 0.94)** |
| C6 | Synthetic 3-1-2 h surge hydrograph + t_end = 8 h | **OPEN — duration sensitivity untested** |
| C7 | Canal-HAND stages/pruning chosen with gate visibility | **DISCLOSED — single-iteration risk stated; held-out event test recommended** |
| C8 | Bathtub run-flag `--fluvial-bankfull-rp 0` vs paper's "bankfull subtracted" | **DEFENSIBLE — subtraction is baked upstream (audit-trap documented below)** |
| C9 | Pumped-polder floor applied to Bangkok only | **DEFENSIBLE — rationale now written down (was code-comment only)** |
| C10 | Bare-earth vs FABDEM | **DEFENSIBLE — licence-driven, per-city lidar-fit** |
| C11 | Singapore DeltaDTM hybrid (only city not lidar-calibrated) | **DISCLOSED** |
| C12 | GEV shape clamp ξ ≤ 0.30; RP1000 extrapolation; single gauge per city | **DISCLOSED in SAFE; KSE carries no forcing-uncertainty sentence (space) — noted** |
| C13 | Bangkok "significant" on a 7-control degenerate stratum (Fisher ≈ 0.08) | **DISCLOSED — criterion named inline; keep both statistics** |
| C14 | IDF anchor duration 1 h (SG) vs 6 h (others) | **DEFENSIBLE — service-standard-matched; KL 1-h variant untested** |
| C15 | Scoring all registers at RP100 ("event-matched") | **DEFENSIBLE — symmetric footprint penalises over-flooding; wording could be tighter** |

---

## 2. Detailed challenges, rationale, and dispositions

### 2.1 Paper-claim challenges (all four FIXED in `ieee-kse2026.tex` this round)

**C1 — The mitigation-delta mechanism was empirically false.**
*Claim (before):* "the bathtub bias is multiplicative (5.2×), so a difference of two
inflated extents is itself inflated."
*Challenge:* we measured it. Engine bathtub on the released seawall DEM at 2100:
SSP2-4.5 = 4,166 km², SSP5-8.5 = 4,201 km² → avoided area ≈ **35 km²**. Inertial:
760.5 vs 852.8 km² → **92 km²**. The bathtub *deflates* the delta (0.4×), it does not
inflate it: the static fill saturates the flat delta under both high-SLR pathways and
washes out the scenario signal. The conclusion ("read the delta off the inertial layer")
survives; the stated mechanism reversed. *Why the wrong claim existed:* it was inherited
from the DSM-era numbers (−133 vs ≈11 km²), where the un-saturated building-blocked
bathtub did inflate the delta. On bare earth the regime changed and the sentence was not
re-derived. *Fix:* paragraph rewritten with the measured 35-vs-92 saturation mechanism.
Provenance: `outputs/_bathtub_check/bkk2100_src_polder`, `bkk245_src_polder`;
`repro/bathtub_bias_check.sh` (2100 block).

**C2 — Abstract attributed coastal over-prediction to the DSM's high bias.**
*Challenge:* measured bathtub extents are *larger* on bare earth than on the DSM
(Bangkok 4,432 vs 3,546 km²) — building mass acted as an accidental barrier, so the DSM
bias *masked* flooding rather than driving over-prediction; the over-prediction is the
solver's. The paper's own §DEM sentence ("what makes the bathtub over-prediction a
solver-architecture artifact rather than a terrain artifact") already said this correctly;
the abstract contradicted it. *Fix:* abstract clause now reads "…high bias that masks
documented flood locations" (the gate-evidenced mechanism: the DSM masked Old Klang Road
and canal corridors).

**C3 — Limitations carried a stale pluvial sentence.** "Currently heterogeneous
(a documented homogenisation step)… explains residual specificity loss from over-ponding
on elevated ground" described the pre-regime-matching state and the old Jakarta fill-spill
CRR failure; current CRRs are 0.90–1.00 and the split is deliberate. *Fix:* reworded to
regime-matched-by-mechanism with the actual residual cost (CRR 0.92 in JKT/KL where the
handfill over-reaches).

**C4 — Methods under-described the released KL pluvial.** The released layer is
`max(fill-spill, canal-HAND)` (`scripts/_apply_kl_canal_pluvial.py`), not handfill alone;
Jakarta's is `max(engine handfill, canal-HAND)`. *Fix:* parenthetical added (KL unioned
per-pixel with its depression cascade). Reproducibility chain for the unions:
`repro/run_atlas_fixed.sh` → `repro/rerun_handfill_scaled.sh` →
`scripts/_apply_{kl,jakarta}_canal_pluvial.py` (run docs: `docs/runs/2026-07-04-*.md`).

### 2.2 Coastal solver

**Why local-inertia at all.** Bates et al. (2010) reduced-physics SWE: drops advection
(valid Fr ≪ 1 — surge/backwater regime), semi-implicit friction, explicit continuity,
CFL-adaptive Δt on a staggered grid, numba-JIT with a verified numpy fallback. Chosen over
(a) bathtub — no dynamics, measured 5.2×/1.2× over-prediction on identical terrain;
(b) full SWE (e.g. ANUGA/LISFLOOD-FP full solvers) — cost and licence-free-stack
constraints; the local-inertia family is the standard screening compromise (LISFLOOD-FP's
own default). The 5.2× Bangkok / 1.2× Jakarta comparison is apples-to-apples by
construction (same seawall DEM, sea mask, tidal seeds, water level; only
`--coastal-solver` differs) — re-verified this week via `repro/bathtub_bias_check.sh`.

**C5 — Uniform Manning n = 0.06 (hardcoded at the `run_inertial` call).** A mangrove
fringe and a paved promenade get identical friction, and n directly controls inland
propagation distance. The *pluvial* rain-on-grid solver takes a per-cell n raster; the
coastal solver never does — an internal inconsistency of sophistication. *Defense:* 0.06
is a mid-range urban-floodplain value; screening grade; extent is reported at a 0.10 m
threshold where first-order geometry dominates. *Disposition:* **CLOSED 2026-07-12.**
(1) Re-cited: the value's source is now Chow (1959) and Arcement & Schneider (1989,
USGS WSP 2339) — developed-floodplain n ≈ 0.05–0.15 — not Bates 2010 (which sources the
solver, not the roughness). (2) Parametrized: `--coastal-manning-n` added to
`run_multihazard.py` (default 0.06, no behaviour change). (3) Sensitivity measured
(`repro/coastal_manning_sensitivity.sh`, Jakarta present RP100 coastal-only — the
undefended subsided delta where overland friction matters most): n = 0.06 / 0.08 / 0.10
give extent 182.1 / 177.1 / 171.1 km² (−2.8% / −6.1% vs base), IoU vs base 0.956 / 0.938,
mean depth 2.0–2.1 m, max at the physical cap throughout. A +67% roughness change moves
the headline extent by ~6% — an order of magnitude below the bathtub↔inertial gap (5.2×)
and within screening tolerance; direction physically correct (more friction, slightly less
inland penetration). Residual note: the sensitivity baseline (182.1 km²) sits −3.4% from
the atlas value (188.5 km², from the depth-cap re-solve run) — a same-config re-run drift
worth knowing but immaterial to the within-run comparison. Bangkok 2100 (defended,
overtopping-driven) left as optional follow-up; the undefended case bounds the friction
lever.

**C6 — Idealised surge forcing.** One synthetic triangular hydrograph (3 h ramp / 1 h
hold / 2 h recession to a permanent MSL+SLR floor) for every city, RP, and scenario;
`t_end = 8 h`; convergence deliberately disabled when the SLR floor is active. *Why:* a
generic design event (no per-storm reconstruction is possible for a 5-scenario × 3-RP
atlas); the asymmetric ramp is a numerical-stability requirement (Dirichlet shock on a
dry bed); the permanent floor is what makes SLR inundation persist after the transient
surge — recognised and handled. *Challenge:* inundation extent is then
surge-duration-limited by construction; if real Gulf-of-Thailand surges persist longer
than 6 h, the inertial extent is under-resolved, and part of the 5.2× bathtub gap would be
"finite-duration physics" (defensible, indeed the point) mixed with "t_end truncation"
(numerical). The subsea pre-flood + permanent floor mean the *SLR component* is not
duration-limited; the *surge component* is. *Disposition:* OPEN — a single t_end-doubling
run (16 h) for Bangkok 2100 would bound the truncation term; recommend recording
`converged` vs `t_end-limited` per released coastal cell (the solver already returns it).

**Datum chain (C12-adjacent).** Gauge de-meaned to local MSL → CMEMS CNES-CLS-2022 MDT
offset → EGM2008 (per-city: SG 1.1588 m, JKT 0.9976 m, BKK 1.1785 m). Best available open
practice; dm-scale MDT error propagates 1:1 into level on flat deltas — inherent to any
open datum chain, disclosed in the docs. The GEV shape clamp ξ ∈ [−0.5, 0.30] prevents
unstable Fréchet fits on 30–50-yr records; the clamp was validated against PUB ponding
ranges for the *pluvial* fit and is asserted, not validated, for surge — RP1000 coastal is
a deep extrapolation either way (SAFE v5 discloses this; KSE omits the forcing-uncertainty
sentence for space — acceptable for a 6-page venue, noted here).

### 2.3 Fluvial

**Why GloFAS → Manning rating → main-stem HAND.** No licensed hydrodynamic model fits the
open-stack constraint; GloFAS provides the only free design discharge. The 180 km²
main-stem threshold is anchored to *which channel the modelled discharge physically
represents* (fixed before the first gate run; corrected a false positive on a 60–77 m
hill), and its failure boundary (out-of-domain mega-rivers: Chao Phraya, Ciliwung
upstream) is disclosed as contribution #5 rather than hidden.

**C8 — the bankfull audit-trap (verified consistent).** The release script passes
`--fluvial-bankfull-rp 0`, which *looks like* it disables the bankfull subtraction the
paper claims. It does not: the subtraction is baked upstream in
`scripts/fit_fluvial_glofas.py` (Manning stage at Q_bankfull subtracted from every RP
stage before the hazard CSV is written — e.g. Bangkok RP100 fluvial `water_level_m` =
0.61 m, an overbank *residual*, not a full stage). The run-time flag is 0 precisely to
avoid double-subtraction. **Any auditor diffing the release script against the paper will
hit this**; it is now documented here and in §10 of the model documentation.

### 2.4 Pluvial

**Why regime-matching instead of one scheme.** Fill-and-spill answers "where does rain
pond?" (depression storage — Bangkok's flat micro-topography); canal-HAND handfill answers
"where does the drainage network overflow?" (canal-dense KL/SG/JKT, where the documented
flood record is drainage-corridor flow that 30 m depression storage cannot see — the
hazard-ablation in Round 1 measured exactly this). A single scheme would either speckle
the canal cities (fill-spill) or invent corridors in Bangkok (handfill). The cost —
heterogeneity — is now framed as a deliberate, mechanism-anchored split (C3 fix).

**C7 — how much of the canal-HAND configuration saw the gate?** The honest accounting:
the KL pruning rule (drains ≥ 0.5 km² accumulation) is physically anchored (headwater
ditches on hills are not flood conveyance) and Jakarta was shown gate-*insensitive* to
pruning (all four variants scored identically — `_apply_jakarta_canal_pluvial.py`); but
the stage scalings (KL 0.5 m at 0.095 m reference excess, clip [0.4, 2.5]; JKT 0.3 m at
0.130 m, clip [0.15, 1.5]; SG engine stage 1.5 m, cap 0.5 m) were selected with gate
visibility, and KL's PASS is the direct product of one model-improvement iteration against
a frozen register (HR 0.65 → 0.71; TSS 0.65 → 0.63, i.e. parity within the ±0.16 CI).
*Defense in place:* register frozen before any scoring and never re-labelled; the ‡
footnote in the paper discloses the conditionality and the revert delta; Round-2's
elevation-null showed the KL register itself cannot fully distinguish model from
topography (null TSS 0.92), which the SAFE paper discloses as "necessary, not sufficient."
*Disposition:* DISCLOSED, with the standing recommendation unchanged from
`model-documentation.md` §10 item 3: physically re-anchor the base stages (drain design
freeboard), and validate the canal-HAND layer against a **held-out event** (a post-2022
flood not in any register) before the next submission cycle.

**C14 — IDF anchor duration heterogeneity (1 h SG vs 6 h others).** Matched to each
service's published design practice (PUB CoP sub-hourly convective design for the
secondary drainage system; MSMA/TMD-RID/BMKG 6-h standards). *Residual challenge:* KL's
convective bursts are also sub-hourly; a 1-h KL variant was never run. Defensible as
standard-anchored (the December-2021 KL event was long-duration), but the sensitivity is
untested — logged.

**Depth caps (0.5 / 1.0 / 3.0 / 3.0 m for SG/JKT/KL/BKK).** Anchored respectively to the
PUB observed ponding range (0.07–0.76 m), documented Jakarta kampung inundation depths,
and (KL/BKK) an effectively-uncapped life-safety bound where the fill-spill geometry is
already self-limiting. Heterogeneous by design; each cap cites its anchor in the
parameter register.

### 2.5 Terrain

**C10 — why not FABDEM.** FABDEM is CC BY-NC — it would break the paper's central
"license-clean, third-party-rebuildable" claim (and its Table I axis). The self-built
correction (z_DSM − b₀ − h_building − f·h_canopy, per-city fit to held-out ICESat-2
ATL08 + GEDI L2A, never transferred between cities) halves MAE and zeroes the urban-core
bias where lidar is dense (Bangkok 1.43 → 0.78 m, bias +1.31 → 0.00). The two-parameter
model cannot fix spatially-varying bias — accepted as screening-grade; the per-zone
accuracy gate is the guard.

**C11 — Singapore is the one city on a different terrain recipe** (DeltaDTM low terrain +
DSM-composited >30 m hills), because its ICESat-2/GEDI residual is 3–5 m MAE — scatter no
per-city fit can beat. This is the "conditions under which more accurate terrain improves
a risk surface" contribution *stated as a finding* rather than a buried inconsistency:
the calibration is gated per city, and the city that fails the gate gets the best open
substitute. DISCLOSED in the paper and §4 of the docs.

**Subsidence correction only for BKK/JKT.** Criterion: documented post-2013 InSAR rates
(up to ~25 cm/yr north Jakarta, 1–2 cm/yr Bangkok); SG/KL have no comparable documented
signal. Omission criterion now stated here (was implicit).

### 2.6 Defences (heterogeneity C9)

Seawall crests are burned per city from documented protection levels (SG +3.0 m, BKK
+2.1 m BMA dike, JKT +2.0 m MSL; `scripts/_fix_coastal_seawall.py`). The pumped-polder
*drain floor* is applied to **Bangkok only** (`apply_pumped_polder.py` in the release
script), although Jakarta polder rings (Pluit, Muara Baru, Penjaringan) exist in the same
module. *Rationale, previously code-comment-only, now on record:* Bangkok's bunded CBD is
documented to have stayed dry through 2011 within its design event (166 BMA pump stations,
80 mm/hr design) — the pump physics demonstrably hold; Jakarta's named polders have
documented chronic rob flooding and pump under-capacity (Pluit inundated in 2020), so
draining them would *over*-protect against the observed record. The asymmetry follows the
evidence, not convenience: the defence is applied exactly where the defence is documented
to work. Jakarta's gate (CRR 0.92) needs no polder drain to pass.

### 2.7 Validation statistics (C13, C15)

Bangkok's "significant skill" rests on the stratified-percentile bootstrap CI [0.19, 0.50]
with a *degenerate* control stratum (7/7 correct rejections — zero resampling variance),
while its exact Fisher test is marginal (p ≈ 0.08). The abstract names the CI criterion
inline and the table footnote carries the Fisher values, so the claim is precise as
worded; both statistics must continue to travel together. Scoring every register at RP100
("event-matched") is symmetric — controls are tested against the same footprint, so TSS
punishes over-flooding — and register events are multi-year flood records rather than
single events; the phrase could still be glossed at first use.

---

## 3. Cross-city heterogeneity register

| Dimension | SG | KL | BKK | JKT | Why it differs | Risk |
|---|---|---|---|---|---|---|
| Terrain recipe | DeltaDTM+DSM-hills hybrid | lidar-calibrated bare-earth (ETH variant) | lidar-calibrated + subsidence | lidar-calibrated + subsidence | lidar density gates the calibration; documented InSAR rates gate subsidence | hybrid bias undisclosed at cell level (gated per zone) |
| Coastal solver | inertial | none (domain ends ~7 km inland) | inertial | inertial | domain clipped to urban core | Port Klang fringe unscreened (disclosed) |
| MSL→EGM2008 offset | 1.1588 | n/a | 1.1785 | 0.9976 | per-gauge CMEMS MDT | dm-scale datum error on flat deltas |
| Defence: crest | +3.0 m | n/a | +2.1 m | +2.0 m | documented protection levels | single continuous crest per city (model-documentation §10 item 4) |
| Defence: pump floor | no | no | **yes** | no (rings exist, unused) | pumps documented to hold (BKK 2011) vs documented to fail (JKT rob) | asymmetry must cite evidence (now does) |
| Pluvial scheme | engine handfill | fill-spill ∪ canal-HAND | fill-spill | engine handfill ∪ canal-HAND | mechanism-matched (depression vs drainage-corridor) | union layers live in post-processors, not the engine flag |
| Handfill stage / cap | 1.5 m / 0.5 m | 0.5 m@0.095 ref / 3.0 m | — / 3.0 m | 2.5 m engine + 0.3 m@0.130 canal / 1.0 m | per-city ponding anchors; scenario-scaled by IDF excess | base stages gate-visible (§10 item 3, OPEN) |
| Canal network pruning | n/a (engine HAND) | ≥0.5 km² accumulation | n/a | unpruned | KL hills have non-conveyance headwater ditches; JKT all-engineered (and gate-insensitive) | — |
| IDF anchor duration | 1 h | 6 h | 6 h | 6 h | national design-standard practice | KL 1-h variant untested |
| Runoff coefficient | 0.75 (+raster) | 0.75 (+raster) | raster only | 0.80 (+raster) | WorldCover raster primary; scalar fallback per land-use mix | second-order |
| Fluvial HAND reference | main-stem v3 | main-stem ≥180 km² (v3eth) | debiased trunk | main-stem v3 | same rule (trunk the discharge represents), per-city accumulation | — |
| Register size (pos/dry) | 38/20 | 31/12 | 32/7 | 33/12 | documented-record availability | BKK 7-control stratum degenerate (C13) |
| Manning n (coastal) | 0.06 | n/a | 0.06 | 0.06 | **homogeneous** — sensitivity measured: 0.06→0.10 moves JKT RP100 extent −6.1% (IoU 0.94) | C5 CLOSED |
| Surge hydrograph | 3-1-2 h | n/a | 3-1-2 h | 3-1-2 h | **homogeneous** — generic design event | C6 OPEN |

The register shows the heterogeneity is of two kinds: **evidence-driven** (terrain recipe,
pump floor, pruning, durations, caps — each anchored to a documented per-city fact) and
**deliberately homogeneous simplifications** (Manning n, hydrograph shape) whose *lack* of
per-city variation is itself the untested assumption. The first kind is defensible and now
documented; the second kind is where the two OPEN sensitivity runs sit.

---

## 4. Actions taken this round

1. `ieee-kse2026.tex`: four corrections (C1 mitigation-delta mechanism → measured
   saturation numbers; C2 abstract bias mechanism; C3 stale pluvial limitation; C4 KL
   union parenthetical). SAFE v5's corresponding sentences were checked and are already
   direction-neutral ("mis-state") or correct — no SAFE edits needed.
2. This document written; summary folded into `model-documentation.md` §10.
3. Rationales that existed only as code comments (Jakarta polder non-application, bankfull
   upstream baking, cap anchors) promoted to the documentation record above.

## 5. Ranked follow-ups (pre-registered, none blocks the current submission)

1. **Coastal sensitivity bracket** (C5+C6, one afternoon): Bangkok 2100 RP100 with
   n ∈ {0.03, 0.10} and t_end = 16 h; record extent deltas and per-cell
   `converged`/`t_end-limited` flags in the parameter register.
2. **Held-out event validation** for the canal-HAND layer (C7): score one post-2022
   documented flood absent from every register, before the next submission cycle.
3. **Physical re-anchoring of handfill base stages** (model-documentation §10 item 3, standing): drain design
   freeboard from PUB CoP / MSMA / PU standards.
4. **KL 1-h IDF variant** (C14): one pluvial re-fit to test duration sensitivity.
5. Gloss "event-matched RP100" at first use (C15) and, if a page frees up, restore the
   one-sentence forcing-uncertainty disclosure to KSE (present in SAFE v5).
