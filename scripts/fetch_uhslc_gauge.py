"""
Derive coastal water-level return periods for Singapore from UHSLC tide gauge data.

Data source
-----------
UHSLC (University of Hawaii Sea Level Center) — Research Quality Dataset
  Station   : Tanjong Pagar, Singapore (UHSLC ID 699)
  Position  : 1.262 N, 103.853 E
  Record    : 1984-01-01 to ~2023-12-31  (~40 years, hourly)
  Units     : millimetres (relative to local gauge datum)
  ERDDAP    : https://uhslc.soest.hawaii.edu/erddap/tabledap/global_hourly_rqds

Method
------
1. Fetch hourly sea-level data year-by-year from the UHSLC ERDDAP service.
2. Remove the long-term record mean (millimetres → metres anomaly above MSL).
   This converts gauge-datum values to anomalies centred on 0 m (≈ EGM2008
   MSL, the vertical datum of the Copernicus DEM used in the flood model).
3. Compute annual maxima of the de-meaned record.
4. Fit a Generalised Extreme Value (GEV) distribution to the annual maxima
   using Maximum-Likelihood Estimation (scipy.stats.genextreme).
5. Extract water-level quantiles for the standard return periods.
6. Write the derived levels back into the baseline hazard CSV, replacing the
   placeholder coastal rows.

Why de-mean instead of de-tide?
  Singapore's tidal range (~3.2 m spring, ~1.8 m neap) dominates the signal.
  Annual maxima of total water level (tide + surge) represent the largest
  plausible coastal inundation event that year — this is the quantity that
  should seed the bathtub coastal flood model (which also treats the DEM
  relative to MSL = 0 m).

Usage
-----
    python scripts/fetch_gesla_singapore.py \\
        --output data/singapore_hazard_baseline_template.csv

    # Dry-run: print derived levels without overwriting the CSV
    python scripts/fetch_gesla_singapore.py --dry-run

Options
-------
--output        Path to the hazard baseline CSV to update (coastal rows replaced).
--start-year    First year to fetch (default 1984).
--end-year      Last year to fetch (default 2023).
--min-years     Minimum valid annual-maxima years required for GEV fit (default 15).
--dry-run       Print return period levels without modifying the CSV.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import click
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.convert_datum import (
    MSL_TO_EGM2008_SINGAPORE,
    make_datum_note,
    msl_anomaly_to_egm2008,
)

RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]

# UHSLC ERDDAP endpoints
_ERDDAP_DATASETS = {
    "rqds": "https://uhslc.soest.hawaii.edu/erddap/tabledap/global_hourly_rqds.csv",
    "fast": "https://uhslc.soest.hawaii.edu/erddap/tabledap/global_hourly_fast.csv",
}
ERDDAP_BASE = _ERDDAP_DATASETS["rqds"]   # kept for backward compatibility
_DEFAULT_UHSLC_ID = 699   # Tanjong Pagar, Singapore (overridden by --uhslc-id)
MISSING_MM = -32767        # UHSLC fill value (millimetres)


def fetch_year_uhslc(
    session,
    year: int,
    uhslc_id: int = _DEFAULT_UHSLC_ID,
    erddap_url: str = _ERDDAP_DATASETS["rqds"],
) -> pd.Series | None:
    """
    Fetch one calendar year of hourly sea-level data from UHSLC ERDDAP.

    Returns a pandas Series (DatetimeIndex UTC, values in metres) with NaN
    for missing observations, or None on HTTP/parse error.
    """
    query = (
        f"time,sea_level"
        f"&uhslc_id={uhslc_id}"
        f'&time>={year}-01-01T00:00:00Z'
        f'&time<={year}-12-31T23:59:59Z'
        f'&orderBy("time")'
    )
    url = erddap_url + "?" + query
    try:
        resp = session.get(url, timeout=60)
    except Exception as exc:
        click.echo(f"  {year}: request error - {exc}", err=True)
        return None

    if resp.status_code == 404:
        # ERDDAP returns 404 when query produces 0 rows
        return None
    if resp.status_code != 200:
        click.echo(f"  {year}: HTTP {resp.status_code}", err=True)
        return None

    try:
        # Skip the units header row (row index 1) after the column-name row
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text), skiprows=[1])
    except Exception as exc:
        click.echo(f"  {year}: CSV parse error - {exc}", err=True)
        return None

    if df.empty or "sea_level" not in df.columns or "time" not in df.columns:
        return None

    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df = df.dropna(subset=["time"]).set_index("time")
    sl = pd.to_numeric(df["sea_level"], errors="coerce")

    # Replace UHSLC fill value with NaN and convert mm → m
    sl = sl.replace(MISSING_MM, np.nan) / 1000.0
    return sl


def compute_annual_maxima(
    years_data: dict[int, pd.Series],
    long_term_mean_m: float,
    min_coverage: float = 0.5,
) -> dict[int, float]:
    """
    Compute annual maxima of the de-meaned sea-level anomaly.

    Parameters
    ----------
    years_data : year → hourly Series (metres, gauge datum)
    long_term_mean_m : overall mean of the record (metres)
    min_coverage : minimum fraction of hours in a year required to keep it

    Returns
    -------
    year → annual maximum anomaly (metres above MSL)
    """
    results: dict[int, float] = {}
    for year, series in sorted(years_data.items()):
        valid = series.dropna()
        # Require at least min_coverage of a full year of hourly data
        min_hours = int(8760 * min_coverage)
        if len(valid) < min_hours:
            continue
        anom = valid - long_term_mean_m
        results[year] = float(anom.max())
    return results


def fit_gev(annual_maxima: np.ndarray) -> tuple[float, float, float]:
    """
    Fit GEV via MLE.  Returns (shape c, loc mu, scale sigma) in scipy convention.
    """
    from scipy.stats import genextreme

    c, loc, scale = genextreme.fit(annual_maxima)
    if scale <= 0:
        raise ValueError(f"GEV fit returned non-positive scale: {scale:.4f}")
    return float(c), float(loc), float(scale)


def gev_return_level(c: float, loc: float, scale: float, return_period: float) -> float:
    """Return level x_T for return period T (years): F(x_T) = 1 - 1/T."""
    from scipy.stats import genextreme

    return float(genextreme.ppf(1.0 - 1.0 / return_period, c, loc=loc, scale=scale))


@click.command()
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=Path("data/singapore_hazard_baseline_template.csv"),
    show_default=True,
    help="Hazard baseline CSV to update with derived coastal return period levels.",
)
@click.option(
    "--dataset",
    "dataset",
    type=click.Choice(["rqds", "fast"]),
    default="rqds",
    show_default=True,
    help=(
        "UHSLC ERDDAP dataset to query.  "
        "'rqds' = Research Quality (default, stricter QC).  "
        "'fast' = Fast-Delivery (broader station coverage, looser QC).  "
        "Use 'fast' for stations not present in the RQ dataset (e.g. Ko Lak, Thailand)."
    ),
)
@click.option(
    "--uhslc-id",
    "uhslc_id",
    type=int,
    default=_DEFAULT_UHSLC_ID,
    show_default=True,
    help=(
        "UHSLC Research Quality station ID to fetch.  "
        "Default 699 = Tanjong Pagar, Singapore.  "
        "Look up other IDs at https://uhslc.soest.hawaii.edu/data/ ."
    ),
)
@click.option(
    "--gauge-name",
    "gauge_name",
    type=str,
    default=None,
    help=(
        "Human-readable station name written into the CSV source_note field.  "
        "Defaults to 'UHSLC station <id>' when not supplied."
    ),
)
@click.option(
    "--start-year",
    type=int,
    default=1984,
    show_default=True,
    help="First year to fetch from UHSLC ERDDAP.",
)
@click.option(
    "--end-year",
    type=int,
    default=2023,
    show_default=True,
    help="Last year to fetch (inclusive).",
)
@click.option(
    "--min-years",
    type=int,
    default=15,
    show_default=True,
    help="Minimum number of valid annual-maxima years required to fit GEV.",
)
@click.option(
    "--msl-to-egm2008-offset",
    "msl_to_egm2008_offset",
    type=float,
    default=MSL_TO_EGM2008_SINGAPORE,
    show_default=True,
    help=(
        "Height of local MSL above the EGM2008 geoid at the tide gauge, in metres "
        "(positive = MSL is above EGM2008).  This offset bridges the gap between "
        "the de-meaned tide-gauge anomaly (relative to local MSL) and the vertical "
        "datum of the Copernicus DEM (EGM2008).  "
        "At Tanjong Pagar the MDT offset is approximately +0.03 to +0.06 m from "
        "CNES-CLS18 / DTU18 MDT products; the default of 0.0 m (MSL ≈ EGM2008) "
        "introduces an error well within the DEM's own ±1–2 m vertical uncertainty "
        "for a screening model.  Supply 0.05 as a best-estimate correction, or "
        "replace with a survey-grade value from SLA Singapore for production use."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print derived return period levels without modifying the CSV.",
)
def cli(
    output_path: Path,
    dataset: str,
    uhslc_id: int,
    gauge_name: str | None,
    start_year: int,
    end_year: int,
    min_years: int,
    msl_to_egm2008_offset: float,
    dry_run: bool,
) -> None:
    if gauge_name is None:
        gauge_name = f"UHSLC station {uhslc_id}"
    erddap_url = _ERDDAP_DATASETS[dataset]
    try:
        import requests
    except ImportError:
        raise click.ClickException("requests is required: pip install requests")
    try:
        from scipy.stats import genextreme  # noqa: F401
    except ImportError:
        raise click.ClickException("scipy is required: pip install scipy")

    click.echo(
        f"Fetching UHSLC tide-gauge data: {gauge_name} (ID {uhslc_id}, "
        f"dataset={dataset}), {start_year}-{end_year} ..."
    )

    session = requests.Session()
    session.headers.update({"User-Agent": "CityFloodModel/1.0 (research)"})

    years_data: dict[int, pd.Series] = {}
    all_values: list[float] = []

    for year in range(start_year, end_year + 1):
        series = fetch_year_uhslc(session, year, uhslc_id=uhslc_id, erddap_url=erddap_url)
        if series is None or series.empty:
            click.echo(f"  {year}: no data")
            continue
        n_valid = int(series.notna().sum())
        click.echo(
            f"  {year}: {n_valid:,} valid hourly obs, "
            f"range [{series.min():.3f}, {series.max():.3f}] m (gauge datum)"
        )
        years_data[year] = series
        all_values.extend(series.dropna().tolist())
        time.sleep(0.3)  # polite delay

    if not years_data:
        raise click.ClickException("No data downloaded - check network access.")

    # Long-term mean across the full record (gauge datum → MSL reference)
    long_term_mean_m = float(np.mean(all_values))
    click.echo(
        f"\nLong-term record mean: {long_term_mean_m:.3f} m (gauge datum) "
        f"-> used as MSL reference"
    )

    # Annual maxima of the de-meaned anomaly
    ann_max = compute_annual_maxima(years_data, long_term_mean_m, min_coverage=0.5)
    years_ok = sorted(ann_max.keys())
    n_years = len(ann_max)
    click.echo(f"{n_years} years of annual maxima computed ({years_ok[0]}-{years_ok[-1]}).")

    if n_years < min_years:
        raise click.ClickException(
            f"Only {n_years} valid years - need at least {min_years}. "
            "Widen the year range or lower --min-years."
        )

    maxima_arr = np.array([ann_max[y] for y in years_ok], dtype=np.float64)
    click.echo(
        f"Annual maxima (anomaly above MSL): "
        f"mean={maxima_arr.mean():.3f} m, "
        f"std={maxima_arr.std():.3f} m, "
        f"min={maxima_arr.min():.3f} m, "
        f"max={maxima_arr.max():.3f} m"
    )

    try:
        c, loc, scale = fit_gev(maxima_arr)
    except Exception as exc:
        raise click.ClickException(f"GEV fit failed: {exc}")

    # In scipy convention, genextreme shape = -ξ (negated tail index)
    xi = -c
    click.echo(f"GEV fit (MLE): xi={xi:.4f}  mu(loc)={loc:.4f} m  sigma(scale)={scale:.4f} m")

    datum_note = make_datum_note(
        source_datum=f"UHSLC_station_{uhslc_id}_de-meaned_to_MSL",
        msl_to_egm2008_offset=msl_to_egm2008_offset,
        extra=f"gauge_long_term_mean={long_term_mean_m:.4f}m",
    )

    rows = []
    click.echo(
        f"\nReturn period levels (EGM2008; "
        f"msl_to_egm2008_offset={msl_to_egm2008_offset:+.4f} m):"
    )
    click.echo(f"  {'RP (yr)':>8}  {'MSL anomaly (m)':>16}  {'EGM2008 (m)':>12}")
    click.echo(f"  {'-'*8}  {'-'*16}  {'-'*12}")
    for rp in RETURN_PERIODS:
        level_msl = gev_return_level(c, loc, scale, rp)
        level_egm2008 = msl_anomaly_to_egm2008(level_msl, msl_to_egm2008_offset)
        # Clamp: flood model requires a positive water level above the datum surface
        level_egm2008 = max(0.05, level_egm2008)
        click.echo(
            f"  {rp:>8d}  {level_msl:>16.3f}  {level_egm2008:>12.3f}"
        )
        rows.append(
            {
                "hazard_type": "coastal",
                "return_period": rp,
                "baseline_water_level_m": round(level_egm2008, 3),
                "datum_note": datum_note,
                "source_note": (
                    f"UHSLC RQ {gauge_name} (ID {uhslc_id}); "
                    f"GEV fit to {n_years} annual maxima of de-meaned hourly sea level "
                    f"({years_ok[0]}-{years_ok[-1]}); "
                    f"xi={xi:.4f}, mu={loc:.4f} m, sigma={scale:.4f} m; "
                    f"msl_to_egm2008_offset={msl_to_egm2008_offset:+.4f} m applied"
                ),
            }
        )

    if dry_run:
        click.echo("\n[Dry run] No files modified.")
        return

    # Read existing CSV, replace coastal rows, write back
    if output_path.exists():
        existing = pd.read_csv(output_path)
        non_coastal = existing[existing["hazard_type"] != "coastal"].copy()
    else:
        non_coastal = pd.DataFrame(
            columns=["hazard_type", "return_period", "baseline_water_level_m", "source_note"]
        )

    new_coastal = pd.DataFrame(rows)
    updated = pd.concat([non_coastal, new_coastal], ignore_index=True)
    updated = updated.sort_values(["hazard_type", "return_period"]).reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    updated.to_csv(output_path, index=False)
    click.echo(f"\nUpdated {output_path} with {len(rows)} coastal return-period rows ({gauge_name}).")


if __name__ == "__main__":
    cli()
