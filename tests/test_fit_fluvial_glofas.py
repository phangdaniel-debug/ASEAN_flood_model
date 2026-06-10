"""Tests for fit_fluvial_glofas.py — GloFAS fluvial injection."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

from click.testing import CliRunner
from scripts.fit_fluvial_glofas import (
    fetch_daily_discharge,
    annual_maxima_discharge,
    build_stage_table,
    write_fluvial_rows,
    cli,
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
    assert "discharge_m3s" in result.columns
    assert result.index.tzinfo is not None  # cache path must return UTC-localized index


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


# ===========================================================================
# Task 4 tests: build_stage_table, write_fluvial_rows, cli
# ===========================================================================

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
    assert "atlantis" in result.output or "No GloFAS" in result.output or "Unknown" in result.output


def test_build_stage_table_bankfull_subtraction():
    """With bankfull_discharge_m3s set, stages must be < same run without it."""
    np.random.seed(7)
    maxima = {y: float(v) for y, v in zip(
        range(1984, 2024),
        np.random.exponential(scale=800, size=40) + 1200,
    )}
    kwargs = dict(
        channel_width_m=200.0,
        mannings_n=0.032,
        channel_slope=0.00005,
        xi_max=0.15,
        max_stage_m=20.0,
        lat=14.45,
        lon=100.45,
    )
    rows_no_bankfull = build_stage_table(maxima, **kwargs)
    rows_with_bankfull = build_stage_table(maxima, bankfull_discharge_m3s=1800.0, **kwargs)

    stages_no = [r["baseline_water_level_m"] for r in rows_no_bankfull]
    stages_bf = [r["baseline_water_level_m"] for r in rows_with_bankfull]

    # Bankfull subtraction must reduce every stage
    for rp_idx, (s_no, s_bf) in enumerate(zip(stages_no, stages_bf)):
        assert s_bf < s_no, (
            f"RP index {rp_idx}: bankfull stage {s_bf} >= no-bankfull stage {s_no}"
        )

    # datum_note must reflect bankfull when set
    assert "bankfull" in rows_with_bankfull[0]["datum_note"]
    assert "bankfull" not in rows_no_bankfull[0]["datum_note"]

    # source_note must record bankfull parameters
    assert "bankfull_subtraction" in rows_with_bankfull[0]["source_note"]


def test_build_stage_table_bankfull_subtraction_clamps_to_min():
    """Very high bankfull discharge must not produce negative stages (clamped to 0.05)."""
    np.random.seed(3)
    maxima = {y: float(v) for y, v in zip(
        range(1984, 2024),
        np.random.exponential(scale=200, size=40) + 100,
    )}
    # Bankfull much larger than any RP discharge → all stages should clamp to 0.05
    rows = build_stage_table(
        maxima,
        channel_width_m=200.0,
        mannings_n=0.032,
        channel_slope=0.00005,
        xi_max=0.30,
        max_stage_m=20.0,
        lat=14.45,
        lon=100.45,
        bankfull_discharge_m3s=1_000_000.0,  # absurdly high
    )
    for r in rows:
        assert r["baseline_water_level_m"] >= 0.05


def test_cli_discharge_scale_applied(tmp_path):
    """--discharge-scale reduces GEV mean → smaller output stages.

    Uses bangkok_chao_phraya (w=200m, S=5e-5) so the large mock discharge
    values stay well above the max_stage_m cap at scale=1.0 but fall below
    it at scale=0.42, making the assertion scale=0.42 < scale=1.0 valid.
    We compare at RP2 (first row) where the stage difference is biggest.
    """
    csv = tmp_path / "baseline.csv"
    _write_minimal_baseline(csv)

    np.random.seed(11)
    # Bangkok w=200m, n=0.032, S=5e-5.  At Q=4000 m3/s:
    # d = (4000*0.032/(200*sqrt(5e-5)))^0.6 ≈ 8.6m  → uncapped
    # At Q=4000*0.42=1680: d ≈ 4.8m → smaller (not capped at 20m)
    mock_df = pd.DataFrame(
        {"discharge_m3s": np.random.exponential(2000, 40 * 365) + 2500},
        index=pd.date_range("1984-01-01", periods=40 * 365, freq="D", tz="UTC"),
    )
    runner = CliRunner()

    with patch("scripts.fit_fluvial_glofas.fetch_daily_discharge", return_value=mock_df):
        result_full = runner.invoke(
            cli, ["--city", "bangkok_chao_phraya", "--output", str(csv),
                  "--discharge-scale", "1.0", "--xi-max", "0.15", "--dry-run"]
        )
    with patch("scripts.fit_fluvial_glofas.fetch_daily_discharge", return_value=mock_df):
        result_scaled = runner.invoke(
            cli, ["--city", "bangkok_chao_phraya", "--output", str(csv),
                  "--discharge-scale", "0.42", "--bankfull-discharge", "0",
                  "--xi-max", "0.15", "--dry-run"]
        )

    assert result_full.exit_code == 0, result_full.output
    assert result_scaled.exit_code == 0, result_scaled.output

    def parse_rp2_stage(text: str) -> float:
        """Extract stage value from the RP=2 row (first data row)."""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("2 ") or stripped.startswith("2\t"):
                parts = stripped.split()
                return float(parts[-1])
        raise AssertionError(f"No RP2 line found in output:\n{text}")

    stage_full = parse_rp2_stage(result_full.output)
    stage_scaled = parse_rp2_stage(result_scaled.output)
    assert stage_scaled < stage_full, (
        f"scale=0.42 RP2 stage ({stage_scaled}) should be < scale=1.0 ({stage_full})"
    )


def test_pipeline_suppresses_era5_fluvial_when_glofas_set(tmp_path):
    """run_city_pipeline suppresses ERA5 fluvial step when city has glofas_lat."""
    from click.testing import CliRunner
    from scripts.run_city_pipeline import cli as pipeline_cli

    runner = CliRunner()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))

    # Create the required baseline CSV in tmp_path/jakarta/
    city_data = tmp_path / "jakarta"
    city_data.mkdir(parents=True, exist_ok=True)
    baseline_csv = city_data / "hazard_baseline_template.csv"
    _write_minimal_baseline(baseline_csv)

    with patch("scripts.run_city_pipeline._run", side_effect=fake_run):
        result = runner.invoke(pipeline_cli, [
            "--city", "jakarta",
            "--no-fit-coastal",
            "--no-fit-pluvial",
            "--fit-glofas",
            "--out-root", str(tmp_path),
            "--data-root", str(tmp_path),
        ], catch_exceptions=False)

    # ERA5 fluvial script should NOT appear in any subprocess call
    era5_fluvial_calls = [c for c in calls if "fit_fluvial_baseline_era5" in " ".join(c)]
    assert era5_fluvial_calls == [], (
        f"ERA5 fluvial was called despite --fit-glofas: {era5_fluvial_calls}"
    )

    # GloFAS script SHOULD appear exactly once
    glofas_calls = [c for c in calls if "fit_fluvial_glofas" in " ".join(c)]
    assert len(glofas_calls) == 1, (
        f"Expected exactly one GloFAS step 0c call, got: {glofas_calls}"
    )


def test_pipeline_passes_bias_flags_for_bangkok(tmp_path):
    """Pipeline must forward --discharge-scale and --bankfull-discharge for Bangkok."""
    from scripts.run_city_pipeline import cli as pipeline_cli

    runner = CliRunner()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))

    city_data = tmp_path / "bangkok_chao_phraya"
    city_data.mkdir(parents=True, exist_ok=True)
    baseline_csv = city_data / "hazard_baseline_template.csv"
    _write_minimal_baseline(baseline_csv)

    with patch("scripts.run_city_pipeline._run", side_effect=fake_run):
        result = runner.invoke(pipeline_cli, [
            "--city", "bangkok_chao_phraya",
            "--no-fit-coastal",
            "--no-fit-pluvial",
            "--fit-glofas",
            "--out-root", str(tmp_path),
            "--data-root", str(tmp_path),
        ], catch_exceptions=False)

    glofas_calls = [c for c in calls if "fit_fluvial_glofas" in " ".join(c)]
    assert len(glofas_calls) == 1
    glofas_cmd = " ".join(glofas_calls[0])

    assert "--discharge-scale" in glofas_cmd, (
        f"Pipeline did not forward --discharge-scale to GloFAS step:\n{glofas_cmd}"
    )
    assert "0.42" in glofas_cmd, (
        f"Pipeline did not forward scale value 0.42:\n{glofas_cmd}"
    )
    assert "--bankfull-discharge" in glofas_cmd, (
        f"Pipeline did not forward --bankfull-discharge to GloFAS step:\n{glofas_cmd}"
    )
    assert "1800" in glofas_cmd, (
        f"Pipeline did not forward bankfull 1800 m3/s:\n{glofas_cmd}"
    )
