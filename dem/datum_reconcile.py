"""
Datum reconciliation (spec §1.5, the CRITICAL first step).

ICESat-2 ATL08 / GEDI L2A heights are **WGS84 ellipsoidal**.
GLO-30 / DeltaDTM are **EGM2008 orthometric (geoid)**.
A missed geoid correction is a multi-metre systematic error, so all differencing
(f-calibration, validation, DeltaDTM cross-check) MUST happen on a common datum.

This module converts between the two using the EGM2008 geoid model via PROJ
(grid `us_nga_egm08_25`, fetched through the PROJ network if not local).

    H_orthometric (EGM2008) = h_ellipsoidal (WGS84) - N(lon,lat)
    h_ellipsoidal (WGS84)   = H_orthometric (EGM2008) + N(lon,lat)

where N is the EGM2008 geoid undulation.

Convention used here: GLO-30 is the reference frame (EGM2008), so we bring the
lidar ground truth DOWN to EGM2008 via `ellipsoidal_to_egm2008`.
"""
from __future__ import annotations
import numpy as np
import pyproj
from pyproj import Transformer

# Allow PROJ to fetch the EGM2008 grid on demand if it is not bundled locally.
pyproj.network.set_network_enabled(True)

# WGS84 geographic 3D (ellipsoidal height) -> WGS84 horizontal + EGM2008 height.
_TF_ELL_TO_ORTHO = Transformer.from_crs(
    "EPSG:4979", "EPSG:4326+EPSG:3855", always_xy=True
)
_TF_ORTHO_TO_ELL = Transformer.from_crs(
    "EPSG:4326+EPSG:3855", "EPSG:4979", always_xy=True
)


def ellipsoidal_to_egm2008(lon, lat, h_ell):
    """WGS84 ellipsoidal height -> EGM2008 orthometric height."""
    lon = np.asarray(lon, dtype="float64")
    lat = np.asarray(lat, dtype="float64")
    h_ell = np.asarray(h_ell, dtype="float64")
    _, _, h_ortho = _TF_ELL_TO_ORTHO.transform(lon, lat, h_ell)
    return np.asarray(h_ortho)


def egm2008_to_ellipsoidal(lon, lat, h_ortho):
    """EGM2008 orthometric height -> WGS84 ellipsoidal height."""
    lon = np.asarray(lon, dtype="float64")
    lat = np.asarray(lat, dtype="float64")
    h_ortho = np.asarray(h_ortho, dtype="float64")
    _, _, h_ell = _TF_ORTHO_TO_ELL.transform(lon, lat, h_ortho)
    return np.asarray(h_ell)


def geoid_undulation(lon, lat):
    """EGM2008 geoid undulation N = h_ellipsoidal - H_orthometric (metres)."""
    lon = np.asarray(lon, dtype="float64")
    lat = np.asarray(lat, dtype="float64")
    zeros = np.zeros_like(lon, dtype="float64")
    # h_ortho for ellipsoidal height 0  => H = -N  => N = -H
    h_ortho = ellipsoidal_to_egm2008(lon, lat, zeros)
    return -np.asarray(h_ortho)


if __name__ == "__main__":
    # Self-test over Bangkok (UTM47N domain centre ~ 100.5E, 13.7N).
    lon = np.array([100.50, 100.60, 100.40])
    lat = np.array([13.70, 13.80, 13.60])
    N = geoid_undulation(lon, lat)
    print("EGM2008 geoid undulation N at Bangkok pts (m):", np.round(N, 3))
    # Round-trip check.
    h_ell = np.array([10.0, 20.0, 5.0])
    H = ellipsoidal_to_egm2008(lon, lat, h_ell)
    h_back = egm2008_to_ellipsoidal(lon, lat, H)
    print("h_ell:", h_ell)
    print("H_ortho (EGM2008):", np.round(H, 3))
    print("round-trip h_ell:", np.round(h_back, 6))
    print("max round-trip err (m):", float(np.max(np.abs(h_back - h_ell))))
    print("implied N = h_ell - H:", np.round(h_ell - H, 3))
