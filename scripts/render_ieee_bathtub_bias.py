"""Render IEEE Fig. 3 — bathtub-bias factor at RP2 and RP100 by city, with the
local-inertia overlay for the three solver-compatible coastal cities.

Numbers are taken verbatim from the master draft (docs/paper/draft.md):
  Table 4 (bathtub-bias vs documented present-day extents):
      Singapore RP2 91x / RP100 25x ; Bangkok 66x / 12x ; Jakarta 7x / 1.7x
  Table 5 (bathtub -> local-inertia RP100 extent ratio):
      Bangkok 12.5x ; Singapore 1.4x ; Jakarta 1.4x

The inertial-corrected RP100 *residual* bias is the bathtub RP100 bias divided by
the inertial reduction ratio (inertial_extent/documented = bathtub_bias / ratio):
      Bangkok 12 / 12.5 = ~1.0x  (the headline)
      Singapore 25 / 1.4 = ~17.9x  (ratio fix is modest; SG documented extent is tiny)
      Jakarta 1.7 / 1.4 = ~1.2x

Log y-axis (values span ~1-91x); a 1x reference line marks perfect agreement.

Run:  python scripts/render_ieee_bathtub_bias.py
Out:  docs/paper/figures/ieee_fig3_bathtub_bias.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "docs" / "paper" / "figures" / "ieee_fig3_bathtub_bias.png"

CITIES = ["Singapore", "Bangkok", "Jakarta"]
RP2_BATHTUB = [91.0, 66.0, 7.0]
RP100_BATHTUB = [25.0, 12.0, 1.7]
INERTIAL_RATIO = [1.4, 12.5, 1.4]
RP100_INERTIAL = [b / r for b, r in zip(RP100_BATHTUB, INERTIAL_RATIO)]  # residual bias

C_RP2 = "#9ecae1"       # light blue
C_RP100 = "#3182bd"     # mid blue
C_INERT = "#e6550d"     # orange (the fix)

x = np.arange(len(CITIES))
w = 0.26

fig, ax = plt.subplots(figsize=(5.0, 3.1), dpi=300)

b1 = ax.bar(x - w, RP2_BATHTUB, w, label="RP2 (bathtub)", color=C_RP2, edgecolor="#333", linewidth=0.4)
b2 = ax.bar(x, RP100_BATHTUB, w, label="RP100 (bathtub)", color=C_RP100, edgecolor="#333", linewidth=0.4)
b3 = ax.bar(x + w, RP100_INERTIAL, w, label="RP100 (local-inertia)", color=C_INERT, edgecolor="#333", linewidth=0.4)

ax.axhline(1.0, color="#555", lw=0.9, ls="--", zorder=0)
ax.text(-0.45, 1.06, "1× (perfect)", fontsize=6.5, color="#555",
        ha="left", va="bottom")

ax.set_yscale("log")
ax.set_ylim(0.7, 140)
ax.set_ylabel("Bathtub-bias factor (model / documented)", fontsize=8)
ax.set_xticks(x)
ax.set_xticklabels(CITIES, fontsize=8.5)
ax.tick_params(axis="y", labelsize=7)
ax.set_axisbelow(True)
ax.yaxis.grid(True, which="both", color="#e0e0e0", lw=0.5)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)


def label(bars, vals):
    for rect, v in zip(bars, vals):
        txt = f"{v:.0f}×" if v >= 10 or v == round(v) else f"{v:.1f}×"
        ax.annotate(txt, (rect.get_x() + rect.get_width() / 2, rect.get_height()),
                    textcoords="offset points", xytext=(0, 1.5),
                    ha="center", va="bottom", fontsize=6.2)


label(b1, RP2_BATHTUB)
label(b2, RP100_BATHTUB)
label(b3, RP100_INERTIAL)

# headline annotation on Bangkok's inertial bar
bk = 1
ax.annotate("12.5× reduction\n→ ≈1×",
            xy=(bk + w, RP100_INERTIAL[bk]),
            xytext=(bk + w + 0.05, 4.2),
            fontsize=6.3, color=C_INERT, ha="left", va="bottom",
            arrowprops=dict(arrowstyle="->", color=C_INERT, lw=0.8))

ax.legend(fontsize=6.8, loc="upper right", frameon=True, framealpha=0.9,
          borderpad=0.4, handlelength=1.3)

fig.tight_layout(pad=0.4)
fig.savefig(OUT, bbox_inches="tight")
print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")
