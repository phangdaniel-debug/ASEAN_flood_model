"""
Derive fluvial channel stage from GloFAS v4 daily river discharge.

Uses the Open-Meteo Flood API (flood-api.open-meteo.com) — free, no key,
CC-BY 4.0, backed by the Copernicus GloFAS v4 Reanalysis (1984–present,
~5 km resolution).  Replaces ERA5-rainfall-derived stages for cities where
the local ERA5 grid cell cannot represent the upstream basin (mega-rivers:
Chao Phraya, Pasig/Marikina, Saigon, Ciliwung).

Method
------
1. Download (or load cached) daily discharge from Open-Meteo Flood API.
2. Extract annual maxima (years with <50% coverage dropped).
3. Fit GEV to annual maxima series (same gev_utils.fit_gev as ERA5 path).
4. Convert RP discharges to channel stage via Manning's equation using the
   city's existing channel_width_m, mannings_n, channel_slope from CityConfig.
5. Overwrite fluvial rows in hazard_baseline_template.csv.

Usage
-----
    python scripts/fit_fluvial_glofas.py --city jakarta
    python scripts/fit_fluvial_glofas.py --city bangkok_chao_phraya --dry-run
    python scripts/fit_fluvial_glofas.py --city manila --no-cache
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import click
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.cities import CITIES
from scripts.gev_utils import fit_gev, gev_return_level, mannings_stage

RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]
_API_BASE = "https://flood-api.open-meteo.com/v1/flood"
_START_DATE = "1984-01-01"
_END_DATE   = "2024-12-31"


def fetch_daily_discharge(
    lat: float,
    lon: float,
    start_date: str = _START_DATE,
    end_date: str = _END_DATE,
    cache_path: Path | None = None,
    timeout: int = 120,
) -> pd.DataFrame:
    """
    Fetch daily river discharge from Open-Meteo Flood API (GloFAS v4).

    Parameters
    ----------
    lat, lon    : WGS84 coordinates of the river reach to sample
    start_date  : ISO8601 start date (default 1984-01-01)
    end_date    : ISO8601 end date (default 2024-12-31)
    cache_path  : if given and exists, load from parquet instead of fetching
    timeout     : HTTP request timeout in seconds

    Returns
    -------
    DataFrame with DatetimeIndex (UTC) and column 'discharge_m3s'.

    Raises
    ------
    ValueError  : if the API returns no valid (non-null) discharge values
    """
    if cache_path is not None and Path(cache_path).exists():
        click.echo(f"  Loading cached GloFAS discharge from {cache_path} ...")
        df = pd.read_parquet(cache_path)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, utc=True)
        elif df.index.tzinfo is None:
            df.index = df.index.tz_localize("UTC")
        click.echo(f"  {len(df):,} daily records ({df.index[0].year}–{df.index[-1].year}).")
        return df

    url = (
        f"{_API_BASE}?latitude={lat}&longitude={lon}"
        f"&daily=river_discharge"
        f"&start_date={start_date}&end_date={end_date}"
        f"&forecast_days=0"
    )
    click.echo(f"  Fetching GloFAS discharge ({lat}N {lon}E) ...")
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        payload = json.loads(resp.read())

    times = payload["daily"]["time"]
    values = payload["daily"]["river_discharge"]

    index = pd.to_datetime(times, utc=True)
    df = pd.DataFrame({"discharge_m3s": values}, index=index)
    df["discharge_m3s"] = pd.to_numeric(df["discharge_m3s"], errors="coerce")

    n_valid = int(df["discharge_m3s"].notna().sum())
    if n_valid == 0:
        raise ValueError(
            f"GloFAS API returned no valid discharge at ({lat}, {lon}). "
            "Check coordinates — the point may not be on a GloFAS river reach. "
            "Try adjusting lat/lon by 0.05–0.10 degrees toward the main channel."
        )

    click.echo(f"  {len(df):,} daily records, {n_valid:,} non-null.")

    if cache_path is not None:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_path)
        click.echo(f"  Cached to {cache_path}")

    return df


def annual_maxima_discharge(
    series: pd.Series,
    min_days: int = 183,
) -> dict[int, float]:
    """
    Annual maxima of daily discharge; years with fewer than min_days
    non-null values are excluded.

    Parameters
    ----------
    series   : daily discharge Series with DatetimeIndex
    min_days : minimum valid days per year (default 183 = 50% of 365)

    Returns
    -------
    dict mapping year (int) → annual maximum discharge (float, m³/s)
    """
    results: dict[int, float] = {}
    for year, group in series.groupby(series.index.year):
        n_valid = int(group.notna().sum())
        if n_valid < min_days:
            continue
        results[int(year)] = float(group.max(skipna=True))
    return results


def build_stage_table(
    maxima: dict[int, float],
    channel_width_m: float,
    mannings_n: float,
    channel_slope: float,
    xi_max: float,
    max_stage_m: float,
    lat: float,
    lon: float,
    bankfull_discharge_m3s: float | None = None,
) -> list[dict]:
    """
    Fit GEV to annual maxima and convert RP discharges to Manning stage.

    Parameters
    ----------
    maxima                  : dict of year → annual maximum discharge (m³/s).
                              Values should already have any bias correction applied.
    channel_width_m         : representative channel width (m)
    mannings_n              : Manning's roughness coefficient
    channel_slope           : channel slope (m/m)
    xi_max                  : GEV shape parameter cap (positive = heavy tail)
    max_stage_m             : physical cap on output stage (m)
    lat, lon                : GloFAS sample coordinates (for source_note)
    bankfull_discharge_m3s  : if set, subtract Manning(Q_bankfull) from each RP
                              stage to produce flood depth above normal water level
                              rather than total channel depth.  Use for flat,
                              managed, or tidal channels (e.g. Chao Phraya).

    Returns a list of dicts ready for CSV writing (one per return period).
    """
    n_years = len(maxima)
    years = sorted(maxima.keys())
    maxima_arr = np.array([maxima[y] for y in years], dtype=np.float64)

    try:
        c, loc, scale = fit_gev(maxima_arr, xi_max=xi_max)
    except Exception as exc:
        raise ValueError(f"GEV fit failed: {exc}") from exc

    xi = -c
    click.echo(f"  GEV fit: xi={xi:.4f}  mu={loc:.1f} m3/s  sigma={scale:.1f} m3/s")

    # Bankfull stage: Manning total depth at Q_bankfull, subtracted from each RP.
    stage_bankfull_m = 0.0
    if bankfull_discharge_m3s is not None and bankfull_discharge_m3s > 0.0:
        stage_bankfull_m = mannings_stage(
            bankfull_discharge_m3s, channel_width_m, mannings_n, channel_slope
        )
        click.echo(
            f"  Bankfull: Q={bankfull_discharge_m3s:.0f} m3/s -> "
            f"Manning depth={stage_bankfull_m:.3f} m (subtracted from each RP stage)"
        )

    header = f"\n  {'RP (yr)':>8}  {'Q_rp (m3/s)':>12}  {'Total (m)':>10}  {'Stage (m)':>10}"
    if bankfull_discharge_m3s is None:
        header = f"\n  {'RP (yr)':>8}  {'Q_rp (m3/s)':>12}  {'Stage (m)':>10}"
    click.echo(header)
    click.echo(f"  {'-'*8}  {'-'*12}  {'-'*10}" + ("  " + "-"*10 if bankfull_discharge_m3s is not None else ""))

    rows = []
    for rp in RETURN_PERIODS:
        q_rp = max(1.0, gev_return_level(c, loc, scale, rp))
        total_m = mannings_stage(q_rp, channel_width_m, mannings_n, channel_slope)
        stage_m = max(0.05, min(round(total_m - stage_bankfull_m, 4), max_stage_m))
        if bankfull_discharge_m3s is not None:
            click.echo(f"  {rp:>8d}  {q_rp:>12.1f}  {total_m:>10.3f}  {stage_m:>10.3f}")
        else:
            click.echo(f"  {rp:>8d}  {q_rp:>12.1f}  {stage_m:>10.3f}")

        bankfull_note = (
            f"; bankfull_subtraction Q={bankfull_discharge_m3s:.0f}m3s "
            f"depth={stage_bankfull_m:.3f}m"
            if bankfull_discharge_m3s is not None else ""
        )
        rows.append({
            "hazard_type": "fluvial",
            "return_period": rp,
            "baseline_water_level_m": stage_m,
            "gev_shape": xi,
            "gev_loc_mm": loc,      # m³/s stored in mm column (schema-compatible)
            "gev_scale_mm": scale,  # m³/s stored in mm column (schema-compatible)
            "datum_note": (
                "relative_stage_above_bankfull_m; "
                "height_above_normal_water_level_compatible_with_HAND_model"
                if bankfull_discharge_m3s is not None
                else
                "relative_stage_above_channel_bed_m; "
                "no_absolute_datum_conversion_required; "
                "compatible_with_HAND_model_which_is_also_relative"
            ),
            "source_note": (
                f"GloFAS v4 Reanalysis via Open-Meteo Flood API ({lat}N {lon}E); "
                f"GEV fit to {n_years} annual maxima of daily discharge "
                f"({years[0]}-{years[-1]}); "
                f"Manning w={channel_width_m}m n={mannings_n} S={channel_slope}; "
                f"xi={xi:.4f} mu={loc:.1f}m3s sigma={scale:.1f}m3s"
                + bankfull_note
            ),
        })
    return rows


def write_fluvial_rows(rows: list[dict], output_path: Path) -> None:
    """Overwrite fluvial rows in the baseline CSV; leave other hazards intact."""
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
    click.echo(f"\n  Updated {output_path} with {len(rows)} fluvial rows.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option("--city", "city_slug", required=True,
              help="City slug as defined in scripts/cities.py (must have glofas_lat set).")
@click.option("--cache", "cache_path", type=click.Path(path_type=Path), default=None,
              help="Parquet cache path. Default: cache/glofas_{slug}.parquet.")
@click.option("--no-cache", "force_fetch", is_flag=True, default=False,
              help="Force re-fetch even if cache exists.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Print RP table without writing CSV.")
@click.option("--xi-max", "xi_max", type=float, default=0.30, show_default=True)
@click.option("--max-stage-m", "max_stage_m", type=float, default=20.0, show_default=True,
              help="Physical cap on stage (m). Default 20 m for large rivers.")
@click.option("--min-years", "min_years", type=int, default=10, show_default=True)
@click.option("--output", "output_path", type=click.Path(path_type=Path), default=None,
              help="Override default CSV path (data/{slug}/hazard_baseline_template.csv).")
@click.option("--start-date", default=_START_DATE, show_default=True)
@click.option("--end-date", default=_END_DATE, show_default=True)
@click.option("--discharge-scale", "discharge_scale", type=float, default=None,
              help=(
                  "Multiplicative bias-correction factor applied to daily discharge "
                  "before GEV fitting.  Overrides city.glofas_discharge_scale when set. "
                  "Default: use CityConfig value (1.0 if not configured)."
              ))
@click.option("--bankfull-discharge", "bankfull_discharge", type=float, default=None,
              help=(
                  "Bankfull discharge (m³/s).  Manning stage at this flow is subtracted "
                  "from each RP stage to give flood depth above normal water level. "
                  "Overrides city.glofas_bankfull_discharge_m3s when set. "
                  "Omit (or set 0) to skip bankfull subtraction."
              ))
def cli(
    city_slug: str,
    cache_path: Path | None,
    force_fetch: bool,
    dry_run: bool,
    xi_max: float,
    max_stage_m: float,
    min_years: int,
    output_path: Path | None,
    start_date: str,
    end_date: str,
    discharge_scale: float | None,
    bankfull_discharge: float | None,
) -> None:
    """Fit GloFAS fluvial baseline for a city and write to hazard_baseline_template.csv."""
    if city_slug not in CITIES:
        raise click.ClickException(f"Unknown city '{city_slug}'. Check scripts/cities.py.")
    city = CITIES[city_slug]
    if city.glofas_lat is None:
        raise click.ClickException(
            f"No GloFAS coordinates configured for '{city_slug}'. "
            "Add glofas_lat / glofas_lon to CityConfig in scripts/cities.py."
        )

    effective_cache = cache_path or (PROJECT_ROOT / "cache" / f"glofas_{city_slug}.parquet")
    if force_fetch and effective_cache.exists():
        effective_cache.unlink()
        click.echo(f"  Removed cache {effective_cache} (--no-cache).")

    csv_path = output_path or (
        PROJECT_ROOT / "data" / city_slug / "hazard_baseline_template.csv"
    )

    # Resolve bias-correction scale: CLI flag overrides CityConfig.
    effective_scale = (
        discharge_scale
        if discharge_scale is not None
        else city.glofas_discharge_scale
    )

    # Resolve bankfull discharge: CLI flag overrides CityConfig; 0.0 means skip.
    effective_bankfull: float | None
    if bankfull_discharge is not None:
        effective_bankfull = bankfull_discharge if bankfull_discharge > 0.0 else None
    else:
        effective_bankfull = city.glofas_bankfull_discharge_m3s

    click.echo(
        f"\nGloFAS fluvial injection: {city.name} "
        f"({city.glofas_lat}N {city.glofas_lon}E)"
    )
    click.echo(
        f"  Channel: w={city.channel_width_m}m  n={city.mannings_n}  "
        f"S={city.channel_slope}  max_stage={max_stage_m}m"
    )
    if effective_scale != 1.0:
        click.echo(f"  Discharge scale: {effective_scale} (bias correction)")
    if effective_bankfull is not None:
        click.echo(f"  Bankfull discharge: {effective_bankfull} m3/s (stage subtraction)")

    # 1. Fetch
    df = fetch_daily_discharge(
        city.glofas_lat, city.glofas_lon,
        start_date=start_date, end_date=end_date,
        cache_path=effective_cache,
    )

    # 2. Apply bias correction and compute annual maxima.
    discharge_series = df["discharge_m3s"]
    if effective_scale != 1.0:
        discharge_series = discharge_series * effective_scale
    maxima = annual_maxima_discharge(discharge_series)
    n_years = len(maxima)
    if n_years < min_years:
        raise click.ClickException(
            f"Insufficient GloFAS record: {n_years} valid years < {min_years} minimum. "
            "Try extending --start-date or adjusting coordinates."
        )
    click.echo(f"  {n_years} years of annual maxima.")

    # 3. GEV + stage table
    try:
        rows = build_stage_table(
            maxima,
            channel_width_m=city.channel_width_m,
            mannings_n=city.mannings_n,
            channel_slope=city.channel_slope,
            xi_max=xi_max,
            max_stage_m=max_stage_m,
            lat=city.glofas_lat,
            lon=city.glofas_lon,
            bankfull_discharge_m3s=effective_bankfull,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if dry_run:
        click.echo("\n[Dry run] No files modified.")
        return

    # 4. Write CSV
    write_fluvial_rows(rows, csv_path)


if __name__ == "__main__":
    cli()
