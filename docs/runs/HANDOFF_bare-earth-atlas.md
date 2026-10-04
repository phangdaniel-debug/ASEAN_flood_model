# Handoff — make the bare-earth DEM the sole terrain for the SAFE/IEEE flood atlas

**Date:** 2026-06-17
**For:** a fresh model session driving `D:\GPTs\Projects\flood-v3.0` (DEM pipeline) +
`D:\GPTs\Projects\flood-v2.0` (flood model + validation).
**Goal:** the SAFE paper (`flood-v2.0/docs/paper/v2/safe2026-v4.tex`) currently reports a
GLO-30 **DSM** atlas with a separate bare-earth *comparison*. The author wants the **bare-earth
to be the single reported terrain** (drop the two-DEM comparison). The terrain blocker
(Singapore) is now solved (this handoff). What remains is a **re-analysis**: re-run validation,
the SSP5-8.5/2100 extent table, and the bathtub→inertial coastal analysis on bare-earth for all
four cities, then rewrite the paper's results on those numbers.

> **Read first:** `flood-v2.0/docs/superpowers/runs/2026-06-17-v3dem-cross-city.md`
> (the controlled present-day A/B + per-city findings) and `...-v3dem-bangkok-pumped-polder.md`
> (Bangkok de-bias + pumped-polder). This file is the operational checklist; those are the why.

---

## 0. The decisive caveats — read before running anything

1. **Bathtub bias WIDENS on bare-earth — do not claim bare-earth fixes it.** Removing buildings
   exposes more connected low land, so a *bathtub* on bare-earth floods MORE than on the DSM, and
   inertial-coastal extents grow too (Bangkok bare-earth inertial ≈862 km² vs DSM inertial 283).
   The bathtub→inertial contribution is a SOLVER artifact (steady-state vs dynamic), independent
   of terrain, and bare-earth makes the inertial solver *more* necessary. Reframe accordingly;
   the old "DSM buildings drive the over-prediction" wording is backwards.
2. **Defended/pumped deltas need pump physics on bare-earth.** Bangkok's accurate low terrain
   leaks coastal water into the bunded/pumped CBD; it only behaves once the documented
   pumped-polder floor is applied (`scripts/apply_pumped_polder.py`). Jakarta's pumped districts
   genuinely flood (rob) and must stay wet — no polder there.
3. **Singapore terrain = DeltaDTM, NOT ICESat-2.** ICESat-2/GEDI cannot validate dense, reclaimed
   SG (ATL08 ground is building/canopy-contaminated; DeltaDTM, validated ~0.45 m globally,
   disagrees with ATL08 by ~2 m → the lidar is the noisy reference). SG bare-earth is DeltaDTM
   where covered (all flood-relevant terrain ≤30 m) + ICESat-2 fill for the non-flood interior.
4. **Per-city calibration is never reused.** f/bias0 are per city (`flood-v3.0/dem/<city>/calib*/
   calibration.json`). All four cities use **ETH 10 m canopy** (KL harmonised from Meta CHM —
   invariance-tested; see cross-city dossier §4a).
5. **Cardinal rule:** flooded dry-controls and missed positives STAY in every register; never
   relabel to pass.
6. **Bangkok fluvial stage = 0.5245 m (RP100 relative overbank), NOT 6.46 m.** The committed
   `data/bangkok/hazard_levels_*.csv` value is the relative overbank for the HAND method (as for
   Jakarta/KL). An earlier v3 run used the *absolute* BCP mainstem stage 6.46 m through HAND →
   856 km² at 5.78 m median depth (a bug, fixed 2026-06-18). Corrected fluvial = 491 km² at
   ≤0.52 m; corrected gate HR 0.44 / CRR 1.00 / TSS 0.44 (run `bangkok_fix_polder_ssp585_2020/`).
   HR is bounded by the out-of-domain Chao-Phraya 2011 districts (limitation #22); single-stage
   HAND cannot reach them — the documented intended fix is hydrodynamic mainstem routing
   (`2026-06-06-bangkok-mainstem-hand-viability.md`), not yet implemented.

---

## 1. Environment — two interpreters, do not cross them

- **flood-v2.0 model / HAND / run_multihazard / validate_hotspots** → Python 3.14:
  `C:\Users\Daniel\AppData\Local\Python\pythoncore-3.14-64\python.exe` (has pysheds 0.5 + full stack).
- **flood-v3.0 DEM build (calibrate/build/validate/condition/compose)** → `sfincs` conda env,
  env-PATH method (NO `mamba`, NO bare env python — foreign-BLAS crash):
  ```powershell
  $E="D:\GPTs\Python\envs\sfincs"; $env:PATH="$E\Library\bin;$E;$E\Scripts;"+$env:PATH
  $env:GDAL_DATA="$E\Library\share\gdal"; $env:PROJ_DATA="$E\Library\share\proj"
  python dem\<script>.py ...
  ```

---

## 2. Bare-earth DEM inventory (all EGM2008 / UTM / 30 m, drop-in for v2.0 terrain)

| City | Adopted bare-earth (present, conditioned) | Provenance | Gate / caveat |
|---|---|---|---|
| Bangkok | `flood-v3.0/dem/bangkok/dem_bareearth_bangkok_present_conditioned.tif` **+ de-bias + polder** (see §5) | ICESat-2-calib GLO-30 | urban −0.88 m → CBD de-bias required; pumped-polder floor required |
| Jakarta | `flood-v3.0/dem/jakarta/dem_bareearth_jakarta_present_conditioned.tif` | ICESat-2-calib GLO-30 | PASS (urban +0.25 m); no fixes |
| Kuala Lumpur | `flood-v3.0/dem/kl/dem_bareearth_kl_eth_present_conditioned.tif` | ICESat-2-calib GLO-30, **ETH canopy** | urban +0.18 m ok; inland MAE/coastal-zone FIX is spurious (KL inland) |
| **Singapore** | `flood-v3.0/dem/singapore/dem_bareearth_singapore_present_conditioned.tif` | **DeltaDTM** + ICESat-2 fill | DeltaDTM authoritative ≤30 m (flood-relevant); high interior approximate, non-flood |

Deprecated/aux: SG ICESat-2 build is preserved as
`dem_bareearth_singapore_icesat2_present_conditioned_DEPRECATED.tif` (failed accuracy gate —
keep for the methods note, do NOT use for flooding). KL Meta-CHM build retained as the §4a
invariance control (`dem_bareearth_kl_present_conditioned.tif`).

Per-city calibration (never reuse): BKK f=0.066/b0=+0.24; JKT f=0.102/b0=+0.585;
KL(ETH) f=0.184/b0=+1.454; SG = DeltaDTM (no f). Bangkok held-out: MAE 1.35→0.74 m,
bias +0.75→−0.30 m vs DSM.

## 3. HAND inputs already built on bare-earth terrain (in `outputs_v3dem/_dem/`)

Method: reuse the v2 drainage-channel network (cells where v2 HAND≈0) and recompute HAND on the
bare-earth terrain — isolates the terrain change. Script: `flood-v2.0/scripts/_build_v3_hand.py`.

| City | HAND raster | from v2 network |
|---|---|---|
| Jakarta | `jakarta_hand_v3.tif` | dense single-stage `hand_utm48s.tif` |
| KL | `kl_hand_mainstem_v3eth.tif` | main-stem `hand_mainstem_utm47n.tif` |
| Bangkok | `hand_trunk_v3_debiased.tif` | trunk (built on the de-biased DEM) |
| Singapore | `singapore_hand_v3_deltadtm.tif` | `hand_utm48n.tif` (median 2.31 m vs DSM 5.98) |

KL also has `kl_raingrid_v3eth.tif` (drain-burn transferred onto the ETH bare-earth, for the
raingrid pluvial). Bangkok DEM/defence artifacts: `outputs_v3dem/_dem/bangkok_v3_debiased_defended.tif`,
`bangkok_pumped_polder_mask.tif`.

## 4. Present-day controlled-A/B results already obtained (for reference)

| City | DSM TSS (same-engine) | bare-earth TSS | note |
|---|---|---|---|
| Jakarta | 0.39 | **0.57** | raw win |
| Bangkok | 0.42 | **0.44** | de-bias + polder (corrected fluvial 0.5245 m; HR out-of-domain-bounded). The earlier 0.56 used a buggy 6.46 m mainstem stage via HAND — see §0.6. |
| KL | 0.35 | **0.59** | fluvial (ETH); CRR 1.00; recovers Old Klang Rd |
| Singapore | (DSM 0.47, flood-atlas-era) | **TODO** | run on DeltaDTM bare-earth (§6.1) |

## 5. Flood-run commands (present-day; switch `--hazard-levels` to the 2100 CSV for the atlas)

Run with the **pythoncore-3.14** python from `flood-v2.0/`. RP100-only CSVs are in
`outputs_v3dem/_<city>_rp100.csv`; for 2100 use `data/<city>/hazard_levels_ssp585_2100.csv`
(or build an RP100-only slice). Score with
`scripts/validate_hotspots.py --city <city> --out-dir <dir> --rp 100`.

**Jakarta** (`--no-clamp-negative-land`; inertial coastal):
```
run_multihazard.py --dem flood-v3.0/dem/jakarta/dem_bareearth_jakarta_present_conditioned.tif
  --hazard-levels <jakarta csv> --scenario SSP5-8.5 --horizon <2020|2100>
  --out-dir outputs_v3dem/jakarta_<...> --fluvial-hand-raster outputs_v3dem/_dem/jakarta_hand_v3.tif
  --sea-mask-raster data/jakarta/sea_mask_utm48s.tif --tidal-channel-raster data/jakarta/river_mask_utm48s.tif
  --tidal-burn-elevation 2.0 --coastal-solver inertial --coastal-msl-egm2008 0.9976
  --pluvial-model fillspill --pluvial-depth-cap 3.0 --runoff-coeff 0.80
  --runoff-coeff-raster data/jakarta/runoff_coeff_utm48s.tif --fluvial-bankfull-rp 0 --no-clamp-negative-land
```

**Kuala Lumpur** (inland; raingrid pluvial; no coastal):
```
run_multihazard.py --dem flood-v3.0/dem/kl/dem_bareearth_kl_eth_present_conditioned.tif
  --hazard-levels <kl csv> --scenario SSP5-8.5 --horizon <...> --out-dir outputs_v3dem/kl_<...>
  --only-hazard-types fluvial,pluvial --fluvial-hand-raster outputs_v3dem/_dem/kl_hand_mainstem_v3eth.tif
  --fluvial-bankfull-rp 0 --pluvial-model raingrid --pluvial-dem-raster outputs_v3dem/_dem/kl_raingrid_v3eth.tif
  --pluvial-depth-cap 3.0 --tidal-channel-raster data/kuala_lumpur/drainage_waterways_utm47n.tif
  --runoff-coeff-raster data/kuala_lumpur/runoff_coeff_utm47n.tif --runoff-coeff 0.75 --raingrid-workers 0
```
> KL caveat: under the corrected dT=0 present-day forcing, KL pluvial net-excess is tiny
> (RP100 0.095 m) → pluvial ≈0 for both DEMs; KL's present-day gain is fluvial. At 2100 the
> pluvial forcing is larger, so re-check.

**Bangkok** (de-biased DEM + defences + pumped-polder post-process):
```
run_multihazard.py --dem outputs_v3dem/_dem/bangkok_v3_debiased_defended.tif
  --hazard-levels <bangkok csv> --scenario SSP5-8.5 --horizon <...> --out-dir outputs_v3dem/bangkok_<...>
  --fluvial-hand-raster outputs_v3dem/_dem/hand_trunk_v3_debiased.tif --fluvial-bankfull-rp 0
  --sea-mask-raster data/bangkok/sea_mask_utm47n.tif --tidal-channel-raster data/bangkok/river_mask_utm47n.tif
  --tidal-burn-elevation 2.0 --coastal-solver inertial --coastal-msl-egm2008 <bkk msl>
  --pluvial-model fillspill --pluvial-depth-cap 3.0 --runoff-coeff 0.80 ...
# then drain the pumped CBD:
apply_pumped_polder.py --city bangkok --src-dir outputs_v3dem/bangkok_<...> --out-dir <...>_polder --rp 100
# score the _polder dir.  (Verify bkk msl / mask paths against data/bangkok/.)
```

**Singapore** (NEW — build HAND already done; mirror the v2 SG config; run BOTH arms):
```
# v3 (bare-earth):
run_multihazard.py --dem flood-v3.0/dem/singapore/dem_bareearth_singapore_present_conditioned.tif
  --hazard-levels <sg csv> --scenario SSP5-8.5 --horizon <...> --out-dir outputs_v3dem/singapore_<...>
  --fluvial-hand-raster outputs_v3dem/_dem/singapore_hand_v3_deltadtm.tif
  --sea-mask-raster data/singapore/sea_mask_utm48n.tif --tidal-channel-raster data/singapore/river_mask_utm48n.tif
  --tidal-burn-elevation 2.0 --coastal-solver inertial --pluvial-model fillspill --pluvial-depth-cap 3.0
  --runoff-coeff 0.75 --runoff-coeff-raster data/singapore/runoff_coeff_utm48n.tif
# v2 control (same config, DSM terrain + v2 hand_utm48n.tif) for the apples-to-apples baseline,
#   because the vendored SG gate (0.82/0.65/0.47) is flood-atlas-era, not current-engine.
# Score both with validate scripts; SG uses scripts/_score_singapore_hotspot_v2.py OR
#   validate_hotspots.py --city singapore (confirm which register the paper cites).
```

## 6. Remaining tasks (ordered)

1. **Singapore present-day gate on the DeltaDTM bare-earth** (§5 SG). Run v3 + a same-config v2
   control; score; record HR/CRR/TSS. This is the one present-day gate not yet done.
2. **2100 extent table on bare-earth** (Table II of the paper): run all four cities at
   RP100/SSP5-8.5/2100 on bare-earth, record coastal/fluvial/pluvial/combined km². Coastal is
   the slow part (inertial, ~30 min/city). Bangkok must include the polder step.
3. **Bathtub→inertial on bare-earth** (Fig 4 / Sec. "validation"): for the coastal cities
   (SG, BKK, JKT) run RP100 present-day coastal with `--coastal-solver bathtub` AND `inertial`
   on the bare-earth; recompute the model/observed ratio. EXPECT the gap to widen vs the DSM
   (caveat 0.1). Rewrite the bathtub narrative as a pure solver-architecture result.
4. **Compile the bare-earth gate table** (all four present-day) to replace Table III.
5. **Rewrite `safe2026-v4.tex`** (→ v5): make bare-earth the sole terrain, delete the DSM atlas
   numbers and the §"Does More Accurate Terrain Help?" comparison, fold the DEM construction
   (error model + per-city calib + SG-DeltaDTM rationale) into the pipeline section, and rebuild
   Tables II/III + Fig 4 from the bare-earth runs. Mirror into the IEEE paper if desired.

## 7. What must be reported honestly (do not bury)

- Bangkok present-day bare-earth needs the CBD de-bias + documented pumped-polder floor; state it.
- Singapore terrain is DeltaDTM (lidar unusable); the ICESat-2 build is deprecated. The
  ICESat-2 → DeltaDTM switch IS the SG story, not a failure to hide.
- KL pluvial ≈0 under corrected present-day forcing (forcing, not terrain).
- Bathtub bias widens on bare-earth; the inertial solver is the (terrain-independent) fix.
- Canopy-product invariance (KL ETH vs Meta: b0 1.454 vs 1.457; gate ±1 borderline spot) —
  keep as the robustness note.

## 8. Key files
- DEMs: `flood-v3.0/dem/<city>/dem_bareearth_<city>_present_conditioned.tif` (SG = DeltaDTM).
- HANDs + KL raingrid + Bangkok defended/polder: `flood-v2.0/outputs_v3dem/_dem/`.
- Build/helper scripts: `flood-v3.0/dem/_build_sg_deltadtm_bareearth.py`, `..._build_kl_eth_canopy.py`;
  `flood-v2.0/scripts/_build_v3_hand.py`, `_build_kl_v3eth_raingrid.py`, `_probe_city_v3.py`,
  `apply_pumped_polder.py`.
- Dossiers: `flood-v2.0/docs/superpowers/runs/2026-06-17-v3dem-cross-city.md`,
  `...-v3dem-bangkok-pumped-polder.md`. DEM build method: `flood-v3.0/dem/DEM_HANDOFF.md`.
