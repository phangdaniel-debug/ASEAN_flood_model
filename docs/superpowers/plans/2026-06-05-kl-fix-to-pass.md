# KL Fix-to-PASS (Plan 3 of N) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two validation-diagnosed defects that made the KL baseline fail the hotspot specificity gate, so the model reaches a **legitimate** PASS — the gate clears because the underlying problems are fixed, not because a parameter was tuned to pass.

**Architecture:** Two surgical, documented-fact-anchored fixes: (1) wire the pluvial 3.0 m depth-cap through `run_city_pipeline.py` → `run_multihazard.py` (a one-line gap; the cap option already exists downstream), then re-run the KL baseline so the over-extent (Bukit Antarabangsa) is removed; (2) set the KL hotspot hit-radius to 50 m, anchored to KL Nominatim geocoding precision (~one city block) — which removes the radius-artefact false-positives (Mont Kiara / Bukit Kiara / Damansara Heights). Then re-validate and update the dossier with the honest post-fix verdict.

**Tech Stack:** Python 3, numpy, scipy, pandas, rasterio, click, pytest. All open data.

**Scope (deliberately narrow — the gate-closing fixes only).** Deferred to **Plan 4**: limitation-#16 scenario-forcing regen, fluvial event-RP re-anchoring (needs its own design decision on the re-anchoring method), growing the dry-control register to n≥15 (must stay model-blind to avoid the negative-set confound, SG limitation #15), and the SSP5-8.5 2100 scenario + viz suite + final dossier. Those are a separate deliverable; this plan only gets the present-day KL baseline to a defensible PASS.

**Inputs:** the merged `main` (Plans 1+2). Baseline rasters at `outputs/kuala_lumpur_ssp585_2020/` (will be regenerated). KL register + validator + gates already committed.

**Discipline guard:** the 50 m radius is justified by documented geocoding precision (dossier §3/§6, already integrity-reviewed), NOT by the gate flip. If, after both fixes, the gate still FAILs, that is a legitimate result to record — do NOT search for a third parameter to nudge.

---

### Task 1: Wire the pluvial depth-cap through the pipeline

**Context:** `run_multihazard.py` already has `--pluvial-depth-cap` (line 401) → `run_rain_on_grid(..., peak_depth_cap_m=pluvial_depth_cap)` (line 816). The bug is that `run_city_pipeline.py` builds the `run_model_cmd` (lines 836–877) without appending it, so the cap is never passed (defaults to `None` = uncapped). The user-facing `--max-ponding-depth-m` (default 3.0, variable `max_ponding_depth_m`) is in scope at that point (already used at line 472).

**Files:**
- Modify: `scripts/run_city_pipeline.py` (append one `extend` to `run_model_cmd`)

- [ ] **Step 1: Add the missing argument forwarding**

In `scripts/run_city_pipeline.py`, find this exact line (in the `run_model_cmd` construction, ~line 867):
```python
    run_model_cmd.extend(["--pluvial-model", pluvial_model])
```
and insert immediately AFTER it:
```python
    # Forward the pluvial ponding depth cap to run_multihazard's raingrid path.
    # Without this the cap defaulted to None (uncapped) — the root cause of the
    # KL baseline pluvial over-extent (max 4.5 m > 3.0 m cap; Plan-2 finding #2).
    run_model_cmd.extend(["--pluvial-depth-cap", str(max_ponding_depth_m)])
```

- [ ] **Step 2: Verify the module still imports and the option is wired**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
python -c "import sys;sys.path.insert(0,'.');import scripts.run_city_pipeline;print('import OK')"
grep -n "pluvial-depth-cap" scripts/run_city_pipeline.py
python scripts/run_multihazard.py --help 2>&1 | grep -A1 "pluvial-depth-cap"
```
Expected: `import OK`; the grep shows the new `--pluvial-depth-cap` line in run_city_pipeline; run_multihazard `--help` confirms the option exists downstream.

- [ ] **Step 3: Commit**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
git add scripts/run_city_pipeline.py
git commit -m "fix: forward --pluvial-depth-cap from pipeline to run_multihazard (raingrid was uncapped)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Re-run the KL present-day baseline with the cap enforced

**Context:** The cap only affects the raingrid pluvial (coastal bathtub + fluvial HAND are unchanged, but the pipeline re-runs all hazards; the pluvial raingrid is the slow part). This regenerates `outputs/kuala_lumpur_ssp585_2020/` with capped pluvial depths. Long compute (~tens of minutes); run in the background.

**Files:**
- Produces (gitignored): regenerated `outputs/kuala_lumpur_ssp585_2020/` + summary
- Modify (tracked): `docs/superpowers/runs/2026-06-04-kl-baseline.md` (append a "capped re-run" note) OR a new dated run record

- [ ] **Step 1: Re-run the pipeline (background) with the same hardened flags as Plan 1 Task 7**

Run (bash, background):
```bash
cd /d/GPTs/Projects/flood-v2.0
python scripts/run_city_pipeline.py --city kuala_lumpur \
    --scenario SSP5-8.5 --horizon 2020 --delta-T 0.0 \
    --pluvial-model raingrid --coastal-solver bathtub \
    --no-fit-era5 --no-fit-coastal --no-fit-glofas \
    --no-sea-mask --no-build-river-raster --no-street-overlay \
    --max-ponding-depth-m 3.0 \
    --out-root outputs 2>&1 | tee outputs_kl_baseline_capped.log
```
Expected: completes; prints "Wrote summary: outputs/kuala_lumpur_ssp585_2020/summary_SSP5-8.5_2020.csv".

- [ ] **Step 2: Verify the cap held (the fix worked)**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
python -c "
import pandas as pd
df = pd.read_csv('outputs/kuala_lumpur_ssp585_2020/summary_SSP5-8.5_2020.csv')
p = df[df.hazard_type=='pluvial'][['return_period','flooded_area_km2','max_depth_m']]
print(p.to_string(index=False))
print('MAX pluvial max_depth_m =', p['max_depth_m'].max())
assert p['max_depth_m'].max() <= 3.0 + 1e-6, 'CAP NOT ENFORCED'
print('PASS: pluvial depths capped at 3.0 m')
"
```
Expected: every pluvial `max_depth_m` ≤ 3.0 m (was 4.5 m); assertion passes. **If the assertion fails, STOP** — the wiring didn't take effect; report rather than proceeding.

- [ ] **Step 3: Re-run the monotonicity + mass gate on the capped summary**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
python scripts/check_rp_monotonicity.py \
    --summary outputs/kuala_lumpur_ssp585_2020/summary_SSP5-8.5_2020.csv \
    --domain-km2 3520.2 --max-wet-fraction 0.6
```
Expected: `PASS` (capping reduces depths, not monotonicity).

- [ ] **Step 4: Record the capped re-run** — append a dated section to `docs/superpowers/runs/2026-04-... ` — create `docs/superpowers/runs/2026-06-05-kl-baseline-capped.md` with: the command, the verbatim pluvial summary table (from Step 2), confirmation max ≤ 3.0 m, and the monotonicity PASS. No placeholders — paste real numbers.

- [ ] **Step 5: Commit the record**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
git add docs/superpowers/runs/2026-06-05-kl-baseline-capped.md
git commit -m "chore: record capped KL baseline re-run (pluvial max_depth now <= 3.0 m)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Set the KL hotspot hit-radius to 50 m (geocoding-anchored)

**Context:** The 150 m default (inherited from Singapore's denser-grid geocoding) over-reaches KL's ridge-top dry controls to low cells 100–150 m downslope. KL Nominatim geocoding resolves to ~50–100 m (≈ one city block), so 50 m is the precision-matched window. This is committed as the KL validator's default with the rationale in the code, not passed ad-hoc.

**Files:**
- Modify: `scripts/validate_hotspots_kl.py` (`--radius-m` default 150.0 → 50.0 + rationale comment)
- Test: `tests/test_validate_hotspots_kl.py` (add a default-radius assertion)

- [ ] **Step 1: Write the failing test** — append to `tests/test_validate_hotspots_kl.py`:
```python
def test_kl_default_radius_is_50m_geocoding_anchored():
    # KL Nominatim geocoding resolves to ~one city block; 50 m is the
    # precision-matched window (not 150 m, which is SG's denser-grid default).
    import click
    from scripts.validate_hotspots_kl import cli
    radius_opt = next(p for p in cli.params if p.name == "radius_m")
    assert radius_opt.default == 50.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run (bash): `cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_validate_hotspots_kl.py::test_kl_default_radius_is_50m_geocoding_anchored -q`
Expected: FAIL (default is still 150.0).

- [ ] **Step 3: Change the default radius**

In `scripts/validate_hotspots_kl.py`, change this exact option:
```python
@click.option("--radius-m", type=float, default=150.0, show_default=True)
```
to:
```python
@click.option("--radius-m", type=float, default=50.0, show_default=True,
              help="Hit-radius (m). KL default 50 m matches Nominatim geocoding "
                   "precision (~one city block); SG used 150 m for its denser grid. "
                   "Anchored to geocoding precision, NOT to the gate verdict (see dossier).")
```

- [ ] **Step 4: Run the test to verify it passes**

Run (bash): `cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_validate_hotspots_kl.py -q`
Expected: 3 passed (the 2 gate tests + the new default-radius test).

- [ ] **Step 5: Commit**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
git add scripts/validate_hotspots_kl.py tests/test_validate_hotspots_kl.py
git commit -m "feat: set KL hotspot hit-radius default to 50 m (geocoding-precision-anchored)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Re-validate against the capped baseline

**Context:** With both fixes in place (capped pluvial + 50 m radius), re-run the hotspot validator and capture the honest result. Expectation: the cap removes the Bukit Antarabangsa over-extent and 50 m removes the radius artefacts, so CRR should clear 0.70 while HR holds — but record whatever the numbers actually are.

**Files:**
- Produces: `outputs/kuala_lumpur_ssp585_2020/_validation/combined_rp100.tif` (gitignored)

- [ ] **Step 1: Run the validator at the new defaults and capture verbatim**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
echo "=== default (50 m) ==="; python scripts/validate_hotspots_kl.py --out-dir outputs/kuala_lumpur_ssp585_2020 --rp 100
echo "=== 150 m (for before/after comparison) ==="; python scripts/validate_hotspots_kl.py --out-dir outputs/kuala_lumpur_ssp585_2020 --rp 100 --radius-m 150
```
Capture both verbatim (HR / CRR / TSS+CI / GATE). The 150 m run shows whether the depth-cap alone improved CRR (Bukit Antarabangsa should now correctly reject); the 50 m run is the operational verdict.

- [ ] **Step 2: Sanity-check Bukit Antarabangsa specifically (did the cap fix the over-extent?)**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
python -c "
import sys;sys.path.insert(0,'.')
from scripts.city_manifest import load_hotspots_from_manifest
from scripts.hotspot_scoring import sample_score
c='outputs/kuala_lumpur_ssp585_2020/_validation/combined_rp100.tif'
hs=load_hotspots_from_manifest('kuala_lumpur')
for h in hs:
    if 'Antarabangsa' in h.label:
        print('Bukit Antarabangsa max depth @10m =', round(sample_score(c,h.lon,h.lat,radius_m=10),3),
              '@50m =', round(sample_score(c,h.lon,h.lat,radius_m=50),3))
"
```
Expected (if cap worked): the @10 m depth at Bukit Antarabangsa is now below the 0.10 m threshold (it was wet pre-cap). Record the value.

- [ ] **Step 3: No commit** (this task produces only gitignored outputs + captured numbers for Task 5). Proceed to Task 5.

---

### Task 5: Update the validation dossier with the post-fix verdict

**Context:** Record the honest before/after. If both gates now PASS at 50 m with the cap, state that the model reached a legitimate PASS — and be explicit that it was the two documented fixes (not tuning) that did it. If it still FAILs, record that honestly and carry it to Plan 4.

**Files:**
- Modify: `docs/superpowers/runs/2026-06-05-kl-validation-dossier.md` (add a "## 7. Post-fix re-validation (Plan 3)" section)

- [ ] **Step 1: Append the post-fix section** to `docs/superpowers/runs/2026-06-05-kl-validation-dossier.md` using the REAL captured numbers from Task 4:
  - A before/after table: (pre-fix 150 m: HR 1.00 / CRR 0.43 / FAIL) vs (post-cap 150 m: HR / CRR / verdict) vs (post-cap 50 m: HR / CRR / verdict).
  - State which fix resolved which false-positive: depth-cap → Bukit Antarabangsa (cite the @10 m depth now < 0.10 m); 50 m radius → Mont Kiara / Bukit Kiara / Damansara Heights.
  - The updated two-gate verdict (numeric AND visual). If PASS: "ACCEPTABLE (present-day, hotspot-validated)" with the explicit caveat that TSS remains modest with a wide CI at n=7 (register growth is Plan 4). If still FAIL: record honestly + Plan-4 carry.
  - Do NOT overclaim: the PASS (if any) is for present-day KL pluvial hotspot specificity; coastal=0 (inland), extent-CSI N/A (#17), scenario grid still #16, fluvial RP still un-re-anchored — all remain Plan-4 items.

- [ ] **Step 2: Commit**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
git add docs/superpowers/runs/2026-06-05-kl-validation-dossier.md
git commit -m "docs: KL dossier post-fix re-validation (depth-cap + 50 m radius)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (against the dossier's Plan-3 dispositions):**
- Depth-cap fix (run-record #2) → Tasks 1–2. ✓
- KL 50 m radius (geocoding-anchored) → Task 3. ✓
- Re-validate + honest verdict → Tasks 4–5. ✓
- Scenario regen #16, fluvial re-anchoring, register growth, SSP585-2100, viz → explicitly **Plan 4** (scope note). ✓ (deferred, not dropped)

**2. Placeholder scan:** Code steps show exact edits; run steps show exact commands + expected output + assertions. Tasks 2/4/5 require pasting REAL captured numbers (correct — they don't exist until the re-run). No "TBD".

**3. Consistency:** `max_ponding_depth_m` (run_city_pipeline cli param) → `--pluvial-depth-cap` (run_multihazard option, line 401) → `peak_depth_cap_m` (run_rain_on_grid, line 816) — the chain is verified against the real code. The 50 m default is set in `validate_hotspots_kl.py` and asserted in its test. The re-run command matches Plan-1 Task 7's hardened flags + the new `--max-ponding-depth-m 3.0`.

**Discipline check:** every fix is anchored to a documented fact (the cap is a pre-existing 3.0 m engineering limit; 50 m to geocoding precision). The plan explicitly forbids hunting a third parameter if the gate still fails. ✓

---

## Execution Handoff

Plan 3 of N (gate-closing fixes). After execution: final review → finish branch → Plan 4 (scenario regen #16, fluvial event-RP re-anchoring, register growth, SSP5-8.5 2100, viz).
