"""Build the Bangkok flood-hotspot register (geocoded + DEM-verified) — Plan B1.

Mirrors scripts/build_kl_hotspot_register.py. Positives = localities documented flooded in
the 2011 Thailand megaflood; dry controls = the bunded inner core documented defended /
stayed dry (see docs/superpowers/runs/2026-06-06-bangkok-hotspot-research.md). Geocodes each
via OpenStreetMap Nominatim and records the DEM elevation for the verification table.

Bangkok is a FLAT delta, so — unlike KL's hill controls — the dry controls are LOW-lying
(the defended CBD). The KL elevation gate (`dry must sit high`) is therefore DROPPED. A dry
control is flagged for review only if it geocodes within ~50 m of a documented positive
(i.e. likely mis-placed onto a flood area). Positives that land implausibly high (>30 m on
the GLO-30 delta DEM, where the city sits ~0–5 m) are flagged as probable mis-geocodes.

Output: data/bangkok/manifest/hotspots.csv (name,lon,lat,kind,confidence,source).
Usage:
    python scripts/build_bangkok_hotspot_register.py            # geocode + write
    python scripts/build_bangkok_hotspot_register.py --dry-run  # print table only

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
DEM_PATH = PROJECT_ROOT / "data" / "bangkok" / "copernicus_dem_utm47n.tif"
OUT_CSV = PROJECT_ROOT / "data" / "bangkok" / "manifest" / "hotspots.csv"

# Bangkok Metropolitan Region viewbox to bias Nominatim (min_lon, min_lat, max_lon, max_lat)
VIEWBOX = (100.30, 13.45, 100.95, 14.20)

# Delta DEM elevation expectations (m, GLO-30): the whole BMR sits ~0-5 m. A documented
# positive landing implausibly high is a mis-geocode (a building rooftop or an upland point).
POSITIVE_MAX_ELEV_M = 30.0
# Dry controls are LOW-lying defended core — NO minimum-elevation gate (cf. KL hills). The
# mis-geocode guard for a dry control is proximity to a positive instead (metres).
DRY_MIN_DIST_TO_POSITIVE_M = 50.0

# (display_name, geocode_query, kind, source) — model-blind; see the research doc.
SEED: list[tuple[str, str, str, str]] = [
    # --- Positives: documented flooded in the 2011 Thailand megaflood ---
    ("Don Mueang", "Don Mueang, Bangkok, Thailand", "positive", "2011 flood: district + domestic airport inundated (Wikipedia; HII)"),
    ("Sai Mai", "Sai Mai, Bangkok, Thailand", "positive", "2011 flood: could not drain to sea pumping stations (HII)"),
    ("Khlong Sam Wa", "Khlong Sam Wa, Bangkok, Thailand", "positive", "2011 flood: NE district flooded (HII)"),
    ("Lak Si", "Lak Si, Bangkok, Thailand", "positive", "2011 flood: assistance dispatched (Wikipedia)"),
    ("Bang Khen", "Bang Khen, Bangkok, Thailand", "positive", "2011 flood: northern district flooded (HII/news)"),
    ("Bang Sue", "Bang Sue, Bangkok, Thailand", "positive", "2011 flood: assistance dispatched (Wikipedia)"),
    ("Rangsit", "Rangsit, Pathum Thani, Thailand", "positive", "2011 flood: Rangsit Univ. total inundation; businesses closed (Wikipedia)"),
    ("Lam Luk Ka", "Lam Luk Ka, Pathum Thani, Thailand", "positive", "2011 flood: Rangsit/Lumlukka corridor flooded (Wikipedia)"),
    # NOTE: Nava Nakorn industrial estate (a famous 2011-flooded estate) is DROPPED —
    # it sits at 14.11 N, north of the `bangkok` DEM extent (max 14.05 N), so the model
    # cannot evaluate it (out-of-domain, cf. KL Taman Sri Muda). The in-domain Rangsit /
    # Lam Luk Ka corridor already represents the upstream northern flooded belt.
    ("Bang Bua Thong", "Bang Bua Thong, Nonthaburi, Thailand", "positive", "2011 flood: Nonthaburi west flooded (HII/news)"),
    ("Pak Kret", "Pak Kret, Nonthaburi, Thailand", "positive", "2011 flood: riverside Nonthaburi flooded (news)"),
    ("Mueang Nonthaburi", "Mueang Nonthaburi, Nonthaburi, Thailand", "positive", "2011 flood: provincial-capital riverfront flooded (news)"),
    ("Min Buri", "Min Buri, Bangkok, Thailand", "positive", "2011 flood: eastern district flooded (HII)"),
    ("Nong Chok", "Nong Chok, Bangkok, Thailand", "positive", "2011 flood: far-eastern district flooded (HII)"),
    ("Taling Chan", "Taling Chan, Bangkok, Thailand", "positive", "2011 flood: western district flooded (news)"),
    ("Thawi Watthana", "Thawi Watthana, Bangkok, Thailand", "positive", "2011 flood: western district flooded (news)"),
    ("Bang Phlat", "Bang Phlat, Bangkok, Thailand", "positive", "2011 flood: riverfront overtopping (CBS/news)"),
    # --- Dry controls: documented-defended inner core that stayed dry in 2011 ---
    ("Silom", "Silom, Bang Rak, Bangkok, Thailand", "dry", "2011: CBD core held dry behind floodwalls (CNN; France24)"),
    ("Sathorn", "Sathon, Bangkok, Thailand", "dry", "2011: CBD held dry (CNN)"),
    ("Sukhumvit (Watthana)", "Sukhumvit Road, Watthana, Bangkok, Thailand", "dry", "2011: commercial/tourist core stayed dry (CNN; CSMonitor)"),
    ("Pathum Wan / Siam", "Pathum Wan, Bangkok, Thailand", "dry", "2011: Siam CBD stayed dry (news)"),
    ("Lumphini", "Lumphini, Pathum Wan, Bangkok, Thailand", "dry", "2011: central, defended, dry (news)"),
    ("Bang Rak", "Bang Rak, Bangkok, Thailand", "dry", "2011: riverside CBD held by floodwall (news)"),
    ("Ratchathewi", "Ratchathewi, Bangkok, Thailand", "dry", "2011: inner district stayed dry (news)"),
]


def _geocode(query: str) -> tuple[float, float] | None:
    params = {
        "q": query, "format": "json", "limit": "1",
        "viewbox": ",".join(str(v) for v in (VIEWBOX[0], VIEWBOX[3], VIEWBOX[2], VIEWBOX[1])),
        "bounded": "1",
        "countrycodes": "th",
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
