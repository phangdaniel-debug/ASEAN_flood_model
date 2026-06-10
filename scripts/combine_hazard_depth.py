"""Combine per-hazard depth rasters into a single wet field (per-cell max).

Used by the validation harness: the model field scored against documented
hotspots for a rainfall/riverine event is the max of the pluvial and fluvial
depths at the event RP. NaN (nodata) is treated as "no contribution" unless
ALL layers are NaN at that cell, which stays NaN.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio


def combine_depth_arrays(arrays: list[np.ndarray]) -> np.ndarray:
    """Element-wise max across float arrays; NaN only where every layer is NaN."""
    stack = np.stack([a.astype(np.float64) for a in arrays], axis=0)
    all_nan = np.all(np.isnan(stack), axis=0)
    out = np.nanmax(stack, axis=0)
    out[all_nan] = np.nan
    return out.astype(np.float32)


def combine_depth_rasters(raster_paths: list[Path], out_path: Path) -> Path:
    """Read aligned depth rasters, write their per-cell max to ``out_path``."""
    arrays, profile = [], None
    for p in raster_paths:
        with rasterio.open(p) as ds:
            arrays.append(ds.read(1))
            if profile is None:
                profile = ds.profile
    combined = combine_depth_arrays(arrays)
    profile.update(dtype="float32", count=1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(combined, 1)
    return out_path
