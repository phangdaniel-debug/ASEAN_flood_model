# Bare-earth DEM — Handoff: building the v3.0 DEM for the other cities

**Purpose.** Reproduce the Bangkok v3.0 bare-earth DEM pipeline for **Jakarta (ID), Kuala
Lumpur (MY), Singapore (SG)**. The deliverable for each city is a single conditioned
bare-earth raster, **EGM2008 orthometric / UTM, 30 m**, that drops straight into the v2.0
flood model in place of its GLO-30 DSM terrain.

> Why this matters: against held-out ICESat-2, the Bangkok v3.0 bare-earth halves DEM error
> vs the v2.0 GLO-30 DSM (overall MAE 0.74 m vs 1.35 m) and removes the DSM's +0.75 m
> building/canopy high-bias (v3.0 bias −0.30 m). Each new city repeats the same build +
> calibration + gate to earn that same improvement. **Calibration is per-city — never reuse
> Bangkok's `f`/`bias0`.**

---

## 0. The drop-in deliverable (what v2.0 consumes)

| | |
|---|---|
| **File** | `dem/<city>/dem_bareearth_<city>_present_conditioned.tif` |
| **CRS / datum** | UTM (city zone) / **EGM2008** — same frame as v2.0's `glo30_subsidence_corrected_*` terrain |
| **Resolution / grid** | 30 m, **built on v2.0's existing GLO-30 grid for that city** so extent/transform match (drop-in, no resampling in v2.0) |
| **v2.0 swap point** | v2.0 reads `glo30_subsidence_corrected_<utm>.tif`. Point its terrain input at the conditioned bare-earth instead (or overwrite a copy). Both are EGM2008/UTM/30 m → no other change needed. |

The Bangkok reference deliverable is `dem/bangkok/dem_bareearth_bangkok_present_conditioned.tif`.

---

## 1. Environment — the one rule that breaks everything

Run **inside the activated conda env**. Calling the env's `python.exe` directly loads a
foreign BLAS DLL and crashes (`0xC06D007F`, surfaces as exit 127 / "no output"). This was the
root cause of every "segfault" in development.

```powershell
# Option A (recommended — clean streaming output):
$E="D:\GPTs\Python\envs\sfincs"
$env:PATH="$E\Library\bin;$E;$E\Scripts;"+$env:PATH
$env:GDAL_DATA="$E\Library\share\gdal"; $env:PROJ_DATA="$E\Library\share\proj"
python dem\<script>.py ...

# Option B:
mamba run -n sfincs python dem\<script>.py ...
```

- Conda root: `D:\GPTs\Python` (Miniforge). Envs: `sfincs` (preferred; has osmnx) or
  `hydromt-sfincs`. Recreate from `repro/environment_sfincs.yml`.
- **EarthData auth** (for ground truth): `earthaccess` netrc strategy. Windows gotcha — it
  reads `C:\Users\Daniel\_netrc` (**underscore**), not `.netrc`. Keep both in sync.
- **Never** name a dir/file `aux` (reserved Windows device). Aux inputs live in `auxdata/`.
- Raster warp/align goes through `WarpedVRT` (`dem/raster_utils.py`) — never materialise the
  full source. `rasterio.merge()` crashes natively in this env; extract single tiles instead.

---

## 2. The pipeline (scripts, in order)

All in `dem/`. Each is CLI-driven with `--`-args that default to Bangkok paths — **override
the paths per city**. The error model throughout:

```
GLO30_DSM  ≈  true_ground  +  building_height  +  f·canopy_height
```

| Step | Script | Does | Key outputs |
|---|---|---|---|
| **0. Datum** | `datum_reconcile.py` | WGS84-ellipsoid (lidar) ↔ EGM2008 (DEM) via PROJ EGM2008 grid. **Used internally by steps 1–2; the critical first correction.** | (library) |
| **1. Ground truth** | `extract_ground_points.py` | Stream-and-subset ATL08 + GEDI over the city bbox (HTTP range reads, no full granule DL), QC, reconcile to EGM2008 | `ground_truth/{atl08,gedi}_ground_points.parquet` |
| **2. Calibrate** | `calibrate_dem.py` | Fit `bias0` (median true-ground residual) + `f` (origin-fit on vegetated), assign zones, hold out 30% | `calib/points_sampled.parquet`, `calib/calibration.json` |
| **3. Build** | `build_bareearth_dem.py` | Subtract `bias0`; subtract `f·canopy`; mask buildings & backfill from **true-ground only**; optional subsidence delta → present-day | `dem_bareearth_<city>.tif`, `dem_qa_<city>.tif` |
| **4. Validate + gate** | `validate_dem.py` | Per-zone bias/MAE/RMSE on **held-out** points; DeltaDTM coastal x-check; §1.5 verdict | `dem_validation_<city>.{json,csv}` |
| **5. Compose** *(if gate = FALL BACK)* | `compose_dem.py` | Blend DeltaDTM near-coast + our model inland (distance-from-sea ramp, elevation seam 8–12 m, keep our building cells) | `dem_bareearth_<city>_composite.tif` |
| **6. Condition** | `condition_dem.py` | De-spike GLO-30 radar artefacts (7×7 median fill >5 m below local) + clamp land floor → SFINCS/v2.0-safe | `dem_bareearth_<city>_present_conditioned.tif` |

DeltaDTM tile pull (single tile from the remote 17 GB Asia.zip via HTTP range): adapt
`extract_deltadtm.py` — change `TILE` to the city's 1° tile and `OUT`.

### Bangkok-calibrated reference values (do NOT reuse — refit per city)
`bias0 = +0.24 m`, `f = 0.066`. Build thresholds that carried over fine: build-mask
`bcov>0.25`, true-ground `bcov<0.05 & canopy<2 m`, canopy-correct only where `canopy>1 m`.

---

## 3. Per-city inputs

For each city, gather the same six input families. Tiles are named by SW corner; **the city
bbox must sit inside the listed tile(s) — verify before download** (Bangkok fit entirely in
one 3° tile, N12E099; larger cities may straddle two — fetch neighbours and mosaic).

| Family | Source | License (commercial) | Notes |
|---|---|---|---|
| **GLO-30 DSM (raw + subsidence-corrected)** | Copernicus / **already in v2.0** per city | Cop free & open ✅ | Base surface. Build on v2.0's existing UTM grid. Subsidence correction is **city-specific** — reuse v2.0's `apply_subsidence_correction.py` output (`flood-v2.0/data/<city>/...`). |
| **ICESat-2 ATL08** | NASA NSIDC via `earthaccess` | open (login) ✅ | Cleaner terrain; **primary for the `f`-fit**. |
| **GEDI L2A** | NASA ORNL via `earthaccess` | open (login) ✅ | Under-canopy-biased; supplementary. |
| **ETH Global Canopy Height 10 m (2020)** | repo doi 10.3929/ethz-b-000609802 (3° COG tiles) | project states open — confirm string | 3° tiles, SW-corner names. |
| **Google Open Buildings v3** | GCS `open-buildings-data/v3/...` (v2.0 `fetch_open_buildings.py`) | CC-BY 4.0 ✅ + attr | → `building_coverage_<utm>.tif` (fractional coverage on DEM grid). |
| **ESA WorldCover 2021 v200** | `esa-worldcover.s3 v200/2021/map/` (3° tiles) | CC-BY 4.0 ✅ + attr | zoning + later roughness. |
| **DeltaDTM v1.1** | 4TU doi 10.4121/21997565 (Asia.zip, range reads) | CC-BY 4.0 ✅ + attr | coastal x-check / FALL-BACK compose only. 1° tiles. |

> **License guardrails (from the spec, must hold):** FABDEM is **excluded** (CC-BY-NC-SA,
> non-commercial). Everything above is commercial-clean with attribution. Do not publish any
> OSM-derived burned DEM / network as a database (ODbL) — OSM is process-input only.

### City parameters — starting estimates (verify each against the actual data bbox)

| City | UTM (EPSG) | ~Centre lon/lat | ETH/WorldCover 3° tile (SW corner) | DeltaDTM 1° tile | Subsidence |
|---|---|---|---|---|---|
| **Jakarta** | 48S (32748) | 106.85°E, 6.2°S | **S09E105** | **S07E106** | **Severe** — dominant signal; get the best local subsidence rate v2.0 used. |
| **Kuala Lumpur** | 47N (32647) | 101.69°E, 3.14°N | **N03E099** | **N03E101** | Minimal (hilly inland) — subsidence delta ≈ 0. |
| **Singapore** | 48N (32648) | 103.82°E, 1.35°N | **N00E102** | **N01E103** | Minimal. |

Tile-name rule (how Bangkok's N12E099 / N13E100 were derived): floor the bbox SW corner to the
tile grid (3° for ETH/WorldCover, 1° for DeltaDTM); S/N and E/W from the hemisphere. **Confirm
by listing the zip / checking bounds before committing** — Jakarta's southern-hemisphere `S`
tiles especially.

---

## 4. Calibration & the decision gate (do not rush — spec §1.5)

1. **Datum first.** ATL08/GEDI are WGS84-ellipsoid; GLO-30/DeltaDTM are EGM2008. Reconcile
   before *any* differencing — a missed geoid is a multi-metre systematic error. (Bangkok
   undulation N ≈ −31.4 m; each city differs — `datum_reconcile.geoid_undulation(lon,lat)`.)
2. **Hold out 30%, seeded.** Never validate on calibration points.
3. **`bias0`** = median residual on true-ground (non-built, low-canopy) calib points — applied
   uniformly so the canopy term only handles the canopy-correlated part. (This split fixed the
   vegetated over-correction; don't fold the flat offset into `f`.)
4. **`f`** = origin-fit `(c·r).sum()/(c·c).sum()` on vegetated calib points, clipped [0,1].
5. **Zones:** coastal_flat (≤ ~2 m EGM2008), urban_core (bcov>0.25), vegetated
   (canopy>3 m & bcov<0.05), other.
6. **Per-zone bias / MAE / RMSE + check-point count.** Report the **urban-core point count
   prominently** — lidar is sparsest exactly where building removal is the value-add (honesty
   metric). Sparse urban → PASS-WITH-CAVEAT, not silent pass.

**Gate (validate_dem.py):**
- **PASS** → ship the single DEM (→ step 6 condition).
- **FALL BACK** (coastal can't reach DeltaDTM grade, as Bangkok) → run `compose_dem.py`
  (near-coast DeltaDTM + our inland), re-validate, then condition. Bangkok chose **option B**:
  DeltaDTM only in a near-Gulf band (`coast-dist-cells`), our calibrated model keeps the whole
  inland city — preserves the building-removal contribution. Tune `coast-dist-cells` per city.
- **FIX** → recalibrate `f` / revisit backfill thresholds; do not proceed.

Bangkok final held-out (PASS via near-coast composite), for sanity comparison:
coastal_flat 0.55/+0.10, vegetated 0.49/−0.15, other 0.95/−0.59, urban_core 1.51/−0.88 (MAE/bias m).

---

## 5. Per-city runbook (copy, set `<city>` + paths)

```powershell
# activate env (section 1) first
$C="jakarta"   # jakarta | kl | singapore
$B="D:\GPTs\Projects\flood-v3.0\dem\$C"

# 1. ground truth (resumable; one part-parquet per granule)
python dem\extract_ground_points.py --dem $B\glo30_dsm_<utm>.tif --outdir $B\ground_truth --product both
# 2. calibrate (per-city f + bias0; 30% holdout)
python dem\calibrate_dem.py --gt-dir $B\ground_truth --glo30 $B\glo30_dsm_<utm>.tif `
    --canopy $B\auxdata\ETH_..._<tile>.tif --bcov $B\auxdata\building_coverage_<utm>.tif `
    --worldcover $B\auxdata\worldcover_2021_<tile>.tif --out $B\calib
# 3. build bare-earth (+ optional subsidence delta for present-day)
python dem\build_bareearth_dem.py --glo30 $B\glo30_dsm_<utm>.tif --canopy ... --bcov ... `
    --worldcover ... --calibration $B\calib\calibration.json `
    --subsidence-corrected $B\glo30_subsidence_corrected_<utm>.tif `
    --out $B\dem_bareearth_$C.tif --qa-out $B\dem_qa_$C.tif
# 4. validate + gate
python dem\validate_dem.py --bareearth $B\dem_bareearth_$C.tif --points $B\calib\points_sampled.parquet `
    --deltadtm $B\auxdata\deltadtm_$C.tif --out $B\dem_validation_$C
# 5. compose — ONLY if gate = FALL BACK
python dem\compose_dem.py --bareearth $B\dem_bareearth_$C.tif --deltadtm $B\auxdata\deltadtm_$C.tif `
    --qa $B\dem_qa_$C.tif --out $B\dem_bareearth_${C}_composite.tif --sea-mask <v2.0 sea mask>
# 6. condition (--in = the gate-PASS DEM, single or composite)
python dem\condition_dem.py --in $B\dem_bareearth_$C.tif `
    --out $B\dem_bareearth_${C}_present_conditioned.tif
```

Then point the v2.0 model's terrain input at `dem_bareearth_<city>_present_conditioned.tif`.

---

## 6. Gotchas (all hit during Bangkok)

- **Activate the env** (§1) — the #1 cause of crashes.
- `condition_dem.py` now takes `--in`/`--out` (defaults to Bangkok); spike/floor knobs are
  `--win`/`--rel-thresh`/`--land-floor` if a city's artefacts differ.
- ETH canopy nodata = 255 (clamp). Open-buildings = fractional coverage on the DEM grid.
- WorldCover classes used: 10/20/30/40/90/95 veg, 50 built, 80 water.
- Build on v2.0's **existing UTM grid** per city so the output is drop-in (matching
  transform/extent/30 m).
- `region`/bbox derivations must be lon/lat (EPSG:4326) — UTM coords give a garbage zone.
- DeltaDTM clips to ~10 m MSL (coastal only) and is 1° tiles; `extract_deltadtm.py` reads one
  tile from the remote zip without downloading 17 GB.
- Honesty: pluvial/coastal *model* skill is a separate question — this handoff is about the
  **terrain**, which is the validated, unambiguous v3.0 win.

---

## 7. Cross-references

- Plan & full Bangkok results: `dem/PHASE1_DEM_PLAN.md`
- v3.0-vs-v2.0 DEM score: `dem/dem_compare.py`
- Aux provenance/license/attribution strings: `dem/bangkok/auxdata/README.md`
- Env root-cause + run pattern: `repro/ENV_NOTES.md`
- Spec source of truth: `SFINCS_MASTER_SPEC.md` (§1)
- Persistent notes: `~/.claude/.../memory/flood-v3-deployment.md`
</content>
</invoke>
