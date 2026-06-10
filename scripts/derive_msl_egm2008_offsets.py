"""
Derive CNES-CLS-2022 hybrid MDT offsets for all active UHSLC gauges and
patch ``data/<city>/hazard_baseline_template.csv`` and ``scripts/cities.py``.

The MDT (Mean Dynamic Topography) is the height of local mean sea level
above the EGM2008 geoid, which is the DEM datum. Gauge sea levels are
reported relative to local MSL; we add the MDT offset to express them in
EGM2008 so they are directly comparable to the GLO-30 DEM.

Idempotent: if a prior offset has been applied (detected by regex against
``msl_to_egm2008_offset=+X.Xm`` in source_note / datum_note), only the
delta ``new_offset - prior_offset`` is applied.

Usage
-----
    python scripts/derive_msl_egm2008_offsets.py            # dry-run
    python scripts/derive_msl_egm2008_offsets.py --write    # apply patches
    python scripts/derive_msl_egm2008_offsets.py --write --no-write-cities

CMEMS credentials (required for --write and for the MDT fetch)
--------------------------------------------------------------
    pip install copernicusmarine
    copernicusmarine login   # saves credentials to ~/.copernicusmarine/...
    -- or, on systems where the entry-point exe is not on PATH --
    python -c "from copernicusmarine import login; login()"
"""
from __future__ import annotations

import re
import sys
from datetime import date as _date
from pathlib import Path
from typing import TYPE_CHECKING

import click
import pandas as pd

if TYPE_CHECKING:
    import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CITIES_PY = PROJECT_ROOT / "scripts" / "cities.py"
DATA_DIR = PROJECT_ROOT / "data"

# CMEMS hybrid CNES-CLS-2022 MDT product (1/8 deg global, 1993-2012 mean).
# Product page: https://data.marine.copernicus.eu/product/SEALEVEL_GLO_PHY_MDT_008_063
# Dataset ID was renamed 2024-2025 (cmems_..._P20Y-T -> cnes_..._P20Y) and the
# underlying solution upgraded from CNES-CLS18 to the hybrid CNES-CLS-2022 + CMEMS2020.
CMEMS_DATASET_ID = "cnes_obs-sl_glo_phy-mdt_my_0.125deg_P20Y"
CMEMS_MDT_VAR = "mdt"

# Bounding box covering all active gauges (SG, KL, BKK, JKT, PH, VN).
# Manila Bay (120.97 E) and Vung Tau (107.07 E) extended 2026-05-15.
_BBOX = dict(
    minimum_latitude=-10.0,
    maximum_latitude=20.0,
    minimum_longitude=95.0,
    maximum_longitude=125.0,
)

# Idempotency tag written into datum_note
_TAG = "mdt_cnes_cls22"

# Actual UHSLC gauge coordinates (from https://uhslc.soest.hawaii.edu/data/).
# The CityConfig.era5_lat/lon is the *city centroid* used for precipitation
# fetch; sampling MDT there hits land cells (NaN). MDT must be sampled at
# the open-ocean tide-gauge location.
UHSLC_GAUGE_COORDS: dict[int, tuple[float, float]] = {
    699: (1.2650, 103.8500),   # Singapore - Tanjong Pagar
    140: (3.0000, 101.3667),   # Kelang / Port Klang, Malaysia
    328: (11.7950,  99.8167),  # Ko Lak, Thailand (Gulf of Thailand)
    161: (-6.1167, 106.8500),  # Tanjung Priok, Jakarta
    304: (14.5833, 120.9667),  # Manila (Fort Santiago) - Manila Bay
    257: (10.3400, 107.0700),  # Vung Tau, Vietnam
}

_SEP = "=" * 70
_DASH = "-" * 70


# ---------------------------------------------------------------------------
# CSV patch helpers
# ---------------------------------------------------------------------------

def _append_note(existing: str, suffix: str) -> str:
    """Append suffix to datum_note, handling empty/NaN existing values."""
    s = str(existing).strip()
    if not s or s == "nan":
        return suffix
    return f"{s} | {suffix}"


_PRIOR_OFFSET_RE = re.compile(
    r"msl_to_egm2008_offset\s*=\s*([+-]?\d+(?:\.\d+)?)\s*m"
)


def _extract_prior_offset(text: str) -> float:
    """Extract any previously-applied msl_to_egm2008_offset from a note.

    Returns 0.0 if none is found.
    """
    if not text or text == "nan":
        return 0.0
    m = _PRIOR_OFFSET_RE.search(text)
    if not m:
        return 0.0
    try:
        return float(m.group(1))
    except ValueError:
        return 0.0


def patch_coastal_rows(
    df: pd.DataFrame,
    offset: float,
    date_str: str,
) -> tuple[pd.DataFrame, int, float]:
    """
    Replace any previously-applied MSL-to-EGM2008 offset with the new MDT
    offset on coastal rows.

    The net adjustment to ``baseline_water_level_m`` is ``(offset - prior)``
    so the operation is idempotent regardless of the prior state. A prior
    offset is detected by regex against ``source_note`` (or ``datum_note``)
    for the literal pattern ``msl_to_egm2008_offset=+X.Xm``.

    Returns
    -------
    (patched_df, n_changed, prior_offset)
    """
    df = df.copy()
    already_tagged = df["datum_note"].fillna("").astype(str).str.contains(
        _TAG, na=False
    )
    mask = (df["hazard_type"].str.lower() == "coastal") & (~already_tagged)
    n_patched = int(mask.sum())
    if n_patched == 0:
        return df, 0, 0.0

    # Detect prior offset from the first matching coastal row.
    sample = df.loc[mask].iloc[0]
    src_note = str(sample.get("source_note", "") or "")
    dn_note = str(sample.get("datum_note", "") or "")
    prior = _extract_prior_offset(src_note) or _extract_prior_offset(dn_note)

    net_delta = offset - prior
    df.loc[mask, "baseline_water_level_m"] = (
        pd.to_numeric(df.loc[mask, "baseline_water_level_m"], errors="raise")
        + net_delta
    ).round(4)
    if abs(prior) > 1e-6:
        suffix = (
            f"{_TAG}={offset:+.4f}m applied {date_str} "
            f"(net delta {net_delta:+.4f}m; replaces prior {prior:+.4f}m)"
        )
    else:
        suffix = f"{_TAG}={offset:+.4f}m applied {date_str}"
    df.loc[mask, "datum_note"] = [
        _append_note(v, suffix)
        for v in df.loc[mask, "datum_note"].fillna("").astype(str)
    ]
    return df, n_patched, prior


# ---------------------------------------------------------------------------
# cities.py patch helper
# ---------------------------------------------------------------------------

def patch_cities_file(path: Path, slug: str, offset: float) -> bool:
    """
    Replace msl_to_egm2008_offset value for the named slug in cities.py.

    Finds the CityConfig block containing ``slug="<slug>"`` using a DOTALL
    regex and replaces the ``msl_to_egm2008_offset=<old>`` line within that
    block.  Returns True if the file was changed.
    """
    text = path.read_text(encoding="utf-8")
    new_value_str = f"{offset:.4f}"

    pattern = re.compile(
        r'(slug\s*=\s*"' + re.escape(slug) + r'".*?'
        r'msl_to_egm2008_offset\s*=\s*)([\d.+-]+)',
        re.DOTALL,
    )

    def _replacer(m: re.Match) -> str:
        current = m.group(2).strip()
        try:
            if round(float(current), 6) == round(offset, 6):
                return m.group(0)  # already correct — no change
        except ValueError:
            pass
        return m.group(1) + new_value_str

    new_text = pattern.sub(_replacer, text)
    if new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# MDT fetch + interpolation
# ---------------------------------------------------------------------------

def interpolate_mdt(ds: "xr.Dataset", lat: float, lon: float) -> float:
    """Sample MDT at (lat, lon).

    The MDT product is an ocean-only field (NaN on land). We use linear
    bilinear interpolation when the target cell is in open water; if the
    direct interpolation returns NaN (gauge near a coastal-masked pixel),
    we fall back to nearest-neighbour using only finite grid cells within
    a 0.5-degree radius (~55 km).

    Squeezes the vestigial 1-element time dimension before converting.
    """
    import numpy as np

    direct = ds[CMEMS_MDT_VAR].interp(
        latitude=lat, longitude=lon, method="linear"
    ).squeeze()
    val = float(direct.values)
    if np.isfinite(val):
        return val

    # Fallback: nearest finite ocean cell. Operate on full 2D arrays
    # to avoid issues with descending-latitude `slice()` returning empty.
    da = ds[CMEMS_MDT_VAR].squeeze()
    arr = da.values
    if arr.ndim != 2:
        return float("nan")
    lats = da["latitude"].values
    lons = da["longitude"].values
    finite = np.isfinite(arr)
    if not finite.any():
        return float("nan")
    lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")
    dist2 = (lat_grid - lat) ** 2 + (lon_grid - lon) ** 2
    dist2 = np.where(finite, dist2, np.inf)
    idx = np.unravel_index(int(np.argmin(dist2)), dist2.shape)
    # Sanity bound: don't snap to cells more than ~1 degree (~110 km) away
    if np.sqrt(dist2[idx]) > 1.0:
        return float("nan")
    return float(arr[idx])


def fetch_mdt_grid() -> "xr.Dataset":
    """Download a regional MDT subset from CMEMS (requires free registration)."""
    try:
        import copernicusmarine
    except ImportError as exc:
        raise ImportError(
            "copernicusmarine package not installed. "
            "Run: pip install copernicusmarine"
        ) from exc
    return copernicusmarine.open_dataset(
        dataset_id=CMEMS_DATASET_ID,
        variables=[CMEMS_MDT_VAR],
        **_BBOX,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--write", is_flag=True, default=False,
    help="Apply patches to CSVs and cities.py.",
)
@click.option(
    "--no-write-cities", "no_write_cities", is_flag=True, default=False,
    help="Skip cities.py patch when --write is used.",
)
@click.option(
    "--date", "date_override", default=None, metavar="YYYY-MM-DD",
    help="Override today's date in datum_note (default: today).",
)
def cli(write: bool, no_write_cities: bool, date_override: str | None) -> None:
    """Derive CNES-CLS-2022 hybrid MDT offsets for all active UHSLC gauges.

    \b
    Dry-run (default): fetches MDT and prints a table of derived offsets.
    --write: additionally patches data/<city>/hazard_baseline_template.csv
             and scripts/cities.py.
    """
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from cities import CITIES  # noqa: PLC0415

    date_str = date_override or str(_date.today())

    # ------------------------------------------------------------------
    # 1. Fetch MDT grid
    # ------------------------------------------------------------------
    click.echo("Fetching CNES-CLS-2022 hybrid MDT grid from CMEMS ...")
    try:
        ds = fetch_mdt_grid()
    except ImportError as exc:
        click.echo(f"ERROR: {exc}", err=True)
        raise SystemExit(1)
    except Exception as exc:
        click.echo(f"ERROR fetching MDT: {exc}", err=True)
        click.echo(
            "Ensure credentials are configured:\n"
            "  copernicusmarine configure\n"
            "  -- or set CMEMS_USERNAME / CMEMS_PASSWORD env vars",
            err=True,
        )
        raise SystemExit(1)

    # ------------------------------------------------------------------
    # 2. Derive offset per unique UHSLC gauge (sample at actual gauge coords)
    # ------------------------------------------------------------------
    gauge_offsets: dict[int, float] = {}
    for cfg in CITIES.values():
        if cfg.uhslc_id is None:
            continue
        if cfg.uhslc_id in gauge_offsets:
            continue
        if cfg.uhslc_id not in UHSLC_GAUGE_COORDS:
            click.echo(
                f"WARN: UHSLC {cfg.uhslc_id} not in UHSLC_GAUGE_COORDS lookup; "
                "skipping (falling back to era5 centroid)",
                err=True,
            )
            gauge_offsets[cfg.uhslc_id] = interpolate_mdt(
                ds, lat=cfg.era5_lat, lon=cfg.era5_lon
            )
        else:
            glat, glon = UHSLC_GAUGE_COORDS[cfg.uhslc_id]
            gauge_offsets[cfg.uhslc_id] = interpolate_mdt(ds, lat=glat, lon=glon)

    # ------------------------------------------------------------------
    # 3. Print summary table
    # ------------------------------------------------------------------
    mode_label = "WRITE" if write else "DRY-RUN (use --write to apply)"
    click.echo(_SEP)
    click.echo("CNES-CLS-2022 MDT offsets for active UHSLC gauges")
    click.echo(f"  Mode : {mode_label}")
    click.echo(f"  Date : {date_str}")
    click.echo(_SEP)
    click.echo(
        f"  {'City slug':<22} {'UHSLC':>6} {'Gauge lat':>10} {'Gauge lon':>10} {'MDT (m)':>9}"
    )
    click.echo(_DASH)
    seen: set[int] = set()
    for cfg in CITIES.values():
        if cfg.uhslc_id is None or cfg.uhslc_id in seen:
            continue
        seen.add(cfg.uhslc_id)
        offset = gauge_offsets[cfg.uhslc_id]
        glat, glon = UHSLC_GAUGE_COORDS.get(
            cfg.uhslc_id, (cfg.era5_lat, cfg.era5_lon)
        )
        click.echo(
            f"  {cfg.slug:<22} {cfg.uhslc_id:>6} "
            f"{glat:>10.4f} {glon:>10.4f} {offset:>+9.4f}"
        )
    click.echo(_SEP)

    if not write:
        click.echo("Dry-run complete. Pass --write to apply patches.")
        return

    # ------------------------------------------------------------------
    # 4. Patch baseline CSVs
    # ------------------------------------------------------------------
    click.echo("\nPatching baseline CSVs ...")
    for city_slug, cfg in CITIES.items():
        if cfg.uhslc_id is None:
            continue
        offset = gauge_offsets[cfg.uhslc_id]
        csv_path = DATA_DIR / city_slug / "hazard_baseline_template.csv"
        if not csv_path.exists():
            click.echo(f"  SKIP  {city_slug}: CSV not found at {csv_path}")
            continue
        df = pd.read_csv(csv_path, dtype=str)
        df["baseline_water_level_m"] = pd.to_numeric(
            df["baseline_water_level_m"], errors="coerce"
        )
        patched_df, n, prior = patch_coastal_rows(
            df, offset=offset, date_str=date_str
        )
        if n > 0:
            patched_df.to_csv(csv_path, index=False)
            net = offset - prior
            if abs(prior) > 1e-6:
                click.echo(
                    f"  PATCH {city_slug}: {n} coastal rows "
                    f"(new={offset:+.4f}m, prior={prior:+.4f}m, net delta={net:+.4f}m)"
                )
            else:
                click.echo(
                    f"  PATCH {city_slug}: {n} coastal rows (offset={offset:+.4f}m)"
                )
        else:
            click.echo(f"  SKIP  {city_slug}: already patched or no coastal rows")

    # ------------------------------------------------------------------
    # 5. Patch cities.py
    # ------------------------------------------------------------------
    if no_write_cities:
        click.echo("\nSkipping cities.py patch (--no-write-cities).")
        return

    click.echo("\nPatching cities.py ...")
    for city_slug, cfg in CITIES.items():
        if cfg.uhslc_id is None:
            continue
        offset = gauge_offsets[cfg.uhslc_id]
        changed = patch_cities_file(CITIES_PY, slug=city_slug, offset=offset)
        status = "PATCH" if changed else "SKIP (already correct)"
        click.echo(f"  {status:<5} {city_slug} -> msl_to_egm2008_offset={offset:.4f}")

    click.echo("\nDone.")


if __name__ == "__main__":
    cli()
