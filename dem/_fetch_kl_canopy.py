"""KL canopy fetch (substitute for the retired ETH 10m host).

The ETH GlobalCanopyHeight 10m 2020 v1 direct host (share.phys.ethz.ch .../3deg_cogs/)
is RETIRED — all tile requests now redirect to a gated ETH research-collection page
(HTTP 500). This was already flagged in dem/bangkok/auxdata/README.md, where Bangkok's
tile was a manual user download.

Substitute: Meta / WRI High-Resolution Canopy Height (alsgedi_global_v6_float, 1 m, 2020,
CC-BY 4.0) on the public AWS bucket dataforgood-fb-data (no-sign). It is a canopy-height
raster on the same datum-free (height-above-ground) footing, so the per-city error model
residual ~= bias0 + f*canopy still holds — f is refit against THIS canopy raster in
calibrate_dem.py, so the substitution is internally consistent.

This script:
  1. downloads the tile index geojson (chunked, resumable),
  2. selects quadkey tiles intersecting the KL bbox,
  3. warps each onto the KL 30m GLO-30 grid (average resampling) and overlays into a
     single canopy GeoTIFF the dem/ scripts can read unchanged.
"""
import json
from pathlib import Path
import numpy as np
import requests
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling, transform_bounds

BASE = "https://dataforgood-fb-data.s3.amazonaws.com/forests/v1/alsgedi_global_v6_float/"
AUX = Path(r"D:\GPTs\Projects\flood-v3.0\dem\kl\auxdata")
DEM = r"D:\GPTs\Projects\flood-v3.0\dem\kl\glo30_dsm_utm47n.tif"
GEOJSON = AUX / "_meta_tiles.geojson"
OUT = AUX / "canopy_meta_chm_kl.tif"


def download(url, dst, chunk=1 << 20):
    dst = Path(dst)
    with requests.get(url, timeout=120, stream=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        got = 0
        with open(dst, "wb") as f:
            for c in r.iter_content(chunk_size=chunk):
                f.write(c)
                got += len(c)
        print(f"downloaded {dst.name}: {got/1e6:.1f} MB (declared {total/1e6:.1f})", flush=True)


def feat_bbox(geom):
    """min/max lon/lat of a polygon/multipolygon ring set."""
    xs, ys = [], []
    def walk(coords):
        for c in coords:
            if isinstance(c[0], (list, tuple)):
                walk(c)
            else:
                xs.append(c[0]); ys.append(c[1])
    walk(geom["coordinates"])
    return min(xs), min(ys), max(xs), max(ys)


def main():
    AUX.mkdir(parents=True, exist_ok=True)
    if not GEOJSON.exists() or GEOJSON.stat().st_size < 1000:
        download(BASE + "tiles.geojson", GEOJSON)
    gj = json.loads(GEOJSON.read_text())
    feats = gj["features"]
    print(f"index features: {len(feats)}", flush=True)

    with rasterio.open(DEM) as dem:
        b = dem.bounds
        lo, la, hi, ha = transform_bounds(dem.crs, "EPSG:4326", b.left, b.bottom, b.right, b.top)
        H, W = dem.height, dem.width
        prof = dem.profile.copy()
        print(f"KL bbox lonlat=({lo:.4f},{la:.4f},{hi:.4f},{ha:.4f})", flush=True)

        # tiles whose bbox intersects KL bbox
        sel = []
        for ft in feats:
            tlo, tla, thi, tha = feat_bbox(ft["geometry"])
            if tlo <= hi and thi >= lo and tla <= ha and tha >= la:
                p = ft["properties"]
                # tile name property varies; try common keys
                name = p.get("tile") or p.get("name") or p.get("location") or p.get("quadkey")
                sel.append(name)
        sel = [s for s in sel if s]
        print(f"intersecting tiles ({len(sel)}): {sel}", flush=True)
        if not sel:
            # dump one feature's properties to learn the schema
            print("SAMPLE PROPS:", json.dumps(feats[0]["properties"]), flush=True)
            raise SystemExit("no intersecting tiles / unknown name property")

        out = np.full((H, W), np.nan, dtype="float32")
        for name in sel:
            url = f"{BASE}chm/{name}.tif"
            local = AUX / f"_meta_chm_{name}.tif"
            # Download the full COG locally first — streaming a 754 MB COG via WarpedVRT
            # over HTTP triggers truncated-strip reads (TIFFReadEncodedStrip failed).
            # A local file warps reliably. Resume if partial.
            if not local.exists() or local.stat().st_size == 0:
                for attempt in range(6):
                    try:
                        download(url, local)
                        break
                    except Exception as e:
                        print(f"  dl {name} attempt {attempt+1}: {type(e).__name__} {str(e)[:80]}", flush=True)
                        if local.exists():
                            local.unlink()
            print(f"warping {name} (local {local.stat().st_size/1e6:.0f} MB) ...", flush=True)
            with rasterio.open(local) as src:
                with WarpedVRT(src, crs=dem.crs, transform=dem.transform,
                               width=W, height=H, resampling=Resampling.average) as vrt:
                    a = vrt.read(1).astype("float32")
                    nod = vrt.nodata if vrt.nodata is not None else src.nodata
            if nod is not None:
                a = np.where(a == nod, np.nan, a)
            fill = np.isnan(out) & np.isfinite(a)
            out[fill] = a[fill]
            print(f"  filled {int(fill.sum()):,} cells", flush=True)

    n_cov = int(np.isfinite(out).sum())
    out_w = np.where(np.isfinite(out), out, 255).astype("float32")  # 255 = nodata (matches ETH convention)
    prof.update(dtype="float32", count=1, nodata=255, compress="deflate")
    with rasterio.open(OUT, "w", **prof) as d:
        d.write(out_w, 1)
    v = out[np.isfinite(out)]
    print(f"coverage {n_cov:,}/{H*W:,} ({100*n_cov/(H*W):.1f}%)", flush=True)
    if v.size:
        print(f"canopy m: min/med/mean/max = {v.min():.2f}/{np.median(v):.2f}/{v.mean():.2f}/{v.max():.2f}", flush=True)
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
