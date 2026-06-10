"""Build a densified drainage network raster from OSM waterways.

Fetches OSM *waterway* LINE features (drain, ditch, canal, stream, river, etc.)
for the KL bounding box, optionally adds a DEM-derived flow-accumulation channel
network as a gap-filler, and rasterises the result onto the raingrid DEM grid.

Outputs
-------
Always:
  data/kuala_lumpur/drainage_waterways_utm47n.tif  — waterways-only mask (1=drain)
If --accum-threshold is given:
  data/kuala_lumpur/drainage_combined_utm47n.tif   — waterways UNION DEM channels

Correction note (Plan 5, Task 2):
  An earlier diagnostic script (_fetch_osm_dense_drainage.py) included both
  waterways AND roads. Roads are excluded here because in this model drainage
  outlets are zero-depth sinks; roads flood (documented hotspots), so treating
  roads as sinks is physically wrong and would over-drain the domain.  The real,
  citable drainage network is OSM-mapped waterways only.

Underground filter:
  Culverted / tunnelled channels (tunnel=culvert/yes/covered/building_passage,
  covered=yes, layer<0) are excluded by default — the DEM records surface
  elevation above the pipe, not the channel invert, so including them would
  give spurious low HAND values and distort flow routing.

Usage (waterways-only):
    python scripts/build_drainage_network.py \\
        --dem data/kuala_lumpur/copernicus_dem_utm47n_raingrid.tif

Usage (with DEM flow-accumulation fallback, threshold 200 pixels):
    python scripts/build_drainage_network.py \\
        --dem data/kuala_lumpur/copernicus_dem_utm47n_raingrid.tif \\
        --accum-threshold 200
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import click
import numpy as np
import rasterio
from rasterio.features import rasterize

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# pysheds 0.5 uses np.in1d which was removed in NumPy 2.0.
# Patch it back as an alias for np.isin (same semantics for 1-D inputs).
if not hasattr(np, "in1d"):
    np.in1d = np.isin  # type: ignore[attr-defined]

import osmnx as ox  # noqa: E402

# KL bounding box (WGS84)
KL_BBOX = dict(min_lon=101.40, min_lat=2.90, max_lon=101.95, max_lat=3.42)

# Buffer radius around waterway line features before rasterization (metres, UTM CRS)
BUFFER_M = 15.0

MAX_RETRIES = 3
RETRY_DELAY_S = 15


def _is_underground(row) -> bool:
    """Return True if an OSM waterway feature is culverted, tunnelled, or
    otherwise flows underground.

    Mirrors the filter in build_river_raster_from_osm.py (which seeds the HAND
    drainage mask) so both rasters are consistent.

    Checked tags:
      tunnel   : culvert | yes | covered | building_passage
      covered  : yes
      layer    : any negative integer (below street level)

    Underground waterways are excluded because:
    (1) The DEM records road/building surface elevation above the pipe, not the
        channel invert, so cells around culverts have underestimated HAND and
        produce false surface flooding.
    (2) The model does not represent culvert hydraulic capacity.
    (3) D8 flow routing on a flat road surface does not follow the underground
        pipe path, distorting watershed delineation.
    """
    tunnel = str(row.get("tunnel") or "").strip().lower()
    if tunnel in ("culvert", "yes", "covered", "building_passage"):
        return True
    covered = str(row.get("covered") or "").strip().lower()
    if covered == "yes":
        return True
    try:
        layer = int(row.get("layer") or 0)
        if layer < 0:
            return True
    except (ValueError, TypeError):
        pass
    return False


def _fetch_with_retries(
    bbox: dict,
    tags: dict,
    label: str,
    max_retries: int = MAX_RETRIES,
    retry_delay_s: float = RETRY_DELAY_S,
):
    """Fetch OSM features by bbox with exponential-backoff retry logic.

    Returns a GeoDataFrame, or raises RuntimeError after all retries exhausted.
    The RuntimeError message begins with 'NEEDS_CONTEXT:' so the caller/CI
    can detect network failures that require operator intervention.
    """
    west = bbox["min_lon"]
    south = bbox["min_lat"]
    east = bbox["max_lon"]
    north = bbox["max_lat"]

    delay = retry_delay_s
    for attempt in range(1, max_retries + 1):
        try:
            click.echo(
                f"  [{label}] Attempt {attempt}/{max_retries}: querying Overpass API..."
            )
            # osmnx 2.x bbox order: (left, bottom, right, top) = (west, south, east, north)
            gdf = ox.features_from_bbox(bbox=(west, south, east, north), tags=tags)
            click.echo(f"  [{label}] Fetched {len(gdf):,} features.")
            return gdf
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  [{label}] Attempt {attempt} failed: {exc}")
            if attempt < max_retries:
                click.echo(f"  [{label}] Retrying in {delay:.0f}s...")
                time.sleep(delay)
                delay *= 2  # exponential back-off
            else:
                raise RuntimeError(
                    f"NEEDS_CONTEXT: OSM fetch for '{label}' failed after "
                    f"{max_retries} attempts. Last error: {exc}"
                ) from exc


def _build_waterways_mask(
    dem_crs,
    dem_transform,
    dem_shape: tuple[int, int],
    buffer_m: float,
    include_underground: bool,
) -> np.ndarray:
    """Fetch OSM waterways and rasterize to a uint8 boolean array.

    Returns a numpy array shaped ``dem_shape`` with 1 = drainage channel,
    0 = non-channel.
    """
    waterway_tags = {"waterway": True}
    click.echo("\nFetching OSM waterway features...")
    gdf = _fetch_with_retries(KL_BBOX, waterway_tags, label="waterway")

    # Keep line geometries only (polygons are water bodies, not channels)
    gdf = gdf[gdf.geometry.type.isin(["LineString", "MultiLineString"])].copy()
    if gdf.empty:
        raise click.ClickException(
            "No line-based waterway features found in OSM query."
        )
    click.echo(f"  Line features: {len(gdf):,}")

    # Filter underground/culverted channels
    n_total = len(gdf)
    if not include_underground:
        underground_mask = gdf.apply(_is_underground, axis=1)
        n_underground = int(underground_mask.sum())
        gdf = gdf[~underground_mask].copy()
        click.echo(
            f"  Filtered {n_underground:,} underground/culverted features "
            f"({100.0 * n_underground / n_total:.1f}% of {n_total:,}). "
            f"{len(gdf):,} open-channel features retained."
        )
        if gdf.empty:
            raise click.ClickException(
                "No open-channel waterway features remain after filtering. "
                "Use --include-underground to override."
            )
    else:
        click.echo(
            f"  Including all {n_total:,} waterway features (underground not filtered)."
        )

    # Project to DEM CRS, buffer, collect (geometry, value) pairs
    click.echo(f"  Projecting to {dem_crs} and buffering by {buffer_m} m...")
    gdf_proj = gdf.to_crs(dem_crs)
    shapes = []
    for geom in gdf_proj.geometry:
        if geom is None or geom.is_empty:
            continue
        buffered = geom.buffer(buffer_m)
        if buffered is not None and not buffered.is_empty:
            shapes.append((buffered, 1))

    if not shapes:
        raise click.ClickException("No valid waterway geometries to rasterize.")

    click.echo(f"  Rasterizing {len(shapes):,} buffered geometries...")
    mask = rasterize(
        shapes,
        out_shape=dem_shape,
        transform=dem_transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )

    n_drain = int(np.sum(mask > 0))
    n_total_cells = dem_shape[0] * dem_shape[1]
    click.echo(
        f"  Waterways drainage cells: {n_drain:,} / {n_total_cells:,} "
        f"({100.0 * n_drain / n_total_cells:.2f}%)"
    )
    return mask


def _build_accum_mask(
    dem_path: Path,
    dem_shape: tuple[int, int],
    dem_transform,
    dem_crs,
    accum_threshold: int,
    profile: dict,
) -> np.ndarray:
    """Derive a drainage channel mask from DEM flow accumulation using pysheds.

    Uses the same conditioning pipeline as model/hand_model.py:
      fill pits → fill depressions → resolve flats → D8 flow direction → accumulation.

    The ``np.in1d`` → ``np.isin`` shim (limitation #7) is applied at module
    import time (top of this file) to handle pysheds 0.5 on NumPy ≥ 2.0.

    Parameters
    ----------
    dem_path:
        Path to the DEM GeoTIFF (used to construct the pysheds Grid directly
        rather than via a temp file — avoids double I/O).
    accum_threshold:
        Minimum accumulation count (pixels) to classify as a channel cell.
        At 30 m resolution, 200 pixels ≈ 0.18 km² contributing area.

    Returns
    -------
    mask : uint8 array shaped ``dem_shape``; 1 = channel cell.
    """
    try:
        from pysheds.grid import Grid
    except ImportError as exc:
        raise ImportError(
            "pysheds is required for accumulation-based drainage derivation. "
            "Install with: pip install pysheds"
        ) from exc

    click.echo(
        f"\nDeriving DEM flow-accumulation channels "
        f"(threshold = {accum_threshold} pixels)..."
    )
    click.echo("  Running pysheds conditioning pipeline (may take several minutes)...")

    import os
    import tempfile

    # Write the DEM to a temp file because pysheds Grid.from_raster needs a path
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        prof = profile.copy()
        prof.update(dtype="float32", count=1, nodata=-9999.0)

        with rasterio.open(dem_path) as src:
            dem_arr = src.read(1).astype(np.float32)
        dem_arr[~np.isfinite(dem_arr)] = -9999.0

        with rasterio.open(tmp_path, "w", **prof) as dst:
            dst.write(dem_arr, 1)

        grid = Grid.from_raster(tmp_path)
        raw = grid.read_raster(tmp_path)
        click.echo("  fill_pits...")
        pit_filled = grid.fill_pits(raw)
        click.echo("  fill_depressions...")
        dep_filled = grid.fill_depressions(pit_filled)
        click.echo("  resolve_flats...")
        inflated = grid.resolve_flats(dep_filled)
        click.echo("  flowdir + accumulation...")
        fdir = grid.flowdir(inflated)
        acc = grid.accumulation(fdir)

        acc_arr = np.asarray(acc)
    finally:
        os.unlink(tmp_path)

    mask = (acc_arr >= accum_threshold).astype(np.uint8)
    n_chan = int(np.sum(mask))
    n_total = dem_shape[0] * dem_shape[1]
    click.echo(
        f"  Accumulation-derived channels: {n_chan:,} / {n_total:,} cells "
        f"({100.0 * n_chan / n_total:.2f}%) at threshold={accum_threshold}"
    )
    return mask


def _write_raster(
    arr: np.ndarray,
    profile: dict,
    output_path: Path,
    label: str,
) -> None:
    out_profile = profile.copy()
    out_profile.update(dtype="uint8", count=1, nodata=0, compress="deflate")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **out_profile) as dst:
        dst.write(arr, 1)
    click.echo(f"Wrote {label}: {output_path}")


@click.command()
@click.option(
    "--dem", "dem_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Reference raingrid DEM GeoTIFF (sets CRS, transform, shape).",
)
@click.option(
    "--output-waterways", "waterways_out",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Output path for waterways-only drainage raster. "
        "Default: data/kuala_lumpur/drainage_waterways_utm47n.tif "
        "(derived from dem parent directory)."
    ),
)
@click.option(
    "--output-combined", "combined_out",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Output path for combined (waterways + DEM channels) drainage raster. "
        "Default: data/kuala_lumpur/drainage_combined_utm47n.tif. "
        "Only written when --accum-threshold is provided."
    ),
)
@click.option(
    "--accum-threshold", "accum_threshold",
    type=int,
    default=None,
    show_default=True,
    help=(
        "If set, additionally derive DEM flow-accumulation channels at this "
        "pixel threshold and UNION them with the waterways mask. "
        "Writes the combined raster to --output-combined. "
        "At 30 m resolution, 200 pixels ≈ 0.18 km² contributing area."
    ),
)
@click.option(
    "--buffer-m", "buffer_m",
    type=float,
    default=BUFFER_M,
    show_default=True,
    help="Buffer radius (m) around waterway line features before rasterization.",
)
@click.option(
    "--include-underground/--exclude-underground",
    "include_underground",
    default=False,
    show_default=True,
    help=(
        "Include culverted/tunnelled waterways in the drainage mask. "
        "Default is False: underground channels are excluded because the DEM "
        "records surface elevation above the pipe, not the channel invert."
    ),
)
def cli(
    dem_path: Path,
    waterways_out: Path | None,
    combined_out: Path | None,
    accum_threshold: int | None,
    buffer_m: float,
    include_underground: bool,
) -> None:
    """Build OSM-waterways drainage raster for KL (+ optional DEM fallback)."""

    with rasterio.open(dem_path) as src:
        dem_crs = src.crs
        dem_transform = src.transform
        dem_shape = (src.height, src.width)
        profile = src.profile.copy()

    click.echo(f"DEM CRS   : {dem_crs}")
    click.echo(f"DEM shape : {dem_shape}  transform: {dem_transform}")

    # Resolve default output paths relative to the DEM's parent directory
    data_dir = dem_path.parent
    if waterways_out is None:
        waterways_out = data_dir / "drainage_waterways_utm47n.tif"
    if combined_out is None:
        combined_out = data_dir / "drainage_combined_utm47n.tif"

    # Step 1: Build waterways-only mask
    ww_mask = _build_waterways_mask(
        dem_crs=dem_crs,
        dem_transform=dem_transform,
        dem_shape=dem_shape,
        buffer_m=buffer_m,
        include_underground=include_underground,
    )
    _write_raster(ww_mask, profile, waterways_out, "waterways-only drainage raster")

    # Step 2 (optional): DEM flow-accumulation fallback
    if accum_threshold is not None:
        acc_mask = _build_accum_mask(
            dem_path=dem_path,
            dem_shape=dem_shape,
            dem_transform=dem_transform,
            dem_crs=dem_crs,
            accum_threshold=accum_threshold,
            profile=profile,
        )
        combined = np.where((ww_mask > 0) | (acc_mask > 0), np.uint8(1), np.uint8(0))
        n_combined = int(np.sum(combined))
        n_ww_only = int(np.sum(ww_mask))
        n_acc_only = int(np.sum((ww_mask == 0) & (acc_mask > 0)))
        click.echo(
            f"\nCombined drainage: {n_combined:,} cells "
            f"(waterways: {n_ww_only:,}, "
            f"DEM-only additions: {n_acc_only:,})"
        )
        _write_raster(combined, profile, combined_out, "combined drainage raster")
    else:
        click.echo(
            "\nNo --accum-threshold given — skipping DEM flow-accumulation fallback."
        )

    click.echo("\nDone.")


if __name__ == "__main__":
    cli()
