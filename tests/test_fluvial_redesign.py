"""Tests for the fluvial ERA5-Land migration (Issue #20)."""
from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Task 1 — fetch function moved to gev_utils
# ---------------------------------------------------------------------------

def test_gev_utils_exports_era5land_fetch():
    from scripts.gev_utils import fetch_hourly_precip_era5land
    assert callable(fetch_hourly_precip_era5land)


def test_pluvial_script_no_longer_defines_fetch():
    source = Path("scripts/fit_pluvial_baseline_era5.py").read_text(encoding="utf-8")
    assert "def fetch_hourly_precip_era5land" not in source


def test_pluvial_validator_imports_from_gev_utils():
    source = Path("scripts/validate_pluvial_idf_anchors.py").read_text(encoding="utf-8")
    assert "from scripts.fit_pluvial_baseline_era5 import fetch_hourly_precip_era5land" not in source
    assert "gev_utils" in source


# ---------------------------------------------------------------------------
# Task 2 — fluvial script migrated to ERA5-Land
# ---------------------------------------------------------------------------

def test_fluvial_script_has_no_precip_scale():
    source = Path("scripts/fit_fluvial_baseline_era5.py").read_text(encoding="utf-8")
    assert "precip_scale" not in source


def test_fluvial_script_uses_open_meteo_not_nasa():
    source = Path("scripts/fit_fluvial_baseline_era5.py").read_text(encoding="utf-8")
    assert "open-meteo.com" in source
    assert "power.larc.nasa.gov" not in source


def test_fluvial_xi_max_default_is_030():
    source = Path("scripts/fit_fluvial_baseline_era5.py").read_text(encoding="utf-8")
    assert "default=0.30" in source
    # xi-max context must not reference old 0.5 default
    xi_max_idx = source.find('"xi_max"')
    if xi_max_idx != -1:
        context = source[max(0, xi_max_idx - 200):xi_max_idx + 200]
        assert "default=0.5," not in context


def test_scs_effective_runoff_basic():
    from scripts.fit_fluvial_baseline_era5 import scs_effective_runoff
    # CN=85: S=44.82, Ia=8.96; P=200 -> Q=(191.04)^2/235.86 ≈ 154.7 mm
    result = scs_effective_runoff(200.0, 85.0)
    assert 140.0 < result < 170.0


def test_scs_effective_runoff_below_ia():
    from scripts.fit_fluvial_baseline_era5 import scs_effective_runoff
    # CN=85: Ia=8.96 mm; P=5 mm < Ia -> 0
    result = scs_effective_runoff(5.0, 85.0)
    assert result == 0.0


def test_mannings_stage_positive():
    from scripts.fit_fluvial_baseline_era5 import mannings_stage
    # Q=10 m³/s, w=10 m, n=0.04, S=0.002 -> d ≈ 0.93 m
    result = mannings_stage(10.0, 10.0, 0.04, 0.002)
    assert result > 0.0
    assert isinstance(result, float)


def test_scs_peak_discharge_formula():
    from scripts.fit_fluvial_baseline_era5 import scs_peak_discharge
    # Formula: Tp = D/2 + 0.6*Tc = 24/2 + 0.6*0.5 = 12.3 h
    # Qp = 0.208 * 10 * 50 / 12.3 = 8.455 m³/s
    result = scs_peak_discharge(
        q_eff_mm=50.0,
        catchment_km2=10.0,
        storm_duration_h=24.0,
        time_of_conc_h=0.5,
    )
    assert 8.0 < result < 9.0


# ---------------------------------------------------------------------------
# Task 3 — run_city_pipeline.py updated for ERA5-Land fluvial
# ---------------------------------------------------------------------------

def test_fit_fluvial_default_follows_fit_era5():
    """do_fit_fluvial must resolve to fit_era5 when no override is given."""
    source = Path("scripts/run_city_pipeline.py").read_text(encoding="utf-8")
    # The old hard-coded False default must be gone
    assert "do_fit_fluvial = False" not in source
    # The new ERA5-aligned default must be present
    assert "do_fit_fluvial = fit_era5" in source


def test_pipeline_merra2_warning_removed():
    """The MERRA-2 wet-bias warning block must be absent."""
    source = Path("scripts/run_city_pipeline.py").read_text(encoding="utf-8")
    assert "WARNING: fluvial still uses MERRA-2" not in source
    assert "ERA5-Land migration pending" not in source


# ---------------------------------------------------------------------------
# Task 4 — validate_fluvial_idf_anchors.py
# ---------------------------------------------------------------------------

def test_fluvial_validator_script_exists():
    assert Path("scripts/validate_fluvial_idf_anchors.py").exists()


def test_fluvial_validator_imports_from_gev_utils():
    source = Path("scripts/validate_fluvial_idf_anchors.py").read_text(encoding="utf-8")
    assert "from scripts.gev_utils import" in source
    assert "fetch_hourly_precip_era5land" in source


def test_fluvial_validator_uses_24h_window():
    source = Path("scripts/validate_fluvial_idf_anchors.py").read_text(encoding="utf-8")
    assert "WINDOW_H = 24" in source
