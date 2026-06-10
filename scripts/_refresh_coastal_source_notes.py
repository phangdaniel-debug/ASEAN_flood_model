"""One-off: refresh stale `msl_to_egm2008_offset=...` literal inside the
coastal source_note text on every city's hazard_baseline_template.csv.

Background
----------
``scripts/derive_msl_egm2008_offsets.py`` updates ``baseline_water_level_m``
and appends an authoritative ``mdt_cnes_cls22=+X.XXXXm applied <date>``
record to ``datum_note``, but leaves the original GEV-fit ``source_note``
unchanged.  Some source_notes carry an obsolete literal
``msl_to_egm2008_offset=+0.0000 m applied`` (or interim +0.2500/+0.3500),
which is technically correct as a record of the fit-step datum operation
(the GEV fit itself used 0 m), but reads as if no MDT was ever applied.

This script rewrites that literal to the final effective CMEMS value
recorded in scripts/cities.py so a reader of source_note alone is not
misled.  Datum_note is the authoritative audit record and is unchanged.

Usage:
    python scripts/_refresh_coastal_source_notes.py
    python scripts/_refresh_coastal_source_notes.py --dry-run
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.cities import CITIES

# Cities with coastal rows + a msl_to_egm2008_offset value
TARGETS = ["singapore", "kuala_lumpur", "bangkok",
           "jakarta", "manila", "hcmc"]

_OFFSET_RE = re.compile(
    r"msl_to_egm2008_offset\s*=\s*[+-]?\d+(?:\.\d+)?\s*m"
)


@click.command()
@click.option("--dry-run", is_flag=True, default=False)
def cli(dry_run: bool) -> None:
    for slug in TARGETS:
        cfg = CITIES.get(slug)
        if cfg is None or cfg.msl_to_egm2008_offset is None:
            continue
        offset = float(cfg.msl_to_egm2008_offset)
        replacement = (
            f"msl_to_egm2008_offset={offset:+.4f} m "
            f"(CMEMS CNES-CLS-2022 MDT applied 2026-05-16)"
        )

        csv = PROJECT_ROOT / "data" / slug / "hazard_baseline_template.csv"
        df = pd.read_csv(csv, dtype=str)
        mask = df["hazard_type"].str.lower() == "coastal"
        n_changed = 0
        new_notes = []
        for i, row in df.loc[mask].iterrows():
            src = str(row.get("source_note", "") or "")
            new = _OFFSET_RE.sub(replacement, src, count=1)
            if new != src:
                n_changed += 1
            new_notes.append((i, new))
        if not n_changed:
            click.echo(f"  {slug}: no stale literal found")
            continue

        for i, txt in new_notes:
            df.at[i, "source_note"] = txt

        click.echo(f"  {slug}: {n_changed} coastal source_notes refreshed "
                   f"-> '{replacement[:60]}...'")

        if dry_run:
            sample = df.loc[mask, "source_note"].iloc[0]
            click.echo(f"     sample: {sample[:180]}")
            continue

        df.to_csv(csv, index=False)


if __name__ == "__main__":
    cli()
