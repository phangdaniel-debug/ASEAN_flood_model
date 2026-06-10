"""Naive open pluvial baseline (spec section 7.2, REVISED): TWI threshold.

The deliberately-unsophisticated method a competitor could run for free:
a Topographic Wetness Index (TWI = ln(a / tan β)) on the RAW Copernicus DSM,
flagging the wettest cells (low-lying convergent ground) as flooded. No
calibration, no rain-on-grid routing, no drainage network. RP-independent
(pure topography). This is the *binding* comparator in the thesis gate; the TSS
+ dry-control design (spec 4.3) is what stops it winning by flooding low ground.

Replaces the depression-fill baseline, which is degenerate on Singapore's
island geometry (drains everything, or fills the whole island as a thin sheet).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import click
import numpy as np
import rasterio
from rasterio.transform import from_origin

# pysheds 0.5 + numpy>=2.0 compat: np.in1d was removed; np.isin is equivalent.
if not hasattr(np, "in1d"):
    np.in1d = np.isin  # type: ignore[attr-defined]

from pysheds.grid import Grid  # noqa: E402  (import after the shim above)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

_SENTINEL = -9999.0  # nodata sentinel for the temp GeoTIFF pysheds requires


def naive_tpi_index(dem: np.ndarray, *, window_cells: int = 5) -> np.ndarray:
    """Local depression depth (negative Topographic Position Index).

    score = mean(neighbourhood elevation) − elevation, so a cell sitting below
    its surroundings (a local hollow) gets a *positive, larger* score = more
    flood-prone. A second, structurally independent naive baseline: pure *local*
    relative elevation, with no flow routing or catchment accumulation (cf. TWI),
    and no island-degenerate depression fill. NaN (nodata) preserved.
    """
    from scipy.ndimage import uniform_filter
    a = np.asarray(dem, dtype=np.float64)
    finite = np.isfinite(a)
    filled = np.where(finite, a, 0.0)
    cnt = uniform_filter(finite.astype(np.float64), size=window_cells, mode="nearest")
    ssum = uniform_filter(filled, size=window_cells, mode="nearest")
    neigh_mean = np.divide(ssum, cnt, out=np.full_like(ssum, np.nan), where=cnt > 0)
    score = neigh_mean - a
    score[~finite] = np.nan
    return score


def naive_tpi_depth(
    dem: np.ndarray,
    *,
    flag_fraction: float = 0.15,
    flagged_depth_m: float = 0.30,
    window_cells: int = 5,
) -> np.ndarray:
    """Threshold the TPI index: flag the ``flag_fraction`` most locally-depressed cells."""
    if not (0.0 <= flag_fraction <= 1.0):
        raise ValueError(f"flag_fraction must be in [0, 1], got {flag_fraction}")
    finite = np.isfinite(dem)
    res = np.zeros_like(np.asarray(dem, dtype=np.float64))
    res[~finite] = np.nan
    if not finite.any() or flag_fraction == 0.0:
        return res
    tpi = naive_tpi_index(dem, window_cells=window_cells)
    valid = np.isfinite(tpi)
    vals = tpi[valid]
    if vals.size == 0:
        return res
    threshold = float(np.quantile(vals, 1.0 - flag_fraction))
    res[valid & (tpi >= threshold)] = flagged_depth_m
    return res


def naive_twi_index(dem: np.ndarray, *, cell_size_m: float = 30.0) -> np.ndarray:
    """Continuous Topographic Wetness Index TWI = ln(a / tan β).

    a = (flow_accumulation + 1) * cell_size_m; tan β = max(cell_slope, 1e-3)
    to avoid division by zero on flats. NaN (nodata) preserved. This is the
    raw, threshold-free index — the fair continuous *score* for a ranking
    (ROC-AUC) comparison; :func:`naive_twi_depth` thresholds it. pysheds
    requires a Raster, so the DEM is written to a temporary GeoTIFF.
    """
    out = np.array(dem, dtype=np.float64, copy=True)
    finite = np.isfinite(out)
    twi = np.full_like(out, np.nan)
    if not finite.any():
        return twi

    work = out.copy()
    work[~finite] = _SENTINEL
    h, w = work.shape
    transform = from_origin(0.0, h * cell_size_m, cell_size_m, cell_size_m)
    tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    tmp.close()
    try:
        with rasterio.open(
            tmp.name, "w", driver="GTiff", height=h, width=w, count=1,
            dtype="float64", crs="EPSG:32648", transform=transform,
            nodata=_SENTINEL,
        ) as ds:
            ds.write(work, 1)
        grid = Grid.from_raster(tmp.name)
        raw = grid.read_raster(tmp.name)
        pit = grid.fill_pits(raw)
        dep = grid.fill_depressions(pit)
        inflated = grid.resolve_flats(dep)
        fdir = grid.flowdir(inflated)
        acc = np.asarray(grid.accumulation(fdir), dtype=np.float64)
        slope = np.asarray(grid.cell_slopes(inflated, fdir), dtype=np.float64)
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    a = (acc + 1.0) * cell_size_m
    tan_beta = np.maximum(slope, 1e-3)
    twi[finite] = np.log(a / tan_beta)[finite]
    return twi


def naive_twi_depth(
    dem: np.ndarray,
    *,
    flag_fraction: float = 0.15,
    flagged_depth_m: float = 0.30,
    cell_size_m: float = 30.0,
) -> np.ndarray:
    """Pseudo-depth raster flagging the wettest ``flag_fraction`` of land cells.

    Thresholds :func:`naive_twi_index`: flagged cells get ``flagged_depth_m``;
    all other finite cells 0.0; NaN (nodata) preserved.
    """
    if not (0.0 <= flag_fraction <= 1.0):
        raise ValueError(f"flag_fraction must be in [0, 1], got {flag_fraction}")
    finite = np.isfinite(dem)
    res = np.zeros_like(np.asarray(dem, dtype=np.float64))
    res[~finite] = np.nan
    if not finite.any() or flag_fraction == 0.0:
        return res
    twi = naive_twi_index(dem, cell_size_m=cell_size_m)
    valid = np.isfinite(twi)
    vals = twi[valid]
    if vals.size == 0:
        return res
    threshold = float(np.quantile(vals, 1.0 - flag_fraction))
    res[valid & (twi >= threshold)] = flagged_depth_m
    return res


@click.command()
@click.option("--dem", "dem_path", type=click.Path(path_type=Path),
              default=PROJECT_ROOT / "data/singapore/copernicus_dem_utm48n.tif",
              show_default=True, help="RAW DSM (not bare-earth/conditioned).")
@click.option("--flag-fraction", type=float, default=0.15, show_default=True,
              help="Fraction of wettest land cells flagged flooded (spec 7.2 / 4.5).")
@click.option("--flagged-depth", "flagged_depth_m", type=float, default=0.30,
              show_default=True, help="Nominal depth (m) written to flagged cells.")
@click.option("--out", "out_path", type=click.Path(path_type=Path), required=True)
@click.option("--continuous-out", "cont_path", type=click.Path(path_type=Path),
              default=None, help="Also write the raw continuous TWI index (for ROC-AUC).")
def cli(dem_path: Path, flag_fraction: float, flagged_depth_m: float,
        out_path: Path, cont_path: Path | None):
    """Build the naive TWI-threshold pluvial baseline raster (RP-independent)."""
    with rasterio.open(dem_path) as ds:
        dem = ds.read(1).astype(np.float64)
        if ds.nodata is not None:
            dem = np.where(dem == ds.nodata, np.nan, dem)
        profile = ds.profile
        cell_size_m = abs(ds.transform.a)
    depth = naive_twi_depth(dem, flag_fraction=flag_fraction,
                            flagged_depth_m=flagged_depth_m, cell_size_m=cell_size_m)
    profile.update(dtype="float32", count=1, nodata=float("nan"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as ds:
        ds.write(depth.astype("float32"), 1)
    n_flag = int(np.sum(np.isfinite(depth) & (depth > 0)))
    click.echo(f"Wrote naive TWI baseline (flag_fraction={flag_fraction}, "
               f"{n_flag} cells flagged) -> {out_path}")
    if cont_path is not None:
        twi = naive_twi_index(dem, cell_size_m=cell_size_m)
        cont_path = Path(cont_path)
        cont_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(cont_path, "w", **profile) as ds:
            ds.write(twi.astype("float32"), 1)
        click.echo(f"Wrote continuous TWI index -> {cont_path}")


if __name__ == "__main__":
    cli()
