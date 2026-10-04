"""Robustly fetch the Open Buildings tile 2e7 (~5.9 GB) with HTTP Range resume,
into the v2.0 cache so scripts/fetch_open_buildings.py reuses it, then rasterise
to building_coverage_utm48s.tif on the Jakarta GLO-30 grid.

The plain v2.0 fetch broke mid-stream (IncompleteRead at 1.65 GB) under bandwidth
contention. This resumes the cached partial instead of restarting.
"""
import gzip
import subprocess
import sys
from pathlib import Path

import requests

CACHE = Path(r"D:/GPTs/Projects/flood-v2.0/cache/openbuildings")
DEST = CACHE / "2e7_buildings.csv.gz"
URL = ("https://storage.googleapis.com/open-buildings-data/v3/"
       "polygons_s2_level_4_gzip/2e7_buildings.csv.gz")


def resumable(url, dest, retries=50):
    for attempt in range(retries):
        have = dest.stat().st_size if dest.exists() else 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        try:
            with requests.get(url, headers=headers, stream=True, timeout=300) as r:
                if r.status_code == 416:  # already complete
                    print("  range not satisfiable -> already complete", flush=True)
                    return
                if r.status_code not in (200, 206):
                    print(f"  status {r.status_code}, retry", flush=True)
                    continue
                cr = r.headers.get("Content-Range")
                full = int(cr.split("/")[-1]) if cr else have + int(r.headers.get("Content-Length", 0))
                mode = "ab" if (have and r.status_code == 206) else "wb"
                if mode == "wb":
                    have = 0
                with open(dest, mode) as f:
                    for chunk in r.iter_content(chunk_size=8 * 1024 * 1024):
                        f.write(chunk)
                        have += len(chunk)
                sz = dest.stat().st_size
                if sz >= full:
                    print(f"  complete {sz/1e9:.2f} GB", flush=True)
                    return
                print(f"  partial {sz/1e9:.2f}/{full/1e9:.2f} GB, resume", flush=True)
        except Exception as e:  # noqa: BLE001
            sz = dest.stat().st_size if dest.exists() else 0
            print(f"  attempt {attempt+1}: {type(e).__name__} at {sz/1e9:.2f} GB, resume", flush=True)
    raise SystemExit("failed after retries")


def verify_gzip(dest):
    """Confirm the gz is fully readable to the end (tail decompresses)."""
    n = 0
    with gzip.open(dest, "rt") as f:
        for _ in f:
            n += 1
    print(f"  gzip OK, {n:,} lines", flush=True)


if __name__ == "__main__":
    print(f"resuming {DEST} from {DEST.stat().st_size/1e9 if DEST.exists() else 0:.2f} GB", flush=True)
    resumable(URL, DEST)
    print("verifying gzip integrity...", flush=True)
    verify_gzip(DEST)
    print("DOWNLOAD OK -> now run fetch_open_buildings.py (will reuse cache)", flush=True)
