"""Unit tests for validate_historical_events.py"""
from __future__ import annotations

import numpy as np
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.validate_historical_events import compute_metrics


def test_compute_metrics_perfect():
    obs  = np.array([[True,  True,  False, False]])
    pred = np.array([[True,  True,  False, False]])
    m = compute_metrics(pred, obs)
    assert m["csi"]  == pytest.approx(1.0)
    assert m["h"]    == pytest.approx(1.0)
    assert m["far"]  == pytest.approx(0.0)
    assert m["bias"] == pytest.approx(1.0)
    assert m["tp"] == 2
    assert m["fp"] == 0
    assert m["fn"] == 0


def test_compute_metrics_no_overlap():
    obs  = np.array([[True,  True,  False, False]])
    pred = np.array([[False, False, True,  True]])
    m = compute_metrics(pred, obs)
    assert m["csi"] == pytest.approx(0.0)
    assert m["h"]   == pytest.approx(0.0)
    assert m["tp"]  == 0
    assert m["fp"]  == 2
    assert m["fn"]  == 2


def test_compute_metrics_partial_overlap():
    # obs flooded: cols 0-3; pred flooded: cols 0-1 only
    # TP=2, FP=0, FN=2
    obs  = np.array([[True, True, True, True]])
    pred = np.array([[True, True, False, False]])
    m = compute_metrics(pred, obs)
    assert m["tp"]   == 2
    assert m["fp"]   == 0
    assert m["fn"]   == 2
    assert m["csi"]  == pytest.approx(2 / 4)   # 0.50
    assert m["h"]    == pytest.approx(2 / 4)   # 0.50
    assert m["far"]  == pytest.approx(0.0)
    assert m["bias"] == pytest.approx(2 / 4)   # 0.50 (under-predict)


def test_compute_metrics_all_false_predicted():
    obs  = np.array([[True, True]])
    pred = np.array([[False, False]])
    m = compute_metrics(pred, obs)
    assert m["csi"] == pytest.approx(0.0)
    assert m["h"]   == pytest.approx(0.0)
    # FAR = FP/(TP+FP) = 0/0 → 0.0 by convention
    assert m["far"] == pytest.approx(0.0)


def test_compute_metrics_all_false_observed():
    obs  = np.array([[False, False]])
    pred = np.array([[True, True]])
    m = compute_metrics(pred, obs)
    # TP=0, FP=2, FN=0
    assert m["csi"]  == pytest.approx(0.0)
    assert m["far"]  == pytest.approx(1.0)   # FP/(TP+FP) = 2/2 = 1.0
    assert np.isnan(m["bias"])               # (TP+FP)/(TP+FN) = 2/0 → nan (undefined)


def test_compute_metrics_shape_mismatch_raises():
    obs  = np.array([[True, False, True]])
    pred = np.array([[True, False]])
    with pytest.raises(ValueError, match="same shape"):
        compute_metrics(pred, obs)


def test_compute_metrics_2d_array():
    obs  = np.array([[True, False], [False, True]])
    pred = np.array([[True, True],  [False, False]])
    # TP=1, FP=1, FN=1
    m = compute_metrics(pred, obs)
    assert m["tp"]  == 1
    assert m["fp"]  == 1
    assert m["fn"]  == 1
    assert m["csi"] == pytest.approx(1 / 3)


import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from scripts.validate_historical_events import (
    rasterize_footprint,
    load_depth_mask,
    find_depth_raster,
)


# ── rasterize_footprint ────────────────────────────────────────────────────

def test_rasterize_footprint_full_coverage():
    """A polygon covering the entire grid → all pixels True."""
    transform = from_origin(0, 300, 30, 30)   # 10×10 grid, 30 m pixels
    geom = box(0, 0, 300, 300)
    mask = rasterize_footprint([geom], height=10, width=10, transform=transform)
    assert mask.shape == (10, 10)
    assert mask.all()


def test_rasterize_footprint_half_coverage():
    """A polygon covering the bottom half → ~50 pixels True."""
    transform = from_origin(0, 300, 30, 30)
    geom = box(0, 0, 300, 150)   # y 0–150 = rows 5–9 (bottom half)
    mask = rasterize_footprint([geom], height=10, width=10, transform=transform)
    # rasterio burns centre-of-pixel; bottom 5 rows should be covered
    assert mask.sum() == 50


def test_rasterize_footprint_empty():
    """Empty geometry list → all False."""
    transform = from_origin(0, 300, 30, 30)
    mask = rasterize_footprint([], height=10, width=10, transform=transform)
    assert mask.shape == (10, 10)
    assert not mask.any()


# ── load_depth_mask ────────────────────────────────────────────────────────

def _write_depth_tif(path, data):
    h, w = data.shape
    with rasterio.open(
        str(path), "w", driver="GTiff",
        height=h, width=w, count=1, dtype="float32",
        transform=from_origin(0, h * 30, 30, 30), crs="EPSG:32748",
    ) as dst:
        dst.write(data.astype("float32"), 1)


def test_load_depth_mask_threshold(tmp_path):
    data = np.array([[0.05, 0.10, 0.15, 0.0]])
    path = tmp_path / "depth.tif"
    _write_depth_tif(path, data)
    mask = load_depth_mask(path, threshold=0.10)
    # 0.05 < 0.10 → False; 0.10 >= 0.10 → True; 0.15 → True; 0.0 → False
    expected = np.array([[False, True, True, False]])
    np.testing.assert_array_equal(mask, expected)


def test_load_depth_mask_nodata(tmp_path):
    """NoData pixels should be treated as dry (False)."""
    data = np.array([[0.5, -9999.0]])
    path = tmp_path / "depth_nd.tif"
    h, w = data.shape
    with rasterio.open(
        str(path), "w", driver="GTiff",
        height=h, width=w, count=1, dtype="float32",
        transform=from_origin(0, 30, 30, 30), crs="EPSG:32748",
        nodata=-9999.0,
    ) as dst:
        dst.write(data.astype("float32"), 1)
    mask = load_depth_mask(path, threshold=0.10)
    expected = np.array([[True, False]])
    np.testing.assert_array_equal(mask, expected)


# ── find_depth_raster ──────────────────────────────────────────────────────

def test_find_depth_raster_found(tmp_path):
    rp_dir = tmp_path / "pluvial" / "rp_50"
    rp_dir.mkdir(parents=True)
    tif = rp_dir / "pluvial_depth_SSP5-8.5_2100_rp50.tif"
    _write_depth_tif(tif, np.full((3, 3), 0.2))
    from scripts.validate_historical_events import find_depth_raster
    assert find_depth_raster(tmp_path, "pluvial", 50) == tif


def test_find_depth_raster_missing(tmp_path):
    from scripts.validate_historical_events import find_depth_raster
    assert find_depth_raster(tmp_path, "pluvial", 50) is None


import zipfile as _zipfile
from shapely import to_wkb as _to_wkb
from shapely.geometry import shape as _shape
from pyogrio.raw import write as _ogr_write

from scripts.validate_historical_events import (
    extract_zip,
    find_shapefile,
    load_flood_footprint,
)


def _make_shapefile(directory: Path, polygons: list[dict]) -> Path:
    """Write a minimal shapefile with 'class' attribute using pyogrio."""
    directory.mkdir(parents=True, exist_ok=True)
    shp_path = directory / "flood.shp"
    geom_wkbs = np.array([_to_wkb(_shape(p["geometry"])) for p in polygons], dtype=object)
    classes = np.array([p["properties"].get("class", "") for p in polygons])
    _ogr_write(
        str(shp_path),
        geom_wkbs,
        field_data=[classes],
        fields=["class"],
        geometry_type="Polygon",
        crs="EPSG:4326",
        driver="ESRI Shapefile",
    )
    return shp_path


def _make_zip(shp_path: Path, zip_path: Path) -> Path:
    """Zip the shapefile (and sidecar files) into zip_path."""
    with _zipfile.ZipFile(str(zip_path), "w") as zf:
        for f in shp_path.parent.glob(shp_path.stem + ".*"):
            zf.write(str(f), f.name)
    return zip_path


# ── extract_zip ─────────────────────────────────────────────────────────────

def test_extract_zip_creates_directory(tmp_path):
    shp_path = _make_shapefile(tmp_path / "src", [
        {"geometry": {"type": "Polygon", "coordinates": [[(0,0),(1,0),(1,1),(0,1),(0,0)]]},
         "properties": {"class": "Flooded"}}
    ])
    zip_path = tmp_path / "test.zip"
    _make_zip(shp_path, zip_path)

    extract_dir = extract_zip(zip_path)
    assert extract_dir.exists()
    assert extract_dir.is_dir()
    assert any(extract_dir.glob("*.shp"))


def test_extract_zip_idempotent(tmp_path):
    """Calling extract_zip twice does not raise."""
    shp_path = _make_shapefile(tmp_path / "src2", [
        {"geometry": {"type": "Polygon", "coordinates": [[(0,0),(1,0),(1,1),(0,1),(0,0)]]},
         "properties": {"class": "Flooded"}}
    ])
    zip_path = tmp_path / "test2.zip"
    _make_zip(shp_path, zip_path)
    extract_zip(zip_path)
    extract_zip(zip_path)  # second call — should not error


# ── find_shapefile ───────────────────────────────────────────────────────────

def test_find_shapefile_finds_shp(tmp_path):
    shp = tmp_path / "flood.shp"
    shp.touch()
    result = find_shapefile(tmp_path)
    assert result == shp


def test_find_shapefile_raises_if_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_shapefile(tmp_path)


# ── load_flood_footprint ─────────────────────────────────────────────────────

def test_load_flood_footprint_filters_by_class(tmp_path):
    from shapely.geometry import mapping, box
    shp_path = _make_shapefile(tmp_path / "filt", [
        {"geometry": mapping(box(0, 0, 1, 1)), "properties": {"class": "Flooded"}},
        {"geometry": mapping(box(1, 0, 2, 1)), "properties": {"class": "Possibly flooded"}},
    ])
    geoms = load_flood_footprint(shp_path, "EPSG:4326",
                                 flood_attr="class", flood_value="Flooded")
    assert len(geoms) == 1


def test_load_flood_footprint_no_filter(tmp_path):
    from shapely.geometry import box
    shp_path = tmp_path / "nofilt" / "water.shp"
    (tmp_path / "nofilt").mkdir()
    geom_wkbs = np.array([_to_wkb(box(i, 0, i+1, 1)) for i in range(3)], dtype=object)
    _ogr_write(str(shp_path), geom_wkbs,
               field_data=[np.array([0, 1, 2])],
               fields=["id"],
               geometry_type="Polygon",
               crs="EPSG:4326",
               driver="ESRI Shapefile")
    geoms = load_flood_footprint(shp_path, "EPSG:4326",
                                 flood_attr=None, flood_value=None)
    assert len(geoms) == 3


def test_load_flood_footprint_reprojects(tmp_path):
    """Verify reprojection: a box in WGS84 arrives in a metric CRS."""
    from shapely.geometry import mapping, box
    shp_path = _make_shapefile(tmp_path / "reproj", [
        {"geometry": mapping(box(100.0, 0.0, 100.01, 0.01)),
         "properties": {"class": "Flooded"}},
    ])
    geoms = load_flood_footprint(shp_path, "EPSG:32648",   # UTM 48N
                                 flood_attr="class", flood_value="Flooded")
    assert len(geoms) == 1
    # Reprojection check: northing y should be in metres (~554 m), not degree-scale (~0.005)
    # (UTM 48N easting for 100°E is negative — 100°E is west of the 105°E central meridian)
    assert geoms[0].centroid.y > 100  # metres, clearly not degrees


# ---------------------------------------------------------------------------
# Task 5: validate_event orchestration tests
# ---------------------------------------------------------------------------

from unittest.mock import patch, MagicMock

from scripts.validate_historical_events import (
    validate_event, EventConfig, CSI_PASS, CSI_WARN,
    HIT_PASS_LIMITED, HIT_WARN_LIMITED,
)


def _make_event_config(city_slug="jakarta", out_dir_str="outputs/jakarta_ssp585_2100"):
    return EventConfig(
        event_id="TEST",
        description="Test event",
        city_slug=city_slug,
        source_url="https://example.com/test.zip",
        raster_obs=None,
        flood_attr=None,
        flood_value=None,
        hazard_types=("pluvial",),
        rp_range=(50,),
        default_out_dir=out_dir_str,
    )


def test_validate_event_pass(tmp_path):
    """validate_event returns LIMITED-PASS when model perfectly matches observed.

    The test grid is 150 m × 150 m ≈ 0.0225 km², far below
    OBS_AREA_LIMITED_KM2 (5.0), so validation falls into the sparse-obs
    LIMITED tier and gates on hit-rate H. Perfect overlap → H=1.0 ≥
    HIT_PASS_LIMITED (0.30) → LIMITED-PASS.
    """
    # Create a depth raster: 5×5, all 0.5 m (flooded above 0.1 m threshold)
    rp_dir = tmp_path / "pluvial" / "rp_50"
    rp_dir.mkdir(parents=True)
    tif = rp_dir / "pluvial_depth_SSP5-8.5_2100_rp50.tif"
    depth_data = np.full((5, 5), 0.5, dtype=np.float32)
    _write_depth_tif(tif, depth_data)

    # Observed footprint: full 5×5 grid (150 m × 150 m in UTM)
    from shapely.geometry import box
    observed_geom = box(0, 0, 150, 150)

    event = _make_event_config(out_dir_str=str(tmp_path))

    with patch("scripts.validate_historical_events.download_zip") as mock_dl, \
         patch("scripts.validate_historical_events.extract_zip") as mock_ex, \
         patch("scripts.validate_historical_events.find_shapefile") as mock_fs, \
         patch("scripts.validate_historical_events.load_flood_footprint") as mock_lf:

        mock_dl.return_value = MagicMock()
        mock_ex.return_value = MagicMock()
        mock_fs.return_value = MagicMock()
        mock_lf.return_value = [observed_geom]   # 1 polygon = full grid

        result = validate_event(event, out_dir=tmp_path, depth_threshold=0.10, no_download=False)

    assert result["verdict"] == "LIMITED-PASS"
    assert result["best_hazard"] == "pluvial"
    assert result["best_rp"] == 50
    assert result["best_csi"] == pytest.approx(1.0)
    assert result["best_h"] == pytest.approx(1.0)


def test_validate_event_warn(tmp_path):
    """validate_event returns LIMITED-WARN when hit-rate is in [HIT_WARN_LIMITED, HIT_PASS_LIMITED).

    The grid is sub-OBS_AREA_LIMITED_KM2, so validation gates on hit-rate H.
    Model predicts flooding in only the first row (5 px) while the observed
    footprint covers the full grid (25 px): TP=5, FN=20 -> H=5/25=0.20,
    which is in [HIT_WARN_LIMITED=0.15, HIT_PASS_LIMITED=0.30) -> LIMITED-WARN.
    """
    rp_dir = tmp_path / "pluvial" / "rp_50"
    rp_dir.mkdir(parents=True)
    tif = rp_dir / "pluvial_depth_SSP5-8.5_2100_rp50.tif"
    # Predict flooding only in the first row (5 px); rest dry.
    depth_data = np.zeros((5, 5), dtype=np.float32)
    depth_data[0, :] = 0.5
    _write_depth_tif(tif, depth_data)

    # Observed covers the full 5×5 grid (25 px).
    from shapely.geometry import box
    observed_geom = box(0, 0, 150, 150)
    event = _make_event_config(out_dir_str=str(tmp_path))

    with patch("scripts.validate_historical_events.download_zip"), \
         patch("scripts.validate_historical_events.extract_zip"), \
         patch("scripts.validate_historical_events.find_shapefile"), \
         patch("scripts.validate_historical_events.load_flood_footprint") as mock_lf:
        mock_lf.return_value = [observed_geom]
        result = validate_event(event, out_dir=tmp_path, depth_threshold=0.10, no_download=False)

    assert result["verdict"] == "LIMITED-WARN"
    assert HIT_WARN_LIMITED <= result["best_h"] < HIT_PASS_LIMITED


def test_validate_event_fail(tmp_path):
    """validate_event returns LIMITED-FAIL when model predicts nothing.

    Sub-OBS_AREA_LIMITED_KM2 grid → LIMITED tier; no predicted flood means
    H=0 < HIT_WARN_LIMITED (0.15) → LIMITED-FAIL.
    """
    rp_dir = tmp_path / "pluvial" / "rp_50"
    rp_dir.mkdir(parents=True)
    tif = rp_dir / "pluvial_depth_SSP5-8.5_2100_rp50.tif"
    # All depths = 0 → no predicted flood
    _write_depth_tif(tif, np.zeros((5, 5), dtype=np.float32))

    from shapely.geometry import box
    observed_geom = box(0, 0, 150, 150)
    event = _make_event_config(out_dir_str=str(tmp_path))

    with patch("scripts.validate_historical_events.download_zip"), \
         patch("scripts.validate_historical_events.extract_zip"), \
         patch("scripts.validate_historical_events.find_shapefile"), \
         patch("scripts.validate_historical_events.load_flood_footprint") as mock_lf:
        mock_lf.return_value = [observed_geom]
        result = validate_event(event, out_dir=tmp_path, depth_threshold=0.10, no_download=False)

    assert result["verdict"] == "LIMITED-FAIL"
    assert result["best_csi"] == pytest.approx(0.0)


def test_validate_event_missing_out_dir():
    """validate_event raises SystemExit(2) if out_dir does not exist."""
    event = _make_event_config(out_dir_str="outputs/nonexistent_city")
    with pytest.raises(SystemExit) as exc_info:
        validate_event(event, out_dir=Path("outputs/nonexistent_city"),
                       depth_threshold=0.10, no_download=False)
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# Task 6: CLI tests
# ---------------------------------------------------------------------------

from click.testing import CliRunner
from scripts.validate_historical_events import cli


def test_cli_unknown_event():
    runner = CliRunner()
    result = runner.invoke(cli, ["--event", "XXXXXXX"])
    assert result.exit_code != 0
    assert "Unknown event" in result.output


def test_cli_missing_out_dir():
    runner = CliRunner()
    result = runner.invoke(cli, ["--event", "JKT2020",
                                 "--out-dir", "outputs/nonexistent_99"])
    assert result.exit_code == 2


def test_cli_no_download_cache_miss(tmp_path):
    """--no-download: if download_zip raises FileNotFoundError, validate_event exits 2."""
    # Create a depth raster so validate_event passes the "no rasters found" check
    # and reaches the download step.
    rp_dir = tmp_path / "pluvial" / "rp_10"
    rp_dir.mkdir(parents=True)
    _write_depth_tif(rp_dir / "pluvial_depth_SSP5-8.5_2100_rp10.tif",
                     np.full((5, 5), 0.5, dtype=np.float32))

    # Patch download_zip so it behaves as if the cache is empty with --no-download
    with patch("scripts.validate_historical_events.download_zip",
               side_effect=FileNotFoundError("Cache miss and --no-download set")):
        runner = CliRunner()
        result = runner.invoke(cli, ["--event", "JKT2020",
                                     "--out-dir", str(tmp_path),
                                     "--no-download"])
    # FileNotFoundError caught in validate_event → sys.exit(2)
    assert result.exit_code == 2
