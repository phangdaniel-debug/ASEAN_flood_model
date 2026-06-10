"""Render Figure 2 for the IEEE R10-HTC paper: Bangkok RP100 combined-hazard flood depth.

Per-pixel-max of the three committed Bangkok RP100 depth rasters (SSP5-8.5/2100... note:
the validation baseline is the 2020 hazard set in outputs/bangkok_ssp585_2020/, which is what
exists locally; the figure illustrates the screening flood envelope). Single-panel, column-width,
300 dpi PNG -> docs/paper/figures/ieee_fig2_bangkok_rp100.png.
"""
import sys
from pathlib import Path

import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "bangkok_ssp585_2020"
HAZ = ["coastal", "fluvial", "pluvial"]
OUT = ROOT / "docs" / "paper" / "figures" / "ieee_fig2_bangkok_rp100.png"


def load_depth(hz):
    p = BASE / hz / "rp_100" / f"{hz}_depth_SSP5-8.5_2020_rp100.tif"
    with rasterio.open(p) as ds:
        a = ds.read(1).astype("float32")
        nod = ds.nodata
        bounds = ds.bounds
    a = np.where(np.isfinite(a), a, np.nan)
    if nod is not None:
        a = np.where(a == nod, np.nan, a)
    return a, bounds


def main():
    layers, bounds = [], None
    for hz in HAZ:
        a, b = load_depth(hz)
        layers.append(a)
        bounds = b
    # per-pixel max across hazards (NaN-safe)
    stack = np.stack(layers, axis=0)
    combined = np.nanmax(stack, axis=0)
    combined = np.where(combined > 0.1, combined, np.nan)  # show only flooded (>0.1 m)

    wet = np.isfinite(combined)
    area_km2 = wet.sum() * 900 / 1e6
    print(f"combined flooded (>0.1 m): {area_km2:.0f} km2; "
          f"depth p50={np.nanpercentile(combined,50):.2f} p95={np.nanpercentile(combined,95):.2f} m")

    # severity-style discrete colourmap (minor/moderate/major/severe), colour-blind-safe blues
    bins = [0.1, 0.15, 0.5, 1.0, np.inf]
    colors = ["#bdd7e7", "#6baed6", "#3182bd", "#08519c"]
    cmap = ListedColormap(colors)
    norm = BoundaryNorm([0.1, 0.15, 0.5, 1.0, 3.0], cmap.N)

    extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]
    fig, ax = plt.subplots(figsize=(3.4, 3.6), dpi=300)  # column width
    ax.set_facecolor("#f2f2f2")
    im = ax.imshow(combined, extent=extent, origin="upper", cmap=cmap, norm=norm,
                   interpolation="nearest")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("Bangkok — RP100 combined-hazard flood depth", fontsize=8, pad=4)

    # scale bar (10 km) in projected metres
    x0 = bounds.left + 0.06 * (bounds.right - bounds.left)
    y0 = bounds.bottom + 0.06 * (bounds.top - bounds.bottom)
    ax.plot([x0, x0 + 10000], [y0, y0], color="k", lw=2)
    ax.text(x0 + 5000, y0 + 0.012 * (bounds.top - bounds.bottom), "10 km",
            ha="center", va="bottom", fontsize=6)
    ax.annotate("N", xy=(0.94, 0.90), xytext=(0.94, 0.80), xycoords="axes fraction",
                ha="center", fontsize=8, arrowprops=dict(arrowstyle="-|>", color="k"))

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02, ticks=[0.125, 0.32, 0.72, 1.5])
    cbar.ax.set_yticklabels(["minor", "moderate", "major", "severe"], fontsize=6)
    cbar.set_label("flood depth class", fontsize=7)

    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300, bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
