"""
Validate the IDF-anchored pluvial baselines for all five non-Singapore cities.

This is the per-city counterpart to ``validate_pluvial_singapore.py`` (which
gates against PUB-published ponding observations).  For KL / Bangkok / Jakarta
/ Manila / HCMC we do not have a published ponding-depth-vs-RP curve to gate
against, so the validator instead checks the **derivability** of the baseline
ponding caps from the documented national IDF anchors plus the ponding-cap
formula used in ``cities.py``.

For each city:

1.  Re-derive the Gumbel (mu, sigma) from the two documented IDF anchors
    (RP_a, x_a, RP_b, x_b) -- same logic as ``_refit_pluvial_ifd.fit_gumbel``.
2.  For each return period in the CSV, compute the expected rainfall depth
    P(RP) = mu + sigma * y_T where y_T = -ln(-ln(1 - 1/T)).
3.  Apply the documented ponding-cap formula:
        cap = clip(max(floor, (P - drain) / 1000 * rc / daf), 0.005, 3.0)
4.  Compare to the value stored in ``hazard_baseline_template.csv``.

Verdicts per RP
---------------
    PASS  : recomputed and stored caps agree to within 1 mm
    WARN  : drain-capacity floor (both recomputed and stored at 0.005 m)
    FAIL  : disagreement > 1 mm (CSV out of sync with documented anchors)
    INFO  : reported, no gate

Global checks (per city)
------------------------
    *  Monotonicity: stored caps must be non-decreasing across RPs.
    *  Engineering cap: RP1000 cap must lie strictly below 3.0 m.
    *  RP2/5 ponding above drain capacity is a configuration warning
       (drain too low for the anchor).

Exit codes
----------
    0 : no FAIL verdicts in any city
    1 : at least one FAIL verdict
    2 : a city CSV is missing or malformed

Usage
-----
    python scripts/validate_pluvial_all_cities.py
    python scripts/validate_pluvial_all_cities.py --city manila
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENGINEERING_CAP_M = 3.0
MATCH_TOL_M       = 0.001   # 1 mm — caps are stored to 4 dp
FLOOR_M           = 0.005


CITY_CONFIG: dict[str, dict] = {
    "kuala_lumpur": {
        "name": "Kuala Lumpur",
        "idf_source": "JPS MSMA",
        "rp_a": 2,  "x_a": 90.0,
        "rp_b": 100, "x_b": 165.0,
        "drain": 70.0, "rc": 0.75, "daf": 0.10,
    },
    "bangkok": {
        "name": "Bangkok",
        "idf_source": "TMD / RID",
        "rp_a": 5,  "x_a": 85.0,
        "rp_b": 100, "x_b": 150.0,
        "drain": 80.0, "rc": 0.80, "daf": 0.15,
    },
    "jakarta": {
        "name": "Jakarta",
        "idf_source": "BMKG",
        "rp_a": 2,  "x_a": 85.0,
        "rp_b": 100, "x_b": 175.0,
        "drain": 45.0, "rc": 0.80, "daf": 0.15,
    },
    "manila": {
        "name": "Manila",
        "idf_source": "PAGASA Port Area / JICA 2012 MFCMP",
        "rp_a": 2,  "x_a": 80.0,
        "rp_b": 100, "x_b": 210.0,
        "drain": 100.0, "rc": 0.82, "daf": 0.10,
    },
    "hcmc": {
        "name": "HCMC",
        "idf_source": "JICA 2011 HCMC Drainage Master Plan",
        # JICA 2011 anchors as recorded in scripts/cities.py / fix_hcmc_pluvial.py
        "rp_a": 10, "x_a": 85.0,
        "rp_b": 50, "x_b": 130.0,
        "drain": 70.0, "rc": 0.78, "daf": 0.20,
    },
}

_SEP  = "=" * 78
_DASH = "-" * 78


def fit_gumbel(rp_a: float, x_a: float, rp_b: float, x_b: float) -> tuple[float, float]:
    y_a = -np.log(-np.log(1 - 1 / rp_a))
    y_b = -np.log(-np.log(1 - 1 / rp_b))
    sigma = (x_b - x_a) / (y_b - y_a)
    mu = x_a - sigma * y_a
    return mu, sigma


def gumbel_p(rp: float, mu: float, sigma: float) -> float:
    y = -np.log(-np.log(1 - 1 / rp))
    return mu + sigma * y


def expected_cap(p_mm: float, drain: float, rc: float, daf: float) -> float:
    excess = max(0.0, p_mm - drain)
    cap = excess / 1000.0 * rc / daf
    return round(min(max(FLOOR_M, cap), ENGINEERING_CAP_M), 4)


def validate_city(slug: str, cfg: dict) -> tuple[int, int, int]:
    """Returns (n_pass, n_warn, n_fail)."""
    csv = PROJECT_ROOT / "data" / slug / "hazard_baseline_template.csv"
    if not csv.exists():
        click.echo(f"  [{slug}] CSV not found: {csv}", err=True)
        sys.exit(2)

    df = pd.read_csv(csv)
    pluvial = df[df["hazard_type"].str.lower() == "pluvial"].copy()
    if pluvial.empty:
        click.echo(f"  [{slug}] no pluvial rows in CSV", err=True)
        sys.exit(2)

    pluvial = pluvial.sort_values("return_period").reset_index(drop=True)
    rps  = pluvial["return_period"].astype(int).tolist()
    caps = pluvial["baseline_water_level_m"].astype(float).tolist()

    mu, sigma = fit_gumbel(cfg["rp_a"], cfg["x_a"], cfg["rp_b"], cfg["x_b"])

    click.echo(_SEP)
    click.echo(f"{cfg['name']} ({slug}) — {cfg['idf_source']}")
    click.echo(
        f"  Anchors  : RP{cfg['rp_a']}={cfg['x_a']:.1f} mm  RP{cfg['rp_b']}={cfg['x_b']:.1f} mm"
    )
    click.echo(
        f"  Gumbel   : xi=0  mu={mu:.3f} mm  sigma={sigma:.3f} mm"
    )
    click.echo(
        f"  Ponding  : drain={cfg['drain']:.0f} mm  rc={cfg['rc']:.2f}  daf={cfg['daf']:.2f}"
    )
    click.echo(_SEP)
    click.echo(f"  {'RP':>4}  {'Rain mm':>9}  {'Expected':>10}  {'CSV':>10}  Verdict")
    click.echo(_DASH)

    n_pass = n_warn = n_fail = 0
    fails: list[str] = []

    # Monotonicity (cumulative diff)
    for i in range(1, len(caps)):
        if caps[i] + 1e-4 < caps[i - 1]:
            fails.append(
                f"monotonicity break at RP{rps[i]}: {caps[i]:.4f} < RP{rps[i-1]} {caps[i-1]:.4f}"
            )

    for rp, csv_cap in zip(rps, caps):
        p_mm = gumbel_p(rp, mu, sigma)
        exp_cap = expected_cap(p_mm, cfg["drain"], cfg["rc"], cfg["daf"])
        diff = abs(csv_cap - exp_cap)

        # Decide verdict
        if csv_cap >= ENGINEERING_CAP_M - 1e-6:
            verdict = "FAIL"
            fails.append(
                f"RP{rp}: stored cap {csv_cap:.4f} m hit engineering cap {ENGINEERING_CAP_M:.1f} m"
            )
            n_fail += 1
        elif exp_cap == FLOOR_M and csv_cap == FLOOR_M:
            verdict = "WARN"
            n_warn += 1
        elif diff <= MATCH_TOL_M:
            verdict = "PASS"
            n_pass += 1
        else:
            verdict = "FAIL"
            fails.append(
                f"RP{rp}: stored {csv_cap:.4f} m vs expected {exp_cap:.4f} m "
                f"(diff {diff*1000:.1f} mm)"
            )
            n_fail += 1

        note = ""
        if verdict == "WARN":
            note = "(drain capacity exceeds rainfall — physically zero ponding)"
        click.echo(
            f"  RP{rp:>3}  {p_mm:>8.2f}   {exp_cap:>9.4f}   {csv_cap:>9.4f}   {verdict}  {note}"
        )

    click.echo(_DASH)
    summary = f"  PASS={n_pass}  WARN={n_warn}  FAIL={n_fail}"
    if fails:
        click.echo(summary + "  !! issues:")
        for f in fails:
            click.echo(f"    - {f}")
    else:
        click.echo(summary + "  OK all checks within bounds")
    return n_pass, n_warn, n_fail


@click.command()
@click.option(
    "--city",
    type=click.Choice(list(CITY_CONFIG) + ["all"]),
    default="all",
    show_default=True,
    help="Single city slug or 'all' for the full suite.",
)
def cli(city: str) -> None:
    targets = list(CITY_CONFIG) if city == "all" else [city]

    total_pass = total_warn = total_fail = 0
    for slug in targets:
        cfg = CITY_CONFIG[slug]
        p, w, f = validate_city(slug, cfg)
        total_pass += p
        total_warn += w
        total_fail += f
        click.echo("")

    click.echo(_SEP)
    click.echo(
        f"SUITE TOTAL  PASS={total_pass}  WARN={total_warn}  FAIL={total_fail}"
    )
    click.echo(_SEP)

    if total_fail:
        click.echo("OVERALL: FAIL — at least one CSV is out of sync with its IDF anchors.")
        sys.exit(1)
    elif total_warn:
        click.echo("OVERALL: PASS with warnings (drain-capacity floor zones).")
        sys.exit(0)
    else:
        click.echo("OVERALL: PASS — all baselines reproducible from documented anchors.")
        sys.exit(0)


if __name__ == "__main__":
    cli()
