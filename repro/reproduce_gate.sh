#!/usr/bin/env bash
# Reproduce the paper's validation gate (Table 3): documented-hotspot location skill,
# present-day RP100, bare-earth terrain, model-blind frozen EXPANDED registers,
# POST-RETROFIT atlas (canal-HAND pluvial 2026-07-04 + pluvial closing 2026-07-07).
#
# validate_hotspots.py defaults to the expanded register (hotspots_expanded.csv),
# which is the register scored in the paper. Pass --register hotspots.csv for the
# smaller diagnostic set. Bangkok is scored on its pumped-polder present-day output.
# Singapore's register was imported into data/singapore/manifest/ on 2026-07-04 and
# scores through the same path.
#
# Expected (Table 3, re-baselined 2026-07-12; Fisher = one-sided exact):
#   Jakarta       33/12  HR 0.85  CRR 0.92  TSS 0.77 [0.54, 0.94]  p=4.5e-6   PASS
#   Kuala Lumpur  31/12  HR 0.71  CRR 0.92  TSS 0.63 [0.38, 0.84]  p=2.6e-4   PASS (narrowest)
#   Singapore     38/20  HR 0.71  CRR 0.90  TSS 0.61 [0.41, 0.79]  p=7.9e-6   PASS
#   Bangkok       32/7   HR 0.34  CRR 1.00  TSS 0.34 [0.19, 0.50]  p=0.077    sig.(bootstrap); bounded
# Full stats incl. the no-pluvial decomposition: scripts/_rebaseline_stats.py
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-python}"
A=outputs/_fixed_atlas

$PY scripts/validate_hotspots.py --city jakarta      --out-dir $A/jakarta_ssp585_2020_rp100             --rp 100 || true
$PY scripts/validate_hotspots.py --city kuala_lumpur --out-dir $A/kuala_lumpur_ssp585_2020_rp100        --rp 100 || true
$PY scripts/validate_hotspots.py --city singapore    --out-dir $A/singapore_ssp585_2020_rp100           --rp 100 || true
$PY scripts/validate_hotspots.py --city bangkok      --out-dir $A/bangkok_ssp585_2020_rp100_polder      --rp 100 || true
