"""Tests for scripts/gev_utils.py — shared GEV and rolling-precipitation utilities."""
import numpy as np
import pandas as pd


def test_rolling_accumulation_6h():
    """6 consecutive 1 mm/hr hours produce a rolling max of 6 mm."""
    idx = pd.date_range("2001-01-01", periods=12, freq="1h")
    s = pd.Series([1.0] * 6 + [0.0] * 6, index=idx)
    from scripts.gev_utils import rolling_accumulation
    result = rolling_accumulation(s, window_h=6)
    assert abs(result.iloc[5] - 6.0) < 1e-6


def test_rolling_accumulation_single_spike():
    """A single 10 mm/hr hour produces a 6h rolling max of 10."""
    idx = pd.date_range("2001-01-01", periods=24, freq="1h")
    s = pd.Series(0.0, index=idx)
    s.iloc[12] = 10.0
    from scripts.gev_utils import rolling_accumulation
    result = rolling_accumulation(s, window_h=6)
    assert result.max() == 10.0


def test_annual_maxima_three_years():
    """Three years with known maxima are extracted correctly."""
    idx = pd.date_range("2001-01-01", periods=8760 * 3, freq="1h")
    s = pd.Series(0.0, index=idx)
    s.iloc[100] = 50.0
    s.iloc[8860] = 80.0
    s.iloc[17620] = 30.0
    from scripts.gev_utils import rolling_accumulation, annual_maxima
    acc = rolling_accumulation(s, window_h=1)
    maxima = annual_maxima(acc)
    assert maxima[2001] == 50.0
    assert maxima[2002] == 80.0
    assert maxima[2003] == 30.0


def test_annual_maxima_sparse_year_excluded():
    """A year with <50% valid observations is excluded."""
    idx_full = pd.date_range("2001-01-01", periods=8760, freq="1h")
    idx_sparse = pd.date_range("2002-01-01", periods=100, freq="1h")
    s = pd.concat([
        pd.Series(5.0, index=idx_full),
        pd.Series(99.0, index=idx_sparse),
    ]).sort_index()
    from scripts.gev_utils import rolling_accumulation, annual_maxima
    acc = rolling_accumulation(s, window_h=1)
    maxima = annual_maxima(acc, min_coverage=0.5)
    assert 2001 in maxima
    assert 2002 not in maxima


def test_fit_gev_returns_three_floats():
    """fit_gev returns (c, loc, scale); scale is positive."""
    from scipy.stats import gumbel_r
    rng = np.random.default_rng(42)
    samples = gumbel_r.rvs(loc=50, scale=20, size=25, random_state=rng)
    from scripts.gev_utils import fit_gev
    c, loc, scale = fit_gev(samples)
    assert isinstance(c, float) and isinstance(loc, float)
    assert scale > 0


def test_gev_return_level_monotone():
    """Longer return periods give higher (or equal) return levels."""
    from scipy.stats import gumbel_r
    rng = np.random.default_rng(0)
    samples = gumbel_r.rvs(loc=100, scale=30, size=30, random_state=rng)
    from scripts.gev_utils import fit_gev, gev_return_level
    c, loc, scale = fit_gev(samples)
    levels = [gev_return_level(c, loc, scale, rp) for rp in [2, 10, 100, 1000]]
    assert all(levels[i] <= levels[i + 1] for i in range(len(levels) - 1))
