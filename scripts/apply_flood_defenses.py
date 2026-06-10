"""
Burn flood-defense crest elevations into a city DEM.

For each city in ``DEFENSE_CONFIGS`` we model engineered defense lines
(dykes, sea walls, polder rings) as polylines in WGS-84 with a crest
elevation expressed in metres above local MSL.  The script:

1. Converts each crest from local MSL to EGM2008 by adding the city's
   ``msl_to_egm2008_offset`` (the CMEMS CNES-CLS-2022 MDT).
2. Reprojects each polyline into the DEM's CRS.
3. Buffers each line by a small margin (default ~3 cells / 90 m at
   30 m grid) so a continuous ridge appears on the raster.
4. Burns ``max(DEM, crest_egm2008)`` into the DEM at the buffered
   pixels.

The output is written next to the input DEM with a ``_defended``
suffix.  Downstream pipeline steps can then be re-run pointing at the
new DEM to produce defended flood-extent rasters; the original
no-defense DEM is preserved so both variants can be compared.

This is a **screening-grade representation**: vertices are
approximate (from published BMA / DPSI / NCICD / PUB schematic maps
plus geographic context), defense crests are uniform along each
segment, and overtopping flow physics is not modelled (water either
sits below or floods over to full WL beyond the ridge).  It is
appropriate for first-order maps of "what changes if the documented
defense system holds at crest height X" — not for engineering design
of defense upgrades.

Usage::

    python scripts/apply_flood_defenses.py --city bangkok
    python scripts/apply_flood_defenses.py --city bangkok --dry-run
    python scripts/apply_flood_defenses.py --city bangkok \\
        --dem data/bangkok/copernicus_dem_utm47n_subsidence_corrected.tif

The script defaults to the **subsidence-corrected** DEM if it exists,
otherwise the raw GLO-30 DEM.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import click
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize
from shapely.geometry import LineString, mapping


# ---------------------------------------------------------------------------
# Defense configurations
# ---------------------------------------------------------------------------
# Each city has:
#   msl_to_egm2008_offset : float (m) — MDT shifting local MSL to EGM2008
#   defenses              : list of dicts with name, crest_msl_m, vertices, source_note
# Vertices are (lon, lat) WGS-84.
# ---------------------------------------------------------------------------

DEFENSE_CONFIGS: dict[str, dict] = {
    "bangkok": {
        "msl_to_egm2008_offset": 1.1785,  # CMEMS CNES-CLS-2022 (2026-05-16)
        "defenses": [
            {
                "name": "King's Dyke — eastern BMA flood-protection arc",
                "crest_msl_m": 2.5,
                "vertices": [
                    # Approximate polyline from north (Don Mueang) sweeping
                    # east and south around the BMA core, ending at the
                    # Bangna coast.  Sourced from BMA Drainage Master Plan
                    # (Phien-wej et al. 2006 figs; BMA 2012 raise to 2.5 m).
                    [100.610, 13.920],   # Don Mueang fringe
                    [100.660, 13.890],   # Sai Mai
                    [100.700, 13.860],   # Khlong Sam Wa
                    [100.720, 13.820],   # Min Buri
                    [100.720, 13.760],   # Saphan Sung
                    [100.700, 13.720],   # Prawet
                    [100.670, 13.680],   # Bang Kapi south
                    [100.640, 13.650],   # Bangna inner
                    [100.620, 13.640],   # Bangna outer
                    [100.610, 13.630],   # Sukhumvit Soi 105
                ],
                "source_note": (
                    "BMA Drainage Master Plan / Phien-wej et al. 2006 + "
                    "post-2011 raise to 2.5 m crest. Schematic polyline."
                ),
            },
            {
                "name": "Chao Phraya right-bank dyke (Thon Buri side)",
                "crest_msl_m": 2.0,
                "vertices": [
                    [100.495, 13.860],   # Nonthaburi south, right bank
                    [100.495, 13.810],   # Bang Phlat
                    [100.495, 13.760],   # Bangkok Yai
                    [100.510, 13.700],   # Phasi Charoen north
                    [100.530, 13.670],   # Phra Pradaeng west
                    [100.545, 13.640],   # Bang Kachao west boundary
                ],
                "source_note": "BMA / RID Chao Phraya bank-protection schematic.",
            },
            {
                "name": "Chao Phraya left-bank dyke (Phra Nakhon side)",
                "crest_msl_m": 2.0,
                "vertices": [
                    [100.510, 13.860],   # Nonthaburi east, left bank
                    [100.510, 13.810],   # Dusit
                    [100.515, 13.750],   # Pathum Wan / Sathon
                    [100.555, 13.710],   # Khlong Toei
                    [100.595, 13.690],   # Phra Khanong
                    [100.620, 13.660],   # Bangna inner
                ],
                "source_note": "BMA / RID Chao Phraya bank-protection schematic.",
            },
            {
                "name": "Bang Krachao polder ring",
                "crest_msl_m": 3.0,
                "vertices": [
                    # Closed ring around Bang Kachao peninsula
                    [100.545, 13.690],
                    [100.560, 13.690],
                    [100.570, 13.680],
                    [100.570, 13.670],
                    [100.560, 13.660],
                    [100.545, 13.655],
                    [100.535, 13.665],
                    [100.535, 13.680],
                    [100.545, 13.690],
                ],
                "source_note": "RID Bang Krachao polder schematic; ~3 m design crest.",
            },
        ],
        "default_dem": "copernicus_dem_utm47n_subsidence_corrected.tif",
        "buffer_m": 45.0,    # 1.5 pixels at 30 m grid
    },
    # -----------------------------------------------------------------
    # SINGAPORE
    # Marina Barrage (PUB tidal closure, ~3.5 m MSL crest) + the East
    # Coast Park bund (~5 m MSL crest along ECP). Source: PUB Coastal
    # Adaptation Study 2015; Marina Barrage technical brochure (PUB).
    # -----------------------------------------------------------------
    "singapore": {
        "msl_to_egm2008_offset": 1.1588,
        "defenses": [
            {
                "name": "Marina Barrage tidal closure",
                "crest_msl_m": 3.5,
                "vertices": [
                    [103.8703, 1.2807],  # west abutment, Marina South pier
                    [103.8718, 1.2810],  # mid-barrage span
                    [103.8734, 1.2812],  # east abutment, Marina East
                ],
                "source_note": (
                    "PUB Marina Barrage closure dam (constructed 2008). "
                    "Design crest +3.5 m MSL; impounds Marina Reservoir "
                    "as freshwater body."
                ),
            },
            {
                "name": "East Coast Park bund (ECP foreshore)",
                "crest_msl_m": 5.0,
                "vertices": [
                    [103.8975, 1.2980],  # Marina East / ECP west end
                    [103.9180, 1.3015],  # ECP Area D
                    [103.9395, 1.3055],  # ECP Area C / NSRCC
                    [103.9590, 1.3105],  # ECP Area B / Bedok Jetty
                    [103.9780, 1.3175],  # ECP Area A / Changi
                    [103.9920, 1.3230],  # ECP eastern terminus
                ],
                "source_note": (
                    "PUB Coastal Adaptation Study 2015 — ECP foreshore "
                    "bund designed to RP100 surge + SLR allowance; "
                    "~5 m above MSL."
                ),
            },
        ],
        "default_dem": "copernicus_dem_utm48n.tif",
        "buffer_m": 45.0,
    },
    # -----------------------------------------------------------------
    # JAKARTA
    # NCICD Phase A outer seawall (~32 km along N. Jakarta coast, ~4 m
    # MSL crest where built; gaps remain in Phase 1) + the major
    # North-Jakarta polder rings (Pluit, Muara Baru, Penjaringan).
    # Source: NCICD Master Plan (Bappenas / Witteveen+Bos 2014);
    # Brinkman & Hartman 2013; PAM Jaya polder system inventory.
    # -----------------------------------------------------------------
    "jakarta": {
        "msl_to_egm2008_offset": 0.9976,
        "defenses": [
            {
                "name": "NCICD Phase A outer seawall (north coast arc)",
                "crest_msl_m": 4.0,
                "vertices": [
                    [106.7250, -6.1050],  # Penjaringan west / Pluit outlet
                    [106.7460, -6.1010],  # Pluit
                    [106.7700, -6.1015],  # Muara Karang
                    [106.7960, -6.0980],  # Muara Baru / Sunda Kelapa
                    [106.8250, -6.0970],  # Ancol west
                    [106.8480, -6.0985],  # Ancol Marina
                    [106.8700, -6.1000],  # Tanjung Priok west
                    [106.9000, -6.0995],  # Kalibaru
                    [106.9300, -6.1015],  # Cilincing west
                    [106.9550, -6.1080],  # Cilincing east
                    [106.9750, -6.1140],  # Marunda
                ],
                "source_note": (
                    "NCICD Master Plan 2014 (Bappenas / Witteveen+Bos) — "
                    "Phase A outer dyke design crest +4 m MSL. "
                    "Partially constructed; treated as continuous "
                    "for screening."
                ),
            },
            {
                "name": "Pluit polder ring",
                "crest_msl_m": 2.5,
                "vertices": [
                    [106.7780, -6.1060],
                    [106.7860, -6.1060],
                    [106.7920, -6.1110],
                    [106.7920, -6.1180],
                    [106.7860, -6.1230],
                    [106.7780, -6.1230],
                    [106.7720, -6.1180],
                    [106.7720, -6.1110],
                    [106.7780, -6.1060],
                ],
                "source_note": (
                    "Pluit polder ring (Pluit pumping station catchment) — "
                    "schematic from PAM Jaya inventory; +2.5 m MSL design crest."
                ),
            },
            {
                "name": "Muara Baru polder ring",
                "crest_msl_m": 2.5,
                "vertices": [
                    [106.8060, -6.1050],
                    [106.8160, -6.1050],
                    [106.8200, -6.1100],
                    [106.8200, -6.1160],
                    [106.8140, -6.1190],
                    [106.8040, -6.1180],
                    [106.8010, -6.1130],
                    [106.8010, -6.1080],
                    [106.8060, -6.1050],
                ],
                "source_note": (
                    "Muara Baru polder (fish-port catchment); +2.5 m MSL "
                    "design crest per PAM Jaya schematic."
                ),
            },
            {
                "name": "Penjaringan polder ring (Ancol west)",
                "crest_msl_m": 2.5,
                "vertices": [
                    [106.7600, -6.1180],
                    [106.7700, -6.1180],
                    [106.7740, -6.1240],
                    [106.7720, -6.1300],
                    [106.7640, -6.1330],
                    [106.7560, -6.1310],
                    [106.7540, -6.1250],
                    [106.7560, -6.1200],
                    [106.7600, -6.1180],
                ],
                "source_note": (
                    "Penjaringan polder ring; +2.5 m MSL design crest "
                    "per PAM Jaya / Bappenas RDTR figures."
                ),
            },
        ],
        "default_dem": "copernicus_dem_utm48s_subsidence_corrected.tif",
        "buffer_m": 45.0,
    },
    # -----------------------------------------------------------------
    # MANILA
    # MMDA seawalls along Malabon-Navotas-Manila Bay reclamation coast,
    # Pasig River walls (both banks), KAMANAVA polder perimeter.
    # Source: JICA 2012 Master Plan for Flood Management in Metro
    # Manila (MFCMP); MMDA Annual Reports; DPWH Pasig-Marikina River
    # Channel Improvement Project (PMRCIP).
    # -----------------------------------------------------------------
    "manila": {
        "msl_to_egm2008_offset": 1.1292,
        "defenses": [
            {
                "name": "Malabon–Navotas coastal seawall",
                "crest_msl_m": 2.5,
                "vertices": [
                    [120.9430, 14.6900],  # Navotas north
                    [120.9480, 14.6850],
                    [120.9510, 14.6790],
                    [120.9530, 14.6720],  # Navotas south fish-port
                    [120.9550, 14.6650],  # Malabon Bay edge
                    [120.9580, 14.6580],  # Tondo north
                ],
                "source_note": (
                    "MMDA / DPWH Manila Bay coast protection; +2.5 m MSL "
                    "design crest per JICA MFCMP 2012 §5.4."
                ),
            },
            {
                "name": "Manila Bay reclamation revetment (Tondo–Pasay)",
                "crest_msl_m": 3.0,
                "vertices": [
                    [120.9580, 14.6580],  # Tondo north
                    [120.9610, 14.6450],  # Pier 18
                    [120.9645, 14.6310],  # Manila Yacht Club
                    [120.9700, 14.5800],  # Mall of Asia revetment
                    [120.9740, 14.5500],  # SM MOA Arena
                    [120.9790, 14.5260],  # Pasay reclamation south
                ],
                "source_note": (
                    "DPWH Manila Bay Development Plan revetment + SM MOA "
                    "reclamation seawalls; +3.0 m MSL design crest."
                ),
            },
            {
                "name": "Pasig River north-bank floodwall (Manila -> Pasig City)",
                "crest_msl_m": 3.0,
                "vertices": [
                    [120.9660, 14.5950],  # Pasig river mouth Manila Bay
                    [120.9800, 14.5945],  # Intramuros / Jones Bridge
                    [120.9900, 14.5935],  # Quiapo
                    [120.9990, 14.5930],  # Sta. Cruz / Sampaloc
                    [121.0080, 14.5925],  # San Miguel / Malacañang
                    [121.0260, 14.5940],  # Sta. Ana
                    [121.0450, 14.5750],  # Mandaluyong / Pasig east
                    [121.0700, 14.5680],  # Pasig City
                ],
                "source_note": (
                    "DPWH PMRCIP Pasig floodwall (post-1995 design). "
                    "Crest +3.0 m MSL = Pasig River mean flood plus "
                    "1.5 m freeboard."
                ),
            },
            {
                "name": "Pasig River south-bank floodwall",
                "crest_msl_m": 3.0,
                "vertices": [
                    [120.9660, 14.5940],  # river mouth
                    [120.9800, 14.5935],  # Ermita
                    [120.9900, 14.5925],  # Paco / Sta. Ana north
                    [120.9990, 14.5915],  # Sta. Ana
                    [121.0080, 14.5908],  # Makati north
                    [121.0260, 14.5920],  # Makati east
                    [121.0450, 14.5730],  # Mandaluyong south
                    [121.0700, 14.5660],  # Pasig City south
                ],
                "source_note": "DPWH PMRCIP Pasig floodwall south bank.",
            },
            {
                "name": "KAMANAVA polder perimeter dyke",
                "crest_msl_m": 2.5,
                "vertices": [
                    [120.9580, 14.6580],  # Tondo north (Manila Bay edge)
                    [120.9700, 14.6620],  # Navotas inland
                    [120.9870, 14.6650],  # Malabon centre
                    [120.9960, 14.6720],  # KAMANAVA east
                    [121.0050, 14.6810],  # Valenzuela north
                    [121.0150, 14.6850],  # Valenzuela east
                    [121.0200, 14.6700],  # Caloocan east
                    [121.0150, 14.6500],  # Caloocan south
                    [121.0000, 14.6400],  # Tondo east
                    [120.9800, 14.6450],  # closing
                    [120.9580, 14.6580],
                ],
                "source_note": (
                    "KAMANAVA (Kalookan-Malabon-Navotas-Valenzuela) "
                    "flood-control project perimeter dyke; +2.5 m MSL "
                    "design crest per JICA MFCMP 2012 §6.2."
                ),
            },
        ],
        "default_dem": "copernicus_dem_utm51n_subsidence_corrected.tif",
        "buffer_m": 45.0,
    },
    # -----------------------------------------------------------------
    # HO CHI MINH CITY
    # Saigon-Nha Be southern ring dyke (~12 km arc; partial completion;
    # crest +2.5 m MSL where built) + the major tide gates at Nha Be,
    # Binh Chanh, Cai Lon, Cai Tan, Phu Xuan, Phu My, Muong Chuoi.
    # Source: SCFC HCMC Flood Management Plan; JICA 2009 Drainage and
    # Sewerage Study; Trinh et al. 2017 SIWRR.
    # -----------------------------------------------------------------
    "hcmc": {
        "msl_to_egm2008_offset": 1.1707,
        "defenses": [
            {
                "name": "Saigon-Nha Be southern ring dyke (D7 south + Nha Be)",
                "crest_msl_m": 2.5,
                "vertices": [
                    [106.7300, 10.7350],  # D8 south / Binh Hung
                    [106.7430, 10.7280],  # D8 / Nha Be NW
                    [106.7560, 10.7200],  # Nha Be west
                    [106.7700, 10.7100],  # Nha Be centre
                    [106.7850, 10.7050],  # Nha Be SE
                    [106.7990, 10.7030],  # Phu My Hung south
                    [106.8120, 10.7080],  # Tan Thuan
                    [106.8260, 10.7140],  # D7 east / Saigon River bank
                    [106.8380, 10.7240],  # D7 / Binh Thanh boundary
                ],
                "source_note": (
                    "SCFC HCMC Flood Management Plan — Saigon-Nha Be "
                    "outer dyke; +2.5 m MSL design crest. Constructed "
                    "in 2017-2024 between D7 and Nha Be; treated as "
                    "continuous for screening."
                ),
            },
            {
                "name": "Saigon River right-bank floodwall (D1 -> D2 -> D7)",
                "crest_msl_m": 2.5,
                "vertices": [
                    [106.7050, 10.7800],  # Saigon River entry from D2 north
                    [106.7150, 10.7740],  # D1 / Bach Dang waterfront
                    [106.7250, 10.7680],  # Khanh Hoi / D4 east
                    [106.7380, 10.7600],  # D4 south
                    [106.7500, 10.7500],  # D7 north / Tan Thuan
                    [106.7650, 10.7400],  # D7 SW / Phu My Hung
                ],
                "source_note": (
                    "SCFC / DPSI Saigon River floodwall on right (urban) "
                    "bank; +2.5 m MSL crest. Bach Dang -> Tan Thuan reach."
                ),
            },
            {
                "name": "Nha Be tide gate",
                "crest_msl_m": 3.0,
                "vertices": [
                    [106.7480, 10.7180],
                    [106.7510, 10.7155],
                ],
                "source_note": (
                    "Nha Be tide-gate barrier (constructed 2020). "
                    "Crest +3.0 m MSL when closed."
                ),
            },
            {
                "name": "Phu My tide gate",
                "crest_msl_m": 3.0,
                "vertices": [
                    [106.7900, 10.7160],
                    [106.7930, 10.7135],
                ],
                "source_note": (
                    "Phu My tide gate (part of HCMC anti-tide scheme); "
                    "crest +3.0 m MSL when closed."
                ),
            },
            {
                "name": "Muong Chuoi tide gate",
                "crest_msl_m": 3.0,
                "vertices": [
                    [106.7150, 10.7020],
                    [106.7180, 10.6995],
                ],
                "source_note": (
                    "Muong Chuoi tide gate (Binh Chanh south); crest "
                    "+3.0 m MSL when closed."
                ),
            },
        ],
        "default_dem": "copernicus_dem_utm48n_subsidence_corrected.tif",
        "buffer_m": 45.0,
    },
}


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def burn_defenses(
    dem_path: Path,
    config: dict,
    out_path: Path,
    buffer_m: float | None = None,
    dry_run: bool = False,
) -> tuple[int, float]:
    """Burn defense crests into the DEM and write the defended raster.

    Returns ``(n_pixels_modified, max_dem_increase_m)``.
    """
    buffer_m = buffer_m if buffer_m is not None else config.get("buffer_m", 45.0)

    with rasterio.open(dem_path) as src:
        dem = src.read(1)
        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs
        nodata = src.nodata if src.nodata is not None else -9999.0

    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    shapes: list[tuple] = []

    for d in config["defenses"]:
        crest_egm = d["crest_msl_m"] + config["msl_to_egm2008_offset"]
        verts_xy = [transformer.transform(lon, lat) for lon, lat in d["vertices"]]
        line = LineString(verts_xy)
        buf = line.buffer(buffer_m)
        shapes.append((mapping(buf), float(crest_egm)))
        click.echo(
            f"  {d['name']}: "
            f"{d['crest_msl_m']:.2f}m MSL -> {crest_egm:.4f}m EGM2008; "
            f"length={line.length / 1000:.1f}km"
        )

    crest_raster = rasterize(
        shapes,
        out_shape=dem.shape,
        transform=transform,
        fill=-9999.0,
        dtype="float32",
    )

    # Only modify finite land pixels (skip nodata).
    mask = (crest_raster > -9000) & (dem != nodata) & np.isfinite(dem)
    delta = np.zeros_like(dem, dtype=np.float32)
    delta[mask] = np.maximum(0.0, crest_raster[mask] - dem[mask])
    n_modified = int((delta > 0).sum())
    max_increase = float(delta.max()) if n_modified else 0.0
    mean_increase = float(delta[mask].mean()) if mask.sum() else 0.0

    defended = dem.astype(np.float32).copy()
    defended[mask] = np.maximum(defended[mask], crest_raster[mask])

    if dry_run:
        click.echo(
            f"\n[dry-run]\n  Pixels modified: {n_modified:,}\n"
            f"  Mean DEM raise where modified: {mean_increase:.3f} m\n"
            f"  Max DEM raise: {max_increase:.3f} m"
        )
        return n_modified, max_increase

    profile.update(dtype="float32", compress="deflate", predictor=2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(defended, 1)

    click.echo(
        f"\nWrote {out_path}\n"
        f"  Pixels modified: {n_modified:,}\n"
        f"  Mean DEM raise where modified: {mean_increase:.3f} m\n"
        f"  Max DEM raise: {max_increase:.3f} m"
    )
    return n_modified, max_increase


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option("--city", "city_slug",
              type=click.Choice(list(DEFENSE_CONFIGS)), required=True)
@click.option("--dem", "dem_path", type=click.Path(path_type=Path), default=None,
              help="Input DEM (default: city's preferred DEM in data/<city>/).")
@click.option("--output", "out_path", type=click.Path(path_type=Path), default=None,
              help="Output path (default: <dem_stem>_defended.tif next to input).")
@click.option("--buffer-m", type=float, default=None,
              help="Override buffer radius around defense lines (m).")
@click.option("--dry-run", is_flag=True, default=False)
def cli(
    city_slug: str,
    dem_path: Path | None,
    out_path: Path | None,
    buffer_m: float | None,
    dry_run: bool,
) -> None:
    config = DEFENSE_CONFIGS[city_slug]
    project_root = Path(__file__).resolve().parents[1]
    if dem_path is None:
        dem_path = project_root / "data" / city_slug / config["default_dem"]
    if out_path is None:
        out_path = dem_path.with_name(dem_path.stem + "_defended.tif")

    click.echo(
        f"Apply flood defenses\n"
        f"  city  : {city_slug}\n"
        f"  DEM in: {dem_path}\n"
        f"  DEM out: {out_path}\n"
        f"  MDT offset: +{config['msl_to_egm2008_offset']:.4f} m\n"
    )
    burn_defenses(dem_path, config, out_path,
                  buffer_m=buffer_m, dry_run=dry_run)


if __name__ == "__main__":
    cli()
