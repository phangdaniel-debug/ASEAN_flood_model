"""
One-off migration: convert each city's pluvial ``baseline_water_level_m``
from the legacy lumped ``ponding_cap_m`` to ``excess_depth_m`` (post-drain
rain depth, m) for the catchment-routed fill-spill pluvial model.

The catchment-routed model (model/pluvial_model.py, May 2026) consumes the
post-drain excess rain depth and applies the runoff coefficient per-cell at
run time.  The pluvial baselines, however, were written by
``_refit_pluvial_ifd.py`` (and the Singapore / HCMC equivalents) as the old
lumped ponding cap ``min(max(0.005, excess/1000 * rc/daf), 3.0)``.

Every pluvial row in ``data/<city>/hazard_baseline_template.csv`` already
stores the IDF-anchored Gumbel parameters (``gev_loc_mm``, ``gev_scale_mm``)
and the drain capacity (inside ``source_note``).  ``excess_depth_m`` is
therefore recomputed directly, with no runoff coefficient or
depression-area fraction applied:

    p_mm           = genextreme.ppf(1 - 1/rp, 0, loc=gev_loc_mm, scale=gev_scale_mm)
    excess_depth_m = max(0, p_mm - drain_capacity_mm) / 1000

This matches the formula in the redesigned ``fit_pluvial_baseline_era5.py``.
``source_note`` is left untouched (it is provenance); only
``baseline_water_level_m`` and ``datum_note`` change.

See docs/superpowers/specs/2026-05-21-catchment-routed-pluvial-model-design.md

Run once:  python scripts/_migrate_pluvial_baselines_excess_depth.py
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from scipy.stats import genextreme

ROOT = Path(__file__).resolve().parents[1]

CITIES = [
    "singapore", "kuala_lumpur", "bangkok", "bangkok_chao_phraya",
    "klang_shah_alam", "subang_langat", "tangerang", "bekasi_depok",
    "jakarta", "manila", "hcmc",
]

_DRAIN_RE = re.compile(r"drain_capacity\s*=\s*([0-9.]+)\s*mm")
_NEW_DATUM = (
    "excess_depth_m (post-drain rain depth, m); routed by "
    "flood_depth_pluvial_fillspill which applies the per-cell runoff "
    "coefficient at run time"
)


def migrate_city(slug: str) -> bool:
    """Rewrite one city's pluvial baseline rows in place.  Returns True if
    the file was changed."""
    csv_path = ROOT / "data" / slug / "hazard_baseline_template.csv"
    if not csv_path.exists():
        print(f"  {slug:22s}  SKIP — no baseline template")
        return False

    df = pd.read_csv(csv_path)
    is_pluvial = df["hazard_type"].astype(str).str.lower() == "pluvial"
    if not is_pluvial.any():
        print(f"  {slug:22s}  SKIP — no pluvial rows")
        return False

    by_rp: dict[int, float] = {}
    for idx in df.index[is_pluvial]:
        rp = float(df.at[idx, "return_period"])
        mu = float(df.at[idx, "gev_loc_mm"])
        sigma = float(df.at[idx, "gev_scale_mm"])
        match = _DRAIN_RE.search(str(df.at[idx, "source_note"]))
        if match is None:
            raise ValueError(
                f"{slug} RP{rp:g}: no 'drain_capacity=<n>mm' in source_note"
            )
        drain_mm = float(match.group(1))
        p_mm = float(genextreme.ppf(1.0 - 1.0 / rp, 0, loc=mu, scale=sigma))
        excess_depth_m = round(max(0.0, p_mm - drain_mm) / 1000.0, 6)
        df.at[idx, "baseline_water_level_m"] = excess_depth_m
        df.at[idx, "datum_note"] = _NEW_DATUM
        by_rp[int(rp)] = excess_depth_m

    df.to_csv(csv_path, index=False)
    print(
        f"  {slug:22s}  {int(is_pluvial.sum())} rows -> excess_depth_m   "
        f"RP2={by_rp.get(2, float('nan')):.4f}  "
        f"RP100={by_rp.get(100, float('nan')):.4f}  "
        f"RP1000={by_rp.get(1000, float('nan')):.4f}"
    )
    return True


def main() -> None:
    print("Migrating pluvial baselines: ponding_cap_m -> excess_depth_m")
    print("=" * 70)
    changed = sum(migrate_city(slug) for slug in CITIES)
    print("=" * 70)
    print(f"Done. {changed} city baseline templates updated.")


if __name__ == "__main__":
    main()
