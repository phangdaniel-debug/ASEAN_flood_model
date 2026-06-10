# Historical Event Validation (R4) — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Validate the multi-hazard flood pipeline against two documented historical flood events (Jakarta January 2020, KL December 2021) by comparing modelled depth rasters against Copernicus EMSR observed flood polygons, reporting CSI/H/FAR metrics and applying WARN/FAIL gates. Closes Issue #11 (R4).

**Architecture:** Single script `scripts/validate_historical_events.py` with a self-contained `EVENTS` registry dict (mirrors the `ANCHORS` pattern in `validate_fluvial_idf_anchors.py`). Auto-downloads EMSR ZIPs on first run, caches under `data/<city>/emsr/<event_id>/`, rasterizes flood polygons to the DEM grid, sweeps configured RP range across both hazard types, and picks the best-CSI match.

**Tech Stack:** Python + `fiona` (shapefile read) + `shapely` (geometry) + `rasterio` (rasterize, DEM grid) + `numpy` + `click` — all already in the pipeline stack. No `geopandas` dependency.

---

## 1. Configured Events

| Event ID | Activation | City | Date | Primary hazard | RP range to test |
|---|---|---|---|---|---|
| `EMSR432` | Jakarta floods | `jakarta` | Jan 2020 | pluvial + fluvial | RP10–RP200 for each |
| `EMSR530` | Malaysia floods | `kuala_lumpur` | Dec 2021 | fluvial + pluvial | RP10–RP200 for each |

**Manila Ondoy 2009 excluded** — Copernicus EMS began operations 2012; no EMSR product exists for this event. Deferred to future work using DFO/MODIS-derived extents.

---

## 2. EMSR Data

### 2.1 Product type

Each EMSR activation ships multiple components (areas of interest, AOIs). We use the **grading** product — a polygon layer with attribute `class`:
- `"Flooded"` — confirmed inundation → **used as observed mask**
- `"Possibly flooded"` — not used (would flatter the model)
- `"Not affected"` — not used

### 2.2 Download and cache

Download URL is hardcoded per event in `EVENTS` dict (direct ZIP from Copernicus EMS portal, no API key required). Cache path: `data/<city>/emsr/<event_id>/<filename>.zip`. ZIP extracted on first run; subsequent runs skip download if the extracted shapefile exists.

### 2.3 Reprojection

EMSR polygons ship in WGS84 (EPSG:4326). Reproject to the city's DEM CRS (e.g. UTM48S for Jakarta) using `fiona` + `shapely.ops.transform` before rasterization.

### 2.4 Rasterization

`rasterio.features.rasterize(shapes, out_shape=dem.shape, transform=dem_transform)` — burns 1 into pixels whose centroid falls inside any `"Flooded"` polygon. Output is a boolean numpy array on the same 30 m grid as the pipeline depth rasters.

---

## 3. Comparison Methodology

### 3.1 Model flood mask

For each `(hazard_type, rp)` candidate, load `outputs/<city>_ssp585_2100/<hazard>/rp_<rp>/<hazard>_depth_SSP5-8.5_2100_rp<rp>.tif`. Pixels with depth ≥ **0.10 m** are predicted flooded; below is dry.

The 0.10 m threshold matches the approximate minimum mappable depth in the EMSR grading schema.

### 3.2 Contingency table (per pixel)

|  | Observed flooded | Observed dry |
|---|---|---|
| **Predicted flooded** | TP | FP |
| **Predicted dry** | FN | TN |

### 3.3 Metrics

| Metric | Formula | Interpretation |
|---|---|---|
| Hit rate **H** | TP / (TP + FN) | Fraction of observed flood captured by model |
| False alarm ratio **FAR** | FP / (TP + FP) | Fraction of predicted flood not observed |
| Critical success index **CSI** | TP / (TP + FP + FN) | Overall skill; 1=perfect, 0=no skill |
| Bias | (TP + FP) / (TP + FN) | >1 over-predicts area; <1 under-predicts |

### 3.4 Best-match RP selection

The script tests all `(hazard_type, rp)` combinations in the configured range and selects the combination with the highest CSI. This is reported as the "best-match return period" and is the basis for the WARN/FAIL gate. All individual results are printed as INFO rows.

### 3.5 Gates

| Verdict | Condition |
|---|---|
| PASS | Best CSI ≥ 0.30 |
| WARN | 0.15 ≤ best CSI < 0.30 |
| FAIL | Best CSI < 0.15 |

Thresholds are informed by published screening-model benchmarks (Sampson et al. 2015 reported CSI 0.4–0.6 for continental-scale LISFLOOD; a bathtub model at 30 m targeting ≥ 0.30 is defensible for a screening application).

---

## 4. CLI

```bash
# Run all configured events (default out-dir = outputs/<city>_ssp585_2100)
python scripts/validate_historical_events.py

# Single event
python scripts/validate_historical_events.py --event EMSR432

# Override output directory
python scripts/validate_historical_events.py --event EMSR530 --out-dir outputs/kuala_lumpur_ssp585_2100
```

Options:
- `--event TEXT` — filter to one EMSR activation ID; default runs all
- `--out-dir PATH` — directory containing `pluvial/rp_*/` and `fluvial/rp_*/` subdirectories; default `outputs/<city>_ssp585_2100`
- `--depth-threshold FLOAT` — flooded threshold in metres; default 0.10
- `--no-download` — skip network fetch (fail if cache missing); useful for offline CI

### Exit codes

| Code | Meaning |
|---|---|
| 0 | All events PASS or WARN |
| 1 | At least one event FAIL |
| 2 | Output directory or cached EMSR data not found |

---

## 5. Output Format

```
========================================================================
Historical event validation: EMSR432 — Jakarta floods Jan 2020
  City       : jakarta
  Source     : https://emergency.copernicus.eu/.../EMSR432_...zip
  Obs. area  : 847.3 km²  (class="Flooded" polygons, 30 m grid)
  Flood thr  : 0.10 m
  RP range   : pluvial RP10–RP200, fluvial RP10–RP200
========================================================================
  Hazard    RP      CSI     H       FAR     Bias   Verdict
  --------  ------  ------  ------  ------  -----  -------
  pluvial   10      0.08    0.09    0.14    0.11   INFO
  pluvial   25      0.18    0.22    0.19    0.27   INFO
  pluvial   50      0.31    0.38    0.17    0.46   INFO
  pluvial   100     0.34    0.41    0.15    0.49   INFO   ← best CSI
  pluvial   200     0.29    0.36    0.21    0.46   INFO
  fluvial   10      0.06    0.07    0.18    0.09   INFO
  fluvial   25      0.11    0.13    0.24    0.17   INFO
  fluvial   50      0.14    0.17    0.22    0.22   INFO
  fluvial   100     0.16    0.20    0.21    0.25   INFO
  fluvial   200     0.15    0.18    0.24    0.24   INFO
------------------------------------------------------------------------
Best match : pluvial RP100  (CSI=0.34, H=0.41, FAR=0.15, Bias=0.49)
  → Verdict: PASS
  → Model captures 41% of observed flood area at RP100 pluvial
  → Model under-predicts total area by ~2× (Bias=0.49)
========================================================================
OVERALL: PASS
```

---

## 6. File Layout

```
scripts/
  validate_historical_events.py     ← new script

data/
  jakarta/
    emsr/
      EMSR432/
        EMSR432_AOI01_DEL_PRODUCT_r1_RTP01_v1.zip   ← cached download
        EMSR432_AOI01_DEL_PRODUCT_r1_RTP01_v1/      ← extracted
          *.shp / *.dbf / *.prj / ...
  kuala_lumpur/
    emsr/
      EMSR530/
        ...
```

No changes to `run_city_pipeline.py`, `run_multihazard.py`, or `cities.py` — this is a standalone validator.

---

## 7. Out of Scope

- Manila Ondoy 2009 — excluded (no EMSR product; deferred to DFO/MODIS source)
- Bangkok 2011, Singapore 2010 Orchard Rd — deferred to future iterations
- Automatic update of confidence ratings in `cities.py` — operator reads the report and updates manually
- Compound hazard validation (surge + rainfall co-occurrence) — separate research question
- Writing a diff raster (`--write-diff-raster`) — deferred; add as a follow-up if QGIS review is needed

---

## 8. Notes on EMSR URL Discovery

The exact component URLs for EMSR432 and EMSR530 must be verified from the Copernicus EMS portal before implementation:
- EMSR432: https://emergency.copernicus.eu/mapping/list-of-components/EMSR432
- EMSR530: https://emergency.copernicus.eu/mapping/list-of-components/EMSR530

The implementation task should include a step to fetch the portal page, identify the grading product ZIP URL for each activation, and hardcode it in the `EVENTS` dict. If the portal page structure has changed, the implementer should fall back to manually downloading the ZIP and documenting the URL.
