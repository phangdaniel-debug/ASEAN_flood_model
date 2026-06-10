from __future__ import annotations

import json
from pathlib import Path

import click
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Offline cache (limitation: pipeline re-fetched the remote AR6 zarr every run
# and broke twice on transient outages). The extracted values are tiny (a few
# floats per site/scenario/year), so we cache the EXTRACTED records keyed by the
# request parameters. A committed cache makes re-runs offline-repeatable; the
# remote zarr is opened ONLY on a cache miss. `zarr` is imported lazily inside
# the fetch path so a fully-cached run needs neither network nor the zarr import.
# ---------------------------------------------------------------------------
DEFAULT_CACHE_PATH = Path("data/_ar6_lsl_cache.json")
_CACHE_FIELDS = ("water_level_m", "source_note", "source_url",
                 "location_id", "location_lat", "location_lon")


def _cache_key(workflow_id, scenario, lat, lon, percentile, baseline_year, horizon) -> str:
    return (f"{workflow_id}|{scenario}|{float(lat):.4f}|{float(lon):.4f}"
            f"|p{percentile:g}|b{int(baseline_year)}|y{int(horizon)}")


def load_cache(path: Path) -> dict:
    if Path(path).exists():
        return json.loads(Path(path).read_text())
    return {}


def save_cache(cache: dict, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(cache, indent=1, sort_keys=True))


EXPERIMENT_MAP = {
    "SSP1-1.9": "ssp119",
    "SSP1-2.6": "ssp126",
    "SSP2-4.5": "ssp245",
    "SSP3-7.0": "ssp370",
    "SSP5-8.5": "ssp585",
}

BASE_URL = (
    "https://storage.googleapis.com/ar6-lsl-simulations-public-standard/"
    "tide-gauges/full_sample_workflows/{workflow_id}/{experiment_id}/total-workflow.zarr"
)


def _open_projection_group(zarr_url: str):
    import zarr  # lazy: a fully-cached run needs neither network nor zarr
    return zarr.open_group(zarr_url, mode="r")


_GROUP_MEMO: dict = {}


def _group_for(zarr_url: str):
    if zarr_url not in _GROUP_MEMO:
        _GROUP_MEMO[zarr_url] = _open_projection_group(zarr_url)
    return _GROUP_MEMO[zarr_url]


def resolve_sea_level_entry(
    cache: dict, *, workflow_id: str, scenario: str, lat: float, lon: float,
    percentile: float, baseline_year: int, horizon: int,
    offline: bool = False, refresh_cache: bool = False,
) -> dict:
    """Cache-aware AR6 sea-level delta for one (scenario, horizon).

    Mutates ``cache`` on a miss; the remote zarr is opened ONLY on a miss (memoised
    per URL within the process). ``offline=True`` raises on a miss. The caller owns
    loading/saving ``cache`` (so a batch writes once). Returns the entry dict
    (``water_level_m`` + provenance). This is the single offline-repeatable entry
    point used by BOTH this CLI and build_hazard_levels (limitation #18-sibling:
    AR6 re-fetch broke runs twice).
    """
    if scenario not in EXPERIMENT_MAP:
        raise ValueError(
            f"Unsupported scenario {scenario!r}. Supported: {sorted(EXPERIMENT_MAP)}"
        )
    key = _cache_key(workflow_id, scenario, lat, lon, percentile, baseline_year, horizon)
    if not refresh_cache and key in cache:
        return dict(cache[key])
    if offline:
        raise click.ClickException(
            f"--offline: no cached AR6 value for {key!r}. Run once online "
            "(or with --refresh-cache) to populate the cache."
        )
    zarr_url = BASE_URL.format(workflow_id=workflow_id, experiment_id=EXPERIMENT_MAP[scenario])
    group = _group_for(zarr_url)
    loc_idx = _pick_location(group, lat=lat, lon=lon)
    units = _get_sea_level_units(group)
    raw = _extract_level_for_year(
        group=group, year=horizon, percentile=percentile,
        baseline_year=baseline_year, location_idx=loc_idx,
    )
    entry = {
        "water_level_m": float(_to_meters(raw, units)),
        "source_note": ("IPCC AR6 Zarr tide-gauge workflow; nearest location; "
                        f"p{percentile:g}; baseline={baseline_year}"),
        "source_url": zarr_url,
        "location_id": int(np.asarray(group["locations"][loc_idx]).item()),
        "location_lat": float(np.asarray(group["lat"][loc_idx]).item()),
        "location_lon": float(np.asarray(group["lon"][loc_idx]).item()),
    }
    cache[key] = entry
    return dict(entry)


def _get_sea_level_units(group) -> str:
    """Return the declared units of sea_level_change from the Zarr attributes."""
    try:
        return str(group["sea_level_change"].attrs.get("units", "")).lower()
    except Exception:
        return ""


def _to_meters(value: float, units: str) -> float:
    """Convert a sea-level value to metres based on the declared units attribute."""
    if units in ("m", "meters", "metres"):
        return value
    if units in ("mm", "millimeters", "millimetres"):
        return value / 1000.0
    raise ValueError(
        f"Unrecognised sea_level_change units {units!r} in AR6 Zarr dataset. "
        "Expected 'mm' or 'm'. Inspect the dataset and update this conversion."
    )


def _pick_location(group, lat: float, lon: float) -> int:
    # Great-circle distance is preferable, but euclidean in lat/lon is adequate
    # for nearest-neighbor index selection at this stage.
    lat_arr = np.asarray(group["lat"][:], dtype=np.float64)
    lon_arr = np.asarray(group["lon"][:], dtype=np.float64)
    dlat = lat_arr - lat
    dlon = lon_arr - lon
    dist2 = dlat**2 + dlon**2
    idx = int(np.argmin(dist2))
    return idx


def _extract_level_for_year(
    group,
    year: int,
    percentile: float,
    baseline_year: int,
    location_idx: int,
) -> float:
    years = np.asarray(group["years"][:], dtype=int)
    if year not in years:
        raise ValueError(f"Year {year} not available. Dataset years: {years.tolist()}")
    if baseline_year not in years:
        raise ValueError(
            f"Baseline year {baseline_year} not available. Dataset years: {years.tolist()}"
        )

    sea_level = group["sea_level_change"]
    year_idx = int(np.where(years == year)[0][0])
    base_idx = int(np.where(years == baseline_year)[0][0])

    slc_year = np.asarray(sea_level[:, year_idx, location_idx], dtype=np.float64)
    slc_base = np.asarray(sea_level[:, base_idx, location_idx], dtype=np.float64)
    q = percentile / 100.0
    # Compute the delta per Monte Carlo sample before taking the quantile so
    # that sample correlation between years is preserved. Taking
    # quantile(year) - quantile(base) independently overestimates spread at
    # the tails (p17/p83 etc.).
    return float(np.quantile(slc_year - slc_base, q))


@click.command()
@click.option("--lat", type=float, required=True, help="Site latitude")
@click.option("--lon", type=float, required=True, help="Site longitude")
@click.option(
    "--scenario",
    "scenarios",
    multiple=True,
    required=True,
    help="Repeatable scenario name, e.g. SSP5-8.5",
)
@click.option(
    "--horizon",
    "horizons",
    type=int,
    multiple=True,
    required=True,
    help="Repeatable target year, e.g. 2050 --horizon 2100",
)
@click.option(
    "--percentile",
    type=float,
    default=50.0,
    show_default=True,
    help="Projection percentile over Monte Carlo samples (0-100).",
)
@click.option(
    "--baseline-year",
    type=int,
    default=2020,
    show_default=True,
    help="Relative baseline year used to compute delta water level.",
)
@click.option(
    "--workflow-id",
    type=str,
    default="wf_1e",
    show_default=True,
    help="AR6 workflow id exposed by Rutgers public bucket.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    required=True,
    help="Output scenario CSV for flood model.",
)
@click.option("--cache-path", "cache_path", type=click.Path(path_type=Path),
              default=DEFAULT_CACHE_PATH, show_default=True,
              help="On-disk cache of extracted AR6 sea-level deltas (offline-repeatability).")
@click.option("--offline", is_flag=True, default=False,
              help="Use ONLY the cache; error on any miss (no network/zarr). For repeatable re-runs.")
@click.option("--refresh-cache", is_flag=True, default=False,
              help="Ignore cached values and re-fetch from the remote zarr, updating the cache.")
def cli(
    lat: float,
    lon: float,
    scenarios: tuple[str, ...],
    horizons: tuple[int, ...],
    percentile: float,
    baseline_year: int,
    workflow_id: str,
    output_path: Path,
    cache_path: Path,
    offline: bool,
    refresh_cache: bool,
) -> None:
    if percentile < 0 or percentile > 100:
        raise ValueError("percentile must be between 0 and 100")

    cache = load_cache(cache_path)
    n_before = len(cache)
    records: list[dict] = []
    for scenario in scenarios:
        for horizon in sorted(set(horizons)):
            entry = resolve_sea_level_entry(
                cache, workflow_id=workflow_id, scenario=scenario, lat=lat, lon=lon,
                percentile=percentile, baseline_year=baseline_year, horizon=horizon,
                offline=offline, refresh_cache=refresh_cache,
            )
            rec = dict(entry)
            rec["scenario"] = scenario
            rec["horizon"] = int(horizon)
            records.append(rec)

    n_fetched = len(cache) - n_before
    if n_fetched or refresh_cache:
        save_cache(cache, cache_path)
    click.echo(f"AR6 sea-level: {len(records) - n_fetched} cache hit(s), {n_fetched} fetched "
               f"({'cache updated' if (n_fetched or refresh_cache) else 'cache unchanged'}: {cache_path})")

    _cols = ["scenario", "horizon", "water_level_m", "source_note",
             "source_url", "location_id", "location_lat", "location_lon"]
    out_df = (pd.DataFrame(records)[_cols]
              .sort_values(["scenario", "horizon"]).reset_index(drop=True))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False)
    click.echo(f"Wrote {len(out_df)} rows to {output_path}")


if __name__ == "__main__":
    cli()
