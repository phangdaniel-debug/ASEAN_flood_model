"""Render v2 Fig. 2 -- asset life versus scenario uncertainty.

A port entering planning today is designed/built through the mid-2030s and then
operates for 50+ years, into the 2080s -- deep inside the widening SLR fan. The
three SSP trajectories (SSP1-1.9 / SSP2-4.5 / SSP5-8.5) diverge across that asset
life. Curves are SCHEMATIC accelerating (quadratic-ish) paths to illustrative
2085 endpoints; the figure communicates the asset-life-vs-uncertainty geometry,
not a precise projection. The ASEAN AR6 P50-by-2100 endpoints (+0.62 m SG,
+1.62 m BKK) are annotated as the policy-relevant span.

Run:  python scripts/render_v2_fig2_assetlife.py
Out:  docs/paper/v2/figures/fig2_assetlife.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "docs" / "paper" / "v2" / "figures" / "fig2_assetlife.png"

C_LOW = "#2c7fb8"     # SSP1-1.9
C_MID = "#41ab5d"     # SSP2-4.5
C_HIGH = "#e0671b"    # SSP5-8.5

YR0, YR1 = 2025, 2085
years = np.linspace(YR0, YR1, 200)
t = (years - YR0) / (YR1 - YR0)          # 0..1
accel = t ** 1.5                          # accelerating SLR

# illustrative 2085 endpoints (m, rel. 2025)
END = {"SSP1-1.9": 0.45, "SSP2-4.5": 0.78, "SSP5-8.5": 1.38}
low = END["SSP1-1.9"] * accel
mid = END["SSP2-4.5"] * accel
high = END["SSP5-8.5"] * accel

fig, ax = plt.subplots(figsize=(3.45, 2.45), dpi=300)

# uncertainty fan
ax.fill_between(years, low, high, color="#cfe3ef", alpha=0.7, lw=0, zorder=1)
ax.plot(years, high, color=C_HIGH, lw=1.6, zorder=3, label="SSP5-8.5")
ax.plot(years, mid, color=C_MID, lw=1.6, zorder=3, label="SSP2-4.5")
ax.plot(years, low, color=C_LOW, lw=1.6, zorder=3, label="SSP1-1.9")

# asset-life bar near the top
ybar = 1.64
ax.add_patch(plt.Rectangle((2030, ybar), 5, 0.07, color="#9aa0a6", zorder=4))
ax.add_patch(plt.Rectangle((2035, ybar), 50, 0.07, color="#2b3a42", zorder=4))
ax.text(2032.5, ybar - 0.10, "design\n+ build", fontsize=5.4, ha="center",
        va="center", color="#555", linespacing=0.95)
ax.text(2060, ybar + 0.105, "useful life (50+ yr)", fontsize=6.6, ha="center",
        va="center", color="#2b3a42", fontweight="bold")

# operating-window note
ax.text(2056, 0.27,
        "a port planned today\noperates into the\nwidening-uncertainty zone",
        fontsize=6.0, ha="center", va="center", color="#555", linespacing=1.15)

# ASEAN P50 endpoint annotation
ax.annotate("ASEAN P50 SLR by 2100:\n+0.62 m (SG)   +1.62 m (BKK)",
            xy=(2085, 1.38), xytext=(2049, 1.18),
            fontsize=6.0, ha="left", va="center", color="#333", linespacing=1.2)

ax.set_xlim(YR0, YR1)
ax.set_ylim(0, 1.85)
ax.set_ylabel("sea-level rise (m, rel. 2025)", fontsize=7.0)
ax.set_xticks([2030, 2045, 2060, 2075, 2085])
ax.tick_params(labelsize=6.5)
ax.legend(fontsize=6.2, loc="center left", bbox_to_anchor=(0.012, 0.46),
          frameon=False, handlelength=1.4, borderpad=0.2, labelspacing=0.3)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.spines["left"].set_color("#888")
ax.spines["bottom"].set_color("#888")
ax.yaxis.grid(True, color="#ececec", lw=0.5)
ax.set_axisbelow(True)

fig.tight_layout(pad=0.3)
fig.savefig(OUT, bbox_inches="tight", pad_inches=0.03)
print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")
