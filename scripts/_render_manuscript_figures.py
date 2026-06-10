"""Render the manuscript figures from frozen validation data.

Outputs PNGs to docs/paper/figures/. Pure-derived from the committed register +
rasters, so re-running reproduces the figures. Run:
    python scripts/_render_manuscript_figures.py
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.hotspot_scoring import load_hotspots, hit_vectors, score_vectors, roc_auc  # noqa: E402
FIG = ROOT / "docs/paper/figures"
FIG.mkdir(parents=True, exist_ok=True)
REG = ROOT / "data/singapore/flood_obs/hotspots/sg_pluvial_hotspots.csv"
MODEL = glob.glob(str(ROOT / "outputs/singapore_ssp585_2020/pluvial/rp_50/pluvial_depth_*.tif"))[0]
TWI_C = ROOT / "cache/baselines/naive_twi_continuous_sg.tif"
TWI_D = ROOT / "cache/baselines/naive_twi_sg.tif"
AQ = ROOT / "cache/aqueduct/aqueduct_sg_rp50.tif"

C = {"model": "#1f77b4", "TWI": "#d62728", "Aqueduct": "#7f7f7f"}
hs = load_hotspots(REG)
rng = np.random.default_rng(12345)


def _ci(vec, n=10000):
    v = np.asarray(vec, float)
    if v.size == 0:
        return 0.0, 0.0, 0.0
    idx = rng.integers(0, v.size, size=(n, v.size))
    bs = v[idx].mean(axis=1)
    return float(v.mean()), float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))


# ---- Figure 1: ROC curves (threshold-free) -------------------------------------
def fig_roc():
    fig, ax = plt.subplots(figsize=(5.2, 5.0))
    for nm, path in [("model", MODEL), ("TWI", TWI_C), ("Aqueduct", AQ)]:
        f, d = score_vectors(hs, path)
        f, d = np.asarray(f), np.asarray(d)
        thr = np.unique(np.concatenate([f, d, [-np.inf, np.inf]]))[::-1]
        tpr = [(f >= t).mean() for t in thr]
        fpr = [(d >= t).mean() for t in thr]
        ax.plot(fpr, tpr, color=C[nm], lw=2, label=f"{nm} (AUC {roc_auc(f, d):.2f})")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8, alpha=0.6, label="no skill (0.50)")
    ax.set_xlabel("False-positive rate (1 − specificity)")
    ax.set_ylabel("True-positive rate (hit-rate)")
    ax.set_title("Threshold-free ranking skill (ROC), present-day field")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.02); ax.legend(loc="lower right", fontsize=9)
    ax.set_aspect("equal")
    fig.tight_layout(); fig.savefig(FIG / "fig1_roc.png", dpi=200); plt.close(fig)
    print("wrote fig1_roc.png")


# ---- Figure 2: precision-recall split (HR vs CRR bars + CIs) --------------------
def fig_precision_recall():
    names = ["model", "TWI", "Aqueduct"]
    paths = {"model": MODEL, "TWI": TWI_D, "Aqueduct": AQ}
    hr, crr = {}, {}
    for nm in names:
        f, d = hit_vectors(hs, paths[nm], depth_threshold_m=0.10)
        hr[nm] = _ci([1.0 if x else 0.0 for x in f])
        crr[nm] = _ci([1.0 if not x else 0.0 for x in d])
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 4.2))
    for ax, metric, lbl in [(axes[0], hr, "Hit-rate (recall)"),
                            (axes[1], crr, "Correct-reject rate (specificity)")]:
        xs = np.arange(len(names))
        vals = [metric[n][0] for n in names]
        lo = [metric[n][0] - metric[n][1] for n in names]
        hi = [metric[n][2] - metric[n][0] for n in names]
        ax.bar(xs, vals, color=[C[n] for n in names],
               yerr=[lo, hi], capsize=5, edgecolor="black", lw=0.6)
        ax.set_xticks(xs); ax.set_xticklabels(names)
        ax.set_ylim(0, 1.05); ax.set_ylabel(lbl)
        for x, v in zip(xs, vals):
            ax.text(x, v + 0.03, f"{v:.2f}", ha="center", fontsize=9)
    axes[0].set_title("Recall: TWI floods all low ground; Aqueduct ~nothing")
    axes[1].set_title("Specificity: model ≫ TWI  (Aqueduct=1.0 is degenerate, flags ~nothing)")
    fig.suptitle("Precision–recall split at the operating point (RP50, ≥0.10 m; N=38/20)",
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(FIG / "fig2_precision_recall.png", dpi=200); plt.close(fig)
    print("wrote fig2_precision_recall.png")


# ---- Figure 3: hazard-map panel ------------------------------------------------
def fig_hazard_maps():
    base = ROOT / "outputs/singapore_ssp585_2100"
    layers = []
    for haz, rp in [("pluvial", 100), ("fluvial", 100), ("coastal", 100)]:
        g = glob.glob(str(base / haz / f"rp_{rp}" / f"*depth*rp{rp}*.tif")) or \
            glob.glob(str(base / haz / f"rp_{rp}" / "*depth*.tif"))
        if g:
            layers.append((haz, g[0]))
    if not layers:
        print("hazard rasters not found; skipping fig3"); return
    fig, axes = plt.subplots(1, len(layers), figsize=(4.0 * len(layers), 4.2))
    if len(layers) == 1:
        axes = [axes]
    for ax, (haz, p) in zip(axes, layers):
        with rasterio.open(p) as ds:
            a = ds.read(1).astype(float)
        a = np.where(np.isfinite(a) & (a > 0.05), a, np.nan)
        im = ax.imshow(np.clip(a, 0, 2.0), cmap="Blues", vmin=0, vmax=2.0)
        ax.set_title(f"{haz.capitalize()} (RP100, SSP5-8.5/2100)"); ax.axis("off")
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.01, label="depth (m, clipped 2 m)")
    fig.savefig(FIG / "fig3_hazard_maps.png", dpi=170, bbox_inches="tight"); plt.close(fig)
    print("wrote fig3_hazard_maps.png")


# ---- Figure 4: pipeline schematic ----------------------------------------------
def fig_pipeline():
    fig, ax = plt.subplots(figsize=(9.5, 3.4)); ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 4)
    def box(x, y, w, h, text, fc):
        ax.add_patch(plt.Rectangle((x, y), w, h, fc=fc, ec="black", lw=1.0))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.2)
    def arrow(x0, y0, x1, y1):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="->", lw=1.1))
    box(0.1, 1.4, 1.8, 1.2, "Open inputs\nGLO-30, tide gauges,\nAR6, IDF, PUB", "#e8f0fe")
    box(2.3, 1.4, 1.8, 1.2, "Bare-earth DEM\n+ surgical\nde-pitting", "#e8f0fe")
    box(4.5, 2.55, 1.8, 0.95, "Coastal bathtub\n(GEV + SLR)", "#fde8e8")
    box(4.5, 1.45, 1.8, 0.95, "Pluvial rain-on-grid\n(local-inertial)", "#e8f7e8")
    box(4.5, 0.35, 1.8, 0.95, "Fluvial HAND\n(channel-masked)", "#fdf3e8")
    box(6.8, 1.4, 1.5, 1.2, "Hazard\nlayers\n(per RP/scenario)", "#f0f0f0")
    box(8.5, 1.4, 1.4, 1.2, "Documented-\nregister\nvalidation", "#ede8fe")
    arrow(1.9, 2.0, 2.3, 2.0); arrow(4.1, 2.0, 4.5, 3.0)
    arrow(4.1, 2.0, 4.5, 1.9); arrow(4.1, 2.0, 4.5, 0.8)
    for yy in (3.0, 1.9, 0.8):
        arrow(6.3, yy, 6.8, 2.0)
    arrow(8.3, 2.0, 8.5, 2.0)
    ax.set_title("Open multi-hazard pipeline and documented-register validation", fontsize=10)
    fig.tight_layout(); fig.savefig(FIG / "fig4_pipeline.png", dpi=200); plt.close(fig)
    print("wrote fig4_pipeline.png")


def _random_negatives(model_path, positives, n=60, seed=2026):
    import math
    from rasterio.warp import transform as T
    from scripts.hotspot_scoring import sample_score
    ds = rasterio.open(model_path); arr = ds.read(1); H, W = arr.shape
    rng = np.random.default_rng(seed)
    def far(lo, la):
        return min(math.hypot((lo - h.lon) * 111320 * math.cos(math.radians(la)),
                              (la - h.lat) * 110540) for h in positives) >= 300
    pts = []
    while len(pts) < n:
        r = int(rng.integers(0, H)); c = int(rng.integers(0, W))
        if not np.isfinite(arr[r, c]):
            continue
        x, y = ds.transform * (c + 0.5, r + 0.5)
        lo, la = T(ds.crs, "EPSG:4326", [x], [y])
        if far(lo[0], la[0]):
            pts.append((lo[0], la[0]))
    return pts


def _roc_xy(flood, dry):
    f, d = np.asarray(flood), np.asarray(dry)
    thr = np.unique(np.concatenate([f, d, [-np.inf, np.inf]]))[::-1]
    return [(d >= t).mean() for t in thr], [(f >= t).mean() for t in thr]


def fig_roc_flip():
    """Two ROC panels showing the comparative verdict flips with the negative set."""
    from scripts.hotspot_scoring import sample_score
    pos = [h for h in hs if h.cls == "flood"]
    mf, md = score_vectors(hs, MODEL)        # model: pos, curated dry
    tf, td = score_vectors(hs, TWI_C)        # TWI:   pos, curated dry
    rnd = _random_negatives(MODEL, pos)
    m_rand = [sample_score(MODEL, lo, la) for lo, la in rnd]
    t_rand = [sample_score(TWI_C, lo, la) for lo, la in rnd]
    panels = [("vs low-lying dry controls (hard)", md, td),
              ("vs random land (easy)", m_rand, t_rand)]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.6))
    for ax, (title, mneg, tneg) in zip(axes, panels):
        fx, fy = _roc_xy(mf, mneg); tx, ty = _roc_xy(tf, tneg)
        ax.plot(fx, fy, color=C["model"], lw=2,
                label=f"model (AUC {roc_auc(mf, mneg):.2f})")
        ax.plot(tx, ty, color=C["TWI"], lw=2,
                label=f"TWI (AUC {roc_auc(tf, tneg):.2f})")
        ax.plot([0, 1], [0, 1], "k--", lw=0.8, alpha=0.6)
        ax.set_title(title); ax.set_xlabel("false-positive rate")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1.02); ax.set_aspect("equal")
        ax.legend(loc="lower right", fontsize=9)
    axes[0].set_ylabel("true-positive rate")
    fig.suptitle("The comparative verdict flips with the negative set", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(FIG / "fig5_roc_flip.png", dpi=200); plt.close(fig)
    print("wrote fig5_roc_flip.png")


if __name__ == "__main__":
    fig_roc(); fig_precision_recall(); fig_hazard_maps(); fig_pipeline(); fig_roc_flip()
    print("done ->", FIG)
