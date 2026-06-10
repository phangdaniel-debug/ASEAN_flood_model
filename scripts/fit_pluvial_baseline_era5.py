"""
Derive pluvial post-drain excess rain depths from ERA5-Land hourly precipitation.

Rainfall source
---------------
ERA5-Land via Open-Meteo Archive API (free, no key, CC-BY 4.0).
  - URL : https://archive-api.open-meteo.com/v1/era5
  - Param: hourly=precipitation (mm per hour)
  - Resolution: ~9 km, 1950-present
  - Reference: Munoz-Sabater et al. (2021) Earth Syst. Sci. Data 13:4349.
                doi:10.5194/essd-13-4349-2021

ERA5-Land replaces the previous NASA POWER MERRA-2 source.  MERRA-2 had
a 5-30x wet bias in tropical SEA that required a per-city `precip_scale`
calibrated against national IDF curves -- a replicability blocker.
ERA5-Land's residual bias against gauge observations in SEA is small
(~1.0-1.5x) and within GEV sampling uncertainty, so no scaling is applied.

Method
------
1. Download hourly ERA5-Land precipitation for the city centroid.
2. Compute rolling N-hour accumulation (default 6 h -- typical urban
   convective storm duration).
3. Extract annual maxima of the rolling accumulation.
4. Fit a Generalised Extreme Value distribution via MLE (xi clamped).
5. Convert design rainfall depth to the post-drain rain depth:

       excess_mm      = max(0, GEV_quantile(rp) - drain_capacity_mm)
       excess_depth_m = excess_mm / 1000

   This raw value is written as `baseline_water_level_m`.  The downstream
   catchment-routed fill-spill model applies the per-cell runoff coefficient
   (from the WorldCover land-cover raster) and routes runoff by catchment.
   The `--runoff-coeff` and `--depression-area-fraction` CLI options are
   retained for back-compatibility but are no longer applied in this script.

6. Write pluvial rows to the hazard baseline CSV.

Caching
-------
Pass --cache-precip <path>.  If the file exists, the download is skipped.
Cache key is independent of MERRA-2 caches; do not reuse old MERRA-2
parquet files (different units, different source).
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.gev_utils import (
    rolling_accumulation,
    annual_maxima,
    fit_gev,
    gev_return_level,
    fetch_hourly_precip_era5land,
)

RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]

# Default coordinates -- Singapore centroid (overridden by --lat/--lon)
_DEFAULT_LAT = 1.2903
_DEFAULT_LON = 103.8519


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option("--output", "output_path", type=click.Path(path_type=Path),
              default=Path("data/singapore_hazard_baseline_template.csv"), show_default=True,
              help="Hazard baseline CSV -- pluvial rows will be replaced.")
@click.option("--lat", type=float, default=_DEFAULT_LAT, show_default=True)
@click.option("--lon", type=float, default=_DEFAULT_LON, show_default=True)
@click.option("--start-year", type=int, default=2001, show_default=True)
@click.option("--end-year", type=int, default=2024, show_default=True)
@click.option("--window-h", type=int, default=6, show_default=True,
              help=(
                  "Rolling accumulation window (h).  "
                  "6 h = primary-drain design storm (e.g., PUB 100 mm/6h primary drain). "
                  "1 h = secondary/tertiary-drain flash-flood mechanism (e.g., Singapore "
                  "PUB CoP secondary drain RP5 ~70 mm/1h; Orchard Rd / Bukit Timah events). "
                  "Note: ERA5-Land 1h peak intensity underestimates gauge observations by "
                  "~10% in Singapore; manual anchor via --drain-capacity-mm + direct template "
                  "edit is preferred over relying on the ERA5 fit at 1h resolution."
              ))
@click.option("--runoff-coeff", type=float, default=0.75, show_default=True,
              help="Retained for back-compatibility; no longer applied by this script. "
                   "The fill-spill model applies runoff coefficients per-cell from the "
                   "WorldCover raster at run time.")
@click.option("--drain-capacity-mm", type=float, default=100.0, show_default=True,
              help="Rainfall depth (mm) that the primary drainage network conveys "
                   "without surface ponding.  Calibrate to national RP design standard.")
@click.option("--depression-area-fraction", "depression_area_fraction",
              type=float, default=0.10, show_default=True,
              help=(
                  "Retained for back-compatibility; no longer applied in this script. "
                  "The downstream fill-spill model applies per-cell runoff coefficients "
                  "and routes by catchment.  Previously: "
                  "ponding_cap_m = (excess_mm/1000) * runoff_coeff / depression_area_fraction. "
                  "Default 0.10 (Singapore PUB)."
              ))
@click.option("--min-years", type=int, default=20, show_default=True)
@click.option("--xi-max", "xi_max", type=float, default=0.30, show_default=True,
              help="Maximum allowed GEV shape xi. 0.30 caps Frechet tails to prevent "
                   "unrealistic RP200-1000 ponding depths for tropical sub-daily precip.")
@click.option("--max-ponding-depth-m", "max_ponding_depth_m",
              type=float, default=3.0, show_default=True,
              help="Retained for back-compatibility; no longer applied by this script. "
                   "Previously clamped the output ponding depth; the fill-spill model "
                   "does not use this cap.")
@click.option("--cache-precip", "cache_path", type=click.Path(path_type=Path), default=None,
              help="Parquet cache file for ERA5-Land hourly precipitation.")
@click.option("--dry-run", is_flag=True, default=False)
def cli(
    output_path: Path,
    lat: float, lon: float,
    start_year: int, end_year: int,
    window_h: int,
    runoff_coeff: float,
    drain_capacity_mm: float,
    depression_area_fraction: float,
    min_years: int,
    xi_max: float,
    max_ponding_depth_m: float,
    cache_path: Path | None,
    dry_run: bool,
) -> None:
    if not (0 < depression_area_fraction <= 1.0):
        raise click.UsageError(
            f"--depression-area-fraction must be in (0, 1], got {depression_area_fraction}"
        )

    # 1. Load or download
    if cache_path is not None and Path(cache_path).exists():
        click.echo(f"Loading cached ERA5-Land precipitation from {cache_path}")
        precip = pd.read_parquet(cache_path).squeeze()
        if not isinstance(precip.index, pd.DatetimeIndex):
            precip.index = pd.to_datetime(precip.index, utc=True)
        elif precip.index.tzinfo is None:
            precip.index = precip.index.tz_localize("UTC")
    else:
        click.echo(f"Downloading ERA5-Land hourly ({lat}N, {lon}E), {start_year}-{end_year} ...")
        precip = fetch_hourly_precip_era5land(lat, lon, start_year, end_year)
        if cache_path is not None:
            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
            precip.to_frame().to_parquet(cache_path)
            click.echo(f"  Cached -> {cache_path}")
    click.echo(f"  {len(precip):,} hourly records ({precip.index[0].year}-{precip.index[-1].year}).")

    # 2. Rolling accumulation
    click.echo(f"\nComputing {window_h}h rolling accumulation ...")
    acc = rolling_accumulation(precip, window_h)

    # 3. Annual maxima
    ann_max = annual_maxima(acc, min_coverage=0.5)
    years_ok = sorted(ann_max.keys())
    n_years = len(ann_max)
    click.echo(f"{n_years} years of annual maxima ({years_ok[0]}-{years_ok[-1]}).")
    if n_years < min_years:
        raise click.ClickException(
            f"Only {n_years} valid years -- need at least {min_years}."
        )

    maxima_arr = np.array([ann_max[y] for y in years_ok], dtype=np.float64)
    click.echo(
        f"Annual maxima of {window_h}h accumulation (mm): "
        f"mean={maxima_arr.mean():.1f}  std={maxima_arr.std():.1f}  "
        f"min={maxima_arr.min():.1f}  max={maxima_arr.max():.1f}"
    )

    # 4. GEV fit
    c, loc, scale = fit_gev(maxima_arr, xi_max=xi_max)
    xi = -c
    click.echo(f"GEV fit (MLE): xi={xi:.4f}  mu={loc:.3f} mm  sigma={scale:.3f} mm")

    # 5. Return period table
    rows = []
    click.echo(
        f"\nPluvial excess rain depths "
        f"(drain_capacity={drain_capacity_mm}mm; runoff_coeff and "
        f"depression_area_fraction applied downstream per-cell):"
    )
    click.echo(f"  {'RP (yr)':>8}  {'Design rainfall (mm)':>22}  {'Excess depth (m)':>18}")
    click.echo(f"  {'-'*8}  {'-'*22}  {'-'*18}")
    for rp in RETURN_PERIODS:
        design_mm = max(1.0, gev_return_level(c, loc, scale, rp))
        excess_mm = max(0.0, design_mm - drain_capacity_mm)
        # excess_depth_m is the post-drain rain depth (m).  The runoff
        # coefficient is now applied per-cell at run time (spatially, from
        # the WorldCover raster), so it is NOT applied here.  Likewise
        # depression_area_fraction is retired — the fill-spill model
        # distributes runoff by catchment, not by a lumped fraction.
        excess_depth_m = excess_mm / 1000.0
        click.echo(f"  {rp:>8d}  {design_mm:>22.1f}  {excess_depth_m:>18.4f}")
        rows.append({
            "hazard_type": "pluvial",
            "return_period": rp,
            "baseline_water_level_m": excess_depth_m,
            "gev_shape": xi,
            "gev_loc_mm": loc,
            "gev_scale_mm": scale,
            "datum_note": (
                "excess_depth_m (post-drain rain depth, m); downstream "
                "flood_depth_pluvial_fillspill multiplies by the per-cell "
                "runoff coefficient and routes it by catchment."
            ),
            "source_note": (
                f"ERA5-Land via Open-Meteo Archive ({lat}N {lon}E); "
                f"GEV fit to {n_years} annual maxima of {window_h}h rolling "
                f"precipitation ({years_ok[0]}-{years_ok[-1]}); "
                f"drain_capacity={drain_capacity_mm}mm; "
                f"runoff_coeff={runoff_coeff}; "
                f"depression_area_fraction={depression_area_fraction}; "
                f"xi={xi:.4f} mu={loc:.3f}mm sigma={scale:.3f}mm"
            ),
        })

    if dry_run:
        click.echo("\n[Dry run] No files modified.")
        return

    # 6. Write CSV
    if output_path.exists():
        existing = pd.read_csv(output_path)
        other = existing[existing["hazard_type"] != "pluvial"].copy()
    else:
        other = pd.DataFrame(columns=[
            "hazard_type", "return_period", "baseline_water_level_m", "source_note"
        ])
    updated = pd.concat([other, pd.DataFrame(rows)], ignore_index=True)
    updated = updated.sort_values(["hazard_type", "return_period"]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    updated.to_csv(output_path, index=False)
    click.echo(f"\nUpdated {output_path} with {len(rows)} pluvial rows.")


if __name__ == "__main__":
    cli()
