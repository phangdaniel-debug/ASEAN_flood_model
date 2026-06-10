"""Regenerate combined flood maps + street overlays for every city + composite.

Iterates over scripts.cities.CITIES, runs make_combined_flood_maps.py and
overlay_street_maps.py against each city's outputs directory.  Greater KL /
Greater Jakarta composites are appended manually.

Usage:
    python scripts/_regen_all_plots.py
    python scripts/_regen_all_plots.py --skip-overlay   # combined only
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

# Slug → display name; appended composites have no CityConfig entry.
EXTRA = [
    ("greater_kl", "Greater Kuala Lumpur"),
    ("greater_jakarta", "Greater Jakarta"),
]


def _run(cmd: list[str]) -> None:
    click.echo("  $ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if r.returncode != 0:
        raise SystemExit(f"failed (rc={r.returncode}): {' '.join(cmd)}")


@click.command()
@click.option("--scenario", default="SSP5-8.5", show_default=True)
@click.option("--horizon",  default=2100,       show_default=True, type=int)
@click.option("--skip-overlay", is_flag=True,   help="Skip the street-overlay step.")
@click.option(
    "--only",
    default=None,
    help="Comma-separated subset of slugs to regenerate (default: all).",
)
def cli(scenario: str, horizon: int, skip_overlay: bool, only: str | None) -> None:
    from scripts.cities import CITIES

    pairs = [(slug, cfg.name) for slug, cfg in CITIES.items()] + EXTRA
    if only:
        wanted = set(only.split(","))
        pairs = [p for p in pairs if p[0] in wanted]

    # Convert scenario string (e.g. "SSP5-8.5") to dir-suffix slug ("ssp585")
    sce_slug = scenario.lower().replace("-", "").replace(".", "")

    for slug, name in pairs:
        out_dir = PROJECT_ROOT / "outputs" / f"{slug}_{sce_slug}_{horizon}"
        if not out_dir.exists():
            click.echo(f"[skip] {slug}: no outputs dir")
            continue
        click.echo(f"\n=== {slug} ({name}) ===")
        _run([
            PY, str(PROJECT_ROOT / "scripts" / "make_combined_flood_maps.py"),
            "--out-dir",   str(out_dir),
            "--scenario",  scenario,
            "--horizon",   str(horizon),
            "--city-name", name,
        ])
        if not skip_overlay:
            _run([
                PY, str(PROJECT_ROOT / "scripts" / "overlay_street_maps.py"),
                "--out-dir",   str(out_dir),
                "--scenario",  scenario,
                "--horizon",   str(horizon),
                "--city-name", name,
            ])

    click.echo("\nAll plots regenerated.")


if __name__ == "__main__":
    cli()
