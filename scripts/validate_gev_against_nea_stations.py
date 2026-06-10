"""
Track A -- Validate ERA5 GEV/Gumbel fit against NEA station annual maxima.

Data source
-----------
NEA Historical Rainfall datasets on data.gov.sg (collection 2279).
  - 5-minute interval rainfall (mm) from ~60-96 automated stations.
  - Coverage: 2016-2024 (9 years).
  - Free API key registration: https://data.gov.sg
  - CKAN datastore_search endpoint with pagination.

Method
------
1. Download each year's 5-minute station data via the CKAN API, paginated
   in chunks of 32 000 rows.  Progress is cached to Parquet so partial
   runs can be resumed.
2. For each station-year compute the annual maximum of the 6-hour rolling
   accumulation (same window as the ERA5 fit).
3. Pool station-years into a combined sample and fit a GEV via MLE.
4. Compare station-derived GEV quantiles against the ERA5-fitted Gumbel
   at each standard return period (RP2-RP1000).
5. Compute a multiplicative bias-correction factor per return period:
       bc_factor(T) = Q_station(T) / Q_era5(T)
6. Write a summary CSV and PDF validation figure.

Rate limiting
-------------
Without an API key the CKAN endpoint returns HTTP 429 after ~1 request.
A free API key from https://data.gov.sg/profile raises the limit
substantially.  Pass the key with --api-key or set the environment
variable DATA_GOV_SG_API_KEY.

The download step respects a configurable inter-request delay
(--request-delay, default 1.5 s) and retries with exponential back-off
on 429 responses.  Completed year-level Parquet files are never
re-downloaded, so you can safely interrupt and resume.

Usage
-----
    # Full run (downloads ~2-10 GB, takes ~30 min with API key)
    python scripts/validate_gev_against_nea_stations.py \\
        --api-key YOUR_KEY \\
        --cache-dir cache/nea_rainfall \\
        --baseline data/singapore_hazard_baseline_template.csv \\
        --out-dir outputs/validation

    # Skip download, re-use cached Parquet files
    python scripts/validate_gev_against_nea_stations.py \\
        --no-download \\
        --cache-dir cache/nea_rainfall \\
        --baseline data/singapore_hazard_baseline_template.csv \\
        --out-dir outputs/validation

    # Dry-run: just print bias table, no figures
    python scripts/validate_gev_against_nea_stations.py \\
        --no-download --dry-run \\
        --cache-dir cache/nea_rainfall \\
        --baseline data/singapore_hazard_baseline_template.csv
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import click
import numpy as np
import pandas as pd

# --- dataset IDs ------------------------------------------------------------
# data.gov.sg collection 2279 -- child dataset IDs by year
YEAR_TO_DATASET: dict[int, str] = {
    2016: "d_79a6f0fb898996d415b207bb26ed0fa6",
    2017: "d_1990a5a1aeaf3dd243cf4dae294a61c4",
    2018: "d_024fb501ce7092b71bb713eaf54fa7eb",
    2019: "d_61995f092320e7155b7528050880b502",
    2020: "d_9e7de44094f876f6804b8b5bcee45c81",
    2021: "d_3b41598f74f1f11fc3430348fea51af5",
    2022: "d_42d64cc6c176ace1c52fbb40b9ede302",
    2023: "d_f864cc30d58b467db83659ad17c737bf",
    2024: "d_a0b69d3e02576a1fd0ab673e71f83507",
}

CKAN_SEARCH_URL = "https://data.gov.sg/api/action/datastore_search"
CHUNK_SIZE = 20_000         # rows per API request (413 above ~24k)
WINDOW_H = 6                # accumulation window -- must match ERA5 fit
RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]


# -----------------------------------------------------------------------------
# Download
# -----------------------------------------------------------------------------

def _get(session, url: str, params: dict, max_retries: int = 10, base_delay: float = 15.0):
    """GET with exponential back-off on 429 (rate limit) and 503 (overload)."""
    for attempt in range(max_retries):
        resp = session.get(url, params=params, timeout=60)
        if resp.status_code == 200:
            return resp
        if resp.status_code in (429, 503):
            wait = base_delay * (2 ** min(attempt, 5))  # cap at ~8 min
            label = "rate-limited" if resp.status_code == 429 else "server overloaded"
            click.echo(f"    [{resp.status_code}] {label} -- waiting {wait:.0f}s (attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
    raise click.ClickException(f"Exceeded {max_retries} retries for {url} params={params}")


def download_year(
    year: int,
    cache_dir: Path,
    api_key: str | None,
    request_delay: float,
) -> Path:
    """
    Download all rows for *year* from the CKAN API and save to Parquet.

    Returns the path to the cached Parquet file.  If the file already exists
    it is returned immediately without any network access.
    """
    try:
        import requests
    except ImportError:
        raise ImportError("requests is required: pip install requests")

    cache_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = cache_dir / f"nea_rainfall_{year}.parquet"
    if parquet_path.exists():
        click.echo(f"  {year}: cached - {parquet_path}")
        return parquet_path

    dataset_id = YEAR_TO_DATASET[year]
    headers: dict[str, str] = {"User-Agent": "Singapore-FloodModel/1.0 (research)"}
    if api_key:
        headers["x-api-key"] = api_key

    session = requests.Session()
    session.headers.update(headers)

    click.echo(f"  {year}: downloading dataset {dataset_id} ...")

    # Only fetch the columns we need -- reduces payload ~60%
    fields = "timestamp,station_id,station_name,location_longitude,location_latitude,reading_value"

    # First request -- discover total row count
    params = {"resource_id": dataset_id, "limit": 1, "offset": 0, "fields": fields}
    resp = _get(session, CKAN_SEARCH_URL, params, base_delay=15.0)
    total: int = resp.json()["result"]["total"]
    click.echo(f"    total rows: {total:,}")

    chunks: list[pd.DataFrame] = []
    offset = 0
    while offset < total:
        params = {"resource_id": dataset_id, "limit": CHUNK_SIZE, "offset": offset,
                  "fields": fields}
        resp = _get(session, CKAN_SEARCH_URL, params, base_delay=15.0)
        records = resp.json()["result"]["records"]
        if not records:
            break
        chunks.append(pd.DataFrame(records))
        offset += len(records)
        pct = 100 * offset / total
        click.echo(f"    {offset:,}/{total:,}  ({pct:.1f}%)", nl=True)
        time.sleep(request_delay)

    df = pd.concat(chunks, ignore_index=True)

    # Keep only the columns we need to minimise storage
    keep = ["timestamp", "station_id", "station_name", "location_longitude",
            "location_latitude", "reading_value"]
    df = df[[c for c in keep if c in df.columns]]
    df["reading_value"] = pd.to_numeric(df["reading_value"], errors="coerce")
    df.to_parquet(parquet_path, index=False)
    click.echo(f"    saved - {parquet_path}  ({parquet_path.stat().st_size / 1e6:.1f} MB)")
    return parquet_path


# -----------------------------------------------------------------------------
# Processing
# -----------------------------------------------------------------------------

def compute_annual_maxima_from_parquet(parquet_path: Path, year: int) -> pd.DataFrame:
    """
    Load one year's Parquet, resample to hourly per station, compute
    6-hour rolling max accumulation, and return the annual maximum per station.

    Returns
    -------
    DataFrame with columns: station_id, station_name, lon, lat, year,
                            ann_max_6h_mm
    """
    df = pd.read_parquet(parquet_path)

    # Parse timestamps -- data is SGT (UTC+8); convert to UTC for consistency
    df["ts"] = pd.to_datetime(df["timestamp"], utc=False, errors="coerce")
    if df["ts"].dt.tz is None:
        # Assume SGT -- localize then convert
        df["ts"] = df["ts"].dt.tz_localize("Asia/Singapore", ambiguous="NaT",
                                            nonexistent="NaT").dt.tz_convert("UTC")
    df = df.dropna(subset=["ts", "reading_value"])
    df["reading_value"] = df["reading_value"].clip(lower=0)  # remove negatives

    rows = []
    for station_id, grp in df.groupby("station_id"):
        grp = grp.sort_values("ts").set_index("ts")["reading_value"]

        # 5-min readings - hourly totals (sum; min_count=6 requires -6 valid obs)
        hourly = grp.resample("1h").sum(min_count=6)

        # 6-hour rolling accumulation
        acc6h = hourly.rolling(window=WINDOW_H, min_periods=max(1, WINDOW_H // 2)).sum()

        if acc6h.notna().sum() < 100:
            continue  # skip stations with almost no data this year

        ann_max = float(acc6h.max(skipna=True))
        meta = df[df["station_id"] == station_id].iloc[0]

        rows.append({
            "station_id": station_id,
            "station_name": meta.get("station_name", ""),
            "lon": float(meta.get("location_longitude", np.nan)),
            "lat": float(meta.get("location_latitude", np.nan)),
            "year": year,
            "ann_max_6h_mm": ann_max,
        })

    if not rows:
        return pd.DataFrame(columns=["station_id", "station_name", "lon", "lat",
                                     "year", "ann_max_6h_mm"])
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# Statistics
# -----------------------------------------------------------------------------

def fit_gev(maxima: np.ndarray) -> tuple[float, float, float]:
    """Fit GEV via MLE. Returns (c, loc, scale) in scipy convention (c = -xi)."""
    from scipy.stats import genextreme
    c, loc, scale = genextreme.fit(maxima)
    if scale <= 0:
        raise ValueError(f"GEV fit non-positive scale={scale:.4f}")
    return float(c), float(loc), float(scale)


def gev_quantile(c: float, loc: float, scale: float, rp: float) -> float:
    from scipy.stats import genextreme
    return float(genextreme.ppf(1.0 - 1.0 / rp, c, loc=loc, scale=scale))


def gumbel_quantile(loc: float, scale: float, rp: float) -> float:
    """Gumbel (GEV xi=0) quantile: x = mu - sigma-ln(-ln(1-1/T))."""
    return loc - scale * np.log(-np.log(1.0 - 1.0 / rp))


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

@click.command()
@click.option(
    "--baseline",
    "baseline_path",
    type=click.Path(exists=True, path_type=Path),
    default=Path("data/singapore_hazard_baseline_template.csv"),
    show_default=True,
    help="Hazard baseline CSV produced by fit_pluvial_baseline_era5.py.",
)
@click.option(
    "--cache-dir",
    type=click.Path(path_type=Path),
    default=Path("cache/nea_rainfall"),
    show_default=True,
    help="Directory for cached per-year Parquet files.",
)
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=Path("outputs/validation"),
    show_default=True,
)
@click.option(
    "--api-key",
    "api_key",
    default=None,
    envvar="DATA_GOV_SG_API_KEY",
    help=(
        "data.gov.sg API key (free registration at https://data.gov.sg/profile). "
        "Also reads DATA_GOV_SG_API_KEY environment variable.  Without a key the "
        "CKAN endpoint rate-limits aggressively."
    ),
)
@click.option(
    "--years",
    default=",".join(str(y) for y in sorted(YEAR_TO_DATASET)),
    show_default=True,
    help="Comma-separated list of years to download/process.",
)
@click.option(
    "--request-delay",
    type=float,
    default=1.5,
    show_default=True,
    help="Seconds to wait between paginated API requests.",
)
@click.option(
    "--download/--no-download",
    "do_download",
    default=True,
    show_default=True,
    help="Download fresh data or rely entirely on existing cache.",
)
@click.option(
    "--min-station-years",
    type=int,
    default=5,
    show_default=True,
    help="Minimum station-year records required to include a station in the pooled GEV fit.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print bias table without writing figures.",
)
def cli(
    baseline_path: Path,
    cache_dir: Path,
    out_dir: Path,
    api_key: str | None,
    years: str,
    request_delay: float,
    do_download: bool,
    min_station_years: int,
    dry_run: bool,
) -> None:
    year_list = sorted(int(y) for y in years.split(","))

    # -- 0. Load ERA5 baseline parameters -------------------------------------
    baseline = pd.read_csv(baseline_path)
    pluvial = baseline[baseline["hazard_type"] == "pluvial"].copy()
    if pluvial.empty:
        raise click.ClickException("No pluvial rows in baseline CSV.")
    # All rows share the same GEV parameters (fitted once to pooled ERA5 maxima)
    era5_c   = float(pluvial["gev_shape"].iloc[0])   # scipy: c = -xi
    era5_loc = float(pluvial["gev_loc_mm"].iloc[0])
    era5_sca = float(pluvial["gev_scale_mm"].iloc[0])
    era5_xi  = -era5_c
    click.echo(
        f"ERA5 GEV: xi={era5_xi:.4f}  mu={era5_loc:.2f} mm  sigma={era5_sca:.2f} mm"
    )

    # -- 1. Download / load station data --------------------------------------
    all_maxima: list[pd.DataFrame] = []
    click.echo(f"\nProcessing {len(year_list)} years: {year_list}")

    for year in year_list:
        if year not in YEAR_TO_DATASET:
            click.echo(f"  {year}: no dataset ID -- skipping")
            continue

        parquet_path = cache_dir / f"nea_rainfall_{year}.parquet"

        if do_download and not parquet_path.exists():
            if not api_key:
                click.echo(
                    f"  [warn] No API key set.  Attempting download for {year} "
                    "-- expect heavy rate-limiting.  Register at "
                    "https://data.gov.sg/profile and pass --api-key or set "
                    "DATA_GOV_SG_API_KEY.",
                    err=True,
                )
            try:
                download_year(year, cache_dir, api_key, request_delay)
            except Exception as exc:
                click.echo(f"  {year}: download failed -- {exc}.  Skipping.", err=True)
                continue

        if not parquet_path.exists():
            click.echo(f"  {year}: no cache file, skipping (run with --download).")
            continue

        click.echo(f"  {year}: computing annual maxima from {parquet_path.name} ...")
        try:
            yr_max = compute_annual_maxima_from_parquet(parquet_path, year)
            if yr_max.empty:
                click.echo(f"  {year}: no stations passed coverage threshold -- skipping.")
                continue
            n_stations = len(yr_max)
            click.echo(
                f"    {n_stations} stations  "
                f"max={yr_max['ann_max_6h_mm'].max():.1f} mm  "
                f"median={yr_max['ann_max_6h_mm'].median():.1f} mm"
            )
            all_maxima.append(yr_max)
        except Exception as exc:
            click.echo(f"  {year}: processing failed -- {exc}.  Skipping.", err=True)

    if not all_maxima:
        raise click.ClickException(
            "No station data processed.  Run with --download or check --cache-dir."
        )

    combined = pd.concat(all_maxima, ignore_index=True)
    n_station_years = len(combined)
    n_stations_total = combined["station_id"].nunique()
    click.echo(
        f"\nCombined sample: {n_station_years} station-years from "
        f"{n_stations_total} stations ({combined['year'].min()}-{combined['year'].max()})"
    )

    # -- 2. Filter stations with enough years ---------------------------------
    counts = combined.groupby("station_id")["year"].count()
    keep_stations = counts[counts >= min_station_years].index
    filtered = combined[combined["station_id"].isin(keep_stations)]
    click.echo(
        f"After filtering (-{min_station_years} years): "
        f"{len(filtered)} station-years from {filtered['station_id'].nunique()} stations"
    )

    if len(filtered) < 10:
        raise click.ClickException(
            f"Only {len(filtered)} station-years after filtering -- "
            "lower --min-station-years or download more years."
        )

    maxima_arr = filtered["ann_max_6h_mm"].dropna().values

    # -- 3. Fit GEV to station pool --------------------------------------------
    try:
        sta_c, sta_loc, sta_sca = fit_gev(maxima_arr)
    except Exception as exc:
        raise click.ClickException(f"GEV fit failed: {exc}")

    sta_xi = -sta_c
    click.echo(
        f"Station GEV (MLE): xi={sta_xi:.4f}  mu={sta_loc:.2f} mm  sigma={sta_sca:.2f} mm"
    )

    # -- 4. Return-period comparison table ------------------------------------
    click.echo(
        f"\n{'RP':>6}  {'ERA5 (mm)':>12}  {'Station (mm)':>14}  {'Bias factor':>12}"
    )
    click.echo(f"  {'-'*6}  {'-'*12}  {'-'*14}  {'-'*12}")

    rp_rows = []
    for rp in RETURN_PERIODS:
        era5_q   = gev_quantile(era5_c, era5_loc, era5_sca, rp)
        sta_q    = gev_quantile(sta_c,  sta_loc,  sta_sca,  rp)
        bc       = sta_q / era5_q if era5_q > 0 else np.nan
        click.echo(f"  {rp:>6d}  {era5_q:>12.1f}  {sta_q:>14.1f}  {bc:>12.3f}")
        rp_rows.append({
            "return_period": rp,
            "era5_design_rainfall_mm": round(era5_q, 2),
            "station_design_rainfall_mm": round(sta_q, 2),
            "bias_correction_factor": round(bc, 4),
        })

    bias_df = pd.DataFrame(rp_rows)

    if dry_run:
        click.echo("\n[Dry run] No files written.")
        return

    # -- 5. Write outputs ------------------------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)

    # Bias-correction table CSV
    csv_path = out_dir / "nea_gev_bias_correction.csv"
    bias_df.to_csv(csv_path, index=False)
    click.echo(f"\nBias-correction table - {csv_path}")

    # Station annual maxima CSV
    maxima_csv = out_dir / "nea_station_annual_maxima.csv"
    combined.to_csv(maxima_csv, index=False)
    click.echo(f"Station annual maxima  - {maxima_csv}")

    # -- 6. Validation figure --------------------------------------------------
    _plot_validation(
        maxima_arr=maxima_arr,
        era5_c=era5_c, era5_loc=era5_loc, era5_sca=era5_sca,
        sta_c=sta_c,   sta_loc=sta_loc,   sta_sca=sta_sca,
        bias_df=bias_df,
        combined=combined,
        out_dir=out_dir,
        n_years=len(year_list),
    )


def _plot_validation(
    maxima_arr: np.ndarray,
    era5_c: float, era5_loc: float, era5_sca: float,
    sta_c: float,  sta_loc: float,  sta_sca: float,
    bias_df: pd.DataFrame,
    combined: pd.DataFrame,
    out_dir: Path,
    n_years: int,
) -> None:
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from scipy.stats import genextreme

    fig = plt.figure(figsize=(14, 10), dpi=150)
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.38, wspace=0.32)

    rp_range = np.logspace(np.log10(1.5), np.log10(2000), 200)
    era5_rl  = [gev_quantile(era5_c, era5_loc, era5_sca, t) for t in rp_range]
    sta_rl   = [gev_quantile(sta_c,  sta_loc,  sta_sca,  t) for t in rp_range]

    # -- Panel A: return-level plot --------------------------------------------
    ax_rl = fig.add_subplot(gs[0, 0])
    ax_rl.semilogx(rp_range, era5_rl, "b-",  lw=2, label="ERA5 GEV")
    ax_rl.semilogx(rp_range, sta_rl,  "r-",  lw=2, label="Station GEV (pooled)")

    # Empirical plotting positions (Weibull: i/(n+1))
    sorted_max = np.sort(maxima_arr)
    n = len(sorted_max)
    emp_probs = np.arange(1, n + 1) / (n + 1)
    emp_rp    = 1.0 / (1.0 - emp_probs)
    ax_rl.scatter(emp_rp, sorted_max, s=8, color="grey", alpha=0.5,
                  label=f"Station obs. (n={n})", zorder=5)

    ax_rl.set_xlabel("Return period (years)", fontsize=9)
    ax_rl.set_ylabel("6-hour rainfall (mm)", fontsize=9)
    ax_rl.set_title("A.  Return-level comparison", fontsize=10)
    ax_rl.legend(fontsize=8)
    ax_rl.grid(True, which="both", alpha=0.3)
    ax_rl.set_xlim(1.5, 2000)

    # -- Panel B: bias-correction factors -------------------------------------
    ax_bc = fig.add_subplot(gs[0, 1])
    rps_plot = bias_df["return_period"].values
    bcs_plot = bias_df["bias_correction_factor"].values
    ax_bc.axhline(1.0, color="grey", lw=1, ls="--", label="No bias")
    ax_bc.semilogx(rps_plot, bcs_plot, "ro-", lw=2, ms=6)
    for rp, bc in zip(rps_plot, bcs_plot):
        ax_bc.annotate(f"{bc:.2f}", (rp, bc), textcoords="offset points",
                       xytext=(4, 4), fontsize=7)
    ax_bc.set_xlabel("Return period (years)", fontsize=9)
    ax_bc.set_ylabel("Bias factor  (station / ERA5)", fontsize=9)
    ax_bc.set_title("B.  Multiplicative bias-correction factor", fontsize=10)
    ax_bc.legend(fontsize=8)
    ax_bc.grid(True, which="both", alpha=0.3)
    ax_bc.set_xlim(1.5, 2000)

    # -- Panel C: histogram of station annual maxima ---------------------------
    ax_hist = fig.add_subplot(gs[1, 0])
    ax_hist.hist(maxima_arr, bins=30, color="steelblue", edgecolor="white",
                 alpha=0.8, density=True, label="Station pool")
    x_pdf = np.linspace(maxima_arr.min() * 0.8, maxima_arr.max() * 1.2, 200)
    ax_hist.plot(x_pdf, genextreme.pdf(x_pdf, era5_c, loc=era5_loc, scale=era5_sca),
                 "b-", lw=2, label="ERA5 GEV PDF")
    ax_hist.plot(x_pdf, genextreme.pdf(x_pdf, sta_c, loc=sta_loc, scale=sta_sca),
                 "r-", lw=2, label="Station GEV PDF")
    ax_hist.set_xlabel("6-hour annual maximum rainfall (mm)", fontsize=9)
    ax_hist.set_ylabel("Density", fontsize=9)
    ax_hist.set_title("C.  Annual maxima distribution", fontsize=10)
    ax_hist.legend(fontsize=8)
    ax_hist.grid(True, alpha=0.3)

    # -- Panel D: station map --------------------------------------------------
    ax_map = fig.add_subplot(gs[1, 1])
    station_means = combined.groupby("station_id").agg(
        lon=("lon", "first"), lat=("lat", "first"),
        mean_max=("ann_max_6h_mm", "mean"),
        n_years=("year", "count"),
    ).reset_index()
    sc = ax_map.scatter(
        station_means["lon"], station_means["lat"],
        c=station_means["mean_max"], cmap="YlOrRd",
        s=station_means["n_years"] * 12,
        vmin=maxima_arr.min() * 0.8, vmax=maxima_arr.max() * 0.9,
        edgecolors="grey", linewidths=0.4, alpha=0.85, zorder=5,
    )
    cbar = fig.colorbar(sc, ax=ax_map, fraction=0.035, pad=0.04)
    cbar.set_label("Mean 6h annual max (mm)", fontsize=8)
    ax_map.set_xlabel("Longitude", fontsize=9)
    ax_map.set_ylabel("Latitude", fontsize=9)
    ax_map.set_title("D.  Station locations (colour = mean max, size = n-years)", fontsize=9)
    ax_map.grid(True, alpha=0.3)

    # -- GEV parameter box -----------------------------------------------------
    era5_xi = -era5_c
    sta_xi  = -sta_c
    txt = (
        f"ERA5 GEV:    xi={era5_xi:.3f}  mu={era5_loc:.1f} mm  sigma={era5_sca:.1f} mm\n"
        f"Station GEV: xi={sta_xi:.3f}  mu={sta_loc:.1f} mm  sigma={sta_sca:.1f} mm\n"
        f"Station-years: {len(maxima_arr)}  (n_years data={n_years})"
    )
    fig.text(0.5, 0.005, txt, ha="center", va="bottom", fontsize=8,
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#f0f0f0", alpha=0.8))

    fig.suptitle(
        "Track A -- ERA5 GEV vs NEA Station Annual Maxima (6-hour rainfall, Singapore)",
        fontsize=12, y=1.01,
    )

    out_path = out_dir / "validation_gev_nea_stations.png"
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    click.echo(f"Validation figure      - {out_path}")


if __name__ == "__main__":
    cli()
