"""
Hydro-condition the bare-earth DEM for SFINCS / the v2.0 model: remove GLO-30 radar
artefact spikes (very-negative pixels from low coherence) that otherwise fill to tens of
metres in a rain-on-grid run. Reuses the v2.0 approach: replace each spike with its
WINxWIN neighbourhood median. Spikes = cells well below their local surroundings or below
a physical land floor (delta land doesn't sit at -30 m).

Real low-lying basins are preserved (only anomalies are touched).

CLI (defaults = Bangkok, for backward compatibility):
    python dem/condition_dem.py \
        --in  dem/<city>/dem_bareearth_<city>_present.tif \
        --out dem/<city>/dem_bareearth_<city>_present_conditioned.tif

Run inside the activated env (see dem/DEM_HANDOFF.md §1), e.g.
    mamba run -n sfincs python dem/condition_dem.py --in ... --out ...
"""
from __future__ import annotations
import argparse
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

DEF_IN = r"D:\GPTs\Projects\flood-v3.0\dem\bangkok\dem_bareearth_bangkok_present.tif"
DEF_OUT = r"D:\GPTs\Projects\flood-v3.0\dem\bangkok\dem_bareearth_bangkok_present_conditioned.tif"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src", default=DEF_IN,
                    help="input bare-earth DEM (the gate-PASS single or composite raster)")
    ap.add_argument("--out", dest="dst", default=DEF_OUT,
                    help="output conditioned DEM")
    ap.add_argument("--win", type=int, default=7,
                    help="neighbourhood window for the median filter (cells)")
    ap.add_argument("--rel-thresh", type=float, default=5.0,
                    help="cell >this many m below local median = artefact spike -> median-fill")
    ap.add_argument("--land-floor", type=float, default=-2.0,
                    help="physical floor (m EGM2008); deeper = radar artefact -> clamp")
    args = ap.parse_args()

    with rasterio.open(args.src) as s:
        a = s.read(1).astype("float64")
        prof = s.profile.copy()
        nod = s.nodata
    land = np.isfinite(a) & (a != nod)
    work = a.copy()
    # 1) median-fill ISOLATED deep spikes (one pass; relative to local terrain).
    med = ndimage.median_filter(np.where(land, work, np.nan), size=args.win)
    spike = land & (work < med - args.rel_thresh)
    work[spike] = med[spike]
    print(f"median-filled {int(spike.sum())} isolated spike cells")
    # 2) clamp remaining sub-floor artefacts to the physical land floor (deterministic).
    clamp = land & (work < args.land_floor)
    work[clamp] = args.land_floor
    print(f"clamped {int(clamp.sum())} cells to floor {args.land_floor} m")
    out = np.where(land, work, nod).astype("float32")
    prof.update(dtype="float32", compress="deflate")
    Path(args.dst).parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(args.dst, "w", **prof) as d:
        d.write(out, 1)
    d_land = out[land].astype("float64")
    print(f"conditioned elev min/med/max: {d_land.min():.2f}/{np.median(d_land):.2f}/{d_land.max():.2f} m")
    print(f"cells < -5m now: {int((d_land < -5).sum())}")
    print("wrote", args.dst)


if __name__ == "__main__":
    main()
