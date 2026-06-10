from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np

# pysheds 0.5 uses np.in1d which was removed in NumPy 2.0.
# Patch it back as an alias for np.isin (same semantics for 1-D inputs).
if not hasattr(np, "in1d"):
    np.in1d = np.isin  # type: ignore[attr-defined]


def compute_hand(
    dem: np.ndarray,
    drainage_mask: np.ndarray,
    profile: dict,
) -> np.ndarray:
    """
    Compute Height Above Nearest Drainage (HAND) using D8 flow-path routing.

    For each cell, HAND = elevation(cell) - elevation(nearest channel cell),
    where "nearest" is measured along the D8 flow path, not straight-line
    distance.  This correctly respects watershed boundaries: a cell is always
    assigned to a channel in its own drainage basin, never to a channel across
    a topographic divide.

    The previous Euclidean implementation mis-assigned ~20 % of land pixels to
    channel cells at higher elevation (across ridges), giving HAND = 0 and
    causing those pixels to flood at any positive stage regardless of their
    actual distance from rivers.

    Implementation uses pysheds ``compute_hand`` (D8 iterative algorithm):
      1. Condition the DEM (fill pits → fill depressions → resolve flats).
      2. Compute D8 flow direction on the conditioned DEM.
      3. Trace each cell's flow path downstream to the nearest drainage cell.
      4. HAND = conditioned_elevation(cell) - conditioned_elevation(channel).

    Parameters
    ----------
    dem : float32 array (rows, cols)
        Ground elevation in metres.  NaN marks nodata.
    drainage_mask : bool array (rows, cols)
        True at every cell belonging to the drainage network (channel cells).
    profile : dict
        Rasterio write profile for the DEM (CRS, transform, etc.).

    Returns
    -------
    hand : float32 array (rows, cols)
        HAND in metres, >= 0.  NaN where dem is nodata or no flow path
        reaches a channel cell (isolated pixels).
    """
    try:
        from pysheds.grid import Grid
    except ImportError as exc:
        raise ImportError(
            "pysheds is required for flow-path HAND. "
            "Install with: pip install pysheds"
        ) from exc

    import rasterio

    if dem.shape != drainage_mask.shape:
        raise ValueError("dem and drainage_mask must have the same shape")
    drainage_mask = drainage_mask.astype(bool)
    if not np.any(drainage_mask):
        raise ValueError(
            "drainage_mask contains no True cells — cannot compute HAND. "
            "Check that the river raster overlaps the DEM extent."
        )

    dem_tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    mask_tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    dem_tmp.close()
    mask_tmp.close()

    try:
        # Write DEM
        prof = profile.copy()
        prof.update(dtype="float32", count=1, nodata=-9999.0)
        dem_write = np.where(np.isfinite(dem), dem, -9999.0).astype(np.float32)
        with rasterio.open(dem_tmp.name, "w", **prof) as dst:
            dst.write(dem_write, 1)

        # Write drainage mask (uint8: 1 = channel, 0 = non-channel)
        mask_prof = profile.copy()
        mask_prof.update(dtype="uint8", count=1, nodata=0)
        with rasterio.open(mask_tmp.name, "w", **mask_prof) as dst:
            dst.write(drainage_mask.astype(np.uint8), 1)

        # Condition DEM and compute flow direction
        grid = Grid.from_raster(dem_tmp.name)
        raw  = grid.read_raster(dem_tmp.name)
        pit_filled = grid.fill_pits(raw)
        dep_filled = grid.fill_depressions(pit_filled)
        inflated   = grid.resolve_flats(dep_filled)
        fdir       = grid.flowdir(inflated)

        # Load drainage mask as a pysheds Raster
        mask_raster = grid.read_raster(mask_tmp.name)

        # Compute HAND along D8 flow paths
        hand_raster = grid.compute_hand(fdir, inflated, mask_raster)
        hand = np.asarray(hand_raster).astype(np.float32)

    finally:
        os.unlink(dem_tmp.name)
        os.unlink(mask_tmp.name)

    hand = np.maximum(0.0, hand)
    hand[~np.isfinite(dem)] = np.nan
    # pysheds may return large sentinel values where no path reaches a channel
    hand[hand > 1e6] = np.nan

    return hand


def fill_depressions(dem: np.ndarray, profile: dict) -> np.ndarray:
    """
    Fill topographic depressions in a DEM using pysheds.

    Each interior local minimum is raised to the elevation of its lowest
    pour point — the point where water would spill out of the depression.
    The result is used to compute maximum ponding depth:
        max_ponding = fill_depressions(dem) - dem

    Parameters
    ----------
    dem : float32 array
        Ground elevation in metres.  NaN = nodata (treated as open drain).
    profile : dict
        Rasterio write profile for the DEM.

    Returns
    -------
    filled : float32 array, same shape as dem
        Depression-filled DEM.  NaN preserved where dem is NaN.
    """
    try:
        from pysheds.grid import Grid
    except ImportError as exc:
        raise ImportError(
            "pysheds is required for depression filling. "
            "Install with: pip install pysheds"
        ) from exc

    import rasterio

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        prof = profile.copy()
        prof.update(dtype="float32", count=1, nodata=-9999.0)

        dem_write = dem.copy()
        dem_write[~np.isfinite(dem_write)] = -9999.0

        with rasterio.open(tmp_path, "w", **prof) as dst:
            dst.write(dem_write.astype(np.float32), 1)

        grid = Grid.from_raster(tmp_path)
        raw = grid.read_raster(tmp_path)
        pit_filled = grid.fill_pits(raw)
        dep_filled = grid.fill_depressions(pit_filled)

        filled = np.asarray(dep_filled).astype(np.float32)
    finally:
        os.unlink(tmp_path)

    filled[~np.isfinite(dem)] = np.nan
    return filled


def derive_drainage_mask_from_accumulation(
    dem: np.ndarray,
    profile: dict,
    acc_threshold: int = 500,
) -> np.ndarray:
    """
    Derive a drainage-network mask from flow accumulation using pysheds.

    Writes the DEM to a temporary GeoTIFF, runs the pysheds conditioning and
    flow-routing pipeline, then returns a boolean mask where True marks cells
    whose upstream contributing area (in pixels) is >= ``acc_threshold``.

    Parameters
    ----------
    dem : float32 array
        Ground elevation in metres.  NaN = nodata.
    profile : dict
        Rasterio profile of the DEM (used to write the temp file).
    acc_threshold : int
        Minimum flow-accumulation value (in pixels) to be counted as a
        drainage cell.  A value of 500 at 30 m resolution corresponds to
        roughly 0.45 km² of contributing area.

    Returns
    -------
    drainage_mask : bool array, same shape as dem
    """
    try:
        from pysheds.grid import Grid
    except ImportError as exc:
        raise ImportError(
            "pysheds is required for accumulation-based drainage derivation. "
            "Install with: pip install pysheds"
        ) from exc

    import rasterio

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        prof = profile.copy()
        prof.update(dtype="float32", count=1, nodata=-9999.0)

        dem_write = dem.copy()
        dem_write[~np.isfinite(dem_write)] = -9999.0

        with rasterio.open(tmp_path, "w", **prof) as dst:
            dst.write(dem_write.astype(np.float32), 1)

        grid = Grid.from_raster(tmp_path)
        raw = grid.read_raster(tmp_path)

        pit_filled = grid.fill_pits(raw)
        flooded = grid.fill_depressions(pit_filled)
        inflated = grid.resolve_flats(flooded)
        fdir = grid.flowdir(inflated)
        acc = grid.accumulation(fdir)

        drainage_mask = np.asarray(acc) >= acc_threshold
    finally:
        os.unlink(tmp_path)

    return drainage_mask.astype(bool)


# pysheds default dirmap (N, NE, E, SE, S, SW, W, NW) -> the 0..7 code
# convention of model.pluvial_model (0=NW 1=N 2=NE 3=W 4=E 5=SW 6=S 7=SE).
_PYSHEDS_TO_D8 = {64: 1, 128: 2, 1: 4, 2: 7, 4: 6, 8: 5, 16: 3, 32: 0}


def flow_direction_filled(dem: np.ndarray, profile: dict) -> np.ndarray:
    """D8 flow direction on the conditioned (pit-filled, depression-filled,
    flat-resolved) DEM, encoded in the 0..7 convention of
    ``model.pluvial_model`` (-1 = drains off-domain / nodata).

    The conditioned DEM has no pits, so the flow field is acyclic and every
    cell drains to the raster boundary — the property the pluvial spill walk
    relies on.
    """
    try:
        from pysheds.grid import Grid
    except ImportError as exc:
        raise ImportError(
            "pysheds is required for filled-DEM flow routing. "
            "Install with: pip install pysheds"
        ) from exc
    import rasterio

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        prof = profile.copy()
        prof.update(dtype="float32", count=1, nodata=-9999.0)
        dem_write = dem.copy()
        dem_write[~np.isfinite(dem_write)] = -9999.0
        with rasterio.open(tmp_path, "w", **prof) as dst:
            dst.write(dem_write.astype(np.float32), 1)

        grid = Grid.from_raster(tmp_path)
        raw = grid.read_raster(tmp_path)
        pit_filled = grid.fill_pits(raw)
        dep_filled = grid.fill_depressions(pit_filled)
        inflated = grid.resolve_flats(dep_filled)
        fdir_pysheds = np.asarray(grid.flowdir(inflated)).astype(np.int64)
    finally:
        os.unlink(tmp_path)

    fdir = np.full(dem.shape, -1, dtype=np.int8)
    for code, d8 in _PYSHEDS_TO_D8.items():
        fdir[fdir_pysheds == code] = d8
    fdir[~np.isfinite(dem)] = -1
    return fdir
