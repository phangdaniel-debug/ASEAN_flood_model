#!/usr/bin/env bash
# Wait for the Jakarta coastal depth-cap re-solve to finish its LAST combo
# (ssp585_2100 RP1000), then stage + upload the Jakarta Zenodo record (draft only).
# Launched in the background; emits a task-notification on exit.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="C:/Users/Daniel/AppData/Local/Python/pythoncore-3.14-64/python.exe"
RP1000="outputs/_fixed_atlas/jakarta_ssp585_2100_rp1000/coastal/rp_1000/coastal_depth_SSP5-8.5_2100_rp1000.tif"

START=$(date +%s)
DEADLINE=$((START + 5 * 3600))   # 5h safety stop
echo "[watch] start $(date '+%Y-%m-%d %H:%M'); waiting for rp1000 re-solve (mtime > $START)"
while :; do
  if [ -f "$RP1000" ]; then
    m=$(stat -c %Y "$RP1000" 2>/dev/null || echo 0)
    if [ "$m" -gt "$START" ]; then
      echo "[watch] rp1000 re-solved at $(date '+%H:%M')"; break
    fi
  fi
  if [ "$(date +%s)" -gt "$DEADLINE" ]; then echo "[watch] TIMEOUT"; exit 3; fi
  sleep 120
done

echo "[watch] buffering 150s for final severity/summary writes..."
sleep 150

echo "[watch] === staging jakarta record ==="
"$PY" scripts/_zenodo_package_city.py jakarta || { echo "[watch] PACKAGE FAILED"; exit 1; }

echo "[watch] === uploading jakarta draft ==="
if [ -s zenodo/.token ]; then
  "$PY" scripts/_zenodo_upload.py jakarta || { echo "[watch] UPLOAD FAILED (retry on wake)"; exit 2; }
else
  echo "[watch] no zenodo/.token — staged only, skipping upload"
fi
echo "[watch] DONE $(date '+%H:%M')"
