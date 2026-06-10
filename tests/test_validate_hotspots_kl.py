import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.validate_hotspots_kl import evaluate_gate


def test_gate_passes_when_hr_and_crr_meet_floor():
    ok, reasons = evaluate_gate(hit_rate=0.82, crr=0.86,
                                hr_floor=0.70, crr_floor=0.70)
    assert ok and reasons == []


def test_gate_fails_and_reports_each_shortfall():
    ok, reasons = evaluate_gate(hit_rate=0.55, crr=0.40,
                                hr_floor=0.70, crr_floor=0.70)
    assert not ok
    assert any("hit-rate" in r for r in reasons)
    assert any("crr" in r.lower() for r in reasons)


def test_kl_default_radius_is_50m_geocoding_anchored():
    # KL Nominatim geocoding resolves to ~one city block; 50 m is the
    # precision-matched window (not 150 m, which is SG's denser-grid default).
    from scripts.validate_hotspots_kl import cli
    radius_opt = next(p for p in cli.params if p.name == "radius_m")
    assert radius_opt.default == 50.0
