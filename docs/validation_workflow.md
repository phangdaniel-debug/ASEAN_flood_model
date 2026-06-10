# Flood Model Validation Workflow

**Status:** Framework defined; event runs not yet executed (gap R4 in replicability audit).  
**Date:** 2026-04-25  
**Objective:** Establish a repeatable, open-data validation process comparing model flood-depth
outputs against documented historical events, using only publicly available sources.

---

## 1. Scope and priority

| Priority | City | Event | Peak depth reference | Source |
|---|---|---|---|---|
| **P0** | Jakarta | 1–2 Jan 2020 (Banjir Besar) | BNPB inundation map; media photo-validation | [BNPB Geoportal](https://gis.bnpb.go.id) |
| **P0** | Jakarta | 17 Jan 2013 (Ciliwung overflow) | BPBD DKI depth contours; Bulletin BNPB No. 3/2013 | BNPB/BPBD |
| **P0** | Kuala Lumpur | 18–19 Dec 2021 (multi-basin) | JPS/DID Malaysia hourly reports; Bernama coverage | [JPS Portal](https://www.water.gov.my) |
| **P1** | Bangkok | Aug–Nov 2011 (Chao Phraya mega-flood) | GISTDA satellite inundation maps; ADPC Red Cross | [GISTDA](https://www.gistda.or.th) |
| **P2** | Manila | 26 Sep 2009 (Typhoon Ondoy/Ketsana) | PAGASA rainfall records; NDRRMC sitreps | NDRRMC/PAGASA |
| **P2** | HCMC | Oct 2019 (king tide + rainfall) | VnExpress photos; MONRE flood bulletins | MONRE Vietnam |

---

## 2. General validation protocol (open, replicable)

### Step 1 — Select historical event and its approximate return period

Choose an event with a documented, publicly cited return period or recurrence description.

**Jakarta 2020 example:**
> BNPB reported the event as a "1-in-50 to 1-in-100 year flood" (Kementerian PUPR, Jan 2020).
> Model RP100 output is the appropriate comparison scenario.

**KL 2021 example:**
> DID Malaysia described the Klang Valley event as "once-in-100-year rainfall intensity"
> (JPS Bulletin 1/2022). Compare against RP100 model output.

### Step 2 — Acquire open reference inundation data

| Source type | Where to obtain | Format |
|---|---|---|
| National disaster agency inundation shapefiles | BNPB (Indonesia), BPBD DKI, NDRRMC (Philippines), GISTDA (Thailand) | SHP / GeoJSON |
| Satellite-derived inundation (SAR) | Copernicus Emergency Management Service (CEMS) Rapid Mapping (<https://emergency.copernicus.eu/mapping>) | SHP (CC-BY) |
| Sentinel-1 SAR backscatter (DIY) | Copernicus Open Access Hub (<https://scihub.copernicus.eu>), free registration | SAFE/GeoTIFF |
| News photo geo-tagging | Social media posts, street-level depth photos (GPS EXIF) | point observations |

**Preferred approach:** Copernicus CEMS Rapid Mapping products are available for all P0-P1 events
(Jakarta 2020 EMSR432, KL 2021 EMSR530, Bangkok 2011 EMSR004).  They are CC-BY-4.0 and
include grading polygons (not flooded / affected / damaged) at 10–30 m resolution.

### Step 3 — Run model at baseline (historical) conditions

Run the pipeline with subsidence correction **disabled** (historical event pre-dates significant
additional subsidence accumulation) and with SSP-neutral baseline hazard levels:

```bash
# Jakarta 2020 — compare against RP100 output
python scripts/run_city_pipeline.py \
    --city jakarta \
    --scenario SSP2-4.5 --horizon 2020 \
    --no-fit-era5 --no-fit-coastal \
    --delta-T 0.0 \
    --out-root outputs/validation_jakarta_2020
```

> `--delta-T 0.0` disables climate scaling so the model represents ~2020 baseline hazard levels.
> `--no-fit-era5 --no-fit-coastal` reuse cached baseline fits to avoid re-downloading data.
>
> **Note (2026-04-27):** `--no-fit-era5` is now equivalent to `--no-fit-pluvial --no-fit-fluvial`. Per-hazard flags `--fit-pluvial/--no-fit-pluvial` and `--fit-fluvial/--no-fit-fluvial` are also available. The fluvial fit is now skipped by default (`--no-fit-fluvial`) to preserve calibrated baseline rows until ERA5-Land migration; pass `--fit-fluvial` only if you intend to refit with MERRA-2 (currently produces unusable stages — see methodology doc §3.1).

### Step 4 — Binary flood-extent comparison (confusion matrix)

Convert both model and reference to a binary wet/dry 30 m raster, then compute:

| Metric | Formula | Target |
|---|---|---|
| **Critical Success Index (CSI / Jaccard)** | TP / (TP + FP + FN) | > 0.40 acceptable, > 0.60 good |
| **False Alarm Ratio (FAR)** | FP / (TP + FP) | < 0.40 |
| **Probability of Detection (POD)** | TP / (TP + FN) | > 0.60 |
| **Bias** | (TP + FP) / (TP + FN) | 0.8–1.2 is unbiased |

**Reference:** Pappenberger et al. (2007), Bates & De Roo (2000) — standard for large-scale
inundation model verification.

```python
# Pseudocode — implement in scripts/validate_flood_event.py (planned)
import numpy as np, rasterio

def confusion_matrix_raster(model_tif: str, reference_shp: str, threshold_m: float = 0.05):
    """
    model_tif    : combined depth raster (max of coastal/fluvial/pluvial)
    reference_shp: Copernicus CEMS or BNPB inundation polygon
    threshold_m  : minimum model depth to count as "flooded" (default 5 cm)
    """
    ...  # rasterize reference onto model grid; apply threshold to model
    TP = np.sum((model_wet) & (ref_wet))
    FP = np.sum((model_wet) & (~ref_wet))
    FN = np.sum((~model_wet) & (ref_wet))
    CSI = TP / (TP + FP + FN)
    return {"CSI": CSI, "FAR": FP / (TP + FP), "POD": TP / (TP + FN)}
```

### Step 5 — Depth comparison at point observations

Where street-level depth photos or gauge readings are available:

1. Extract modelled depth at the GPS/address location.
2. Compare against observed depth (read from photo watermarks, flood-marker photos, or gauge records).
3. Report mean absolute error (MAE) and root-mean-squared error (RMSE) in metres.

**Acceptable thresholds for a screening model:**
- MAE < 0.3 m (within one floor level)
- RMSE < 0.5 m
- No systematic bias > 0.2 m (model consistently over- or under-predicts)

### Step 6 — Document results and flag residuals

Record findings in `docs/validation_results.md` (planned) using the template:

```
## Event: Jakarta Banjir Besar, 1 Jan 2020  
- Model RP compared: RP100 (SSP baseline, delta_T=0)  
- Reference: Copernicus CEMS EMSR432 Grading Map  
- CSI: 0.XX  |  FAR: 0.XX  |  POD: 0.XX  
- Median depth error (n=YY street observations): +/- Z m  
- Key residuals: [district, reason]  
- Conclusion: acceptable / requires recalibration  
```

---

## 3. Known limitations to document in each validation run

| Limitation | Why it matters |
|---|---|
| **Return period mismatch** | Observed event RP is estimated, not precisely known; uncertainty in RP assignment propagates directly into validation |
| **Antecedent soil moisture** | SCS-CN model assumes a fixed initial-abstraction ratio; wet antecedent conditions (Ia = 0.2S) may not match the event day |
| **No upstream basin forcing** | ERA5-fitted fluvial peaks miss upstream basin rainfall for large rivers (Ciliwung, Pasig, Chao Phraya) — expected under-prediction in those reaches |
| **DEM vintage** | Copernicus GLO-30 TanDEM-X 2013 acquisition; subsidence since 2013 not captured unless --subsidence-correction applied |
| **Compound hazard timing** | Model stacks per-driver maxima (not simultaneous); actual joint peak may differ |
| **Drainage infrastructure** | Pumping stations, retention ponds, tide gates not modelled; may inflate false-alarm area near engineered features |

---

## 4. Planned implementation

| Task | Status | Priority |
|---|---|---|
| `scripts/validate_flood_event.py` — binary confusion matrix CLI | Not started | P0 |
| Download Copernicus CEMS EMSR432 (Jakarta 2020) | Not started | P0 |
| Run Jakarta RP50/RP100 baseline validation | Not started | P0 |
| Download CEMS EMSR530 (KL 2021) | Not started | P0 |
| Run KL RP100 baseline validation | Not started | P0 |
| Publish results in `docs/validation_results.md` | Not started | P0 |

---

## 5. References

- Copernicus Emergency Management Service (CEMS) Mapping Products:
  <https://emergency.copernicus.eu/mapping/list-of-activations-rapid>
- BNPB Geoportal (Indonesia): <https://gis.bnpb.go.id>
- JPS/DID Malaysia Water Level & Rainfall: <https://www.water.gov.my>
- PAGASA Philippines: <https://www.pagasa.dost.gov.ph>
- Pappenberger et al. (2007) "Uncertainty in the calibration of effective roughness parameters
  in HEC-RAS using inundation and downstream level observations". *J. Hydrol.* 337:11–23.
- Bates P.D. & De Roo A.P.J. (2000) "A simple raster-based model for flood inundation
  simulation". *J. Hydrol.* 236:54–77.
- Funk C. et al. (2015) "The climate hazards infrared precipitation with stations — a new
  environmental record for monitoring extremes". *Sci. Data* 2:150066.
  doi:10.1038/sdata.2015.66
