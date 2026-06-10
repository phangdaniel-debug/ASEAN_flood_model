# Raingrid RP-Parallelisation (Plan 10 of N) — limitation #18

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Cut the ~5–6 h/city raingrid wall-clock (#18) by ~2.5–3× by running the **independent per-RP pluvial solves in a process pool (1 numba thread/worker)** instead of serially. The solver scales only 1.73× at 6 threads (benchmark: `docs/superpowers/runs/2026-06-06-raingrid-parallel-benchmark.md`), so 6 single-thread workers reclaim the wasted cores. **Zero answer change** — the `prange` loops are element-wise → bit-identical regardless of thread count.

**Architecture:** Pre-solve ALL raingrid pluvial RPs in a `ProcessPoolExecutor` before the serial hazard loop, caching `{rp: peak_depth}`; the serial loop's pluvial branch then just looks up the cached depth (denoise/floor/write unchanged). Coastal + fluvial stay serial (already fast). Read-only inputs (`raingrid_z/outlet/n/perfect_sink` + scalar params) are shipped to workers **once via the pool initializer**, not per task. Each worker calls `numba.set_num_threads(1)`.

**Discipline guards:**
- **Do NOT touch the solver maths or the post-storm settling tail** (Plan 4 / #18: early-stopping the tail is forbidden — it under-floods). This change is **pure scheduling**.
- **Bit-identical gate:** a test must show parallel `peak_depth` == serial `peak_depth` exactly on a small grid (the prange loops are element-wise, so this must hold; if it doesn't, STOP and investigate — something shares state).
- Back-compat: `--raingrid-workers 1` reproduces the exact current serial path.

**Tech Stack:** Python 3, numpy, numba, `concurrent.futures.ProcessPoolExecutor`, click, pytest. Windows uses **spawn** → worker fn + initializer must be top-level & picklable; module import must be side-effect-free (it is — click runs only under `__main__`).

**Key files:** `scripts/run_multihazard.py` (raingrid precompute ~739–792; pluvial branch ~821–852; CLI), new `model/raingrid_parallel.py` (worker + pool driver), `tests/test_raingrid_parallel.py`.

---

### Task 1: Parallel solve module + bit-identical test (TDD)

**Files:** Create `model/raingrid_parallel.py`, `tests/test_raingrid_parallel.py`

- [ ] **Step 1 (failing test):** `tests/test_raingrid_parallel.py` — on a small grid (e.g. 80×80, a few outlets, uniform net rain), compute peak_depth two ways and assert **bit-identical**:
```python
import sys; from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.pluvial_rain_model import run_rain_on_grid
from model.raingrid_parallel import solve_rps_parallel

def _inputs(n=80):
    z = np.zeros((n, n)); outlet = np.zeros((n, n), bool); outlet[n//2, n//2] = True
    nman = np.full((n, n), 0.05)
    return z, outlet, nman

def _serial(z, outlet, nman, rp_levels, **kw):
    out = {}
    for rp, lv in rp_levels:
        net = np.where(outlet, 0.0, lv)
        out[rp] = run_rain_on_grid(z, outlet, net, nman, **kw)["peak_depth"]
    return out

def test_parallel_matches_serial_bit_identical():
    z, outlet, nman = _inputs()
    rp_levels = [(2, 0.05), (10, 0.10), (100, 0.20)]
    kw = dict(storm_duration_s=600.0, total_duration_s=1800.0, dx=30.0, dy=30.0,
              verbose=False, open_boundary=False)
    serial = _serial(z, outlet, nman, rp_levels, **kw)
    par = solve_rps_parallel(z, outlet, nman, rp_levels, solver_kwargs=kw, max_workers=2)
    for rp, _ in rp_levels:
        assert np.array_equal(np.nan_to_num(serial[rp]), np.nan_to_num(par[rp])), f"RP{rp} differs"
```

- [ ] **Step 2:** Implement `model/raingrid_parallel.py`:
```python
"""Run independent per-RP rain-on-grid solves in a process pool (1 numba thread
per worker). Pure scheduling — each solve is identical to the serial call, so the
peak_depth is bit-identical (the solver's prange loops are element-wise)."""
from __future__ import annotations
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

# Module-level worker state (populated once per worker by the initializer).
_W: dict = {}


def _init_worker(z, outlet, nman, perfect_sink, solver_kwargs):
    # One numba thread per worker: many single-thread solves beat few many-thread
    # solves (solver is ~29% efficient at 6 threads — see parallel-benchmark.md).
    try:
        import numba
        numba.set_num_threads(1)
    except Exception:
        pass
    _W["z"] = z; _W["outlet"] = outlet; _W["nman"] = nman
    _W["perfect_sink"] = perfect_sink; _W["kw"] = dict(solver_kwargs)


def _solve_one(task):
    rp, level_m = task
    from model.pluvial_rain_model import run_rain_on_grid
    z = _W["z"]; outlet = _W["outlet"]
    if level_m <= 0.0:
        d = np.zeros(z.shape, dtype=np.float32); d[~np.isfinite(z)] = np.nan
        return rp, d
    net = np.where(outlet, 0.0, level_m * 1.0)  # caller pre-bakes runoff into level_m
    res = run_rain_on_grid(z, outlet, net, _W["nman"],
                           perfect_sink_mask=_W["perfect_sink"], **_W["kw"])
    return rp, res["peak_depth"]


def solve_rps_parallel(z, outlet, nman, rp_levels, *, solver_kwargs,
                       perfect_sink=None, max_workers=None):
    """rp_levels: list[(rp, net_level_m)] where net_level_m is the per-cell net rain
    scalar already multiplied by runoff (matches the serial `level_m*runoff` call).
    Returns {rp: peak_depth ndarray}. max_workers defaults to min(cores, n_rps)."""
    n = len(rp_levels)
    if max_workers is None:
        max_workers = max(1, min(os.cpu_count() or 1, n))
    if max_workers <= 1 or n <= 1:
        _init_worker(z, outlet, nman, perfect_sink, solver_kwargs)
        return dict(_solve_one(t) for t in rp_levels)
    out = {}
    with ProcessPoolExecutor(max_workers=max_workers, initializer=_init_worker,
                             initargs=(z, outlet, nman, perfect_sink, solver_kwargs)) as ex:
        for rp, depth in ex.map(_solve_one, rp_levels):
            out[rp] = depth
    return out
```
NOTE: the serial code computes `net_rain = where(outlet, 0, level_m * runoff_coeff_arr)`. To keep the worker simple and identical, the **caller** (run_multihazard) passes `net_level` already as `level_m` *scalar* only when runoff is uniform; when `runoff_coeff_arr` is an array, pass the full per-cell net-rain array instead. Implement `rp_levels` to carry the **precomputed net-rain array** per RP (not a scalar) so the worker is exactly `run_rain_on_grid(z, outlet, net_rain_arr, n, ...)` — eliminating any runoff ambiguity. Adjust `_solve_one`/test accordingly (pass `net_rain` arrays). Keep peak_depth as the return.

- [ ] **Step 3:** Run the test → bit-identical PASS. If multiprocessing is unavailable in the sandbox, the `max_workers<=1` path still runs in-process; ensure the test forces `max_workers=2` and is marked `skipif` only on platforms without spawn. Commit.
```bash
cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_raingrid_parallel.py -q
git add model/raingrid_parallel.py tests/test_raingrid_parallel.py
git commit -m "feat: process-pool RP-parallel raingrid solver (1 thread/worker; bit-identical) — #18

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 2: Wire into run_multihazard (pre-solve cache + CLI)

**Files:** Modify `scripts/run_multihazard.py`

- [ ] **Step 1:** Add CLI option near the raingrid options:
```python
@click.option("--raingrid-workers", "raingrid_workers", type=int, default=0, show_default=True,
              help="Parallel worker processes for the per-RP raingrid pluvial solves "
                   "(0=auto=min(cores,#RPs); 1=serial). 1 thread/worker. Bit-identical to serial (#18).")
```
Add `raingrid_workers: int,` to `cli(...)`.

- [ ] **Step 2:** After the raingrid precompute block (~792) and before the hazard loop, when `pluvial_model=="raingrid"` and `sea_mask is not None`: gather the pluvial rows, build each RP's **net-rain array** exactly as the serial branch does (`np.where(raingrid_outlet, 0.0, level_m * runoff_coeff_arr)`; `level_m<=0 → all-zero`), call `solve_rps_parallel(raingrid_z, raingrid_outlet, raingrid_n, rp_net_list, solver_kwargs={...same kwargs as the serial run_rain_on_grid call: storm_duration_s, total_duration_s, dx, dy, progress_interval=600, verbose=False, peak_depth_cap_m=pluvial_depth_cap, drain_conveyance_m_s=drain_conveyance_m_s}, perfect_sink=raingrid_perfect_sink, max_workers=(None if raingrid_workers==0 else raingrid_workers))`. Store `pluvial_peak_cache = {rp: peak_depth}`.
- [ ] **Step 3:** In the pluvial branch of the loop (~833), replace the inline `res = run_rain_on_grid(...)` with `peak = pluvial_peak_cache[rp]` then the existing `denoise_min_cluster(peak, ...)` + `apply_depth_floor(...)` (unchanged). Leave the non-raingrid pluvial models and coastal/fluvial untouched.
- [ ] **Step 4:** Verify import + `--help` shows the option + full suite green. Commit.
```bash
cd /d/GPTs/Projects/flood-v2.0
python -c "import sys;sys.path.insert(0,'.');import scripts.run_multihazard;print('OK')"
python -m pytest tests/ -q 2>&1 | tail -3
git add scripts/run_multihazard.py
git commit -m "feat: --raingrid-workers — pre-solve RP raingrid in a process pool (#18)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 3: End-to-end equivalence + speedup measurement (offline)

- [ ] **Step 1:** On the real KL inputs, run a SHORT proof: pick 2 low RPs (rp_2, rp_5) and run the pluvial-only path twice — `--raingrid-workers 1` (serial) and `--raingrid-workers 2` — into two out-dirs. Confirm the depth rasters are **bit-identical** (`np.array_equal` on the read-back arrays, NaN-normalised). This proves equivalence on real data without the full ~5 h run.
- [ ] **Step 2:** Measure wall-clock: time the serial vs pooled run of the same 2–3 RPs; report the speedup and the extrapolated 9-RP batch time. Expected ≈ 2.5–3× (benchmark). Record in the benchmark doc.
- [ ] **Step 3:** Honest verdict: did it deliver a real, bit-identical speedup? If equivalence fails, STOP (a worker is sharing/mutating state) — report, do not ship. If speedup < ~1.8×, note the gap (memory bandwidth / spawn overhead) but ship if equivalence holds (still a win).

### Task 4: Document — #18 update + memory

- [ ] **Step 1:** Update limitation #18: perf blocker MITIGATED via RP-parallel pool (1 thread/worker), ~Nx measured speedup, bit-identical; early-stop still forbidden. Note the default (`--raingrid-workers 0`=auto). Commit. Update memory (`v2-spec-and-plans.md`): #18 mitigated, multi-city raingrid cost cut ~Nx.

---

## Self-Review
**Spec coverage:** parallel module + bit-identical test (T1) → wire into pipeline + CLI (T2) → real-data equivalence + speedup (T3) → document (T4). ✓
**Placeholder scan:** worker/driver code is concrete; the net-rain-array note removes runoff ambiguity; CLI + wiring point at exact line ranges; expected speedup from the committed benchmark. ✓
**Discipline:** pure scheduling (no solver/tail change — #18/Plan 4 lesson); bit-identical gate (element-wise prange); back-compat via workers=1; offline (AR6). ✓

## Execution Handoff
Plan 10 of N. After execution: finish branch → unblocks scenario rasters (#16) and the multi-city transfer (Bangkok/Jakarta each ~2–3× faster). Remaining KL: #16 scenario regen, SSP5-8.5 2100 + viz, AR6 offline-repeatability.
