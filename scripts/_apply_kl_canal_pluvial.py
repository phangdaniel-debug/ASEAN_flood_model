"""Apply the canal-HAND pluvial to Kuala Lumpur's fixed-atlas cells (2026-07-04).

pluvial_new = max(shipped_handfill, clip(stage_cell - HAND_canal, 0, 3.0)), channels masked.
HAND_canal = height above the OSM drain network (data/kuala_lumpur/drainage_waterways_utm47n.tif)
PRUNED to drains with >= 0.5 km2 flow accumulation (unpruned, hill headwater ditches flood the
high dry controls Federal Hill/TTDI). stage_cell = 0.5 m x (cell pluvial excess / 0.095), the
engine handfill scenario-scaling, clipped [0.4, 2.5].

Validated on the expanded hotspot gate (RP100/2020): HR 0.65->0.71 (recovers Segambut Dalam,
Jalan Tun Razak, Bangsar), CRR 1.00->0.92, TSS 0.65->0.63 (parity within the +/-0.16 CI).
Pristine rasters preserved as *.tif.orig; the pre-change atlas is flood_maps_atlas_legacy.html.
Summary CSVs and severity rasters are NOT regenerated (documented as stale for pluvial).
"""
import sys
import csv
import glob
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import rasterio

if not hasattr(np, "in1d"):
    np.in1d = np.isin
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder

DEM = "dem/kl/dem_bareearth_kl_eth_present_conditioned.tif"
DRAINS = "data/kuala_lumpur/drainage_waterways_utm47n.tif"
BASE_STAGE = 0.5
BASE_EXCESS = 0.095
PRUNE_KM2 = 0.5

with rasterio.open(DEM) as ds:
    dem = ds.read(1).astype("float32")
    prof = ds.profile
dem[dem < -1000] = np.nan
drain_mask = rasterio.open(DRAINS).read(1) > 0

td = tempfile.mkdtemp()
tmp = os.path.join(td, "d.tif")
p2 = {**prof, "dtype": "float32", "nodata": -9999.0, "count": 1}
for k in ("blockxsize", "blockysize", "tiled", "interleave"):
    p2.pop(k, None)
with rasterio.open(tmp, "w", **p2) as o:
    o.write(np.where(np.isfinite(dem), dem, -9999.0).astype("float32"), 1)
grid = Grid.from_raster(tmp)
demr = grid.read_raster(tmp)
inflated = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(demr)))
fdir = grid.flowdir(inflated)
acc = np.asarray(grid.accumulation(fdir))
pruned = drain_mask & (acc > int(PRUNE_KM2 * 1e6 / 900))
vf = ViewFinder(affine=demr.viewfinder.affine, shape=demr.viewfinder.shape,
                crs=demr.viewfinder.crs, nodata=np.bool_(False))
dm = Raster(pruned.astype(np.bool_), viewfinder=vf)
idx = np.asarray(grid.compute_hand(fdir, inflated, dm, return_index=True))
inf = np.asarray(inflated, "float32")
flat = np.clip(idx.ravel(), 0, inf.size - 1)
ph = (inf - inf.ravel()[flat].reshape(dem.shape)).astype("float32")
ph[~(pruned.ravel()[flat].reshape(dem.shape) & np.isfinite(dem))] = np.nan
print(f"pruned canal-HAND built ({int(pruned.sum())} drain cells)", flush=True)

cells = sorted(glob.glob("outputs/_fixed_atlas/kuala_lumpur_*"))
for d in cells:
    tifs = glob.glob(f"{d}/pluvial/rp_*/pluvial_depth_*.tif")
    summ = glob.glob(f"{d}/summary_*.csv")
    if not tifs or not summ:
        print(f"  {d}: missing pluvial or summary, SKIP")
        continue
    excess = None
    with open(summ[0], encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            if row["hazard_type"] == "pluvial":
                excess = float(row["water_level_m"])
    if excess is None:
        print(f"  {d}: no pluvial row, SKIP")
        continue
    stage = float(np.clip(BASE_STAGE * excess / BASE_EXCESS, 0.4, 2.5))
    p = tifs[0]
    orig = p + ".orig"
    if not os.path.exists(orig):
        import shutil
        shutil.copy2(p, orig)
    with rasterio.open(orig) as ds:
        base = ds.read(1).astype("float32")
        bprof = ds.profile
    base = np.where(np.isfinite(base), base, 0.0).astype("float32")
    hf = np.float32(stage) - ph
    hf = np.where(np.isfinite(hf) & (hf > 0), np.minimum(hf, 3.0), 0.0).astype("float32")
    hf[pruned] = 0.0                              # channels are conveyance, not inundation
    new = np.maximum(base, hf)
    new[~np.isfinite(dem)] = np.nan
    bprof.update(compress="deflate")
    for k in ("blockxsize", "blockysize", "tiled", "interleave"):
        bprof.pop(k, None)
    with rasterio.open(p, "w", **bprof) as o:
        o.write(np.where(np.isfinite(new), new, bprof.get("nodata", -9999.0)
                         if bprof.get("nodata") is not None else np.nan).astype("float32"), 1)
    w0 = (base >= 0.1).sum() * 900 / 1e6
    w1 = (np.isfinite(new) & (new >= 0.1)).sum() * 900 / 1e6
    print(f"  {os.path.basename(d)}: excess {excess*1000:.0f}mm stage {stage:.2f}m | "
          f"pluvial {w0:.0f} -> {w1:.0f} km2", flush=True)
print("DONE")
