"""
Sanity-check post-regen flood depth rasters.

Usage:
    python scripts/_check_regen.py <city_slug>
"""
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]

SEVERITY_THRESHOLD_M = 0.15  # match pipeline default


def summarize(city: str, scenario: str = "SSP5-8.5", horizon: int = 2100) -> None:
    out = ROOT / "outputs" / f"{city}_ssp{scenario.replace('SSP', '').replace('-', '').replace('.', '')}_{horizon}"
    if not out.exists():
        # fall back to ssp585_2100 naming
        out = ROOT / "outputs" / f"{city}_ssp585_{horizon}"
    if not out.exists():
        print(f"  [skip] no output dir for {city}")
        return

    print(f"\n=== {city} ({out.name}) ===")
    print(f"  {'Hazard':<8} {'RP':>5}  {'Area>0.15m (km2)':>18}  {'Mean (m)':>10}  {'Max (m)':>10}")
    print(f"  {'-'*8} {'-'*5}  {'-'*18}  {'-'*10}  {'-'*10}")
    for haz in ["coastal", "fluvial", "pluvial"]:
        for rp in [2, 10, 100, 1000]:
            p = out / haz / f"rp_{rp}" / f"{haz}_depth_{scenario}_{horizon}_rp{rp}.tif"
            if not p.exists():
                continue
            try:
                with rasterio.open(p) as src:
                    d = src.read(1, masked=True)
                    cell_area_km2 = abs(src.transform[0] * src.transform[4]) / 1e6
                    flooded_mask = (d > SEVERITY_THRESHOLD_M).filled(False)
                    n_flooded = int(flooded_mask.sum())
                    area_km2 = n_flooded * cell_area_km2
                    if n_flooded > 0:
                        mean_m = float(d[flooded_mask].mean())
                        max_m = float(d.max())
                    else:
                        mean_m = max_m = 0.0
                    print(f"  {haz:<8} {rp:>5}  {area_km2:>18.1f}  {mean_m:>10.2f}  {max_m:>10.2f}")
            except Exception as e:
                print(f"  {haz:<8} {rp:>5}  ERROR {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for city in sys.argv[1:]:
        summarize(city)
