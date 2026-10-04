"""Harvest flooded-extent (km2, >=0.10 m) per city x scenario x RP x hazard layer
for the HTML dashboard. Coastal/fluvial/pluvial come from the atlas rasters
(same _resolve logic as build_compound_exceedance); combined comes from the
compound marginal in outputs/_compound/extent_summary.csv.

Out: outputs/_viz/extents.json
"""
import csv
import glob
import json
from pathlib import Path

import numpy as np
import rasterio

RPS = [10, 100, 1000]
HZ = ["coastal", "fluvial", "pluvial"]
CITIES = ["bangkok", "jakarta", "kuala_lumpur", "singapore"]
SCENARIOS = ["present", "ssp245_2050", "ssp245_2100", "ssp585_2050", "ssp585_2100"]
WET = 0.10


def _resolve(city, scen, rp, hz):
    if scen == "present":
        stems = [f"{city}_present"] if rp == 100 else [f"{city}_ssp585_2020_rp{rp}"]
    else:
        stems = [f"{city}_{scen}"] if rp == 100 else [f"{city}_{scen}_rp{rp}"]
    cands = []
    for s in stems:
        for suff in (("_polder", "") if city == "bangkok" else ("",)):
            cands += glob.glob(f"outputs/{s}{suff}/{hz}/rp_{rp}/{hz}_depth_*_rp{rp}.tif")
    return cands[0] if cands else None


def km2(path):
    if path is None:
        return 0.0
    with rasterio.open(path) as r:
        a = r.read(1).astype("float64")
        if r.nodata is not None:
            a[a == r.nodata] = 0.0
        a = np.nan_to_num(a, nan=0.0)
        px = abs(r.transform.a) * abs(r.transform.e)
        return round(float((a >= WET).sum()) * px / 1e6, 1)


def load_combined():
    p = Path("outputs/_compound/extent_summary.csv")
    out = {}
    if p.exists():
        for row in csv.DictReader(open(p)):
            out[(row["city"], row["scenario"], int(row["rp"]))] = round(float(row["marginal_km2"]), 1)
    return out


def main():
    combined = load_combined()
    data = {}
    for c in CITIES:
        data[c] = {}
        for sc in SCENARIOS:
            data[c][sc] = {}
            for rp in RPS:
                rec = {hz: km2(_resolve(c, sc, rp, hz)) for hz in HZ}
                rec["combined"] = combined.get((c, sc, rp), round(max(rec.values()), 1))
                data[c][sc][rp] = rec
                print(f"{c:13s} {sc:12s} RP{rp:<5d} "
                      f"C={rec['coastal']:7.1f} F={rec['fluvial']:7.1f} "
                      f"P={rec['pluvial']:7.1f} -> comb={rec['combined']:7.1f}")
    outp = Path("outputs/_viz/extents.json")
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(data, indent=1))
    print(f"\nwrote {outp}")


if __name__ == "__main__":
    main()
