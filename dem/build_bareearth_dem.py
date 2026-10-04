"""
Phase 1 bare-earth DEM build (spec §1.4).

Error model:  GLO30 ≈ true_ground + building_height + f·canopy_height
So, on the raw GLO-30 DSM (EGM2008):
  1. **Vegetation** — subtract f·canopy_height (f from calibrate_dem.py) where canopy
     is present and the cell is not building-dominated.  (Calibrated subtraction, not
     naive full-canopy removal — avoids over-digging mangrove/green fringe.)
  2. **Buildings** — mask cells above a footprint-coverage threshold and backfill from
     **true-ground pixels only** (non-building, low-canopy), via nearest-true-ground
     (no blind averaging that pulls from adjacent buildings/canopy).
  3. **QA mask** — per-cell flags; wall-to-wall blocks far from any true-ground cell are
     flagged low-confidence backfill.

Optional: apply the v2.0 subsidence delta to emit a present-day DEM (kept SEPARATE
from horizon-accumulated DEMs per spec).

NB: uses scipy.ndimage (C, no BLAS) + GDAL warp only — avoids the env's BLAS crash.

Outputs (dem/bangkok/):
  dem_bareearth_bangkok[_present].tif
  dem_qa_bangkok.tif   (uint8 bitmask: 1=building-backfilled, 2=low-confidence
                        backfill, 4=canopy-corrected, 8=water)
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

from raster_utils import read_aligned

QA_BUILDING = 1
QA_LOWCONF = 2
QA_CANOPY = 4
QA_WATER = 8


def main():
    ap = argparse.ArgumentParser()
    base = r"D:\GPTs\Projects\flood-v3.0\dem\bangkok"
    ap.add_argument("--glo30", default=rf"{base}\glo30_dsm_utm47n.tif",
                    help="RAW GLO-30 DSM (EGM2008, UTM) — base surface.")
    ap.add_argument("--canopy", default=rf"{base}\auxdata\ETH_GlobalCanopyHeight_10m_2020_N12E099_Map.tif")
    ap.add_argument("--bcov", default=rf"{base}\auxdata\building_coverage_utm47n.tif")
    ap.add_argument("--worldcover", default=rf"{base}\auxdata\worldcover_2021_N12E099.tif")
    ap.add_argument("--calibration", default=rf"{base}\calib\calibration.json",
                    help="calibrate_dem.py output (provides f).")
    ap.add_argument("--f-override", type=float, default=None)
    ap.add_argument("--bias0-override", type=float, default=None,
                    help="global datum/epoch offset (m) to subtract; default from calibration.json")
    ap.add_argument("--subsidence-corrected", default=None,
                    help="Optional v2.0 subsidence-corrected GLO-30; its delta vs raw is "
                         "added to emit a present-day DEM.")
    ap.add_argument("--out", default=rf"{base}\dem_bareearth_bangkok.tif")
    ap.add_argument("--qa-out", default=rf"{base}\dem_qa_bangkok.tif")
    ap.add_argument("--build-thresh", type=float, default=0.25, help="bcov above this = building cell to backfill")
    ap.add_argument("--trueground-bcov", type=float, default=0.05, help="bcov below this = candidate true ground")
    ap.add_argument("--trueground-canopy", type=float, default=2.0, help="canopy below this (m) = candidate true ground")
    ap.add_argument("--canopy-min", type=float, default=1.0, help="subtract f·canopy only where canopy above this (m)")
    ap.add_argument("--lowconf-dist-cells", type=float, default=10.0, help="backfill farther than this from true ground = low-confidence")
    args = ap.parse_args()

    # f + global offset bias0
    rep = json.loads(Path(args.calibration).read_text()) if Path(args.calibration).exists() else {}
    f = args.f_override if args.f_override is not None else rep.get("f_fit", {}).get("f_clipped")
    bias0 = args.bias0_override if args.bias0_override is not None else rep.get("f_fit", {}).get("bias0_m", 0.0)
    if f is None:
        raise SystemExit("no f in calibration.json; pass --f-override")
    print(f"using f = {f:.4f}, bias0 = {bias0:+.3f} m")

    with rasterio.open(args.glo30) as src:
        dsm = src.read(1).astype("float64")
        profile = src.profile.copy()
        nod = src.nodata
        finite = np.isfinite(dsm)
        if nod is not None:
            finite &= dsm != nod
        # Align auxiliary layers onto the DEM grid (GDAL warp; bilinear for
        # continuous canopy, nearest for categorical land cover).
        canopy = read_aligned(args.canopy, src, "bilinear")
        lc = read_aligned(args.worldcover, src, "nearest") if Path(args.worldcover).exists() else np.full(dsm.shape, np.nan)
        bcov = read_aligned(args.bcov, src, "bilinear") if Path(args.bcov).exists() else np.zeros(dsm.shape)

    canopy = np.where(np.isfinite(canopy) & (canopy < 255), canopy, 0.0).clip(min=0)
    bcov = np.where(np.isfinite(bcov), bcov, 0.0)
    water = np.isfinite(lc) & (lc == 80)

    qa = np.zeros(dsm.shape, dtype="uint8")
    work = dsm.copy()

    # 0) Global systematic offset (datum/epoch/residual subsidence) — uniform shift
    #    so the canopy term only handles the canopy-correlated part (spec §1.5 fix).
    work[finite] -= bias0

    # 1) Calibrated canopy subtraction (not on buildings or water).
    built = (bcov > args.build_thresh) & finite
    canopy_cells = finite & ~built & ~water & (canopy > args.canopy_min)
    work[canopy_cells] -= f * canopy[canopy_cells]
    qa[canopy_cells] |= QA_CANOPY

    # 2) Building mask-and-backfill from TRUE-GROUND only.
    true_ground = finite & ~built & ~water & (bcov < args.trueground_bcov) & (canopy < args.trueground_canopy)
    if not true_ground.any():
        raise SystemExit("no true-ground cells found; check inputs/thresholds")
    # nearest true-ground cell index + distance (cells)
    dist, (ir, ic) = ndimage.distance_transform_edt(
        ~true_ground, return_distances=True, return_indices=True)
    nearest_ground = work[ir, ic]
    work[built] = nearest_ground[built]
    qa[built] |= QA_BUILDING
    lowconf = built & (dist > args.lowconf_dist_cells)
    qa[lowconf] |= QA_LOWCONF
    qa[water] |= QA_WATER
    print(f"cells: built={int(built.sum()):,} canopy-corr={int(canopy_cells.sum()):,} "
          f"true-ground={int(true_ground.sum()):,} low-conf backfill={int(lowconf.sum()):,}")

    # Optional present-day subsidence delta.
    if args.subsidence_corrected and Path(args.subsidence_corrected).exists():
        with rasterio.open(args.subsidence_corrected) as ss:
            sc = ss.read(1).astype("float64")
            if ss.nodata is not None:
                sc = np.where(sc == ss.nodata, np.nan, sc)
        delta = sc - dsm
        delta = np.where(np.isfinite(delta), delta, 0.0)
        work = work + delta
        print(f"applied subsidence delta: mean {np.nanmean(delta[finite]):+.3f} m")

    out = np.where(finite, work, nod if nod is not None else -9999.0).astype("float32")
    profile.update(dtype="float32", compress="deflate", nodata=nod if nod is not None else -9999.0)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(args.out, "w", **profile) as dst:
        dst.write(out, 1)

    qa_profile = profile.copy()
    qa_profile.update(dtype="uint8", nodata=0)
    with rasterio.open(args.qa_out, "w", **qa_profile) as dst:
        dst.write(qa, 1)

    diff = (out[finite].astype("float64") - dsm[finite])
    print(f"bare-earth vs GLO-30 on land: mean {diff.mean():+.3f} m  "
          f"median {np.median(diff):+.3f} m  p5/p95 {np.percentile(diff,5):+.2f}/{np.percentile(diff,95):+.2f} m")
    print(f"wrote {args.out}\nwrote {args.qa_out}")


if __name__ == "__main__":
    main()
