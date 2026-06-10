"""City-manifest contract for the multi-hazard flood pipeline.

A city is "complete and validatable" only when, in addition to its CityConfig
(scripts/cities.py), it carries four manifest CSVs under data/<slug>/manifest/:

    forcing_anchors.csv  hazard,duration_h,anchor_rp,anchor_value,unit,source,citation
    observed_events.csv  event_id,hazard,event_date,est_rp_low,est_rp_high,extent_path,source
    hotspots.csv         name,lon,lat,kind,confidence,source
    gates.csv            hazard,metric,threshold,direction,citation

forcing_anchors.csv and gates.csv MUST contain at least one data row; the
observed_events and hotspots manifests may be populated incrementally (header
only is allowed) so a city can be staged before its full register exists.

This module is intentionally pure (no I/O beyond reading the CSVs) so it is
unit-testable against a tmp_path fixture.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

MANIFEST_FILENAMES: dict[str, str] = {
    "forcing_anchors": "forcing_anchors.csv",
    "observed_events": "observed_events.csv",
    "hotspots": "hotspots.csv",
    "gates": "gates.csv",
}

REQUIRED_NONEMPTY: set[str] = {"forcing_anchors", "gates"}

EXPECTED_COLUMNS: dict[str, set[str]] = {
    "forcing_anchors": {"hazard", "duration_h", "anchor_rp", "anchor_value",
                        "unit", "source", "citation"},
    "observed_events": {"event_id", "hazard", "event_date", "est_rp_low",
                        "est_rp_high", "extent_path", "source"},
    "hotspots": {"name", "lon", "lat", "kind", "confidence", "source"},
    "gates": {"hazard", "metric", "threshold", "direction", "citation"},
}


def manifest_dir(slug: str, data_root: Path = Path("data")) -> Path:
    return Path(data_root) / slug / "manifest"


def load_anchors(slug: str, data_root: Path = Path("data")) -> pd.DataFrame:
    path = manifest_dir(slug, data_root) / MANIFEST_FILENAMES["forcing_anchors"]
    return pd.read_csv(path)


def validate_manifest(slug: str, data_root: Path = Path("data")) -> list[str]:
    """Return a list of human-readable problems; an empty list means valid."""
    problems: list[str] = []
    mdir = manifest_dir(slug, data_root)
    for key, fname in MANIFEST_FILENAMES.items():
        fpath = mdir / fname
        if not fpath.exists():
            problems.append(f"[{slug}] missing manifest file: {fname}")
            continue
        try:
            df = pd.read_csv(fpath)
        except Exception as exc:  # malformed CSV
            problems.append(f"[{slug}] {fname}: unreadable ({exc})")
            continue
        missing_cols = EXPECTED_COLUMNS[key] - set(df.columns)
        if missing_cols:
            problems.append(
                f"[{slug}] {fname}: missing column(s) "
                f"{sorted(missing_cols)}"
            )
        if key in REQUIRED_NONEMPTY and len(df) == 0:
            problems.append(f"[{slug}] {fname}: required manifest is empty")
    return problems


def load_hotspots_from_manifest(slug: str, data_root: Path = Path("data")):
    """Adapt the four-manifest hotspots.csv to hotspot_scoring.Hotspot objects.

    Maps: name→label, kind(positive→"flood"/dry→"dry"), confidence→georef_confidence.
    The manifest carries no documented depth or anchor RP, so those default to
    None / 0. Rows with a blank lon/lat (geocode failures, confidence=="failed")
    are skipped — they must not enter the hit-rate / CRR.

    Only ``kind`` in {"positive","dry"} is scored. Any other kind (e.g.
    "dry_diagnostic" — the Plan-9 systematic hard negatives, which are a documented
    DIAGNOSTIC contaminated by KL's pervasive valley flood-proneness, NOT the
    primary gate) is skipped from the scored register. Load those separately.
    """
    import pandas as pd
    from scripts.hotspot_scoring import Hotspot

    SCORED_KINDS = {"positive", "dry"}
    path = manifest_dir(slug, data_root) / MANIFEST_FILENAMES["hotspots"]
    df = pd.read_csv(path)
    out = []
    for _, r in df.iterrows():
        if pd.isna(r["lon"]) or pd.isna(r["lat"]) or str(r["lon"]).strip() == "":
            continue
        kind = str(r["kind"]).strip()
        if kind not in SCORED_KINDS:
            continue
        cls = "flood" if kind == "positive" else "dry"
        out.append(Hotspot(
            label=str(r["name"]).strip(),
            lon=float(r["lon"]), lat=float(r["lat"]),
            cls=cls, documented_depth_m=None, anchor_rp=0,
            source=str(r["source"]).strip(),
            georef_confidence=str(r["confidence"]).strip(),
        ))
    return out
