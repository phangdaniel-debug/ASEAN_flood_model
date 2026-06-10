"""
Visualise flood depth rasters for a specific return period.

Produces a 4-panel PNG: coastal | fluvial | pluvial | combined (pixel-wise max).

Example
-------
    python scripts/make_rp_flood_map.py \\
      --out-dir outputs/singapore_ssp585_2100 \\
      --scenario SSP5-8.5 \\
      --horizon 2100 \\
      --rp 1000
"""
from __future__ import annotations

from pathlib import Path

import click
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import rasterio

HAZARDS = ("coastal", "fluvial", "pluvial")


def _load_depth(root: Path, hazard: str, scenario: str, horizon: int, rp: int) -> np.ndarray:
    path = root / hazard / f"rp_{rp}" / f"{hazard}_depth_{scenario}_{horizon}_rp{rp}.tif"
    if not path.exists():
        raise click.ClickException(f"Missing raster: {path}")
    with rasterio.open(path) as src:
        arr = src.read(1).astype(np.float32)
        nd = src.nodata
        if nd is not None:
            arr = np.where(arr == nd, np.nan, arr)
    return arr


@click.command()
@click.option(
    "--out-dir",
    "out_dir",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--scenario", required=True, help="e.g. SSP5-8.5")
@click.option("--horizon", type=int, required=True, help="e.g. 2100")
@click.option("--rp", "return_period", type=int, required=True, help="Return period in years, e.g. 1000")
@click.option(
    "--vmax",
    type=float,
    default=None,
    help="Colorbar max depth (m). Defaults to 98th pct of the combined layer.",
)
def cli(
    out_dir: Path,
    scenario: str,
    horizon: int,
    return_period: int,
    vmax: float | None,
) -> None:
    arrays: dict[str, np.ndarray] = {}
    for hazard in HAZARDS:
        click.echo(f"Loading {hazard} RP{return_period} ...")
        arrays[hazard] = _load_depth(out_dir, hazard, scenario, horizon, return_period)

    # Combined: pixel-wise max across all three hazards
    stacked = np.stack([arrays[h] for h in HAZARDS], axis=0)
    arrays["combined"] = np.nanmax(stacked, axis=0)
    labels = {
        "coastal": "Coastal",
        "fluvial": "Fluvial",
        "pluvial": "Pluvial",
        "combined": "Combined (max)",
    }

    if vmax is None:
        combined = arrays["combined"]
        finite = combined[np.isfinite(combined) & (combined > 0)]
        vmax = float(np.percentile(finite, 98)) if finite.size else 3.0
        vmax = max(vmax, 0.1)
        click.echo(f"Auto vmax: {vmax:.2f} m")

    cmap = plt.get_cmap("YlOrRd")
    norm = mcolors.Normalize(vmin=0, vmax=vmax)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=200, squeeze=False)
    panel_order = ["coastal", "fluvial", "pluvial", "combined"]

    for idx, key in enumerate(panel_order):
        row, col = divmod(idx, 2)
        ax = axes[row][col]
        arr = arrays[key].copy()
        arr[arr <= 0] = np.nan  # dry cells → transparent background

        im = ax.imshow(arr, cmap=cmap, norm=norm, interpolation="nearest")
        ax.set_title(labels[key], fontsize=12, fontweight="bold")
        ax.set_xlabel("Column index (30 m grid)", fontsize=8)
        ax.set_ylabel("Row index (30 m grid)", fontsize=8)
        ax.tick_params(labelsize=7)

        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("Flood depth (m)", fontsize=8)
        cbar.ax.tick_params(labelsize=7)

        # Summary stats in subtitle
        wet = arr[np.isfinite(arr) & (arr > 0)]
        if wet.size:
            ax.set_xlabel(
                f"Wet pixels: {wet.size:,}  |  mean {wet.mean():.2f} m  |  max {wet.max():.2f} m",
                fontsize=8,
            )

    fig.suptitle(
        f"Singapore Flood Depth  --  1-in-{return_period} Year Return Period\n"
        f"Scenario {scenario}, horizon {horizon}",
        fontsize=13,
        fontweight="bold",
    )
    fig.tight_layout()

    out_path = out_dir / f"flood_depth_rp{return_period}_{scenario}_{horizon}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    click.echo(f"Wrote: {out_path}")


if __name__ == "__main__":
    cli()
