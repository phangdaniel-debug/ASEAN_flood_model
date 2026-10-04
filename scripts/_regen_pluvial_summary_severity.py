"""Derive the pluvial severity raster + summary CSV row from the FINAL pluvial depth.

Runs LAST in the STAGE-2 chain (see repro/run_atlas_fixed.sh), after every apply that
writes pluvial_depth_*.tif. This script is READ-ONLY on the depth raster:

 1. Recomputes the pluvial severity raster with the engine's own classify_depth_severity
    (bands 0.15 / 0.50 / 1.00 m; nodata 255).
 2. Recomputes the pluvial summary row (areas, depths, wet_pixels, per-severity areas) with
    the engine's own summarize_depth / severity_area_stats, and rewrites ONLY the pluvial
    line of each summary_*.csv (all other hazard rows kept byte-identical).

WHY IT NO LONGER TOUCHES THE DEPTH RASTER (2026-07-13)
------------------------------------------------------
Until now this script also "restored" each cell's valid-data footprint from the *.orig
sidecar. That was a one-time repair for footprint damage the 2026-07-04 canal-HAND apply
introduced, and it was only ever correct while this script ran IMMEDIATELY after that apply.

The 2026-07-07 bridge-closing invalidated it. *.orig holds the PRE-canal-HAND footprint,
but the closing deliberately keeps bridged cells that fall OUTSIDE it
(_apply_city_pluvial_closing.py: `new[~np.isfinite(d) & ~bridged] = np.nan`). Re-masking to
the *.orig footprint therefore DELETED legitimate bridged cells: measured on
jakarta_ssp585_2100_rp100, it silently cut the pluvial extent by 2.81 km2 (337.2 -> 334.4 km2
at >=0.10 m), taking it away from the published Table 2 value of 337.

The footprint is the applies' business, not this script's. The depth raster as the chain
leaves it is authoritative; this step only derives products from it.
"""
import glob
import os
import sys
from pathlib import Path

import numpy as np
import rasterio

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def classify_depth_severity(depth):
    out = np.full(depth.shape, 255, dtype=np.uint8)
    finite = np.isfinite(depth)
    out[finite & (depth <= 0.0)] = 0
    out[finite & (depth > 0.0) & (depth <= 0.15)] = 1
    out[finite & (depth > 0.15) & (depth <= 0.50)] = 2
    out[finite & (depth > 0.50) & (depth <= 1.00)] = 3
    out[finite & (depth > 1.00)] = 4
    return out


def summarize_and_severity(depth, transform):
    """Engine-identical stats. pixel_area = |a*e| (all city CRS are projected UTM)."""
    pa = float(abs(transform.a * transform.e))
    wet = np.isfinite(depth) & (depth > 0)
    n = int(np.count_nonzero(wet))
    depth_stats = {
        "flooded_area_m2": n * pa,
        "flooded_area_km2": n * pa / 1_000_000.0,
        "mean_depth_m": float(np.nanmean(depth[wet])) if n else 0.0,
        "max_depth_m": float(np.nanmax(depth[wet])) if n else 0.0,
        "wet_pixels": n,
    }
    sev = classify_depth_severity(depth)
    sev_stats = {}
    for value, label in [(1, "minor"), (2, "moderate"), (3, "major"), (4, "severe")]:
        c = int(np.count_nonzero(sev == value))
        sev_stats[f"{label}_area_km2"] = c * pa / 1_000_000.0
    return depth_stats, sev_stats, sev


# summary column -> which recomputed value (order fixed by the engine's header)
RECOMPUTED = ["flooded_area_m2", "flooded_area_km2", "mean_depth_m", "max_depth_m",
              "wet_pixels", "minor_area_km2", "moderate_area_km2", "major_area_km2",
              "severe_area_km2"]


def rewrite_summary(summary_path, new_vals):
    raw = open(summary_path, "r", encoding="utf-8", newline="").read()
    term = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(term)
    header = lines[0].split(",")
    ci = {name: i for i, name in enumerate(header)}
    out_lines = []
    changed = 0
    for ln in lines:
        if ln.startswith("pluvial,"):
            f = ln.split(",")
            for name in RECOMPUTED:
                v = new_vals[name]
                f[ci[name]] = str(int(v)) if name == "wet_pixels" else str(v)
            out_lines.append(",".join(f))
            changed += 1
        else:
            out_lines.append(ln)
    assert changed == 1, f"expected 1 pluvial row, found {changed} in {summary_path}"
    open(summary_path, "w", encoding="utf-8", newline="").write(term.join(out_lines))


def process(city_glob):
    cells = sorted(glob.glob(f"outputs/_fixed_atlas/{city_glob}"))
    for cell in cells:
        dps = glob.glob(f"{cell}/pluvial/rp_*/pluvial_depth_*.tif")
        summ = glob.glob(f"{cell}/summary_*.csv")
        if not dps or not summ:
            print(f"  {os.path.basename(cell)}: missing pluvial/summary, SKIP")
            continue
        dp = dps[0]
        # READ-ONLY: the depth raster as the STAGE-2 chain leaves it is authoritative.
        # Never re-mask it to the *.orig footprint here — that wipes the closing's
        # bridged cells. See the module docstring.
        with rasterio.open(dp) as ds:
            depth = ds.read(1)
            prof = ds.profile
            transform = ds.transform
        # 1. severity raster
        depth_stats, sev_stats, sev = summarize_and_severity(depth, transform)
        sev_path = glob.glob(f"{cell}/pluvial/rp_*/pluvial_severity_*.tif")[0]
        sprof = prof.copy()
        sprof.update(dtype="uint8", count=1, compress="deflate", nodata=255)
        with rasterio.open(sev_path, "w", **sprof) as dst:
            dst.write(sev, 1)
        # 3. summary row
        rewrite_summary(summ[0], {**depth_stats, **sev_stats})
        print(f"  {os.path.basename(cell)}: wet {depth_stats['wet_pixels']} px, "
              f"{depth_stats['flooded_area_km2']:.1f} km2 | sev "
              f"m/M/j/s = {sev_stats['minor_area_km2']:.1f}/{sev_stats['moderate_area_km2']:.1f}/"
              f"{sev_stats['major_area_km2']:.1f}/{sev_stats['severe_area_km2']:.1f}", flush=True)


if __name__ == "__main__":
    # ALL FOUR cities: the 2026-07-07 bridge-closing changed every city's pluvial
    # extent, so every city's summary/severity must be regenerated — not just the two
    # that got the canal-HAND. (Before 2026-07-13 this ran for KL+Jakarta only and
    # BEFORE the closing, which left all four summaries stale vs their rasters:
    # SG 95.1 vs 111.2, KL 262.3 vs 296.2, BKK 264.6 vs 229.8, JKT 252.7 vs 297.6 km²
    # at RP100/2020.) Run this LAST in the chain — see repro/run_atlas_fixed.sh.
    for cg in ("kuala_lumpur_*", "jakarta_*", "singapore_*", "bangkok_*"):
        print(f"=== {cg} ===", flush=True)
        process(cg)
    print("DONE")
