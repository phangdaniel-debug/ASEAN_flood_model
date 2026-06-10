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
