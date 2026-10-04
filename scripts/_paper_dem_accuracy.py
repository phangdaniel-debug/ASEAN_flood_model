"""DEM-accuracy table data for the SAFE paper (§6): held-out MAE/bias for
DSM vs adopted bare-earth vs (Singapore) DeltaDTM/hybrid, overall + urban-core.

Samples each terrain at the held-out lidar points and compares to h_egm2008.
Run: python scripts/_paper_dem_accuracy.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform as wt

ROOT = Path(__file__).resolve().parents[1]

CITY = {  # city: (points, dsm, bareearth, deltadtm-or-hybrid-or-None)
    "bangkok": ("dem/bangkok/calib/points_sampled.parquet",
                "data/bangkok/copernicus_dem_utm47n.tif",
                "dem/_hand/bangkok_v3_debiased_defended.tif", None),
    "jakarta": ("dem/jakarta/calib/points_sampled.parquet",
                "data/jakarta/copernicus_dem_utm48s.tif",
                "dem/jakarta/dem_bareearth_jakarta_present_conditioned.tif", None),
    "kl": ("dem/kl/calib_eth/points_sampled.parquet",
           "data/kuala_lumpur/copernicus_dem_utm47n.tif",
           "dem/kl/dem_bareearth_kl_eth_present_conditioned.tif", None),
    "singapore": ("dem/singapore/calib/points_sampled.parquet",
                  "data/singapore/copernicus_dem_utm48n.tif",
                  "dem/singapore/dem_bareearth_singapore_present_conditioned.tif",
                  "dem/_hand/singapore_hybrid_dem.tif"),
}


def samp(path, lons, lats):
    with rasterio.open(path) as r:
        xs, ys = wt("EPSG:4326", r.crs, list(lons), list(lats))
        A = r.read(1)
        out = []
        for x, y in zip(xs, ys):
            row, col = r.index(x, y)
            if 0 <= row < A.shape[0] and 0 <= col < A.shape[1]:
                v = A[row, col]
                out.append(np.nan if (r.nodata is not None and v == r.nodata) else float(v))
            else:
                out.append(np.nan)
    return np.array(out)


def stats(d, truth):
    m = np.isfinite(d) & np.isfinite(truth)
    if not m.sum():
        return (np.nan, np.nan, 0)
    r = (d - truth)[m]
    return (float(np.abs(r).mean()), float(r.mean()), int(m.sum()))


def main():
    print(f"{'city':9s} {'src':16s} {'MAE':>6} {'bias':>7} {'urbanMAE':>9} {'urbanbias':>10} {'n':>6}")
    for c, (pts, dsm, be, dd) in CITY.items():
        df = pd.read_parquet(ROOT / pts)
        ho = df[df["split"] == "holdout"] if "split" in df.columns else df
        truth = ho["h_egm2008"].values
        lons, lats = ho["lon"].values, ho["lat"].values
        urban = ho["zone"].values == "urban_core" if "zone" in ho.columns else np.zeros(len(ho), bool)
        sources = [("DSM", dsm), ("bare-earth", be)] + ([("DeltaDTM/hybrid", dd)] if dd else [])
        for label, path in sources:
            d = samp(str(ROOT / path), lons, lats)
            mae, bias, n = stats(d, truth)
            umae, ubias, un = stats(d[urban], truth[urban]) if urban.any() else (np.nan, np.nan, 0)
            print(f"{c:9s} {label:16s} {mae:6.2f} {bias:+7.2f} "
                  f"{umae:9.2f} {ubias:+10.2f} {n:>6}")
        print()


if __name__ == "__main__":
    main()
