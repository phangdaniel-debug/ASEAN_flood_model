"""
2D Local Inertia flood solver (Bates, Horritt & Fewtrell, 2010).

Reference
---------
Bates P.D., Horritt M.S. & Fewtrell T.J. (2010).
    A simple inertial formulation of the shallow water equations for
    efficient two-dimensional flood inundation modelling.
    Journal of Hydrology 387(1-2): 33-45.
    https://doi.org/10.1016/j.jhydrol.2010.03.027

Overview
--------
Solves the simplified shallow-water equations by omitting the nonlinear
advection term (u·∇u), which is negligible for slowly-evolving flood waves
at low Froude numbers (Fr << 1).  Appropriate for:

  - Urban coastal inundation (storm surge, sea-level rise)
  - Riverine overbank flooding
  - Any scenario where Fr < ~0.5 (Singapore flatland flooding)

What this adds over bathtub / HAND
------------------------------------
  bathtub     HAND       inertial
  -------     ----       --------
  static      static     dynamic pressure gradient → backwater effects ✓
  no mass     D8 topo    strict mass conservation ✓
  no vel      no vel     flow velocity → h×v hazard product ✓
  no connect  D8 only    hydraulic connectivity across full 2D domain ✓

Equations
---------
Interface unit discharge (x-direction, analogous for y):

    q_x^{n+1}_{i,j} = ( q_x^n_{i,j} - g · h_f · (η_{i,j+1} - η_{i,j}) / Δx · Δt )
                       / ( 1 + g · n² · |q_x^n_{i,j}| · Δt / h_f^{7/3} )

where:
    η_{i,j} = z_{i,j} + d_{i,j}              water-surface elevation (m above datum)
    h_f      = max(η_L, η_R) − max(z_L, z_R) flow depth at interface (≥ 0)
    n        = Manning's roughness coefficient
    g        = 9.806 m/s²

Mass conservation (continuity):

    d^{n+1}_{i,j} = d^n_{i,j}
                  − (Δt/Δx) · (q^{n+1}_{x,i,j} − q^{n+1}_{x,i,j−1})
                  − (Δt/Δy) · (q^{n+1}_{y,i,j} − q^{n+1}_{y,i−1,j})

Stability:  Δt ≤ CFL_ALPHA · Δx / (√(g·d_max) + u_max)

Array conventions
-----------------
All arrays are (rows, cols) for cell-centred quantities.
qx is (rows, cols-1): qx[i, j] is the unit discharge at the interface
    between cell (i, j) and cell (i, j+1).  Positive = flow in +x direction.
qy is (rows-1, cols): qy[i, j] is the unit discharge at the interface
    between cell (i, j) and cell (i+1, j).  Positive = flow in +y direction.
NaN in z = nodata / wall cell (no flux crosses its boundaries).
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np

try:
    import numba
    _HAS_NUMBA = True
except ImportError:
    _HAS_NUMBA = False

G: float = 9.806       # gravitational acceleration (m s⁻²)
MIN_DEPTH: float = 1e-3  # minimum interface depth to be treated as wet (m)
CFL_ALPHA: float = 0.7   # CFL safety factor (< 1)

# Padding (cells) around the active solver bbox when cropping is enabled.
# Generous enough that the bbox doesn't bite into the wet plume during the run.
_CROP_PAD_CELLS: int = 32


# ---------------------------------------------------------------------------
# Internal kernels
# ---------------------------------------------------------------------------
#
# Two versions of each hot kernel coexist:
#   * `_flux_x_np` etc. — the original pure-numpy implementations, kept as
#     a verified reference and used when numba is unavailable.
#   * `_flux_x_jit` etc. — numba @njit(parallel=True, fastmath=True) versions
#     compiled once at import time, used when numba is available.
#
# The module-level `_flux_x` etc. names bind to the JIT version when
# `_HAS_NUMBA` is True, otherwise to the numpy version.  All three caller
# sites in `run_inertial` therefore continue to work unchanged.

# ---------- numba JIT kernels (preferred path when numba available) -----------

if _HAS_NUMBA:
    @numba.njit(parallel=True, fastmath=True, cache=True)
    def _flux_x_jit(z, d, qx, n, dx, dt):
        rows, cols = z.shape
        out = np.zeros_like(qx)
        n2 = n * n
        for i in numba.prange(rows):
            for j in range(cols - 1):
                zL = z[i, j]; zR = z[i, j + 1]
                if not (np.isfinite(zL) and np.isfinite(zR)):
                    continue  # wall: zero flux
                eta_L = zL + d[i, j]
                eta_R = zR + d[i, j + 1]
                eta_max = eta_L if eta_L > eta_R else eta_R
                z_max = zL if zL > zR else zR
                h_flow = eta_max - z_max
                if h_flow <= MIN_DEPTH:
                    continue
                deta_dx = (eta_R - eta_L) / dx
                q = qx[i, j]
                aq = q if q >= 0.0 else -q
                h73 = h_flow ** (7.0 / 3.0)
                denom = 1.0 + G * n2 * aq * dt / h73
                out[i, j] = (q - G * h_flow * deta_dx * dt) / denom
        return out

    @numba.njit(parallel=True, fastmath=True, cache=True)
    def _flux_y_jit(z, d, qy, n, dy, dt):
        rows, cols = z.shape
        out = np.zeros_like(qy)
        n2 = n * n
        for i in numba.prange(rows - 1):
            for j in range(cols):
                zT = z[i, j]; zB = z[i + 1, j]
                if not (np.isfinite(zT) and np.isfinite(zB)):
                    continue
                eta_T = zT + d[i, j]
                eta_B = zB + d[i + 1, j]
                eta_max = eta_T if eta_T > eta_B else eta_B
                z_max = zT if zT > zB else zB
                h_flow = eta_max - z_max
                if h_flow <= MIN_DEPTH:
                    continue
                deta_dy = (eta_B - eta_T) / dy
                q = qy[i, j]
                aq = q if q >= 0.0 else -q
                h73 = h_flow ** (7.0 / 3.0)
                denom = 1.0 + G * n2 * aq * dt / h73
                out[i, j] = (q - G * h_flow * deta_dy * dt) / denom
        return out

    @numba.njit(parallel=True, fastmath=True, cache=True)
    def _continuity_jit(d, qx, qy, dx, dy, dt):
        rows, cols = d.shape
        out = np.empty_like(d)
        inv_dx = dt / dx
        inv_dy = dt / dy
        for i in numba.prange(rows):
            for j in range(cols):
                # x-divergence: qx[i,j-1] (left face in) − qx[i,j] (right face out)
                fl = qx[i, j - 1] if j > 0 else 0.0
                fr = qx[i, j]     if j < cols - 1 else 0.0
                # y-divergence: qy[i-1,j] (top face in) − qy[i,j] (bottom face out)
                ft = qy[i - 1, j] if i > 0 else 0.0
                fb = qy[i, j]     if i < rows - 1 else 0.0
                d_new = d[i, j] - inv_dx * (fr - fl) - inv_dy * (fb - ft)
                out[i, j] = d_new if d_new > 0.0 else 0.0
        return out


# ---------- pure-numpy fallbacks (verified reference) ------------------------

def _flux_x_np(
    z: np.ndarray,
    d: np.ndarray,
    qx: np.ndarray,
    n: float,
    dx: float,
    dt: float,
) -> np.ndarray:
    """Update x-direction unit discharges for one timestep."""
    eta = z + d
    h_flow = np.maximum(
        0.0,
        np.maximum(eta[:, :-1], eta[:, 1:]) - np.maximum(z[:, :-1], z[:, 1:]),
    )
    wet = h_flow > MIN_DEPTH

    deta_dx = (eta[:, 1:] - eta[:, :-1]) / dx
    # friction denominator: 1 + g n² |q| Δt / h^(7/3)
    h73 = np.where(wet, h_flow ** (7.0 / 3.0), 1.0)
    denom = 1.0 + G * n**2 * np.abs(qx) * dt / h73

    qx_new = np.where(wet, (qx - G * h_flow * deta_dx * dt) / denom, 0.0)

    # Zero flux across nodata walls
    wall = ~np.isfinite(z[:, :-1]) | ~np.isfinite(z[:, 1:])
    return np.where(wall, 0.0, qx_new)


def _flux_y_np(
    z: np.ndarray,
    d: np.ndarray,
    qy: np.ndarray,
    n: float,
    dy: float,
    dt: float,
) -> np.ndarray:
    """Update y-direction unit discharges for one timestep."""
    eta = z + d
    h_flow = np.maximum(
        0.0,
        np.maximum(eta[:-1, :], eta[1:, :]) - np.maximum(z[:-1, :], z[1:, :]),
    )
    wet = h_flow > MIN_DEPTH

    deta_dy = (eta[1:, :] - eta[:-1, :]) / dy
    h73 = np.where(wet, h_flow ** (7.0 / 3.0), 1.0)
    denom = 1.0 + G * n**2 * np.abs(qy) * dt / h73

    qy_new = np.where(wet, (qy - G * h_flow * deta_dy * dt) / denom, 0.0)

    wall = ~np.isfinite(z[:-1, :]) | ~np.isfinite(z[1:, :])
    return np.where(wall, 0.0, qy_new)


def _continuity_np(
    d: np.ndarray,
    qx: np.ndarray,
    qy: np.ndarray,
    dx: float,
    dy: float,
    dt: float,
) -> np.ndarray:
    """Apply the finite-difference continuity equation to update depth."""
    # Flux divergence in x: div_x[i,j] = qx[i,j] - qx[i,j-1]
    # (boundary faces have zero flux by construction — qx is (rows, cols-1))
    div_x = np.zeros_like(d)
    div_x[:, :-1] += qx   # right face of cell j
    div_x[:, 1:]  -= qx   # left  face of cell j  (= right face of cell j-1)

    div_y = np.zeros_like(d)
    div_y[:-1, :] += qy
    div_y[1:, :]  -= qy

    d_new = d - (dt / dx) * div_x - (dt / dy) * div_y
    return np.maximum(0.0, d_new)


# ---------- dispatcher bindings ---------------------------------------------
# Choose the JIT kernels when numba is available; fall back to numpy otherwise.
if _HAS_NUMBA:
    _flux_x = _flux_x_jit
    _flux_y = _flux_y_jit
    _continuity = _continuity_jit
else:
    _flux_x = _flux_x_np
    _flux_y = _flux_y_np
    _continuity = _continuity_np


def _adaptive_dt(
    d: np.ndarray,
    qx: np.ndarray,
    qy: np.ndarray,
    dx: float,
    dy: float,
    dt_max: float,
    sea_mask: np.ndarray | None = None,
) -> float:
    """CFL-limited adaptive timestep.

    Sea cells are fixed Dirichlet BCs and are excluded from the CFL
    condition — their (potentially large) depths would otherwise impose
    an unnecessarily small timestep before any land flooding begins.
    """
    # Only land cells participate in the CFL condition
    if sea_mask is not None:
        wet = (d > MIN_DEPTH) & ~sea_mask
    else:
        wet = d > MIN_DEPTH

    if not wet.any():
        return dt_max

    c_max = float(np.sqrt(G * d[wet]).max())

    # Interface-based velocity estimates (all interfaces, conservative)
    v_max = 0.0
    h_x = 0.5 * (d[:, :-1] + d[:, 1:])
    valid_x = h_x > MIN_DEPTH
    if valid_x.any():
        v_max = max(v_max, float(np.abs(qx[valid_x] / h_x[valid_x]).max()))

    h_y = 0.5 * (d[:-1, :] + d[1:, :])
    valid_y = h_y > MIN_DEPTH
    if valid_y.any():
        v_max = max(v_max, float(np.abs(qy[valid_y] / h_y[valid_y]).max()))

    dt_cfl = CFL_ALPHA * min(dx, dy) / (c_max + v_max + 1e-10)
    return min(dt_cfl, dt_max)


def _cell_velocity(
    d: np.ndarray,
    qx: np.ndarray,
    qy: np.ndarray,
) -> np.ndarray:
    """
    Approximate cell-centred flow speed (m/s) from face unit discharges.

    Each cell receives contributions from both of its adjacent interfaces.
    Cells with depth < MIN_DEPTH are assigned speed 0.
    """
    vx = np.zeros_like(d)
    vy = np.zeros_like(d)

    h_x = 0.5 * (d[:, :-1] + d[:, 1:])
    valid_x = h_x > MIN_DEPTH
    h_x_safe = np.where(valid_x, h_x, 1.0)
    u_face = np.where(valid_x, qx / h_x_safe, 0.0)
    vx[:, :-1] += 0.5 * u_face
    vx[:, 1:]  += 0.5 * u_face

    h_y = 0.5 * (d[:-1, :] + d[1:, :])
    valid_y = h_y > MIN_DEPTH
    h_y_safe = np.where(valid_y, h_y, 1.0)
    v_face = np.where(valid_y, qy / h_y_safe, 0.0)
    vy[:-1, :] += 0.5 * v_face
    vy[1:, :]  += 0.5 * v_face

    speed = np.sqrt(vx**2 + vy**2)
    speed[~(d > MIN_DEPTH)] = 0.0
    return speed


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def _compute_solver_bbox(
    z: np.ndarray,
    sea_mask: np.ndarray,
    max_wl: float,
    pad: int = _CROP_PAD_CELLS,
) -> tuple[int, int, int, int]:
    """Return ``(i0, i1, j0, j1)`` half-open bbox of cells the solver must touch.

    A cell is "potentially wet" if it is in ``sea_mask`` or its bed elevation
    is at or below ``max_wl``.  The bbox of all such cells (plus ``pad``
    cells of buffer) is the minimum domain the solver needs to evolve.
    Cells outside the bbox stay dry forever; we can drop them.

    Returns the bbox covering the full domain if more than 75 % of finite
    cells qualify (cropping not worthwhile).
    """
    rows, cols = z.shape
    candidate = sea_mask | ((z <= max_wl) & np.isfinite(z))
    if candidate.sum() > 0.75 * np.isfinite(z).sum():
        return 0, rows, 0, cols
    ys, xs = np.where(candidate)
    if len(ys) == 0:
        return 0, rows, 0, cols
    i0 = max(0, int(ys.min()) - pad)
    i1 = min(rows, int(ys.max()) + pad + 1)
    j0 = max(0, int(xs.min()) - pad)
    j1 = min(cols, int(xs.max()) + pad + 1)
    return i0, i1, j0, j1


def run_inertial(
    z: np.ndarray,
    sea_mask: np.ndarray,
    wl_boundary: float | np.ndarray | Callable[[float], float],
    initial_depth: np.ndarray | None = None,
    n: float = 0.06,
    dx: float = 30.0,
    dy: float = 30.0,
    t_end: float = 21_600.0,
    dt_max: float = 30.0,
    convergence_tol: float = 1e-3,
    convergence_window: int = 100,
    progress_interval: int = 500,
    compute_velocity: bool = False,
    crop_bbox: bool = True,
) -> dict:
    """
    Run a 2D local inertia flood simulation.

    Boundary conditions
    -------------------
    Sea cells (``sea_mask == True``) are held at a Dirichlet water-surface
    elevation.  ``wl_boundary`` may be either a fixed float (static BC,
    equivalent to bathtub at steady state) or a callable ``wl_fn(t_s) ->
    float`` that returns the WSE at simulated time ``t_s`` (seconds).
    Passing a time-varying hydrograph produces physically meaningful
    dynamic propagation: wave front advance, partial inundation during
    ramp-up, and post-surge drainage.  At the domain edge, zero-flux
    conditions are imposed by construction (qx/qy arrays are smaller than
    the cell array).

    Warm start
    ----------
    Pass ``initial_depth`` to hot-start from an existing bathtub or HAND
    depth raster.  Starting near the solution typically reduces the number
    of timesteps to convergence by 3–5×.

    Convergence
    -----------
    The simulation stops when the mean absolute depth change over
    ``convergence_window`` consecutive steps falls below
    ``convergence_tol`` metres, or when the simulated time reaches
    ``t_end``, whichever comes first.

    Parameters
    ----------
    z : float64 (rows, cols)
        Bed elevation in metres (EGM2008).  NaN = nodata / wall.
    sea_mask : bool (rows, cols)
        True for cells held at ``wl_boundary``.
    wl_boundary : float or Callable[[float], float]
        Water-surface elevation at sea cells (m, EGM2008).  Pass a float
        for a static (steady-state) BC or a callable ``wl_fn(t_s)`` for a
        time-varying surge hydrograph.  The callable receives the current
        simulated time in seconds and must return a float WSE.
    initial_depth : float64 (rows, cols) or None
        Warm-start depth (m).  None = start from a dry bed.
    n : float
        Manning's roughness coefficient.
        Typical values: 0.02 open water, 0.05 urban paved, 0.08 urban dense.
    dx, dy : float
        Cell dimensions (m).  Must match the DEM's projected CRS pixel size.
    t_end : float
        Maximum simulation duration (s).  Default 6 hours.
    dt_max : float
        Maximum allowed timestep (s).  The CFL condition will further reduce
        this when the flow is fast or shallow.
    convergence_tol : float
        Mean |Δd| threshold for early stopping (m).  Default 1e-3 m (1 mm)
        is appropriate for flood-mapping applications where the useful severity
        threshold starts at 150 mm.  Tighten to 1e-4 only if sub-millimetre
        accuracy of the final water surface is required.
    convergence_window : int
        Number of consecutive steps over which mean |Δd| is evaluated.
        Default 100 (was 200) gives faster detection with negligible effect on
        accuracy once the surge has peaked and the domain is draining.
    progress_interval : int
        Print a status line every this many steps.
    compute_velocity : bool
        If True, compute and return ``peak_velocity`` and ``peak_hv`` at every
        timestep (adds ~15–20 % per-step cost).  Default False skips the
        velocity kernel; ``peak_velocity`` and ``peak_hv`` are returned as
        zero arrays.  Set True only when the velocity/hazard-product outputs
        are actually needed downstream.

    Returns
    -------
    dict with keys:
        ``peak_depth``    float32 (rows, cols) — maximum depth at each cell (m)
        ``peak_velocity`` float32 (rows, cols) — peak flow speed (m/s);
                          zero array when ``compute_velocity=False``
        ``peak_hv``       float32 (rows, cols) — peak depth × speed (m²/s);
                          zero array when ``compute_velocity=False``
        ``final_depth``   float32 (rows, cols) — depth at end of run (m)
        ``elapsed_s``     float  — simulated time reached (s)
        ``n_steps``       int    — number of timesteps taken
        ``converged``     bool   — whether convergence criterion was met
    """
    full_rows, full_cols = z.shape

    # ---- Optional domain crop --------------------------------------------------
    # Determine the smallest bounding box that the wet plume can ever occupy
    # (sea cells + every land cell with bed <= max plausible WL + a buffer).
    # All arrays inside the hot loop are then sliced to this bbox, halving or
    # better the per-step work in cities where most of the bbox is dry.
    if crop_bbox:
        if callable(wl_boundary):
            # Sample the hydrograph to find its peak
            sample_ts = np.linspace(0.0, t_end, 24)
            peak_wl = max(float(np.nanmax(np.asarray(wl_boundary(t)))) for t in sample_ts)
        elif isinstance(wl_boundary, np.ndarray):
            # Per-cell WSE field: peak over the boundary cells only.
            _bvals = wl_boundary[sea_mask]
            peak_wl = float(np.nanmax(_bvals)) if _bvals.size else 0.0
        else:
            peak_wl = float(wl_boundary)
        i0, i1, j0, j1 = _compute_solver_bbox(z, sea_mask, peak_wl + 1.0)
        if (i1 - i0) * (j1 - j0) < 0.95 * full_rows * full_cols:
            print(
                f"  Inertial solver: cropping bbox from "
                f"{full_rows}×{full_cols} ({full_rows*full_cols:,} cells) to "
                f"{i1-i0}×{j1-j0} ({(i1-i0)*(j1-j0):,} cells) "
                f"— {100*(1 - (i1-i0)*(j1-j0)/(full_rows*full_cols)):.0f}% reduction",
                flush=True,
            )
            z = z[i0:i1, j0:j1].copy()
            sea_mask = sea_mask[i0:i1, j0:j1].copy()
            if initial_depth is not None:
                initial_depth = initial_depth[i0:i1, j0:j1].copy()
            if isinstance(wl_boundary, np.ndarray):
                wl_boundary = wl_boundary[i0:i1, j0:j1].copy()
            _bbox = (i0, i1, j0, j1)
        else:
            _bbox = None
    else:
        _bbox = None

    rows, cols = z.shape
    land = np.isfinite(z) & ~sea_mask

    # Detect boundary-condition kind. Three forms are supported:
    #   - float                      : uniform WSE held at all boundary cells (coastal)
    #   - Callable[[float], float]   : time-varying uniform WSE (surge hydrograph)
    #   - ndarray (rows, cols)       : STATIC PER-CELL WSE field (riverine — the river
    #                                  surface slopes with the bed, so each channel cell is
    #                                  held at bed+overbank; the spill then routes onto the
    #                                  floodplain hydrodynamically, unlike static HAND).
    wl_is_fn = callable(wl_boundary)
    wl_is_arr = isinstance(wl_boundary, np.ndarray)

    # Pre-compute safe bed (replaces NaN with 0 for depth arithmetic only)
    z_safe = np.where(np.isfinite(z), z, 0.0)

    # Initial boundary depth field d_sea = max(0, WSE - bed). For the array BC this is
    # computed once (static); for scalar/callable it is a broadcast scalar recomputed each
    # step when time-varying.
    if wl_is_arr:
        wl_t = float(np.nanmax(np.where(sea_mask, wl_boundary, np.nan)))  # label only
        d_sea = np.maximum(0.0, wl_boundary - z_safe)
    else:
        wl_t = wl_boundary(0.0) if wl_is_fn else float(wl_boundary)  # type: ignore[operator]
        d_sea = np.maximum(0.0, wl_t - z_safe)

    # ---- Initialise depth ----
    if initial_depth is not None:
        d = np.where(land, np.asarray(initial_depth, dtype=np.float64), 0.0)
    else:
        d = np.zeros((rows, cols), dtype=np.float64)

    d[~np.isfinite(z)] = 0.0

    # Impose the Dirichlet BC at boundary cells
    d = np.where(sea_mask, d_sea, d)

    qx = np.zeros((rows, cols - 1), dtype=np.float64)
    qy = np.zeros((rows - 1, cols), dtype=np.float64)

    peak_depth = d.copy()
    peak_vel   = np.zeros((rows, cols), dtype=np.float64)  # only populated when compute_velocity=True

    t = 0.0
    step = 0
    recent_changes: list[float] = []
    converged = False

    bc_label = "wl_fn(t)" if wl_is_fn else f"wl={wl_t:.3f}m"
    print(
        f"  Inertial solver: {rows}×{cols} cells  "
        f"dx={dx:.0f}m  n={n}  {bc_label}  "
        f"t_end={t_end/3600:.1f}h  "
        f"{'warm-start' if initial_depth is not None else 'cold-start'}",
        flush=True,
    )

    while t < t_end and step < 100_000:
        dt = _adaptive_dt(d, qx, qy, dx, dy, dt_max, sea_mask=sea_mask)
        dt = min(dt, t_end - t)
        if dt < 1e-6:
            break

        # Update time-varying boundary condition before applying fluxes
        if wl_is_fn:
            wl_t = wl_boundary(t)  # type: ignore[operator]
            d_sea = np.maximum(0.0, wl_t - z_safe)

        qx = _flux_x(z, d, qx, n, dx, dt)
        qy = _flux_y(z, d, qy, n, dy, dt)
        d_new = _continuity(d, qx, qy, dx, dy, dt)

        # Re-impose Dirichlet BC at sea cells and zero at nodata
        d_new = np.where(sea_mask, d_sea, d_new)
        d_new[~np.isfinite(z)] = 0.0

        # Track peak depth (always).  Velocity is optional — skip it by
        # default because _cell_velocity costs ~15–20 % per-step and the
        # output is unused in most pipeline invocations.
        peak_depth = np.maximum(peak_depth, d_new)
        if compute_velocity:
            vel = _cell_velocity(d_new, qx, qy)
            peak_vel = np.maximum(peak_vel, vel)

        # Convergence check (wet land cells only).
        # Using all land cells inflates the denominator when most of the
        # domain is dry (e.g. early in a surge ramp-up), driving mean_change
        # to near-zero and triggering spurious early stopping.
        wet_land = land & (d_new > MIN_DEPTH)
        if wet_land.any():
            mean_change = float(np.mean(np.abs(d_new[wet_land] - d[wet_land])))
        else:
            mean_change = float("inf")  # dry domain — never converged
        recent_changes.append(mean_change)
        if len(recent_changes) > convergence_window:
            recent_changes.pop(0)

        if step % progress_interval == 0:
            wet_count = int(np.sum(d_new[land] > MIN_DEPTH))
            wl_suffix = f"  wl={wl_t:.3f}m" if wl_is_fn else ""
            print(
                f"  step={step:5d}  t={t/3600:.2f}h  "
                f"dt={dt:.1f}s  wet={wet_count:,}  "
                f"mean_dD={mean_change:.2e}m{wl_suffix}",
                flush=True,
            )

        d = d_new
        t += dt
        step += 1

        rolling_mean = float(np.mean(recent_changes)) if recent_changes else float("inf")
        if (
            len(recent_changes) == convergence_window
            and np.isfinite(rolling_mean)
            and rolling_mean < convergence_tol
        ):
            converged = True
            print(
                f"  Converged at step={step}  t={t/3600:.2f}h  "
                f"(mean_dD={rolling_mean:.2e}m < {convergence_tol})",
                flush=True,
            )
            break

    if compute_velocity:
        peak_hv = (peak_depth * peak_vel).astype(np.float32)
        peak_vel[~np.isfinite(z)] = np.nan
        peak_hv[~np.isfinite(z)]  = np.nan
    else:
        # Return zero arrays (same shape) so callers that check the key still work
        peak_hv  = np.zeros((rows, cols), dtype=np.float32)
        peak_vel = np.zeros((rows, cols), dtype=np.float32)

    peak_depth[~np.isfinite(z)] = np.nan

    # ---- Restore cropped outputs to full-domain extents if cropping was used ---
    if _bbox is not None:
        i0, i1, j0, j1 = _bbox
        def _restore(arr, fill):
            full = np.full((full_rows, full_cols), fill, dtype=arr.dtype)
            full[i0:i1, j0:j1] = arr
            return full
        peak_depth = _restore(peak_depth.astype(np.float32), np.nan)
        peak_vel   = _restore(peak_vel.astype(np.float32),   np.nan if compute_velocity else 0.0)
        peak_hv    = _restore(peak_hv.astype(np.float32),    np.nan if compute_velocity else 0.0)
        d          = _restore(d.astype(np.float32),          0.0)

    return {
        "peak_depth":    peak_depth.astype(np.float32),
        "peak_velocity": peak_vel.astype(np.float32),
        "peak_hv":       peak_hv,
        "final_depth":   d.astype(np.float32),
        "elapsed_s":     t,
        "n_steps":       step,
        "converged":     converged,
    }
