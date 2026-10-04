"""Render v2 Fig. 3 -- pipeline data-flow as a vertical flowchart for one IEEE column.

    open-data inputs -> forcing & conditioning -> three per-hazard solvers
    (coastal / fluvial / pluvial, incl. the KL/Jakarta canal-HAND union)
    -> per-pixel-max composite -> 30 m atlas -> trust gate.

Layout is computed in POINT units (1 y-unit == 1 pt) so box heights exactly fit their
text (fontsize x linespacing) with no dead room at the bottom -- the figure height is
derived from the stack, not fixed a priori. Pure matplotlib.

Run:  python scripts/render_v2_fig3_pipeline.py
Out:  docs/paper/figures/fig3_pipeline.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "docs" / "paper" / "figures" / "fig3_pipeline.png"

# Muted, single-hue (gray-blue) palette: three tint depths only, so the chart reads as
# one system. Hazard boxes share ONE fill (the titles differentiate them); the terminal
# trust gate is the deepest tint.
EDGE = "#4a4a4a"
C_TINT1 = "#f3f5f7"   # inputs
C_TINT2 = "#e8edf1"   # forcing / composite
C_TINT3 = "#dde5eb"   # hazard solvers / atlas
C_GATE  = "#d2dce4"   # trust gate (terminal emphasis)

TITLE_FS  = 7.4
BODY_FS   = 6.1
LSPACE    = 1.33
LINE      = BODY_FS * LSPACE       # pt per body line -- exact
TITLE_OFF = 5.0                    # pt from box top to title top
TITLE_GAP = 16.5                   # pt from box top to body-text top
PAD       = 5.0                    # pt below the last body line
GAP       = 17.0                   # pt between stacked boxes
W         = 9.4                    # box width (x-units; x-scale is independent)

def h_of(n_lines):
    return TITLE_GAP + LINE * n_lines + PAD

# ---- box contents ------------------------------------------------------------------
IN_LINES    = ["Copernicus GLO-30 DEM · ERA5-Land",
               "UHSLC tides · GloFAS v4 discharge",
               "IPCC AR6 SLR · ESA WorldCover · OSM"]
FORCE_LINES = ["per-country IDF  (PUB · JPS · TMD · BMKG)",
               "GEV surge · AR6 SLR · zone subsidence"]
COAST_LINES = ["local-inertia", "shallow-water", "+ sea defences"]
FLUV_LINES  = ["main-stem HAND,", "GloFAS stage", "(Manning rating)"]
PLUV_LINES  = ["IDF-excess,", "regime-matched:", "fill-spill / handfill",
               "∪ canal-HAND", "(KL, Jakarta)"]
COMP_LINES  = ["severity: minor / moderate / major / severe"]
OUT_LINES   = ["RP 10 / 100 / 1000 × (present +",
               "SSP2-4.5 / SSP5-8.5 × 2050 / 2100)",
               "one command per city"]
GATE_LINES  = ["model-blind hotspot location skill",
               "+ bathtub-bias characterisation"]

# ---- pure-arithmetic layout pass (point units, top at 0 going down) ----------------
tops = {}
y = 0.0
for key, lines in (("in", IN_LINES), ("force", FORCE_LINES),
                   ("haz", PLUV_LINES),          # hazard row height = tallest (pluvial)
                   ("comp", COMP_LINES), ("out", OUT_LINES), ("gate", GATE_LINES)):
    tops[key] = y
    y -= h_of(len(lines))
    y -= GAP
bottom = y + GAP                                  # remove trailing gap
MARGIN = 6.0
span = MARGIN + abs(bottom) + MARGIN

fig, ax = plt.subplots(figsize=(3.9, span / 72.0), dpi=300)
ax.set_xlim(0, 10)
ax.set_ylim(bottom - MARGIN, MARGIN)
ax.axis("off")

def box(cx, top, w, title, body_lines, fc):
    h = h_of(len(body_lines))
    # x-units are ~28 pt wide while y-units are 1 pt, so corner rounding must be made
    # isotropic via mutation_aspect (else corners smear across the whole box edge).
    ax.add_patch(FancyBboxPatch(
        (cx - w / 2, top - h), w, h,
        boxstyle="round,pad=0,rounding_size=0.12", mutation_aspect=28.0,
        linewidth=0.8, edgecolor=EDGE, facecolor=fc, zorder=2))
    ax.text(cx, top - TITLE_OFF, title, ha="center", va="top",
            fontsize=TITLE_FS, fontweight="bold", zorder=3)
    ax.text(cx, top - TITLE_GAP, "\n".join(body_lines), ha="center", va="top",
            fontsize=BODY_FS, zorder=3, linespacing=LSPACE)
    return top - h

def arrow(x0, y0, x1, y1):
    ax.add_patch(FancyArrowPatch(
        (x0, y0), (x1, y1),
        arrowstyle="-|>", mutation_scale=8, linewidth=0.8,
        color=EDGE, shrinkA=0, shrinkB=0, zorder=1))

b_in    = box(5.0, tops["in"], W, "Open-data inputs  (free, no registration)", IN_LINES, C_TINT1)
b_force = box(5.0, tops["force"], W, "Forcing & conditioning", FORCE_LINES, C_TINT2)

s_top   = tops["haz"]
b_coast = box(1.80, s_top, 2.95, "Coastal", COAST_LINES, C_TINT3)
b_fluv  = box(5.00, s_top, 2.95, "Fluvial", FLUV_LINES, C_TINT3)
b_pluv  = box(8.20, s_top, 2.95, "Pluvial", PLUV_LINES, C_TINT3)
s_bot   = min(b_coast, b_fluv, b_pluv)

b_comp  = box(5.0, tops["comp"], W, "Per-pixel-maximum composite", COMP_LINES, C_TINT2)
b_out   = box(5.0, tops["out"], W, "30 m multi-hazard flood atlas", OUT_LINES, C_TINT3)
b_gate  = box(5.0, tops["gate"], W, "Trust gate", GATE_LINES, C_GATE)

# arrows
arrow(5.0, b_in, 5.0, tops["force"])
for cx in (1.80, 5.0, 8.20):
    arrow(5.0, b_force, cx, s_top)
for cx, b in ((1.80, b_coast), (5.0, b_fluv), (8.20, b_pluv)):
    arrow(cx, b, 5.0, tops["comp"])
arrow(5.0, b_comp, 5.0, tops["out"])
arrow(5.0, b_out, 5.0, tops["gate"])

fig.savefig(OUT, bbox_inches="tight", pad_inches=0.04)
print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")
