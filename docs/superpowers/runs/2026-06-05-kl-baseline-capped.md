# KL capped baseline — 2026-06-05

**Depth-cap fix (Plan 3 Task 1):** `run_city_pipeline.py` now forwards `--pluvial-depth-cap`
to `run_multihazard` (commit `67f4a6e`). Verified working: a re-run produced rp_5–rp_50 with
`max_depth = 3.000 m` exactly.

**Why the full re-run was aborted + post-hoc clip used:** the raingrid solver is pathologically
slow at high RP (~30–45 min/RP and rising; a full 9-RP run is ~5–6 h — logged as limitation #18).
The full capped re-run was killed mid-RP100. Because the in-pipeline cap is exactly
`peak = min(peak, cap)` applied after the solve, clipping the already-written rasters is
**mathematically identical** to a capped re-run. `scripts/_apply_pluvial_depth_cap.py` clipped all
pluvial rasters to 3.0 m and refreshed the summary. The proper fix (raingrid performance →
clean regenerate) is Plan 4.

**Capped pluvial summary (after clip):**

| RP | flooded_area_km² | max_depth_m |
|---|---|---|
| 2 | 97.4 | 1.604 |
| 5 | 278.5 | 3.000 |
| 10 | 394.0 | 3.000 |
| 25 | 475.7 | 3.000 |
| 50 | 535.8 | 3.000 |
| 100 | 589.4 | 3.000 |
| 200 | 637.6 | 3.000 |
| 500 | 658.9 | 3.000 |
| 1000 | 695.8 | 3.000 |

Monotonicity + mass-plausibility gate: **PASS**. Max pluvial depth now ≤ 3.0 m (was 4.5 m).

**Key result — the cap does NOT change the hotspot gate.** Re-validation at 50 m radius on the
capped baseline is identical to the uncapped run (HR 0.71, CRR 0.71, GATE PASS): the false-positive
dry controls are shallow-wet (< 3 m), so clipping deep cells leaves the ≥ 0.10 m wet/dry
classification unchanged. The cap is a physical-plausibility fix (a bank rejects 4.5 m urban
ponding on sight), not a specificity fix. See dossier §7.
