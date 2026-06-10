"""Physics tests for the rain-on-grid pluvial model.

Each test builds a synthetic terrain and checks a property the shallow-water
rain-on-grid solver must satisfy:

  1. Flat closed impervious box -> uniform ponding equal to the net rain depth
     (water has nowhere to go: pure mass storage).
  2. Mass conservation: water introduced = water ponded + water drained out.
  3. Tilted plane draining to an outlet -> thin sheet, no deep ponding.
  4. Single central bowl -> ponding in the bowl deeper than the rain depth
     (catchment concentration), shallow elsewhere.
"""
import numpy as np
import pytest

from model.pluvial_rain_model import run_rain_on_grid, denoise_min_cluster


def test_denoise_drops_small_clusters_keeps_large():
    """Sub-threshold clusters are zeroed; large coherent pools are preserved."""
    d = np.zeros((30, 30), dtype=np.float64)
    # A large coherent pool (5x5 = 25 cells) and an isolated 1-cell speckle.
    d[5:10, 5:10] = 0.4
    d[20, 20] = 0.4
    out = denoise_min_cluster(d, wet_threshold_m=0.05, min_cluster_cells=6)
    assert (out[5:10, 5:10] == 0.4).all()      # big pool kept
    assert out[20, 20] == 0.0                   # speckle dropped


def test_denoise_preserves_nan():
    d = np.full((10, 10), np.nan)
    d[2:6, 2:6] = 0.3                            # 16-cell pool
    out = denoise_min_cluster(d, min_cluster_cells=6)
    assert np.isnan(out[0, 0])
    assert (out[2:6, 2:6] == 0.3).all()


def test_flat_closed_box_stores_all_rain():
    """Flat, closed, impervious domain: every cell retains exactly the net rain."""
    z = np.zeros((20, 20), dtype=np.float64)
    outlet = np.zeros((20, 20), dtype=bool)        # no outlets
    net_rain = 0.05                                # 50 mm net excess

    res = run_rain_on_grid(
        z, outlet, net_rain, n=0.05,
        storm_duration_s=600.0, total_duration_s=900.0,
        dx=30.0, dy=30.0, dt_max=30.0, verbose=False,
        open_boundary=False,  # deliberately closed domain: edge must not drain
    )
    peak = res["peak_depth"]
    # With no slope and no outlet, water stays put: depth == net rain everywhere.
    assert np.allclose(peak, net_rain, atol=1e-4), \
        f"expected uniform {net_rain} m, got [{peak.min():.4f}, {peak.max():.4f}]"


def test_mass_conserved_closed_box():
    """Closed box: total ponded volume equals total rain volume introduced."""
    z = np.zeros((30, 30), dtype=np.float64)
    outlet = np.zeros((30, 30), dtype=bool)
    net_rain = 0.04

    res = run_rain_on_grid(
        z, outlet, net_rain, n=0.06,
        storm_duration_s=600.0, total_duration_s=900.0,
        dx=30.0, dy=30.0, verbose=False,
        open_boundary=False,  # deliberately closed domain: nothing should drain
    )
    # Closed domain -> nothing drains out -> end mass == introduced mass.
    assert res["mass_end_m3"] == pytest.approx(res["mass_in_m3"], rel=1e-3)


def test_tilted_plane_drains_to_outlet_no_deep_ponding():
    """Uniform slope to an outlet edge: thin sheet flow, no deep ponding,
    and most water drains out by the end of the run."""
    rows, cols = 40, 40
    # Bed falls from north (high) to south (low); south edge is the outlet.
    z = np.tile(np.linspace(4.0, 0.0, rows)[:, None], (1, cols)).astype(np.float64)
    outlet = np.zeros((rows, cols), dtype=bool)
    outlet[-1, :] = True                            # south edge drains freely
    net_rain = 0.05

    res = run_rain_on_grid(
        z, outlet, net_rain, n=0.05,
        storm_duration_s=900.0, total_duration_s=5400.0,
        dx=30.0, dy=30.0, verbose=False,
    )
    peak = res["peak_depth"]
    land_peak = peak[:-1, :]                         # exclude the forced-dry outlet row
    # Sheet flow on a slope stays shallow — nowhere should pond near the full
    # rain depth times a large factor.
    assert np.nanmax(land_peak) < 0.15, \
        f"unexpected deep ponding on a slope: max={np.nanmax(land_peak):.3f} m"
    # Most of the introduced water should have drained out the outlet.
    assert res["mass_end_m3"] < 0.5 * res["mass_in_m3"], \
        f"slope failed to drain: end={res['mass_end_m3']:.0f} in={res['mass_in_m3']:.0f}"


def test_central_bowl_concentrates_ponding():
    """A bowl in the middle of a draining plane ponds deeper than the rain
    depth, because it collects runoff from its catchment."""
    rows, cols = 41, 41
    # Gentle bowl: elevation rises with distance from centre.
    yy, xx = np.mgrid[0:rows, 0:cols]
    r = np.sqrt((yy - rows // 2) ** 2 + (xx - cols // 2) ** 2)
    z = (r * 0.05).astype(np.float64)               # ~0 at centre, rises outward
    # Outlets around the border so water can leave the domain.
    outlet = np.zeros((rows, cols), dtype=bool)
    outlet[0, :] = outlet[-1, :] = outlet[:, 0] = outlet[:, -1] = True
    net_rain = 0.03

    res = run_rain_on_grid(
        z, outlet, net_rain, n=0.06,
        storm_duration_s=1800.0, total_duration_s=7200.0,
        dx=30.0, dy=30.0, verbose=False,
    )
    peak = res["peak_depth"]
    centre = peak[rows // 2, cols // 2]
    # The bowl centre must collect more than a single cell's rain depth.
    assert centre > net_rain, \
        f"bowl centre {centre:.3f} m did not exceed rain depth {net_rain} m"
    # And it should be the deepest point in the domain.
    assert centre >= np.nanmax(peak) - 1e-6


def test_outlets_stay_dry():
    """Outlet cells are perfect sinks and must report zero depth."""
    z = np.zeros((15, 15), dtype=np.float64)
    outlet = np.zeros((15, 15), dtype=bool)
    outlet[0, 0] = True
    res = run_rain_on_grid(
        z, outlet, 0.05, n=0.05,
        storm_duration_s=600.0, total_duration_s=600.0, verbose=False,
    )
    assert res["peak_depth"][0, 0] == 0.0


def test_spatial_manning_n_accepted():
    """A per-cell Manning's n array runs without error and conserves mass."""
    z = np.zeros((20, 20), dtype=np.float64)
    outlet = np.zeros((20, 20), dtype=bool)
    n = np.full((20, 20), 0.05)
    n[:, :10] = 0.08                                  # rougher half
    res = run_rain_on_grid(
        z, outlet, 0.04, n=n,
        storm_duration_s=600.0, total_duration_s=900.0, verbose=False,
        open_boundary=False,  # closed domain: tests mass conservation without edge drainage
    )
    assert res["mass_end_m3"] == pytest.approx(res["mass_in_m3"], rel=1e-3)


def _ramp_plane(rows=30, cols=30, slope=0.5):
    """Plane sloping down toward the bottom edge (row -1); higher at top."""
    z = np.empty((rows, cols), dtype=np.float64)
    for i in range(rows):
        z[i, :] = (rows - 1 - i) * slope  # row 0 highest, last row = 0
    return z

def test_open_boundary_drains_edge():
    z = _ramp_plane()
    no_outlet = np.zeros(z.shape, dtype=bool)  # no sea/river outlets at all
    res_open = run_rain_on_grid(
        z, no_outlet, 0.2, 0.05,
        storm_duration_s=600.0, total_duration_s=900.0, dt_max=10.0,
        verbose=False, open_boundary=True,
    )
    res_closed = run_rain_on_grid(
        z, no_outlet, 0.2, 0.05,
        storm_duration_s=600.0, total_duration_s=900.0, dt_max=10.0,
        verbose=False, open_boundary=False,
    )
    peak_open = res_open["peak_depth"]
    assert np.nanmax(peak_open[-1, :]) < 0.05
    assert np.nanmax(peak_open) < np.nanmax(res_closed["peak_depth"])

def test_open_boundary_default_on():
    z = _ramp_plane()
    no_outlet = np.zeros(z.shape, dtype=bool)
    res_default = run_rain_on_grid(
        z, no_outlet, 0.2, 0.05,
        storm_duration_s=600.0, total_duration_s=900.0, dt_max=10.0,
        verbose=False,
    )
    assert np.nanmax(res_default["peak_depth"][-1, :]) < 0.05


def test_peak_depth_cap_clips_overshoot():
    # Closed single-cell pit fed by heavy rain -> deep ponding without a cap.
    z = np.full((15, 15), 10.0, dtype=np.float64)
    z[7, 7] = 6.0  # 4 m-deep pit
    no_outlet = np.zeros(z.shape, dtype=bool)
    common = dict(storm_duration_s=600.0, total_duration_s=1200.0, dt_max=10.0,
                  verbose=False, open_boundary=False)
    uncapped = run_rain_on_grid(z, no_outlet, 5.0, 0.05, **common)
    capped = run_rain_on_grid(z, no_outlet, 5.0, 0.05, peak_depth_cap_m=1.0, **common)
    assert np.nanmax(uncapped["peak_depth"]) > 1.0          # would exceed cap
    assert np.nanmax(capped["peak_depth"]) <= 1.0 + 1e-9    # clipped
    # NaN nodata preserved under capping
    z2 = z.copy(); z2[0, 0] = np.nan
    capped2 = run_rain_on_grid(z2, no_outlet, 5.0, 0.05, peak_depth_cap_m=1.0, **common)
    assert np.isnan(capped2["peak_depth"][0, 0])
