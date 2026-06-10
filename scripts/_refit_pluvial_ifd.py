"""
One-off refit script for KL/BKK/JKT/Manila pluvial baselines.

Replaces NASA POWER MERRA-2 / ERA5-Land (xi>0 Frechet) fits with national
IDF-anchored Gumbel (xi=0) fits, matching the methodology used for
Singapore (MSS) and HCMC (JICA 2011). Two-anchor Gumbel solve from publicly
documented JPS, TMD, BMKG, and PAGASA IDF values.

Anchors:
  - KL JPS MSMA:        RP2 = 90 mm, RP100 = 165 mm  (Manual Saliran Mesra Alam)
  - Bangkok TMD:        RP5 = 85 mm, RP100 = 150 mm  (Thai Met Dept / RID design)
  - Jakarta BMKG:       RP2 = 85 mm, RP100 = 175 mm  (Indonesia BMKG IDF)
  - Manila PAGASA:      RP2 = 80 mm, RP100 = 210 mm  (Port Area Synoptic IDF;
                        JICA 2012 Manila Flood Control Master Plan, MMDA design)

Run: python scripts/_refit_pluvial_ifd.py
"""
from __future__ import annotations

import sys
from datetime import date as _date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import genextreme

ROOT = Path(__file__).resolve().parents[1]

RPS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]


def fit_gumbel(rp_a: float, x_a: float, rp_b: float, x_b: float) -> tuple[float, float]:
    """Two-anchor Gumbel (xi=0) fit. Returns (mu, sigma)."""
    y_a = -np.log(-np.log(1 - 1 / rp_a))
    y_b = -np.log(-np.log(1 - 1 / rp_b))
    sigma = (x_b - x_a) / (y_b - y_a)
    mu = x_a - sigma * y_a
    return mu, sigma


def ponding_cap(p_mm: float, drain: float, rc: float, daf: float,
                floor: float = 0.005, hard_cap: float = 3.0) -> float:
    excess = max(0.0, p_mm - drain)
    cap = excess / 1000.0 * rc / daf
    return round(min(max(floor, cap), hard_cap), 4)


CITIES = [
    {
        "slug": "kuala_lumpur",
        "name": "KL",
        "idf_source": "JPS MSMA",
        "rp_a": 2, "x_a": 90.0,
        "rp_b": 100, "x_b": 165.0,
        "drain": 70.0, "rc": 0.75, "daf": 0.10,
        "lat": 3.139, "lon": 101.687,
        "prior_note": "replaces NASA POWER MERRA-2 GEV (xi=0.3 Frechet, mu=72mm) which had heavy upper tail",
    },
    {
        "slug": "bangkok",
        "name": "Bangkok",
        "idf_source": "TMD / RID",
        "rp_a": 5, "x_a": 85.0,
        "rp_b": 100, "x_b": 150.0,
        "drain": 80.0, "rc": 0.80, "daf": 0.15,
        "lat": 13.756, "lon": 100.502,
        "prior_note": "replaces NASA POWER MERRA-2 GEV (xi=0.3 Frechet, mu=77.8mm) which hit 3.0m cap at RP1000",
    },
    {
        "slug": "jakarta",
        "name": "Jakarta",
        "idf_source": "BMKG",
        "rp_a": 2, "x_a": 85.0,
        "rp_b": 100, "x_b": 175.0,
        "drain": 45.0, "rc": 0.80, "daf": 0.15,
        "lat": -6.209, "lon": 106.846,
        "prior_note": "replaces NASA POWER MERRA-2 GEV (xi=0.04 Gumbel-ish, mu=75.6mm) which used unanchored fit",
    },
    {
        "slug": "manila",
        "name": "Manila",
        "idf_source": "PAGASA Port Area Synoptic / JICA 2012 MFCMP",
        "rp_a": 2, "x_a": 80.0,
        "rp_b": 100, "x_b": 210.0,
        "drain": 100.0, "rc": 0.82, "daf": 0.10,
        "lat": 14.5995, "lon": 120.9842,
        "prior_note": "replaces ERA5-Land GEV (xi=0.196 Frechet, mu=46.3mm) which gave -27.8% bias vs PAGASA validator (RP100 ERA5=0.59m vs PAGASA target ~0.90m)",
    },
    # ------------------------------------------------------------------
    # Supplementary configs — same national IDF anchors + same per-city
    # drain / rc / daf as their parent metropolitan slug.  Added 2026-05-16
    # after a results audit found these five configs still using the
    # NASA POWER MERRA-2 fallback (some hitting the 3.0 m cap at RP1000).
    # ------------------------------------------------------------------
    {
        "slug": "klang_shah_alam",
        "name": "Klang/Shah Alam",
        "idf_source": "JPS MSMA (same as KL core)",
        "rp_a": 2, "x_a": 90.0,
        "rp_b": 100, "x_b": 165.0,
        "drain": 70.0, "rc": 0.75, "daf": 0.10,
        "lat": 3.07, "lon": 101.515,
        "prior_note": "replaces NASA POWER MERRA-2 (RP1000=2.082m); inherits JPS MSMA anchors from kuala_lumpur",
    },
    {
        "slug": "subang_langat",
        "name": "Subang/Langat",
        "idf_source": "JPS MSMA (same as KL core)",
        "rp_a": 2, "x_a": 90.0,
        "rp_b": 100, "x_b": 165.0,
        "drain": 70.0, "rc": 0.75, "daf": 0.10,
        "lat": 2.975, "lon": 101.76,
        "prior_note": "replaces NASA POWER MERRA-2 (RP1000=3.000m, cap hit); inherits JPS MSMA anchors from kuala_lumpur",
    },
    {
        "slug": "bangkok_chao_phraya",
        "name": "Bangkok Chao Phraya",
        "idf_source": "TMD / RID (same as Bangkok core)",
        "rp_a": 5, "x_a": 85.0,
        "rp_b": 100, "x_b": 150.0,
        "drain": 80.0, "rc": 0.80, "daf": 0.15,
        "lat": 13.756, "lon": 100.502,
        "prior_note": "replaces NASA POWER MERRA-2 (RP1000=3.000m, cap hit); inherits TMD/RID anchors from bangkok",
    },
    {
        "slug": "tangerang",
        "name": "Tangerang",
        "idf_source": "BMKG (same as Jakarta core)",
        "rp_a": 2, "x_a": 85.0,
        "rp_b": 100, "x_b": 175.0,
        "drain": 45.0, "rc": 0.80, "daf": 0.15,
        "lat": -6.225, "lon": 106.625,
        "prior_note": "replaces NASA POWER MERRA-2 (RP1000=2.266m); inherits BMKG anchors from jakarta",
    },
    {
        "slug": "bekasi_depok",
        "name": "Bekasi/Depok",
        "idf_source": "BMKG (same as Jakarta core)",
        "rp_a": 2, "x_a": 85.0,
        "rp_b": 100, "x_b": 175.0,
        "drain": 45.0, "rc": 0.80, "daf": 0.15,
        "lat": -6.30, "lon": 107.00,
        "prior_note": "replaces NASA POWER MERRA-2 (RP1000=3.000m, cap hit); inherits BMKG anchors from jakarta",
    },
]


def refit_city(cfg: dict) -> None:
    slug = cfg["slug"]
    mu, sigma = fit_gumbel(cfg["rp_a"], cfg["x_a"], cfg["rp_b"], cfg["x_b"])
    date_str = str(_date.today())
    src_note = (
        f"{cfg['name']} {cfg['idf_source']} 6h IDF-calibrated Gumbel ({date_str}); "
        f"xi=0.0000 mu={mu:.3f}mm sigma={sigma:.3f}mm; "
        f"anchors RP{cfg['rp_a']}={cfg['x_a']}mm RP{cfg['rp_b']}={cfg['x_b']}mm; "
        f"drain_capacity={cfg['drain']}mm; runoff_coeff={cfg['rc']}; "
        f"depression_area_fraction={cfg['daf']}; "
        f"{cfg['prior_note']}"
    )
    datum_note = (
        "ponding_cap_m; downstream flood_depth_pluvial_ponding "
        "fills DEM depressions up to this level; relative datum"
    )

    csv_path = ROOT / "data" / slug / "hazard_baseline_template.csv"
    df = pd.read_csv(csv_path, dtype=str)

    # Drop existing pluvial rows, keep coastal + fluvial
    other = df[df["hazard_type"].str.lower() != "pluvial"].copy()

    rows = []
    for rp in RPS:
        p = float(genextreme.ppf(1 - 1 / rp, 0, loc=mu, scale=sigma))
        cap_m = ponding_cap(p, cfg["drain"], cfg["rc"], cfg["daf"])
        rows.append({
            "hazard_type": "pluvial",
            "return_period": rp,
            "baseline_water_level_m": cap_m,
            "source_note": src_note,
            "gev_shape": 0.0,
            "gev_loc_mm": round(mu, 3),
            "gev_scale_mm": round(sigma, 3),
            "datum_note": datum_note,
        })
    new_pluvial = pd.DataFrame(rows)
    out = pd.concat([other, new_pluvial], ignore_index=True)
    # Preserve original column order
    out = out[df.columns.tolist()]
    out.to_csv(csv_path, index=False)
    print(f"  {slug}: mu={mu:.3f}, sigma={sigma:.3f} -> "
          f"RP2={rows[0]['baseline_water_level_m']:.4f}, "
          f"RP10={rows[2]['baseline_water_level_m']:.4f}, "
          f"RP100={rows[5]['baseline_water_level_m']:.4f}, "
          f"RP1000={rows[8]['baseline_water_level_m']:.4f}")


def main() -> None:
    print(f"Refitting KL / Bangkok / Jakarta pluvial to national IDF anchors:")
    print(f"  Date: {_date.today()}")
    print()
    for cfg in CITIES:
        refit_city(cfg)
    print()
    print("Done. Run pluvial pipelines to regenerate depth rasters.")


if __name__ == "__main__":
    main()
