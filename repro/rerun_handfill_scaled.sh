#!/usr/bin/env bash
# Post-rebuild re-runs. Run ONLY AFTER run_atlas_fixed.sh has finished
# (the RUN_ATLAS_FIXED_DONE marker is in outputs/_fixed_atlas/rebuild.log).
#
# PHASE 1 (default) — handfill stage scaling.
#   The handfill pluvial model used a FIXED --pluvial-hand-stage, so Singapore's and
#   Jakarta's pluvial layer was identical at every RP and every scenario (forcing-
#   invariant). With --pluvial-hand-stage-baseline the effective stage scales with the
#   per-RP rain excess, preserving the present-day RP100 calibration (so the gate is
#   unchanged) while making the layer respond to RP and climate. This phase re-runs the
#   PLUVIAL layer only for the 30 SG+Jakarta cells and swaps it into the existing atlas
#   cells (coastal + fluvial untouched). Cheap: seconds per cell.
#
# PHASE 2 (--with-coastal-cap) — coastal depth-cap fix.  EXPENSIVE (~10 h).
#   The inertial physical cap uses `peak_WSE - max(0,bed)`, which UNDER-states depth on
#   below-MSL land (Jakarta subsidence). The fix is `peak_WSE - bed`. This is depth-only
#   (extents are unchanged), so the paper's extent-based headline numbers do NOT need it.
#   It requires re-solving the inertial coastal layer for Jakarta (15 cells, ~41 min
#   each). OFF by default; consider documenting the limitation instead. Bangkok's core is
#   above MSL so its below-MSL exposure is minimal — add it only if a check shows it
#   matters.
#
# Usage:
#   bash repro/rerun_handfill_scaled.sh                 # Phase 1 only
#   bash repro/rerun_handfill_scaled.sh --with-coastal-cap   # Phase 1 + 2 (~10 h)
#   bash repro/rerun_handfill_scaled.sh --force ...     # skip the rebuild-done guard
set -u
PY='C:/Users/Daniel/AppData/Local/Python/pythoncore-3.14-64/python.exe'
cd "$(dirname "$0")/.."
ATLAS=outputs/_fixed_atlas
TMP=outputs/_diag/_rerun_tmp

WITH_CAP=0; FORCE=0
for a in "$@"; do
  [ "$a" = "--with-coastal-cap" ] && WITH_CAP=1
  [ "$a" = "--force" ] && FORCE=1
done

# --- guard: the rebuild must be finished (this script mutates atlas cells) ----------
if ! grep -q "RUN_ATLAS_FIXED_DONE" "$ATLAS/rebuild.log" 2>/dev/null; then
  echo "[guard] rebuild not finished (no RUN_ATLAS_FIXED_DONE in $ATLAS/rebuild.log)."
  [ "$FORCE" = "1" ] || { echo "        run after it completes, or pass --force."; exit 1; }
  echo "        --force given; proceeding anyway."
fi

SCEN=(ssp585_2020 ssp245_2050 ssp245_2100 ssp585_2050 ssp585_2100)
LABELS=("SSP5-8.5:2020" "SSP2-4.5:2050" "SSP2-4.5:2100" "SSP5-8.5:2050" "SSP5-8.5:2100")
RPS=(10 100 1000)

# ====================================================================================
# PHASE 1 — handfill stage scaling (Singapore + Jakarta)
# ====================================================================================
declare -A BASELINE=( [singapore]=0.069602 [jakarta]=0.129999 )   # present-day RP100 excess (calibration point)
declare -A HANDR=(    [singapore]=dem/_hand/singapore_hand_v3_hybrid.tif [jakarta]=dem/_hand/jakarta_hand_v3.tif )
declare -A STAGE=(    [singapore]=1.5 [jakarta]=2.5 )
declare -A CAP=(      [singapore]=0.5 [jakarta]=1.0 )
declare -A DEM=(      [singapore]=dem/_diag/singapore_seawall.tif [jakarta]=dem/_diag/jakarta_seawall.tif )
declare -A SEAM=(     [singapore]=data/singapore/sea_mask_utm48n_framefix.tif [jakarta]=data/jakarta/sea_mask_utm48s_framefix.tif )
declare -A RIVM=(     [singapore]=data/singapore/river_mask_utm48n.tif [jakarta]=data/jakarta/river_mask_utm48s.tif )
declare -A RCR=(      [singapore]=data/singapore/runoff_coeff_utm48n.tif [jakarta]=data/jakarta/runoff_coeff_utm48s.tif )
declare -A RCV=(      [singapore]=0.75 [jakarta]=0.80 )
declare -A NOCLAMP=(  [singapore]="" [jakarta]="--no-clamp-negative-land" )

echo "### PHASE 1: handfill stage scaling (SG + Jakarta pluvial) ###"
for city in singapore jakarta; do
  for i in "${!SCEN[@]}"; do
    IFS=':' read -r label hz <<< "${LABELS[$i]}"; stem="${SCEN[$i]}"
    for rp in "${RPS[@]}"; do
      cell="$ATLAS/${city}_${stem}_rp${rp}"
      csv="data/${city}/hazard_levels_${stem}_rp${rp}.csv"
      [ -d "$cell/pluvial/rp_${rp}" ] || { echo "  skip (no cell) $cell"; continue; }
      [ -f "$csv" ] || { echo "  skip (no csv) $csv"; continue; }
      tmp="$TMP/${city}_${stem}_rp${rp}"; rm -rf "$tmp"
      "$PY" scripts/run_multihazard.py --dem "${DEM[$city]}" \
        --hazard-levels "$csv" --scenario "$label" --horizon "$hz" --out-dir "$tmp" \
        --only-hazard-types pluvial --pluvial-model handfill ${NOCLAMP[$city]} \
        --pluvial-hand-raster "${HANDR[$city]}" --pluvial-hand-stage "${STAGE[$city]}" \
        --pluvial-hand-stage-baseline "${BASELINE[$city]}" --pluvial-depth-cap "${CAP[$city]}" \
        --sea-mask-raster "${SEAM[$city]}" \
        --tidal-channel-raster "${RIVM[$city]}" --tidal-burn-elevation 2.0 \
        --runoff-coeff-raster "${RCR[$city]}" --runoff-coeff "${RCV[$city]}" --fluvial-bankfull-rp 0 \
        >/dev/null 2>&1 || { echo "  FAIL run $cell"; continue; }
      cp -f "$tmp"/pluvial/rp_${rp}/*.tif "$cell"/pluvial/rp_${rp}/ 2>/dev/null
      "$PY" scripts/_patch_summary_hazard.py "$cell" "$tmp" pluvial
      echo "  done $city $stem rp$rp"
    done
  done
done
rm -rf "$TMP"
echo "### PHASE 1 DONE — SG+Jakarta pluvial now RP/scenario-responsive ###"

# ====================================================================================
# PHASE 2 — coastal depth-cap fix (Jakarta), OPT-IN
# ====================================================================================
if [ "$WITH_CAP" = "1" ]; then
  echo "### PHASE 2: coastal depth-cap fix (Jakarta coastal re-solve, ~10 h) ###"
  # apply the one-line code fix (idempotent): peak_WSE - max(0,bed)  ->  peak_WSE - bed
  if grep -q 'float(level_m) - np.maximum(0.0, _bed)' scripts/run_multihazard.py; then
    "$PY" - <<'PYEOF'
import io
p="scripts/run_multihazard.py"; s=open(p,encoding="utf-8").read()
s=s.replace("float(level_m) - np.maximum(0.0, _bed)","float(level_m) - _bed")
open(p,"w",encoding="utf-8",newline="").write(s)
print("  applied depth-cap fix to run_multihazard.py")
PYEOF
  else
    echo "  depth-cap fix already applied (or pattern not found) — continuing"
  fi
  MSL_jakarta=0.9976
  for i in "${!SCEN[@]}"; do
    IFS=':' read -r label hz <<< "${LABELS[$i]}"; stem="${SCEN[$i]}"
    for rp in "${RPS[@]}"; do
      cell="$ATLAS/jakarta_${stem}_rp${rp}"; csv="data/jakarta/hazard_levels_${stem}_rp${rp}.csv"
      [ -d "$cell/coastal/rp_${rp}" ] || { echo "  skip (no cell) $cell"; continue; }
      tmp="$TMP/jakarta_cap_${stem}_rp${rp}"; rm -rf "$tmp"
      "$PY" scripts/run_multihazard.py --dem dem/_diag/jakarta_seawall.tif \
        --hazard-levels "$csv" --scenario "$label" --horizon "$hz" --out-dir "$tmp" \
        --only-hazard-types coastal --coastal-solver inertial --coastal-msl-egm2008 "$MSL_jakarta" \
        --no-clamp-negative-land --sea-mask-raster data/jakarta/sea_mask_utm48s_framefix.tif \
        --tidal-channel-raster data/jakarta/river_mask_utm48s.tif --tidal-burn-elevation 2.0 \
        || { echo "  FAIL coastal $cell"; continue; }
      cp -f "$tmp"/coastal/rp_${rp}/*.tif "$cell"/coastal/rp_${rp}/ 2>/dev/null
      "$PY" scripts/_patch_summary_hazard.py "$cell" "$tmp" coastal
      echo "  done jakarta coastal-cap $stem rp$rp"
    done
  done
  rm -rf "$TMP"
  echo "### PHASE 2 DONE ###"
else
  echo "(Phase 2 coastal depth-cap skipped — pass --with-coastal-cap to run it, ~10 h.)"
fi

echo "### RERUN_HANDFILL_SCALED_DONE ###"
