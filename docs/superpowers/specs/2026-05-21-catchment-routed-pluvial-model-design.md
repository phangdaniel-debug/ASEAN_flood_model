# Catchment-Routed Pluvial Flood Model — Design

**Date:** 2026-05-21
**Status:** Approved design — ready for implementation planning

## Problem

The current pluvial solver `flood_depth_pluvial_ponding` (`model/flood_depth_model.py`)
distributes rainfall with a single lumped scalar:

```python
filled      = fill_depressions(dem)
max_ponding = filled - dem                       # depression depth, topography-only
depth       = min(water_level_m, max_ponding)    # water_level_m = lumped RP ponding cap
```

A cell is wet iff `max_ponding > 0` — i.e. it sits in *any* topographic depression.
That set is fixed by the DEM and **independent of return period**. `water_level_m`
changes only depth, never extent.

**Evidence.** Pluvial flooded area is identical across all nine return periods for
every city (SSP5-8.5/2100): Bangkok 2355 km², HCMC 1454 km², Jakarta 530 km²,
Manila 290 km², Singapore 330 km² — RP2 = RP1000 exactly. Even with the 0.05 m
rendering floor, Manila pluvial is 0 km² at RP2 then a flat 280 km² from RP5
through RP1000.

**Why this is wrong:**

1. Real pluvial flood *extent* grows strongly with return period; here it is frozen.
2. There is no catchment/runoff routing — every depression is filled regardless of
   whether its upstream catchment could actually supply that much water.
3. RP2 is grossly overstated (every GLO-30 micro-pit wet), masked only by a
   rendering-time floor, not fixed in the model.
4. The function docstring claims RP-dependent extent ("only shallow depressions
   fill at low return periods") — the code does not deliver it.

## Goal

Replace the spatial distribution step with a **catchment-routed fill-and-spill
cascade** so pluvial flood extent responds to return period and concentrates in
genuinely flood-prone terrain. The IDF-anchored GEV rainfall side is unchanged.

Success criterion: the new model is re-validated against Singapore PUB
observations (`validate_pluvial_singapore.py`) and re-tuned to pass, and pluvial
extent grows monotonically with return period for every city.

## Solution Overview

The rainfall side of the pipeline is sound — `fit_pluvial_baseline_era5.py`
derives a per-RP `excess_mm` (GEV-fitted 6 h rainfall minus the city's primary
`drain_capacity_mm`), IDF-anchored and validated. Only the *spatial* step is
replaced: instead of collapsing the excess into one `depression_area_fraction`
scalar, route it across the terrain.

### Algorithm — Fill-Spill-Merge cascade

Reference: Barnes, Callaghan & Wickert (2020), *Computing water flow through
complex landscapes — Part 2: Fill-Spill-Merge*, Earth Surface Dynamics 8.

1. **Flow directions.** D8 flow directions on the conditioned DEM via pysheds —
   reuse the conditioned DEM/flow grid the HAND pipeline already computes.
2. **Depression inventory (topography-only, computed once per city).** Identify
   every depression: its cells, pour point, pour elevation, and its
   hypsometric curve `V(h)` (stored water volume when filled to elevation `h`)
   and `A(h)` (wet area at `h`). Depressions nest; build the depression
   hierarchy as a binary tree.
3. **Runoff supply (per RP).** Each land cell generates runoff volume
   `excess_depth_m × runoff_coeff(x, y) × cell_area`. Accumulate runoff down the
   D8 flow directions; the volume arriving at each depression is its catchment
   supply.
4. **Cascade (per RP).** Fill each depression from its catchment supply via
   `V(h)`. If supply exceeds capacity-to-pour-point, the surplus **spills** over
   the pour point into the downstream depression (or off-domain). Sibling
   depressions that fill to a shared level **merge** into their parent. Process
   the hierarchy leaves-up.
5. **Output.** For every cell ending under water, `depth = water_level − bed`.

Because the depression inventory and hypsometric curves are RP-independent, they
are computed **once** per city; each of the nine return periods is then only the
cheap step-3/4 cascade.

### Why this fixes the frozen extent

- **Low RP:** small `excess_depth_m` → only depressions fed by large catchments
  collect enough runoff to pond above the wetness threshold; isolated micro-pits
  stay dry → small extent.
- **High RP:** large `excess_depth_m` → depressions fill, overflow, spill, and
  merge; water spreads to new cells → extent grows monotonically with RP and
  concentrates in genuinely flood-prone lows, differing city-to-city by drainage
  structure.

### Enhancements folded in (compute-free)

- **A. Precompute topography once.** Flow directions, depression hierarchy and
  hypsometric curves are RP-independent — computed once, reused for all nine RPs.
  This is *faster* than the current model, which recomputes `fill_depressions`
  every RP.
- **B. Spill into rivers and sea as outflow.** When the cascade spills runoff
  onto a `river_mask_*.tif` or `sea_mask_*.tif` cell, the water leaves the
  domain instead of ponding. Fixes the current artifact of pluvial water
  puddling on river channels.
- **C. Minimum-depression filter.** Depressions shallower than a threshold
  (default 0.5 m — GLO-30 vertical noise) are dropped from the inventory before
  the cascade; their cells route through as ordinary terrain. Removes the
  spurious-micro-pit noise floor at source.
- **D. Share flow computation with HAND.** Reuse the pysheds-conditioned DEM /
  flow grid the HAND step already produces, rather than recomputing.

### Enhancement E — spatially-variable runoff coefficient (ESA WorldCover)

Today `runoff_coeff` is one per-city scalar (~0.75). Real runoff generation
varies 4–5× across a city. A new step fetches **ESA WorldCover 2021 v200**
(10 m global land cover, free) per city and derives a per-cell runoff
coefficient:

| WorldCover class | Runoff coeff |
|---|---|
| 10 Tree cover | 0.20 |
| 20 Shrubland | 0.30 |
| 30 Grassland | 0.25 |
| 40 Cropland | 0.35 |
| 50 Built-up | 0.90 |
| 60 Bare / sparse vegetation | 0.50 |
| 80 Permanent water | 1.00 |
| 90 Herbaceous wetland | 0.60 |
| 95 Mangroves | 0.55 |
| 100 Moss / lichen | 0.30 |

(Class 70 Snow/ice does not occur in the ASEAN domains.) WorldCover 10 m is
mapped class → coefficient, then resampled to the 30 m DEM grid by **averaging
the coefficient** (so a half-paved cell gets ~0.55 — sub-grid impervious
weighting). The result is reprojected to the DEM CRS and written as
`data/<city>/runoff_coeff_<utm>.tif`. The per-city scalar `runoff_coeff` remains
the fallback when no WorldCover raster exists. The runoff-coefficient values are
tunable during the Singapore calibration step.

## Components & File Structure

### New files

- **`model/pluvial_model.py`** — the fill-and-spill solver. Public entry point:
  `flood_depth_pluvial_fillspill(dem, excess_depth_m, runoff_coeff, sea_mask,
  river_mask, profile, *, min_depression_depth_m=0.5, wet_threshold_m=0.05)`.
  `runoff_coeff` accepts either a per-cell `np.ndarray` (the WorldCover-derived
  raster) or a `float` (the per-city fallback scalar); `excess_depth_m` is the
  scalar post-drain rain depth for the return period. Internals:
  depression-hierarchy build + hypsometric curves (precomputed), the per-RP
  volume cascade, numba-accelerated kernels. Self-contained so
  `flood_depth_model.py` does not grow.
- **`scripts/fetch_esa_worldcover.py`** — fetch ESA WorldCover 10 m for a city
  DEM bbox, map land-cover classes → runoff coefficient, resample to the 30 m
  DEM grid (coefficient-averaged), reproject to the DEM CRS, write
  `data/<city>/runoff_coeff_<utm>.tif`. Follows the existing
  `fetch_copernicus_dem.py` pattern.
- **`tests/test_pluvial_fillspill.py`** — synthetic-DEM unit tests.

### Modified files

- **`scripts/fit_pluvial_baseline_era5.py`** — emit `excess_depth_m` per RP
  (`max(0, GEV_6h(RP) − drain_capacity_mm)/1000`). Stop multiplying by the
  scalar `runoff_coeff` and dividing by `depression_area_fraction` — the
  runoff-coefficient multiply moves to run time so it can be spatial. The
  pluvial `water_level_m` column in the hazard CSV now carries `excess_depth_m`;
  the output note is updated to say so.
- **`scripts/run_multihazard.py`** — dispatch pluvial to
  `flood_depth_pluvial_fillspill`; load the runoff-coeff raster and river mask;
  add `--pluvial-model {fillspill,legacy}` (default `fillspill`).
- **`scripts/run_city_pipeline.py`** — add a WorldCover fetch + runoff-coeff
  raster build step; thread `--pluvial-model`.
- **`model/flood_depth_model.py`** — `flood_depth_pluvial_ponding` kept
  untouched as the `legacy` option.
- **`scripts/cities.py`** — `runoff_coeff` documented as the fallback scalar
  used when no WorldCover raster exists; `depression_area_fraction` marked
  deprecated (unused by the fill-spill model).
- **`docs/hazard_methodology_comparison.md`** — §4 pluvial section rewritten to
  describe the catchment-routed model.

## Validation, Testing & Rollout

1. **TDD.** Write `tests/test_pluvial_fillspill.py` first, build the solver
   against it. Synthetic-DEM cases:
   - a depression wets only when its catchment supply exceeds the wet threshold;
   - a two-depression chain where the upstream one spills into the downstream
     one once full;
   - flooded extent grows monotonically as `excess_depth_m` increases;
   - runoff spilled onto a river/sea cell leaves the domain (no ponding there);
   - depressions below `min_depression_depth_m` are ignored.
2. **Re-fit baselines.** Re-run `fit_pluvial_baseline_era5.py` for all 11 city
   configs to emit `excess_depth_m`.
3. **WorldCover.** Fetch ESA WorldCover and build `runoff_coeff_<utm>.tif` for
   every city.
4. **Calibrate on Singapore.** Re-run pluvial for Singapore; validate with
   `validate_pluvial_singapore.py` against PUB observations; tune
   `wet_threshold_m`, `min_depression_depth_m` and the WorldCover→coefficient
   mapping until it passes.
5. **Confirm IDF anchors.** Re-run the IDF-anchor validators
   (`validate_pluvial_idf_anchors.py`, `validate_pluvial_all_cities.py`) — the
   rainfall side is unchanged, so these are expected to be unaffected; confirm.
6. **Roll out.** Re-run pluvial for all cities; verify extent grows
   monotonically with RP; spot-check the `rp_comparison` panels; A/B against
   `--pluvial-model legacy`; cross-check Bangkok.

## Known Risks

- **The depression-hierarchy fill-spill is the substantial implementation
  piece.** Mitigated by following the well-defined Barnes et al. (2020)
  Fill-Spill-Merge algorithm and by the synthetic-DEM unit tests built first.
- **pysheds 0.5 + NumPy 2** — pysheds 0.5 uses the removed `np.in1d`; the shim
  already present at the top of `model/hand_model.py` is reused.
- **ESA WorldCover fetch** is a network dependency; the fetch script caches the
  per-city clip to `data/<city>/` so re-runs are offline.

## Out of Scope

- Transient street sheet-flow during the storm (rain-on-grid hydrodynamic) —
  considered and rejected during brainstorming as too slow.
- Spatially-variable drainage capacity — no spatial drainage dataset available.
- Multi-duration design storms (1 h / 3 h / 24 h) — the model stays on the
  existing 6 h design storm.
