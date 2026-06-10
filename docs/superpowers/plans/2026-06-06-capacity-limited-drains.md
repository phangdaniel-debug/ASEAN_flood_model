# Capacity-Limited Drains for the Raingrid Pluvial (Plan 6 of N)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix limitation #19 at root — the raingrid treats every drainage cell as an **infinite sink**, so flood-prone spots beside a drain (Old Klang Road, by Sungai Klang) over-drain to 0.00 m. Make drains **finite-capacity**: an outlet conveys water away up to a documented drain capacity; when overwhelmed, the excess ponds (the drain backs up → adjacent flooding, as in reality). Target: keep Plan 5's over-extent gain (Bukit Antarabangsa stays drained) AND restore the over-drained real flood spots (Old Klang Road floods again) → a clean, *real* PASS.

**The exact change:** in `model/pluvial_rain_model.py::run_rain_on_grid`, the outlet step is currently `d_new[outlet_mask] = 0.0` (line ~320, "Outlets are perfect sinks"). Replace with a rate-limited removal: remove up to `drain_conveyance_m_s * dt` of depth per step at outlet cells; the remainder stays (ponds). `drain_conveyance_m_s = None` preserves the perfect-sink default (back-compat).

**Discipline guards (hard-won):**
- The conveyance rate is **calibrated to a documented drain capacity** (KL/MSMA monsoon-drain design → Manning conveyance → per-cell depth-removal rate), **NOT** tuned to whatever makes the gate pass (forbidden loop, Plan 3 lesson).
- Verify the fix is **real, not cosmetic**: it must restore Old Klang Road (HR up) **while keeping** Bukit Antarabangsa drained (CRR held) and the extent reduced. A value that re-broadens the whole extent (capacity too low → infinite-sink behaviour lost) or that doesn't restore Old Klang Road (capacity too high → still ~infinite sink) is not the answer — but the *selection criterion is the documented capacity*, not the gate.

**Perf reality (limitation #18, unsolved):** each KL raingrid re-run is ~3 h, so calibration cannot sweep many values cheaply. Compute ONE conveyance value analytically from a documented drain spec, run once, and judge. If it misses, iterate sparingly — each iteration anchored to a documented capacity, never to the gate.

**Re-run mechanics:** use the offline direct `run_multihazard` (Plan 4/5 pattern; AR6 re-fetch still breaks the full pipeline) with `--tidal-channel-raster data/kuala_lumpur/drainage_waterways_utm47n.tif` (committed dense drainage) + the drain-burned raingrid DEM.

**Tech Stack:** Python 3, numpy, numba, rasterio, click, pytest.

**Scope:** the drain-capacity model change + KL calibration + validation only. Deferred: register growth (n≥15), #16 regen, fluvial RP re-anchoring, SSP5-8.5 2100 + viz, AR6 offline-repeatability.

---

### Task 1: Capacity-limited outlet in `run_rain_on_grid` (TDD)

**Files:**
- Modify: `model/pluvial_rain_model.py` (`run_rain_on_grid` signature + outlet step)
- Test: `tests/test_drain_capacity.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_drain_capacity.py`:
```python
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.pluvial_rain_model import run_rain_on_grid


def _flat_with_one_drain(n=30):
    # flat basin, a single drain cell in the centre; closed boundary
    z = np.zeros((n, n), dtype=np.float64)
    outlet = np.zeros((n, n), dtype=bool)
    outlet[n // 2, n // 2] = True
    return z, outlet


def test_high_conveyance_matches_perfect_sink():
    z, outlet = _flat_with_one_drain()
    kw = dict(net_rain_depth_m=0.05, n=0.05, storm_duration_s=600.0,
              total_duration_s=1800.0, dx=30.0, dy=30.0, verbose=False,
              open_boundary=False)
    sink = run_rain_on_grid(z, outlet, **kw)                       # default: perfect sink
    fast = run_rain_on_grid(z, outlet, drain_conveyance_m_s=10.0, **kw)  # huge capacity
    # a very large conveyance behaves ~ like a perfect sink at the drain cell
    assert abs(float(sink["peak_depth"][15, 15]) - float(fast["peak_depth"][15, 15])) < 0.02


def test_finite_conveyance_ponds_at_overwhelmed_drain():
    z, outlet = _flat_with_one_drain()
    kw = dict(net_rain_depth_m=0.20, n=0.05, storm_duration_s=600.0,
              total_duration_s=1800.0, dx=30.0, dy=30.0, verbose=False,
              open_boundary=False)
    sink = run_rain_on_grid(z, outlet, **kw)                          # perfect sink
    limited = run_rain_on_grid(z, outlet, drain_conveyance_m_s=1e-5, **kw)  # tiny capacity
    # a tiny conveyance can't shed the inflow -> the drain cell ponds (depth > sink case)
    assert float(limited["peak_depth"][15, 15]) > float(sink["peak_depth"][15, 15]) + 0.01
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_drain_capacity.py -q`
Expected: FAIL — `unexpected keyword argument 'drain_conveyance_m_s'`.

- [ ] **Step 3: Implement** — add `drain_conveyance_m_s: float | None = None` to the `run_rain_on_grid` signature (after `convergence`/`peak_depth_cap_m` params), and replace the outlet step (currently lines ~319–320):
```python
        # Outlets are perfect sinks; nodata stays dry.
        d_new[outlet_mask] = 0.0
```
with:
```python
        # Outlets convey water away. Default: perfect sink. If a finite drain
        # conveyance is set, remove only up to drain_conveyance_m_s*dt of depth
        # per step; the remainder ponds (the drain is overwhelmed and backs up,
        # flooding adjacent ground — e.g. Old Klang Road by Sungai Klang).
        if drain_conveyance_m_s is None:
            d_new[outlet_mask] = 0.0
        else:
            d_new[outlet_mask] = np.maximum(
                0.0, d_new[outlet_mask] - drain_conveyance_m_s * dt)
```
(Keep `d_new[~finite] = 0.0` on the next line.) NOTE: `_adaptive_dt(..., sea_mask=outlet_mask)` still treats outlets specially for the timestep — leave it; if stability degrades with finite conveyance, report it rather than silently changing the CFL.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_drain_capacity.py -q`
Expected: PASS (2 passed). If `test_high_conveyance_matches_perfect_sink` is borderline, adjust ONLY the conveyance magnitude / tolerance in the test (not the solver) so the intent holds; report it.

- [ ] **Step 5: No regression + commit**

Run: `cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/ -q 2>&1 | tail -3` (expect 212/1).
```bash
git add model/pluvial_rain_model.py tests/test_drain_capacity.py
git commit -m "feat: capacity-limited drains in run_rain_on_grid (finite conveyance; default perfect-sink) — limitation #19

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Forward `--drain-conveyance-m-s` through run_multihazard

**Files:** Modify `scripts/run_multihazard.py` (CLI option + pass to the `run_rain_on_grid` call ~line 809).

- [ ] **Step 1:** Add the option near the raingrid options:
```python
@click.option("--drain-conveyance-m-s", "drain_conveyance_m_s", type=float, default=None,
              help="Finite drain conveyance (m/s of depth shed per outlet cell per second). "
                   "Omit for perfect-sink drains. Calibrated to documented drain capacity (limitation #19).")
```
Add `drain_conveyance_m_s: float | None,` to `cli(...)`, and pass `drain_conveyance_m_s=drain_conveyance_m_s,` into the `run_rain_on_grid(...)` call (after `peak_depth_cap_m=...`).

- [ ] **Step 2:** Verify import + `--help` shows it + suite green. Commit:
```bash
cd /d/GPTs/Projects/flood-v2.0
python -c "import sys;sys.path.insert(0,'.');import scripts.run_multihazard;print('OK')"
python scripts/run_multihazard.py --help 2>&1 | grep drain-conveyance
git add scripts/run_multihazard.py
git commit -m "feat: --drain-conveyance-m-s passthrough to run_rain_on_grid

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Compute the conveyance anchor from a documented drain spec (analytical — no re-run)

**Files:** Create `docs/superpowers/runs/2026-06-06-drain-conveyance-anchor.md`

- [ ] **Step 1:** Source a representative KL/MSMA monsoon-drain design (cross-section: width, depth, slope, Manning's n — e.g. MSMA secondary-drain typical section). Compute its Manning conveyance Q (m³/s), then the **per-cell depth-shed rate** = Q / (cell area = 30×30 = 900 m²) → `drain_conveyance_m_s`. Show the calculation + cite the MSMA section. Record the resulting value (one number). **This is the conveyance — chosen from the documented drain, not the gate.** Commit the record.

---

### Task 4: Single offline re-run with finite drains (background)

- [ ] **Step 1:** Back up the current (infinite-sink dense-drainage) pluvial rasters to `outputs/_ref_infinitesink_pluvial/`.
- [ ] **Step 2:** Run offline `run_multihazard` (the Plan-5 dense-drainage command) **plus** `--drain-conveyance-m-s <value from Task 3>`. Long (~3 h); background. Confirm completion + cap ≤ 3.0 m + monotonicity.

---

### Task 5: Validate — does it fix the over-drain without losing the over-extent gain?

- [ ] **Step 1:** Run `validate_hotspots_kl.py --rp 100`; capture HR/CRR/TSS+CI/GATE.
- [ ] **Step 2 (the decisive per-spot check):** confirm **Old Klang Road floods again** (the #19 over-drain fixed) AND **Bukit Antarabangsa stays drained** (Plan-5 over-extent gain kept). Use `sample_score` at both pins (as in the Plan-5 diagnostic). Report both.
- [ ] **Step 3:** Compare extent vs the infinite-sink reference (should be slightly broader — overwhelmed drains pond — but far below the sparse-drainage extent). Honest verdict: did finite drains give a clean, *real* PASS (HR ≥ 0.70 AND CRR held), or partially?

---

### Task 6: Document — dossier §9 + limitation #19 update

- [ ] **Step 1:** Append dossier §9: the finite-drain model, the documented conveyance anchor, the before/after (infinite-sink vs finite-drain: HR/CRR/TSS + Old Klang Road + Bukit Antarabangsa), the honest verdict. Update limitation #19 status (resolved / improved / residual). Commit.

---

## Self-Review

**1. Spec coverage:** drain-capacity model change (Tasks 1–2) → documented conveyance anchor (Task 3) → single re-run (Task 4) → decisive validation incl. the two named spots (Task 5) → document (Task 6). ✓
**2. Placeholder scan:** the exact code change is shown (outlet-step replacement) + TDD; the conveyance value is computed from a documented drain in Task 3 (a real number + citation, not invented). Run steps show commands + expected checks. ✓
**3. Discipline:** conveyance anchored to a documented drain capacity NOT the gate (Plan 3 lesson); fix verified real via the named-spot check + over-draining guard (Plan 4/5 lesson); perf-limited iteration acknowledged (#18); offline re-run (AR6 flakiness). ✓

## Execution Handoff

Plan 6 of N. After execution: final review → finish branch → remaining work (register growth n≥15; #16 regen; fluvial RP re-anchoring — would also help Taman Sri Muda; SSP5-8.5 2100 + viz; AR6 offline-repeatability).
