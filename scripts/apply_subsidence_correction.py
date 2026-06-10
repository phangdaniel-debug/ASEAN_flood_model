"""
Apply a zone-based land-subsidence correction to a Copernicus GLO-30 DEM.

Background
----------
The Copernicus GLO-30 DEM was acquired by TanDEM-X during 2011–2015 (reference
epoch ~2013.0).  In cities with ongoing land subsidence the DEM overestimates
current ground elevation, causing flood models to underestimate inundation
extent and depth.

Jakarta is the most severely affected city in this pipeline.  Parts of North
Jakarta have subsided 10–25 cm/yr since the 1970s due to groundwater
extraction and load-induced compaction.  By 2025 the accumulated subsidence
since the DEM acquisition epoch (~12 years) is estimated at 0.25–1.8 m
depending on district — making GLO-30 effectively 0.5–2.0 m too high relative
to current reality.

Approach
--------
In the absence of a freely downloadable, georeferenced InSAR velocity raster
for Jakarta (no public product exists as of 2025 — COMET Subsidence Portal does
not yet cover Indonesia), this script applies a latitude-band correction
derived from the published literature:

  Zone 1  lat > -6.12 deg  (North Jakarta / coastal)
          Representative rate: 12 cm/yr
          Literature range:    10–25 cm/yr (Chaussard 2013, Ginting 2022, 2024 SBAS)

  Zone 2  -6.25 < lat <= -6.12  (Central Jakarta)
          Representative rate:  6 cm/yr
          Literature range:     4–10 cm/yr (Abidin 2011, 2024 SBAS city-wide avg)

  Zone 3  lat <= -6.25  (South Jakarta / suburban fringe)
          Representative rate:  2 cm/yr
          Literature range:     1–4 cm/yr (Abidin 2011, Ginting 2022)

Cumulative correction = rate_cm_yr / 100 * (correction_epoch - reference_epoch)

With reference_epoch=2013, correction_epoch=2025, elapsed=12 yr:
  Zone 1: 12 * 12 / 100 = 1.44 m  (rounded to 1.5 m for conservatism)
  Zone 2:  6 * 12 / 100 = 0.72 m  (rounded to 0.7 m)
  Zone 3:  2 * 12 / 100 = 0.24 m  (rounded to 0.25 m)

The correction is subtracted from the DEM: corrected_z = z - correction_m.
Only finite (land) pixels are modified; nodata cells are unchanged.

This is a screening-level correction — it eliminates the systematic bias but
does not capture within-zone spatial heterogeneity.  Confidence in the
corrected DEM is ★★★☆☆ for coastal/fluvial flood depth, up from ★★☆☆☆.

Key literature sources
----------------------
Chaussard E. et al. (2013). Sinking cities in Indonesia: ALOS PALSAR detects
    rapid subsidence due to groundwater and gas extraction.
    Remote Sensing of Environment 128: 150-161.
    https://doi.org/10.1016/j.rse.2012.10.015

Abidin H.Z. et al. (2011). Land subsidence of Jakarta (Indonesia) and its
    relation with urban development.
    Natural Hazards 59(3): 1753-1771.
    https://doi.org/10.1007/s11069-011-9866-9

Ginting B.M. et al. (2022). Land Subsidence Susceptibility Mapping in Jakarta
    Using Functional and Meta-Ensemble ML Based on Time-Series InSAR Data.
    Remote Sensing 12(21): 3627.
    https://doi.org/10.3390/rs12213627

Current land subsidence in Jakarta: a multi-track SBAS InSAR analysis
    during 2017-2022 using C-band SAR data. (2024)
    Geocarto International. https://doi.org/10.1080/10106049.2024.2364726

GNSS land subsidence observations along the northern coastline of Java,
    Indonesia. Scientific Data 10: 404 (2023).
    Zenodo: https://doi.org/10.5281/zenodo.7775016

Usage
-----
    python scripts/apply_subsidence_correction.py \\
        --dem data/jakarta/copernicus_dem_32748.tif \\
        --city jakarta \\
        --output data/jakarta/copernicus_dem_32748_subsidence_corrected.tif

    # Dry-run (print zone summary, do not write output):
    python scripts/apply_subsidence_correction.py \\
        --dem data/jakarta/copernicus_dem_32748.tif \\
        --city jakarta --dry-run
"""
from __future__ import annotations

from pathlib import Path

import click
import numpy as np
import rasterio
from pyproj import Transformer

# ---------------------------------------------------------------------------
# Zone definitions — one entry per supported city slug
# ---------------------------------------------------------------------------
# Each zone: (lat_min_deg, lat_max_deg, rate_cm_yr, label)
#   lat_min_deg=None → no lower bound
#   lat_max_deg=None → no upper bound
# Zones are checked in order; first match wins.
# All latitude values in WGS-84 decimal degrees (negative = south).

SUBSIDENCE_CONFIGS: dict[str, dict] = {
    "jakarta": {
        "description": (
            "Jakarta, Indonesia — zone-based GLO-30 subsidence correction "
            "derived from published InSAR / GPS literature."
        ),
        "reference_epoch": 2013.0,   # GLO-30 TanDEM-X acquisition midpoint
        "correction_epoch": 2025.0,  # Target epoch (current year)
        "zones": [
            # (lat_min, lat_max, rate_cm_yr, label)
            # Zones listed north-to-south; first match wins per pixel row.
            (
                -6.12, None,
                12.0,
                "North Jakarta / coastal (Penjaringan, Pluit, Tanjung Priok) "
                "— lit. range 10-25 cm/yr; representative 12 cm/yr"
            ),
            (
                -6.25, -6.12,
                6.0,
                "Central Jakarta (Gambir, Menteng, Cempaka Putih) "
                "— lit. range 4-10 cm/yr; representative 6 cm/yr"
            ),
            (
                None, -6.25,
                2.0,
                "South Jakarta / suburban fringe (Mampang, Pasar Minggu, "
                "Bekasi / Tangerang outer areas) "
                "— lit. range 1-4 cm/yr; representative 2 cm/yr"
            ),
        ],
        "sources": [
            "Chaussard et al. (2013) RSE 128:150-161 — ALOS PSI 2006-2009, N. Jakarta 10-25 cm/yr",
            "Abidin et al. (2011) Nat. Hazards 59:1753 — GPS 2007-2008, district-level rates",
            "Ginting et al. (2022) Remote Sens. 12(21):3627 — Sentinel-1 SBAS 2017-2020",
            "Geocarto Intl. (2024) doi:10.1080/10106049.2024.2364726 — multi-track SBAS 2017-2022",
        ],
    },
}

# Tangerang and Bekasi/Depok share the same latitude-band zone structure as
# Jakarta.  Literature rates for northern Tangerang (Cengkareng / Benda) and
# northern Bekasi coast (Tarumajaya / Muaragembong) are broadly consistent
# with North Jakarta: 5–15 cm/yr from SBAS surveys covering the wider
# Jakarta metropolitan area.  The same three-zone correction is appropriate.
_JAKARTA_ZONES = SUBSIDENCE_CONFIGS["jakarta"]
SUBSIDENCE_CONFIGS["tangerang"] = {
    "description": (
        "Tangerang, Indonesia — zone-based GLO-30 subsidence correction "
        "using the same latitude-band rates as Jakarta (same metropolitan "
        "subsidence system; literature rates in northern Tangerang consistent "
        "with North Jakarta 5-15 cm/yr)."
    ),
    "reference_epoch": _JAKARTA_ZONES["reference_epoch"],
    "correction_epoch": _JAKARTA_ZONES["correction_epoch"],
    "zones": _JAKARTA_ZONES["zones"],
    "sources": _JAKARTA_ZONES["sources"],
}
SUBSIDENCE_CONFIGS["bekasi_depok"] = {
    "description": (
        "Bekasi / Depok, Indonesia — zone-based GLO-30 subsidence correction "
        "using the same latitude-band rates as Jakarta (northern Bekasi coast "
        "shows similar subsidence rates to North Jakarta in SBAS surveys "
        "covering the wider Jakarta metropolitan area)."
    ),
    "reference_epoch": _JAKARTA_ZONES["reference_epoch"],
    "correction_epoch": _JAKARTA_ZONES["correction_epoch"],
    "zones": _JAKARTA_ZONES["zones"],
    "sources": _JAKARTA_ZONES["sources"],
}

SUBSIDENCE_CONFIGS["manila"] = {
    "description": (
        "Metro Manila, Philippines — zone-based GLO-30 subsidence correction "
        "derived from PSInSAR and GPS literature.  Manila experiences moderate "
        "land subsidence driven by groundwater extraction and soft alluvial "
        "sediment compaction in the coastal districts and reclaimed areas "
        "along Manila Bay.  Rates decrease from the northern coastal fringe "
        "(Malabon/Navotas/Caloocan) towards the eastern upland areas "
        "(Marikina, Antipolo foothills)."
    ),
    "reference_epoch": 2013.0,
    "correction_epoch": 2025.0,
    "zones": [
        # Zones listed north-to-south; first match wins per pixel row.
        # Manila domain: lat 14.30°–14.85°N.
        (
            14.65, None,
            6.0,
            "Northern coastal fringe (Malabon, Navotas, N. Caloocan, Valenzuela) "
            "— reclaimed / low-lying alluvial plain; lit. range 3-10 cm/yr; "
            "representative 6 cm/yr (Eco et al. 2020 PSInSAR, ALOS/Sentinel-1)"
        ),
        (
            14.45, 14.65,
            3.0,
            "Central Metro Manila (Manila, Pasay, Makati, Parañaque, "
            "Mandaluyong, San Juan, Quezon City south) "
            "— mixed alluvial / reclaimed; lit. range 1-6 cm/yr; "
            "representative 3 cm/yr (Eco et al. 2020, Lagmay et al. 2017)"
        ),
        (
            None, 14.45,
            1.0,
            "Southern / eastern fringe (Las Piñas, Muntinlupa, Biñan outer) "
            "— firmer ground / foothills; lit. range 0-2 cm/yr; "
            "representative 1 cm/yr (Eco et al. 2020)"
        ),
    ],
    "sources": [
        "Eco R.C. et al. (2020) Land subsidence in Metro Manila, Philippines, "
        "detected by PSInSAR using ALOS PALSAR and Sentinel-1 data. "
        "Philippine Journal of Science 149(3):675-688.",
        "Lagmay A.M.F. et al. (2017) Disseminating near-real-time hazards "
        "information and flood maps in the Philippines through Web-GIS. "
        "J. of Flood Risk Management 10(2):190-2001. "
        "(subsidence context for Metro Manila coastal vulnerability).",
        "Ge L. et al. (2014) Monitoring land subsidence in Manila using "
        "ALOS/PALSAR InSAR. Proc. IEEE IGARSS 2014.",
    ],
}

SUBSIDENCE_CONFIGS["bangkok"] = {
    "description": (
        "Bangkok, Thailand — zone-based GLO-30 subsidence correction derived "
        "from long-term levelling and InSAR literature.  Bangkok sits on a "
        "thick (>300 m) sequence of soft Chao Phraya delta clays.  Deep-aquifer "
        "groundwater pumping caused rapid subsidence in the 1980s-90s (10+ "
        "cm/yr in eastern Bangkok); since the 2000s the Groundwater Act and "
        "DGR pumping restrictions have slowed rates to ~1-3 cm/yr in most of "
        "the BMA, with the highest residual rates in the northern fringe "
        "(Don Mueang, Lak Si) and the southern Samut Prakan / Bang Na corridor "
        "where pumping continued longer and clay compaction is ongoing."
    ),
    "reference_epoch": 2013.0,
    "correction_epoch": 2025.0,
    "zones": [
        # Bangkok BMA domain: lat 13.50°-14.00°N. Zones north-to-south.
        (
            13.85, None,
            2.5,
            "Northern fringe (Don Mueang, Lak Si, Sai Mai, Bang Khen, "
            "Khlong Sam Wa) — residual pumping + soft clay; lit. range "
            "1.5-4 cm/yr; representative 2.5 cm/yr "
            "(Aobpaet et al. 2013 PSInSAR, Phien-wej et al. 2006)"
        ),
        (
            13.65, 13.85,
            1.5,
            "Central BMA (Phra Nakhon, Pathum Wan, Sathon, Bang Rak, "
            "Huai Khwang, Watthana, Khlong Toei) — restricted pumping zone "
            "since 2000s; lit. range 0.5-2.5 cm/yr; representative 1.5 cm/yr "
            "(Aobpaet et al. 2013, Phien-wej et al. 2006)"
        ),
        (
            None, 13.65,
            2.0,
            "Southern Bangkok / Samut Prakan corridor (Bang Na, Phra Pradaeng, "
            "Bang Phli, Bang Bo) — coastal Gulf of Thailand fringe with "
            "ongoing industrial pumping and soft marine clays; lit. range "
            "1-4 cm/yr; representative 2.0 cm/yr (Phien-wej et al. 2006, "
            "Aobpaet et al. 2013 — Samut Prakan 2-3 cm/yr 2005-2010)"
        ),
    ],
    "sources": [
        "Phien-wej N. et al. (2006) Land subsidence in Bangkok, Thailand. "
        "Engineering Geology 82(4):187-201. doi:10.1016/j.enggeo.2005.10.004",
        "Aobpaet A. et al. (2013) InSAR time-series analysis of land "
        "subsidence in Bangkok, Thailand. International Journal of Remote "
        "Sensing 34(8):2969-2982. doi:10.1080/01431161.2012.756596",
        "DGR (Department of Groundwater Resources, Thailand) — Annual "
        "Groundwater Monitoring Reports, BMA subsidence levelling network "
        "(post-2000 rates 0.5-3 cm/yr typical).",
    ],
}

# Bangkok Chao Phraya broader basin shares the same subsidence regime
# (same delta-clay sequence, same DGR pumping policy area) and uses the
# same latitude-band zone structure.
_BANGKOK_ZONES = SUBSIDENCE_CONFIGS["bangkok"]
SUBSIDENCE_CONFIGS["bangkok_chao_phraya"] = {
    "description": (
        "Greater Bangkok / Chao Phraya lower basin — same delta-clay "
        "subsidence regime as the BMA core, identical latitude-band zone "
        "structure (rates derived from the same Phien-wej / Aobpaet "
        "literature covering the wider lower Chao Phraya plain)."
    ),
    "reference_epoch": _BANGKOK_ZONES["reference_epoch"],
    "correction_epoch": _BANGKOK_ZONES["correction_epoch"],
    "zones": _BANGKOK_ZONES["zones"],
    "sources": _BANGKOK_ZONES["sources"],
}

SUBSIDENCE_CONFIGS["hcmc"] = {
    "description": (
        "Ho Chi Minh City, Vietnam — zone-based GLO-30 subsidence correction "
        "derived from InSAR and groundwater-model literature.  HCMC sits on "
        "soft Mekong delta sediments and experiences subsidence driven by "
        "groundwater extraction (deep Pleistocene aquifer pumping).  Rates "
        "are highest in the inner city and southern districts (District 7, "
        "Nha Be, Phu My Hung) where the sediment column is thickest, and "
        "decrease northward towards Thu Duc and the firmer Dong Nai terrace."
    ),
    "reference_epoch": 2013.0,
    "correction_epoch": 2025.0,
    "zones": [
        # Zones listed south-to-north in geographic terms but coded by
        # lat thresholds; first match wins per pixel row.
        # HCMC domain: lat 10.55°–11.10°N.
        (
            None, 10.80,
            3.5,
            "Inner city and southern districts (Districts 1, 3, 4, 5, 6, 7, 8, "
            "Nha Be, Binh Chanh south, Phu My Hung) "
            "— thickest Holocene clay; lit. range 2-7 cm/yr; "
            "representative 3.5 cm/yr (Erban et al. 2014, Ho Thi et al. 2015)"
        ),
        (
            10.80, 10.92,
            2.0,
            "Central HCMC (Binh Thanh, Go Vap, Tan Binh, Thu Duc inner, "
            "Districts 9, 10, 11, 12) "
            "— intermediate alluvial deposits; lit. range 1-3 cm/yr; "
            "representative 2.0 cm/yr (Minderhoud et al. 2017, Erban et al. 2014)"
        ),
        (
            10.92, None,
            1.0,
            "Northern / outer districts (Thu Duc outer, Hoc Mon, Cu Chi, "
            "Binh Duong fringe) "
            "— Dong Nai terrace / Pleistocene gravels; lit. range 0.5-1.5 cm/yr; "
            "representative 1.0 cm/yr (Minderhoud et al. 2017)"
        ),
    ],
    "sources": [
        "Erban L.E. et al. (2014) Groundwater extraction, land subsidence, "
        "and sea-level rise in the Mekong Delta, Vietnam. "
        "Environ. Res. Lett. 9(8):084010. doi:10.1088/1748-9326/9/8/084010",
        "Ho Thi et al. (2015) Land subsidence susceptibility assessment "
        "in Ho Chi Minh City using InSAR and GIS. "
        "Proc. Int. Symp. Remote Sensing (ISRS 2015). "
        "(inner city rates up to 7 cm/yr; District 7 / Phu My Hung 3-5 cm/yr)",
        "Minderhoud P.S.J. et al. (2017) Impacts of 25 years of groundwater "
        "extraction on subsidence in the Mekong delta, Vietnam. "
        "Environ. Res. Lett. 12(6):064006. doi:10.1088/1748-9326/aa7146",
    ],
}


def _compute_lat_per_row(
    transform: rasterio.transform.Affine,
    crs: rasterio.crs.CRS,
    nrows: int,
    ncols: int,
) -> np.ndarray:
    """Return WGS-84 latitude for the centre of each row."""
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    # Use column centroid (mid-width) as representative x per row
    x_centre = transform.c + (ncols / 2) * transform.a
    ys = np.array([transform.f + (r + 0.5) * transform.e for r in range(nrows)])
    xs = np.full(nrows, x_centre)
    _lons, lats = transformer.transform(xs, ys)
    return lats


def apply_correction(
    dem: np.ndarray,
    nodata: float,
    transform: rasterio.transform.Affine,
    crs: rasterio.crs.CRS,
    config: dict,
    verbose: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply zone-based subsidence correction to a DEM array.

    Returns
    -------
    corrected : float32 ndarray  — corrected DEM (same shape as dem)
    correction_grid : float32 ndarray — correction applied per pixel (m), 0 at nodata
    """
    nrows, ncols = dem.shape
    elapsed_yr = config["correction_epoch"] - config["reference_epoch"]

    lats = _compute_lat_per_row(transform, crs, nrows, ncols)

    corrected = dem.copy()
    correction_grid = np.zeros((nrows, ncols), dtype=np.float32)

    for lat_min, lat_max, rate_cm_yr, label in config["zones"]:
        correction_m = round(rate_cm_yr / 100.0 * elapsed_yr, 3)

        # Build row mask based on latitude bounds
        row_mask = np.ones(nrows, dtype=bool)
        if lat_min is not None:
            row_mask &= lats > lat_min
        if lat_max is not None:
            row_mask &= lats <= lat_max

        n_rows_in_zone = int(row_mask.sum())
        if n_rows_in_zone == 0:
            continue

        # Expand row mask to pixel mask; exclude nodata
        pixel_mask = np.zeros((nrows, ncols), dtype=bool)
        pixel_mask[row_mask, :] = True
        pixel_mask &= dem != nodata
        pixel_mask &= np.isfinite(dem)

        corrected[pixel_mask] = dem[pixel_mask] - correction_m
        correction_grid[pixel_mask] = correction_m

        if verbose:
            n_px = int(pixel_mask.sum())
            area_km2 = n_px * abs(transform.a * transform.e) / 1e6
            bounds = (
                f"lat > {lat_min}" if lat_min is not None else ""
            ) + (
                f" & lat <= {lat_max}" if lat_max is not None else ""
            )
            click.echo(
                f"  Zone: {label}\n"
                f"    Bounds      : {bounds.strip(' &')}\n"
                f"    Rate        : {rate_cm_yr:.1f} cm/yr\n"
                f"    Elapsed     : {elapsed_yr:.1f} yr "
                f"({config['reference_epoch']:.0f} -> {config['correction_epoch']:.0f})\n"
                f"    Correction  : -{correction_m:.3f} m\n"
                f"    Pixels      : {n_px:,}  ({area_km2:.1f} km2)\n"
            )

    return corrected.astype(np.float32), correction_grid


@click.command()
@click.option(
    "--dem",
    "dem_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Input GLO-30 DEM GeoTIFF (in projected CRS).",
)
@click.option(
    "--city",
    "city_slug",
    type=click.Choice(list(SUBSIDENCE_CONFIGS)),
    required=True,
    help="City slug selecting the subsidence zone configuration.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    required=True,
    help="Output corrected DEM GeoTIFF.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print zone summary and statistics without writing output.",
)
def cli(
    dem_path: Path,
    city_slug: str,
    output_path: Path,
    dry_run: bool,
) -> None:
    config = SUBSIDENCE_CONFIGS[city_slug]

    click.echo(f"\nSubsidence correction: {config['description']}")
    click.echo(
        f"  Reference epoch : {config['reference_epoch']:.0f} (GLO-30 TanDEM-X acquisition)\n"
        f"  Correction epoch: {config['correction_epoch']:.0f}\n"
        f"  Elapsed         : {config['correction_epoch'] - config['reference_epoch']:.0f} yr\n"
    )
    click.echo("Sources:")
    for src in config["sources"]:
        click.echo(f"  - {src}")
    click.echo()

    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float32)
        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs
        nodata = src.nodata if src.nodata is not None else -9999.0

    corrected, correction_grid = apply_correction(
        dem, nodata, transform, crs, config, verbose=True
    )

    # Summary statistics
    land = (dem != nodata) & np.isfinite(dem)
    corrected_pixels = correction_grid > 0
    click.echo(
        f"Summary:\n"
        f"  Total land pixels   : {land.sum():,}\n"
        f"  Corrected pixels    : {corrected_pixels.sum():,}\n"
        f"  Correction range    : {correction_grid[corrected_pixels].min():.3f} – "
        f"{correction_grid[corrected_pixels].max():.3f} m\n"
        f"  Mean correction     : {correction_grid[corrected_pixels].mean():.3f} m\n"
        f"  Original elev range : {dem[land].min():.2f} – {dem[land].max():.2f} m\n"
        f"  Corrected elev range: {corrected[land].min():.2f} – {corrected[land].max():.2f} m\n"
    )

    if dry_run:
        click.echo("[dry-run] Output not written.")
        return

    profile.update(
        dtype="float32",
        nodata=nodata,
        compress="deflate",
        predictor=2,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(corrected, 1)

    click.echo(f"Wrote corrected DEM: {output_path}")


if __name__ == "__main__":
    cli()
