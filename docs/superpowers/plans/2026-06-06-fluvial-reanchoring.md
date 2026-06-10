# Fluvial Discharge Re-anchoring (Plan 7 of N)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the documented GLOFAS fluvial under-estimate (GLOFAS calls Dec-2021 RP~6 vs JPS-documented RP50–100) by a **documented magnitude bias correction** to the Klang discharge, so the RP100 overbank stage rises enough to flood **Old Klang Road** (HAND 5.45 m, the current HR gap) — turning KL's marginal HR-fail into a clean, real PASS. The correction is anchored to the documented rainfall bias, NOT tuned to the gate.

**Diagnosis (established 2026-06-06):**
- **Taman Sri Muda is OUT of scope** for this fix — 7.6 km from the nearest modeled HAND floodplain cell. It is not a discharge problem; it's outside the modeled channel domain (retention-pond-failure / channel-network-coverage issue). Document, don't chase here.
- **Old Klang Road IS the target** — on the floodplain (HAND min 5.45 m within 60 m), but the current RP100 overbank stage is only 3.31 m → dry. The other floodplain hotspots (Masjid Jamek, Jln Tun Razak, Kampung Baru) have HAND 0 → already flooded, unaffected.
- **The correction reaches it:** stage ∝ Q^0.6 (Manning wide-channel), so the documented ~2.06× discharge correction raises RP100 stage from 3.31 → ~5.9 m above bankfull > 5.45 m → Old Klang Road floods (~0.5 m). Elevated dry controls are off-floodplain → unaffected → CRR holds.

**Why magnitude (not event-RP relabeling):** the root cause is ERA5 under-estimating the rainfall → GLOFAS under-estimating the discharge *magnitude*. So the fix is to scale the discharge **up** (direction unambiguous). A pure event-RP relabel would re-shape the tail and could *reduce* RP100 discharge — wrong direction. The factor comes from the documented rainfall bias.

**Discipline guards:**
- Factor anchored to the **documented rainfall bias** (ERA5-Land 6h RP2 = 43.6 mm vs JPS MSMA 90 mm → 90/43.6 = 2.06×), with the event-RP (RP6→~RP50-100) as a consistency cross-check — NOT tuned to make Old Klang Road's stage hit 5.45 m.
- Verify the gain is **real**: Old Klang Road floods AND CRR holds (dry controls don't get falsely flooded) AND no spurious over-flooding of the floodplain. If CRR drops, the correction is over-broadening — report, don't accept.

**Fast re-run:** fluvial is HAND inundation (quick), NOT the slow raingrid. Regenerate ONLY the fluvial rasters (the pluvial dense-drainage rasters are unchanged; the validator combines pluvial∨fluvial). So this plan iterates in minutes, not hours. Offline (no AR6).

**Tech Stack:** Python 3, numpy, scipy, rasterio, click, pytest. Key files: `scripts/gev_utils.py` (`gev_return_level`, `mannings_stage`), the KL fluvial GEV in `data/kuala_lumpur/hazard_baseline_template.csv` (xi=0.2835, mu=149.5 m³/s, sigma=44.7 m³/s; bankfull Q=98 m³/s → stage 1.756 m; channel w=30 m, n=0.035, S=0.002).

---

### Task 1: Compute + record the discharge bias factor (analytical)

**Files:** Create `docs/superpowers/runs/2026-06-06-fluvial-bias-anchor.md`
- [ ] **Step 1:** Record the factor: rainfall anchor (ERA5-Land 6h RP2 43.6 mm vs JPS 90 mm → **f = 2.06**), the linear rainfall→peak-discharge assumption (stated as an approximation), and the event-RP consistency cross-check (after ×2.06, confirm Dec-2021-magnitude lands ~RP50–100 in the rescaled GEV — compute it via `gev_return_level`). State plainly: the factor is the documented rainfall bias, not a gate-fit. Commit.

### Task 2: Regenerate KL fluvial RP-stages with the bias factor (TDD)

**Files:** Create `scripts/apply_fluvial_bias.py`; Test `tests/test_fluvial_bias.py`; produces a corrected fluvial hazard-levels CSV.
- [ ] **Step 1 (failing test):** `apply_fluvial_bias(gev_xi, gev_mu, gev_sigma, rp, factor, bankfull_q, channel_w, n, slope)` returns the corrected stage-above-bankfull = `mannings_stage(factor*Q_rp) - mannings_stage(bankfull_q)` where `Q_rp = gev_return_level(...)`. Test: factor=1.0 reproduces the committed baseline stage (RP100 ≈ 3.31 m within 0.05); factor=2.06 gives a larger stage (~5.9 m); monotone in RP.
- [ ] **Step 2:** implement using `scripts/gev_utils.gev_return_level` + `mannings_stage` (c=-xi). Verify green.
- [ ] **Step 3:** generate `data/kuala_lumpur/hazard_levels_ssp585_2020_fluvbias.csv` — copy the committed `hazard_levels_ssp585_2020.csv`, replace the **fluvial** `water_level_m` rows with the factor-2.06 corrected stages (leave coastal/pluvial rows untouched). Confirm the RP100 fluvial stage is now ~5.9 m. Commit script + test (CSV is a small tracked artifact — commit it).

### Task 3: Regenerate ONLY the fluvial rasters (fast)

**Files:** produces (gitignored) `outputs/kuala_lumpur_ssp585_2020/fluvial/`
- [ ] **Step 1:** Back up current fluvial rasters → `outputs/_ref_fluvbias_pre/`.
- [ ] **Step 2:** Run `run_multihazard` offline with a **fluvial-only** hazard-levels CSV (strip coastal/pluvial rows from `..._fluvbias.csv` so only fluvial is computed → no slow raingrid) + `--fluvial-hand-raster data/kuala_lumpur/hand_utm47n.tif` + the channel/sea inputs. This regenerates only the fluvial rasters (HAND inundation, fast). Confirm completion + monotonicity of fluvial stages.

### Task 4: Re-validate — does Old Klang Road flood, CRR held?

- [ ] **Step 1:** `validate_hotspots_kl.py --rp 100` → capture HR/CRR/TSS/GATE (the validator recombines the unchanged pluvial with the new fluvial).
- [ ] **Step 2 (decisive per-spot):** Old Klang Road fluvial depth @50 m now > 0.10 m? (the HR restore). Confirm the dry controls did NOT gain fluvial hits (CRR held). Confirm Taman Sri Muda still 0 (expected — out of domain). Report all.
- [ ] **Step 3:** Honest verdict: did the documented bias correction give a clean PASS (HR ≥ 0.70 AND CRR ≥ 0.70)? If HR rose but CRR dropped, the correction over-broadens → report (don't accept). If HR didn't rise, the factor wasn't enough to clear Old Klang Road's HAND — report honestly (do NOT inflate the factor past the documented value to force it).

### Task 5: Document — dossier §10 + limitation updates

- [ ] **Step 1:** Dossier §10: the diagnosis (Taman Sri Muda out-of-domain; Old Klang Road the real target), the documented 2.06× anchor, the before/after (HR/CRR/TSS; Old Klang Road depth), the verdict. Update #19 (Old Klang Road resolved via fluvial, if so) + add/extend a fluvial-under-anchoring limitation + a Taman-Sri-Muda-out-of-domain note. If a clean PASS: state KL present-day is **validated (HR/CRR both ≥ floor, significant TSS)**. Commit.

---

## Self-Review
**Spec coverage:** documented factor (T1) → regenerate fluvial stages (T2, TDD) → fast fluvial-only re-run (T3) → decisive validation incl. Old Klang Road + CRR guard (T4) → document (T5). ✓
**Placeholder scan:** the factor is a documented number (2.06, from the cited rainfall bias); the stage math uses real gev_utils functions; the +2× → 5.9 m → floods 5.45 m HAND chain is shown. Run steps have explicit checks. ✓
**Discipline:** factor anchored to documented rainfall bias not the gate (Plan 3 lesson); real-not-cosmetic verified via per-spot + CRR guard (Plan 4/5 lesson); Taman Sri Muda honestly scoped out (diagnosis, not hidden). ✓

## Execution Handoff
Plan 7 of N. Fast iteration (no raingrid). After execution: final review → finish branch → remaining work (register growth n≥15; #16 regen; SSP5-8.5 2100 + viz; AR6 offline-repeatability; then transfer KL template to Bangkok + Jakarta).
