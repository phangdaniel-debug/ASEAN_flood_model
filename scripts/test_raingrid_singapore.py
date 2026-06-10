"""Standalone validation of the rain-on-grid pluvial model on Singapore.

Runs one RP, prints runtime / mass-balance / wet-area stats, and saves the
peak-depth array + a PNG for visual inspection.  Used to validate the model
on real terrain before wiring it into the pipeline.

Key correctness point: sea cells are kept FINITE (bed = 0 m) and placed in the
outlet mask so they act as free-drainage sinks.  If sea cells were left NaN
they would be treated as zero-flux walls and water would pile at the coast.
"""
import sys, time
from pathlib import Path

import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from model.flood_depth_model import load_dem
from model.pluvial_rain_model import run_rain_on_grid

EXCESS_BY_RP = {  # Singapore 2100 SSP5-8.5, 50 mm drain, after x1.28 CC (m)
    10: 0.015368, 25: 0.034787, 50: 0.049192, 100: 0.063491,
    200: 0.077738, 500: 0.096535, 1000: 0.110740,
}


def main(rp: int = 100, dem_file: str = "data/singapore/copernicus_dem_utm48n.tif",
         tag: str = "") -> None:
    dem, profile = load_dem(str(PROJECT_ROOT / dem_file))
    print(f"DEM: {dem_file}")
    with rasterio.open(PROJECT_ROOT / "data/singapore/sea_mask_utm48n.tif") as s:
        sm = s.read(1)
    with rasterio.open(PROJECT_ROOT / "data/singapore/river_mask_utm48n.tif") as s:
        rm = s.read(1)
    with rasterio.open(PROJECT_ROOT / "data/singapore/runoff_coeff_utm48n.tif") as s:
        rc = s.read(1).astype(float); rc[rc == s.nodata] = np.nan

    # Bed: keep sea cells FINITE at 0 m (MSL) so they are valid outlet sinks.
    z = dem.astype(np.float64).copy()
    z[sm == 0] = 0.0                       # sea -> MSL bed
    # genuine nodata (outside tile) stays NaN
    z[~np.isfinite(dem) & (sm != 0)] = np.nan

    outlet = (sm == 0) | (rm > 0)          # sea + open canal network are sinks

    rc_filled = np.where(np.isfinite(rc), rc, 0.4)
    excess = EXCESS_BY_RP[rp]
    net_rain = excess * rc_filled
    # rain only on land (not sea); zero it on sea so we don't inject over outlets
    net_rain = np.where(sm == 1, net_rain, 0.0)

    # Manning's n approx from runoff coeff (impervious->low n, veg->high n)
    n_arr = np.clip(0.11 - 0.08 * rc_filled, 0.03, 0.10)

    print(f"=== Singapore rain-on-grid RP{rp} ===")
    print(f"land cells: {int((sm==1).sum()):,}  outlets(sea+river): {int(outlet.sum()):,}")
    print(f"net_rain on land mm: {float(np.nanmin(net_rain[sm==1]))*1000:.1f} - "
          f"{float(net_rain[sm==1].max())*1000:.1f}")

    t0 = time.time()
    res = run_rain_on_grid(z, outlet, net_rain, n_arr,
                           storm_duration_s=3600.0, total_duration_s=5400.0,
                           dx=30.0, dy=30.0, dt_max=30.0,
                           progress_interval=300, verbose=True)
    elapsed = time.time() - t0

    peak = res["peak_depth"]
    # Report only on land (sea cells are forced 0 anyway)
    peak_land = np.where(sm == 1, peak, np.nan)
    for thr in (0.05, 0.15, 0.30):
        n = int(np.nansum(peak_land > thr))
        print(f"  wet>{int(thr*100):>2}cm: {n:>7,} cells = {n*900/1e6:5.1f} km2")
    print(f"  peak max: {np.nanmax(peak_land):.2f} m   "
          f"mean(wet>5cm): {np.nanmean(peak_land[peak_land>0.05]):.3f} m")
    print(f"  mass in: {res['mass_in_m3']/1e6:.2f} Mm3   "
          f"retained on land: {res['mass_end_m3']/1e6:.2f} Mm3 "
          f"({100*res['mass_end_m3']/res['mass_in_m3']:.0f}%)")
    print(f"  RUNTIME: {elapsed:.0f}s  ({res['n_steps']} steps, t={res['elapsed_s']/3600:.2f}h)")

    np.save(PROJECT_ROOT / f"outputs/_tmp_sg_raingrid_rp{rp}{tag}.npy", peak_land)

    # PNG — show hazard depths >15cm
    d = peak_land.copy(); d[d <= 0.15] = np.nan
    fig, ax = plt.subplots(figsize=(12, 8))
    norm = mcolors.Normalize(vmin=0.15, vmax=1.0)
    ax.imshow(d, cmap="Blues", norm=norm, origin="upper", interpolation="nearest")
    haz = int(np.nansum(peak_land > 0.15))
    ax.set_title(f"Singapore pluvial RP{rp} — RAIN-ON-GRID {tag} (50mm drain, 2100)\n"
                 f"{haz*900/1e6:.1f} km² > 15cm   max {np.nanmax(peak_land):.2f} m", fontsize=11)
    ax.axis("off")
    plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap="Blues"), ax=ax,
                 label="Peak ponding depth (m)", shrink=0.6)
    plt.tight_layout()
    out = PROJECT_ROOT / f"outputs/sg_raingrid_rp{rp}{tag}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"  saved {out}")


if __name__ == "__main__":
    rp = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    dem_file = sys.argv[2] if len(sys.argv) > 2 else "data/singapore/copernicus_dem_utm48n.tif"
    tag = sys.argv[3] if len(sys.argv) > 3 else ""
    main(rp, dem_file, tag)
