"""
Cross-check ERA5-Land GEV fits against published national IDF anchors.

For each city with a documented IDF anchor, fetch (or load from cache)
the hourly ERA5-Land precipitation, compute the 6h-rolling-sum GEV
return level at the anchor RP, and compare with the cited published
value.  Tolerance: +/- 25 %.

Anchors are cited in scripts/cities.py notes:
  Singapore        : PUB primary drain RP10 6h ~ 100 mm
  Kuala Lumpur (+) : JPS Malaysia RP2 6h ~ 90 mm  (range 80-100)
  Bangkok (+)      : TMD Thailand RP5 6h ~ 85 mm  (range 80-90)
  Jakarta (+)      : BMKG Indonesia RP2 6h ~ 85 mm
  Manila           : PAGASA RP10 6h ~ 130 mm (range 120-140)
  HCMC             : (no anchor cited)

(+) extended to supplementary configs of the same country.

Usage
-----
    # Validate all anchored cities (downloads ERA5-Land from Open-Meteo
    # if not cached; ~5 chunks of 5 years per city, polite ~1-2 min each)
    python scripts/validate_pluvial_idf_anchors.py

    # Validate one city
    python scripts/validate_pluvial_idf_anchors.py --city kuala_lumpur

Exit codes
----------
    0 : every checked city is within +/- 25 %
    1 : one or more cities deviate beyond +/- 25 %
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

from scripts.cities import CITIES
from scripts.gev_utils import (
    rolling_accumulation,
    annual_maxima,
    fit_gev,
    gev_return_level,
    fetch_hourly_precip_era5land,
)


# (city_slug, anchor_rp, anchor_mm_6h, source)
ANCHORS: list[tuple[str, int, float, str]] = [
    ("singapore",          10, 100.0, "PUB primary drain RP10"),
    ("kuala_lumpur",        2,  90.0, "JPS Malaysia RP2 6h (80-100 range)"),
    ("klang_shah_alam",     2,  90.0, "JPS Malaysia RP2 6h (80-100 range)"),
    ("subang_langat",       2,  90.0, "JPS Malaysia RP2 6h (80-100 range)"),
    ("bangkok",             5,  85.0, "TMD Thailand RP5 6h (80-90 range)"),
    ("bangkok_chao_phraya", 5,  85.0, "TMD Thailand RP5 6h (80-90 range)"),
    ("jakarta",             2,  85.0, "BMKG Indonesia RP2 6h"),
    ("tangerang",           2,  85.0, "BMKG Indonesia RP2 6h"),
    ("bekasi_depok",        2,  85.0, "BMKG Indonesia RP2 6h"),
    ("manila",             10, 130.0, "PAGASA RP10 6h (120-140 range)"),
    # hcmc: no anchor cited; intentionally omitted.
]

DEVIATION_TOLERANCE = 0.25  # +/- 25 %
WINDOW_H = 6
START_YEAR = 2001
END_YEAR = 2024
CACHE_DIR = PROJECT_ROOT / "cache"


def _load_or_fetch(slug: str, lat: float, lon: float) -> pd.Series:
    cache_path = CACHE_DIR / f"era5land_{slug}_pluvial.parquet"
    if cache_path.exists():
        click.echo(f"  [{slug}] using cache {cache_path.name}")
        s = pd.read_parquet(cache_path).squeeze()
        if not isinstance(s.index, pd.DatetimeIndex):
            s.index = pd.to_datetime(s.index, utc=True)
        elif s.index.tzinfo is None:
            s.index = s.index.tz_localize("UTC")
        return s
    click.echo(f"  [{slug}] downloading ERA5-Land (no cache yet) ...")
    s = fetch_hourly_precip_era5land(lat, lon, START_YEAR, END_YEAR)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    s.to_frame().to_parquet(cache_path)
    return s


def _gev_rp_value(series: pd.Series, rp: int, window_h: int = WINDOW_H) -> float:
    acc = rolling_accumulation(series, window_h)
    maxima = annual_maxima(acc)
    if len(maxima) < 5:
        raise ValueError(f"only {len(maxima)} annual maxima; need >=5")
    arr = np.array(list(maxima.values()), dtype=np.float64)
    c, loc, scale = fit_gev(arr)
    return gev_return_level(c, loc, scale, rp)


@click.command()
@click.option("--city", "city_slug", default=None,
              help="Validate one city; omit to validate all anchored cities.")
def cli(city_slug: str | None):
    if city_slug is not None:
        anchors = [a for a in ANCHORS if a[0] == city_slug]
        if not anchors:
            raise click.ClickException(
                f"No anchor for {city_slug!r}.  Anchored cities: "
                f"{', '.join(a[0] for a in ANCHORS)}"
            )
    else:
        anchors = ANCHORS

    sep = "=" * 80
    click.echo(sep)
    click.echo(f"Pluvial IDF anchor validation (tolerance +/- {DEVIATION_TOLERANCE:.0%})")
    click.echo(sep)
    click.echo(f"{'City':<22}{'RP':>4}  {'Anchor':>10}  "
               f"{'ERA5-Land':>12}  {'Dev':>7}  Verdict")
    click.echo("-" * 80)

    failures: list[str] = []
    for slug, rp, anchor_mm, source in anchors:
        if slug not in CITIES:
            click.echo(f"{slug:<22}{rp:>4}  {anchor_mm:>10.1f}  "
                       f"{'N/A':>12}  {'-':>7}  SKIP (not in CITIES)")
            continue
        cfg = CITIES[slug]
        try:
            series = _load_or_fetch(slug, cfg.era5_lat, cfg.era5_lon)
            era5_mm = _gev_rp_value(series, rp)
        except Exception as exc:
            click.echo(f"{slug:<22}{rp:>4}  {anchor_mm:>10.1f}  "
                       f"{'ERROR':>12}  {'-':>7}  FAIL ({exc})")
            failures.append(f"{slug}: {exc}")
            continue

        dev = (era5_mm - anchor_mm) / anchor_mm
        verdict = "PASS" if abs(dev) <= DEVIATION_TOLERANCE else "FAIL"
        click.echo(f"{slug:<22}{rp:>4}  {anchor_mm:>10.1f}  "
                   f"{era5_mm:>12.1f}  {dev:>+7.1%}  {verdict}")
        if verdict == "FAIL":
            failures.append(
                f"{slug}: ERA5={era5_mm:.1f} mm vs anchor {anchor_mm:.1f} mm "
                f"({dev:+.1%}; source: {source})"
            )

    click.echo(sep)
    if failures:
        click.echo(f"FAIL: {len(failures)} city(ies) outside +/-{DEVIATION_TOLERANCE:.0%}:")
        for f in failures:
            click.echo(f"  - {f}")
        click.echo("\nDocument the deviation in scripts/cities.py notes.")
        click.echo("Do NOT introduce a multiplicative scaling factor "
                   "(re-creates the precip_scale problem).")
        sys.exit(1)
    else:
        click.echo("All checked cities within tolerance.")
        sys.exit(0)


if __name__ == "__main__":
    cli()
