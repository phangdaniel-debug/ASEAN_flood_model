# scripts/validate_pluvial_hotspots_singapore.py
"""Comparative hotspot validation for Singapore pluvial (spec sections 4, 7).

Scores our pluvial depth raster and two comparators (Aqueduct; naive baseline)
against the documented hotspot table, computes hit-rate / correct-reject / TSS,
applies numeric gates 3-4, and prints the headline thesis sentence.

Exit codes: 0 = gate passes; 1 = gate fails; 2 = inputs missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.hotspot_scoring import (  # noqa: E402
    load_hotspots, score_table, passes_numeric_gate, ScoreResult,
    hit_vectors, skill_scores, bootstrap_tss_ci, bootstrap_tss_diff_ci,
)

DEFAULT_TABLE = PROJECT_ROOT / "data/singapore/flood_obs/hotspots/sg_pluvial_hotspots.csv"
_SEP = "=" * 72


def _model_raster(out_dir: Path, rp: int) -> Path | None:
    d = out_dir / "pluvial" / f"rp_{rp}"
    if not d.is_dir():
        return None
    tifs = list(d.glob("pluvial_depth_*.tif"))
    return tifs[0] if tifs else None


@click.command()
@click.option("--out-dir", type=click.Path(path_type=Path),
              default=PROJECT_ROOT / "outputs/singapore_ssp585_2100", show_default=True)
@click.option("--table", "table_path", type=click.Path(path_type=Path),
              default=DEFAULT_TABLE, show_default=True)
@click.option("--aqueduct", "aqueduct_path", type=click.Path(path_type=Path), default=None,
              help="Aqueduct comparator raster (from fetch_aqueduct_singapore.py).")
@click.option("--naive", "naive_path", type=click.Path(path_type=Path), default=None,
              help="Naive baseline raster (from build_naive_pluvial_baseline.py).")
@click.option("--rp", type=int, default=50, show_default=True, help="Anchor RP for scoring.")
@click.option("--radius-m", type=float, default=150.0, show_default=True)
@click.option("--depth-threshold", type=float, default=0.10, show_default=True)
@click.option("--hit-rate-floor", type=float, default=0.70, show_default=True)
@click.option("--margin", type=float, default=0.20, show_default=True)
@click.option("--bootstrap/--no-bootstrap", default=True, show_default=True,
              help="Report 95% bootstrap CIs on TSS and paired model-vs-baseline ΔTSS.")
@click.option("--n-boot", type=int, default=10000, show_default=True)
def cli(out_dir, table_path, aqueduct_path, naive_path, rp, radius_m,
        depth_threshold, hit_rate_floor, margin, bootstrap, n_boot):
    hotspots = load_hotspots(table_path)
    n_pos = sum(1 for h in hotspots if h.cls == "flood")
    n_neg = sum(1 for h in hotspots if h.cls == "dry")

    model_raster = _model_raster(out_dir, rp)
    if model_raster is None:
        click.echo(f"[error] No pluvial RP{rp} raster under {out_dir}. "
                   f"Run the Singapore pipeline first.", err=True)
        sys.exit(2)

    def _vecs(path):
        if not path:
            return None
        return hit_vectors(hotspots, path, radius_m=radius_m,
                           depth_threshold_m=depth_threshold)

    model_v = _vecs(model_raster)
    aqueduct_v = _vecs(aqueduct_path)
    naive_v = _vecs(naive_path)

    def _res(v):
        return skill_scores(v[0], v[1]) if v is not None else None

    model = _res(model_v)
    aqueduct = _res(aqueduct_v)
    naive = _res(naive_v)

    click.echo(_SEP)
    click.echo("Singapore pluvial documented-hotspot validation (comparative)")
    click.echo(f"  table: {table_path.name}  positives={n_pos}  dry-controls={n_neg}")
    click.echo(f"  anchor RP{rp}  radius={radius_m:.0f} m  depth>= {depth_threshold:.2f} m")
    click.echo(_SEP)
    click.echo(f"  {'source':<22}{'HR':>7}{'CRR':>7}{'TSS':>7}")
    click.echo("-" * 72)

    def _row(name, r: ScoreResult | None):
        if r is None:
            click.echo(f"  {name:<22}{'(not provided)':>21}")
        else:
            click.echo(f"  {name:<22}{r.hit_rate:>7.2f}{r.correct_reject_rate:>7.2f}{r.tss:>7.2f}")

    _row("our model", model)
    _row("Aqueduct (riv+coast)", aqueduct)
    _row("naive open baseline", naive)
    click.echo(_SEP)

    if bootstrap:
        click.echo(f"  95% bootstrap CIs (stratified, n_boot={n_boot}, seed=12345)")
        click.echo("-" * 72)

        def _ci_row(name, v):
            if v is None:
                return
            pt, lo, hi = bootstrap_tss_ci(v[0], v[1], n_boot=n_boot)
            click.echo(f"  {name:<22} TSS={pt:>5.2f}  [{lo:>5.2f}, {hi:>5.2f}]")

        _ci_row("our model", model_v)
        _ci_row("Aqueduct (riv+coast)", aqueduct_v)
        _ci_row("naive open baseline", naive_v)

        # Paired model-vs-baseline ΔTSS — the test of whether the margin is real.
        for bname, bv in (("Aqueduct", aqueduct_v), ("naive", naive_v)):
            if bv is None:
                continue
            d, dlo, dhi, frac = bootstrap_tss_diff_ci(
                model_v[0], model_v[1], bv[0], bv[1], n_boot=n_boot)
            verdict = ("model better (CI excludes 0)" if dlo > 0 else
                       "baseline better (CI excludes 0)" if dhi < 0 else
                       "indistinguishable (CI spans 0)")
            click.echo(f"  d(model-{bname:<8}) = {d:>5.2f}  [{dlo:>5.2f}, {dhi:>5.2f}]"
                       f"  P(model>base)={frac:.2f}  -> {verdict}")
        click.echo(_SEP)

    baselines = [b for b in (aqueduct, naive) if b is not None]
    if not baselines:
        click.echo("[error] No baselines provided — gate 4 (comparative margin) "
                   "cannot be evaluated. Provide --aqueduct and/or --naive.", err=True)
        sys.exit(2)

    ok, reasons = passes_numeric_gate(model, baselines,
                                      hit_rate_floor=hit_rate_floor, margin=margin)

    parts = [f"our model TSS={model.tss:.2f}"]
    if aqueduct is not None:
        parts.append(f"Aqueduct={aqueduct.tss:.2f}")
    if naive is not None:
        parts.append(f"naive={naive.tss:.2f}")
    click.echo("THESIS: On {} documented flood + {} dry control points, {}.".format(
        n_pos, n_neg, "; ".join(parts)))

    if ok:
        click.echo("OVERALL: PASS (gates 3 & 4).")
        sys.exit(0)
    click.echo("OVERALL: FAIL")
    for r in reasons:
        click.echo(f"  - {r}")
    sys.exit(1)


if __name__ == "__main__":
    cli()
