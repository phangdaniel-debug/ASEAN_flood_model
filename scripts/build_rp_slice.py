"""Filter a hazard_levels CSV to a single return period (one row per hazard).

Lets the slow inertial-coastal / raingrid solvers run at a single RP instead of
every RP in the full forcing table. Reused in the step-3 atlas for the
RP10/RP100/RP1000 slices.
"""
from __future__ import annotations

from pathlib import Path

import click
import pandas as pd


@click.command()
@click.option("--in-csv", "in_csv", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--rp", type=int, required=True, help="Return period to keep (e.g. 100).")
@click.option("--out-csv", "out_csv", type=click.Path(path_type=Path), required=True)
def cli(in_csv: Path, rp: int, out_csv: Path) -> None:
    df = pd.read_csv(in_csv)
    df["return_period"] = df["return_period"].astype(int)
    sliced = df[df["return_period"] == rp].copy()
    if sliced.empty:
        raise SystemExit(f"[error] no rows with return_period=={rp} in {in_csv}")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    sliced.to_csv(out_csv, index=False)
    haz = ", ".join(f"{r.hazard_type}={float(r.water_level_m):.4f}" for r in sliced.itertuples())
    click.echo(f"wrote {len(sliced)} rows (RP{rp}) -> {out_csv}  [{haz}]")


if __name__ == "__main__":
    cli()
