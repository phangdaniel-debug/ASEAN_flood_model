#!/usr/bin/env bash
# Coastal Manning-n sensitivity (closes adversarial-review item C5).
# Jakarta present-day RP100, coastal-only (--only-hazard-types coastal), n in {0.06,0.08,0.10}.
# Jakarta = the representative undefended, subsided delta where surface friction most
# affects overland surge spread. Compares the RP100 coastal flooded extent + depths.
set -u
PY='C:/Users/Daniel/AppData/Local/Python/pythoncore-3.14-64/python.exe'
cd "$(dirname "$0")/.."

for n in 0.06 0.08 0.10; do
  echo "===== Jakarta coastal  n=$n  ====="
  "$PY" scripts/run_multihazard.py --dem dem/_diag/jakarta_seawall.tif \
    --fluvial-hand-raster dem/_hand/jakarta_hand_v3_mainstem.tif \
    --hazard-levels data/jakarta/hazard_levels_ssp585_2020_rp100only.csv \
    --scenario SSP5-8.5 --horizon 2020 --out-dir "outputs/_diag/manning_n/jakarta_n${n}" \
    --only-hazard-types coastal \
    --coastal-solver inertial --coastal-manning-n "$n" \
    --coastal-msl-egm2008 0.9976 --no-clamp-negative-land \
    --sea-mask-raster data/jakarta/sea_mask_utm48s_framefix.tif \
    --tidal-channel-raster data/jakarta/river_mask_utm48s.tif --tidal-burn-elevation 2.0 \
    --runoff-coeff-raster data/jakarta/runoff_coeff_utm48s.tif --fluvial-bankfull-rp 0
done
echo "### MANNING_SENSITIVITY_DONE ###"
