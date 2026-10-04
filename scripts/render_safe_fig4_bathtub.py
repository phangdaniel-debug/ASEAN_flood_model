"""Render SAFE Fig. 4 -- bathtub-vs-inertial RP100 coastal extent, full model domain.

Per city, two bars on a log axis: the connectivity bathtub (default open-screening
solver) vs the local-inertia solver (this work), as the RP100 coastal flooded extent
(km^2) over the full model domain at SSP5-8.5/2100. The two bars differ ONLY in the
solver: both are counted at depth >= 0.10 m (the paper's reporting convention) and both
carry the SAME defence scenario -- Bangkok behind its pumped polder, Jakarta undefended.
The inertial bars are exactly the coastal extents reported in the atlas extent table.
The over-prediction factor (bathtub/inertial) is labelled per city.

    Bangkok  853 -> 4,201 km^2  (4.9x; both behind the design-height dike + pumped polder)
    Jakarta  229 ->   278 km^2  (1.2x; both undefended subsided coast)

Consistency note (2026-07-21): a prior version paired a NON-polder, depth>0 bathtub
numerator (4,432) against the polder, depth>=0.10 inertial denominator (853) -- two
mismatches (defence arm + depth threshold) that inflated the ratio to 5.2x and
contradicted the paper's own mitigation-delta paragraph, which already used the
polder/>=0.10 bathtub value 4,201. Both bars are now measured on the identical basis.
Bathtub source: outputs/_bathtub_check/bkk2100_src_polder (Bangkok, polder),
outputs/_bathtub_check/jakarta_bathtub_2100 (Jakarta), depth>=0.10 m.

Run:  python scripts/render_safe_fig4_bathtub.py
Out:  docs/paper/figures/fig4_bathtub_bias.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "docs" / "paper" / "figures" / "fig4_bathtub_bias.png"

CITIES = ["Bangkok", "Jakarta"]
INERTIAL = [853.0, 229.0]    # this work (local-inertia); = atlas extent table (>=0.10 m)
BATHTUB = [4201.0, 278.0]    # connectivity, SAME defence scenario + >=0.10 m as inertial
FACTOR = [b / i for b, i in zip(BATHTUB, INERTIAL)]

C_INERT = "#1b7f7a"  # teal (this work)
C_BATH = "#9aa0a6"   # grey (default)

x = np.arange(len(CITIES))
w = 0.34

fig, ax = plt.subplots(figsize=(3.45, 2.55), dpi=300)

b1 = ax.bar(x - w / 2, BATHTUB, w, label="connectivity bathtub (default)",
            color=C_BATH, edgecolor="#333", linewidth=0.4)
b2 = ax.bar(x + w / 2, INERTIAL, w, label="local-inertia (this work)",
            color=C_INERT, edgecolor="#333", linewidth=0.4)

ax.set_yscale("log")
ax.set_ylim(100, 12000)
ax.set_ylabel("RP100 coastal extent, full domain (km$^2$)", fontsize=7.0)
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
                    textcoords="offset points", xytext=(0, 1.5),
                    ha="center", va="bottom", fontsize=6.2)


label(b1, BATHTUB)
label(b2, INERTIAL)

# over-prediction factor per city, just above that city's taller (bathtub) bar
for xi, f, top in zip(x, FACTOR, BATHTUB):
    ax.annotate(f"{f:.1f}$\\times$", xy=(xi, top), xytext=(xi, top * 1.55),
                ha="center", va="bottom", fontsize=7.6, fontweight="bold",
                color=C_INERT)

ax.set_title("Bathtub over-prediction (SSP5-8.5 / 2100)", fontsize=7.4, pad=14)
ax.legend(fontsize=6.2, loc="upper right", frameon=True, framealpha=0.9,
          borderpad=0.4, handlelength=1.2)

fig.tight_layout(pad=0.3)
fig.savefig(OUT, bbox_inches="tight", pad_inches=0.03)
print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")
