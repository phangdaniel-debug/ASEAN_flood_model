# KL Foundation (Plan 1 of 3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up `flood-v2.0` seeded from the validated `flood-atlas` Singapore model, formalize the four-manifest homogeneity contract, apply the two cheap forward-looking fixes (depth-aware pluvial floor + scenario-forcing consistency guard), and regenerate the Kuala Lumpur **present-day** return-period rasters as the first concrete artifact.

**Architecture:** `CityConfig` (in `scripts/cities.py`) stays the single source of per-city truth; the pipeline stays generic. A new per-city `manifest/` directory (four CSVs) plus a loader/validator (`scripts/city_manifest.py`) makes "city is validatable" mechanical. Two surgical fixes are added (a depth-aware floor in the raingrid pluvial branch; a scenario-forcing monotonicity guard). The KL present-day baseline is produced by the existing `run_city_pipeline.py` with `--pluvial-model raingrid --coastal-solver bathtub --delta-T 0.0`, then checked by an automated RP-monotonicity smoke test (the cheap subset of the visual gate).

**Tech Stack:** Python 3, numpy, scipy, pandas, rasterio, click, pytest. Open-data inputs only (Copernicus GLO-30, Google Open Buildings, ESA WorldCover, ERA5-Land via Open-Meteo, GLOFAS, UHSLC, Copernicus GFM SAR).

**Scope note:** This is Plan 1 of 3. Plan 2 (validation harness: extent-CSI vs MYS2021 SAR, hotspot hit-rate, point-depth, bootstrap CIs, two-gate dossier) and Plan 3 (validation-driven fixes incl. fluvial event-RP re-anchoring, SSP5-8.5 2100, viz) are authored after Plan 1's baseline exists — their tasks depend on what validation reveals.

**Source-of-truth paths:** flood-atlas lives at `D:/GPTs/Projects/flood-atlas`; the new repo at `D:/GPTs/Projects/flood-v2.0` (current working directory). The spec is at `docs/superpowers/specs/2026-06-04-asean-flood-v2-design.md` (already present in flood-v2.0).

---

### Task 1: Seed flood-v2.0 from flood-atlas and initialize the repo

**Files:**
- Create: `D:/GPTs/Projects/flood-v2.0/.gitignore`
- Copy: entire `flood-atlas` tree (minus VCS/regenerable dirs) into `flood-v2.0`
- Preserve: the already-present `flood-v2.0/docs/superpowers/specs/2026-06-04-asean-flood-v2-design.md` and `flood-v2.0/docs/superpowers/plans/2026-06-04-kl-foundation.md`

- [ ] **Step 1: Copy the flood-atlas tree into flood-v2.0 (PowerShell), excluding VCS and regenerable dirs**

robocopy mirrors directory contents without deleting the already-present v2.0 spec/plan (no `/MIR`). It excludes `.git`, `.worktrees`, and the regenerable `outputs/`, `cache/`, `logs/`.

Run (PowerShell):
```powershell
robocopy "D:\GPTs\Projects\flood-atlas" "D:\GPTs\Projects\flood-v2.0" /E `
  /XD "D:\GPTs\Projects\flood-atlas\.git" "D:\GPTs\Projects\flood-atlas\.worktrees" `
       "D:\GPTs\Projects\flood-atlas\outputs" "D:\GPTs\Projects\flood-atlas\cache" `
       "D:\GPTs\Projects\flood-atlas\logs" "D:\GPTs\Projects\flood-atlas\__pycache__" `
       "D:\GPTs\Projects\flood-atlas\.pytest_cache"
if ($LASTEXITCODE -le 7) { Write-Output "robocopy OK (exit $LASTEXITCODE)" } else { Write-Error "robocopy failed ($LASTEXITCODE)" }
```
Expected: robocopy exit code ≤ 7 (0–7 are success codes for robocopy). `scripts/`, `model/`, `data/`, `docs/`, `tests/`, `conftest.py`, `requirements.txt` now exist under flood-v2.0; the v2.0 spec + this plan are still present.

- [ ] **Step 2: Write the .gitignore (regenerable artifacts excluded)**

Create `D:/GPTs/Projects/flood-v2.0/.gitignore`:
```gitignore
# Regenerable — never committed (per HANDOFF §5)
outputs/
cache/
logs/
*.log

# Python
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: Initialize the repo and make the seed commit on `main`**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
git init
git add -A
git commit -m "chore: seed flood-v2.0 from flood-atlas (validated Singapore reference)

Includes the approved v2.0 design spec and KL foundation plan.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
Expected: a single initial commit; `git log --oneline` shows one entry; `git status` clean.

- [ ] **Step 4: Create the working branch for foundation work**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
git checkout -b kl-foundation
```
Expected: `git branch` shows `* kl-foundation`.

- [ ] **Step 5: Verify the seeded repo is functional**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
python -c "import sys; sys.path.insert(0,'.'); from scripts.cities import CITIES; print('cities:', 'kuala_lumpur' in CITIES, len(CITIES))"
python -c "import sys; sys.path.insert(0,'.'); from model.pluvial_rain_model import run_rain_on_grid, denoise_min_cluster; print('pluvial import OK')"
pytest tests/ -q 2>&1 | tail -5
```
Expected: `cities: True <N>` (kuala_lumpur present), `pluvial import OK`, and the inherited test suite collects and runs (pre-existing pass/fail baseline noted — do not fix inherited failures here).

- [ ] **Step 6: Commit (no-op if clean) — checkpoint marker**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
git add -A && git commit -m "chore: confirm seeded repo imports + test collection" --allow-empty
```

---

### Task 2: City-manifest contract — loader + validator

**Files:**
- Create: `scripts/city_manifest.py`
- Test: `tests/test_city_manifest.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_city_manifest.py`:
```python
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.city_manifest import (
    MANIFEST_FILENAMES,
    REQUIRED_NONEMPTY,
    manifest_dir,
    load_anchors,
    validate_manifest,
)


def _write_valid_manifest(root: Path, slug: str) -> Path:
    mdir = root / slug / "manifest"
    mdir.mkdir(parents=True)
    pd.DataFrame(
        [{"hazard": "pluvial", "duration_h": 6, "anchor_rp": 2,
          "anchor_value": 90.0, "unit": "mm", "source": "JPS MSMA",
          "citation": "MSMA 2nd ed."}]
    ).to_csv(mdir / "forcing_anchors.csv", index=False)
    pd.DataFrame(
        [{"hazard": "fluvial", "metric": "CSI", "threshold": 0.40,
          "direction": ">=", "citation": "Bates & De Roo 2000"}]
    ).to_csv(mdir / "gates.csv", index=False)
    # observed_events + hotspots may be header-only (populated incrementally)
    pd.DataFrame(columns=["event_id", "hazard", "event_date", "est_rp_low",
                          "est_rp_high", "extent_path", "source"]
                 ).to_csv(mdir / "observed_events.csv", index=False)
    pd.DataFrame(columns=["name", "lon", "lat", "kind", "confidence", "source"]
                 ).to_csv(mdir / "hotspots.csv", index=False)
    return mdir


def test_valid_manifest_returns_no_problems(tmp_path):
    _write_valid_manifest(tmp_path, "kuala_lumpur")
    assert validate_manifest("kuala_lumpur", data_root=tmp_path) == []


def test_missing_required_file_is_reported(tmp_path):
    mdir = _write_valid_manifest(tmp_path, "kuala_lumpur")
    (mdir / "gates.csv").unlink()
    problems = validate_manifest("kuala_lumpur", data_root=tmp_path)
    assert any("gates.csv" in p for p in problems)


def test_required_file_must_be_nonempty(tmp_path):
    mdir = _write_valid_manifest(tmp_path, "kuala_lumpur")
    pd.DataFrame(columns=["hazard", "duration_h", "anchor_rp", "anchor_value",
                          "unit", "source", "citation"]
                 ).to_csv(mdir / "forcing_anchors.csv", index=False)
    problems = validate_manifest("kuala_lumpur", data_root=tmp_path)
    assert any("forcing_anchors.csv" in p and "empty" in p.lower() for p in problems)


def test_missing_expected_column_is_reported(tmp_path):
    mdir = _write_valid_manifest(tmp_path, "kuala_lumpur")
    pd.DataFrame([{"hazard": "pluvial", "anchor_rp": 2}]
                 ).to_csv(mdir / "forcing_anchors.csv", index=False)
    problems = validate_manifest("kuala_lumpur", data_root=tmp_path)
    assert any("anchor_value" in p for p in problems)


def test_load_anchors_returns_rows(tmp_path):
    _write_valid_manifest(tmp_path, "kuala_lumpur")
    df = load_anchors("kuala_lumpur", data_root=tmp_path)
    assert float(df.loc[df.anchor_rp == 2, "anchor_value"].iloc[0]) == 90.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0 && pytest tests/test_city_manifest.py -q
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.city_manifest'`.

- [ ] **Step 3: Write the minimal implementation**

Create `scripts/city_manifest.py`:
```python
"""City-manifest contract for the multi-hazard flood pipeline.

A city is "complete and validatable" only when, in addition to its CityConfig
(scripts/cities.py), it carries four manifest CSVs under data/<slug>/manifest/:

    forcing_anchors.csv  hazard,duration_h,anchor_rp,anchor_value,unit,source,citation
    observed_events.csv  event_id,hazard,event_date,est_rp_low,est_rp_high,extent_path,source
    hotspots.csv         name,lon,lat,kind,confidence,source
    gates.csv            hazard,metric,threshold,direction,citation

forcing_anchors.csv and gates.csv MUST contain at least one data row; the
observed_events and hotspots manifests may be populated incrementally (header
only is allowed) so a city can be staged before its full register exists.

This module is intentionally pure (no I/O beyond reading the CSVs) so it is
unit-testable against a tmp_path fixture.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

MANIFEST_FILENAMES: dict[str, str] = {
    "forcing_anchors": "forcing_anchors.csv",
    "observed_events": "observed_events.csv",
    "hotspots": "hotspots.csv",
    "gates": "gates.csv",
}

REQUIRED_NONEMPTY: set[str] = {"forcing_anchors", "gates"}

EXPECTED_COLUMNS: dict[str, set[str]] = {
    "forcing_anchors": {"hazard", "duration_h", "anchor_rp", "anchor_value",
                        "unit", "source", "citation"},
    "observed_events": {"event_id", "hazard", "event_date", "est_rp_low",
                        "est_rp_high", "extent_path", "source"},
    "hotspots": {"name", "lon", "lat", "kind", "confidence", "source"},
    "gates": {"hazard", "metric", "threshold", "direction", "citation"},
}


def manifest_dir(slug: str, data_root: Path = Path("data")) -> Path:
    return Path(data_root) / slug / "manifest"


def load_anchors(slug: str, data_root: Path = Path("data")) -> pd.DataFrame:
    path = manifest_dir(slug, data_root) / MANIFEST_FILENAMES["forcing_anchors"]
    return pd.read_csv(path)


def validate_manifest(slug: str, data_root: Path = Path("data")) -> list[str]:
    """Return a list of human-readable problems; an empty list means valid."""
    problems: list[str] = []
    mdir = manifest_dir(slug, data_root)
    for key, fname in MANIFEST_FILENAMES.items():
        fpath = mdir / fname
        if not fpath.exists():
            problems.append(f"[{slug}] missing manifest file: {fname}")
            continue
        try:
            df = pd.read_csv(fpath)
        except Exception as exc:  # malformed CSV
            problems.append(f"[{slug}] {fname}: unreadable ({exc})")
            continue
        missing_cols = EXPECTED_COLUMNS[key] - set(df.columns)
        if missing_cols:
            problems.append(
                f"[{slug}] {fname}: missing column(s) "
                f"{sorted(missing_cols)}"
            )
        if key in REQUIRED_NONEMPTY and len(df) == 0:
            problems.append(f"[{slug}] {fname}: required manifest is empty")
    return problems
```

- [ ] **Step 4: Run the test to verify it passes**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0 && pytest tests/test_city_manifest.py -q
```
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
git add scripts/city_manifest.py tests/test_city_manifest.py
git commit -m "feat: city-manifest contract (loader + validator)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Populate Kuala Lumpur's four manifests

**Files:**
- Create: `data/kuala_lumpur/manifest/forcing_anchors.csv`
- Create: `data/kuala_lumpur/manifest/gates.csv`
- Create: `data/kuala_lumpur/manifest/observed_events.csv`
- Create: `data/kuala_lumpur/manifest/hotspots.csv`
- Test: `tests/test_kl_manifest.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_kl_manifest.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.city_manifest import validate_manifest, load_anchors


def test_kl_manifest_is_valid():
    # Uses the real repo data/ root.
    assert validate_manifest("kuala_lumpur") == []


def test_kl_pluvial_idf_anchors_present():
    df = load_anchors("kuala_lumpur")
    pluvial = df[df.hazard == "pluvial"]
    rp2 = float(pluvial.loc[pluvial.anchor_rp == 2, "anchor_value"].iloc[0])
    rp100 = float(pluvial.loc[pluvial.anchor_rp == 100, "anchor_value"].iloc[0])
    assert rp2 == 90.0
    assert rp100 == 165.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0 && pytest tests/test_kl_manifest.py -q
```
Expected: FAIL — `validate_manifest` reports missing files (manifest dir does not exist yet).

- [ ] **Step 3: Create the four KL manifest CSVs**

Create `data/kuala_lumpur/manifest/forcing_anchors.csv`:
```csv
hazard,duration_h,anchor_rp,anchor_value,unit,source,citation
pluvial,6,2,90.0,mm,JPS Malaysia MSMA/HP1,"MSMA 2nd ed. (DID Malaysia 2012); Hydrological Procedure No.1 (DID); matches cities.py KL pluvial IDF calibration"
pluvial,6,100,165.0,mm,JPS Malaysia MSMA/HP1,"MSMA 2nd ed. (DID Malaysia 2012); upper IDF anchor used in KL pluvial Gumbel calibration"
```

Create `data/kuala_lumpur/manifest/gates.csv`:
```csv
hazard,metric,threshold,direction,citation
fluvial,CSI,0.40,>=,"Bates & De Roo 2000; Bernhofen et al. 2018 (acceptable band for coarse-resolution inundation models)"
fluvial,POD,0.60,>=,"Pappenberger et al. 2007; Wing et al. 2017"
fluvial,FAR,0.40,<=,"Pappenberger et al. 2007"
coastal,CSI,0.40,>=,"Bates & De Roo 2000 (scored only where coastal is meaningful; N/A inland — see spec 6.1)"
pluvial,idf_ci_coverage,0.90,within,"modelled RP-depth within published IDF 90% confidence band (NOAA Atlas 14 method; MSMA/HP1)"
point_depth,RMSE_m,0.50,<=,"Wing et al. 2017/2021 (depth RMSE benchmark)"
point_depth,bias_abs_m,0.20,<=,"validation_workflow.md screening-model threshold"
```

Create `data/kuala_lumpur/manifest/observed_events.csv`:
```csv
event_id,hazard,event_date,est_rp_low,est_rp_high,extent_path,source
MYS2021,fluvial,2021-12-18,50,100,data/kl/flood_obs/MYS2021/gfm_kl_composite_dec2021.tif,"Copernicus GFM ensemble + UNOSAT (CC-BY); JPS danger-level exceedances imply basin-scale RP50-100"
```

Create `data/kuala_lumpur/manifest/hotspots.csv` (header only — populated in Plan 2 from JPS/DID flood-prone lists, geocoded):
```csv
name,lon,lat,kind,confidence,source
```

- [ ] **Step 4: Run the test to verify it passes**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0 && pytest tests/test_kl_manifest.py -q
```
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
git add data/kuala_lumpur/manifest/ tests/test_kl_manifest.py
git commit -m "feat: populate KL four-manifest (forcing anchors, gates, observed event, hotspot stub)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Depth-aware pluvial floor (proactive Manila-sheet fix)

**Context:** `summarize_depth` (model/flood_depth_model.py:487) counts `depth > 0` as wet. On a flat delta the raingrid solver can produce a spatially *continuous* sub-5cm sheet that survives `denoise_min_cluster` (one large cluster, not speckle) and inflates `flooded_area_km2`/`wet_pixels` (limitation #2). KL's steeper terrain does not trigger this, but the fix is cheap and protects the Jakarta/Bangkok transfer.

**Files:**
- Modify: `model/pluvial_rain_model.py` (add `apply_depth_floor`)
- Modify: `scripts/run_multihazard.py:818-821` (apply the floor in the raingrid branch)
- Test: `tests/test_depth_floor.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_depth_floor.py`:
```python
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.pluvial_rain_model import apply_depth_floor


def test_continuous_subthreshold_sheet_is_stripped():
    # A large CONNECTED sheet of 2 cm water (survives cluster denoise) must be
    # zeroed by the depth floor so it cannot inflate wet-area summaries.
    depth = np.full((50, 50), 0.02, dtype=np.float32)
    out = apply_depth_floor(depth, floor_m=0.05)
    assert np.count_nonzero(out > 0) == 0


def test_real_pool_survives():
    depth = np.zeros((50, 50), dtype=np.float32)
    depth[10:20, 10:20] = 0.30  # a 10x10 cell, 0.30 m pool
    out = apply_depth_floor(depth, floor_m=0.05)
    assert np.count_nonzero(out > 0) == 100
    assert float(out.max()) == pytest.approx(0.30, rel=1e-5)  # float32 round-trip


def test_nan_preserved():
    depth = np.array([[np.nan, 0.02, 0.10]], dtype=np.float32)
    out = apply_depth_floor(depth, floor_m=0.05)
    assert np.isnan(out[0, 0])
    assert out[0, 1] == 0.0
    assert out[0, 2] == 0.10
```

- [ ] **Step 2: Run the test to verify it fails**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0 && pytest tests/test_depth_floor.py -q
```
Expected: FAIL — `ImportError: cannot import name 'apply_depth_floor'`.

- [ ] **Step 3: Add `apply_depth_floor` to model/pluvial_rain_model.py**

Insert immediately after the `denoise_min_cluster` function (after line 173, before `def run_rain_on_grid`):
```python
def apply_depth_floor(depth: np.ndarray, floor_m: float = 0.05) -> np.ndarray:
    """Zero cells whose depth is below ``floor_m``, preserving NaN (nodata).

    Companion to ``denoise_min_cluster``: that drops small *clusters*, this
    drops shallow *cells* regardless of cluster size.  A spatially continuous
    sub-threshold sheet on a flat delta forms one large connected cluster that
    survives the cluster denoise but is hydrologically meaningless; counting it
    as ``wet`` (summarize_depth uses depth > 0) inflates flooded-area summaries
    (limitations register #2, the Manila domain-wide sheet).  Applying this
    floor before the raster is written aligns the reported wet area with the
    same 0.05 m threshold the denoise uses.
    """
    out = depth.copy()
    mask = np.isfinite(out) & (out < floor_m)
    out[mask] = 0.0
    return out
```

- [ ] **Step 4: Run the test to verify it passes**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0 && pytest tests/test_depth_floor.py -q
```
Expected: PASS (3 passed).

- [ ] **Step 5: Wire the floor into the raingrid branch of run_multihazard.py**

In `scripts/run_multihazard.py`, update the import on line 46 and the denoise call at lines 818-821.

Change line 46 from:
```python
from model.pluvial_rain_model import run_rain_on_grid, denoise_min_cluster
```
to:
```python
from model.pluvial_rain_model import run_rain_on_grid, denoise_min_cluster, apply_depth_floor
```

Change lines 818-821 from:
```python
                    # Drop sub-0.5 ha noise speckle; keep coherent pools.
                    depth = denoise_min_cluster(
                        res["peak_depth"], wet_threshold_m=0.05,
                        min_cluster_cells=6).astype(np.float32)
```
to:
```python
                    # Drop sub-0.5 ha noise speckle; keep coherent pools.
                    depth = denoise_min_cluster(
                        res["peak_depth"], wet_threshold_m=0.05,
                        min_cluster_cells=6).astype(np.float32)
                    # Depth-aware floor: strip cells below the wet threshold so a
                    # spatially CONTINUOUS sub-5cm sheet (which survives cluster
                    # denoise on a flat delta) cannot inflate wet-area summaries
                    # (limitations #2). No-op on steep terrain (KL/SG).
                    depth = apply_depth_floor(depth, floor_m=0.05)
```

- [ ] **Step 6: Verify the module still imports and the test suite is green**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
python -c "import sys; sys.path.insert(0,'.'); import scripts.run_multihazard; print('run_multihazard import OK')"
pytest tests/test_depth_floor.py -q
```
Expected: `run_multihazard import OK`; 3 passed.

- [ ] **Step 7: Commit**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
git add model/pluvial_rain_model.py scripts/run_multihazard.py tests/test_depth_floor.py
git commit -m "fix: depth-aware floor on raingrid pluvial output (preempts Manila-sheet area inflation)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Scenario-forcing consistency guard

**Context:** Limitation #9 — SG scenario hazard-level CSVs once carried inconsistent (non-monotone, physically impossible) pluvial forcing. This guard makes that class of bug a committed check rather than a thing caught by eye. The KL scenario CSVs (`data/kuala_lumpur/hazard_levels_*.csv`) carry the pluvial forcing in the `water_level_m` column.

**Files:**
- Create: `scripts/validate_scenario_forcing_consistency.py`
- Test: `tests/test_scenario_forcing_consistency.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_scenario_forcing_consistency.py`:
```python
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.validate_scenario_forcing_consistency import check_pluvial_forcing


def _csv(path: Path, rp_to_level: dict[int, float]):
    rows = [{"hazard_type": "pluvial", "return_period": rp,
             "water_level_m": lvl} for rp, lvl in rp_to_level.items()]
    pd.DataFrame(rows).to_csv(path, index=False)


def test_monotone_increasing_passes(tmp_path):
    order = ["a", "b", "c"]
    _csv(tmp_path / "a.csv", {2: 0.02, 100: 0.09})
    _csv(tmp_path / "b.csv", {2: 0.03, 100: 0.10})
    _csv(tmp_path / "c.csv", {2: 0.04, 100: 0.11})
    problems = check_pluvial_forcing(
        [tmp_path / f"{n}.csv" for n in order], cap_m=0.5)
    assert problems == []


def test_inversion_is_flagged(tmp_path):
    _csv(tmp_path / "a.csv", {100: 0.09})
    _csv(tmp_path / "b.csv", {100: 0.05})  # lower forcing at higher severity
    problems = check_pluvial_forcing(
        [tmp_path / "a.csv", tmp_path / "b.csv"], cap_m=0.5)
    assert any("RP100" in p and "inversion" in p.lower() for p in problems)


def test_physically_impossible_value_is_flagged(tmp_path):
    _csv(tmp_path / "a.csv", {100: 0.76})  # 760 mm net-excess for 6h — impossible (cf. limitation #9; must exceed cap_m=0.5)
    problems = check_pluvial_forcing([tmp_path / "a.csv"], cap_m=0.5)
    assert any("RP100" in p and "cap" in p.lower() for p in problems)
```

- [ ] **Step 2: Run the test to verify it fails**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0 && pytest tests/test_scenario_forcing_consistency.py -q
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.validate_scenario_forcing_consistency'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/validate_scenario_forcing_consistency.py`:
```python
"""Guard against inconsistent pluvial forcing across scenario hazard-level CSVs.

Limitations register #9: scenario CSVs once carried non-monotone and physically
impossible pluvial net-excess (water_level_m). This converts that into a
committed check: across an ordered list of scenario CSVs (least → most severe),
pluvial water_level_m must be non-decreasing at each return period and must not
exceed a physical-plausibility cap.

Usage
-----
    python scripts/validate_scenario_forcing_consistency.py --city kuala_lumpur

Exit codes: 0 = consistent; 1 = one or more problems.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Least → most severe (by warming). Baseline template is the floor.
SCENARIO_ORDER = [
    "hazard_levels_ssp245_2050.csv",
    "hazard_levels_ssp585_2050.csv",
    "hazard_levels_ssp245_2100.csv",
    "hazard_levels_ssp585_2100.csv",
]
PLAUSIBILITY_CAP_M = 0.5  # 6h net-excess ponding depth; >0.5 m is unphysical


def _pluvial_by_rp(csv_path: Path) -> dict[int, float]:
    df = pd.read_csv(csv_path)
    p = df[df["hazard_type"] == "pluvial"]
    return {int(r): float(v) for r, v in zip(p["return_period"], p["water_level_m"])}


def check_pluvial_forcing(csv_paths: list[Path], cap_m: float = PLAUSIBILITY_CAP_M) -> list[str]:
    """Return problems; empty list means consistent."""
    problems: list[str] = []
    series = [(p, _pluvial_by_rp(p)) for p in csv_paths]
    # Cap check on every file.
    for path, by_rp in series:
        for rp, lvl in by_rp.items():
            if lvl > cap_m:
                problems.append(
                    f"{path.name} RP{rp}: water_level_m={lvl:.3f} exceeds "
                    f"plausibility cap {cap_m:.2f} m"
                )
    # Monotonicity across the ordered scenarios, per RP.
    for i in range(1, len(series)):
        prev_path, prev = series[i - 1]
        cur_path, cur = series[i]
        for rp in sorted(set(prev) & set(cur)):
            if cur[rp] + 1e-9 < prev[rp]:
                problems.append(
                    f"RP{rp}: inversion {prev_path.name}={prev[rp]:.3f} > "
                    f"{cur_path.name}={cur[rp]:.3f} (more severe scenario has "
                    f"lower forcing)"
                )
    return problems


@click.command()
@click.option("--city", "city_slug", required=True, help="City slug.")
@click.option("--data-root", type=click.Path(path_type=Path), default=Path("data"))
def cli(city_slug: str, data_root: Path):
    city_dir = data_root / city_slug
    paths = [city_dir / name for name in SCENARIO_ORDER if (city_dir / name).exists()]
    if not paths:
        raise click.ClickException(f"No scenario CSVs found under {city_dir}")
    click.echo(f"Checking {len(paths)} scenario CSV(s) for {city_slug} ...")
    problems = check_pluvial_forcing(paths)
    if problems:
        click.echo(f"FAIL: {len(problems)} problem(s):")
        for p in problems:
            click.echo(f"  - {p}")
        sys.exit(1)
    click.echo("PASS: pluvial forcing monotone and within plausibility cap.")
    sys.exit(0)


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run the test to verify it passes**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0 && pytest tests/test_scenario_forcing_consistency.py -q
```
Expected: PASS (3 passed).

- [ ] **Step 5: Run the guard against the real KL scenario CSVs**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0 && python scripts/validate_scenario_forcing_consistency.py --city kuala_lumpur
```
Expected: `PASS: pluvial forcing monotone and within plausibility cap.` (KL forcing inspected as plausible during planning). **If it FAILs**, do not tweak rasters — open a limitations-register entry and stop; regenerating KL hazard-levels with one consistent pluvial fit is a Plan-3 task.

- [ ] **Step 6: Commit**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
git add scripts/validate_scenario_forcing_consistency.py tests/test_scenario_forcing_consistency.py
git commit -m "feat: scenario-forcing consistency guard (limitation #9 → committed check)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: RP-monotonicity / mass-plausibility smoke check

**Context:** The automated subset of the visual-gate checklist (spec §6.3). Reads a `summary_<scenario>_<horizon>.csv` produced by `run_multihazard.py` and asserts, per hazard, that `flooded_area_km2` and `max_depth_m` are non-decreasing with return period, and that wet area never exceeds a sane fraction of the domain. Columns are exactly those emitted by `summarize_depth` (flood_depth_model.py:493): `flooded_area_km2`, `max_depth_m`, `mean_depth_m`, `wet_pixels`, plus `hazard_type`, `return_period`.

**Files:**
- Create: `scripts/check_rp_monotonicity.py`
- Test: `tests/test_rp_monotonicity.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_rp_monotonicity.py`:
```python
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.check_rp_monotonicity import check_monotonicity


def _summary(path: Path, rows):
    pd.DataFrame(rows).to_csv(path, index=False)


def test_monotone_summary_passes(tmp_path):
    p = tmp_path / "summary.csv"
    _summary(p, [
        {"hazard_type": "pluvial", "return_period": 2, "flooded_area_km2": 1.0, "max_depth_m": 0.3},
        {"hazard_type": "pluvial", "return_period": 10, "flooded_area_km2": 2.0, "max_depth_m": 0.5},
        {"hazard_type": "pluvial", "return_period": 100, "flooded_area_km2": 3.0, "max_depth_m": 0.9},
    ])
    assert check_monotonicity(p, domain_km2=1000.0, max_wet_fraction=0.6) == []


def test_decreasing_area_is_flagged(tmp_path):
    p = tmp_path / "summary.csv"
    _summary(p, [
        {"hazard_type": "fluvial", "return_period": 10, "flooded_area_km2": 5.0, "max_depth_m": 1.0},
        {"hazard_type": "fluvial", "return_period": 100, "flooded_area_km2": 3.0, "max_depth_m": 1.2},
    ])
    problems = check_monotonicity(p, domain_km2=1000.0, max_wet_fraction=0.6)
    assert any("flooded_area_km2" in x and "RP100" in x for x in problems)


def test_excessive_wet_fraction_is_flagged(tmp_path):
    p = tmp_path / "summary.csv"
    _summary(p, [
        {"hazard_type": "pluvial", "return_period": 100, "flooded_area_km2": 900.0, "max_depth_m": 0.5},
    ])
    problems = check_monotonicity(p, domain_km2=1000.0, max_wet_fraction=0.6)
    assert any("wet fraction" in x.lower() for x in problems)
```

- [ ] **Step 2: Run the test to verify it fails**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0 && pytest tests/test_rp_monotonicity.py -q
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.check_rp_monotonicity'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/check_rp_monotonicity.py`:
```python
"""Automated RP-monotonicity + mass-plausibility smoke check.

The machine-checkable subset of the visual-gate checklist (spec 6.3):
per hazard, flooded_area_km2 and max_depth_m must be non-decreasing with
return period, and wet area must not exceed a sane fraction of the domain.
This catches Manila-type domain-wide-sheet and non-monotone bugs instantly.

Usage
-----
    python scripts/check_rp_monotonicity.py --summary outputs/<run>/summary_<sc>_<hz>.csv \
        --domain-km2 <area> [--max-wet-fraction 0.6]

Exit codes: 0 = clean; 1 = one or more problems.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import pandas as pd

MONOTONE_COLUMNS = ["flooded_area_km2", "max_depth_m"]


def check_monotonicity(
    summary_csv: Path,
    domain_km2: float,
    max_wet_fraction: float = 0.6,
) -> list[str]:
    """Return problems; empty list means clean."""
    df = pd.read_csv(summary_csv)
    problems: list[str] = []
    for hazard, grp in df.groupby("hazard_type"):
        grp = grp.sort_values("return_period")
        for col in MONOTONE_COLUMNS:
            if col not in grp.columns:
                continue
            vals = grp[col].to_numpy()
            rps = grp["return_period"].to_numpy()
            for i in range(1, len(vals)):
                if vals[i] + 1e-9 < vals[i - 1]:
                    problems.append(
                        f"{hazard} {col}: RP{int(rps[i])}={vals[i]:.4f} < "
                        f"RP{int(rps[i-1])}={vals[i-1]:.4f} (non-monotone)"
                    )
        if "flooded_area_km2" in grp.columns and domain_km2 > 0:
            for _, r in grp.iterrows():
                frac = float(r["flooded_area_km2"]) / domain_km2
                if frac > max_wet_fraction:
                    problems.append(
                        f"{hazard} RP{int(r['return_period'])}: wet fraction "
                        f"{frac:.0%} exceeds {max_wet_fraction:.0%} of domain"
                    )
    return problems


@click.command()
@click.option("--summary", "summary_csv", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--domain-km2", type=float, required=True, help="Land-domain area (km2) for the wet-fraction check.")
@click.option("--max-wet-fraction", type=float, default=0.6, show_default=True)
def cli(summary_csv: Path, domain_km2: float, max_wet_fraction: float):
    problems = check_monotonicity(summary_csv, domain_km2, max_wet_fraction)
    if problems:
        click.echo(f"FAIL: {len(problems)} problem(s):")
        for p in problems:
            click.echo(f"  - {p}")
        sys.exit(1)
    click.echo("PASS: per-hazard RP monotonicity + mass plausibility hold.")
    sys.exit(0)


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run the test to verify it passes**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0 && pytest tests/test_rp_monotonicity.py -q
```
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
git add scripts/check_rp_monotonicity.py tests/test_rp_monotonicity.py
git commit -m "feat: RP-monotonicity + mass-plausibility smoke check (automated visual-gate subset)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Regenerate the KL present-day baseline and gate it

**Context:** Produces the first concrete artifact — KL present-day RP2…RP1000 depth + severity rasters for all three hazards — using the existing pipeline with the spec's solver choices: `raingrid` pluvial (HANDOFF flags it realistic for KL's steeper terrain), `bathtub` coastal (screening upper bound; inertial shelved), and `--delta-T 0.0` for present-day (no climate scaling). DEM/HAND/river/sea/runoff rasters and the GEV-baked baseline CSV are already present in `data/kuala_lumpur/`, so all fits are reused (`--no-fit-*`). This is a long compute job (rain-on-grid over the Klang Valley domain); run it in the background.

**Files:**
- Produces (gitignored): `outputs/kuala_lumpur_*/...` rasters + `summary_*.csv`
- Create (tracked artifact-of-record): `docs/superpowers/runs/2026-06-04-kl-baseline.md` + copied summary CSV

- [ ] **Step 1: Run the KL present-day baseline pipeline (background)**

Run (bash, background — this is long):
```bash
cd /d/GPTs/Projects/flood-v2.0
python scripts/run_city_pipeline.py --city kuala_lumpur \
    --scenario SSP5-8.5 --horizon 2020 --delta-T 0.0 \
    --pluvial-model raingrid --coastal-solver bathtub \
    --no-fit-era5 --no-fit-coastal --no-fit-glofas \
    --out-root outputs 2>&1 | tee outputs_kl_baseline.log
```
Expected: pipeline runs to completion and prints the output directory path and `Wrote summary: outputs/<run_dir>/summary_SSP5-8.5_2020.csv`. Note the exact `<run_dir>` it prints (convention: `kuala_lumpur_ssp585_2020`).

- [ ] **Step 2: Confirm all three hazards × all RPs produced rasters**

Run (bash) — substitute the printed `<run_dir>`:
```bash
cd /d/GPTs/Projects/flood-v2.0
RUN=outputs/kuala_lumpur_ssp585_2020
ls -1 "$RUN"/coastal/rp_*/*.tif "$RUN"/fluvial/rp_*/*.tif "$RUN"/pluvial/rp_*/*.tif | wc -l
cat "$RUN"/summary_SSP5-8.5_2020.csv | head -30
```
Expected: a nonzero count covering coastal/fluvial/pluvial across RP2…RP1000 (9 RPs × 3 hazards × 2 raster types = up to 54 files); the summary CSV lists rows per (hazard_type, return_period).

- [ ] **Step 3: Run the scenario-forcing consistency guard (already implemented in Task 5)**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0 && python scripts/validate_scenario_forcing_consistency.py --city kuala_lumpur
```
Expected: `PASS`.

- [ ] **Step 4: Run the RP-monotonicity smoke check on the produced summary**

Compute the KL land-domain area for the wet-fraction denominator from the DEM, then run the check.

Run (bash) — substitute the printed `<run_dir>`:
```bash
cd /d/GPTs/Projects/flood-v2.0
python -c "
import sys; sys.path.insert(0,'.')
import numpy as np, rasterio
with rasterio.open('data/kuala_lumpur/copernicus_dem_utm47n.tif') as ds:
    a = ds.read(1, masked=True)
    px = abs(ds.transform.a*ds.transform.e)
    land_km2 = int(np.ma.count(a))*px/1e6
print(f'{land_km2:.1f}')
" > /tmp/kl_land_km2.txt
LAND=$(cat /tmp/kl_land_km2.txt)
python scripts/check_rp_monotonicity.py \
    --summary outputs/kuala_lumpur_ssp585_2020/summary_SSP5-8.5_2020.csv \
    --domain-km2 "$LAND" --max-wet-fraction 0.6
```
Expected: `PASS: per-hazard RP monotonicity + mass plausibility hold.` **If it FAILs:** convert each flagged item to a limitations-register entry (do NOT tweak parameters to make the picture look right — that is the forbidden loop). Non-monotone pluvial → investigate as a Plan-2/3 finding; this gate is diagnostic, not a tuning target.

- [ ] **Step 5: Record the run as a tracked artifact-of-record**

Copy the summary into a tracked location (rasters stay gitignored) and write a short provenance note.

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
mkdir -p docs/superpowers/runs
cp outputs/kuala_lumpur_ssp585_2020/summary_SSP5-8.5_2020.csv \
   docs/superpowers/runs/2026-06-04-kl-baseline-summary.csv
```

Create `docs/superpowers/runs/2026-06-04-kl-baseline.md`:
```markdown
# KL present-day baseline run — 2026-06-04

**Command:**
`run_city_pipeline.py --city kuala_lumpur --scenario SSP5-8.5 --horizon 2020 --delta-T 0.0 --pluvial-model raingrid --coastal-solver bathtub --no-fit-era5 --no-fit-coastal --no-fit-glofas`

**Solver choices (spec):** raingrid pluvial (HANDOFF: realistic for KL steeper terrain),
bathtub coastal (screening upper bound; inertial shelved), delta_T=0 (present-day, no climate scaling).

**Gates run:** scenario-forcing consistency = PASS/FAIL; RP-monotonicity + mass plausibility = PASS/FAIL
(fill in actual results; attach any limitations-register entries opened).

**Output (gitignored):** `outputs/kuala_lumpur_ssp585_2020/` — RP2…RP1000 depth+severity rasters,
coastal/fluvial/pluvial. Summary copied to `2026-06-04-kl-baseline-summary.csv`.

**Next:** Plan 2 — validation harness (extent-CSI vs MYS2021 SAR, hotspot hit-rate, point-depth,
bootstrap CIs, two-gate dossier).
```

- [ ] **Step 6: Commit the artifact-of-record**

Run (bash):
```bash
cd /d/GPTs/Projects/flood-v2.0
git add docs/superpowers/runs/
git commit -m "chore: record KL present-day baseline run + gate results

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (against `2026-06-04-asean-flood-v2-design.md`):**
- §3 Workspace setup → Task 1 (seed, .gitignore, carry/leave, repo init). ✓
- §4 Four-manifest contract → Task 2 (loader/validator) + Task 3 (KL manifests). ✓
- §5.1 Pluvial + depth-aware masking fix → Task 4 + Task 7 (raingrid run). ✓
- §5.2 Fluvial → baseline rasters produced in Task 7; **event-RP re-anchoring deferred to Plan 3** (validation-driven, per Hybrid choice). ✓ (scoped out by design)
- §5.3 Coastal bathtub screening → Task 7 (`--coastal-solver bathtub`). ✓
- §6.3 Visual-gate automated subset → Task 6 + Task 7 Step 4. ✓
- §7.5 Scenario-forcing consistency → Task 5. ✓
- §8.1 Present-day RP suite artifact → Task 7. ✓ (SSP5-8.5 2100 future scenario deferred to Plan 3.)
- §6.1 gate thresholds (citations) → encoded in Task 3 `gates.csv`. ✓ (gates *applied* in Plan 2.)
- Validation harness (extent-CSI, hotspot hit-rate, point-depth, bootstrap CIs, dossier, viz) → **Plan 2/3** by design. ✓

**2. Placeholder scan:** No "TBD/TODO/implement later". Every code step shows complete code; every run step shows the exact command + expected output. The `<run_dir>` substitution in Task 7 is an explicit value the pipeline prints (convention given), not a placeholder. ✓

**3. Type consistency:** `validate_manifest(slug, data_root)` signature consistent across Tasks 2/3 and tests. `apply_depth_floor(depth, floor_m)` consistent between Task 4 definition, test, and the run_multihazard call site. `check_pluvial_forcing(csv_paths, cap_m)` and `check_monotonicity(summary_csv, domain_km2, max_wet_fraction)` consistent between implementation and tests. Summary columns (`flooded_area_km2`, `max_depth_m`, `hazard_type`, `return_period`) match `summarize_depth` (flood_depth_model.py:493). ✓

---

## Execution Handoff

Plan 1 of 3 complete. Plans 2 (validation harness) and 3 (validation-driven fixes + SSP5-8.5 2100 + viz) are authored after this plan's baseline exists.
