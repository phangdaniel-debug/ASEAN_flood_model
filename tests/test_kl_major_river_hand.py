import math
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.warp import transform as rio_transform

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Main-stem-referenced HAND: drainage = flow-accumulation channels with upstream
# catchment >= 180 km² (thr=200000 px), the trunk Klang network the ~500 km²
# GLoFAS discharge represents. See 2026-06-06-major-river-hand-anchor.md.
HAND = Path("data/kuala_lumpur/hand_mainstem_utm47n.tif")
OVERBANK_RP100 = 6.06  # corrected factor-2.06 RP100 overbank stage (m)

# (label, lon, lat, expect_floods_at_overbank)
SPOTS = [
    ("Federal Hill (dry control)", 101.67906, 3.13859, False),  # hill — must NOT flood
    ("Old Klang Road (+)",         101.65920, 3.08261, True),   # documented target — must flood
    ("Masjid Jamek (+)",           101.69518, 3.14894, True),
    ("Kampung Baru (+)",           101.70300, 3.16300, True),
]


def _hand_min(ds, hand, lon, lat, radius_m=50.0):
    xs, ys = rio_transform("EPSG:4326", ds.crs, [lon], [lat])
    col_f, row_f = ~ds.transform * (xs[0], ys[0])
    row, col = int(math.floor(row_f)), int(math.floor(col_f))
    rr = int(math.ceil(radius_m / abs(ds.transform.e)))
    rc = int(math.ceil(radius_m / abs(ds.transform.a)))
    r0, r1 = max(0, row - rr), min(ds.height, row + rr + 1)
    c0, c1 = max(0, col - rc), min(ds.width, col + rc + 1)
    block = hand[r0:r1, c0:c1]
    finite = np.isfinite(block)
    return float(np.nanmin(block)) if finite.any() else float("nan")


@pytest.mark.skipif(not HAND.exists(), reason="main-stem HAND not built yet")
@pytest.mark.parametrize("label,lon,lat,floods", SPOTS)
def test_mainstem_hand_floodplain_separation(label, lon, lat, floods):
    with rasterio.open(HAND) as ds:
        hand = ds.read(1).astype("float64")
        nod = ds.nodata
        if nod is not None:
            hand = np.where(hand == nod, np.nan, hand)
        hmin = _hand_min(ds, hand, lon, lat)
    assert np.isfinite(hmin), f"{label}: no finite HAND in window"
    if floods:
        assert hmin < OVERBANK_RP100, f"{label}: HAND_min {hmin:.2f} should flood at {OVERBANK_RP100} m"
    else:
        # Federal Hill must be well clear of the overbank stage (real separation, not borderline).
        assert hmin > OVERBANK_RP100 + 5.0, f"{label}: HAND_min {hmin:.2f} too low — hill still floods"
