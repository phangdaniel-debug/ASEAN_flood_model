"""
Post-run validation: defended vs undefended sanity checks.

For every (city, scenario, horizon) where both an undefended output dir
(e.g. ``outputs/bangkok_ssp245_2050``) and a defended output dir
(``outputs/bangkok_ssp245_2050_defended``) exist:

  Check 1: For every (hazard, RP), the defended flooded area must be
           less than or equal to the undefended flooded area (within a
           5% tolerance for numerical noise). A defense raising flooded
           area is a bug -- either the burn introduced spurious wet
           pixels, or the solver behaved unexpectedly with the modified
           DEM.

  Check 2: For every (hazard), flooded area should be monotonically
           non-decreasing with RP (RP2 <= RP5 <= ... <= RP1000). A
           higher-RP event flooding less than a lower-RP event is a
           statistical bug. We also flag RP2 specifically when it is
           NOT small or zero, since per the methodology doc most cities
           should produce near-zero RP2 hazard.

The check reads each scenario's ``summary_<scen>_<yr>.csv`` -- written by
``run_multihazard.py`` -- rather than re-opening the depth rasters.

Exit code 0 = all checks pass. Exit code 1 = one or more anomalies; the
report lists them with the exact summary-CSV row and the relative path
to the corresponding PNG so the figures can be inspected visually.

Usage::

    python scripts/_review_defended_vs_undefended.py
    python scripts/_review_defended_vs_undefended.py --out-root outputs
    python scripts/_review_defended_vs_undefended.py --tolerance 0.10
    python scripts/_review_defended_vs_undefended.py --rp2-cap-km2 30
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import click


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_summary(csv_path: Path) -> dict:
    """Return {(hazard, rp): {'km2': float, 'wl': float, 'mean_d': float, 'max_d': float}}."""
    rows: dict = {}
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            hazard = r["hazard_type"]
            rp = int(r["return_period"])
            rows[(hazard, rp)] = {
                "km2":    float(r["flooded_area_km2"]),
                "wl":     float(r["water_level_m"]),
                "mean_d": float(r["mean_depth_m"]),
                "max_d":  float(r["max_depth_m"]),
            }
    return rows


def _scenario_pair_label(undef: Path, defended: Path) -> str:
    """Short label like 'bangkok / SSP2-4.5 2050'."""
    name = undef.name  # e.g. bangkok_ssp245_2050
    parts = name.split("_")
    if len(parts) >= 3 and parts[-1].isdigit() and parts[-2].startswith("ssp"):
        city = "_".join(parts[:-2])
        scen = parts[-2]
        yr   = parts[-1]
        scen_label = f"SSP{scen[3]}-{scen[4]}.{scen[5]}" if len(scen) == 6 else scen
        return f"{city} / {scen_label} {yr}"
    return name


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_defended_le_undefended(
    label: str, undef: dict, defended: dict, tol: float
) -> list[str]:
    """Flag any (hazard, RP) where defended exceeds undefended * (1 + tol)."""
    issues: list[str] = []
    keys = set(undef.keys()) | set(defended.keys())
    for k in sorted(keys):
        if k not in undef or k not in defended:
            continue
        u = undef[k]["km2"]
        d = defended[k]["km2"]
        if u <= 0:
            # If undefended is zero, defended must also be zero (no surge
            # to defend against). Any positive defended value is suspect.
            if d > 0.01:
                issues.append(
                    f"  [{label}] {k[0]} RP{k[1]}: defended={d:.2f} km² but "
                    f"undefended=0 (suspicious)"
                )
            continue
        if d > u * (1 + tol):
            ratio = d / u
            issues.append(
                f"  [{label}] {k[0]} RP{k[1]}: defended={d:.2f} km² > "
                f"undefended={u:.2f} km² (×{ratio:.2f}, tol={tol:.0%})"
            )
    return issues


def check_monotonic(label: str, summary: dict, variant: str) -> list[str]:
    """Flag any hazard where flooded area is not monotonic non-decreasing in RP."""
    issues: list[str] = []
    by_hazard: dict = {}
    for (h, rp), row in summary.items():
        by_hazard.setdefault(h, []).append((rp, row["km2"]))
    for h, pairs in by_hazard.items():
        pairs.sort()
        for (rp1, km1), (rp2, km2) in zip(pairs, pairs[1:]):
            # Allow a tiny epsilon for floating-point/grid-quantisation
            # noise (cap fluvial/pluvial bathymetry can produce sub-pixel
            # variations).
            if km2 < km1 - 0.05:
                issues.append(
                    f"  [{label}/{variant}] {h}: RP{rp2} ({km2:.2f} km²) < "
                    f"RP{rp1} ({km1:.2f} km²) -- non-monotonic"
                )
    return issues


def check_rp2_small(
    label: str, summary: dict, variant: str, cap_km2: float
) -> list[str]:
    """Flag RP2 hazards exceeding the small/zero cap.

    Per §4.3 / §6.5 of the methodology doc, most cities should produce
    near-zero pluvial RP2 (drain capacity > design RP2 rainfall) and
    small fluvial RP2 (RP2 channels are bankfull-handled). Coastal RP2
    is documented as 5-30 km² for most cities. We accept any RP2 below
    ``cap_km2``; anything larger is flagged for review.
    """
    issues: list[str] = []
    for hazard in ("coastal", "fluvial", "pluvial"):
        row = summary.get((hazard, 2))
        if row is None:
            continue
        if row["km2"] > cap_km2:
            issues.append(
                f"  [{label}/{variant}] {hazard} RP2: {row['km2']:.2f} km² > "
                f"{cap_km2:.0f} km² cap (mean depth {row['mean_d']:.2f} m, "
                f"WL {row['wl']:.2f} m)"
            )
    return issues


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

@click.command()
@click.option("--out-root", type=click.Path(path_type=Path),
              default=Path("outputs"), show_default=True,
              help="Root directory containing per-city output folders.")
@click.option("--tolerance", type=float, default=0.05, show_default=True,
              help="Fractional tolerance on defended <= undefended check "
                   "(0.05 = 5% slack for numerical noise).")
@click.option("--rp2-cap-km2", type=float, default=50.0, show_default=True,
              help="Maximum RP2 flooded km² considered 'small or zero'. "
                   "Per §6.5 documented observations: coastal RP2 should be "
                   "5-30 km² for most cities; 50 km² is a permissive cap.")
def cli(out_root: Path, tolerance: float, rp2_cap_km2: float) -> None:
    if not out_root.exists():
        click.echo(f"[error] {out_root} does not exist", err=True)
        sys.exit(2)

    # Pair undefended ↔ defended directories.
    pairs: list[tuple[Path, Path]] = []
    for undef_dir in sorted(out_root.iterdir()):
        if not undef_dir.is_dir():
            continue
        if undef_dir.name.endswith("_defended") or "_defended_" in undef_dir.name:
            continue
        defended_dir = undef_dir.with_name(undef_dir.name + "_defended")
        if defended_dir.exists():
            pairs.append((undef_dir, defended_dir))

    if not pairs:
        click.echo(f"[warn] No undefended/defended pairs found under {out_root}.")
        sys.exit(0)

    click.echo("=" * 70)
    click.echo(f"Defended vs undefended review across {len(pairs)} city/scenario pairs")
    click.echo(f"  tolerance     : defended <= undefended * {1 + tolerance:.2f}")
    click.echo(f"  RP2 cap (km²) : {rp2_cap_km2:.0f}")
    click.echo("=" * 70)

    all_issues: list[str] = []
    n_pairs_checked = 0
    n_pairs_skipped = 0

    for undef_dir, defended_dir in pairs:
        label = _scenario_pair_label(undef_dir, defended_dir)
        # Locate summary CSVs by glob -- name pattern includes scenario string.
        undef_csv = next(iter(undef_dir.glob("summary_*.csv")), None)
        def_csv   = next(iter(defended_dir.glob("summary_*.csv")), None)
        if undef_csv is None or def_csv is None:
            click.echo(f"  [skip] {label}: missing summary CSV "
                       f"(undef={undef_csv}, def={def_csv})")
            n_pairs_skipped += 1
            continue
        n_pairs_checked += 1
        undef_summary = _load_summary(undef_csv)
        def_summary   = _load_summary(def_csv)
        all_issues.extend(check_defended_le_undefended(
            label, undef_summary, def_summary, tolerance))
        all_issues.extend(check_monotonic(label, undef_summary, "undef"))
        all_issues.extend(check_monotonic(label, def_summary, "defd"))
        all_issues.extend(check_rp2_small(label, undef_summary, "undef", rp2_cap_km2))
        all_issues.extend(check_rp2_small(label, def_summary, "defd",   rp2_cap_km2))

    click.echo("")
    click.echo(f"Pairs checked: {n_pairs_checked}  (skipped {n_pairs_skipped})")
    click.echo(f"Anomalies    : {len(all_issues)}")
    click.echo("=" * 70)
    if all_issues:
        click.echo("\nDETAILS:\n")
        for issue in all_issues:
            click.echo(issue)
        sys.exit(1)
    else:
        click.echo("\n[OK] All checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    cli()
