"""Rain-on-grid pluvial flood model.

Solves the 2-D local-inertial shallow-water equations with a spatially
distributed *rainfall source term* to simulate flash-flood ponding driven by
drainage-capacity exceedance — the dominant pluvial mechanism in steep,
well-drained urban terrain (e.g. Singapore) that the fill-spill
depression-storage model structurally cannot represent.

Why a separate model
--------------------
``model.pluvial_model`` (fill-spill) routes runoff to *closed* topographic
depressions and lets the rest drain freely to the sea.  That is correct for
flat delta/alluvial cities (Bangkok, Jakarta, HCMC) whose terrain is full of
real closed basins.  But on a hilly, radially-drained island most excess rain
flows down open gradients to the coast and never enters a closed depression,
so fill-spill reports almost no ponding — even though the real city floods.
Those floods are a *transient* phenomenon: for ~1 h the drains are saturated
and rain accumulates on flat open ground.  Capturing that requires solving the
shallow-water equations with rainfall as a source, which is what this module
does.

Physical model
--------------
* Net excess rainfall = (design rainfall − drain capacity) × per-cell runoff
  coefficient.  This total depth is applied as a uniform-rate source over a
  fixed storm duration (default 1 h, matching the 1-hour IDF parameterisation).
* Water routes downhill under the same local-inertial discretisation as
  ``model.inertial_wave_model`` (Bates, Horritt & Fewtrell 2010), here with a
  spatially variable Manning's n (derived from land cover).
* Cells flagged as outlets (sea + the open river/canal network) are held at
  zero depth and act as free-drainage sinks — this is what prevents the whole
  domain filling like a bathtub.
* The peak depth reached at each cell over the storm-plus-settling window is
  returned as the flood map (the peak occurs at ≈ end of storm).

The drain capacity is *already* removed when computing the excess depth, so no
additional drainage sink is applied during the storm — doing so would
double-count the drainage network.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from model.inertial_wave_model import (
    CFL_ALPHA,
    G,
    MIN_DEPTH,
    _adaptive_dt,
    _continuity,
    _HAS_NUMBA,
)

if _HAS_NUMBA:
    import numba

    @numba.njit(parallel=True, fastmath=True, cache=True)
    def _rain_flux_x_jit(z, d, qx, n, dx, dt):
        """x-face unit discharges with a per-cell (face-averaged) Manning's n."""
        rows, cols = z.shape
        out = np.zeros_like(qx)
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
                nf = 0.5 * (n[i, j] + n[i, j + 1])
                deta_dx = (eta_R - eta_L) / dx
                q = qx[i, j]
                aq = q if q >= 0.0 else -q
                h73 = h_flow ** (7.0 / 3.0)
                denom = 1.0 + G * nf * nf * aq * dt / h73
                out[i, j] = (q - G * h_flow * deta_dx * dt) / denom
        return out

    @numba.njit(parallel=True, fastmath=True, cache=True)
    def _rain_flux_y_jit(z, d, qy, n, dy, dt):
        """y-face unit discharges with a per-cell (face-averaged) Manning's n."""
        rows, cols = z.shape
        out = np.zeros_like(qy)
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
                nf = 0.5 * (n[i, j] + n[i + 1, j])
                deta_dy = (eta_B - eta_T) / dy
                q = qy[i, j]
                aq = q if q >= 0.0 else -q
                h73 = h_flow ** (7.0 / 3.0)
                denom = 1.0 + G * nf * nf * aq * dt / h73
                out[i, j] = (q - G * h_flow * deta_dy * dt) / denom
        return out

    _rain_flux_x = _rain_flux_x_jit
    _rain_flux_y = _rain_flux_y_jit
else:                                                  # pragma: no cover
    def _rain_flux_x(z, d, qx, n, dx, dt):
        """numpy fallback — n is face-averaged in x (shape rows, cols-1)."""
        eta = z + d
        h_flow = np.maximum(
            0.0,
            np.maximum(eta[:, :-1], eta[:, 1:]) - np.maximum(z[:, :-1], z[:, 1:]),
        )
        wet = h_flow > MIN_DEPTH
        nf = 0.5 * (n[:, :-1] + n[:, 1:])
        deta_dx = (eta[:, 1:] - eta[:, :-1]) / dx
        h73 = np.where(wet, h_flow ** (7.0 / 3.0), 1.0)
        denom = 1.0 + G * nf**2 * np.abs(qx) * dt / h73
        qx_new = np.where(wet, (qx - G * h_flow * deta_dx * dt) / denom, 0.0)
        wall = ~np.isfinite(z[:, :-1]) | ~np.isfinite(z[:, 1:])
        return np.where(wall, 0.0, qx_new)

    def _rain_flux_y(z, d, qy, n, dy, dt):
        """numpy fallback — n is face-averaged in y (shape rows-1, cols)."""
        eta = z + d
        h_flow = np.maximum(
            0.0,
            np.maximum(eta[:-1, :], eta[1:, :]) - np.maximum(z[:-1, :], z[1:, :]),
        )
        wet = h_flow > MIN_DEPTH
        nf = 0.5 * (n[:-1, :] + n[1:, :])
        deta_dy = (eta[1:, :] - eta[:-1, :]) / dy
        h73 = np.where(wet, h_flow ** (7.0 / 3.0), 1.0)
        denom = 1.0 + G * nf**2 * np.abs(qy) * dt / h73
        qy_new = np.where(wet, (qy - G * h_flow * deta_dy * dt) / denom, 0.0)
        wall = ~np.isfinite(z[:-1, :]) | ~np.isfinite(z[1:, :])
        return np.where(wall, 0.0, qy_new)


def denoise_min_cluster(
    depth: np.ndarray,
    wet_threshold_m: float = 0.05,
    min_cluster_cells: int = 6,
) -> np.ndarray:
    """Drop wet clusters smaller than ``min_cluster_cells`` as sub-resolution
    noise, preserving the depth field of retained clusters.

    Connected wet regions (8-connectivity, depth > ``wet_threshold_m``) below
    the size cut are zeroed.  This removes the residual single/few-cell ponding
    speckle that a 30 m global DEM produces, while keeping coherent pools.
    NaN (nodata) cells are preserved.

    ``min_cluster_cells=6`` at 30 m corresponds to ~0.5 ha — roughly the
    smallest pluvial ponding feature meaningfully resolvable at this pixel size.
    """
    out = depth.copy()
    finite = np.isfinite(out)
    wet = finite & (out > wet_threshold_m)
    if not wet.any():
        return out
    lbl, nc = ndimage.label(wet, structure=np.ones((3, 3), dtype=int))
    if nc:
        sizes = ndimage.sum(np.ones(out.shape), lbl, index=range(1, nc + 1))
        keep = np.zeros(nc + 1, dtype=bool)
        keep[1:] = sizes >= min_cluster_cells
        drop = ~keep[lbl] & wet
        out[drop] = 0.0
    return out


def apply_depth_floor(depth: np.ndarray, floor_m: float = 0.05) -> np.ndarray:
    """Zero cells whose depth is below ``floor_m``, preserving NaN (nodata).

    Companion to ``denoise_min_cluster``: that drops small *clusters*, this
    drops shallow *cells* regardless of cluster size.  A spatially continuous
    sub-threshold sheet on a flat delta forms one large connected cluster that
    survives the cluster denoise but is hydrologically meaningless; counting it
    as ``wet`` (summarize_depth uses depth > 0) inflates flooded-area summaries
    (limitations register #2, the Manila domain-wide sheet).  Applying this
    floor before the raster is written aligns the reported wet area with the
    same 0.05 m threshold the denoise uses.
    """
    out = depth.copy()
    mask = np.isfinite(out) & (out < floor_m)
    out[mask] = 0.0
    return out


def run_rain_on_grid(
    z: np.ndarray,
    outlet_mask: np.ndarray,
    net_rain_depth_m,
    n,
    *,
    storm_duration_s: float = 3600.0,
    total_duration_s: float = 5400.0,
    dx: float = 30.0,
    dy: float = 30.0,
    dt_max: float = 30.0,
    progress_interval: int = 500,
    verbose: bool = True,
    open_boundary: bool = True,
    peak_depth_cap_m: float | None = None,
    drain_conveyance_m_s: float | None = None,
    perfect_sink_mask: np.ndarray | None = None,
) -> dict:
    """Rain-on-grid pluvial simulation; returns peak ponding depth.

    Parameters
    ----------
    z : float64 (rows, cols)
        Bed elevation (m).  NaN = nodata / wall (zero-flux).
    outlet_mask : bool (rows, cols)
        Free-drainage sinks (sea + open river/canal cells).  Depth is forced
        to zero at these cells every step, so any water flowing in leaves the
        domain.
    net_rain_depth_m : float or float64 (rows, cols)
        Total net excess rainfall depth applied over the storm (m), i.e.
        ``excess_depth_m * runoff_coeff`` per cell.  Applied at a uniform rate
        over ``storm_duration_s`` to land (non-outlet) cells only.
    n : float or float64 (rows, cols)
        Manning's roughness coefficient, per cell.  Face-averaged internally.
    storm_duration_s : float
        Duration over which the net rain is applied (s).  Default 1 h.
    total_duration_s : float
        Total simulated time (s); the extra time beyond the storm lets water
        route into downslope lows so the true peak is captured.  Default 1.5 h.
    dx, dy : float
        Cell size (m).
    dt_max : float
        Maximum timestep (s); the CFL condition reduces it for fast/shallow flow.
    progress_interval : int
        Print a status line every this many steps when ``verbose``.
    verbose : bool
        Print solver progress.
    open_boundary : bool
        If True (default), the outermost ring of finite cells acts as a
        free-drainage outlet, representing flow leaving the clipped domain.
        Prevents runoff from piling against the array edge (a wall artefact of
        the finite domain). Set False for a deliberately closed domain.
    peak_depth_cap_m : float or None
        If set, clip returned peak and final depths to this maximum (m),
        preserving NaN. A physical life-safety bound on residual solver
        overshoot, applied after routing (cf. the coastal model's depth cap).
    drain_conveyance_m_s : float or None
        Maximum depth (m) conveyed away per second at each outlet cell.  None
        (default) = perfect sink (back-compat).  A finite value lets the drain
        be overwhelmed: the remainder ponds on the adjacent land — e.g. Old
        Klang Road by Sungai Klang (limitation #19).
    perfect_sink_mask : bool (rows, cols) or None
        Within the outlet cells, mark which are perfect sinks regardless of
        ``drain_conveyance_m_s`` (e.g. sea cells and major rivers that convey
        freely).  Only meaningful when ``drain_conveyance_m_s`` is set; ignored
        otherwise.  Cells that are True here are zeroed every step; the
        remaining outlet cells get the finite conveyance treatment (limitation #19).

    Returns
    -------
    dict with keys:
        ``peak_depth``   float32 (rows, cols) — max depth over the run (m); NaN at nodata
        ``final_depth``  float32 (rows, cols) — depth at end of run (m)
        ``elapsed_s``    float — simulated time reached (s)
        ``n_steps``      int   — number of timesteps taken
        ``mass_in_m3``   float — total net rain volume introduced (m³)
        ``mass_end_m3``  float — water remaining on land at end of run (m³)
    """
    rows, cols = z.shape
    finite = np.isfinite(z)
    outlet_mask = outlet_mask.astype(bool) & finite
    if open_boundary:
        # Clipped-domain edge is an open (transmissive) boundary: runoff routed
        # to the map edge exits the domain rather than piling against the
        # array's no-flux wall. The outermost ring of finite cells drains every
        # step via the existing outlet handling.
        border = np.zeros(z.shape, dtype=bool)
        border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
        outlet_mask = outlet_mask | (border & finite)
    land = finite & ~outlet_mask
    cell_area = dx * dy

    # Per-cell net rain rate (m/s); zero on outlets / nodata.
    if np.ndim(net_rain_depth_m):
        net_depth = np.where(land, np.asarray(net_rain_depth_m, dtype=np.float64), 0.0)
    else:
        net_depth = np.where(land, float(net_rain_depth_m), 0.0)
    rain_rate = net_depth / storm_duration_s
    mass_in = float(net_depth.sum()) * cell_area

    # Per-cell Manning's n; safe (finite, positive) everywhere for the kernel.
    if np.ndim(n):
        n_arr = np.asarray(n, dtype=np.float64).copy()
    else:
        n_arr = np.full((rows, cols), float(n), dtype=np.float64)
    n_arr[~np.isfinite(n_arr) | (n_arr <= 0.0)] = 0.05

    z_work = z.astype(np.float64)
    d = np.zeros((rows, cols), dtype=np.float64)
    qx = np.zeros((rows, cols - 1), dtype=np.float64)
    qy = np.zeros((rows - 1, cols), dtype=np.float64)
    peak = np.zeros((rows, cols), dtype=np.float64)

    if verbose:
        print(
            f"  Rain-on-grid: {rows}×{cols} cells  dx={dx:.0f}m  "
            f"storm={storm_duration_s/3600:.2f}h  total={total_duration_s/3600:.2f}h  "
            f"net_rain_max={float(net_depth.max())*1000:.1f}mm  "
            f"outlets={int(outlet_mask.sum()):,}",
            flush=True,
        )

    t = 0.0
    step = 0
    while t < total_duration_s and step < 200_000:
        dt = _adaptive_dt(d, qx, qy, dx, dy, dt_max, sea_mask=outlet_mask)
        dt = min(dt, total_duration_s - t)
        if dt < 1e-6:
            break

        qx = _rain_flux_x(z_work, d, qx, n_arr, dx, dt)
        qy = _rain_flux_y(z_work, d, qy, n_arr, dy, dt)
        d_new = _continuity(d, qx, qy, dx, dy, dt)

        # Rainfall source (uniform rate while the storm is on).
        if t < storm_duration_s:
            d_new = d_new + rain_rate * dt

        # Outlets convey water away. Default: perfect sink. If a finite drain
        # conveyance is set, remove only up to drain_conveyance_m_s*dt of depth
        # per step; the remainder ponds (the drain is overwhelmed and backs up,
        # flooding adjacent ground — e.g. Old Klang Road by Sungai Klang). #19
        if drain_conveyance_m_s is None:
            d_new[outlet_mask] = 0.0
        else:
            # Per-channel-type drains (limitation #19): perfect-sink cells (sea +
            # major rivers) fully drain; finite drains (minor channels) shed only
            # drain_conveyance_m_s*dt per step and pond the rest when overwhelmed.
            if perfect_sink_mask is not None:
                d_new[perfect_sink_mask] = 0.0
                fin = outlet_mask & ~perfect_sink_mask
            else:
                fin = outlet_mask
            d_new[fin] = np.maximum(0.0, d_new[fin] - drain_conveyance_m_s * dt)
        d_new[~finite] = 0.0

        peak = np.maximum(peak, d_new)

        if verbose and step % progress_interval == 0:
            wet = int(np.sum(d_new[land] > MIN_DEPTH))
            print(
                f"    step={step:6d}  t={t/3600:.3f}h  dt={dt:.1f}s  "
                f"wet={wet:,}  max_d={float(d_new.max()):.3f}m",
                flush=True,
            )

        d = d_new
        t += dt
        step += 1

    mass_end = float(d[land].sum()) * cell_area
    peak[~finite] = np.nan

    if peak_depth_cap_m is not None:
        peak = np.where(np.isfinite(peak), np.minimum(peak, peak_depth_cap_m), peak)
        d = np.where(np.isfinite(d), np.minimum(d, peak_depth_cap_m), d)

    return {
        "peak_depth": peak.astype(np.float32),
        "final_depth": d.astype(np.float32),
        "elapsed_s": t,
        "n_steps": step,
        "mass_in_m3": mass_in,
        "mass_end_m3": mass_end,
    }
