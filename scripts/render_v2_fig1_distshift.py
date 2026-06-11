"""Render v2 Fig. 1 -- the climate "math" for screening (distribution shift).

Two Gaussian hazard distributions: "today" (N(0,1)) and "+1 sigma warmer"
(N(1,1)). A fixed extreme threshold at +2 sigma (relative to today's mean) is
exceeded with probability 2.3% today and 15.9% after a one-sigma mean shift --
a ~7x jump that turns a 44-year event into a ~6-year event. The figure is a
schematic of the mechanism (faster-than-mean growth of tail frequency), NOT a
result derived from any specific IDF curve.

Math check (standard normal):
    P(X>2 | mu=0) = 0.0228  -> ~1/0.0228 = 44 yr
    P(X>2 | mu=1) = P(Z>1)  = 0.1587 -> ~1/0.1587 = 6.3 yr ; ratio 6.9x

Run:  python scripts/render_v2_fig1_distshift.py
Out:  docs/paper/v2/figures/fig1_distshift.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "docs" / "paper" / "v2" / "figures" / "fig1_distshift.png"

C_TODAY = "#9aa0a6"   # grey
C_WARM = "#e0671b"    # orange
THRESH = 2.0          # +2 sigma relative to today's mean


def gauss(x, mu, sd=1.0):
    return np.exp(-0.5 * ((x - mu) / sd) ** 2) / (sd * np.sqrt(2 * np.pi))


x = np.linspace(-4.2, 6.2, 1000)
today = gauss(x, 0.0)
warm = gauss(x, 1.0)

fig, ax = plt.subplots(figsize=(3.45, 2.25), dpi=300)

# curves
ax.plot(x, today, color=C_TODAY, lw=1.4, zorder=3)
ax.plot(x, warm, color=C_WARM, lw=1.6, zorder=4)

# shaded tails beyond the threshold
xt = x[x >= THRESH]
ax.fill_between(xt, gauss(xt, 0.0), color=C_TODAY, alpha=0.45, lw=0, zorder=2)
ax.fill_between(xt, gauss(xt, 1.0), color=C_WARM, alpha=0.40, lw=0, zorder=2)

# threshold line
ax.axvline(THRESH, color="#333", lw=1.0, ls="--", zorder=5)
ax.text(THRESH + 0.08, 0.40, "extreme\nthreshold", fontsize=6.6, va="top",
        ha="left", color="#333", linespacing=1.0)

# curve labels (placed on the outer shoulders so they don't collide)
ax.text(-1.55, 0.305, "today", fontsize=7.2, color=C_TODAY, ha="center",
        fontweight="bold")
ax.text(2.35, 0.305, "+1$\\sigma$ warmer", fontsize=7.2, color=C_WARM,
        ha="center", fontweight="bold")

# annotations on the tail
ax.annotate("2.3% $\\rightarrow$ 15.9%\n($\\approx$7$\\times$ more frequent)\n"
            "44-yr $\\rightarrow$ 6-yr event",
            xy=(2.65, 0.045), xytext=(3.05, 0.20),
            fontsize=6.5, color="#333", ha="left", va="center", linespacing=1.25,
            arrowprops=dict(arrowstyle="->", color="#666", lw=0.7))

ax.set_xlabel("hazard magnitude (e.g. design rainfall)", fontsize=7.2)
ax.set_xlim(-4.2, 6.2)
ax.set_ylim(0, 0.46)
ax.set_yticks([])
ax.set_xticks([])
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color("#888")

fig.tight_layout(pad=0.3)
fig.savefig(OUT, bbox_inches="tight", pad_inches=0.03)
print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")
