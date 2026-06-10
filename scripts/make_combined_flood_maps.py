"""
Generate two multi-hazard flood visualisations:

1. Combined hazard map (one per return period)
   Each pixel is coloured by the hazard that contributes the greatest depth:
       Coastal  → Blues
       Fluvial  → Oranges
       Pluvial  → Greens
   Colour intensity is proportional to depth (0 – vmax).
   Where two hazards overlap the one with the larger depth wins.

2. Return-period comparison panel (3 × 3 grid)
   Shows the combined maximum depth across all three hazards at each of the
   nine standard return periods (RP2 … RP1000) in a single figure.

Usage
-----
    python scripts/make_combined_flood_maps.py \\
        --out-dir outputs/singapore_ssp585_2100 \\
        --scenario SSP5-8.5 --horizon 2100
"""
from __future__ import annotations

from pathlib import Path

import click
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import rasterio

RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]

# Colour maps per hazard — same hue family, high-contrast
HAZARD_CMAPS = {
    "coastal": "Blues",
    "fluvial": "Oranges",
    "pluvial": "Greens",
}
HAZARD_COLOURS = {          # representative solid colour for legend patches
    "coastal": "#2166AC",
    "fluvial": "#D94801",
    "pluvial": "#1A9850",
}


def _load_depth(
    root: Path,
    hazard: str,
    scenario: str,
    horizon: int,
    rp: int,
    pluvial_floor: float = 0.0,
) -> np.ndarray:
    p = root / hazard / f"rp_{rp}" / f"{hazard}_depth_{scenario}_{horizon}_rp{rp}.tif"
    if not p.exists():
        raise FileNotFoundError(f"Missing raster: {p}")
    with rasterio.open(p) as src:
        arr = src.read(1).astype(np.float32)
    arr[~np.isfinite(arr)] = 0.0
    arr[arr < 0] = 0.0
    # Suppress sub-threshold pluvial "puddles" — at RP2 the per-pixel cap can be
    # the 0.005 m drain-capacity floor, which paints every spurious GLO-30
    # micro-depression and exaggerates apparent extent. Treats anything below
    # `pluvial_floor` as dry for both rendering and area accounting.
    if hazard == "pluvial" and pluvial_floor > 0:
        arr[arr < pluvial_floor] = 0.0
    return arr


def _make_combined_rgba(
    depths: dict[str, np.ndarray],
    vmax: float,
) -> np.ndarray:
    """
    Build an RGBA image where each pixel is coloured by the dominant hazard.
    Alpha is proportional to normalised depth (transparent where dry).
    """
    rows, cols = next(iter(depths.values())).shape
    rgba = np.zeros((rows, cols, 4), dtype=np.float32)

    # Determine dominant hazard per pixel (largest depth wins)
    stacked = np.stack([depths[h] for h in HAZARD_CMAPS], axis=0)   # (3, r, c)
    dominant_idx = np.argmax(stacked, axis=0)                         # (r, c)
    max_depth = stacked.max(axis=0)                                    # (r, c)

    hazard_list = list(HAZARD_CMAPS.keys())
    for i, hazard in enumerate(hazard_list):
        cmap = plt.get_cmap(HAZARD_CMAPS[hazard])
        mask = (dominant_idx == i) & (max_depth > 0)
        if not mask.any():
            continue
        norm_d = np.clip(max_depth[mask] / vmax, 0.0, 1.0)
        # Use the upper half of each cmap (0.4 → 1.0) to keep colours vivid
        mapped = cmap(0.4 + 0.6 * norm_d)          # shape (N, 4)
        rgba[mask] = mapped

    # Make dry cells fully transparent
    dry = max_depth <= 0
    rgba[dry, 3] = 0.0

    return rgba


def plot_combined(
    root: Path,
    scenario: str,
    horizon: int,
    rp: int,
    vmax: float,
    out_path: Path,
    city_name: str = "",
    pluvial_floor: float = 0.0,
) -> None:
    depths = {
        h: _load_depth(root, h, scenario, horizon, rp, pluvial_floor=pluvial_floor)
        for h in HAZARD_CMAPS
    }

    rgba = _make_combined_rgba(depths, vmax)
    max_depth = np.stack(list(depths.values())).max(axis=0)
    rows, cols = max_depth.shape

    fig, ax = plt.subplots(figsize=(9, 7), dpi=200)

    # Light grey background for Singapore land area
    land_bg = np.zeros((rows, cols, 4), dtype=np.float32)
    any_finite = np.any(
        [
            np.isfinite(_load_depth(root, h, scenario, horizon, rp, pluvial_floor=pluvial_floor))
            for h in HAZARD_CMAPS
        ],
        axis=0,
    )
    # Load a single depth file to identify nodata
    with rasterio.open(
        root / "coastal" / f"rp_{rp}" / f"coastal_depth_{scenario}_{horizon}_rp{rp}.tif"
    ) as src:
        sample = src.read(1).astype(np.float32)
    land_mask = np.isfinite(sample)
    land_bg[land_mask] = [0.88, 0.88, 0.88, 1.0]
    ax.imshow(land_bg, interpolation="nearest")

    # Overlay combined flood colours
    ax.imshow(rgba, interpolation="nearest")

    # Depth colourbar (shared normalisation)
    sm = plt.cm.ScalarMappable(cmap="Greys_r", norm=mcolors.Normalize(vmin=0, vmax=vmax))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label("Flood depth (m)", fontsize=9)

    # Hazard legend
    patches = [
        mpatches.Patch(color=HAZARD_COLOURS[h], label=h.title())
        for h in HAZARD_CMAPS
    ]
    ax.legend(handles=patches, loc="lower right", fontsize=8, framealpha=0.85)

    wet_km2 = float((max_depth > 0).sum()) * 30 * 30 / 1e6
    title_city = f"{city_name} " if city_name else ""
    ax.set_title(
        f"{title_city}Multi-Hazard Flood Depth  ({scenario}, {horizon}, RP{rp})\n"
        f"Total flooded area: {wet_km2:.1f} km²",
        fontsize=11,
    )
    ax.set_xlabel("Column index (30m grid)", fontsize=9)
    ax.set_ylabel("Row index (30m grid)", fontsize=9)
    ax.tick_params(labelsize=8)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def plot_rp_comparison(
    root: Path,
    scenario: str,
    horizon: int,
    vmax: float,
    out_path: Path,
    city_name: str = "",
    pluvial_floor: float = 0.0,
) -> None:
    """3 × 3 grid comparing combined max depth at each return period."""
    rps = RETURN_PERIODS
    ncols, nrows = 3, 3
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 11), dpi=150)
    title_city = f"{city_name} " if city_name else ""
    fig.suptitle(
        f"{title_city}Multi-Hazard Flood Depth — Return Period Comparison\n"
        f"({scenario}, {horizon})  |  colour = dominant hazard  |  vmax = {vmax:.1f} m",
        fontsize=12,
        y=1.01,
    )

    # Load a coastal raster once to get land mask
    with rasterio.open(
        root / "coastal" / f"rp_{rps[0]}" / f"coastal_depth_{scenario}_{horizon}_rp{rps[0]}.tif"
    ) as src:
        sample_land = np.isfinite(src.read(1).astype(np.float32))

    for idx, rp in enumerate(rps):
        ax = axes[idx // ncols, idx % ncols]
        depths = {
            h: _load_depth(root, h, scenario, horizon, rp, pluvial_floor=pluvial_floor)
            for h in HAZARD_CMAPS
        }
        rgba = _make_combined_rgba(depths, vmax)
        max_depth = np.stack(list(depths.values())).max(axis=0)
        wet_km2 = float((max_depth > 0).sum()) * 30 * 30 / 1e6

        land_bg = np.zeros((*sample_land.shape, 4), dtype=np.float32)
        land_bg[sample_land] = [0.88, 0.88, 0.88, 1.0]
        ax.imshow(land_bg, interpolation="nearest")
        ax.imshow(rgba, interpolation="nearest")

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


@click.command()
@click.option("--out-dir", "root", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--scenario", required=True)
@click.option("--horizon", type=int, required=True)
@click.option(
    "--vmax",
    type=float,
    default=1.5,
    show_default=True,
    help="Depth scale maximum (m) shared across all maps.",
)
@click.option(
    "--return-periods",
    "rp_list",
    default=",".join(str(r) for r in RETURN_PERIODS),
    show_default=True,
    help="Comma-separated return periods for individual combined maps.",
)
@click.option(
    "--city-name",
    "city_name",
    default="",
    show_default=True,
    help="City display name shown in map titles (e.g. 'Bangkok'). Defaults to empty (omitted).",
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
        "Write the nine individual per-RP PNGs in addition to the 3x3 "
        "comparison panel. Default OFF (May 2026): the per-RP files "
        "are redundant with the comparison panel and create folder "
        "clutter; use scripts/build_viz_suite.py for cross-cutting "
        "visualisations instead. Pass --per-rp to restore the old "
        "behaviour."
    ),
)
def cli(
    root: Path,
    scenario: str,
    horizon: int,
    vmax: float,
    rp_list: str,
    city_name: str,
    pluvial_floor: float,
    per_rp: bool,
) -> None:
    rps = [int(x) for x in rp_list.split(",")]

    # 1. Individual combined map per RP (opt-in)
    if per_rp:
        for rp in rps:
            out = root / f"map_combined_{scenario}_{horizon}_rp{rp}.png"
            plot_combined(
                root, scenario, horizon, rp, vmax, out,
                city_name=city_name, pluvial_floor=pluvial_floor,
            )
            click.echo(f"Wrote combined map: {out}")

    # 2. Return-period comparison panel (always written)
    out_panel = root / f"map_combined_{scenario}_{horizon}_rp_comparison.png"
    plot_rp_comparison(
        root, scenario, horizon, vmax, out_panel,
        city_name=city_name, pluvial_floor=pluvial_floor,
    )
    click.echo(f"Wrote comparison panel: {out_panel}")


if __name__ == "__main__":
    cli()
