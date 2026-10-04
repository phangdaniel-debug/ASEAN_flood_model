"""
Phase 1 DEM validation + decision gate (spec §1.5).

Samples the BUILT bare-earth DEM at the HELD-OUT ground points (never the
calibration points), reports per-zone signed bias / MAE / RMSE / check-point
count, optionally cross-checks the coastal-flat zone against DeltaDTM, and emits
the §1.5 gate verdict (PASS single-DEM / FIX / FALL BACK to a coastal composite).

Honesty requirement: the urban-core check-point COUNT is reported prominently —
ICESat-2/GEDI are sparsest exactly where building removal is the value-add.

Tolerances are screening defaults (tunable); coastal target ≈ DeltaDTM ~0.45 m MAE.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

from raster_utils import sample_points, read_aligned


def zone_stats(resid: np.ndarray) -> dict:
    r = resid[np.isfinite(resid)]
    if len(r) == 0:
        return {"n": 0}
    return {"n": int(len(r)), "bias_m": float(r.mean()),
            "mae_m": float(np.abs(r).mean()),
            "rmse_m": float(np.sqrt((r ** 2).mean())),
            "p5_m": float(np.percentile(r, 5)), "p95_m": float(np.percentile(r, 95))}


def main():
    ap = argparse.ArgumentParser()
    base = r"D:\GPTs\Projects\flood-v3.0\dem\bangkok"
    ap.add_argument("--bareearth", default=rf"{base}\dem_bareearth_bangkok.tif")
    ap.add_argument("--points", default=rf"{base}\calib\points_sampled.parquet",
                    help="calibrate_dem.py output; uses split=='holdout' rows.")
    ap.add_argument("--deltadtm", default=rf"{base}\auxdata\deltadtm_bangkok.tif",
                    help="optional coastal benchmark for the cross-check.")
    ap.add_argument("--out", default=rf"{base}\dem_validation_bangkok")
    # gate tolerances (screening defaults)
    ap.add_argument("--coastal-mae-tol", type=float, default=0.60)
    ap.add_argument("--bias-tol", type=float, default=0.50)
    ap.add_argument("--inland-mae-tol", type=float, default=1.50)
    ap.add_argument("--urban-min-points", type=int, default=30)
    ap.add_argument("--urban-bias-tol", type=float, default=0.50,
                    help="Max |urban-core bias| (m). Over-removed buildings bias the CBD "
                         "low and inflate coastal flood extent on pumped/dyked deltas — the "
                         "zone the flood gate is most sensitive to (added after the Bangkok "
                         "v3 finding: -0.88 m urban bias passed the old gate).")
    ap.add_argument("--highground-elev", type=float, default=30.0,
                    help="Elevation (m) above which held-out points are treated as 'high "
                         "ground' for the vertical-coverage-cap check.")
    ap.add_argument("--highground-bias-tol", type=float, default=2.0,
                    help="Max under-representation (m) of high ground before flagging a "
                         "vertical-coverage cap. Products like DeltaDTM cap at ~30 m, so the "
                         "interior hills read far too low, collapsing their HAND and spuriously "
                         "fluvial-flooding the highest dry controls (added after the Singapore "
                         "finding: hills capped at 30 m vs 50-85 m truth → -9 to -29 m bias). "
                         "Flood-depth is unaffected (low terrain), but the HAND/fluvial needs a "
                         "high-ground composite before use.")
    ap.add_argument("--highground-min-points", type=int, default=20,
                    help="Min high-ground check-points before the coverage-cap gate is binding.")
    args = ap.parse_args()

    df = pd.read_parquet(args.points)
    ho = df[df["split"] == "holdout"].copy()
    if not len(ho):
        raise SystemExit("no holdout points")

    with rasterio.open(args.bareearth) as src:
        dem_crs = src.crs
    to_dem = Transformer.from_crs("EPSG:4326", dem_crs, always_xy=True)
    xs, ys = to_dem.transform(ho["lon"].values, ho["lat"].values)
    ho["be"] = sample_points(args.bareearth, xs, ys)
    ho["resid"] = ho["be"] - ho["h_egm2008"]
    ho = ho[np.isfinite(ho["resid"])]

    zones = {z: zone_stats(g["resid"].values) for z, g in ho.groupby("zone")}
    overall = zone_stats(ho["resid"].values)

    # Optional DeltaDTM coastal cross-check (raster-level, coastal-flat only).
    coastal_xcheck = None
    if Path(args.deltadtm).exists():
        with rasterio.open(args.bareearth) as src:
            be = src.read(1).astype("float64")
            if src.nodata is not None:
                be = np.where(be == src.nodata, np.nan, be)
            dd = read_aligned(args.deltadtm, src, "bilinear")
        m = np.isfinite(be) & np.isfinite(dd) & (be <= 10.0)  # coastal-flat band
        d = (be - dd)[m]
        if len(d):
            coastal_xcheck = {"n_cells": int(len(d)), "mae_m": float(np.abs(d).mean()),
                              "bias_m": float(d.mean())}

    # Gate logic (spec §1.5).
    coastal = zones.get("coastal_flat", {"n": 0})
    veg = zones.get("vegetated", {"n": 0})
    urban = zones.get("urban_core", {"n": 0})
    reasons = []
    coastal_ok = coastal.get("n", 0) > 0 and coastal["mae_m"] <= args.coastal_mae_tol \
        and abs(coastal["bias_m"]) <= args.bias_tol
    veg_ok = veg.get("n", 0) > 0 and abs(veg["bias_m"]) <= args.bias_tol
    inland_ok = (zones.get("other", {}).get("mae_m", 1e9) <= args.inland_mae_tol)
    urban_enough = urban.get("n", 0) >= args.urban_min_points
    # Urban-core bias gate (only meaningful when enough ground truth constrains it).
    urban_bias_ok = (not urban_enough) or abs(urban.get("bias_m", 0.0)) <= args.urban_bias_tol

    # Vertical-coverage-cap gate (added after the Singapore DeltaDTM finding): held-out
    # points above --highground-elev whose DEM reads far too low signal a product cap that
    # collapses the HAND on the interior hills. Flood-depth uses low terrain (unaffected),
    # but the fluvial HAND must be built on a high-ground composite first.
    highground = zone_stats(ho.loc[ho["h_egm2008"] > args.highground_elev, "resid"].values)
    n_highground = highground.get("n", 0)
    highground_constrained = n_highground >= args.highground_min_points
    highground_ok = (not highground_constrained) or \
        (highground.get("bias_m", 0.0) >= -args.highground_bias_tol)

    if not urban_enough:
        reasons.append(f"urban_core check-points = {urban.get('n',0)} (< {args.urban_min_points}); "
                       "urban bias is under-constrained by ground truth (honesty flag, spec §1.5).")
    if urban_enough and not urban_bias_ok:
        reasons.append(f"urban_core bias {urban.get('bias_m'):+.2f} m exceeds ±{args.urban_bias_tol} m "
                       "(building over/under-removal). The CBD is the terrain the coastal flood gate "
                       "is most sensitive to on pumped/dyked deltas — re-condition the urban core "
                       "toward the held-out points before flood use.")
    if not veg_ok and veg.get("n", 0) > 0:
        reasons.append(f"vegetated bias {veg.get('bias_m'):+.2f} m off → recalibrate f.")
    if not coastal_ok and coastal.get("n", 0) > 0:
        reasons.append(f"coastal MAE {coastal.get('mae_m'):.2f} m / bias {coastal.get('bias_m'):+.2f} m "
                       "outside tolerance.")
    if highground_constrained and not highground_ok:
        reasons.append(f"high-ground (>{args.highground_elev:.0f} m) bias {highground.get('bias_m'):+.2f} m "
                       f"over {n_highground} pts → VERTICAL COVERAGE CAP: the DEM under-represents the "
                       "interior hills (product capped below the terrain range), collapsing their HAND. "
                       "Flood-depth is unaffected, but composite the high ground (e.g. the DSM) before "
                       "building the fluvial HAND.")

    urban_flag = "" if urban_bias_ok else \
        f" — URBAN-CORE BIAS {urban.get('bias_m'):+.2f} m: re-condition CBD before flood use"
    highground_flag = "" if highground_ok else \
        f" — HIGH-GROUND COVERAGE CAP {highground.get('bias_m'):+.2f} m: composite high ground before HAND/fluvial use"
    caveats = urban_flag + highground_flag
    if coastal_ok and veg_ok and inland_ok:
        if urban_enough and urban_bias_ok and highground_ok:
            verdict = "PASS (single DEM)"
        elif not urban_enough:
            verdict = "PASS-WITH-CAVEAT (single DEM; weak urban ground truth)" + highground_flag
        else:
            verdict = "PASS-WITH-CAVEAT (single DEM)" + caveats
    elif not coastal_ok and (veg_ok and inland_ok):
        verdict = "FALL BACK (DeltaDTM coastal-flat + candidate inland, seam-smooth ~10 m)" + caveats
    else:
        verdict = "FIX (recalibrate f / revisit backfill — see reasons)" + highground_flag

    report = {
        "bareearth": args.bareearth,
        "n_holdout": int(len(ho)),
        "overall": overall,
        "zones": zones,
        "coastal_deltadtm_xcheck": coastal_xcheck,
        "tolerances": {"coastal_mae": args.coastal_mae_tol, "bias": args.bias_tol,
                       "inland_mae": args.inland_mae_tol, "urban_min_points": args.urban_min_points},
        "gate": {"verdict": verdict, "reasons": reasons,
                 "coastal_ok": coastal_ok, "veg_ok": veg_ok,
                 "inland_ok": inland_ok, "urban_enough": urban_enough,
                 "urban_bias_ok": urban_bias_ok,
                 "highground_ok": highground_ok, "highground": highground},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out + ".json").write_text(json.dumps(report, indent=2))
    # tidy per-zone CSV too
    rows = [{"zone": z, **s} for z, s in zones.items()]
    pd.DataFrame(rows).to_csv(args.out + ".csv", index=False)

    print(json.dumps(report, indent=2))
    print(f"\nGATE: {verdict}")
    print(f"wrote {args.out}.json / .csv")


if __name__ == "__main__":
    main()
