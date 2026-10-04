"""Render the SAFE/v5 bathtub-bias figure: bathtub vs local-inertia RP100
coastal extent (km^2) on the bare-earth terrain, present-day, log scale.

Solver-vs-solver on identical terrain and water levels (matched pairs):
    Bangkok   bathtub 3,621 -> inertial 698 km^2   (5.2x ; gradient/defence-rich)
    Jakarta   bathtub   173 -> inertial 144 km^2   (1.2x ; uniformly subsided)

The over-prediction is regime-dependent: largest where terrain gradient and
sub-pixel defences matter, near-harmless on a uniformly-connected delta.

Run:  python scripts/render_safe_fig_bathtub.py
Out:  docs/paper/figures/fig4_bathtub_bias.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "docs" / "paper" / "figures" / "fig4_bathtub_bias.png"

CITIES = ["Bangkok", "Jakarta"]
BATHTUB = [3621.3, 173.47]   # connectivity bathtub, RP100 coastal extent (km^2)
INERTIAL = [698.0, 143.61]   # local-inertia, same terrain + water level (km^2)
RATIO = [b / i for b, i in zip(BATHTUB, INERTIAL)]

C_BATH = "#9aa0a6"   # grey (default open-screening solver)
C_INERT = "#1b7f7a"  # teal (this work)

x = np.arange(len(CITIES))
w = 0.34

fig, ax = plt.subplots(figsize=(3.45, 2.55), dpi=300)

b1 = ax.bar(x - w / 2, BATHTUB, w, label="bathtub (default)",
            color=C_BATH, edgecolor="#333", linewidth=0.4)
b2 = ax.bar(x + w / 2, INERTIAL, w, label="local-inertia (this work)",
            color=C_INERT, edgecolor="#333", linewidth=0.4)

ax.set_yscale("log")
ax.set_ylim(80, 8000)
ax.set_ylabel("RP100 coastal extent (km$^2$, present-day)", fontsize=7.0)
ax.set_xticks(x)
ax.set_xticklabels(CITIES, fontsize=8.0)
ax.tick_params(axis="y", labelsize=6.5)
ax.set_axisbelow(True)
ax.yaxis.grid(True, which="both", color="#ececec", lw=0.5)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)


def label(bars, vals):
    for rect, v in zip(bars, vals):
        ax.annotate(f"{v:,.0f}", (rect.get_x() + rect.get_width() / 2, rect.get_height()),
                    textcoords="offset points", xytext=(0, 1.6),
                    ha="center", va="bottom", fontsize=6.2)


label(b1, BATHTUB)
label(b2, INERTIAL)

# regime-dependent over-prediction factor, just above each city's tall bar
for xi, bt, r in zip(x, BATHTUB, RATIO):
    ax.annotate(f"{r:.1f}$\\times$ over-pred.",
                xy=(xi, bt * 1.32), ha="center", va="bottom",
                fontsize=6.6, color=C_INERT, fontweight="bold")

ax.legend(fontsize=6.4, loc="upper right", frameon=True, framealpha=0.95,
          borderpad=0.4, handlelength=1.2)

fig.tight_layout(pad=0.3)
fig.savefig(OUT, bbox_inches="tight", pad_inches=0.03)
print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")
