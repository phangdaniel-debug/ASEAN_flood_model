"""Verify CityConfig has glofas_lat/glofas_lon and 4 cities are configured."""
import dataclasses

import pytest

from scripts.cities import CITIES, CityConfig


def test_cityconfig_has_glofas_fields():
    fields = {f.name for f in dataclasses.fields(CityConfig)}
    assert "glofas_lat" in fields
    assert "glofas_lon" in fields


def test_cityconfig_has_bias_correction_fields():
    """New Level-1 Bangkok fix fields must be present with correct defaults."""
    fields = {f.name: f for f in dataclasses.fields(CityConfig)}
    assert "glofas_discharge_scale" in fields
    assert "glofas_bankfull_discharge_m3s" in fields
    assert fields["glofas_discharge_scale"].default == 1.0
    assert fields["glofas_bankfull_discharge_m3s"].default is None


def test_glofas_cities_configured():
    for slug in ("jakarta", "bangkok_chao_phraya", "manila", "hcmc"):
        city = CITIES[slug]
        assert city.glofas_lat is not None, f"{slug} missing glofas_lat"
        assert city.glofas_lon is not None, f"{slug} missing glofas_lon"


def test_non_glofas_cities_have_none():
    # kuala_lumpur gained GloFAS injection (Klang R. at Shah Alam); it is now
    # a GloFAS city. Only singapore and the pluvial-only bangkok slug remain
    # without GloFAS discharge coords.
    for slug in ("singapore", "bangkok"):
        city = CITIES[slug]
        assert city.glofas_lat is None, f"{slug} should have glofas_lat=None"
        assert city.glofas_lon is None, f"{slug} should have glofas_lon=None"


def test_bangkok_bias_correction_values():
    """Bangkok must have the Level-1 bias correction and bankfull values set."""
    city = CITIES["bangkok_chao_phraya"]
    assert city.glofas_discharge_scale == pytest.approx(0.42), (
        f"Expected scale=0.42, got {city.glofas_discharge_scale}"
    )
    assert city.glofas_bankfull_discharge_m3s == pytest.approx(1800.0), (
        f"Expected bankfull=1800.0 m3/s, got {city.glofas_bankfull_discharge_m3s}"
    )


def test_non_bangkok_cities_have_default_scale():
    """Only bangkok_chao_phraya carries the Level-1 discharge_scale bias
    correction (0.42). All other GloFAS cities use the default scale=1.0.

    (Bankfull discharge is set independently per city — kuala_lumpur, manila,
    and hcmc now have bankfull values, while jakarta does not — so it is not
    asserted here.)
    """
    for slug in ("jakarta", "kuala_lumpur", "manila", "hcmc"):
        city = CITIES[slug]
        assert city.glofas_discharge_scale == pytest.approx(1.0), (
            f"{slug}: expected default scale=1.0, got {city.glofas_discharge_scale}"
        )
