"""City duration ('persistence class') rasters for the v4.0 fixed atlas.
Spec + pre-registered gates: flood-v5.0/docs/technical/duration-layer-methodology.md
(Addendum 2). Classes: 1:<6h 2:6-24h 3:1-3d 4:3-7d 5:>7d (0 = dry). Defined ONLY where
the shipped depth is wet (>=0.10 m) — cannot alter extent.

fluvial : f = ((S - d + 0.1)/S)^2.5 (S = cell fluvial water_level_m; derived from the
          DEPTH raster, consistent with shipped data) -> city recession curve (bankfull-
          floored). SG: urban drawdown (PUB canal overflow, not a natural river).
coastal : city gauge event-shape lookup at depth-below-peak. (Bangkok polder protection
          is already in the depth rasters; duration follows the wet mask.)
pluvial : depth / drain-rate. Urban (rc>=0.85): MY,SG 50 mm/h (MSMA / PUB CoP);
          JKT,BKK 40 mm/h (PU / BMA). Natural 3 mm/h. canal-HAND cells (wet(preclose)
          & ~wet(.orig)) use the engineered rate regardless of landcover. Bridged cells
          (closing sidecar): class = donor - 1, floor 1.
"""
import csv
import glob
import json
import os
import re

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from scipy import ndimage

CUR = json.load(open("data/city_duration_curves.json"))
FRACS = np.array([0.0, 0.10, 0.25, 0.50, 0.70, 0.90, 0.95])
CLASS_EDGES_H = [6.0, 24.0, 72.0, 168.0]
CAP_H = 30 * 24
URBAN_RATE = {"kuala_lumpur": 50.0, "singapore": 50.0, "jakarta": 40.0, "bangkok": 40.0}
NATURAL_RATE = 3.0
# Singapore has NO natural-drainage regime: the PUB Code of Practice places the entire
# island inside engineered catchments, so open/vegetated land (rc<0.85) drains at a
# managed-open rate (half the urban rate), not tropical-clay 3 mm/h. Without this, 42%
# of SG pluvial claimed 3-7 day persistence vs PUB-documented sub-4-hour ponding.
# Other cities keep 3 mm/h: Bangkok/Jakarta outer-area multi-day ponding is documented.
OPEN_RATE = {"singapore": 25.0}
RC = {"kuala_lumpur": "data/kuala_lumpur/runoff_coeff_utm47n.tif",
      "singapore": "data/singapore/runoff_coeff_utm48n.tif",
      "jakarta": "data/jakarta/runoff_coeff_utm48s.tif",
      "bangkok": "data/bangkok/runoff_coeff_utm47n.tif"}


def classify_hours(h):
    c = np.zeros(h.shape, dtype=np.uint8)
    c[h > 0] = 1
    for i, e in enumerate(CLASS_EDGES_H, start=2):
        c[h >= e] = i
    return c


def recession_hours(f, city):
    a = CUR["fluvial_recession"][city]
    d = np.array([a["recession"][str(x)]["median_days"] for x in FRACS])
    return np.clip(np.interp(np.clip(f, 0, 1), FRACS, d), 0, 30) * 24.0


def coastal_hours(depth, city):
    g = CUR["coastal_event_shapes"][city]["duration_below_peak_h"]
    dz = np.array(sorted(float(z) for z in g))
    hh = np.array([g[str(z)]["median_h"] for z in dz])
    return np.interp(depth, dz, hh, left=0.0, right=hh[-1]).astype("float32")


def rc_on_grid(city, ref_path):
    with rasterio.open(ref_path) as ref:
        shape, tr, crs = ref.shape, ref.transform, ref.crs
    with rasterio.open(RC[city]) as ds:
        if ds.shape == shape:
            return ds.read(1)
        out = np.zeros(shape, "float32")
        reproject(ds.read(1), out, src_transform=ds.transform, src_crs=ds.crs,
                  dst_transform=tr, dst_crs=crs, resampling=Resampling.nearest)
        return out


for cell in sorted(glob.glob("outputs/_fixed_atlas/*")):
    m = re.match(r"(kuala_lumpur|singapore|jakarta|bangkok)_(ssp\d+_\d+)_rp(\d+)",
                 os.path.basename(cell))
    if not m:
        continue
    city, scen, rp = m.group(1), m.group(2), int(m.group(3))
    summ = glob.glob(f"{cell}/summary_*.csv")
    if not summ and cell.endswith("_polder"):
        summ = glob.glob(f"{cell[:-7]}/summary_*.csv")   # polder dirs carry no summary
    S_fluv = None
    if summ:
        for r in csv.DictReader(open(summ[0], encoding="utf-8", errors="replace")):
            if r["hazard_type"] == "fluvial":
                S_fluv = float(r["water_level_m"])
    outdir = f"{cell}/duration"
    os.makedirs(outdir, exist_ok=True)
    classes, prof = {}, None
    # fluvial
    g = glob.glob(f"{cell}/fluvial/rp_{rp}/fluvial_depth_*.tif")
    if g:
        with rasterio.open(g[0]) as ds:
            d = ds.read(1); prof = ds.profile
        wet = np.isfinite(d) & (d >= 0.1)
        hrs = np.zeros(d.shape, "float32")
        if city == "singapore":
            hrs[wet] = np.minimum(d[wet] * 1000.0 / URBAN_RATE[city], CAP_H)
        elif S_fluv and S_fluv > 0:
            f = np.clip((S_fluv - d[wet] + 0.1) / S_fluv, 0, 1) ** 2.5
            hrs[wet] = recession_hours(f, city)
        classes["fluvial"] = classify_hours(hrs)
    # coastal
    g = glob.glob(f"{cell}/coastal/rp_{rp}/coastal_depth_*.tif")
    if g and city in CUR["coastal_event_shapes"]:
        with rasterio.open(g[0]) as ds:
            d = ds.read(1); prof = prof or ds.profile
        wet = np.isfinite(d) & (d >= 0.1)
        hrs = np.zeros(d.shape, "float32")
        if wet.any():
            hrs[wet] = coastal_hours(d[wet].astype("float32"), city)
        classes["coastal"] = classify_hours(hrs)
    # pluvial
    g = glob.glob(f"{cell}/pluvial/rp_{rp}/pluvial_depth_*.tif")
    if g:
        pl = g[0]
        with rasterio.open(pl) as ds:
            d = ds.read(1); prof = prof or ds.profile
        wet = np.isfinite(d) & (d >= 0.1)
        rc = rc_on_grid(city, pl)
        open_rate = OPEN_RATE.get(city, NATURAL_RATE)
        rate = np.where(np.asarray(rc) >= 0.85, URBAN_RATE[city], open_rate)
        # canal-HAND cells -> engineered rate regardless of landcover
        orig, pre = pl + ".orig", pl + ".preclose"
        if os.path.exists(orig) and os.path.exists(pre):
            a0 = rasterio.open(orig).read(1)
            a1 = rasterio.open(pre).read(1)
            canal = (np.nan_to_num(a1, nan=0) >= 0.1) & ~(np.nan_to_num(a0, nan=0) >= 0.1)
            rate = np.where(canal, URBAN_RATE[city], rate)
        hrs = np.zeros(d.shape, "float32")
        hrs[wet] = np.minimum(d[wet] * 1000.0 / rate[wet], CAP_H)
        pcls = classify_hours(hrs)
        bp = pl.replace("pluvial_depth", "pluvial_bridged")
        if os.path.exists(bp):
            bridged = rasterio.open(bp).read(1).astype(bool)
            if bridged.any():
                donor = ndimage.grey_dilation(np.where(bridged, 0, pcls), size=(3, 3))
                sel = bridged & wet
                pcls[sel] = np.maximum(1, donor[sel].astype(np.int16) - 1).astype(np.uint8)
        classes["pluvial"] = pcls
    if not classes:
        continue
    oprof = {**prof, "dtype": "uint8", "nodata": 0, "count": 1, "compress": "deflate"}
    for k in ("blockxsize", "blockysize", "tiled", "interleave"):
        oprof.pop(k, None)
    comb = None
    for hz, c in classes.items():
        with rasterio.open(f"{outdir}/duration_{hz}_rp{rp}.tif", "w", **oprof) as o:
            o.write(c, 1)
        comb = c if comb is None else np.maximum(comb, c)
    with rasterio.open(f"{outdir}/duration_combined_rp{rp}.tif", "w", **oprof) as o:
        o.write(comb, 1)
print("DONE")
