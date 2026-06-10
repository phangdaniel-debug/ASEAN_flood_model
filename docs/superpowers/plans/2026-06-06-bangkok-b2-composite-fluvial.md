# Bangkok B2 — Composite Fluvial + Main-Stem HAND (Plan B2 of N)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** Fix the two diagnosed B1 fluvial failures by validating Bangkok against the **composite** (pluvial ∨ klong-fluvial ∨ **Chao Phraya mainstem fluvial** ∨ coastal) with a **main-stem HAND**, so HR recovers (the mainstem reaches the 2011-flooded outer districts) and CRR recovers (no klong over-broadcast across the delta). Evidence-driven follow-on to the B1 dossier (`…/runs/2026-06-06-bangkok-validation-dossier.md`).

**Architecture (worked out in B2 design exploration):** Bangkok flooding = 4 components. The `bangkok` config models pluvial + a 5 km² *klong* fluvial + inertial coastal; the **Chao Phraya mainstem** (160,000 km², RP100 stage **7.11 m**) lives in the separate `bangkok_chao_phraya` (BCP) config (own smaller grid). B1's CRR crash = the klong's 0.58 m stage applied via *dense OSM-river HAND* floods the whole delta incl. the defended CBD; B1's HR miss = the klong can't represent the mainstem 2011 flood. Fix: build ONE Bangkok **main-stem HAND** (accumulation channels at the Chao Phraya trunk scale) and reference BOTH fluvials to it — the klong's small stage then floods little (CRR up), the mainstem's 7 m stage floods the trunk floodplain reaching the 2011 districts (HR up). Mirrors KL Plan 8 (#20).

**Cardinal discipline:** main-stem HAND threshold anchored to the **trunk catchment scale** (channel-init / OSM-river HAND over-floods — KL's 875 km² lesson), NOT the gate. The defended CBD may still flood from the 7 m mainstem via HAND → that's the **documented King's-Dyke-not-modeled finding** (kept, reported, dry control STAYS). The gate reveals; never tuned to.

**Tech Stack:** Python 3, pysheds 0.5 (`model/hand_model.py` accumulation + `compute_hand`), rasterio (+ `reproject` for the BCP→bangkok grid resample), run_multihazard, the generalized `validate_hotspots.py --city`. Inputs: `data/bangkok/copernicus_dem_utm47n_subsidence_corrected.tif`, `data/bangkok_chao_phraya/hazard_levels_ssp585_2020.csv` (mainstem stages), the B1 `outputs/bangkok_ssp585_2020/{pluvial,coastal}/rp_100` (reuse — unchanged).

---

### Task 1: Bangkok main-stem HAND — build + viability (the crux; mirrors KL Plan 8)

**Files:** Create `data/bangkok/hand_mainstem_utm47n.tif`; viability run doc `…/runs/2026-06-06-bangkok-mainstem-hand-viability.md`.

- [ ] **Step 1 (viability sweep):** Adapt `scripts/_diag_hand_extent_tradeoff.py` for Bangkok: build accumulation-derived HAND (`derive_drainage_mask_from_accumulation` + `compute_hand` on the subsidence-corrected bangkok DEM) at thresholds spanning channel-init → trunk (e.g. 2000 / 20000 / 200000 / 1,000,000 px). For EACH: report RP100 fluvial extent at the **mainstem stage 7.11 m** (`HAND < 7.11`, % of domain) AND HAND_min at: 3 defended-CBD dry controls (Silom/Sathorn/Sukhumvit — want HAND high enough they DON'T flood, or accept the documented King's-Dyke finding) + 4 missed-2011 positives (Sai Mai/Bang Bua Thong/Pak Kret/Mueang Nonthaburi — want them reached). Anchor the threshold to the **Chao Phraya trunk catchment scale** (the lower-mainstem accumulation; the BCP catchment is 160,000 km² but only the in-domain lower reach matters). Pick the threshold that (a) reaches the 2011 districts, (b) gives a credible extent (NOT ~whole domain), (c) is anchored to the trunk scale not the gate.
- [ ] **Step 2:** Build + commit `data/bangkok/hand_mainstem_utm47n.tif` at the chosen threshold via `scripts/build_hand_raster.py --acc-threshold`. Record the anchor + sweep in the viability doc. Commit.

### Task 2: Regenerate the klong fluvial with main-stem HAND (CRR fix)

- [ ] **Step 1:** Re-run ONLY the bangkok klong-fluvial RP100 offline (`run_multihazard … --only-hazard-types fluvial --fluvial-hand-raster data/bangkok/hand_mainstem_utm47n.tif --fluvial-bankfull-rp 0`, RP100-only CSV) → `outputs/bangkok_ssp585_2020/fluvial/` (replaces the over-broad OSM-HAND klong fluvial). Confirm the klong extent collapses (small stage × trunk HAND → little flooding) and the CBD clears.

### Task 3: Generate the Chao Phraya mainstem fluvial with main-stem HAND + resample

**Files:** produces a mainstem-fluvial RP100 raster on the **bangkok** grid.

- [ ] **Step 1:** Generate BCP mainstem fluvial RP100 offline using the bangkok DEM + `hand_mainstem_utm47n.tif` + the BCP mainstem stage (7.11 m at RP100) with `--fluvial-bankfull-rp 0`. Simplest: build a 1-row fluvial CSV with the BCP RP100 mainstem stage and run `--only-hazard-types fluvial` on the **bangkok** grid (so it's already aligned — no resample needed). Output to a scratch dir, then copy as `outputs/bangkok_ssp585_2020/mainstem_fluvial/rp_100/…tif`. (If instead BCP's own grid is used, `rasterio.warp.reproject` onto the bangkok grid.) Confirm the mainstem extent is credible (trunk floodplain, reaches the outer 2011 districts, NOT the whole domain — the KL 875 km² guard).

### Task 4: Composite validation

- [ ] **Step 1:** Extend the wet-mask union to include the mainstem fluvial. Either (a) add `mainstem_fluvial` to `_hazard_rasters()` in `validate_hotspots.py` (so the union picks it up), or (b) pre-combine mainstem into the existing `fluvial` raster (depth-max). Keep KL regression-locked (KL has no mainstem_fluvial → unchanged). TDD the helper change.
- [ ] **Step 2:** Run `validate_hotspots.py --city bangkok --rp 100` → HR/CRR/TSS + CI. Per-spot: confirm (a) the outer 2011 districts now WET (HR up via mainstem), (b) the klong no longer floods the CBD (CRR up), (c) any residual CBD flooding is from the mainstem (the documented King's-Dyke finding — report, keep the control).

### Task 5: Bias check (only if HR still short) + dossier + verdict

- [ ] **Step 1:** If HR still < 0.70 after the mainstem (i.e. the 7.11 m mainstem still misses documented 2011 districts), evaluate a **documented** TMD/ERA5 rainfall-bias on the mainstem discharge (Bangkok 2011 = GLoFAS ~RP6, same ERA5 under-estimate as KL) — anchored to the bias ratio, not the gate. Otherwise skip (the mainstem may already reach them).
- [ ] **Step 2:** Append the Bangkok dossier (§2): the main-stem HAND fix, the composite gate (before B1 → after B2: HR/CRR/TSS), per-spot, the King's-Dyke caveat, honest verdict (PASS / marginal / residual). Update limitations + memory. Commit. Finish branch.

---

## Self-Review
**Spec coverage:** main-stem HAND viability+build (T1) → klong re-HAND CRR fix (T2) → mainstem fluvial HR fix (T3) → composite validate (T4) → bias-if-needed + document (T5). Implements the user-chosen "validate the composite" with the KL main-stem-HAND playbook. ✓
**Placeholder scan:** the HAND viability mirrors a named existing KL script; the run commands reuse the proven offline `--only-hazard-types fluvial --fluvial-hand-raster --fluvial-bankfull-rp 0` pattern; the mainstem stage (7.11 m) + threshold-sweep are concrete; the over-flood guard (KL 875 km² lesson) is explicit. ✓
**Discipline:** threshold anchored to trunk catchment not gate; defended-CBD dry controls STAY (King's-Dyke finding); KL regression-locked; validation-first within B2 (bias only if evidence calls). ✓

## Execution Handoff
Plan B2 of N. After execution: finish branch → (if needed) full 9-RP Bangkok baseline once an inertial-solver parallelization exists → Jakarta transfer (carry the now-twice-proven main-stem-HAND rule).
