# 2026-07-04 — KL pluvial replaced with canal-HAND handfill (fixed atlas)

## Why

The shipped KL pluvial (fixed-atlas handfill vintage, 37.9 km² at RP100/2020) was
objectively under-powered for the region's flash-flood capital: the referee stress-test
decomposition showed **pluvial-only HR = 0.13** (4 of 31 documented flash-flood streets)
vs Jakarta 0.64 / Bangkok 0.25, and the layer was near-redundant in the combined gate
(NO-PLUVIAL HR 0.58 vs ALL 0.65). Visually it was 9,165 sub-hectare specks (largest
patch 0.18 km²) — inconsistent with KL's documented contiguous flash flooding.

## What changed

For all 15 KL fixed-atlas cells (5 scenarios × 3 RPs):

```
pluvial_new = max( shipped_handfill,  clip(stage_cell − HAND_canal, 0, 3.0) ), channels masked
HAND_canal  = height above the OSM drain network (drainage_waterways_utm47n.tif),
              PRUNED to drains with ≥ 0.5 km² flow accumulation
stage_cell  = 0.5 m × (cell pluvial excess / 0.095), clipped [0.4, 2.5]   (engine handfill scaling)
```

The pruning is essential: unpruned, hill headwater ditches flood the high dry controls
(Federal Hill, TTDI). Applied by `scripts/_apply_kl_canal_pluvial.py`.

## Results

| | shipped | new |
|---|---|---|
| pluvial extent (RP100/2020) | 37.9 km² | 246 km² |
| largest contiguous patch | 0.18 km² | 6.5 km² |
| flash-flood streets hit by pluvial | 13% | 55% |
| gate HR | 0.65 | **0.71** (recovers Segambut Dalam, Jalan Tun Razak, Bangsar) |
| gate CRR | 1.00 | 0.92 (one hill control floods) |
| gate TSS | 0.65 | 0.63 (parity within the ±0.16 bootstrap CI) |

Scenario scaling is monotone (RP10 ≈ 224–227 km² → RP1000/2100 ≈ 315 km²).
Bangkok and Jakarta gates unchanged (0.34/1.00, 0.76/1.00).

## Paper impact (Table 3 / extent tables re-opened)

- Table 3 KL row: 0.65 / 1.00 / 0.65 → **0.71 / 0.92 / 0.63**.
- KL pluvial extents in any extent table increase as above.
- Summary CSVs and pluvial severity rasters: **REGENERATED 2026-07-04** by
  `scripts/_regen_pluvial_summary_severity.py` (see the dedicated regen section in the
  Jakarta changelog). No longer stale — safe for paper-table rebuild.

## Provenance / rollback

- Pristine pluvial rasters: `*.tif.orig` alongside every changed tif (all cities).
- Pre-change atlas HTML: `outputs/_viz/flood_maps_atlas_legacy.html` (original palette
  renderer, pristine data — LEGACY snapshot, keep).
- Exploration evidence: `outputs/kl_pluvial_explore.log`, `outputs/kl_pluvial_pruned.log`.
- Current atlas: `outputs/_viz/flood_maps_atlas.html` (coverage-weighted opacity renderer).

## Candidates deliberately NOT applied (pending decision)

- Same canal-HAND retrofit for Bangkok / Jakarta / Singapore (their registers would
  arbitrate identically; BKK/JKT pluvial already carries gate weight, so gate risk differs).
- flood-v5.0 country tier: CF2 dense-HAND handfill (POD 0.59→0.79, CSI 0.051→0.041 —
  a POD-vs-CSI product decision).
