"""Render hazard maps for the §11 visual-QA gate (read-only). Saves PNGs."""
import glob
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import transform as rio_transform
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from scripts.hotspot_scoring import load_hotspots

ROOT = Path(__file__).resolve().parents[1]
SCN = "ssp585_2100"
OUT = ROOT / "outputs" / "_visual_gate"
OUT.mkdir(parents=True, exist_ok=True)
hot = load_hotspots(ROOT / "data/singapore/flood_obs/hotspots/sg_pluvial_hotspots.csv")


def load(haz, rp):
    fs = glob.glob(str(ROOT / f"outputs/singapore_{SCN}/{haz}/rp_{rp}/{haz}_depth_*.tif"))
    with rasterio.open(fs[0]) as ds:
        a = ds.read(1).astype(float)
        if ds.nodata is not None:
            a = np.where(a == ds.nodata, np.nan, a)
        tr, crs = ds.transform, ds.crs
    return a, tr, crs


def px(tr, crs, lon, lat):
    xs, ys = rio_transform("EPSG:4326", crs, [lon], [lat])
    c, r = ~tr * (xs[0], ys[0])
    return c, r


def panel(ax, a, title, tr=None, crs=None, pts=False):
    m = np.ma.masked_where(~np.isfinite(a) | (a < 0.05), a)
    im = ax.imshow(m, cmap="viridis", norm=LogNorm(vmin=0.05, vmax=3.0), interpolation="nearest")
    ax.set_title(title, fontsize=9)
    ax.set_xticks([]); ax.set_yticks([])
    if pts and tr is not None:
        for h in hot:
            c, r = px(tr, crs, h.lon, h.lat)
            ax.plot(c, r, "o", ms=4, mec="k", mew=0.5,
                    mfc=("red" if h.cls == "flood" else "cyan"))
    return im


fig, axs = plt.subplots(2, 3, figsize=(15, 10))
a10, tr, crs = load("pluvial", 10)
a100, _, _ = load("pluvial", 100)
a1000, _, _ = load("pluvial", 1000)
ac, _, _ = load("coastal", 100)
af, _, _ = load("fluvial", 100)
im = panel(axs[0, 0], a10, "Pluvial RP10")
panel(axs[0, 1], a100, "Pluvial RP100")
panel(axs[0, 2], a1000, "Pluvial RP1000 (capped 3.0 m)")
panel(axs[1, 0], ac, "Coastal RP100 (bathtub)")
panel(axs[1, 1], af, "Fluvial RP100 (HAND, channel-masked)")
panel(axs[1, 2], a100, "Pluvial RP100 + hotspots (red=flood, cyan=dry)", tr, crs, pts=True)
fig.colorbar(im, ax=axs, fraction=0.02, pad=0.02, label="depth (m, log)")
fig.suptitle(f"§11 visual-QA gate — Singapore {SCN}", fontsize=12)
fig.savefig(OUT / "visual_gate_overview.png", dpi=85, bbox_inches="tight")
print("wrote", OUT / "visual_gate_overview.png")

# Zoom on central/hotspot region for speckle/spike inspection
fig2, ax2 = plt.subplots(figsize=(10, 7))
im2 = panel(ax2, a100, "Pluvial RP100 + hotspots (full domain)", tr, crs, pts=True)
fig2.colorbar(im2, ax=ax2, fraction=0.03, label="depth (m, log)")
fig2.savefig(OUT / "pluvial_rp100_hotspots.png", dpi=110, bbox_inches="tight")
print("wrote", OUT / "pluvial_rp100_hotspots.png")
