"""
Shared GEV and rolling-precipitation utilities for the flood pipeline.

Extracted from fit_pluvial_baseline_era5.py and fit_fluvial_baseline_era5.py
(previously duplicated).
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd


def rolling_accumulation(precip: pd.Series, window_h: int) -> pd.Series:
    """Rolling sum of hourly precipitation over ``window_h`` hours (mm)."""
    return precip.rolling(window=window_h, min_periods=max(1, window_h // 2)).sum()


def annual_maxima(series: pd.Series, min_coverage: float = 0.5) -> dict[int, float]:
    """Annual maxima; years with <min_coverage * 8760 valid hours are excluded."""
    results: dict[int, float] = {}
    for year, group in series.groupby(series.index.year):
        n_valid = int(group.notna().sum())
        if n_valid < int(8760 * min_coverage):
            continue
        results[int(year)] = float(group.max(skipna=True))
    return results


def fit_gev(maxima: np.ndarray, xi_max: float = 0.30) -> tuple[float, float, float]:
    """
    Fit GEV via MLE.  Returns scipy.stats.genextreme parameterisation (c, loc, scale).
    Shape xi = -c is clamped to [-0.5, xi_max] to prevent unstable Frechet fits.

    xi_max=0.30 (Gumbel-to-light-Frechet range) is appropriate for tropical
    sub-daily precipitation; the previous 0.5 allowed heavy Frechet tails that
    produced unrealistically large RP200-1000 ponding depths for Singapore.
    Validated against PUB observed ponding range (RP10-RP1000: 0.07-0.76 m).
    """
    import click
    from scipy.stats import genextreme
    c, loc, scale = genextreme.fit(maxima)
    if scale <= 0:
        raise ValueError(f"GEV fit returned non-positive scale={scale:.4f}")
    xi = -c
    xi_clamped = float(np.clip(xi, -0.5, xi_max))
    if abs(xi_clamped - xi) > 1e-6:
        click.echo(
            f"  [info] GEV shape xi={xi:.4f} clamped to {xi_clamped:.4f} "
            f"(xi_max={xi_max}). Re-fitting with fixed shape."
        )
        c_fixed = -xi_clamped
        _, loc, scale = genextreme.fit(maxima, f0=c_fixed)
        c = c_fixed
    return float(c), float(loc), float(scale)


def gev_return_level(c: float, loc: float, scale: float, rp: float) -> float:
    """GEV quantile at return period T: F(x_T) = 1 - 1/T."""
    from scipy.stats import genextreme
    return float(genextreme.ppf(1.0 - 1.0 / rp, c, loc=loc, scale=scale))


def fetch_hourly_precip_era5land(
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
    chunk_years: int = 5,
) -> "pd.Series":
    """
    Download hourly ERA5-Land precipitation (mm/h) from Open-Meteo Archive.

    Free, no API key required.  Returns a DatetimeIndex (UTC) pd.Series
    with column name ``precipitation_mm_h``.  Uses 3-attempt retry with
    exponential backoff.

    Parameters
    ----------
    lat, lon : float
        Coordinates of the ERA5-Land grid point (nearest neighbour used by API).
    start_year, end_year : int
        Inclusive date range.  ERA5-Land starts 1950; 2001 is a practical default.
    chunk_years : int
        Years per API request.  Default 5 keeps individual payloads small.
    """
    import time
    import requests
    import click

    _URL = "https://archive-api.open-meteo.com/v1/era5"
    chunks: list[pd.Series] = []
    for yr0 in range(start_year, end_year + 1, chunk_years):
        yr1 = min(yr0 + chunk_years - 1, end_year)
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": f"{yr0}-01-01",
            "end_date": f"{yr1}-12-31",
            "hourly": "precipitation",
            "timezone": "UTC",
        }
        click.echo(f"  ERA5-Land {yr0}-{yr1} ... ", nl=False)
        resp = None
        for attempt in range(3):
            try:
                resp = requests.get(_URL, params=params, timeout=180)
                resp.raise_for_status()
                break
            except Exception as exc:
                if attempt == 2:
                    raise click.ClickException(
                        f"Open-Meteo request failed ({yr0}-{yr1}): {exc}"
                    ) from exc
                time.sleep(5 * (attempt + 1))
        payload = resp.json()
        if "hourly" not in payload or "precipitation" not in payload["hourly"]:
            raise click.ClickException(
                f"Unexpected Open-Meteo response keys: {list(payload.keys())}"
            )
        times = pd.to_datetime(payload["hourly"]["time"], utc=True)
        values = np.array(payload["hourly"]["precipitation"], dtype=np.float32)
        values[values < 0] = np.nan
        series = pd.Series(values, index=times, name="precipitation_mm_h").sort_index()
        n_valid = int(np.isfinite(values).sum())
        click.echo(f"{n_valid:,} valid obs")
        chunks.append(series)
        time.sleep(0.5)

    combined = pd.concat(chunks).sort_index()
    return combined[~combined.index.duplicated(keep="first")]


def mannings_stage(
    q_peak_m3s: float,
    channel_width_m: float,
    mannings_n: float,
    channel_slope: float,
) -> float:
    """
    Bankfull stage above the channel bed (m) from Manning's equation.

    Assumes a wide rectangular cross-section: hydraulic radius R ≈ depth d
    (valid when w/d > 5).

        Q ≈ (1/n) · w · d^(5/3) · √S
        d = (Q · n / (w · √S))^(3/5)

    Parameters
    ----------
    q_peak_m3s    : discharge (m³/s)
    channel_width_m : channel width (m)
    mannings_n    : Manning's roughness coefficient
    channel_slope : dimensionless channel slope (m/m)

    Returns
    -------
    stage_m : water depth above channel bed (m), >= 0
    """
    if q_peak_m3s <= 0.0:
        return 0.0
    if channel_width_m <= 0 or mannings_n <= 0 or channel_slope <= 0:
        raise ValueError("Channel parameters must be positive.")
    d = (q_peak_m3s * mannings_n / (channel_width_m * channel_slope ** 0.5)) ** 0.6
    if channel_width_m / d < 5:
        warnings.warn(
            f"  [warn] w/d = {channel_width_m / d:.1f} < 5; wide-channel "
            "approximation may underestimate stage.",
            stacklevel=2,
        )
    return float(d)
