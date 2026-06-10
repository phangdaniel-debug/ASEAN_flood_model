from __future__ import annotations

import sys
from pathlib import Path

import click
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.convert_datum import validate_datum_notes
from scripts.build_scenarios_from_ar6_zarr import (
    BASE_URL,
    DEFAULT_CACHE_PATH,
    EXPERIMENT_MAP,
    load_cache,
    resolve_sea_level_entry,
    save_cache,
)


_GEV_COLS = {"gev_shape", "gev_loc_mm", "gev_scale_mm"}


def _gev_cc_factor(
    gev_shape: float,
    gev_loc_mm: float,
    gev_scale_mm: float,
    return_period: float,
    delta_T: float,
    cc_rate: float,
    hydraulic_exponent: float,
) -> float:
    """
    Return-period-specific climate scaling factor derived from a CC-perturbed GEV.

    The baseline GEV(mu, sigma, xi) is perturbed proportionally on location and scale,
    which is the first-order approximation of Clausius-Clapeyron intensification:

        mu' = mu x (1 + cc_rate x delta_T)
        sigma' = sigma x (1 + cc_rate x delta_T)
        xi' = xi      (shape is a distributional property, not a scale)

    The precipitation scaling factor for return period T is:

        precip_factor(T) = GEV.ppf(1 - 1/T, mu', sigma', xi) / GEV.ppf(1 - 1/T, mu, sigma, xi)

    For xi > 0 (Frechet tail, typical of tropical convective rainfall) this ratio
    grows with T, reproducing the observed super-CC intensification of rare events.

    A ``hydraulic_exponent`` is applied on top of the precipitation ratio to account
    for the nonlinear rainfall->stage transformation:

        - Pluvial (linear: stage prop_to P):  hydraulic_exponent = 1.0  (exact)
        - Fluvial (Manning: stage prop_to P^0.6 for urban CN=85):  hydraulic_exponent = 0.6

    Parameters
    ----------
    gev_shape : xi in standard sign convention (positive = heavy/Frechet tail).
    gev_loc_mm, gev_scale_mm : GEV location mu and scale sigma in millimetres.
    return_period : exceedance return period in years (T >= 2).
    delta_T : warming relative to the baseline in degC.
    cc_rate : Clausius-Clapeyron fractional intensification rate per degC (default 0.07).
    hydraulic_exponent : power applied to the precipitation ratio (1.0 for pluvial,
        0.6 for fluvial Manning approximation).
    """
    from scipy.stats import genextreme

    c = -gev_shape  # scipy convention: shape c = -xi
    p = 1.0 - 1.0 / return_period
    baseline_q = genextreme.ppf(p, c, loc=gev_loc_mm, scale=gev_scale_mm)
    if baseline_q <= 0:
        raise ValueError(
            f"Baseline GEV quantile is non-positive ({baseline_q:.4f} mm) "
            f"at RP={return_period}. Check GEV parameters (shape={gev_shape:.4f}, "
            f"loc={gev_loc_mm:.3f} mm, scale={gev_scale_mm:.3f} mm)."
        )
    alpha = 1.0 + cc_rate * delta_T
    future_q = genextreme.ppf(p, c, loc=gev_loc_mm * alpha, scale=gev_scale_mm * alpha)
    precip_ratio = float(future_q / baseline_q)
    return float(precip_ratio ** hydraulic_exponent)


@click.command()
@click.option(
    "--baseline-hazards",
    "baseline_hazards_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help=(
        "CSV with columns hazard_type, return_period, baseline_water_level_m. "
        "Baseline represents present-day levels."
    ),
)
@click.option("--scenario", required=True, help="e.g. SSP5-8.5")
@click.option("--horizon", type=int, required=True, help="e.g. 2050 or 2100")
@click.option("--lat", type=float, default=1.2903, show_default=True, help="Singapore site latitude")
@click.option("--lon", type=float, default=103.8519, show_default=True, help="Singapore site longitude")
@click.option("--percentile", type=float, default=50.0, show_default=True)
@click.option("--baseline-year", type=int, default=2020, show_default=True)
@click.option("--workflow-id", type=str, default="wf_1e", show_default=True)
@click.option("--cache-path", "cache_path", type=click.Path(path_type=Path),
              default=DEFAULT_CACHE_PATH, show_default=True,
              help="On-disk cache of AR6 sea-level deltas (offline-repeatability).")
@click.option("--offline", is_flag=True, default=False,
              help="Use ONLY the cached AR6 sea-level; error on a miss (no network).")
@click.option("--refresh-cache", is_flag=True, default=False,
              help="Re-fetch AR6 from the remote zarr, updating the cache.")
@click.option(
    "--fluvial-factor",
    type=float,
    default=1.10,
    show_default=True,
    help="Multiplier applied to baseline fluvial levels for future conditions.",
)
@click.option(
    "--pluvial-factor",
    type=float,
    default=1.15,
    show_default=True,
    help="Multiplier applied to baseline pluvial levels for future conditions.",
)
@click.option(
    "--delta-T",
    "delta_T",
    type=float,
    default=None,
    help=(
        "Warming relative to the baseline year in degC.  When provided AND the "
        "baseline CSV contains GEV parameter columns (gev_shape, gev_loc_mm, "
        "gev_scale_mm), return-period-specific CC scaling is applied to "
        "fluvial and pluvial levels, overriding --fluvial-factor / --pluvial-factor.  "
        "Approximate values from IPCC AR6 WGI SPM: SSP2-4.5/2050 ~ 1.0 degC, "
        "SSP2-4.5/2100 ~ 2.1 degC, SSP5-8.5/2050 ~ 1.5 degC, SSP5-8.5/2100 ~ 4.0 degC "
        "(all relative to ~2020 conditions)."
    ),
)
@click.option(
    "--cc-rate",
    "cc_rate",
    type=float,
    default=0.07,
    show_default=True,
    help=(
        "Clausius-Clapeyron fractional intensification rate per degC warming.  "
        "0.07 (7 %/degC) is appropriate for daily and sub-daily tropical rainfall.  "
        "Only used when --delta-T is provided."
    ),
)
@click.option(
    "--hydraulic-exponent",
    "hydraulic_exponent",
    type=float,
    default=0.6,
    show_default=True,
    help=(
        "Power applied to the precipitation GEV ratio when scaling fluvial stages.  "
        "Accounts for the nonlinear rainfall->stage transformation: Manning's equation "
        "gives stage prop_to Q^(3/5) and Q ~ P for urban catchments (CN=85, Ia << P), "
        "so hydraulic_exponent ~ 0.6.  Pluvial uses 1.0 exactly (linear transform).  "
        "Only used when --delta-T is provided."
    ),
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    required=True,
)
def cli(
    baseline_hazards_path: Path,
    scenario: str,
    horizon: int,
    lat: float,
    lon: float,
    percentile: float,
    baseline_year: int,
    workflow_id: str,
    cache_path: Path,
    offline: bool,
    refresh_cache: bool,
    fluvial_factor: float,
    pluvial_factor: float,
    delta_T: float | None,
    cc_rate: float,
    hydraulic_exponent: float,
    output_path: Path,
) -> None:
    df = pd.read_csv(baseline_hazards_path)
    required = {"hazard_type", "return_period", "baseline_water_level_m"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    # Datum validation - warn if coastal levels lack EGM2008 provenance
    datum_warnings = validate_datum_notes(df)
    for w in datum_warnings:
        click.echo(f"[datum warn] {w}", err=True)
    if scenario not in EXPERIMENT_MAP:
        raise ValueError(f"Unsupported scenario {scenario!r}. Supported: {sorted(EXPERIMENT_MAP)}")

    # Cache-aware AR6 sea-level lookup (offline-repeatable; opens the remote zarr
    # only on a cache miss). The pipeline previously re-fetched every run and
    # broke twice on transient outages.
    _cache = load_cache(cache_path)
    _n_before = len(_cache)
    _entry = resolve_sea_level_entry(
        _cache, workflow_id=workflow_id, scenario=scenario, lat=lat, lon=lon,
        percentile=percentile, baseline_year=baseline_year, horizon=horizon,
        offline=offline, refresh_cache=refresh_cache,
    )
    if len(_cache) != _n_before or refresh_cache:
        save_cache(_cache, cache_path)
    coastal_delta_m = float(_entry["water_level_m"])
    conversion_applied = _entry.get("source_note", "AR6 cached")

    out = df.copy()
    out["hazard_type"] = out["hazard_type"].astype(str).str.lower()
    out["return_period"] = out["return_period"].astype(int)
    out["scenario"] = scenario
    out["horizon"] = horizon
    out["water_level_m"] = out["baseline_water_level_m"].astype(float)

    coastal = out["hazard_type"] == "coastal"
    fluvial = out["hazard_type"] == "fluvial"
    pluvial = out["hazard_type"] == "pluvial"

    # -----------------------------------------------------------------------
    # Coastal: additive AR6 delta
    # -----------------------------------------------------------------------
    out.loc[coastal, "water_level_m"] = out.loc[coastal, "water_level_m"] + coastal_delta_m
    out.loc[coastal, "scaling_factor"] = np.nan
    out.loc[coastal, "scaling_method"] = f"coastal_delta_additive(delta_m={coastal_delta_m:.4f})"

    # -----------------------------------------------------------------------
    # Fluvial / Pluvial: return-period-specific GEV-CC or uniform factor
    # -----------------------------------------------------------------------
    use_gev = delta_T is not None and _GEV_COLS.issubset(out.columns)
    if delta_T is not None and not use_gev:
        click.echo(
            "[warn] --delta-T provided but baseline CSV is missing GEV columns "
            f"({sorted(_GEV_COLS)}). Falling back to uniform factors.",
            err=True,
        )

    if use_gev:
        scaling_note_fluvial = (
            f"GEV-CC(delta_T={delta_T}C, cc_rate={cc_rate}, "
            f"hydraulic_exponent={hydraulic_exponent})"
        )
        scaling_note_pluvial = (
            f"GEV-CC(delta_T={delta_T}C, cc_rate={cc_rate}, hydraulic_exponent=1.0)"
        )
        for idx in out[fluvial].index:
            rp = int(out.at[idx, "return_period"])
            factor = _gev_cc_factor(
                gev_shape=float(out.at[idx, "gev_shape"]),
                gev_loc_mm=float(out.at[idx, "gev_loc_mm"]),
                gev_scale_mm=float(out.at[idx, "gev_scale_mm"]),
                return_period=rp,
                delta_T=delta_T,
                cc_rate=cc_rate,
                hydraulic_exponent=hydraulic_exponent,
            )
            out.at[idx, "water_level_m"] = out.at[idx, "water_level_m"] * factor
            out.at[idx, "scaling_factor"] = factor
            out.at[idx, "scaling_method"] = scaling_note_fluvial
        for idx in out[pluvial].index:
            rp = int(out.at[idx, "return_period"])
            factor = _gev_cc_factor(
                gev_shape=float(out.at[idx, "gev_shape"]),
                gev_loc_mm=float(out.at[idx, "gev_loc_mm"]),
                gev_scale_mm=float(out.at[idx, "gev_scale_mm"]),
                return_period=rp,
                delta_T=delta_T,
                cc_rate=cc_rate,
                hydraulic_exponent=1.0,  # pluvial transform is linear
            )
            out.at[idx, "water_level_m"] = out.at[idx, "water_level_m"] * factor
            out.at[idx, "scaling_factor"] = factor
            out.at[idx, "scaling_method"] = scaling_note_pluvial
        fluvial_pluvial_note = (
            "Fluvial/pluvial: return-period-specific GEV-CC scaling; "
            f"delta_T={delta_T}C; cc_rate={cc_rate}/C."
        )
    else:
        out.loc[fluvial, "water_level_m"] = out.loc[fluvial, "water_level_m"] * fluvial_factor
        out.loc[fluvial, "scaling_factor"] = fluvial_factor
        out.loc[fluvial, "scaling_method"] = f"uniform(factor={fluvial_factor})"
        out.loc[pluvial, "water_level_m"] = out.loc[pluvial, "water_level_m"] * pluvial_factor
        out.loc[pluvial, "scaling_factor"] = pluvial_factor
        out.loc[pluvial, "scaling_method"] = f"uniform(factor={pluvial_factor})"
        fluvial_pluvial_note = (
            "Fluvial/pluvial: baseline scaled by uniform user-provided factors "
            f"(fluvial={fluvial_factor}, pluvial={pluvial_factor}). "
            "Provide --delta-T to enable return-period-specific GEV-CC scaling."
        )

    out["source_note"] = (
        "Coastal: IPCC AR6 Zarr delta added to baseline. " + fluvial_pluvial_note
    )
    out["coastal_delta_m"] = coastal_delta_m
    out["coastal_delta_conversion"] = conversion_applied
    out["coastal_source_url"] = _entry.get("source_url", "AR6 cached")

    cols = [
        "hazard_type",
        "return_period",
        "scenario",
        "horizon",
        "water_level_m",
        "scaling_factor",
        "scaling_method",
        "source_note",
        "coastal_delta_m",
        "coastal_delta_conversion",
        "coastal_source_url",
    ]
    out = out[cols].sort_values(["hazard_type", "return_period"]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    # Print a summary table showing per-RP factors for fluvial and pluvial
    if use_gev:
        click.echo(f"\nReturn-period-specific CC scaling (delta_T={delta_T} degC):")
        click.echo(f"  {'RP':>6}  {'fluvial factor':>16}  {'pluvial factor':>16}")
        click.echo(f"  {'-'*6}  {'-'*16}  {'-'*16}")
        fl = out[out["hazard_type"] == "fluvial"].set_index("return_period")["scaling_factor"]
        pl = out[out["hazard_type"] == "pluvial"].set_index("return_period")["scaling_factor"]
        for rp in sorted(set(fl.index) | set(pl.index)):
            fl_val = f"{fl[rp]:.4f}" if rp in fl.index else "  n/a  "
            pl_val = f"{pl[rp]:.4f}" if rp in pl.index else "  n/a  "
            click.echo(f"  {rp:>6d}  {fl_val:>16}  {pl_val:>16}")

    click.echo(f"Wrote Singapore hazard levels: {output_path}")


if __name__ == "__main__":
    cli()
