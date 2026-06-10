"""KL present-day RP-progression: combined pluvial∨fluvial depth at RP2/10/100/1000."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio
from scripts.combine_hazard_depth import combine_depth_rasters
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

YR, SCN = 2020, "SSP5-8.5"
RPS = [2, 10, 100, 1000]
base = f"outputs/kuala_lumpur_ssp585_{YR}"
cmap = LinearSegmentedColormap.from_list("flood", ["#c6e2ff","#3b82f6","#1e3a8a","#4c1d95"])

fig, axes = plt.subplots(1, 4, figsize=(22, 7), constrained_layout=True)
for ax, rp in zip(axes, RPS):
    pl = f"{base}/pluvial/rp_{rp}/pluvial_depth_{SCN}_{YR}_rp{rp}.tif"
    fl = f"{base}/fluvial/rp_{rp}/fluvial_depth_{SCN}_{YR}_rp{rp}.tif"
    out = f"{base}/_validation/combined_rp{rp}.tif"
    Path(f"{base}/_validation").mkdir(parents=True, exist_ok=True)
    combine_depth_rasters([pl, fl], Path(out))
    with rasterio.open(out) as d:
        a = d.read(1).astype(float); a = np.where(np.isfinite(a), a, np.nan)
        b = d.bounds
    w = a[np.isfinite(a) & (a > 0.1)]
    ext = w.size*900/1e6; mean = w.mean() if w.size else 0
    im = ax.imshow(np.where(a > 0.1, a, np.nan), extent=(b.left,b.right,b.bottom,b.top),
                   cmap=cmap, vmin=0, vmax=3.0, interpolation="nearest")
    ax.set_title(f"RP{rp}  ·  {ext:.0f} km²  ·  mean {mean:.2f} m", fontsize=13)
    ax.set_xticks([]); ax.set_yticks([])
cb = fig.colorbar(im, ax=axes, shrink=0.7, location="bottom", pad=0.02, aspect=50)
cb.set_label("Flood depth (m), capped at 3.0 m", fontsize=11)
fig.suptitle("Kuala Lumpur present-day (2020) combined flood hazard — return-period progression",
             fontsize=15, weight="bold")
out = Path(f"{base}/kl_rp_progression_2020.png")
fig.savefig(out, dpi=120, bbox_inches="tight"); print("wrote", out)
