"""Render IEEE Fig. 1 — the pipeline as a VERTICAL flowchart sized for one IEEE column.

The reused fig4_pipeline.png is landscape and becomes illegible at ~3.4 in column
width. This draws a portrait data-flow:

    open-data inputs  ->  forcing & conditioning  ->  three per-hazard solvers
    (coastal / fluvial / pluvial, in parallel)  ->  per-pixel-max composite
    ->  30 m multi-hazard atlas.

Boxes are laid out top-down with heights auto-fitted to line count. Pure matplotlib.

Run:  python scripts/render_ieee_pipeline.py
Out:  docs/paper/figures/ieee_fig1_pipeline.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "docs" / "paper" / "figures" / "ieee_fig1_pipeline.png"

EDGE = "#333333"
C_IN    = "#eef1f4"
C_FORCE = "#e3ebf3"
C_COAST = "#cfe2f3"
C_FLUV  = "#d9ead3"
C_PLUV  = "#fce5cd"
C_COMP  = "#e3ebf3"
C_OUT   = "#cfe7e6"

TITLE_FS  = 7.5
BODY_FS   = 6.2
LINE      = 0.52   # data-units per body line
TITLE_GAP = 0.58   # data-units from box top to first body line
PAD       = 0.22   # bottom padding inside box

fig, ax = plt.subplots(figsize=(3.9, 5.5), dpi=300)
ax.set_xlim(0, 10)
ax.axis("off")


def box(cx, top, w, title, body_lines, fc, body_fs=BODY_FS):
    """Draw a box whose top edge is at y=top; height auto-fits the line count.
    Returns the box's bottom y."""
    h = TITLE_GAP + LINE * len(body_lines) + PAD
    cy = top - h / 2
    ax.add_patch(FancyBboxPatch(
        (cx - w / 2, cy - h / 2), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.14",
        linewidth=0.8, edgecolor=EDGE, facecolor=fc, zorder=2))
    ax.text(cx, top - 0.26, title, ha="center", va="top",
            fontsize=TITLE_FS, fontweight="bold", zorder=3)
    ax.text(cx, top - TITLE_GAP, "\n".join(body_lines), ha="center", va="top",
            fontsize=body_fs, zorder=3, linespacing=1.3)
    return cy - h / 2


def arrow(x0, y0, x1, y1):
    ax.add_patch(FancyArrowPatch(
        (x0, y0), (x1, y1),
        arrowstyle="-|>", mutation_scale=8, linewidth=0.8,
        color=EDGE, shrinkA=0, shrinkB=0, zorder=1))


GAP = 0.58
W   = 9.4

# 1) Inputs — 3 lines (WorldCover + OSM merged)
b_in = box(5.0, 13.5, W, "Open-data inputs  (free, no registration)", [
    "Copernicus GLO-30 DEM · ERA5-Land",
    "UHSLC tides · GloFAS v4 discharge",
    "IPCC AR6 SLR · ESA WorldCover · OSM",
], C_IN)

# 2) Forcing & conditioning — 2 lines (IDF line merged)
b_force = box(5.0, b_in - GAP, W, "Forcing & conditioning", [
    "Per-country IDF  (PUB · JPS · TMD · BMKG)",
    "GEV surge · AR6 SLR · subsidence DEM",
], C_FORCE)

# 3) Three per-hazard solvers (parallel) — 2 lines each
s_top = b_force - GAP
b_coast = box(1.80, s_top, 2.95, "Coastal",
              ["local-inertia", "shallow-water solver"], C_COAST, body_fs=6.0)
box(5.00, s_top, 2.95, "Fluvial",
    ["main-stem HAND", "(GloFAS-reach trunk)"], C_FLUV, body_fs=6.0)
box(8.20, s_top, 2.95, "Pluvial",
    ["fill-and-spill", "(runoff coeff/cell)"], C_PLUV, body_fs=6.0)

# 4) Composite — 1 line
b_comp = box(5.0, b_coast - GAP, W, "Per-pixel-maximum composite",
             ["severity: minor / moderate / major / severe"], C_COMP, body_fs=6.0)

# 5) Output — 2 lines
b_out = box(5.0, b_comp - GAP, W, "30 m multi-hazard flood atlas", [
    "9 RPs × SSP2-4.5 / SSP5-8.5 × 2050 / 2100",
    "open & reproducible — one command per city",
], C_OUT)

# Arrows
arrow(5.0, b_in, 5.0, b_in - GAP)
for cx in (1.80, 5.0, 8.20):
    arrow(5.0, b_force, cx, s_top)
for cx in (1.80, 5.0, 8.20):
    arrow(cx, b_coast, 5.0, b_coast - GAP)
arrow(5.0, b_comp, 5.0, b_comp - GAP)

ax.set_ylim(b_out - 0.3, 13.8)
fig.savefig(OUT, bbox_inches="tight", pad_inches=0.04)
print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")
