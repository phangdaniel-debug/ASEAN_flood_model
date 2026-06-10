import numpy as np
import pytest
from rasterio.transform import from_origin
from scripts.build_conditioned_dem import depit_dem


def _profile(h, w):
    return {
        "driver": "GTiff", "height": h, "width": w, "count": 1,
        "dtype": "float32", "crs": "EPSG:32648",
        "transform": from_origin(0.0, h * 30.0, 30.0, 30.0),
    }


def _plain_with_pits():
    """20x20 plain at 10 m with 4 single-cell pits (well interior)."""
    dem = np.full((20, 20), 10.0, dtype="float64")
    dem[5, 5] = -5.0    # A: artifact floor (<0), depth 15 m
    dem[5, 15] = 5.0    # B: deep (depth 5 m), floor > 0
    dem[15, 5] = 9.0    # C: shallow real hollow (depth 1 m), floor > 0
    dem[15, 15] = 9.7   # D: noise pit (depth 0.3 m)
    return dem


def test_conditioned_mode_fills_only_noise():
    dem = _plain_with_pits()
    finite = np.ones_like(dem, dtype=bool)
    out, stats = depit_dem(dem, _profile(20, 20), finite,
                           noise_pit_depth_m=0.5, deep_pit_depth_m=None)
    assert out[15, 15] == pytest.approx(10.0, abs=1e-3)   # D noise -> filled
    assert out[5, 5] == pytest.approx(-5.0, abs=1e-3)     # A kept
    assert out[5, 15] == pytest.approx(5.0, abs=1e-3)     # B kept
    assert out[15, 5] == pytest.approx(9.0, abs=1e-3)     # C kept


def test_raingrid_mode_fills_artifact_and_deep_keeps_shallow():
    dem = _plain_with_pits()
    finite = np.ones_like(dem, dtype=bool)
    out, stats = depit_dem(dem, _profile(20, 20), finite,
                           noise_pit_depth_m=0.5, deep_pit_depth_m=3.0,
                           sea_level_m=0.0)
    assert out[5, 5] == pytest.approx(10.0, abs=1e-3)     # A artifact -> filled
    assert out[5, 15] == pytest.approx(10.0, abs=1e-3)    # B deep -> filled
    assert out[15, 15] == pytest.approx(10.0, abs=1e-3)   # D noise -> filled
    assert out[15, 5] == pytest.approx(9.0, abs=1e-3)     # C shallow real -> KEPT


def test_raingrid_mode_has_no_artifact_or_deep_pits_left():
    dem = _plain_with_pits()
    finite = np.ones_like(dem, dtype=bool)
    out, _ = depit_dem(dem, _profile(20, 20), finite,
                       noise_pit_depth_m=0.5, deep_pit_depth_m=3.0, sea_level_m=0.0)
    from model.hand_model import fill_depressions
    filled = fill_depressions(out, _profile(20, 20)).astype(np.float64)
    residual_depth = filled - out
    assert out.min() >= 0.0 - 1e-6
    assert residual_depth.max() < 3.0


def test_nondepression_terrain_unchanged():
    dem = _plain_with_pits()
    finite = np.ones_like(dem, dtype=bool)
    out, _ = depit_dem(dem, _profile(20, 20), finite,
                       noise_pit_depth_m=0.5, deep_pit_depth_m=3.0)
    assert out[0, 0] == pytest.approx(10.0, abs=1e-3)     # plain cell untouched
