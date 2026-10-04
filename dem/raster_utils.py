"""Shared raster helpers for Phase 1.

IMPORTANT (env bug): rasterio 1.4.4's `src.sample()` and
`rasterio.transform.rowcol()` with numpy-array inputs segfault on this Windows
box (0xC0000005), and `np.linalg.*` / `@` crash via the BLAS DLL conflict
(see repro/ENV_NOTES.md). Everything here uses manual affine math + element-wise
numpy only — no rowcol, no sample(), no BLAS.
"""
from __future__ import annotations
import numpy as np
import rasterio


def sample_points(raster_path, xs, ys, band: int = 1):
    """Nearest-cell sample at coords already in the raster's CRS -> float array
    (nodata -> NaN, out-of-bounds -> NaN)."""
    xs = np.asarray(xs, dtype="float64")
    ys = np.asarray(ys, dtype="float64")
    with rasterio.open(raster_path) as src:
        arr = src.read(band)
        nod = src.nodata
        inv = ~src.transform
        cols = np.floor(inv.a * xs + inv.b * ys + inv.c).astype("int64")
        rows = np.floor(inv.d * xs + inv.e * ys + inv.f).astype("int64")
        h, w = arr.shape
        inb = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w)
        out = np.full(xs.shape, np.nan, dtype="float64")
        out[inb] = arr[rows[inb], cols[inb]].astype("float64")
    if nod is not None:
        out = np.where(out == nod, np.nan, out)
    return out


def read_aligned(path, like_src, resampling="nearest"):
    """Read a raster reprojected/resampled onto the grid of an open rasterio
    dataset `like_src`. Returns a float64 array on like_src's grid (nodata->NaN).

    Uses a WarpedVRT so GDAL reprojects lazily and we only materialise the small
    destination window — never the full (possibly 36000x36000) source. (GDAL warp,
    no BLAS.)"""
    from rasterio.vrt import WarpedVRT
    from rasterio.warp import Resampling
    rs = getattr(Resampling, resampling)
    with rasterio.open(path) as src:
        with WarpedVRT(src, crs=like_src.crs, transform=like_src.transform,
                       width=like_src.width, height=like_src.height,
                       resampling=rs) as vrt:
            arr = vrt.read(1).astype("float64")
            nod = vrt.nodata if vrt.nodata is not None else src.nodata
    if nod is not None:
        arr = np.where(arr == nod, np.nan, arr)
    return arr
