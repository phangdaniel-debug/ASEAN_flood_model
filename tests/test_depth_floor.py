import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.pluvial_rain_model import apply_depth_floor


def test_continuous_subthreshold_sheet_is_stripped():
    # A large CONNECTED sheet of 2 cm water (survives cluster denoise) must be
    # zeroed by the depth floor so it cannot inflate wet-area summaries.
    depth = np.full((50, 50), 0.02, dtype=np.float32)
    out = apply_depth_floor(depth, floor_m=0.05)
    assert np.count_nonzero(out > 0) == 0


def test_real_pool_survives():
    depth = np.zeros((50, 50), dtype=np.float32)
    depth[10:20, 10:20] = 0.30  # a 10x10 cell, 0.30 m pool
    out = apply_depth_floor(depth, floor_m=0.05)
    assert np.count_nonzero(out > 0) == 100
    assert float(out.max()) == pytest.approx(0.30, rel=1e-5)


def test_nan_preserved():
    depth = np.array([[np.nan, 0.02, 0.10]], dtype=np.float32)
    out = apply_depth_floor(depth, floor_m=0.05)
    assert np.isnan(out[0, 0])
    assert out[0, 1] == 0.0
    assert out[0, 2] == 0.10
