"""OneMap (Singapore) geocoder for the documented-hotspot register.

OneMap is the Singapore Land Authority's authoritative national map service;
its `common/elastic/search` endpoint returns surveyed lat/lon for an address
or place name, needs no auth token, and is commercial-safe (SLA open terms).

Used to put register coordinates on an authoritative basis instead of
hand-typed pins (limitations register #6b). Pure parsing is import-testable;
network calls are cached to disk so a re-run is offline and deterministic.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_ENDPOINT = "https://www.onemap.gov.sg/api/common/elastic/search"
# Singapore mainland + islands bounding box — reject anything outside it.
_SG_LON = (103.6, 104.1)
_SG_LAT = (1.15, 1.48)


@dataclass(frozen=True)
class GeocodeResult:
    query: str
    lon: float
    lat: float
    matched: str          # OneMap SEARCHVAL of the chosen result
    n_results: int        # how many candidates OneMap returned
    in_sg: bool           # lon/lat inside the Singapore bbox


def parse_onemap_response(query: str, payload: dict) -> GeocodeResult | None:
    """Pick the first result from a OneMap search payload (pure / testable).

    Returns None when OneMap found nothing. ``in_sg`` flags whether the chosen
    point falls inside the Singapore bounding box (a sanity guard against a
    stray match).
    """
    results = payload.get("results") or []
    if not results:
        return None
    top = results[0]
    lon = float(top["LONGITUDE"])
    lat = float(top["LATITUDE"])
    in_sg = (_SG_LON[0] <= lon <= _SG_LON[1]) and (_SG_LAT[0] <= lat <= _SG_LAT[1])
    return GeocodeResult(
        query=query,
        lon=lon,
        lat=lat,
        matched=top.get("SEARCHVAL", ""),
        n_results=len(results),
        in_sg=in_sg,
    )


def _http_fetch(query: str, *, max_retries: int = 5, base_delay: float = 1.5) -> dict:
    """Call OneMap, backing off on HTTP 429 (rate limit). Polite by default."""
    url = _ENDPOINT + "?" + urllib.parse.urlencode(
        {"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1})
    req = urllib.request.Request(url, headers={"User-Agent": "flood-atlas/1.0"})
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))  # 1.5, 3, 6, 12 s
                continue
            raise


def geocode(
    query: str,
    *,
    cache_dir: Path,
    fetcher=_http_fetch,
) -> GeocodeResult | None:
    """Geocode ``query`` via OneMap, caching the raw payload to ``cache_dir``.

    A cached payload is reused (offline, deterministic); ``fetcher`` is
    injectable so tests never touch the network.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(query.strip().lower().encode("utf-8")).hexdigest()[:16]
    cache_file = cache_dir / f"{key}.json"
    if cache_file.exists():
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
    else:
        payload = fetcher(query)
        cache_file.write_text(json.dumps(payload), encoding="utf-8")
    return parse_onemap_response(query, payload)
