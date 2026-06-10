"""Run the full city + composite pipeline grid across multiple scenarios.

Iterates over a list of (scenario, horizon) combinations, runs all 11 city
pipelines (bathtub solver, no refit) plus Greater KL / Greater Jakarta
composites under each, and finally regenerates plots for every output
directory produced.

Designed to fill in the 2 × 2 scenario × horizon grid (SSP5-8.5 / SSP2-4.5
× 2050 / 2100) on top of the existing SSP5-8.5 2100 baseline.

Usage:
    python scripts/_run_scenario_grid.py --combo SSP5-8.5,2050
    python scripts/_run_scenario_grid.py --combo SSP2-4.5,2050 --combo SSP2-4.5,2100
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PY = sys.executable

# City slug -> extra flags
CITY_FLAGS: dict[str, list[str]] = {
    "singapore":            ["--coastal-solver", "bathtub"],
    "kuala_lumpur":         ["--coastal-solver", "bathtub"],
    "bangkok":              ["--coastal-solver", "bathtub", "--subsidence-correction"],
    "bangkok_chao_phraya":  ["--coastal-solver", "bathtub", "--subsidence-correction"],
    "jakarta":              ["--coastal-solver", "bathtub", "--subsidence-correction"],
    "tangerang":            ["--coastal-solver", "bathtub", "--subsidence-correction"],
    "bekasi_depok":         ["--coastal-solver", "bathtub", "--subsidence-correction"],
    "manila":               ["--coastal-solver", "bathtub", "--subsidence-correction"],
    "hcmc":                 ["--coastal-solver", "bathtub", "--subsidence-correction"],
    "klang_shah_alam":      ["--coastal-solver", "bathtub"],
    "subang_langat":        ["--coastal-solver", "bathtub"],
}

NO_FIT_FLAGS = ["--no-fit-era5", "--no-fit-glofas", "--no-fit-coastal"]


def _run(cmd: list[str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    click.echo(f"  $ {' '.join(cmd[:6])} ... > {log_path.name}")
    with log_path.open("w") as f:
        r = subprocess.run(cmd, cwd=PROJECT_ROOT, stdout=f, stderr=subprocess.STDOUT)
    return r.returncode


@click.command()
@click.option(
    "--combo",
    multiple=True,
    required=True,
    help="Comma-separated 'scenario,horizon' tuple, e.g. 'SSP5-8.5,2050'. May be repeated.",
)
@click.option("--skip-plots", is_flag=True, default=False)
def cli(combo: tuple[str, ...], skip_plots: bool) -> None:
    combos = [tuple(c.split(",")) for c in combo]
    for scenario, horizon in combos:
        click.echo(f"\n=== Scenario grid: {scenario} / {horizon} ===")

        # Cities serial
        for slug, extra in CITY_FLAGS.items():
            log = PROJECT_ROOT / "logs" / f"grid_{scenario}_{horizon}_{slug}.log"
            cmd = [
                PY, str(PROJECT_ROOT / "scripts" / "run_city_pipeline.py"),
                "--city", slug,
                "--scenario", scenario,
                "--horizon", str(horizon),
                *extra,
                *NO_FIT_FLAGS,
            ]
            rc = _run(cmd, log)
            click.echo(f"    {slug:<22} rc={rc}")

        # Composites
        for compositor, name in [
            ("make_greater_kl_composite.py",      "greater_kl"),
            ("make_greater_jakarta_composite.py", "greater_jakarta"),
        ]:
            log = PROJECT_ROOT / "logs" / f"grid_{scenario}_{horizon}_{name}.log"
            cmd = [
                PY, str(PROJECT_ROOT / "scripts" / compositor),
                "--scenario", scenario,
                "--horizon", str(horizon),
            ]
            rc = _run(cmd, log)
            click.echo(f"    {name:<22} rc={rc}")

        if not skip_plots:
            # Plot regen for this combo
            log = PROJECT_ROOT / "logs" / f"grid_{scenario}_{horizon}_plots.log"
            cmd = [
                PY, str(PROJECT_ROOT / "scripts" / "_regen_all_plots.py"),
                "--scenario", scenario,
                "--horizon", str(horizon),
            ]
            rc = _run(cmd, log)
            click.echo(f"    plots rc={rc}")

    click.echo("\nDone.")


if __name__ == "__main__":
    cli()
