"""Fetch + mosaic the ETH Global Canopy Height 10m 2020 tiles for Jakarta.

The original share.phys.ethz.ch direct host is RETIRED (301 -> Research Collection 500).
Working mirror = the ETH libdrive ownCloud share (token cO8or7iOe5dT2Rt, /3deg_cogs),
which serves the COG tiles with HTTP 206 / image/tiff. CC-BY 4.0.

Jakarta straddles -6 deg lat, so mosaic S09E105 (lat -9..-6) + S06E105 (lat -6..-3),
windowed to the GLO-30 bbox + buffer. Output EPSG:4326, ETH nodata = 255.

Run inside the sfincs env (DEM_HANDOFF.md s1).
"""
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.io import MemoryFile
from rasterio.windows import from_bounds
from rasterio.transform import from_origin

AUX = Path(r"D:/GPTs/Projects/flood-v3.0/dem/jakarta/auxdata")
BUF = 0.05
BBOX = (106.5983 - BUF, -6.4518 - BUF, 107.0523 + BUF, -5.8985 + BUF)
BASE = ("https://libdrive.ethz.ch/index.php/s/cO8or7iOe5dT2Rt/download"
        "?path=%2F3deg_cogs&files=")
TILES = ["S09E105", "S06E105"]
NOD = 255


def _windowed_read(src, bbox):
    lo, la, hi, ha = bbox
    b = src.bounds
    lo2, la2 = max(lo, b.left), max(la, b.bottom)
    hi2, ha2 = min(hi, b.right), min(ha, b.top)
    if lo2 >= hi2 or la2 >= ha2:
        return None
    win = from_bounds(lo2, la2, hi2, ha2, src.transform)
    return src.read(1, window=win), src.window_transform(win)


def _resumable_download(url, dest, retries=20):
    """Stream to dest with HTTP Range resume; survives IncompleteRead drops."""
    dest = Path(dest)
    for attempt in range(retries):
        have = dest.stat().st_size if dest.exists() else 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        try:
            with requests.get(url, headers=headers, stream=True, timeout=300) as r:
                if r.status_code in (200, 206):
                    total = have + int(r.headers.get("Content-Length", 0))
                    mode = "ab" if (have and r.status_code == 206) else "wb"
                    if mode == "wb":
                        have = 0
                    with open(dest, mode) as f:
                        for chunk in r.iter_content(chunk_size=4 * 1024 * 1024):
                            f.write(chunk)
                            have += len(chunk)
                    # verify complete
                    cr = r.headers.get("Content-Range")
                    full = int(cr.split("/")[-1]) if cr else total
                    if dest.stat().st_size >= full:
                        print(f"  complete {dest.stat().st_size/1e6:.1f} MB", flush=True)
                        return
                    print(f"  partial {dest.stat().st_size/1e6:.1f}/{full/1e6:.1f} MB, resume", flush=True)
                else:
                    print(f"  status {r.status_code}, retry", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {attempt+1}: {type(e).__name__} at {dest.stat().st_size if dest.exists() else 0}B, resume", flush=True)
    raise SystemExit(f"failed to download {url} after {retries} attempts")


def main():
    arrays, res = [], None
    for t in TILES:
        fn = f"ETH_GlobalCanopyHeight_10m_2020_{t}_Map.tif"
        local = AUX / fn
        print("downloading", fn, flush=True)
        _resumable_download(BASE + fn, local)
        with rasterio.open(local) as src:
            res = src.res[0]
            got = _windowed_read(src, BBOX)
            if got:
                arrays.append(got)
                print("  windowed", got[0].shape, flush=True)
    lo, la, hi, ha = BBOX
    width = int(round((hi - lo) / res))
    height = int(round((ha - la) / res))
    transform = from_origin(lo, ha, res, res)
    canvas = np.full((height, width), NOD, dtype="uint8")
    for arr, wt in arrays:
        h, w = arr.shape
        for rr in range(h):
            xs = wt.c + (np.arange(w) + 0.5) * wt.a
            y = wt.f + (rr + 0.5) * wt.e
            cc = np.floor((xs - lo) / res).astype("int64")
            crow = int(np.floor((ha - y) / res))
            if crow < 0 or crow >= height:
                continue
            valid = (cc >= 0) & (cc < width)
            tgt = canvas[crow]
            cc_v, vals = cc[valid], arr[rr][valid]
            mask = tgt[cc_v] == NOD
            tgt[cc_v[mask]] = vals[mask]
    out = AUX / "canopy_eth_2020_jakarta.tif"
    prof = {"driver": "GTiff", "dtype": "uint8", "count": 1, "width": width,
            "height": height, "crs": "EPSG:4326", "transform": transform,
            "nodata": NOD, "compress": "deflate"}
    with rasterio.open(out, "w", **prof) as d:
        d.write(canvas, 1)
    v = canvas[canvas != NOD]
    print(f"wrote {out} valid={v.size} canopy m min/med/max="
          f"{v.min()}/{np.median(v)}/{v.max()}  (>3m: {int((v>3).sum())})", flush=True)
    print("CANOPY DONE", flush=True)


if __name__ == "__main__":
    main()
