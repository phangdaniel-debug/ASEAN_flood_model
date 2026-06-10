"""Tests for MSL-to-EGM2008 offset derivation and CSV/cities.py patching."""
from __future__ import annotations

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_baseline_df() -> pd.DataFrame:
    """Minimal baseline CSV with 2 coastal, 1 fluvial, 1 pluvial row."""
    return pd.DataFrame({
        "hazard_type": ["coastal", "coastal", "fluvial", "pluvial"],
        "return_period": [2, 100, 100, 100],
        "baseline_water_level_m": [1.60, 1.90, 1.50, 0.20],
        "source_note": ["gauge_fit", "gauge_fit", "era5_fit", "era5_fit"],
        "datum_note": [
            "source=UHSLC; msl_to_egm2008_offset=+0.0000m; target_datum=EGM2008",
            "source=UHSLC; msl_to_egm2008_offset=+0.0000m; target_datum=EGM2008",
            "",
            "",
        ],
    })


def _make_empty_note_df() -> pd.DataFrame:
    """Coastal rows with empty datum_note (Jakarta literature-value case)."""
    return pd.DataFrame({
        "hazard_type": ["coastal", "coastal"],
        "return_period": [2, 100],
        "baseline_water_level_m": [0.42, 0.63],
        "source_note": ["literature", "literature"],
        "datum_note": ["", ""],
    })


# ---------------------------------------------------------------------------
# patch_coastal_rows
# ---------------------------------------------------------------------------

def test_coastal_rows_get_offset():
    from scripts.derive_msl_egm2008_offsets import patch_coastal_rows
    df = _make_baseline_df()
    patched, n, prior = patch_coastal_rows(df, offset=0.1234, date_str="2026-04-27")
    assert prior == pytest.approx(0.0)
    assert patched.loc[0, "baseline_water_level_m"] == pytest.approx(1.60 + 0.1234)
    assert patched.loc[1, "baseline_water_level_m"] == pytest.approx(1.90 + 0.1234)
    assert n == 2


def test_non_coastal_rows_unchanged():
    from scripts.derive_msl_egm2008_offsets import patch_coastal_rows
    df = _make_baseline_df()
    patched, _, _ = patch_coastal_rows(df, offset=0.1234, date_str="2026-04-27")
    assert patched.loc[2, "baseline_water_level_m"] == pytest.approx(1.50)
    assert patched.loc[3, "baseline_water_level_m"] == pytest.approx(0.20)


def test_datum_note_appended():
    from scripts.derive_msl_egm2008_offsets import patch_coastal_rows
    df = _make_baseline_df()
    patched, _, _ = patch_coastal_rows(df, offset=0.1234, date_str="2026-04-27")
    note = patched.loc[0, "datum_note"]
    assert "mdt_cnes_cls22=+0.1234m applied 2026-04-27" in note
    # Original content preserved
    assert "msl_to_egm2008_offset=+0.0000m" in note
    # Check row 1 as well
    note1 = patched.loc[1, "datum_note"]
    assert "mdt_cnes_cls22=+0.1234m applied 2026-04-27" in note1


def test_patch_coastal_rows_idempotent():
    from scripts.derive_msl_egm2008_offsets import patch_coastal_rows
    df = _make_baseline_df()
    patched1, _, _ = patch_coastal_rows(df, offset=0.1234, date_str="2026-04-27")
    patched2, n2, _ = patch_coastal_rows(patched1, offset=0.1234, date_str="2026-04-27")
    assert n2 == 0
    # Value must not be double-added
    assert patched2.loc[0, "baseline_water_level_m"] == pytest.approx(1.60 + 0.1234)
    assert patched2.loc[1, "baseline_water_level_m"] == pytest.approx(1.90 + 0.1234)


def test_empty_datum_note_handled():
    """Jakarta literature rows have empty datum_note; patch must not crash."""
    from scripts.derive_msl_egm2008_offsets import patch_coastal_rows
    df = _make_empty_note_df()
    patched, n, _ = patch_coastal_rows(df, offset=0.30, date_str="2026-04-27")
    assert n == 2
    assert patched.loc[0, "baseline_water_level_m"] == pytest.approx(0.42 + 0.30)
    assert "mdt_cnes_cls22=+0.3000m applied 2026-04-27" in patched.loc[0, "datum_note"]
    # Must not start with " | "
    assert not patched.loc[0, "datum_note"].startswith(" |")


# ---------------------------------------------------------------------------
# patch_cities_file
# ---------------------------------------------------------------------------

_CITIES_SNIPPET = """\
_register(CityConfig(
    name="Singapore",
    slug="singapore",
    msl_to_egm2008_offset=0.0,
))
_register(CityConfig(
    name="Kuala Lumpur",
    slug="kuala_lumpur",
    msl_to_egm2008_offset=0.0,
))
"""


def test_patch_cities_file_updates_target_slug(tmp_path):
    from scripts.derive_msl_egm2008_offsets import patch_cities_file
    p = tmp_path / "cities.py"
    p.write_text(_CITIES_SNIPPET, encoding="utf-8")
    changed = patch_cities_file(p, slug="singapore", offset=0.0412)
    assert changed is True
    text = p.read_text(encoding="utf-8")
    assert "msl_to_egm2008_offset=0.0412" in text


def test_patch_cities_file_leaves_other_slugs_unchanged(tmp_path):
    from scripts.derive_msl_egm2008_offsets import patch_cities_file
    p = tmp_path / "cities.py"
    p.write_text(_CITIES_SNIPPET, encoding="utf-8")
    patch_cities_file(p, slug="singapore", offset=0.0412)
    text = p.read_text(encoding="utf-8")
    # Find KL block and check its offset is still 0.0
    kl_start = text.index('slug="kuala_lumpur"')
    kl_block = text[kl_start:]
    offset_line = next(
        line for line in kl_block.splitlines() if "msl_to_egm2008_offset" in line
    )
    assert "0.0" in offset_line
    assert "0.0412" not in offset_line


def test_patch_cities_file_idempotent(tmp_path):
    from scripts.derive_msl_egm2008_offsets import patch_cities_file
    p = tmp_path / "cities.py"
    p.write_text(_CITIES_SNIPPET, encoding="utf-8")
    patch_cities_file(p, slug="singapore", offset=0.0412)
    changed_second = patch_cities_file(p, slug="singapore", offset=0.0412)
    assert changed_second is False


def test_patch_cities_file_returns_false_when_value_unchanged(tmp_path):
    from scripts.derive_msl_egm2008_offsets import patch_cities_file
    p = tmp_path / "cities.py"
    # Already has the correct value
    content = _CITIES_SNIPPET.replace(
        'slug="singapore",\n    msl_to_egm2008_offset=0.0,',
        'slug="singapore",\n    msl_to_egm2008_offset=0.0412,',
    )
    p.write_text(content, encoding="utf-8")
    changed = patch_cities_file(p, slug="singapore", offset=0.0412)
    assert changed is False


# ---------------------------------------------------------------------------
# interpolate_mdt
# ---------------------------------------------------------------------------

def _make_mock_mdt_ds() -> "xr.Dataset":
    """4x3 synthetic MDT grid for testing interpolation (no CMEMS needed).

    Covers lat -10..20, lon 95..112 to include all active gauge coords,
    including Jakarta at lat≈-6.2.
    """
    import numpy as np
    import xarray as xr
    lats = np.array([-10.0, 0.0, 10.0, 20.0])
    lons = np.array([95.0, 100.0, 112.0])
    # Values increase with latitude; all in a realistic MDT range
    data = np.array([
        [0.04, 0.05, 0.06],
        [0.08, 0.10, 0.12],
        [0.20, 0.25, 0.27],
        [0.30, 0.33, 0.38],
    ])
    return xr.Dataset(
        {
            "mdt": xr.DataArray(
                data,
                dims=["latitude", "longitude"],
                coords={"latitude": lats, "longitude": lons},
            )
        }
    )


def test_interpolate_mdt_exact_node():
    from scripts.derive_msl_egm2008_offsets import interpolate_mdt
    ds = _make_mock_mdt_ds()
    result = interpolate_mdt(ds, lat=0.0, lon=95.0)
    assert result == pytest.approx(0.08, abs=1e-6)


def test_interpolate_mdt_bilinear_latitude():
    from scripts.derive_msl_egm2008_offsets import interpolate_mdt
    ds = _make_mock_mdt_ds()
    # Midpoint lat=5 between row 0 (0.08) and row 10 (0.20) at lon=95 -> 0.14
    result = interpolate_mdt(ds, lat=5.0, lon=95.0)
    assert result == pytest.approx(0.14, abs=1e-4)


def test_interpolate_mdt_returns_float():
    from scripts.derive_msl_egm2008_offsets import interpolate_mdt
    ds = _make_mock_mdt_ds()
    result = interpolate_mdt(ds, lat=1.29, lon=103.85)
    assert isinstance(result, float)


def test_interpolate_mdt_active_gauge_coords_in_range():
    """Each active gauge ERA5 coord should interpolate within the expected sub-range of the mock grid.

    Bounds are derived from the mock grid's per-latitude-band values, not real MDT.
    They are deliberately tighter than (0, 0.5) to catch interpolation errors:
      - Singapore  (1.29°N, 103.85°E): lat 0→10 band, expect ~0.10–0.15
      - KL         (3.14°N, 101.69°E): lat 0→10 band, expect ~0.10–0.20
      - Bangkok   (13.76°N, 100.50°E): lat 10→20 band, expect ~0.25–0.35
      - Jakarta    (-6.23°N, 106.63°E): lat -10→0 band, expect ~0.05–0.15
    """
    from scripts.derive_msl_egm2008_offsets import interpolate_mdt
    ds = _make_mock_mdt_ds()
    # (lat, lon, lo, hi) — bounds reflect which latitude band of the mock grid applies
    gauge_bounds = [
        (1.2903,  103.8519,  0.08, 0.20),   # Singapore — lat [0,10] band
        (3.1390,  101.6869,  0.08, 0.22),   # KL — lat [0,10] band
        (13.7563, 100.5018,  0.22, 0.35),   # Bangkok — lat [10,20] band
        (-6.225,  106.625,   0.04, 0.15),   # Jakarta — lat [-10,0] band
    ]
    for lat, lon, lo, hi in gauge_bounds:
        val = interpolate_mdt(ds, lat=lat, lon=lon)
        assert lo <= val <= hi, (
            f"MDT={val:.4f} outside [{lo}, {hi}] for gauge at ({lat}, {lon})"
        )


# ---------------------------------------------------------------------------
# Integration test (skipped unless CMEMS credentials present)
# ---------------------------------------------------------------------------

import os

@pytest.mark.skipif(
    not os.environ.get("CMEMS_USERNAME"),
    reason="CMEMS credentials not set (set CMEMS_USERNAME to enable)"
)
def test_live_cmems_offsets_within_literature_bounds():
    """
    Fetch real CNES-CLS18 MDT and verify each gauge's offset is within
    +-0.05 m of known literature MDT estimates for SE Asia.

    Literature bounds (CNES-CLS18 / DTU15 consensus):
      Singapore (Tanjong Pagar)  : 0.02 -- 0.08 m
      Port Klang                 : 0.08 -- 0.18 m
      Ko Lak / Bangkok           : 0.22 -- 0.35 m
      Tanjung Priok / Jakarta    : 0.25 -- 0.40 m
    """
    from scripts.derive_msl_egm2008_offsets import fetch_mdt_grid, interpolate_mdt

    ds = fetch_mdt_grid()

    bounds = {
        699: (1.2903,  103.8519, 0.02, 0.08),   # Singapore
        140: (3.1390,  101.6869, 0.08, 0.18),   # Port Klang
        328: (13.7563, 100.5018, 0.22, 0.35),   # Ko Lak / Bangkok
        161: (-6.225,  106.625,  0.25, 0.40),   # Tanjung Priok / Jakarta
    }

    for uhslc_id, (lat, lon, lo, hi) in bounds.items():
        offset = interpolate_mdt(ds, lat=lat, lon=lon)
        assert lo <= offset <= hi, (
            f"UHSLC {uhslc_id}: MDT={offset:.4f} m outside literature bounds "
            f"[{lo}, {hi}] m"
        )
