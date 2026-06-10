"""Recover present-day coastal flood extents from the scaled SSP5-8.5/2100 rasters.

For a coastal flood, the bathtub model gives::

    scaled_depth(i,j) = max(0, scaled_WL - DEM(i,j))

where scaled_WL = baseline_WL + AR6_SLR_delta.  Subtracting the SLR delta
from the depth raster therefore recovers the present-day (baseline) depth::

    present_depth(i,j) = max(0, scaled_depth(i,j) - SLR_delta)

This is exact for coastal (stage is spatially constant); it would be an
approximation for fluvial/pluvial whose WL varies spatially, so the
script restricts itself to coastal hazards.

Output: a single CSV ``outputs/_bias_vs_observed.csv`` plus a stdout
table comparing modelled present-day RP2 / RP100 coastal extents to
order-of-magnitude documented historical extents for each city.
"""
from __future__ import annotations

from pathlib import Path

import click
import numpy as np
import pandas as pd
import rasterio

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEPTH_THRESHOLD_M = 0.10

# Documented historical RP2 / RP100 coastal flooded area (km2).
# Order-of-magnitude estimates from published sources where available;
# rough engineering judgement otherwise (always cite specific sources
# in the eventual paper).
OBSERVED_KM2 = {
    "singapore":    {2:   0.5, 100:   2.0,
                     "src": ("PUB 2015 Coastal Adaptation Study — Marina Barrage + "
                             "East Coast bund near-eliminate RP2 coastal flood at present-day")},
    "kuala_lumpur": {2:   0.0, 100:   0.5,
                     "src": "Inland city; documented coastal flooding only at Klang river mouth (Port Klang)"},
    "bangkok":      {2:  30.0, 100: 200.0,
                     "src": ("BMA / RID 2021 reports of annual king-tide flooding 20-50 km2 "
                             "(Samut Prakan / Bang Khun Thian / Phra Pradaeng south); "
                             "RP100 typhoon-surge ~200 km2 documented by Trinh 2017")},
    "jakarta":      {2:  15.0, 100:  80.0,
                     "src": ("North Jakarta polder annual rob events 5-20 km2 (Brinkman 2013; "
                             "BAPPENAS reports); RP100 ~80 km2 per NCICD master plan 2014")},
    "manila":       {2:   5.0, 100: 100.0,
                     "src": ("Navotas/Malabon/Las Piñas annual king-tide ~5-10 km2 documented "
                             "by Lagmay et al. 2017; RP100 = Ondoy-class typhoon surge ~100 km2 "
                             "for purely coastal component")},
    "hcmc":         {2:  50.0, 100: 250.0,
                     "src": ("SIWRR / DPSI HCMC reports of annual peak-tide flooding 30-70 km2 "
                             "in D7/D8/Nha Be/Binh Chanh-S; RP100 ~250 km2 per Trinh 2017")},
}

CITIES_TO_REPORT = ["singapore", "kuala_lumpur", "bangkok", "jakarta", "manila", "hcmc"]


def _scaled_depth_path(slug: str, rp: int) -> Path:
    return (PROJECT_ROOT / "outputs" / f"{slug}_ssp585_2100" /
            "coastal" / f"rp_{rp}" / f"coastal_depth_SSP5-8.5_2100_rp{rp}.tif")


def _slr_delta(slug: str) -> float:
    p = PROJECT_ROOT / "data" / slug / "hazard_levels_ssp585_2100.csv"
    df = pd.read_csv(p)
    rows = df[df.hazard_type == "coastal"]
    return float(rows.iloc[0]["coastal_delta_m"])


def _area_below_thr(depth: np.ndarray, thr: float, pixel_m2: float) -> float:
    return int((depth > thr).sum()) * pixel_m2 / 1e6


@click.command()
@click.option("--threshold", default=DEPTH_THRESHOLD_M, show_default=True,
              help="Depth threshold (m) for counting a pixel as flooded.")
def cli(threshold: float) -> None:
    rows: list[dict] = []
    for slug in CITIES_TO_REPORT:
        slr = _slr_delta(slug)
        out = {"city": slug, "slr_delta_m": slr}
        for rp in (2, 100):
            p = _scaled_depth_path(slug, rp)
            if not p.exists():
                click.echo(f"[skip] {slug} RP{rp}: {p}", err=True)
                continue
            with rasterio.open(p) as ds:
                scaled_depth = ds.read(1).astype(np.float32)
                px_m2 = abs(ds.res[0] * ds.res[1])
            scaled_area = _area_below_thr(scaled_depth, threshold, px_m2)
            present_depth = np.maximum(0.0, scaled_depth - slr)
            present_area = _area_below_thr(present_depth, threshold, px_m2)
            obs = OBSERVED_KM2[slug][rp]
            bias = (present_area / obs) if obs > 0 else float("inf")
            out[f"rp{rp}_scaled_km2"] = round(scaled_area, 1)
            out[f"rp{rp}_present_km2"] = round(present_area, 1)
            out[f"rp{rp}_observed_km2"] = obs
            out[f"rp{rp}_bias_factor"] = round(bias, 1) if obs > 0 else None
        rows.append(out)

    df = pd.DataFrame(rows)
    out_csv = PROJECT_ROOT / "outputs" / "_bias_vs_observed.csv"
    df.to_csv(out_csv, index=False)

    click.echo("\nPresent-day coastal flood extents (recovered by subtracting AR6 SLR delta):\n")
    fmt = "{:<14}{:>8}{:>12}{:>12}{:>12}{:>8}"
    click.echo(fmt.format("city", "SLR_d", "scaled_km2", "present_km2", "obs_km2", "bias"))
    click.echo("-" * 66)
    for rp in (2, 100):
        click.echo(f"\nRP{rp}:")
        for r in rows:
            click.echo(fmt.format(
                r["city"],
                f"{r['slr_delta_m']:.2f}",
                str(r[f"rp{rp}_scaled_km2"]),
                str(r[f"rp{rp}_present_km2"]),
                str(r[f"rp{rp}_observed_km2"]),
                str(r[f"rp{rp}_bias_factor"]),
            ))
    click.echo(f"\nWrote {out_csv}")


if __name__ == "__main__":
    cli()
