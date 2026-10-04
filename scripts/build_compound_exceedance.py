"""Compound / joint-exceedance layer (handoff §6, §12.1).

For a city x scenario, combine the 3-RP per-hazard depth rasters (coastal, fluvial,
pluvial at RP10/100/1000) into, per target RP:

  - marginal (headline) : per-pixel max of the three hazards at that RP (current method).
  - independence-joint   : combined exceedance under hazard independence,
      AEP_joint(d) = 1 - prod_i (1 - AEP_i(d)),
    inverted at the target AEP {0.1, 0.01, 0.001}. Each hazard's depth->AEP curve is
    log-linear in AEP across RP10/100/1000, clipped outside the 10-1000 yr range.
  - sum-of-marginals     : sum_i d_i(RP), the full-positive-dependence upper envelope
    (discussed bound only).

The joint footprint at fixed RP is >= the marginal (three independent processes exceed
any one) and <= the sum. Per-pixel inversion is a vectorised bisection in [marginal, sum].

Usage:
  python scripts/build_compound_exceedance.py --city singapore --scenario present
  python scripts/build_compound_exceedance.py --city all --scenario all
"""
from __future__ import annotations

import glob
from pathlib import Path

import click
import numpy as np
import rasterio

RPS = [10, 100, 1000]
AEP = {10: 0.1, 100: 0.01, 1000: 0.001}
HZ = ["coastal", "fluvial", "pluvial"]
CITIES = ["bangkok", "jakarta", "kuala_lumpur", "singapore"]
SCENARIOS = ["present", "ssp245_2050", "ssp245_2100", "ssp585_2050", "ssp585_2100"]
WET = 0.10  # m


def _resolve(city: str, scen: str, rp: int, hz: str) -> str | None:
    """Glob the depth raster for (city, scenario, rp, hazard) in the fixed atlas
    (outputs/_fixed_atlas). Bangkok uses the _polder (drained) output."""
    stem = f"{city}_ssp585_2020_rp{rp}" if scen == "present" else f"{city}_{scen}_rp{rp}"
    cands = []
    # prefer the pumped-polder output for Bangkok
    for suff in (("_polder", "") if city == "bangkok" else ("",)):
        cands += glob.glob(f"outputs/_fixed_atlas/{stem}{suff}/{hz}/rp_{rp}/{hz}_depth_*_rp{rp}.tif")
    return cands[0] if cands else None


def _read(path: str, shape, transform, crs) -> np.ndarray:
    if path is None:
        return np.zeros(shape, dtype="float64")  # missing hazard (e.g. KL coastal) -> dry
    with rasterio.open(path) as r:
        a = r.read(1).astype("float64")
        if r.nodata is not None:
            a[a == r.nodata] = 0.0
    return np.nan_to_num(a, nan=0.0)


def _aep_of_depth(d, d10, d100, d1000):
    """Vectorised AEP at depth d on a per-hazard depth->AEP curve, log-linear in AEP,
    clipped to [0.001, 0.1]. d10<=d100<=d1000 are the RP10/100/1000 depths."""
    L = np.full_like(d, -1.0)  # log10(AEP); default 0.1 (frequent end)
    # segment RP10..RP100 (L: -1 -> -2)
    seg1 = (d > d10) & (d <= d100)
    den1 = np.where(d100 - d10 > 1e-9, d100 - d10, 1e-9)
    L = np.where(seg1, -1.0 - (d - d10) / den1, L)
    # segment RP100..RP1000 (L: -2 -> -3)
    seg2 = (d > d100) & (d < d1000)
    den2 = np.where(d1000 - d100 > 1e-9, d1000 - d100, 1e-9)
    L = np.where(seg2, -2.0 - (d - d100) / den2, L)
    L = np.where(d >= d1000, -3.0, L)  # clip rare end
    return np.power(10.0, np.clip(L, -3.0, -1.0))


def _joint_depth(depth_at_rp: dict, target_rp: int) -> np.ndarray:
    """Per-pixel independence-joint depth at target_rp, via bisection in [marginal, sum]."""
    # per-hazard sorted depths across RPs
    d = {hz: {rp: depth_at_rp[(hz, rp)] for rp in RPS} for hz in HZ}
    marg = np.maximum.reduce([d[hz][target_rp] for hz in HZ])
    summ = np.add.reduce([d[hz][target_rp] for hz in HZ])
    at = AEP[target_rp]

    def aep_joint(x):
        prod = np.ones_like(x)
        for hz in HZ:
            prod *= (1.0 - _aep_of_depth(x, d[hz][10], d[hz][100], d[hz][1000]))
        return 1.0 - prod

    lo, hi = marg.copy(), np.maximum(summ, marg + 1e-6)
    # if even the sum can't reach the target AEP (clipping floor), the joint is capped at sum
    reachable = aep_joint(hi) <= at + 1e-12
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        deeper = aep_joint(mid) > at  # AEP too high -> need deeper
        lo = np.where(deeper, mid, lo)
        hi = np.where(deeper, hi, mid)
    out = 0.5 * (lo + hi)
    return np.where(reachable, out, summ)  # cap at sum where target unreachable


@click.command()
@click.option("--city", default="all")
@click.option("--scenario", default="all")
def cli(city: str, scenario: str):
    cities = CITIES if city == "all" else [city]
    scens = SCENARIOS if scenario == "all" else [scenario]
    rows = []
    for c in cities:
        for sc in scens:
            # reference grid from the RP100 coastal-or-any raster
            ref = next((_resolve(c, sc, 100, hz) for hz in HZ if _resolve(c, sc, 100, hz)), None)
            if ref is None:
                click.echo(f"[skip] {c}/{sc}: no RP100 raster"); continue
            with rasterio.open(ref) as r:
                shape, transform, crs, prof = r.shape, r.transform, r.crs, r.profile
            # need all 3 RPs present
            missing = [rp for rp in RPS if not any(_resolve(c, sc, rp, hz) for hz in HZ)]
            if missing:
                click.echo(f"[skip] {c}/{sc}: missing RP {missing}"); continue
            depth = {(hz, rp): _read(_resolve(c, sc, rp, hz), shape, transform, crs)
                     for hz in HZ for rp in RPS}
            outdir = Path(f"outputs/_compound/{c}_{sc}"); outdir.mkdir(parents=True, exist_ok=True)
            prof.update(dtype="float32", count=1, nodata=float("nan"), compress="deflate", predictor=2)
            for rp in RPS:
                marg = np.maximum.reduce([depth[(hz, rp)] for hz in HZ])
                summ = np.add.reduce([depth[(hz, rp)] for hz in HZ])
                joint = _joint_depth(depth, rp)
                for name, arr in (("marginal", marg), ("joint", joint), ("sum", summ)):
                    with rasterio.open(outdir / f"{name}_rp{rp}.tif", "w", **prof) as dst:
                        dst.write(arr.astype("float32"), 1)
                km2 = lambda a: float((a >= WET).sum()) * abs(transform.a) * abs(transform.e) / 1e6
                rows.append((c, sc, rp, km2(marg), km2(joint), km2(summ)))
                click.echo(f"  {c:13s} {sc:12s} RP{rp:<4d} marginal={km2(marg):7.1f}  "
                           f"joint={km2(joint):7.1f}  sum={km2(summ):7.1f} km2")
    if rows:
        import csv
        with open("outputs/_compound/extent_summary.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["city", "scenario", "rp", "marginal_km2", "joint_km2", "sum_km2"])
            w.writerows(rows)
        click.echo(f"\nwrote outputs/_compound/extent_summary.csv ({len(rows)} rows)")


if __name__ == "__main__":
    cli()
