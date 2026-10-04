"""Stage a per-city Zenodo record for the flood atlas (anonymized, double-blind).

For each city it writes a lightweight staging folder `zenodo/<city>/` containing:
  - MANIFEST.csv   : (source_path, archive_name, bytes) for every file in the record
  - README.md      : anonymized description + contents + reproduce note
  - LICENSE        : CC-BY-4.0 pointer
  - zenodo.json    : Zenodo deposition metadata (creators = Anonymous)
  - upload.sh      : curl-based Zenodo API upload from MANIFEST (needs $ZENODO_TOKEN)

It does NOT copy or zip the rasters (they stay in place; upload.sh streams them
directly), so it is safe to run while other jobs touch the outputs of OTHER cities.

Usage:  python scripts/_zenodo_package_city.py singapore kuala_lumpur bangkok
        python scripts/_zenodo_package_city.py jakarta        # after the depth-cap re-solve
        python scripts/_zenodo_package_city.py all
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys

import numpy as np
import rasterio

SCEN = ["ssp585_2020", "ssp245_2050", "ssp245_2100", "ssp585_2050", "ssp585_2100"]
RPS = [10, 100, 1000]

CITY = {
    "singapore": dict(name="Singapore", inputs=[
        "dem/_diag/singapore_seawall.tif",
        "dem/_hand/singapore_hand_v3_mainstem.tif", "dem/_hand/singapore_hand_v3_hybrid.tif",
        "data/singapore/sea_mask_utm48n_framefix.tif", "data/singapore/river_mask_utm48n.tif",
        "data/singapore/runoff_coeff_utm48n.tif"],
        globs=["data/singapore/hazard_levels_*.csv", "data/singapore/manifest/hotspots*.csv",
               "data/singapore/flood_obs/hotspots/*.csv"]),
    "kuala_lumpur": dict(name="Kuala Lumpur", inputs=[
        "dem/kl/dem_bareearth_kl_eth_present_conditioned.tif", "dem/_hand/kl_hand_mainstem_v3eth.tif",
        "data/kuala_lumpur/trunk_drainage_mask_utm47n.tif",
        "data/kuala_lumpur/sea_mask_utm47n.tif", "data/kuala_lumpur/drainage_waterways_utm47n.tif",
        "data/kuala_lumpur/runoff_coeff_utm47n.tif"],
        globs=["data/kuala_lumpur/hazard_levels_*.csv", "data/kuala_lumpur/manifest/hotspots*.csv"]),
    "jakarta": dict(name="Jakarta", inputs=[
        "dem/_diag/jakarta_seawall.tif",
        "dem/_hand/jakarta_hand_v3_mainstem.tif", "dem/_hand/jakarta_hand_v3.tif",
        "data/jakarta/sea_mask_utm48s_framefix.tif", "data/jakarta/river_mask_utm48s.tif",
        "data/jakarta/runoff_coeff_utm48s.tif"],
        globs=["data/jakarta/hazard_levels_*.csv", "data/jakarta/manifest/hotspots*.csv"]),
    "bangkok": dict(name="Bangkok", inputs=[
        "dem/_diag/bangkok_seawall.tif", "dem/_hand/hand_trunk_v3_debiased.tif",
        "dem/_hand/bangkok_pumped_polder_mask.tif",
        "data/bangkok/sea_mask_utm47n_framefix.tif", "data/bangkok/river_mask_utm47n.tif",
        "data/bangkok/runoff_coeff_utm47n.tif"],
        globs=["data/bangkok/hazard_levels_*.csv", "data/bangkok/manifest/hotspots*.csv"]),
}

README = """# Open Multi-Hazard Flood Atlas — {name}

Design-event **coastal, fluvial, and pluvial** flood-depth maps at **30 m** for {name},
for the present day and four climate combinations (SSP2-4.5 / SSP5-8.5 x 2050 / 2100) at
three return periods (RP10 / RP100 / RP1000). One city of an open, validated four-city
ASEAN atlas accompanying a manuscript by Daniel Phang (Independent Researcher, Singapore).

## Contents
- `maps/{city}_<scenario>_rp<rp>/<hazard>/` -- per-hazard flood **depth** (m, GeoTIFF) and
  **severity** class rasters, with a per-cell `summary_*.csv` (flooded area km2, mean/max
  depth). Hazards: coastal (local-inertia shallow water), fluvial (HAND), pluvial
  (fill-spill or HAND-handfill). Scenario `ssp585_2020` = present day.
- `inputs/` -- the license-clean bare-earth DEM, HAND raster(s), per-(scenario, return
  period) forcing (`hazard_levels_*.csv`), sea / river masks, the runoff-coefficient
  raster, and the frozen documented-hotspot validation register: everything needed to
  reproduce the maps from the open pipeline.

## Reporting conventions -- read before comparing with the manuscript

`summary_*.csv` and the manuscript count flooded area at **different depth thresholds**, so
the same cell and hazard legitimately carries two different numbers:

| Source | Wet-cell rule | Rationale |
| --- | --- | --- |
| `summary_*.csv` (`flooded_area_km2`, `wet_pixels`, `mean_depth_m`, `max_depth_m`) | `depth > 0` | The model engine's native wet-cell definition. |
| The manuscript's extent tables | `depth >= 0.10 m` | Screening threshold: suppresses the sub-decimetre film the fill-spill / HAND solvers leave over near-flat terrain. |

Neither is authoritative -- **the depth rasters are**. Both numbers derive from the same
shipped `*_depth_*.tif`, so either is reproducible:

```python
import rasterio, numpy as np
a = rasterio.open(
    "maps/{city}_ssp585_2100_rp100/pluvial/pluvial_depth_SSP5-8.5_2100_rp100.tif"
).read(1)
px = 900  # 30 m cells on a projected UTM grid -> 900 m2 each
gt0 = float((np.isfinite(a) & (a >  0.00)).sum()) * px / 1e6   # {gt0} km2  <- summary_*.csv
ge  = float((np.isfinite(a) & (a >= 0.10)).sum()) * px / 1e6   # {ge} km2  <- manuscript
```

For this cell the two conventions differ by {gap} km2 -- entirely cells shallower than
0.10 m. Apply the same threshold to both sides before comparing this dataset with another.

## Reproduce
Every input derives from free, openly-licensed sources (Copernicus DEM, ERA5-Land,
GloFAS, IPCC AR6 sea level, ESA WorldCover, and national IDF standards). The maps are
produced by the open pipeline released separately. See the accompanying manuscript for
the full methodology, the model-blind validation gate, and per-city parameters.

## License
**CC-BY-4.0** (this dataset). See `LICENSE`.

## Citation
Phang, Daniel (2026). *Open Multi-Hazard Flood Atlas -- {name}.* Zenodo. DOI reserved on
this record; please cite the DOI and the accompanying manuscript.
"""

LICENSE = ("This dataset is released under the Creative Commons Attribution 4.0 "
           "International License (CC-BY-4.0): https://creativecommons.org/licenses/by/4.0/\n")

UPLOAD = """#!/usr/bin/env bash
# Upload this city's flood-atlas record to Zenodo as a DRAFT deposition.
#   export ZENODO_TOKEN=<your token>   (zenodo.org -> Applications -> Personal access tokens, scope deposit:write)
#   bash upload.sh                     (then review + Publish on zenodo.org)
# Use https://sandbox.zenodo.org/api to rehearse first (set ZENODO_API).
set -euo pipefail
: "${ZENODO_TOKEN:?set ZENODO_TOKEN}"
API="${ZENODO_API:-https://zenodo.org/api}"
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
PY="C:/Users/Daniel/AppData/Local/Python/pythoncore-3.14-64/python.exe"
dep=$(curl -sf -H "Authorization: Bearer $ZENODO_TOKEN" -H "Content-Type: application/json" -X POST "$API/deposit/depositions" -d '{}')
id=$(echo "$dep"  | "$PY" -c "import sys,json;print(json.load(sys.stdin)['id'])")
bucket=$(echo "$dep" | "$PY" -c "import sys,json;print(json.load(sys.stdin)['links']['bucket'])")
echo "deposition $id"
curl -sf -H "Authorization: Bearer $ZENODO_TOKEN" -H "Content-Type: application/json" -X PUT "$API/deposit/depositions/$id" -d @"$HERE/zenodo.json" >/dev/null
tail -n +2 "$HERE/MANIFEST.csv" | while IFS=, read -r src arch bytes; do
  curl -sf -H "Authorization: Bearer $ZENODO_TOKEN" --upload-file "$ROOT/$src" "$bucket/$arch" >/dev/null && echo "  + $arch"
done
echo "DRAFT ready -> review and Publish at: ${API%/api}/deposit/$id"
"""


def collect(slug):
    cfg = CITY[slug]
    files = []  # (src, arch)
    for stem in SCEN:
        for rp in RPS:
            base = f"outputs/_fixed_atlas/{slug}_{stem}_rp{rp}"
            d = base + "_polder" if slug == "bangkok" and os.path.isdir(base + "_polder") else base
            for hz in ("coastal", "fluvial", "pluvial"):
                for f in sorted(glob.glob(f"{d}/{hz}/rp_{rp}/*.tif")):
                    files.append((f, f"maps/{slug}_{stem}_rp{rp}/{hz}/{os.path.basename(f)}"))
            for f in sorted(glob.glob(f"{d}/summary_*.csv")):
                files.append((f, f"maps/{slug}_{stem}_rp{rp}/{os.path.basename(f)}"))
    for f in cfg["inputs"]:
        if os.path.exists(f):
            files.append((f, f"inputs/{os.path.basename(f)}"))
        else:
            print(f"  [warn] missing input: {f}")
    for g in cfg["globs"]:
        for f in sorted(glob.glob(g)):
            files.append((f, f"inputs/{os.path.basename(f)}"))
    return files


def threshold_figs(slug):
    """Measure the >0 vs >=0.10 m gap on the exact cell the README's worked example cites.

    Measured at stage time, from the raster this package actually SHIPS (note the same
    _polder preference collect() uses for Bangkok), so the README can never drift from the
    data the way a hard-coded number would.
    """
    base = f"outputs/_fixed_atlas/{slug}_ssp585_2100_rp100"
    d = base + "_polder" if slug == "bangkok" and os.path.isdir(base + "_polder") else base
    hits = glob.glob(f"{d}/pluvial/rp_*/pluvial_depth_*.tif")
    if not hits:
        raise SystemExit(f"threshold_figs: no pluvial depth raster under {d}")
    with rasterio.open(hits[0]) as ds:
        a = ds.read(1)
        px = abs(ds.transform.a * ds.transform.e)
    gt0 = float(np.count_nonzero(np.isfinite(a) & (a > 0.0))) * px / 1e6
    ge = float(np.count_nonzero(np.isfinite(a) & (a >= 0.10))) * px / 1e6
    return gt0, ge


def stage(slug):
    cfg = CITY[slug]
    out = f"zenodo/{slug}"
    os.makedirs(out, exist_ok=True)
    files = collect(slug)
    total = sum(os.path.getsize(s) for s, _ in files)
    with open(f"{out}/MANIFEST.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["source_path", "archive_name", "bytes"])
        for s, a in files:
            w.writerow([s.replace("\\", "/"), a, os.path.getsize(s)])
    gt0, ge = threshold_figs(slug)
    open(f"{out}/README.md", "w", encoding="utf-8").write(README.format(
        name=cfg["name"], city=slug,
        gt0=f"{gt0:.1f}", ge=f"{ge:.1f}", gap=f"{gt0 - ge:.1f}"))
    open(f"{out}/LICENSE", "w", encoding="utf-8").write(LICENSE)
    open(f"{out}/upload.sh", "w", encoding="utf-8", newline="\n").write(UPLOAD)
    meta = {"metadata": {
        "title": f"Open Multi-Hazard Flood Atlas -- {cfg['name']} (30 m; present + SSP2-4.5/SSP5-8.5 x 2050/2100; RP10/100/1000)",
        "upload_type": "dataset",
        "description": (f"Design-event coastal, fluvial and pluvial flood-depth maps at 30 m for {cfg['name']}, "
                        "present-day and four climate scenarios at three return periods, plus the license-clean "
                        "bare-earth DEM, HAND, forcing, masks and validation register needed to reproduce them. "
                        "One city of an open four-city ASEAN atlas (Singapore, Kuala Lumpur, Bangkok, Jakarta)."),
        "creators": [{"name": "Phang, Daniel", "affiliation": "Independent Researcher",
                      "orcid": "0009-0006-3785-4458"}],
        "license": "cc-by-4.0",
        "access_right": "open",
        "version": "1.0",
        "keywords": ["flood hazard", "multi-hazard", "ASEAN", cfg["name"], "open data",
                     "climate scenarios", "coastal", "fluvial", "pluvial", "30 m"],
    }}
    json.dump(meta, open(f"{out}/zenodo.json", "w", encoding="utf-8"), indent=2)
    print(f"  {cfg['name']:13s}: {len(files):4d} files, {total/1e9:5.2f} GB  -> {out}/")
    return total


def main():
    args = sys.argv[1:] or ["all"]
    cities = list(CITY) if args == ["all"] else args
    print("=== staging per-city Zenodo records ===")
    grand = 0
    for c in cities:
        if c not in CITY:
            print(f"  [skip] unknown city {c}"); continue
        grand += stage(c)
    print(f"  TOTAL across staged cities: {grand/1e9:.2f} GB  (Zenodo per-record limit: 50 GB)")


if __name__ == "__main__":
    main()
