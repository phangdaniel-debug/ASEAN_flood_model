# scripts/fetch_aqueduct_singapore.py
"""Fetch WRI Aqueduct riverine+coastal flood hazard rasters and clip to the
Singapore pipeline grid, producing a single 'any Aqueduct flood' depth raster
for comparator scoring (spec section 7.1).

Aqueduct Flood Hazard Maps: WRI/PBL, CC BY 4.0 (commercial-safe).
Resolution ~1 km (riverine) / coastal. The ~1 km vs 150 m hit-radius mismatch
is a documented known asymmetry (spec section 7), not corrected here.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import click
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# WRI Aqueduct v2 flood hazard download base (verify reachable at run time).
AQUEDUCT_BASE = "http://wri-projects.s3.amazonaws.com/AqueductFloodTool/download/v2"


def _aqueduct_urls(rp: int) -> list[str]:
    """Candidate riverine + coastal filenames for a return period (historical baseline)."""
    return [
        f"{AQUEDUCT_BASE}/inunriver_historical_000000000WATCH_1980_rp{rp:05d}.tif",
        f"{AQUEDUCT_BASE}/inuncoast_historical_nosub_hist_rp{rp:04d}_0.tif",
    ]


def _download(url: str, dest: Path) -> bool:
    if dest.exists():
        click.echo(f"  cached {dest.name}")
        return True
    try:
        with urllib.request.urlopen(url, timeout=180) as resp:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resp.read())
        click.echo(f"  downloaded {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")
        return True
    except Exception as exc:  # noqa: BLE001 - report and continue
        click.echo(f"  [warn] could not fetch {url}: {exc}", err=True)
        return False


@click.command()
@click.option("--rp", type=int, default=50, show_default=True)
@click.option("--ref", "ref_path", type=click.Path(path_type=Path),
              default=PROJECT_ROOT / "data/singapore/copernicus_dem_utm48n.tif",
              show_default=True, help="Grid to clip/reproject onto.")
@click.option("--out", "out_path", type=click.Path(path_type=Path), required=True)
def cli(rp: int, ref_path: Path, out_path: Path):
    cache = PROJECT_ROOT / "cache" / "aqueduct"
    with rasterio.open(ref_path) as ref:
        dst = np.zeros((ref.height, ref.width), dtype=np.float32)
        ref_transform, ref_crs = ref.transform, ref.crs
        profile = ref.profile

    fetched_any = False
    for url in _aqueduct_urls(rp):
        dest = cache / Path(url).name
        if not _download(url, dest):
            continue
        fetched_any = True
        with rasterio.open(dest) as src:
            src_arr = src.read(1).astype(np.float32)
            if src.nodata is not None:
                src_arr = np.where(src_arr == src.nodata, 0.0, src_arr)
            layer = np.zeros_like(dst)
            reproject(source=src_arr, destination=layer,
                      src_transform=src.transform, src_crs=src.crs,
                      dst_transform=ref_transform, dst_crs=ref_crs,
                      resampling=Resampling.bilinear)
        dst = np.maximum(dst, layer)  # union of riverine+coastal depths

    if not fetched_any:
        click.echo("[error] No Aqueduct layers fetched — dataset URLs may have "
                   "moved. Update AQUEDUCT_BASE / filename pattern.", err=True)
        sys.exit(2)

    profile.update(dtype="float32", count=1, nodata=float("nan"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as ds:
        ds.write(dst.astype("float32"), 1)
    click.echo(f"Wrote Aqueduct comparator RP{rp} -> {out_path}")


if __name__ == "__main__":
    cli()
