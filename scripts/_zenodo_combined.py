"""Create ONE combined Zenodo record for the whole four-city atlas -> a single DOI.

Uploads the four existing per-city zips (zenodo/<city>/<city>_flood_atlas.zip,
built by _zenodo_package_city.py + _zenodo_upload.py) plus a combined README and
LICENSE to a single draft deposition. Use this instead of four separate records
when one DOI should cover the whole atlas.

Usage:  python scripts/_zenodo_combined.py
Env:    ZENODO_API (default https://zenodo.org/api)
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.environ.get("ZENODO_API", "https://zenodo.org/api")
TOKEN = open(os.path.join(ROOT, "zenodo", ".token")).read().strip()
AUTH = {"Authorization": f"Bearer {TOKEN}"}
CITIES = [("singapore", "Singapore"), ("kuala_lumpur", "Kuala Lumpur"),
          ("bangkok", "Bangkok"), ("jakarta", "Jakarta")]

TITLE = ("Open Multi-Hazard Flood Atlas -- Singapore, Kuala Lumpur, Bangkok and Jakarta "
         "(30 m; present + SSP2-4.5/SSP5-8.5 x 2050/2100; RP10/100/1000)")
DESC = ("Design-event coastal, fluvial and pluvial flood-depth maps at 30 m for four ASEAN "
        "cities -- Singapore, Kuala Lumpur, Bangkok and Jakarta -- for the present day and "
        "four climate scenarios (SSP2-4.5 / SSP5-8.5 x 2050 / 2100) at three return periods "
        "(RP10 / RP100 / RP1000). Each city ships as a zip containing per-hazard flood-depth "
        "and severity rasters plus the license-clean bare-earth DEM, HAND, forcing, masks and "
        "the frozen documented-hotspot validation register needed to reproduce them from the "
        "open pipeline. Coastal uses a local-inertia shallow-water solver behind documented "
        "defences; fluvial uses main-stem HAND; pluvial is regime-matched (fill-and-spill for "
        "depression-storage cities, HAND-handfill for canal-dense cities). Accompanies a "
        "manuscript by Daniel Phang (Independent Researcher, Singapore).")

README = """# Open Multi-Hazard Flood Atlas -- Singapore, Kuala Lumpur, Bangkok & Jakarta

Design-event **coastal, fluvial, and pluvial** flood-depth maps at **30 m** for four ASEAN
cities, for the present day and four climate combinations (SSP2-4.5 / SSP5-8.5 x 2050 / 2100)
at three return periods (RP10 / RP100 / RP1000). An open, validated four-city atlas
accompanying a manuscript by Daniel Phang (Independent Researcher, Singapore).

## Contents
One zip per city (extract to browse the per-hazard tree):
- `singapore_flood_atlas.zip`
- `kuala_lumpur_flood_atlas.zip`
- `bangkok_flood_atlas.zip`
- `jakarta_flood_atlas.zip`

Each zip contains:
- `maps/<city>_<scenario>_rp<rp>/<hazard>/` -- per-hazard flood **depth** (m, GeoTIFF) and
  **severity** class rasters, with a per-scenario `summary_*.csv` (flooded area km2, mean/max
  depth). Hazards: coastal (local-inertia shallow water), fluvial (main-stem HAND), pluvial
  (fill-spill or HAND-handfill). Scenario `ssp585_2020` = present day.
- `inputs/` -- the license-clean bare-earth DEM, HAND raster(s), per-(scenario, return period)
  forcing (`hazard_levels_*.csv`), sea / river masks, the runoff-coefficient raster, and the
  frozen documented-hotspot validation register.

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
a = rasterio.open("maps/<cell>/pluvial/pluvial_depth_<scenario>_<rp>.tif").read(1)
px = 900  # 30 m cells on a projected UTM grid -> 900 m2 each
gt0 = float((np.isfinite(a) & (a >  0.00)).sum()) * px / 1e6   # <- summary_*.csv
ge  = float((np.isfinite(a) & (a >= 0.10)).sum()) * px / 1e6   # <- manuscript
```

The gap is entirely cells shallower than 0.10 m; it is widest where the solver leaves a
sub-decimetre film over flat terrain (largest for Bangkok's pumped delta). Each city zip's
README carries a worked example with that city's own figures. Apply the same threshold to
both sides before comparing this dataset with another.

## Reproduce
Every input derives from free, openly-licensed sources (Copernicus DEM, ERA5-Land, GloFAS,
IPCC AR6 sea level, ESA WorldCover, and national IDF standards). See the accompanying
manuscript for the full methodology, the model-blind validation gate, and per-city parameters.

## License
**CC-BY-4.0** (this dataset). See `LICENSE`.

## Citation
Phang, Daniel (2026). *Open Multi-Hazard Flood Atlas -- Singapore, Kuala Lumpur, Bangkok &
Jakarta.* Zenodo. Please cite this record's DOI and the accompanying manuscript.
"""

LICENSE = ("This dataset is released under the Creative Commons Attribution 4.0 International "
           "License (CC-BY-4.0): https://creativecommons.org/licenses/by/4.0/\n")

META = {"metadata": {
    "title": TITLE,
    "upload_type": "dataset",
    "description": DESC,
    "creators": [{"name": "Phang, Daniel", "affiliation": "Independent Researcher",
                  "orcid": "0009-0006-3785-4458"}],
    "license": "cc-by-4.0",
    "access_right": "open",
    "version": "1.0",
    "keywords": ["flood hazard", "multi-hazard", "ASEAN", "Singapore", "Kuala Lumpur",
                 "Bangkok", "Jakarta", "open data", "climate scenarios", "coastal",
                 "fluvial", "pluvial", "30 m"],
}}


def req(method, url, data=None, headers=None, retries=3):
    hdrs = dict(AUTH)
    if headers:
        hdrs.update(headers)
    for attempt in range(1, retries + 1):
        r = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(r, timeout=900) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            b = e.read()
            if e.code >= 500 and attempt < retries:
                time.sleep(2 * attempt); continue
            raise SystemExit(f"HTTP {e.code} {method} {url}\n{b[:800].decode(errors='replace')}")
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(2 * attempt); continue
            raise SystemExit(f"conn error {method} {url}: {e}")


def main():
    cdir = os.path.join(ROOT, "zenodo", "_combined")
    os.makedirs(cdir, exist_ok=True)
    open(os.path.join(cdir, "README.md"), "w", encoding="utf-8").write(README)
    open(os.path.join(cdir, "LICENSE"), "w", encoding="utf-8").write(LICENSE)
    json.dump(META, open(os.path.join(cdir, "zenodo.json"), "w", encoding="utf-8"), indent=2)

    _, body = req("POST", f"{API}/deposit/depositions",
                  data=b"{}", headers={"Content-Type": "application/json"})
    dep = json.loads(body)
    did = dep["id"]
    bucket = dep["links"]["bucket"]
    doi = dep["metadata"].get("prereserve_doi", {}).get("doi", "?")
    print(f"draft {did}  reserved DOI {doi}")
    req("PUT", f"{API}/deposit/depositions/{did}",
        data=json.dumps(META).encode(), headers={"Content-Type": "application/json"})
    print("metadata set")

    files = [(f"{slug}_flood_atlas.zip", os.path.join(ROOT, "zenodo", slug, f"{slug}_flood_atlas.zip"))
             for slug, _ in CITIES]
    files += [("README.md", os.path.join(cdir, "README.md")),
              ("LICENSE", os.path.join(cdir, "LICENSE"))]
    for name, path in files:
        with open(path, "rb") as f:
            payload = f.read()
        req("PUT", f"{bucket}/{name}", data=payload,
            headers={"Content-Type": "application/octet-stream"})
        print(f"  + {name} ({os.path.getsize(path) / 1e6:.1f} MB)")
    print(f"\nDONE -> DRAFT {dep['links']['html']}")
    print(f"        reserved DOI {doi}")


if __name__ == "__main__":
    main()
