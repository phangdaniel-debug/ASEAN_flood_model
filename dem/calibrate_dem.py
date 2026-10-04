"""
Phase 1 DEM calibration (spec §1.5): fit the X-band canopy penetration fraction f
and characterise the GLO-30 DSM error by zone, using ICESat-2/GEDI ground truth.

Error model (spec §1.1):   GLO30 ≈ true_ground + building_height + f·canopy_height
In vegetated, non-built areas building_height≈0, so:
    residual = GLO30 − ground_truth ≈ a + f·canopy_height
(a = systematic DSM−truth bias; f ∈ [0,1] = penetration fraction).

Both GLO-30 (native EGM2008) and the ground points (reconciled to EGM2008 by
extract_ground_points.py) are on the same datum, so they difference directly.

Outputs (dem/bangkok/calib/):
  points_sampled.parquet   ground points + sampled DSM/canopy/bcov/landcover + zone + split
  calibration.json         fitted f (+ per-density-bin), intercept, zone residual stats, gate inputs
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

from raster_utils import sample_points

# WorldCover classes (10 tree, 20 shrub, 30 grass, 40 crop, 50 built, 60 bare,
# 70 snow, 80 water, 90 wetland, 95 mangrove, 100 moss)
WC_VEG = {10, 20, 30, 40, 90, 95}
WC_BUILT = {50}
WC_WATER = {80}


def load_ground_points(gt_dir: Path, sources=("atl08", "gedi")) -> pd.DataFrame:
    names = {"atl08": "atl08_ground_points.parquet", "gedi": "gedi_ground_points.parquet"}
    frames = []
    for s in sources:
        p = gt_dir / names[s]
        if p.exists():
            df = pd.read_parquet(p)
            if len(df):
                frames.append(df[["lon", "lat", "h_egm2008", "source"]])
    if not frames:
        raise SystemExit(f"no ground-point parquets for {sources} in {gt_dir}")
    return pd.concat(frames, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    base = r"D:\GPTs\Projects\flood-v3.0\dem\bangkok"
    ap.add_argument("--gt-dir", default=rf"{base}\ground_truth")
    ap.add_argument("--glo30", default=rf"{base}\glo30_dsm_utm47n.tif",
                    help="RAW GLO-30 DSM (EGM2008) — the surface the error model describes.")
    ap.add_argument("--canopy", default=rf"{base}\auxdata\ETH_GlobalCanopyHeight_10m_2020_N12E099_Map.tif")
    ap.add_argument("--bcov", default=rf"{base}\auxdata\building_coverage_utm47n.tif")
    ap.add_argument("--worldcover", default=rf"{base}\auxdata\worldcover_2021_N12E099.tif")
    ap.add_argument("--out", default=rf"{base}\calib")
    ap.add_argument("--sources", default="atl08,gedi",
                    help="comma list: atl08,gedi (ATL08 is cleaner terrain; GEDI is "
                         "under-canopy-biased — prefer atl08 for the f-fit).")
    ap.add_argument("--holdout", type=float, default=0.30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--coastal-flat-max-m", type=float, default=2.0,
                    help="EGM2008 elevation (m) below which a point is 'coastal-flat'.")
    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    sources = tuple(s.strip() for s in args.sources.split(",") if s.strip())
    df = load_ground_points(Path(args.gt_dir), sources)
    print(f"ground points: {len(df)} ({df['source'].value_counts().to_dict()})")

    # Project lon/lat to the GLO-30 CRS (UTM) for UTM rasters; keep lon/lat for 4326 rasters.
    with rasterio.open(args.glo30) as src:
        dem_crs = src.crs
    to_utm = Transformer.from_crs("EPSG:4326", dem_crs, always_xy=True)
    x_utm, y_utm = to_utm.transform(df["lon"].values, df["lat"].values)

    def _sample_in_native_crs(path):
        """Sample a raster using coords in ITS OWN CRS. ETH/WorldCover native tiles
        are EPSG:4326 (sample with lon/lat); KL's canopy/worldcover were warped onto
        the UTM DEM grid (sample with x_utm/y_utm). sample_points does no reprojection,
        so picking the matching coord pair is required."""
        with rasterio.open(path) as r:
            rcrs = r.crs
        if rcrs is not None and rcrs.to_epsg() == 4326:
            return sample_points(path, df["lon"].values, df["lat"].values)
        if rcrs is not None and rcrs == dem_crs:
            return sample_points(path, x_utm, y_utm)
        # General case: reproject query lon/lat into the raster's CRS.
        tr = Transformer.from_crs("EPSG:4326", rcrs, always_xy=True)
        rx, ry = tr.transform(df["lon"].values, df["lat"].values)
        return sample_points(path, rx, ry)

    df["dsm"] = sample_points(args.glo30, x_utm, y_utm)
    df["bcov"] = sample_points(args.bcov, x_utm, y_utm) if Path(args.bcov).exists() else np.nan
    df["canopy"] = _sample_in_native_crs(args.canopy) if Path(args.canopy).exists() else np.nan
    df["lc"] = _sample_in_native_crs(args.worldcover) if Path(args.worldcover).exists() else np.nan

    # ETH canopy nodata is 255; clamp obvious fill.
    df.loc[df["canopy"] >= 255, "canopy"] = np.nan
    df["canopy"] = df["canopy"].fillna(0.0).clip(lower=0)
    df["bcov"] = df["bcov"].fillna(0.0)

    df = df[np.isfinite(df["dsm"])].copy()
    df["residual"] = df["dsm"] - df["h_egm2008"]

    # Drop water + gross outliers.
    df = df[(df["lc"] != 80) | df["lc"].isna()]
    df = df[df["residual"].between(-15, 40)].copy()
    print(f"usable points after QC: {len(df)}")

    # Zones (spec §1.5).
    df["zone"] = "other"
    df.loc[df["h_egm2008"] <= args.coastal_flat_max_m, "zone"] = "coastal_flat"
    df.loc[df["bcov"] > 0.25, "zone"] = "urban_core"
    df.loc[(df["canopy"] > 3.0) & (df["bcov"] < 0.05), "zone"] = "vegetated"

    # Hold out 30% (seeded), never calibrate on validation points.
    rng = np.random.default_rng(args.seed)
    df["split"] = np.where(rng.random(len(df)) < args.holdout, "holdout", "calib")
    print("zones:", df["zone"].value_counts().to_dict(), flush=True)

    # (1) Global systematic offset bias0 = median residual on TRUE-GROUND calib
    # points (non-built, low-canopy). Captures datum/epoch/residual-subsidence and
    # is applied UNIFORMLY by the build — so the canopy term doesn't absorb (and
    # over-correct for) the flat offset, which is what over-dug vegetated areas.
    tg = df[(df["split"] == "calib") & (df["bcov"] < 0.05) & (df["canopy"] < 2.0)]
    bias0 = float(np.median(tg["residual"].values)) if len(tg) >= 30 else 0.0

    # (2) Fit f THROUGH THE ORIGIN on vegetated calib points: residual − bias0 = f·canopy.
    # Element-wise numpy only — np.linalg.lstsq segfaults in this env (BLAS DLL conflict).
    veg = df[(df["zone"] == "vegetated") & (df["split"] == "calib") & (df["canopy"] > 0)]
    fit = {"bias0_m": bias0, "n_trueground_calib": int(len(tg))}
    if len(veg) >= 30:
        c = veg["canopy"].values.astype("float64")
        r = veg["residual"].values.astype("float64") - bias0
        scc = float((c * c).sum())
        f = float((c * r).sum() / scc) if scc > 0 else 0.0
        f_clip = float(np.clip(f, 0.0, 1.0))
        fit.update({"f_raw": f, "f_clipped": f_clip, "n_veg_calib": int(len(veg))})
        bins = [3, 6, 10, 15, 25, 100]
        vb = veg.assign(cbin=pd.cut(veg["canopy"], bins), radj=r)
        fit["per_bin"] = {
            str(k): {"n": int(len(g)),
                     "mean_resid_minus_bias0_m": float(g["radj"].mean()),
                     "mean_canopy_m": float(g["canopy"].mean())}
            for k, g in vb.groupby("cbin", observed=True)}
    else:
        fit["warning"] = f"too few vegetated calib points ({len(veg)}) to fit f"

    # Per-zone RAW-DSM residual stats (baseline before correction), held-out only.
    ho = df[df["split"] == "holdout"]
    zone_stats = {}
    for z, g in df.groupby("zone"):
        gho = ho[ho["zone"] == z]
        zone_stats[z] = {
            "n_total": int(len(g)),
            "n_holdout": int(len(gho)),
            "raw_bias_m": float(g["residual"].mean()),
            "raw_mae_m": float(g["residual"].abs().mean()),
            "raw_rmse_m": float(np.sqrt((g["residual"] ** 2).mean())),
        }

    report = {
        "n_points": int(len(df)),
        "source_counts": {k: int(v) for k, v in df["source"].value_counts().items()},
        "f_fit": fit,
        "zones": zone_stats,
        "params": {"holdout": args.holdout, "seed": args.seed,
                   "coastal_flat_max_m": args.coastal_flat_max_m},
        "note": "f fit on vegetated non-built CALIB points only; zone stats on HOLDOUT. "
                "Urban-core check-point count is the honesty metric (spec §1.5).",
    }
    df.to_parquet(outdir / "points_sampled.parquet", index=False)
    (outdir / "calibration.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"\nwrote {outdir/'points_sampled.parquet'} and {outdir/'calibration.json'}")


if __name__ == "__main__":
    main()
