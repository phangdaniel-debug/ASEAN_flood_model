import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.city_manifest import load_hotspots_from_manifest


def test_adapter_maps_manifest_to_hotspots(tmp_path):
    mdir = tmp_path / "kuala_lumpur" / "manifest"
    mdir.mkdir(parents=True)
    pd.DataFrame([
        {"name": "Taman Sri Muda", "lon": 101.5345, "lat": 3.0325,
         "kind": "positive", "confidence": "high", "source": "Dec 2021"},
        {"name": "Bukit Gasing", "lon": 101.6594, "lat": 3.0915,
         "kind": "dry", "confidence": "high", "source": "control"},
    ]).to_csv(mdir / "hotspots.csv", index=False)

    hs = load_hotspots_from_manifest("kuala_lumpur", data_root=tmp_path)
    by_cls = {h.cls for h in hs}
    assert by_cls == {"flood", "dry"}
    sri_muda = next(h for h in hs if h.label == "Taman Sri Muda")
    assert sri_muda.cls == "flood"
    assert sri_muda.lon == 101.5345 and sri_muda.lat == 3.0325
    assert sri_muda.documented_depth_m is None
    assert sri_muda.georef_confidence == "high"


def test_adapter_skips_failed_geocode_rows(tmp_path):
    mdir = tmp_path / "kuala_lumpur" / "manifest"
    mdir.mkdir(parents=True)
    pd.DataFrame([
        {"name": "good", "lon": 101.7, "lat": 3.1, "kind": "positive",
         "confidence": "high", "source": "x"},
        {"name": "failed", "lon": "", "lat": "", "kind": "positive",
         "confidence": "failed", "source": "x"},
    ]).to_csv(mdir / "hotspots.csv", index=False)
    hs = load_hotspots_from_manifest("kuala_lumpur", data_root=tmp_path)
    assert [h.label for h in hs] == ["good"]
