"""
HCMC fluvial extension: add Mekong-backwater contribution to Saigon RP stages.

Background
----------
HCMC sits at the confluence of two distinct flood-driving systems:

  1. Saigon-Dong Nai (4,700 km²) — local discharge driver.  Currently
     sampled at Thu Dau Mot (10.98N, 106.65E); fitted by
     ``fit_fluvial_glofas.py``.

  2. Mekong delta backwater (Sep–Nov) — the Mekong main-stem flood
     pulse propagates through the delta and raises water levels in the
     Saigon-Soai Rap reach via tidal backwater.  Trinh et al. (2017)
     and SIWRR delta-hydraulics studies report 0.3–0.5 m of Sep–Nov
     stage uplift at HCMC during typical Mekong flood years (e.g.
     2000, 2011, 2018) relative to dry-season climatology.

Method
------
Independent two-component model with documented additive scaling:

  *  **Saigon component**: take the existing Saigon-only RP stages
     already in ``data/hcmc/hazard_baseline_template.csv`` (produced by
     ``fit_fluvial_glofas.py`` against the Thu Dau Mot point).
  *  **Mekong backwater component**: fetch GloFAS at Tan Chau
     (10.80N, 105.25E) — the canonical upper-delta benchmark.  Fit a
     GEV to annual maximum Mekong discharge.  For each RP, the Mekong
     RP discharge produces an additive backwater stage at HCMC computed
     as:

        backwater_m(RP) = co_factor * (Q_Mekong_RP - Q_Mekong_bf) * BACKWATER_SCALE

     where:
       - Q_Mekong_bf = minimum annual maximum (bankfull proxy)
       - BACKWATER_SCALE = 1.05e-5 m per m³/s above bankfull
            (anchored: Trinh et al. 2017 — 0.4 m HCMC tidal-stage uplift
             at Q=80,000 m³/s, vs ~42,000 m³/s bankfull)
       - co_factor = 0.5 — half-weight to account for incomplete
            co-occurrence (Mekong floods Sep–Nov; Saigon floods may
            occur outside this window) and inter-basin attenuation.

  *  **Combined RP stage** = Saigon RP stage + Mekong backwater(RP).

This produces a documented, defensible additive correction to the
existing Saigon-only baseline.  It is intentionally simpler than a
joint-probability copula model — for a screening pipeline the additive
approximation captures the dominant first-order effect.

Caveats
-------
*  Co-occurrence (`co_factor=0.5`) is an engineering judgement, not a
   measured copula correlation; the true Mekong-Saigon dependence
   structure varies year-to-year.
*  ``BACKWATER_SCALE`` is anchored to one literature reference point;
   real attenuation depends on Cai Mep / Soai Rap channel hydraulics
   and the precise tide phase.
*  Result confidence remains screening-grade ★★★☆☆; a full coupled
   model (SIWRR-MIKE21) would be required to resolve these.

The script updates only the fluvial rows of
``data/hcmc/hazard_baseline_template.csv``; coastal and pluvial rows
are preserved.

Usage
-----
    python scripts/_extend_hcmc_fluvial_mekong.py
    python scripts/_extend_hcmc_fluvial_mekong.py --dry-run
"""
from __future__ import annotations

import sys
from datetime import date as _date
from pathlib import Path

import click
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.cities import CITIES
from scripts.fit_fluvial_glofas import (
    annual_maxima_discharge,
    fetch_daily_discharge,
)
from scripts.gev_utils import fit_gev, gev_return_level

# Mekong upper-delta benchmark (Tan Chau, Vietnam)
MEKONG_LAT = 10.80
MEKONG_LON = 105.25

# Backwater scaling — anchored to Trinh et al. 2017 (SIWRR/MARD):
# Q_Mekong = 80,000 m³/s at Tan Chau produces ~0.4 m HCMC tidal-stage
# uplift relative to non-flood season; Q_bankfull ~ 42,000 m³/s.
# Scale = 0.4 m / (80,000 - 42,000) m³/s = 1.053e-5 m per m³/s above bf.
BACKWATER_SCALE_M_PER_M3S = 1.053e-5

# Co-occurrence weight — partial Mekong-Saigon flood overlap, plus
# Tan-Chau-to-HCMC attenuation.  Screening-grade engineering judgement.
CO_FACTOR = 0.5

XI_MAX = 0.30

RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]


@click.command()
@click.option("--dry-run", is_flag=True, default=False)
def cli(dry_run: bool) -> None:
    city = CITIES["hcmc"]
    out_csv = PROJECT_ROOT / "data" / "hcmc" / "hazard_baseline_template.csv"
    cache_dir = PROJECT_ROOT / "cache"

    click.echo(f"HCMC fluvial extension — Mekong backwater additive  (date={_date.today()})")
    click.echo(f"  Saigon point  : ({city.glofas_lat}N, {city.glofas_lon}E) Thu Dau Mot (existing)")
    click.echo(f"  Mekong point  : ({MEKONG_LAT}N, {MEKONG_LON}E) Tan Chau")
    click.echo(f"  Backwater scale: {BACKWATER_SCALE_M_PER_M3S:.2e} m / (m3/s above Mekong bf)")
    click.echo(f"  Co-occurrence  : co_factor={CO_FACTOR}")
    click.echo("")

    # -----------------------------------------------------------------------
    # 1. Read the existing Saigon-only fluvial baseline
    # -----------------------------------------------------------------------
    df_csv = pd.read_csv(out_csv, dtype=str)
    fluvial_old = df_csv[df_csv["hazard_type"].str.lower() == "fluvial"].copy()
    fluvial_old["return_period"] = fluvial_old["return_period"].astype(int)
    fluvial_old["baseline_water_level_m"] = fluvial_old["baseline_water_level_m"].astype(float)
    fluvial_old = fluvial_old.set_index("return_period").sort_index()
    click.echo("Existing Saigon-only fluvial RP stages:")
    for rp in RETURN_PERIODS:
        click.echo(f"  RP{rp:<4d}  {fluvial_old.loc[rp, 'baseline_water_level_m']:.4f} m")
    click.echo("")

    # -----------------------------------------------------------------------
    # 2. Fetch Mekong discharge at Tan Chau and fit a GEV
    # -----------------------------------------------------------------------
    mekong = fetch_daily_discharge(
        MEKONG_LAT, MEKONG_LON,
        cache_path=cache_dir / "glofas_mekong_tan_chau.parquet",
    )["discharge_m3s"]
    am_M = annual_maxima_discharge(mekong)
    years = sorted(am_M.keys())
    am_M_arr = np.array([am_M[y] for y in years])
    click.echo(f"Mekong annual maxima (Tan Chau): "
               f"n={len(am_M_arr)}  min={am_M_arr.min():.0f}  "
               f"med={np.median(am_M_arr):.0f}  max={am_M_arr.max():.0f}")

    Qbf_M = float(am_M_arr.min())
    click.echo(f"Mekong bankfull proxy (min annual max): {Qbf_M:.0f} m3/s")

    c, loc, scale = fit_gev(am_M_arr, xi_max=XI_MAX)
    xi = -c
    click.echo(f"Mekong GEV: xi={xi:+.4f}  mu={loc:.0f}  sigma={scale:.0f}")
    click.echo("")

    # -----------------------------------------------------------------------
    # 3. For each RP, compute Mekong RP discharge -> additive backwater -> total
    # -----------------------------------------------------------------------
    click.echo(f"  {'RP':>5}  {'Q_Mekong':>10}  {'Backwater':>10}  "
               f"{'Saigon':>8}  {'Combined':>9}")
    click.echo("  " + "-"*54)
    new_rows = []
    for rp in RETURN_PERIODS:
        q_rp = gev_return_level(c, loc, scale, rp)
        backwater_m = max(0.0, CO_FACTOR * (q_rp - Qbf_M) * BACKWATER_SCALE_M_PER_M3S)
        saigon_only = float(fluvial_old.loc[rp, "baseline_water_level_m"])
        combined = round(saigon_only + backwater_m, 4)
        click.echo(f"  RP{rp:<3d}  {q_rp:>10.0f}  {backwater_m:>9.4f}  "
                   f"{saigon_only:>7.4f}  {combined:>8.4f}")

        old_row = fluvial_old.loc[rp].to_dict()
        old_src = str(old_row.get("source_note", ""))
        new_src = (
            old_src
            + f"; +Mekong backwater RP{rp} via Tan Chau ({MEKONG_LAT}N, {MEKONG_LON}E) "
            f"GloFAS GEV xi={xi:+.4f} mu={loc:.0f} sigma={scale:.0f}; "
            f"backwater_m={backwater_m:.4f} "
            f"(scale={BACKWATER_SCALE_M_PER_M3S:.2e}m/m3s, co_factor={CO_FACTOR}, "
            f"Trinh et al. 2017 SIWRR/MARD)"
        )
        new_rows.append({
            "hazard_type": "fluvial",
            "return_period": rp,
            "baseline_water_level_m": combined,
            "source_note": new_src,
            "gev_shape": old_row.get("gev_shape", ""),
            "gev_loc_mm": old_row.get("gev_loc_mm", ""),
            "gev_scale_mm": old_row.get("gev_scale_mm", ""),
            "datum_note": (
                "relative_stage_above_bankfull_m; "
                "Saigon main-stem RP stage + co_factor*Mekong-backwater additive; "
                "compatible_with_HAND_model"
            ),
        })

    if dry_run:
        click.echo("\n[dry-run] Not writing CSV.")
        return

    other = df_csv[df_csv["hazard_type"].str.lower() != "fluvial"].copy()
    out = pd.concat([other, pd.DataFrame(new_rows)], ignore_index=True)
    out = out[df_csv.columns.tolist()]
    out.to_csv(out_csv, index=False)
    click.echo(f"\nWrote {out_csv}")


if __name__ == "__main__":
    cli()
