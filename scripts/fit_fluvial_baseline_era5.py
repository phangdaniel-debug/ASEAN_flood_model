"""
Derive fluvial channel stage from reanalysis precipitation (any city).

Originally written for Singapore; now invoked for every city configured in
scripts/cities.py — Singapore, Kuala Lumpur, Klang/Shah Alam,
Subang/Langat, Bangkok, Jakarta core, Bekasi/Depok and Tangerang.
The script is fully generic; only the docstring still mentions Singapore
for historical context.

Data source
-----------
ERA5-Land via Open-Meteo Archive API (free, no key, CC-BY 4.0).
  - URL : https://archive-api.open-meteo.com/v1/era5
  - Resolution: ~9 km; available 1950–present.
  - Same source and fetch function as fit_pluvial_baseline_era5.py.
  - Use --cache-precip to share the downloaded data between both scripts.

Method
------
1. Download (or load cached) hourly precipitation for the selected city.
2. Compute rolling 24-hour accumulation → annual maxima.
3. Fit a GEV distribution → design 24h rainfall at each return period.
4. Convert to effective runoff using the SCS Curve Number method:

       S  = 25400 / CN − 254                  [mm, potential max retention]
       Ia = 0.2 × S                            [mm, initial abstraction]
       Q_eff = (P − Ia)² / (P + 0.8·S)        [mm] for P > Ia, else 0

   Default CN = 85 (urban Singapore — predominantly impervious, Group C/D soils).

5. Estimate peak discharge via the SCS triangular unit hydrograph:

       Tp  = D/2 + 0.6·Tc                     [h, time to peak]
       Qp  = 0.208 × A_km2 × Q_eff_mm / Tp_h  [m³/s]

   where D=24h (storm duration), Tc=time of concentration, A=catchment area.

   Default parameters represent a representative Singapore urban waterway:
       A  = 10 km²  (moderate urban catchment)
       Tc = 0.5 h   (short, dense urban drainage network)

6. Convert peak discharge to bankfull channel stage via Manning's equation
   (wide rectangular channel approximation, valid when w/d > 5):

       d = (Qp · n / (w · √S))^(3/5)          [m above channel bed]

   Default channel parameters:
       n = 0.040  (concrete-lined Singapore drain, minor vegetation)
       w = 10 m   (representative urban channel width)
       S = 0.002  (channel slope — Singapore lowland waterways)

7. Write fluvial rows to the hazard baseline CSV, replacing placeholders.

Interpretation
--------------
The resulting stage_m is used by the HAND flood model:

    depth(x, y) = max(0, stage_m − HAND(x, y))

It represents the water-surface elevation above the channel bed at each return
period for a representative catchment.  Larger catchments will have higher
stages; smaller ones lower.  The representative parameters above are tuned to
Singapore's mid-size urban drains.  Adjust --catchment-km2 and --channel-width
for sensitivity testing.

Usage
-----
    python scripts/fit_fluvial_baseline_era5.py \\
        --output data/singapore_hazard_baseline_template.csv

    # Reuse or share a cached ERA5-Land download
    python scripts/fit_fluvial_baseline_era5.py \\
        --cache-precip cache/era5land_singapore_fluvial.parquet \\
        --output data/singapore/hazard_baseline_template.csv

    # Preview without writing
    python scripts/fit_fluvial_baseline_era5.py --dry-run

    # Adjust for a larger catchment
    python scripts/fit_fluvial_baseline_era5.py \\
        --catchment-km2 50 --channel-width 20 --time-of-conc 1.0 \\
        --output data/singapore_hazard_baseline_template.csv
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

RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]

# Default coordinates — Singapore centroid (overridden by --lat/--lon CLI flags)
_DEFAULT_LAT = 1.2903
_DEFAULT_LON = 103.8519


# ---------------------------------------------------------------------------
# Statistics — shared GEV utilities live in scripts/gev_utils.py
# ---------------------------------------------------------------------------

from scripts.gev_utils import (
    rolling_accumulation,
    annual_maxima,
    fit_gev,
    gev_return_level,
    fetch_hourly_precip_era5land,
    mannings_stage,
)


# ---------------------------------------------------------------------------
# Hydraulic conversion
# ---------------------------------------------------------------------------

def scs_effective_runoff(rainfall_mm: float, cn: float) -> float:
    """
    SCS Curve Number effective runoff depth (mm).

    Parameters
    ----------
    rainfall_mm : total storm rainfall depth (mm)
    cn : SCS Curve Number (dimensionless, 0–100)

    Returns
    -------
    Q_eff : effective runoff depth (mm), >= 0
    """
    if cn <= 0 or cn >= 100:
        raise ValueError(f"CN must be in (0, 100), got {cn}")
    S = 25400.0 / cn - 254.0       # potential maximum retention (mm)
    Ia = 0.2 * S                    # initial abstraction (mm)
    if rainfall_mm <= Ia:
        return 0.0
    return (rainfall_mm - Ia) ** 2 / (rainfall_mm + 0.8 * S)


def scs_peak_discharge(
    q_eff_mm: float,
    catchment_km2: float,
    storm_duration_h: float,
    time_of_conc_h: float,
) -> float:
    """
    Peak discharge via SCS triangular unit hydrograph (m³/s).

        Tp  = D/2 + 0.6·Tc
        Qp  = 0.208 × A × Q_eff / Tp

    Parameters
    ----------
    q_eff_mm : effective runoff depth (mm)
    catchment_km2 : catchment area (km²)
    storm_duration_h : storm duration (hours)
    time_of_conc_h : time of concentration (hours)

    Returns
    -------
    Q_peak : peak discharge (m³/s)
    """
    Tp = storm_duration_h / 2.0 + 0.6 * time_of_conc_h   # hours
    Q_peak = 0.208 * catchment_km2 * q_eff_mm / Tp        # m³/s
    return max(0.0, Q_peak)



# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=Path("data/singapore_hazard_baseline_template.csv"),
    show_default=True,
    help="Hazard baseline CSV — fluvial rows will be replaced.",
)
@click.option(
    "--lat", type=float, default=_DEFAULT_LAT, show_default=True,
    help="Latitude of the ERA5 precipitation point.",
)
@click.option(
    "--lon", type=float, default=_DEFAULT_LON, show_default=True,
    help="Longitude of the ERA5 precipitation point.",
)
@click.option("--start-year", type=int, default=2001, show_default=True)
@click.option("--end-year", type=int, default=2024, show_default=True)
@click.option(
    "--window-h",
    type=int,
    default=24,
    show_default=True,
    help=(
        "Rolling accumulation window (hours).  24 h captures the daily rainfall "
        "totals that drive catchment-scale runoff in Singapore."
    ),
)
@click.option(
    "--curve-number",
    type=float,
    default=85.0,
    show_default=True,
    help=(
        "SCS Curve Number.  85 is appropriate for urban Singapore "
        "(predominantly impervious, Group C/D soils)."
    ),
)
@click.option(
    "--catchment-km2",
    type=float,
    default=10.0,
    show_default=True,
    help=(
        "Representative catchment area (km²).  Affects peak discharge magnitude.  "
        "Default 10 km² is typical for Singapore's smaller urban waterways.  "
        "Use 50–100 km² for larger reservoir catchments (Kallang, Pandan)."
    ),
)
@click.option(
    "--time-of-conc",
    "time_of_conc_h",
    type=float,
    default=0.50,
    show_default=True,
    help="Time of concentration (hours).  0.5 h is typical for dense urban Singapore.",
)
@click.option(
    "--channel-width",
    type=float,
    default=10.0,
    show_default=True,
    help="Representative channel width (m).  10 m for small urban drains.",
)
@click.option(
    "--mannings-n",
    type=float,
    default=0.040,
    show_default=True,
    help=(
        "Manning's roughness coefficient.  0.040 for concrete-lined Singapore "
        "urban channel with minor vegetation."
    ),
)
@click.option(
    "--channel-slope",
    type=float,
    default=0.002,
    show_default=True,
    help="Channel slope (m/m).  0.002 typical for Singapore lowland waterways.",
)
@click.option(
    "--min-years",
    type=int,
    default=20,
    show_default=True,
    help="Minimum valid annual-maxima years required for GEV fit.",
)
@click.option(
    "--xi-max",
    "xi_max",
    type=float,
    default=0.30,
    show_default=True,
    help=(
        "Maximum allowed GEV shape parameter xi. Re-fits with fixed shape when "
        "unconstrained MLE exceeds this bound (prevents Frechet explosion). "
        "0.30 caps Frechet tails for tropical 24h precipitation."
    ),
)
@click.option(
    "--max-stage-m",
    "max_stage_m",
    type=float,
    default=8.0,
    show_default=True,
    help=(
        "Physical upper cap on fluvial channel stage (metres). Prevents unrealistic "
        "depths from ERA5-based SCS/Manning hydraulics on flat or large catchments. "
        "Default 8 m is a reasonable upper bound for urban river stages; increase "
        "to 15-20 m for large natural rivers."
    ),
)
@click.option(
    "--cache-precip",
    "cache_path",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Path to Parquet cache of hourly precipitation.  "
        "If exists, download is skipped.  Shared with fit_pluvial_baseline_era5.py."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print derived levels without modifying the CSV.",
)
def cli(
    output_path: Path,
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
    window_h: int,
    curve_number: float,
    catchment_km2: float,
    time_of_conc_h: float,
    channel_width: float,
    mannings_n: float,
    channel_slope: float,
    min_years: int,
    xi_max: float,
    max_stage_m: float,
    cache_path: Path | None,
    dry_run: bool,
) -> None:
    # ------------------------------------------------------------------
    # 1. Load or download precipitation
    # ------------------------------------------------------------------
    if cache_path is not None and Path(cache_path).exists():
        click.echo(f"Loading cached ERA5-Land precipitation from {cache_path} ...")
        precip = pd.read_parquet(cache_path).squeeze()
        if not isinstance(precip.index, pd.DatetimeIndex):
            precip.index = pd.to_datetime(precip.index, utc=True)
        elif precip.index.tzinfo is None:
            precip.index = precip.index.tz_localize("UTC")
        click.echo(f"  {len(precip):,} hourly records ({precip.index[0].year}–{precip.index[-1].year}).")
    else:
        click.echo(
            f"Downloading ERA5-Land hourly precipitation "
            f"({lat}°N, {lon}°E) via Open-Meteo, {start_year}–{end_year} ..."
        )
        precip = fetch_hourly_precip_era5land(lat, lon, start_year, end_year)
        n_valid = int(precip.notna().sum())
        click.echo(f"  Total: {len(precip):,} hourly records, {n_valid:,} non-NaN.")

        if cache_path is not None:
            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
            precip.to_frame().to_parquet(cache_path)
            click.echo(f"  Saved to cache: {cache_path}")

    # ------------------------------------------------------------------
    # 2. Rolling accumulation → annual maxima
    # ------------------------------------------------------------------
    click.echo(f"\nComputing {window_h}h rolling accumulation ...")
    acc = rolling_accumulation(precip, window_h)

    ann_max = annual_maxima(acc, min_coverage=0.5)
    years_ok = sorted(ann_max.keys())
    n_years = len(ann_max)
    click.echo(f"{n_years} years of annual maxima ({years_ok[0]}–{years_ok[-1]}).")

    if n_years < min_years:
        raise click.ClickException(
            f"Only {n_years} valid years — need at least {min_years}."
        )

    maxima_arr = np.array([ann_max[y] for y in years_ok], dtype=np.float64)
    click.echo(
        f"Annual maxima of {window_h}h rainfall (mm): "
        f"mean={maxima_arr.mean():.1f}  std={maxima_arr.std():.1f}  "
        f"min={maxima_arr.min():.1f}  max={maxima_arr.max():.1f}"
    )

    # ------------------------------------------------------------------
    # 3. GEV fit
    # ------------------------------------------------------------------
    try:
        c, loc, scale = fit_gev(maxima_arr, xi_max=xi_max)
    except Exception as exc:
        raise click.ClickException(f"GEV fit failed: {exc}")

    xi = -c
    click.echo(f"GEV fit (MLE): xi={xi:.4f}  mu={loc:.3f} mm  sigma={scale:.3f} mm")

    # Echo channel parameters
    click.echo(
        f"\nChannel parameters: "
        f"A={catchment_km2} km²  Tc={time_of_conc_h} h  "
        f"w={channel_width} m  n={mannings_n}  S={channel_slope}"
    )
    click.echo(f"SCS CN={curve_number}")
    S_retention = 25400.0 / curve_number - 254.0
    click.echo(f"  S={S_retention:.1f} mm  Ia={0.2*S_retention:.1f} mm (initial abstraction)")

    # ------------------------------------------------------------------
    # 4. Return period table
    # ------------------------------------------------------------------
    rows = []
    click.echo(
        f"\n  {'RP (yr)':>8}  {'Design 24h (mm)':>16}  "
        f"{'Q_eff (mm)':>11}  {'Q_peak (m³/s)':>14}  {'Stage (m)':>10}"
    )
    click.echo(f"  {'-'*8}  {'-'*16}  {'-'*11}  {'-'*14}  {'-'*10}")

    for rp in RETURN_PERIODS:
        design_mm = max(1.0, gev_return_level(c, loc, scale, rp))
        q_eff_mm = scs_effective_runoff(design_mm, curve_number)
        q_peak = scs_peak_discharge(
            q_eff_mm,
            catchment_km2=catchment_km2,
            storm_duration_h=float(window_h),
            time_of_conc_h=time_of_conc_h,
        )
        stage_m = mannings_stage(q_peak, channel_width, mannings_n, channel_slope)
        stage_m = max(0.05, min(round(stage_m, 4), max_stage_m))

        click.echo(
            f"  {rp:>8d}  {design_mm:>16.1f}  "
            f"{q_eff_mm:>11.1f}  {q_peak:>14.2f}  {stage_m:>10.3f}"
        )
        rows.append(
            {
                "hazard_type": "fluvial",
                "return_period": rp,
                "baseline_water_level_m": stage_m,
                "gev_shape": xi,
                "gev_loc_mm": loc,
                "gev_scale_mm": scale,
                "datum_note": (
                    "relative_stage_above_channel_bed_m; "
                    "no_absolute_datum_conversion_required; "
                    "compatible_with_HAND_model_which_is_also_relative"
                ),
                "source_note": (
                    f"ERA5-Land via Open-Meteo Archive ({lat}N {lon}E); "
                    f"GEV fit to {n_years} annual maxima of {window_h}h rainfall "
                    f"({years_ok[0]}–{years_ok[-1]}); "
                    f"SCS CN={curve_number}; "
                    f"SCS UH A={catchment_km2}km2 Tc={time_of_conc_h}h; "
                    f"Manning w={channel_width}m n={mannings_n} S={channel_slope}; "
                    f"xi={xi:.4f} mu={loc:.3f}mm sigma={scale:.3f}mm"
                ),
            }
        )

    if dry_run:
        click.echo("\n[Dry run] No files modified.")
        return

    # ------------------------------------------------------------------
    # 5. Write to CSV
    # ------------------------------------------------------------------
    if output_path.exists():
        existing = pd.read_csv(output_path)
        other = existing[existing["hazard_type"] != "fluvial"].copy()
    else:
        other = pd.DataFrame(
            columns=["hazard_type", "return_period", "baseline_water_level_m", "source_note"]
        )

    updated = pd.concat([other, pd.DataFrame(rows)], ignore_index=True)
    updated = updated.sort_values(["hazard_type", "return_period"]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    updated.to_csv(output_path, index=False)
    click.echo(f"\nUpdated {output_path} with {len(rows)} fluvial rows.")


if __name__ == "__main__":
    cli()
