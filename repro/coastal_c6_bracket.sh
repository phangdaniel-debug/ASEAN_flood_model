#!/usr/bin/env bash
# Review C5+C6 closure bracket (adversarial-review-2026-07-09.md, ranked follow-up #1):
# Bangkok SSP5-8.5/2100 RP100 coastal, inertial, three variants vs the shipped run:
#   tend16 : t_end = 16 h (57,600 s), n = 0.06  -> bounds the t_end-truncation term.
#            The 3-1-2 h hydrograph is UNCHANGED; only the post-surge settling window
#            doubles, so any extent growth is water still propagating at the 8 h cutoff.
#   n003   : n = 0.03, t_end = 8 h             -> smooth-surface end of the Manning
#   n010   : n = 0.10, t_end = 8 h                bracket on the DEFENDED, overtopping-
#            driven case (C5 measured only undefended Jakarta).
# Sequential on purpose: the numba kernels parallelise across all cores; concurrent
# runs would thrash. Compare against outputs/_fixed_atlas/bangkok_ssp585_2100_rp100
# (same DEM, masks, forcing; only the varied flag differs).
set -u
PY='C:/Users/Daniel/AppData/Local/Python/pythoncore-3.14-64/python.exe'
cd "$(dirname "$0")/.."
OUT=outputs/_diag/c6_bracket
mkdir -p "$OUT"

run () {
  local name="$1"; shift
  if [ -f "$OUT/$name/coastal/rp_100/coastal_depth_SSP5-8.5_2100_rp100.tif" ]; then
    echo "=== $name already done, skip ==="; return
  fi
  echo "=== $name start $(date '+%H:%M:%S') ==="
  "$PY" scripts/run_multihazard.py --dem dem/_diag/bangkok_seawall.tif \
    --hazard-levels data/bangkok/hazard_levels_ssp585_2100_rp100.csv \
    --scenario "SSP5-8.5" --horizon 2100 --out-dir "$OUT/$name" \
    --coastal-solver inertial --coastal-msl-egm2008 1.1785 --no-clamp-negative-land \
    --sea-mask-raster data/bangkok/sea_mask_utm47n_framefix.tif \
    --tidal-channel-raster data/bangkok/river_mask_utm47n.tif --tidal-burn-elevation 2.0 \
    --only-hazard-types coastal "$@" 2>&1 | grep -E "coastal|converged|Wrote|Error|error" | tail -6
  echo "=== $name done $(date '+%H:%M:%S') ==="
}

run tend16 --inertial-t-end 57600
run n003   --coastal-manning-n 0.03
run n010   --coastal-manning-n 0.10
echo "### C6_BRACKET_DONE ###"
