# MSL to EGM2008 Offset Derivation — Design Spec

**Date:** 2026-04-27  
**Status:** Approved — pending implementation  
**Closes:** Issue #12 in `docs/hazard_methodology_comparison.md`  
**Objective:** Replace the `msl_to_egm2008_offset = 0.0` placeholder in all active city configs with derived Mean Dynamic Topography (MDT) values, and patch the existing baseline CSVs so coastal water levels are correctly referenced to the EGM2008 datum.

---

## 1. Background

The Copernicus GLO-30 DEM uses EGM2008 as its vertical reference. Tide gauge sea levels are de-meaned to local MSL. The difference between local MSL and EGM2008 is the **Mean Dynamic Topography** (MDT) — the permanent tilt of the ocean surface due to large-scale circulation. In Southeast Asia the MDT is positive and non-trivial:

| Gauge / Sea | Expected MDT |
|---|---|
| Singapore (Singapore Strait) | ~+0.04 m |
| Port Klang (Strait of Malacca) | ~+0.12 m |
| Ko Lak / Bangkok (Gulf of Thailand) | ~+0.28 m |
| Tanjung Priok / Jakarta (Java Sea) | ~+0.30 m |

With `offset = 0.0`, coastal water levels for Bangkok and Jakarta are systematically ~0.25–0.30 m too low, causing a consistent underestimate of coastal flood extent. This is smaller than the GLO-30 DEM RMSE (~1–2 m) but is a systematic bias rather than random error, and should be corrected.

---

## 2. Scope

**In scope:**
- All city configs with `uhslc_id != None` and an existing baseline CSV: Singapore, kuala_lumpur, klang_shah_alam, subang_langat, bangkok, bangkok_chao_phraya, jakarta, tangerang, bekasi_depok
- Jakarta's coastal rows (literature values, not UHSLC-fitted) receive the same additive offset — the MDT correction is valid regardless of water level source

**Out of scope:**
- Manila and HCMC (`uhslc_id=None`, no coastal CSV generated yet)
- Fluvial and pluvial rows (water levels are self-relative; no absolute datum applies)

---

## 3. MDT Source

**Product:** CNES-CLS18 global MDT  
**Access:** Copernicus Marine Service (CMEMS) via `copernicusmarine` Python package (free registration at marine.copernicus.eu)  
**Resolution:** 1/8° (~14 km) — sufficient for MDT, which varies at 100–1000 km scales  
**Variable:** `mdt` (metres above EGM2008)  
**Bounding box fetched:** −10°S to 20°N, 95°E to 112°E (covers all active gauges; small subset, lazy remote access)

The `era5_lat` / `era5_lon` from each city's `CityConfig` is used as the lookup coordinate. Gauge coordinates are within 50–150 km of the ERA5 point; MDT variation over this distance is ≤0.02 m (well within screening accuracy).

---

## 4. Architecture — `scripts/derive_msl_egm2008_offsets.py`

### 4.1 Inputs

- `scripts/cities.py` — read `era5_lat`, `era5_lon`, `uhslc_id`, city key for all configs
- CMEMS CNES-CLS18 MDT product (fetched on demand)
- `data/<city>/hazard_baseline_template.csv` — patched in-place when `--write` is passed

### 4.2 Processing steps

**Step 1 — Fetch MDT grid**

```python
import copernicusmarine
ds = copernicusmarine.open_dataset(
    dataset_id="cmems_obs-sl_glo_phy-mdt_my_0.125deg_P20Y-T",
    variables=["mdt"],
    minimum_latitude=-10, maximum_latitude=20,
    minimum_longitude=95, maximum_longitude=112,
)
```

**Step 2 — Interpolate per unique gauge**

Group city configs by `uhslc_id` (cities sharing a gauge share the same MDT value). For each unique gauge, interpolate:

```python
offset = float(ds["mdt"].interp(latitude=lat, longitude=lon, method="linear"))
```

**Step 3 — Patch baseline CSVs**

For each city with a real baseline CSV:
1. Load CSV as `pandas.DataFrame`
2. Select rows where `hazard_type == "coastal"` and current `datum_note` does not already contain `mdt_cnes_cls18`
3. Add `offset` to `baseline_water_level_m`
4. Append `| mdt_cnes_cls18=+X.XXXXm applied YYYY-MM-DD` to `datum_note`
5. Write CSV back (idempotent — skips rows already patched)

**Step 4 — Update `cities.py`**

For each city config, print the suggested replacement:
```
  [singapore]  msl_to_egm2008_offset: 0.0 -> +0.0412
```
With `--write`, auto-patch `cities.py` using line-by-line regex: iterate all `CityConfig` instances in `CITIES`, match each by `city_key`, and replace its `msl_to_egm2008_offset=0.0` line with the derived value. Multiple configs sharing the same UHSLC gauge (e.g., kuala_lumpur / klang_shah_alam / subang_langat all share UHSLC 140) each get the same offset written independently — the patch iterates all configs, not just unique gauges.

### 4.3 CLI

```bash
# Dry-run: print derived offsets and affected CSV row counts, make no changes
python scripts/derive_msl_egm2008_offsets.py

# Apply: patch CSVs + cities.py
python scripts/derive_msl_egm2008_offsets.py --write

# Apply CSVs only (skip cities.py auto-patch)
python scripts/derive_msl_egm2008_offsets.py --write --no-write-cities
```

### 4.4 Idempotency

The script checks for `mdt_cnes_cls18` in `datum_note` before patching. Running `--write` a second time is a no-op for already-patched rows. `cities.py` patch checks whether the current value already equals the derived value before writing.

---

## 5. Testing — `tests/test_msl_egm2008_offsets.py`

| Test | Type | Description |
|---|---|---|
| `test_csv_patch_coastal_only` | Unit | Patching adds offset to coastal rows only; fluvial/pluvial rows unchanged |
| `test_csv_patch_idempotent` | Unit | Running patch twice produces same result as once |
| `test_datum_note_update` | Unit | `datum_note` append is correct and idempotent |
| `test_offset_range` | Unit | Each active gauge's offset is in [0.0, 0.5] m (sanity check on dummy MDT grid) |
| `test_live_cmems` | Integration | Marked `@pytest.mark.skip` unless `CMEMS_USERNAME` env var set; checks live offsets are within ±0.05 m of known MDT literature estimates |

---

## 6. Documentation updates

| File | Change |
|---|---|
| `docs/hazard_methodology_comparison.md` | §2.2: replace "0.0 placeholder" note with derived values table; Issue #12: mark RESOLVED |
| `scripts/convert_datum.py` | Update `MSL_TO_EGM2008_SINGAPORE` from 0.0 to derived value; add constants for other gauges |
| `scripts/cities.py` | Replace PSMSL/NGA derivation workflow comment with reference to `derive_msl_egm2008_offsets.py` |
| `docs/hazard_methodology_comparison.md` (Recent fixes table) | Add 2026-04-27 entry for Issue #12 |

---

## 7. Known limitations

- MDT from CNES-CLS18 represents a 20-year mean (1993–2012). Long-term MDT trends (~0.001 m/yr) are negligible for this model's purpose.
- Using `era5_lat`/`era5_lon` as the MDT lookup point introduces ≤0.02 m error vs the true gauge location — well within screening accuracy.
- Jakarta coastal rows are literature estimates (not GEV-fitted); the MDT offset is applied identically but the underlying water level uncertainty (~0.2 m) dominates.
- CMEMS requires a free account. Credentials must be available in the environment (via `copernicusmarine configure` or `CMEMS_USERNAME`/`CMEMS_PASSWORD` env vars). The dry-run mode reports this requirement clearly if credentials are absent.
