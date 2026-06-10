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
