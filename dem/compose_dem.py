"""
Phase 1 coastal composite (spec §1.5 FALL BACK).

The candidate bare-earth passes inland/vegetated/urban but can't reach DeltaDTM-grade
quality in the coastal-flat zone (gate = FALL BACK). So compose:
  - DeltaDTM where it has data (coastal-flat, clips ~10 m MSL),
  - candidate bare-earth inland,
  - linear seam blend across an elevation band (default 8-12 m) so there's no step.

Both are EGM2008, so they're directly blendable. DeltaDTM is reprojected onto the
candidate grid via WarpedVRT.

Output: dem_bareearth_bangkok_composite.tif + updates QA (bit 16 = DeltaDTM-sourced).
"""
from __future__ import annotations
import argparse
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

from raster_utils import read_aligned

QA_DELTADTM = 16


def main():
    ap = argparse.ArgumentParser()
    base = r"D:\GPTs\Projects\flood-v3.0\dem\bangkok"
    ap.add_argument("--bareearth", default=rf"{base}\dem_bareearth_bangkok.tif")
    ap.add_argument("--deltadtm", default=rf"{base}\auxdata\deltadtm_bangkok.tif")
    ap.add_argument("--qa", default=rf"{base}\dem_qa_bangkok.tif")
    ap.add_argument("--out", default=rf"{base}\dem_bareearth_bangkok_composite.tif")
    ap.add_argument("--seam-lo", type=float, default=8.0, help="below this DeltaDTM elev: full DeltaDTM weight")
    ap.add_argument("--seam-hi", type=float, default=12.0, help="above this: full candidate weight")
    # Near-coast restriction: keep OUR calibrated model (urban building-removal +
    # bare-earth inland, spec §1.2); use DeltaDTM only near the sea where the
    # candidate can't reach DeltaDTM grade.
    ap.add_argument("--sea-mask", default=r"D:\GPTs\Projects\flood-v4.0\data\bangkok\sea_mask_utm47n.tif")
    ap.add_argument("--sea-value", type=int, default=0)
    ap.add_argument("--coast-dist-cells", type=float, default=600.0, help="full DeltaDTM weight within this many cells of sea (30 m cells)")
    ap.add_argument("--coast-ramp-cells", type=float, default=150.0, help="ramp DeltaDTM->candidate over this band")
    # Keep OUR building-removal: never let DeltaDTM override built-up cells.
    ap.add_argument("--bcov", default=r"D:\GPTs\Projects\flood-v3.0\dem\bangkok\auxdata\building_coverage_utm47n.tif")
    ap.add_argument("--urban-bcov", type=float, default=0.10, help="exclude DeltaDTM where building coverage exceeds this")
    args = ap.parse_args()

    with rasterio.open(args.bareearth) as src:
        be = src.read(1).astype("float64")
        prof = src.profile.copy()
        nod = src.nodata
        finite_be = np.isfinite(be) & (be != nod if nod is not None else True)
        dd = read_aligned(args.deltadtm, src, "bilinear")  # NaN where invalid/inland
        sea = read_aligned(args.sea_mask, src, "nearest")
        bcov = read_aligned(args.bcov, src, "bilinear") if Path(args.bcov).exists() else np.zeros(be.shape)

    dd_valid = np.isfinite(dd)
    # Elevation seam: 1 (DeltaDTM) below seam_lo, ramps to 0 above seam_hi (DeltaDTM clips ~10 m).
    w_elev = np.clip((args.seam_hi - dd) / (args.seam_hi - args.seam_lo), 0.0, 1.0)
    # Distance-from-sea ramp: 1 within coast_dist of the sea, ramps to 0 over coast_ramp.
    # Keeps DeltaDTM near the Gulf and hands back to our model before the inland urban core.
    is_sea = sea == args.sea_value
    dist = ndimage.distance_transform_edt(~is_sea)  # cells (C, no BLAS)
    w_dist = np.clip((args.coast_dist_cells - dist) / args.coast_ramp_cells, 0.0, 1.0)
    # Built-up exclusion: keep our mask-and-backfill where buildings are (spec §1.2).
    bcov = np.where(np.isfinite(bcov), bcov, 0.0)
    w_built = (bcov <= args.urban_bcov).astype("float64")
    w = w_elev * w_dist * w_built

    comp = be.copy()
    both = dd_valid & finite_be
    comp[both] = w[both] * dd[both] + (1.0 - w[both]) * be[both]
    only_dd = dd_valid & ~finite_be
    comp[only_dd] = dd[only_dd]

    dd_sourced = dd_valid & (w > 0.5)
    n_blend = int((both & (w > 0.0) & (w < 1.0)).sum())
    print(f"DeltaDTM-sourced cells: {int(dd_sourced.sum()):,}  seam-blend cells: {n_blend:,}  "
          f"candidate-only: {int((finite_be & ~dd_valid).sum()):,}")

    out = np.where(finite_be | dd_valid, comp, nod if nod is not None else -9999.0).astype("float32")
    prof.update(dtype="float32", compress="deflate", nodata=nod if nod is not None else -9999.0)
    with rasterio.open(args.out, "w", **prof) as d:
        d.write(out, 1)

    # Update QA bit for DeltaDTM-sourced cells.
    if Path(args.qa).exists():
        with rasterio.open(args.qa) as q:
            qa = q.read(1)
            qprof = q.profile.copy()
        qa[dd_sourced] |= QA_DELTADTM
        with rasterio.open(args.qa, "w", **qprof) as q:
            q.write(qa, 1)

    diff = (out[finite_be] - be[finite_be].astype("float32"))
    print(f"composite vs candidate on land: mean {diff.mean():+.3f} m (coastal pulled toward DeltaDTM)")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
