import sys; from pathlib import Path
import re
from click.testing import CliRunner
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.validate_hotspots import cli, _hazard_rasters

OUT = Path("outputs/kuala_lumpur_ssp585_2020")

def _parse(output):
    hr = float(re.search(r"hit-rate=([0-9.]+)", output).group(1))
    crr = float(re.search(r"CRR=([0-9.]+)", output).group(1))
    return hr, crr

import pytest
@pytest.mark.skipif(not OUT.exists(), reason="KL outputs absent")
def test_kl_via_general_matches_known_gate():
    r = CliRunner().invoke(cli, ["--city", "kuala_lumpur", "--out-dir", str(OUT), "--rp", "100"])
    assert r.exit_code == 0, r.output
    hr, crr = _parse(r.output)
    assert abs(hr - 0.76) < 0.01 and abs(crr - 0.86) < 0.01

def test_hazard_rasters_unions_only_existing(tmp_path):
    (tmp_path / "pluvial" / "rp_100").mkdir(parents=True)
    (tmp_path / "pluvial" / "rp_100" / "pluvial_depth_SSP5-8.5_2020_rp100.tif").write_bytes(b"x")
    found = _hazard_rasters(tmp_path, "SSP5-8.5", 2020, 100)
    assert [p.parent.parent.name for p in found] == ["pluvial"]
