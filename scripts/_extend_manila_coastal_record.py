"""
One-off Manila coastal record extension.

Background
----------
Manila's coastal baseline is currently fit on UHSLC Research-Quality (RQ)
dataset station 304 (Fort Santiago) for 1985-2001 — 17 valid years.  The
RQ archive stops in 2001 because the Fort Santiago gauge was decommissioned
from the RQ programme; the gauge itself continues to report via the
UHSLC Fast-Delivery (FD) channel under the same station ID.

A 17-year RQ-only fit gives a compressed GEV (xi=-0.466, very strongly
bounded; RP2-RP1000 spread only 0.18 m).  Splicing the FD record
2002-2024 onto the RQ record nearly doubles the sample size and yields
a more defensible RP curve at high return periods.

Procedure
---------
1. Fetch RQ hourly data 1985-2001  -> 17 candidate years.
2. Fetch FD hourly data 2002-2024  -> up to 23 candidate years.
3. Concatenate the hourly series, compute the long-term mean across the
   combined record, de-mean, and take annual maxima (>=50% hourly
   coverage required per year).
4. Fit a GEV (MLE) on the spliced annual maxima.
5. Extract RP2 / 5 / 10 / 25 / 50 / 100 / 200 / 500 / 1000 levels.
6. Apply the documented MSL-to-EGM2008 offset (+1.1292 m, CMEMS 2026-05-16).
7. Write back to data/manila/hazard_baseline_template.csv, replacing the
   coastal rows.

This is a one-off equivalent to fetch_uhslc_gauge.py but with two
sequential ERDDAP queries (RQ + FD) before the GEV fit.

Usage
-----
    python scripts/_extend_manila_coastal_record.py
    python scripts/_extend_manila_coastal_record.py --dry-run
"""
from __future__ import annotations

import sys
from datetime import date as _date
from pathlib import Path

import click
import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.fetch_uhslc_gauge import (
    _ERDDAP_DATASETS,
    fetch_year_uhslc,
    fit_gev,
    gev_return_level,
)

UHSLC_RQ_ID      = 304       # Research-Quality archive (1985-2001)
UHSLC_FD_ID      = 370       # Fast-Delivery continuation (same physical Manila gauge,
                             # confirmed via ERDDAP station catalog: 14.583N, 120.967E)
GAUGE_NAME       = "Manila, Philippines — UHSLC RQ 304 + FD 370 (spliced)"
MDT_OFFSET_M     = 1.1292   # CMEMS CNES-CLS-2022 (2026-05-16)
RQ_START         = 1985
RQ_END           = 2001
FD_START         = 2002
FD_END           = 2024
RETURN_PERIODS   = [2, 5, 10, 25, 50, 100, 200, 500, 1000]
MIN_COVERAGE     = 0.50
CSV_PATH         = PROJECT_ROOT / "data" / "manila" / "hazard_baseline_template.csv"


def fetch_block(session, dataset: str, start: int, end: int, uhslc_id: int) -> dict[int, pd.Series]:
    url = _ERDDAP_DATASETS[dataset]
    out: dict[int, pd.Series] = {}
    for year in range(start, end + 1):
        s = fetch_year_uhslc(session, year, uhslc_id=uhslc_id, erddap_url=url)
        if s is None or s.dropna().empty:
            click.echo(f"  {dataset} {year}: empty / missing")
            continue
        out[year] = s
        click.echo(f"  {dataset} {year}: {len(s.dropna()):>6d} valid hourly samples")
    return out


def annual_maxima(years_data: dict[int, pd.Series], mean_m: float) -> dict[int, float]:
    min_hours = int(8760 * MIN_COVERAGE)
    out: dict[int, float] = {}
    for yr, s in sorted(years_data.items()):
        valid = s.dropna()
        if len(valid) < min_hours:
            click.echo(f"  {yr}: SKIP (only {len(valid)} valid hours < {min_hours})")
            continue
        out[yr] = float((valid - mean_m).max())
    return out


@click.command()
@click.option("--dry-run", is_flag=True, default=False)
def cli(dry_run: bool) -> None:
    sess = requests.Session()
    click.echo(f"Manila UHSLC 304 tail-extension run  (date={_date.today()})")
    click.echo(f"  RQ window : {RQ_START}-{RQ_END}")
    click.echo(f"  FD window : {FD_START}-{FD_END}")
    click.echo()

    click.echo(f"Fetching RQ block (uhslc_id={UHSLC_RQ_ID})...")
    rq = fetch_block(sess, "rqds", RQ_START, RQ_END, UHSLC_RQ_ID)
    click.echo()
    click.echo(f"Fetching FD block (uhslc_id={UHSLC_FD_ID})...")
    fd = fetch_block(sess, "fast", FD_START, FD_END, UHSLC_FD_ID)
    click.echo()

    if not rq and not fd:
        click.echo("No data retrieved.", err=True)
        sys.exit(1)

    # IMPORTANT — UHSLC RQ (id 304) and FD (id 370) use different reference
    # datums for the same physical Manila gauge (a ~1.1 m offset is present in
    # the raw values).  De-mean each block separately so the annual maxima
    # are anomalies above each block's own mean -- then they are comparable.
    rq_mean = float(pd.concat(list(rq.values())).dropna().mean()) if rq else float("nan")
    fd_mean = float(pd.concat(list(fd.values())).dropna().mean()) if fd else float("nan")
    click.echo(f"Block means (gauge datum): RQ={rq_mean:.3f} m  FD={fd_mean:.3f} m  "
               f"diff={rq_mean-fd_mean:+.3f} m (datum discontinuity)")
    click.echo()

    ams_rq = annual_maxima(rq, rq_mean)
    ams_fd = annual_maxima(fd, fd_mean)
    ams = {**ams_rq, **ams_fd}
    click.echo(f"Valid annual maxima: {len(ams)} years")
    for yr, m in sorted(ams.items()):
        click.echo(f"  {yr}: {m:+.3f} m")
    click.echo()

    if len(ams) < 25:
        click.echo(f"WARNING: only {len(ams)} years of valid AM — short record.",
                   err=True)

    am_arr = np.array(list(ams.values()))
    c, loc, scale = fit_gev(am_arr)
    click.echo(f"GEV (scipy genextreme) c={c:+.4f}  loc={loc:+.4f}  scale={scale:.4f}")
    # Note: scipy uses c = -xi convention
    xi = -c
    click.echo(f"   -> xi={xi:+.4f}  mu={loc:+.4f}  sigma={scale:.4f}")
    click.echo()

    click.echo("Return levels (anomaly + MDT offset = EGM2008):")
    rows = []
    for rp in RETURN_PERIODS:
        x = gev_return_level(c, loc, scale, rp)
        x_egm = x + MDT_OFFSET_M
        click.echo(f"  RP{rp:>4}: anomaly={x:+.4f}  +MDT={x_egm:+.4f} m EGM2008")
        rows.append((rp, x_egm, x))
    click.echo()

    if dry_run:
        click.echo("[dry-run] Not writing CSV.")
        return

    df = pd.read_csv(CSV_PATH, dtype=str)
    other = df[df["hazard_type"].str.lower() != "coastal"].copy()

    date_str = str(_date.today())
    src_note = (
        f"{GAUGE_NAME}; spliced UHSLC RQ {RQ_START}-{RQ_END} + FD {FD_START}-{FD_END}; "
        f"{len(ams)} valid annual maxima ({date_str}); "
        f"GEV(xi={xi:+.4f}, mu={loc:+.4f}, sigma={scale:.4f}); "
        f"MDT_offset_to_EGM2008=+{MDT_OFFSET_M:.4f} m (CMEMS CNES-CLS-2022)"
    )
    datum_note = (
        "baseline_water_level_m in EGM2008; tide+surge total water level "
        "(annual max anomaly + MSL-to-EGM2008 offset); compatible with "
        "Copernicus GLO-30 DEM vertical datum"
    )

    new_coastal = pd.DataFrame([
        {
            "hazard_type": "coastal",
            "return_period": rp,
            "baseline_water_level_m": round(x_egm, 4),
            "source_note": src_note,
            "gev_shape": round(xi, 4),
            "gev_loc_mm": round(loc, 3),    # column name retained for schema compat
            "gev_scale_mm": round(scale, 3),
            "datum_note": datum_note,
        }
        for rp, x_egm, _ in rows
    ])

    out = pd.concat([new_coastal, other], ignore_index=True)
    out = out[df.columns.tolist()]
    out.to_csv(CSV_PATH, index=False)
    click.echo(f"Wrote {CSV_PATH}")


if __name__ == "__main__":
    cli()
