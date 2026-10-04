#!/usr/bin/env bash
# Run a list of Bangkok (scenario,RP) jobs sequentially. Used to fan the remaining
# Bangkok fill across parallel streams. Each arg = "stem:label:horizon:rp".
# Same config as atlas_fill.sh bangkok (debiased+defended DEM, inertial coastal,
# fillspill pluvial, runoff raster) + the pumped-polder post-step.
set -u
PY='C:/Users/Daniel/AppData/Local/Python/pythoncore-3.14-64/python.exe'
cd "$(dirname "$0")/.."
for spec in "$@"; do
  IFS=':' read -r stem label hz rp <<< "$spec"
  out="outputs/bangkok_${stem}_rp${rp}"
  csv="data/bangkok/hazard_levels_${stem}_rp${rp}.csv"
  echo "=== bangkok ${stem} rp${rp} (label=${label} horizon=${hz}) ==="
  "$PY" scripts/run_multihazard.py \
    --dem dem/_hand/bangkok_v3_debiased_defended.tif \
    --fluvial-hand-raster dem/_hand/hand_trunk_v3_debiased.tif \
    --hazard-levels "$csv" --scenario "$label" --horizon "$hz" --out-dir "$out" \
    --coastal-solver inertial --coastal-msl-egm2008 1.1785 --no-clamp-negative-land \
    --sea-mask-raster data/bangkok/sea_mask_utm47n.tif \
    --tidal-channel-raster data/bangkok/river_mask_utm47n.tif --tidal-burn-elevation 2.0 \
    --pluvial-model fillspill --pluvial-depth-cap 3.0 \
    --runoff-coeff-raster data/bangkok/runoff_coeff_utm47n.tif --fluvial-bankfull-rp 0
  "$PY" scripts/apply_pumped_polder.py --city bangkok --src-dir "$out" --out-dir "${out}_polder" \
    --rp "$rp" --scenario "$label" --horizon "$hz"
  echo "    done -> ${out}_polder"
done
echo "STREAM_DONE"
