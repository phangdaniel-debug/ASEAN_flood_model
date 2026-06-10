import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.combine_hazard_depth import combine_depth_arrays


def test_elementwise_max_preserves_nan_where_both_nan():
    a = np.array([[0.0, 0.5, np.nan]], dtype=np.float32)
    b = np.array([[0.3, 0.2, np.nan]], dtype=np.float32)
    out = combine_depth_arrays([a, b])
    assert out[0, 0] == 0.3
    assert out[0, 1] == 0.5
    assert np.isnan(out[0, 2])


def test_nan_in_one_layer_takes_the_other():
    a = np.array([[np.nan, 0.4]], dtype=np.float32)
    b = np.array([[0.7, np.nan]], dtype=np.float32)
    out = combine_depth_arrays([a, b])
    assert out[0, 0] == 0.7
    assert out[0, 1] == 0.4
