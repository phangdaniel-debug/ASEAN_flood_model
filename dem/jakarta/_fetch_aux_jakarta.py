"""Fetch + mosaic Jakarta aux tiles that straddle the -6 deg latitude line.

Jakarta GLO-30 grid lonlat bbox ~ (106.598..107.052, -6.452..-5.899). ~18% of the
grid (North Jakarta coast) is north of -6 deg, so the southern-estimate tiles must be
mosaicked with their northern neighbours:
  WorldCover (3deg): S09E105 (lat -9..-6) + S06E105 (lat -6..-3)
  DeltaDTM   (1deg): S07E106 (lat -7..-6) + S06E106 (lat -6..-5)

Outputs (EPSG:4326, lon/lat) covering the bbox + small buffer:
  auxdata/worldcover_2021_jakarta.tif
  auxdata/deltadtm_jakarta.tif

Run inside the sfincs env (DEM_HANDOFF.md s1).
"""
import io
import zipfile
from pathlib import Path

import fsspec
import numpy as np
import rasterio
import requests
from rasterio.io import MemoryFile
from rasterio.merge import merge  # noqa: F401  (not used; merge() crashes in env)

AUX = Path(r"D:/GPTs/Projects/flood-v3.0/dem/jakarta/auxdata")
AUX.mkdir(parents=True, exist_ok=True)

# Jakarta lonlat bbox + buffer (deg)
BUF = 0.05
BBOX = (106.5983 - BUF, -6.4518 - BUF, 107.0523 + BUF, -5.8985 + BUF)  # lo,la,hi,ha

WC_BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
WC_TILES = ["S09E105", "S06E105"]
DD_URL = ("https://data.4tu.nl/file/1da2e70f-6c4d-4b03-86bd-b53e789cc629/"
          "672eba4c-1334-44c6-8119-8879ded25912")
DD_TILES = ["DeltaDTM_v1_1_S07E106.tif", "DeltaDTM_v1_1_S06E106.tif"]


def _windowed_read(src, bbox):
    """Read only the bbox window from an open dataset; return (arr, window-transform, prof)."""
    from rasterio.windows import from_bounds
    lo, la, hi, ha = bbox
    # clamp bbox to dataset bounds
    b = src.bounds
    lo2, la2 = max(lo, b.left), max(la, b.bottom)
    hi2, ha2 = min(hi, b.right), min(ha, b.top)
    if lo2 >= hi2 or la2 >= ha2:
        return None
    win = from_bounds(lo2, la2, hi2, ha2, src.transform)
    arr = src.read(1, window=win)
    wt = src.window_transform(win)
    return arr, wt


def _mosaic_to_bbox(arrays, dtype, nodata, out_path, res):
    """Paste per-tile windowed reads onto a single bbox grid (EPSG:4326)."""
    lo, la, hi, ha = BBOX
    width = int(round((hi - lo) / res))
    height = int(round((ha - la) / res))
    from rasterio.transform import from_origin
    transform = from_origin(lo, ha, res, res)
    canvas = np.full((height, width), nodata, dtype=dtype)
    for arr, wt in arrays:
        # map this tile-window into the canvas via its own transform
        h, w = arr.shape
        for r in range(h):
            # vectorised per-row paste
            xs = wt.c + (np.arange(w) + 0.5) * wt.a
            y = wt.f + (r + 0.5) * wt.e
            cc = np.floor((xs - lo) / res).astype("int64")
            rr = int(np.floor((ha - y) / res))
            if rr < 0 or rr >= height:
                continue
            valid = (cc >= 0) & (cc < width)
            row = arr[r]
            tgt = canvas[rr]
            # only fill where canvas is still nodata (first tile wins; tiles don't overlap)
            cc_v = cc[valid]
            vals = row[valid]
            mask = tgt[cc_v] == nodata
            tgt[cc_v[mask]] = vals[mask]
    prof = {"driver": "GTiff", "dtype": dtype, "count": 1, "width": width,
            "height": height, "crs": "EPSG:4326", "transform": transform,
            "nodata": nodata, "compress": "deflate"}
    with rasterio.open(out_path, "w", **prof) as d:
        d.write(canvas, 1)
    return canvas, prof


def fetch_worldcover():
    out = AUX / "worldcover_2021_jakarta.tif"
    arrays = []
    res = None
    nod = 0
    for t in WC_TILES:
        fn = f"ESA_WorldCover_10m_2021_v200_{t}_Map.tif"
        url = WC_BASE + fn
        print("WC downloading", fn, flush=True)
        r = requests.get(url, timeout=600)
        r.raise_for_status()
        with MemoryFile(r.content) as mf, mf.open() as src:
            res = src.res[0]
            nod = src.nodata if src.nodata is not None else 0
            got = _windowed_read(src, BBOX)
            if got:
                arrays.append(got)
                print("  windowed", got[0].shape, "nodata", nod, flush=True)
    canvas, _ = _mosaic_to_bbox(arrays, "uint8", int(nod), str(out), res)
    vals, counts = np.unique(canvas, return_counts=True)
    print("WC wrote", out, "classes", dict(zip(vals.tolist(), counts.tolist())), flush=True)


def fetch_deltadtm():
    out = AUX / "deltadtm_jakarta.tif"
    fs = fsspec.filesystem("http")
    zf = zipfile.ZipFile(fs.open(DD_URL))
    arrays = []
    res = None
    nod = None
    for t in DD_TILES:
        print("DD reading", t, flush=True)
        data = zf.read(t)
        with MemoryFile(data) as mf, mf.open() as src:
            res = src.res[0]
            nod = src.nodata
            print("  bounds", tuple(round(x, 3) for x in src.bounds), "nodata", nod, flush=True)
            got = _windowed_read(src, BBOX)
            if got:
                arrays.append(got)
                print("  windowed", got[0].shape, flush=True)
    canvas, _ = _mosaic_to_bbox(arrays, "float32", float(nod), str(out), res)
    v = canvas[(canvas != nod) & np.isfinite(canvas)]
    if v.size:
        print(f"DD wrote {out} valid={v.size} elev min/med/max="
              f"{v.min():.2f}/{np.median(v):.2f}/{v.max():.2f} m", flush=True)
    else:
        print("DD wrote", out, "NO valid cells in bbox", flush=True)


if __name__ == "__main__":
    fetch_worldcover()
    fetch_deltadtm()
    print("AUX DONE", flush=True)
