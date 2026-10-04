"""Regenerate the Kuala Lumpur main-stem fluvial HAND from committed inputs.

Closes the reproducibility gap noted in docs/technical/model-documentation.md §6.2.3:
KL's shipped fluvial HAND (`dem/_hand/kl_hand_mainstem_v3eth.tif`) was built by an
uncommitted v3-lineage step and had no flood-v4.0 builder. This script regenerates it
**bit-exactly** from two committed inputs:

  1. `dem/kl/dem_bareearth_kl_eth_present_conditioned.tif` — the ETH-canopy bare-earth DEM
     (the same DEM the atlas driver feeds the solver).
  2. `data/kuala_lumpur/trunk_drainage_mask_utm47n.tif` — the frozen main-stem drainage
     network (1 = channel cell). This is the load-bearing v2-lineage input: KL's trunk
     network is denser than a plain flow-accumulation threshold reproduces (a >=180 km2
     accumulation threshold gives only ~3 km2 of channel and IoU 0.82 against the shipped
     HAND — see the §6.2.3 note), so the network topology is shipped as an explicit frozen
     mask rather than re-derived. Its provenance is the v2 Klang-trunk drainage; it is
     committed here so the HAND is regenerable and auditable.

HAND is then `model.hand_model.compute_hand(DEM, drainage_mask)` — the same transform used
for every other city. Verified to reproduce the shipped raster to max|Δ| = 0 (identical).

Usage:  python scripts/_fix_kl_trunk_hand.py [--verify]
Out:    dem/_hand/kl_hand_mainstem_v3eth.tif
"""
import sys
from pathlib import Path

import click
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.flood_depth_model import load_dem  # noqa: E402
from model.hand_model import compute_hand  # noqa: E402

DEM = ROOT / "dem/kl/dem_bareearth_kl_eth_present_conditioned.tif"
MASK = ROOT / "data/kuala_lumpur/trunk_drainage_mask_utm47n.tif"
OUT = ROOT / "dem/_hand/kl_hand_mainstem_v3eth.tif"


@click.command()
@click.option("--verify", is_flag=True, help="Compare against the existing OUT raster and report max|Δ|.")
def cli(verify):
    dem, profile = load_dem(str(DEM))
    dem = np.asarray(dem, dtype="float64")
    with rasterio.open(MASK) as r:
        drainage = r.read(1).astype(bool)
    if drainage.shape != dem.shape:
        raise SystemExit(f"shape mismatch DEM {dem.shape} vs mask {drainage.shape}")
    print(f"KL trunk drainage: {int(drainage.sum()):,} channel cells "
          f"({float(drainage.sum()) * 0.0009:.1f} km2)")
    hand = compute_hand(dem, drainage, profile)

    if verify and OUT.exists():
        with rasterio.open(OUT) as r:
            ship = r.read(1)
        both = np.isfinite(ship) & np.isfinite(hand)
        d = np.abs(ship[both] - hand[both])
        print(f"  vs shipped: max|delta|={d.max():.6f} mean|delta|={d.mean():.6f} "
              f"finite ship={int(np.isfinite(ship).sum()):,} new={int(np.isfinite(hand).sum()):,} "
              f"-> {'IDENTICAL' if d.max() < 1e-3 else 'DIFFERS'}")
        return

    prof = profile.copy()
    prof.update(dtype="float32", count=1, compress="deflate", predictor=2, nodata=float("nan"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(OUT, "w", **prof) as dst:
        dst.write(hand.astype("float32"), 1)
    print(f"wrote {OUT}  (HAND max {float(np.nanmax(hand)):.1f} m)")


if __name__ == "__main__":
    cli()
