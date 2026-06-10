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
MAX_DEPRESSION_DEPTH_M: float = 3.0    # depressions deeper than this are not
                                       # urban surface-ponding basins — they are
                                       # quarries, valleys, reservoir basins or
                                       # DEM artifacts, and are excluded (as sea
                                       # and reservoirs are)
MIN_DEPRESSION_AREA_CELLS: int = 9     # depressions smaller than this are
                                       # sub-pixel DSM artefacts (inter-building
                                       # voids in the Copernicus GLO-30 DSM).
                                       # 9 cells = 8,100 m2 ~ 90m x 90m —
                                       # roughly the minimum real urban ponding
                                       # feature that is resolvable at 30m.
                                       # This is the primary guard against the
                                       # thousands of 1-5 cell DSM pits that
                                       # the depth filter alone does not remove.

# D8 neighbour offsets, indexed 0..7.  Direction code i means "flow to the
# neighbour at (row + _D8_DR[i], col + _D8_DC[i])".
# 0=NW 1=N 2=NE 3=W 4=E 5=SW 6=S 7=SE
_D8_DR = (-1, -1, -1, 0, 0, 1, 1, 1)
_D8_DC = (-1, 0, 1, -1, 1, -1, 0, 1)
_D8_DIST = (2.0 ** 0.5, 1.0, 2.0 ** 0.5, 1.0, 1.0, 2.0 ** 0.5, 1.0, 2.0 ** 0.5)  # diagonal neighbours are sqrt(2) cell-widths away


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
                # Ties resolve to the lowest direction code (k processed in
                # order 0..7).  Strictly > 0 means flat/equal-elevation
                # neighbours never become flow targets.
                if slope > best_slope:
                    best_slope = slope
                    best = k
            fdir[i, j] = best
    return fdir


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
    sorted_beds: list[np.ndarray]
    cell_area_m2: float


def build_depression_inventory(
    dem: np.ndarray,
    filled: np.ndarray,
    cell_area_m2: float,
    min_depression_depth_m: float = MIN_DEPRESSION_DEPTH_M,
    max_depression_depth_m: float = MAX_DEPRESSION_DEPTH_M,
    min_depression_area_cells: int = MIN_DEPRESSION_AREA_CELLS,
) -> DepressionInventory:
    """Inventory every depression deeper than ``min_depression_depth_m``.

    A depression is a connected component (8-connectivity) of
    ``filled - dem > 0``.  Components whose maximum depth is below
    ``min_depression_depth_m`` are discarded as DEM noise.  Components
    whose maximum depth exceeds ``max_depression_depth_m`` are excluded
    as non-ponding features (quarries, valleys, reservoir basins, or DEM
    artifacts) — they are not urban surface-ponding basins.  Components
    smaller than ``min_depression_area_cells`` are discarded as sub-pixel
    DSM artefacts (e.g., inter-building voids in the Copernicus GLO-30).

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
    # O(cells x components) scan — acceptable as a once-per-city precomputation.
    for raw in range(1, n_raw + 1):
        mask = raw_labels == raw
        n_cells = int(mask.sum())
        if n_cells < min_depression_area_cells:
            continue   # sub-pixel DSM artefact — drop
        d_max = float(depth[mask].max())
        if d_max < min_depression_depth_m:
            continue   # sub-noise depression — drop
        if d_max > max_depression_depth_m:
            continue   # too deep for an urban ponding basin (quarry, valley,
                       # reservoir basin, or DEM artifact) — drop
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


@numba.njit(cache=True)
def _terminal_labels(fdir: np.ndarray, labels: np.ndarray,
                     order: np.ndarray) -> np.ndarray:
    """Flat array: the depression id each cell's D8 path terminates in.

    ``order`` is the cell flat-indices sorted by ascending elevation, so a
    cell is always processed after its (lower) downstream neighbour.  A
    value of -1 means the path leaves the domain or ends in a non-depression
    sink: a sub-noise pit, or a depression excluded by the inventory's
    min/max depth filters (a quarry, valley, reservoir basin or DEM
    artifact).  Runoff routed to a -1 terminal is dropped from pluvial
    accounting — for excluded deep features that is intentional: they
    absorb or drain their inflow rather than surface-pond, exactly as
    sea / river sinks do.
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
            # Safe because d8_flow_direction only assigns a direction to
            # strictly-lower neighbours, so ascending-elevation order
            # guarantees the downstream cell is already resolved here.
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
    # First cell of each depression, found in a single O(cells) pass —
    # the walk start is arbitrary (any cell of a filled depression drains
    # to the same pour point on the conditioned DEM).
    uniq_labels, first_flat = np.unique(labels.ravel(), return_index=True)
    first_cell = {int(v): int(first_flat[k])
                  for k, v in enumerate(uniq_labels) if v > 0}
    for d in range(inv.n):
        fi = first_cell.get(d + 1)
        if fi is None:
            continue
        # On the conditioned DEM every cell of a filled depression drains to
        # the same pour point, so any cell is a valid walk start.
        i, j = divmod(fi, cols)
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

    ``capacity_m3[d]`` must equal the volume implied by ``sorted_beds[d]``
    filled to ``pour_elev[d]`` — they are consistent by construction from
    ``build_depression_inventory``.  The ``>= capacity`` vs ``_fill_level``
    branch boundary relies on that consistency.
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
    max_depression_depth_m: float = MAX_DEPRESSION_DEPTH_M,
    min_depression_area_cells: int = MIN_DEPRESSION_AREA_CELLS,
    wet_threshold_m: float = WET_THRESHOLD_M,
) -> PluvialTopography:
    """Build the RP-independent topographic state once for a city.

    Parameters
    ----------
    dem : np.ndarray
        Land DEM in metres; sea cells must be NaN.
    sea_mask : np.ndarray
        Boolean array; overflow spilled onto these cells leaves the domain.
    river_mask : np.ndarray
        Boolean array; overflow spilled onto these cells leaves the domain.
    profile : dict
        Rasterio profile for the DEM.  pysheds needs the full profile and the
        transform provides the pixel size used to compute ``cell_area_m2``.
    min_depression_depth_m : float
        Depressions shallower than this value are treated as DEM noise and
        discarded.
    max_depression_depth_m : float
        Depressions deeper than this value are excluded as non-ponding features
        (quarries, valleys, reservoir basins, or DEM artifacts).
    min_depression_area_cells : int
        Depressions with fewer cells than this value are treated as sub-pixel
        DSM artefacts (inter-building voids in the Copernicus GLO-30 DSM) and
        discarded.  See ``MIN_DEPRESSION_AREA_CELLS`` for rationale.
    wet_threshold_m : float
        Carried on the returned object; cells shallower than this are set dry
        when routing individual return periods.

    Returns
    -------
    PluvialTopography
        RP-independent topographic state ready for ``route_pluvial_rp``.
    """
    from model.hand_model import fill_depressions, flow_direction_filled

    tr = profile["transform"]
    cell_area_m2 = abs(tr.a * tr.e)
    dem = dem.astype(np.float64)
    filled = fill_depressions(dem, profile).astype(np.float64)
    inv = build_depression_inventory(dem, filled, cell_area_m2,
                                     min_depression_depth_m,
                                     max_depression_depth_m,
                                     min_depression_area_cells)
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
    """Pluvial depth (float32) for one return period, reusing ``topo``.

    Returns
    -------
    np.ndarray
        float32 ponding depth (metres).  NaN where the DEM is NaN.  An
        all-zero (NaN-masked) raster is returned when the topography has no
        depressions or ``excess_depth_m <= 0``.
    """
    dem = topo.dem
    inv = topo.inv
    depth = np.zeros(dem.shape, dtype=np.float64)
    if inv.n == 0 or excess_depth_m <= 0.0:
        depth[~np.isfinite(dem)] = np.nan
        return depth.astype(np.float32)

    rc = (runoff_coeff if np.ndim(runoff_coeff) else
          np.full(dem.shape, float(runoff_coeff)))
    rc = np.where(np.isfinite(dem) & np.isfinite(rc), rc, 0.0)
    # per-cell runoff volume = excess rain * runoff coeff * cell area
    runoff_volume = excess_depth_m * rc * topo.cell_area_m2

    supply = compute_catchment_supply(dem, topo.fdir, inv, runoff_volume)
    levels = run_cascade(inv.pour_elev, inv.capacity_m3, inv.sorted_beds,
                         topo.spill_dest, supply, topo.cell_area_m2)
    # paint depth = max(0, water level - bed) for every depression cell
    for d in range(inv.n):
        cells = inv.labels == (d + 1)
        depth[cells] = np.maximum(0.0, levels[d] - dem[cells])

    depth[depth < topo.wet_threshold_m] = 0.0
    depth[~np.isfinite(dem)] = np.nan
    return depth.astype(np.float32)


def flood_depth_pluvial_fillspill(
    dem: np.ndarray,
    excess_depth_m: float,
    runoff_coeff,
    sea_mask: np.ndarray,
    river_mask: np.ndarray,
    profile: dict,
    *,
    min_depression_depth_m: float = MIN_DEPRESSION_DEPTH_M,
    max_depression_depth_m: float = MAX_DEPRESSION_DEPTH_M,
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
        max_depression_depth_m=max_depression_depth_m,
        wet_threshold_m=wet_threshold_m,
    )
    return route_pluvial_rp(topo, excess_depth_m, runoff_coeff)
