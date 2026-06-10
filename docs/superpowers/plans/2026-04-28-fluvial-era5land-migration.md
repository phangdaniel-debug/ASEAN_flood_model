# Fluvial ERA5-Land Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `fit_fluvial_baseline_era5.py` from NASA POWER MERRA-2 to ERA5-Land via Open-Meteo, re-enabling `--fit-fluvial` by default and rewriting all 9 active-city baselines with a clean, reproducible source.

**Architecture:** Move the shared `fetch_hourly_precip_era5land()` function into `gev_utils.py` (where all shared pipeline utilities live), remove MERRA-2 fetch and `--precip-scale` from the fluvial script, flip the pipeline default, and add a 24h IDF anchor validator modelled on the existing pluvial validator. All 9 city baseline CSVs are refit during implementation — ERA5-Land via Open-Meteo requires no credentials.

**Tech Stack:** Python, click, requests, pandas, numpy, scipy (GEV), Open-Meteo Archive API (free, no key).

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `scripts/gev_utils.py` | Modify | Add `fetch_hourly_precip_era5land()` (moved from pluvial script) |
| `scripts/fit_pluvial_baseline_era5.py` | Modify | Remove local fetch function; import from `gev_utils` |
| `scripts/validate_pluvial_idf_anchors.py` | Modify | Update import: `fit_pluvial_baseline_era5` → `gev_utils` |
| `scripts/fit_fluvial_baseline_era5.py` | Modify | Remove MERRA-2 fetch + `--precip-scale`; use ERA5-Land; update defaults/notes |
| `scripts/run_city_pipeline.py` | Modify | Flip `--fit-fluvial` default; rename cache; remove MERRA-2 warning |
| `scripts/validate_fluvial_idf_anchors.py` | Create | 24h IDF anchor validator (analogous to pluvial validator) |
| `tests/test_fluvial_redesign.py` | Create | Unit tests for the migration |
| `data/*/hazard_baseline_template.csv` | Modify | Refit fluvial rows for all 9 active cities |
| `docs/hazard_methodology_comparison.md` | Modify | Issue #20 RESOLVED; Recent Fixes table; §3.1 update |

---

### Task 1: Move `fetch_hourly_precip_era5land` to `gev_utils.py`

**Files:**
- Modify: `scripts/gev_utils.py`
- Modify: `scripts/fit_pluvial_baseline_era5.py:61,80-140`
- Modify: `scripts/validate_pluvial_idf_anchors.py:53`
- Create: `tests/test_fluvial_redesign.py`

- [ ] **Step 1: Write three failing tests**

Create `tests/test_fluvial_redesign.py`:

```python
"""Tests for the fluvial ERA5-Land migration (Issue #20)."""
from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Task 1 — fetch function moved to gev_utils
# ---------------------------------------------------------------------------

def test_gev_utils_exports_era5land_fetch():
    from scripts.gev_utils import fetch_hourly_precip_era5land
    assert callable(fetch_hourly_precip_era5land)


def test_pluvial_script_no_longer_defines_fetch():
    source = Path("scripts/fit_pluvial_baseline_era5.py").read_text(encoding="utf-8")
    assert "def fetch_hourly_precip_era5land" not in source


def test_pluvial_validator_imports_from_gev_utils():
    source = Path("scripts/validate_pluvial_idf_anchors.py").read_text(encoding="utf-8")
    assert "from scripts.fit_pluvial_baseline_era5 import fetch_hourly_precip_era5land" not in source
    assert "gev_utils" in source
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_fluvial_redesign.py::test_gev_utils_exports_era5land_fetch \
       tests/test_fluvial_redesign.py::test_pluvial_script_no_longer_defines_fetch \
       tests/test_fluvial_redesign.py::test_pluvial_validator_imports_from_gev_utils -v
```

Expected: all three FAIL (function not yet in gev_utils; definition still in pluvial script).

- [ ] **Step 3: Add `fetch_hourly_precip_era5land` to `gev_utils.py`**

Append the following to `scripts/gev_utils.py` (after `gev_return_level`):

```python


def fetch_hourly_precip_era5land(
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
    chunk_years: int = 5,
) -> "pd.Series":
    """
    Download hourly ERA5-Land precipitation (mm/h) from Open-Meteo Archive.

    Free, no API key required.  Returns a DatetimeIndex (UTC) pd.Series
    with column name ``precipitation_mm_h``.  Uses 3-attempt retry with
    exponential backoff.

    Parameters
    ----------
    lat, lon : float
        Coordinates of the ERA5-Land grid point (nearest neighbour used by API).
    start_year, end_year : int
        Inclusive date range.  ERA5-Land starts 1950; 2001 is a practical default.
    chunk_years : int
        Years per API request.  Default 5 keeps individual payloads small.
    """
    import time
    import requests
    import click

    _URL = "https://archive-api.open-meteo.com/v1/era5"
    chunks: list[pd.Series] = []
    for yr0 in range(start_year, end_year + 1, chunk_years):
        yr1 = min(yr0 + chunk_years - 1, end_year)
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": f"{yr0}-01-01",
            "end_date": f"{yr1}-12-31",
            "hourly": "precipitation",
            "timezone": "UTC",
        }
        click.echo(f"  ERA5-Land {yr0}-{yr1} ... ", nl=False)
        for attempt in range(3):
            try:
                resp = requests.get(_URL, params=params, timeout=180)
                resp.raise_for_status()
                break
            except Exception as exc:
                if attempt == 2:
                    raise click.ClickException(
                        f"Open-Meteo request failed ({yr0}-{yr1}): {exc}"
                    ) from exc
                time.sleep(5 * (attempt + 1))
        payload = resp.json()
        if "hourly" not in payload or "precipitation" not in payload["hourly"]:
            raise click.ClickException(
                f"Unexpected Open-Meteo response keys: {list(payload.keys())}"
            )
        times = pd.to_datetime(payload["hourly"]["time"], utc=True)
        values = np.array(payload["hourly"]["precipitation"], dtype=np.float32)
        values[values < 0] = np.nan
        series = pd.Series(values, index=times, name="precipitation_mm_h").sort_index()
        n_valid = int(np.isfinite(values).sum())
        click.echo(f"{n_valid:,} valid obs")
        chunks.append(series)
        time.sleep(0.5)

    combined = pd.concat(chunks).sort_index()
    return combined[~combined.index.duplicated(keep="first")]
```

- [ ] **Step 4: Remove the function definition from `fit_pluvial_baseline_era5.py`**

In `scripts/fit_pluvial_baseline_era5.py`:

**Remove** top-level `import requests` (line ~61) — it was only used inside `fetch_hourly_precip_era5land`.

**Remove** the two constants below `ERA5_LAND_START_YEAR` and `OPEN_METEO_ARCHIVE_URL` (lines ~80-81):
```python
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/era5"
ERA5_LAND_START_YEAR = 1950   # ERA5-Land starts 1950; we use 2001+ for SEA cities
```

**Remove** the entire `fetch_hourly_precip_era5land` function definition (lines ~88-140).

**Update** the `gev_utils` import block to include the moved function:

Old:
```python
from scripts.gev_utils import (
    rolling_accumulation,
    annual_maxima,
    fit_gev,
    gev_return_level,
)
```

New:
```python
from scripts.gev_utils import (
    rolling_accumulation,
    annual_maxima,
    fit_gev,
    gev_return_level,
    fetch_hourly_precip_era5land,
)
```

- [ ] **Step 5: Update import in `validate_pluvial_idf_anchors.py`**

In `scripts/validate_pluvial_idf_anchors.py`, change line ~53:

Old:
```python
from scripts.fit_pluvial_baseline_era5 import fetch_hourly_precip_era5land
```

New:
```python
from scripts.gev_utils import fetch_hourly_precip_era5land
```

- [ ] **Step 6: Run all three tests — expect PASS**

```
pytest tests/test_fluvial_redesign.py::test_gev_utils_exports_era5land_fetch \
       tests/test_fluvial_redesign.py::test_pluvial_script_no_longer_defines_fetch \
       tests/test_fluvial_redesign.py::test_pluvial_validator_imports_from_gev_utils -v
```

Expected: 3 PASS.

- [ ] **Step 7: Run full suite — no regressions**

```
pytest -v
```

Expected: 28 passed, 1 skipped (same as before).

- [ ] **Step 8: Commit**

```bash
git add scripts/gev_utils.py scripts/fit_pluvial_baseline_era5.py \
        scripts/validate_pluvial_idf_anchors.py tests/test_fluvial_redesign.py
git commit -m "refactor: move fetch_hourly_precip_era5land to gev_utils (Issue #20)"
```

---

### Task 2: Migrate `fit_fluvial_baseline_era5.py` to ERA5-Land

**Files:**
- Modify: `scripts/fit_fluvial_baseline_era5.py`
- Modify: `tests/test_fluvial_redesign.py`

- [ ] **Step 1: Add six failing tests to `tests/test_fluvial_redesign.py`**

Append to the end of the file:

```python
# ---------------------------------------------------------------------------
# Task 2 — fluvial script migrated to ERA5-Land
# ---------------------------------------------------------------------------

def test_fluvial_script_has_no_precip_scale():
    source = Path("scripts/fit_fluvial_baseline_era5.py").read_text(encoding="utf-8")
    assert "precip_scale" not in source


def test_fluvial_script_uses_open_meteo_not_nasa():
    source = Path("scripts/fit_fluvial_baseline_era5.py").read_text(encoding="utf-8")
    assert "open-meteo.com" in source
    assert "power.larc.nasa.gov" not in source


def test_fluvial_xi_max_default_is_030():
    source = Path("scripts/fit_fluvial_baseline_era5.py").read_text(encoding="utf-8")
    # default=0.5 must be gone; default=0.30 must be present
    assert "default=0.5," not in source
    assert "default=0.30" in source


def test_scs_effective_runoff_basic():
    from scripts.fit_fluvial_baseline_era5 import scs_effective_runoff
    # CN=85: S=44.82, Ia=8.96; P=200 -> Q=(191.04)^2/235.86 ≈ 154.7 mm
    result = scs_effective_runoff(200.0, 85.0)
    assert 140.0 < result < 170.0


def test_scs_effective_runoff_below_ia():
    from scripts.fit_fluvial_baseline_era5 import scs_effective_runoff
    # CN=85: Ia=8.96 mm; P=5 mm < Ia -> 0
    result = scs_effective_runoff(5.0, 85.0)
    assert result == 0.0


def test_mannings_stage_positive():
    from scripts.fit_fluvial_baseline_era5 import mannings_stage
    # Q=10 m³/s, w=10 m, n=0.04, S=0.002 -> d ≈ 0.93 m
    result = mannings_stage(10.0, 10.0, 0.04, 0.002)
    assert result > 0.0
    assert isinstance(result, float)
```

- [ ] **Step 2: Run new tests — expect failures**

```
pytest tests/test_fluvial_redesign.py::test_fluvial_script_has_no_precip_scale \
       tests/test_fluvial_redesign.py::test_fluvial_script_uses_open_meteo_not_nasa \
       tests/test_fluvial_redesign.py::test_fluvial_xi_max_default_is_030 -v
```

Expected: 3 FAIL (script still references MERRA-2 / precip_scale / old default).

- [ ] **Step 3: Rewrite `scripts/fit_fluvial_baseline_era5.py`**

Make the following changes to `scripts/fit_fluvial_baseline_era5.py`:

**3a. Update module docstring** — replace the "Data source" section:

Old:
```
Data source
-----------
NASA POWER Hourly API (MERRA-2 / ERA5-corrected reanalysis back-end).
  - No registration or API key required.
  - Same source as fit_pluvial_baseline_era5.py.
  - Use --cache-precip to share the downloaded data between both scripts.
```

New:
```
Data source
-----------
ERA5-Land via Open-Meteo Archive API (free, no key, CC-BY 4.0).
  - URL : https://archive-api.open-meteo.com/v1/era5
  - Resolution: ~9 km; available 1950–present.
  - Same source and fetch function as fit_pluvial_baseline_era5.py.
  - Use --cache-precip to share the downloaded data between both scripts.
```

**3b. Remove the MERRA-2 URL constants** (lines ~99-103):

Remove:
```python
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"
# NASA POWER hourly data is available from 2001-01-01 onwards.
NASA_POWER_START_YEAR = 2001
```

**3c. Remove the entire `fetch_hourly_precip` function** (the MERRA-2 function, lines ~111-180). It starts with:

```python
def fetch_hourly_precip(
    lat: float,
```

and ends just before `# ---------------------------------------------------------------------------` comment before `# Statistics`.

**3d. Update the gev_utils import block** to include `fetch_hourly_precip_era5land`:

Old:
```python
from scripts.gev_utils import (
    rolling_accumulation,
    annual_maxima,
    fit_gev,
    gev_return_level,
)
```

New:
```python
from scripts.gev_utils import (
    rolling_accumulation,
    annual_maxima,
    fit_gev,
    gev_return_level,
    fetch_hourly_precip_era5land,
)
```

**3e. Remove the `--precip-scale` CLI option** (the full `@click.option` block including its multi-line `help=`):

Remove:
```python
@click.option(
    "--precip-scale",
    "precip_scale",
    type=float,
    default=1.0,
    show_default=True,
    help=(
        "Multiplicative bias-correction factor applied to raw MERRA-2 hourly "
        "precipitation before GEV fitting. Bangkok: ~0.18. Singapore: 1.0."
    ),
)
```

**3f. Update `--xi-max` default** from `0.5` to `0.30`:

Old:
```python
    default=0.5,
    show_default=True,
    help=(
        "Maximum allowed GEV shape parameter xi. Re-fits with fixed shape when "
        "unconstrained MLE exceeds this bound (prevents Frechet explosion)."
    ),
```

New:
```python
    default=0.30,
    show_default=True,
    help=(
        "Maximum allowed GEV shape parameter xi. Re-fits with fixed shape when "
        "unconstrained MLE exceeds this bound (prevents Frechet explosion). "
        "0.30 caps Frechet tails for tropical 24h precipitation."
    ),
```

**3g. Remove `precip_scale` from the `cli()` function signature**:

Old:
```python
    precip_scale: float,
    xi_max: float,
```

New:
```python
    xi_max: float,
```

**3h. Replace the MERRA-2 download block with ERA5-Land**:

Old (inside `cli()`):
```python
    if cache_path is not None and Path(cache_path).exists():
        click.echo(f"Loading cached precipitation from {cache_path} ...")
        precip = pd.read_parquet(cache_path).squeeze()
        if not isinstance(precip.index, pd.DatetimeIndex):
            precip.index = pd.to_datetime(precip.index, utc=True)
        elif precip.index.tzinfo is None:
            precip.index = precip.index.tz_localize("UTC")
        click.echo(f"  {len(precip):,} hourly records ({precip.index[0].year}–{precip.index[-1].year}).")
    else:
        click.echo(
            f"Downloading hourly precipitation "
            f"({lat}°N, {lon}°E) via NASA POWER, {start_year}–{end_year} ..."
        )
        precip = fetch_hourly_precip(lat, lon, start_year, end_year)
        n_valid = int(precip.notna().sum())
        click.echo(f"  Total: {len(precip):,} hourly records, {n_valid:,} non-NaN.")

        if cache_path is not None:
            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
            precip.to_frame().to_parquet(cache_path)
            click.echo(f"  Saved to cache: {cache_path}")

    # ------------------------------------------------------------------
    # 1b. Bias correction
    # ------------------------------------------------------------------
    if abs(precip_scale - 1.0) > 1e-6:
        click.echo(f"Applying precipitation bias correction: x{precip_scale:.4f}")
        precip = precip * precip_scale
```

New:
```python
    if cache_path is not None and Path(cache_path).exists():
        click.echo(f"Loading cached ERA5-Land precipitation from {cache_path} ...")
        precip = pd.read_parquet(cache_path).squeeze()
        if not isinstance(precip.index, pd.DatetimeIndex):
            precip.index = pd.to_datetime(precip.index, utc=True)
        elif precip.index.tzinfo is None:
            precip.index = precip.index.tz_localize("UTC")
        click.echo(f"  {len(precip):,} hourly records ({precip.index[0].year}–{precip.index[-1].year}).")
    else:
        click.echo(
            f"Downloading ERA5-Land hourly precipitation "
            f"({lat}°N, {lon}°E) via Open-Meteo, {start_year}–{end_year} ..."
        )
        precip = fetch_hourly_precip_era5land(lat, lon, start_year, end_year)
        n_valid = int(precip.notna().sum())
        click.echo(f"  Total: {len(precip):,} hourly records, {n_valid:,} non-NaN.")

        if cache_path is not None:
            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
            precip.to_frame().to_parquet(cache_path)
            click.echo(f"  Saved to cache: {cache_path}")
```

**3i. Update `source_note` in output rows**:

Old:
```python
                    f"NASA POWER MERRA-2 ({lat}N {lon}E); "
```

New:
```python
                    f"ERA5-Land via Open-Meteo Archive ({lat}N {lon}E); "
```

- [ ] **Step 4: Run all nine tests — expect PASS**

```
pytest tests/test_fluvial_redesign.py -v
```

Expected: 9 PASS (3 from Task 1 + 6 new).

- [ ] **Step 5: Run full suite — no regressions**

```
pytest -v
```

Expected: 34 passed, 1 skipped.

- [ ] **Step 6: Commit**

```bash
git add scripts/fit_fluvial_baseline_era5.py tests/test_fluvial_redesign.py
git commit -m "feat: migrate fit_fluvial_baseline_era5.py from MERRA-2 to ERA5-Land (Issue #20)"
```

---

### Task 3: Update `run_city_pipeline.py`

**Files:**
- Modify: `scripts/run_city_pipeline.py:160-165,348,393-450`
- Modify: `tests/test_fluvial_redesign.py`

- [ ] **Step 1: Add two failing tests**

Append to `tests/test_fluvial_redesign.py`:

```python
# ---------------------------------------------------------------------------
# Task 3 — pipeline default updated
# ---------------------------------------------------------------------------

def test_fit_fluvial_default_follows_fit_era5():
    source = Path("scripts/run_city_pipeline.py").read_text(encoding="utf-8")
    assert "do_fit_fluvial = False if fit_fluvial_override is None" not in source
    assert "do_fit_fluvial = fit_era5 if fit_fluvial_override is None" in source


def test_pipeline_merra2_warning_removed():
    source = Path("scripts/run_city_pipeline.py").read_text(encoding="utf-8")
    assert "WARNING: fluvial still uses MERRA-2" not in source
```

- [ ] **Step 2: Run new tests — expect FAIL**

```
pytest tests/test_fluvial_redesign.py::test_fit_fluvial_default_follows_fit_era5 \
       tests/test_fluvial_redesign.py::test_pipeline_merra2_warning_removed -v
```

Expected: 2 FAIL.

- [ ] **Step 3: Update the `--fit-fluvial/--no-fit-fluvial` help string**

In `scripts/run_city_pipeline.py`, replace lines ~160-165:

Old:
```python
@click.option(
    "--fit-fluvial/--no-fit-fluvial", "fit_fluvial_override", default=None,
    help="Override --fit-era5 for fluvial only.  "
         "Default is --no-fit-fluvial because fluvial still uses MERRA-2 (wet-biased) "
         "pending migration to ERA5-Land.  Re-fitting overwrites calibrated baseline "
         "rows with uncorrected MERRA-2 values that saturate the stage cap.  "
         "Set --fit-fluvial explicitly only after the ERA5-Land fluvial migration.",
)
```

New:
```python
@click.option(
    "--fit-fluvial/--no-fit-fluvial", "fit_fluvial_override", default=None,
    help="Override --fit-era5 for fluvial only.  "
         "Default follows --fit-era5 (True when not disabled).  "
         "Pass --no-fit-fluvial to preserve existing fluvial baseline rows.",
)
```

- [ ] **Step 4: Update the cache path name to `era5land_` prefix**

In `scripts/run_city_pipeline.py`, line ~348:

Old:
```python
    era5_cache_fluvial = Path("cache") / f"era5_{city.slug}_fluvial.parquet"
```

New:
```python
    era5_cache_fluvial = Path("cache") / f"era5land_{city.slug}_fluvial.parquet"
```

- [ ] **Step 5: Flip the `do_fit_fluvial` default**

In `scripts/run_city_pipeline.py`, line ~399:

Old:
```python
    do_fit_fluvial = False if fit_fluvial_override is None else fit_fluvial_override
```

New:
```python
    do_fit_fluvial = fit_era5 if fit_fluvial_override is None else fit_fluvial_override
```

- [ ] **Step 6: Remove the MERRA-2 warning; update the section header and skip message**

In `scripts/run_city_pipeline.py`, replace lines ~421-450:

Old:
```python
    # ------------------------------------------------------------------
    # 0b. Fluvial baseline (MERRA-2 via NASA POWER — migration pending)
    # ------------------------------------------------------------------
    if do_fit_fluvial:
        click.echo("\n=== Step 0b: Fit fluvial baseline (MERRA-2) ===")
        click.echo(
            "  WARNING: fluvial still uses MERRA-2 (wet-biased for tropical SEA).\n"
            "  Re-fitting will overwrite calibrated baseline rows.  Use --no-fit-fluvial\n"
            "  (the default) to preserve existing rows until ERA5-Land migration."
        )
        _run([
```

New:
```python
    # ------------------------------------------------------------------
    # 0b. Fluvial baseline (ERA5-Land via Open-Meteo)
    # ------------------------------------------------------------------
    if do_fit_fluvial:
        click.echo("\n=== Step 0b: Fit fluvial baseline (ERA5-Land) ===")
        _run([
```

Also update the `else` branch skip message (~lines 447-450):

Old:
```python
    else:
        click.echo(
            "\n[skip] --no-fit-fluvial (default): preserving existing fluvial baseline rows.\n"
            "  Fluvial ERA5-Land migration pending.  Use --fit-fluvial to re-fit with MERRA-2."
        )
```

New:
```python
    else:
        click.echo("\n[skip] --no-fit-fluvial: reusing existing fluvial baseline rows.")
```

- [ ] **Step 7: Run all tests — expect PASS**

```
pytest tests/test_fluvial_redesign.py -v
```

Expected: 11 PASS.

- [ ] **Step 8: Run full suite**

```
pytest -v
```

Expected: 36 passed, 1 skipped.

- [ ] **Step 9: Commit**

```bash
git add scripts/run_city_pipeline.py tests/test_fluvial_redesign.py
git commit -m "feat: re-enable --fit-fluvial by default after ERA5-Land migration (Issue #20)"
```

---

### Task 4: Create `validate_fluvial_idf_anchors.py`

**Files:**
- Create: `scripts/validate_fluvial_idf_anchors.py`
- Modify: `tests/test_fluvial_redesign.py`

- [ ] **Step 1: Add three failing tests**

Append to `tests/test_fluvial_redesign.py`:

```python
# ---------------------------------------------------------------------------
# Task 4 — fluvial IDF anchor validator
# ---------------------------------------------------------------------------

def test_validate_fluvial_idf_anchors_importable():
    import scripts.validate_fluvial_idf_anchors as mod
    assert hasattr(mod, "ANCHORS")
    assert hasattr(mod, "WINDOW_H")


def test_validate_fluvial_uses_24h_window():
    source = Path("scripts/validate_fluvial_idf_anchors.py").read_text(encoding="utf-8")
    assert "WINDOW_H = 24" in source


def test_validate_fluvial_anchors_cover_active_cities():
    from scripts.validate_fluvial_idf_anchors import ANCHORS
    slugs = {a[0] for a in ANCHORS}
    expected = {
        "singapore", "kuala_lumpur", "klang_shah_alam", "subang_langat",
        "bangkok", "bangkok_chao_phraya", "jakarta", "tangerang", "bekasi_depok",
    }
    assert expected.issubset(slugs)
```

- [ ] **Step 2: Run new tests — expect FAIL**

```
pytest tests/test_fluvial_redesign.py::test_validate_fluvial_idf_anchors_importable \
       tests/test_fluvial_redesign.py::test_validate_fluvial_uses_24h_window \
       tests/test_fluvial_redesign.py::test_validate_fluvial_anchors_cover_active_cities -v
```

Expected: 3 FAIL (module does not exist).

- [ ] **Step 3: Create `scripts/validate_fluvial_idf_anchors.py`**

```python
"""
Cross-check ERA5-Land 24h GEV fits against published national 24h IDF anchors.

For each active city, fetch (or load from cache) the hourly ERA5-Land
precipitation, compute the 24h-rolling-sum GEV return level at RP10, and
compare with the cited published 24h national design-rainfall benchmark.

Tolerance: +/- 30 % (wider than pluvial 25 % because ERA5-Land gauge-bias
correction is strongest at daily timescales, but IDF design safety factors
and grid averaging still introduce ~10-20 % residual uncertainty).

Anchors (24h design rainfall, RP10):
  Singapore        : PUB/MSS ~ 180 mm
  Kuala Lumpur (+) : JPS DID Malaysia ~ 200 mm
  Bangkok (+)      : TMD Thailand ~ 170 mm
  Jakarta (+)      : BMKG Indonesia ~ 180 mm

(+) extended to supplementary configs of the same country.

Usage
-----
    python scripts/validate_fluvial_idf_anchors.py
    python scripts/validate_fluvial_idf_anchors.py --city singapore

Exit codes
----------
    0 : every checked city is within +/- 30 %
    1 : one or more cities deviate beyond +/- 30 %
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.cities import CITIES
from scripts.gev_utils import (
    rolling_accumulation,
    annual_maxima,
    fit_gev,
    gev_return_level,
    fetch_hourly_precip_era5land,
)

# (city_slug, anchor_rp, anchor_mm_24h, source)
ANCHORS: list[tuple[str, int, float, str]] = [
    ("singapore",           10, 180.0, "PUB/MSS Singapore RP10 24h IDF"),
    ("kuala_lumpur",        10, 200.0, "JPS DID Malaysia RP10 24h IDF"),
    ("klang_shah_alam",     10, 200.0, "JPS DID Malaysia RP10 24h IDF"),
    ("subang_langat",       10, 200.0, "JPS DID Malaysia RP10 24h IDF"),
    ("bangkok",             10, 170.0, "TMD Thailand RP10 24h IDF"),
    ("bangkok_chao_phraya", 10, 170.0, "TMD Thailand RP10 24h IDF"),
    ("jakarta",             10, 180.0, "BMKG Indonesia RP10 24h IDF"),
    ("tangerang",           10, 180.0, "BMKG Indonesia RP10 24h IDF"),
    ("bekasi_depok",        10, 180.0, "BMKG Indonesia RP10 24h IDF"),
]

DEVIATION_TOLERANCE = 0.30   # +/- 30 %
WINDOW_H = 24
START_YEAR = 2001
END_YEAR = 2024
CACHE_DIR = PROJECT_ROOT / "cache"


def _load_or_fetch(slug: str, lat: float, lon: float) -> pd.Series:
    cache_path = CACHE_DIR / f"era5land_{slug}_fluvial.parquet"
    if cache_path.exists():
        click.echo(f"  [{slug}] using cache {cache_path.name}")
        s = pd.read_parquet(cache_path).squeeze()
        if not isinstance(s.index, pd.DatetimeIndex):
            s.index = pd.to_datetime(s.index, utc=True)
        elif s.index.tzinfo is None:
            s.index = s.index.tz_localize("UTC")
        return s
    click.echo(f"  [{slug}] downloading ERA5-Land ...")
    s = fetch_hourly_precip_era5land(lat, lon, START_YEAR, END_YEAR)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    s.to_frame().to_parquet(cache_path)
    return s


def _gev_rp_value(series: pd.Series, rp: int, window_h: int = WINDOW_H) -> float:
    acc = rolling_accumulation(series, window_h)
    maxima = annual_maxima(acc)
    if len(maxima) < 5:
        raise ValueError(f"only {len(maxima)} annual maxima; need >=5")
    arr = np.array(list(maxima.values()), dtype=np.float64)
    c, loc, scale = fit_gev(arr)
    return gev_return_level(c, loc, scale, rp)


@click.command()
@click.option("--city", "city_slug", default=None,
              help="Validate one city; omit to validate all anchored cities.")
def cli(city_slug: str | None) -> None:
    if city_slug is not None:
        anchors = [a for a in ANCHORS if a[0] == city_slug]
        if not anchors:
            raise click.ClickException(
                f"No anchor for {city_slug!r}.  Anchored cities: "
                f"{', '.join(a[0] for a in ANCHORS)}"
            )
    else:
        anchors = ANCHORS

    sep = "=" * 80
    click.echo(sep)
    click.echo(
        f"Fluvial IDF anchor validation  "
        f"(24h RP10, tolerance +/- {DEVIATION_TOLERANCE:.0%})"
    )
    click.echo(sep)
    click.echo(
        f"{'City':<22}{'RP':>4}  {'Anchor (mm)':>12}  "
        f"{'ERA5-Land':>12}  {'Dev':>7}  Verdict"
    )
    click.echo("-" * 80)

    failures: list[str] = []
    for slug, rp, anchor_mm, source in anchors:
        if slug not in CITIES:
            click.echo(
                f"{slug:<22}{rp:>4}  {anchor_mm:>12.1f}  "
                f"{'N/A':>12}  {'-':>7}  SKIP (not in CITIES)"
            )
            continue
        cfg = CITIES[slug]
        try:
            series = _load_or_fetch(slug, cfg.era5_lat, cfg.era5_lon)
            era5_mm = _gev_rp_value(series, rp)
        except Exception as exc:
            click.echo(
                f"{slug:<22}{rp:>4}  {anchor_mm:>12.1f}  "
                f"{'ERROR':>12}  {'-':>7}  FAIL ({exc})"
            )
            failures.append(f"{slug}: {exc}")
            continue

        dev = (era5_mm - anchor_mm) / anchor_mm
        verdict = "PASS" if abs(dev) <= DEVIATION_TOLERANCE else "FAIL"
        click.echo(
            f"{slug:<22}{rp:>4}  {anchor_mm:>12.1f}  "
            f"{era5_mm:>12.1f}  {dev:>+7.1%}  {verdict}"
        )
        if verdict == "FAIL":
            failures.append(
                f"{slug}: ERA5={era5_mm:.1f} mm vs anchor {anchor_mm:.1f} mm "
                f"({dev:+.1%}; source: {source})"
            )

    click.echo(sep)
    if failures:
        click.echo(
            f"FAIL: {len(failures)} city(ies) outside +/-{DEVIATION_TOLERANCE:.0%}:"
        )
        for f in failures:
            click.echo(f"  - {f}")
        click.echo(
            "\nDocument deviations in scripts/cities.py notes.  "
            "Do NOT introduce a multiplicative scaling factor."
        )
        sys.exit(1)
    else:
        click.echo("All checked cities within tolerance.")
        sys.exit(0)


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run all tests — expect PASS**

```
pytest tests/test_fluvial_redesign.py -v
```

Expected: 14 PASS.

- [ ] **Step 5: Run full suite**

```
pytest -v
```

Expected: 41 passed, 1 skipped.

- [ ] **Step 6: Commit**

```bash
git add scripts/validate_fluvial_idf_anchors.py tests/test_fluvial_redesign.py
git commit -m "feat: add validate_fluvial_idf_anchors.py (24h ERA5-Land vs national IDF, Issue #20)"
```

---

### Task 5: Refit all city baseline CSVs

**Files:**
- Modify: `data/singapore/hazard_baseline_template.csv`
- Modify: `data/kuala_lumpur/hazard_baseline_template.csv`
- Modify: `data/klang_shah_alam/hazard_baseline_template.csv`
- Modify: `data/subang_langat/hazard_baseline_template.csv`
- Modify: `data/bangkok/hazard_baseline_template.csv`
- Create:  `data/bangkok_chao_phraya/hazard_baseline_template.csv` (directory does not exist yet)
- Modify: `data/jakarta/hazard_baseline_template.csv`
- Modify: `data/tangerang/hazard_baseline_template.csv`
- Modify: `data/bekasi_depok/hazard_baseline_template.csv`

**Note:** `bangkok_chao_phraya` has no data directory yet; the script creates it automatically via `output_path.parent.mkdir(parents=True, exist_ok=True)`. Its large catchment parameters (`catchment_km2=160000`, `channel_slope=0.00005`) will produce stages hitting the `max_stage_m=8.0 m` cap at most RPs — this is expected and documented behaviour for the supplementary Chao Phraya config.

- [ ] **Step 1: Dry-run Singapore first**

```bash
python scripts/fit_fluvial_baseline_era5.py \
  --lat 1.2903 --lon 103.8519 \
  --curve-number 85.0 --catchment-km2 10.0 --time-of-conc 0.5 \
  --channel-width 10.0 --mannings-n 0.04 --channel-slope 0.002 \
  --dry-run
```

Expected: table printed, no file written. Verify RP2 stage ~1.0–2.0 m, monotonically increasing.

- [ ] **Step 2: Refit Singapore**

```bash
python scripts/fit_fluvial_baseline_era5.py \
  --lat 1.2903 --lon 103.8519 \
  --curve-number 85.0 --catchment-km2 10.0 --time-of-conc 0.5 \
  --channel-width 10.0 --mannings-n 0.04 --channel-slope 0.002 \
  --cache-precip cache/era5land_singapore_fluvial.parquet \
  --output data/singapore/hazard_baseline_template.csv
```

Expected: `Updated data/singapore/hazard_baseline_template.csv with 9 fluvial rows.`
Verify `source_note` in the CSV now says `ERA5-Land via Open-Meteo Archive`.

- [ ] **Step 3: Refit Kuala Lumpur**

```bash
python scripts/fit_fluvial_baseline_era5.py \
  --lat 3.139 --lon 101.6869 \
  --curve-number 82.0 --catchment-km2 30.0 --time-of-conc 1.5 \
  --channel-width 30.0 --mannings-n 0.035 --channel-slope 0.002 \
  --cache-precip cache/era5land_kuala_lumpur_fluvial.parquet \
  --output data/kuala_lumpur/hazard_baseline_template.csv
```

- [ ] **Step 4: Refit Klang Shah Alam**

```bash
python scripts/fit_fluvial_baseline_era5.py \
  --lat 3.07 --lon 101.515 \
  --curve-number 80.0 --catchment-km2 50.0 --time-of-conc 2.0 \
  --channel-width 40.0 --mannings-n 0.035 --channel-slope 0.001 \
  --cache-precip cache/era5land_klang_shah_alam_fluvial.parquet \
  --output data/klang_shah_alam/hazard_baseline_template.csv
```

- [ ] **Step 5: Refit Subang Langat**

```bash
python scripts/fit_fluvial_baseline_era5.py \
  --lat 2.975 --lon 101.76 \
  --curve-number 80.0 --catchment-km2 25.0 --time-of-conc 1.25 \
  --channel-width 20.0 --mannings-n 0.035 --channel-slope 0.0018 \
  --cache-precip cache/era5land_subang_langat_fluvial.parquet \
  --output data/subang_langat/hazard_baseline_template.csv
```

- [ ] **Step 6: Refit Bangkok**

```bash
python scripts/fit_fluvial_baseline_era5.py \
  --lat 13.7563 --lon 100.5018 \
  --curve-number 80.0 --catchment-km2 5.0 --time-of-conc 0.5 \
  --channel-width 15.0 --mannings-n 0.025 --channel-slope 0.002 \
  --cache-precip cache/era5land_bangkok_fluvial.parquet \
  --output data/bangkok/hazard_baseline_template.csv
```

- [ ] **Step 7: Refit Bangkok Chao Phraya** (creates directory)

```bash
python scripts/fit_fluvial_baseline_era5.py \
  --lat 13.7563 --lon 100.5018 \
  --curve-number 82.0 --catchment-km2 160000.0 --time-of-conc 168.0 \
  --channel-width 350.0 --mannings-n 0.035 --channel-slope 0.00005 \
  --cache-precip cache/era5land_bangkok_fluvial.parquet \
  --output data/bangkok_chao_phraya/hazard_baseline_template.csv
```

Note: stage will be capped at `max_stage_m=8.0 m` at most/all RPs — expected; ERA5 single-point is not meaningful for the Chao Phraya mainstem.

- [ ] **Step 8: Refit Jakarta**

```bash
python scripts/fit_fluvial_baseline_era5.py \
  --lat -6.2088 --lon 106.8456 \
  --curve-number 82.0 --catchment-km2 10.0 --time-of-conc 0.75 \
  --channel-width 15.0 --mannings-n 0.033 --channel-slope 0.0015 \
  --cache-precip cache/era5land_jakarta_fluvial.parquet \
  --output data/jakarta/hazard_baseline_template.csv
```

- [ ] **Step 9: Refit Tangerang**

```bash
python scripts/fit_fluvial_baseline_era5.py \
  --lat -6.225 --lon 106.625 \
  --curve-number 82.0 --catchment-km2 20.0 --time-of-conc 1.0 \
  --channel-width 20.0 --mannings-n 0.035 --channel-slope 0.001 \
  --cache-precip cache/era5land_tangerang_fluvial.parquet \
  --output data/tangerang/hazard_baseline_template.csv
```

- [ ] **Step 10: Refit Bekasi Depok**

```bash
python scripts/fit_fluvial_baseline_era5.py \
  --lat -6.3 --lon 107.0 \
  --curve-number 82.0 --catchment-km2 20.0 --time-of-conc 1.0 \
  --channel-width 25.0 --mannings-n 0.033 --channel-slope 0.0015 \
  --cache-precip cache/era5land_bekasi_depok_fluvial.parquet \
  --output data/bekasi_depok/hazard_baseline_template.csv
```

- [ ] **Step 11: Spot-check all updated CSVs**

For each city CSV, verify:
1. `fluvial` rows have `source_note` containing `ERA5-Land via Open-Meteo Archive`
2. `baseline_water_level_m` is monotonically non-decreasing across return periods
3. Non-fluvial rows (coastal, pluvial) are unchanged

```bash
python -c "
import pandas as pd, pathlib
for p in sorted(pathlib.Path('data').glob('*/hazard_baseline_template.csv')):
    df = pd.read_csv(p)
    fl = df[df.hazard_type == 'fluvial']
    if fl.empty:
        print(f'{p.parent.name}: no fluvial rows')
        continue
    ok_src = fl['source_note'].str.contains('ERA5-Land', na=False).all()
    stages = fl.sort_values('return_period')['baseline_water_level_m'].tolist()
    mono = all(a <= b for a, b in zip(stages, stages[1:]))
    print(f'{p.parent.name}: src_ok={ok_src} mono={mono} stages={[round(s,3) for s in stages]}')
"
```

- [ ] **Step 12: Run full test suite — no regressions**

```
pytest -v
```

Expected: 41 passed, 1 skipped.

- [ ] **Step 13: Commit all CSVs**

```bash
git add data/
git commit -m "feat: refit all city fluvial baselines with ERA5-Land source (Issue #20)"
```

---

### Task 6: Update `docs/hazard_methodology_comparison.md`

**Files:**
- Modify: `docs/hazard_methodology_comparison.md`

- [ ] **Step 1: Add 2026-04-28 entry to the Recent Fixes table**

Find the Recent Fixes table (around line 23-28). Add a new row immediately after the 2026-04-27 MSL offset entry:

```markdown
| 2026-04-28 | Fluvial ERA5-Land migration (Issue #20) | `fit_fluvial_baseline_era5.py` migrated from NASA POWER MERRA-2 to ERA5-Land via Open-Meteo Archive. `--precip-scale` removed; `xi_max` default tightened 0.5 → 0.30; `--fit-fluvial` re-enabled by default. `fetch_hourly_precip_era5land()` moved to `gev_utils.py` (shared with pluvial). `validate_fluvial_idf_anchors.py` added (24h RP10 vs national IDF, ±30% tolerance). All 9 active city baselines refit. |
```

- [ ] **Step 2: Mark Issue #20 RESOLVED**

Find Issue #20 in the issues table (around line 520). Change its status cell:

Old:
```markdown
| 20 | All cities | Fluvial | **Fluvial pipeline still uses MERRA-2** (no longer corrected by `precip_scale` since the 2026-04-26 redesign). Re-fitting now produces unusable stages (saturated at 8 m cap → zero overbank). Calibrated baseline rows preserved by `--no-fit-fluvial` default. **Fluvial ERA5-Land migration is the next major redesign.** | **Open — Critical** |
```

New:
```markdown
| 20 | All cities | Fluvial | ~~Fluvial pipeline still uses MERRA-2.~~ **FIXED 2026-04-28**: Migrated to ERA5-Land via Open-Meteo. `--precip-scale` removed; `--fit-fluvial` re-enabled by default. All 9 active city baselines refit. Validator: `scripts/validate_fluvial_idf_anchors.py`. | **RESOLVED** |
```

- [ ] **Step 3: Update §3.1 fluvial data source reference**

Find the §3.1 section (search for `MERRA-2 wet bias`). Update the paragraph that describes the fluvial source:

Old (find and replace this sentence):
```
**MERRA-2 wet bias:** MERRA-2 substantially overestimates convective precipitation in tropical SEA. The `precip_scale` factors (0.10–0.18) were calibrated by comparing MERRA-2 annual maxima to local gauge IDF statistics. Singapore's authoritative IDF data (PUB 24h, MSS 6h) served as the reference benchmark for this calibration.
```

New:
```
**Fluvial rainfall source (ERA5-Land):** The fluvial pipeline uses ERA5-Land via Open-Meteo Archive (same source as pluvial). MERRA-2 was retired in 2026-04-28 (Issue #20): without `precip_scale`, MERRA-2 wet bias saturated Manning's 8 m stage cap at every RP. ERA5-Land 24h daily totals are gauge-bias-corrected and have ≤30% residual deviation from published national 24h IDF anchors (Singapore PUB, JPS Malaysia, TMD Thailand, BMKG Indonesia). No multiplicative correction is applied. Validation: `scripts/validate_fluvial_idf_anchors.py`.
```

- [ ] **Step 4: Run full test suite**

```
pytest -v
```

Expected: 41 passed, 1 skipped.

- [ ] **Step 5: Commit**

```bash
git add docs/hazard_methodology_comparison.md
git commit -m "docs: mark Issue #20 RESOLVED; update §3.1 fluvial data source (ERA5-Land)"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Task 1 = §3.1 shared fetch; Task 2 = §3.2 fluvial script; Task 3 = §3.3 pipeline; Task 4 = §3.4 validator; Task 5 = §5 baselines; Task 6 = §6 docs. All sections covered.
- [x] **No placeholders:** All code blocks are complete. No TBD/TODO.
- [x] **Type consistency:** `fetch_hourly_precip_era5land` signature identical across all tasks. `ANCHORS` type `list[tuple[str, int, float, str]]` consistent between Task 4 implementation and Task 4 test. `WINDOW_H = 24` used in both implementation and test assertion.
- [x] **Bangkok Chao Phraya:** No data directory yet — script creates it; cap behaviour documented in Step 7 note.
- [x] **Cache naming:** `era5land_{slug}_fluvial.parquet` used consistently in pipeline (Task 3 Step 4), validator (Task 4), and refit commands (Task 5).
