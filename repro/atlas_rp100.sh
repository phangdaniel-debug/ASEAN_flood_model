#!/usr/bin/env bash
# RP100 future atlas — run ONE city's 4 scenario-horizons sequentially.
# Usage: bash repro/atlas_rp100.sh <bangkok|jakarta|kuala_lumpur|singapore>
# Launch one per city in parallel (parallelise across cities, sequential within).
# Terrain is held at present-day for all horizons (decision #5); only the forcing
# CSV (RP100 slice, carrying the AR6 SLR delta) changes per scenario.
set -u
PY='C:/Users/Daniel/AppData/Local/Python/pythoncore-3.14-64/python.exe'
cd "$(dirname "$0")/.."
CITY="$1"

# scenario stem : scenario label : horizon
SCEN=(
  "ssp245_2050:SSP2-4.5:2050"
  "ssp245_2100:SSP2-4.5:2100"
  "ssp585_2050:SSP5-8.5:2050"
  "ssp585_2100:SSP5-8.5:2100"
)

run_city () {
  local label="$1" hz="$2" out="$3" csv="$4"
  case "$CITY" in
    kuala_lumpur)
      "$PY" scripts/run_multihazard.py --dem dem/kl/dem_bareearth_kl_eth_present_conditioned.tif \
        --fluvial-hand-raster dem/_hand/kl_hand_mainstem_v3eth.tif --hazard-levels "$csv" \
        --scenario "$label" --horizon "$hz" --out-dir "$out" \
        --only-hazard-types fluvial,pluvial --pluvial-model raingrid \
        --pluvial-dem-raster dem/_hand/kl_raingrid_v3eth.tif --pluvial-depth-cap 3.0 \
        --tidal-channel-raster data/kuala_lumpur/drainage_waterways_utm47n.tif \
        --runoff-coeff-raster data/kuala_lumpur/runoff_coeff_utm47n.tif --runoff-coeff 0.75 --fluvial-bankfull-rp 0
      ;;
    jakarta)
      "$PY" scripts/run_multihazard.py --dem dem/jakarta/dem_bareearth_jakarta_present_conditioned.tif \
        --fluvial-hand-raster dem/_hand/jakarta_hand_v3.tif --hazard-levels "$csv" \
        --scenario "$label" --horizon "$hz" --out-dir "$out" \
        --coastal-solver inertial --coastal-msl-egm2008 0.9976 --no-clamp-negative-land \
        --sea-mask-raster data/jakarta/sea_mask_utm48s.tif \
        --tidal-channel-raster data/jakarta/river_mask_utm48s.tif --tidal-burn-elevation 2.0 \
        --pluvial-model fillspill --pluvial-depth-cap 3.0 \
        --runoff-coeff-raster data/jakarta/runoff_coeff_utm48s.tif --runoff-coeff 0.80 \
        --fluvial-bankfull-rp 0
      ;;
    singapore)
      "$PY" scripts/run_multihazard.py --dem dem/singapore/dem_bareearth_singapore_present_conditioned.tif \
        --fluvial-hand-raster dem/_hand/singapore_hand_v3_hybrid.tif --hazard-levels "$csv" \
        --scenario "$label" --horizon "$hz" --out-dir "$out" \
        --coastal-solver inertial --coastal-msl-egm2008 1.1588 \
        --sea-mask-raster data/singapore/sea_mask_utm48n.tif \
        --tidal-channel-raster data/singapore/river_mask_utm48n.tif --tidal-burn-elevation 2.0 \
        --pluvial-model fillspill --pluvial-depth-cap 3.0 \
        --runoff-coeff-raster data/singapore/runoff_coeff_utm48n.tif --runoff-coeff 0.75 \
        --fluvial-bankfull-rp 0
      ;;
    bangkok)
      "$PY" scripts/run_multihazard.py --dem dem/_hand/bangkok_v3_debiased_defended.tif \
        --fluvial-hand-raster dem/_hand/hand_trunk_v3_debiased.tif --hazard-levels "$csv" \
        --scenario "$label" --horizon "$hz" --out-dir "$out" \
        --coastal-solver inertial --coastal-msl-egm2008 1.1785 --no-clamp-negative-land \
        --sea-mask-raster data/bangkok/sea_mask_utm47n.tif \
        --tidal-channel-raster data/bangkok/river_mask_utm47n.tif --tidal-burn-elevation 2.0 \
        --pluvial-model fillspill --pluvial-depth-cap 3.0 \
        --runoff-coeff-raster data/bangkok/runoff_coeff_utm47n.tif \
        --fluvial-bankfull-rp 0
      "$PY" scripts/apply_pumped_polder.py --city bangkok --src-dir "$out" --out-dir "${out}_polder" \
        --rp 100 --scenario "$label" --horizon "$hz"
      ;;
    *)
      echo "unknown city: $CITY" >&2; exit 2 ;;
  esac
}

for triple in "${SCEN[@]}"; do
  IFS=':' read -r stem label hz <<< "$triple"
  out="outputs/${CITY}_${stem}"
  csv="data/${CITY}/hazard_levels_${stem}_rp100.csv"
  echo "=== $CITY $stem (label=$label horizon=$hz) ==="
  run_city "$label" "$hz" "$out" "$csv"
  echo "    done -> $out"
done
echo "ATLAS_CITY_DONE $CITY"
