"""Robust per-city Zenodo uploader (replaces the fragile upload.sh).

Reads the token from zenodo/.token (gitignored), then for each city:
  POST a draft deposition -> PUT metadata (zenodo/<city>/zenodo.json)
  -> upload ONE zip of the full maps/+inputs/ tree (built from MANIFEST.csv),
     plus README.md and LICENSE as visible landing-page files.

The Zenodo bucket API is flat (no slashes in object keys), so the folder tree
that the README documents is shipped inside <city>_flood_atlas.zip and extracts
to exactly that layout. Every HTTP error prints status + body and aborts that
city (leaving the rest). Transient errors retry up to 3x. Nothing is published;
each city ends as a DRAFT for manual review + Publish.

Usage:  python scripts/_zenodo_upload.py singapore kuala_lumpur bangkok
Env:    ZENODO_API (default https://zenodo.org/api)
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.environ.get("ZENODO_API", "https://zenodo.org/api")
TOKEN = open(os.path.join(ROOT, "zenodo", ".token")).read().strip()
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def req(method, url, data=None, headers=None, retries=3):
    hdrs = dict(AUTH)
    if headers:
        hdrs.update(headers)
    for attempt in range(1, retries + 1):
        r = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(r, timeout=900) as resp:
                body = resp.read()
                return resp.status, body
        except urllib.error.HTTPError as e:
            body = e.read()
            if e.code >= 500 and attempt < retries:
                time.sleep(2 * attempt)
                continue
            raise SystemExit(f"  HTTP {e.code} on {method} {url}\n  {body[:800].decode(errors='replace')}")
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(2 * attempt)
                continue
            raise SystemExit(f"  connection error on {method} {url}: {e}")


def build_zip(slug, cdir):
    """Zip the full maps/+inputs/ tree (manifest archive_name = path in zip)."""
    with open(os.path.join(cdir, "MANIFEST.csv"), newline="") as fh:
        rows = list(csv.DictReader(fh))
    zpath = os.path.join(cdir, f"{slug}_flood_atlas.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for row in rows:
            z.write(os.path.join(ROOT, row["source_path"]), arcname=row["archive_name"])
        z.write(os.path.join(cdir, "README.md"), arcname="README.md")
        z.write(os.path.join(cdir, "LICENSE"), arcname="LICENSE")
    mb = os.path.getsize(zpath) / 1e6
    print(f"  built {os.path.basename(zpath)} ({len(rows)} files, {mb:.1f} MB)")
    return zpath


def put_file(bucket, name, path):
    with open(path, "rb") as f:
        payload = f.read()
    req("PUT", f"{bucket}/{name}", data=payload,
        headers={"Content-Type": "application/octet-stream"})


def upload_city(slug):
    cdir = os.path.join(ROOT, "zenodo", slug)
    print(f"===== {slug} =====")
    zpath = build_zip(slug, cdir)
    # 1. create draft
    status, body = req("POST", f"{API}/deposit/depositions",
                       data=b"{}", headers={"Content-Type": "application/json"})
    dep = json.loads(body)
    did = dep["id"]
    bucket = dep["links"]["bucket"]
    doi = dep["metadata"].get("prereserve_doi", {}).get("doi", "?")
    print(f"  draft {did}  (reserved DOI {doi})")
    # 2. metadata
    meta = open(os.path.join(cdir, "zenodo.json"), "rb").read()
    req("PUT", f"{API}/deposit/depositions/{did}",
        data=meta, headers={"Content-Type": "application/json"})
    print("  metadata set")
    # 3. files: the zip + visible README/LICENSE
    for name, path in [(f"{slug}_flood_atlas.zip", zpath),
                       ("README.md", os.path.join(cdir, "README.md")),
                       ("LICENSE", os.path.join(cdir, "LICENSE"))]:
        put_file(bucket, name, path)
        print(f"  + {name}")
    html = dep["links"]["html"]
    print(f"  DONE -> DRAFT {html}  (DOI {doi})")
    return {"city": slug, "id": did, "doi": doi, "html": html}


def main():
    cities = sys.argv[1:] or ["singapore", "kuala_lumpur", "bangkok"]
    out = [upload_city(c) for c in cities]
    print("\n=== summary ===")
    for r in out:
        print(f"  {r['city']:13s} draft {r['id']}  DOI {r['doi']}")
        print(f"                {r['html']}")


if __name__ == "__main__":
    main()
