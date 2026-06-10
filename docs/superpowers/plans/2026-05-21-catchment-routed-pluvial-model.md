# Catchment-Routed Pluvial Flood Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the lumped depression-fill pluvial solver — whose flood extent is frozen across all return periods — with a catchment-routed fill-and-spill cascade whose extent grows with return period.

**Architecture:** A new self-contained module `model/pluvial_model.py` builds a depression inventory from the DEM, routes each return period's runoff into depressions by D8 catchment, fills each depression via its hypsometric curve, and spills overflow downstream through a topologically-ordered cascade. Overflow routing uses flow directions computed on the conditioned (pit-filled, depression-filled, flat-resolved) DEM, which is acyclic and drains every cell to the domain boundary. Runoff supply is weighted by an ESA WorldCover-derived per-cell runoff coefficient. The rainfall side (GEV-fitted IDF-anchored 6 h design storm) is unchanged.

**Tech Stack:** Python, numpy, scipy.ndimage, numba (`@njit`), pysheds (DEM conditioning + flow direction, via `model.hand_model`), rasterio, click.

**Design spec:** `docs/superpowers/specs/2026-05-21-catchment-routed-pluvial-model-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `model/pluvial_model.py` (new) | Fill-and-spill solver: D8 flow, depression inventory, catchment supply, spill graph, cascade, public entry point. |
| `model/hand_model.py` (modify) | Add `flow_direction_filled` — D8 flow on the conditioned filled DEM, encoded for the spill walk. |
| `scripts/fetch_esa_worldcover.py` (new) | Fetch ESA WorldCover 10 m, map land-cover classes → runoff coefficient, resample to the DEM grid. |
| `tests/test_pluvial_fillspill.py` (new) | Unit + integration tests on synthetic DEMs. |
| `scripts/fit_pluvial_baseline_era5.py` (modify) | Emit `excess_depth_m` per RP instead of the lumped `ponding_cap_m`. |
| `scripts/run_multihazard.py` (modify) | Dispatch pluvial to the new solver; `--pluvial-model` flag; precompute topography once. |
| `scripts/run_city_pipeline.py` (modify) | WorldCover fetch step; thread `--pluvial-model`. |
| `scripts/cities.py` (modify) | Document `runoff_coeff` as fallback scalar; deprecate `depression_area_fraction`. |
| `model/flood_depth_model.py` | Unchanged — `flood_depth_pluvial_ponding` retained as the `legacy` option. |
| `docs/hazard_methodology_comparison.md` (modify) | Rewrite §4 pluvial section. |

**Algorithm note for the implementer.** A depression is one connected component of `filled_dem - dem > min_depression_depth_m`, where `filled_dem` is the pysheds depression-filled DEM. Each depression is modelled with a single water level and its hypsometric (elevation–volume) curve — a deliberate, documented approximation of the Barnes et al. (2020) Fill-Spill-Merge nested hierarchy: sub-depression behaviour is captured by the hypsometric curve (at a low fill level only the deepest cells are wet), and inter-depression overflow is captured by the spill cascade. A depression's overflow destination is found by walking the flow directions of the *conditioned* DEM (pit-filled, depression-filled, flat-resolved) — that DEM is acyclic and drains every cell to the boundary, so the walk is well-defined. A naive "lowest rim cell" rule is **not** used: rim cells frequently drain back into their own depression. This is adequate for a screening-grade pluvial model and keeps the solver tractable and testable.

---

## Task 1: ESA WorldCover fetch + runoff-coefficient raster

**Files:**
- Create: `scripts/fetch_esa_worldcover.py`
- Test: `tests/test_pluvial_fillspill.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_pluvial_fillspill.py` with:

```python
"""Tests for the catchment-routed pluvial model."""
import numpy as np
import pytest


def test_worldcover_class_to_runoff_coeff():
    """Each ESA WorldCover class maps to its documented runoff coefficient."""
    from scripts.fetch_esa_worldcover import WORLDCOVER_RUNOFF_COEFF, class_to_runoff_coeff

    classes = np.array([[10, 50], [80, 40]], dtype=np.uint8)
    coeff = class_to_runoff_coeff(classes)
    assert coeff[0, 0] == pytest.approx(WORLDCOVER_RUNOFF_COEFF[10])   # tree cover
    assert coeff[0, 1] == pytest.approx(WORLDCOVER_RUNOFF_COEFF[50])   # built-up
    assert coeff[1, 0] == pytest.approx(WORLDCOVER_RUNOFF_COEFF[80])   # water
    assert coeff[1, 1] == pytest.approx(WORLDCOVER_RUNOFF_COEFF[40])   # cropland


def test_worldcover_unknown_class_falls_back():
    """An unmapped class code uses the fallback coefficient, not a crash."""
    from scripts.fetch_esa_worldcover import class_to_runoff_coeff, FALLBACK_RUNOFF_COEFF

    coeff = class_to_runoff_coeff(np.array([[0]], dtype=np.uint8))   # 0 = unmapped
    assert coeff[0, 0] == pytest.approx(FALLBACK_RUNOFF_COEFF)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pluvial_fillspill.py::test_worldcover_class_to_runoff_coeff -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.fetch_esa_worldcover'`

- [ ] **Step 3: Write minimal implementation**

Create `scripts/fetch_esa_worldcover.py`:

```python
"""
Fetch ESA WorldCover 2021 v200 (10 m global land cover) for a city DEM
bounding box and derive a per-cell runoff coefficient raster aligned to
the DEM grid.

ESA WorldCover is CC-BY 4.0, hosted as Cloud-Optimized GeoTIFFs on AWS
S3 (public, no credentials).  The 11 land-cover classes are mapped to
rational-method runoff coefficients, then the 10 m coefficient grid is
resampled (averaged) to the 30 m DEM grid so a partially-paved cell
receives an intermediate coefficient — sub-grid impervious weighting.

Usage
-----
    python scripts/fetch_esa_worldcover.py \\
        --dem data/bangkok/copernicus_dem_utm47n.tif \\
        --output data/bangkok/runoff_coeff_utm47n.tif
"""
from __future__ import annotations

from pathlib import Path

import click
import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject, transform_bounds

# ESA WorldCover v200 class code -> rational-method runoff coefficient.
WORLDCOVER_RUNOFF_COEFF: dict[int, float] = {
    10: 0.20,   # tree cover
    20: 0.30,   # shrubland
    30: 0.25,   # grassland
    40: 0.35,   # cropland
    50: 0.90,   # built-up
    60: 0.50,   # bare / sparse vegetation
    70: 0.10,   # snow and ice (absent in ASEAN domains)
    80: 1.00,   # permanent water bodies
    90: 0.60,   # herbaceous wetland
    95: 0.55,   # mangroves
    100: 0.30,  # moss and lichen
}
FALLBACK_RUNOFF_COEFF: float = 0.40


def class_to_runoff_coeff(classes: np.ndarray) -> np.ndarray:
    """Map an array of WorldCover class codes to runoff coefficients."""
    coeff = np.full(classes.shape, FALLBACK_RUNOFF_COEFF, dtype=np.float32)
    for code, value in WORLDCOVER_RUNOFF_COEFF.items():
        coeff[classes == code] = value
    return coeff
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pluvial_fillspill.py::test_worldcover_class_to_runoff_coeff tests/test_pluvial_fillspill.py::test_worldcover_unknown_class_falls_back -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Add the CLI and commit**

Append the CLI to `scripts/fetch_esa_worldcover.py`:

```python
_S3_BASE = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
)


def _tile_name(lat: float, lon: float) -> str:
    """WorldCover tile covering (lat, lon); tiles start at 3-degree multiples."""
    tlat = int(np.floor(lat / 3.0) * 3)
    tlon = int(np.floor(lon / 3.0) * 3)
    ns = f"N{tlat:02d}" if tlat >= 0 else f"S{-tlat:02d}"
    ew = f"E{tlon:03d}" if tlon >= 0 else f"W{-tlon:03d}"
    return f"ESA_WorldCover_10m_2021_v200_{ns}{ew}_Map.tif"


@click.command()
@click.option("--dem", "dem_path", type=click.Path(exists=True, path_type=Path),
              required=True, help="City DEM GeoTIFF (defines grid + CRS).")
@click.option("--output", "output_path", type=click.Path(path_type=Path),
              required=True, help="Output runoff-coefficient GeoTIFF.")
def cli(dem_path: Path, output_path: Path) -> None:
    with rasterio.open(dem_path) as dem_src:
        dem_crs = dem_src.crs
        dem_transform = dem_src.transform
        dem_w, dem_h = dem_src.width, dem_src.height
        dem_bounds = dem_src.bounds

    wgs84 = rasterio.crs.CRS.from_epsg(4326)
    lon0, lat0, lon1, lat1 = transform_bounds(dem_crs, wgs84, *dem_bounds)
    tiles = sorted({
        _tile_name(la, lo) for la in (lat0, lat1) for lo in (lon0, lon1)
    })
    click.echo(f"WorldCover tiles needed: {tiles}")

    from rasterio.merge import merge
    srcs = [rasterio.open(f"{_S3_BASE}/{t}") for t in tiles]
    mosaic, mosaic_transform = merge(srcs, bounds=(lon0, lat0, lon1, lat1))
    for s in srcs:
        s.close()
    coeff_wgs = class_to_runoff_coeff(mosaic[0])

    coeff_dem = np.empty((dem_h, dem_w), dtype=np.float32)
    reproject(
        source=coeff_wgs,
        destination=coeff_dem,
        src_transform=mosaic_transform,
        src_crs=wgs84,
        dst_transform=dem_transform,
        dst_crs=dem_crs,
        resampling=Resampling.average,
    )

    profile = {
        "driver": "GTiff", "dtype": "float32", "count": 1,
        "width": dem_w, "height": dem_h, "crs": dem_crs,
        "transform": dem_transform, "compress": "deflate", "nodata": np.nan,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(coeff_dem, 1)
    click.echo(
        f"Wrote runoff-coefficient raster: {output_path}  "
        f"(mean={np.nanmean(coeff_dem):.3f})"
    )


if __name__ == "__main__":
    cli()
```

```bash
git add scripts/fetch_esa_worldcover.py tests/test_pluvial_fillspill.py
git commit -m "feat: ESA WorldCover fetch + runoff-coefficient raster"
```

---

## Task 2: Emit `excess_depth_m` from the pluvial baseline fit

**Files:**
- Modify: `scripts/fit_pluvial_baseline_era5.py`
- Test: `tests/test_pluvial_redesign.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pluvial_redesign.py`:

```python
def test_excess_depth_m_is_drain_subtracted_rainfall():
    """excess_depth_m = max(0, design_mm - drain_capacity_mm) / 1000,
    independent of runoff_coeff and depression_area_fraction."""
    design_mm = 210.0
    drain_capacity_mm = 100.0
    excess_depth_m = max(0.0, design_mm - drain_capacity_mm) / 1000.0
    assert excess_depth_m == pytest.approx(0.110)
    # Below drain capacity -> zero excess.
    assert max(0.0, 80.0 - 100.0) / 1000.0 == pytest.approx(0.0)
```

(`pytest` is already imported at the top of `tests/test_pluvial_redesign.py`.)

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `python -m pytest tests/test_pluvial_redesign.py::test_excess_depth_m_is_drain_subtracted_rainfall -v`
Expected: PASS — this test pins the formula the code in Step 3 must emit. Proceed regardless; it guards against later regressions.

- [ ] **Step 3: Modify `fit_pluvial_baseline_era5.py`**

In `scripts/fit_pluvial_baseline_era5.py`, locate the three lines in the per-RP
loop:

```python
        excess_mm = max(0.0, design_mm - drain_capacity_mm)
        runoff_depth_m = (excess_mm / 1000.0) * runoff_coeff
        cap_m = runoff_depth_m / depression_area_fraction
```

Replace them with:

```python
        excess_mm = max(0.0, design_mm - drain_capacity_mm)
        # excess_depth_m is the post-drain rain depth (m).  The runoff
        # coefficient is now applied per-cell at run time (spatially, from
        # the WorldCover raster), so it is NOT applied here.  Likewise
        # depression_area_fraction is retired — the fill-spill model
        # distributes runoff by catchment, not by a lumped fraction.
        excess_depth_m = excess_mm / 1000.0
```

In the row-dict construction below it, replace the line setting
`"baseline_water_level_m": cap_m,` with:

```python
            "baseline_water_level_m": excess_depth_m,
```

Update the adjacent explanatory note string (the text mentioning
`ponding_cap_m; downstream flood_depth_pluvial_ponding ...`) to:

```python
                "excess_depth_m (post-drain rain depth, m); downstream "
                "flood_depth_pluvial_fillspill multiplies by the per-cell "
                "runoff coefficient and routes it by catchment.",
```

- [ ] **Step 4: Run test + a smoke check**

Run: `python -m pytest tests/test_pluvial_redesign.py -v`
Expected: PASS (all tests in the file)

Run: `python scripts/fit_pluvial_baseline_era5.py --help`
Expected: prints usage with no import error.

- [ ] **Step 5: Commit**

```bash
git add scripts/fit_pluvial_baseline_era5.py tests/test_pluvial_redesign.py
git commit -m "feat: pluvial baseline emits excess_depth_m for catchment routing"
```

---

## Task 3: Module skeleton + D8 flow direction

**Files:**
- Create: `model/pluvial_model.py`
- Test: `tests/test_pluvial_fillspill.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pluvial_fillspill.py`:

```python
def test_d8_flow_direction_points_downhill():
    """Each cell's D8 direction points at its steepest-descent neighbour;
    a local minimum has direction -1 (a sink)."""
    from model.pluvial_model import d8_flow_direction

    z = np.array([[3.0, 2.0, 1.0],
                  [3.0, 2.0, 1.0],
                  [3.0, 2.0, 1.0]], dtype=np.float64)
    fdir = d8_flow_direction(z)
    # Direction code 4 == (row 0, col +1) == due east (see _D8_DR/_D8_DC).
    assert fdir[1, 0] == 4
    assert fdir[1, 1] == 4
    assert fdir[1, 2] == -1   # rightmost column: no lower neighbour -> sink


def test_d8_flow_direction_pit_is_sink():
    """A one-cell pit surrounded by higher ground has direction -1."""
    from model.pluvial_model import d8_flow_direction

    z = np.array([[5.0, 5.0, 5.0],
                  [5.0, 1.0, 5.0],
                  [5.0, 5.0, 5.0]], dtype=np.float64)
    fdir = d8_flow_direction(z)
    assert fdir[1, 1] == -1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pluvial_fillspill.py::test_d8_flow_direction_points_downhill -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'model.pluvial_model'`

- [ ] **Step 3: Create `model/pluvial_model.py`**

```python
"""
Catchment-routed pluvial flood model (fill-and-spill cascade).

Replaces the lumped depression-fill model whose flood extent was frozen
across all return periods.  Runoff (post-drain excess rain, weighted by a
per-cell runoff coefficient) is routed by D8 catchment into topographic
depressions; each depression fills via its hypsometric curve and spills
overflow downstream through a topologically-ordered cascade.

A depression is one connected component of ``filled_dem - dem`` deeper
than ``min_depression_depth_m``.  Each depression carries a single water
level and a hypsometric (elevation-volume) curve — a deliberate,
documented approximation of the Barnes et al. (2020) Fill-Spill-Merge
nested hierarchy that is adequate for screening-grade pluvial mapping.

See docs/superpowers/specs/2026-05-21-catchment-routed-pluvial-model-design.md
"""
from __future__ import annotations

from dataclasses import dataclass

import numba
import numpy as np
from scipy import ndimage

WET_THRESHOLD_M: float = 0.05          # cells shallower than this count as dry
MIN_DEPRESSION_DEPTH_M: float = 0.5    # depressions shallower than this are noise

# D8 neighbour offsets, indexed 0..7.  Direction code i means "flow to the
# neighbour at (row + _D8_DR[i], col + _D8_DC[i])".
# 0=NW 1=N 2=NE 3=W 4=E 5=SW 6=S 7=SE
_D8_DR = (-1, -1, -1, 0, 0, 1, 1, 1)
_D8_DC = (-1, 0, 1, -1, 1, -1, 0, 1)
_D8_DIST = (1.4142135, 1.0, 1.4142135, 1.0, 1.0, 1.4142135, 1.0, 1.4142135)


@numba.njit(cache=True)
def d8_flow_direction(z: np.ndarray) -> np.ndarray:
    """Steepest-descent D8 flow direction on the raw DEM.

    Returns an int8 array of direction codes 0..7 (index into _D8_DR/_D8_DC),
    or -1 where the cell is a sink (no strictly-lower neighbour) or nodata.
    """
    rows, cols = z.shape
    fdir = np.full((rows, cols), -1, dtype=np.int8)
    for i in range(rows):
        for j in range(cols):
            zc = z[i, j]
            if not np.isfinite(zc):
                continue
            best = -1
            best_slope = 0.0
            for k in range(8):
                ii = i + _D8_DR[k]
                jj = j + _D8_DC[k]
                if ii < 0 or ii >= rows or jj < 0 or jj >= cols:
                    continue
                zn = z[ii, jj]
                if not np.isfinite(zn):
                    continue
                slope = (zc - zn) / _D8_DIST[k]
                if slope > best_slope:
                    best_slope = slope
                    best = k
            fdir[i, j] = best
    return fdir
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pluvial_fillspill.py -k d8_flow_direction -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add model/pluvial_model.py tests/test_pluvial_fillspill.py
git commit -m "feat: pluvial_model module skeleton + D8 flow direction"
```

---

## Task 4: Depression inventory

**Files:**
- Modify: `model/pluvial_model.py`
- Test: `tests/test_pluvial_fillspill.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pluvial_fillspill.py`:

```python
def test_depression_inventory_finds_deep_depressions_only():
    """Depressions shallower than min_depression_depth_m are filtered out."""
    from model.pluvial_model import build_depression_inventory

    dem = np.full((5, 5), 10.0, dtype=np.float64)
    dem[1, 1] = 6.0    # deep pit (depth 4 m) -> depression
    dem[3, 3] = 9.8    # shallow pit (depth 0.2 m) -> filtered out
    filled = dem.copy()
    filled[1, 1] = 10.0
    filled[3, 3] = 10.0

    inv = build_depression_inventory(dem, filled, cell_area_m2=900.0,
                                     min_depression_depth_m=0.5)
    assert inv.n == 1
    assert inv.pour_elev[0] == pytest.approx(10.0)
    assert inv.capacity_m3[0] == pytest.approx(4.0 * 900.0)


def test_depression_inventory_labels_cover_depression_cells():
    """inv.labels marks exactly the cells inside kept depressions (1-based)."""
    from model.pluvial_model import build_depression_inventory

    dem = np.full((5, 5), 10.0, dtype=np.float64)
    dem[2, 2] = 5.0
    filled = dem.copy()
    filled[2, 2] = 10.0
    inv = build_depression_inventory(dem, filled, cell_area_m2=900.0,
                                     min_depression_depth_m=0.5)
    assert inv.labels[2, 2] == 1
    assert inv.labels[0, 0] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pluvial_fillspill.py::test_depression_inventory_finds_deep_depressions_only -v`
Expected: FAIL with `ImportError: cannot import name 'build_depression_inventory'`

- [ ] **Step 3: Add the inventory to `model/pluvial_model.py`**

Append to `model/pluvial_model.py`:

```python
@dataclass
class DepressionInventory:
    """Per-depression topographic data, computed once per DEM.

    Attributes
    ----------
    n : int
        Number of depressions.
    labels : int32 (rows, cols)
        1-based depression id per cell; 0 = not in a kept depression.
    pour_elev : float64 (n,)
        Spill (pour-point) elevation of each depression.
    capacity_m3 : float64 (n,)
        Water volume each depression holds when filled to its pour elevation.
    sorted_beds : list[np.ndarray]
        For depression d, the bed elevations of its cells sorted ascending —
        used to invert the hypsometric curve.
    cell_area_m2 : float
        Area of one grid cell.
    """
    n: int
    labels: np.ndarray
    pour_elev: np.ndarray
    capacity_m3: np.ndarray
    sorted_beds: list
    cell_area_m2: float


def build_depression_inventory(
    dem: np.ndarray,
    filled: np.ndarray,
    cell_area_m2: float,
    min_depression_depth_m: float = MIN_DEPRESSION_DEPTH_M,
) -> DepressionInventory:
    """Inventory every depression deeper than ``min_depression_depth_m``.

    A depression is a connected component (8-connectivity) of
    ``filled - dem > 0``.  Components whose maximum depth is below
    ``min_depression_depth_m`` are discarded as DEM noise.

    Within one outer depression ``filled`` is constant and equals the
    pour-point elevation, so ``pour_elev`` is read directly from ``filled``.
    """
    depth = filled - dem
    raw_labels, n_raw = ndimage.label(depth > 0.0,
                                      structure=np.ones((3, 3), dtype=int))
    labels = np.zeros(dem.shape, dtype=np.int32)
    pour_elev: list[float] = []
    capacity: list[float] = []
    sorted_beds: list[np.ndarray] = []

    next_id = 0
    for raw in range(1, n_raw + 1):
        mask = raw_labels == raw
        if float(depth[mask].max()) < min_depression_depth_m:
            continue   # noise — drop
        next_id += 1
        labels[mask] = next_id
        beds = np.sort(dem[mask].astype(np.float64))
        pe = float(filled[mask].flat[0])   # constant within an outer depression
        pour_elev.append(pe)
        capacity.append(float(np.sum(np.maximum(0.0, pe - beds))) * cell_area_m2)
        sorted_beds.append(beds)

    return DepressionInventory(
        n=next_id,
        labels=labels,
        pour_elev=np.asarray(pour_elev, dtype=np.float64),
        capacity_m3=np.asarray(capacity, dtype=np.float64),
        sorted_beds=sorted_beds,
        cell_area_m2=cell_area_m2,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pluvial_fillspill.py -k depression_inventory -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add model/pluvial_model.py tests/test_pluvial_fillspill.py
git commit -m "feat: pluvial depression inventory with min-depth noise filter"
```

---

## Task 5: Terminal labels + catchment supply

**Files:**
- Modify: `model/pluvial_model.py`
- Test: `tests/test_pluvial_fillspill.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pluvial_fillspill.py`:

```python
def test_catchment_supply_sums_runoff_draining_into_depression():
    """Every cell's runoff is credited to the depression its D8 path ends in."""
    from model.pluvial_model import (build_depression_inventory,
                                     d8_flow_direction, compute_catchment_supply)

    dem = np.array([[5.0, 4.0, 3.0],
                    [5.0, 4.0, 3.0],
                    [5.0, 4.0, 3.0]], dtype=np.float64)
    dem[:, 2] = 0.0                       # right column is a deep pit trough
    filled = dem.copy()
    filled[:, 2] = 3.0
    inv = build_depression_inventory(dem, filled, cell_area_m2=1.0,
                                     min_depression_depth_m=0.5)
    fdir = d8_flow_direction(dem)
    runoff_volume = np.full(dem.shape, 2.0, dtype=np.float64)
    supply = compute_catchment_supply(dem, fdir, inv, runoff_volume)
    # All 9 cells drain into the single depression -> 9 * 2.0.
    assert supply[0] == pytest.approx(18.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pluvial_fillspill.py::test_catchment_supply_sums_runoff_draining_into_depression -v`
Expected: FAIL with `ImportError: cannot import name 'compute_catchment_supply'`

- [ ] **Step 3: Add terminal-label routing to `model/pluvial_model.py`**

Append to `model/pluvial_model.py`:

```python
@numba.njit(cache=True)
def _terminal_labels(fdir: np.ndarray, labels: np.ndarray,
                     order: np.ndarray) -> np.ndarray:
    """Flat array: the depression id each cell's D8 path terminates in.

    ``order`` is the cell flat-indices sorted by ascending elevation, so a
    cell is always processed after its (lower) downstream neighbour.  A
    value of -1 means the path leaves the domain or ends in a non-depression
    sink (its runoff is lost — negligible by construction).
    """
    rows, cols = fdir.shape
    term = np.full(rows * cols, -1, dtype=np.int64)
    for idx in range(order.size):
        flat = order[idx]
        i = flat // cols
        j = flat % cols
        d = fdir[i, j]
        if d < 0:
            lab = labels[i, j]
            term[flat] = lab - 1 if lab > 0 else -1
        else:
            ii = i + _D8_DR[d]
            jj = j + _D8_DC[d]
            term[flat] = term[ii * cols + jj]
    return term


def compute_catchment_supply(
    dem: np.ndarray,
    fdir: np.ndarray,
    inv: DepressionInventory,
    runoff_volume: np.ndarray,
) -> np.ndarray:
    """Total runoff volume (m3) draining into each depression.

    Each cell is credited to the depression its D8 flow path terminates in.
    """
    finite = np.isfinite(dem)
    order = np.argsort(np.where(finite, dem, np.inf), axis=None)
    term = _terminal_labels(fdir, inv.labels, order.astype(np.int64))
    rv = runoff_volume.ravel().astype(np.float64)
    valid = term >= 0
    supply = np.bincount(term[valid], weights=rv[valid],
                         minlength=max(inv.n, 1)).astype(np.float64)
    return supply[:inv.n]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pluvial_fillspill.py -k catchment_supply -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add model/pluvial_model.py tests/test_pluvial_fillspill.py
git commit -m "feat: pluvial catchment-supply routing via D8 terminal labels"
```

---

## Task 6: Spill graph — robust routing on the conditioned DEM

**Files:**
- Modify: `model/hand_model.py` (add `flow_direction_filled`)
- Modify: `model/pluvial_model.py` (add `build_spill_graph`)
- Test: `tests/test_pluvial_fillspill.py`

A depression's overflow destination is found by walking the flow directions
of the *conditioned* DEM (pit-filled, depression-filled, flat-resolved).
That DEM is acyclic and drains every cell to the domain boundary, so the
walk — start inside the depression, follow flow until it reaches another
depression's cell (the destination) or a sea / river / off-domain cell
(SINK) — is well-defined. `build_spill_graph` takes the conditioned flow
field as a plain array argument so it is unit-testable without pysheds;
`flow_direction_filled` is the pysheds wrapper that produces that array and
is exercised by the Task 8 integration tests.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pluvial_fillspill.py`:

```python
def test_build_spill_graph_walks_to_downstream_depression():
    """Walking the conditioned flow field from a depression reaches the
    downstream depression its overflow drains into."""
    from model.pluvial_model import build_spill_graph, DepressionInventory

    rows, cols = 3, 8
    dem = np.full((rows, cols), 10.0)
    labels = np.zeros((rows, cols), dtype=np.int32)
    labels[1, 1] = 1   # depression 0
    labels[1, 5] = 2   # depression 1
    inv = DepressionInventory(
        n=2, labels=labels,
        pour_elev=np.array([10.0, 10.0]),
        capacity_m3=np.array([1.0, 1.0]),
        sorted_beds=[np.array([0.0]), np.array([0.0])],
        cell_area_m2=900.0,
    )
    fdir_filled = np.full((rows, cols), -1, dtype=np.int8)
    fdir_filled[1, 1:7] = 4   # cells (1,1)..(1,6) all flow east
    sea = np.zeros((rows, cols), dtype=bool)
    river = np.zeros((rows, cols), dtype=bool)
    dest = build_spill_graph(dem, inv, fdir_filled, sea, river)
    assert dest[0] == 1     # depression 0 spills into depression 1
    assert dest[1] == -1    # depression 1 walk runs off the domain edge


def test_build_spill_graph_river_is_sink():
    """A depression whose overflow path hits a river cell spills to -1."""
    from model.pluvial_model import build_spill_graph, DepressionInventory

    rows, cols = 3, 6
    dem = np.full((rows, cols), 10.0)
    labels = np.zeros((rows, cols), dtype=np.int32)
    labels[1, 1] = 1
    inv = DepressionInventory(
        n=1, labels=labels, pour_elev=np.array([10.0]),
        capacity_m3=np.array([1.0]), sorted_beds=[np.array([0.0])],
        cell_area_m2=900.0,
    )
    fdir_filled = np.full((rows, cols), -1, dtype=np.int8)
    fdir_filled[1, 1:4] = 4
    sea = np.zeros((rows, cols), dtype=bool)
    river = np.zeros((rows, cols), dtype=bool)
    river[1, 3] = True
    dest = build_spill_graph(dem, inv, fdir_filled, sea, river)
    assert dest[0] == -1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pluvial_fillspill.py::test_build_spill_graph_walks_to_downstream_depression -v`
Expected: FAIL with `ImportError: cannot import name 'build_spill_graph'`

- [ ] **Step 3: Add `build_spill_graph` to `model/pluvial_model.py`**

Append to `model/pluvial_model.py`:

```python
def build_spill_graph(
    dem: np.ndarray,
    inv: DepressionInventory,
    fdir_filled: np.ndarray,
    sea_mask: np.ndarray,
    river_mask: np.ndarray,
) -> np.ndarray:
    """Spill destination of each depression (-1 = overflow leaves the domain).

    ``fdir_filled`` is the D8 flow field of the conditioned (pit-filled,
    depression-filled, flat-resolved) DEM, encoded 0..7 / -1 — see
    ``model.hand_model.flow_direction_filled``.  It is acyclic and drains
    every cell to the boundary.  The walk starts at a cell of the depression
    and follows ``fdir_filled`` until it reaches a cell belonging to another
    depression (the destination) or a sea / river / off-domain cell (SINK).
    """
    rows, cols = dem.shape
    labels = inv.labels
    spill_dest = np.full(inv.n, -1, dtype=np.int64)
    max_steps = rows * cols
    for d in range(inv.n):
        cell = np.argwhere(labels == d + 1)
        if cell.size == 0:
            continue
        i, j = int(cell[0, 0]), int(cell[0, 1])
        for _ in range(max_steps):
            lab = labels[i, j]
            if lab != 0 and lab - 1 != d:
                spill_dest[d] = lab - 1          # reached another depression
                break
            if sea_mask[i, j] or river_mask[i, j]:
                break                            # SINK
            dd = fdir_filled[i, j]
            if dd < 0:
                break                            # off-domain / nodata -> SINK
            i += _D8_DR[dd]
            j += _D8_DC[dd]
            if i < 0 or i >= rows or j < 0 or j >= cols:
                break                            # ran off the edge -> SINK
    return spill_dest
```

- [ ] **Step 4: Run the spill-graph test to verify it passes**

Run: `python -m pytest tests/test_pluvial_fillspill.py -k build_spill_graph -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Add `flow_direction_filled` to `model/hand_model.py`**

Append to `model/hand_model.py`:

```python
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
```

- [ ] **Step 6: Smoke-test `flow_direction_filled` and commit**

Run:
```bash
python -c "import numpy as np; from affine import Affine; import rasterio; \
from model.hand_model import flow_direction_filled; \
z = np.array([[3.,2.,1.],[3.,2.,1.],[3.,2.,1.]]); \
p = {'driver':'GTiff','width':3,'height':3,'count':1,'dtype':'float32', \
'crs':rasterio.crs.CRS.from_epsg(32647), \
'transform':Affine(30.,0.,0.,0.,-30.,0.),'nodata':-9999.0}; \
f = flow_direction_filled(z, p); print('flow_direction_filled OK', f.shape, f.dtype)"
```
Expected: prints `flow_direction_filled OK (3, 3) int8` with no error.

```bash
git add model/hand_model.py model/pluvial_model.py tests/test_pluvial_fillspill.py
git commit -m "feat: pluvial spill graph via conditioned-DEM flow routing"
```

---

## Task 7: Fill-spill cascade

**Files:**
- Modify: `model/pluvial_model.py`
- Test: `tests/test_pluvial_fillspill.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pluvial_fillspill.py`:

```python
def test_fill_level_partial_fill_below_capacity():
    """A depression supplied with less than its capacity fills part-way; the
    water level solves V(level) = supply via the hypsometric curve."""
    from model.pluvial_model import _fill_level

    beds = np.array([0.0, 1.0, 2.0, 3.0])   # 4 cells, area 1 m2
    pour_elev = 4.0
    # Supply 1.0 m3: only the deepest cell fills; h - 0 = 1 -> h = 1.
    assert _fill_level(beds, pour_elev, 1.0, 1.0) == pytest.approx(1.0)
    # Supply 6.0 m3: cells 0,1,2 below h; 3h - 3 = 6 -> h = 3.
    assert _fill_level(beds, pour_elev, 1.0, 6.0) == pytest.approx(3.0)


def test_cascade_spills_excess_downstream():
    """An over-supplied depression fills to its pour level and routes the
    surplus into its downstream depression."""
    from model.pluvial_model import run_cascade

    # Two single-cell depressions (bed 0, area 1).  dep 0 pours at 5 m
    # (capacity = 5 m3); dep 1 pours at 100 m (capacity = 100 m3).
    # dep 0 spills into dep 1; dep 1 spills off-domain.
    pour_elev = np.array([5.0, 100.0])
    capacity = np.array([5.0, 100.0])
    sorted_beds = [np.array([0.0]), np.array([0.0])]
    spill_dest = np.array([1, -1])
    supply = np.array([30.0, 0.0])   # dep 0 over-supplied by 25 m3
    levels = run_cascade(pour_elev, capacity, sorted_beds, spill_dest,
                         supply, cell_area_m2=1.0)
    assert levels[0] == pytest.approx(5.0)     # dep 0 filled to its pour level
    assert levels[1] == pytest.approx(25.0)    # dep 1 holds the 25 m3 surplus
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pluvial_fillspill.py::test_fill_level_partial_fill_below_capacity -v`
Expected: FAIL with `ImportError: cannot import name '_fill_level'`

- [ ] **Step 3: Add the cascade to `model/pluvial_model.py`**

Append to `model/pluvial_model.py`:

```python
def _fill_level(
    sorted_beds: np.ndarray,
    pour_elev: float,
    cell_area_m2: float,
    supply_m3: float,
) -> float:
    """Water level at which the depression stores ``supply_m3``.

    Inverts the hypsometric curve V(h) = cell_area * sum_i max(0, h - bed_i).
    Capped at ``pour_elev`` (the caller handles overflow beyond capacity).
    """
    if supply_m3 <= 0.0:
        return float(sorted_beds[0])
    n = sorted_beds.size
    prefix = np.cumsum(sorted_beds)            # prefix[k] = sum of beds 0..k
    for k in range(n):
        # Volume when the level is exactly sorted_beds[k] (cells 0..k-1 wet).
        below = prefix[k - 1] if k > 0 else 0.0
        vol_at_bed_k = cell_area_m2 * (k * sorted_beds[k] - below)
        if vol_at_bed_k > supply_m3:
            # Level lies between sorted_beds[k-1] and sorted_beds[k]: k cells wet.
            level = (supply_m3 / cell_area_m2 + below) / k
            return min(level, pour_elev)
    # All n cells submerged.
    level = (supply_m3 / cell_area_m2 + prefix[n - 1]) / n
    return min(level, pour_elev)


def _topological_order(spill_dest: np.ndarray) -> list:
    """Depression ids ordered so each appears before its spill destination."""
    n = spill_dest.size
    indegree = np.zeros(n, dtype=np.int64)
    for d in range(n):
        dst = spill_dest[d]
        if dst >= 0:
            indegree[dst] += 1
    queue = [d for d in range(n) if indegree[d] == 0]
    order: list = []
    while queue:
        d = queue.pop()
        order.append(d)
        dst = spill_dest[d]
        if dst >= 0:
            indegree[dst] -= 1
            if indegree[dst] == 0:
                queue.append(int(dst))
    # The priority-flood inventory cannot produce a cycle; if one somehow
    # appears, append the remainder defensively so no depression is dropped.
    if len(order) < n:
        seen = set(order)
        order.extend(d for d in range(n) if d not in seen)
    return order


def run_cascade(
    pour_elev: np.ndarray,
    capacity_m3: np.ndarray,
    sorted_beds: list,
    spill_dest: np.ndarray,
    supply_m3: np.ndarray,
    cell_area_m2: float,
) -> np.ndarray:
    """Fill every depression and cascade overflow downstream.

    Returns the final water level of each depression.  Processing in
    topological order guarantees a depression's total inflow is final
    before it is filled.
    """
    n = pour_elev.size
    inflow = supply_m3.astype(np.float64).copy()
    levels = np.array([float(b[0]) for b in sorted_beds], dtype=np.float64)
    for d in _topological_order(spill_dest):
        total_in = inflow[d]
        if total_in >= capacity_m3[d]:
            levels[d] = pour_elev[d]
            surplus = total_in - capacity_m3[d]
            dst = spill_dest[d]
            if dst >= 0:
                inflow[dst] += surplus       # else surplus leaves the domain
        else:
            levels[d] = _fill_level(sorted_beds[d], pour_elev[d],
                                    cell_area_m2, total_in)
    return levels
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pluvial_fillspill.py -k "fill_level or cascade" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add model/pluvial_model.py tests/test_pluvial_fillspill.py
git commit -m "feat: pluvial fill-spill cascade with hypsometric fill"
```

---

## Task 8: Public entry point + integration tests

**Files:**
- Modify: `model/pluvial_model.py`
- Test: `tests/test_pluvial_fillspill.py`

- [ ] **Step 1: Write the failing test**

Add this helper near the top of `tests/test_pluvial_fillspill.py` (after the
`import` lines):

```python
def _profile(dem, cell_m=30.0):
    """A complete rasterio profile for a synthetic DEM — pysheds needs a real
    GeoTIFF behind its Grid, so width/height/crs/transform must all be set."""
    import rasterio
    from affine import Affine
    return {
        "driver": "GTiff", "width": dem.shape[1], "height": dem.shape[0],
        "count": 1, "dtype": "float32",
        "crs": rasterio.crs.CRS.from_epsg(32647),
        "transform": Affine(cell_m, 0.0, 0.0, 0.0, -cell_m, 0.0),
        "nodata": -9999.0,
    }


def _bowl_dem():
    """13x13 gently west-high sloping plateau (~10 m) with one central
    6 m-deep conical bowl.  The slope guarantees the conditioned DEM is not
    perfectly flat so pysheds flat-resolution always has an outlet."""
    z = np.full((13, 13), 10.0, dtype=np.float64)
    for i in range(13):
        for j in range(13):
            z[i, j] = 10.0 + (12 - j) * 0.05          # gentle west-high slope
            r = ((i - 6) ** 2 + (j - 6) ** 2) ** 0.5
            if r < 4:
                z[i, j] = z[i, j] - (4 - r) * 1.5     # carve the bowl
    return z
```

Add the integration tests:

```python
def test_fillspill_extent_grows_with_rainfall():
    """Pluvial extent must grow as the return-period rain depth increases —
    the whole point of the redesign."""
    from model.pluvial_model import flood_depth_pluvial_fillspill

    dem = _bowl_dem()
    profile = _profile(dem)
    sea = np.zeros(dem.shape, dtype=bool)
    river = np.zeros(dem.shape, dtype=bool)

    def wet_area(excess_depth_m):
        depth = flood_depth_pluvial_fillspill(
            dem, excess_depth_m, runoff_coeff=0.75,
            sea_mask=sea, river_mask=river, profile=profile,
        )
        return int(np.sum(np.isfinite(depth) & (depth > 0)))

    small = wet_area(0.002)    # ~RP2 — little runoff
    large = wet_area(0.200)    # ~RP1000 — much runoff
    assert large > small, "extent must grow with rainfall"


def test_fillspill_dry_when_no_rain():
    """Zero excess rain -> zero pluvial flooding."""
    from model.pluvial_model import flood_depth_pluvial_fillspill

    dem = _bowl_dem()
    profile = _profile(dem)
    sea = np.zeros(dem.shape, dtype=bool)
    depth = flood_depth_pluvial_fillspill(
        dem, 0.0, runoff_coeff=0.75, sea_mask=sea, river_mask=sea,
        profile=profile,
    )
    assert np.nansum(depth) == pytest.approx(0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pluvial_fillspill.py::test_fillspill_extent_grows_with_rainfall -v`
Expected: FAIL with `ImportError: cannot import name 'flood_depth_pluvial_fillspill'`

- [ ] **Step 3: Add the public entry point to `model/pluvial_model.py`**

Append to `model/pluvial_model.py`:

```python
def flood_depth_pluvial_fillspill(
    dem: np.ndarray,
    excess_depth_m: float,
    runoff_coeff,
    sea_mask: np.ndarray,
    river_mask: np.ndarray,
    profile: dict,
    *,
    min_depression_depth_m: float = MIN_DEPRESSION_DEPTH_M,
    wet_threshold_m: float = WET_THRESHOLD_M,
) -> np.ndarray:
    """Catchment-routed pluvial flood depth (metres).

    Parameters
    ----------
    dem : float64 (rows, cols)
        Land DEM in metres.  Sea cells must already be NaN.
    excess_depth_m : float
        Post-drain rain depth for the return period (m) — the value emitted
        by ``fit_pluvial_baseline_era5.py``.
    runoff_coeff : np.ndarray or float
        Per-cell runoff coefficient raster (WorldCover-derived) or a scalar
        fallback.
    sea_mask, river_mask : bool (rows, cols)
        Overflow spilled onto these cells leaves the domain.
    profile : dict
        Rasterio profile — ``profile["transform"]`` gives the pixel size and
        pysheds needs the full profile to condition the DEM.
    min_depression_depth_m : float
        Depressions shallower than this are treated as DEM noise.
    wet_threshold_m : float
        Cells shallower than this in the result are set to 0 (dry).

    Returns
    -------
    depth : float32 (rows, cols)
        Pluvial ponding depth; NaN where ``dem`` is NaN.
    """
    from model.hand_model import fill_depressions, flow_direction_filled

    tr = profile["transform"]
    cell_area_m2 = abs(tr.a * tr.e)

    dem = dem.astype(np.float64)
    filled = fill_depressions(dem, profile).astype(np.float64)

    inv = build_depression_inventory(dem, filled, cell_area_m2,
                                     min_depression_depth_m)
    depth = np.zeros(dem.shape, dtype=np.float64)
    if inv.n == 0 or excess_depth_m <= 0.0:
        depth[~np.isfinite(dem)] = np.nan
        return depth.astype(np.float32)

    # Per-cell runoff volume = excess rain * runoff coeff * cell area.
    rc = (runoff_coeff if np.ndim(runoff_coeff) else
          np.full(dem.shape, float(runoff_coeff)))
    rc = np.where(np.isfinite(dem) & np.isfinite(rc), rc, 0.0)
    runoff_volume = excess_depth_m * rc * cell_area_m2

    fdir = d8_flow_direction(dem)                       # raw DEM, for supply
    fdir_filled = flow_direction_filled(dem, profile)   # conditioned, for spill
    supply = compute_catchment_supply(dem, fdir, inv, runoff_volume)
    spill_dest = build_spill_graph(dem, inv, fdir_filled, sea_mask, river_mask)
    levels = run_cascade(inv.pour_elev, inv.capacity_m3, inv.sorted_beds,
                         spill_dest, supply, cell_area_m2)

    # Paint depth = max(0, water level - bed) for every depression cell.
    for d in range(inv.n):
        cells = inv.labels == (d + 1)
        depth[cells] = np.maximum(0.0, levels[d] - dem[cells])

    depth[depth < wet_threshold_m] = 0.0
    depth[~np.isfinite(dem)] = np.nan
    return depth.astype(np.float32)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pluvial_fillspill.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add model/pluvial_model.py tests/test_pluvial_fillspill.py
git commit -m "feat: pluvial fill-spill public entry point"
```

---

## Task 9: Dispatch in `run_multihazard.py`

**Files:**
- Modify: `scripts/run_multihazard.py`
- Test: `tests/test_pluvial_fillspill.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pluvial_fillspill.py`:

```python
def test_run_multihazard_exposes_pluvial_model_flag():
    """run_multihazard.py advertises the --pluvial-model option."""
    import subprocess, sys
    out = subprocess.run(
        [sys.executable, "scripts/run_multihazard.py", "--help"],
        capture_output=True, text=True,
    )
    assert "--pluvial-model" in out.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pluvial_fillspill.py::test_run_multihazard_exposes_pluvial_model_flag -v`
Expected: FAIL — `--pluvial-model` is not yet in the help text.

- [ ] **Step 3: Modify `scripts/run_multihazard.py`**

3a. Add the import near the other `model` imports at the top:

```python
from model.pluvial_model import flood_depth_pluvial_fillspill
```

3b. Add two CLI options alongside the other `@click.option` declarations on
the `cli` command:

```python
@click.option(
    "--pluvial-model",
    "pluvial_model",
    type=click.Choice(["fillspill", "legacy"]),
    default="fillspill",
    show_default=True,
    help="Pluvial solver: 'fillspill' = catchment-routed fill-and-spill "
         "cascade (extent grows with RP); 'legacy' = the lumped "
         "depression-fill model (frozen extent, kept for A/B comparison).",
)
@click.option(
    "--runoff-coeff-raster",
    "runoff_coeff_raster_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="WorldCover-derived per-cell runoff-coefficient GeoTIFF aligned to "
         "the DEM.  When omitted a uniform scalar of 0.75 is used.",
)
```

3c. Add `pluvial_model: str` and `runoff_coeff_raster_path: Path | None` to the
`cli` function signature with the other parameters.

3d. After the DEM is loaded and before the return-period loop — next to where
`sea_mask` is read — load the runoff coefficient:

```python
    # Runoff coefficient for the fill-spill pluvial model: per-cell raster
    # when supplied, else a uniform scalar.
    runoff_coeff_arr: np.ndarray | float
    if runoff_coeff_raster_path is not None:
        with rasterio.open(runoff_coeff_raster_path) as rc_src:
            runoff_coeff_arr = rc_src.read(1).astype(np.float64)
        if runoff_coeff_arr.shape != dem.shape:
            raise ValueError("runoff-coeff raster shape does not match the DEM")
    else:
        runoff_coeff_arr = 0.75
```

3e. Determine the river mask once, before the loop. Search the file for an
existing `channel_mask` variable (used by `derive_tidal_channel_seeds`). If it
exists, add:

```python
    pluvial_river_mask = (
        channel_mask if channel_mask is not None
        else np.zeros(dem.shape, dtype=bool)
    )
```

If no `channel_mask` variable exists, instead add:

```python
    pluvial_river_mask = np.zeros(dem.shape, dtype=bool)
```

3f. Find the pluvial depth branch in the return-period loop — the line:

```python
        elif hazard == "pluvial" and sea_mask is not None:
            depth = flood_depth_pluvial_ponding(dem_land, level_m, profile)
```

Replace it with:

```python
        elif hazard == "pluvial" and sea_mask is not None:
            if pluvial_model == "fillspill":
                # `level_m` for pluvial rows is excess_depth_m (post-drain
                # rain depth, m) — see fit_pluvial_baseline_era5.py.
                depth = flood_depth_pluvial_fillspill(
                    dem_land, level_m, runoff_coeff_arr,
                    sea_mask=sea_mask, river_mask=pluvial_river_mask,
                    profile=profile,
                )
            else:
                depth = flood_depth_pluvial_ponding(dem_land, level_m, profile)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pluvial_fillspill.py::test_run_multihazard_exposes_pluvial_model_flag -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/run_multihazard.py tests/test_pluvial_fillspill.py
git commit -m "feat: run_multihazard dispatches pluvial to fill-spill solver"
```

---

## Task 10: WorldCover step + flag threading in `run_city_pipeline.py`

**Files:**
- Modify: `scripts/run_city_pipeline.py`
- Test: `tests/test_pluvial_fillspill.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pluvial_fillspill.py`:

```python
def test_run_city_pipeline_exposes_pluvial_model_flag():
    """run_city_pipeline.py advertises the --pluvial-model option."""
    import subprocess, sys
    out = subprocess.run(
        [sys.executable, "scripts/run_city_pipeline.py", "--help"],
        capture_output=True, text=True,
    )
    assert "--pluvial-model" in out.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pluvial_fillspill.py::test_run_city_pipeline_exposes_pluvial_model_flag -v`
Expected: FAIL — option not present.

- [ ] **Step 3: Modify `scripts/run_city_pipeline.py`**

3a. Add the CLI option next to the other `@click.option` declarations:

```python
@click.option(
    "--pluvial-model",
    "pluvial_model",
    type=click.Choice(["fillspill", "legacy"]),
    default="fillspill",
    show_default=True,
    help="Pluvial solver passed through to run_multihazard.py.",
)
```

3b. Add `pluvial_model: str` to the `cli` function signature.

3c. After the sea-mask build step (Step 3 in that file) and before the
run-model step, add a WorldCover step:

```python
    # ------------------------------------------------------------------
    # 3b. ESA WorldCover runoff-coefficient raster (for fill-spill pluvial)
    # ------------------------------------------------------------------
    runoff_coeff_raster: Path | None = None
    if pluvial_model == "fillspill":
        runoff_coeff_raster = city_data / f"runoff_coeff_{utm_tag}.tif"
        if runoff_coeff_raster.exists():
            click.echo(f"[info] Reusing runoff-coeff raster: {runoff_coeff_raster}")
        else:
            click.echo("\n=== Step 3b: Fetch ESA WorldCover runoff coefficient ===")
            _run([
                py, str(PROJECT_ROOT / "scripts" / "fetch_esa_worldcover.py"),
                "--dem",    str(dem_path),
                "--output", str(runoff_coeff_raster),
            ])
```

3d. Find where `run_model_cmd` (the `run_multihazard.py` invocation list) is
assembled. Append the new arguments after it is built:

```python
    run_model_cmd.extend(["--pluvial-model", pluvial_model])
    if runoff_coeff_raster is not None and runoff_coeff_raster.exists():
        run_model_cmd.extend(["--runoff-coeff-raster", str(runoff_coeff_raster)])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pluvial_fillspill.py::test_run_city_pipeline_exposes_pluvial_model_flag -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/run_city_pipeline.py tests/test_pluvial_fillspill.py
git commit -m "feat: run_city_pipeline fetches WorldCover and threads pluvial-model flag"
```

---

## Task 11: Documentation — `cities.py` and methodology doc

**Files:**
- Modify: `scripts/cities.py`
- Modify: `docs/hazard_methodology_comparison.md`

- [ ] **Step 1: Update `cities.py` field docstrings**

In `scripts/cities.py`, find the `depression_area_fraction` field comment
block and replace it with:

```python
    # DEPRECATED (2026-05-21): unused by the catchment-routed fill-spill
    # pluvial model.  Retained only so the legacy --pluvial-model=legacy
    # path keeps working.  See docs/superpowers/specs/
    # 2026-05-21-catchment-routed-pluvial-model-design.md
    depression_area_fraction: float = 0.10
```

Find the `runoff_coeff` field comment and append to it:

```python
    # With --pluvial-model=fillspill this is only the fallback scalar used
    # when no WorldCover runoff_coeff_<utm>.tif raster exists for the city.
```

- [ ] **Step 2: Update the methodology doc**

In `docs/hazard_methodology_comparison.md`, locate the §4 pluvial section
(search for `depression_area_fraction` or `ponding_cap`). Add this paragraph
at the start of the pluvial model description:

```markdown
**Catchment-routed pluvial model (2026-05-21).** Pluvial flooding is computed
by a fill-and-spill cascade (`model/pluvial_model.py`): post-drain excess
rainfall, weighted per cell by an ESA WorldCover-derived runoff coefficient,
is routed by D8 catchment into topographic depressions; each depression fills
via its hypsometric curve and spills overflow downstream along the conditioned
DEM's flow field. Unlike the previous lumped depression-fill model — whose
flood *extent* was identical at every return period — extent now grows with
return period. The legacy model is retained behind `--pluvial-model legacy`.
See `docs/superpowers/specs/2026-05-21-catchment-routed-pluvial-model-design.md`.
```

- [ ] **Step 3: Verify the docs still parse**

Run: `python -c "import scripts.cities"`
Expected: no error (the dataclass still parses).

- [ ] **Step 4: Commit**

```bash
git add scripts/cities.py docs/hazard_methodology_comparison.md
git commit -m "docs: catchment-routed pluvial model in cities.py and methodology"
```

---

## Task 12: Precompute topography once per city

This task fulfils design-spec enhancement A: the depression inventory, both
flow fields and the spill graph are RP-independent, so they are computed once
per city and reused across all nine return periods rather than rebuilt nine
times. It is correctness-neutral — the per-RP results are identical — so it is
sequenced after the solver is proven (Tasks 3–8) and dispatched (Task 9).

**Files:**
- Modify: `model/pluvial_model.py`
- Modify: `scripts/run_multihazard.py`
- Test: `tests/test_pluvial_fillspill.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pluvial_fillspill.py`:

```python
def test_prebuilt_topography_matches_per_call_result():
    """Routing an RP through a prebuilt PluvialTopography gives the identical
    depth raster as the all-in-one entry point."""
    from model.pluvial_model import (build_pluvial_topography,
                                     flood_depth_pluvial_fillspill,
                                     route_pluvial_rp)

    dem = _bowl_dem()
    profile = _profile(dem)
    sea = np.zeros(dem.shape, dtype=bool)
    river = np.zeros(dem.shape, dtype=bool)

    topo = build_pluvial_topography(dem, sea, river, profile)
    routed = route_pluvial_rp(topo, excess_depth_m=0.05, runoff_coeff=0.75)
    direct = flood_depth_pluvial_fillspill(
        dem, 0.05, runoff_coeff=0.75, sea_mask=sea, river_mask=river,
        profile=profile,
    )
    assert np.array_equal(np.nan_to_num(routed), np.nan_to_num(direct))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pluvial_fillspill.py::test_prebuilt_topography_matches_per_call_result -v`
Expected: FAIL with `ImportError: cannot import name 'build_pluvial_topography'`

- [ ] **Step 3: Add the topography object to `model/pluvial_model.py`**

Append to `model/pluvial_model.py`:

```python
@dataclass
class PluvialTopography:
    """RP-independent topographic state for the fill-spill pluvial model.

    Built once per city and reused for every return period.
    """
    dem: np.ndarray
    inv: DepressionInventory
    fdir: np.ndarray            # raw-DEM D8, for catchment supply
    spill_dest: np.ndarray
    cell_area_m2: float
    wet_threshold_m: float


def build_pluvial_topography(
    dem: np.ndarray,
    sea_mask: np.ndarray,
    river_mask: np.ndarray,
    profile: dict,
    *,
    min_depression_depth_m: float = MIN_DEPRESSION_DEPTH_M,
    wet_threshold_m: float = WET_THRESHOLD_M,
) -> PluvialTopography:
    """Build the RP-independent topographic state once for a city."""
    from model.hand_model import fill_depressions, flow_direction_filled

    tr = profile["transform"]
    cell_area_m2 = abs(tr.a * tr.e)
    dem = dem.astype(np.float64)
    filled = fill_depressions(dem, profile).astype(np.float64)
    inv = build_depression_inventory(dem, filled, cell_area_m2,
                                     min_depression_depth_m)
    fdir = d8_flow_direction(dem)
    fdir_filled = flow_direction_filled(dem, profile)
    spill_dest = build_spill_graph(dem, inv, fdir_filled, sea_mask, river_mask)
    return PluvialTopography(dem=dem, inv=inv, fdir=fdir,
                             spill_dest=spill_dest, cell_area_m2=cell_area_m2,
                             wet_threshold_m=wet_threshold_m)


def route_pluvial_rp(
    topo: PluvialTopography,
    excess_depth_m: float,
    runoff_coeff,
) -> np.ndarray:
    """Pluvial depth (float32) for one return period, reusing ``topo``."""
    dem = topo.dem
    inv = topo.inv
    depth = np.zeros(dem.shape, dtype=np.float64)
    if inv.n == 0 or excess_depth_m <= 0.0:
        depth[~np.isfinite(dem)] = np.nan
        return depth.astype(np.float32)

    rc = (runoff_coeff if np.ndim(runoff_coeff) else
          np.full(dem.shape, float(runoff_coeff)))
    rc = np.where(np.isfinite(dem) & np.isfinite(rc), rc, 0.0)
    runoff_volume = excess_depth_m * rc * topo.cell_area_m2

    supply = compute_catchment_supply(dem, topo.fdir, inv, runoff_volume)
    levels = run_cascade(inv.pour_elev, inv.capacity_m3, inv.sorted_beds,
                         topo.spill_dest, supply, topo.cell_area_m2)
    for d in range(inv.n):
        cells = inv.labels == (d + 1)
        depth[cells] = np.maximum(0.0, levels[d] - dem[cells])

    depth[depth < topo.wet_threshold_m] = 0.0
    depth[~np.isfinite(dem)] = np.nan
    return depth.astype(np.float32)
```

Then rewrite the body of `flood_depth_pluvial_fillspill` to delegate, so the
two code paths cannot diverge:

```python
def flood_depth_pluvial_fillspill(
    dem: np.ndarray,
    excess_depth_m: float,
    runoff_coeff,
    sea_mask: np.ndarray,
    river_mask: np.ndarray,
    profile: dict,
    *,
    min_depression_depth_m: float = MIN_DEPRESSION_DEPTH_M,
    wet_threshold_m: float = WET_THRESHOLD_M,
) -> np.ndarray:
    """Catchment-routed pluvial flood depth (metres) for a single return
    period.  Convenience wrapper: builds the topography then routes one RP.
    For multiple return periods on the same DEM, call
    ``build_pluvial_topography`` once and ``route_pluvial_rp`` per RP.
    """
    topo = build_pluvial_topography(
        dem, sea_mask, river_mask, profile,
        min_depression_depth_m=min_depression_depth_m,
        wet_threshold_m=wet_threshold_m,
    )
    return route_pluvial_rp(topo, excess_depth_m, runoff_coeff)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pluvial_fillspill.py -v`
Expected: PASS (all tests, including the new one and the Task 8 tests).

- [ ] **Step 5: Use the prebuilt topography in `run_multihazard.py`**

In `scripts/run_multihazard.py`, change the import added in Task 9 to:

```python
from model.pluvial_model import build_pluvial_topography, route_pluvial_rp
```

Before the return-period loop (next to the runoff-coeff load from Task 9 step
3d), add:

```python
    # Build the RP-independent pluvial topography once when fill-spill is on.
    pluvial_topo = None
    if pluvial_model == "fillspill" and sea_mask is not None:
        pluvial_topo = build_pluvial_topography(
            dem_land, sea_mask, pluvial_river_mask, profile,
        )
```

Replace the pluvial branch from Task 9 step 3f with:

```python
        elif hazard == "pluvial" and sea_mask is not None:
            if pluvial_model == "fillspill":
                # `level_m` for pluvial rows is excess_depth_m (m).
                depth = route_pluvial_rp(pluvial_topo, level_m, runoff_coeff_arr)
            else:
                depth = flood_depth_pluvial_ponding(dem_land, level_m, profile)
```

- [ ] **Step 6: Verify and commit**

Run: `python -m pytest tests/test_pluvial_fillspill.py -v`
Expected: PASS.

Run: `python scripts/run_multihazard.py --help`
Expected: prints usage with no import error.

```bash
git add model/pluvial_model.py scripts/run_multihazard.py tests/test_pluvial_fillspill.py
git commit -m "perf: precompute pluvial topography once, reuse across return periods"
```

---

## Task 13: Validation & rollout

**Files:**
- No code changes — this task runs the pipeline and validators.

- [ ] **Step 1: Run the full new test suite**

Run: `python -m pytest tests/test_pluvial_fillspill.py tests/test_pluvial_redesign.py -v`
Expected: all PASS.

- [ ] **Step 2: Re-fit the pluvial baselines**

Re-run `fit_pluvial_baseline_era5.py` (via `scripts/_refit_pluvial_ifd.py` if
that is the project's refit wrapper — inspect it first) for all 11 city
configs so each hazard CSV's pluvial rows carry `excess_depth_m`.
Expected: each `data/<city>/hazard_levels_*.csv` pluvial `water_level_m`
column now holds small values (roughly 0.0–0.2 m).

- [ ] **Step 3: Fetch WorldCover for the calibration city**

Run:
```bash
python scripts/fetch_esa_worldcover.py \
    --dem data/singapore/copernicus_dem_utm48n.tif \
    --output data/singapore/runoff_coeff_utm48n.tif
```
Expected: writes the raster; the printed mean coefficient is plausible
(~0.4–0.7 for a dense city).

- [ ] **Step 4: Run Singapore pluvial and validate against PUB**

Run the Singapore pipeline with `--pluvial-model fillspill`, then:
```bash
python scripts/validate_pluvial_singapore.py
```
Expected: the validator reports its verdict. If it FAILs, tune
`WET_THRESHOLD_M` / `MIN_DEPRESSION_DEPTH_M` in `model/pluvial_model.py` and the
`WORLDCOVER_RUNOFF_COEFF` mapping in `scripts/fetch_esa_worldcover.py`, re-run,
and repeat until it passes. Commit the tuned constants:
```bash
git add model/pluvial_model.py scripts/fetch_esa_worldcover.py
git commit -m "tune: pluvial fill-spill constants to pass Singapore PUB validation"
```

- [ ] **Step 5: Confirm the IDF-anchor validators are unaffected**

Run:
```bash
python scripts/validate_pluvial_idf_anchors.py
python scripts/validate_pluvial_all_cities.py
```
Expected: same verdicts as before this work (the rainfall side is unchanged).
If they regressed, stop and investigate before rollout.

- [ ] **Step 6: Roll out to all cities and verify RP-dependence**

Re-run every city pipeline with `--pluvial-model fillspill`. Then verify
pluvial flooded area now grows with return period:
```bash
python scripts/_review_defended_vs_undefended.py
```
Expected: no monotonicity anomalies for pluvial. Spot-check
`outputs/_viz/01_rp_comparison/` panels — pluvial green should now expand from
RP2 to RP1000 rather than being identical. A/B one city against
`--pluvial-model legacy` to confirm the difference.

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "feat: roll out catchment-routed pluvial model to all cities"
```

---

## Self-Review Notes

- **Spec coverage:** fill-and-spill cascade (Tasks 3–8); robust spill via
  conditioned-DEM flow routing (Task 6 — replaces the naive lowest-rim-cell
  rule that plan self-review found unsound); enhancement A precompute-once
  (Task 12 — `PluvialTopography` built once, reused across all 9 RPs);
  enhancement B river/sea outflow (Task 6 `build_spill_graph`); enhancement C
  min-depression filter (Task 4); enhancement D shares pysheds DEM
  conditioning with HAND (`flow_direction_filled` lives in `model/hand_model.py`
  beside `fill_depressions`); enhancement E WorldCover runoff coefficient
  (Tasks 1, 10); `--pluvial-model legacy` retained (Tasks 9, 12); re-validation
  against PUB (Task 13).
- **Type consistency:** `DepressionInventory` fields (`n`, `labels`,
  `pour_elev`, `capacity_m3`, `sorted_beds`, `cell_area_m2`) are produced in
  Task 4 and consumed unchanged in Tasks 5, 6, 8, 12. `d8_flow_direction`,
  `compute_catchment_supply`, `build_spill_graph`, `run_cascade`,
  `_fill_level`, `flow_direction_filled`, `build_pluvial_topography`,
  `route_pluvial_rp`, `flood_depth_pluvial_fillspill` signatures match every
  call site in the tests and in `run_multihazard.py`.
- **Resolved during self-review:** (1) the spill graph was rewritten to walk
  the conditioned-DEM flow field — the original "lowest rim cell" rule
  produced self-loops because rim cells often drain back into their own
  depression; (2) the cascade test now uses a capacity consistent with its
  pour elevation and bed; (3) the integration-test profile is a complete
  rasterio profile so pysheds can condition the synthetic DEM.
