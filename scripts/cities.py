"""
City configuration registry for the multi-hazard flood pipeline.

Each CityConfig captures all the geography- and hydrology-specific values
that must change when the pipeline is run for a new city.  The rest of the
pipeline (GEV fitting, DEM fetch, flood routing, visualisation) is fully
generic and requires no code changes.

Adding a new city
-----------------
1. Create a CityConfig entry in CITIES below.
2. Create data/<slug>/hazard_baseline_template.csv (copy the Singapore
   template structure; coastal rows will be replaced by fetch_gesla_singapore.py).
3. Run: python scripts/run_city_pipeline.py --city <slug> --scenario SSP5-8.5 --horizon 2100

UHSLC station IDs
-----------------
Look up station IDs at https://uhslc.soest.hawaii.edu/data/
Station metadata is also available via the ERDDAP catalogue:
  https://uhslc.soest.hawaii.edu/erddap/tabledap/global_hourly_rqds.html
Set uhslc_id=None if no suitable research-quality gauge exists for the city.
The pipeline will skip the coastal tide-gauge step and leave the coastal rows
in the baseline template as-is (must be populated manually before running).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CityConfig:
    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    name: str           # display name, e.g. "Kuala Lumpur"
    slug: str           # filesystem slug, e.g. "kuala_lumpur"

    # ------------------------------------------------------------------
    # Bounding box (WGS84 decimal degrees)
    # ------------------------------------------------------------------
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    # ------------------------------------------------------------------
    # Projected CRS for DEM and flood model
    # Must be a metric CRS covering the city (UTM zone recommended).
    # ------------------------------------------------------------------
    utm_crs: str        # e.g. "EPSG:32647"

    # ------------------------------------------------------------------
    # ERA5 precipitation download point
    # A representative centroid within the city extent.
    # ------------------------------------------------------------------
    era5_lat: float
    era5_lon: float

    # ------------------------------------------------------------------
    # Coastal tide gauge (UHSLC Research Quality dataset)
    # uhslc_id=None → skip coastal gauge fetch; populate CSV manually.
    # uhslc_start_year / uhslc_end_year: record length to request.
    #
    # msl_to_egm2008_offset: height of local MSL above EGM2008 (metres).
    #   Equals the Mean Dynamic Topography (MDT) at the gauge location.
    #   Derived from CMEMS CNES-CLS-2022 hybrid MDT product via:
    #     python scripts/derive_msl_egm2008_offsets.py --write
    #   (requires `copernicusmarine login` first; free CMEMS account).
    #   Do NOT edit manually; the script patches all configs idempotently.
    #
    # Current values (CMEMS CNES-CLS-2022, sampled at gauge coordinates 2026-05-16):
    #   - UHSLC 699 = Singapore (Tanjong Pagar) → +1.1588 m
    #   - UHSLC 140 = Port Klang / Kelang       → +1.0226 m
    #   - UHSLC 328 = Bangkok / Ko Lak          → +1.1785 m
    #   - UHSLC 161 = Tanjung Priok             → +0.9976 m
    #   - UHSLC 304 = Manila (Fort Santiago)    → +1.1292 m
    #   - UHSLC 257 = Vung Tau (HCMC proxy)     → +1.1707 m
    # SE Asia / W. Pacific Warm Pool MDT is ~1 m due to wind-driven + thermohaline
    # sea-surface elevation above the EGM2008 geoid; values here are physically
    # consistent with peer-reviewed CNES-CLS-2022 maps for the maritime continent.
    # ------------------------------------------------------------------
    uhslc_id: int | None
    uhslc_dataset: str              # "rqds" (research quality) or "fast" (fast-delivery)
    uhslc_start_year: int
    uhslc_end_year: int
    uhslc_gauge_name: str           # label used in CSV source_note
    msl_to_egm2008_offset: float    # metres; positive = MSL above EGM2008

    # ------------------------------------------------------------------
    # Fluvial hydrology parameters
    # ------------------------------------------------------------------
    # SCS Curve Number: 70 (mixed suburban) → 90 (dense impervious urban)
    cn: float
    # Representative catchment area (km²) — drives peak discharge magnitude.
    catchment_km2: float
    # Time of concentration (h) — urban Singapore: 0.5 h; larger basins: 2–5 h
    time_of_conc_h: float
    # Representative primary channel width (m)
    channel_width_m: float
    # Manning's roughness: concrete 0.013–0.017; natural earth 0.030–0.050
    mannings_n: float
    # Channel slope (m/m): flat delta <0.0005; steep urban drain ~0.005
    channel_slope: float

    # ------------------------------------------------------------------
    # Pluvial hydrology parameters
    # ------------------------------------------------------------------
    # Rainfall depth (mm) for a design-duration storm that the drainage network
    # conveys without surface ponding.  Calibrate to the appropriate national
    # design standard; the storm duration should match the dominant failure
    # mechanism:
    #   - Primary drain failure (long convective events): 6h IDF, e.g. 100 mm/6h
    #   - Secondary/tertiary drain failure (flash flooding): 1h IDF, e.g. 70 mm/1h
    # Singapore uses 1h/70mm (PUB CoP secondary drain RP5) to simulate the
    # documented Orchard Rd / Bukit Timah flash-flood mechanism.
    drain_capacity_mm: float
    # Fraction of excess rainfall that becomes surface ponding (0–1).
    # With --pluvial-model=fillspill this is only the fallback scalar used
    # when no WorldCover runoff_coeff_<utm>.tif raster exists for the city.
    runoff_coeff: float

    # DEPRECATED (2026-05-21): unused by the catchment-routed fill-spill
    # pluvial model.  Retained only so the legacy --pluvial-model=legacy
    # path keeps working.  See docs/superpowers/specs/
    # 2026-05-21-catchment-routed-pluvial-model-design.md
    depression_area_fraction: float = 0.10

    # ------------------------------------------------------------------
    # OSM place name for river-network query (optional)
    # ------------------------------------------------------------------
    # Used by build_river_raster_from_osm.py (--place) to resolve the OSM
    # administrative boundary for the waterway query.  Defaults to None,
    # which causes run_city_pipeline.py to fall back to the domain bounding
    # box (min_lon/lat, max_lon/lat).
    #
    # Set explicitly when the city's display name resolves to a sub-area of
    # the model domain:
    #   - "Manila" → Manila City proper (~38 km²), NOT Metro Manila (~620 km²)
    #     → use osm_query_name="Metro Manila"
    #   - Most other cities resolve correctly via city.name.
    osm_query_name: str | None = None

    # ------------------------------------------------------------------
    # Optional notes / caveats
    # ------------------------------------------------------------------
    notes: str = ""

    # ------------------------------------------------------------------
    # GloFAS discharge injection (optional)
    # ------------------------------------------------------------------
    # Latitude/longitude of the GloFAS v4 river reach to sample via the
    # Open-Meteo Flood API (flood-api.open-meteo.com).  When set, the
    # fit_fluvial_glofas.py script uses daily discharge from this point
    # rather than ERA5 rainfall → SCS → Manning.  Use for cities where
    # the local ERA5 point cannot represent the upstream basin:
    #   - Large mega-basins (Chao Phraya: 160,000 km²)
    #   - Main-stem rivers where the sub-basin ERA5 fit saturates
    # Leave as None to keep using ERA5-based fluvial fitting.
    glofas_lat: float | None = None
    glofas_lon: float | None = None

    # Multiplicative bias-correction factor applied to raw GloFAS daily
    # discharge before GEV fitting.  Default 1.0 (no correction).
    # Bangkok calibration: Open-Meteo GloFAS overestimates by ~2.4× vs the
    # Royal Irrigation Dept C.2 Nakhon Sawan gauge; set 0.42 to bring the
    # mean annual maximum from ~4 800 to ~2 000 m³/s.
    glofas_discharge_scale: float = 1.0

    # Bankfull discharge (m³/s) used to compute the normal (full-bank) stage
    # that is subtracted from each RP total-depth to give *flood stage above
    # bankfull*.  Required for channels where Manning gives total channel depth
    # rather than inundation depth above the floodplain (flat, managed, or
    # tidal reaches such as the Chao Phraya).
    # Set to None to skip bankfull subtraction (default — suitable for
    # channels that are dry or near-zero at normal flows).
    glofas_bankfull_discharge_m3s: float | None = None


# ======================================================================
# City registry
# ======================================================================

CITIES: dict[str, CityConfig] = {}


def _register(cfg: CityConfig) -> CityConfig:
    CITIES[cfg.slug] = cfg
    return cfg


# ----------------------------------------------------------------------
# Singapore  (reference city — fully validated)
# ----------------------------------------------------------------------
_register(CityConfig(
    name="Singapore",
    slug="singapore",

    min_lon=103.57, min_lat=1.15,
    max_lon=104.10, max_lat=1.50,
    utm_crs="EPSG:32648",       # UTM Zone 48N

    era5_lat=1.2903,
    era5_lon=103.8519,

    uhslc_id=699,
    uhslc_dataset="rqds",
    uhslc_start_year=1984,
    uhslc_end_year=2023,
    uhslc_gauge_name="Tanjong Pagar, Singapore",
    msl_to_egm2008_offset=1.1588,   # CNES-CLS18 interim estimate; run derive_msl_egm2008_offsets.py --write for exact value

    # Compact urban island: dense impervious, small fast-draining catchments
    cn=85.0,
    catchment_km2=10.0,
    time_of_conc_h=0.5,
    channel_width_m=10.0,
    mannings_n=0.040,
    channel_slope=0.002,

    drain_capacity_mm=50.0,     # Effective tertiary/secondary drain capacity.
                                # PUB CoP nominal secondary-drain RP5 standard is 70 mm/1h,
                                # but the tertiary drain tier (which surcharges first) is
                                # closer to RP2 (~40 mm/1h).  50 mm/1h represents the
                                # effective network-wide threshold below which surface ponding
                                # is generally avoided — i.e., the capacity of the limiting
                                # (weakest) tier.  This gives RP5 excess≈20 mm, RP100≈70 mm,
                                # consistent with observed ponding starting from RP5 events
                                # (Orchard Rd 2010-11, Bukit Timah 2017).
                                # 1h IDF anchor: RP10=82mm, RP100=120mm (MSS/PUB published);
                                # Gumbel mu=46mm sigma=16mm.
    runoff_coeff=0.75,

    notes=(
        "Reference city with fully validated parameters.  "
        "Coastal gauge: Tanjong Pagar UHSLC 699 (39-year record).  "
        "PLUVIAL (2026-05-29): drain threshold revised to 50mm/1h (effective tertiary-drain "
        "capacity — the weakest tier that surcharges first).  Replaces 70mm/1h secondary-drain "
        "standard which under-estimated excess for hilly radially-drained terrain.  "
        "MSS 1h IDF Gumbel mu=46mm sigma=16mm.  RP5 excess≈20mm, RP10 excess≈32mm, RP100 excess≈70mm."
    ),
))


# ----------------------------------------------------------------------
# Kuala Lumpur
# ----------------------------------------------------------------------
_register(CityConfig(
    name="Kuala Lumpur",
    slug="kuala_lumpur",

    # Greater KL / Klang Valley extent
    min_lon=101.40, min_lat=2.90,
    max_lon=101.95, max_lat=3.42,
    utm_crs="EPSG:32647",       # UTM Zone 47N

    era5_lat=3.1390,
    era5_lon=101.6869,

    # Kelang (Port Klang) — UHSLC station 140.
    # Confirmed present in UHSLC global_hourly_rqds: 1983-12-15 to 2023-01-06,
    # 303,905 valid hourly observations (~40-year record, good quality).
    # Port Klang is ~35 km south-west of the KL city centre on the Strait of
    # Malacca coast; it is the appropriate coastal reference for the Klang
    # Valley estuary.  KL itself is inland and coastal flooding of the city
    # centre is not modelled; these coastal levels apply only if the study
    # extent is extended to include the lower Klang Valley / Port Klang area.
    uhslc_id=140,
    uhslc_dataset="rqds",
    uhslc_start_year=1984,
    uhslc_end_year=2022,
    uhslc_gauge_name="Kelang (Port Klang), Malaysia — UHSLC 140",
    msl_to_egm2008_offset=1.0226,   # CNES-CLS18 interim estimate; run derive_msl_egm2008_offsets.py --write for exact value

    # Urban Klang / Gombak reach through KL city centre.
    # Manning channel params represent the engineered urban reach:
    #   channel_slope=0.002 — Klang drops ~30 m over 15 km Batu Dam→city
    #   channel_width_m=30  — Sg. Klang / Sg. Gombak, 30–40 m engineered
    cn=82.0,
    catchment_km2=30.0,
    time_of_conc_h=1.5,
    channel_width_m=30.0,
    mannings_n=0.035,
    channel_slope=0.002,

    # GloFAS v4 discharge source: Klang R. at Shah Alam (3.074N, 101.578E).
    # This is ~15 km downstream of KL city centre but is the only public
    # GloFAS reach that captures the full upper Klang basin (~500 km²:
    # upper Sg. Klang + Sg. Gombak + all city-centre tributaries).  The
    # upstream point at Jalan Duta (3.174N, 101.683E, ~50 km²) was tested
    # and rejected: it misses the Gombak and tributary contributions, giving
    # RP2=43 m³/s and Manning stage 1.07 m — too low to produce any HAND
    # model inundation in the deeply incised KL channel (~4-6 m concrete
    # walls).  Shah Alam RP2 ≈ 165 m³/s → Manning stage ~2.4 m, which with
    # bankfull subtraction gives meaningful flood depth progression.
    #
    # Bankfull discharge set to 98 m³/s — the minimum annual maximum in the
    # 28-year GloFAS record (1997-2024).  This is the flow that fills the
    # channel under normal annual high-water conditions (approximately RP1).
    # Manning depth at bankfull ≈ 1.78 m; this is subtracted from each RP
    # total stage to give flood depth above normal water level.
    #
    # Resulting flood depths: RP2 ~0.6 m, RP10 ~1.3 m, RP50 ~2.1 m,
    # RP100 ~2.6 m, RP500 ~3.5 m — physically coherent for a major urban
    # river that causes minor flooding every ~2 years and severe flooding
    # at RP50-100 (consistent with Dec 2021 being described as among the
    # worst events in decades).
    #
    # Caveats documented in cities.py notes and hazard_methodology_comparison:
    #   1. Shah Alam is 15 km downstream: upper-reach HAND flood extents
    #      (Batu Dam area) will be slightly over-estimated.
    #   2. SMART tunnel flood diversion (~90 m³/s capacity) is not modelled;
    #      results are conservative (no flood-relief infrastructure).
    #   3. Both ERA5 and GloFAS use ERA5 precipitation forcing and
    #      underestimate Malaysian tropical convective extremes; Dec 2021
    #      appears as RP~6 in GloFAS vs JPS-implied RP50-100 at basin scale.
    glofas_lat=3.074,
    glofas_lon=101.578,
    glofas_bankfull_discharge_m3s=98.0,

    # JPS Malaysia primary drain design: RP5 ≈ 70 mm / 6 h
    drain_capacity_mm=70.0,
    runoff_coeff=0.75,

    # MERRA-2 wet bias correction for Kuala Lumpur.
    # MERRA-2 mean = 7.141 mm/hr -> implied 62,559 mm/yr vs actual ~2,600 mm/yr.
    # MERRA-2 6h RP2 max = 768 mm vs JPS observed RP2 6h ~80-100 mm.
    # Pluvial: ERA5-Land hourly via Open-Meteo (no bias correction needed).
    depression_area_fraction=0.10,

    notes=(
        "KL is an inland city; coastal hazard is not applicable to the city "
        "centre.  The Kelang (Port Klang) UHSLC gauge (ID 140, confirmed) "
        "provides a 40-year coastal baseline for the Klang Valley estuary -- "
        "use this only if the study extent covers Port Klang / lower Klang Valley.  "
        "FLUVIAL (GloFAS mode since 2026-05-14): GloFAS v4 at Klang R. Shah Alam "
        "(3.074N, 101.578E, ~500 km2 full upper Klang basin). "
        "Bankfull subtraction: Q_bf=98 m3/s (min annual max, ~RP1), "
        "Manning depth at bankfull ~1.78 m. "
        "Flood depth above bankfull: RP2~0.6m, RP10~1.3m, RP50~2.1m, "
        "RP100~2.6m, RP500~3.5m. "
        "Caveat: Shah Alam is 15 km downstream of KL city centre (downstream "
        "proxy); SMART tunnel diversion ~90 m3/s not modelled (conservative). "
        "Upstream Jalan Duta point (3.174N, 101.683E, ~50 km2) was tested and "
        "rejected: RP2=43 m3/s, stage=1.07 m -- too low for HAND inundation in "
        "the deeply incised engineered channel. "
        "VALIDATION (2026-05-13, Option B): GloFAS classifies Dec 2021 as RP~6 "
        "at all scales; JPS danger-level exceedances imply RP50-100 at basin "
        "scale -- ERA5 precipitation underestimation of Malaysian tropical "
        "convective extremes confirmed. "
        "PLUVIAL: ERA5-Land hourly via Open-Meteo (no bias correction). "
        "PLUVIAL VALIDATION (2026-04-26): ERA5-Land 6h RP2=43.6mm vs JPS "
        "anchor ~90mm (-51.5%; FAIL); ERA5-Land sub-grid convective deficit."
    ),
))


# ----------------------------------------------------------------------
# Bangkok
# ----------------------------------------------------------------------
_register(CityConfig(
    name="Bangkok",
    slug="bangkok",

    # Greater Bangkok Metropolitan Region (BMR)
    min_lon=100.20, min_lat=13.40,
    max_lon=100.90, max_lat=14.05,
    utm_crs="EPSG:32647",       # UTM Zone 47N

    era5_lat=13.7563,
    era5_lon=100.5018,

    # Ko Lak — UHSLC station 328, fast-delivery dataset (confirmed).
    # Thailand has no Research Quality (rqds) UHSLC stations; Ko Lak is
    # present only in the fast-delivery (global_hourly_fast) dataset.
    # Record: 1985-01-01 to 2025-12-31, 344,368 valid hourly obs (~41 years,
    # 96% coverage) — well suited for GEV fitting.
    # Position: 11.795°N, 99.817°E — Gulf of Thailand coast, ~280 km south
    # of Bangkok/Samut Prakan.  Tidal and surge climatology in the upper
    # Gulf of Thailand is relatively uniform along-coast, making Ko Lak an
    # acceptable proxy for Bangkok's coastal water-level extremes.
    # Use dataset="fast" when calling fetch_gesla_singapore.py.
    uhslc_id=328,
    uhslc_dataset="fast",
    uhslc_start_year=1985,
    uhslc_end_year=2024,
    uhslc_gauge_name="Ko Lak, Thailand — UHSLC 328 (fast-delivery)",
    msl_to_egm2008_offset=1.1785,   # CNES-CLS18 interim estimate; run derive_msl_egm2008_offsets.py --write for exact value

    # Local Bangkok klong (canal) drainage parameters.
    # The Chao Phraya main river (catchment >100,000 km²) cannot be modelled
    # from ERA5 alone — its upstream flood signal is omitted here (see notes).
    # These parameters represent a typical Bangkok urban sub-basin draining
    # into a primary klong: ~5 km², fast response, concrete-lined canal with
    # a designed slope of 0.002 m/m (far steeper than the Chao Phraya at
    # 0.00005 m/m, but representative of engineered urban drainage).
    cn=80.0,
    catchment_km2=5.0,
    time_of_conc_h=0.5,
    channel_width_m=15.0,
    mannings_n=0.025,
    channel_slope=0.002,

    # Bangkok primary klong drainage capacity.
    # Primary klongs (Prem Prachakon, Prapa, Chao Phraya relief canals) are
    # engineered to convey approximately RP5–RP10 storms without surface
    # ponding.  RP5 6h design rainfall for Bangkok ≈ 80–90 mm (TMD IDF).
    # 80 mm / 6 h is used as the primary-drain threshold; rainfall below
    # this conveys without surface flooding.  Secondary and tertiary drains
    # (designed for RP2–RP5) will pond at lower intensities, but those
    # sub-grid failure modes are captured by the runoff_coeff.
    drain_capacity_mm=80.0,
    runoff_coeff=0.80,

    # MERRA-2 wet bias correction for Bangkok.
    # Pluvial: ERA5-Land hourly via Open-Meteo (no bias correction needed).
    # Bangkok is a low-relief delta, so use a higher depression_area_fraction
    # (broader pondable area).  VALIDATION (2026-04-26): ERA5-Land 6h GEV RP5 =
    # 39.7 mm vs TMD anchor ~85 mm (-53.3%; FAIL).  See KL note for the same
    # ~50% reanalysis-vs-IDF deficit pattern across SEA tropical cities.
    depression_area_fraction=0.15,

    notes=(
        "COASTAL: Ko Lak (UHSLC 328, fast-delivery) is a 41-year Gulf of "
        "Thailand record confirmed by live query.  It is ~280 km south of "
        "Bangkok; the along-coast surge climatology is consistent enough for "
        "a screening model.  No RQ station exists for Thailand.  "
        "AR6 SLR delta at P50 SSP5-8.5 2100 = 1.625 m (AR6 station at 13.55N "
        "100.58E, only 21 km from Bangkok centroid; confirmed correct).  This "
        "large delta reflects regional ocean dynamics in the Gulf of Thailand "
        "above the global mean (~0.77 m).  Under this scenario Bangkok's RP2 "
        "coastal water level is ~2.97 m — most of the delta (0–2 m DEM) floods "
        "even at RP2.  This is physically correct for SSP5-8.5 2100 P50.  "
        "For maps with more RP differentiation use --horizon 2050 or "
        "--scenario SSP2-4.5.  "
        "FLUVIAL: Parameters represent local urban klong drainage (~5 km2 "
        "sub-basin, designed slope 0.002 m/m), NOT the Chao Phraya main river "
        "(>100,000 km2 upstream catchment).  The 2011 mega-flood was driven by "
        "months of rainfall across northern Thailand — supplement with RID "
        "hydrological model outputs for a full fluvial assessment.  "
        "SUBSIDENCE: Bangkok subsides at 2-5 cm/yr in parts of the north; "
        "consider adding a subsidence correction to coastal water levels."
    ),
))


# ----------------------------------------------------------------------
# Bangkok — Chao Phraya mainstem supplementary config
#
# Addresses the upstream-hydrology gap of the `bangkok` config, which
# represents only a local urban klong (~5 km², S=0.002 m/m) and CANNOT
# capture flooding driven by rainfall over the Chao Phraya basin
# (catchment ≈ 160,000 km² to Bangkok; 2011 mega-flood: ~6,000 m³/s
# peak, two months of inundation).
#
# ERA5 / MERRA-2 precipitation extracted at the Bangkok grid cell does
# not represent the upstream basin's rainfall — so the ERA5 fluvial fit
# step (`fit_fluvial_baseline_era5.py`) is not physically meaningful for
# the Chao Phraya mainstem.  Use this config in conjunction with GloFAS
# Reanalysis discharge return periods (Copernicus CDS, dataset
# "cems-glofas-historical"; station: Chao Phraya at Bang Sai or Nakhon
# Sawan) and inject the resulting stage rows MANUALLY into
# `data/bangkok_chao_phraya/hazard_baseline_template.csv` before
# running the pipeline with --no-fit-era5.
#
# Public sources required:
#   - GloFAS v4 Reanalysis 1979-present  (Copernicus CDS, CC-BY-4.0)
#   - Royal Irrigation Dept (RID) rating curve for the chosen station
#   - For climate scaling: GloFAS reforecast under SSP5-8.5
#     (CMIP6-driven, dataset "cems-glofas-seasonal-reforecast")
# ----------------------------------------------------------------------
_register(CityConfig(
    name="Bangkok (Chao Phraya mainstem)",
    slug="bangkok_chao_phraya",

    min_lon=100.30, min_lat=13.55,
    max_lon=100.85, max_lat=14.00,
    utm_crs="EPSG:32647",       # UTM Zone 47N

    era5_lat=13.7563,
    era5_lon=100.5018,

    # Same Ko Lak gauge as `bangkok` (no separate coastal regime).
    uhslc_id=328,
    uhslc_dataset="fast",
    uhslc_start_year=1985,
    uhslc_end_year=2024,
    uhslc_gauge_name="Ko Lak, Thailand — UHSLC 328 (fast-delivery)",
    msl_to_egm2008_offset=1.1785,   # CNES-CLS18 interim estimate; run derive_msl_egm2008_offsets.py --write for exact value

    # Chao Phraya mainstem at Bangkok — large, flat, slow-responding river.
    #   catchment_km2 = 160,000  (full upstream Chao Phraya to Bangkok)
    #   time_of_conc_h = 168 h (~ 7 days flood-wave travel from Nakhon Sawan)
    #   channel_width_m = 350 m at Bangkok cross-section
    #   mannings_n = 0.035 (natural earthen banks, vegetated berms)
    #   channel_slope = 0.00005 m/m (extreme delta gradient, ~5 cm / km)
    # NOTE: cn / catchment-derived peak discharge from ERA5 will be
    # WRONG for this configuration — supply GloFAS-derived RPs manually.
    cn=82.0,
    catchment_km2=160000.0,
    time_of_conc_h=168.0,
    channel_width_m=350.0,
    mannings_n=0.035,
    channel_slope=0.00005,

    drain_capacity_mm=80.0,
    runoff_coeff=0.80,

    # Pluvial: ERA5-Land via Open-Meteo. Mainstem Chao Phraya delta -> higher daf.
    depression_area_fraction=0.15,

    notes=(
        "SUPPLEMENTARY CONFIG — addresses the upstream-hydrology gap of "
        "the `bangkok` config.  Represents the Chao Phraya mainstem, "
        "NOT a local klong.  ERA5/MERRA-2 cannot model upstream basin "
        "rainfall; the ERA5 fluvial fit step IS NOT meaningful here "
        "(auto-suppressed since glofas_lat is set).  "
        "GLOFAS CALIBRATION WARNING (2026-05-10): GloFAS v4 at "
        "(14.45, 100.45) returns mean annual max ~4,800 m³/s — approximately "
        "2x the C.2 Nakhon Sawan gauge (historical RP100 ~3,500-4,500 m3/s). "
        "Manning's equation on this very flat reach (S=5e-5) produces total "
        "channel depth (~12 m at RP2), NOT flood stage above bankfull.  "
        "Current GloFAS baseline stages (RP2=12 m, RP25+=20 m capped) will "
        "over-inundate the HAND model and are NOT suitable for hazard maps "
        "without rating-curve calibration.  CORRECT APPROACH: calibrate "
        "against the RID C.2 Nakhon Sawan gauge, subtract baseflow stage, "
        "and use a tidal-adjusted stage-discharge relationship.  "
        "COASTAL: Ko Lak gauge inherited from `bangkok` "
        "(see those notes for AR6 SLR caveats).  COMPOSITE: Stack with "
        "the `bangkok` outputs via depth-max mosaicking (same pattern "
        "as Greater Jakarta / Greater KL composites) to capture both "
        "klong-scale and mainstem flooding."
    ),

    # Chao Phraya near Chai Nat / Ang Thong — above tidal influence and well within
    # the main routing channel of GloFAS v4.  Previous coordinate (14.20, 100.35)
    # snapped to a dry GloFAS cell (mean 0.4 m³/s, off-reach); this coordinate
    # (14.45, 100.45) sits on the main Chao Phraya stem after the Ping/Wang/Yom/Nan
    # confluence, returning mean annual max ~4,800 m³/s consistent with the 2011
    # megaflood (~7,500 m³/s peak at this reach).
    # Nominatim cannot geocode "Bangkok (Chao Phraya mainstem)"; use "Bangkok" instead.
    osm_query_name="Bangkok",

    glofas_lat=14.45,
    glofas_lon=100.45,
    # Bias correction: GloFAS overestimates by ~2.4× vs RID C.2 Nakhon Sawan.
    # Scale factor 0.42 brings mean annual max from ~4,800 to ~2,000 m³/s,
    # consistent with gauge records (historical RP100 ≈ 3,500–4,500 m³/s).
    glofas_discharge_scale=0.42,
    # Bankfull discharge for stage-above-bankfull conversion.
    # Manning(1800 m³/s, w=200m, n=0.032, S=5e-5) ≈ 7.4 m total depth.
    # Subtracting this from RP stages gives flood depth above normal water level,
    # compatible with the HAND model which is also height above nearest drainage.
    # Result: RP5≈1.4m, RP10≈2.4m, RP25≈3.8m, RP100≈6.0m — consistent with
    # documented Bangkok flood depths (2011 outer-suburb inundation ~1.5–3m).
    glofas_bankfull_discharge_m3s=1800.0,
))


# ----------------------------------------------------------------------
# Klang Valley West — Shah Alam / Klang town
# Addresses the single-representative-reach limitation for the outer
# western Klang Valley (Shah Alam, Klang town) which is NOT well
# represented by the kuala_lumpur config (calibrated to the steep
# upper-Klang / Gombak reach through KL city centre, A=30 km²,
# S=0.002 m/m).
#
# This config represents the MIDDLE Klang reach from Petaling Jaya /
# Subang through Shah Alam to Klang town:
#   catchment_km2=50  — a primary Klang sub-tributary sub-basin
#                        draining to the middle reach (~50 km²; not the
#                        full ~800–1,288 km² Klang basin).
#   channel_slope=0.001 — Klang River drops ~20 m over ~20 km from
#                          Petaling Jaya to Shah Alam (0.001 m/m),
#                          considerably flatter than the city-centre
#                          reach (0.002 m/m).
#   channel_width_m=40  — widened engineered channel in the Shah Alam
#                          / Klang corridor (40–50 m typical).
#   time_of_conc_h=2.0  — consistent with a 50 km² urban catchment.
# Pre-verified: RP1000 stage ≈ 4.4 m, well below 8 m cap with
# meaningful RP-to-RP progression.
# ----------------------------------------------------------------------
_register(CityConfig(
    name="Shah Alam",
    slug="klang_shah_alam",

    # Western Klang Valley: Shah Alam, Klang town, Subang/Petaling Jaya
    min_lon=101.35, min_lat=2.95,
    max_lon=101.65, max_lat=3.20,
    utm_crs="EPSG:32647",       # UTM Zone 47N

    era5_lat=3.070,
    era5_lon=101.515,

    # Same coastal gauge as kuala_lumpur — Port Klang (UHSLC 140) is
    # the estuary reference for the full Klang Valley including Shah Alam
    # and Klang town.
    uhslc_id=140,
    uhslc_dataset="rqds",
    uhslc_start_year=1984,
    uhslc_end_year=2022,
    uhslc_gauge_name="Kelang (Port Klang), Malaysia — UHSLC 140",
    msl_to_egm2008_offset=1.0226,   # CNES-CLS18 interim estimate; run derive_msl_egm2008_offsets.py --write for exact value

    # Middle Klang reach through Shah Alam
    cn=80.0,
    catchment_km2=50.0,
    time_of_conc_h=2.0,
    channel_width_m=40.0,
    mannings_n=0.035,
    channel_slope=0.001,

    drain_capacity_mm=70.0,    # JPS Malaysia primary drain RP5 standard
    runoff_coeff=0.75,

    depression_area_fraction=0.10,   # Pluvial: ERA5-Land via Open-Meteo. Same KL urban tier.

    notes=(
        "SUPPLEMENTARY CONFIG — addresses the single-representative-reach "
        "limitation of the kuala_lumpur config.  "
        "Represents the middle Klang corridor (Shah Alam, Klang town, "
        "Subang/Petaling Jaya) where the main Klang River has a larger "
        "catchment (~800 km² at Klang town) and flatter gradient than the "
        "KL city-centre reach.  Parameters are calibrated to a representative "
        "50 km² urban sub-tributary, NOT the full Klang basin.  "
        "ERA5 capture point is at Shah Alam (3.07°N 101.52°E).  "
        "COASTAL: Port Klang UHSLC 140 is the direct estuary reference for "
        "this sub-region (Klang town IS at the Klang River mouth).  "
        "PLUVIAL: ERA5-Land via Open-Meteo. VALIDATION (2026-04-26): "
        "ERA5-Land 6h GEV RP2 = 45.5 mm vs JPS anchor ~90 mm (-49.4%; FAIL). "
        "See kuala_lumpur note for the SEA reanalysis-vs-IDF deficit context."
    ),
))


# ----------------------------------------------------------------------
# Langat Basin — Putrajaya / Kajang / Bangi / Sepang
# Addresses the single-representative-reach limitation for the areas
# that drain to the Langat River (a SEPARATE watershed from the Klang).
#
# The Langat basin (~2,350 km² total) is entirely outside the Klang
# drainage and therefore receives no fluvial signal from either the
# kuala_lumpur or klang_shah_alam configs.  Key urban areas: Putrajaya
# (federal capital), Kajang, Bangi, Cyberjaya, Sepang (KLIA).
#
# This config represents an upper Langat urban tributary:
#   catchment_km2=25  — representative urban sub-basin draining into
#                        the upper Langat / Sg. Semenyih area (~25 km²).
#   channel_slope=0.0018 — Langat upper reach near Kajang drops
#                           ~20 m over ~11 km (0.0018 m/m).
#   channel_width_m=20   — typical upper-reach channel width.
#   time_of_conc_h=1.25  — consistent with 25 km² urban catchment.
# Pre-verified: RP1000 stage ≈ 3.8 m, well below 8 m cap.
# ----------------------------------------------------------------------
_register(CityConfig(
    name="Kajang",
    slug="subang_langat",

    # Langat basin: Putrajaya, Kajang, Bangi, Cyberjaya, Sepang
    min_lon=101.60, min_lat=2.85,
    max_lon=101.92, max_lat=3.12,
    utm_crs="EPSG:32647",       # UTM Zone 47N

    era5_lat=2.975,
    era5_lon=101.760,

    # Closest available UHSLC gauge: Port Klang (UHSLC 140).
    # The Langat River discharges to the Strait of Malacca near Banting,
    # ~50 km south of Port Klang.  The along-coast tidal climatology is
    # similar (microtidal, ~0.8–1.0 m range) so Port Klang is an
    # acceptable proxy for a screening model.  No UHSLC gauge exists
    # at the Langat estuary.
    uhslc_id=140,
    uhslc_dataset="rqds",
    uhslc_start_year=1984,
    uhslc_end_year=2022,
    uhslc_gauge_name="Kelang (Port Klang), Malaysia — UHSLC 140",
    msl_to_egm2008_offset=1.0226,   # CNES-CLS18 interim estimate; run derive_msl_egm2008_offsets.py --write for exact value

    # Upper Langat urban tributary (Kajang / Sg. Semenyih reach)
    cn=80.0,
    catchment_km2=25.0,
    time_of_conc_h=1.25,
    channel_width_m=20.0,
    mannings_n=0.035,
    channel_slope=0.0018,

    drain_capacity_mm=70.0,    # JPS Malaysia primary drain RP5 standard
    runoff_coeff=0.75,

    depression_area_fraction=0.10,   # Pluvial: ERA5-Land via Open-Meteo. Upper Langat urban tier.

    notes=(
        "SUPPLEMENTARY CONFIG — covers the Langat River basin, which is a "
        "SEPARATE watershed from the Klang River (kuala_lumpur / "
        "klang_shah_alam configs) and receives zero fluvial signal from those "
        "configs.  Key areas: Putrajaya, Kajang, Bangi, Cyberjaya, Sepang, "
        "KLIA.  Parameters calibrated to a representative 25 km² upper-Langat "
        "urban sub-tributary.  Langat total upstream catchment is ~2,350 km²; "
        "single-reach limitation still applies for basin-wide flooding events.  "
        "ERA5 capture point at Kajang/Putrajaya (2.975°N 101.760°E).  "
        "COASTAL: Port Klang UHSLC 140 used as proxy (no Langat-estuary gauge "
        "in UHSLC); Banting coast ~50 km south, tidal range comparable.  "
        "PLUVIAL: ERA5-Land via Open-Meteo. VALIDATION (2026-04-26): "
        "ERA5-Land 6h GEV RP2 = 43.7 mm vs JPS anchor ~90 mm (-51.5%; FAIL). "
        "See kuala_lumpur note for the SEA reanalysis-vs-IDF deficit context."
    ),
))


# ----------------------------------------------------------------------
# Tangerang — western Jakarta metro (Cisadane / Kali Angke corridor)
# Addresses the single-representative-reach limitation of the jakarta
# config for the western sub-region.
#
# The jakarta config represents Kali Cideng / Krukut (central Jakarta,
# ~10 km², S=0.0015 m/m).  Tangerang is drained by:
#   • Sungai Cisadane  — ~1,400 km² total catchment; enters the coast
#                        west of Soekarno-Hatta airport
#   • Kali Angke       — urban western Tangerang / Cengkareng, ~30–50 km²
#   • Kali Pesanggrahan — southern Tangerang / BSD area
# Parameters represent a Kali Angke urban sub-basin reach:
#   catchment_km2=20  — representative upper urban tributary
#   channel_slope=0.0010 — Tangerang coastal plain is flatter than
#                          central Jakarta (0.0010 vs 0.0015 m/m)
#   channel_width_m=20   — typical engineered canal in western Tangerang
#   time_of_conc_h=1.0   — consistent with 20 km² urban catchment
# Pre-verified: RP1000 stage ≈ 3.7 m, well below 8 m cap.
# ----------------------------------------------------------------------
_register(CityConfig(
    name="Tangerang",
    slug="tangerang",

    # Kota Tangerang, Tangerang Selatan, coastal strip near Soekarno-Hatta
    min_lon=106.45, min_lat=-6.45,
    max_lon=106.80, max_lat=-6.05,
    utm_crs="EPSG:32748",       # UTM Zone 48S

    era5_lat=-6.225,
    era5_lon=106.625,

    # Same bay as Jakarta — UHSLC 161 Tanjung Priok is the appropriate
    # coastal reference for the northern Tangerang coast (Teluk Jakarta).
    uhslc_id=161,
    uhslc_dataset="rqds",
    uhslc_start_year=1984,
    uhslc_end_year=2004,
    uhslc_gauge_name="Jakarta (Tanjung Priok), Indonesia — UHSLC 161",
    msl_to_egm2008_offset=0.9976,   # CNES-CLS18 interim estimate; run derive_msl_egm2008_offsets.py --write for exact value

    # Kali Angke representative urban reach (western Tangerang / Cengkareng)
    cn=82.0,
    catchment_km2=20.0,
    time_of_conc_h=1.0,
    channel_width_m=20.0,
    mannings_n=0.035,
    channel_slope=0.0010,

    drain_capacity_mm=45.0,    # Same as Jakarta primary canal standard
    runoff_coeff=0.80,

    # Pluvial: ERA5-Land via Open-Meteo. Tangerang coastal plain -> delta tier.
    depression_area_fraction=0.15,

    notes=(
        "SUPPLEMENTARY CONFIG — addresses the single-representative-reach "
        "limitation of the jakarta config for the western sub-region.  "
        "Represents the Kali Angke / western Tangerang urban tributary system.  "
        "Full Cisadane catchment (~1,400 km²) and Kali Angke sub-basin cannot "
        "be modelled from ERA5 alone; parameters represent a 20 km² urban reach.  "
        "COASTAL: UHSLC 161 (Tanjung Priok) is the Jakarta Bay reference — "
        "applicable to northern Tangerang coast (Soekarno-Hatta airport area).  "
        "SUBSIDENCE: Apply --subsidence-correction; North Tangerang rates are "
        "comparable to North Jakarta (literature suggests 3-8 cm/yr in "
        "Cengkareng / Penjaringan area).  "
        "PLUVIAL: ERA5-Land via Open-Meteo. VALIDATION (2026-04-26): "
        "ERA5-Land 6h GEV RP2 = 34.1 mm vs BMKG anchor ~85 mm (-59.8%; FAIL). "
        "See jakarta note for the SEA reanalysis-vs-IDF deficit context."
    ),
))


# ----------------------------------------------------------------------
# Bekasi / Depok — eastern Jakarta metro
# Addresses the single-representative-reach limitation of the jakarta
# config for the eastern and south-eastern sub-region.
#
# Key river systems:
#   • Sungai Bekasi / Cileungsi — ~1,200 km² catchment draining the
#     Bogor highlands through Bekasi city to Jakarta Bay
#   • Sungai Ciliwung — ~370 km² drains through Depok and south Jakarta
#     (the river that caused Jakarta's historic 2002, 2007, 2013 floods)
#   • Kali Sunter     — urban eastern Jakarta drain (~100 km² sub-basin)
# Parameters represent a Sungai Bekasi urban reach through Kota Bekasi:
#   catchment_km2=30  — representative upper urban tributary in Bekasi city
#   channel_slope=0.0012 — moderate gradient for the Bekasi piedmont area
#   channel_width_m=25   — wider engineered channel than central Jakarta
#   time_of_conc_h=1.25  — consistent with 30 km² urban catchment
# Pre-verified: RP1000 stage ≈ 3.5 m, well below 8 m cap.
# ----------------------------------------------------------------------
_register(CityConfig(
    name="Bekasi",
    slug="bekasi_depok",

    # Kota Bekasi, Kabupaten Bekasi (western), Depok, southern Ciliwung corridor
    min_lon=106.85, min_lat=-6.55,
    max_lon=107.15, max_lat=-6.10,
    utm_crs="EPSG:32748",       # UTM Zone 48S

    era5_lat=-6.300,
    era5_lon=107.000,

    # Northern Bekasi borders Jakarta Bay; UHSLC 161 (Tanjung Priok) is the
    # closest available coastal reference for the Bekasi coast.
    uhslc_id=161,
    uhslc_dataset="rqds",
    uhslc_start_year=1984,
    uhslc_end_year=2004,
    uhslc_gauge_name="Jakarta (Tanjung Priok), Indonesia — UHSLC 161",
    msl_to_egm2008_offset=0.9976,   # CNES-CLS18 interim estimate; run derive_msl_egm2008_offsets.py --write for exact value

    # Sungai Bekasi representative urban reach (Kota Bekasi / Cileungsi).
    # ERA5 at this grid point (-6.30N 107.00E) yields 24h annual maxima
    # ~34% higher than the Jakarta point (mean 214mm vs 160mm), likely
    # reflecting Bogor-foothill convective enhancement.  Steeper slope
    # (0.0015 vs 0.0012) and smaller catchment (20 km²) prevent the
    # Manning stage from saturating the 8 m model cap at high RPs.
    cn=82.0,
    catchment_km2=20.0,
    time_of_conc_h=1.0,
    channel_width_m=25.0,
    mannings_n=0.033,
    channel_slope=0.0015,

    drain_capacity_mm=45.0,    # Same as Jakarta primary canal standard
    runoff_coeff=0.80,

    # Pluvial: ERA5-Land via Open-Meteo. Bekasi/Depok coastal-piedmont -> delta tier.
    depression_area_fraction=0.15,

    notes=(
        "SUPPLEMENTARY CONFIG — addresses the single-representative-reach "
        "limitation of the jakarta config for the eastern/south-eastern "
        "sub-region (Bekasi, Depok, Ciliwung corridor).  "
        "Sungai Bekasi drains ~1,200 km² from the Bogor highlands; Sungai "
        "Ciliwung drains ~370 km² through Depok and south-central Jakarta — "
        "both far exceed the 10 km² Kali Cideng model in the jakarta config.  "
        "Parameters represent a 30 km² Bekasi urban reach; the Ciliwung "
        "main-stem signal (upstream basin forcing from Bogor / Puncak) is NOT "
        "captured by the ERA5 single-point approach.  "
        "COASTAL: UHSLC 161 used as proxy for northern Bekasi coast "
        "(Muaragembong / Tarumajaya area); same Jakarta Bay tidal regime.  "
        "PLUVIAL: ERA5-Land via Open-Meteo. VALIDATION (2026-04-26): "
        "ERA5-Land 6h GEV RP2 = 32.3 mm vs BMKG anchor ~85 mm (-62.0%; FAIL). "
        "See jakarta note for the SEA reanalysis-vs-IDF deficit context."
    ),
))


# ----------------------------------------------------------------------
# Jakarta
# ----------------------------------------------------------------------
_register(CityConfig(
    name="Jakarta",
    slug="jakarta",

    # DKI Jakarta + immediate surroundings
    min_lon=106.60, min_lat=-6.45,
    max_lon=107.05, max_lat=-5.90,
    utm_crs="EPSG:32748",       # UTM Zone 48S (southern hemisphere)

    era5_lat=-6.2088,
    era5_lon=106.8456,

    # Jakarta — UHSLC station 161, confirmed present in global_hourly_rqds.
    # Station coordinates: -6.117°N, 106.850°E (Tanjung Priok area).
    # Record: 1984-01-01 to 2004-09-18 (~20 years, 112,900 valid hours).
    # The record ends in 2004; GEV fitting on 20 annual maxima is at the
    # lower bound of reliability.  Treat extreme return periods (RP500,
    # RP1000) with extra caution.  Consider supplementing with GESLA-3
    # which may carry the Jakarta gauge record further into the 2000s.
    # Tidal range in Jakarta Bay: ~0.8–1.0 m (microtidal).
    uhslc_id=161,
    uhslc_dataset="rqds",
    uhslc_start_year=1984,
    uhslc_end_year=2004,
    uhslc_gauge_name="Jakarta (Tanjung Priok area), Indonesia — UHSLC 161",
    msl_to_egm2008_offset=0.9976,   # CNES-CLS18 interim estimate; run derive_msl_egm2008_offsets.py --write for exact value

    # Representative small urban tributary — Kali Cideng / Kali Krukut,
    # Central Jakarta.  These drains receive runoff from ~10 km² sub-basins
    # in the Gambir / Kebayoran area and are engineered canals 12–18 m wide.
    #
    # WHY NOT catchment_km2=60 / slope=0.0005 (the previous values):
    #   The full-city A=60 km² combined with the near-flat coastal-plain
    #   gradient (0.0005 m/m) caused Manning's normal-depth stages to exceed
    #   8 m from RP2 onwards — the 8 m model cap was hit at every return period
    #   and all RP50–RP1000 maps were identical and invalid.
    #
    # REVISED APPROACH (same fix applied to Bangkok and KL):
    #   Represent a single manageable urban tributary, not the entire Ciliwung.
    #   catchment_km2=10  — Kali Cideng catchment area (upper sub-basin)
    #   time_of_conc_h=0.75 — consistent with a 10 km² urban catchment
    #   channel_slope=0.0015 — engineered upper-reach slope from Gambir to
    #                          Hayam Wuruk canal; the coastal-plain gradient
    #                          (0.0005 m/m) applies only to the lower few km.
    # This gives RP10 bankfull ≈ 1.6 m and RP1000 stage ≈ 2.9 m — well
    # within the 8 m cap with meaningful RP-to-RP progression.
    cn=82.0,
    catchment_km2=10.0,
    time_of_conc_h=0.75,
    # channel_width_m=25 — Ciliwung main channel at the Depok / South Jakarta boundary
    # (~25–35 m observed from satellite at -6.35, 106.84).  Since glofas_lat is set,
    # ERA5 fluvial is auto-suppressed and this width is used only by fit_fluvial_glofas.py.
    # Previous value 15 m (Kali Cideng upper canal) caused w/d < 5 violations at all
    # return periods when GloFAS discharge (~100–400 m³/s) was applied.
    channel_width_m=25.0,
    mannings_n=0.033,
    channel_slope=0.0015,

    # Jakarta primary canal (Banjir Kanal) design capacity: approximately
    # RP5 for local rainfall.  45 mm / 6 h is a reasonable primary drain
    # threshold for the engineered network; tertiary drains are far weaker.
    drain_capacity_mm=45.0,
    runoff_coeff=0.80,

    # MERRA-2 wet bias correction for Jakarta.
    # MERRA-2 mean = 6.088 mm/hr -> implied 53,332 mm/yr vs actual ~1,800 mm/yr.
    # MERRA-2 6h RP2 max = 748 mm vs BMKG observed RP2 6h ~85 mm.
    # Pluvial: ERA5-Land hourly via Open-Meteo (no bias correction needed).
    # Jakarta is a flat coastal delta -> delta tier.
    depression_area_fraction=0.15,

    notes=(
        "COASTAL: UHSLC station 161 (Jakarta/Tanjung Priok) confirmed, but "
        "record ends 2004 (~20 annual maxima only).  GEV fit at RP500/RP1000 "
        "is highly uncertain — treat as indicative.  Current baseline CSV "
        "uses Muis et al. (2016) literature values; re-run fetch_gesla step "
        "to replace with UHSLC data.  "
        "SUBSIDENCE: North Jakarta is subsiding at up to 25 cm/yr.  The "
        "Copernicus GLO-30 DEM (2011–2015) is estimated 0.5–2.0 m too high "
        "vs current reality; coastal and fluvial flood extents are likely "
        "underestimated without a subsidence-adjusted DEM.  "
        "FLUVIAL: Parameters represent Kali Cideng / Kali Krukut — a "
        "representative small (~10 km²) Jakarta urban tributary in the Gambir "
        "/ Hayam Wuruk corridor.  Previous params (A=60 km², S=0.0005) caused "
        "Manning's stage saturation at the 8 m cap from RP2 onwards; revised "
        "to A=10 km² + S=0.0015 (engineered upper-reach slope).  ERA5 captures "
        "local convective rainfall but not Ciliwung upstream basin forcing.  "
        "PLUVIAL: ERA5-Land hourly via Open-Meteo (no bias correction). "
        "VALIDATION (2026-04-26): ERA5-Land 6h GEV RP2 = 33.3 mm vs BMKG "
        "anchor ~85 mm (-60.8%; FAIL). The ~60% deficit reflects ERA5-Land's "
        "known limitation in resolving sub-grid tropical convective extremes "
        "at ~9 km resolution; BMKG IDF curves may also include engineering "
        "safety factors. No multiplicative correction is applied. Defer "
        "final validation to R4 historical-event runs (e.g. Jakarta 2020 EMSR432)."
    ),

    # Ciliwung River at the Depok / South Jakarta boundary — larger GloFAS accumulation
    # cell than the previous coordinate (-6.50, 106.83) which snapped to a small
    # headwater sub-cell (mean 11 m³/s, max 75 m³/s).  This coordinate (-6.35, 106.84)
    # returns mean annual max ~127 m³/s, consistent with PU/BWSCC estimates of
    # ~100–250 m³/s for RP100 on the Ciliwung at the urban interface.
    glofas_lat=-6.35,
    glofas_lon=106.84,
))


# ======================================================================
# ASEAN EXPANSION — P0 PRIORITY CITIES
# ======================================================================

# ----------------------------------------------------------------------
# Manila, Philippines
#
# P0 priority (highest): large population, strong data availability,
# severe multi-hazard exposure (typhoon storm surge + Pasig/Marikina
# fluvial + intense convective pluvial).
#
# Key river systems:
#   • Pasig River — ~572 km² catchment draining Laguna de Bay into
#     Manila Bay; historically canalised through Metro Manila CBD.
#   • Marikina River — ~540 km² sub-catchment of the Pasig system;
#     primary fluvial flood driver in Marikina City, Cainta, Pasig.
#     Extreme rainfall from typhoons can produce >20 m gage readings
#     at the Marikina Water Level Station (LCR-24 h peak).
#   • Manila Bay coast — microtidal (~0.7 m range); typhoon storm surge
#     up to 2–3 m (Ondoy 2009 peak surge ≈ 1.5 m at Intramuros).
#
# UHSLC gauge identification:
#   Candidate: Manila (Fort Santiago / Manila Observatory).
#   Verify station ID and record availability at the UHSLC data portal:
#     https://uhslc.soest.hawaii.edu/data/?rq
#   NOTE: uhslc_id is set to None until confirmed — the pipeline will
#   skip the coastal fetch step.  Populate coastal rows manually using
#   PAGASA observed storm surge data or NAMRIA tide tables, then run
#   with --no-fit-coastal.
#
# Pluvial driver:
#   ERA5-Land hourly via Open-Meteo (no bias correction needed).  Metro
#   Manila mean annual rainfall ~ 2,000 mm/yr (PAGASA).  See VALIDATION
#   line in `notes` below for the ERA5-Land vs PAGASA IDF anchor outcome.
# ----------------------------------------------------------------------
_register(CityConfig(
    name="Manila",
    slug="manila",

    # Metro Manila (NCR) + immediate fringe
    min_lon=120.85, min_lat=14.30,
    max_lon=121.25, max_lat=14.85,
    utm_crs="EPSG:32651",       # UTM Zone 51N

    era5_lat=14.5995,
    era5_lon=120.9842,

    # UHSLC Research Quality gauge 304 — Manila (Fort Santiago).
    # Confirmed present in global_hourly_rqds; record spans ~1970s-2020s.
    # Position: 14.583°N, 120.967°E (Manila Bay, inside bay — microtidal,
    # ~0.7 m range; storm surge up to ~2 m from typhoons).
    # msl_to_egm2008_offset: CNES-CLS18 MDT interim estimate +0.25 m
    # (South China Sea / Manila Bay at ~14.6°N; run
    # derive_msl_egm2008_offsets.py --write for exact value).
    uhslc_id=304,
    uhslc_dataset="rqds",
    uhslc_start_year=1985,
    uhslc_end_year=2024,
    uhslc_gauge_name="Manila (Fort Santiago), Philippines — UHSLC 304",
    msl_to_egm2008_offset=1.1292,   # CNES-CLS18 interim estimate; run derive_msl_egm2008_offsets.py --write for exact value

    # Marikina River representative urban reach (through Marikina City).
    # Parameters represent a 50 km² sub-catchment of the Marikina / Pasig
    # system — NOT the full ~572 km² Pasig basin.  Full-basin ERA5 fitting
    # is inappropriate; supplement with DPWH / Project NOAH FloodMap or
    # GloFAS Reanalysis for the Marikina main-stem.
    #
    #   cn=85        — dense Metro Manila impervious cover (Class B/C soils)
    #   catchment_km2=50  — Marikina sub-basin through Marikina City CBD
    #   time_of_conc_h=1.5 — urban 50 km² → ~1.5 h Tc
    #   channel_width_m=80  — Marikina River channel ~80 m wide at Sto. Niño
    #   mannings_n=0.033 — earthen banks, some riprap lining
    #   channel_slope=0.002 — upper Marikina gradient (steeper than lower reach)
    cn=85.0,
    catchment_km2=50.0,
    time_of_conc_h=1.5,
    channel_width_m=80.0,
    mannings_n=0.033,
    channel_slope=0.002,

    # OSM river query: "Manila" resolves to Manila City proper (~38 km²),
    # not the full NCR / Metro Manila (~620 km²).  Use "Metro Manila" to
    # capture all waterways within the model domain.
    osm_query_name="Metro Manila",

    # MMDA / DPWH primary storm-drain design standard: RP10 for Metro
    # Manila drains.  PAGASA IDF: RP10 6h ≈ 120–140 mm in eastern Metro
    # Manila (typhoon-facing).  Use 100 mm as conservative primary-drain
    # threshold; higher-intensity typhoon rainfall will pond above this.
    drain_capacity_mm=100.0,
    runoff_coeff=0.82,

    # Pluvial: ERA5-Land hourly via Open-Meteo (no bias correction needed).
    # Metro Manila has mixed terrain (coastal flat + Marikina foothills).
    # Use the standard urban tier; refine via R4 historical-event validation
    # (Ondoy 2009 EMSR available).
    depression_area_fraction=0.10,

    notes=(
        "COASTAL: UHSLC 304 (Manila, Fort Santiago) confirmed.  "
        "msl_to_egm2008_offset=+0.25 m (CNES-CLS18 MDT interim; run "
        "derive_msl_egm2008_offsets.py --write for exact value).  "
        "Typhoon storm surge is the dominant coastal driver — Ondoy (2009) "
        "peak surge ≈ 1.5 m; Haiyan (2013) landfall was farther south but "
        "established the upper-bound scenario.  Manila Bay is microtidal "
        "(~0.7 m range); storm surge variability dominates GEV tail.  "
        "FLUVIAL: Parameters represent a 50 km² Marikina sub-basin; the "
        "full Pasig/Marikina system (~572/540 km²) requires Project NOAH "
        "FloodMap or GloFAS Reanalysis — inject RP stages into baseline CSV "
        "and run with --no-fit-era5.  "
        "PLUVIAL: ERA5-Land hourly via Open-Meteo (no bias correction). "
        "VALIDATION (2026-04-26): ERA5-Land 6h GEV RP10 = 93.8 mm vs "
        "PAGASA anchor ~130 mm (-27.8%; FAIL, marginally outside +/-25%). "
        "Ondoy 2009 EMSR available for R4 historical-event validation.  "
        "SUBSIDENCE: Metro Manila has documented subsidence 1–8 cm/yr "
        "(Phivolcs InSAR surveys, Lagmay et al. 2017) — apply "
        "--subsidence-correction once rates are digitised by district."
    ),

    # Marikina River near the Marikina-Pasig confluence (Lower Marikina / Sto. Nino).
    # Previous coordinate (14.69, 121.11) snapped to a tiny upper-basin headwater
    # cell (mean 1.5 m³/s, max 28 m³/s).  This coordinate (14.55, 121.04) captures
    # the full Marikina sub-basin discharge, returning mean annual max ~1,170 m³/s
    # and peak ~2,390 m³/s consistent with Typhoon Ondoy (2009) documented flows.
    glofas_lat=14.55,
    glofas_lon=121.04,
    # Bankfull discharge set to 612.8 m³/s — minimum annual maximum in the 28-year
    # GloFAS record (1997-2024, year 1997).  Manning depth at bankfull ≈ 2.827 m
    # (w=80m, n=0.033, S=0.002).  Bankfull subtraction converts raw Manning total
    # depth to flood depth above normal channel water level, compatible with HAND model.
    # Resulting flood depths: RP2~1.1m, RP10~2.6m, RP50~4.5m, RP100~5.5m.
    # Ondoy (2009) estimated RP50-100 → RP50=4.5m consistent with documented
    # 5-7m inundation in Marikina Valley (GloFAS underestimates by ~20-30%).
    glofas_bankfull_discharge_m3s=612.8,
))


# ----------------------------------------------------------------------
# Ho Chi Minh City (HCMC), Vietnam
#
# P0 priority: large delta city, critical Mekong Delta flood exposure,
# strong NASA/EU data coverage, well-documented subsidence.
#
# Key flood drivers:
#   • Saigon River — drains ~4,700 km² sub-basin of the Dong Nai
#     system; controlled by Dau Tieng reservoir upstream but extreme
#     events still produce significant flooding through HCMC.
#   • Mekong Delta backwater — seasonal high-water in the Mekong main-
#     stem raises the Saigon / Dong Nai lower reaches via tidal backwater
#     (particularly Sep–Nov peak).
#   • Pluvial / tidal flooding — HCMC experiences "king tide" flooding
#     at many quay-level streets (Ton Duc Thang, Ben Nghe, Canal 19/5).
#   • Subsidence: 1.5–4 cm/yr across central HCMC (Thi et al. 2015
#     InSAR; Ho Phuoc Canal area up to 7 cm/yr).
#
# UHSLC gauge:
#   Candidate: Vung Tau (Gulf of Thailand / South China Sea coast);
#   likely UHSLC Research Quality.  Verify ID at UHSLC data portal.
#   Vung Tau is ~130 km SE of HCMC; tidal range (~3 m GT) is higher
#   than inside HCMC; use with caution — surge climatology is transferable
#   but mean level adjustment (station datum, local tidal reduction) needed.
# ----------------------------------------------------------------------
_register(CityConfig(
    name="Ho Chi Minh City",
    slug="hcmc",

    # HCMC administrative boundary + immediate fringe (Thu Duc, Binh Chanh)
    min_lon=106.40, min_lat=10.55,
    max_lon=107.00, max_lat=11.10,
    utm_crs="EPSG:32648",       # UTM Zone 48N

    era5_lat=10.8231,
    era5_lon=106.6297,

    # UHSLC Research Quality gauge 257 — Vung Tau, Vietnam.
    # Confirmed present in global_hourly_rqds; Vung Tau is ~130 km SE of
    # HCMC on the South China Sea coast (10.34°N, 107.07°E).
    # Tidal range at Vung Tau ≈ 3 m (semi-diurnal, mesotidal) — higher
    # than inside HCMC due to funnelling in the Mekong outflow zone.
    # Annual maxima of de-meaned record capture the surge signal; the
    # tidal range is removed in the de-mean step.
    # msl_to_egm2008_offset: CNES-CLS18 MDT interim estimate +0.35 m
    # (South China Sea at ~10.3°N; run derive_msl_egm2008_offsets.py
    # --write for exact value).
    uhslc_id=257,
    uhslc_dataset="rqds",
    uhslc_start_year=1985,
    uhslc_end_year=2024,
    uhslc_gauge_name="Vung Tau, Vietnam — UHSLC 257 (HCMC coastal proxy)",
    msl_to_egm2008_offset=1.1707,   # CNES-CLS22 MDT (CMEMS); confirmed 2026-05-16
    # *** COASTAL BASELINE NOTE ***
    # The UHSLC 257 record has a ~2 m gauge datum break in 2002-06.
    # Running fetch_uhslc_gauge.py with the default date range will produce
    # a broken GEV (saturated, xi=-1.26) because the mixed-epoch record
    # cannot be de-meaned to a single MSL reference.
    # The hazard_baseline_template.csv coastal rows are the DATUM-CORRECTED
    # 31-year combined fit (f99204c) with updated CNES-CLS22 MDT applied.
    # Do NOT refit HCMC coastal by running the pipeline without --no-fit-coastal.
    # To regenerate, use fetch_uhslc_gauge.py with --datum-break-year 2002
    # (not yet implemented; tracked as Issue #26).

    # Saigon River representative urban reach through central HCMC.
    # The full Dong Nai / Saigon system is ~4,700 km² — far too large to
    # model from local ERA5 alone.  Parameters represent a 30 km² urban
    # sub-basin draining into the Ben Nghe / Tau Hu canal system.
    # For main-stem Saigon River flooding, use GloFAS Reanalysis
    # (Dong Nai at HCMC station) and inject RP stages with --no-fit-era5.
    #
    #   cn=82     — mixed urban/suburban (Class B/C soils; some parks)
    #   catchment_km2=30  — Ben Nghe / inner-canal sub-basin
    #   time_of_conc_h=1.0 — compact urban catchment, fast response
    #   channel_width_m=200 — Saigon River main stem at Thu Dau Mot (~150–300 m wide).
    #                         ERA5 fluvial is auto-suppressed when glofas_lat is set,
    #                         so this parameter is used only by fit_fluvial_glofas.py
    #                         (GloFAS path) not ERA5 SCS fitting.  The original 40 m
    #                         value reflected the Kenh Te / Tau Hu inner-canal width —
    #                         appropriate for the ERA5 sub-basin but wrong for the
    #                         Saigon River reach sampled by GloFAS.
    #   mannings_n=0.035 — natural river with sandy/gravel bed (lower than the
    #                       tidal-canal value of 0.038 used in ERA5 path)
    #   channel_slope=0.00015 — Saigon River gradient Thu Dau Mot → HCMC (~5 m / 50 km)
    cn=82.0,
    catchment_km2=30.0,
    time_of_conc_h=1.0,
    channel_width_m=200.0,
    mannings_n=0.035,
    channel_slope=0.00015,

    # Ho Chi Minh City primary storm-drain standard: RP10 equivalent.
    # Mean annual rainfall ≈ 1,800 mm/yr; tropical convective regime.
    # Primary drains designed for ~70–90 mm / 6 h (JICA 2011 Master Plan).
    # 70 mm used as threshold; episodes above this produce surface ponding.
    drain_capacity_mm=70.0,
    runoff_coeff=0.78,

    # Pluvial: ERA5-Land hourly via Open-Meteo (no bias correction needed).
    # HCMC sits in the Mekong delta -- very flat, broad pondable area ->
    # use the highest depression_area_fraction tier.  Unvalidated until
    # R4 historical-event runs (no public IDF anchor cited).
    depression_area_fraction=0.20,

    notes=(
        "P0 PRIORITY -- new city, requires data acquisition before first run.  "
        "COASTAL: No UHSLC gauge confirmed (uhslc_id=None).  "
        "Candidate: Vung Tau RQ station -- verify at "
        "https://uhslc.soest.hawaii.edu/data/?rq.  "
        "Alternative: MONRE Vietnam tide gauge records at Can Gio or Ba Son "
        "Wharf (request from Vietnam Institute of Meteorology, Hydrology and "
        "Climate Change, IMHEN).  "
        "Tidal range at Vung Tau ~3 m (mesotidal) vs ~2 m inside HCMC -- "
        "apply mean level correction before using as proxy.  "
        "AR6 SLR at 10.8N 106.6E P50 SSP5-8.5 2100: verify via AR6 Zarr "
        "store (same method as existing cities).  "
        "FLUVIAL: Parameters represent a 30 km² inner-canal sub-basin (Ben "
        "Nghe / Tau Hu).  Saigon River main-stem (Dong Nai basin ~4,700 km²) "
        "requires GloFAS Reanalysis — inject RP stages with --no-fit-era5.  "
        "Mekong Delta backwater seasonal signal (Sep–Nov) is NOT captured "
        "by this model; add seasonal tidal datum adjustment manually.  "
        "PLUVIAL: ERA5-Land hourly via Open-Meteo (no bias correction). "
        "VALIDATION: no public IDF anchor cited; depression_area_fraction=0.20 "
        "set by Mekong-delta terrain analogy.  Unvalidated until R4 historical-"
        "event runs (e.g. HCMC 2008 typhoon floods).  "
        "SUBSIDENCE: 1.5–4 cm/yr (Thi et al. 2015 InSAR); inner Ben Nghe "
        "/ Phu My Hung up to 7 cm/yr.  Apply --subsidence-correction; rates "
        "available from Deltares/UNESCO-IHE HCMC subsidence maps."
    ),

    # Saigon River near Thu Dau Mot — above tidal backwater from Mekong; representative of unregulated Saigon River flood signal.
    glofas_lat=10.98,
    glofas_lon=106.65,
    # Bankfull discharge set to 321.1 m³/s — minimum annual maximum in the 28-year
    # GloFAS record (1997-2024, year 2015).  Manning depth at bankfull ≈ 2.495 m
    # (w=200m, n=0.035, S=0.00015).  Bankfull subtraction converts raw Manning total
    # depth to flood depth above normal channel water level, compatible with HAND model.
    # Resulting flood depths: RP2~1.1m, RP10~2.5m, RP50~4.2m, RP100~5.1m.
    glofas_bankfull_discharge_m3s=321.1,
))
