from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click


# IPCC AR6 WGI SPM Table SPM.1 — approximate warming (°C) relative to ~2020
# for the two scenarios used in this pipeline.
_DELTA_T_TABLE: dict[tuple[str, int], float] = {
    ("SSP2-4.5", 2050): 1.0,
    ("SSP2-4.5", 2100): 2.1,
    ("SSP5-8.5", 2050): 1.5,
    ("SSP5-8.5", 2100): 4.0,
}


def _infer_delta_T(scenario: str, horizon: int) -> float | None:
    """Return AR6 median warming estimate for scenario/horizon, or None if unknown."""
    return _DELTA_T_TABLE.get((scenario, horizon))


def _run(cmd: list[str]) -> None:
    click.echo(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise click.ClickException(f"Command failed with exit code {result.returncode}: {' '.join(cmd)}")


@click.command()
@click.option("--scenario", default="SSP5-8.5", show_default=True)
@click.option("--horizon", type=int, default=2100, show_default=True)
@click.option("--percentile", type=float, default=50.0, show_default=True)
@click.option("--baseline-year", type=int, default=2020, show_default=True)
@click.option("--fluvial-factor", type=float, default=1.10, show_default=True)
@click.option("--pluvial-factor", type=float, default=1.15, show_default=True)
@click.option(
    "--delta-T",
    "delta_T",
    type=float,
    default=None,
    help=(
        "Warming (°C) relative to baseline year for GEV-CC scaling of fluvial/pluvial "
        "levels.  If omitted the pipeline looks up an AR6 SPM value for the chosen "
        "scenario+horizon (SSP2-4.5 or SSP5-8.5, 2050 or 2100).  Falls back to "
        "--fluvial-factor/--pluvial-factor when no GEV columns are present."
    ),
)
@click.option(
    "--fit-era5/--no-fit-era5",
    "fit_era5",
    default=True,
    show_default=True,
    help=(
        "Run fit_pluvial_baseline_era5.py and fit_fluvial_baseline_era5.py before "
        "building hazard levels.  Requires internet access to Open-Meteo.  "
        "Disable with --no-fit-era5 to reuse the existing baseline CSV as-is."
    ),
)
@click.option(
    "--era5-cache",
    "era5_cache",
    type=click.Path(path_type=Path),
    default=Path("cache/era5_singapore_precip.parquet"),
    show_default=True,
    help="Parquet cache shared between the two ERA5 fit scripts (download once).",
)
@click.option("--connectivity-neighbors", type=click.Choice(["4", "8"]), default="8", show_default=True)
@click.option("--target-resolution", type=float, default=30.0, show_default=True)
@click.option(
    "--dem-output",
    type=click.Path(path_type=Path),
    default=Path("data/singapore/copernicus_dem_utm48n.tif"),
    show_default=True,
)
@click.option(
    "--hazard-level-output",
    type=click.Path(path_type=Path),
    default=Path("data/singapore/hazard_levels_ssp585_2100.csv"),
    show_default=True,
)
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=Path("outputs/singapore_ssp585_2100"),
    show_default=True,
)
@click.option(
    "--baseline-hazards",
    type=click.Path(exists=True, path_type=Path),
    default=Path("data/singapore_hazard_baseline_template.csv"),
    show_default=True,
)
@click.option(
    "--seed-water-raster",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Optional raster (>0 = open/permanent water) aligned to DEM.",
)
@click.option(
    "--sea-mask/--no-sea-mask",
    "build_sea_mask",
    default=True,
    show_default=True,
    help=(
        "Derive and apply a land/sea mask from the DEM before running the flood "
        "model.  Eliminates spurious ocean flooding and enables the pluvial "
        "depression-filling model.  Disable only if you supply a pre-built mask."
    ),
)
@click.option(
    "--fluvial-river-raster",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help=(
        "OSM river mask raster aligned to the DEM (>0 = river cell). "
        "When provided, a HAND raster is computed and used for fluvial inundation "
        "instead of the bathtub method.  Generate the river mask with "
        "scripts/build_river_raster_from_osm.py."
    ),
)
def cli(
    scenario: str,
    horizon: int,
    percentile: float,
    baseline_year: int,
    fluvial_factor: float,
    pluvial_factor: float,
    delta_T: float | None,
    fit_era5: bool,
    era5_cache: Path,
    connectivity_neighbors: str,
    target_resolution: float,
    dem_output: Path,
    hazard_level_output: Path,
    out_dir: Path,
    baseline_hazards: Path,
    seed_water_raster: Path | None,
    build_sea_mask: bool,
    fluvial_river_raster: Path | None,
) -> None:
    py = sys.executable
    project_root = Path(__file__).resolve().parents[1]

    # ------------------------------------------------------------------
    # 0. Fit ERA5 baselines (downloads precipitation, fits GEV, writes CSV)
    # ------------------------------------------------------------------
    if fit_era5:
        click.echo("\n=== Step 0a: fit pluvial baseline (ERA5) ===")
        _run([
            py, str(project_root / "scripts" / "fit_pluvial_baseline_era5.py"),
            "--cache-precip", str(era5_cache),
            "--output", str(baseline_hazards),
        ])
        click.echo("\n=== Step 0b: fit fluvial baseline (ERA5) ===")
        _run([
            py, str(project_root / "scripts" / "fit_fluvial_baseline_era5.py"),
            "--cache-precip", str(era5_cache),
            "--output", str(baseline_hazards),
        ])
    else:
        click.echo("[info] Skipping ERA5 fit — reusing existing baseline CSV.")

    # ------------------------------------------------------------------
    # 1. Fetch Copernicus DEM
    # ------------------------------------------------------------------
    # Singapore bbox, reprojection target for meter-based analysis.
    fetch_cmd = [
        py,
        str(project_root / "scripts" / "fetch_copernicus_dem.py"),
        "--min-lon",
        "103.57",
        "--min-lat",
        "1.15",
        "--max-lon",
        "104.10",
        "--max-lat",
        "1.50",
        "--target-crs",
        "EPSG:32648",
        "--target-resolution",
        str(target_resolution),
        "--output",
        str(dem_output),
    ]
    _run(fetch_cmd)

    # ------------------------------------------------------------------
    # 2. Build scenario hazard levels
    # ------------------------------------------------------------------
    # Resolve delta_T: explicit flag > AR6 lookup > None (falls back to factors)
    effective_delta_T = delta_T if delta_T is not None else _infer_delta_T(scenario, horizon)
    if effective_delta_T is not None:
        click.echo(
            f"[info] Using delta_T={effective_delta_T} °C for GEV-CC scaling "
            f"({scenario} {horizon})."
        )
    else:
        click.echo(
            f"[warn] No delta_T for {scenario} {horizon} — "
            "using uniform fluvial/pluvial factors.",
            err=True,
        )

    build_levels_cmd = [
        py,
        str(project_root / "scripts" / "build_singapore_hazard_levels.py"),
        "--baseline-hazards",
        str(baseline_hazards),
        "--scenario",
        scenario,
        "--horizon",
        str(horizon),
        "--lat",
        "1.2903",
        "--lon",
        "103.8519",
        "--percentile",
        str(percentile),
        "--baseline-year",
        str(baseline_year),
        "--fluvial-factor",
        str(fluvial_factor),
        "--pluvial-factor",
        str(pluvial_factor),
        "--output",
        str(hazard_level_output),
    ]
    if effective_delta_T is not None:
        build_levels_cmd.extend(["--delta-T", str(effective_delta_T)])
    _run(build_levels_cmd)

    sea_mask_raster: Path | None = None
    if build_sea_mask:
        sea_mask_raster = dem_output.parent / "sea_mask_utm48n.tif"
        _run([
            py,
            str(project_root / "scripts" / "build_sea_mask.py"),
            "--dem", str(dem_output),
            "--output", str(sea_mask_raster),
        ])

    hand_raster: Path | None = None
    _default_hand = dem_output.parent / "hand_utm48n.tif"
    if fluvial_river_raster is not None:
        hand_raster = _default_hand
        build_hand_cmd = [
            py,
            str(project_root / "scripts" / "build_hand_raster.py"),
            "--dem",
            str(dem_output),
            "--river-raster",
            str(fluvial_river_raster),
            "--output",
            str(hand_raster),
        ]
        _run(build_hand_cmd)
    elif _default_hand.exists():
        # Reuse a pre-built HAND raster if no river raster was passed but one
        # already exists from a previous run.  Avoids silently falling back to
        # the bathtub method, which only floods cells topographically connected
        # to the sea and misses inland floodplains.
        hand_raster = _default_hand
        click.echo(f"[info] Reusing pre-built HAND raster: {hand_raster}")

    run_model_cmd = [
        py,
        str(project_root / "scripts" / "run_singapore_multihazard.py"),
        "--dem",
        str(dem_output),
        "--hazard-levels",
        str(hazard_level_output),
        "--scenario",
        scenario,
        "--horizon",
        str(horizon),
        "--out-dir",
        str(out_dir),
        "--connectivity-neighbors",
        connectivity_neighbors,
    ]
    if seed_water_raster is not None:
        run_model_cmd.extend(["--seed-water-raster", str(seed_water_raster)])
    if hand_raster is not None:
        run_model_cmd.extend(["--fluvial-hand-raster", str(hand_raster)])
    if sea_mask_raster is not None:
        run_model_cmd.extend(["--sea-mask-raster", str(sea_mask_raster)])
    if fluvial_river_raster is not None:
        run_model_cmd.extend([
            "--tidal-channel-raster", str(fluvial_river_raster),
            "--tidal-burn-elevation", "2.0",
        ])
    _run(run_model_cmd)

    click.echo("")
    click.echo("Singapore flood pipeline completed.")
    click.echo(f"Outputs: {out_dir}")


if __name__ == "__main__":
    cli()
