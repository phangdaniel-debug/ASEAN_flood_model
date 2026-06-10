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
