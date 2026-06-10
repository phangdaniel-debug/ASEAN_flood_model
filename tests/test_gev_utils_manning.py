"""Test mannings_stage in gev_utils (moved from fit_fluvial_baseline_era5)."""
import pytest
from scripts.gev_utils import mannings_stage


def test_mannings_stage_unit_inputs():
    # Q=1, w=1, n=1, S=1 -> d = (1*1/(1*1))^0.6 = 1.0^0.6 = 1.0
    assert mannings_stage(1.0, 1.0, 1.0, 1.0) == pytest.approx(1.0, rel=1e-6)


def test_mannings_stage_zero_discharge():
    assert mannings_stage(0.0, 10.0, 0.035, 0.00005) == 0.0


def test_mannings_stage_invalid_params():
    with pytest.raises(ValueError):
        mannings_stage(100.0, 0.0, 0.035, 0.001)   # width=0


def test_mannings_stage_era5_still_works():
    # Confirm mannings_stage is re-exported from the ERA5 script after the move.
    import importlib
    mod = importlib.import_module("scripts.fit_fluvial_baseline_era5")
    assert hasattr(mod, "mannings_stage"), "mannings_stage not re-exported from ERA5 script"
    assert mod.mannings_stage is mannings_stage  # same object, not a copy
