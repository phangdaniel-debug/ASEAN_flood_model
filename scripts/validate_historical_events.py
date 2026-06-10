"""
Validate the multi-hazard flood pipeline against documented historical flood events.

Downloads observed flood polygons, rasterizes to the pipeline DEM grid, sweeps all
configured (hazard_type, RP) combinations, and reports CSI / H / FAR metrics with
WARN / FAIL gates.

Events configured:
    JKT2020  - Jakarta Jan 2020 (Sentinel-Asia EOS-ARIA flood proxy, Sentinel-1 SAR)
    MYS2021  - Malaysia Dec 2021 / Jan 2022 (UNOSAT FL20220112MYS, Sentinel-2,
               Pahang & Johor states, imagery date 10 Jan 2022)

Usage
-----
    python scripts/validate_historical_events.py                     # all events
    python scripts/validate_historical_events.py --event JKT2020     # single event
    python scripts/validate_historical_events.py --event MYS2021 \
        --out-dir outputs/kuala_lumpur_ssp585_2100

Exit codes
----------
    0 : all events PASS or WARN
    1 : at least one event FAIL
    2 : output directory or cached flood data not found
"""
from __future__ import annotations

import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
import click
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Event registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EventConfig:
    event_id: str          # short ID, e.g. "JKT2020"
    description: str       # human-readable, e.g. "Jakarta floods Jan 2020"
    city_slug: str         # e.g. "jakarta"
    # Observation source — exactly ONE of the following must be set:
    source_url: str | None      # direct ZIP download (vector polygons), no auth required
    raster_obs: str | None      # path (PROJECT_ROOT-relative) to a cached binary flood raster
    flood_attr: str | None   # shapefile attribute to filter on; None = use all polygons
    flood_value: str | None  # value to match exactly as stored in the DBF attribute table; None = use all polygons
    hazard_types: tuple[str, ...]
    rp_range: tuple[int, ...]
    default_out_dir: str   # relative to PROJECT_ROOT
    obs_note: str = ""     # short human-readable caveat about the obs source
    obs_band: int = 1            # for raster_obs: 1-indexed band carrying flood mask
    obs_mask_band: int | None = None   # optional 1-indexed band to EXCLUDE (e.g. permanent water)
    obs_is_local_zip: bool = False     # if True, treat source_url as a relative path under data/


# Jakarta Jan 2020 — Sentinel-Asia / EOS-ARIA Flood Proxy Map v1.5
# Source: https://sentinel-asia.org/EO/2020/article20200101ID.html
# All polygons represent Sentinel-1 detected water; no class filter needed.
_JKT2020_URL = (
    "https://sentinel-asia.org/EO/2020/article20200101ID/"
    "EOS_ARIA-SG_20200102_FPM_Indonesia_Floods_v1.5_SHP.zip"
)

# Malaysia Dec 2021 / Jan 2022 — UNOSAT FL20220112MYS (Sentinel-2, 10 Jan 2022)
# Covers Pahang & Johor states.  Published 14 Jan 2022 on UNOSAT CERN filesystem.
# Confirmed reachable: 5.2 MB ZIP, HTTP 200.
# Attribute schema (inspected from DBF): Water_Clas field, value "Flood Water".
# Source page: https://unosat.docs.cern.ch/unosat-maps/MY/FL20220112MYS/
_MYS2021_URL = (
    "https://unosat.docs.cern.ch/unosat-maps/MY/FL20220112MYS/"
    "FL20220112MYS_SHP.zip"
)


EVENTS: list[EventConfig] = [
    EventConfig(
        event_id="JKT2020",
        description="Jakarta floods Jan 2020",
        city_slug="jakarta",
        source_url=_JKT2020_URL,
        raster_obs=None,
        flood_attr=None,   # all polygons = detected water
        flood_value=None,
        hazard_types=("pluvial", "fluvial"),
        rp_range=(10, 25, 50, 100, 200),
        default_out_dir="outputs/jakarta_ssp585_2100",
        obs_note=(
            "Sentinel-Asia / EOS-ARIA Flood Proxy Map v1.5 (Sentinel-1 SAR). "
            "Captures peri-urban / open-water flood; misses urban floods inside "
            "central Jakarta SAR layover/shadow zones."
        ),
    ),
    EventConfig(
        event_id="THA2011",
        description=(
            "Thailand 2011 mega-flood (Aug 2011 - Jan 2012) — Chao Phraya basin, "
            "Cloud-to-Street Global Flood Database (Tellman et al. 2021 Nature) "
            "DFO event 3850 MODIS-derived inundation."
        ),
        city_slug="bangkok",
        source_url=None,
        raster_obs="data/bangkok/flood_obs/THA2011/DFO_3850_From_20110805_to_20120109.tif",
        obs_band=1,         # 'flooded' band
        obs_mask_band=5,    # 'jrc_perm_water' — exclude permanent water bodies
        flood_attr=None, flood_value=None,
        hazard_types=("fluvial", "coastal", "pluvial"),
        rp_range=(10, 25, 50, 100, 200),
        default_out_dir="outputs/bangkok_ssp585_2100",
        obs_note=(
            "MODIS 250 m flood-mapping from the GFD (CC-BY). Coarse for dense "
            "urban Bangkok and undercounts cloud-obscured / building-shadow "
            "flooding. Best used as a basin-scale envelope; DFO event 3850."
        ),
    ),
    EventConfig(
        event_id="PHL2009",
        description=(
            "Typhoon Ondoy / Ketsana, Metro Manila (Sep 26-30, 2009) — "
            "COSMO-SkyMed X-band SAR processed by ITHACA via UN-SPIDER."
        ),
        city_slug="manila",
        source_url=None,
        raster_obs=None,
        # Local shapefile path; we extend the validator to accept a local
        # shapefile via the same raster_obs/extracted-dir mechanism.
        flood_attr=None, flood_value=None,
        hazard_types=("fluvial", "pluvial", "coastal"),
        rp_range=(10, 25, 50, 100, 200),
        default_out_dir="outputs/manila_ssp585_2100",
        obs_note=(
            "COSMO-SkyMed X-band SAR (2009-09-30), ITHACA / UN-SPIDER, "
            "1:250 000 generalised polygons. Urban SAR-shadow blanks "
            "central built-up Marikina / Pasig (Abon et al. 2011 HESS)."
        ),
        obs_is_local_zip=True,  # signals: read shapefile from data/manila/flood_obs/PHL2009/
    ),
    EventConfig(
        event_id="MYS2021",
        description=(
            "KL floods Dec 2021 — local Copernicus GFM Sentinel-1 ensemble "
            "(replaces UNOSAT FL20220112MYS Pahang/Johor — geographic mismatch)"
        ),
        city_slug="kuala_lumpur",
        source_url=None,
        # Composite of 15 GFM ensemble Sentinel-1 tiles (16-22 Dec 2021) covering
        # the KL pipeline bbox; built by scripts/fetch_gfm_mys2021.py.
        raster_obs="data/kl/flood_obs/MYS2021/gfm_kl_composite_dec2021.tif",
        flood_attr=None,
        flood_value=None,
        hazard_types=("fluvial", "pluvial"),
        rp_range=(10, 25, 50, 100, 200),
        default_out_dir="outputs/kuala_lumpur_ssp585_2100",
        obs_note=(
            "Copernicus GFM Sentinel-1 ensemble (16-22 Dec 2021).  "
            "Urban SAR exclusion masks ~69% of the KL bbox (SAR double-bounce "
            "indistinguishable from open water in dense built-up areas).  "
            "Composite captures only ~0.14 km^2 of peri-urban flood — useful as "
            "a lower-bound spatial cross-check, not a representative obs set."
        ),
    ),
]

# ---------------------------------------------------------------------------
# Gate thresholds
# ---------------------------------------------------------------------------
CSI_PASS = 0.30
CSI_WARN = 0.15

# When the observation footprint is too small to give meaningful area-based
# verdicts (e.g. SAR-based urban-excluded observations) we fall back to a
# hit-rate-only check.  Obs areas below OBS_AREA_LIMITED_KM2 trigger the
# "LIMITED" verdict tier: PASS if H >= HIT_PASS_LIMITED, WARN otherwise.
OBS_AREA_LIMITED_KM2 = 5.0
HIT_PASS_LIMITED     = 0.30
HIT_WARN_LIMITED     = 0.15

_SEP  = "=" * 72
_DASH = "-" * 72

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(
    predicted: np.ndarray,
    observed: np.ndarray,
) -> dict[str, float | int]:
    """Compute flood validation contingency metrics.

    Parameters
    ----------
    predicted : bool ndarray — model-predicted flooded pixels (depth >= threshold)
    observed  : bool ndarray — observed flooded pixels (rasterized polygon)

    Both arrays must have the same shape (enforced).

    Returns
    -------
    dict with keys: tp, fp, fn, csi, h, far, bias

    Division-by-zero conventions (matching WMO verification literature):
      csi  = 0.0 when tp+fp+fn == 0  (empty grid)
      h    = 0.0 when tp+fn == 0     (no observed flood pixels)
      far  = 0.0 when tp+fp == 0     (no predicted flood pixels)
      bias = nan when tp+fn == 0     (undefined — cannot normalise against zero
                                      observed area; use np.isnan() to detect)
    """
    if predicted.shape != observed.shape:
        raise ValueError(
            f"predicted and observed must have the same shape; "
            f"got {predicted.shape} vs {observed.shape}"
        )
    pred = predicted.astype(bool)
    obs  = observed.astype(bool)

    tp = int(np.sum( pred &  obs))
    fp = int(np.sum( pred & ~obs))
    fn = int(np.sum(~pred &  obs))

    csi  = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
    h    = tp / (tp + fn)      if (tp + fn)      > 0 else 0.0
    far  = fp / (tp + fp)      if (tp + fp)      > 0 else 0.0
    bias = (tp + fp) / (tp + fn) if (tp + fn)    > 0 else float("nan")

    return {"tp": tp, "fp": fp, "fn": fn,
            "csi": csi, "h": h, "far": far, "bias": bias}


# ---------------------------------------------------------------------------
# Rasterization
# ---------------------------------------------------------------------------

def _load_obs_raster_to_grid(
    obs_path: Path,
    ref_path: Path,
    height: int,
    width: int,
    transform,
    crs_wkt: str,
    obs_band: int = 1,
    obs_mask_band: int | None = None,
) -> np.ndarray:
    """Reproject a binary flood-obs raster onto the pipeline DEM grid.

    Parameters
    ----------
    obs_band : 1-indexed band from the source raster carrying the flood mask
               (default 1).  For the Global Flood Database (Tellman 2021),
               band 1 = `flooded` (transient + permanent), band 5 =
               `jrc_perm_water` (permanent water to exclude).
    obs_mask_band : optional 1-indexed band whose nonzero values mark
                    permanent water to be EXCLUDED from the flood mask.
                    Use band 5 for GFD rasters.

    Any pixel value == 1 in the obs_band (after nearest-neighbour
    reprojection) becomes True.  NaN / nodata is treated as not-flooded.
    """
    import rasterio
    from rasterio.warp import reproject, Resampling

    with rasterio.open(obs_path) as src, rasterio.open(ref_path) as ref:
        src_arr = src.read(obs_band).astype(np.float32)
        # NaN in source → set to 0 (not flooded)
        if np.issubdtype(src_arr.dtype, np.floating):
            src_arr = np.where(np.isnan(src_arr), 0.0, src_arr)
        src_nodata = src.nodata
        if src_nodata is not None and not (isinstance(src_nodata, float) and np.isnan(src_nodata)):
            src_arr = np.where(src_arr == src_nodata, 0.0, src_arr)

        dst = np.zeros((height, width), dtype=np.float32)
        reproject(
            source=src_arr,
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=0.0,
            dst_transform=transform,
            dst_crs=ref.crs,
            dst_nodata=0.0,
            resampling=Resampling.nearest,
        )
        mask = dst > 0.5

        if obs_mask_band is not None:
            exc = src.read(obs_mask_band).astype(np.float32)
            if np.issubdtype(exc.dtype, np.floating):
                exc = np.where(np.isnan(exc), 0.0, exc)
            dst_exc = np.zeros((height, width), dtype=np.float32)
            reproject(
                source=exc, destination=dst_exc,
                src_transform=src.transform, src_crs=src.crs, src_nodata=0.0,
                dst_transform=transform, dst_crs=ref.crs, dst_nodata=0.0,
                resampling=Resampling.nearest,
            )
            mask = mask & (dst_exc <= 0.5)

    return mask


def rasterize_footprint(
    geometries: list,
    height: int,
    width: int,
    transform,
) -> np.ndarray:
    """Burn flood polygons into a boolean raster on the DEM grid.

    Parameters
    ----------
    geometries : list of shapely geometries (already in the target CRS)
    height, width : grid dimensions (pixels)
    transform : rasterio Affine transform for the grid

    Returns
    -------
    bool ndarray of shape (height, width); True = inside a flood polygon
    """
    from rasterio.features import rasterize as _rasterize
    from shapely.geometry import mapping

    if not geometries:
        return np.zeros((height, width), dtype=bool)

    shapes = [(mapping(g), 1) for g in geometries]
    arr = _rasterize(
        shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype="uint8",
        all_touched=False,
    )
    return arr.astype(bool)


# ---------------------------------------------------------------------------
# Depth raster utilities
# ---------------------------------------------------------------------------

def find_depth_raster(out_dir: Path, hazard_type: str, rp: int) -> Path | None:
    """Locate the depth TIF for a given hazard type and return period.

    Looks for: <out_dir>/<hazard_type>/rp_<rp>/<hazard_type>_depth_*.tif
    Returns None if not found.
    """
    rp_dir = out_dir / hazard_type / f"rp_{rp}"
    if not rp_dir.exists():
        return None
    matches = list(rp_dir.glob(f"{hazard_type}_depth_*.tif"))
    return matches[0] if matches else None


def load_depth_mask(tif_path: Path, threshold: float) -> np.ndarray:
    """Read a depth raster and return a boolean flooded mask.

    Pixels with depth >= threshold are True (flooded).
    NoData / masked pixels are treated as dry (False).
    """
    import rasterio

    with rasterio.open(tif_path) as ds:
        arr = ds.read(1, masked=True)

    # Fill masked/nodata pixels with 0 (dry); masked=True always returns MaskedArray
    return arr.filled(0.0) >= threshold


# ---------------------------------------------------------------------------
# Flood polygon download, extraction, loading
# ---------------------------------------------------------------------------

def download_zip(url: str, cache_dir: Path, no_download: bool = False) -> Path:
    """Download a ZIP to cache_dir, or return cached path if already present.

    Parameters
    ----------
    url         : direct HTTPS download URL
    cache_dir   : directory to store the ZIP (created if needed)
    no_download : if True, skip network fetch and fail if cache missing

    Returns
    -------
    Path to the downloaded (or cached) ZIP file.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    filename = url.rstrip("/").split("/")[-1]
    zip_path = cache_dir / filename

    if zip_path.exists():
        click.echo(f"  Using cached {zip_path.name}")
        return zip_path

    if no_download:
        raise FileNotFoundError(
            f"Cache miss and --no-download set: {zip_path}\n"
            f"Run without --no-download to fetch from {url}"
        )

    click.echo(f"  Downloading {url} ...")
    with urllib.request.urlopen(url, timeout=120) as response:
        zip_path.write_bytes(response.read())
    click.echo(f"  Saved -> {zip_path} ({zip_path.stat().st_size / 1024:.0f} KB)")
    return zip_path


def extract_zip(zip_path: Path) -> Path:
    """Extract a ZIP archive next to the ZIP file; return the extract directory.

    Extraction is skipped if the directory already exists.
    """
    extract_dir = zip_path.parent / zip_path.stem
    if not extract_dir.exists():
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
    return extract_dir


def find_shapefile(extract_dir: Path) -> Path:
    """Find the most relevant .shp file under extract_dir (recursive).

    Prefers files whose names contain flood-content keywords
    (FloodExtent, Flood_Extent, Flooded, FPM) over analysis-extent or
    cloud-obstruction shapefiles.  Falls back to the first match if no
    preferred file exists.

    Raises FileNotFoundError if no .shp file is found at all.
    """
    matches = list(extract_dir.rglob("*.shp"))
    if not matches:
        raise FileNotFoundError(f"No .shp file found under {extract_dir}")
    _PREFERRED = ("FloodExtent", "Flood_Extent", "Flooded", "FPM", "flood")
    for kw in _PREFERRED:
        for m in sorted(matches):
            if kw.lower() in m.name.lower():
                return m
    return sorted(matches)[0]


def load_flood_footprint(
    shp_path: Path,
    target_crs: str,
    flood_attr: str | None,
    flood_value: str | None,
) -> list:
    """Read flood polygons from a shapefile, reproject, and optionally filter by class.

    Parameters
    ----------
    shp_path    : path to the .shp file
    target_crs  : EPSG string or WKT for the output CRS (e.g. "EPSG:32748")
    flood_attr  : attribute name to filter on; None = include all features
    flood_value : attribute value to match exactly (DBF-stored value); None = include all

    Returns
    -------
    list of shapely geometries in target_crs
    """
    from pyogrio.raw import read as _read
    from pyproj import CRS, Transformer
    from shapely import from_wkb
    from shapely.ops import transform as shapely_transform

    # Returns (meta, fids_or_None, geometry_wkb_array, field_data_list)
    meta, _fids, geometry_wkb, field_data_list = _read(str(shp_path))

    src_crs = CRS.from_user_input(meta["crs"])
    tgt_crs = CRS.from_user_input(target_crs)
    transformer = Transformer.from_crs(src_crs, tgt_crs, always_xy=True)

    # Build field name → values mapping
    field_names = list(meta["fields"]) if meta["fields"] is not None else []
    field_data_list = field_data_list if field_data_list is not None else []
    fields_map = {name: arr for name, arr in zip(field_names, field_data_list)}

    geometries: list = []
    for i, geom_wkb_bytes in enumerate(geometry_wkb):
        if geom_wkb_bytes is None:
            continue
        # Optionally filter by flood class attribute (exact match, case-insensitive)
        if flood_attr is not None and flood_value is not None:
            col = fields_map.get(flood_attr)
            raw = (str(col[i]) if col is not None else "").strip()
            if raw.lower() != flood_value.lower():
                continue
        geom = from_wkb(geom_wkb_bytes)
        geom_proj = shapely_transform(transformer.transform, geom)
        geometries.append(geom_proj)

    return geometries


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def validate_event(
    event: EventConfig,
    out_dir: Path | None,
    depth_threshold: float,
    no_download: bool,
) -> dict:
    """Download, rasterize, and validate one historical event.

    Returns a dict with keys:
        verdict, best_hazard, best_rp, best_csi, best_h, best_far, best_bias,
        obs_area_km2, all_rows
    Exits with code 2 if out_dir does not exist or no depth rasters found.
    """
    import rasterio

    resolved_out = out_dir if out_dir is not None else PROJECT_ROOT / event.default_out_dir
    if not resolved_out.exists():
        click.echo(f"[error] Output directory not found: {resolved_out}\n"
                   f"        Run the pipeline for '{event.city_slug}' first.", err=True)
        sys.exit(2)

    if not event.source_url and not event.raster_obs and not event.obs_is_local_zip:
        click.echo(f"[error] No obs source configured for {event.event_id}.", err=True)
        sys.exit(2)

    cache_dir = PROJECT_ROOT / "data" / event.city_slug / "flood_obs" / event.event_id

    # ── Discover a reference depth raster for grid metadata ─────────────────
    ref_raster: Path | None = None
    for ht in event.hazard_types:
        for rp in event.rp_range:
            ref_raster = find_depth_raster(resolved_out, ht, rp)
            if ref_raster:
                break
        if ref_raster:
            break

    if ref_raster is None:
        click.echo(f"[error] No depth rasters found under {resolved_out} for "
                   f"hazard types {event.hazard_types}.", err=True)
        sys.exit(2)

    with rasterio.open(ref_raster) as ds:
        height    = ds.height
        width     = ds.width
        transform = ds.transform
        crs_wkt   = ds.crs.to_wkt()
        pixel_area_m2 = abs(ds.res[0] * ds.res[1])

    # ── Load observed footprint (raster OR vector polygons) ─────────────────
    if event.raster_obs:
        obs_path = PROJECT_ROOT / event.raster_obs
        if not obs_path.exists():
            click.echo(f"[error] Cached raster obs not found: {obs_path}", err=True)
            sys.exit(2)
        obs_mask = _load_obs_raster_to_grid(
            obs_path, ref_raster, height, width, transform, crs_wkt,
            obs_band=event.obs_band,
            obs_mask_band=event.obs_mask_band,
        )
    elif event.obs_is_local_zip:
        # Local shapefile already extracted under cache_dir (or as plain .shp)
        shps = list(cache_dir.rglob("*.shp"))
        if not shps:
            click.echo(f"[error] No .shp found under {cache_dir}", err=True)
            sys.exit(2)
        shp_path = shps[0]
        geoms = load_flood_footprint(shp_path, crs_wkt,
                                     event.flood_attr, event.flood_value)
        obs_mask = rasterize_footprint(geoms, height, width, transform)
    else:
        try:
            zip_path = download_zip(event.source_url, cache_dir, no_download)
        except FileNotFoundError as exc:
            click.echo(f"[error] {exc}", err=True)
            sys.exit(2)
        extract_dir = extract_zip(zip_path)
        shp_path = find_shapefile(extract_dir)

        geoms = load_flood_footprint(shp_path, crs_wkt,
                                     event.flood_attr, event.flood_value)
        if not geoms:
            click.echo(f"[warn] No matching polygons found in {shp_path.name} "
                       f"(flood_attr={event.flood_attr!r}, flood_value={event.flood_value!r}).")

        obs_mask = rasterize_footprint(geoms, height, width, transform)

    obs_area_km2 = float(obs_mask.sum()) * pixel_area_m2 / 1e6

    # ── Sweep all (hazard_type, rp) combos ──────────────────────────────────
    all_rows: list[dict] = []
    best: dict = {"csi": -1.0}

    for hazard_type in event.hazard_types:
        for rp in event.rp_range:
            depth_path = find_depth_raster(resolved_out, hazard_type, rp)
            if depth_path is None:
                all_rows.append({
                    "hazard": hazard_type, "rp": rp,
                    "csi": None, "h": None, "far": None, "bias": None,
                })
                continue
            pred_mask = load_depth_mask(depth_path, depth_threshold)
            m = compute_metrics(pred_mask, obs_mask)
            all_rows.append({"hazard": hazard_type, "rp": rp, **m})
            if m["csi"] > best.get("csi", -1.0):
                best = {"hazard": hazard_type, "rp": rp, **m}

    # ── Determine verdict ────────────────────────────────────────────────────
    best_csi = float(best.get("csi", 0.0) or 0.0)
    best_h   = float(best.get("h",   0.0) or 0.0)

    # Sparse-obs fallback: when the observation footprint is too small for
    # meaningful CSI / FAR (e.g. SAR-based obs in dense urban areas), pick
    # the best-H row instead and gate on hit-rate only.
    if obs_area_km2 < OBS_AREA_LIMITED_KM2:
        h_rows = [r for r in all_rows if r.get("h") is not None]
        if h_rows:
            best = max(h_rows, key=lambda r: r["h"])
            best_csi = float(best.get("csi", 0.0) or 0.0)
            best_h   = float(best.get("h",   0.0) or 0.0)
        if best_h >= HIT_PASS_LIMITED:
            verdict = "LIMITED-PASS"
        elif best_h >= HIT_WARN_LIMITED:
            verdict = "LIMITED-WARN"
        else:
            verdict = "LIMITED-FAIL"
    elif best_csi >= CSI_PASS:
        verdict = "PASS"
    elif best_csi >= CSI_WARN:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    return {
        "verdict":      verdict,
        "best_hazard":  best.get("hazard", ""),
        "best_rp":      best.get("rp", 0),
        "best_csi":     best_csi,
        "best_h":       best.get("h", 0.0),
        "best_far":     best.get("far", 0.0),
        "best_bias":    best.get("bias", float("nan")),
        "obs_area_km2": obs_area_km2,
        "all_rows":     all_rows,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _print_event_report(event: EventConfig, result: dict, depth_threshold: float = 0.10) -> None:
    """Print the per-event metrics table and verdict to stdout."""
    click.echo(_SEP)
    click.echo(f"Historical event validation: {event.event_id} - {event.description}")
    click.echo(f"  City       : {event.city_slug}")
    if event.source_url:
        src_str = event.source_url
    elif event.raster_obs:
        src_str = f"raster: {event.raster_obs}"
    else:
        src_str = f"local-shp: data/{event.city_slug}/flood_obs/{event.event_id}/"
    click.echo(f"  Source     : {src_str}")
    if event.obs_note:
        click.echo(f"  Obs note   : {event.obs_note}")
    click.echo(f"  Obs. area  : {result['obs_area_km2']:.1f} km2  "
               f"(flood polygons rasterized to 30 m grid)")
    click.echo(f"  Flood thr  : {depth_threshold:.2f} m")
    rp_label = ", ".join(
        f"{ht} RP{min(event.rp_range)}-RP{max(event.rp_range)}"
        for ht in event.hazard_types
    )
    click.echo(f"  RP range   : {rp_label}")
    click.echo(_SEP)

    click.echo(f"  {'Hazard':<10}{'RP':>6}  {'CSI':>6}  {'H':>6}  "
               f"{'FAR':>6}  {'Bias':>6}  Verdict")
    click.echo(_DASH)

    for row in result["all_rows"]:
        if row.get("csi") is None:
            click.echo(f"  {row['hazard']:<10}{row['rp']:>6}  {'N/A':>6}  "
                       f"{'N/A':>6}  {'N/A':>6}  {'N/A':>6}  SKIP")
            continue
        is_best = (row["hazard"] == result["best_hazard"]
                   and row["rp"] == result["best_rp"])
        # Label depends on which metric drove the verdict
        if is_best:
            marker = "  <- best H" if result["verdict"].startswith("LIMITED") else "  <- best CSI"
        else:
            marker = ""
        bias_val = row["bias"]
        bias_str = "  nan" if (isinstance(bias_val, float) and np.isnan(bias_val)) else f"{bias_val:>6.2f}"
        click.echo(
            f"  {row['hazard']:<10}{row['rp']:>6}  "
            f"{row['csi']:>6.2f}  {row['h']:>6.2f}  "
            f"{row['far']:>6.2f}  {bias_str}  INFO{marker}"
        )

    click.echo(_DASH)
    best_bias = result['best_bias']
    bias_str = "nan" if (isinstance(best_bias, float) and np.isnan(best_bias)) else f"{best_bias:.2f}"
    click.echo(
        f"Best match : {result['best_hazard']} RP{result['best_rp']}  "
        f"(CSI={result['best_csi']:.2f}, H={result['best_h']:.2f}, "
        f"FAR={result['best_far']:.2f}, Bias={bias_str})"
    )
    click.echo(f"  -> Verdict: {result['verdict']}")
    click.echo(_SEP)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command()
@click.option("--event", "event_id", default=None,
              help="Filter to one event ID (e.g. JKT2020). Default: run all.")
@click.option("--out-dir", "out_dir", type=click.Path(path_type=Path), default=None,
              help="Override output directory (only used when --event is also set).")
@click.option("--depth-threshold", "depth_threshold", type=float, default=0.10,
              show_default=True, help="Flooded depth threshold in metres.")
@click.option("--no-download", "no_download", is_flag=True, default=False,
              help="Skip network fetch; fail if cache missing.")
def cli(
    event_id: str | None,
    out_dir: Path | None,
    depth_threshold: float,
    no_download: bool,
) -> None:
    """Validate flood pipeline against historical observed flood extents."""

    # Select events to run
    if event_id is not None:
        matching = [e for e in EVENTS if e.event_id == event_id]
        if not matching:
            valid = ", ".join(e.event_id for e in EVENTS)
            click.echo(f"Unknown event '{event_id}'. Valid IDs: {valid}")
            sys.exit(1)
        events_to_run = matching
    else:
        events_to_run = EVENTS
        if out_dir is not None:
            click.echo("[warn] --out-dir is ignored when running all events "
                       "(each event uses its configured default_out_dir).")

    fails: list[str] = []

    for event in events_to_run:
        # Use per-event default unless overridden (only honoured for single-event runs)
        effective_out = out_dir if (event_id is not None and out_dir is not None) \
            else PROJECT_ROOT / event.default_out_dir

        click.echo(f"\nRunning: {event.event_id} - {event.description}")
        result = validate_event(event, effective_out, depth_threshold, no_download)
        _print_event_report(event, result, depth_threshold)

        # Both regular FAIL and LIMITED-FAIL count against exit code.  Regular
        # WARN, LIMITED-PASS, and LIMITED-WARN do not.
        if result["verdict"] in {"FAIL", "LIMITED-FAIL"}:
            fails.append(event.event_id)

    click.echo("")
    if fails:
        click.echo(f"OVERALL: FAIL - {len(fails)} event(s) below CSI/H thresholds: "
                   f"{', '.join(fails)}")
        sys.exit(1)
    else:
        click.echo("OVERALL: PASS (all events PASS / WARN / LIMITED-PASS / LIMITED-WARN)")
        sys.exit(0)


if __name__ == "__main__":
    cli()
