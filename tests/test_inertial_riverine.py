"""Riverine boundary mode for the inertial solver (Bangkok B2).

The core property that motivates the hydrodynamic approach over single-stage HAND:
water released from the river channel propagates onto the CONNECTED floodplain but does
NOT flood a low pit DISCONNECTED behind a ridge — whereas HAND (depth = stage - HAND)
would wrongly flood that low pit because its height-above-drainage is below the stage.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.inertial_wave_model import run_inertial


def _channel_floodplain_pit(rows=12, cols=40):
    """River at j=0 (bed 0); connected floodplain j=1..18 (bed rises 0.1->1.0);
    a 5 m ridge wall at j=19..21; a low pit (bed 0.5) j=22..39 disconnected behind it."""
    z = np.zeros((rows, cols), dtype=np.float64)
    for j in range(1, 19):
        z[:, j] = 0.1 + (j - 1) * (0.9 / 17.0)   # 0.1 .. 1.0, below the 2 m overbank
    z[:, 19:22] = 5.0                            # ridge wall (above overbank)
    z[:, 22:] = 0.5                              # low plain behind ridge (below overbank)
    river = np.zeros((rows, cols), dtype=bool)
    river[:, 0] = True
    return z, river


def test_riverine_array_bc_floods_connected_not_disconnected():
    z, river = _channel_floodplain_pit()
    # Per-cell WSE: river cells held at bed + 2 m overbank (depth 2 m along the channel).
    OVERBANK = 2.0
    wse = z + OVERBANK
    res = run_inertial(
        z, river, wl_boundary=wse,
        n=0.05, dx=30.0, dy=30.0, t_end=7200.0, dt_max=10.0,
        convergence_tol=1e-4, crop_bbox=False,
    )
    pk = res["peak_depth"]
    # Connected floodplain just off the river floods (water routed in).
    assert float(np.nanmax(pk[:, 3])) > 0.3, f"connected floodplain stayed dry: {np.nanmax(pk[:, 3])}"
    assert float(np.nanmax(pk[:, 10])) > 0.05, "mid floodplain should get some water"
    # Disconnected low pit BEHIND the 5 m ridge stays dry — the hydrodynamic property.
    assert float(np.nanmax(pk[:, 30])) < 0.02, \
        f"disconnected pit wrongly flooded ({np.nanmax(pk[:, 30])} m) — HAND-like leak"
    # Sanity: a static HAND would flood that pit (HAND there ~0.5 m < 2 m stage). The point
    # of the hydrodynamic BC is that it does NOT.


def test_coastal_scalar_bc_still_works():
    """Regression: the existing scalar-WSE coastal BC is unchanged by the array extension."""
    z, sea = _channel_floodplain_pit()
    res = run_inertial(
        z, sea, wl_boundary=2.0,          # uniform WSE at the boundary column
        n=0.05, dx=30.0, dy=30.0, t_end=7200.0, dt_max=10.0,
        convergence_tol=1e-4, crop_bbox=False,
    )
    pk = res["peak_depth"]
    # Boundary column held at WSE 2.0 over bed 0 -> depth ~2 m.
    assert abs(float(np.nanmax(pk[:, 0])) - 2.0) < 0.2
    # Connected floodplain floods; disconnected pit stays dry (same connectivity physics).
    assert float(np.nanmax(pk[:, 3])) > 0.3
    assert float(np.nanmax(pk[:, 30])) < 0.02
