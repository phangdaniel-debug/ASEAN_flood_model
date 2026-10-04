"""Patch one hazard's rows in an atlas cell's summary CSV from a re-run temp summary.

Usage:  _patch_summary_hazard.py <atlas_cell_dir> <tmp_dir> <hazard_type>

When a single hazard layer is re-run (e.g. handfill pluvial with stage scaling, or the
coastal depth-cap fix) into a temp out-dir, its rasters are copied into the existing
atlas cell but the cell's summary_*.csv still carries the OLD stats for that hazard.
This copies the per-RP statistic columns (areas, depths, wet_pixels, water_level_m) for
the named hazard from the temp run's summary into the atlas cell's summary, leaving the
raster-path columns and every OTHER hazard's rows untouched.

Used by repro/rerun_handfill_scaled.sh.
"""
import csv
import glob
import os
import sys

STAT = (
    "water_level_m", "flooded_area_m2", "flooded_area_km2", "mean_depth_m",
    "max_depth_m", "wet_pixels", "minor_area_km2", "moderate_area_km2",
    "major_area_km2", "severe_area_km2",
)


def _summary(d):
    g = glob.glob(os.path.join(d, "summary_*.csv"))
    if not g:
        raise SystemExit(f"no summary_*.csv in {d}")
    return g[0]


def main():
    cell, tmp, hz = sys.argv[1], sys.argv[2], sys.argv[3]
    new = {}
    with open(_summary(tmp), newline="") as f:
        for r in csv.DictReader(f):
            if r["hazard_type"] == hz:
                new[r["return_period"]] = r
    cell_csv = _summary(cell)
    with open(cell_csv, newline="") as f:
        rd = csv.DictReader(f)
        fields = rd.fieldnames
        rows = list(rd)
    n = 0
    for r in rows:
        if r["hazard_type"] == hz and r["return_period"] in new:
            src = new[r["return_period"]]
            for k in STAT:
                if k in r and k in src:
                    r[k] = src[k]
            n += 1
    with open(cell_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"    patched {n} {hz} row(s) in {os.path.basename(cell_csv)}")


if __name__ == "__main__":
    main()
