# Fluvial ERA5-Land Migration — Design Spec

**Date:** 2026-04-28  
**Status:** Approved — pending implementation  
**Closes:** Issue #20 in `docs/hazard_methodology_comparison.md`  
**Objective:** Migrate `fit_fluvial_baseline_era5.py` from NASA POWER MERRA-2 to ERA5-Land via Open-Meteo Archive, eliminating the wet-bias problem that makes fluvial re-fitting unusable without `precip_scale`, and re-enabling `--fit-fluvial` by default in the pipeline.

---

## 1. Background

After the 2026-04-26 pluvial redesign removed `precip_scale` from `CityConfig`, the fluvial script (`fit_fluvial_baseline_era5.py`) became broken for re-fitting: MERRA-2 24h annual maxima for Singapore produce design discharges that saturate Manning's `max_stage_m=8.0 m` cap at every return period, making all RP outputs identical. The workaround (`--no-fit-fluvial` default) preserves old calibrated baseline rows on disk, but those rows have stale `source_note` strings referencing MERRA-2 and cannot be regenerated. Fluvial ERA5-Land migration closes this gap.

For 24h daily totals, ERA5-Land performs significantly better than for 6h sub-daily rainfall:
- The ERA5-Land gauge-bias correction is strongest at daily timescales
- Daily totals are less sensitive to convective cell size (~9 km grid)
- Expected residual bias vs published 24h IDF anchors: ≤ 30% (vs ~50% for 6h pluvial)

The hydraulic chain (SCS-CN effective runoff → SCS triangular unit hydrograph → Manning's normal depth) is unchanged. Only the precipitation source changes.

---

## 2. Scope

**In scope:**
- `scripts/gev_utils.py` — add `fetch_hourly_precip_era5land()` (moved from pluvial script)
- `scripts/fit_pluvial_baseline_era5.py` — remove local fetch function; import from `gev_utils`
- `scripts/fit_fluvial_baseline_era5.py` — swap data source; remove `--precip-scale`; update defaults and notes
- `scripts/run_city_pipeline.py` — re-enable `--fit-fluvial` by default; remove MERRA-2 warning
- `scripts/validate_fluvial_idf_anchors.py` — new validation script (analogous to pluvial validator)
- `tests/test_fluvial_redesign.py` — new unit tests for the migration
- `data/*/hazard_baseline_template.csv` — refit fluvial rows for all 9 active cities
- `docs/hazard_methodology_comparison.md` — Issue #20 resolved; §3.1 update

**Out of scope:**
- The SCS-CN → Manning hydraulic chain (unchanged)
- The 24h accumulation window (unchanged; appropriate for daily-driven catchment flooding)
- The `max_stage_m=8.0 m` cap (unchanged)
- GloFAS / RID supplementary configs (Bangkok Chao Phraya, etc.) — ERA5 single-point fluvial still not meaningful for mega-basins; documented limitation remains

---

## 3. Architecture

### 3.1 `gev_utils.py` — shared fetch function

Move `fetch_hourly_precip_era5land()` from `fit_pluvial_baseline_era5.py` into `gev_utils.py` verbatim. Both fit scripts import it from there. The function signature and behaviour are unchanged:

```python
def fetch_hourly_precip_era5land(
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
    chunk_years: int = 5,
) -> pd.Series:
    """Download hourly ERA5-Land precipitation (mm/h) from Open-Meteo Archive."""
```

Cache files written by the pluvial script remain readable by the fluvial script (same Parquet format, same column name `precipitation_mm_h`). Cache sharing is opt-in via `--cache-precip`.

### 3.2 `fit_fluvial_baseline_era5.py` — source swap

**Remove:**
- `fetch_hourly_precip()` function (MERRA-2 / NASA POWER)
- `NASA_POWER_URL`, `NASA_POWER_START_YEAR` constants
- `--precip-scale` CLI option
- Bias-correction block (`if abs(precip_scale - 1.0) > 1e-6: precip = precip * precip_scale`)

**Add:**
```python
from scripts.gev_utils import fetch_hourly_precip_era5land
```

**Change defaults:**
- `--xi-max` default: `0.5` → `0.30` (aligns with pluvial; caps Frechet tails for tropical 24h precip)
- `--start-year` default: `2001` (unchanged; ERA5-Land covers 1950+ but 2001 gives 24 years)

**Update `source_note` in output rows:**
```
"ERA5-Land via Open-Meteo Archive ({lat}N {lon}E); GEV fit to {n_years} annual maxima
of {window_h}h rainfall ({y0}–{y1}); SCS CN=...; ..."
```

### 3.3 `run_city_pipeline.py` — re-enable default

```python
# Before
do_fit_fluvial = False if fit_fluvial_override is None else fit_fluvial_override

# After
do_fit_fluvial = fit_era5 if fit_fluvial_override is None else fit_fluvial_override
```

Remove the `"WARNING: fluvial still uses MERRA-2"` echo block. Update the `--fit-fluvial/--no-fit-fluvial` help string to remove the MERRA-2 pending-migration caveat.

### 3.4 `validate_fluvial_idf_anchors.py` — new validation script

Same structure as `validate_pluvial_idf_anchors.py`. For each active city, downloads ERA5-Land 24h annual maxima (honouring `--cache-dir`), fits GEV at `xi_max=0.30`, and reports the deviation from published national 24h design-rainfall benchmarks.

**Anchors used (24h design rainfall at RP10, published national IDF):**

| City group | Anchor (mm, 24h RP10) | Source |
|---|---|---|
| Singapore | 180 | PUB / MSS Singapore IDF |
| KL / Klang / Langat | 200 | JPS DID Malaysia |
| Bangkok / Bangkok CP | 170 | TMD Thailand |
| Jakarta / Tangerang / Bekasi | 180 | BMKG Indonesia |

**Verdict thresholds:** PASS ≤ 30% deviation; WARN 30–50%; FAIL > 50%.  
30% tolerance (vs 25% for pluvial) reflects that 24h GEV at RP10 on a 24-year record is more stable than 6h GEV, but ERA5-Land gauge-bias correction at daily timescales still carries ~10–20% uncertainty.

---

## 4. Testing — `tests/test_fluvial_redesign.py`

| Test | Description |
|---|---|
| `test_fluvial_script_has_no_precip_scale` | `fit_fluvial_baseline_era5.py` source does not contain `precip_scale` |
| `test_fluvial_script_uses_open_meteo_endpoint` | Source references `open-meteo.com`, not `power.larc.nasa.gov` |
| `test_gev_utils_exports_era5land_fetch` | `from scripts.gev_utils import fetch_hourly_precip_era5land` succeeds |
| `test_pluvial_script_imports_era5land_from_gev_utils` | Pluvial script no longer defines `fetch_hourly_precip_era5land` locally |
| `test_scs_effective_runoff_basic` | `scs_effective_runoff(200, 85)` returns value within expected range |
| `test_scs_effective_runoff_below_ia` | Rainfall below initial abstraction → 0 runoff |
| `test_mannings_stage_positive` | `mannings_stage(10.0, 10.0, 0.04, 0.002)` returns positive float |
| `test_xi_max_default_is_030` | CLI `--xi-max` default in fluvial script is `0.30` |
| `test_fit_fluvial_default_enabled_in_pipeline` | `run_city_pipeline.py` source: `do_fit_fluvial` resolves to `fit_era5` when override is None |

---

## 5. Baseline CSV refit

All 9 active cities are refit with the new ERA5-Land source as part of this implementation (ERA5-Land via Open-Meteo requires no credentials). Cities and their ERA5 coordinates:

| City slug | ERA5 lat | ERA5 lon |
|---|---|---|
| singapore | 1.2903 | 103.8519 |
| kuala_lumpur | 3.1390 | 101.6869 |
| klang_shah_alam | 3.070 | 101.515 |
| subang_langat | 2.975 | 101.760 |
| bangkok | 13.7563 | 100.5018 |
| bangkok_chao_phraya | 13.7563 | 100.5018 |
| jakarta | -6.2088 | 106.8456 |
| tangerang | -6.225 | 106.625 |
| bekasi_depok | -6.300 | 107.000 |

Each baseline CSV is refit by running the updated `fit_fluvial_baseline_era5.py` with the city's `CityConfig` parameters. The updated CSVs are committed to the repository.

---

## 6. Documentation updates

| File | Change |
|---|---|
| `docs/hazard_methodology_comparison.md` | §3.1: update fluvial data source; Issue #20: mark RESOLVED; Recent Fixes table: add 2026-04-28 entry |
| `scripts/fit_fluvial_baseline_era5.py` | Module docstring: update "Data source" section to ERA5-Land |

---

## 7. Known limitations (unchanged)

- ERA5-Land single-point approach cannot capture upstream basin forcing for large rivers (Chao Phraya >100,000 km², Ciliwung ~370 km², Cisadane ~1,400 km²). Single-reach configs document this explicitly.
- 24-year record (2001–2024) limits statistical robustness at RP≥500; `xi_max=0.30` cap mitigates tail blow-up.
- Bangkok Chao Phraya supplementary config still requires GloFAS-derived discharge inputs for meaningful fluvial stages; ERA5 single-point is documented as not meaningful for that config.
