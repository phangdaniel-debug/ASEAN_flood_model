"""Unit tests for drainage density diagnostic (summarize_distance)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts._diagnose_drainage_density import summarize_distance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_grid(rows: int, cols: int):
    """Return (outlet_mask, land_mask) for an all-land grid with NO outlets."""
    land = np.ones((rows, cols), dtype=bool)
    outlet = np.zeros((rows, cols), dtype=bool)
    return outlet, land


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_single_outlet_column_median():
    """One outlet column on the left; land fills the rest.

    For a 5×10 grid with cell_size=1 m and outlets in column 0,
    the nearest-outlet distance for each cell (i,j) = j.
    Land excludes the outlet column (j>0 only since outlet cells may be sea),
    but here outlet_mask and land_mask are independent — land covers all cells.

    Column distances: col 0→0, col 1→1, ..., col 9→9.
    All 5 rows are symmetric.  Values in land: 0,1,2,3,4,5,6,7,8,9 (each×5).
    Median of [0]*5,[1]*5,...,[9]*5 = median of 0..9 = 4.5 m.
    """
    rows, cols = 5, 10
    outlet, land = _make_grid(rows, cols)
    outlet[:, 0] = True  # left column is outlet

    stats = summarize_distance(outlet, land, wet_mask=None, cell_size_m=1.0)

    assert stats["outlet_count"] == rows  # 5 outlet cells
    assert stats["land_count"] == rows * cols
    assert abs(stats["land_median_m"] - 4.5) < 0.6  # EDT rounds; allow small tolerance
    assert stats["land_max_m"] == pytest.approx(9.0, abs=0.1)


def test_no_wet_mask_omits_wet_keys():
    """When wet_mask is None, wet_* keys must be absent from result."""
    rows, cols = 3, 3
    outlet, land = _make_grid(rows, cols)
    outlet[1, 1] = True

    stats = summarize_distance(outlet, land, wet_mask=None, cell_size_m=30.0)

    assert "wet_count" not in stats
    assert "wet_median_m" not in stats


def test_wet_mask_subset_distance():
    """Wet cells that are all adjacent to the outlet have smaller median distance."""
    rows, cols = 10, 10
    outlet, land = _make_grid(rows, cols)
    outlet[0, :] = True  # top row is outlet

    # Wet = only the second row (distance = 1 cell = 30 m)
    wet = np.zeros((rows, cols), dtype=bool)
    wet[1, :] = True

    stats = summarize_distance(outlet, land, wet_mask=wet, cell_size_m=30.0)

    assert stats["wet_count"] == cols  # 10 cells
    assert stats["wet_median_m"] == pytest.approx(30.0, abs=0.1)


def test_pct_of_land():
    """Outlet percentage of land should be 100 * outlet_count / land_count."""
    rows, cols = 4, 4
    outlet, land = _make_grid(rows, cols)
    outlet[0, 0] = True  # 1 of 16 cells

    stats = summarize_distance(outlet, land, cell_size_m=30.0)

    expected_pct = 100.0 / 16.0
    assert abs(stats["pct_of_land"] - expected_pct) < 1e-6


def test_all_outlet_zero_distance():
    """When every cell is an outlet, all distances should be zero."""
    rows, cols = 3, 4
    outlet = np.ones((rows, cols), dtype=bool)
    land = np.ones((rows, cols), dtype=bool)

    stats = summarize_distance(outlet, land, cell_size_m=30.0)

    assert stats["land_median_m"] == pytest.approx(0.0)
    assert stats["land_max_m"] == pytest.approx(0.0)
