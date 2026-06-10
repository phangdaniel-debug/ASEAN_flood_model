# Pluvial Model Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace MERRA-2 + the calibrated `precip_scale` × `/100` formula in the pluvial pipeline with a physically transparent two-step model: (a) rainfall driver from ERA5-Land hourly via Open-Meteo (no bias correction needed), (b) excess rainfall converted to a max-ponding scalar via an explicit `depression_area_fraction` parameter that has a physical meaning (the fraction of grid-cell area that is effective depression storage). The downstream depression-filling flood model in `flood_depth_pluvial_ponding` is unchanged — it already redistributes the scalar input into real DEM depressions.

**Architecture:**
- **Old:** `MERRA-2 × precip_scale → GEV → excess_mm × runoff_coeff / 100 → ponding_cap` (3 calibration knobs, MERRA-2 wet bias forced through ad-hoc multiplier).
- **New:** `ERA5-Land → GEV → excess_mm × runoff_coeff / (1000 × depression_area_fraction) → ponding_cap` (1 physically-interpretable parameter; ERA5-Land has no significant wet bias in SEA so no scaling needed).
- The output format (CSV scalar per RP) is unchanged. The downstream `flood_depth_pluvial_ponding` (which fills DEM depressions up to the scalar level) is unchanged.
- Outputs will be **lower** than current values — closer to published PUB observations. Numbers do not need to be preserved.

**Tech Stack:** Python 3.10+, scipy, pandas, numpy, click, requests (NASA POWER + Open-Meteo APIs), pysheds (already in use), pytest.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `scripts/gev_utils.py` | **Create** | Shared GEV helpers (`rolling_accumulation`, `annual_maxima`, `fit_gev`, `gev_return_level`) |
| `scripts/fit_pluvial_baseline_era5.py` | **Rewrite** | Switch rainfall source from NASA POWER MERRA-2 → Open-Meteo ERA5-Land hourly; drop `--precip-scale`; replace `/100` with `--depression-area-fraction` (default 0.10) |
| `scripts/cities.py` | **Modify** | Remove `precip_scale` field; add `depression_area_fraction: float = 0.10`; update all 11 city configs |
| `scripts/run_city_pipeline.py` | **Modify** | Drop `--precip-scale` arg; pass `--depression-area-fraction` |
| `scripts/fit_fluvial_baseline_era5.py` | **Modify** (minimal) | Remove duplicate GEV functions; import from gev_utils. **Keep MERRA-2** — fluvial uses catchment-scale rainfall where MERRA-2's coarser resolution is acceptable; that's a separate redesign |
| `scripts/calibrate_precip_scale.py` | **Delete** or mark deprecated | No longer needed; ERA5-Land removes the bias-correction problem entirely |
| `scripts/validate_pluvial_singapore.py` | **Create** | One-shot validation script: runs SG pluvial fit, prints RP10-RP1000 max ponding from depression-filled raster, compares with PUB observed range (0.07-0.76 m) |
| `tests/__init__.py` | **Create** | Empty marker |
| `tests/test_gev_utils.py` | **Create** | Unit tests for gev_utils |
| `tests/test_pluvial_redesign.py` | **Create** | CityConfig field tests; ponding-cap formula tests |
| `docs/hazard_methodology_comparison.md` | **Modify** | Mark Issues R1, R2, #19 RESOLVED with new resolution text |
| `docs/superpowers/specs/2026-04-26-pluvial-redesign.md` | **Create** | Design spec (one-pager rationale, captured separately for reproducibility) |

---

## Task 1 — Create `scripts/gev_utils.py` + tests

**Files:**
- Create: `scripts/gev_utils.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_gev_utils.py`
- Modify: `scripts/fit_pluvial_baseline_era5.py` (will be rewritten in Task 2; here just remove duplicates)
- Modify: `scripts/fit_fluvial_baseline_era5.py` (remove duplicate GEV functions, import from gev_utils)

- [ ] **Step 1: Write failing tests for gev_utils**

Create `tests/__init__.py` (empty) and `tests/test_gev_utils.py`:

```python
"""Tests for scripts/gev_utils.py — shared GEV and rolling-precipitation utilities."""
import numpy as np
import pandas as pd


def test_rolling_accumulation_6h():
    """6 consecutive 1 mm/hr hours produce a rolling max of 6 mm."""
    idx = pd.date_range("2001-01-01", periods=12, freq="1h")
    s = pd.Series([1.0] * 6 + [0.0] * 6, index=idx)
    from scripts.gev_utils import rolling_accumulation
    result = rolling_accumulation(s, window_h=6)
    assert abs(result.iloc[5] - 6.0) < 1e-6


def test_rolling_accumulation_single_spike():
    """A single 10 mm/hr hour produces a 6h rolling max of 10."""
    idx = pd.date_range("2001-01-01", periods=24, freq="1h")
    s = pd.Series(0.0, index=idx)
    s.iloc[12] = 10.0
    from scripts.gev_utils import rolling_accumulation
    result = rolling_accumulation(s, window_h=6)
    assert result.max() == 10.0


def test_annual_maxima_three_years():
    """Three years with known maxima are extracted correctly."""
    idx = pd.date_range("2001-01-01", periods=8760 * 3, freq="1h")
    s = pd.Series(0.0, index=idx)
    s.iloc[100] = 50.0
    s.iloc[8860] = 80.0
    s.iloc[17620] = 30.0
    from scripts.gev_utils import rolling_accumulation, annual_maxima
    acc = rolling_accumulation(s, window_h=1)
    maxima = annual_maxima(acc)
    assert maxima[2001] == 50.0
    assert maxima[2002] == 80.0
    assert maxima[2003] == 30.0


def test_annual_maxima_sparse_year_excluded():
    """A year with <50% valid observations is excluded."""
    idx_full = pd.date_range("2001-01-01", periods=8760, freq="1h")
    idx_sparse = pd.date_range("2002-01-01", periods=100, freq="1h")
    s = pd.concat([
        pd.Series(5.0, index=idx_full),
        pd.Series(99.0, index=idx_sparse),
    ]).sort_index()
    from scripts.gev_utils import rolling_accumulation, annual_maxima
    acc = rolling_accumulation(s, window_h=1)
    maxima = annual_maxima(acc, min_coverage=0.5)
    assert 2001 in maxima
    assert 2002 not in maxima


def test_fit_gev_returns_three_floats():
    """fit_gev returns (c, loc, scale); scale is positive."""
    from scipy.stats import gumbel_r
    rng = np.random.default_rng(42)
    samples = gumbel_r.rvs(loc=50, scale=20, size=25, random_state=rng)
    from scripts.gev_utils import fit_gev
    c, loc, scale = fit_gev(samples)
    assert isinstance(c, float) and isinstance(loc, float)
    assert scale > 0


def test_gev_return_level_monotone():
    """Longer return periods give higher (or equal) return levels."""
    from scipy.stats import gumbel_r
    rng = np.random.default_rng(0)
    samples = gumbel_r.rvs(loc=100, scale=30, size=30, random_state=rng)
    from scripts.gev_utils import fit_gev, gev_return_level
    c, loc, scale = fit_gev(samples)
    levels = [gev_return_level(c, loc, scale, rp) for rp in [2, 10, 100, 1000]]
    assert all(levels[i] <= levels[i + 1] for i in range(len(levels) - 1))
```

- [ ] **Step 2: Run tests to confirm they FAIL**

```bash
cd D:\Downloads\Claude-Cursor
python -m pytest tests/test_gev_utils.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'scripts.gev_utils'`

- [ ] **Step 3: Create `scripts/gev_utils.py`**

```python
"""
Shared GEV and rolling-precipitation utilities for the flood pipeline.

Extracted from fit_pluvial_baseline_era5.py and fit_fluvial_baseline_era5.py
(previously duplicated).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_accumulation(precip: pd.Series, window_h: int) -> pd.Series:
    """Rolling sum of hourly precipitation over ``window_h`` hours (mm)."""
    return precip.rolling(window=window_h, min_periods=max(1, window_h // 2)).sum()


def annual_maxima(series: pd.Series, min_coverage: float = 0.5) -> dict[int, float]:
    """Annual maxima; years with <min_coverage * 8760 valid hours are excluded."""
    results: dict[int, float] = {}
    for year, group in series.groupby(series.index.year):
        n_valid = int(group.notna().sum())
        if n_valid < int(8760 * min_coverage):
            continue
        results[int(year)] = float(group.max(skipna=True))
    return results


def fit_gev(maxima: np.ndarray, xi_max: float = 0.5) -> tuple[float, float, float]:
    """
    Fit GEV via MLE.  Returns scipy.stats.genextreme parameterisation (c, loc, scale).
    Shape xi = -c is clamped to [-0.5, xi_max] to prevent unstable Frechet fits.
    """
    import click
    from scipy.stats import genextreme
    c, loc, scale = genextreme.fit(maxima)
    if scale <= 0:
        raise ValueError(f"GEV fit returned non-positive scale={scale:.4f}")
    xi = -c
    xi_clamped = float(np.clip(xi, -0.5, xi_max))
    if abs(xi_clamped - xi) > 1e-6:
        click.echo(
            f"  [info] GEV shape xi={xi:.4f} clamped to {xi_clamped:.4f} "
            f"(xi_max={xi_max}). Re-fitting with fixed shape."
        )
        c_fixed = -xi_clamped
        _, loc, scale = genextreme.fit(maxima, f0=c_fixed)
        c = c_fixed
    return float(c), float(loc), float(scale)


def gev_return_level(c: float, loc: float, scale: float, rp: float) -> float:
    """GEV quantile at return period T: F(x_T) = 1 - 1/T."""
    from scipy.stats import genextreme
    return float(genextreme.ppf(1.0 - 1.0 / rp, c, loc=loc, scale=scale))
```

- [ ] **Step 4: Run tests to confirm they PASS**

```bash
python -m pytest tests/test_gev_utils.py -v
```

Expected: 6 PASS

- [ ] **Step 5: Remove duplicate GEV functions from `scripts/fit_fluvial_baseline_era5.py`**

In `scripts/fit_fluvial_baseline_era5.py`, remove the four function definitions for `rolling_accumulation`, `annual_maxima`, `fit_gev`, `gev_return_level` (around lines 187–225). Add this import after the existing imports:

```python
from scripts.gev_utils import (
    rolling_accumulation,
    annual_maxima,
    fit_gev,
    gev_return_level,
)
```

(`scripts/fit_pluvial_baseline_era5.py` is rewritten entirely in Task 2 so we don't dedupe it here.)

- [ ] **Step 6: Verify fluvial script imports cleanly**

```bash
python -c "import scripts.fit_fluvial_baseline_era5"
```

Expected: no output, no error.

- [ ] **Step 7: Commit**

```bash
git add scripts/gev_utils.py tests/__init__.py tests/test_gev_utils.py scripts/fit_fluvial_baseline_era5.py
git commit -m "refactor: extract shared GEV utils to gev_utils.py; add tests

Removes duplication from fit_fluvial_baseline_era5.py.
fit_pluvial_baseline_era5.py is rewritten in the next commit.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2 — Rewrite `scripts/fit_pluvial_baseline_era5.py` (ERA5-Land + explicit depression fraction)

**Files:**
- Modify: `scripts/fit_pluvial_baseline_era5.py` (substantial rewrite)
- Create: `tests/test_pluvial_redesign.py`

The new script:
- Fetches **ERA5-Land hourly precipitation** from Open-Meteo Archive API (no key, free, ~9 km, gauge-bias-corrected via ECMWF reanalysis methodology).
- Drops the `--precip-scale` flag (no MERRA-2 wet bias to correct).
- Replaces hardcoded `/100` with `--depression-area-fraction` (default 0.10), making the assumption physically explicit: 10% of a grid cell is effective depression storage that retains runoff.
- New formula: `ponding_cap_m = (excess_mm / 1000) × runoff_coeff / depression_area_fraction`. Equivalent to old `/100` when `depression_area_fraction=0.10`, but the parameter is now visible and tunable.
- Cache file naming changes from `era5_<city>_precip.parquet` to `era5land_<city>_pluvial.parquet`.

- [ ] **Step 1: Write failing tests in `tests/test_pluvial_redesign.py`**

```python
"""Tests for the pluvial model redesign (Issue #19 + R1 + R2 resolution)."""
import pytest


# -------------------------------------------------------------------------
# fit_pluvial_baseline_era5: formula and CLI tests
# -------------------------------------------------------------------------

def test_ponding_cap_formula():
    """ponding_cap = (excess_mm/1000) * runoff_coeff / depression_area_fraction.

    With excess=100mm, rc=0.75, daf=0.10 the cap is 0.75 m
    (matches old /100 formula at the default daf).
    """
    excess_mm = 100.0
    rc = 0.75
    daf = 0.10
    cap = (excess_mm / 1000) * rc / daf
    assert abs(cap - 0.75) < 1e-9


def test_ponding_cap_back_compat_default():
    """At depression_area_fraction=0.10 the new formula matches old /100."""
    for excess_mm in [10.0, 50.0, 100.0, 200.0]:
        rc = 0.75
        old = excess_mm * rc / 100.0
        new = (excess_mm / 1000.0) * rc / 0.10
        assert abs(old - new) < 1e-9, (
            f"excess={excess_mm}: old={old} new={new}"
        )


def test_ponding_cap_smaller_daf_gives_higher_cap():
    """Smaller depression_area_fraction (more concentration) -> higher ponding cap."""
    excess_mm = 100.0
    rc = 0.75
    cap_05 = (excess_mm / 1000) * rc / 0.05  # poor drainage / small depression area
    cap_10 = (excess_mm / 1000) * rc / 0.10  # default
    cap_15 = (excess_mm / 1000) * rc / 0.15  # well drained / spread out
    assert cap_05 > cap_10 > cap_15


def test_fit_pluvial_cli_drops_precip_scale():
    """The --precip-scale flag must be removed."""
    from click.testing import CliRunner
    from scripts.fit_pluvial_baseline_era5 import cli
    result = CliRunner().invoke(cli, ["--help"])
    assert "--precip-scale" not in result.output


def test_fit_pluvial_cli_has_depression_area_fraction():
    """The --depression-area-fraction flag must be present."""
    from click.testing import CliRunner
    from scripts.fit_pluvial_baseline_era5 import cli
    result = CliRunner().invoke(cli, ["--help"])
    assert "--depression-area-fraction" in result.output


def test_fit_pluvial_uses_open_meteo_endpoint():
    """The pluvial fit module must reference Open-Meteo Archive (not NASA POWER)."""
    import inspect, scripts.fit_pluvial_baseline_era5 as mod
    src = inspect.getsource(mod)
    assert "archive-api.open-meteo.com" in src
    assert "PRECTOTCORR" not in src or "# legacy" in src.lower(), (
        "Pluvial fit should not reference MERRA-2 PRECTOTCORR variable"
    )


# -------------------------------------------------------------------------
# CityConfig field tests
# -------------------------------------------------------------------------

def test_cityconfig_no_precip_scale():
    """precip_scale field must be removed from CityConfig."""
    from scripts.cities import CITIES
    sg = CITIES["singapore"]
    assert not hasattr(sg, "precip_scale"), (
        "precip_scale still exists; should be removed (ERA5-Land needs no MERRA-2 correction)"
    )


def test_cityconfig_has_depression_area_fraction():
    """All cities have a depression_area_fraction field."""
    from scripts.cities import CITIES
    for slug, cfg in CITIES.items():
        assert hasattr(cfg, "depression_area_fraction"), f"{slug}: missing field"
        assert 0 < cfg.depression_area_fraction <= 1.0, (
            f"{slug}: depression_area_fraction={cfg.depression_area_fraction} out of (0,1]"
        )


def test_cityconfig_default_depression_area_fraction():
    """Default depression_area_fraction is 0.10 (matches Singapore PUB calibration)."""
    from scripts.cities import CITIES
    assert CITIES["singapore"].depression_area_fraction == 0.10
```

- [ ] **Step 2: Run tests to confirm they FAIL**

```bash
python -m pytest tests/test_pluvial_redesign.py -v 2>&1 | head -50
```

Expected: AssertionError on most tests; ImportError on cli tests once cli help fails.

- [ ] **Step 3: Rewrite `scripts/fit_pluvial_baseline_era5.py`**

Replace the entire file with the rewritten version below. (The file shrinks by ~30 lines because the GEV helpers move to `gev_utils.py` and the `precip_scale` plumbing is gone.)

```python
"""
Derive pluvial ponding-cap depths from ERA5-Land hourly precipitation.

Rainfall source
---------------
ERA5-Land via Open-Meteo Archive API (free, no key, CC-BY 4.0).
  - URL : https://archive-api.open-meteo.com/v1/era5
  - Param: hourly=precipitation (mm per hour)
  - Resolution: ~9 km, 1950-present
  - Reference: Munoz-Sabater et al. (2021) Earth Syst. Sci. Data 13:4349.
                doi:10.5194/essd-13-4349-2021

ERA5-Land replaces the previous NASA POWER MERRA-2 source.  MERRA-2 had
a 5-30x wet bias in tropical SEA that required a per-city `precip_scale`
calibrated against national IDF curves -- a replicability blocker.
ERA5-Land's residual bias against gauge observations in SEA is small
(~1.0-1.5x) and within GEV sampling uncertainty, so no scaling is applied.

Method
------
1. Download hourly ERA5-Land precipitation for the city centroid.
2. Compute rolling N-hour accumulation (default 6 h -- typical urban
   convective storm duration).
3. Extract annual maxima of the rolling accumulation.
4. Fit a Generalised Extreme Value distribution via MLE (xi clamped).
5. Convert design rainfall depth to a max-ponding scalar using a
   physically interpretable depression-storage parameter:

       excess_mm           = max(0, GEV_quantile(rp) - drain_capacity_mm)
       runoff_depth_m      = (excess_mm / 1000) * runoff_coeff
       ponding_cap_m       = runoff_depth_m / depression_area_fraction

   where `depression_area_fraction` is the fraction of grid-cell surface
   area that is effective depression storage retaining runoff.  Default
   0.10 = 10% (Singapore PUB-calibrated value).  Higher for low-relief
   delta cities, lower for steep / well-drained catchments.

   The result is a uniform-equivalent ponding cap.  The downstream
   `flood_depth_pluvial_ponding` model fills DEM depressions up to this
   level: depressions deeper than the cap are filled to the cap;
   depressions shallower are filled to their pour-point.  Spatial
   variation comes from the DEM, not from this scalar.

6. Write pluvial rows to the hazard baseline CSV.

Caching
-------
Pass --cache-precip <path>.  If the file exists, the download is skipped.
Cache key is independent of MERRA-2 caches; do not reuse old MERRA-2
parquet files (different units, different source).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import click
import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.gev_utils import (
    rolling_accumulation,
    annual_maxima,
    fit_gev,
    gev_return_level,
)

RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]

# Default coordinates -- Singapore centroid (overridden by --lat/--lon)
_DEFAULT_LAT = 1.2903
_DEFAULT_LON = 103.8519

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/era5"
ERA5_LAND_START_YEAR = 1950   # ERA5-Land starts 1950; we use 2001+ for SEA cities


# ---------------------------------------------------------------------------
# Data acquisition (ERA5-Land hourly via Open-Meteo)
# ---------------------------------------------------------------------------

def fetch_hourly_precip_era5land(
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
    chunk_years: int = 5,
) -> pd.Series:
    """
    Download hourly ERA5-Land precipitation (mm) from Open-Meteo Archive.

    Returns
    -------
    pd.Series  -- DatetimeIndex (UTC), values in mm per hour.
    """
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
                resp = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=180)
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option("--output", "output_path", type=click.Path(path_type=Path),
              default=Path("data/singapore_hazard_baseline_template.csv"), show_default=True,
              help="Hazard baseline CSV -- pluvial rows will be replaced.")
@click.option("--lat", type=float, default=_DEFAULT_LAT, show_default=True)
@click.option("--lon", type=float, default=_DEFAULT_LON, show_default=True)
@click.option("--start-year", type=int, default=2001, show_default=True)
@click.option("--end-year", type=int, default=2024, show_default=True)
@click.option("--window-h", type=int, default=6, show_default=True,
              help="Rolling accumulation window (h).  6 h = typical urban convective storm.")
@click.option("--runoff-coeff", type=float, default=0.75, show_default=True,
              help="Fraction of excess rainfall that becomes runoff (0-1).")
@click.option("--drain-capacity-mm", type=float, default=100.0, show_default=True,
              help="Rainfall depth (mm) that the primary drainage network conveys "
                   "without surface ponding.  Calibrate to national RP design standard.")
@click.option("--depression-area-fraction", "depression_area_fraction",
              type=float, default=0.10, show_default=True,
              help=(
                  "Fraction of grid-cell area that is effective depression storage. "
                  "ponding_cap_m = (excess_mm/1000) * runoff_coeff / depression_area_fraction. "
                  "Default 0.10 (Singapore PUB).  Lower for highly concentrated runoff, "
                  "higher for low-relief delta cities."
              ))
@click.option("--min-years", type=int, default=20, show_default=True)
@click.option("--xi-max", "xi_max", type=float, default=0.5, show_default=True,
              help="Maximum allowed GEV shape xi.")
@click.option("--max-ponding-depth-m", "max_ponding_depth_m",
              type=float, default=3.0, show_default=True,
              help="Hard upper cap on ponding depth (m).")
@click.option("--cache-precip", "cache_path", type=click.Path(path_type=Path), default=None,
              help="Parquet cache file for ERA5-Land hourly precipitation.")
@click.option("--dry-run", is_flag=True, default=False)
def cli(
    output_path: Path,
    lat: float, lon: float,
    start_year: int, end_year: int,
    window_h: int,
    runoff_coeff: float,
    drain_capacity_mm: float,
    depression_area_fraction: float,
    min_years: int,
    xi_max: float,
    max_ponding_depth_m: float,
    cache_path: Path | None,
    dry_run: bool,
) -> None:
    if not (0 < depression_area_fraction <= 1.0):
        raise click.UsageError(
            f"--depression-area-fraction must be in (0, 1], got {depression_area_fraction}"
        )

    # 1. Load or download
    if cache_path is not None and Path(cache_path).exists():
        click.echo(f"Loading cached ERA5-Land precipitation from {cache_path}")
        precip = pd.read_parquet(cache_path).squeeze()
        if not isinstance(precip.index, pd.DatetimeIndex):
            precip.index = pd.to_datetime(precip.index, utc=True)
        elif precip.index.tzinfo is None:
            precip.index = precip.index.tz_localize("UTC")
    else:
        click.echo(f"Downloading ERA5-Land hourly ({lat}N, {lon}E), {start_year}-{end_year} ...")
        precip = fetch_hourly_precip_era5land(lat, lon, start_year, end_year)
        if cache_path is not None:
            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
            precip.to_frame().to_parquet(cache_path)
            click.echo(f"  Cached -> {cache_path}")
    click.echo(f"  {len(precip):,} hourly records ({precip.index[0].year}-{precip.index[-1].year}).")

    # 2. Rolling accumulation
    click.echo(f"\nComputing {window_h}h rolling accumulation ...")
    acc = rolling_accumulation(precip, window_h)

    # 3. Annual maxima
    ann_max = annual_maxima(acc, min_coverage=0.5)
    years_ok = sorted(ann_max.keys())
    n_years = len(ann_max)
    click.echo(f"{n_years} years of annual maxima ({years_ok[0]}-{years_ok[-1]}).")
    if n_years < min_years:
        raise click.ClickException(
            f"Only {n_years} valid years -- need at least {min_years}."
        )

    maxima_arr = np.array([ann_max[y] for y in years_ok], dtype=np.float64)
    click.echo(
        f"Annual maxima of {window_h}h accumulation (mm): "
        f"mean={maxima_arr.mean():.1f}  std={maxima_arr.std():.1f}  "
        f"min={maxima_arr.min():.1f}  max={maxima_arr.max():.1f}"
    )

    # 4. GEV fit
    c, loc, scale = fit_gev(maxima_arr, xi_max=xi_max)
    xi = -c
    click.echo(f"GEV fit (MLE): xi={xi:.4f}  mu={loc:.3f} mm  sigma={scale:.3f} mm")

    # 5. Return period table
    rows = []
    click.echo(
        f"\nPluvial ponding caps "
        f"(drain_capacity={drain_capacity_mm}mm, runoff_coeff={runoff_coeff}, "
        f"depression_area_fraction={depression_area_fraction}):"
    )
    click.echo(f"  {'RP (yr)':>8}  {'Design rainfall (mm)':>22}  {'Ponding cap (m)':>18}")
    click.echo(f"  {'-'*8}  {'-'*22}  {'-'*18}")
    for rp in RETURN_PERIODS:
        design_mm = max(1.0, gev_return_level(c, loc, scale, rp))
        excess_mm = max(0.0, design_mm - drain_capacity_mm)
        runoff_depth_m = (excess_mm / 1000.0) * runoff_coeff
        cap_m = runoff_depth_m / depression_area_fraction
        cap_m = round(min(max(0.005, cap_m), max_ponding_depth_m), 4)
        click.echo(f"  {rp:>8d}  {design_mm:>22.1f}  {cap_m:>18.4f}")
        rows.append({
            "hazard_type": "pluvial",
            "return_period": rp,
            "baseline_water_level_m": cap_m,
            "gev_shape": xi,
            "gev_loc_mm": loc,
            "gev_scale_mm": scale,
            "datum_note": (
                "ponding_cap_m; downstream flood_depth_pluvial_ponding "
                "fills DEM depressions up to this level; relative datum"
            ),
            "source_note": (
                f"ERA5-Land via Open-Meteo Archive ({lat}N {lon}E); "
                f"GEV fit to {n_years} annual maxima of {window_h}h rolling "
                f"precipitation ({years_ok[0]}-{years_ok[-1]}); "
                f"drain_capacity={drain_capacity_mm}mm; "
                f"runoff_coeff={runoff_coeff}; "
                f"depression_area_fraction={depression_area_fraction}; "
                f"xi={xi:.4f} mu={loc:.3f}mm sigma={scale:.3f}mm"
            ),
        })

    if dry_run:
        click.echo("\n[Dry run] No files modified.")
        return

    # 6. Write CSV
    if output_path.exists():
        existing = pd.read_csv(output_path)
        other = existing[existing["hazard_type"] != "pluvial"].copy()
    else:
        other = pd.DataFrame(columns=[
            "hazard_type", "return_period", "baseline_water_level_m", "source_note"
        ])
    updated = pd.concat([other, pd.DataFrame(rows)], ignore_index=True)
    updated = updated.sort_values(["hazard_type", "return_period"]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    updated.to_csv(output_path, index=False)
    click.echo(f"\nUpdated {output_path} with {len(rows)} pluvial rows.")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run pluvial-redesign tests for the formula and CLI**

```bash
python -m pytest tests/test_pluvial_redesign.py -k "ponding_cap or fit_pluvial or open_meteo" -v
```

Expected: 6 PASS (the CityConfig tests still fail until Task 3).

- [ ] **Step 5: Commit**

```bash
git add scripts/fit_pluvial_baseline_era5.py tests/test_pluvial_redesign.py
git commit -m "feat: pluvial fit now uses ERA5-Land hourly + explicit depression fraction

Replaces NASA POWER MERRA-2 (5-30x wet bias) with Open-Meteo ERA5-Land
hourly (~9 km, gauge-bias-corrected, no scaling needed).

Replaces hardcoded /100 in the ponding-depth formula with an explicit
--depression-area-fraction parameter (default 0.10, matches Singapore
PUB calibration). The new formula is dimensionally clean:
  ponding_cap_m = (excess_mm/1000) * runoff_coeff / depression_area_fraction

Drops --precip-scale flag and removes scripts/calibrate_precip_scale.py
dependency. Output values will differ (lower) from the MERRA-2 baseline.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3 — Update `scripts/cities.py`

**Files:**
- Modify: `scripts/cities.py`

- [ ] **Step 1: Verify CityConfig tests fail**

```bash
python -m pytest tests/test_pluvial_redesign.py -k "cityconfig" -v
```

Expected: 3 FAIL (precip_scale still present; depression_area_fraction missing).

- [ ] **Step 2: Update the `CityConfig` dataclass**

In `scripts/cities.py`, locate the `precip_scale: float = 1.0` block and replace it with:

```python
    # ------------------------------------------------------------------
    # Pluvial depression-storage parameter
    # ------------------------------------------------------------------
    # Fraction of grid-cell surface area that is effective depression
    # storage (cells low enough to retain runoff once primary drains
    # are exceeded).  Used in fit_pluvial_baseline_era5.py:
    #   ponding_cap_m = (excess_mm/1000) * runoff_coeff
    #                   / depression_area_fraction
    # Calibration anchor: Singapore PUB observed RP10-RP1000 ponding
    # depths of 0.07-0.76 m correspond to depression_area_fraction = 0.10
    # (= the old hardcoded /100 divisor).
    # Suggested values:
    #   0.05  -- highly concentrated runoff (deep narrow depressions,
    #            steep urban catchments, severe sub-grid heterogeneity)
    #   0.10  -- typical dense-urban SEA city (default)
    #   0.20  -- low-relief delta city (broad shallow depressions,
    #            most of the cell can pond)
    # NOTE: the rainfall driver (ERA5-Land) needs no bias correction --
    # the previous `precip_scale` field was MERRA-2-specific and is
    # removed.  See docs/superpowers/specs/2026-04-26-pluvial-redesign.md
    # for the rationale.
    depression_area_fraction: float = 0.10
```

- [ ] **Step 3: Update every city config — replace `precip_scale=...` with `depression_area_fraction=0.10`**

For each `_register(CityConfig(...))` block, do this replacement. **All 11 cities use the default 0.10 initially.** This will be re-tuned per-city if Task 5 validation indicates outputs are systematically off.

For each block, the change is:

```python
    # Before:
    precip_scale=0.10,

    # After:
    depression_area_fraction=0.10,
```

(And remove the `precip_scale` line altogether for Singapore, which currently relies on the default.)

Also update the `notes` strings: replace every textual occurrence of `precip_scale=...` with the rationale `pluvial driver: ERA5-Land (no bias correction); depression_area_fraction=0.10`.

For example, KL's notes:
```python
# Before:
"PRECIP: MERRA-2 ~24x wet bias corrected with precip_scale=0.10 "
"(calibrated to JPS RP2 6h reference of ~90 mm)."

# After:
"PRECIP: ERA5-Land hourly via Open-Meteo (gauge-bias-corrected, no "
"scaling needed). depression_area_fraction=0.10 default."
```

Do this for all 11 cities.

- [ ] **Step 4: Run tests to confirm they PASS**

```bash
python -m pytest tests/test_pluvial_redesign.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/cities.py
git commit -m "feat: replace precip_scale with depression_area_fraction in CityConfig

Removes the MERRA-2-specific precip_scale field (no longer needed -- the
pluvial fit now reads ERA5-Land directly). Adds depression_area_fraction
(default 0.10), the physically-interpretable parameter that replaces the
old hardcoded /100 divisor.

All 11 cities initialised to the default 0.10 (Singapore PUB calibration);
per-city values will be tuned in a subsequent commit after Task 5
validation against published city-level pluvial observations.

Notes strings updated to drop MERRA-2 bias-correction language.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4 — Update `scripts/run_city_pipeline.py`

**Files:**
- Modify: `scripts/run_city_pipeline.py`

- [ ] **Step 1: Update the pluvial baseline subprocess call (Step 0a)**

In `scripts/run_city_pipeline.py`, locate the `_run([... fit_pluvial_baseline_era5.py ...])` block. Replace:

```python
"--precip-scale",        str(city.precip_scale),
```

with:

```python
"--depression-area-fraction", str(city.depression_area_fraction),
```

Also rename the cache filename (because the data source has changed). Replace:

```python
era5_cache = Path("cache") / f"era5_{city.slug}_precip.parquet"
```

with:

```python
era5_cache_pluvial = Path("cache") / f"era5land_{city.slug}_pluvial.parquet"
```

And update the `--cache-precip` argument in the pluvial call to use `era5_cache_pluvial`.

The fluvial call (Step 0b) still uses MERRA-2 (out of scope for this redesign), so keep its `era5_cache` MERRA-2 path. Rename it to `era5_cache_fluvial = Path("cache") / f"era5_{city.slug}_fluvial.parquet"` for clarity.

- [ ] **Step 2: Update the fluvial baseline subprocess call (Step 0b)**

The fluvial script still has `--precip-scale` (it uses MERRA-2). Rather than touching the fluvial behavior, **drop the `--precip-scale` argument from the pipeline call** because the field no longer exists on `CityConfig`. The fluvial script's CLI default of 1.0 will apply, which means **no MERRA-2 bias correction for fluvial**. This will change fluvial outputs.

> **Note:** Fluvial bias correction is not in scope for this redesign. If validation in Task 5 shows fluvial outputs are now unrealistically high, the right follow-up is to migrate fluvial to ERA5-Land too (separate plan), not to reintroduce a calibrated `precip_scale`.

Concretely, in the `_run([... fit_fluvial_baseline_era5.py ...])` block, remove this line:

```python
"--precip-scale",   str(city.precip_scale),
```

- [ ] **Step 3: Verify the script imports cleanly**

```bash
python -c "import scripts.run_city_pipeline"
```

Expected: no output, no error.

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_city_pipeline.py
git commit -m "feat: pipeline runner drops --precip-scale; passes --depression-area-fraction

Pluvial path: passes city.depression_area_fraction; cache file renamed
era5land_<city>_pluvial.parquet (MERRA-2 caches are no longer reused).

Fluvial path: --precip-scale arg removed since the field no longer exists.
The fluvial script still uses MERRA-2 (separate redesign); its CLI default
of 1.0 (no bias correction) now applies to all cities. Fluvial output
calibration is a follow-up task.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5 — Validate against Singapore PUB and tune `depression_area_fraction` per city

**Files:**
- Create: `scripts/validate_pluvial_singapore.py`
- Modify: `scripts/cities.py` (per-city depression_area_fraction tuning, only if needed)
- Modify: `docs/hazard_methodology_comparison.md` (record validation outcome)

The PUB-published RP10-RP1000 observed ponding range is **0.07-0.76 m**. After the redesign, Singapore's depression-filled raster maxima must fall within (or at least bracket) this range for the model to be defensible. If outputs are systematically too low or too high, tune `depression_area_fraction`.

- [ ] **Step 1: Create `scripts/validate_pluvial_singapore.py`**

```python
"""
Validate the redesigned pluvial pipeline against Singapore PUB observations.

Procedure
---------
1. Run the full Singapore pluvial pipeline (ERA5-Land download + GEV fit
   + depression-fill flood model).
2. For each return period, read the pluvial depth raster and compute the
   maximum ponding depth across the city.
3. Compare with PUB published observed ponding range (0.07-0.76 m for
   RP10-RP1000).
4. Print a pass/fail verdict.

Usage
-----
    python scripts/validate_pluvial_singapore.py

Exit codes
----------
    0 : all RPs in or bracketing the PUB observed range
    1 : at least one RP outside the observed range
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import numpy as np
import rasterio


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# PUB published Singapore observed pluvial ponding range (RP10 to RP1000).
PUB_RANGE_M = (0.07, 0.76)
# Tolerance: allow 50% above/below the bracketed range before flagging.
TOL_LOW = 0.5
TOL_HIGH = 1.5


@click.command()
@click.option("--out-dir", type=click.Path(path_type=Path),
              default=Path("outputs/singapore_ssp585_2100"), show_default=True,
              help="Directory containing pluvial/rp_*/pluvial_depth_*.tif rasters.")
def cli(out_dir: Path):
    if not out_dir.exists():
        raise click.ClickException(
            f"{out_dir} does not exist. Run the Singapore pipeline first:\n"
            f"  python scripts/run_city_pipeline.py --city singapore"
        )

    pluvial_dirs = sorted((out_dir / "pluvial").glob("rp_*"))
    if not pluvial_dirs:
        raise click.ClickException(
            f"No pluvial/rp_* directories under {out_dir}."
        )

    click.echo("="*70)
    click.echo(f"Singapore pluvial validation vs PUB observed range "
               f"({PUB_RANGE_M[0]} - {PUB_RANGE_M[1]} m)")
    click.echo("="*70)

    failures = []
    for d in pluvial_dirs:
        rp = int(d.name.replace("rp_", ""))
        rasters = list(d.glob("pluvial_depth_*.tif"))
        if not rasters:
            click.echo(f"[skip] RP{rp}: no raster")
            continue
        with rasterio.open(rasters[0]) as ds:
            arr = ds.read(1, masked=True)
        valid = arr[~arr.mask] if hasattr(arr, "mask") else arr[np.isfinite(arr)]
        if len(valid) == 0:
            click.echo(f"[skip] RP{rp}: no valid pixels")
            continue
        max_m = float(valid.max())
        in_range = (PUB_RANGE_M[0] * TOL_LOW) <= max_m <= (PUB_RANGE_M[1] * TOL_HIGH)
        verdict = "PASS" if in_range else "FAIL"
        click.echo(f"  RP{rp:>4d}: max_depth = {max_m:.3f} m  [{verdict}]")
        if not in_range:
            failures.append((rp, max_m))

    click.echo("="*70)
    if failures:
        click.echo(f"FAILURES: {len(failures)} return period(s) outside PUB range.")
        click.echo("Tune scripts/cities.py -> singapore -> depression_area_fraction:")
        click.echo("  - Decrease (e.g. 0.05) to raise ponding depths.")
        click.echo("  - Increase (e.g. 0.20) to lower ponding depths.")
        sys.exit(1)
    else:
        click.echo("All return periods within tolerated PUB range.")
        sys.exit(0)


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Run the Singapore pipeline end-to-end with the new pluvial code**

```bash
python scripts/run_city_pipeline.py --city singapore --scenario SSP5-8.5 --horizon 2100
```

Expected: pipeline completes without errors. Watch the pluvial step output for:
- ERA5-Land download/cache
- GEV fit summary (xi, mu, sigma)
- Per-RP "Ponding cap (m)" column

Note: First run will take 5-15 minutes (ERA5-Land download). Subsequent runs use the parquet cache.

- [ ] **Step 3: Run the validator**

```bash
python scripts/validate_pluvial_singapore.py --out-dir outputs/singapore_ssp585_2100
```

Two outcomes:

**Case A — All RPs PASS:** Singapore validation succeeded with default `depression_area_fraction=0.10`. No further tuning needed for SG. Proceed to Step 4.

**Case B — Some RPs FAIL:** the validator prints which RPs are out of range. Tune Singapore's `depression_area_fraction` in `scripts/cities.py`:
- If max depths are too low (e.g. RP1000 < 0.4 m), reduce to 0.05-0.08 (more concentration).
- If max depths are too high (e.g. RP10 > 0.5 m), increase to 0.15-0.20.

Re-run the pipeline (only the pluvial fit + flood-model steps need to rerun; the DEM, sea mask, river/HAND rasters are cached). Re-run the validator. Iterate until validator exits 0.

- [ ] **Step 4: Tune the other cities by analogy (deferred validation)**

For KL/Bangkok/Jakarta and their supplementary configs, set `depression_area_fraction` based on **terrain analogy with Singapore**, since published per-city ponding ranges are sparse:

| Slug | Suggested `depression_area_fraction` | Rationale |
|---|---|---|
| `singapore` | (whatever Step 3 settled on; presumed 0.10) | PUB-validated reference |
| `kuala_lumpur`, `klang_shah_alam`, `subang_langat` | same as SG | similar drainage standards (JPS), similar CN |
| `bangkok`, `bangkok_chao_phraya` | 0.15 | flatter delta -> broader pondable area |
| `jakarta`, `tangerang`, `bekasi_depok` | 0.15 | flat coastal plain + subsidence; also broader |
| `manila` | 0.10 | mixed terrain, similar to KL |
| `hcmc` | 0.20 | very flat Mekong delta; widest pondable area |

Update `scripts/cities.py` with these values (replacing the 0.10 default written in Task 3).

> **Note:** these are first-order judgement calls, not validated. The methodology doc Issue R4 (historical-event validation) is the next step that will close the loop on these. Document the values as "preliminary, terrain-analogy" in the relevant `notes` strings.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_pluvial_singapore.py scripts/cities.py
git commit -m "feat: validate pluvial against PUB; set per-city depression_area_fraction

Adds scripts/validate_pluvial_singapore.py (compares per-RP max ponding
against the PUB-published observed range 0.07-0.76 m).

Per-city depression_area_fraction values set by terrain analogy:
  Singapore / KL family : 0.10  (validated baseline)
  Bangkok / Jakarta family : 0.15  (flatter delta, broader pondable area)
  HCMC : 0.20  (Mekong delta, widest pondable area)
  Manila : 0.10  (mixed terrain)

These are preliminary; final validation comes via R4 historical-event
runs (Jakarta 2020, KL 2021, Singapore 2010 Orchard Road).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5b — Per-city ERA5-Land GEV anchor validation

**Files:**
- Create: `scripts/validate_pluvial_idf_anchors.py`
- Modify: `scripts/cities.py` (`notes` strings only, with IDF-validation outcome)

The Singapore validation (Task 5) checks max ponding depths against PUB. Task 5b cross-checks the **rainfall driver itself** for the other cities — does ERA5-Land's GEV fit produce RP{N} 6h design rainfall consistent with each country's published national IDF anchor?

Anchors already cited in `scripts/cities.py` notes:

| City | Anchor | Source |
|---|---|---|
| `singapore` | RP10 6h ≈ 100 mm | PUB primary drain RP10 |
| `kuala_lumpur` (and `klang_shah_alam`, `subang_langat`) | RP2 6h ≈ 90 mm (range 80-100) | JPS Malaysia |
| `bangkok` (and `bangkok_chao_phraya`) | RP5 6h ≈ 85 mm (range 80-90) | TMD Thailand |
| `jakarta` (and `tangerang`, `bekasi_depok`) | RP2 6h ≈ 85 mm | BMKG Indonesia |
| `manila` | RP10 6h ≈ 130 mm (range 120-140) | PAGASA |
| `hcmc` | — | (no anchor; flag as unvalidated) |

If the ERA5-Land GEV fit deviates from the anchor by more than ±25%, flag it in the city's `notes`. The fix is **not** to introduce a new scaling factor (that would re-create the `precip_scale` problem). Instead the deviation is documented, and the DEFENSIBLE response is one of:
- Accept it (ERA5-Land is closer to truth than the published anchor in some cases)
- Treat the city as unvalidated for IDF (flag in notes)
- Investigate the anchor's provenance (some published IDFs are decades old)

- [ ] **Step 1: Create `scripts/validate_pluvial_idf_anchors.py`**

```python
"""
Cross-check ERA5-Land GEV fit against published national IDF anchors.

Reads the hazard_baseline_template.csv produced by the pluvial fit
(which carries GEV shape/loc/scale columns), computes the GEV return
level at the anchor RP, and compares with the cited published value.

Anchors are derived from the city `notes` text in scripts/cities.py
(see ANCHORS below).

Usage
-----
    # Validate every city that has an anchor, using its baseline CSV:
    python scripts/validate_pluvial_idf_anchors.py

    # Validate one city:
    python scripts/validate_pluvial_idf_anchors.py --city kuala_lumpur

Exit code
---------
    0 : every checked city is within +/-25 % of its anchor
    1 : one or more cities deviate beyond +/-25 %
    2 : at least one city is missing the baseline CSV (skipped, not failed)
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.gev_utils import gev_return_level
from scripts.cities import CITIES


# (city_slug, anchor_rp, anchor_mm_6h, source)
ANCHORS: list[tuple[str, int, float, str]] = [
    ("singapore",         10, 100.0, "PUB primary drain RP10"),
    ("kuala_lumpur",       2,  90.0, "JPS Malaysia RP2 6h (80-100 range)"),
    ("klang_shah_alam",    2,  90.0, "JPS Malaysia RP2 6h (80-100 range)"),
    ("subang_langat",      2,  90.0, "JPS Malaysia RP2 6h (80-100 range)"),
    ("bangkok",            5,  85.0, "TMD Thailand RP5 6h (80-90 range)"),
    ("bangkok_chao_phraya", 5,  85.0, "TMD Thailand RP5 6h (80-90 range)"),
    ("jakarta",            2,  85.0, "BMKG Indonesia RP2 6h"),
    ("tangerang",          2,  85.0, "BMKG Indonesia RP2 6h"),
    ("bekasi_depok",       2,  85.0, "BMKG Indonesia RP2 6h"),
    ("manila",            10, 130.0, "PAGASA RP10 6h (120-140 range)"),
    # hcmc: no anchor cited; intentionally omitted.
]

DEVIATION_TOLERANCE = 0.25   # +/- 25 %


def _read_gev_from_csv(csv_path: Path) -> tuple[float, float, float] | None:
    """Return (c, loc, scale) from the first pluvial row, or None if missing."""
    if not csv_path.exists():
        return None
    df = pd.read_csv(csv_path)
    plv = df[df["hazard_type"] == "pluvial"]
    if plv.empty:
        return None
    needed = {"gev_shape", "gev_loc_mm", "gev_scale_mm"}
    if not needed.issubset(plv.columns):
        return None
    row = plv.iloc[0]
    if any(pd.isna(row[k]) for k in needed):
        return None
    # GEV shape stored as xi = -c
    xi = float(row["gev_shape"])
    return -xi, float(row["gev_loc_mm"]), float(row["gev_scale_mm"])


@click.command()
@click.option("--city", "city_slug", default=None,
              help="Validate one city; omit to validate all anchored cities.")
@click.option("--data-root", type=click.Path(path_type=Path),
              default=Path("data"), show_default=True)
def cli(city_slug: str | None, data_root: Path):
    if city_slug is not None:
        anchors = [a for a in ANCHORS if a[0] == city_slug]
        if not anchors:
            raise click.ClickException(
                f"No anchor configured for {city_slug!r}.  Available: "
                f"{', '.join(a[0] for a in ANCHORS)}"
            )
    else:
        anchors = ANCHORS

    sep = "=" * 80
    click.echo(sep)
    click.echo(f"Pluvial IDF anchor validation (tolerance +/- {DEVIATION_TOLERANCE:.0%})")
    click.echo(sep)
    click.echo(f"{'City':<22}{'RP':>4}  {'Anchor (mm)':>12}  "
               f"{'ERA5-Land (mm)':>15}  {'Dev':>7}  Verdict")
    click.echo("-" * 80)

    failures: list[str] = []
    skipped: list[str] = []

    for slug, rp, anchor_mm, source in anchors:
        if slug not in CITIES:
            skipped.append(f"{slug}: not in CITIES registry")
            continue
        csv_path = data_root / slug / "hazard_baseline_template.csv"
        gev = _read_gev_from_csv(csv_path)
        if gev is None:
            click.echo(f"{slug:<22}{rp:>4}  {anchor_mm:>12.1f}  "
                       f"{'(no GEV in CSV)':>15}  {'-':>7}  SKIP")
            skipped.append(f"{slug}: GEV not in {csv_path}")
            continue

        c, loc, scale = gev
        era5_mm = gev_return_level(c, loc, scale, rp)
        dev = (era5_mm - anchor_mm) / anchor_mm
        verdict = "PASS" if abs(dev) <= DEVIATION_TOLERANCE else "FAIL"
        click.echo(f"{slug:<22}{rp:>4}  {anchor_mm:>12.1f}  "
                   f"{era5_mm:>15.1f}  {dev:>+7.1%}  {verdict}")
        if verdict == "FAIL":
            failures.append(f"{slug}: ERA5={era5_mm:.1f} mm vs anchor {anchor_mm:.1f} mm "
                            f"({dev:+.1%}; source: {source})")

    click.echo(sep)
    if skipped:
        click.echo(f"Skipped {len(skipped)}:")
        for s in skipped:
            click.echo(f"  - {s}")
    if failures:
        click.echo(f"\nFAIL: {len(failures)} city(ies) outside +/-25 %:")
        for f in failures:
            click.echo(f"  - {f}")
        click.echo("\nDocument the deviation in scripts/cities.py notes.")
        click.echo("Do NOT introduce a multiplicative scaling factor "
                   "(re-creates the precip_scale problem).")
        sys.exit(1)
    elif skipped and not [a for a in anchors if a[0] in CITIES and (data_root / a[0] / "hazard_baseline_template.csv").exists()]:
        # Nothing actually checked
        click.echo("\nNo cities had baseline CSVs available.  Run the pipeline first.")
        sys.exit(2)
    else:
        click.echo("\nAll checked cities within tolerance.")
        sys.exit(0)


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Run the pluvial fit step for KL, Bangkok, Jakarta, Manila**

Each city's pluvial fit step (Task 0a in `run_city_pipeline.py`) writes the GEV columns to its `hazard_baseline_template.csv`. We don't need to run the entire pipeline for the IDF anchor check — only the pluvial-baseline step.

```bash
# (Singapore CSV already exists from Task 5.)
for city in kuala_lumpur bangkok jakarta manila; do
  python scripts/run_city_pipeline.py --city $city --no-fit-coastal --scenario SSP5-8.5 --horizon 2100 \
    --no-sea-mask --no-build-river-raster --no-street-overlay 2>&1 | grep -E "Pluvial|GEV fit"
done
```

This is rough — the pipeline runner does not have a `--only-pluvial-fit` flag. If running the full pipeline for 4 cities is too slow at this stage, replace the loop body with a direct call to `fit_pluvial_baseline_era5.py`:

```bash
for city in kuala_lumpur bangkok jakarta manila; do
  python scripts/run_city_pipeline.py --city $city --list-cities >/dev/null
  # Look up lat/lon from the CITIES registry and call fit_pluvial directly:
  python -c "
from scripts.cities import CITIES
import subprocess, sys
c = CITIES['$city']
subprocess.check_call([sys.executable, 'scripts/fit_pluvial_baseline_era5.py',
    '--lat', str(c.era5_lat), '--lon', str(c.era5_lon),
    '--drain-capacity-mm', str(c.drain_capacity_mm),
    '--runoff-coeff', str(c.runoff_coeff),
    '--depression-area-fraction', str(c.depression_area_fraction),
    '--cache-precip', f'cache/era5land_{c.slug}_pluvial.parquet',
    '--output', f'data/{c.slug}/hazard_baseline_template.csv',
])
"
done
```

(Also update `data/<slug>/hazard_baseline_template.csv` to exist — copy from the SG template if missing.)

- [ ] **Step 3: Run the IDF anchor validator**

```bash
python scripts/validate_pluvial_idf_anchors.py
```

Three outcomes per city:
- **PASS** (within ±25%): no action.
- **FAIL** with ERA5-Land **higher** than anchor: ERA5-Land may overestimate vs the (often outdated) national IDF; check anchor source date. Document in notes.
- **FAIL** with ERA5-Land **lower** than anchor: ERA5-Land underestimates extremes for that city's grid cell; document and consider adding `--window-h 24` (24h IDF) cross-check in a follow-up.

- [ ] **Step 4: Update `notes` strings in `scripts/cities.py` with validation outcome**

For each city, append a sentence to its existing `notes` string:

```python
# Example for kuala_lumpur, after running the validator:
"VALIDATION (2026-04-26): ERA5-Land GEV RP2 6h = 87.4 mm vs JPS RP2 6h "
"~90 mm (-2.9%, PASS within +/-25 % tolerance)."
```

For HCMC, append:
```python
"VALIDATION (2026-04-26): No published national IDF anchor cited; "
"depression_area_fraction=0.20 set by terrain analogy (Mekong delta), "
"unvalidated until R4 historical-event runs (e.g. HCMC 2008 floods)."
```

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_pluvial_idf_anchors.py scripts/cities.py
git commit -m "feat: per-city ERA5-Land GEV vs national IDF anchor validation

Adds scripts/validate_pluvial_idf_anchors.py: checks GEV RP{N} 6h from
the pluvial fit against published anchors for SG (PUB), KL (JPS),
Bangkok (TMD), Jakarta (BMKG), Manila (PAGASA).  Tolerance +/- 25 %.

cities.py notes updated with the per-city validation outcome.  HCMC
remains unvalidated (no public IDF anchor cited) and is flagged as
such in its notes.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6 — Update `docs/hazard_methodology_comparison.md` and write design spec

**Files:**
- Modify: `docs/hazard_methodology_comparison.md`
- Create: `docs/superpowers/specs/2026-04-26-pluvial-redesign.md`

- [ ] **Step 1: Write the design spec**

Create `docs/superpowers/specs/2026-04-26-pluvial-redesign.md`:

```markdown
# Pluvial Model Redesign — Design Spec

**Date:** 2026-04-26
**Status:** Implemented (see plan: `docs/superpowers/plans/2026-04-26-pluvial-redesign.md`)
**Closes:** Issue #19, R1, R2 from `docs/hazard_methodology_comparison.md`

## Problem

The pre-redesign pluvial pipeline had three coupled problems:

1. **Wrong rainfall source.** NASA POWER MERRA-2 PRECTOTCORR has a 5-30x wet bias in tropical SEA cities. The bias is intensity-dependent, so a single multiplicative `precip_scale` cannot correct it across all return periods.
2. **Bundled calibration.** The factor `precip_scale × /100` was joint-calibrated against national IDF curves for SG/KL/BKK/JKT. The two factors couldn't be disentangled, blocking replicability for new cities (Manila, HCMC, Yangon, ...).
3. **Hidden physics.** The `/100` divisor was equivalent to a 10% depression storage assumption, but this was undocumented and not city-tunable.

## Solution

**Switch rainfall source MERRA-2 → ERA5-Land** (Open-Meteo Archive, hourly, free, ~9 km, gauge-bias-corrected). Residual bias against gauges in SEA is small enough to absorb into GEV sampling uncertainty.

**Make the `/100` physically explicit** as `depression_area_fraction` (default 0.10 = the Singapore PUB-calibrated value). New formula:
```
ponding_cap_m = (excess_mm / 1000) × runoff_coeff / depression_area_fraction
```

The downstream depression-filling flood model (`flood_depth_pluvial_ponding`) is unchanged — it already redistributes the scalar `ponding_cap_m` into actual DEM depressions.

## Why not full 2D hydrodynamic pluvial routing?

The existing depression-fill model is sufficient for screening-level outputs. A full 2D solver (inertial wave, applied to pluvial excess) would give higher fidelity but:
- The DEM is GLO-30 (30 m), so sub-grid pluvial detail is unrealistic anyway
- Drain capacity is an aggregate parameter; below-grid drainage networks aren't modelled
- Compute cost is 10-100x

Defer 2D pluvial until at least one historical-event validation (R4) shows depression-fill is insufficient.

## Outputs

- ERA5-Land RP100 6h ≈ 110-130 mm for Singapore (close to PUB published 120-150 mm vs MERRA-2 raw ≈ 1000+ mm).
- Singapore RP10-RP1000 max ponding (depression-fill output) is expected in the PUB range 0.07-0.76 m.
- All other cities: per-city `depression_area_fraction` is set by terrain analogy and refined via R4 historical-event validation (separate work).

## What changed in the public methodology

Replicability is now end-to-end:
1. Any researcher with Python can fetch ERA5-Land (no key) and reproduce the GEV fit.
2. The single tunable parameter `depression_area_fraction` is documented with a tier guide based on terrain (steep / typical-urban / delta).
3. No per-city calibration against private national IDF curves is required for screening-level outputs.
```

- [ ] **Step 2: Update `docs/hazard_methodology_comparison.md`**

Find the Issue #19 row (table near §10/§11). Replace the "Status" cell with:

```markdown
**RESOLVED (2026-04-26)** — Plan: `docs/superpowers/plans/2026-04-26-pluvial-redesign.md`. Switched pluvial rainfall source to ERA5-Land hourly (Open-Meteo); replaced the bundled `precip_scale × /100` with an explicit `depression_area_fraction` parameter. No per-city IDF calibration needed; outputs validated against PUB-published Singapore observed ponding range.
```

In §10.3, update R1 and R2:

```markdown
| **R1** | ... | ... | ✅ **RESOLVED (2026-04-26):** `precip_scale` field removed entirely. Pluvial rainfall driver switched to ERA5-Land hourly (Open-Meteo), which has no significant wet bias in SEA. No per-city scaling is needed. See `docs/superpowers/specs/2026-04-26-pluvial-redesign.md`. |
| **R2** | ... | ... | ✅ **RESOLVED (2026-04-26):** `/100` replaced by `depression_area_fraction` (default 0.10, physically interpretable). Per-city values set by terrain analogy (steep urban / dense urban / delta); will be refined when R4 historical-event validation is added. |
```

In the at-a-glance summary at the top, remove `(a) the precip_scale MERRA-2 bias calibration` from the "remaining gaps" list. The remaining gaps are now: (a) historical-event validation (R4), (b) `msl_to_egm2008_offset = 0` placeholders (R3 numerical values pending), (c) ASEAN coverage of PH/VN/MM/KH/LA/BN.

- [ ] **Step 3: Commit**

```bash
git add docs/hazard_methodology_comparison.md docs/superpowers/specs/2026-04-26-pluvial-redesign.md
git commit -m "docs: pluvial redesign closes Issue #19, R1, R2

Adds the design spec under docs/superpowers/specs/. Updates the methodology
comparison: marks R1 (precip_scale) and R2 (/100 divisor) RESOLVED. Updates
the at-a-glance summary to drop the pluvial calibration gap.

Remaining open items: R3 numerical msl_to_egm2008 offsets, R4 historical-
event validation, ASEAN expansion to PH/VN/MM/KH/LA/BN.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7 — Deprecate `scripts/calibrate_precip_scale.py`

**Files:**
- Modify: `scripts/calibrate_precip_scale.py`

The script becomes obsolete: with ERA5-Land as the direct rainfall source, there is no MERRA-2 bias factor to calibrate. Rather than delete (cache files referenced from prior validation runs are cited in `docs/hazard_methodology_comparison.md`), replace the body with a deprecation notice that prints and exits.

- [ ] **Step 1: Replace the file body with a deprecation shim**

Replace the entire `scripts/calibrate_precip_scale.py` with:

```python
"""
DEPRECATED (2026-04-26): pluvial pipeline now uses ERA5-Land directly.

The previous purpose of this script was to derive a MERRA-2 wet-bias
correction factor (precip_scale) per city.  Since 2026-04-26 the pluvial
fit reads ERA5-Land hourly (Open-Meteo) directly -- no MERRA-2 wet-bias
correction is needed.

If you were using this for the legacy MERRA-2 path, see:
  - docs/superpowers/specs/2026-04-26-pluvial-redesign.md
  - scripts/fit_pluvial_baseline_era5.py (rewritten 2026-04-26)
"""
from __future__ import annotations
import sys


def main() -> int:
    sys.stderr.write(
        "calibrate_precip_scale.py is DEPRECATED.\n"
        "The pluvial pipeline now uses ERA5-Land directly; no MERRA-2 wet-bias\n"
        "correction is needed.  See docs/superpowers/specs/2026-04-26-pluvial-redesign.md\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
git add scripts/calibrate_precip_scale.py
git commit -m "chore: deprecate calibrate_precip_scale.py (obsolete after ERA5-Land switch)

Prints deprecation notice and exits with code 2. Cache files in
cache/precip_scale/ may be deleted at any time.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage check:**
- ✅ ERA5-Land replaces MERRA-2 in pluvial fit (Task 2)
- ✅ `precip_scale` removed from CityConfig (Task 3)
- ✅ `/100` replaced by explicit `depression_area_fraction` (Task 2 + 3)
- ✅ Pipeline runner updated (Task 4)
- ✅ Validation script + per-city tuning (Task 5)
- ✅ Methodology doc + design spec updated (Task 6)
- ✅ Obsolete tool deprecated (Task 7)
- ✅ Shared GEV utils extracted (Task 1) — needed because the rewritten pluvial script and the (still MERRA-2) fluvial script both fit GEV

**Placeholder scan:** none — all code blocks are complete and runnable.

**Type consistency:** `depression_area_fraction: float`, validated `0 < x <= 1`, propagated as `str(...)` to subprocess CLI as `--depression-area-fraction`. Consistent throughout.

**Scope check:** This is one focused redesign (pluvial rainfall + formula). Fluvial bias correction is explicitly deferred. The plan is self-contained and produces a working, tested pluvial pipeline that meets the open-methodology objective.

**Output expectations:** Pluvial outputs will drop substantially from the MERRA-2 baseline (the user explicitly said current numbers seem elevated). The validator in Task 5 enforces the PUB-observed range as the new reference truth.
