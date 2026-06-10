"""
Derive a land/sea mask from the Copernicus DEM.

The Copernicus GLO-30 DEM represents open ocean in two ways:

* Most coastal areas: open sea stored as exactly 0.0 m.
* Some coastal bays and delta coastlines (e.g. Manila Bay, HCMC delta):
  open sea stored as NaN (nodata, -9999) due to low TanDEM-X coherence
  over water during acquisition.

This script runs a combined BFS (enabled by default via --nan-bfs):

1. NaN-BFS: seeds from boundary NaN pixels, propagates through all
   connected NaN pixels.  Captures coastlines stored as nodata in GLO-30.
2. 0-m BFS: seeds from boundary pixels at or below 0.0 m, propagates
   through all connected sub-zero pixels.  Standard GLO-30 ocean pixels.

The union of both passes is written as a binary raster:

    1 = land  (retain for flood modelling)
    0 = sea   (exclude — trivially "flooded" by any positive water level)
  255 = nodata

Tidal channel pixels are NOT burned into the sea mask.  Earlier versions
burned channel cells to -0.1 m before the BFS to extend coastal
connectivity, but this caused those cells to be classified as sea, making
them ineligible as tidal seeds in derive_tidal_channel_seeds() (which
requires ~sea_mask).  The tidal seed derivation handles channel
connectivity directly from the sea boundary without needing the burn.

Enclosed water bodies need an interior --seed-latlon point:

* Enclosed bays (Manila Bay): the clipped GLO-30 tile stores the bay as
  <=0 m elevation and the bay does not touch the raster boundary, so
  neither the NaN-BFS nor the 0-m BFS can reach it from the edge.  A
  two-field 'lat,lon' seed flood-fills the enclosed <=0 m basin.
* Elevated inland lakes (Laguna de Bay, ~1.0 m surface): a water body
  above MSL that no 0-m pass can reach.  A three-field 'lat,lon,maxelev'
  seed runs a dedicated BFS over its connected dem<=maxelev component.

Usage
-----
    # Standard (NaN-BFS + 0-m BFS; open coastlines touching the boundary)
    python scripts/build_sea_mask.py \\
      --dem data/singapore/copernicus_dem_utm48n.tif \\
      --output data/singapore/sea_mask_utm48n.tif

    # Manila: enclosed Manila Bay (sea seed) + Laguna de Bay (lake seed)
    python scripts/build_sea_mask.py \\
      --dem data/manila/copernicus_dem_utm51n.tif \\
      --output data/manila/sea_mask_utm51n.tif \\
      --seed-latlon 14.5,120.9 \\
      --seed-latlon 14.41,121.15,2.0

    # Legacy 0-m-only BFS (skips NaN propagation):
    python scripts/build_sea_mask.py \\
      --dem data/singapore/copernicus_dem_utm48n.tif \\
      --output data/singapore/sea_mask_utm48n.tif \\
      --no-nan-bfs
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import numpy as np
import rasterio

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.flood_depth_model import derive_sea_mask, load_dem


@click.command()
@click.option(
    "--dem",
    "dem_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Input Copernicus DEM GeoTIFF.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    required=True,
    help="Output sea-mask GeoTIFF (uint8: 1=land, 0=sea, 255=nodata).",
)
@click.option(
    "--connectivity",
    type=click.Choice(["4", "8"]),
    default="8",
    show_default=True,
    help="BFS neighbourhood connectivity.",
)
@click.option(
    "--nan-bfs/--no-nan-bfs",
    "nan_bfs",
    default=True,
    show_default=True,
    help=(
        "Also seed the BFS from boundary NaN (nodata) pixels.  "
        "Required for GLO-30 tiles where open ocean is stored as nodata "
        "rather than 0.0 m (e.g. Manila Bay, HCMC delta coast).  "
        "Disable with --no-nan-bfs only when the domain has no "
        "NaN-dominated coastlines and legacy 0-m-only behaviour is needed."
    ),
)
@click.option(
    "--seed-latlon",
    "seed_latlon",
    multiple=True,
    metavar="LAT,LON[,MAXELEV]",
    help=(
        "Interior BFS seed point (WGS84).  Repeatable.  Two forms:\n\n"
        "  'lat,lon'          -- sea seed: an open-water body enclosed "
        "within the DEM domain that does not touch the raster boundary "
        "(e.g. Manila Bay, a ~335 km2 region of <=0 m pixels with no "
        "<=0 m path to the raster edge).  Unioned into the 0-m / NaN "
        "BFS seed set.\n\n"
        "  'lat,lon,maxelev'  -- elevated-lake seed: a permanent inland "
        "water body whose surface sits above 0 m (e.g. Laguna de Bay at "
        "~1.0 m).  A dedicated BFS fills its connected dem<=maxelev "
        "component, seeded only from this point.  Pick maxelev safely "
        "above the lake surface but below the surrounding rim."
    ),
)
def cli(
    dem_path: Path,
    output_path: Path,
    connectivity: str,
    nan_bfs: bool,
    seed_latlon: tuple[str, ...],
) -> None:
    dem, profile = load_dem(dem_path)

    # Project any interior seed points (WGS84 lat/lon) onto the DEM grid.
    # Two-field 'lat,lon' seeds feed the standard sea passes (extra_seeds);
    # three-field 'lat,lon,maxelev' seeds each become an independent
    # elevated-water pass for inland lakes above MSL.
    extra_seeds: np.ndarray | None = None
    elevated_water_seeds: list[tuple[np.ndarray, float]] = []
    if seed_latlon:
        from rasterio.transform import rowcol as _rowcol
        from rasterio.warp import transform as _warp_transform

        wgs84 = rasterio.crs.CRS.from_epsg(4326)
        _extra = np.zeros(dem.shape, dtype=bool)
        for latlon in seed_latlon:
            parts = [p.strip() for p in latlon.split(",")]
            if len(parts) not in (2, 3):
                raise click.BadParameter(
                    f"--seed-latlon must be 'lat,lon' or 'lat,lon,maxelev', "
                    f"got {latlon!r}"
                )
            lat, lon = float(parts[0]), float(parts[1])
            max_elev = float(parts[2]) if len(parts) == 3 else None
            xs, ys = _warp_transform(wgs84, profile["crs"], [lon], [lat])
            row, col = _rowcol(profile["transform"], xs[0], ys[0])
            row, col = int(row), int(col)
            if not (0 <= row < dem.shape[0] and 0 <= col < dem.shape[1]):
                click.echo(
                    f"[warn] seed lat={lat}, lon={lon} -> pixel ({row}, {col}) "
                    f"is outside DEM bounds - skipped",
                    err=True,
                )
                continue
            elev = dem[row, col]
            elev_str = "NaN" if not np.isfinite(elev) else f"{elev:.3f} m"
            if max_elev is None:
                is_candidate = (not np.isfinite(elev)) or (elev <= 0.0)
                _extra[row, col] = True
                note = "" if is_candidate else "  [warn] not a sea candidate (>0 m)"
                click.echo(
                    f"  Sea seed: lat={lat}, lon={lon} -> row={row}, "
                    f"col={col}  (DEM elev={elev_str}){note}"
                )
            else:
                seed_arr = np.zeros(dem.shape, dtype=bool)
                seed_arr[row, col] = True
                elevated_water_seeds.append((seed_arr, max_elev))
                is_candidate = np.isfinite(elev) and (elev <= max_elev)
                note = "" if is_candidate else (
                    f"  [warn] DEM elev exceeds maxelev={max_elev} m"
                )
                click.echo(
                    f"  Elevated-lake seed: lat={lat}, lon={lon} -> row={row}, "
                    f"col={col}  (DEM elev={elev_str}, maxelev={max_elev} m){note}"
                )
        if _extra.any():
            extra_seeds = _extra

    mode = "NaN-BFS + 0-m BFS" if nan_bfs else "0-m BFS only (legacy)"
    notes = []
    if extra_seeds is not None:
        notes.append(f"{int(extra_seeds.sum())} sea seed(s)")
    if elevated_water_seeds:
        notes.append(f"{len(elevated_water_seeds)} elevated-lake seed(s)")
    seed_note = f" + {' + '.join(notes)}" if notes else ""
    click.echo(f"Deriving sea mask via BFS from raster boundary ({mode}){seed_note} ...")
    sea_mask = derive_sea_mask(
        dem,
        connectivity=int(connectivity),
        nan_bfs=nan_bfs,
        extra_seeds=extra_seeds,
        elevated_water_seeds=elevated_water_seeds or None,
    )

    nan_mask = ~np.isfinite(dem)
    n_sea   = int(np.count_nonzero(sea_mask))
    n_land  = int(np.count_nonzero(~sea_mask & ~nan_mask))
    n_nodata = int(np.count_nonzero(nan_mask & ~sea_mask))
    pixel_area_km2 = abs(profile["transform"].a * profile["transform"].e) / 1e6
    click.echo(
        f"  Sea    pixels : {n_sea:>8,}  (~{n_sea   * pixel_area_km2:.0f} km2)\n"
        f"  Land   pixels : {n_land:>8,}  (~{n_land  * pixel_area_km2:.0f} km2)\n"
        f"  Nodata pixels : {n_nodata:>8,}"
    )

    # Sea pixels written as 0; nodata (non-sea NaN) written as 255; land as 1.
    land_mask = np.where(sea_mask, 0, np.where(nan_mask, 255, 1)).astype(np.uint8)

    profile_out = profile.copy()
    profile_out.update(dtype="uint8", count=1, compress="deflate", nodata=255)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile_out) as dst:
        dst.write(land_mask, 1)

    click.echo(f"Wrote sea mask: {output_path}  (0=sea, 1=land, 255=nodata)")


if __name__ == "__main__":
    cli()
