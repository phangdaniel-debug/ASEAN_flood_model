import json

import pytest

from scripts.geocode_onemap import GeocodeResult, geocode, parse_onemap_response

_PAYLOAD = {
    "found": 2,
    "results": [
        {"SEARCHVAL": "ORCHARD ROAD", "LATITUDE": "1.3016", "LONGITUDE": "103.8382"},
        {"SEARCHVAL": "ORCHARD ROAD (other)", "LATITUDE": "1.3041", "LONGITUDE": "103.8322"},
    ],
}


def test_parse_picks_first_result_and_flags_in_sg():
    r = parse_onemap_response("Orchard Road", _PAYLOAD)
    assert r is not None
    assert r.matched == "ORCHARD ROAD"
    assert r.lon == pytest.approx(103.8382)
    assert r.lat == pytest.approx(1.3016)
    assert r.n_results == 2
    assert r.in_sg is True


def test_parse_returns_none_when_no_results():
    assert parse_onemap_response("nowhere", {"found": 0, "results": []}) is None


def test_parse_flags_out_of_sg_point():
    payload = {"results": [{"SEARCHVAL": "X", "LATITUDE": "40.0", "LONGITUDE": "-74.0"}]}
    r = parse_onemap_response("New York", payload)
    assert r.in_sg is False


def test_geocode_caches_and_uses_injected_fetcher(tmp_path):
    calls = []

    def fake_fetch(q):
        calls.append(q)
        return _PAYLOAD

    cache = tmp_path / "geocode"
    r1 = geocode("Orchard Road", cache_dir=cache, fetcher=fake_fetch)
    r2 = geocode("Orchard Road", cache_dir=cache, fetcher=fake_fetch)  # cache hit
    assert isinstance(r1, GeocodeResult) and r1 == r2
    assert calls == ["Orchard Road"], "second call must hit the cache, not the fetcher"
    # payload persisted to disk
    assert len(list(cache.glob("*.json"))) == 1


def test_geocode_never_calls_network_when_cache_present(tmp_path):
    cache = tmp_path / "geocode"
    geocode("Orchard Road", cache_dir=cache, fetcher=lambda q: _PAYLOAD)

    def boom(q):
        raise AssertionError("network must not be called on a cache hit")

    r = geocode("Orchard Road", cache_dir=cache, fetcher=boom)
    assert r.matched == "ORCHARD ROAD"
