"""
Overlay OpenStreetMap street tiles on combined flood maps.

Re-renders map_combined_* PNG files with a street basemap underneath the
flood-depth layer, so readers can orient themselves spatially.

Usage
-----
    python scripts/overlay_street_maps.py \
        --out-dir outputs/singapore_ssp585_2100 \
        --scenario SSP5-8.5 --horizon 2100

Output files are written to <out-dir>/street_overlay/ with the same
naming convention as make_combined_flood_maps.py.
"""
from __future__ import annotations

from pathlib import Path

import click
import contextily as ctx
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject

RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]

HAZARD_CMAPS = {
    "coastal": "Blues",
    "fluvial": "Oranges",
    "pluvial": "Greens",
}
HAZARD_COLOURS = {
    "coastal": "#2166AC",
    "fluvial": "#D94801",
    "pluvial": "#1A9850",
}

DST_CRS = "EPSG:3857"  # Web Mercator used by contextily tile providers

# CartoDB Voyager: subtle green parks, blue water, light road network —
# enough colour to orient the reader without competing with flood layers.
BASEMAP = ctx.providers.CartoDB.Voyager

# Inches of usable map width for the single-RP figures.
# Height is derived from the actual geographic aspect ratio so the island
# is never stretched or squashed.
_MAP_W_IN = 8.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_depth_3857(
    root: Path,
    hazard: str,
    scenario: str,
    horizon: int,
    rp: int,
    pluvial_floor: float = 0.0,
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """
    Load a depth raster and reproject it to EPSG:3857.

    Returns
    -------
    data : np.ndarray  shape (H, W), float32, nodata → 0
    bounds_3857 : (left, bottom, right, top) in EPSG:3857
    """
    p = root / hazard / f"rp_{rp}" / f"{hazard}_depth_{scenario}_{horizon}_rp{rp}.tif"
    if not p.exists():
        raise FileNotFoundError(f"Missing raster: {p}")

    with rasterio.open(p) as src:
        transform, width, height = calculate_default_transform(
            src.crs, DST_CRS, src.width, src.height, *src.bounds
        )
        data = np.full((height, width), np.nan, dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=data,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=DST_CRS,
            resampling=Resampling.nearest,
            dst_nodata=np.nan,
        )
        bounds_3857 = rasterio.transform.array_bounds(height, width, transform)

    data[~np.isfinite(data)] = 0.0
    data[data < 0] = 0.0
    # Suppress sub-threshold pluvial "puddles" — see make_combined_flood_maps._load_depth.
    if hazard == "pluvial" and pluvial_floor > 0:
        data[data < pluvial_floor] = 0.0
    return data, bounds_3857  # bounds_3857 = (left, bottom, right, top)


def _load_land_mask_3857(
    root: Path, scenario: str, horizon: int, rp: int
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Reproject coastal raster to EPSG:3857 and return finite-pixel mask."""
    p = (
        root
        / "coastal"
        / f"rp_{rp}"
        / f"coastal_depth_{scenario}_{horizon}_rp{rp}.tif"
    )
    with rasterio.open(p) as src:
        transform, width, height = calculate_default_transform(
            src.crs, DST_CRS, src.width, src.height, *src.bounds
        )
        raw = np.full((height, width), np.nan, dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=raw,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=DST_CRS,
            resampling=Resampling.nearest,
            dst_nodata=np.nan,
        )
        bounds_3857 = rasterio.transform.array_bounds(height, width, transform)
    return np.isfinite(raw), bounds_3857


def _make_combined_rgba(
    depths: dict[str, np.ndarray], vmax: float
) -> np.ndarray:
    """RGBA image: each pixel coloured by the dominant hazard, alpha ∝ depth."""
    rows, cols = next(iter(depths.values())).shape
    rgba = np.zeros((rows, cols, 4), dtype=np.float32)

    stacked = np.stack([depths[h] for h in HAZARD_CMAPS], axis=0)
    dominant_idx = np.argmax(stacked, axis=0)
    max_depth = stacked.max(axis=0)

    hazard_list = list(HAZARD_CMAPS.keys())
    for i, hazard in enumerate(hazard_list):
        cmap = plt.get_cmap(HAZARD_CMAPS[hazard])
        mask = (dominant_idx == i) & (max_depth > 0)
        if not mask.any():
            continue
        norm_d = np.clip(max_depth[mask] / vmax, 0.0, 1.0)
        mapped = cmap(0.4 + 0.6 * norm_d)
        rgba[mask] = mapped

    rgba[max_depth <= 0, 3] = 0.0
    return rgba


# ---------------------------------------------------------------------------
# Per-RP map
# ---------------------------------------------------------------------------

def plot_combined_with_streets(
    root: Path,
    scenario: str,
    horizon: int,
    rp: int,
    vmax: float,
    out_path: Path,
    basemap_alpha: float,
    flood_alpha: float,
    city_name: str = "",
    pluvial_floor: float = 0.0,
) -> None:
    # Load and reproject all hazard layers
    depths: dict[str, np.ndarray] = {}
    bounds_3857: tuple[float, float, float, float] | None = None
    for h in HAZARD_CMAPS:
        data, b = _load_depth_3857(root, h, scenario, horizon, rp, pluvial_floor=pluvial_floor)
        depths[h] = data
        if bounds_3857 is None:
            bounds_3857 = b

    assert bounds_3857 is not None
    left, bottom, right, top = bounds_3857

    rgba = _make_combined_rgba(depths, vmax)
    max_depth = np.stack(list(depths.values())).max(axis=0)
    wet_km2 = float((max_depth > 0).sum()) * 30 * 30 / 1e6

    # Derive figure height from the true geographic aspect ratio so Singapore
    # is never stretched.  Add room for title (0.6 in) and axis labels (0.9 in).
    geo_aspect = (right - left) / (top - bottom)   # ~1.51 for Singapore
    map_h_in   = _MAP_W_IN / geo_aspect
    fig_w      = _MAP_W_IN + 1.8   # colorbar + right margin
    fig_h      = map_h_in + 1.5    # title + xlabel
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=200)
    ax.set_xlim(left, right)
    ax.set_ylim(bottom, top)
    ax.set_aspect("equal")

    # --- Street basemap ---
    ctx.add_basemap(
        ax,
        crs=DST_CRS,
        source=BASEMAP,
        alpha=basemap_alpha,
        zoom="auto",
    )

    # --- Flood-depth overlay ---
    rgba_display = rgba.copy()
    rgba_display[..., 3] *= flood_alpha
    ax.imshow(
        rgba_display,
        extent=[left, right, bottom, top],
        origin="upper",
        zorder=2,
        interpolation="bilinear",
    )

    # Depth colour-bar
    sm = plt.cm.ScalarMappable(
        cmap="Greys_r", norm=mcolors.Normalize(vmin=0, vmax=vmax)
    )
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label("Flood depth (m)", fontsize=9)

    # Hazard legend
    patches = [
        mpatches.Patch(color=HAZARD_COLOURS[h], label=h.title())
        for h in HAZARD_CMAPS
    ]
    ax.legend(handles=patches, loc="lower right", fontsize=8, framealpha=0.85)

    title_city = f"{city_name} " if city_name else ""
    ax.set_title(
        f"{title_city}Multi-Hazard Flood Depth  ({scenario}, {horizon}, RP{rp})\n"
        f"Total flooded area: {wet_km2:.1f} km²",
        fontsize=11,
    )
    ax.tick_params(labelsize=7)
    ax.set_xlabel("Easting (Web Mercator)", fontsize=8)
    ax.set_ylabel("Northing (Web Mercator)", fontsize=8)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    click.echo(f"Wrote: {out_path}")


# ---------------------------------------------------------------------------
# 3 × 3 comparison panel
# ---------------------------------------------------------------------------

def plot_rp_comparison_with_streets(
    root: Path,
    scenario: str,
    horizon: int,
    vmax: float,
    out_path: Path,
    basemap_alpha: float,
    flood_alpha: float,
    city_name: str = "",
    pluvial_floor: float = 0.0,
) -> None:
    rps = RETURN_PERIODS
    ncols, nrows_grid = 3, 3

    # Pre-compute shared bounds from the first RP
    _, bounds_3857 = _load_depth_3857(root, "coastal", scenario, horizon, rps[0])
    left, bottom, right, top = bounds_3857

    # Size each cell to match the geographic aspect ratio
    geo_aspect  = (right - left) / (top - bottom)
    cell_w_in   = 5.2
    cell_h_in   = cell_w_in / geo_aspect
    fig_w       = cell_w_in * ncols + 0.4
    fig_h       = cell_h_in * nrows_grid + 1.2   # suptitle + legend
    fig, axes = plt.subplots(nrows_grid, ncols, figsize=(fig_w, fig_h), dpi=150)
    title_city = f"{city_name} " if city_name else ""
    fig.suptitle(
        f"{title_city}Multi-Hazard Flood Depth — Return Period Comparison\n"
        f"({scenario}, {horizon})  |  colour = dominant hazard  |  vmax = {vmax:.1f} m",
        fontsize=12,
        y=1.01,
    )

    for idx, rp in enumerate(rps):
        ax = axes[idx // ncols, idx % ncols]
        ax.set_xlim(left, right)
        ax.set_ylim(bottom, top)
        ax.set_aspect("equal")

        # Street basemap
        ctx.add_basemap(
            ax,
            crs=DST_CRS,
            source=BASEMAP,
            alpha=basemap_alpha,
            zoom="auto",
        )

        # Flood overlay
        depths = {
            h: _load_depth_3857(root, h, scenario, horizon, rp, pluvial_floor=pluvial_floor)[0]
            for h in HAZARD_CMAPS
        }
        rgba = _make_combined_rgba(depths, vmax)
        max_depth = np.stack(list(depths.values())).max(axis=0)
        wet_km2 = float((max_depth > 0).sum()) * 30 * 30 / 1e6

        rgba_display = rgba.copy()
        rgba_display[..., 3] *= flood_alpha
        ax.imshow(
            rgba_display,
            extent=[left, right, bottom, top],
            origin="upper",
            zorder=2,
            interpolation="bilinear",
        )
        ax.set_title(f"RP {rp}  ({wet_km2:.0f} km²)", fontsize=9)
        ax.axis("off")

    # Shared legend
    patches = [
        mpatches.Patch(color=HAZARD_COLOURS[h], label=h.title())
        for h in HAZARD_CMAPS
    ]
    fig.legend(
        handles=patches,
        loc="lower center",
        ncol=3,
        fontsize=9,
        framealpha=0.9,
        bbox_to_anchor=(0.5, -0.02),
    )

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    click.echo(f"Wrote: {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--out-dir", "root",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Directory containing coastal/fluvial/pluvial sub-folders.",
)
@click.option("--scenario", required=True, help="Climate scenario string, e.g. SSP5-8.5")
@click.option("--horizon", type=int, required=True, help="Climate horizon year, e.g. 2100")
@click.option(
    "--vmax", type=float, default=1.5, show_default=True,
    help="Depth scale maximum (m) shared across all maps.",
)
@click.option(
    "--return-periods", "rp_list",
    default=",".join(str(r) for r in RETURN_PERIODS),
    show_default=True,
    help="Comma-separated return periods.",
)
@click.option(
    "--basemap-alpha", type=float, default=1.0, show_default=True,
    help="Opacity of the street basemap layer (0=transparent, 1=opaque).",
)
@click.option(
    "--flood-alpha", type=float, default=0.80, show_default=True,
    help="Opacity of the flood-depth overlay (0=transparent, 1=opaque).",
)
@click.option(
    "--sub-dir", "sub_dir",
    default="street_overlay",
    show_default=True,
    help="Sub-directory inside --out-dir where outputs are saved.",
)
@click.option(
    "--city-name",
    "city_name",
    default="",
    show_default=True,
    help="City display name shown in map titles (e.g. 'Bangkok').",
)
@click.option(
    "--pluvial-floor",
    "pluvial_floor",
    type=float,
    default=0.05,
    show_default=True,
    help=(
        "Suppress pluvial cells with depth below this threshold (m). "
        "Default 0.05 m hides the 0.005 m drain-capacity floor that "
        "paints every spurious GLO-30 micro-depression at low RPs. "
        "Set to 0 to render every wet cell."
    ),
)
@click.option(
    "--per-rp/--no-per-rp",
    "per_rp",
    default=False,
    show_default=True,
    help=(
        "Write the nine individual per-RP street-overlay PNGs in "
        "addition to the 3x3 comparison panel. Default OFF (May 2026) "
        "to reduce folder clutter; the comparison panel covers the "
        "same information at a glance."
    ),
)
def cli(
    root: Path,
    scenario: str,
    horizon: int,
    vmax: float,
    rp_list: str,
    basemap_alpha: float,
    flood_alpha: float,
    sub_dir: str,
    city_name: str,
    pluvial_floor: float,
    per_rp: bool,
) -> None:
    rps = [int(x) for x in rp_list.split(",")]
    out_root = root / sub_dir

    if per_rp:
        click.echo(f"Fetching street tiles and rendering {len(rps)} per-RP maps + comparison panel …")
        for rp in rps:
            out = out_root / f"map_combined_streets_{scenario}_{horizon}_rp{rp}.png"
            plot_combined_with_streets(
                root, scenario, horizon, rp, vmax, out, basemap_alpha, flood_alpha,
                city_name=city_name, pluvial_floor=pluvial_floor,
            )
    else:
        click.echo("Fetching street tiles and rendering comparison panel only (use --per-rp for individual RPs) …")

    # Comparison panel (always written)
    out_panel = out_root / f"map_combined_streets_{scenario}_{horizon}_rp_comparison.png"
    plot_rp_comparison_with_streets(
        root, scenario, horizon, vmax, out_panel, basemap_alpha, flood_alpha,
        city_name=city_name, pluvial_floor=pluvial_floor,
    )


if __name__ == "__main__":
    cli()
