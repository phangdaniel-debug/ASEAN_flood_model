# GloFAS Fluvial Injection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ERA5-rainfall-derived fluvial stages for four cities (Jakarta, Bangkok Chao Phraya, Manila, HCMC) with stages from GloFAS v4 daily river discharge via the Open-Meteo Flood API (free, no key, CC-BY 4.0).

**Architecture:** New standalone script `scripts/fit_fluvial_glofas.py` mirrors the structure of `fit_fluvial_baseline_era5.py` — fetch daily discharge, extract annual maxima, fit GEV, convert to Manning stage, overwrite fluvial rows in the baseline CSV. `mannings_stage` is moved to `scripts/gev_utils.py` so both scripts share it. `run_city_pipeline.py` gains a `--fit-glofas/--no-fit-glofas` flag; when a city has `glofas_lat` set, GloFAS fitting runs automatically and ERA5 fluvial fitting is suppressed.

**Tech Stack:** Python 3.11+, pandas, numpy, scipy (GEV via `gev_utils.py`), urllib (built-in HTTP), click, pytest. Open-Meteo Flood API (GloFAS v4, `flood-api.open-meteo.com`).

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `scripts/cities.py` | Modify | Add `glofas_lat`/`glofas_lon` to `CityConfig`; set for 4 cities |
| `scripts/gev_utils.py` | Modify | Add `mannings_stage` (moved from ERA5 script) |
| `scripts/fit_fluvial_baseline_era5.py` | Modify | Import `mannings_stage` from `gev_utils` instead of defining locally |
| `scripts/fit_fluvial_glofas.py` | Create | Fetch → annual maxima → GEV → Manning → CSV write |
| `tests/test_fit_fluvial_glofas.py` | Create | 10 unit tests |
| `scripts/run_city_pipeline.py` | Modify | Add `--fit-glofas` flag; wire into step 0c |

---

### Task 1: Add `glofas_lat` / `glofas_lon` to CityConfig and 4 cities

**Files:**
- Modify: `scripts/cities.py` (dataclass definition ~line 30, and the 4 city configs)

- [ ] **Step 1: Write a failing test that asserts the new fields exist**

Create `tests/test_glofas_cityconfig.py`:

```python
"""Verify CityConfig has glofas_lat/glofas_lon and 4 cities are configured."""
import pytest
from scripts.cities import CITIES, CityConfig
import dataclasses


def test_cityconfig_has_glofas_fields():
    fields = {f.name for f in dataclasses.fields(CityConfig)}
    assert "glofas_lat" in fields
    assert "glofas_lon" in fields


def test_glofas_cities_configured():
    for slug in ("jakarta", "bangkok_chao_phraya", "manila", "hcmc"):
        city = CITIES[slug]
        assert city.glofas_lat is not None, f"{slug} missing glofas_lat"
        assert city.glofas_lon is not None, f"{slug} missing glofas_lon"


def test_non_glofas_cities_have_none():
    for slug in ("singapore", "kuala_lumpur", "bangkok"):
        city = CITIES[slug]
        assert city.glofas_lat is None, f"{slug} should have glofas_lat=None"
        assert city.glofas_lon is None, f"{slug} should have glofas_lon=None"
```

- [ ] **Step 2: Run to confirm it fails**

```
pytest tests/test_glofas_cityconfig.py -v
```

Expected: `AttributeError: 'CityConfig' object has no attribute 'glofas_lat'`

- [ ] **Step 3: Add the fields to `CityConfig` in `scripts/cities.py`**

After the `notes: str = ""` field (around line 157), add:

```python
    # ------------------------------------------------------------------
    # GloFAS discharge injection (optional)
    # ------------------------------------------------------------------
    # Latitude/longitude of the GloFAS v4 river reach to sample via the
    # Open-Meteo Flood API (flood-api.open-meteo.com).  When set, the
    # fit_fluvial_glofas.py script uses daily discharge from this point
    # rather than ERA5 rainfall → SCS → Manning.  Use for cities where
    # the local ERA5 point cannot represent the upstream basin:
    #   - Large mega-basins (Chao Phraya: 160,000 km²)
    #   - Main-stem rivers where the sub-basin ERA5 fit saturates
    # Leave as None to keep using ERA5-based fluvial fitting.
    glofas_lat: float | None = None
    glofas_lon: float | None = None
```

- [ ] **Step 4: Set coordinates for the 4 cities in `scripts/cities.py`**

In the `jakarta` CityConfig block (after existing fields, before closing parenthesis):

```python
    glofas_lat=-6.50,
    glofas_lon=106.83,
    # Ciliwung River near Depok — upstream of Jakarta urban area;
    # captures full basin signal before channel enters city.
```

In the `bangkok_chao_phraya` CityConfig block:

```python
    glofas_lat=14.20,
    glofas_lon=100.35,
    # Chao Phraya near Bang Sai / Ang Thong — above tidal influence,
    # per existing CityConfig notes.
```

In the `manila` CityConfig block:

```python
    glofas_lat=14.69,
    glofas_lon=121.11,
    # Marikina River near Rodriguez / Montalban — above valley narrows;
    # full sub-basin of Pasig/Marikina system captured.
```

In the `hcmc` CityConfig block:

```python
    glofas_lat=10.98,
    glofas_lon=106.65,
    # Saigon River near Thu Dau Mot — above tidal backwater from Mekong;
    # representative of unregulated Saigon River flood signal.
```

- [ ] **Step 5: Run the test to confirm it passes**

```
pytest tests/test_glofas_cityconfig.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add scripts/cities.py tests/test_glofas_cityconfig.py
git commit -m "feat: add glofas_lat/glofas_lon to CityConfig; set for 4 cities"
```

---

### Task 2: Move `mannings_stage` to `gev_utils.py`

The `mannings_stage` function currently lives only in `fit_fluvial_baseline_era5.py`. Both the existing and new scripts need it. Moving it to `gev_utils.py` avoids duplication.

**Files:**
- Modify: `scripts/gev_utils.py` (add function)
- Modify: `scripts/fit_fluvial_baseline_era5.py` (import from gev_utils)

- [ ] **Step 1: Write a failing test for `mannings_stage` imported from `gev_utils`**

Add to a new file `tests/test_gev_utils_manning.py`:

```python
"""Test mannings_stage in gev_utils (moved from fit_fluvial_baseline_era5)."""
import pytest
from scripts.gev_utils import mannings_stage


def test_mannings_stage_unit_inputs():
    # Q=1, w=1, n=1, S=1 -> d = (1*1/(1*1))^0.6 = 1.0^0.6 = 1.0
    assert mannings_stage(1.0, 1.0, 1.0, 1.0) == pytest.approx(1.0, rel=1e-6)


def test_mannings_stage_zero_discharge():
    assert mannings_stage(0.0, 10.0, 0.035, 0.00005) == 0.0


def test_mannings_stage_invalid_params():
    with pytest.raises(ValueError):
        mannings_stage(100.0, 0.0, 0.035, 0.001)   # width=0


def test_mannings_stage_era5_still_works():
    # Confirm existing ERA5 script still imports correctly after the move
    from scripts.fit_fluvial_baseline_era5 import mannings_stage as ms_era5
    # Both point to same function (or produce same result)
    assert ms_era5(1.0, 1.0, 1.0, 1.0) == pytest.approx(1.0, rel=1e-6)
```

- [ ] **Step 2: Run to confirm it fails**

```
pytest tests/test_gev_utils_manning.py -v
```

Expected: `ImportError: cannot import name 'mannings_stage' from 'scripts.gev_utils'`

- [ ] **Step 3: Add `mannings_stage` to `scripts/gev_utils.py`**

Append after `gev_return_level` (end of file):

```python


def mannings_stage(
    q_peak_m3s: float,
    channel_width_m: float,
    mannings_n: float,
    channel_slope: float,
) -> float:
    """
    Bankfull stage above the channel bed (m) from Manning's equation.

    Assumes a wide rectangular cross-section: hydraulic radius R ≈ depth d
    (valid when w/d > 5).

        Q ≈ (1/n) · w · d^(5/3) · √S
        d = (Q · n / (w · √S))^(3/5)

    Parameters
    ----------
    q_peak_m3s    : discharge (m³/s)
    channel_width_m : channel width (m)
    mannings_n    : Manning's roughness coefficient
    channel_slope : dimensionless channel slope (m/m)

    Returns
    -------
    stage_m : water depth above channel bed (m), >= 0
    """
    if q_peak_m3s <= 0.0:
        return 0.0
    if channel_width_m <= 0 or mannings_n <= 0 or channel_slope <= 0:
        raise ValueError("Channel parameters must be positive.")
    import click
    d = (q_peak_m3s * mannings_n / (channel_width_m * channel_slope ** 0.5)) ** 0.6
    if channel_width_m / max(d, 0.01) < 5:
        click.echo(
            f"  [warn] w/d = {channel_width_m/d:.1f} < 5; wide-channel "
            "approximation may underestimate stage.",
            err=True,
        )
    return float(d)
```

- [ ] **Step 4: Update `scripts/fit_fluvial_baseline_era5.py` to import from gev_utils**

Find the import block near line 108:

```python
from scripts.gev_utils import (
    rolling_accumulation,
    annual_maxima,
    fit_gev,
    gev_return_level,
    fetch_hourly_precip_era5land,
)
```

Replace with:

```python
from scripts.gev_utils import (
    rolling_accumulation,
    annual_maxima,
    fit_gev,
    gev_return_level,
    fetch_hourly_precip_era5land,
    mannings_stage,
)
```

Then remove the `mannings_stage` function definition from `fit_fluvial_baseline_era5.py` (lines ~171–210, the full function body). The `scs_effective_runoff` and `scs_peak_discharge` functions stay — only `mannings_stage` moves.

- [ ] **Step 5: Run all tests to confirm nothing broke**

```
pytest tests/test_gev_utils_manning.py tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all existing tests still pass, 4 new tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/gev_utils.py scripts/fit_fluvial_baseline_era5.py tests/test_gev_utils_manning.py
git commit -m "refactor: move mannings_stage to gev_utils for reuse by GloFAS script"
```

---

### Task 3: `fetch_daily_discharge` and `annual_maxima_discharge`

Create the new script with its two data-ingestion functions, fully tested.

**Files:**
- Create: `scripts/fit_fluvial_glofas.py`
- Create: `tests/test_fit_fluvial_glofas.py`

- [ ] **Step 1: Write failing tests for fetch and annual maxima**

Create `tests/test_fit_fluvial_glofas.py`:

```python
"""Tests for fit_fluvial_glofas.py — GloFAS fluvial injection."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

from scripts.fit_fluvial_glofas import (
    fetch_daily_discharge,
    annual_maxima_discharge,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api_response(n_days: int = 365 * 10, q_values=None) -> bytes:
    """Build a minimal Open-Meteo Flood API JSON response."""
    dates = pd.date_range("1984-01-01", periods=n_days, freq="D")
    if q_values is None:
        q_values = [float(100 + i % 200) for i in range(n_days)]
    payload = {
        "latitude": -6.5,
        "longitude": 106.83,
        "daily_units": {"time": "iso8601", "river_discharge": "m³/s"},
        "daily": {
            "time": [d.strftime("%Y-%m-%d") for d in dates],
            "river_discharge": q_values,
        },
    }
    return json.dumps(payload).encode()


# ---------------------------------------------------------------------------
# fetch_daily_discharge tests
# ---------------------------------------------------------------------------

def test_fetch_discharge_returns_dataframe():
    """Mock HTTP → DataFrame with DatetimeIndex and discharge_m3s column."""
    mock_response = MagicMock()
    mock_response.read.return_value = _make_api_response()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        df = fetch_daily_discharge(-6.50, 106.83)

    assert isinstance(df.index, pd.DatetimeIndex)
    assert "discharge_m3s" in df.columns
    assert len(df) > 0
    assert df["discharge_m3s"].notna().any()


def test_fetch_discharge_cache_hit(tmp_path):
    """Cache parquet exists → no HTTP call made."""
    cache = tmp_path / "glofas_test.parquet"
    dates = pd.date_range("1984-01-01", periods=100, freq="D")
    df = pd.DataFrame({"discharge_m3s": np.random.rand(100) * 500}, index=dates)
    df.to_parquet(cache)

    with patch("urllib.request.urlopen") as mock_url:
        result = fetch_daily_discharge(-6.50, 106.83, cache_path=cache)

    mock_url.assert_not_called()
    assert len(result) == 100


def test_fetch_discharge_empty_response_raises():
    """All-null discharge response raises ValueError."""
    null_values = [None] * (365 * 10)
    mock_response = MagicMock()
    mock_response.read.return_value = _make_api_response(q_values=null_values)
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        with pytest.raises(ValueError, match="no valid discharge"):
            fetch_daily_discharge(-6.50, 106.83)


# ---------------------------------------------------------------------------
# annual_maxima_discharge tests
# ---------------------------------------------------------------------------

def test_annual_maxima_basic():
    """Known daily series → correct annual maxima extracted."""
    # 2 full years: 2000 max=500, 2001 max=300
    dates_2000 = pd.date_range("2000-01-01", "2000-12-31", freq="D")
    dates_2001 = pd.date_range("2001-01-01", "2001-12-31", freq="D")
    vals_2000 = [100.0] * len(dates_2000)
    vals_2000[180] = 500.0   # peak on day 181
    vals_2001 = [80.0] * len(dates_2001)
    vals_2001[90] = 300.0

    series = pd.Series(
        vals_2000 + vals_2001,
        index=dates_2000.append(dates_2001),
        dtype=float,
    )
    result = annual_maxima_discharge(series)
    assert result[2000] == pytest.approx(500.0)
    assert result[2001] == pytest.approx(300.0)


def test_annual_maxima_partial_year_dropped():
    """A year with fewer than 183 valid days is excluded."""
    # Only Jan–Mar 2000 (91 days) — should be dropped
    dates = pd.date_range("2000-01-01", "2000-03-31", freq="D")
    series = pd.Series([200.0] * len(dates), index=dates)
    result = annual_maxima_discharge(series)
    assert 2000 not in result
```

- [ ] **Step 2: Run to confirm tests fail**

```
pytest tests/test_fit_fluvial_glofas.py::test_fetch_discharge_returns_dataframe tests/test_fit_fluvial_glofas.py::test_fetch_discharge_cache_hit tests/test_fit_fluvial_glofas.py::test_fetch_discharge_empty_response_raises tests/test_fit_fluvial_glofas.py::test_annual_maxima_basic tests/test_fit_fluvial_glofas.py::test_annual_maxima_partial_year_dropped -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.fit_fluvial_glofas'`

- [ ] **Step 3: Create `scripts/fit_fluvial_glofas.py` with the two functions**

```python
"""
Derive fluvial channel stage from GloFAS v4 daily river discharge.

Uses the Open-Meteo Flood API (flood-api.open-meteo.com) — free, no key,
CC-BY 4.0, backed by the Copernicus GloFAS v4 Reanalysis (1984–present,
~5 km resolution).  Replaces ERA5-rainfall-derived stages for cities where
the local ERA5 grid cell cannot represent the upstream basin (mega-rivers:
Chao Phraya, Pasig/Marikina, Saigon, Ciliwung).

Method
------
1. Download (or load cached) daily discharge from Open-Meteo Flood API.
2. Extract annual maxima (years with <50% coverage dropped).
3. Fit GEV to annual maxima series (same gev_utils.fit_gev as ERA5 path).
4. Convert RP discharges to channel stage via Manning's equation using the
   city's existing channel_width_m, mannings_n, channel_slope from CityConfig.
5. Overwrite fluvial rows in hazard_baseline_template.csv.

Usage
-----
    python scripts/fit_fluvial_glofas.py --city jakarta
    python scripts/fit_fluvial_glofas.py --city bangkok_chao_phraya --dry-run
    python scripts/fit_fluvial_glofas.py --city manila --no-cache
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import click
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.gev_utils import fit_gev, gev_return_level, mannings_stage

RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]
_API_BASE = "https://flood-api.open-meteo.com/v1/flood"
_START_DATE = "1984-01-01"
_END_DATE   = "2024-12-31"


def fetch_daily_discharge(
    lat: float,
    lon: float,
    start_date: str = _START_DATE,
    end_date: str = _END_DATE,
    cache_path: Path | None = None,
    timeout: int = 120,
) -> pd.DataFrame:
    """
    Fetch daily river discharge from Open-Meteo Flood API (GloFAS v4).

    Parameters
    ----------
    lat, lon    : WGS84 coordinates of the river reach to sample
    start_date  : ISO8601 start date (default 1984-01-01)
    end_date    : ISO8601 end date (default 2024-12-31)
    cache_path  : if given and exists, load from parquet instead of fetching
    timeout     : HTTP request timeout in seconds

    Returns
    -------
    DataFrame with DatetimeIndex (UTC) and column 'discharge_m3s'.

    Raises
    ------
    ValueError  : if the API returns no valid (non-null) discharge values
    """
    if cache_path is not None and Path(cache_path).exists():
        click.echo(f"  Loading cached GloFAS discharge from {cache_path} ...")
        df = pd.read_parquet(cache_path)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, utc=True)
        elif df.index.tzinfo is None:
            df.index = df.index.tz_localize("UTC")
        click.echo(f"  {len(df):,} daily records ({df.index[0].year}–{df.index[-1].year}).")
        return df

    url = (
        f"{_API_BASE}?latitude={lat}&longitude={lon}"
        f"&daily=river_discharge"
        f"&start_date={start_date}&end_date={end_date}"
        f"&forecast_days=0"
    )
    click.echo(f"  Fetching GloFAS discharge ({lat}N {lon}E) ...")
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        payload = json.loads(resp.read())

    times = payload["daily"]["time"]
    values = payload["daily"]["river_discharge"]

    index = pd.to_datetime(times, utc=True)
    df = pd.DataFrame({"discharge_m3s": values}, index=index)
    df["discharge_m3s"] = pd.to_numeric(df["discharge_m3s"], errors="coerce")

    n_valid = int(df["discharge_m3s"].notna().sum())
    if n_valid == 0:
        raise ValueError(
            f"GloFAS API returned no valid discharge at ({lat}, {lon}). "
            "Check coordinates — the point may not be on a GloFAS river reach. "
            "Try adjusting lat/lon by 0.05–0.10 degrees toward the main channel."
        )

    click.echo(f"  {len(df):,} daily records, {n_valid:,} non-null.")

    if cache_path is not None:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_path)
        click.echo(f"  Cached to {cache_path}")

    return df


def annual_maxima_discharge(
    series: pd.Series,
    min_days: int = 183,
) -> dict[int, float]:
    """
    Annual maxima of daily discharge; years with fewer than min_days
    non-null values are excluded.

    Parameters
    ----------
    series   : daily discharge Series with DatetimeIndex
    min_days : minimum valid days per year (default 183 = 50% of 365)

    Returns
    -------
    dict mapping year (int) → annual maximum discharge (float, m³/s)
    """
    results: dict[int, float] = {}
    for year, group in series.groupby(series.index.year):
        n_valid = int(group.notna().sum())
        if n_valid < min_days:
            continue
        results[int(year)] = float(group.max(skipna=True))
    return results
```

- [ ] **Step 4: Run the tests to confirm they pass**

```
pytest tests/test_fit_fluvial_glofas.py::test_fetch_discharge_returns_dataframe tests/test_fit_fluvial_glofas.py::test_fetch_discharge_cache_hit tests/test_fit_fluvial_glofas.py::test_fetch_discharge_empty_response_raises tests/test_fit_fluvial_glofas.py::test_annual_maxima_basic tests/test_fit_fluvial_glofas.py::test_annual_maxima_partial_year_dropped -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/fit_fluvial_glofas.py tests/test_fit_fluvial_glofas.py
git commit -m "feat: add fetch_daily_discharge and annual_maxima_discharge"
```

---

### Task 4: GEV fit, Manning stage, CSV write, and CLI

Complete `fit_fluvial_glofas.py` with the remaining logic and tests.

**Files:**
- Modify: `scripts/fit_fluvial_glofas.py` (add `build_stage_table`, `write_fluvial_rows`, `cli`)
- Modify: `tests/test_fit_fluvial_glofas.py` (add 5 more tests)

- [ ] **Step 1: Write the remaining failing tests**

Append to `tests/test_fit_fluvial_glofas.py`:

```python
from scripts.gev_utils import mannings_stage as _mannings_stage
from scripts.fit_fluvial_glofas import build_stage_table, write_fluvial_rows
from click.testing import CliRunner
from scripts.fit_fluvial_glofas import cli


def _write_minimal_baseline(path: Path) -> None:
    """Write a minimal hazard_baseline_template.csv with coastal and pluvial rows."""
    rows = []
    for rp in [2, 10, 100]:
        rows.append({"hazard_type": "coastal", "return_period": rp,
                     "baseline_water_level_m": 1.0, "source_note": "test",
                     "gev_shape": "", "gev_loc_mm": "", "gev_scale_mm": "", "datum_note": ""})
        rows.append({"hazard_type": "pluvial", "return_period": rp,
                     "baseline_water_level_m": 0.5, "source_note": "test",
                     "gev_shape": "", "gev_loc_mm": "", "gev_scale_mm": "", "datum_note": ""})
    pd.DataFrame(rows).to_csv(path, index=False)


def test_mannings_stage_unit_inputs():
    # Q=1, w=1, n=1, S=1 -> d=(1*1/(1*1))^0.6 = 1.0
    from scripts.gev_utils import mannings_stage
    assert mannings_stage(1.0, 1.0, 1.0, 1.0) == pytest.approx(1.0, rel=1e-6)


def test_build_stage_table_monotonic():
    """RP stages must strictly increase with return period."""
    # Use a simple annual maxima dict that gives a valid GEV
    np.random.seed(42)
    maxima = {y: float(v) for y, v in zip(
        range(1984, 2024),
        np.random.exponential(scale=300, size=40) + 200,
    )}
    rows = build_stage_table(
        maxima,
        channel_width_m=350.0,
        mannings_n=0.035,
        channel_slope=0.00005,
        xi_max=0.30,
        max_stage_m=30.0,
        lat=14.20,
        lon=100.35,
        n_years=40,
    )
    stages = [r["baseline_water_level_m"] for r in rows]
    for i in range(len(stages) - 1):
        assert stages[i] <= stages[i + 1], (
            f"Stage not monotonic at index {i}: {stages[i]} > {stages[i+1]}"
        )


def test_write_fluvial_rows_preserves_other_hazards(tmp_path):
    """Fluvial rows overwritten; coastal and pluvial rows untouched."""
    csv = tmp_path / "baseline.csv"
    _write_minimal_baseline(csv)

    np.random.seed(0)
    maxima = {y: float(v) for y, v in zip(
        range(1984, 2024),
        np.random.exponential(scale=200, size=40) + 100,
    )}
    rows = build_stage_table(
        maxima,
        channel_width_m=15.0,
        mannings_n=0.033,
        channel_slope=0.0015,
        xi_max=0.30,
        max_stage_m=20.0,
        lat=-6.50,
        lon=106.83,
        n_years=40,
    )
    write_fluvial_rows(rows, csv)

    df = pd.read_csv(csv)
    assert set(df["hazard_type"].unique()) == {"coastal", "pluvial", "fluvial"}
    assert len(df[df["hazard_type"] == "fluvial"]) == 9   # 9 return periods
    assert len(df[df["hazard_type"] == "coastal"]) == 3   # untouched


def test_dry_run_does_not_write(tmp_path):
    """--dry-run prints output but leaves CSV unchanged."""
    csv = tmp_path / "baseline.csv"
    _write_minimal_baseline(csv)
    original = csv.read_text()

    runner = CliRunner()
    # Patch fetch so no network call happens
    mock_df = pd.DataFrame(
        {"discharge_m3s": np.random.exponential(300, 40 * 365) + 100},
        index=pd.date_range("1984-01-01", periods=40 * 365, freq="D", tz="UTC"),
    )
    with patch("scripts.fit_fluvial_glofas.fetch_daily_discharge", return_value=mock_df):
        result = runner.invoke(cli, ["--city", "jakarta", "--output", str(csv), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert csv.read_text() == original   # unchanged


def test_cli_unknown_city_exits_nonzero():
    runner = CliRunner()
    result = runner.invoke(cli, ["--city", "atlantis"])
    assert result.exit_code != 0
    assert "No GloFAS" in result.output or "atlantis" in result.output
```

- [ ] **Step 2: Run to confirm the new tests fail**

```
pytest tests/test_fit_fluvial_glofas.py -v -k "monotonic or preserves or dry_run or unknown_city or unit_inputs" 2>&1 | tail -15
```

Expected: `ImportError` — `build_stage_table`, `write_fluvial_rows`, `cli` not defined yet.

- [ ] **Step 3: Add `build_stage_table`, `write_fluvial_rows`, and `cli` to `scripts/fit_fluvial_glofas.py`**

Append after `annual_maxima_discharge`:

```python


def build_stage_table(
    maxima: dict[int, float],
    channel_width_m: float,
    mannings_n: float,
    channel_slope: float,
    xi_max: float,
    max_stage_m: float,
    lat: float,
    lon: float,
    n_years: int,
) -> list[dict]:
    """
    Fit GEV to annual maxima and convert RP discharges to Manning stage.

    Returns a list of dicts ready for CSV writing (one per return period).
    """
    years = sorted(maxima.keys())
    maxima_arr = np.array([maxima[y] for y in years], dtype=np.float64)

    try:
        c, loc, scale = fit_gev(maxima_arr, xi_max=xi_max)
    except Exception as exc:
        raise click.ClickException(f"GEV fit failed: {exc}")

    xi = -c
    click.echo(f"  GEV fit: xi={xi:.4f}  mu={loc:.1f} m3/s  sigma={scale:.1f} m3/s")
    click.echo(
        f"\n  {'RP (yr)':>8}  {'Q_rp (m3/s)':>12}  {'Stage (m)':>10}"
    )
    click.echo(f"  {'-'*8}  {'-'*12}  {'-'*10}")

    rows = []
    for rp in RETURN_PERIODS:
        q_rp = max(1.0, gev_return_level(c, loc, scale, rp))
        stage_m = mannings_stage(q_rp, channel_width_m, mannings_n, channel_slope)
        stage_m = max(0.05, min(round(stage_m, 4), max_stage_m))
        click.echo(f"  {rp:>8d}  {q_rp:>12.1f}  {stage_m:>10.3f}")
        rows.append({
            "hazard_type": "fluvial",
            "return_period": rp,
            "baseline_water_level_m": stage_m,
            "gev_shape": xi,
            "gev_loc_mm": loc,      # m³/s stored in mm column (schema-compatible)
            "gev_scale_mm": scale,  # m³/s stored in mm column (schema-compatible)
            "datum_note": (
                "relative_stage_above_channel_bed_m; "
                "no_absolute_datum_conversion_required; "
                "compatible_with_HAND_model_which_is_also_relative"
            ),
            "source_note": (
                f"GloFAS v4 Reanalysis via Open-Meteo Flood API ({lat}N {lon}E); "
                f"GEV fit to {n_years} annual maxima of daily discharge "
                f"({years[0]}-{years[-1]}); "
                f"Manning w={channel_width_m}m n={mannings_n} S={channel_slope}; "
                f"xi={xi:.4f} mu={loc:.1f}m3s sigma={scale:.1f}m3s"
            ),
        })
    return rows


def write_fluvial_rows(rows: list[dict], output_path: Path) -> None:
    """Overwrite fluvial rows in the baseline CSV; leave other hazards intact."""
    if output_path.exists():
        existing = pd.read_csv(output_path)
        other = existing[existing["hazard_type"] != "fluvial"].copy()
    else:
        other = pd.DataFrame(
            columns=["hazard_type", "return_period", "baseline_water_level_m", "source_note"]
        )
    updated = pd.concat([other, pd.DataFrame(rows)], ignore_index=True)
    updated = updated.sort_values(["hazard_type", "return_period"]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    updated.to_csv(output_path, index=False)
    click.echo(f"\n  Updated {output_path} with {len(rows)} fluvial rows.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option("--city", "city_slug", required=True,
              help="City slug as defined in scripts/cities.py (must have glofas_lat set).")
@click.option("--cache", "cache_path", type=click.Path(path_type=Path), default=None,
              help="Parquet cache path. Default: cache/glofas_{slug}.parquet.")
@click.option("--no-cache", "force_fetch", is_flag=True, default=False,
              help="Force re-fetch even if cache exists.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Print RP table without writing CSV.")
@click.option("--xi-max", "xi_max", type=float, default=0.30, show_default=True)
@click.option("--max-stage-m", "max_stage_m", type=float, default=20.0, show_default=True,
              help="Physical cap on stage (m). Default 20 m for large rivers.")
@click.option("--min-years", "min_years", type=int, default=10, show_default=True)
@click.option("--output", "output_path", type=click.Path(path_type=Path), default=None,
              help="Override default CSV path (data/{slug}/hazard_baseline_template.csv).")
@click.option("--start-date", default=_START_DATE, show_default=True)
@click.option("--end-date", default=_END_DATE, show_default=True)
def cli(
    city_slug: str,
    cache_path: Path | None,
    force_fetch: bool,
    dry_run: bool,
    xi_max: float,
    max_stage_m: float,
    min_years: int,
    output_path: Path | None,
    start_date: str,
    end_date: str,
) -> None:
    """Fit GloFAS fluvial baseline for a city and write to hazard_baseline_template.csv."""
    from scripts.cities import CITIES

    if city_slug not in CITIES:
        raise click.ClickException(f"Unknown city '{city_slug}'. Run --list to see options.")
    city = CITIES[city_slug]
    if city.glofas_lat is None:
        raise click.ClickException(
            f"No GloFAS coordinates configured for '{city_slug}'. "
            "Add glofas_lat / glofas_lon to CityConfig in scripts/cities.py."
        )

    effective_cache = cache_path or (PROJECT_ROOT / "cache" / f"glofas_{city_slug}.parquet")
    if force_fetch and effective_cache.exists():
        effective_cache.unlink()
        click.echo(f"  Removed cache {effective_cache} (--no-cache).")

    csv_path = output_path or (
        PROJECT_ROOT / "data" / city_slug / "hazard_baseline_template.csv"
    )

    click.echo(
        f"\nGloFAS fluvial injection: {city.name} "
        f"({city.glofas_lat}N {city.glofas_lon}E)"
    )
    click.echo(
        f"  Channel: w={city.channel_width_m}m  n={city.mannings_n}  "
        f"S={city.channel_slope}  max_stage={max_stage_m}m"
    )

    # 1. Fetch
    df = fetch_daily_discharge(
        city.glofas_lat, city.glofas_lon,
        start_date=start_date, end_date=end_date,
        cache_path=effective_cache,
    )

    # 2. Annual maxima
    maxima = annual_maxima_discharge(df["discharge_m3s"])
    n_years = len(maxima)
    if n_years < min_years:
        raise click.ClickException(
            f"Insufficient GloFAS record: {n_years} valid years < {min_years} minimum. "
            "Try extending --start-date or adjusting coordinates."
        )
    click.echo(f"  {n_years} years of annual maxima.")

    # 3. GEV + stage table
    rows = build_stage_table(
        maxima,
        channel_width_m=city.channel_width_m,
        mannings_n=city.mannings_n,
        channel_slope=city.channel_slope,
        xi_max=xi_max,
        max_stage_m=max_stage_m,
        lat=city.glofas_lat,
        lon=city.glofas_lon,
        n_years=n_years,
    )

    if dry_run:
        click.echo("\n[Dry run] No files modified.")
        return

    # 4. Write CSV
    write_fluvial_rows(rows, csv_path)


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run all tests in the file**

```
pytest tests/test_fit_fluvial_glofas.py -v --tb=short
```

Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/fit_fluvial_glofas.py tests/test_fit_fluvial_glofas.py
git commit -m "feat: add build_stage_table, write_fluvial_rows, cli to fit_fluvial_glofas"
```

---

### Task 5: Pipeline integration — `--fit-glofas` flag

**Files:**
- Modify: `scripts/run_city_pipeline.py`

- [ ] **Step 1: Write a failing test for the pipeline suppression behaviour**

Append to `tests/test_fit_fluvial_glofas.py`:

```python
def test_pipeline_suppresses_era5_fluvial_when_glofas_set(tmp_path):
    """run_city_pipeline suppresses ERA5 fluvial step when city has glofas_lat."""
    from click.testing import CliRunner
    from scripts.run_city_pipeline import cli as pipeline_cli

    runner = CliRunner()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

    with patch("scripts.run_city_pipeline._run", side_effect=fake_run), \
         patch("scripts.fit_fluvial_glofas.fetch_daily_discharge") as mock_fetch:
        mock_df = pd.DataFrame(
            {"discharge_m3s": np.random.exponential(300, 40 * 365) + 100},
            index=pd.date_range("1984-01-01", periods=40 * 365, freq="D", tz="UTC"),
        )
        mock_fetch.return_value = mock_df

        result = runner.invoke(pipeline_cli, [
            "--city", "jakarta",
            "--no-fit-coastal", "--no-build-river-raster",
            "--no-sea-mask",
            "--fit-glofas",
            "--no-fit-pluvial",
            "--out-root", str(tmp_path),
            "--data-root", str(tmp_path),
        ], catch_exceptions=False)

    # ERA5 fluvial script should NOT appear in any subprocess call
    era5_fluvial_calls = [c for c in calls if "fit_fluvial_baseline_era5" in " ".join(c)]
    assert era5_fluvial_calls == [], (
        f"ERA5 fluvial was called despite --fit-glofas: {era5_fluvial_calls}"
    )
```

- [ ] **Step 2: Run to confirm it fails**

```
pytest tests/test_fit_fluvial_glofas.py::test_pipeline_suppresses_era5_fluvial_when_glofas_set -v
```

Expected: FAIL — ERA5 fluvial still runs (flag not implemented yet).

- [ ] **Step 3: Add `--fit-glofas` flag and step 0c to `scripts/run_city_pipeline.py`**

Find the block of `@click.option` flags around `--fit-fluvial/--no-fit-fluvial` (line ~160). Add immediately after that option:

```python
@click.option(
    "--fit-glofas/--no-fit-glofas", "fit_glofas_override", default=None,
    help="Fetch GloFAS discharge and fit fluvial baseline (replaces ERA5 fluvial). "
         "Auto-enabled when city.glofas_lat is set. Disable with --no-fit-glofas.",
)
```

Add `fit_glofas_override: bool | None` to the `cli` function signature (alongside `fit_fluvial_override`).

Find the flag-resolution block (around line 395):

```python
    do_fit_pluvial = fit_era5 if fit_pluvial_override is None else fit_pluvial_override
    do_fit_fluvial = fit_era5 if fit_fluvial_override is None else fit_fluvial_override
```

Replace with:

```python
    do_fit_pluvial = fit_era5 if fit_pluvial_override is None else fit_pluvial_override
    # GloFAS: auto-enable when coordinates configured; supersedes ERA5 fluvial.
    do_fit_glofas = (city.glofas_lat is not None) if fit_glofas_override is None else fit_glofas_override
    # ERA5 fluvial is suppressed when GloFAS runs (unless user forces --fit-fluvial).
    if do_fit_glofas and fit_fluvial_override is None:
        do_fit_fluvial = False
    else:
        do_fit_fluvial = fit_era5 if fit_fluvial_override is None else fit_fluvial_override
```

After the existing step 0b block (around line 439, after `click.echo("\n[skip] --no-fit-fluvial: ...")`), add step 0c:

```python
    # ------------------------------------------------------------------
    # 0c. GloFAS fluvial baseline (cities with glofas_lat configured)
    # ------------------------------------------------------------------
    if do_fit_glofas:
        if city.glofas_lat is None:
            click.echo(
                "\n[skip] --fit-glofas: no glofas_lat configured for "
                f"'{city.slug}'. Add coordinates to CityConfig first."
            )
        else:
            click.echo("\n=== Step 0c: Fit fluvial baseline (GloFAS via Open-Meteo) ===")
            _run([
                py, str(PROJECT_ROOT / "scripts" / "fit_fluvial_glofas.py"),
                "--city",        city.slug,
                "--xi-max",      str(gev_xi_max),
                "--max-stage-m", str(max_stage_m),
                "--output",      str(baseline_csv),
            ])
    else:
        if city.glofas_lat is not None:
            click.echo("\n[skip] --no-fit-glofas: reusing existing GloFAS fluvial rows.")
```

- [ ] **Step 4: Run the pipeline test**

```
pytest tests/test_fit_fluvial_glofas.py::test_pipeline_suppresses_era5_fluvial_when_glofas_set -v
```

Expected: `1 passed`

- [ ] **Step 5: Run the full test suite**

```
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all tests pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add scripts/run_city_pipeline.py tests/test_fit_fluvial_glofas.py
git commit -m "feat: add --fit-glofas flag to run_city_pipeline; auto-suppresses ERA5 fluvial"
```

---

### Task 6: Smoke test — all 4 cities with `--dry-run`

Verify the complete pipeline works end-to-end against the real Open-Meteo Flood API.

**Files:**
- No code changes — run commands only.

- [ ] **Step 1: Dry-run Jakarta**

```
python scripts/fit_fluvial_glofas.py --city jakarta --dry-run
```

Expected output includes:
- `GloFAS fluvial injection: Jakarta (-6.5N 106.83E)`
- A table of RP2–RP1000 discharge and stage values
- `[Dry run] No files modified.`
- Stage at RP10 > 0 m and < 20 m
- No `ValueError` about coordinates

- [ ] **Step 2: Dry-run Bangkok Chao Phraya**

```
python scripts/fit_fluvial_glofas.py --city bangkok_chao_phraya --dry-run
```

Expected: stage values reasonable (RP100 likely 5–15 m given the large basin). Previously all values were capped at 8.0 m from ERA5.

- [ ] **Step 3: Dry-run Manila**

```
python scripts/fit_fluvial_glofas.py --city manila --dry-run
```

Expected: monotonically increasing stages, no errors.

- [ ] **Step 4: Dry-run HCMC**

```
python scripts/fit_fluvial_glofas.py --city hcmc --dry-run
```

Expected: monotonically increasing stages, no errors.

- [ ] **Step 5: Write Jakarta baseline (no --dry-run)**

```
python scripts/fit_fluvial_glofas.py --city jakarta
```

Expected:
- `Updated data/jakarta/hazard_baseline_template.csv with 9 fluvial rows.`
- Fluvial rows now show GloFAS source notes
- Coastal and pluvial rows unchanged

Verify:

```
python -c "
import pandas as pd
df = pd.read_csv('data/jakarta/hazard_baseline_template.csv')
print(df[df['hazard_type']=='fluvial'][['return_period','baseline_water_level_m','source_note']].to_string())
"
```

Expected: 9 fluvial rows with `source_note` starting `GloFAS v4 Reanalysis`.

- [ ] **Step 6: Write Bangkok Chao Phraya, Manila, HCMC baselines**

```
python scripts/fit_fluvial_glofas.py --city bangkok_chao_phraya
python scripts/fit_fluvial_glofas.py --city manila
python scripts/fit_fluvial_glofas.py --city hcmc
```

Each should print `Updated data/{slug}/hazard_baseline_template.csv with 9 fluvial rows.`

- [ ] **Step 7: Run full test suite one final time**

```
pytest tests/ -v --tb=short 2>&1 | tail -15
```

Expected: all tests pass.

- [ ] **Step 8: Commit smoke test results**

```bash
git add data/jakarta/hazard_baseline_template.csv \
        data/bangkok_chao_phraya/hazard_baseline_template.csv \
        data/manila/hazard_baseline_template.csv \
        data/hcmc/hazard_baseline_template.csv \
        cache/glofas_jakarta.parquet \
        cache/glofas_bangkok_chao_phraya.parquet \
        cache/glofas_manila.parquet \
        cache/glofas_hcmc.parquet
git commit -m "feat: inject GloFAS fluvial baselines for jakarta, bangkok_chao_phraya, manila, hcmc"
```

---

## Self-review notes

- `gev_loc_mm` / `gev_scale_mm` CSV column names are reused for m³/s values — documented in source_note and spec; column names stay unchanged to preserve schema compatibility with `build_hazard_levels.py`.
- `max_stage_m` default is 20.0 m in GloFAS script (vs 8.0 m in ERA5 script) — Chao Phraya and Saigon main-stem stages can legitimately exceed 8 m.
- Cache files are stored in `cache/` (already in `.gitignore` pattern); baseline CSVs are committed.
- The pipeline test mocks `_run` so no actual subprocess calls or network calls are made.
