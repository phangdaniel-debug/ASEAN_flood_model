#!/usr/bin/env bash
# Present-day (SSP5-8.5/2020) verification run with the three diagnostic fixes:
#   1. KL pluvial: raingrid -> fillspill (+ sea-mask outlet)
#   2. Singapore fluvial: dense-canal HAND -> main-stem HAND (>=50 km2)
#   3. Coastal: continuous coastline seawall DEMs (dem/_diag/<city>_seawall.tif)
# Outputs to outputs/_fixed/<city>_present[/ _polder for bangkok].
set -u
PY='C:/Users/Daniel/AppData/Local/Python/pythoncore-3.14-64/python.exe'
cd "$(dirname "$0")/.."
mkdir -p outputs/_fixed

echo "=== KL (fillspill pluvial) ==="
"$PY" scripts/run_multihazard.py --dem dem/kl/dem_bareearth_kl_eth_present_conditioned.tif \
  --fluvial-hand-raster dem/_hand/kl_hand_mainstem_v3eth.tif \
  --hazard-levels data/kuala_lumpur/hazard_levels_ssp585_2020.csv \
  --scenario SSP5-8.5 --horizon 2020 --out-dir outputs/_fixed/kuala_lumpur_present \
  --only-hazard-types fluvial,pluvial --pluvial-model fillspill --pluvial-depth-cap 3.0 \
  --sea-mask-raster data/kuala_lumpur/sea_mask_utm47n.tif \
  --tidal-channel-raster data/kuala_lumpur/drainage_waterways_utm47n.tif --tidal-burn-elevation 2.0 \
  --runoff-coeff-raster data/kuala_lumpur/runoff_coeff_utm47n.tif --runoff-coeff 0.75 --fluvial-bankfull-rp 0

echo "=== JAKARTA (seawall) ==="
"$PY" scripts/run_multihazard.py --dem dem/_diag/jakarta_seawall.tif \
  --fluvial-hand-raster dem/_hand/jakarta_hand_v3.tif \
  --hazard-levels data/jakarta/hazard_levels_ssp585_2020.csv \
  --scenario SSP5-8.5 --horizon 2020 --out-dir outputs/_fixed/jakarta_present \
  --coastal-solver inertial --coastal-msl-egm2008 0.9976 --no-clamp-negative-land \
  --sea-mask-raster data/jakarta/sea_mask_utm48s_framefix.tif \
  --tidal-channel-raster data/jakarta/river_mask_utm48s.tif --tidal-burn-elevation 2.0 \
  --pluvial-model fillspill --pluvial-depth-cap 3.0 \
  --runoff-coeff-raster data/jakarta/runoff_coeff_utm48s.tif --runoff-coeff 0.80 --fluvial-bankfull-rp 0

echo "=== SINGAPORE (seawall + main-stem HAND) ==="
"$PY" scripts/run_multihazard.py --dem dem/_diag/singapore_seawall.tif \
  --fluvial-hand-raster dem/_hand/singapore_hand_v3_mainstem.tif \
  --hazard-levels data/singapore/hazard_levels_ssp585_2020.csv \
  --scenario SSP5-8.5 --horizon 2020 --out-dir outputs/_fixed/singapore_present \
  --coastal-solver inertial --coastal-msl-egm2008 1.1588 \
  --sea-mask-raster data/singapore/sea_mask_utm48n_framefix.tif \
  --tidal-channel-raster data/singapore/river_mask_utm48n.tif --tidal-burn-elevation 2.0 \
  --pluvial-model fillspill --pluvial-depth-cap 3.0 \
  --runoff-coeff-raster data/singapore/runoff_coeff_utm48n.tif --runoff-coeff 0.75 --fluvial-bankfull-rp 0

echo "=== BANGKOK (seawall + pumped polder) ==="
"$PY" scripts/run_multihazard.py --dem dem/_diag/bangkok_seawall.tif \
  --fluvial-hand-raster dem/_hand/hand_trunk_v3_debiased.tif \
  --hazard-levels data/bangkok/hazard_levels_ssp585_2020.csv \
  --scenario SSP5-8.5 --horizon 2020 --out-dir outputs/_fixed/bangkok_present \
  --coastal-solver inertial --coastal-msl-egm2008 1.1785 --no-clamp-negative-land \
  --sea-mask-raster data/bangkok/sea_mask_utm47n_framefix.tif \
  --tidal-channel-raster data/bangkok/river_mask_utm47n.tif --tidal-burn-elevation 2.0 \
  --pluvial-model fillspill --pluvial-depth-cap 3.0 \
  --runoff-coeff-raster data/bangkok/runoff_coeff_utm47n.tif --fluvial-bankfull-rp 0
"$PY" scripts/apply_pumped_polder.py --city bangkok --src-dir outputs/_fixed/bangkok_present \
  --out-dir outputs/_fixed/bangkok_present_polder --rp 100 --scenario SSP5-8.5 --horizon 2020

echo "### RUN_FIXED_PRESENT_DONE ###"
