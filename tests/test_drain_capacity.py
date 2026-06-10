import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.pluvial_rain_model import run_rain_on_grid


def _flat_with_one_drain(n=30):
    z = np.zeros((n, n), dtype=np.float64)
    outlet = np.zeros((n, n), dtype=bool)
    outlet[n // 2, n // 2] = True
    return z, outlet


def test_high_conveyance_matches_perfect_sink():
    z, outlet = _flat_with_one_drain()
    kw = dict(net_rain_depth_m=0.05, n=0.05, storm_duration_s=600.0,
              total_duration_s=1800.0, dx=30.0, dy=30.0, verbose=False,
              open_boundary=False)
    sink = run_rain_on_grid(z, outlet, **kw)
    fast = run_rain_on_grid(z, outlet, drain_conveyance_m_s=10.0, **kw)
    assert abs(float(sink["peak_depth"][15, 15]) - float(fast["peak_depth"][15, 15])) < 0.02


def test_finite_conveyance_ponds_at_overwhelmed_drain():
    z, outlet = _flat_with_one_drain()
    kw = dict(net_rain_depth_m=0.20, n=0.05, storm_duration_s=600.0,
              total_duration_s=1800.0, dx=30.0, dy=30.0, verbose=False,
              open_boundary=False)
    sink = run_rain_on_grid(z, outlet, **kw)
    limited = run_rain_on_grid(z, outlet, drain_conveyance_m_s=1e-5, **kw)
    assert float(limited["peak_depth"][15, 15]) > float(sink["peak_depth"][15, 15]) + 0.01


def test_perfect_sink_mask_cells_fully_drain():
    # two outlet cells: one a perfect sink (e.g. sea/major river), one a finite drain.
    n = 30
    z = np.zeros((n, n), dtype=np.float64)
    outlet = np.zeros((n, n), dtype=bool)
    outlet[10, 10] = True   # finite drain
    outlet[20, 20] = True   # perfect sink
    psm = np.zeros((n, n), dtype=bool)
    psm[20, 20] = True
    kw = dict(net_rain_depth_m=0.20, n=0.05, storm_duration_s=600.0,
              total_duration_s=1800.0, dx=30.0, dy=30.0, verbose=False, open_boundary=False)
    res = run_rain_on_grid(z, outlet, drain_conveyance_m_s=1e-5,
                           perfect_sink_mask=psm, **kw)
    # perfect-sink cell stays ~dry; finite-drain cell ponds (overwhelmed at tiny conveyance)
    assert float(res["peak_depth"][20, 20]) < 0.02
    assert float(res["peak_depth"][10, 10]) > float(res["peak_depth"][20, 20]) + 0.05
