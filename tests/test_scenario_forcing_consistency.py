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
