"""Build the Kuala Lumpur flood-hotspot register (geocoded + DEM-verified).

Per limitations register #6b ("hand-typed coordinates are unreliable — do not
expand the register by eye"), this compiles the KL register from a *documented*
seed list (chronic DBKL/DID flood-prone locations + Dec-2021 event epicentres +
elevated dry controls), geocodes each via OpenStreetMap Nominatim, and
cross-checks the modelled-DEM elevation so a mis-geocode (a "positive" landing on
high ground, or a "dry control" in a low area) is flagged for review rather than
silently polluting the hit-rate / CRR.

Output: data/kuala_lumpur/manifest/hotspots.csv  (name,lon,lat,kind,confidence,source)
plus a verification table on stdout (name, lon, lat, kind, dem_elev_m, flag).

Usage
-----
    python scripts/build_kl_hotspot_register.py            # geocode + write
    python scripts/build_kl_hotspot_register.py --dry-run  # print only, no write

Geocoding is network-dependent (Nominatim, 1 req/s, custom UA). Points that fail
to geocode are written with empty lon/lat and confidence=failed for manual follow-up.
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import click
import numpy as np
import rasterio
from rasterio.warp import transform as warp_transform

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEM_PATH = PROJECT_ROOT / "data" / "kuala_lumpur" / "copernicus_dem_utm47n.tif"
OUT_CSV = PROJECT_ROOT / "data" / "kuala_lumpur" / "manifest" / "hotspots.csv"

# KL/Klang Valley viewbox to bias Nominatim (min_lon, min_lat, max_lon, max_lat)
VIEWBOX = (101.40, 2.90, 101.95, 3.42)

# Elevation expectations (m, GLO-30) for the DEM cross-check.
# KL's city centre sits at ~30-56 m (genuinely higher than Singapore's ~5-20 m),
# while its dry-control hills are 66-156 m — so 60 m cleanly separates the two
# populations for KL (vs 45 m borrowed from SG, which over-flagged city-centre roads).
POSITIVE_MAX_ELEV_M = 60.0   # documented flood-prone points should sit low (KL-calibrated)
DRY_MIN_ELEV_M = 60.0        # elevated dry controls should sit high

# (display_name, geocode_query, kind, source)
#   kind: "positive" (documented flooded / flood-prone) | "dry" (elevated control)
SEED: list[tuple[str, str, str, str]] = [
    # --- Chronic KL flood-prone (DBKL 14-hotspot list + DID Klang Valley) ---
    ("Jalan Sultan Azlan Shah", "Jalan Sultan Azlan Shah, Kuala Lumpur, Malaysia", "positive", "DBKL flood-hotspot list (Scoop 2024)"),
    ("Lebuhraya Sultan Iskandar (Mahameru)", "Lebuhraya Mahameru, Kuala Lumpur, Malaysia", "positive", "DBKL flood-hotspot list (Scoop 2024)"),
    ("Jalan Tun Sambanthan, Brickfields", "Jalan Tun Sambanthan, Brickfields, Kuala Lumpur, Malaysia", "positive", "DBKL flood-hotspot list (Scoop 2024)"),
    ("Segambut Dalam", "Segambut Dalam, Kuala Lumpur, Malaysia", "positive", "DBKL flood-hotspot list (Toba River)"),
    ("Pantai Dalam", "Pantai Dalam, Kuala Lumpur, Malaysia", "positive", "DBKL flood-hotspot list (Scoop 2024)"),
    ("Bukit Jalil", "Bukit Jalil, Kuala Lumpur, Malaysia", "positive", "DBKL flood-hotspot list (Scoop 2024; LRT station underpass)"),
    ("Jalan Rahmat (PWTC / Sg Gombak)", "Jalan Rahmat, Kuala Lumpur, Malaysia", "positive", "DBKL hotspot; +600 mm after ~2h rain (Brudirect/Star)"),
    ("Bulatan Datuk Onn", "Bulatan Dato Onn, Kuala Lumpur, Malaysia", "positive", "DBKL flood-hotspot list (Scoop 2024)"),
    ("Jalan Tun Razak", "Jalan Tun Razak, Kuala Lumpur, Malaysia", "positive", "DID/Star Klang Valley hotspots (2019)"),
    ("Jalan Raja Chulan", "Jalan Raja Chulan, Kuala Lumpur, Malaysia", "positive", "DID/Star Klang Valley hotspots (2019)"),
    ("Masjid Jamek (Gombak-Klang confluence)", "Masjid Jamek, Kuala Lumpur, Malaysia", "positive", "Historic Gombak/Klang confluence flood (SMART tunnel rationale)"),
    ("Kampung Baru", "Kampung Baru, Kuala Lumpur, Malaysia", "positive", "Historic KL flood-prone (Klang riverbank)"),
    ("Jalan Chow Kit", "Chow Kit, Kuala Lumpur, Malaysia", "positive", "DID/DBKL flash-flood records"),
    ("Old Klang Road", "Old Klang Road, Kuala Lumpur, Malaysia", "positive", "Dec 2021 Klang Valley floods (Malay Mail)"),
    # --- December 2021 event epicentres (catastrophic inundation) ---
    ("Taman Sri Muda, Shah Alam", "Taman Sri Muda, Shah Alam, Selangor, Malaysia", "positive", "Dec 2021 floods, 14 deaths, ~4 m (Wikipedia; ISEAS 2022/26)"),
    ("Taman Sri Nanding, Hulu Langat", "Taman Sri Nanding, Hulu Langat, Selangor, Malaysia", "positive", "Dec 2021 Hulu Langat (UTHM study)"),
    ("Klang town", "Klang, Selangor, Malaysia", "positive", "Dec 2021 worst-hit district (Wikipedia)"),
    # Dropped after DEM cross-check (limitation #6b):
    #   Kg Bukit Lanchong — Nominatim mis-geocoded to the "Bukit"/hill (139 m); flooded area is low.
    #   Kg Sungai Lui     — Dec 2021 event there was a debris-flow/landslide (Titiwangsa range),
    #                       not pluvial ponding; mechanistically out of scope for the model.
    # --- Elevated dry controls (model-blind selection; DEM-verified) ---
    ("Bukit Tunku (Kenny Hills)", "Bukit Tunku, Kuala Lumpur, Malaysia", "dry", "Elevated residential control"),
    ("Damansara Heights", "Damansara Heights, Kuala Lumpur, Malaysia", "dry", "Elevated residential control"),
    ("Bukit Antarabangsa", "Bukit Antarabangsa, Ampang, Selangor, Malaysia", "dry", "Hillside control"),
    ("Bukit Gasing", "Bukit Gasing, Petaling Jaya, Selangor, Malaysia", "dry", "Forested ridge control"),
    ("Mont Kiara", "Mont Kiara, Kuala Lumpur, Malaysia", "dry", "Elevated residential control"),
    ("Bukit Persekutuan (Federal Hill)", "Bukit Persekutuan, Kuala Lumpur, Malaysia", "dry", "Elevated control"),
    ("Bukit Kiara", "Bukit Kiara, Kuala Lumpur, Malaysia", "dry", "Forested hill control"),
]


def _geocode(query: str) -> tuple[float, float] | None:
    params = {
        "q": query, "format": "json", "limit": "1",
        "viewbox": ",".join(str(v) for v in (VIEWBOX[0], VIEWBOX[3], VIEWBOX[2], VIEWBOX[1])),
        "bounded": "1",
        "countrycodes": "my",
    }
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "flood-v2.0-hotspot-register/1.0 (research)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:  # noqa: BLE001
        click.echo(f"    [warn] geocode failed for {query!r}: {exc}", err=True)
        return None
    if not data:
        return None
    return float(data[0]["lon"]), float(data[0]["lat"])


def _dem_elev(lon: float, lat: float, ds, dem_crs) -> float | None:
    xs, ys = warp_transform("EPSG:4326", dem_crs, [lon], [lat])
    row, col = ds.index(xs[0], ys[0])
    if not (0 <= row < ds.height and 0 <= col < ds.width):
        return None
    val = ds.read(1)[row, col]
    if ds.nodata is not None and val == ds.nodata:
        return None
    return float(val)


@click.command()
@click.option("--dry-run", is_flag=True, default=False, help="Print the table; do not write the CSV.")
def cli(dry_run: bool):
    ds = rasterio.open(DEM_PATH)
    dem_crs = ds.crs
    rows: list[dict] = []
    click.echo(f"{'name':<42}{'lon':>9}{'lat':>8}{'kind':>9}{'elev_m':>8}  flag")
    click.echo("-" * 92)
    for name, query, kind, source in SEED:
        coord = _geocode(query)
        time.sleep(1.1)  # Nominatim usage policy: <= 1 req/s
        if coord is None:
            click.echo(f"{name:<42}{'--':>9}{'--':>8}{kind:>9}{'--':>8}  GEOCODE_FAILED")
            rows.append({"name": name, "lon": "", "lat": "", "kind": kind,
                         "confidence": "failed", "source": source})
            continue
        lon, lat = coord
        elev = _dem_elev(lon, lat, ds, dem_crs)
        flag = "ok"
        conf = "high"
        if elev is None:
            flag, conf = "OUT_OF_DEM", "low"
        elif kind == "positive" and elev > POSITIVE_MAX_ELEV_M:
            flag, conf = f"REVIEW: positive high ({elev:.0f} m)", "low"
        elif kind == "dry" and elev < DRY_MIN_ELEV_M:
            flag, conf = f"REVIEW: dry-control low ({elev:.0f} m)", "low"
        elev_s = f"{elev:.0f}" if elev is not None else "--"
        click.echo(f"{name:<42}{lon:>9.4f}{lat:>8.4f}{kind:>9}{elev_s:>8}  {flag}")
        rows.append({"name": name, "lon": f"{lon:.5f}", "lat": f"{lat:.5f}",
                     "kind": kind, "confidence": conf, "source": source})
    ds.close()

    n_pos = sum(1 for r in rows if r["kind"] == "positive")
    n_dry = sum(1 for r in rows if r["kind"] == "dry")
    n_review = sum(1 for r in rows if r["confidence"] in ("low", "failed"))
    click.echo("-" * 92)
    click.echo(f"positives={n_pos}  dry_controls={n_dry}  need_review={n_review}")

    if dry_run:
        click.echo("\n[dry-run] not written.")
        return
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "lon", "lat", "kind", "confidence", "source"])
        w.writeheader()
        w.writerows(rows)
    click.echo(f"\nWrote {OUT_CSV} ({len(rows)} rows).")


if __name__ == "__main__":
    cli()
