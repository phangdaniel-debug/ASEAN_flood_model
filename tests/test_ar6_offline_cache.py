"""AR6 sea-level extraction must be offline-repeatable via the on-disk cache.

These tests never touch the network: they verify the cache key/round-trip and that
`--offline` resolves a SEEDED cache end-to-end (and errors on a miss). The remote
zarr fetch path is not unit-tested (no network in CI).
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_scenarios_from_ar6_zarr import (
    cli, _cache_key, load_cache, save_cache, _CACHE_FIELDS,
)


def test_cache_key_deterministic_and_param_sensitive():
    a = _cache_key("wf_1e", "SSP5-8.5", 3.074, 101.578, 50.0, 2020, 2100)
    b = _cache_key("wf_1e", "SSP5-8.5", 3.0740, 101.5780, 50.0, 2020, 2100)
    c = _cache_key("wf_1e", "SSP5-8.5", 3.074, 101.578, 50.0, 2020, 2050)  # diff horizon
    assert a == b           # same key under float formatting
    assert a != c           # horizon changes the key


def test_cache_round_trip(tmp_path):
    p = tmp_path / "c.json"
    save_cache({"k": {"water_level_m": 0.42}}, p)
    assert load_cache(p) == {"k": {"water_level_m": 0.42}}
    assert load_cache(tmp_path / "missing.json") == {}


def _seed(path, key):
    save_cache({key: {f: (0.4321 if f == "water_level_m" else f"x_{f}") for f in _CACHE_FIELDS}}, path)


def test_offline_uses_seeded_cache_without_network(tmp_path):
    cache = tmp_path / "ar6.json"
    out = tmp_path / "scen.csv"
    key = _cache_key("wf_1e", "SSP5-8.5", 3.074, 101.578, 50.0, 2020, 2100)
    _seed(cache, key)
    r = CliRunner().invoke(cli, [
        "--lat", "3.074", "--lon", "101.578", "--scenario", "SSP5-8.5",
        "--horizon", "2100", "--output", str(out),
        "--cache-path", str(cache), "--offline",
    ])
    assert r.exit_code == 0, r.output
    df = pd.read_csv(out)
    assert len(df) == 1
    assert abs(float(df.iloc[0]["water_level_m"]) - 0.4321) < 1e-9
    assert list(df.columns)[:3] == ["scenario", "horizon", "water_level_m"]


def test_offline_errors_on_cache_miss(tmp_path):
    cache = tmp_path / "ar6.json"
    save_cache({}, cache)
    r = CliRunner().invoke(cli, [
        "--lat", "3.074", "--lon", "101.578", "--scenario", "SSP5-8.5",
        "--horizon", "2100", "--output", str(tmp_path / "o.csv"),
        "--cache-path", str(cache), "--offline",
    ])
    assert r.exit_code != 0
    assert "no cached AR6 value" in r.output


def test_build_hazard_levels_offline_uses_cache(tmp_path):
    """Pipeline-level: build_hazard_levels coastal AR6 lookup is offline-repeatable."""
    import pandas as pd
    from click.testing import CliRunner
    from scripts.build_hazard_levels import cli as bhl_cli

    base = tmp_path / "baseline.csv"
    pd.DataFrame({
        "hazard_type": ["coastal", "pluvial", "fluvial"],
        "return_period": [100, 100, 100],
        "baseline_water_level_m": [2.0, 0.10, 1.50],
    }).to_csv(base, index=False)

    cache = tmp_path / "ar6.json"
    out = tmp_path / "scen.csv"
    key = _cache_key("wf_1e", "SSP5-8.5", 3.074, 101.578, 50.0, 2020, 2100)
    _seed(cache, key)  # water_level_m = 0.4321 (coastal delta)

    r = CliRunner().invoke(bhl_cli, [
        "--baseline-hazards", str(base), "--scenario", "SSP5-8.5", "--horizon", "2100",
        "--lat", "3.074", "--lon", "101.578", "--output", str(out),
        "--cache-path", str(cache), "--offline",
    ])
    assert r.exit_code == 0, r.output
    df = pd.read_csv(out)
    coastal = df[df.hazard_type == "coastal"].iloc[0]
    # coastal future level = baseline 2.0 + cached AR6 delta 0.4321
    assert abs(float(coastal["water_level_m"]) - (2.0 + 0.4321)) < 1e-6
