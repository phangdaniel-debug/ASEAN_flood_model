"""Automated RP-monotonicity + mass-plausibility smoke check.

The machine-checkable subset of the visual-gate checklist (spec 6.3):
per hazard, flooded_area_km2 and max_depth_m must be non-decreasing with
return period, and wet area must not exceed a sane fraction of the domain.
This catches Manila-type domain-wide-sheet and non-monotone bugs instantly.

Usage
-----
    python scripts/check_rp_monotonicity.py --summary outputs/<run>/summary_<sc>_<hz>.csv \
        --domain-km2 <area> [--max-wet-fraction 0.6]

Exit codes: 0 = clean; 1 = one or more problems.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import pandas as pd

MONOTONE_COLUMNS = ["flooded_area_km2", "max_depth_m"]


def check_monotonicity(
    summary_csv: Path,
    domain_km2: float,
    max_wet_fraction: float = 0.6,
) -> list[str]:
    """Return problems; empty list means clean."""
    df = pd.read_csv(summary_csv)
    problems: list[str] = []
    for hazard, grp in df.groupby("hazard_type"):
        grp = grp.sort_values("return_period")
        for col in MONOTONE_COLUMNS:
            if col not in grp.columns:
                continue
            vals = grp[col].to_numpy()
            rps = grp["return_period"].to_numpy()
            for i in range(1, len(vals)):
                if vals[i] + 1e-9 < vals[i - 1]:
                    problems.append(
                        f"{hazard} {col}: RP{int(rps[i])}={vals[i]:.4f} < "
                        f"RP{int(rps[i-1])}={vals[i-1]:.4f} (non-monotone)"
                    )
        if "flooded_area_km2" in grp.columns and domain_km2 > 0:
            for _, r in grp.iterrows():
                frac = float(r["flooded_area_km2"]) / domain_km2
                if frac > max_wet_fraction:
                    problems.append(
                        f"{hazard} RP{int(r['return_period'])}: wet fraction "
                        f"{frac:.0%} exceeds {max_wet_fraction:.0%} of domain"
                    )
    return problems


@click.command()
@click.option("--summary", "summary_csv", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--domain-km2", type=float, required=True, help="Land-domain area (km2) for the wet-fraction check.")
@click.option("--max-wet-fraction", type=float, default=0.6, show_default=True)
def cli(summary_csv: Path, domain_km2: float, max_wet_fraction: float):
    problems = check_monotonicity(summary_csv, domain_km2, max_wet_fraction)
    if problems:
        click.echo(f"FAIL: {len(problems)} problem(s):")
        for p in problems:
            click.echo(f"  - {p}")
        sys.exit(1)
    click.echo("PASS: per-hazard RP monotonicity + mass plausibility hold.")
    sys.exit(0)


if __name__ == "__main__":
    cli()
