from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform as rio_transform

from scripts.hotspot_scoring import (
    Hotspot,
    ScoreResult,
    bootstrap_auc_diff_ci,
    bootstrap_tss_ci,
    bootstrap_tss_diff_ci,
    hit_vectors,
    load_hotspots,
    passes_numeric_gate,
    roc_auc,
    sample_hit,
    sample_score,
    score_table,
    score_vectors,
    skill_scores,
)

TABLE = Path(__file__).resolve().parents[1] / "data/singapore/flood_obs/hotspots/sg_pluvial_hotspots.csv"

def test_load_hotspots_parses_rows():
    rows = load_hotspots(TABLE)
    assert len(rows) >= 3
    assert all(isinstance(r, Hotspot) for r in rows)
    orchard = next(r for r in rows if "Orchard" in r.label)
    assert orchard.cls == "flood"
    assert orchard.documented_depth_m == pytest.approx(0.4)
    assert orchard.anchor_rp == 50

def test_every_row_has_a_source():
    rows = load_hotspots(TABLE)
    assert all(r.source.strip() for r in rows), "every hotspot must cite a source"

def test_class_values_are_valid():
    rows = load_hotspots(TABLE)
    assert all(r.cls in ("flood", "dry") for r in rows)

def test_table_meets_spec_counts():
    rows = load_hotspots(TABLE)
    pos = [r for r in rows if r.cls == "flood"]
    dry = [r for r in rows if r.cls == "dry"]
    assert 12 <= len(pos) <= 40, f"spec wants 12-40 positives, got {len(pos)}"
    assert 5 <= len(dry) <= 24, f"spec wants 5-24 dry controls, got {len(dry)}"

def test_load_hotspots_rejects_out_of_range_coords(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "label,lon,lat,class,documented_depth_m,anchor_rp,source,georef_confidence\n"
        "bad_pt,999.0,1.3,flood,,50,src,high\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="lon"):
        load_hotspots(bad)

def _write_raster(tmp_path, arr, *, res=30.0, crs="EPSG:32648",
                  origin_x=360000.0, origin_y=160000.0):
    path = tmp_path / "depth.tif"
    transform = from_origin(origin_x, origin_y, res, res)
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0],
                       width=arr.shape[1], count=1, dtype="float32",
                       crs=crs, transform=transform, nodata=np.nan) as ds:
        ds.write(arr.astype("float32"), 1)
    return path

def _lonlat_of_cell(path, row, col):
    with rasterio.open(path) as ds:
        x, y = ds.transform * (col + 0.5, row + 0.5)
        lons, lats = rio_transform(ds.crs, "EPSG:4326", [x], [y])
    return lons[0], lats[0]

def test_sample_hit_true_when_deep_cell_within_radius(tmp_path):
    arr = np.zeros((20, 20), dtype="float32")
    arr[10, 10] = 0.5  # one deep cell
    path = _write_raster(tmp_path, arr)
    lon, lat = _lonlat_of_cell(path, 10, 10)
    assert sample_hit(path, lon, lat, radius_m=150.0, depth_threshold_m=0.10) is True

def test_sample_hit_false_when_all_shallow(tmp_path):
    arr = np.full((20, 20), 0.02, dtype="float32")  # below threshold
    path = _write_raster(tmp_path, arr)
    lon, lat = _lonlat_of_cell(path, 10, 10)
    assert sample_hit(path, lon, lat, radius_m=150.0, depth_threshold_m=0.10) is False

def test_sample_hit_false_when_deep_cell_outside_radius(tmp_path):
    arr = np.zeros((40, 40), dtype="float32")
    arr[0, 0] = 1.0  # deep, but far from the sampled point
    path = _write_raster(tmp_path, arr)
    lon, lat = _lonlat_of_cell(path, 30, 30)
    assert sample_hit(path, lon, lat, radius_m=150.0, depth_threshold_m=0.10) is False

def test_sample_hit_false_when_point_outside_raster(tmp_path):
    arr = np.zeros((10, 10), dtype="float32")
    path = _write_raster(tmp_path, arr)
    assert sample_hit(path, 0.0, 0.0, radius_m=150.0, depth_threshold_m=0.10) is False


def test_skill_scores_perfect():
    r = skill_scores(flood_hits=[True, True, True, True], dry_hits=[False, False])
    assert r.hit_rate == 1.0
    assert r.correct_reject_rate == 1.0
    assert r.tss == 1.0

def test_skill_scores_flood_everything():
    r = skill_scores(flood_hits=[True, True, True, True], dry_hits=[True, True])
    assert r.hit_rate == 1.0
    assert r.correct_reject_rate == 0.0
    assert r.tss == 0.0

def test_skill_scores_mixed():
    r = skill_scores(flood_hits=[True, True, True, False], dry_hits=[False, True])
    assert r.hit_rate == 0.75
    assert r.correct_reject_rate == 0.5
    assert r.tss == 0.25

def test_passes_numeric_gate_true():
    model = ScoreResult(hit_rate=0.7, correct_reject_rate=0.8, tss=0.5)
    base_a = ScoreResult(hit_rate=0.0, correct_reject_rate=1.0, tss=0.0)
    base_b = ScoreResult(hit_rate=0.6, correct_reject_rate=0.3, tss=-0.1)
    ok, reasons = passes_numeric_gate(model, [base_a, base_b],
                                      hit_rate_floor=0.70, margin=0.20)
    assert ok is True
    assert reasons == []

def test_passes_numeric_gate_fails_on_low_hitrate():
    model = ScoreResult(hit_rate=0.5, correct_reject_rate=0.9, tss=0.4)
    base = ScoreResult(hit_rate=0.0, correct_reject_rate=1.0, tss=0.0)
    ok, reasons = passes_numeric_gate(model, [base], hit_rate_floor=0.70, margin=0.20)
    assert ok is False
    assert any("hit-rate" in r for r in reasons)

def test_passes_numeric_gate_fails_on_thin_margin():
    model = ScoreResult(hit_rate=0.8, correct_reject_rate=0.7, tss=0.5)
    base = ScoreResult(hit_rate=0.7, correct_reject_rate=0.65, tss=0.35)
    ok, reasons = passes_numeric_gate(model, [base], hit_rate_floor=0.70, margin=0.20)
    assert ok is False
    assert any("margin" in r for r in reasons)


def test_roc_auc_perfect_inverted_and_chance():
    assert roc_auc([3.0, 2.0, 4.0], [0.0, 1.0]) == pytest.approx(1.0)   # all flood > all dry
    assert roc_auc([0.0, 1.0], [3.0, 2.0, 4.0]) == pytest.approx(0.0)   # inverted
    assert roc_auc([1.0, 1.0], [1.0, 1.0]) == pytest.approx(0.5)        # all tied
    # one tie at the boundary: flood {2,1}, dry {1,0} -> pairs (2>1,2>0,1=1,1>0)=3.5/4
    assert roc_auc([2.0, 1.0], [1.0, 0.0]) == pytest.approx(3.5 / 4.0)


def test_roc_auc_empty_side_is_chance():
    assert roc_auc([], [1.0, 2.0]) == 0.5
    assert roc_auc([1.0], []) == 0.5


def test_sample_score_returns_max_in_window(tmp_path):
    arr = np.zeros((40, 40), dtype="float32")
    arr[10, 10] = 0.4
    arr[10, 11] = 0.9  # higher, also within radius
    path = _write_raster(tmp_path, arr)
    lon, lat = _lonlat_of_cell(path, 10, 10)
    assert sample_score(path, lon, lat, radius_m=150.0) == pytest.approx(0.9)


def test_sample_score_zero_outside_raster(tmp_path):
    arr = np.full((10, 10), 0.5, dtype="float32")
    path = _write_raster(tmp_path, arr)
    assert sample_score(path, 0.0, 0.0, radius_m=150.0) == 0.0


def test_bootstrap_auc_diff_zero_when_equal_and_positive_when_dominant():
    f, d = [3.0, 2.0, 4.0, 5.0], [0.0, 1.0, 0.5]
    pt, lo, hi, frac = bootstrap_auc_diff_ci(f, d, f, d, n_boot=1000, seed=3)
    assert pt == pytest.approx(0.0)
    assert lo == pytest.approx(0.0) and hi == pytest.approx(0.0)  # identical, paired
    # same 3 positives / 2 negatives: model ranks perfectly (AUC 1.0),
    # baseline inverts (all dry > all flood, AUC 0.0)
    pt2, lo2, hi2, frac2 = bootstrap_auc_diff_ci(
        [3.0, 4.0, 5.0], [0.0, 1.0],   # model: flood high, dry low
        [0.0, 1.0, 2.0], [3.0, 4.0],   # baseline: flood low, dry high
        n_boot=1000, seed=5)
    assert pt2 == pytest.approx(1.0)
    assert lo2 > 0.0 and frac2 == pytest.approx(1.0)


def test_hit_vectors_returns_per_point_booleans(tmp_path):
    arr = np.zeros((40, 40), dtype="float32")
    arr[10, 10] = 0.5
    path = _write_raster(tmp_path, arr)
    flood_lon, flood_lat = _lonlat_of_cell(path, 10, 10)
    dry_lon, dry_lat = _lonlat_of_cell(path, 30, 30)
    table = tmp_path / "t.csv"
    table.write_text(
        "label,lon,lat,class,documented_depth_m,anchor_rp,source,georef_confidence\n"
        f"flood_pt,{flood_lon},{flood_lat},flood,,50,src,high\n"
        f"dry_pt,{dry_lon},{dry_lat},dry,,50,src,high\n",
        encoding="utf-8",
    )
    fh, dh = hit_vectors(load_hotspots(table), path,
                         radius_m=150.0, depth_threshold_m=0.10)
    assert fh == [True]
    assert dh == [False]


def test_bootstrap_tss_ci_brackets_point_and_is_deterministic():
    # 8 positives all hit, 8 negatives all correct-reject -> TSS = 1.0
    fh = [True] * 8
    dh = [False] * 8
    point, lo, hi = bootstrap_tss_ci(fh, dh, n_boot=2000, seed=7)
    assert point == pytest.approx(1.0)
    assert lo == pytest.approx(1.0) and hi == pytest.approx(1.0)
    # determinism: same seed -> same CI
    again = bootstrap_tss_ci(fh, dh, n_boot=2000, seed=7)
    assert (point, lo, hi) == again


def test_bootstrap_tss_ci_has_width_for_mixed_results():
    fh = [True, True, True, False, True, False, True, True]   # HR 0.75
    dh = [False, False, True, False, False, True, False, False]  # CRR 0.75
    point, lo, hi = bootstrap_tss_ci(fh, dh, n_boot=4000, seed=11)
    assert lo < point < hi          # genuine uncertainty band
    assert -1.0 <= lo and hi <= 1.0  # TSS bounds respected


def test_bootstrap_tss_diff_ci_zero_when_model_equals_baseline():
    fh = [True, False, True, True]
    dh = [False, True, False, False]
    point, lo, hi, p_better = bootstrap_tss_diff_ci(fh, dh, fh, dh,
                                                    n_boot=2000, seed=3)
    assert point == pytest.approx(0.0)
    assert lo <= 0.0 <= hi
    # identical scores -> paired difference is exactly 0 every resample
    assert lo == pytest.approx(0.0) and hi == pytest.approx(0.0)


def test_bootstrap_tss_diff_ci_positive_when_model_dominates():
    model_f, model_d = [True] * 6, [False] * 6          # TSS 1.0
    base_f, base_d = [False] * 6, [True] * 6            # TSS -1.0
    point, lo, hi, p_better = bootstrap_tss_diff_ci(model_f, model_d,
                                                    base_f, base_d,
                                                    n_boot=2000, seed=5)
    assert point == pytest.approx(2.0)
    assert lo > 0.0                # CI excludes zero -> significant
    assert p_better == pytest.approx(1.0)


def test_score_table_separates_classes(tmp_path):
    # Build a raster that floods the flood point but not the dry point.
    arr = np.zeros((40, 40), dtype="float32")
    arr[10, 10] = 0.5
    path = _write_raster(tmp_path, arr)
    flood_lon, flood_lat = _lonlat_of_cell(path, 10, 10)
    dry_lon, dry_lat = _lonlat_of_cell(path, 30, 30)

    table = tmp_path / "t.csv"
    table.write_text(
        "label,lon,lat,class,documented_depth_m,anchor_rp,source,georef_confidence\n"
        f"flood_pt,{flood_lon},{flood_lat},flood,,50,src,high\n"
        f"dry_pt,{dry_lon},{dry_lat},dry,,50,src,high\n",
        encoding="utf-8",
    )
    res = score_table(load_hotspots(table), path,
                      radius_m=150.0, depth_threshold_m=0.10)
    assert res.hit_rate == 1.0
    assert res.correct_reject_rate == 1.0
    assert res.tss == 1.0
