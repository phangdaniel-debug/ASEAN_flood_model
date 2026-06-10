"""The RP-parallel raingrid driver must be BIT-IDENTICAL to the serial solve.

The solver's prange loops are element-wise (no cross-iteration reduction), so the
peak_depth must not depend on thread count or on serial-vs-pool execution. If this
test ever fails, a worker is sharing/mutating state — STOP, do not ship.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.pluvial_rain_model import run_rain_on_grid
from model.raingrid_parallel import solve_rps_parallel

SOLVER_KW = dict(storm_duration_s=600.0, total_duration_s=1800.0, dx=30.0, dy=30.0,
                 verbose=False, open_boundary=False)
RP_LEVELS = [(2, 0.05), (10, 0.10), (100, 0.20)]


def _inputs(n=80):
    z = np.zeros((n, n), dtype=np.float64)
    outlet = np.zeros((n, n), dtype=bool)
    outlet[n // 2, n // 2] = True
    nman = np.full((n, n), 0.05, dtype=np.float64)
    runoff = np.full((n, n), 0.75, dtype=np.float64)
    return z, outlet, nman, runoff


def _serial(z, outlet, nman, runoff):
    out = {}
    for rp, lv in RP_LEVELS:
        net = np.where(outlet, 0.0, lv * runoff)
        out[rp] = run_rain_on_grid(z, outlet, net, nman, **SOLVER_KW)["peak_depth"]
    return out


def _assert_identical(a, b, rp):
    assert np.array_equal(np.nan_to_num(a, nan=-999.0), np.nan_to_num(b, nan=-999.0)), \
        f"RP{rp}: parallel result differs from serial"


def test_inprocess_path_matches_serial():
    # max_workers=1 takes the in-process path — must equal the direct serial loop.
    z, outlet, nman, runoff = _inputs()
    serial = _serial(z, outlet, nman, runoff)
    par = solve_rps_parallel(z, outlet, nman, RP_LEVELS, solver_kwargs=SOLVER_KW,
                             runoff_coeff=runoff, max_workers=1)
    for rp, _ in RP_LEVELS:
        _assert_identical(serial[rp], par[rp], rp)


def test_pool_path_matches_serial_bit_identical():
    z, outlet, nman, runoff = _inputs()
    serial = _serial(z, outlet, nman, runoff)
    try:
        par = solve_rps_parallel(z, outlet, nman, RP_LEVELS, solver_kwargs=SOLVER_KW,
                                 runoff_coeff=runoff, max_workers=2)
    except Exception as exc:  # platform without usable spawn pool
        pytest.skip(f"process pool unavailable: {exc}")
    for rp, _ in RP_LEVELS:
        _assert_identical(serial[rp], par[rp], rp)
