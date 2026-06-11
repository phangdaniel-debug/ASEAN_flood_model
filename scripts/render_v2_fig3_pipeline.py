"""Render v2 Fig. 3 -- pipeline data-flow as a vertical flowchart for one IEEE column.

Matches the reviewed-PDF pipeline, which adds a TRUST GATE terminal box below the
atlas (model-blind hotspot location skill + bathtub-bias characterisation):

    open-data inputs -> forcing & conditioning -> three per-hazard solvers
    (coastal / fluvial / pluvial) -> per-pixel-max composite -> 30 m atlas
    -> trust gate.

Boxes are laid out top-down with heights auto-fitted to line count. Pure matplotlib.

Run:  python scripts/render_v2_fig3_pipeline.py
Out:  docs/paper/v2/figures/fig3_pipeline.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "docs" / "paper" / "v2" / "figures" / "fig3_pipeline.png"

EDGE = "#333333"
C_IN    = "#eef1f4"
C_FORCE = "#e3ebf3"
C_COAST = "#cfe2f3"
C_FLUV  = "#d9ead3"
C_PLUV  = "#fce5cd"
C_COMP  = "#e3ebf3"
C_OUT   = "#cfe7e6"
C_GATE  = "#f4d9c4"

TITLE_FS  = 7.4
BODY_FS   = 6.1
LINE      = 0.52
TITLE_GAP = 0.58
PAD       = 0.22

fig, ax = plt.subplots(figsize=(3.9, 6.1), dpi=300)
ax.set_xlim(0, 10)
ax.axis("off")


def box(cx, top, w, title, body_lines, fc, body_fs=BODY_FS):
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


GAP = 0.55
W = 9.4

b_in = box(5.0, 14.7, W, "Open-data inputs  (free, no registration)", [
    "Copernicus GLO-30 DEM · ERA5-Land",
    "UHSLC tides · GloFAS v4 discharge",
    "IPCC AR6 SLR · ESA WorldCover · OSM",
], C_IN)

b_force = box(5.0, b_in - GAP, W, "Forcing & conditioning", [
    "per-country IDF  (PUB · JPS · TMD · BMKG)",
    "GEV surge · AR6 SLR · zone subsidence",
], C_FORCE)

s_top = b_force - GAP
b_coast = box(1.80, s_top, 2.95, "Coastal",
              ["local-inertia", "shallow-water", "(bathtub fallback)"], C_COAST, body_fs=5.9)
box(5.00, s_top, 2.95, "Fluvial",
    ["main-stem HAND", "(GloFAS-reach", "trunk)"], C_FLUV, body_fs=5.9)
box(8.20, s_top, 2.95, "Pluvial",
    ["IDF-excess", "fill-and-spill", "(per-cell runoff)"], C_PLUV, body_fs=5.9)

b_comp = box(5.0, b_coast - GAP, W, "Per-pixel-maximum composite",
             ["severity: minor / moderate / major / severe"], C_COMP, body_fs=6.0)

b_out = box(5.0, b_comp - GAP, W, "30 m multi-hazard flood atlas", [
    "9 RP × SSP2-4.5 / SSP5-8.5 × 2050 / 2100",
    "one command per city",
], C_OUT)

b_gate = box(5.0, b_out - GAP, W, "Trust gate", [
    "model-blind hotspot location skill",
    "+ bathtub-bias characterisation",
], C_GATE, body_fs=6.0)

# arrows
arrow(5.0, b_in, 5.0, b_in - GAP)
for cx in (1.80, 5.0, 8.20):
    arrow(5.0, b_force, cx, s_top)
for cx in (1.80, 5.0, 8.20):
    arrow(cx, b_coast, 5.0, b_coast - GAP)
arrow(5.0, b_comp, 5.0, b_comp - GAP)
arrow(5.0, b_out, 5.0, b_out - GAP)

ax.set_ylim(b_gate - 0.3, 15.0)
fig.savefig(OUT, bbox_inches="tight", pad_inches=0.04)
print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")
