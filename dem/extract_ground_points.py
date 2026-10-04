"""
Phase 1 ground-truth extraction (stream-and-subset).

Opens ATL08 / GEDI L2A granules remotely (HTTP range reads via earthaccess.open),
reads ONLY the coordinate/height/quality datasets, keeps only points inside the
DEM bbox, applies quality filters, reconciles WGS84-ellipsoidal -> EGM2008, and
writes a tidy ground-point table (parquet).

Avoids downloading whole granules (GEDI ~2.4 GB each; we need only the city subset).

Output columns: lon, lat, h_ellip, h_egm2008, source, beam, granule, plus
product-specific quality columns.
"""
from __future__ import annotations
import argparse
import queue
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import h5py
import rasterio
from rasterio.warp import transform_bounds
import earthaccess

sys.path.insert(0, str(Path(__file__).parent))
from datum_reconcile import ellipsoidal_to_egm2008  # noqa: E402

ATL08 = "ATL08"
GEDI = "GEDI02_A"

# Per-granule guards (a single hung network read previously froze the whole job).
GRANULE_TIMEOUT_S = 420   # GEDI granules normally take ~200-300s; cap well above.
GRANULE_RETRIES = 1


def _open_and_extract(granule, gid, bbox, extractor):
    """Open ONE granule stream and extract — runs inside a timeout-guarded thread."""
    fo = earthaccess.open([granule])[0]
    return extractor(fo, gid, bbox)


def _run_with_timeout(fn, args, timeout):
    """Run fn(*args) in a DAEMON thread so a hung network read can't block the
    process (daemon threads don't join on exit). Returns (status, value)."""
    q = queue.Queue()

    def worker():
        try:
            q.put(("ok", fn(*args)))
        except Exception as e:  # noqa: BLE001
            q.put((f"ERR {type(e).__name__}", None))

    threading.Thread(target=worker, daemon=True).start()
    try:
        return q.get(timeout=timeout)
    except queue.Empty:
        return (f"TIMEOUT>{timeout}s", None)


def dem_bbox_lonlat(dem_path, buffer_deg=0.02):
    with rasterio.open(dem_path) as src:
        b = src.bounds
        lo, la, hi, ha = transform_bounds(src.crs, "EPSG:4326",
                                          b.left, b.bottom, b.right, b.top)
    return (lo - buffer_deg, la - buffer_deg, hi + buffer_deg, ha + buffer_deg)


def _in_bbox(lon, lat, bbox):
    lo, la, hi, ha = bbox
    return (lon >= lo) & (lon <= hi) & (lat >= la) & (lat <= ha)


def extract_atl08(fileobj, granule_id, bbox):
    rows = []
    with h5py.File(fileobj, "r") as f:
        beams = [k for k in f.keys() if k.startswith("gt")]
        for b in beams:
            try:
                ls = f[b]["land_segments"]
                lat = ls["latitude"][:]
                lon = ls["longitude"][:]
                h_te = ls["terrain"]["h_te_best_fit"][:]      # WGS84 ellipsoidal
                h_unc = ls["terrain"]["h_te_uncertainty"][:]
                n_ph = ls["terrain"]["n_te_photons"][:]
            except KeyError:
                continue
            m = _in_bbox(lon, lat, bbox) & np.isfinite(h_te)
            m &= (h_te > -100) & (h_te < 9000)
            m &= (h_unc < 2.0) & (n_ph > 50)                  # quality
            if not m.any():
                continue
            df = pd.DataFrame({
                "lon": lon[m], "lat": lat[m], "h_ellip": h_te[m],
                "h_unc": h_unc[m], "n_photons": n_ph[m],
                "source": "ATL08", "beam": b, "granule": granule_id,
            })
            rows.append(df)
    return pd.concat(rows, ignore_index=True) if rows else None


def extract_gedi(fileobj, granule_id, bbox):
    rows = []
    with h5py.File(fileobj, "r") as f:
        beams = [k for k in f.keys() if k.startswith("BEAM")]
        for b in beams:
            try:
                g = f[b]
                lat = g["lat_lowestmode"][:]
                lon = g["lon_lowestmode"][:]
                elev = g["elev_lowestmode"][:]                # WGS84 ellipsoidal
                qf = g["quality_flag"][:]
                deg = g["degrade_flag"][:]
                sens = g["sensitivity"][:]
            except KeyError:
                continue
            m = _in_bbox(lon, lat, bbox) & np.isfinite(elev)
            m &= (elev > -100) & (elev < 9000)
            m &= (qf == 1) & (deg == 0) & (sens > 0.9)        # quality
            if not m.any():
                continue
            df = pd.DataFrame({
                "lon": lon[m], "lat": lat[m], "h_ellip": elev[m],
                "sensitivity": sens[m],
                "source": "GEDI", "beam": b, "granule": granule_id,
            })
            rows.append(df)
    return pd.concat(rows, ignore_index=True) if rows else None


def _safe_name(gid):
    return "".join(c if (c.isalnum() or c in "._-") else "_" for c in gid)


def run(short_name, tag, bbox, temporal, max_granules, out_parquet):
    """Resumable extraction: one part-parquet per granule (skip-if-done),
    then consolidate. An empty part marks a 0-point granule so resume skips it."""
    out_parquet = Path(out_parquet)
    parts_dir = out_parquet.parent / f"{tag}_parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    res = earthaccess.search_data(short_name=short_name, bounding_box=bbox,
                                  temporal=temporal)
    print(f"{short_name}: {len(res)} granules match", flush=True)
    if max_granules:
        res = res[:max_granules]
        print(f"  (capped to {len(res)} for this run)", flush=True)

    extractor = extract_atl08 if tag == "atl08" else extract_gedi
    t0 = time.time()
    # Resolve granule ids first so we can skip already-done parts before opening streams.
    gids = [g.get("meta", {}).get("native-id", f"{tag}_{i}") for i, g in enumerate(res)]
    todo_idx = [i for i, gid in enumerate(gids)
                if not (parts_dir / f"{_safe_name(gid)}.parquet").exists()]
    print(f"  {len(gids)-len(todo_idx)} already done, {len(todo_idx)} to do", flush=True)

    for j, i in enumerate(todo_idx):
        gid, granule = gids[i], res[i]
        part = parts_dir / f"{_safe_name(gid)}.parquet"
        # Per-granule TIMEOUT + RETRY: a single hung network read must not freeze
        # the whole job (earlier bug). Open per-granule so a retry can re-open.
        df, status = None, "fail"
        for attempt in range(GRANULE_RETRIES + 1):
            status, df = _run_with_timeout(
                _open_and_extract, (granule, gid, bbox, extractor), GRANULE_TIMEOUT_S)
            if status == "ok":
                break
            if attempt < GRANULE_RETRIES:
                print(f"  [{j+1}/{len(todo_idx)}] {gid}: {status}, retry", flush=True)
        if status != "ok":
            # No part written -> retried on a later run. Don't block the job.
            print(f"  [{j+1}/{len(todo_idx)}] {gid}: SKIP ({status}) ({time.time()-t0:.0f}s)", flush=True)
            continue
        if df is None or len(df) == 0:
            df = pd.DataFrame(columns=["lon", "lat", "h_ellip", "source",
                                       "beam", "granule", "h_egm2008"])
        else:
            df["h_egm2008"] = ellipsoidal_to_egm2008(
                df["lon"].values, df["lat"].values, df["h_ellip"].values)
        df.to_parquet(part, index=False)
        print(f"  [{j+1}/{len(todo_idx)}] {gid}: {len(df)} pts ({time.time()-t0:.0f}s)", flush=True)

    # Consolidate all parts.
    all_parts = sorted(parts_dir.glob("*.parquet"))
    frames = [pd.read_parquet(p) for p in all_parts]
    frames = [f for f in frames if len(f)]
    if not frames:
        print(f"{short_name}: NO points extracted", flush=True)
        return None
    allp = pd.concat(frames, ignore_index=True)
    allp.to_parquet(out_parquet, index=False)
    print(f"{short_name}: consolidated {len(allp)} points from {len(all_parts)} parts -> {out_parquet}", flush=True)
    return allp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default=r"D:\GPTs\Projects\flood-v3.0\dem\bangkok\glo30_dsm_utm47n.tif")
    ap.add_argument("--outdir", default=r"D:\GPTs\Projects\flood-v3.0\dem\bangkok\ground_truth")
    ap.add_argument("--product", choices=["atl08", "gedi", "both"], default="both")
    ap.add_argument("--start", default="2019-01-01")
    ap.add_argument("--end", default="2023-12-31")
    ap.add_argument("--max-granules", type=int, default=0)
    args = ap.parse_args()

    earthaccess.login(strategy="netrc")
    bbox = dem_bbox_lonlat(Path(args.dem))
    temporal = (args.start, args.end)
    print(f"bbox={tuple(round(x,4) for x in bbox)} temporal={temporal}", flush=True)
    out = Path(args.outdir)
    if args.product in ("atl08", "both"):
        run(ATL08, "atl08", bbox, temporal, args.max_granules, out / "atl08_ground_points.parquet")
    if args.product in ("gedi", "both"):
        run(GEDI, "gedi", bbox, temporal, args.max_granules, out / "gedi_ground_points.parquet")


if __name__ == "__main__":
    main()
