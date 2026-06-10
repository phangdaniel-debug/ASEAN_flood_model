"""Documented-hotspot validation — the primary gate (Plan 2), generalized to --city.

Builds the combined wet mask at the event RP by unioning whichever per-hazard
depth rasters EXIST for the city (pluvial / fluvial / coastal — KL has no
coastal; delta cities like Bangkok do), scores the committed hotspot register
with the Singapore hotspot_scoring engine, reports hit-rate / CRR / TSS with
bootstrap CIs, and gates against the manifest hotspot thresholds.

Usage
-----
    python scripts/validate_hotspots.py --city kuala_lumpur \
        --out-dir outputs/kuala_lumpur_ssp585_2020 --rp 100

Exit codes: 0 = gate PASS; 1 = gate FAIL; 2 = inputs missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.city_manifest import load_hotspots_from_manifest
from scripts.combine_hazard_depth import combine_depth_rasters
from scripts.hotspot_scoring import hit_vectors, skill_scores, bootstrap_tss_ci


def _hazard_rasters(out_dir, scenario, horizon, rp):
    """Return the list of EXISTING per-hazard depth rasters for this RP."""
    found = []
    for hz in ("pluvial", "fluvial", "coastal"):
        p = out_dir / hz / f"rp_{rp}" / f"{hz}_depth_{scenario}_{horizon}_rp{rp}.tif"
        if p.exists():
            found.append(p)
    return found


def evaluate_gate(hit_rate: float, crr: float,
                  hr_floor: float, crr_floor: float) -> tuple[bool, list[str]]:
    """Pure gate: HR and CRR must each meet their floor. Returns (ok, reasons)."""
    reasons: list[str] = []
    if hit_rate < hr_floor:
        reasons.append(f"hit-rate {hit_rate:.2f} below floor {hr_floor:.2f}")
    if crr < crr_floor:
        reasons.append(f"crr {crr:.2f} below floor {crr_floor:.2f}")
    return (not reasons), reasons


@click.command()
@click.option("--city", required=True,
              help="City slug, e.g. kuala_lumpur or bangkok (selects the hotspot register).")
@click.option("--out-dir", type=click.Path(path_type=Path), required=True,
              help="Pipeline output dir, e.g. outputs/kuala_lumpur_ssp585_2020")
@click.option("--rp", type=int, default=100, show_default=True,
              help="Event-matched return period to score (MYS2021 ~ RP50-100).")
@click.option("--scenario", default="SSP5-8.5", show_default=True)
@click.option("--horizon", type=int, default=2020, show_default=True)
@click.option("--depth-threshold", type=float, default=0.10, show_default=True)
@click.option("--radius-m", type=float, default=50.0, show_default=True,
              help="Hit-radius (m). KL default 50 m matches Nominatim geocoding "
                   "precision (~one city block); SG used 150 m for its denser grid. "
                   "Anchored to geocoding precision, NOT to the gate verdict (see dossier).")
@click.option("--hr-floor", type=float, default=0.70, show_default=True)
@click.option("--crr-floor", type=float, default=0.70, show_default=True)
def cli(city: str, out_dir: Path, rp: int, scenario: str, horizon: int,
        depth_threshold: float, radius_m: float, hr_floor: float, crr_floor: float):
    rasters = _hazard_rasters(out_dir, scenario, horizon, rp)
    if not rasters:
        click.echo(f"[error] no hazard rasters found under {out_dir} for rp{rp}", err=True)
        sys.exit(2)

    combined = combine_depth_rasters(rasters, out_dir / "_validation" / f"combined_rp{rp}.tif")
    hotspots = load_hotspots_from_manifest(city)
    flood_hits, dry_hits = hit_vectors(
        hotspots, combined, radius_m=radius_m, depth_threshold_m=depth_threshold)
    res = skill_scores(flood_hits, dry_hits)
    tss_pt, tss_lo, tss_hi = bootstrap_tss_ci(flood_hits, dry_hits)

    n_pos, n_dry = len(flood_hits), len(dry_hits)
    click.echo(f"{city} hotspot validation @ RP{rp} (threshold {depth_threshold} m, radius {radius_m} m)")
    click.echo(f"  positives n={n_pos}  hits={sum(flood_hits)}  hit-rate={res.hit_rate:.2f}")
    click.echo(f"  dry n={n_dry}  correct-rejects={sum(1 for h in dry_hits if not h)}  CRR={res.correct_reject_rate:.2f}")
    click.echo(f"  TSS={tss_pt:.2f}  95% CI [{tss_lo:.2f}, {tss_hi:.2f}]")

    ok, reasons = evaluate_gate(res.hit_rate, res.correct_reject_rate, hr_floor, crr_floor)
    if ok:
        click.echo("GATE PASS")
        sys.exit(0)
    click.echo("GATE FAIL:")
    for r in reasons:
        click.echo(f"  - {r}")
    sys.exit(1)


if __name__ == "__main__":
    cli()
