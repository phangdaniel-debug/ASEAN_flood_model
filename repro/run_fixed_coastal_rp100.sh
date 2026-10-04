#!/usr/bin/env bash
# Fixed present-day coastal cities, RP100 ONLY (fast visual upfront):
# framefixed sea-masks + citable-crest defence DEMs + (SG) main-stem HAND + (BKK) polder.
set -u
PY='C:/Users/Daniel/AppData/Local/Python/pythoncore-3.14-64/python.exe'
cd "$(dirname "$0")/.."

echo "=== SINGAPORE (smallest first) ==="
"$PY" scripts/run_multihazard.py --dem dem/_diag/singapore_seawall.tif \
  --fluvial-hand-raster dem/_hand/singapore_hand_v3_mainstem.tif \
  --hazard-levels data/singapore/hazard_levels_ssp585_2020_rp100only.csv \
  --scenario SSP5-8.5 --horizon 2020 --out-dir outputs/_fixed/singapore_present \
  --coastal-solver inertial --coastal-msl-egm2008 1.1588 \
  --sea-mask-raster data/singapore/sea_mask_utm48n_framefix.tif \
  --tidal-channel-raster data/singapore/river_mask_utm48n.tif --tidal-burn-elevation 2.0 \
  --pluvial-model handfill --pluvial-hand-raster dem/_hand/singapore_hand_v3_hybrid.tif --pluvial-hand-stage 1.5 --pluvial-depth-cap 0.5 \
  --runoff-coeff-raster data/singapore/runoff_coeff_utm48n.tif --runoff-coeff 0.75 --fluvial-bankfull-rp 0

echo "=== JAKARTA ==="
"$PY" scripts/run_multihazard.py --dem dem/_diag/jakarta_seawall.tif \
  --fluvial-hand-raster dem/_hand/jakarta_hand_v3_mainstem.tif \
  --hazard-levels data/jakarta/hazard_levels_ssp585_2020_rp100only.csv \
  --scenario SSP5-8.5 --horizon 2020 --out-dir outputs/_fixed/jakarta_present \
  --coastal-solver inertial --coastal-msl-egm2008 0.9976 --no-clamp-negative-land \
  --sea-mask-raster data/jakarta/sea_mask_utm48s_framefix.tif \
  --tidal-channel-raster data/jakarta/river_mask_utm48s.tif --tidal-burn-elevation 2.0 \
  --pluvial-model handfill --pluvial-hand-raster dem/_hand/jakarta_hand_v3.tif --pluvial-hand-stage 2.5 --pluvial-depth-cap 1.0 \
  --runoff-coeff-raster data/jakarta/runoff_coeff_utm48s.tif --runoff-coeff 0.80 --fluvial-bankfull-rp 0

echo "=== BANGKOK ==="
"$PY" scripts/run_multihazard.py --dem dem/_diag/bangkok_seawall.tif \
  --fluvial-hand-raster dem/_hand/hand_trunk_v3_debiased.tif \
  --hazard-levels data/bangkok/hazard_levels_ssp585_2020_rp100only.csv \
  --scenario SSP5-8.5 --horizon 2020 --out-dir outputs/_fixed/bangkok_present \
  --coastal-solver inertial --coastal-msl-egm2008 1.1785 --no-clamp-negative-land \
  --sea-mask-raster data/bangkok/sea_mask_utm47n_framefix.tif \
  --tidal-channel-raster data/bangkok/river_mask_utm47n.tif --tidal-burn-elevation 2.0 \
  --pluvial-model fillspill --pluvial-depth-cap 3.0 \
  --runoff-coeff-raster data/bangkok/runoff_coeff_utm47n.tif --fluvial-bankfull-rp 0
"$PY" scripts/apply_pumped_polder.py --city bangkok --src-dir outputs/_fixed/bangkok_present \
  --out-dir outputs/_fixed/bangkok_present_polder --rp 100 --scenario SSP5-8.5 --horizon 2020

echo "### RUN_FIXED_RP100_DONE ###"
