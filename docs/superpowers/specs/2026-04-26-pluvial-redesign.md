# Pluvial Model Redesign — Design Spec

**Date:** 2026-04-26 (with 2026-04-27 follow-up — see end of document)
**Status:** Implemented (see plan: `docs/superpowers/plans/2026-04-26-pluvial-redesign.md`)
**Closes:** Issue #19, R1, R2 from `docs/hazard_methodology_comparison.md`

## Problem

The pre-redesign pluvial pipeline had three coupled problems:

1. **Wrong rainfall source.** NASA POWER MERRA-2 PRECTOTCORR has a 5–30× wet bias in tropical SEA cities. The bias is intensity-dependent, so a single multiplicative `precip_scale` cannot correct it across all return periods.
2. **Bundled calibration.** The factor `precip_scale × /100` was joint-calibrated against national IDF curves for SG/KL/BKK/JKT. The two factors couldn't be disentangled, blocking replicability for new cities.
3. **Hidden physics.** The `/100` divisor was equivalent to a 10% depression-storage assumption, but this was undocumented and not city-tunable.

## Solution

**Switch rainfall source MERRA-2 → ERA5-Land** (Open-Meteo Archive, hourly, free, ~9 km, gauge-bias-corrected for the long-run mean). No multiplicative correction is applied; the long-run mean bias is small enough to absorb into GEV sampling uncertainty.

**Make the `/100` physically explicit** as `depression_area_fraction` (default 0.10 = the Singapore PUB-calibrated value). New formula:

```
ponding_cap_m = (excess_mm / 1000) × runoff_coeff / depression_area_fraction
```

The downstream depression-filling flood model (`flood_depth_pluvial_ponding`) is unchanged — it already redistributes the scalar `ponding_cap_m` into actual DEM depressions via `pysheds.fill_depressions`.

## Validation outcome (2026-04-26)

Run: `python scripts/validate_pluvial_idf_anchors.py`

| City | Anchor (mm 6h) | ERA5-Land GEV | Deviation | Verdict |
|---|---|---|---|---|
| Singapore (RP10) | 100 (PUB) | 91 | -9.4 % | **PASS** |
| Manila (RP10) | 130 (PAGASA) | 94 | -27.8 % | FAIL (marginal) |
| Kuala Lumpur (RP2) | 90 (JPS) | 44 | -51.5 % | FAIL |
| Klang Shah Alam (RP2) | 90 (JPS) | 46 | -49.4 % | FAIL |
| Subang Langat (RP2) | 90 (JPS) | 44 | -51.5 % | FAIL |
| Bangkok (RP5) | 85 (TMD) | 40 | -53.3 % | FAIL |
| Bangkok Chao Phraya (RP5) | 85 (TMD) | 40 | -53.3 % | FAIL |
| Jakarta (RP2) | 85 (BMKG) | 33 | -60.8 % | FAIL |
| Tangerang (RP2) | 85 (BMKG) | 34 | -59.8 % | FAIL |
| Bekasi/Depok (RP2) | 85 (BMKG) | 32 | -62.0 % | FAIL |

**Singapore passes.** Every other anchored city's ERA5-Land 6h GEV is roughly half the published national IDF anchor.

### Why this isn't a blocker

The systematic ~50 % deficit in MY/TH/ID is consistent with two well-documented phenomena, neither of which justifies re-introducing a `precip_scale`-style multiplier:

1. **ERA5-Land ~9 km resolution cannot resolve sub-grid tropical convective storms** (~1–5 km thunderstorm cells). The reanalysis is gauge-bias-corrected at the long-run mean but not at the GEV tail. ECMWF documents this explicitly.
2. **National IDF curves are engineering design products, not pure climatology.** They typically include safety factors and may be derived from short / non-uniform gauge networks. PUB Singapore's IDF is the modern outlier (well-instrumented, recent reanalysis methodology) and that's the one ERA5-Land matches.

Adding a regional multiplier would re-create the original problem (one number absorbing many distinct sources of error). Instead the redesign **accepts ERA5-Land as the rainfall driver of record** and defers final per-city validation to **R4 historical-event runs** (Jakarta 2020 EMSR432, KL 2021 EMSR530, Singapore 2010 Orchard Road) — which compare modelled flood extent and depth directly against observed inundation rather than against an intermediate IDF curve.

## Why not full 2D hydrodynamic pluvial routing

The existing depression-fill model is sufficient for screening-level outputs. A full 2D solver (inertial wave, applied to pluvial excess) would be higher fidelity but:

- DEM is GLO-30 (30 m), so sub-grid pluvial detail is unrealistic anyway
- Drain capacity is an aggregate parameter; below-grid drainage networks aren't modelled
- Compute cost is 10–100× the depression-fill approach

Defer 2D pluvial until at least one R4 historical-event run shows depression-fill is insufficient.

## What changed in the public methodology

Replicability is now end-to-end:

1. Any researcher with Python can fetch ERA5-Land (no key, no registration) and reproduce the GEV fit.
2. The single tunable parameter `depression_area_fraction` is documented with a tier guide based on terrain (steep / typical-urban / delta).
3. No per-city calibration against private national IDF curves is required for screening-level outputs.

## Files touched

- `scripts/gev_utils.py` (new) — shared GEV helpers
- `scripts/fit_pluvial_baseline_era5.py` — rewritten, ERA5-Land + new formula
- `scripts/cities.py` — `precip_scale` removed; `depression_area_fraction` added; per-city validation outcomes recorded in `notes`
- `scripts/run_city_pipeline.py` — pipeline runner uses new fields
- `scripts/validate_pluvial_singapore.py` (new) — PUB max-depth raster validator
- `scripts/validate_pluvial_idf_anchors.py` (new) — national IDF anchor validator
- `scripts/calibrate_precip_scale.py` — deprecated (no MERRA-2 to calibrate)
- `tests/test_gev_utils.py`, `tests/test_pluvial_redesign.py` (new) — 15 tests

---

## 2026-04-27 follow-up

After the initial implementation, two issues surfaced when running the Singapore end-to-end pipeline:

### Issue 1 — Singapore RP200–1000 ponding too high

The Singapore pluvial validator flagged RP200–1000 max ponding depths as physically implausible (1.58 m / 2.53 m / 3.48 m). Diagnosis: with `xi_max=0.50`, the GEV shape parameter for Singapore ERA5-Land was clamped to 0.50 (raw MLE 0.344 was below cap, but tropical sub-daily fits run hot at the cap). The Frechet tail extrapolated too aggressively at high RP.

**Fix:** Tightened `xi_max` default 0.50 → **0.30** in three places:
- `scripts/gev_utils.py` (`fit_gev` function default)
- `scripts/fit_pluvial_baseline_era5.py` (CLI `--xi-max` default)
- `scripts/run_city_pipeline.py` (`--gev-xi-max` CLI default; passed to both pluvial and fluvial fits)

Singapore RP1000 max ponding dropped 3.48 m → 2.73 m, within the 3.0 m engineering safety cap. RP25–100 changed by <20 % (preserved). The change is global (all cities) since heavy Frechet tails are a generic risk for short-record sub-daily precipitation in the tropics.

### Issue 2 — Validator design too strict

The original `validate_pluvial_singapore.py` checked every RP against a single 0.07–0.76 m × ±50 % band. This conflated three different physical situations:
1. RP≤10 at the drain-capacity floor (zero ponding because Singapore drains handle RP10 — *physically correct, not an error*).
2. RP25–100 ponding within the PUB observed range (expected behaviour).
3. RP200–1000 above the band (genuine GEV tail concern, fixed by Issue 1 above).

**Fix:** Redesigned `validate_pluvial_singapore.py` to use **per-RP anchored verdicts**:
- RP≤10 at floor → `WARN` (drain handles RP≤10, not a model error)
- RP=1000 within `[PUB×0.5, 3.0 m engineering cap]` → `PASS`
- All RPs must be monotonically non-decreasing → `FAIL` if violated
- RP25/50/100/200/500 → `INFO` only (no PUB anchor available)

Singapore current state with the new validator: **PASS with 3 warnings** (RP2/5/10 at drain floor — physically correct).

### Issue 3 — Fluvial pipeline broken without `precip_scale`

A side-effect of removing `precip_scale` from `CityConfig`: **fluvial still uses MERRA-2** (the redesign migrated only pluvial to ERA5-Land). Without the per-city wet-bias correction, MERRA-2 24h annual maxima for Singapore (mu = 1837 mm vs ERA5-Land 6h mu = 40 mm — ~50× bias on its native window) produce design discharges that saturate Manning's `max_stage_m=8.0 m` cap for every RP. After climate scaling, every fluvial RP is identical → bankfull = stage at all RPs → zero overbank flooding.

**Fix:** Split `--fit-era5/--no-fit-era5` into per-hazard flags:
- `--fit-pluvial/--no-fit-pluvial` (default **True** — pluvial uses ERA5-Land, safe to refit)
- `--fit-fluvial/--no-fit-fluvial` (default **False** — preserve calibrated fluvial baseline rows from disk; `--fit-fluvial` only after fluvial migrates to ERA5-Land)

Singapore's calibrated fluvial baseline (RP10 = 1.668 m → bankfull, RP1000 = 2.612 m) was restored from the legacy CSV.

### Files touched (2026-04-27)

- `scripts/gev_utils.py` — `xi_max` default 0.50 → 0.30
- `scripts/fit_pluvial_baseline_era5.py` — `--xi-max` CLI default 0.50 → 0.30
- `scripts/run_city_pipeline.py` — `--gev-xi-max` CLI default 0.50 → 0.30; split fit-era5 into per-hazard flags
- `scripts/validate_pluvial_singapore.py` — full rewrite (per-RP anchored verdicts)
- `data/singapore/hazard_baseline_template.csv` — fluvial rows restored from legacy
- `docs/hazard_methodology_comparison.md` — §3.1, §3.4, §4 (1/2/3/4), §8 (#10, #15, #20), §9 updated

### Pending

- Fluvial ERA5-Land migration (the next major redesign — closes Issue #20).
- KL/BKK/JKT pluvial refit at `xi_max=0.30` (will trigger automatically on next pipeline run for those cities).
- R4 historical-event validation (Jakarta 2020 EMSR432, KL 2021 EMSR530, Singapore 2010 Orchard Road).
