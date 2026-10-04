"""Controlled-A/B HAND for a v3 bare-earth DEM: reuse the v2 drainage network
(channel cells where v2 HAND ~= 0) and recompute HAND on the v3 terrain. This
isolates the single variable under test (terrain) — identical drainage topology.

Usage:
  python scripts/_build_v3_hand.py --v2-hand <v2 hand.tif> --v3-dem <v3 dem.tif> --out <out.tif>
"""
import sys
from pathlib import Path

import click
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.flood_depth_model import load_dem
from model.hand_model import compute_hand


@click.command()
@click.option("--v2-hand", required=True, type=click.Path(exists=True))
@click.option("--v3-dem", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
def cli(v2_hand, v3_dem, out):
    with rasterio.open(v2_hand) as r:
        h2 = r.read(1).astype("float64")
    drainage_mask = np.isfinite(h2) & (h2 < 0.01)
    print(f"v2 drainage network: {int(drainage_mask.sum()):,} channel cells")

    dem, profile = load_dem(v3_dem)
    if dem.shape != drainage_mask.shape:
        raise SystemExit(f"shape mismatch dem {dem.shape} vs mask {drainage_mask.shape}")

    print("Computing HAND on v3 terrain (same drainage cells) ...")
    hand = compute_hand(dem, drainage_mask, profile)

    prof = profile.copy()
    prof.update(dtype="float32", count=1, compress="deflate", predictor=2, nodata=np.nan)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out, "w", **prof) as dst:
        dst.write(hand.astype("float32"), 1)

    fin = np.isfinite(hand)
    print(f"wrote {out}")
    print(f"  v3 HAND mean={float(np.nanmean(hand)):.2f} median={float(np.nanmedian(hand)):.2f} max={float(np.nanmax(hand)):.2f}")
    print(f"  v2 HAND mean={float(np.nanmean(h2)):.2f} median={float(np.nanmedian(h2)):.2f}")


if __name__ == "__main__":
    cli()
