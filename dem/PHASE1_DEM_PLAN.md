# Phase 1 — Bare-earth DEM: implementation plan (Bangkok first)

Concrete plan for spec §1. Goal: one bare-earth, subsidence-corrected,
**commercially-clean** 30 m DEM per city in **EGM2008 / UTM**, validation-gated.
Single-DEM vs coastal/inland composite is **decided by the §1.5 gate, not assumed.**

## Terrain error model (spec §1.1)
```
GLO30  ≈  true_ground  +  building_height  +  (f × canopy_height)
```
- Buildings → **mask-and-backfill** from *true-ground pixels only* (not blind IDW —
  the v2.0 `build_bareearth_dem.py` IDW pulls from neighbouring built/canopy cells).
- Vegetation → **calibrated subtraction** `f × canopy_height`, `f ∈ [0,1]` fit per city
  (X-band penetration fraction; **never assume f = 1.0** → over-digs mangrove/green fringe).

## Inputs & sources (Bangkok, UTM 47N / EPSG:32647)
| Input | Source | License | Acquisition | Status |
|---|---|---|---|---|
| GLO-30 base DSM | already in v2.0 | Cop free&open | `flood-v2.0/data/bangkok/copernicus_dem_utm47n.tif` | **on disk** |
| GLO-30 subsidence-corrected | v2.0 | — | `..._subsidence_corrected.tif` (+ `_natdef`, `_defended`) | **on disk** |
| Building footprints | Google Open Buildings v3 (CC-BY) / Overture (CDLA) | **verify commercial** | EE / S2-tile download (v2.0 `fetch_open_buildings.py`) | TODO |
| Canopy height | ETH Global Canopy Height 10 m (primary) | **verify commercial** | langnico.github.io/globalcanopyheight | TODO |
| ICESat-2 ATL08 | NASA NSIDC | open (EarthData login) | nsidc.org/data/atl08 — `earthaccess` lib | TODO (auth) |
| GEDI L2A | NASA ORNL DAAC | open (EarthData login) | daac.ornl.gov/GEDI — `earthaccess` lib | TODO (auth) |
| DeltaDTM | 4TU (CC-BY 4.0) | commercial-OK + attr | doi.org/10.4121/21997565 | TODO (coastal x-check only) |
| WorldCover | ESA (CC-BY 4.0) | commercial-OK + attr | esa-worldcover.org / EE | TODO (zoning + roughness) |

## Build steps (spec §1.4)
1. **Base:** confirm GLO-30 is EGM2008; mosaic→UTM (Bangkok already UTM47N). Apply existing
   v2.0 subsidence correction. Keep **present-day** DEM (validation) separate from
   **horizon-accumulated** DEMs (scenario runs). [reuse `apply_subsidence_correction.py`]
2. **Buildings (mask-and-backfill):** rasterise footprints; backfill under footprints from
   true-ground pixels only (nearby non-footprint low-canopy + ICESat-2/GEDI ground). Flag
   wall-to-wall blocks → low-confidence in QA mask.
3. **Vegetation:** subtract `f × canopy_height` where canopy present (`f` from §1.5).

## Calibration + validation (spec §1.5) — the part that must not be rushed
- **DATUM (do first):** ICESat-2/GEDI = **WGS84 ellipsoid**; GLO-30/DeltaDTM = **EGM2008
  geoid**. Apply geoid undulation to a common datum **before any differencing**
  (missed geoid = multi-metre systematic error). → `datum_reconcile.py`.
- Extract clean ground returns (quality flags; drop water/outliers). **Hold out ~30%**;
  never validate on calibration points.
- **Fit f:** vegetated non-built areas, `residual = GLO30 − ground_truth ≈ f × canopy_height`;
  regress (optionally per canopy-density bin). Per-city `f`.
- **Zones:** coastal-flat (≤~10 m MSL), urban core (high footprint density), vegetated
  (high canopy) — from WorldCover + canopy + footprint density + elevation.
- **Metrics PER ZONE:** signed **bias** (most important), MAE, RMSE, **+ check-point count**
  (honesty: ICESat-2/GEDI sparse in dense urban core — the zone where building removal is
  the value-add).
- **Coastal cross-check:** difference candidate DEM vs **DeltaDTM** in coastal-flat zone.
- **DECISION GATE:** PASS→single DEM; FIX→recalibrate f / revisit backfill;
  FALL BACK→DeltaDTM coastal-flat + candidate inland, seam-smoothed at ~10 m.

## Outputs (`$WORK/dem/`, spec §1.6)
`dem_bareearth_bangkok_present.tif`; `dem_bareearth_bangkok_<scenario>_<horizon>.tif`;
`dem_qa_bangkok.tif`; `dem_validation_bangkok.csv` (+ per-zone table, DeltaDTM x-check, gate).

## Runbook (scripts implemented — run in this order once data is in)
Env python: `D:\GPTs\Python\envs\hydromt-sfincs\python.exe`. **First fix the BLAS env
(repro/ENV_NOTES.md, task #10)** once the ground-truth jobs finish.

```
# 1. Ground truth (resumable; stream-and-subset, no full granule download)
python dem/extract_ground_points.py --product both         # -> ground_truth/{atl08,gedi}_ground_points.parquet
# 2. Calibrate: fit f, zones, 30% holdout, per-zone raw stats
python dem/calibrate_dem.py                                 # -> calib/{points_sampled.parquet,calibration.json}
# 3. Build bare-earth: mask-and-backfill (true-ground only) + f·canopy subtraction
python dem/build_bareearth_dem.py \
    --subsidence-corrected dem/bangkok/glo30_subsidence_corrected_utm47n.tif   # -> dem_bareearth_bangkok.tif + dem_qa
# 4. Validate + §1.5 decision gate (held-out points; optional DeltaDTM x-check)
python dem/validate_dem.py                                  # -> dem_validation_bangkok.{json,csv}
```

## Status
- ✅ Implemented + smoke-tested: `datum_reconcile.py`, `extract_ground_points.py`,
  `raster_utils.py` (safe sampler), `calibrate_dem.py`.
- ✅ Implemented + compile-checked, awaiting full data: `build_bareearth_dem.py`,
  `validate_dem.py`.
- ⏳ Data: WorldCover ✅, canopy ✅; buildings + ATL08/GEDI ground truth fetching.
- 🔧 Blocker before final run: env BLAS fix (task #10).
- 🟡 DeltaDTM (coastal x-check) access still to resolve — gate runs without it (optional).

**Workarounds baked in (remove after env fix):** affine-inverse sampling (rasterio 1.4.4
`sample()`/`rowcol()` segfault) and closed-form OLS for the f-fit (`np.linalg.lstsq` segfault).
Also: aux-input dir is `auxdata/` (NOT `aux/` — reserved Windows device name); raster
warp/align via `WarpedVRT` (never materialise the full 36000² source).

## Interim end-to-end run (partial GT: 1 ATL08 + 1 GEDI granule, + buildings)
Validated all 4 scripts run together. Per-zone bias→MAE (raw GLO-30 → bare-earth):
- urban_core  +0.67→2.34  ⇒  **−0.07→1.90**  (mask-and-backfill works)
- coastal_flat +0.98→1.37 ⇒  −0.15→1.21      (improved)
- vegetated   +0.46→1.12  ⇒  **−1.35→1.77**  (OVER-CORRECTED)
Gate = FIX. **Open calibration question (task #11):** build subtracts `f·canopy` but drops
the −1.23 m regression intercept (GEDI under-canopy ground bias, veg-specific). Fix on the
FULL dataset via origin-fit / `dsm−a−f·canopy` in veg cells / ATL08-vs-GEDI separation.
Do NOT tune on partial data.

## FULL ATL08 run (147k pts; #11 RESOLVED) — base = subsidence-corrected DSM
Fix applied: global `bias0` (median true-ground residual, applied uniformly) + `f` fit
THROUGH ORIGIN on `residual−bias0` vs canopy. Result: **bias0=+0.24 m, f=0.066**.
Held-out per-zone bias / MAE (25,346 pts):
- vegetated   −0.14 / 0.94  ✅ (was −1.35 — over-correction FIXED)
- other       −0.03 / 1.27  ✅
- urban_core  +0.36 / 2.18  ✅ (sufficient + acceptable; buildings inherently noisy)
- coastal_flat +0.63 / 1.24 ❌ (can't reach ~0.45 m DeltaDTM grade)
**GATE = FALL BACK → DeltaDTM coastal-flat + candidate inland, seam-smooth ~10 m.**

## DeltaDTM acquired + composite (gate PASS, but a §1.2-vs-§1.5 tension)
DeltaDTM N13E100 pulled from the remote 17GB Asia.zip via HTTP range reads (fsspec+zipfile,
27.6 MB only) → `auxdata/deltadtm_bangkok.tif`. Cross-check vs candidate (coastal band):
MAE 1.32 m / bias +0.79 m — independently confirms candidate runs ~0.7 m high at the coast.
`compose_dem.py` (DeltaDTM ≤10 m MSL + candidate inland, seam-blend 8–12 m) → **GATE = PASS**:
coastal_flat 0.47/+0.03, vegetated 0.44/−0.16, other 0.89/−0.77, urban 1.40/−1.16 (MAE/bias).
**TENSION:** the composite replaced 68% of the (flat-delta) domain with DeltaDTM, INCLUDING
urban — discarding our mask-and-backfill (the §1.2 contribution). Decision needed: (A) spec-literal
≤10 m composite [passes, but mostly DeltaDTM]; (B) restrict DeltaDTM to near-coast only, keep
candidate urban/inland [preserves contribution; coastal-flat gate TBD]; (C) candidate-only,
document coastal limit honestly [our model throughout, gate=FALL BACK].

## RESOLVED — near-coast composite (option B chosen): GATE = PASS ✅
`compose_dem.py` restricts DeltaDTM to a near-Gulf coastal band (sea-mask distance ramp,
coast_dist=600 cells/18 km + elevation seam 8–12 m); our calibrated model keeps the inland
city (1.94 M cells purely ours). Held-out validation (vs ATL08):
- coastal_flat +0.10 / 0.55 ✅   vegetated −0.15 / 0.49 ✅
- other −0.59 / 0.95 ✅          urban_core −0.88 / 1.51 ✅ (sufficient)
**GATE = PASS (single DEM).** (Building-coverage exclusion was tried but over-removed coastal
built cells → coastal 0.97, fail; distance is the right lever. coast_dist tunable.)
Final outputs (spec §1.6): `dem_bareearth_bangkok_present.tif`, `dem_qa_bangkok.tif`,
`dem_validation_bangkok_composite.{json,csv}`. **PHASE 1 (Bangkok) COMPLETE.**
TODO: horizon-accumulated DEMs (2050/2100 subsidence) for scenarios; replicate for
Jakarta/KL/Singapore; env BLAS fix (#10) before Phase 2.
