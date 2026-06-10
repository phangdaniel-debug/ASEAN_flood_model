# GloFAS Fluvial Injection Design

**Date:** 2026-05-09
**Status:** Approved
**Closes:** Issue #16 (Bangkok Chao Phraya), Issue #21 (placeholder config), Issue #11 (partial — improves Jakarta fluvial for JKT2020 validation)

---

## Goal

Replace the ERA5-rainfall-derived fluvial stages for four cities where the local ERA5 point approach is physically wrong (mega-basins, main-stem rivers) with stages derived directly from GloFAS v4 Reanalysis daily river discharge. The fix unlocks usable fluvial depth maps for Bangkok Chao Phraya, Manila (Pasig/Marikina main-stem), and HCMC (Saigon River), and improves Jakarta's fluvial baseline for validation.

## Background

The ERA5 fluvial fitting path (`fit_fluvial_baseline_era5.py`) derives peak discharge from a single ERA5-Land grid-cell rainfall using SCS Curve Number → SCS Unit Hydrograph → Manning stage. This works for small urban sub-basins (≤50 km²) where the local rainfall dominates. It fails for:

- **Bangkok Chao Phraya** (160,000 km² upstream): every RP saturates the 8 m model cap.
- **Manila Pasig/Marikina main-stem** (572 km²): sub-basin model misses the main-stem flood signal.
- **HCMC Saigon River** (4,700 km²): inner-canal sub-basin only; main-stem unmodelled.
- **Jakarta Ciliwung** (full basin): local ERA5 captures only the immediate city sub-catchment.

GloFAS v4 Reanalysis provides daily discharge at ~5 km resolution from 1984 to near-real-time, freely available via the Open-Meteo Flood API (no registration, CC-BY 4.0).

---

## Architecture

### Files changed

| File | Change |
|---|---|
| `scripts/fit_fluvial_glofas.py` | **New** — fetch, fit, convert, write |
| `tests/test_fit_fluvial_glofas.py` | **New** — ~10 unit tests |
| `scripts/cities.py` | Add `glofas_lat`, `glofas_lon` fields to `CityConfig`; populate for 4 cities |
| `scripts/run_city_pipeline.py` | Add `--fit-glofas/--no-fit-glofas` flag |

### Data flow

```
Open-Meteo Flood API (GloFAS v4, free, no key)
  https://flood-api.open-meteo.com/v1/flood
  ?latitude={glofas_lat}&longitude={glofas_lon}
  &daily=river_discharge&start_date=1984-01-01&end_date=2024-12-31
      |
      v
  daily discharge series (m³/s, ~40 years)
      |
      v  cache as parquet: cache/glofas_{slug}.parquet
      |
      v
  annual maxima (one value per calendar year)
      |
      v  drop partial years (first/last if < 12 months data)
      |
      v
  GEV fit via gev_utils.py  (xi_max=0.30, same as ERA5 path)
      |
      v
  RP discharges: Q(RP2, 5, 10, 25, 50, 100, 200, 500, 1000)  m³/s
      |
      v  Manning stage: d = (Q * n / (w * sqrt(S))) ^ (3/5)
         using CityConfig.channel_width_m, mannings_n, channel_slope
      |
      v
  overwrite fluvial rows in data/{slug}/hazard_baseline_template.csv
  (coastal and pluvial rows untouched)
```

---

## CityConfig changes

Two optional fields added to `CityConfig` dataclass (default `None`):

```python
glofas_lat: float | None = None  # lat of GloFAS river sample point
glofas_lon: float | None = None  # None = skip GloFAS injection for this city
```

### GloFAS sample coordinates

| Slug | River | `glofas_lat` | `glofas_lon` | Rationale |
|---|---|---|---|---|
| `jakarta` | Ciliwung | -6.50 | 106.83 | Upstream of Jakarta urban area near Depok — full Ciliwung basin signal |
| `bangkok_chao_phraya` | Chao Phraya | 14.20 | 100.35 | Bang Sai / Ang Thong — above tidal influence, per existing CityConfig notes |
| `manila` | Marikina | 14.69 | 121.11 | Rodriguez / Montalban — above Marikina valley narrows, full sub-basin |
| `hcmc` | Saigon | 10.98 | 106.65 | Thu Dau Mot — above tidal backwater from Mekong delta |

Manning channel parameters (`channel_width_m`, `mannings_n`, `channel_slope`) are already set correctly in each CityConfig for the main river — no new fields required.

---

## Script interface: `fit_fluvial_glofas.py`

```
python scripts/fit_fluvial_glofas.py --city jakarta
python scripts/fit_fluvial_glofas.py --city bangkok_chao_phraya --dry-run
python scripts/fit_fluvial_glofas.py --city manila --cache cache/glofas_manila.parquet
python scripts/fit_fluvial_glofas.py --city hcmc --no-cache
```

**Flags:**
- `--city SLUG` (required) — must be a city with `glofas_lat` set
- `--cache PATH` — parquet cache path (default: `cache/glofas_{slug}.parquet`)
- `--no-cache` — force re-fetch even if cache exists
- `--dry-run` — print RP table, do not write CSV
- `--xi-max FLOAT` — GEV shape cap (default: 0.30)
- `--output PATH` — override default CSV path

---

## Pipeline integration: `run_city_pipeline.py`

New flag:
```
--fit-glofas/--no-fit-glofas   (default: auto)
```

Behaviour:
- **Auto (default):** GloFAS fitting runs when `city.glofas_lat is not None`, skipped otherwise.
- When GloFAS fitting runs, ERA5 fluvial fitting is **automatically suppressed** for that city (GloFAS supersedes it).
- User can force ERA5 fluvial anyway with explicit `--fit-fluvial`.
- Cities without `glofas_lat` are completely unaffected by this flag.

Example:
```bash
python scripts/run_city_pipeline.py --city bangkok_chao_phraya --scenario SSP5-8.5 --horizon 2100
# → GloFAS fluvial runs automatically; ERA5 fluvial skipped
```

---

## Error handling

| Condition | Behaviour |
|---|---|
| `city.glofas_lat is None` | Raise `ValueError("No GloFAS coordinates configured for {slug}")` |
| API returns all-null discharge at coordinates | Raise `ValueError` with coords + suggestion to adjust lat/lon |
| Fewer than 10 years of valid annual maxima | Raise `ValueError("Insufficient GloFAS record: {n} years < 10 minimum")` |
| GEV xi exceeds xi_max | Cap to xi_max, emit warning (same as ERA5 path) |
| Cache hit | Skip HTTP fetch entirely |
| `--dry-run` | Print table, exit 0, CSV unchanged |

---

## CSV output format

Fluvial rows written to `hazard_baseline_template.csv` follow the existing schema exactly:

```
hazard_type,return_period,baseline_water_level_m,source_note,gev_shape,gev_loc_m3s,gev_scale_m3s,datum_note
fluvial,10,3.45,"GloFAS v4 Reanalysis via Open-Meteo Flood API (-6.50N 106.83E); GEV fit to 40 annual maxima of daily discharge (1984-2024); Manning w=15.0m n=0.033 S=0.0015; xi=0.1234 mu=450.2m3s sigma=120.3m3s",0.1234,450.2,120.3,"relative_stage_above_channel_bed_m; no_absolute_datum_conversion_required; compatible_with_HAND_model_which_is_also_relative"
```

Note: `gev_loc_mm` / `gev_scale_mm` columns repurposed as `gev_loc_m3s` / `gev_scale_m3s` (GEV is fitted to discharge in m³/s, not rainfall in mm). Column names in the CSV header are unchanged to preserve schema compatibility.

---

## Tests (`tests/test_fit_fluvial_glofas.py`)

| Test | Covers |
|---|---|
| `test_fetch_discharge_returns_series` | Mock HTTP → DataFrame with DatetimeIndex, `discharge_m3s` column |
| `test_fetch_discharge_cache_hit` | Cache parquet exists → no HTTP call |
| `test_fetch_discharge_empty_response` | All-null API response → raises `ValueError` |
| `test_annual_maxima_basic` | Known daily series → correct annual maxima |
| `test_annual_maxima_partial_year_dropped` | Partial first/last calendar years excluded |
| `test_manning_stage` | Known Q=500, w=350, n=0.035, S=0.00005 → correct depth (hand-calculated: ~8.5 m) |
| `test_gev_fit_monotonic` | RP stages strictly increase with return period |
| `test_write_csv_overwrites_fluvial_rows` | Fluvial rows replaced; coastal/pluvial rows untouched |
| `test_dry_run_no_write` | `--dry-run` → stdout table printed, CSV unchanged |
| `test_pipeline_skips_era5_fluvial_when_glofas_set` | `run_city_pipeline` suppresses ERA5 fluvial step when `glofas_lat` set |

---

## Out of scope

- GloFAS climate projections / SSP discharge scaling (future work — use ERA5-based SLR scaling for now)
- Rating curve calibration against observed gauge data (Manning approximation used throughout, consistent with ERA5 path)
- Any changes to pluvial or coastal fitting
- Cities without `glofas_lat` set
