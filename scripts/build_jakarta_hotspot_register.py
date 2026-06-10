"""Build the Jakarta flood-hotspot register (geocoded + DEM-verified) — Plan J1.

Mirrors scripts/build_bangkok_hotspot_register.py. Positives = localities documented flooded in
Jakarta's recurrent monsoon floods (2007/2013/2020, esp. the Jan-2020 New Year event); dry
controls = the genuinely-elevated south + the documented-dry central natural-levee core (see
docs/superpowers/runs/2026-06-09-jakarta-hotspot-research.md). Geocodes each via OpenStreetMap
Nominatim and records the DEM elevation for the verification table.

Jakarta DOES have a real elevation gradient (the south rises toward the Bogor piedmont), so —
unlike Bangkok's flat delta — the dry controls are the genuinely-elevated south + the
documented-dry central levee. The elevation expectation for dry controls is therefore SOFT; the
firm mis-geocode guard for a dry control is proximity to a documented positive (i.e. likely
mis-placed onto a flood area). Positives that land implausibly high (>50 m on the GLO-30 DEM,
where the DKI core sits ~0–15 m) are flagged as probable mis-geocodes.

Output: data/jakarta/manifest/hotspots.csv (name,lon,lat,kind,confidence,source).
Usage:
    python scripts/build_jakarta_hotspot_register.py            # geocode + write
    python scripts/build_jakarta_hotspot_register.py --dry-run  # print table only

Geocoding is network-dependent (Nominatim, 1 req/s, custom UA). Points that fail to geocode
are written with empty lon/lat and confidence=failed for manual follow-up.
"""
from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import click
import numpy as np
import rasterio
from rasterio.warp import transform as warp_transform

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEM_PATH = PROJECT_ROOT / "data" / "jakarta" / "copernicus_dem_utm48s.tif"   # uncorrected GLO-30 for geocode-verify
OUT_CSV = PROJECT_ROOT / "data" / "jakarta" / "manifest" / "hotspots.csv"

# Greater Jakarta (Jabodetabek core) viewbox to bias Nominatim (min_lon, min_lat, max_lon, max_lat)
VIEWBOX = (106.60, -6.40, 107.05, -6.05)

# DEM elevation expectations (m, GLO-30). DKI core is ~0-15 m; the south rises toward Depok.
# A documented POSITIVE landing implausibly high is a mis-geocode (rooftop / upland point).
POSITIVE_MAX_ELEV_M = 50.0
# Jakarta DOES have a real elevation gradient (unlike Bangkok's flat delta): dry controls are
# the genuinely-elevated south + documented-dry central levee. Soft elevation expectation only;
# the firm mis-geocode guard for a dry control is proximity to a positive (metres).
DRY_MIN_DIST_TO_POSITIVE_M = 50.0

# (display_name, geocode_query, kind, source) — model-blind; see the research doc.
SEED: list[tuple[str, str, str, str]] = [
    # --- Positives: Ciliwung-corridor fluvial (chronic 2007/2013/2020) ---
    ("Kampung Melayu", "Kampung Melayu, Jatinegara, Jakarta, Indonesia", "positive", "Ciliwung overflow; chronic 2007/2013/2020 flooding (BPBD DKI; news)"),
    ("Bukit Duri", "Bukit Duri, Tebet, Jakarta, Indonesia", "positive", "Ciliwung bank; recurrent inundation 2007/2013/2020 (news; academic)"),
    ("Kampung Pulo", "Kampung Pulo, Jatinegara, Jakarta, Indonesia", "positive", "Ciliwung meander; iconic chronic flood site (BPBD DKI)"),
    ("Cawang", "Cawang, Kramat Jati, Jakarta, Indonesia", "positive", "Ciliwung corridor; 2007/2013/2020 flooding (news)"),
    ("Rawajati", "Rawajati, Pancoran, Jakarta, Indonesia", "positive", "Ciliwung bank South Jakarta; recurrent (news)"),
    ("Bidara Cina", "Bidara Cina, Jatinegara, Jakarta, Indonesia", "positive", "Ciliwung corridor; recurrent (news)"),
    # --- Positives: monsoon pluvial / other rivers (2020-prominent) ---
    ("Cipinang Melayu", "Cipinang Melayu, Makasar, Jakarta, Indonesia", "positive", "East Jakarta; among worst-hit Jan-2020 (news)"),
    ("Kemang", "Kemang, Mampang Prapatan, Jakarta, Indonesia", "positive", "Krukut river; affluent-South pocket flooded Jan-2020 (widely reported)"),
    ("Kelapa Gading", "Kelapa Gading, Jakarta, Indonesia", "positive", "North-East low pluvial basin; chronic ponding 2013/2020 (news)"),
    ("Grogol", "Grogol, Grogol Petamburan, Jakarta, Indonesia", "positive", "West Jakarta; Sekretaris/Grogol canal flooding 2020 (news)"),
    ("Cengkareng", "Cengkareng, Jakarta, Indonesia", "positive", "West Jakarta; Angke/Cengkareng drain flooding 2020 (news)"),
    # --- Positives: North Jakarta rob / coastal-subsidence ---
    ("Penjaringan", "Penjaringan, Jakarta, Indonesia", "positive", "North Jakarta polder below MSL; rob + 2007/2020 coastal flooding (BAPPENAS; news)"),
    ("Pluit", "Pluit, Penjaringan, Jakarta, Indonesia", "positive", "North Jakarta below sea level; chronic rob, pump-dependent (news)"),
    ("Muara Baru", "Muara Baru, Penjaringan, Jakarta, Indonesia", "positive", "North Jakarta fastest-subsiding; rob flooding (Abidin et al.; news)"),
    ("Kalibaru", "Kalibaru, Cilincing, Jakarta, Indonesia", "positive", "North-East coast; rob + tidal flooding (news)"),
    ("Cilincing", "Cilincing, Jakarta, Indonesia", "positive", "North-East coastal kelurahan; rob (news)"),
    # --- Positives reclassified from dry controls (J2 re-exam): central-Jakarta levee areas
    #     DOCUMENTED FLOODED in 2013 (mislabels; see 2026-06-09-jakarta-drycontrol-reexam.md) ---
    ("Menteng", "Menteng, Jakarta, Indonesia", "positive", "Reclassified J2: documented flooded 2013 (Cikini/Menteng on Ciliwung; Thamrin/Bundaran-HI corridor) + 2007 — central Jakarta inundates in RP50-100 events"),
    ("Gambir", "Gambir, Jakarta, Indonesia", "positive", "Reclassified J2: documented flooded 2013 (Merdeka Palace/Monas area surrounded by floodwater) — central Jakarta"),
    # --- Dry controls: genuinely-elevated south (Jakarta's real S->N elevation gradient) ---
    ("Cilandak", "Cilandak, Jakarta, Indonesia", "dry", "Elevated South Jakarta; not on the 2007/2013/2020 flood lists (terrain-high control)"),
    ("Jagakarsa", "Jagakarsa, Jakarta, Indonesia", "dry", "Elevated far-South Jakarta; higher ground toward Depok (control)"),
    ("Lebak Bulus", "Lebak Bulus, Cilandak, Jakarta, Indonesia", "dry", "Elevated South Jakarta (control)"),
    ("Pasar Minggu", "Pasar Minggu, Jakarta, Indonesia", "dry", "South Jakarta upland away from Ciliwung bank (elevated off-river point; control)"),
    ("Cipete", "Cipete, Cilandak, Jakarta, Indonesia", "dry", "Elevated South Jakarta residential (control)"),
    ("Ragunan", "Ragunan, Pasar Minggu, Jakarta, Indonesia", "dry", "Elevated South Jakarta (zoo area, higher ground off the Ciliwung); not a documented event-flood area (J2 control)"),
    ("Pondok Labu", "Pondok Labu, Cilandak, Jakarta, Indonesia", "dry", "Elevated far-South Jakarta near Cilandak; no major event flooding (J2 control)"),
    ("Pondok Pinang", "Pondok Pinang, Kebayoran Lama, Jakarta, Indonesia", "dry", "Elevated South Jakarta (Kebayoran Lama upland); not on documented flood lists (J2 control)"),
]


def _geocode(query: str) -> tuple[float, float] | None:
    params = {
        "q": query, "format": "json", "limit": "1",
        "viewbox": ",".join(str(v) for v in (VIEWBOX[0], VIEWBOX[3], VIEWBOX[2], VIEWBOX[1])),
        "bounded": "1",
        "countrycodes": "id",
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


def _proj_m(lon: float, lat: float, dem_crs) -> tuple[float, float]:
    xs, ys = warp_transform("EPSG:4326", dem_crs, [lon], [lat])
    return float(xs[0]), float(ys[0])


@click.command()
@click.option("--dry-run", is_flag=True, default=False, help="Print the table; do not write the CSV.")
def cli(dry_run: bool):
    ds = rasterio.open(DEM_PATH)
    dem_crs = ds.crs

    # Pass 1: geocode everything, collect coords + elevation.
    recs: list[dict] = []
    for name, query, kind, source in SEED:
        coord = _geocode(query)
        time.sleep(1.1)  # Nominatim usage policy: <= 1 req/s
        if coord is None:
            recs.append({"name": name, "lon": None, "lat": None, "kind": kind,
                         "source": source, "elev": None, "xy": None})
            continue
        lon, lat = coord
        elev = _dem_elev(lon, lat, ds, dem_crs)
        recs.append({"name": name, "lon": lon, "lat": lat, "kind": kind, "source": source,
                     "elev": elev, "xy": _proj_m(lon, lat, dem_crs)})
    ds.close()

    pos_xy = [r["xy"] for r in recs if r["kind"] == "positive" and r["xy"] is not None]

    # Pass 2: verify + flag.
    click.echo(f"{'name':<34}{'lon':>9}{'lat':>9}{'kind':>9}{'elev_m':>8}  flag")
    click.echo("-" * 86)
    rows: list[dict] = []
    for r in recs:
        if r["lon"] is None:
            click.echo(f"{r['name']:<34}{'--':>9}{'--':>9}{r['kind']:>9}{'--':>8}  GEOCODE_FAILED")
            rows.append({"name": r["name"], "lon": "", "lat": "", "kind": r["kind"],
                         "confidence": "failed", "source": r["source"]})
            continue
        flag, conf = "ok", "high"
        elev = r["elev"]
        if elev is None:
            flag, conf = "OUT_OF_DEM", "low"
        elif r["kind"] == "positive" and elev > POSITIVE_MAX_ELEV_M:
            flag, conf = f"REVIEW: positive high ({elev:.0f} m)", "low"
        elif r["kind"] == "dry" and pos_xy:
            dmin = min(np.hypot(r["xy"][0] - px, r["xy"][1] - py) for px, py in pos_xy)
            if dmin < DRY_MIN_DIST_TO_POSITIVE_M:
                flag, conf = f"REVIEW: dry within {dmin:.0f} m of a positive", "low"
        elev_s = f"{elev:.0f}" if elev is not None else "--"
        click.echo(f"{r['name']:<34}{r['lon']:>9.4f}{r['lat']:>9.4f}{r['kind']:>9}{elev_s:>8}  {flag}")
        rows.append({"name": r["name"], "lon": f"{r['lon']:.5f}", "lat": f"{r['lat']:.5f}",
                     "kind": r["kind"], "confidence": conf, "source": r["source"]})

    n_pos = sum(1 for r in rows if r["kind"] == "positive")
    n_dry = sum(1 for r in rows if r["kind"] == "dry")
    n_review = sum(1 for r in rows if r["confidence"] in ("low", "failed"))
    click.echo("-" * 86)
    click.echo(f"positives={n_pos}  dry_controls={n_dry}  need_review={n_review}")

    if dry_run:
        click.echo("\n[dry-run] not written.")
        return
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "lon", "lat", "kind", "confidence", "source"])
        w.writeheader()
        w.writerows(rows)
    click.echo(f"\nWrote {OUT_CSV} ({len(rows)} rows).")


if __name__ == "__main__":
    cli()
