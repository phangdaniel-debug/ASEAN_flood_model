"""Guard against inconsistent pluvial forcing across scenario hazard-level CSVs.

Limitations register #9: scenario CSVs once carried non-monotone and physically
impossible pluvial net-excess (water_level_m). This converts that into a
committed check: across an ordered list of scenario CSVs (least -> most severe),
pluvial water_level_m must be non-decreasing at each return period and must not
exceed a physical-plausibility cap.

Usage
-----
    python scripts/validate_scenario_forcing_consistency.py --city kuala_lumpur

Exit codes: 0 = consistent; 1 = one or more problems.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Least -> most severe (by warming). Baseline template is the floor.
SCENARIO_ORDER = [
    "hazard_levels_ssp245_2050.csv",
    "hazard_levels_ssp585_2050.csv",
    "hazard_levels_ssp245_2100.csv",
    "hazard_levels_ssp585_2100.csv",
]
PLAUSIBILITY_CAP_M = 0.5  # 6h net-excess ponding depth; >0.5 m is unphysical


def _pluvial_by_rp(csv_path: Path) -> dict[int, float]:
    df = pd.read_csv(csv_path)
    p = df[df["hazard_type"] == "pluvial"]
    return {int(r): float(v) for r, v in zip(p["return_period"], p["water_level_m"])}


def check_pluvial_forcing(csv_paths: list[Path], cap_m: float = PLAUSIBILITY_CAP_M) -> list[str]:
    """Return problems; empty list means consistent."""
    problems: list[str] = []
    series = [(p, _pluvial_by_rp(p)) for p in csv_paths]
    # Cap check on every file.
    for path, by_rp in series:
        for rp, lvl in by_rp.items():
            if lvl > cap_m:
                problems.append(
                    f"{path.name} RP{rp}: water_level_m={lvl:.3f} exceeds "
                    f"plausibility cap {cap_m:.2f} m"
                )
    # Monotonicity across the ordered scenarios, per RP.
    for i in range(1, len(series)):
        prev_path, prev = series[i - 1]
        cur_path, cur = series[i]
        for rp in sorted(set(prev) & set(cur)):
            if cur[rp] + 1e-9 < prev[rp]:
                problems.append(
                    f"RP{rp}: inversion {prev_path.name}={prev[rp]:.3f} > "
                    f"{cur_path.name}={cur[rp]:.3f} (more severe scenario has "
                    f"lower forcing)"
                )
    return problems


@click.command()
@click.option("--city", "city_slug", required=True, help="City slug.")
@click.option("--data-root", type=click.Path(path_type=Path), default=Path("data"))
def cli(city_slug: str, data_root: Path):
    city_dir = data_root / city_slug
    paths = [city_dir / name for name in SCENARIO_ORDER if (city_dir / name).exists()]
    if not paths:
        raise click.ClickException(f"No scenario CSVs found under {city_dir}")
    click.echo(f"Checking {len(paths)} scenario CSV(s) for {city_slug} ...")
    problems = check_pluvial_forcing(paths)
    if problems:
        click.echo(f"FAIL: {len(problems)} problem(s):")
        for p in problems:
            click.echo(f"  - {p}")
        sys.exit(1)
    click.echo("PASS: pluvial forcing monotone and within plausibility cap.")
    sys.exit(0)


if __name__ == "__main__":
    cli()
