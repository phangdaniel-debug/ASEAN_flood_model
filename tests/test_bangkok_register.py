"""Pure-logic guards for the Bangkok hotspot register (no network)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_bangkok_hotspot_register import SEED
from scripts.city_manifest import validate_manifest


def test_candidate_list_shape_and_provenance():
    pos = [c for c in SEED if c[2] == "positive"]
    dry = [c for c in SEED if c[2] == "dry"]
    assert len(pos) >= 15, f"expected >=15 positives, got {len(pos)}"
    assert len(dry) >= 7, f"expected >=7 dry controls, got {len(dry)}"
    assert all(c[3].strip() for c in SEED), "every candidate must carry a source/provenance"
    # kinds are only positive/dry
    assert {c[2] for c in SEED} == {"positive", "dry"}


def test_bangkok_manifest_valid_when_present():
    if not Path("data/bangkok/manifest/hotspots.csv").exists():
        pytest.skip("hotspots.csv not geocoded yet")
    assert validate_manifest("bangkok") == []
