# 2026-07-04 — Jakarta pluvial: canal-HAND union applied; 4-city retrofit assessment

## The 4-city assessment (measured, gate-arbitrated)

The KL canal-HAND recipe was tested on the other three cities before any application:

| city | shipped pluvial-only HR | dry-control geometry | canal-HAND verdict |
|---|---|---|---|
| Kuala Lumpur | 0.13 (under-powered) | all high ground (min 49.7 m) | **applied** (see 2026-07-04-kl-canal-hand-pluvial.md) |
| **Jakarta** | 0.64 | high ground (min 31.9 m) | **applied — strict win, TSS improves** |
| Singapore | 0.71 (already strong) | moderate relief (min 6.7 m) | **rejected** — TSS 0.61 → 0.39–0.54 across all variants |
| Bangkok | 0.25 | degenerate (all < 5 m) | **rejected** — CRR 1.00 → 0.43, TSS 0.34 → 0.02 |

**Selection rule (add to methodology):** retrofit canal-HAND only where (a) the shipped
pluvial-only HR is demonstrably low AND (b) the register's dry controls sit meaningfully
higher than its positives (topographic position relative to drainage is informative).
Both are checkable in advance. On flat pumped deltas (Bangkok), engineered drainage
decouples flooding from topography and the mechanism cannot discriminate; in
heavily-drained cities with strong existing skill (Singapore), it only adds false alarms.

## Jakarta change

All 15 cells: `pluvial_new = max(shipped_handfill_2.5m, clip(stage_cell − HAND_canal, 0, 3))`,
channels masked. HAND_canal = full (UNPRUNED) `data/jakarta/river_mask_utm48s.tif` network —
Jakarta's canals are all engineered conveyance; the accumulation pruning used in KL guards
against hill headwater ditches, which do not exist here (gate insensitive to pruning anyway).
`stage_cell = 0.3 m × (cell excess / 0.130)`, clip [0.15, 1.5]. Monotone: RP10 179 km² →
RP1000/2100 342 km²; RP100/2020 163 → 245 km². Applied by `scripts/_apply_jakarta_canal_pluvial.py`.

## Gate (verified post-apply, `_verify_gate_expanded.py` — now 4 cities)

| city | HR | CRR | TSS | vs paper Table 3 |
|---|---|---|---|---|
| kuala_lumpur | 0.71 | 0.92 | 0.63 | was 0.65/1.00/0.65 |
| bangkok | 0.34 | 1.00 | 0.34 | unchanged |
| **jakarta** | **0.85** | **0.92** | **0.77** | was 0.76/1.00/0.76 — **headline TSS improves** |
| singapore | 0.71 | 0.90 | 0.61 | NEW baseline (register imported 2026-07-04) |

## Singapore register import

`data/singapore/manifest/hotspots_expanded.csv` imported from
`flood-v2.0/data/singapore/flood_obs/hotspots/sg_pluvial_hotspots.csv`
(PUB List of Flood-Prone Areas, Nov 2025: 38 positives + 20 dry controls; original kept as
`data/singapore/flood_obs_hotspots_v2import.csv`). This gives v4.0 an SG documented-hotspot
gate it previously lacked; the shipped SG product scores HR 0.71 / CRR 0.90 / TSS 0.61
with no model change — a new validation result available to the paper.

## Summary CSV + severity raster regeneration (KL + Jakarta, 2026-07-04)

`scripts/_regen_pluvial_summary_severity.py` regenerated the stale pluvial products for all
30 changed cells (KL 15 + Jakarta 15). Steps per cell:

1. **Restore the shipped valid-data footprint** from `*.tif.orig`. The canal-HAND apply
   had (a) introduced DEM-edge NaN in KL (shipped grid was all-finite, dry = 0) and
   (b) converted Jakarta's shipped NaN sea mask (1,445,134 cells) to 0.0. Fix:
   `depth = where(isfinite(orig), nan_to_num(new, 0.0), nan)`. Verified **0 spurious wet
   cells** in the shipped-NaN region (canal-HAND never painted the sea), so no wet land
   cell changed — the gate is byte-unchanged (KL 0.71/0.92/0.63, JKT 0.85/0.92/0.77).
2. **Severity raster** recomputed with the engine's `classify_depth_severity`
   (bands 0.15 / 0.50 / 1.00 m; nodata 255). Jakarta's 255-nodata footprint now matches
   the shipped sea mask exactly (1,445,134 cells).
3. **Summary CSV** pluvial row recomputed with the engine's `summarize_depth` /
   `severity_area_stats` and rewritten in place; all other hazard rows kept byte-identical.
   `water_level_m` (pluvial excess forcing) preserved. Validated against a shipped `.orig`:
   reproduces the pre-change row to the last digit.

**NOTE on the extent number for paper tables:** the summary `flooded_area_km2` uses the
engine convention `depth > 0` (KL RP100/2020 = **262.3 km²**), which is LARGER than the
atlas/gate figure of 246 km² (`depth ≥ 0.1`). Both are correct for their product; paper
extent tables read the summary CSV, so use the `depth > 0` value. RP-monotonicity holds
across all 10 scenario-groups (0 violations).

## Provenance / staleness

- Pristine pluvial: `*.tif.orig` sidecars; pre-change atlas: `flood_maps_atlas_legacy.html`.
- Summary CSVs + pluvial severity rasters: **regenerated, no longer stale** (above).
- Exploration evidence: `outputs/city_canal_test.log`, `outputs/sg_canal_gate.log`.
