#!/usr/bin/env bash
# Overnight multi-city batch: rain-on-grid pluvial + bare-earth/conditioned DEM
# + fluvial channel-masking + coastal MSL+SLR recession floor.
#
# Scope: the non-Singapore capitals, SSP5-8.5 2100, undefended.
# Ordered smallest-domain first so the most cities finish if interrupted.
# Reuses cached ERA5/coastal baselines (--no-fit-era5 --no-fit-coastal).
#
# Each city's first run downloads its Google Open Buildings S2 tile (~2-3 GB,
# cached to cache/openbuildings/) and builds the bare-earth + conditioned DEM.
#
# Usage:  bash scripts/run_overnight_batch.sh
set -u

CITIES="manila jakarta kuala_lumpur hcmc bangkok"

for city in $CITIES; do
  echo "==================== START ${city} $(date '+%Y-%m-%d %H:%M:%S') ===================="
  python scripts/run_city_pipeline.py \
      --city "${city}" \
      --scenario SSP5-8.5 --horizon 2100 \
      --no-fit-era5 --no-fit-coastal \
      --pluvial-model raingrid \
      --coastal-solver bathtub
  echo "==================== END   ${city} $(date '+%Y-%m-%d %H:%M:%S') exit=$? ===================="
done

echo "==================== BATCH COMPLETE $(date '+%Y-%m-%d %H:%M:%S') ===================="
