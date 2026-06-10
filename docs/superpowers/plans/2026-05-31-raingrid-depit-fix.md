# Raingrid De-Pitted DEM Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the rain-on-grid high-RP depth blow-up by feeding it a surgically de-pitted DEM — fill only sub-sea-level (artifact) and ≥3 m (unphysical) enclosed depressions, preserve genuine shallow hollows — then re-measure against the existing harness.

**Architecture:** One change at the DEM layer. Extract the depression-classification/fill logic in `scripts/build_conditioned_dem.py` into a pure, testable helper `depit_dem(...)`; the existing `_conditioned.tif` output keeps shallow-only fill, and a new `--raingrid-out` emits a variant that additionally fills artifact + deep depressions. `run_city_pipeline.py` builds that variant and points raingrid's `--pluvial-dem-raster` at it. Solver, fill-spill, coastal/fluvial, and scoring params untouched.

**Tech Stack:** Python, numpy, scipy.ndimage (connected-component labelling), rasterio, pysheds (via `model.hand_model.fill_depressions`), click, pytest.

**Spec:** `docs/superpowers/specs/2026-05-31-raingrid-depressionless-dem-design.md`

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `scripts/build_conditioned_dem.py` | DEM conditioning + (new) raingrid de-pitting | Extract `depit_dem` helper; add `--raingrid-out` / `--deep-pit-depth-m` options |
| `tests/test_build_conditioned_dem.py` | Unit tests for `depit_dem` | Create |
| `scripts/run_city_pipeline.py` | Per-city driver | Singapore: build + use the raingrid DEM for raingrid pluvial |

---

## Task 1: Extract `depit_dem` helper + tests

**Files:**
- Modify: `scripts/build_conditioned_dem.py` (extract helper; refactor the shallow-fill block at lines 76–95 to call it)
- Create: `tests/test_build_conditioned_dem.py`

The helper classifies enclosed depressions and fills a selected subset. **Conditioned mode** (`deep_pit_depth_m=None`): fill only shallow noise pits (max depth < `noise_pit_depth_m`) — identical to current behaviour. **Raingrid mode** (`deep_pit_depth_m` set): additionally fill depressions whose floor elevation `< sea_level_m` (DSM artifact) or whose max depth `≥ deep_pit_depth_m` (unphysical).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_conditioned_dem.py
import numpy as np
import pytest
from rasterio.transform import from_origin
from scripts.build_conditioned_dem import depit_dem


def _profile(h, w):
    return {
        "driver": "GTiff", "height": h, "width": w, "count": 1,
        "dtype": "float32", "crs": "EPSG:32648",
        "transform": from_origin(0.0, h * 30.0, 30.0, 30.0),
    }


def _plain_with_pits():
    """20x20 plain at 10 m with 4 single-cell pits (well interior)."""
    dem = np.full((20, 20), 10.0, dtype="float64")
    dem[5, 5] = -5.0    # A: artifact floor (<0), depth 15 m
    dem[5, 15] = 5.0    # B: deep (depth 5 m), floor > 0
    dem[15, 5] = 9.0    # C: shallow real hollow (depth 1 m), floor > 0
    dem[15, 15] = 9.7   # D: noise pit (depth 0.3 m)
    return dem


def test_conditioned_mode_fills_only_noise():
    dem = _plain_with_pits()
    finite = np.ones_like(dem, dtype=bool)
    out, stats = depit_dem(dem, _profile(20, 20), finite,
                           noise_pit_depth_m=0.5, deep_pit_depth_m=None)
    assert out[15, 15] == pytest.approx(10.0, abs=1e-3)   # D noise -> filled
    assert out[5, 5] == pytest.approx(-5.0, abs=1e-3)     # A kept
    assert out[5, 15] == pytest.approx(5.0, abs=1e-3)     # B kept
    assert out[15, 5] == pytest.approx(9.0, abs=1e-3)     # C kept


def test_raingrid_mode_fills_artifact_and_deep_keeps_shallow():
    dem = _plain_with_pits()
    finite = np.ones_like(dem, dtype=bool)
    out, stats = depit_dem(dem, _profile(20, 20), finite,
                           noise_pit_depth_m=0.5, deep_pit_depth_m=3.0,
                           sea_level_m=0.0)
    assert out[5, 5] == pytest.approx(10.0, abs=1e-3)     # A artifact -> filled
    assert out[5, 15] == pytest.approx(10.0, abs=1e-3)    # B deep -> filled
    assert out[15, 15] == pytest.approx(10.0, abs=1e-3)   # D noise -> filled
    assert out[15, 5] == pytest.approx(9.0, abs=1e-3)     # C shallow real -> KEPT


def test_raingrid_mode_has_no_artifact_or_deep_pits_left():
    dem = _plain_with_pits()
    finite = np.ones_like(dem, dtype=bool)
    out, _ = depit_dem(dem, _profile(20, 20), finite,
                       noise_pit_depth_m=0.5, deep_pit_depth_m=3.0, sea_level_m=0.0)
    # No remaining cell below sea level; no remaining pit deeper than 3 m.
    from model.hand_model import fill_depressions
    filled = fill_depressions(out, _profile(20, 20)).astype(np.float64)
    residual_depth = filled - out
    assert out.min() >= 0.0 - 1e-6
    assert residual_depth.max() < 3.0


def test_nondepression_terrain_unchanged():
    dem = _plain_with_pits()
    finite = np.ones_like(dem, dtype=bool)
    out, _ = depit_dem(dem, _profile(20, 20), finite,
                       noise_pit_depth_m=0.5, deep_pit_depth_m=3.0)
    assert out[0, 0] == pytest.approx(10.0, abs=1e-3)     # plain cell untouched
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_build_conditioned_dem.py -v`
Expected: FAIL — `ImportError: cannot import name 'depit_dem'`.

- [ ] **Step 3: Add the `depit_dem` helper to `scripts/build_conditioned_dem.py`**

Add this module-level function (after the imports, before `cli`). Move the `from model.hand_model import fill_depressions` import to module level (top of file, after the existing imports) so the helper and CLI share it:

```python
def depit_dem(dem, profile, finite, *, noise_pit_depth_m=0.5,
              deep_pit_depth_m=None, sea_level_m=0.0):
    """Classify enclosed depressions and fill a selected subset.

    Always fills shallow noise pits (max depth < ``noise_pit_depth_m``).
    When ``deep_pit_depth_m`` is not None (raingrid mode), ALSO fills any
    depression whose floor elevation < ``sea_level_m`` (DSM artifact) or whose
    max depth >= ``deep_pit_depth_m`` (unphysical). Genuine shallow hollows
    (floor >= sea level, depth in [noise, deep)) are preserved.

    Returns (out_dem float64, stats dict).
    """
    work = np.where(finite, dem, np.nan)
    filled = fill_depressions(work, profile).astype(np.float64)
    pit_depth = np.where(finite, filled - dem, 0.0)
    pit_depth[~np.isfinite(pit_depth)] = 0.0

    labels, n = ndimage.label(pit_depth > 0.0, structure=np.ones((3, 3), dtype=int))
    out = dem.copy()
    stats = {"n_depressions": int(n), "n_shallow": 0, "n_artifact": 0, "n_deep": 0,
             "n_filled_cells": 0}
    if n:
        idx = range(1, n + 1)
        max_depth = np.asarray(ndimage.maximum(pit_depth, labels, idx))
        floor = np.asarray(ndimage.minimum(dem, labels, idx))
        shallow = max_depth < noise_pit_depth_m
        fill = shallow.copy()
        stats["n_shallow"] = int(shallow.sum())
        if deep_pit_depth_m is not None:
            artifact = floor < sea_level_m
            deep = max_depth >= deep_pit_depth_m
            fill = shallow | artifact | deep
            stats["n_artifact"] = int(artifact.sum())
            stats["n_deep"] = int(deep.sum())
        fill_labels = np.flatnonzero(fill) + 1
        mask = np.isin(labels, fill_labels)
        out = np.where(mask, filled, dem)
        stats["n_filled_cells"] = int(mask.sum())
    return out, stats
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_build_conditioned_dem.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Refactor the CLI shallow-fill block to use the helper (preserve `_conditioned` behaviour)**

In `cli()`, replace the existing block (current lines ~76–95, from the comment `# 3. Shallow-pit fill:` through the `click.echo(... real basins)` call) with:

```python
    # 3. Shallow-pit fill (conditioned output): fill only noise pits.
    dem, stats = depit_dem(dem, profile, finite,
                           noise_pit_depth_m=noise_pit_depth_m, deep_pit_depth_m=None)
    click.echo(
        f"Conditioned: filled {stats['n_filled_cells']:,} cells in "
        f"{stats['n_shallow']:,}/{stats['n_depressions']:,} shallow noise pits "
        f"(<{noise_pit_depth_m} m); kept {stats['n_depressions'] - stats['n_shallow']:,} basins")
```

Also remove the now-redundant local `from model.hand_model import fill_depressions` inside `cli()` (it is now imported at module level).

- [ ] **Step 6: Run tests + a regression check that conditioned output is unchanged behaviour**

Run: `python -m pytest tests/test_build_conditioned_dem.py tests/test_pluvial_rain.py -v`
Expected: PASS. (The conditioned path now routes through `depit_dem` with `deep_pit_depth_m=None`, which fills exactly the shallow pits as before.)

- [ ] **Step 7: Commit**

```bash
git add scripts/build_conditioned_dem.py tests/test_build_conditioned_dem.py
git commit -m "refactor(dem): extract depit_dem helper; raingrid de-pitting logic"
```

---

## Task 2: Add `--raingrid-out` / `--deep-pit-depth-m` CLI options

**Files:**
- Modify: `scripts/build_conditioned_dem.py` (add options + emit second output)

- [ ] **Step 1: Add the two click options**

Add to the `cli` decorator stack (after the existing `--noise-pit-depth-m` option):

```python
@click.option("--raingrid-out", "raingrid_out", type=click.Path(path_type=Path),
              default=None,
              help="If set, also emit a surgically de-pitted DEM for rain-on-grid "
                   "(fills artifact + deep depressions; keeps shallow real hollows).")
@click.option("--deep-pit-depth-m", type=float, default=3.0, show_default=True,
              help="Raingrid: fill depressions whose max depth >= this (m). "
                   "Anchored to the validate_pluvial_singapore engineering cap.")
@click.option("--sea-level-m", type=float, default=0.0, show_default=True,
              help="Raingrid: fill depressions whose floor elevation < this (m, "
                   "sub-sea-level land = DSM artifact).")
```

and add the parameters to the `def cli(...)` signature: `raingrid_out: Path, deep_pit_depth_m: float, sea_level_m: float`.

- [ ] **Step 2: Emit the raingrid output (after the conditioned DEM is written, before the final echo)**

Insert just before the closing `click.echo(f"Wrote conditioned DEM: {output_path}")`:

```python
    if raingrid_out is not None:
        # Surgical de-pitting for rain-on-grid: start from the conditioned dem
        # (shallow already filled) and additionally fill artifact + deep pits.
        rg, rg_stats = depit_dem(dem, profile, finite,
                                 noise_pit_depth_m=noise_pit_depth_m,
                                 deep_pit_depth_m=deep_pit_depth_m,
                                 sea_level_m=sea_level_m)
        rg_out = rg.astype(np.float32)
        if nodata is not None:
            rg_out[~finite] = nodata
        Path(raingrid_out).parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(raingrid_out, "w", **profile) as dst:
            dst.write(rg_out, 1)
        click.echo(
            f"Wrote raingrid DEM: {raingrid_out} "
            f"(filled {rg_stats['n_artifact']:,} artifact + {rg_stats['n_deep']:,} deep "
            f"depressions; deep>= {deep_pit_depth_m} m, floor< {sea_level_m} m)")
```

Note: `dem` at this point is the conditioned (shallow-filled) DEM, and `profile` was already updated to float32/deflate when writing the conditioned output — reuse it as-is.

- [ ] **Step 3: Smoke-test on the real Singapore bare-earth DEM**

Run:
```bash
python scripts/build_conditioned_dem.py \
  --dem data/singapore/copernicus_dem_utm48n_bareearth.tif \
  --drainage-raster data/singapore/river_mask_osm_utm48n.tif \
  --sea-mask data/singapore/sea_mask_utm48n.tif \
  --output cache/dem/sg_conditioned_check.tif \
  --raingrid-out cache/dem/sg_raingrid_check.tif
```
Expected: writes both files; the raingrid echo reports a non-zero count of artifact + deep depressions filled.

- [ ] **Step 4: Verify the raingrid DEM has no artifact/deep pits left**

Run:
```bash
python -c "
import numpy as np, rasterio, sys; sys.path.insert(0,'.')
from model.hand_model import fill_depressions
with rasterio.open('cache/dem/sg_raingrid_check.tif') as ds:
    d=ds.read(1).astype('float64'); prof=ds.profile
    nod=ds.nodata
fin=np.isfinite(d) & (d!=nod if nod is not None else True)
filled=fill_depressions(np.where(fin,d,np.nan),prof).astype('float64')
resid=np.where(fin,filled-d,0.0)
print('max residual pit depth (m):', round(float(np.nanmax(resid)),2))
print('land cells < 0 m:', int((fin&(d<0)).sum()))
"
```
Expected: max residual pit depth < 3.0 m and land cells < 0 m == 0 (artifact holes removed). Shallow hollows (<3 m) may remain — that is intended.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_conditioned_dem.py
git commit -m "feat(dem): --raingrid-out emits surgically de-pitted DEM for rain-on-grid"
```

---

## Task 3: Wire the raingrid DEM into the Singapore pipeline

**Files:**
- Modify: `scripts/run_city_pipeline.py` (the conditioned-DEM build block, ~lines 792–810, and `pluvial_dem_raster` assignment ~line 800)

- [ ] **Step 1: Read the current conditioned-DEM build block**

Run: `sed -n '790,812p' scripts/run_city_pipeline.py`
Expected: shows the `build_conditioned_dem.py` invocation that sets `pluvial_dem_raster = dem_path.with_name(dem_path.stem + "_conditioned.tif")` and runs the build command.

- [ ] **Step 2: Add a raingrid DEM path and pass `--raingrid-out` to the build command**

In that block, after the line that sets `pluvial_dem_raster = dem_path.with_name(dem_path.stem + "_conditioned.tif")`, add:

```python
        raingrid_dem = dem_path.with_name(dem_path.stem + "_raingrid.tif")
```

and in the `build_conditioned_dem.py` argument list (the `_run([...])` call that builds the conditioned DEM), append:

```python
            "--raingrid-out", str(raingrid_dem),
```

Then, after that `_run(...)` completes, repoint the raingrid pluvial DEM:

```python
        # Rain-on-grid uses the surgically de-pitted DEM (artifact + >=3 m pits
        # filled) to prevent unbounded ponding in DSM holes; fill-spill keeps
        # the _conditioned DEM. See specs/2026-05-31-raingrid-depressionless-dem-design.md
        if raingrid_dem.exists():
            pluvial_dem_raster = raingrid_dem
```

- [ ] **Step 3: Verify the wiring (dry inspection)**

Run: `grep -n "raingrid_dem\|raingrid-out\|pluvial_dem_raster" scripts/run_city_pipeline.py`
Expected: shows `raingrid_dem` defined, passed via `--raingrid-out`, and assigned to `pluvial_dem_raster` after the build.

- [ ] **Step 4: Commit**

```bash
git add scripts/run_city_pipeline.py
git commit -m "feat(pipeline): Singapore raingrid uses surgically de-pitted DEM"
```

---

## Task 4: Re-measure (the acceptance gate)

**Files:** none modified — rebuild the raingrid DEM, re-run the pluvial pipeline, re-run the four checks, record results.

- [ ] **Step 1: Build the Singapore raingrid DEM**

Run:
```bash
python scripts/build_conditioned_dem.py \
  --dem data/singapore/copernicus_dem_utm48n_bareearth.tif \
  --drainage-raster data/singapore/river_mask_osm_utm48n.tif \
  --sea-mask data/singapore/sea_mask_utm48n.tif \
  --output data/singapore/copernicus_dem_utm48n_conditioned.tif \
  --raingrid-out data/singapore/copernicus_dem_utm48n_raingrid.tif
```
Expected: writes `data/singapore/copernicus_dem_utm48n_raingrid.tif`; echo reports artifact + deep pits filled. (Both DEM files are gitignored data products — not committed.)

- [ ] **Step 2: Re-run the pluvial raingrid sweep on the de-pitted DEM**

Run (mirrors the Task-8 invocation but with the raingrid DEM):
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
Expected: all 9 RP rasters re-written under `outputs/singapore_ssp585_2100/pluvial/rp_*`.

- [ ] **Step 3: Gate 1–2 — depth band + monotonicity (must now PASS)**

Run: `python scripts/validate_pluvial_singapore.py --out-dir outputs/singapore_ssp585_2100`
Expected: exit 0; max depths monotone and RP1000 within [0.38, 3.0] m. If it still FAILs, do NOT tweak: follow the spec §3 escalation (lower `--deep-pit-depth-m`, pre-registered) and re-run.

- [ ] **Step 4: Gate 3–4 — comparative hotspot TSS (must not regress)**

Run:
```bash
python scripts/validate_pluvial_hotspots_singapore.py \
  --out-dir outputs/singapore_ssp585_2100 --rp 50 \
  --naive cache/baselines/naive_twi_sg.tif \
  --aqueduct cache/aqueduct/aqueduct_sg_rp50.tif
```
Expected: hotspot hit-rate ≥ 0.70 (was 0.80). Record the new HR/CRR/TSS for all three sources.

- [ ] **Step 5: HWM point check**

Run: `python scripts/validate_hwm_points.py`
Expected: the Singapore pluvial points (Liat Towers, Bukit Timah) print verdicts; record whether the OVER verdicts (max ~1.7 m before the fix) move toward IN-BAND.

- [ ] **Step 6: Record results + resolve limitation #8**

Update `docs/limitations_register.md`: mark finding #8 resolved (or update with the new numbers if partially improved), and note the before/after max-depth curve. Commit:

```bash
git add docs/limitations_register.md
git commit -m "docs: record raingrid de-pit re-measurement; resolve limitation #8"
```

If gates 1–2 pass and gate-3 hit-rate ≥ 0.70, run the §11 visual-QA checklist as the final coherence veto before declaring the pluvial map done.

---

## Self-Review (completed during planning)

- **Spec coverage:** §2.1 fill criteria (artifact floor <0, deep ≥3 m, keep [0.5,3) m) → Task 1 `depit_dem` + tests; §2.2 where (build_conditioned_dem helper + `--raingrid-out`, pipeline wiring) → Tasks 1–3; §3 acceptance (gates 1–2 pass, gate-3 no regression, HWM, visual) → Task 4; §3.1 tests (artifact/deep filled, shallow kept, no residual artifact/deep, terrain unchanged) → Task 1 four tests; §3 escalation → Task 4 Step 2 note. All covered.
- **Placeholder scan:** no TBD/TODO; every code step shows complete code; the smoke/verify commands have concrete expected outputs.
- **Type/name consistency:** `depit_dem(dem, profile, finite, *, noise_pit_depth_m, deep_pit_depth_m, sea_level_m)` and its `stats` keys (`n_depressions`, `n_shallow`, `n_artifact`, `n_deep`, `n_filled_cells`) are used identically in Tasks 1 and 2; `raingrid_dem` / `--raingrid-out` / `pluvial_dem_raster` consistent across Tasks 2–4.
