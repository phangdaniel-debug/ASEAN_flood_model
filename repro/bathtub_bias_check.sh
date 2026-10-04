#!/usr/bin/env bash
# Reproduce the bare-earth bathtub-vs-inertial RP100 coastal comparison (paper Fig. 4).
#
# APPLES-TO-APPLES: both solvers run on the SAME released seawall DEM (dem/_diag/
# <city>_seawall.tif = bare-earth conditioned + documented coastal-defence crest, built by
# scripts/_fix_coastal_seawall.py), the SAME framefix sea mask, tidal-channel seeds, and
# RP100 present-day still-water level. The commands are IDENTICAL to repro/run_atlas_fixed.sh
# except --coastal-solver is switched inertial->bathtub and --only-hazard-types coastal.
# The released atlas IS the inertial arm, so bathtub-vs-released-inertial is exact parity by
# construction. Bangkok is compared pre-polder (raw solver; the released arm additionally
# applies apply_pumped_polder.py, an orthogonal defence).
#
# Verified result (present SSP5-8.5/2020, RP100, flooded_area_km2):
#   singapore : bathtub    32.6 | inertial   1.18 | 27.5x
#   bangkok   : bathtub  3633.8 | inertial  85.34 | 42.6x   (bathtub ~= DSM-era 3,546; the
#               bare-earth+seawall inertial is far tighter than the DSM inertial 283)
#   jakarta   : bathtub   230.6 | inertial 188.50 |  1.2x   (subsided below-sea bowl: both
#               solvers flood it, so they converge)
set -u
PY='C:/Users/Daniel/AppData/Local/Python/pythoncore-3.14-64/python.exe'
cd "$(dirname "$0")/.."
OUT=outputs/_bathtub_check
mkdir -p "$OUT"

$PY scripts/run_multihazard.py --dem dem/_diag/singapore_seawall.tif \
  --fluvial-hand-raster dem/_hand/singapore_hand_v3_mainstem.tif \
  --hazard-levels data/singapore/hazard_levels_ssp585_2020_rp100.csv \
  --scenario SSP5-8.5 --horizon 2020 --out-dir "$OUT/singapore_bathtub" \
  --coastal-solver bathtub --coastal-msl-egm2008 1.1588 --only-hazard-types coastal \
  --sea-mask-raster data/singapore/sea_mask_utm48n_framefix.tif \
  --tidal-channel-raster data/singapore/river_mask_utm48n.tif --tidal-burn-elevation 2.0 \
  --runoff-coeff-raster data/singapore/runoff_coeff_utm48n.tif --runoff-coeff 0.75 --fluvial-bankfull-rp 0

$PY scripts/run_multihazard.py --dem dem/_diag/bangkok_seawall.tif \
  --fluvial-hand-raster dem/_hand/hand_trunk_v3_debiased.tif \
  --hazard-levels data/bangkok/hazard_levels_ssp585_2020_rp100.csv \
  --scenario SSP5-8.5 --horizon 2020 --out-dir "$OUT/bangkok_bathtub" \
  --coastal-solver bathtub --coastal-msl-egm2008 1.1785 --no-clamp-negative-land --only-hazard-types coastal \
  --sea-mask-raster data/bangkok/sea_mask_utm47n_framefix.tif \
  --tidal-channel-raster data/bangkok/river_mask_utm47n.tif --tidal-burn-elevation 2.0 \
  --runoff-coeff-raster data/bangkok/runoff_coeff_utm47n.tif --fluvial-bankfull-rp 0

$PY scripts/run_multihazard.py --dem dem/_diag/jakarta_seawall.tif \
  --fluvial-hand-raster dem/_hand/jakarta_hand_v3_mainstem.tif \
  --hazard-levels data/jakarta/hazard_levels_ssp585_2020_rp100.csv \
  --scenario SSP5-8.5 --horizon 2020 --out-dir "$OUT/jakarta_bathtub" \
  --coastal-solver bathtub --coastal-msl-egm2008 0.9976 --no-clamp-negative-land --only-hazard-types coastal \
  --sea-mask-raster data/jakarta/sea_mask_utm48s_framefix.tif \
  --tidal-channel-raster data/jakarta/river_mask_utm48s.tif --tidal-burn-elevation 2.0 \
  --runoff-coeff-raster data/jakarta/runoff_coeff_utm48s.tif --runoff-coeff 0.80 --fluvial-bankfull-rp 0

$PY - <<'PYEOF'
import csv, glob
def cst(f):
    for r in csv.DictReader(open(f[0])):
        if r['hazard_type'] == 'coastal': return float(r['flooded_area_km2'])
for c in ['singapore','bangkok','jakarta']:
    b = cst(glob.glob(f'outputs/_bathtub_check/{c}_bathtub/summary_*.csv'))
    i = cst(glob.glob(f'outputs/_fixed_atlas/{c}_ssp585_2020_rp100/summary_*.csv'))
    print(f'{c:10s}: bathtub {b:8.1f} | inertial {i:8.2f} | {b/i:5.1f}x')
PYEOF

# --- 2100 Table-II reconciliation (Bangkok combined, polder arm) ------------------
# Same commands with --horizon 2100 --scenario SSP5-8.5 (and SSP2-4.5) + hazard_levels
# _ssp{585,245}_2100_rp100.csv, then apply_pumped_polder.py on {bathtub coastal + released
# fluvial + pluvial} and per-pixel-max combine. Verified:
#   bathtub combined 2100 (polder) ~= 4,200 km2 (coastal 4,201 dominates)
#   inertial combined 2100 (polder, Table II) = 1,283 km2   -> ~3.3x reduction, STILL coastal-dominated
# Mitigation-delta paragraph was DROPPED (not reconciled): the recomputed 2100 coastal
# avoided-area delta REVERSES the paper's old claim -- bathtub avoided 34 km2 (SSP585 4,201 -
# SSP245 4,166; the flat delta SATURATES under both high-SLR pathways) vs inertial avoided
# 92 km2 (853 - 760). So bathtub UNDER-states the mitigation delta by saturation, it does not
# over-state it ~12x as the DSM-era 133/11 numbers claimed. Paragraph removed rather than
# re-argue; the coastal-solver correction is already carried by Fig. 4 + the Table-II sentence.
