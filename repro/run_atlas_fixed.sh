#!/usr/bin/env bash
# Full fixed-atlas rebuild: all 4 cities x 5 scenario-horizons x 3 RPs with the
# output-plausibility fixes (framefix sea-masks, citable seawalls, main-stem
# fluvial, handfill pluvial, KL fillspill, Bangkok pumped polder).
# RESUMABLE: skips any (city,stem,rp) whose summary already exists.
#
# The SG/Jakarta handfill lines pass --pluvial-hand-stage-baseline (added 2026-07-17):
# the SHIPPED atlas carries the RP/climate-SCALED handfill (historically applied by
# repro/rerun_handfill_scaled.sh after the rebuild); without the flag a clean rebuild
# would produce the forcing-invariant fixed-stage layer instead — identical pluvial at
# every RP — and NOT reproduce the shipped product. Baselines are each city's
# present-day RP100 excess, so the present-day RP100 gate is preserved by construction.
# Outputs: outputs/_fixed_atlas/<city>_<stem>_rp<rp>[/ _polder for bangkok].
set -u
PY='C:/Users/Daniel/AppData/Local/Python/pythoncore-3.14-64/python.exe'
cd "$(dirname "$0")/.."
mkdir -p outputs/_fixed_atlas

# --- regenerate derived rasters (idempotent; cheap except the HANDs) ----------
"$PY" scripts/_fix_sea_mask_frame.py >/dev/null 2>&1 || true
"$PY" scripts/_fix_coastal_seawall.py >/dev/null 2>&1 || true
[ -f dem/_hand/singapore_hand_v3_mainstem.tif ] || "$PY" scripts/_fix_sg_mainstem_hand.py >/dev/null 2>&1
[ -f dem/_hand/jakarta_hand_v3_mainstem.tif ]   || "$PY" scripts/_fix_jakarta_mainstem_hand.py >/dev/null 2>&1
# KL trunk HAND: regenerated bit-exactly from the DEM + the frozen v2-lineage drainage
# mask (data/kuala_lumpur/trunk_drainage_mask_utm47n.tif). Bangkok's hand_trunk_v3_debiased
# is a PRIMARY frozen input (v2-lineage + debiasing, not script-derivable) shipped in the
# archive like the bare-earth DEMs -- see model-documentation.md §6.2.3.
[ -f dem/_hand/kl_hand_mainstem_v3eth.tif ]     || "$PY" scripts/_fix_kl_trunk_hand.py >/dev/null 2>&1

# scenario stems (present = ssp585_2020) and RPs
SCEN=(ssp585_2020 ssp245_2050 ssp245_2100 ssp585_2050 ssp585_2100)
LABELS=("SSP5-8.5:2020" "SSP2-4.5:2050" "SSP2-4.5:2100" "SSP5-8.5:2050" "SSP5-8.5:2100")
RPS=(10 100 1000)

run_cell () {
  local city="$1" stem="$2" rp="$3" label="$4" hz="$5"
  local out="outputs/_fixed_atlas/${city}_${stem}_rp${rp}"
  local csv="data/${city}/hazard_levels_${stem}_rp${rp}.csv"
  local final="$out/summary_${label}_${hz}.csv"
  [ "$city" = "bangkok" ] && final="${out}_polder/summary_${label}_${hz}.csv"
  if [ -f "$final" ]; then echo "  skip ${city} ${stem} rp${rp} (done)"; return; fi
  [ -f "$csv" ] || { echo "  MISSING csv $csv"; return; }
  echo "=== ${city} ${stem} rp${rp} ==="
  case "$city" in
    kuala_lumpur)
      "$PY" scripts/run_multihazard.py --dem dem/kl/dem_bareearth_kl_eth_present_conditioned.tif \
        --fluvial-hand-raster dem/_hand/kl_hand_mainstem_v3eth.tif --hazard-levels "$csv" \
        --scenario "$label" --horizon "$hz" --out-dir "$out" \
        --only-hazard-types fluvial,pluvial --pluvial-model fillspill --pluvial-depth-cap 3.0 \
        --sea-mask-raster data/kuala_lumpur/sea_mask_utm47n.tif \
        --tidal-channel-raster data/kuala_lumpur/drainage_waterways_utm47n.tif --tidal-burn-elevation 2.0 \
        --runoff-coeff-raster data/kuala_lumpur/runoff_coeff_utm47n.tif --runoff-coeff 0.75 --fluvial-bankfull-rp 0 ;;
    singapore)
      "$PY" scripts/run_multihazard.py --dem dem/_diag/singapore_seawall.tif \
        --fluvial-hand-raster dem/_hand/singapore_hand_v3_mainstem.tif --hazard-levels "$csv" \
        --scenario "$label" --horizon "$hz" --out-dir "$out" \
        --coastal-solver inertial --coastal-msl-egm2008 1.1588 \
        --sea-mask-raster data/singapore/sea_mask_utm48n_framefix.tif \
        --tidal-channel-raster data/singapore/river_mask_utm48n.tif --tidal-burn-elevation 2.0 \
        --pluvial-model handfill --pluvial-hand-raster dem/_hand/singapore_hand_v3_hybrid.tif --pluvial-hand-stage 1.5 --pluvial-hand-stage-baseline 0.069602 --pluvial-depth-cap 0.5 \
        --runoff-coeff-raster data/singapore/runoff_coeff_utm48n.tif --runoff-coeff 0.75 --fluvial-bankfull-rp 0 ;;
    jakarta)
      "$PY" scripts/run_multihazard.py --dem dem/_diag/jakarta_seawall.tif \
        --fluvial-hand-raster dem/_hand/jakarta_hand_v3_mainstem.tif --hazard-levels "$csv" \
        --scenario "$label" --horizon "$hz" --out-dir "$out" \
        --coastal-solver inertial --coastal-msl-egm2008 0.9976 --no-clamp-negative-land \
        --sea-mask-raster data/jakarta/sea_mask_utm48s_framefix.tif \
        --tidal-channel-raster data/jakarta/river_mask_utm48s.tif --tidal-burn-elevation 2.0 \
        --pluvial-model handfill --pluvial-hand-raster dem/_hand/jakarta_hand_v3.tif --pluvial-hand-stage 2.5 --pluvial-hand-stage-baseline 0.129999 --pluvial-depth-cap 1.0 \
        --runoff-coeff-raster data/jakarta/runoff_coeff_utm48s.tif --runoff-coeff 0.80 --fluvial-bankfull-rp 0 ;;
    bangkok)
      "$PY" scripts/run_multihazard.py --dem dem/_diag/bangkok_seawall.tif \
        --fluvial-hand-raster dem/_hand/hand_trunk_v3_debiased.tif --hazard-levels "$csv" \
        --scenario "$label" --horizon "$hz" --out-dir "$out" \
        --coastal-solver inertial --coastal-msl-egm2008 1.1785 --no-clamp-negative-land \
        --sea-mask-raster data/bangkok/sea_mask_utm47n_framefix.tif \
        --tidal-channel-raster data/bangkok/river_mask_utm47n.tif --tidal-burn-elevation 2.0 \
        --pluvial-model fillspill --pluvial-depth-cap 3.0 \
        --runoff-coeff-raster data/bangkok/runoff_coeff_utm47n.tif --fluvial-bankfull-rp 0
      "$PY" scripts/apply_pumped_polder.py --city bangkok --src-dir "$out" \
        --out-dir "${out}_polder" --rp "$rp" --scenario "$label" --horizon "$hz" ;;
  esac
  echo "    done -> $out"
}

for city in kuala_lumpur singapore jakarta bangkok; do
  for i in "${!SCEN[@]}"; do
    IFS=':' read -r label hz <<< "${LABELS[$i]}"
    for rp in "${RPS[@]}"; do
      run_cell "$city" "${SCEN[$i]}" "$rp" "$label" "$hz"
    done
  done
done

# =============================================================================
# STAGE 2 — post-solve pluvial chain (folded in 2026-07-13)
# =============================================================================
# The solve loop above produces the STAGE-1 atlas. The SHIPPED atlas (and every
# number in the paper) is that atlas plus the chain below. These ran as detached
# post-processes from 2026-07-04; folding them in makes one command reproduce the
# shipped product. Documented in docs/technical/model-documentation.md §6.3.5.
#
# ORDER IS LOAD-BEARING — do not reorder:
#   1. canal-HAND applies  — recompute from the pristine *.tif.orig sidecar, so they
#      are IDEMPOTENT and safe on a resumed/partial run. KL prunes its drain network
#      to >=0.5 km2 accumulation (hill headwater ditches flood the high dry controls);
#      Jakarta does not (delta canals are all engineered conveyance).
#      Applied only where the 4-city assessment said so: KL + Jakarta. Singapore and
#      Bangkok are DELIBERATELY excluded (SG: already-skilful, retrofit only adds false
#      alarms; BKK: pumped flat delta, CRR collapses 1.00->0.43). See §6.3.5.
#   2. bridge-closing      — backs the CURRENT raster up to *.preclose (once) and closes
#      THAT. It must run AFTER the canal-HAND and must never read *.orig. Idempotent
#      via the *.preclose sidecar. Applies to all four cities.
#   3. summary/severity regen — MUST BE LAST, so the CSVs match the final rasters.
#      Covers all four cities (the closing moves every city's extent).
# -----------------------------------------------------------------------------
echo "=== STAGE 2: canal-HAND retrofit (KL, Jakarta) ==="
"$PY" scripts/_apply_kl_canal_pluvial.py      || echo "  WARN: KL canal-HAND failed"
"$PY" scripts/_apply_jakarta_canal_pluvial.py || echo "  WARN: Jakarta canal-HAND failed"

echo "=== STAGE 2: bridge-closing (all 4 cities) ==="
"$PY" scripts/_apply_city_pluvial_closing.py  || echo "  WARN: pluvial closing failed"

echo "=== STAGE 2: regenerate pluvial summary + severity (all 4 cities, LAST) ==="
"$PY" scripts/_regen_pluvial_summary_severity.py || echo "  WARN: summary/severity regen failed"

echo "### RUN_ATLAS_FIXED_DONE ###"
