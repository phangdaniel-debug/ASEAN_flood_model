# Raingrid parallelisation — scaling benchmark (pre-Plan 10, limitation #18)

**Problem (#18):** the raingrid pluvial solver is ~30–45 min/RP at high RP → ~5–6 h per
city (9 RPs). Critical-path blocker for scenario rasters AND every new city.

**Memory's assumed lever:** "parallelise the 9 independent RP solves (separate
processes; zero answer change)." But `run_rain_on_grid` is **already
`numba.njit(parallel=True)`** — each solve uses all cores. So the question is the
solver's **parallel efficiency**: only if a single solve scales *poorly* with threads
does running several solves with fewer-threads-each recover wasted cores.

## Single-solve thread-scaling (`scripts/_bench_raingrid_scaling.py`)

KL-sized synthetic grid (1924×2045 ≈ 3.9 M cells), fixed solve, NUMBA_NUM_THREADS via
subprocess. Same # timesteps across thread counts (CFL is depth-driven, deterministic),
so wall-time ratio = parallel efficiency. Machine: **6 cores**.

| threads | wall (s) | speedup | efficiency |
|--------:|---------:|--------:|-----------:|
| 1 | 153.84 | 1.00× | 100% |
| 2 | 113.16 | 1.36× | 68% |
| 3 |  99.98 | 1.54× | 51% |
| 6 |  88.87 | **1.73×** | **29%** |

`peak_max = 0.311 m` **identical across all thread counts** (answer is thread-independent).

## Findings

1. **The solver scales poorly** (1.73× at 6 threads = 29% efficiency) — memory-bandwidth-
   bound stencil. At 6 threads, ~4 of 6 cores are effectively wasted.
2. **Therefore process-parallelism helps a lot.** Running the 9 independent RP solves in
   a **6-worker process pool with 1 numba thread each** uses 6× single-core throughput
   vs the serial 6-thread run's 1.73× → **~2.5–3× batch speedup** (5–6 h → ~2 h).
   Batch math (per bench-solve T): serial 9×T(6)=800 s; 6-workers×1-thread ≈ 2 waves ×
   T(1) ≈ 308 s → **2.6×**.
3. **Zero answer change — bit-identical.** The `prange` loops (`_rain_flux_x/y_jit`) are
   **purely element-wise** (`out[i,j]` from fixed-index inputs; no cross-iteration
   reduction), so output is bit-identical regardless of thread count. A 1-thread
   process-pool reproduces the current 6-thread serial output exactly.

## Plan-10 direction

Run the per-RP raingrid solves in a `ProcessPoolExecutor` (max_workers = min(cores, n_RP),
**1 numba thread/worker** via `numba.set_num_threads(1)` in the pool initializer; big
read-only inputs passed once via the initializer, not per task). Coastal/fluvial stay
serial (fast). Default-on for raingrid with ≥2 pluvial RPs; `--raingrid-workers 1`
restores serial. Correctness gate: parallel peak_depth **bit-identical** to serial on a
small grid. **Do NOT** touch the solver maths or the settling tail (Plan 4 #18 lesson —
early-stop is forbidden; this is pure scheduling).

## Implementation result (Plan 10, committed)

- **Equivalence — PROVEN bit-identical (the ship gate).** (a) Unit test
  `tests/test_raingrid_parallel.py` — pool (workers=2) vs serial on an 80×80 grid,
  `np.array_equal`. (b) **Real KL grid (3.9 M cells)**: `run_multihazard` pluvial-only,
  rp_2 + rp_5, `--raingrid-workers 1` vs `2` → both rasters **max|diff| = 0.0**. The
  run_multihazard wiring feeds the pool identical inputs.
- **Speedup — PROJECTED 2.6× for the 9-RP batch; NOT yet measured end-to-end.** The
  per-solve scaling above (1.73× at 6 threads) gives the 2.6× batch projection. A 2-RP
  real test is **unrepresentative** and overhead-dominated: pool 411 s vs serial 291 s
  for a tiny-sim 2-RP run, because (i) only 2 of 6 cores are used, (ii) each worker
  process pays a one-off numba JIT compile (~30–60 s, disk-cached after the first run)
  + spawn cost, which dominates when the solve itself is near-zero. The win requires
  **≥ ~6 substantial RP solves saturating all cores** — i.e. a real full-city run. **The
  end-to-end 9-RP speedup will be confirmed on the next full city run** (scenario rasters
  / Bangkok / Jakarta); a standalone 9-RP serial baseline (~5–6 h) is not run just to
  benchmark. Honest status: capability shipped + equivalence proven; headline speedup is
  the benchmark projection pending a real 9-RP confirmation.

## End-to-end confirmation (2026-06-06) — CONFIRMED ~2.6×

The **SSP5-8.5 2100** KL deliverable provided the first real full 9-RP pool run:
`run_multihazard --raingrid-workers 0` (auto = 6 workers, 1 thread each), 9-RP raingrid
pluvial + main-stem fluvial → **wall = 7757 s ≈ 2.15 h** vs the documented **~5–6 h
serial** baseline → **~2.6×**, at *heavier* 2100 forcing (more water → smaller CFL steps →
slower per-solve), so the realised speedup is conservative. The benchmark projection holds;
#18 is mitigated **and confirmed end-to-end**.
