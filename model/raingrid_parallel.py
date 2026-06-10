"""Run independent per-RP rain-on-grid solves in a process pool, one numba thread
per worker.

This is **pure scheduling**: each per-RP solve is the identical call the serial
pipeline makes, so the returned ``peak_depth`` is **bit-identical** to the serial
result (the solver's ``prange`` loops are element-wise — no cross-iteration
reduction — so the output does not depend on the thread count).

Why 1 thread per worker: ``run_rain_on_grid`` is memory-bandwidth-bound and scales
only ~1.73x at 6 threads (29% efficiency; see
docs/superpowers/runs/2026-06-06-raingrid-parallel-benchmark.md). Running many
single-thread solves in parallel reclaims the wasted cores → ~2.5-3x batch speedup.

The big read-only inputs (bed, outlet, Manning n, perfect-sink, runoff-coeff) are
shipped to each worker **once** via the pool initializer, not per task. Each task
carries only ``(rp, level_m)`` and the worker rebuilds the net-rain field exactly as
the serial branch does: ``net = where(outlet, 0, level_m * runoff_coeff)``.
"""
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

# Per-worker state, populated once by the initializer (avoids re-pickling per task).
_W: dict = {}


def _init_worker(z, outlet, nman, perfect_sink, runoff_coeff, solver_kwargs):
    # One numba thread per worker — see module docstring.
    try:
        import numba
        numba.set_num_threads(1)
    except Exception:
        pass
    _W["z"] = z
    _W["outlet"] = outlet
    _W["nman"] = nman
    _W["perfect_sink"] = perfect_sink
    _W["runoff"] = runoff_coeff
    _W["kw"] = dict(solver_kwargs)


def _net_rain(level_m):
    z = _W["z"]
    outlet = _W["outlet"]
    runoff = _W["runoff"]
    if np.isscalar(runoff):
        rain = np.full(z.shape, float(level_m) * float(runoff), dtype=np.float64)
    else:
        rain = float(level_m) * runoff
    return np.where(outlet, 0.0, rain)


def _solve_one(task):
    rp, level_m = task
    z = _W["z"]
    if level_m <= 0.0:
        d = np.zeros(z.shape, dtype=np.float32)
        d[~np.isfinite(z)] = np.nan
        return rp, d
    from model.pluvial_rain_model import run_rain_on_grid

    net = _net_rain(level_m)
    res = run_rain_on_grid(
        z, _W["outlet"], net, _W["nman"],
        perfect_sink_mask=_W["perfect_sink"], **_W["kw"],
    )
    return rp, res["peak_depth"]


def solve_rps_parallel(z, outlet, nman, rp_levels, *, solver_kwargs,
                       perfect_sink=None, runoff_coeff=1.0, max_workers=None):
    """Solve a set of return-period raingrid pluvial fields in parallel.

    Parameters
    ----------
    z, outlet, nman : ndarray
        Bed elevation, outlet mask, Manning-n — the RP-independent solver inputs.
    rp_levels : list[tuple[int, float]]
        ``(return_period, level_m)`` pairs. ``level_m`` is the per-RP net excess
        rainfall depth (m) BEFORE the runoff multiplier (matches the serial
        ``level_m * runoff_coeff_arr`` call).
    solver_kwargs : dict
        Keyword args forwarded verbatim to ``run_rain_on_grid`` (storm/total
        duration, dx, dy, caps, conveyance, etc.). Must NOT include
        ``perfect_sink_mask`` (passed separately).
    perfect_sink : ndarray | None
        Perfect-sink mask (sea + major rivers).
    runoff_coeff : float | ndarray
        Per-cell runoff coefficient (or scalar). The worker computes
        ``net = where(outlet, 0, level_m * runoff_coeff)``.
    max_workers : int | None
        Worker processes. ``None`` → ``min(cpu_count, n_rps)``. ``1`` → in-process
        serial (identical maths; for back-compat / platforms without spawn).

    Returns
    -------
    dict[int, ndarray]
        ``{return_period: peak_depth}`` — bit-identical to the serial solve.
    """
    n = len(rp_levels)
    if max_workers is None:
        max_workers = max(1, min(os.cpu_count() or 1, n))

    if max_workers <= 1 or n <= 1:
        _init_worker(z, outlet, nman, perfect_sink, runoff_coeff, solver_kwargs)
        try:
            return dict(_solve_one(t) for t in rp_levels)
        finally:
            _W.clear()

    out: dict = {}
    with ProcessPoolExecutor(
        max_workers=max_workers, initializer=_init_worker,
        initargs=(z, outlet, nman, perfect_sink, runoff_coeff, solver_kwargs),
    ) as ex:
        for rp, depth in ex.map(_solve_one, rp_levels):
            out[rp] = depth
    return out
