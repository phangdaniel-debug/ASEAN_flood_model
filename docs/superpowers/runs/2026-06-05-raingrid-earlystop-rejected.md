# Raingrid early-stop — REJECTED (Plan 4 negative result) — 2026-06-05

**Goal:** cut the raingrid solver's high-RP runtime (limitation #18, ~5–6 h/city) via a
post-storm convergence early-stop in `run_rain_on_grid` (mirroring the inertial solver).

**Outcome: REJECTED.** The early-stop changes the flood product — it does not preserve outputs.

## Measurement (direct offline `run_multihazard`, early-stop at 5e-5 vs full-solve reference)

Per-RP wall time grew with RP (16→35 min), total ~3.5 h. But the peak-preservation check vs the
backed-up full-solve reference failed catastrophically:

| RP | full-solve wet (km²) | early-stop wet (km²) | under-flood |
|---|---|---|---|
| 2 | 35.2 | 17.5 | **50%** |
| 5 | 124.3 | 85.2 | 31% |
| 10 | 199.0 | 153.6 | 23% |
| 50 | 330.5 | 272.6 | 18% |
| 100 | 377.8 | 324.1 | 14% |
| 1000 | 484.6 | 437.1 | 10% |

Max per-cell peak diff = **3.0 m** (the cap), with **692,964 cells** differing by >0.10 m.

## Why (the lesson)

1. **The settling tail does real work.** After the 1 h storm, water routes into deep closed
   depressions and their peak keeps rising until ~t_end. Early-stopping skips that → the deep
   lows are under-filled → the map under-floods. The tail is not idle redistribution.
2. **A mean-of-domain convergence metric is unsafe at scale.** The unit test (single bowl) passed
   at 0.011 m because one low dominated the mean |Δd|. On KL's 3.9M-cell domain, a few deep lows
   still filling don't move the mean, so convergence fires while real peak is still rising. A
   max-|Δd| metric would be safe but would essentially never fire on KL (the lows fill until
   t_end), giving no speedup — so the early-stop approach is a dead end either way.
3. **The dangerous trap:** the under-flooded run was faster AND *passed the hotspot gate harder*
   (CRR 0.71→0.86) — because under-flooding rejects more dry controls. Trusting the gate alone
   would have shipped a faster solver that silently computes wrong maps. The explicit
   peak-preservation check (built into the plan) is what caught it.

## Disposition

- Branch `raingrid-perf` discarded; the early-stop code is NOT in `main`.
- Limitation #18 updated with this negative result; perf remains OPEN.
- **Next safe lever (deferred):** parallelise the 9 independent RP solves (separate processes) —
  a wall-clock speedup with zero change to the answer. NOT an algorithmic early-stop.
- **Do not re-attempt early-stopping the settling tail.**
