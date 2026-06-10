import numpy as np
import pytest
from scripts.build_naive_pluvial_baseline import (
    naive_tpi_depth,
    naive_tpi_index,
    naive_twi_depth,
    naive_twi_index,
)


def _valley_dem(n=10):
    """A V-shaped valley: low central column, sloping down toward the last row."""
    dem = np.zeros((n, n), dtype="float64")
    for i in range(n):
        for j in range(n):
            dem[i, j] = abs(j - (n - 1) / 2.0) * 2.0 + (n - 1 - i) * 0.5
    return dem


def test_twi_index_is_continuous_and_higher_in_valley():
    dem = _valley_dem()
    twi = naive_twi_index(dem)
    # continuous (many distinct values), NaN-free here, and wetter in the valley
    assert np.unique(twi[np.isfinite(twi)]).size > 5
    assert np.nanmean(twi[:, 4]) > np.nanmean(twi[:, 0])


def test_twi_index_preserves_nodata():
    dem = _valley_dem()
    dem[0, 0] = np.nan
    twi = naive_twi_index(dem)
    assert np.isnan(twi[0, 0])


def test_tpi_scores_local_pit_high_and_ridge_low():
    dem = np.full((9, 9), 10.0)
    dem[4, 4] = 4.0   # a local pit
    tpi = naive_tpi_index(dem, window_cells=3)
    assert tpi[4, 4] > 0.0                 # pit sits below its surroundings
    assert tpi[4, 4] == tpi.max()          # it is the most depressed cell
    dem2 = np.full((9, 9), 10.0)
    dem2[4, 4] = 16.0  # a local peak
    assert naive_tpi_index(dem2, window_cells=3)[4, 4] < 0.0


def test_tpi_depth_flags_and_preserves_nodata():
    dem = np.full((9, 9), 10.0)
    dem[4, 4] = 2.0
    dem[0, 0] = np.nan
    depth = naive_tpi_depth(dem, flag_fraction=0.05, flagged_depth_m=0.30, window_cells=3)
    assert depth[4, 4] == pytest.approx(0.30)
    assert np.isnan(depth[0, 0])


def test_twi_flags_low_convergent_ground():
    dem = _valley_dem()
    depth = naive_twi_depth(dem, flag_fraction=0.2, flagged_depth_m=0.30)
    # The low central column is flagged wetter than the dry ridge column.
    assert np.nanmean(depth[:, 4]) > np.nanmean(depth[:, 0])
    assert np.nanmean(depth[:, 0]) == pytest.approx(0.0, abs=1e-9)


def test_flagged_cells_carry_nominal_depth_only():
    dem = _valley_dem()
    depth = naive_twi_depth(dem, flag_fraction=0.2, flagged_depth_m=0.30)
    vals = set(np.round(depth[np.isfinite(depth)], 6))
    assert vals.issubset({0.0, 0.30})
    assert 0.30 in vals  # something was flagged


def test_flag_fraction_is_monotonic():
    dem = _valley_dem()
    few = int(np.sum(naive_twi_depth(dem, flag_fraction=0.1) > 0))
    many = int(np.sum(naive_twi_depth(dem, flag_fraction=0.4) > 0))
    assert few < many


def test_nan_preserved():
    dem = _valley_dem()
    dem[0, 0] = np.nan
    depth = naive_twi_depth(dem, flag_fraction=0.2)
    assert np.isnan(depth[0, 0])


def test_all_nan_returns_all_nan():
    dem = np.full((5, 5), np.nan, dtype="float64")
    depth = naive_twi_depth(dem, flag_fraction=0.2)
    assert np.isnan(depth).all()


def test_flag_fraction_zero_flags_nothing():
    dem = _valley_dem()
    depth = naive_twi_depth(dem, flag_fraction=0.0)
    assert np.nansum(depth) == 0.0


def test_flag_fraction_out_of_range_raises():
    dem = _valley_dem()
    with pytest.raises(ValueError, match="flag_fraction"):
        naive_twi_depth(dem, flag_fraction=1.5)
