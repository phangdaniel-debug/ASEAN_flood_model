"""
Build a Greater Kuala Lumpur composite multi-hazard flood map.

Mosaics the three supplementary KL pipeline outputs onto a single grid:

  kuala_lumpur    — upper Klang / Gombak reach, KL city centre
  klang_shah_alam — middle Klang corridor, Shah Alam / Klang town + coastal zone
  subang_langat   — Langat basin, Kajang / Putrajaya / Sepang

For each hazard type and return period the rasters from all three configs are
reprojected onto the kuala_lumpur reference grid and merged by pixel-wise
maximum depth.  The result goes to outputs/greater_kl_ssp585_2100/ (or
--out-dir) and the combined maps are regenerated via make_combined_flood_maps.

Usage
-----
    python scripts/make_greater_kl_composite.py
    python scripts/make_greater_kl_composite.py --outputs-root outputs --horizon 2100
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

PROJECT_ROOT = Path(__file__).resolve().parents[1]

HAZARDS = ["coastal", "fluvial", "pluvial"]
RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]

# Slug order matters: kuala_lumpur is the reference grid; others reproject onto it.
# klang_shah_alam is listed second (coastal zone); subang_langat third (Langat basin).
SOURCE_SLUGS = ["kuala_lumpur", "klang_shah_alam", "subang_langat"]


def _depth_path(base: Path, hazard: str, scenario: str, horizon: int, rp: int) -> Path:
    return base / hazard / f"rp_{rp}" / f"{hazard}_depth_{scenario}_{horizon}_rp{rp}.tif"


def _scenario_slug(scenario: str) -> str:
    return scenario.lower().replace("-", "").replace(".", "")


@click.command()
@click.option(
    "--outputs-root",
    "outputs_root",
    type=click.Path(path_type=Path),
    default=Path("outputs"),
    show_default=True,
    help="Root directory containing per-city pipeline outputs.",
)
@click.option("--scenario", default="SSP5-8.5", show_default=True)
@click.option("--horizon", type=int, default=2100, show_default=True)
@click.option(
    "--out-dir",
    "out_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for composite rasters and maps.  "
         "Defaults to outputs/greater_kl_<scenario_slug>_<horizon>/",
)
@click.option(
    "--vmax",
    type=float,
    default=1.5,
    show_default=True,
    help="Depth scale max (m) passed to make_combined_flood_maps.",
)
def cli(
    outputs_root: Path,
    scenario: str,
    horizon: int,
    out_dir: Path | None,
    vmax: float,
) -> None:
    scen_slug = _scenario_slug(scenario)

    source_dirs = {
        slug: outputs_root / f"{slug}_{scen_slug}_{horizon}"
        for slug in SOURCE_SLUGS
    }
    for slug, d in source_dirs.items():
        if not d.exists():
            raise click.ClickException(
                f"Source directory missing for '{slug}': {d}\n"
                "Run the city pipeline first: "
                f"python scripts/run_city_pipeline.py --city {slug} --no-fit-era5 --no-fit-coastal"
            )

    if out_dir is None:
        out_dir = outputs_root / f"greater_kl_{scen_slug}_{horizon}"

    click.echo(f"\nGreater KL composite  ({scenario}, {horizon})")
    click.echo(f"  Sources : {', '.join(SOURCE_SLUGS)}")
    click.echo(f"  Output  : {out_dir}\n")

    # ------------------------------------------------------------------ #
    # Reference grid: taken from kuala_lumpur coastal RP2 raster          #
    # ------------------------------------------------------------------ #
    ref_path = _depth_path(source_dirs["kuala_lumpur"], "coastal", scenario, horizon, 2)
    with rasterio.open(ref_path) as ref_src:
        ref_transform = ref_src.transform
        ref_crs       = ref_src.crs
        ref_shape     = ref_src.shape          # (rows, cols)
        ref_profile   = ref_src.profile.copy()

    click.echo(
        f"  Reference grid: {ref_shape[0]}×{ref_shape[1]} cells  "
        f"CRS={ref_crs.to_epsg()}  res={abs(ref_transform.a):.0f} m"
    )

    # ------------------------------------------------------------------ #
    # Mosaic: for each hazard × RP, reproject all configs and take max    #
    # ------------------------------------------------------------------ #
    out_profile = ref_profile.copy()
    out_profile.update(dtype="float32", nodata=np.nan, compress="deflate")

    total = len(HAZARDS) * len(RETURN_PERIODS)
    done  = 0

    for hazard in HAZARDS:
        for rp in RETURN_PERIODS:
            merged   = np.full(ref_shape, np.nan, dtype=np.float32)

            for slug in SOURCE_SLUGS:
                src_path = _depth_path(source_dirs[slug], hazard, scenario, horizon, rp)
                if not src_path.exists():
                    click.echo(f"  [skip] {slug} {hazard} RP{rp} — file not found", err=True)
                    continue

                with rasterio.open(src_path) as src:
                    src_data    = src.read(1).astype(np.float32)
                    src_nodata  = src.nodata
                    src_transform = src.transform
                    src_crs     = src.crs

                # Replace nodata with NaN before reprojection
                if src_nodata is not None:
                    src_data = np.where(src_data == src_nodata, np.nan, src_data)
                src_data = np.where(np.isfinite(src_data), src_data, np.nan)
                src_data = np.maximum(0.0, src_data)  # depths are non-negative

                # Reproject onto reference grid (bilinear; NaN→NaN)
                reprojected = np.full(ref_shape, np.nan, dtype=np.float32)
                reproject(
                    source=src_data,
                    destination=reprojected,
                    src_transform=src_transform,
                    src_crs=src_crs,
                    dst_transform=ref_transform,
                    dst_crs=ref_crs,
                    resampling=Resampling.bilinear,
                    src_nodata=np.nan,
                    dst_nodata=np.nan,
                )

                # Pixel-wise max, treating NaN as "no data" (not zero)
                valid = np.isfinite(reprojected)
                both  = np.isfinite(merged) & valid
                merged[both]  = np.maximum(merged[both], reprojected[both])
                new_only = ~np.isfinite(merged) & valid
                merged[new_only] = reprojected[new_only]

            out_path = _depth_path(out_dir, hazard, scenario, horizon, rp)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(out_path, "w", **out_profile) as dst:
                dst.write(merged, 1)

            done += 1
            click.echo(f"  [{done:2d}/{total}] {hazard:8s} RP{rp:4d}  -> {out_path.name}")

    # ------------------------------------------------------------------ #
    # Generate combined PNGs                                               #
    # ------------------------------------------------------------------ #
    click.echo("\nGenerating combined flood maps …")
    subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "make_combined_flood_maps.py"),
            "--out-dir",   str(out_dir),
            "--scenario",  scenario,
            "--horizon",   str(horizon),
            "--vmax",      str(vmax),
            "--city-name", "Greater KL",
        ],
        check=True,
    )

    click.echo(f"\nDone.  Maps written to: {out_dir}")


if __name__ == "__main__":
    cli()
