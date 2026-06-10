"""Invariant guard for the Plan-9 systematic model-blind hard-negative controls.

Locks the four selection criteria (terrain + flood-record, model-blind) so the
committed register cannot silently drift: each systematic dry control must be
ABOVE the RP100 fluvial stage (main-stem HAND > 6.06 m, our band floor 6.0 m),
below the hilltop band, NOT on a channel, and > ~1 km from every documented flood
location. This is the regression analogue of the build_systematic_dry_controls
sampler — it never reads the model's flood rasters.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.warp import transform as rio_transform

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REG = Path("data/kuala_lumpur/manifest/hotspots.csv")
HAND = Path("data/kuala_lumpur/hand_mainstem_utm47n.tif")
DRN = Path("data/kuala_lumpur/drainage_waterways_utm47n.tif")
EXCL = Path("data/kuala_lumpur/_flood_exclusions.json")

RP100_FLUVIAL_STAGE_M = 6.06
HAND_BAND = (6.0, 20.5)   # band the sampler used (small tolerance)
MIN_KM_TO_FLOOD = 0.9     # sampler used 1.0 km; allow rounding slack


def _systematic_rows():
    reg = pd.read_csv(REG)
    return reg[reg["kind"] == "dry_diagnostic"]


@pytest.mark.skipif(not (REG.exists() and HAND.exists()), reason="register / HAND not present")
def test_diagnostic_controls_excluded_from_scored_gate():
    # The 12 systematic hard negatives are a DIAGNOSTIC (kind=dry_diagnostic),
    # not the scored gate. The scored loader must include only positive + dry.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.city_manifest import load_hotspots_from_manifest
    scored = load_hotspots_from_manifest("kuala_lumpur")
    n_dry_scored = sum(1 for h in scored if h.cls == "dry")
    reg = pd.read_csv(REG)
    assert n_dry_scored == int((reg["kind"] == "dry").sum())  # only kind==dry scored
    assert int((reg["kind"] == "dry_diagnostic").sum()) >= 10  # diagnostics retained, unscored


@pytest.mark.skipif(not (REG.exists() and HAND.exists() and EXCL.exists()), reason="inputs absent")
def test_systematic_controls_satisfy_model_blind_invariants():
    rows = _systematic_rows()
    assert len(rows) >= 10, "expected >=10 systematic hard negatives"

    hand_ds = rasterio.open(HAND)
    hand = hand_ds.read(1).astype(float)
    if hand_ds.nodata is not None:
        hand = np.where(hand == hand_ds.nodata, np.nan, hand)
    drn_ds = rasterio.open(DRN)
    drn = drn_ds.read(1)

    reg = pd.read_csv(REG)
    pos = reg[reg["kind"] == "positive"][["lon", "lat"]].dropna().values.tolist()
    extra = [(d["lon"], d["lat"]) for d in json.loads(EXCL.read_text())]
    excl = pos + extra
    ex_x, ex_y = rio_transform("EPSG:4326", hand_ds.crs, [c[0] for c in excl], [c[1] for c in excl])
    excl_xy = np.column_stack([ex_x, ex_y])

    for _, r in rows.iterrows():
        xs, ys = rio_transform("EPSG:4326", hand_ds.crs, [r.lon], [r.lat])
        col, row = ~hand_ds.transform * (xs[0], ys[0])
        ci, ri = int(col), int(row)
        h = float(hand[ri, ci])
        # (1) above the RP100 fluvial stage (not trivially-flooded floodplain)
        assert h > RP100_FLUVIAL_STAGE_M, f"{r['name']}: HAND {h:.1f} <= fluvial stage {RP100_FLUVIAL_STAGE_M}"
        # (1b) within the hard-negative band (lower than hilltop controls)
        assert HAND_BAND[0] <= h <= HAND_BAND[1], f"{r['name']}: HAND {h:.1f} outside band {HAND_BAND}"
        # (2) not on a channel cell
        assert drn[ri, ci] == 0, f"{r['name']}: sits on a drainage channel cell"
        # (3) > ~1 km from every documented flood location
        d_km = float(np.hypot(excl_xy[:, 0] - xs[0], excl_xy[:, 1] - ys[0]).min()) / 1000.0
        assert d_km >= MIN_KM_TO_FLOOD, f"{r['name']}: only {d_km:.2f} km from a documented flood"
