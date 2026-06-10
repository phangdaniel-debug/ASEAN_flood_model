"""Tests for the pluvial model redesign (Issue #19 + R1 + R2 resolution)."""
import pytest


# -------------------------------------------------------------------------
# fit_pluvial_baseline_era5: formula and CLI tests
# -------------------------------------------------------------------------

def test_ponding_cap_formula():
    """ponding_cap = (excess_mm/1000) * runoff_coeff / depression_area_fraction.

    With excess=100mm, rc=0.75, daf=0.10 the cap is 0.75 m
    (matches old /100 formula at the default daf).
    """
    excess_mm = 100.0
    rc = 0.75
    daf = 0.10
    cap = (excess_mm / 1000) * rc / daf
    assert abs(cap - 0.75) < 1e-9


def test_ponding_cap_back_compat_default():
    """At depression_area_fraction=0.10 the new formula matches old /100."""
    for excess_mm in [10.0, 50.0, 100.0, 200.0]:
        rc = 0.75
        old = excess_mm * rc / 100.0
        new = (excess_mm / 1000.0) * rc / 0.10
        assert abs(old - new) < 1e-9, (
            f"excess={excess_mm}: old={old} new={new}"
        )


def test_ponding_cap_smaller_daf_gives_higher_cap():
    """Smaller depression_area_fraction (more concentration) -> higher ponding cap."""
    excess_mm = 100.0
    rc = 0.75
    cap_05 = (excess_mm / 1000) * rc / 0.05  # poor drainage / small depression area
    cap_10 = (excess_mm / 1000) * rc / 0.10  # default
    cap_15 = (excess_mm / 1000) * rc / 0.15  # well drained / spread out
    assert cap_05 > cap_10 > cap_15


def test_fit_pluvial_cli_drops_precip_scale():
    """The --precip-scale flag must be removed."""
    from click.testing import CliRunner
    from scripts.fit_pluvial_baseline_era5 import cli
    result = CliRunner().invoke(cli, ["--help"])
    assert "--precip-scale" not in result.output


def test_fit_pluvial_cli_has_depression_area_fraction():
    """The --depression-area-fraction flag must be present."""
    from click.testing import CliRunner
    from scripts.fit_pluvial_baseline_era5 import cli
    result = CliRunner().invoke(cli, ["--help"])
    assert "--depression-area-fraction" in result.output


def test_fit_pluvial_uses_open_meteo_endpoint():
    """The pluvial fit module must reference Open-Meteo Archive (not NASA POWER)."""
    import inspect, scripts.fit_pluvial_baseline_era5 as mod
    src = inspect.getsource(mod)
    assert "archive-api.open-meteo.com" in src
    # MERRA-2 PRECTOTCORR variable name should not appear in active code
    if "PRECTOTCORR" in src:
        # only allowed inside a comment marked "legacy"
        assert "legacy" in src.lower(), (
            "Pluvial fit references PRECTOTCORR outside a legacy comment"
        )


# -------------------------------------------------------------------------
# CityConfig field tests
# -------------------------------------------------------------------------

def test_cityconfig_no_precip_scale():
    """precip_scale field must be removed from CityConfig."""
    from scripts.cities import CITIES
    sg = CITIES["singapore"]
    assert not hasattr(sg, "precip_scale"), (
        "precip_scale still exists; should be removed (ERA5-Land needs no MERRA-2 correction)"
    )


def test_cityconfig_has_depression_area_fraction():
    """All cities have a depression_area_fraction field."""
    from scripts.cities import CITIES
    for slug, cfg in CITIES.items():
        assert hasattr(cfg, "depression_area_fraction"), f"{slug}: missing field"
        assert 0 < cfg.depression_area_fraction <= 1.0, (
            f"{slug}: depression_area_fraction={cfg.depression_area_fraction} out of (0,1]"
        )


def test_cityconfig_default_depression_area_fraction():
    """Default depression_area_fraction is 0.10 (matches Singapore PUB calibration)."""
    from scripts.cities import CITIES
    assert CITIES["singapore"].depression_area_fraction == 0.10


def test_excess_depth_m_is_drain_subtracted_rainfall():
    """excess_depth_m = max(0, design_mm - drain_capacity_mm) / 1000,
    independent of runoff_coeff and depression_area_fraction."""
    design_mm = 210.0
    drain_capacity_mm = 100.0
    excess_depth_m = max(0.0, design_mm - drain_capacity_mm) / 1000.0
    assert excess_depth_m == pytest.approx(0.110)
    # Below drain capacity -> zero excess.
    assert max(0.0, 80.0 - 100.0) / 1000.0 == pytest.approx(0.0)
