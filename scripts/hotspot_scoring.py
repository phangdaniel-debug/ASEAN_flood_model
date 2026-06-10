"""Documented-hotspot scoring library for Singapore pluvial validation.

Pure, import-testable: loads the attributed hotspot table, samples a depth
raster at a point (radius + depth threshold -> hit), and computes hit-rate,
correct-reject-rate, and the True Skill Statistic (TSS = HR + CRR - 1).

See docs/superpowers/specs/2026-05-31-singapore-scope-design.md sections 4 and 6.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform as rio_transform


@dataclass(frozen=True)
class Hotspot:
    label: str
    lon: float
    lat: float
    cls: str                      # "flood" (positive) | "dry" (negative control)
    documented_depth_m: float | None
    anchor_rp: int
    source: str
    georef_confidence: str


def load_hotspots(csv_path: Path) -> list[Hotspot]:
    """Load and validate the hotspot table. Raises ValueError on bad rows."""
    rows: list[Hotspot] = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=2):  # line 1 = header
            cls = row["class"].strip()
            if cls not in ("flood", "dry"):
                raise ValueError(f"{csv_path}:{i}: class must be flood|dry, got {cls!r}")
            if not row["source"].strip():
                raise ValueError(f"{csv_path}:{i}: every hotspot must cite a source")
            lon, lat = float(row["lon"]), float(row["lat"])
            if not (-180.0 <= lon <= 180.0):
                raise ValueError(f"{csv_path}:{i}: lon {lon} out of range [-180, 180]")
            if not (-90.0 <= lat <= 90.0):
                raise ValueError(f"{csv_path}:{i}: lat {lat} out of range [-90, 90]")
            depth_raw = row["documented_depth_m"].strip()
            rows.append(Hotspot(
                label=row["label"].strip(),
                lon=lon,
                lat=lat,
                cls=cls,
                documented_depth_m=float(depth_raw) if depth_raw else None,
                anchor_rp=int(row["anchor_rp"]),
                source=row["source"].strip(),
                georef_confidence=row["georef_confidence"].strip(),
            ))
    return rows


def sample_hit(
    raster_path: str | Path,
    lon: float,
    lat: float,
    *,
    radius_m: float = 150.0,
    depth_threshold_m: float = 0.10,
) -> bool:
    """True if any cell within ``radius_m`` of (lon, lat) has depth >= threshold.

    Point outside the raster, or no finite cells in the window, -> False.
    """
    with rasterio.open(raster_path) as ds:
        xs, ys = rio_transform("EPSG:4326", ds.crs, [lon], [lat])
        col_f, row_f = ~ds.transform * (xs[0], ys[0])
        row, col = int(math.floor(row_f)), int(math.floor(col_f))
        res_x = abs(ds.transform.a)
        res_y = abs(ds.transform.e)
        rad_px_r = int(math.ceil(radius_m / res_y))
        rad_px_c = int(math.ceil(radius_m / res_x))
        h, w = ds.height, ds.width
        if not (0 <= row < h and 0 <= col < w):
            return False
        r0, r1 = max(0, row - rad_px_r), min(h, row + rad_px_r + 1)
        c0, c1 = max(0, col - rad_px_c), min(w, col + rad_px_c + 1)
        block = ds.read(1, window=((r0, r1), (c0, c1))).astype(np.float64)
        nodata = ds.nodata
        if nodata is not None and not (isinstance(nodata, float) and math.isnan(nodata)):
            block = np.where(block == nodata, np.nan, block)
    finite = np.isfinite(block)
    if not finite.any():
        return False
    return bool(np.any(finite & (block >= depth_threshold_m)))


def sample_score(
    raster_path: str | Path,
    lon: float,
    lat: float,
    *,
    radius_m: float = 150.0,
) -> float:
    """Continuous score at (lon, lat): the MAX finite cell value within ``radius_m``.

    The ranking analogue of :func:`sample_hit` (which thresholds this). Point
    outside the raster, or no finite cells in the window, -> 0.0 (not flagged).
    """
    with rasterio.open(raster_path) as ds:
        xs, ys = rio_transform("EPSG:4326", ds.crs, [lon], [lat])
        col_f, row_f = ~ds.transform * (xs[0], ys[0])
        row, col = int(math.floor(row_f)), int(math.floor(col_f))
        rad_px_r = int(math.ceil(radius_m / abs(ds.transform.e)))
        rad_px_c = int(math.ceil(radius_m / abs(ds.transform.a)))
        h, w = ds.height, ds.width
        if not (0 <= row < h and 0 <= col < w):
            return 0.0
        r0, r1 = max(0, row - rad_px_r), min(h, row + rad_px_r + 1)
        c0, c1 = max(0, col - rad_px_c), min(w, col + rad_px_c + 1)
        block = ds.read(1, window=((r0, r1), (c0, c1))).astype(np.float64)
        nodata = ds.nodata
        if nodata is not None and not (isinstance(nodata, float) and math.isnan(nodata)):
            block = np.where(block == nodata, np.nan, block)
    finite = block[np.isfinite(block)]
    return float(finite.max()) if finite.size else 0.0


def score_vectors(
    hotspots: list[Hotspot],
    raster_path,
    *,
    radius_m: float = 150.0,
) -> tuple[list[float], list[float]]:
    """Per-point continuous scores for (flood positives, dry negatives)."""
    flood = [sample_score(raster_path, h.lon, h.lat, radius_m=radius_m)
             for h in hotspots if h.cls == "flood"]
    dry = [sample_score(raster_path, h.lon, h.lat, radius_m=radius_m)
           for h in hotspots if h.cls == "dry"]
    return flood, dry


def roc_auc(flood_scores, dry_scores) -> float:
    """Threshold-free skill: AUC = P(score(flood) > score(dry)) + ½ P(tie).

    The Mann-Whitney U statistic normalised by n_pos·n_neg. 1.0 = perfect
    ranking, 0.5 = no skill, 0.0 = perfectly inverted. Empty either side -> 0.5.
    """
    fs = np.asarray(flood_scores, dtype=np.float64)
    ds_ = np.asarray(dry_scores, dtype=np.float64)
    if fs.size == 0 or ds_.size == 0:
        return 0.5
    # rank-based AUC (handles ties with ½ credit), O(n log n)
    allv = np.concatenate([fs, ds_])
    order = allv.argsort(kind="mergesort")
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, allv.size + 1)
    # average ranks within ties
    _, inv, counts = np.unique(allv, return_inverse=True, return_counts=True)
    cum = np.cumsum(counts)
    start = cum - counts
    avg_rank = (start + cum + 1) / 2.0
    ranks = avg_rank[inv]
    r_pos = ranks[:fs.size].sum()
    auc = (r_pos - fs.size * (fs.size + 1) / 2.0) / (fs.size * ds_.size)
    return float(auc)


def bootstrap_auc_diff_ci(
    model_flood, model_dry, base_flood, base_dry,
    *, n_boot: int = 10000, ci: float = 0.95, seed: int = 12345,
) -> tuple[float, float, float, float]:
    """Paired stratified bootstrap CI for (model_AUC - baseline_AUC).

    Model and baseline are scored on the same points, so positive and negative
    indices are resampled once per iteration and applied to both (paired).
    Returns ``(point_diff, ci_lo, ci_hi, frac_model_better)``.
    """
    mf, md = np.asarray(model_flood, float), np.asarray(model_dry, float)
    bf, bd = np.asarray(base_flood, float), np.asarray(base_dry, float)
    point = roc_auc(mf, md) - roc_auc(bf, bd)
    if mf.size == 0 or md.size == 0:
        return (point, point, point, 1.0 if point > 0 else 0.0)
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for k in range(n_boot):
        fi = rng.integers(0, mf.size, mf.size)
        di = rng.integers(0, md.size, md.size)
        diffs[k] = roc_auc(mf[fi], md[di]) - roc_auc(bf[fi], bd[di])
    alpha = (1.0 - ci) / 2.0
    return (point, float(np.quantile(diffs, alpha)),
            float(np.quantile(diffs, 1.0 - alpha)), float(np.mean(diffs > 0)))


@dataclass(frozen=True)
class ScoreResult:
    hit_rate: float
    correct_reject_rate: float
    tss: float


def skill_scores(flood_hits: list[bool], dry_hits: list[bool]) -> ScoreResult:
    """Hit-rate on flood positives, correct-reject-rate on dry negatives, TSS.

    TSS (Peirce skill statistic) = hit_rate + correct_reject_rate - 1.
    Empty positive set -> hit_rate 0.0; empty negative set -> CRR 1.0
    (no negatives to get wrong).
    """
    hr = (sum(flood_hits) / len(flood_hits)) if flood_hits else 0.0
    crr = (sum(1 for h in dry_hits if not h) / len(dry_hits)) if dry_hits else 1.0
    return ScoreResult(hit_rate=hr, correct_reject_rate=crr, tss=hr + crr - 1.0)


def score_table(
    hotspots: list[Hotspot],
    raster_path,
    *,
    radius_m: float = 150.0,
    depth_threshold_m: float = 0.10,
) -> ScoreResult:
    """Sample one raster at every hotspot and return the skill scores."""
    flood_hits = [
        sample_hit(raster_path, h.lon, h.lat,
                   radius_m=radius_m, depth_threshold_m=depth_threshold_m)
        for h in hotspots if h.cls == "flood"
    ]
    dry_hits = [
        sample_hit(raster_path, h.lon, h.lat,
                   radius_m=radius_m, depth_threshold_m=depth_threshold_m)
        for h in hotspots if h.cls == "dry"
    ]
    return skill_scores(flood_hits, dry_hits)


def hit_vectors(
    hotspots: list[Hotspot],
    raster_path,
    *,
    radius_m: float = 150.0,
    depth_threshold_m: float = 0.10,
) -> tuple[list[bool], list[bool]]:
    """Per-point hit booleans for (flood positives, dry negatives).

    Same sampling as :func:`score_table`, but returns the raw per-point
    vectors so a caller can bootstrap confidence intervals over them.
    """
    flood_hits = [
        sample_hit(raster_path, h.lon, h.lat,
                   radius_m=radius_m, depth_threshold_m=depth_threshold_m)
        for h in hotspots if h.cls == "flood"
    ]
    dry_hits = [
        sample_hit(raster_path, h.lon, h.lat,
                   radius_m=radius_m, depth_threshold_m=depth_threshold_m)
        for h in hotspots if h.cls == "dry"
    ]
    return flood_hits, dry_hits


def bootstrap_tss_ci(
    flood_hits: list[bool],
    dry_hits: list[bool],
    *,
    n_boot: int = 10000,
    ci: float = 0.95,
    seed: int = 12345,
) -> tuple[float, float, float]:
    """Stratified bootstrap percentile CI for the TSS.

    Positives and negatives are independent samples, so each bootstrap
    iteration resamples them separately (with replacement) and recomputes
    TSS = HR + CRR - 1. Returns ``(point_estimate, ci_lo, ci_hi)``.

    Degenerate inputs (no positives or no negatives) return the point
    estimate for all three values (no resampling possible).
    """
    point = skill_scores(flood_hits, dry_hits).tss
    fh = np.asarray(flood_hits, dtype=float)
    dh = np.asarray(dry_hits, dtype=float)
    if fh.size == 0 or dh.size == 0:
        return (point, point, point)
    rng = np.random.default_rng(seed)
    fi = rng.integers(0, fh.size, size=(n_boot, fh.size))
    di = rng.integers(0, dh.size, size=(n_boot, dh.size))
    hr = fh[fi].mean(axis=1)
    crr = 1.0 - dh[di].mean(axis=1)
    tss = hr + crr - 1.0
    alpha = (1.0 - ci) / 2.0
    lo = float(np.quantile(tss, alpha))
    hi = float(np.quantile(tss, 1.0 - alpha))
    return (point, lo, hi)


def bootstrap_tss_diff_ci(
    model_flood: list[bool],
    model_dry: list[bool],
    base_flood: list[bool],
    base_dry: list[bool],
    *,
    n_boot: int = 10000,
    ci: float = 0.95,
    seed: int = 12345,
) -> tuple[float, float, float, float]:
    """Paired stratified bootstrap CI for (model_TSS - baseline_TSS).

    Model and baseline are scored on the *same* points, so each iteration
    resamples one set of positive indices and one set of negative indices
    and applies them to BOTH classifiers (paired) — this cancels the
    shared sampling noise and is the right test for "is the model's
    margin over the baseline distinguishable from zero?".

    Returns ``(point_diff, ci_lo, ci_hi, frac_model_better)`` where the
    last value is the fraction of resamples with model_TSS > baseline_TSS
    (a one-sided bootstrap p-analogue).
    """
    point = (skill_scores(model_flood, model_dry).tss
             - skill_scores(base_flood, base_dry).tss)
    mf, md = np.asarray(model_flood, float), np.asarray(model_dry, float)
    bf, bd = np.asarray(base_flood, float), np.asarray(base_dry, float)
    if mf.size == 0 or md.size == 0:
        return (point, point, point, 1.0 if point > 0 else 0.0)
    rng = np.random.default_rng(seed)
    fi = rng.integers(0, mf.size, size=(n_boot, mf.size))
    di = rng.integers(0, md.size, size=(n_boot, md.size))
    m_tss = mf[fi].mean(axis=1) + (1.0 - md[di].mean(axis=1)) - 1.0
    b_tss = bf[fi].mean(axis=1) + (1.0 - bd[di].mean(axis=1)) - 1.0
    diff = m_tss - b_tss
    alpha = (1.0 - ci) / 2.0
    lo = float(np.quantile(diff, alpha))
    hi = float(np.quantile(diff, 1.0 - alpha))
    frac_better = float(np.mean(diff > 0.0))
    return (point, lo, hi, frac_better)


def passes_numeric_gate(
    model: ScoreResult,
    baselines: list[ScoreResult],
    *,
    hit_rate_floor: float = 0.70,
    margin: float = 0.20,
) -> tuple[bool, list[str]]:
    """Spec gates 3 & 4: model hit-rate >= floor AND model TSS beats every
    baseline TSS by >= margin. Returns (ok, list_of_failure_reasons)."""
    reasons: list[str] = []
    if model.hit_rate < hit_rate_floor:
        reasons.append(
            f"hit-rate {model.hit_rate:.2f} below floor {hit_rate_floor:.2f}")
    for i, b in enumerate(baselines):
        if (model.tss - b.tss) < margin:
            reasons.append(
                f"TSS margin over baseline #{i} is {model.tss - b.tss:.2f} "
                f"(< required {margin:.2f})")
    return (not reasons), reasons
