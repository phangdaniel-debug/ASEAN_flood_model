"""
Monitor a running city pipeline and print progress every N minutes.

Polls the output directory for expected raster files and reports which
hazard × return-period combinations are complete, in-progress, or pending.

Usage
-----
    # Watch Jakarta run, refresh every 5 minutes (default):
    python scripts/monitor_pipeline.py --city jakarta

    # Watch KL, refresh every 2 minutes:
    python scripts/monitor_pipeline.py --city kuala_lumpur --interval 2

    # One-shot check (no loop):
    python scripts/monitor_pipeline.py --city jakarta --once
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.cities import CITIES

HAZARDS = ["coastal", "fluvial", "pluvial"]
RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]

# Symbol set (ASCII-safe for Windows cp1252 terminals)
SYM_DONE    = "[x]"
SYM_MISSING = "[ ]"
SYM_SEP     = "-" * 62


def _scenario_slug(scenario: str) -> str:
    return scenario.lower().replace("-", "").replace(".", "")


def _depth_path(out_dir: Path, hazard: str, scenario: str, horizon: int, rp: int) -> Path:
    return (
        out_dir / hazard / f"rp_{rp}"
        / f"{hazard}_depth_{scenario}_{horizon}_rp{rp}.tif"
    )


def _png_path(out_dir: Path, scenario: str, horizon: int, rp: int) -> Path:
    return out_dir / f"map_combined_{scenario}_{horizon}_rp{rp}.png"


def _check(out_dir: Path, scenario: str, horizon: int) -> dict:
    """Return a nested status dict: status[hazard][rp] = True/False."""
    status: dict[str, dict[int, bool]] = {}
    for hazard in HAZARDS:
        status[hazard] = {}
        for rp in RETURN_PERIODS:
            status[hazard][rp] = _depth_path(out_dir, hazard, scenario, horizon, rp).exists()
    return status


def _png_check(out_dir: Path, scenario: str, horizon: int) -> dict[int, bool]:
    return {rp: _png_path(out_dir, scenario, horizon, rp).exists() for rp in RETURN_PERIODS}


def _print_status(
    city_name: str,
    out_dir: Path,
    scenario: str,
    horizon: int,
    start_time: datetime,
) -> tuple[int, int]:
    """Print a status table. Returns (done, total)."""
    status   = _check(out_dir, scenario, horizon)
    png_done = _png_check(out_dir, scenario, horizon)

    total = len(HAZARDS) * len(RETURN_PERIODS)
    done  = sum(v for hz in status.values() for v in hz.values())
    pct   = done / total * 100

    elapsed = datetime.now() - start_time
    elapsed_str = str(elapsed).split(".")[0]  # drop microseconds

    # ETA: extrapolate linearly from elapsed
    if done > 0:
        rate     = elapsed.total_seconds() / done          # s per raster
        remaining = timedelta(seconds=rate * (total - done))
        eta_str  = str(remaining).split(".")[0]
    else:
        eta_str = "unknown"

    now = datetime.now().strftime("%H:%M:%S")
    click.echo(f"\n{SYM_SEP}")
    click.echo(
        f"  {city_name}  |  {scenario} {horizon}  |  {now}"
    )
    click.echo(
        f"  Rasters: {done}/{total} ({pct:.0f}%)    "
        f"Elapsed: {elapsed_str}    ETA: {eta_str}"
    )
    click.echo(SYM_SEP)

    # Header row
    rp_header = "  ".join(f"RP{rp:>4}" for rp in RETURN_PERIODS)
    click.echo(f"  {'Hazard':<8}  {rp_header}")
    click.echo(f"  {'-'*8}  {'  '.join(['-'*5]*len(RETURN_PERIODS))}")

    for hazard in HAZARDS:
        cells = "  ".join(
            SYM_DONE if status[hazard][rp] else SYM_MISSING
            for rp in RETURN_PERIODS
        )
        n_hz  = sum(status[hazard].values())
        click.echo(f"  {hazard:<8}  {cells}  ({n_hz}/{len(RETURN_PERIODS)})")

    # PNG row
    png_cells = "  ".join(
        SYM_DONE if png_done[rp] else SYM_MISSING for rp in RETURN_PERIODS
    )
    n_png = sum(png_done.values())
    click.echo(f"  {'maps':<8}  {png_cells}  ({n_png}/{len(RETURN_PERIODS)})")

    click.echo(SYM_SEP)

    if done == total:
        click.echo("  COMPLETE — all rasters written.")
    elif done == 0:
        click.echo("  Waiting for first output file...")
    else:
        # Identify what's currently running (first incomplete raster by hazard order)
        for hazard in HAZARDS:
            for rp in RETURN_PERIODS:
                if not status[hazard][rp]:
                    click.echo(
                        f"  Next expected : {hazard} RP{rp}"
                    )
                    break
            else:
                continue
            break

    return done, total


@click.command()
@click.option(
    "--city", "city_slug",
    required=True,
    type=click.Choice(list(CITIES)),
    help="City slug to monitor.",
)
@click.option("--scenario", default="SSP5-8.5", show_default=True)
@click.option("--horizon",  type=int, default=2100, show_default=True)
@click.option(
    "--out-root",
    type=click.Path(path_type=Path),
    default=Path("outputs"),
    show_default=True,
)
@click.option(
    "--interval", "-n",
    type=float,
    default=5.0,
    show_default=True,
    help="Refresh interval in minutes.",
)
@click.option(
    "--once",
    is_flag=True,
    default=False,
    help="Print one status snapshot and exit (no polling loop).",
)
def cli(
    city_slug: str,
    scenario: str,
    horizon: int,
    out_root: Path,
    interval: float,
    once: bool,
) -> None:
    city     = CITIES[city_slug]
    scen_slug = _scenario_slug(scenario)
    out_dir   = out_root / f"{city_slug}_{scen_slug}_{horizon}"
    start_time = datetime.now()

    click.echo(
        f"\nMonitoring: {city.name}  ({scenario}, {horizon})\n"
        f"Output dir: {out_dir}\n"
        f"Refresh   : {'once' if once else f'every {interval:.0f} min'}"
    )

    if not out_dir.exists():
        click.echo(f"\n[warn] Output directory does not exist yet: {out_dir}")
        click.echo("       Waiting for pipeline to create it...")

    if once:
        _print_status(city.name, out_dir, scenario, horizon, start_time)
        return

    interval_s = interval * 60
    try:
        while True:
            done, total = _print_status(city.name, out_dir, scenario, horizon, start_time)
            if done == total:
                break
            click.echo(f"\n  Next check in {interval:.0f} min  (Ctrl+C to stop)")
            time.sleep(interval_s)
    except KeyboardInterrupt:
        click.echo("\n\nMonitor stopped.")


if __name__ == "__main__":
    cli()
