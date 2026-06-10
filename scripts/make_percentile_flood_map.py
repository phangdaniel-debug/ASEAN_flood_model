"""
Produce a percentile flood-depth map by stacking all return-period depth
rasters and computing per-pixel depth percentiles.

For each pixel the script asks: "across the full return-period spectrum,
what flood depth corresponds to the Nth percentile scenario?"

  P25  → depth exceeded in only 25 % of RP scenarios  (low-end / frequent)
  P50  → median scenario depth
  P75  → above-median scenario depth
  P95  → near worst-case depth

When --hazard combined (default) the pixel-wise maximum across coastal,
fluvial, and pluvial is taken at each return period before the percentile
calculation.  This gives a multi-hazard envelope view.

Outputs
-------
* Multi-panel PNG  : <out-dir>/percentile_depth_<hazard>_<scenario>_<horizon>.png
* Per-percentile GeoTIFFs : <out-dir>/percentile/<hazard>_p<N>_<scenario>_<horizon>.tif

Example
-------
    python scripts/make_percentile_flood_map.py \\
      --out-dir outputs/singapore_ssp585_2100 \\
      --scenario SSP5-8.5 \\
      --horizon 2100

    # single hazard, custom percentiles
    python scripts/make_percentile_flood_map.py \\
      --out-dir outputs/singapore_ssp585_2100 \\
      --scenario SSP5-8.5 \\
      --horizon 2100 \\
      --hazard coastal \\
      --percentiles 10,50,90,99
"""
from __future__ import annotations

from pathlib import Path

import click
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import rasterio

HAZARDS = ("coastal", "fluvial", "pluvial")
RETURN_PERIODS = (2, 5, 10, 25, 50, 100, 200, 500, 1000)


# ---------------------------------------------------------------------------
# Raster loading helpers
# ---------------------------------------------------------------------------

def _depth_path(root: Path, hazard: str, scenario: str, horizon: int, rp: int) -> Path:
    return root / hazard / f"rp_{rp}" / f"{hazard}_depth_{scenario}_{horizon}_rp{rp}.tif"


def _load_stack(
    root: Path,
    hazard: str,
    scenario: str,
    horizon: int,
) -> tuple[np.ndarray, dict]:
    """
    Load all return-period depth rasters for one hazard type.

    Returns
    -------
    stack : float32 array (n_rp, rows, cols)
        Depth in metres; NaN = nodata.
    profile : dict
        Rasterio profile from the first raster (all rasters share CRS/transform).
    """
    arrays: list[np.ndarray] = []
    profile: dict | None = None

    for rp in RETURN_PERIODS:
        path = _depth_path(root, hazard, scenario, horizon, rp)
        if not path.exists():
            raise click.ClickException(f"Missing raster: {path}")
        with rasterio.open(path) as src:
            arr = src.read(1).astype(np.float32)
            nd = src.nodata
            if nd is not None:
                arr = np.where(arr == nd, np.nan, arr)
            if profile is None:
                profile = src.profile.copy()
        arrays.append(arr)

    return np.stack(arrays, axis=0), profile  # type: ignore[return-value]


def _combined_stack(
    root: Path,
    scenario: str,
    horizon: int,
) -> tuple[np.ndarray, dict]:
    """
    For each return period, take the pixel-wise maximum across all three
    hazard types.  This is the multi-hazard envelope.
    """
    stacks: list[np.ndarray] = []
    profile: dict | None = None

    for hazard in HAZARDS:
        s, p = _load_stack(root, hazard, scenario, horizon)
        stacks.append(s)
        if profile is None:
            profile = p

    # shape: (n_hazards, n_rp, rows, cols) → max over hazards → (n_rp, rows, cols)
    combined = np.nanmax(np.stack(stacks, axis=0), axis=0)
    return combined, profile  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Percentile computation
# ---------------------------------------------------------------------------

def compute_depth_percentiles(
    stack: np.ndarray,
    percentiles: list[int],
) -> dict[int, np.ndarray]:
    """
    Compute per-pixel depth percentiles across the return-period axis.

    Parameters
    ----------
    stack : float32 (n_rp, rows, cols)
    percentiles : list of int, e.g. [25, 50, 75, 95]

    Returns
    -------
    dict mapping percentile → float32 array (rows, cols)
    """
    # Pixels that are NaN in every return period are genuinely outside the
    # domain (DEM nodata).  All other NaN values mean "dry for this RP",
    # which is physically equivalent to depth = 0.  We replace NaN with 0
    # before calling np.percentile (much faster than nanpercentile on large
    # arrays) and restore the out-of-domain mask afterwards.
    nodata_mask = np.all(~np.isfinite(stack), axis=0)  # (rows, cols)
    stack_filled = np.where(np.isfinite(stack), stack, 0.0)

    result: dict[int, np.ndarray] = {}
    for p in percentiles:
        pct_arr = np.percentile(stack_filled, p, axis=0).astype(np.float32)
        pct_arr[nodata_mask] = np.nan
        result[p] = pct_arr
    return result


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _panel_label(p: int, n_rp: int) -> str:
    """Human-readable subtitle: approximate rank in the RP spectrum."""
    rank = max(1, round(p / 100 * n_rp))
    approx_rp = RETURN_PERIODS[min(rank - 1, n_rp - 1)]
    return f"P{p}  (~RP{approx_rp} depth)"


def _plot_percentile_panels(
    pct_maps: dict[int, np.ndarray],
    hazard_label: str,
    scenario: str,
    horizon: int,
    vmax: float,
    out_path: Path,
) -> None:
    percentiles = sorted(pct_maps)
    n = len(percentiles)
    ncols = min(n, 2)
    nrows = (n + ncols - 1) // ncols

    fig, axes = plt.subplots(
        nrows, ncols,
        figsize=(7 * ncols, 5.5 * nrows),
        dpi=200,
        squeeze=False,
    )

    cmap = plt.get_cmap("YlOrRd")
    norm = mcolors.Normalize(vmin=0, vmax=vmax)

    for idx, p in enumerate(percentiles):
        row, col = divmod(idx, ncols)
        ax = axes[row][col]
        arr = pct_maps[p].copy()
        arr[~np.isfinite(arr)] = np.nan
        arr[arr <= 0] = np.nan   # mask dry cells so they render as background

        im = ax.imshow(arr, cmap=cmap, norm=norm, interpolation="nearest")
        ax.set_title(
            _panel_label(p, len(RETURN_PERIODS)),
            fontsize=11,
            fontweight="bold",
        )
        ax.set_xlabel("Column index (30 m grid)", fontsize=8)
        ax.set_ylabel("Row index (30 m grid)", fontsize=8)
        ax.tick_params(labelsize=7)

        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("Flood depth (m)", fontsize=8)
        cbar.ax.tick_params(labelsize=7)

    # Hide any unused axes
    for idx in range(n, nrows * ncols):
        row, col = divmod(idx, ncols)
        axes[row][col].set_visible(False)

    fig.suptitle(
        f"Singapore {hazard_label} — Percentile Flood Depth\n"
        f"Scenario {scenario}, horizon {horizon}",
        fontsize=13,
        fontweight="bold",
        y=1.01,
    )
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    click.echo(f"Wrote PNG : {out_path}")


# ---------------------------------------------------------------------------
# GeoTIFF output
# ---------------------------------------------------------------------------

def _write_percentile_tifs(
    pct_maps: dict[int, np.ndarray],
    profile: dict,
    hazard: str,
    scenario: str,
    horizon: int,
    out_dir: Path,
) -> None:
    tif_dir = out_dir / "percentile"
    tif_dir.mkdir(parents=True, exist_ok=True)
    prof = profile.copy()
    prof.update(dtype="float32", count=1, compress="deflate", predictor=2, nodata=np.nan)
    for p, arr in pct_maps.items():
        path = tif_dir / f"{hazard}_p{p}_{scenario}_{horizon}.tif"
        with rasterio.open(path, "w", **prof) as dst:
            dst.write(arr, 1)
        click.echo(f"Wrote TIF : {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--out-dir",
    "out_dir",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Root output directory produced by run_singapore_multihazard.py.",
)
@click.option("--scenario", required=True, help="e.g. SSP5-8.5")
@click.option("--horizon", type=int, required=True, help="e.g. 2100")
@click.option(
    "--hazard",
    type=click.Choice(["coastal", "fluvial", "pluvial", "combined"]),
    default="combined",
    show_default=True,
    help=(
        "Hazard type to summarise.  'combined' takes the pixel-wise maximum "
        "across all three hazards at each return period before computing percentiles."
    ),
)
@click.option(
    "--percentiles",
    "percentiles_str",
    default="25,50,75,95",
    show_default=True,
    help="Comma-separated list of integer percentiles to compute.",
)
@click.option(
    "--vmax",
    type=float,
    default=None,
    help=(
        "Colorbar maximum depth in metres.  "
        "Defaults to the 98th percentile of the highest-percentile layer."
    ),
)
def cli(
    out_dir: Path,
    scenario: str,
    horizon: int,
    hazard: str,
    percentiles_str: str,
    vmax: float | None,
) -> None:
    percentiles = [int(p.strip()) for p in percentiles_str.split(",")]
    bad = [p for p in percentiles if not (0 <= p <= 100)]
    if bad:
        raise click.BadParameter(f"Percentiles must be 0–100, got: {bad}")

    click.echo(f"Loading depth rasters  (hazard={hazard}, {scenario} {horizon}) ...")
    if hazard == "combined":
        stack, profile = _combined_stack(out_dir, scenario, horizon)
        hazard_label = "Combined (coastal / fluvial / pluvial max)"
        hazard_slug = "combined"
    else:
        stack, profile = _load_stack(out_dir, hazard, scenario, horizon)
        hazard_label = hazard.title()
        hazard_slug = hazard

    click.echo(f"Stack shape: {stack.shape}  ({len(RETURN_PERIODS)} return periods)")

    pct_maps = compute_depth_percentiles(stack, percentiles)

    if vmax is None:
        top_layer = pct_maps[max(percentiles)]
        finite_vals = top_layer[np.isfinite(top_layer) & (top_layer > 0)]
        vmax = float(np.percentile(finite_vals, 98)) if finite_vals.size else 3.0
        vmax = max(vmax, 0.1)
        click.echo(f"Auto vmax: {vmax:.2f} m (98th pct of P{max(percentiles)} wet pixels)")

    png_path = out_dir / f"percentile_depth_{hazard_slug}_{scenario}_{horizon}.png"
    _plot_percentile_panels(pct_maps, hazard_label, scenario, horizon, vmax, png_path)

    _write_percentile_tifs(pct_maps, profile, hazard_slug, scenario, horizon, out_dir)


if __name__ == "__main__":
    cli()
