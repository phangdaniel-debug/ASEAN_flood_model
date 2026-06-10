# Raingrid Open-Boundary Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an open (transmissive) boundary to the rain-on-grid solver so runoff routed to the clipped-domain edge exits the map, eliminating the residual high-RP boundary artefact, then re-measure to close the pluvial depth-band gate for Singapore.

**Architecture:** One parameter, `open_boundary=True`, added to `run_rain_on_grid` in `model/pluvial_rain_model.py`. At setup it folds the outermost ring of finite cells into the existing `outlet_mask`, so the existing per-step `d_new[outlet_mask] = 0.0` drains the edge. No kernel, rainfall-source, or pipeline change. Then rebuild the Singapore raingrid DEM at the default 3.0 m de-pit threshold and re-run the four validators.

**Tech Stack:** Python, numpy, pytest (`tests/test_pluvial_rain.py` is the existing test home).

**Spec:** `docs/superpowers/specs/2026-05-31-raingrid-open-boundary-design.md`

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `model/pluvial_rain_model.py` | Rain-on-grid solver | Add `open_boundary: bool = True` param + edge-outlet setup |
| `tests/test_pluvial_rain.py` | Solver unit tests | Add open-boundary tests |

---

## Task 1: Open-boundary parameter in `run_rain_on_grid`

**Files:**
- Modify: `model/pluvial_rain_model.py` (signature ~line 176–189; setup ~line 230–233)
- Test: `tests/test_pluvial_rain.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pluvial_rain.py` (it already imports `numpy as np` and `from model.pluvial_rain_model import run_rain_on_grid`; if not, add those imports at the top):

```python
def _ramp_plane(rows=30, cols=30, slope=0.5):
    """Plane sloping down toward the bottom edge (row -1); higher at top."""
    z = np.empty((rows, cols), dtype=np.float64)
    for i in range(rows):
        z[i, :] = (rows - 1 - i) * slope  # row 0 highest, last row = 0
    return z

def test_open_boundary_drains_edge():
    z = _ramp_plane()
    no_outlet = np.zeros(z.shape, dtype=bool)  # no sea/river outlets at all
    res_open = run_rain_on_grid(
        z, no_outlet, 0.2, 0.05,
        storm_duration_s=600.0, total_duration_s=900.0, dt_max=10.0,
        verbose=False, open_boundary=True,
    )
    res_closed = run_rain_on_grid(
        z, no_outlet, 0.2, 0.05,
        storm_duration_s=600.0, total_duration_s=900.0, dt_max=10.0,
        verbose=False, open_boundary=False,
    )
    peak_open = res_open["peak_depth"]
    # With an open boundary, the draining edge ring stays ~dry...
    assert np.nanmax(peak_open[-1, :]) < 0.05
    # ...and the domain peak is strictly lower than with a closed wall.
    assert np.nanmax(peak_open) < np.nanmax(res_closed["peak_depth"])

def test_open_boundary_default_on():
    z = _ramp_plane()
    no_outlet = np.zeros(z.shape, dtype=bool)
    res_default = run_rain_on_grid(
        z, no_outlet, 0.2, 0.05,
        storm_duration_s=600.0, total_duration_s=900.0, dt_max=10.0,
        verbose=False,
    )
    # Default behaviour == open_boundary=True: bottom edge drains to ~0.
    assert np.nanmax(res_default["peak_depth"][-1, :]) < 0.05
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_pluvial_rain.py -k open_boundary -v`
Expected: FAIL — `TypeError: run_rain_on_grid() got an unexpected keyword argument 'open_boundary'`.

- [ ] **Step 3: Add the parameter to the signature**

In `model/pluvial_rain_model.py`, add `open_boundary: bool = True` to the keyword-only block of `run_rain_on_grid` (after `verbose: bool = True,`):

```python
    progress_interval: int = 500,
    verbose: bool = True,
    open_boundary: bool = True,
) -> dict:
```

- [ ] **Step 4: Implement the edge-outlet setup**

In `run_rain_on_grid`, the setup currently reads:

```python
    rows, cols = z.shape
    finite = np.isfinite(z)
    outlet_mask = outlet_mask.astype(bool) & finite
    land = finite & ~outlet_mask
```

Replace it with (insert the open-boundary block between the `outlet_mask` and `land` lines):

```python
    rows, cols = z.shape
    finite = np.isfinite(z)
    outlet_mask = outlet_mask.astype(bool) & finite
    if open_boundary:
        # Clipped-domain edge is an open (transmissive) boundary: runoff routed
        # to the map edge exits the domain rather than piling against the
        # array's no-flux wall. The outermost ring of finite cells drains every
        # step via the existing outlet handling.
        border = np.zeros(z.shape, dtype=bool)
        border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
        outlet_mask = outlet_mask | (border & finite)
    land = finite & ~outlet_mask
```

- [ ] **Step 5: Document the parameter**

Add to the `run_rain_on_grid` docstring Parameters section, after the `verbose` entry:

```python
    open_boundary : bool
        If True (default), the outermost ring of finite cells acts as a
        free-drainage outlet, representing flow leaving the clipped domain.
        Prevents runoff from piling against the array edge (a wall artefact of
        the finite domain). Set False for a deliberately closed domain.
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_pluvial_rain.py -k open_boundary -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Run the full solver test file (regression)**

Run: `python -m pytest tests/test_pluvial_rain.py -v`
Expected: all pass (the new 2 plus the pre-existing solver tests). If a pre-existing test assumed edge accumulation and now fails, inspect it: the open boundary is the intended new default, so update that test to pass `open_boundary=False` if it is specifically exercising closed-domain behaviour, and note it in the report.

- [ ] **Step 8: Commit**

```bash
git add model/pluvial_rain_model.py tests/test_pluvial_rain.py
git commit -m "feat(pluvial): open-boundary outlet in run_rain_on_grid (clipped-edge fix)"
```

---

## Task 2: Acceptance re-measure (close the pluvial gate)

**Files:** none modified — rebuild the raingrid DEM at the default 3.0 m de-pit, re-run the pluvial sweep, run the validators, record.

- [ ] **Step 1: Rebuild the Singapore raingrid DEM at the default 3.0 m threshold**

Run:
```bash
python scripts/build_conditioned_dem.py \
  --dem data/singapore/copernicus_dem_utm48n_bareearth.tif \
  --drainage-raster data/singapore/river_mask_osm_utm48n.tif \
  --sea-mask data/singapore/sea_mask_utm48n.tif \
  --output data/singapore/copernicus_dem_utm48n_conditioned.tif \
  --raingrid-out data/singapore/copernicus_dem_utm48n_raingrid.tif \
  --deep-pit-depth-m 3.0
```
Expected: echo reports "filled 80 artifact + 448 deep depressions; deep>= 3.0 m". (Reverts the 2.0 m escalation; lighter fill preserves more genuine shallow hollows.)

- [ ] **Step 2: Re-run the Singapore pluvial sweep (now with the open boundary)**

Run:
```bash
python scripts/run_multihazard.py \
  --dem data/singapore/copernicus_dem_utm48n.tif \
  --hazard-levels data/singapore/hazard_levels_ssp585_2100.csv \
  --scenario SSP5-8.5 --horizon 2100 \
  --out-dir outputs/singapore_ssp585_2100 \
  --only-hazard-types pluvial --pluvial-model raingrid \
  --pluvial-dem-raster data/singapore/copernicus_dem_utm48n_raingrid.tif \
  --sea-mask-raster data/singapore/sea_mask_utm48n.tif \
  --tidal-channel-raster data/singapore/river_mask_utm48n.tif \
  --tidal-burn-elevation 2.0 \
  --runoff-coeff-raster data/singapore/runoff_coeff_utm48n.tif \
  --runoff-coeff 0.75
```
Expected: all nine `pluvial/rp_*` rasters re-written. (`run_multihazard` calls `run_rain_on_grid`, which now defaults to `open_boundary=True`.)

- [ ] **Step 3: Gate 1–2 — must now PASS**

Run: `python scripts/validate_pluvial_singapore.py --out-dir outputs/singapore_ssp585_2100`
Expected: exit 0 — max depth monotone non-decreasing and RP1000 ≤ 3.0 m. Record the full RP→max-depth row. If RP1000 still exceeds 3.0 m, do NOT tweak: re-inspect where the max cell now sits (interior vs edge) and report for a fresh diagnosis.

- [ ] **Step 4: Gate 3 — hit-rate no regression**

Run:
```bash
python scripts/validate_pluvial_hotspots_singapore.py \
  --out-dir outputs/singapore_ssp585_2100 --rp 50 \
  --naive cache/baselines/naive_twi_sg.tif \
  --aqueduct cache/aqueduct/aqueduct_sg_rp50.tif
```
Expected: hit-rate ≥ 0.70 (≈ 0.80). Record the HR / CRR / TSS for all three sources.

- [ ] **Step 5: HWM check**

Run: `python scripts/validate_hwm_points.py`
Expected: Singapore pluvial points (Liat Towers, Bukit Timah) remain IN-BAND. Record.

- [ ] **Step 6: Update the paper + limitations register, commit**

In `docs/paper/methodology_singapore.md`: add the final post-open-boundary row to Table 4 (the RP→max-depth values from Step 3), update the §5 status note to reflect gate 1–2 PASS, and update §5.2 to state the boundary artefact is resolved. In `docs/limitations_register.md`: mark #8b resolved with the open-boundary fix.

```bash
git add docs/paper/methodology_singapore.md docs/limitations_register.md
git commit -m "docs: open-boundary closes pluvial gate 1-2; record final depth curve; resolve #8b"
```

- [ ] **Step 7: Visual gate (§11 checklist)**

Only after Steps 3–5 pass: run the fixed visual-QA checklist (monotone area/depth, sane wet-area fraction, hazard separation, no domain-wide sheet/speckle/spikes, hotspots lit / dry ground dry, coastline behaves) against the pluvial rasters as the final coherence veto. Record pass/fail per item; a failed item opens a ticket (conversion rule), not a tweak.

---

## Self-Review (completed during planning)

- **Spec coverage:** §2 fix (param + edge-outlet setup, default on, scoped to `run_rain_on_grid`) → Task 1 Steps 3–5; §3.1 unit tests (edge drains, default on, regression) → Task 1 Steps 1,6,7; §3.2 acceptance re-measure (rebuild @3.0 m, gates 1–2/3, HWM, visual) → Task 2; §3.3 on-success (resolve #8b, update paper) → Task 2 Step 6. All covered.
- **Placeholder scan:** no TBD/TODO; every code step shows complete code; commands have concrete expected output.
- **Type/name consistency:** `open_boundary` (bool, default True) used identically in signature, setup, docstring, and all tests; `run_rain_on_grid` kwargs match the existing signature; DEM/raster paths match Task-2 commands and the prior runs.
