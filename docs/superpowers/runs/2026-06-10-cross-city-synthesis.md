# Cross-City Validation Synthesis — KL → Bangkok → Jakarta (flood-v2.0)

**Date:** 2026-06-10
**Purpose:** Consolidate the multi-city validation transfer. Three ASEAN cities have now been
run through the same model-blind hotspot validation harness. This doc records the comparative
results, the **transferable methodology rules** the transfer established, and the **open
cross-city items** (chiefly the pluvial-method heterogeneity) — so the remaining cities
(Manila, HCMC) start from evidence, not rediscovery.

## 1. Comparative gate results (present-day, RP100, threshold 0.10 m, radius 50 m)

| City | HR | CRR | TSS [95% CI] | pluvial | fluvial | coastal | verdict |
|---|---|---|---|---|---|---|---|
| **Kuala Lumpur** | 0.76 | 0.86 | **0.62** [0.25, 0.88] | raingrid + OSM-drainage | main-stem HAND (#20) | n/a (inland) | **PASS** (validated) |
| **Bangkok** | 0.56 | 0.86 | **0.42** [0.04, 0.75] | fillspill | trunk-HAND on defended DEM | inertial | FAIL-HR — out-of-domain ceiling (#22) |
| **Jakarta** | 0.89 | 0.50 | **0.39** [0.03, 0.75] | fillspill | dense single-stage HAND | inertial | FAIL-CRR — residual pluvial over-ponding (#23) |

All three reach **significant discriminative skill** (every TSS CI excludes zero). KL is a clean
PASS; Bangkok and Jakarta have honest, cleanly-diagnosed ceilings with documented next levers.
**Caveat (see §3.1): KL's gate is a raingrid result; Bangkok/Jakarta are fillspill — the three
are not yet apples-to-apples on the pluvial layer.**

## 2. Transferable methodology rules (proven across cities)

1. **The validation harness transfers cleanly.** The four-manifest contract
   (`forcing_anchors / gates / observed_events / hotspots`) + the generalized
   `validate_hotspots.py --city` (hotspot HR/CRR/TSS + bootstrap CI, Singapore precedent) +
   the model-blind register builder dropped onto Bangkok and Jakarta with **zero engine
   changes** and KL/Bangkok regression-locked throughout. This is the reusable core.

2. **Main-stem HAND rule (#20) — for incised-valley cities.** Reference fluvial HAND to
   flow-accumulation channels at the **modeled-discharge (GloFAS-reach) catchment scale**, NOT
   raw OSM rivers (over-floods hillside rivulets) nor channel-initiation (875 km² absurd
   extent). Validated on KL (180 km² trunk → Federal Hill fixed by physics, extent 100 km²).

3. **Out-of-domain HAND limit (#22, #23) — for flat deltas fed by mega-rivers. CONFIRMED on
   2 of 3 cities.** Single-stage HAND does **not** transfer when the validation event is sourced
   from a catchment whose headwaters lie outside the model domain: the accumulation trunk shifts
   off the natural river, so no threshold both reaches the riverine positives and spares the
   off-channel controls. **Bangkok** (Chao Phraya, 160,000 km², fully out-of-domain → HR ceiling
   0.56) and **Jakarta** (Ciliwung, headwaters at Bogor out-of-domain → main-stem HAND grows
   extent / loses positives). The hydrodynamic alternative is intractable on flat deltas (CFL
   collapse + equilibrium over-flood — Bangkok B2). **Rule for Manila/HCMC: set HR expectations
   from the catchment/domain ratio; the in-domain reach is the achievable scope.**

4. **Dry-control discipline — flooded controls STAY; low/central areas in flood-prone deltas are
   often mislabels.** Model-blind, geocoded + DEM-verified selection (never hand-pinned, #6b).
   A genuine control the model floods is a *reported false positive*, never dropped to pass.
   But a control that is *independently documented-flooded* is a **mislabel** to correct (KL #21
   systematic negatives that were real flood areas; Jakarta Menteng/Gambir documented-flooded
   2007/2013 → reclassified positives). The correction is anchored to flood records, decided
   model-blind, never to move the gate.

5. **Extent-CSI is a weak gate everywhere we tried it; the hotspot gate is the robust primary.**
   KL SAR-blind (urban double-bounce, #17); Bangkok THA2011 MODIS = WARN; Jakarta JKT2020
   Sentinel-1 captures peri-urban open-water but misses the urban core in layover/shadow (#25).
   No city yet has a trustworthy urban extent reference — documented-hotspot HR/CRR/TSS is the
   transferable primary.

## 3. Open cross-city items

### 3.1 Pluvial-method heterogeneity (the homogeneity gap) — OPEN, NEW limitation #26
KL was migrated to the **raingrid** pluvial solver (+ OSM-waterway drainage densification, Plan
5) and validated there. Bangkok and Jakarta use the pipeline-default **fillspill**. The two
models differ structurally (raingrid routes rain to an outlet network; fillspill fills/spills
catchment depressions), so KL's drainage-densification fix is **raingrid-specific and does not
port to fillspill**. Consequence: the three cities' gates are **not apples-to-apples on the
pluvial layer**, and Jakarta's residual CRR FPs are fill-spill over-ponding on elevated ground
(Jagakarsa/Pondok Pinang/Pasar Minggu — the KL Bukit-Antarabangsa pattern, but un-portable).
**Resolution path (deferred, methodology-level): migrate Bangkok+Jakarta to the KL-validated
raingrid+OSM-drainage, then re-validate all three on one method.** This is the true homogeneity
play; it was NOT done as a per-city tweak (which would have increased heterogeneity).

### 3.2 Out-of-domain fluvial (Bangkok, Jakarta)
The honest lever is a **north/upstream-boundary inflow** boundary condition (documented event
stage injected at the domain edge) + tractable routing — logged for both, deliberately not
forced. Bangkok's HR ceiling and Jakarta's Cipete dense-HAND residual both trace here.

### 3.3 Coastal forcing confidence (Jakarta, delta cities)
Jakarta coastal is **qualitative** (Muis et al. 2016 screening, no UHSLC gauge, ±0.2–0.3 m) and
under-reaches the North-Jakarta rob positive (Penjaringan). A documented-confidence limit, not a
tunable defect.

## 4. Status & honest verdict

The **validation harness and the transferable rules are proven**. The multi-city product stands
at: **KL production-complete (PASS + SSP5-8.5 2100)**; **Bangkok** and **Jakarta** validated to
**significant skill with honest, documented ceilings** (out-of-domain HAND limit; pluvial-method
heterogeneity). The discipline held throughout — when planned fixes (Bangkok hydrodynamic,
Jakarta main-stem HAND) were overturned by evidence, they were reported as findings, not forced;
no gate was tuned; flooded genuine controls and missed positives stay in every register.

**Recommended next:** (a) the pluvial homogeneity migration (§3.1) as a deliberate methodology
plan if a clean three-city PASS comparison is wanted; or (b) transfer to **Manila / HCMC**
carrying rules #2–#5 + the §3 limits; or (c) fold this synthesis into the paper draft.
