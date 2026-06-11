"""Render v2 Fig. 4 -- RP100 coastal bathtub-bias factor by city, with the
local-inertia correction (matches the reviewed-PDF Fig. 4).

Per city, two bars on a log axis: bathtub (default open-screening solver) vs
local-inertia (this work), as the RP100 coastal-extent ratio model/observed.

    Singapore  bathtub 25x  -> inertial 18x   (near-zero documented baseline)
    Bangkok    bathtub 12.5x -> inertial 1.0x  (3,546 -> 283 km^2 ; headline)
    Jakarta    bathtub 1.7x  -> inertial 1.2x

A 1x reference line marks perfect agreement. The 1.7-25x range quoted in the
text is Jakarta (min) to Singapore (max).

Run:  python scripts/render_v2_fig4_bathtub_bias.py
Out:  docs/paper/v2/figures/fig4_bathtub_bias.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "docs" / "paper" / "v2" / "figures" / "fig4_bathtub_bias.png"

CITIES = ["Singapore", "Bangkok", "Jakarta"]
BATHTUB = [25.0, 12.5, 1.7]
INERTIAL = [18.0, 1.0, 1.2]

C_BATH = "#9aa0a6"   # grey (default)
C_INERT = "#1b7f7a"  # teal (this work)

x = np.arange(len(CITIES))
w = 0.34

fig, ax = plt.subplots(figsize=(3.45, 2.55), dpi=300)

b1 = ax.bar(x - w / 2, BATHTUB, w, label="bathtub (default)",
            color=C_BATH, edgecolor="#333", linewidth=0.4)
b2 = ax.bar(x + w / 2, INERTIAL, w, label="local-inertia (this work)",
            color=C_INERT, edgecolor="#333", linewidth=0.4)

ax.axhline(1.0, color="#555", lw=0.9, ls="--", zorder=0)
ax.text(-0.46, 1.04, "1$\\times$ ideal", fontsize=6.2, color="#555",
        ha="left", va="bottom")

ax.set_yscale("log")
ax.set_ylim(0.7, 40)
ax.set_ylabel("RP100 coastal bias (model/observed)", fontsize=7.0)
ax.set_xticks(x)
ax.set_xticklabels(CITIES, fontsize=8.0)
ax.tick_params(axis="y", labelsize=6.5)
ax.set_axisbelow(True)
ax.yaxis.grid(True, which="both", color="#ececec", lw=0.5)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)


def label(bars, vals):
    for rect, v in zip(bars, vals):
        txt = f"{v:.0f}$\\times$" if v == round(v) else f"{v:.1f}$\\times$"
        ax.annotate(txt, (rect.get_x() + rect.get_width() / 2, rect.get_height()),
                    textcoords="offset points", xytext=(0, 1.5),
                    ha="center", va="bottom", fontsize=6.2)


label(b1, BATHTUB)
label(b2, INERTIAL)

# headline annotation on Bangkok
ax.annotate("Bangkok: 3,546 $\\rightarrow$ 283 km$^2$",
            xy=(1 + w / 2, 1.0), xytext=(0.62, 5.0),
            fontsize=6.2, color=C_INERT, ha="left", va="bottom",
            arrowprops=dict(arrowstyle="->", color=C_INERT, lw=0.8))

ax.legend(fontsize=6.4, loc="upper right", frameon=True, framealpha=0.9,
          borderpad=0.4, handlelength=1.2)

fig.tight_layout(pad=0.3)
fig.savefig(OUT, bbox_inches="tight", pad_inches=0.03)
print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")
