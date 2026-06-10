"""Post-hoc pluvial depth cap (stopgap utility).

Clips written pluvial depth rasters to a maximum depth and refreshes the
summary CSV's pluvial rows.  This is *mathematically identical* to the
in-pipeline cap (`run_rain_on_grid(..., peak_depth_cap_m=cap)`, which is just
`peak = min(peak, cap)` applied after the solve) — so for any raster the solver
produced uncapped, clipping here yields exactly what a capped re-run would have
written.  NaN (nodata) is preserved; clipping deep cells does NOT change the
wet/dry classification at any threshold below the cap (so it does not affect the
hotspot hit-rate / CRR — see the validation dossier).

Why a stopgap: the raingrid solver is pathologically slow at high RP
(~30-45 min/RP; limitation #18), so a clean full capped re-run is ~5-6 h. This
caps the existing rasters instantly; the proper fix is the raingrid performance
work (Plan 4), after which the baseline is regenerated cleanly.

Usage
-----
    python scripts/_apply_pluvial_depth_cap.py \
        --out-dir outputs/kuala_lumpur_ssp585_2020 --cap 3.0
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import numpy as np
import pandas as pd
import rasterio

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def clip_raster_to_cap(path: Path, cap: float) -> dict:
    """Clip a depth raster in place to ``cap`` (NaN-preserving). Return stats."""
    with rasterio.open(path) as ds:
        a = ds.read(1)
        profile = ds.profile
        transform = ds.transform
        crs = ds.crs
    capped = np.where(np.isfinite(a), np.minimum(a, cap), a).astype(np.float32)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(capped, 1)
    wet = np.isfinite(capped) & (capped > 0)
    px = abs(transform.a * transform.e)
    n = int(np.count_nonzero(wet))
    return {
        "flooded_area_km2": n * px / 1e6,
        "max_depth_m": float(np.nanmax(capped[wet])) if n else 0.0,
        "mean_depth_m": float(np.nanmean(capped[wet])) if n else 0.0,
        "wet_pixels": n,
    }


@click.command()
@click.option("--out-dir", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--cap", type=float, default=3.0, show_default=True)
def cli(out_dir: Path, cap: float):
    summary_paths = list(out_dir.glob("summary_*.csv"))
    if not summary_paths:
        raise click.ClickException(f"no summary_*.csv in {out_dir}")
    summary_path = summary_paths[0]
    df = pd.read_csv(summary_path)

    pluvial_rasters = sorted(out_dir.glob("pluvial/rp_*/pluvial_depth_*.tif"))
    if not pluvial_rasters:
        raise click.ClickException(f"no pluvial rasters under {out_dir}")

    click.echo(f"Capping {len(pluvial_rasters)} pluvial rasters to {cap} m ...")
    for rpath in pluvial_rasters:
        rp = int(rpath.parent.name.split("_")[1])
        stats = clip_raster_to_cap(rpath, cap)
        mask = (df["hazard_type"] == "pluvial") & (df["return_period"] == rp)
        for k, v in stats.items():
            if k in df.columns:
                df.loc[mask, k] = v
        click.echo(f"  rp{rp:<4} max_depth -> {stats['max_depth_m']:.3f} m  "
                   f"area {stats['flooded_area_km2']:.1f} km2")

    df.to_csv(summary_path, index=False)
    click.echo(f"Updated {summary_path.name}")


if __name__ == "__main__":
    cli()
