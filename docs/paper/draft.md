# Open-data multi-hazard flood screening for ASEAN cities: a reproducible 30 m methodology with bias-aware solver selection

**Authors:** TBD
**Affiliations:** TBD
**Corresponding author:** TBD
**Target venue:** IEEE Region 10 Humanitarian Technology Conference (R10-HTC) 2026 — Special Session 1 "Net Zero Integration" (IEEE conference template, two-column, ~6 pages). A condensed IEEE conference version is derived from this master draft; the longer journal form (NHESS / *Environmental Modelling & Software*) remains the extended reference.
**Draft version:** v1.2 (2026-06-10) — 4-city scope (Singapore, Kuala Lumpur, Bangkok, Jakarta)

---

## Abstract

Flood risk in Southeast Asian megacities is rising under joint sea-level rise, precipitation intensification, and ongoing land subsidence in four of the six most exposed cities (Jakarta, Manila, Ho Chi Minh City, Bangkok). Existing screening tools that cover the region fall into three categories with structural limitations: coarse-resolution global open-data products (Aqueduct Floods 4.0 at ~10 km, lacking pluvial; PCR-GLOBWB / GLOFRIS at the same scale); high-resolution closed-source commercial models (Fathom 3.0 at 30 m globally but commercially licensed, with free access restricted to 16 specific developing countries that exclude the major ASEAN cities); and bespoke per-city engineering studies that are not publicly reproducible (NCICD Jakarta, BMA Bangkok, DPSI HCMC, MMDA Manila, PUB Singapore).

We present an open-source, open-data pipeline producing design-event coastal, fluvial, and pluvial flood depth maps at 30 m for nine city configurations across four ASEAN countries (Singapore, Malaysia, Thailand, Indonesia), under four climate combinations (SSP2-4.5 and SSP5-8.5 × 2050 and 2100). To the best of our knowledge this is the first openly reproducible 30 m multi-hazard flood atlas calibrated to national Intensity-Duration-Frequency (IDF) anchors for ASEAN megacities. Pluvial baselines are anchored to the documented design standards of four national meteorological services (PUB, JPS-MSMA, TMD-RID, BMKG), eliminating the 28–62 % deficit that global synthetic rainfall statistics carry over tropical-convective extremes. Coastal hazards use a 2D local-inertia solver (Bates et al., 2010) selected over a bathtub baseline by a quantified bathtub-bias characterisation; the pipeline retains topology-based solver selection (bathtub fallback) for cities whose enclosed sea geometry breaks the inertial wall condition. Fluvial inundation uses Height Above Nearest Drainage with bankfull-stage subtraction for rivers carrying permanent baseflow. Pluvial routing is an open-source implementation of fill-spill-merge methodology (Barnes et al., 2020) integrated with a per-cell runoff coefficient derived from ESA WorldCover 2021 land cover.

Validation comprises four components: IDF-anchor consistency checks across the nine configurations (0 FAIL; the only WARNs are floor-zone return periods where documented design rainfall sits below drain capacity); contingency-metric comparison against three documented historical events (Thailand 2011, Malaysia 2021, Jakarta 2020); quantitative bathtub-bias characterisation by reconstructing present-day extents from the future-scenario rasters; and a systematic model-blind documented-hotspot location-skill gate for three cities (Kuala Lumpur, Bangkok, Jakarta; hit-rate / specificity / true-skill statistic, all three with statistically significant skill). The hotspot tier yields two transferable rules — a main-stem HAND referencing for incised-valley cities, and the limit that single-stage HAND does not transfer to flat deltas fed by out-of-domain mega-rivers (confirmed on two of three cities). Bathtub coastal extent over-predicts documented present-day inundation by 1.7–25× at RP100 across the covered cities (Singapore, Bangkok, Jakarta); the local-inertia solver brings RP100 bias close to 1× where topology permits (Bangkok reduction 12.5×, independently reproduced against an earlier benchmark to the kilometre). Full source code, configuration data, atlas outputs, and an R1–R8 replicability audit are released.

**Keywords:** flood modelling, ASEAN, coastal flooding, fluvial flooding, pluvial flooding, open data, HAND, fill-and-spill, GEV, AR6 sea-level rise, reproducibility, screening

---

## 1. Introduction

### 1.1 ASEAN flood risk and the gap in open screening tools

Southeast Asia contains six of the ten cities globally most exposed to coastal flooding by 2100 under high-emission climate scenarios (Hallegatte et al., 2013; Tellman et al., 2021). Approximately 750 million people live in the ASEAN region, with half expected to be urban-resident within the next decade, and an estimated 20 % of regional GDP sits on flood-exposed land (ADB, 2022). Climate stressors compound: AR6 P50 sea-level rise projections range from +0.62 m (Singapore) to +1.62 m (Bangkok, under SSP5-8.5 by 2100; Fox-Kemper et al., 2021); tropical convective precipitation is intensifying at the Clausius-Clapeyron rate or above (Lenderink et al., 2017); and four of the six megacities exhibit ongoing land subsidence at 1–25 cm yr⁻¹ from groundwater extraction and clay compaction (Phien-wej et al., 2006; Chaussard et al., 2013; Erban et al., 2014; Eco et al., 2020). Major recent flood events demonstrate the multi-hazard character of the regional exposure: the Thailand 2011 megaflood (Trinh et al., 2017), Jakarta 2020 monsoon flooding (Sentinel-Asia, 2020), and Kuala Lumpur December 2021 flash floods (Department of Irrigation and Drainage Malaysia, 2022). This paper covers four of these cities — Singapore, Kuala Lumpur, Bangkok, and Jakarta — across Singapore, Malaysia, Thailand, and Indonesia; extension to the typhoon-driven (Manila) and Mekong-delta (Ho Chi Minh City) regimes is deferred (see §6.4).

Existing flood-screening tooling that covers ASEAN today belongs to one of three categories, none of which simultaneously achieves high resolution, multi-hazard scope, open code, open data, and per-country calibration (Table 1).

**Table 1.** Comparator landscape for ASEAN-relevant flood screening tools.

| Tool | Resolution | Coverage | Hazards | Code | Data | Licence | Per-country IDF calibration |
|---|---|---|---|---|---|---|---|
| **This work** | **30 m** | 9 ASEAN city configurations across 4 countries | Coastal + fluvial + **pluvial** | **Open** (GitHub) | **Open** (GLO-30, ERA5-Land, UHSLC, GloFAS, OSM, AR6 Zarr, WorldCover) | Permissive | **Yes** — four national meteorological services |
| Fathom 3.0 (Wing et al., 2024) | 30 m | Global | C + F + P | Closed | Closed (FABDEM+) | Commercial; free for 16 developing countries (excludes ASEAN megacities) | Global synthetic |
| Aqueduct Floods 4.0 (Hofste et al., 2019; Ward et al., 2020) | ~10 km (5 arc-min) | Global | C + F (no pluvial) | Open methodology | Open data | CC | None |
| GLOFRIS / PCR-GLOBWB 2 (Sutanudjaja et al., 2018) | ~10 km | Global | F (+ coastal extension) | Open | Open | CC | None |
| Olcese et al. (2024) | DEM-grade | Southeast Asia | F + P (no coastal) | Likely closed | Likely closed | Paywalled | None |
| Moody's RMS Asia-Pacific | Various | TH/MY/SG/ID | F + P | Closed | Closed | Commercial | Per-product |
| JBA Global Flood Map | Various | Global | C + F | Closed | Closed | Commercial | Per-product |
| GTSM-ERA5 (Muis et al., 2020) | ~0.1° | Global | Coastal only | Mixed | Open | CC | n/a |
| LISFLOOD-FP (Bates et al., 2010) | High | Configurable | F | Open | Bring-your-own | Open | Bring-your-own |
| City-specific engineering studies (NCICD, BMA, DPSI, MMDA, PUB) | High | Single city | Various | Closed | Closed | Proprietary | Per-city engineering |

Three observations from Table 1 motivate this paper. **First**, no openly reproducible 30 m three-hazard model for ASEAN megacities currently exists. The only comparable-resolution three-hazard global model (Fathom 3.0) is closed-source and the free-access tranche excludes the cities we cover. The only ASEAN-focused regional model (Olcese et al., 2024) lacks the coastal hazard and was not released with open code. The only open-data global alternatives (Aqueduct Floods, GLOFRIS) are an order of magnitude coarser and lack a pluvial layer.

**Second**, no published flood model for the region uses per-country IDF anchoring for the pluvial hazard. Global synthetic rainfall statistics — including ERA5, ERA5-Land, MERRA-2, and the GloFAS reanalysis discharge — systematically under-represent tropical convective extremes by 28–62 % relative to the national IDF curves published by PUB (Singapore), JPS-MSMA (Malaysia), TMD-RID (Thailand), and BMKG (Indonesia). For pluvial screening in the ASEAN region, this is the dominant correctable bias.

**Third**, no published flood-model methodology paper to date includes an end-to-end replicability audit itemising every gap a third party would encounter when reproducing the work. The R1–R8 framework presented in Appendix A is intended as a hygiene contribution applicable beyond this paper.

### 1.2 Contributions

The headline contribution is the deliverable itself: a fully open-source, fully open-data, per-country IDF-calibrated, 30 m, multi-hazard flood atlas for ASEAN megacities — a combination of attributes that does not exist in the published literature. In descending order:

1. **The atlas as a published artefact.** Design-event flood depth maps at 30 m for 9 ASEAN city configurations across four countries, three hazards, and four SSP × horizon combinations, reproducible end-to-end from a public GitHub repository (§4).

2. **Per-country IDF anchoring across four national meteorological services** as the calibration framework. Each country's pluvial GEV is anchored directly to PUB, JPS-MSMA, TMD-RID, or BMKG published design standards (§2.5.1). No published global or regional model does this.

3. **Per-city implementation matrix** as a methodology contribution (§3). The asymmetric public-data environment of ASEAN — gauge availability, IDF curve digitisation status, basin scale, channel hydrology — makes a uniform recipe demonstrably incorrect for three of the four target countries. We document the per-city decision logic explicitly and argue this transparent heterogeneity is the correct structural response.

4. **Bathtub vs local-inertia bias characterisation** (§5.3). We reconstruct present-day flood extent from the SSP5-8.5 / 2100 raster set by subtracting the AR6 SLR delta and compare against documented historical extents from peer-reviewed and grey literature; we then show that the Bates et al. (2010) local-inertia formulation, optimised here to run a single return period on the 6.1-million-cell Bangkok domain in tens of minutes wall-clock, brings RP100 bias close to 1× for cities whose enclosed-bay or enclosed-delta topology does not break the inertial wall condition.

5. **Replicability audit (R1–R8).** Appendix A itemises every data source, every calibration anchor, and every gap a third party would encounter. We argue this format is broadly applicable to flood-model methodology papers.

6. **Open-source FSM-style fill-and-spill pluvial implementation**. The fill-spill-merge methodology (Barnes et al., 2020) is integrated into a screening pipeline with WorldCover-derived per-cell runoff (§2.5). This is not a novel hydraulic method but a published open-source implementation that resolves the return-period-invariant flood-extent artefact of lumped depression-fill approximations still prevalent in screening tools.

7. **Model-blind documented-hotspot location-skill validation** (§5.5). A reusable, city-agnostic gate scores combined-hazard wet masks against a frozen, geocoded, DEM-verified register of documented flooded and documented-dry localities (hit-rate / specificity / true-skill statistic with bootstrap CIs). Applied to three cities with no engine changes, it yields statistically significant skill for all three and two transferable methodology rules — a main-stem HAND referencing for incised-valley cities, and the limit that single-stage HAND does not transfer to flat deltas fed by out-of-domain mega-rivers — together with a discipline that keeps model-flooded genuine controls in the register and corrects only independently-documented mislabels.

### 1.3 Paper structure

§2 describes the pipeline architecture and per-step methods. §3 develops the per-city implementation matrix and the rationale for intentional heterogeneity. §4 presents results across the city × scenario × horizon × hazard grid. §5 reports validation in five tiers: IDF-anchor consistency, historical-event contingency, bathtub-bias quantification, documented-HWM depth cross-check, and a model-blind documented-hotspot location-skill gate. §6 discusses appropriate use, limitations, and future work. §7 concludes.

---

## 2. Pipeline architecture and methods

### 2.1 Overview

The pipeline produces, for each city configuration and each scenario × horizon combination, a set of nine return-period depth rasters per hazard (RP2, 5, 10, 25, 50, 100, 200, 500, 1000), a five-class severity raster derived from documented impact thresholds (JRC European flood damage functions; PUB advisory categories), and a per-pixel-dominant-hazard composite. Figure 1 shows the data flow: a per-city configuration object (`cities.py`) parameterises a single orchestration script (`run_city_pipeline.py`) that successively fetches the Copernicus GLO-30 Digital Elevation Model (DEM), optionally applies a subsidence correction and engineered defence-crest burn-in, derives a sea mask and an OpenStreetMap-based river network, computes Height Above Nearest Drainage (HAND), runs the multi-hazard solver, and emits visualisation products. Every step is implemented in pure Python on the scientific-Python stack (rasterio, scipy, pyproj, pysheds, numba); no external binaries are required.

[**Figure 1.** Pipeline architecture flowchart showing per-step data products, the cities.py configuration surface, and the optional steps (subsidence correction, defence burn-in) that activate based on per-city configuration. Render from the methodology comparison document's overview.]

### 2.2 Terrain

The Copernicus GLO-30 DEM (TanDEM-X, ~2013 reference epoch; Krieger et al., 2007; Wessel et al., 2018) provides global terrain at ~30 m horizontal resolution referenced to the EGM2008 geoid. We download tiles via the Microsoft Planetary Computer Spatio-Temporal Asset Catalog (STAC), mosaic and reproject to the local Universal Transverse Mercator zone at exactly 30 m. The choice of GLO-30 over alternatives (FABDEM v1.2, MERIT Hydro) is driven by global coverage, free public access without registration, and explicit EGM2008 referencing that aligns directly with AR6 SLR projections and tide-gauge-derived water levels.

Three optional in-place modifications can be applied before flood routing: zone-based subsidence correction (§2.2.1), engineered-defence crest burn-in (§2.2.2), and TanDEM-X artefact spike cleanup (§2.2.3).

#### 2.2.1 Subsidence correction

Two of the four covered cities exhibit documented ongoing subsidence between the GLO-30 reference epoch (~2013) and the analysis epoch (~2025): Jakarta (Chaussard et al., 2013; Abidin et al., 2011) and Bangkok (Phien-wej et al., 2006; Aobpaet et al., 2013). (The same correction methodology applies to the deferred Manila and HCMC configurations.) We apply a zone-based correction (`apply_subsidence_correction.py`) using three latitude-band zones per city, with representative subsidence rates from published InSAR and GPS literature. Mean accumulated correction over the analysis interval ranges from −0.24 m (Bangkok) to −0.83 m (Jakarta), affecting between 1.2 and 6.0 million land pixels per city.

Zone-based correction is a screening-grade representation: it removes the systematic bias between the DEM acquisition epoch and the present but does not capture within-zone heterogeneity. A pixel-accurate correction would require co-registered InSAR velocity rasters, which are not publicly available at the required scale and consistency for all four cities.

#### 2.2.2 Engineered defence crest burn-in

For three cities with documented engineered coastal or fluvial defences (Bangkok, Singapore, Jakarta), we represent defence lines as WGS-84 polylines with crest elevations in metres above local mean sea level (`apply_flood_defenses.py:DEFENSE_CONFIGS`). Polylines are reprojected into the DEM coordinate system, buffered to approximately three pixels (~90 m), and burned in via `max(DEM, crest_EGM2008)` after adding the city-specific mean dynamic topography (MDT) offset to bring the crest elevation onto the EGM2008 surface. The defended DEM is written with a `_defended` suffix; downstream steps then run on it, and outputs are routed to a parallel `_defended` output directory so the two scenarios can be compared.

Documented defences include the King's Dyke and Chao Phraya river-bank dykes (Bangkok); the Marina Barrage and East Coast Park bund (Singapore); and the National Capital Integrated Coastal Development (NCICD) Phase A outer seawall and inner polder rings (Jakarta).

Two implementation details matter for correctness. First, the sea mask (§2.6) is derived from the **pre-defence** DEM: defences are flood-routing barriers, not geographical re-definitions of what is ocean, and building the sea mask from the defended DEM would let a burned tide-gate ridge sever a tidal channel from the open sea in the BFS, flipping the channel interior from sea to land. Second, the defended HAND raster is scenario-suffixed (`hand_<utm>_defended.tif`) so that defended and undefended runs do not overwrite each other.

#### 2.2.3 TanDEM-X artefact spike cleanup

The raw GLO-30 occasionally contains spurious very-negative pixel values where TanDEM-X radar coherence was low or processing produced outliers; we clean them by iterative local-median replacement, preserving the original DEM. Among the paper cities the affected pixel counts are small and the correction is minor (e.g. the Bangkok subsidence-corrected DEM carries a handful of sub-domain pits below −5 m against a genuine delta minimum near −3 m). The most extreme cases in the broader suite were in the deferred HCMC and Manila deltas (minima to −83 m), none corresponding to real terrain.

These artefacts are invisible in the default below-zero-clamp mode but propagate as physically implausible ~80 m flood depths when negative-elevation land pixels are retained for genuine subsided polders. We replace each spike with the median of its 7×7 neighbourhood, excluding nodata and other spike pixels (`_clean_dem_artefacts.py`), preserving the original DEM as `*_uncleaned.tif`. The procedure is idempotent and iterated to convergence.

### 2.3 Coastal hazard

#### 2.3.1 Sea-level statistics

Coastal water-level statistics are derived from University of Hawaii Sea Level Center (UHSLC) tide-gauge records (Caldwell et al., 2015). Three of the four covered countries have a qualifying Research-Quality station with a ≥17-year record: Tanjong Pagar (Singapore; UHSLC 699; 39 years), Port Klang (Malaysia; UHSLC 140; 37 years), and Ko Lak (Thailand; UHSLC 328 fast-delivery; 40 years). Jakarta (Indonesia) has no qualifying RQ gauge with a ≥30-year record (UHSLC 161 ended September 2004); we fall back to literature values from Muis et al. (2016) and flag the layer explicitly as screening-only.

For each gauge with a tide-gauge record we apply T_TIDE harmonic analysis (Pawlowicz et al., 2002) to remove the predictable astronomical signal, extract annual maxima of the storm-surge residual, and fit a Generalised Extreme Value (GEV) distribution by maximum likelihood (`scipy.stats.genextreme.fit`) with the shape parameter capped at ξ_max = 0.30 to prevent tail runaway on short records.

A cross-gauge datum-break audit (`fetch_uhslc_gauge.py` annual-maxima consistency check across the full available record) found no internal datum shifts in the three qualifying paper-city stations: the Port Klang record (36 years, 1985–2022) shows no step-change in annual maxima; the Tanjong Pagar Singapore record (38 years, 1985–2023) is internally consistent throughout; and the Ko Lak (Thailand) record is consistent across its span. No gauge-specific datum correction is required for the four paper cities (Jakarta uses literature values, having no qualifying gauge).

#### 2.3.2 Mean dynamic topography offsets

Tide-gauge water levels are referenced to local mean sea level, while the GLO-30 DEM is referenced to EGM2008. The offset between local MSL and EGM2008 at each gauge — the mean dynamic topography — is required to bring water levels and terrain onto a common vertical datum. We sample the Copernicus Marine Service (CMEMS) CNES-CLS-2022 MDT product at each gauge coordinate (`derive_msl_egm2008_offsets.py`), yielding offsets between +0.998 m (Tanjung Priok, Jakarta) and +1.179 m (Ko Lak, Bangkok). The offsets are applied idempotently to the baseline_water_level_m column in each city's hazard CSV.

#### 2.3.3 Sea-level rise projections

Future sea-level rise is added from the IPCC Sixth Assessment Report Working Group I Chapter 9 projection ensemble (Fox-Kemper et al., 2021), accessed via the public NCAR/Rutgers Zarr store. For each station × scenario × horizon we extract the workflow `wf_1e` projection (which includes ice-sheet uncertainty) and compute the percentile delta per Monte Carlo sample before aggregation, preserving intra-sample correlation between the baseline year and the projection year. The P50 SLR delta at SSP5-8.5 / 2100 ranges from +0.62 m (Singapore) to +1.62 m (Bangkok); the latter reflects the Gulf of Thailand's regional dynamic SLR, which exceeds the global mean (~0.77 m) due to ocean-circulation effects identified in AR6 §9.6.

#### 2.3.4 Coastal solvers

The pipeline includes two coastal solver options. The **bathtub** solver fills connected-to-sea depressions up to the target water surface elevation via breadth-first search (BFS) seeded from sea pixels, tidal channel pixels, and optionally a user-supplied lat/lon seed inside an enclosed bay. Runtime is sub-second per return period. It is adequate for very flat coastal plains where wave propagation is negligible (Teng et al., 2017).

The **local-inertia** solver (`model/inertial_wave_model.py`) implements the Bates et al. (2010) formulation of the 2D shallow water equations on a staggered Arakawa C-grid, dropping the nonlinear advection terms (valid for Froude number Fr < 0.5). Sea cells are held at a time-varying surge hydrograph (3-hour linear ramp, 1-hour peak hold, 2-hour linear recession) as Dirichlet boundary conditions. The three hot kernels (x-flux, y-flux, continuity) are compiled with `numba @njit(parallel=True, fastmath=True)`; the solver runs only the smallest bounding box containing potentially wet cells. Under these optimisations a single-return-period inertial solve on Bangkok's 6.1-million-cell grid runs in tens of minutes wall-clock; the validation here therefore focuses on the event-matched RP100, with the full nine-return-period sweep run when a complete design-event set is required.

#### 2.3.5 Per-city solver selection

We select between bathtub and local-inertia per city by the bathtub-bias factor measured against documented historical events (§5.3). Where present-day bathtub bias exceeds approximately 5× and the city's topology supports the inertial wall condition, we use local-inertia. Bathtub remains the default elsewhere. All three coastal cities in this paper (Bangkok, Singapore, Jakarta) have boundary-connected sea topology and use local-inertia. The fallback path is the `_BATHTUB_COASTAL_CITIES` override for cities whose sea is enclosed within the DEM domain: an enclosed-bay or enclosed-delta topology breaks the local-inertia wall condition (which requires zero flux across NaN/land interfaces and therefore provides no path for surge to propagate from the sea mask onto the coastal plain), forcing bathtub. The deferred Manila (enclosed bay) and HCMC (enclosed delta) configurations are the motivating cases (§6.4).

### 2.4 Fluvial hazard

#### 2.4.1 Discharge baselines

Fluvial baselines use one of two driver types depending on catchment scale and data availability. For small canalised catchments where GloFAS routing at 0.1° (~10 km) is too coarse — Singapore (~10 km² PUB primary canals) and the Bangkok klong network (~5 km² urban sub-basin) — we derive design-storm rainfall from ERA5-Land hourly precipitation (Muñoz-Sabater et al., 2021) via the Open-Meteo Historical Weather API, apply the Soil Conservation Service Curve Number method to convert rainfall to direct runoff, and translate runoff to channel stage via Manning's normal-flow equation for a representative wide rectangular channel.

For larger basins (KL ~500 km², Bangkok Chao Phraya >100,000 km², Jakarta ~370 km²), we use GloFAS v4 daily discharge reanalysis (Alfieri et al., 2020) at a sub-basin point, accessed via Open-Meteo's Flood API. The 28-year record (1997–2024) is fit to a GEV distribution with the same xi_max cap as the coastal solver.

For Bangkok Chao Phraya we apply two corrections to the raw GloFAS reanalysis: a 0.42× discharge scale derived from comparison against the Royal Irrigation Department C.2 gauge at Nakhon Sawan (which gives historical RP100 ≈ 3,500–4,500 m³ s⁻¹ versus GloFAS-implied ~4,800 m³ s⁻¹), and a tighter shape cap of ξ_max = 0.15 to prevent the 2011 megaflood outlier from inflating the tail of a 28-year record.

#### 2.4.2 Bankfull subtraction

For rivers carrying permanent baseflow (KL Klang, Bangkok Chao Phraya), the Manning depth at peak return-period discharge corresponds to total channel water depth above the bed, not flood stage above bankfull. We subtract the Manning depth at Q_bf = minimum annual maximum discharge so HAND inundation reflects depth above design capacity. For rivers that are dry between events (Jakarta Ciliwung-Depok) or canalised (Singapore PUB drains), no bankfull subtraction is applied.


#### 2.4.3 Height Above Nearest Drainage

Fluvial inundation depth is computed via the HAND framework (Nobre et al., 2011). We condition the GLO-30 with pysheds pit-filling and flat resolution (Schwanghart and Scherler, 2014; pysheds implements the Planchon and Darboux 2002 algorithm), compute D8 flow direction, accumulate flow upstream, and delineate the **drainage network the modelled discharge represents** — flow-accumulation channels at the catchment scale of the GloFAS sub-basin reach (the *main-stem HAND* referencing, §5.5), rather than a channel-initiation threshold or raw OpenStreetMap waterways. Referencing HAND to a channel-initiation or full-OSM network over-broadens the floodplain (it floods hillside rivulets and, at the channel-initiation scale, ~25 % of the domain at physically absurd depth); referencing it to the trunk the discharge actually represents yields a credible floodplain (§5.5, validated on Kuala Lumpur). For each non-channel pixel we trace the D8 flow path downstream until a channel cell is reached and record the elevation difference. Fluvial inundation depth at return period RP is then `max(0, stage_RP − bankfull − HAND)`.

### 2.5 Pluvial hazard — catchment-routed fill-and-spill

The pluvial baseline construction has two stages: an IDF-anchored rainfall baseline (§2.5.1) and a catchment-routed fill-and-spill solver (§2.5.2). The decoupling matters: the rainfall baseline is set by the national IDF design standard, while the spatial distribution of ponding is determined by topographic catchment routing of post-drain runoff into the depression inventory.

#### 2.5.1 Per-country IDF anchoring

For each country we fit a two-anchor Gumbel distribution (ξ = 0) to two return periods of the documented IDF curve published by the national meteorological service. The **storm duration** itself is part of the per-city heterogeneous parameterisation: Singapore uses a 1-hour IDF because its documented flash-flood mechanism is sub-hourly convective bursts overwhelming secondary/tertiary drains (Orchard Road 2010–11, Bukit Timah 2017); the other three countries retain a 6-hour IDF because their published design frameworks and documented event timescales are multi-hour to multi-day (KL Dec 2021 multi-day basin rainfall; Bangkok 2011 megaflood; Jakarta Jan 2020 ~377 mm/24 h). The IDF duration always matches the dominant local flood mechanism rather than a uniform default. Concretely:

- **Singapore.** Meteorological Service Singapore (MSS) 1-hour IDF (2026-05-27 update): μ = 46.0 mm, σ = 16.0 mm, anchored to RP10 = 82 mm and RP100 = 120 mm (MSS/PUB published values). Drain capacity = 70 mm/1h — the PUB Code of Practice on Surface Water Drainage (6th edition) secondary-drain design standard (RP5, 1-hour storm). This parameterisation replaces the earlier 6-hour primary-drain configuration (MSS 6h: μ = 66 mm, σ = 19.5 mm; primary drain 100 mm/6h) to model the documented flash-flood mechanism: short-duration convective bursts overwhelming secondary and tertiary drains at road level (Orchard Road 2010–11; Bukit Timah 2017). Primary drains (100 mm/6h) were adequate for 6-hour convective storms and produced near-zero pluvial excess at all but extreme return periods; secondary drains (70 mm/1h) are the operative threshold for the documented events.
- **Malaysia.** Department of Irrigation and Drainage Manual Saliran Mesra Alam (JPS-MSMA) 2012: RP2 6h = 90 mm, RP100 6h = 165 mm; μ = 83.5 mm, σ = 17.7 mm. JPS RP5 drain standard 70 mm/6h.
- **Thailand.** Thai Meteorological Department / Royal Irrigation Department: RP5 6h = 85 mm, RP100 6h = 150 mm; μ = 53.6 mm, σ = 21.0 mm. Primary klong network ~80 mm/6h.
- **Indonesia.** Badan Meteorologi, Klimatologi, dan Geofisika (BMKG) urban-station IDF: RP2 6h = 85 mm, RP100 6h = 175 mm; μ = 77.2 mm, σ = 21.3 mm. Banjir Kanal primary drain ~45 mm/6h.

The post-drain excess rainfall at return period RP is then `excess_depth_m = max(0, GEV(RP) − drain_capacity_mm) / 1000`. This produces a single scalar per RP — the spatially uniform depth of rainfall the drainage network cannot convey. The five supplementary configurations (`klang_shah_alam`, `subang_langat`, `bangkok_chao_phraya`, `tangerang`, `bekasi_depok`) inherit the parent-metropolitan IDF anchors with city-specific drain capacities.

For all cities ERA5-Land reanalysis underestimates peak design-duration rainfall relative to the national IDF anchor. For Singapore, ERA5-Land 1h RP10 is approximately 74 mm vs the MSS anchor of 82 mm (−10 %; consistent with the earlier 6h bias of −9.4 %). For Kuala Lumpur, Bangkok, and Jakarta the ERA5-Land deficit exceeds 28 % at RP10 and 50 % at RP100, motivating the direct-anchoring approach over reanalysis-derived statistics.

#### 2.5.2 Catchment-routed fill-and-spill cascade

The scalar `excess_depth_m` is routed to a spatially explicit depth raster via a fill-spill-merge-style cascade implemented in `model/pluvial_model.py`. The implementation follows the methodology of Barnes et al. (2020) with extensions for screening-grade integration:

**Runoff generation.** Each cell's runoff volume is `excess_depth_m × runoff_coeff(cell) × cell_area`, where `runoff_coeff(cell)` is read from a per-cell ESA WorldCover 2021 v200 land-cover raster (Zanaga et al., 2022). The runoff coefficient mapping reflects established surface-hydrology values: built-up impervious 0.85, permanent water 1.0, herbaceous wetland 0.70, cropland 0.40, tree cover 0.15. A per-city scalar fallback (0.75–0.82) is used where the raster is unavailable.

**Catchment supply.** Runoff is routed by D8 flow direction on the raw DEM. Each topographic depression accumulates the runoff generated across its entire upslope catchment.

**Depression inventory.** Topographic depressions are identified from the pysheds-filled DEM (Schwanghart and Scherler, 2014). Each depression is characterised by its constituent cells, capacity (volume to fill to the pour point), and pour-point elevation. Depressions with maximum depth shallower than 0.5 m are excluded as DEM noise; depressions deeper than 3.0 m (`max_depression_depth_m`) are excluded as non-ponding features (quarries, incised valleys, reservoir basins, DEM artefacts).

**Fill and spill.** Each depression fills along its hypsometric (area–elevation) curve until its supplied volume is exhausted or it reaches the pour-point elevation. Overflow spills to the downstream depression along the conditioned-DEM flow field, computed by pysheds. The cascade is processed in topological order so a depression's total inflow is final before fill.

Unlike a lumped depression-fill model that clips a single ponding-cap scalar uniformly to every connected depression, the catchment-routed cascade produces a return-period-dependent flood extent: at low RP only depressions fed by the largest catchments fill enough to wet appreciable area; at higher RP overflow cascades activate progressively more terrain.

### 2.6 Sea-mask construction

A correct sea mask is essential because the GLO-30 DEM stores open ocean inconsistently — most cells at exactly 0.0 m EGM2008, but some coastlines as nodata (−9999) from low-coherence TanDEM-X processing. We construct the sea mask by breadth-first search from the raster boundary through all pixels at z ≤ 0 m, with an additional NaN-BFS pass seeded from boundary nodata pixels (default-enabled; required for the GLO-30 NaN-coded coastlines).

The four paper cities' seas connect to the raster boundary, so no interior seeding is required. (The capability exists for cities whose sea is enclosed inside the clipped domain — e.g. the deferred Manila Bay and Saigon–Nha Be delta configurations require interior seed points — and is the same enclosed-sea topology that forces the bathtub coastal fallback, §2.3/§6.4.)

The sea mask is derived from the **pre-defence** DEM: an engineered defence is a flood-routing barrier, not a geographic redefinition of what is ocean. Deriving the sea mask from the defended DEM would let a burned tide-gate or ring-dyke ridge sever a tidal channel from the open sea in the BFS, flipping the channel interior from sea to land and producing spurious below-MSL flooding at every return period for both coastal and pluvial hazards.

### 2.7 Multi-hazard composition

Coastal, fluvial, and pluvial depth rasters are composited by per-pixel maximum. A per-pixel dominant-hazard raster records which of the three drives the maximum at each cell, for diagnostic visualisation. The combined depth raster is then classified into five severity categories (0 no flood; 1 minor 0–0.15 m; 2 moderate 0.15–0.50 m; 3 major 0.50–1.00 m; 4 severe >1.00 m) using thresholds aligned to JRC European flood damage functions and PUB advisory categories.

The per-pixel maximum composition is a screening-grade approximation of multi-hazard exposure. It is not a joint-exceedance model: the return period labelled on a multi-hazard map is the marginal RP of each hazard separately, not the joint RP of the compound event. Compound events would have substantially shorter marginal RPs and are flagged as an explicit limitation (§6.2).

---

## 3. Per-city implementation matrix

A single uniform methodology would be cosmetically simpler but factually wrong for the ASEAN public-data environment, because public-data availability is asymmetric in five specific ways.

### 3.1 Five reasons heterogeneity is intentional

**Public-data availability is asymmetric.** Among tide-gauge records, Singapore, Malaysia, and Thailand have qualifying UHSLC Research-Quality records with ≥17 years of hourly data; Indonesia's Jakarta-area record ended September 2004 (we fall back to Muis et al., 2016). Among national IDF curves, Singapore (PUB) is digitised in publicly accessible reports; the JPS (Malaysia), TMD (Thailand), and BMKG (Indonesia) curves exist on paper but are not publicly available in machine-readable form. Among discharge gauges, only Thailand provides public gauge data (RID C.2 Nakhon Sawan) that can bias-correct the GloFAS reanalysis.

**Physical hydrology differs by city.** Singapore PUB canals (~10 km², dry between events, concrete-lined) and the Chao Phraya main stem (Bangkok; >100,000 km², permanent monsoon baseflow) require fundamentally different fluvial treatments. The microtidal Java Sea (Jakarta) and the mesotidal Strait of Malacca (Port Klang) require different GEV shape-parameter caps. The flat, well-connected delta depressions of Bangkok and Jakarta and the steep, concentrated drainage of dense urban Singapore produce very different pluvial extent-vs-RP curves under the same rainfall driver.

**Data-validation outcomes vary.** ERA5-Land precipitation passes the Singapore IDF validation within −9.4 % but fails KL, Bangkok, and Jakarta by 28–62 % at RP10. Applying ERA5-Land uniformly across all four countries would knowingly produce wrong pluvial extents in three of them.

**GloFAS reanalysis has location-specific biases.** Bangkok GloFAS over-estimates discharge by approximately 2.4× relative to the RID gauge at Nakhon Sawan; we apply a 0.42× scale correction. Other cities lack public discharge anchors and use uncorrected GloFAS with documented uncertainty (±20–40 % in stage at RP100).

**Record length and tail behaviour vary.** The Bangkok Chao Phraya discharge fit uses a tightened ξ_max = 0.15 cap so that the 2011 megaflood — a single extreme outlier in a 28-year record — does not inflate the GEV tail, whereas the longer, better-behaved coastal tide-gauge records (Tanjong Pagar 38 yr, Port Klang 36 yr, Ko Lak) support the standard ξ_max = 0.30 cap. The shape-parameter cap is therefore set per record length and tail behaviour, not uniformly.

### 3.2 The per-city implementation matrix

Table 2 documents the resulting per-city choices. Cells are colour-coded to indicate confidence: green where a public IDF or RQ-gauge anchor exists and validates cleanly; amber where an anchor is missing or the validation shows a documented limitation; red where structural constraints (e.g., Jakarta's absent qualifying tide gauge, forcing literature-only coastal values) cannot be resolved by additional data.

**Table 2.** Per-city implementation matrix. [Render from §7.1.1 – §7.1.3 of the methodology comparison document.]

### 3.3 Decision protocol for a new ASEAN city

Adding a city to the pipeline follows a fixed five-step protocol: (i) identify the qualifying UHSLC RQ tide gauge for the coastal hazard, or fall back to literature values; (ii) identify the catchment scale of the dominant fluvial system and decide between rainfall-runoff (small canalised catchments) and GloFAS injection (larger basins); (iii) digitise the national 6-hour IDF curve at two anchor points and fit a Gumbel; (iv) document the per-city drain capacity, runoff coefficient, and subsidence configuration; (v) commit the configuration in `cities.py`. The protocol is intentionally explicit so new cities can be added by third parties without bespoke methodology decisions hidden in code.

---

## 4. Results: the ASEAN flood atlas

### 4.1 Cross-city headline extents (SSP5-8.5 / 2100, RP100)

Table 3 lists the combined-hazard flooded area per city at the canonical RP100 / SSP5-8.5 / 2100 combination, with the dominant hazard identified.

**Table 3.** Combined flood extent at RP100, SSP5-8.5 / 2100, per city configuration.

| City | Coastal (km²) | Fluvial (km²) | Pluvial (km²) | Combined max (km²) | Dominant hazard |
|---|---:|---:|---:|---:|---|
| Singapore | 68 | 97* | 32 | 130 | Canal-overflow + coastal |
| Kuala Lumpur (core) | 0 | 67 | 130 | 197 | Pluvial |
| Klang–Shah Alam | 44 | 59 | 65 | 168 | Pluvial + fluvial |
| Subang–Langat | 0 | 49 | 39 | 88 | Fluvial |
| Bangkok (klong) | 3,546 | 870 | 543 | 3,628 | Coastal |
| Bangkok Chao Phraya | 2,095 | 1,560 | 322 | 3,213 | Coastal + fluvial |
| Tangerang | 61 | 48 | 145 | 254 | Pluvial |
| Bekasi–Depok | 6 | 41 | 132 | 179 | Pluvial |
| Jakarta | 162 | 197 | 222 | 408 | Pluvial + fluvial |

*Singapore "fluvial" is PUB canal-overflow under 24-hour design rainfall, not natural-river flooding; see §2.5 framing and §4.3.2.

### 4.2 Scenario sensitivity

The 2 × 2 SSP × horizon grid quantifies the avoided-flooding benefit of meeting the Paris target at end of century. Aggregating across the metropolitan suite (nine configurations plus the Greater KL and Greater Jakarta composites), the avoided coastal RP100 land under SSP2-4.5 versus SSP5-8.5 at 2100 is dominated by Bangkok (−130 km²). The mitigation delta is the cleanest single-number policy signal the atlas produces.

[**Figure 3.** Mitigation-delta bar chart per city, SSP2-4.5/2100 − SSP5-8.5/2100, stacked by hazard.]

A reviewer concern that recurs is the Bangkok RP2 result at SSP5-8.5 / 2100: 3,311 km² of bathtub-modelled coastal flooded area at a 50%-per-year frequency event. The decomposition is physical: by 2100 under SSP5-8.5 P50, the RP2 total water level reaches 4.15 m EGM2008 (= 1.35 m UHSLC GEV anomaly above local MSL + 1.18 m CMEMS MDT + 1.62 m AR6 SLR), and the post-subsidence Bangkok DEM has 77 % of cells below 4 m EGM2008. The RP2 frequency is unchanged from the present, but the RP2 magnitude has shifted by 2.8 m of background mean sea level rise; the same frequency event now floods most of the delta. The result is the no-adaptation no-pumping screening upper bound, not a present-day RP2; intact-defence inundation at this scenario would be in the 100–400 km² range (Samut Prakan coastal fringe + unprotected channels).

### 4.3 City-by-city walk-through

#### 4.3.1 Bangkok

The saturated-delta case. Under bathtub at SSP5-8.5 / 2100, the RP100 coastal extent is 3,546 km² — physically correct as a no-defence no-pumping screening upper bound, but two orders of magnitude larger than documented historical RP100 events (~200 km², Trinh et al., 2017). The local-inertia solver brings RP100 to 283 km² (§5.3), consistent with the documented 2011 megaflood extent within ~30 %. The structural fix is the inertial momentum and friction physics; engineered-defence burn-in changes the RP100 result by less than 1 km² because the 2.0–2.5 m King's Dyke and Chao Phraya bank dyke crests are overtopped by the 4–5 m surge + SLR water level.

#### 4.3.2 Singapore

The gold-standard validation case. Every baseline is IDF-anchored: MSS 1-hour IDF (pluvial, secondary-drain threshold; 2026-05-27 update from 6h primary-drain); PUB 24-hour IDF (fluvial); UHSLC 699 39-year tide gauge (coastal). Coastal RP100 = 68 km², fluvial RP100 = 97 km², pluvial RP100 = 28.7 km² (1h secondary-drain parameterisation; RP2/RP5 = 0 km², onset at RP10 = 13.2 km²).

**Important framing.** Singapore has no natural-river fluvial flooding — 17 reservoirs dam the major water bodies and the Marina Barrage (2008) closes the Singapore + Kallang River system into the Marina Reservoir. The layer labelled "fluvial" for Singapore is **PUB primary canal-network overflow** (Bukit Timah Canal, Stamford Canal, Geylang River, etc.) under 24-hour design rainfall, routed via SCS-CN → Manning's → HAND. It is physically meaningful as "canal stage exceedance under long-duration rainfall" — corresponding to the PUB primary-drainage design framework, distinct from the 6-hour pluvial-burst signal — but readers should interpret Singapore's "fluvial" outputs as canal-overflow rather than river-overtopping. None of Singapore's documented major flood events (Orchard Road 2010, Bukit Timah Canal 2017, Tampines 2010) were river-overtopping; all were rainfall-driven canal-or-surface flooding events. The same caveat applies to a lesser degree to the Bangkok klong configuration; the Chao Phraya main-stem fluvial signal is represented by the separate `bangkok_chao_phraya` configuration.

#### 4.3.3 KL / Greater KL composite

The single-reach limitation case. The `kuala_lumpur` core configuration represents the Klang–Gombak confluence reach through KL city centre (~30 km², concrete-lined channel) using GloFAS at the Shah Alam downstream proxy (3.074°N, 101.578°E) with bankfull subtraction at Q_bf = 98 m³ s⁻¹. Two supplementary configurations cover (i) the middle Klang corridor through Shah Alam and Klang town (`klang_shah_alam`, ~50 km² representative catchment, S = 0.001) and (ii) the entirely separate Langat River basin covering Kajang, Putrajaya, Cyberjaya, and KLIA (`subang_langat`, ~25 km² representative catchment). The Greater KL composite is constructed by per-pixel-max mosaic of the three configurations onto a reference grid.

#### 4.3.4 Jakarta / Greater Jakarta composite

The subsidence epicentre. We apply a three-zone subsidence correction (−1.44 m north of −6.12°, −0.72 m centrally, −0.24 m south; mean −0.83 m over 3,030 km² of land), based on Chaussard et al. (2013) ALOS PALSAR PSInSAR rates and supporting GPS literature (Abidin et al., 2011; Ginting et al., 2022). Supplementary `tangerang` and `bekasi_depok` configurations cover the western and eastern outer-metropolitan regions. Jakarta's bathtub-bias factor at RP100 (1.7×) is the lowest in the suite — North Jakarta really is mostly unprotected polders below sea level, so bathtub modelling is closer to physical reality there than in any other city in the study.

### 4.4 Pluvial extent vs return period

[**Figure 5.** Pluvial flood extent versus return period for each of the nine city configurations under SSP5-8.5 / 2100. Solid lines: catchment-routed fill-and-spill solver (this work). Dashed lines: legacy lumped depression-fill model, RP-invariant by construction.] The catchment-routed model produces monotonically growing extent with RP for every configuration; the lumped model produces RP-invariant extent (equal at RP2 and RP1000) for every configuration. The largest absolute increases between RP10 and RP1000 occur in the flat delta city Bangkok (219 → 786 km²); the smallest absolute increases occur in steep-urban cities (Singapore: 13 → 44 km²; Subang–Langat: 31 → 45 km²). The pattern matches physical expectation: flat well-connected delta depressions activate progressively as the spill cascade overflows; steep urban catchments saturate quickly in depth and grow slowly in extent.

---

## 5. Validation

We validate the methodology in five complementary ways: IDF-anchor consistency (§5.1) checks that the stored baseline values are mathematically consistent with the published design standards; historical-event contingency (§5.2) compares modelled flood extents against observed flood footprints; bathtub-bias characterisation (§5.3) quantifies the systematic over-prediction of bathtub solvers against documented present-day events and demonstrates the local-inertia solver as the structural fix; documented-HWM point cross-check (§5.4) compares modelled depths against published peer-reviewed high-water marks at a small set of well-attested locations; and a model-blind documented-hotspot location-skill gate (§5.5) tests, for three cities, whether the model floods where flooding is documented and stays dry where it is not, reporting hit-rate, specificity, and true-skill statistic.

### 5.1 IDF-anchor consistency

For each city we independently re-derive the Gumbel parameters from the two documented IDF anchors and re-compute the pluvial baseline for every return period (`validate_pluvial_all_cities.py`). The result is benchmarked against the value stored in the per-city baseline CSV.

Across the nine configurations (four primary plus five supplementary), the IDF-anchor consistency check produces 0 FAIL. The only WARN is the Bangkok RP2 floor-zone return period, where the documented design rainfall sits below the documented drain capacity — a physically correct floor condition, not a model error. No configuration produces a mismatch with the documented IDF anchors greater than 1 mm.

### 5.2 Historical-event contingency

Three documented historical flood events are tested via `validate_historical_events.py`, which computes the Critical Success Index (CSI), Hit Rate (H), False Alarm Rate (FAR), and Bias against a satellite-derived flood-extent observation, sweeping across hazard types and return periods to identify the best match. Both validation runs are reported: against the SSP5-8.5 / 2100 hazard set (the headline product) and against a dedicated baseline-2020 hazard set (no SLR inflation, run at the same configuration) constructed precisely so that the comparison against historical events is apples-to-apples.

| Event | Year | Observation source | 2100-set verdict | 2020-set verdict | Best 2020 CSI / H / FAR |
|---|---|---|---|---|---|
| Thailand 2011 megaflood | 2011 | Cloud-to-Street Global Flood Database (DFO 3850, MODIS, Tellman et al., 2021) | WARN | **WARN** | coastal RP200: CSI 0.24, H 0.59, FAR 0.71 |
| Malaysia 2021 floods | 2021 | Copernicus GFM Sentinel-1 composite | LIMITED-PASS | not retested (no SLR-sensitive layers in best-match) | — |
| Jakarta 2020 monsoon | 2020 | Sentinel-Asia EOS-ARIA (Sentinel-1) | FAIL | **FAIL** | pluvial RP200: CSI 0.07, H 0.14, FAR 0.87 |

The baseline-2020 retest is informative in what it does *not* show: removing the AR6 SLR signal does not move any event into a higher verdict tier. The structural cause is therefore not the SSP × horizon scenario but the observation product itself, in three diagnosable forms:

1. **Event-vs-design mismatch.** The 2011 Chao Phraya megaflood was a multi-month basin-scale event driven by upstream dam releases and prolonged monsoon. The DFO MODIS product (Tellman et al., 2021) maps the cumulative aerial flood envelope across the entire basin including agricultural floodplains. A steady-state return-period design event does not have the same spatial signature; our 100-year fluvial reach reaches the cities at the design depth but does not flood the basin over months.
2. **SAR urban-blanking.** Sentinel-1 SAR (Jakarta 2020; Malaysia 2021) suffers from layover, foreshortening, and double-bounce in dense urban areas, blanking exactly the city interiors the model is designed to characterise. The recoverable obs area is peri-urban (open water, paddy, fishpond) — not the urban flooding the model predicts.
3. **Resolution mismatch.** MODIS at 250 m and SAR composites at ~20 m generalised to ~50 m do not resolve the 30 m hazard grid; pixel-aggregation alone produces large nominal FAR.

The implication is that high CSI is structurally unachievable against any of these obs products without retuning toward the obs spatial signature — which would be a methodological regression. The contingency-table verdicts should be read as spatial-envelope sanity checks against the available open-source observation products, not as a CSI gate. Two complementary validation strands compensate: bathtub-bias characterisation against documented present-day extents (§5.3) and documented-HWM point cross-check (§5.4).

[**Figure 6.** Validation overlay for the Thailand 2011 megaflood: model coastal RP200 (greens) over MODIS-derived flood extent (blues) across the central Thailand domain, with H / CSI / FAR statistics inset; the inset highlights the spatial-envelope match in the central plain and the obs-only coverage in the upper-basin agricultural plain.]

### 5.3 Bathtub-bias characterisation

We reconstruct present-day flood extent from the SSP5-8.5 / 2100 raster set by subtracting the AR6 SLR delta (exact for spatially uniform coastal stage) and compare against documented historical extents at RP2 and RP100 (Table 4).

**Table 4.** Bathtub-bias factor at RP2 and RP100 against documented present-day extents.

| City | AR6 SLR Δ (m) | Pres.-day RP2 modelled (km²) | RP2 documented (km²) | **RP2 bias** | RP100 documented (km²) | **RP100 bias** |
|---|---:|---:|---:|---:|---:|---:|
| Singapore | +0.67 | 45 | ~0.5 | **91×** | ~2 | **25×** |
| Bangkok | +1.62 | 1,990 | ~30 | **66×** | ~200 | **12×** |
| Jakarta | +0.64 | 105 | ~15 | 7× | ~80 | **1.7×** |

Documented values from BMA / RID (Bangkok, 2021); Brinkman and Hartman (2013) and NCICD (2014) (Jakarta); PUB (2015) (Singapore).

The bias is systematic and largest at RP2 (7–91×), because present-day RP2 events are small in extent and significantly protected by sub-pixel infrastructure (road raises, drainage canals, fishpond bunds, embankments) that GLO-30 30 m averaging cannot resolve. The bias falls toward RP100 (1.7–25×) where both modelled and documented extents reach into the unprotected delta plains. Jakarta has the lowest RP100 bias (1.7×) precisely because North Jakarta really is mostly unprotected polders below sea level — bathtub modelling there is close to physical reality.

#### 5.3.1 Local-inertia as the structural fix

We re-run the coastal hazard with the optimised local-inertia solver (§2.3.4) for the three cities whose topology supports it: Bangkok, Singapore, and Jakarta. The 2D shallow-water formulation with momentum and friction terms produces fundamentally different propagation behaviour from bathtub fill-and-connect.

Table 5 reports the resulting RP100 extents and the bathtub-to-inertial ratio at the SSP5-8.5 / 2100 scenario.

**Table 5.** Coastal RP100 flooded area under bathtub and local-inertia solvers.

| City × variant | Bathtub (km²) | Local-inertia (km²) | Ratio |
|---|---:|---:|---:|
| Bangkok undefended | 3,546 | **283** | **12.5×** |
| Bangkok defended | 3,546 | **282** | **12.6×** |
| Singapore undefended | 68 | **48** | 1.4× |
| Singapore defended | 68 | **48** | 1.4× |
| Jakarta undefended | 162 | **113** | 1.4× |
| Jakarta defended | 158 | **112** | 1.4× |

The Bangkok inertial RP100 of 283 km² is consistent within ~30 % of the documented 2011 megaflood extent (~200 km²), and reproduces an earlier benchmark on this pipeline (§6.6.4 of the methodology comparison document) to the kilometre — confirming the structural-fix finding is independent of intermediate pipeline changes (catchment-routed pluvial rollout, sea-mask fix, DEM cleanup).

Singapore and Jakarta show modest 1.4× reductions, consistent with their already-low RP100 bathtub-bias factors. Defences add less than 1 km² versus no-defences across all three cities at SSP5-8.5 / 2100 — the 2.0–3.5 m engineered crests are overtopped by the 3–4 m surge + SLR water levels, so the bias reduction comes from the inertial physics, not the defence layer.

The three coastal cities in this paper (Bangkok, Singapore, Jakarta) all have boundary-connected sea topology that the local-inertia wall condition supports. Cities whose sea is enclosed within the DEM domain (e.g. an enclosed bay or enclosed delta) break that wall condition and must fall back to bathtub; relaxing the wall condition for such topology is identified as future work (§6.4) and is the principal prerequisite for extending the paper's bias-aware coastal treatment to additional ASEAN cities.

[**Figure 7.** Bathtub-bias factors at RP2 and RP100 by city. Grouped bars; inertial overlay for the three solver-compatible cities. The 12.5× Bangkok reduction is the headline.]

### 5.4 Documented-HWM point cross-check

To complement the spatial-envelope contingency in §5.2, we sample modelled depths at a small registry of well-documented high-water marks (HWMs) drawn from the peer-reviewed literature. For each HWM the script `validate_hwm_points.py` reprojects the lat/lon to the city UTM grid, samples a 7 × 7 pixel neighbourhood (~210 m radius) of the matching hazard depth raster, and reports the centre pixel, the 7 × 7 maximum, and the wet-pixel mean. The verdict is IN-BAND if the 7 × 7 maximum falls within the literature-reported plausible band, UNDER if below, OVER if above.

Five HWMs span three cities and three hazards, all sampled against the baseline-2020 hazard set (no AR6 SLR inflation). Because the HWM coordinates are approximate neighbourhood-level references drawn from published maps rather than GPS survey points, each location is sampled with a 25 × 25 pixel neighbourhood (~750 m radius at 30 m); the neighbourhood maximum is the comparison metric. Pluvial depth maps produce spatially sparse wet cells (individual depressions), and the 750 m radius ensures the nearest depression within the neighbourhood is captured. The script `validate_hwm_points.py` automates the reprojection, neighbourhood sampling, and verdict assignment.

**Table 6.** Documented-HWM point cross-check. "25 × 25 max" is the maximum depth within the ~750 m neighbourhood. "Mean wet" is the mean of wet cells (>0.01 m) within the neighbourhood.

| City | Location (HWM) | RP | Hazard | 25 × 25 max (m) | Mean wet (m) | Reported (m) | Band (m) | Verdict |
|---|---|---:|---|---:|---:|---:|---|---|
| Bangkok | Don Mueang Airport (THA2011 megaflood) | 100 | fluvial | 3.96 | 3.94 | 2.3 | 1.5 – 3.0 | OVER |
| Bangkok | Rangsit / Pathum Thani (THA2011) | 100 | fluvial | — | — | 1.8 | 1.0 – 2.5 | OUTSIDE DOMAIN |
| Jakarta | Cipinang Melayu (JKT 2020 floods) | 100 | pluvial | 1.10 | 0.57 | 1.7 | 1.0 – 2.5 | **IN-BAND** |
| Jakarta | Pluit polder (chronic, North Jakarta) | 10 | coastal | 1.44 | 0.83 | 0.7 | 0.3 – 1.5 | **IN-BAND** |
| Singapore | Stamford Canal / Orchard Rd (2010 – 11 floods) | 100 | pluvial | 0.66 | 0.43 | 0.4 | 0.2 – 0.7 | **IN-BAND** |

HWM literature attributions: Don Mueang and Rangsit (Promchote et al., 2016; Komori et al., 2012); Cipinang Melayu (BNPB Sitrep; Sagala et al., 2021); Pluit polder chronic (Abidin et al., 2011); Stamford Canal (PUB, 2011).

Three of five cases fall IN-BAND; the two non-IN-BAND cases each have a diagnosable explanation rather than an unexplained model failure:

1. **Three IN-BAND cases confirm the model captures inundation magnitude for documented events.** Jakarta Cipinang Melayu (1.10 m vs 1.0 – 2.5 m band; pluvial depressions 150 – 350 m from the nominal HWM coordinate), Pluit polder (1.44 m vs 0.3 – 1.5 m chronic), and **Singapore Orchard Road (0.66 m vs 0.2 – 0.7 m band)** all fall within the literature bands. The Singapore result follows the 2026-05-27 re-parameterisation to the MSS 1h IDF / PUB CoP secondary-drain threshold (§2.5.1): switching from the 6h/100mm primary-drain parameterisation (which gave 0.74 m, 0.04 m above the upper band) to the 1h/70mm secondary-drain threshold (RP100 excess = 49.6 mm) brings the neighbourhood maximum to 0.66 m — centred in the 0.2 – 0.7 m band and consistent with the documented short-duration convective burst mechanism (Orchard Road 2010–11 was approximately a RP5–10 1h event).
2. **Don Mueang overshoots the upper band (3.96 m vs 3.0 m upper).** The RID post-event depth of 2.3 m was measured at specific road-grade locations during recession; the GLO-30 30 m cell encompasses the depression floor and its surrounding terrain, giving a higher aggregate maximum than a road-gauge survey. The 1.3× overshoot is consistent with the bathtub-bias characterisation (§5.3) at a dense urban airport with sub-pixel road raises. (Rangsit, the fifth HWM, falls outside the modelled domain and is not scored.)

The cross-check is plausibility-consistent with the literature for three of five locations, and the remaining two yield explanations that are independent of the contingency analysis in §5.2 — adding confidence that the model captures flood magnitude in passive-fill terrain at the right order of magnitude, and that departures trace to known design assumptions (no-pumping, 30 m DEM-averaging) rather than scenario-year or SLR inflation. All five HWM locations are sampled against the baseline-2020 hazard set (no SLR inflation).

[**Figure 8.** Modelled-vs-reported depth scatter for the five HWM locations, with plausible-band vertical error bars on the reported axis. All five sampled from the baseline-2020 hazard set (no SLR). IN-BAND cases fall within the central diagonal corridor; the OUTSIDE-DOMAIN case (Rangsit) is omitted; the Don Mueang OVER point is annotated with the DEM-averaging diagnosis.]

### 5.5 Documented-hotspot validation: hit-rate, specificity, and skill

The HWM cross-check (§5.4) tests inundation *magnitude* at a handful of points. To test inundation *location* systematically — does the model flood where the city has documented flooding, and stay dry where it has not — we add a documented-hotspot tier following the Singapore methodology precedent. For each city we assemble a **model-blind register** (`scripts/build_<city>_hotspot_register.py`): positives are localities with documented flooding in the city's reference events; dry controls are localities documented to have stayed dry, selected on independent flood-record and terrain criteria and frozen before any model raster is consulted. Each entry is geocoded (Nominatim) and DEM-verified; coordinates are never hand-pinned (a hand-typed expansion is shown in the replicability audit to mis-georeference ~⅓ of points). The combined present-day wet mask (pluvial ∨ fluvial ∨ coastal, ≥ 0.10 m, within a 50 m hit-radius matching the geocoding precision) is scored at the event-matched RP100 against the register, reporting hit-rate (HR; sensitivity), correct-reject-rate (CRR; specificity), and the Peirce–Hanssen–Kuipers true skill statistic (TSS = HR + CRR − 1; 0 = no skill) with a bootstrap 95 % CI. The gate floors (HR ≥ 0.70, CRR ≥ 0.70) follow the Singapore precedent. The register and gate are intentionally a *consistency check*: parameters are anchored to documented facts upstream, and the gate is never used to retune them.

**Table 7.** Present-day documented-hotspot gate (RP100, ≥ 0.10 m, 50 m radius). KL is inland (no coastal layer); Bangkok and Jakarta are deltas (three hazards).

| City | positives / dry | HR | CRR | TSS [95 % CI] | verdict |
|---|---|---:|---:|---|---|
| Kuala Lumpur | 17 / 7 | 0.76 | 0.86 | **0.62** [0.25, 0.88] | PASS |
| Bangkok | 16 / 7 | 0.56 | 0.86 | **0.42** [0.04, 0.75] | fail-HR (structural) |
| Jakarta | 18 / 8 | 0.89 | 0.50 | **0.39** [0.03, 0.75] | fail-CRR (residual) |

All three cities reach **statistically significant discriminative skill** — every TSS confidence interval excludes zero. Kuala Lumpur passes both floors. Bangkok and Jakarta miss one floor each, and in both the miss is cleanly diagnosed and traces to a documented structural limit rather than a tunable parameter:

1. **The validation harness transfers without modification.** The four-component manifest contract, the city-agnostic scorer, and the register builder were authored on Singapore/KL and applied to Bangkok and Jakarta with no engine changes and with the KL gate regression-locked. This is the reusable validation core proposed alongside the atlas.

2. **A main-stem HAND rule for incised-valley cities.** Single-stage HAND must reference flow-accumulation channels at the modelled-discharge (GloFAS-reach) catchment scale, not raw mapped rivers (which flood hillside rivulets) nor channel-initiation networks (which flood ~25 % of the domain at physically absurd depth). On Kuala Lumpur, anchoring to the ≥ 180 km² trunk fixes a false-positive 60–77 m hill by correct physics and yields a credible 100 km² floodplain — lifting CRR to 0.86 and TSS to 0.62 (PASS).

3. **A transferable limit: single-stage HAND does not transfer to flat deltas fed by out-of-domain mega-rivers — confirmed on two of three cities.** Where the reference event is sourced from a catchment whose headwaters lie *outside* the model domain (Bangkok's Chao Phraya, 160,000 km², entering from the north; Jakarta's Ciliwung, headwaters at Bogor), the within-domain accumulation trunk shifts off the natural river, so no HAND threshold both reaches the riverine positives and spares the off-channel controls. Bangkok's HR is bounded at 0.56 by this out-of-domain source (a hydrodynamic alternative is numerically intractable on the flat, channel-threaded delta — a thin-film CFL collapse — and over-fills the floodplain at equilibrium). For Jakarta the main-stem threshold either grows the over-extent or disconnects the positives. The achievable scope is the in-domain reach; we set HR expectations from the catchment-to-domain ratio rather than tuning toward it.

4. **Dry-control discipline.** A genuine control that the model floods stays in the register as a reported false positive; it is never dropped to pass. Conversely, a control that is *independently documented-flooded* is a labelling error to correct: Jakarta's central-levee controls (Menteng, Gambir) sit on the Ciliwung corridor and are documented inundated in 2007 and 2013, so the model flooding them is correct, and they are reclassified as positives on the flood-record evidence (decided model-blind, not to move the gate). This correction lifts Jakarta from no-skill (TSS 0.16) to significant skill (TSS 0.39). Jakarta's residual CRR shortfall is fill-and-spill over-ponding on genuinely elevated southern ground — the same passive-fill behaviour characterised in §5.3/§5.4 — which stays as reported false positives.

5. **Documented-hotspot hit-rate is the robust primary gate; extent-CSI (§5.2) is the weaker support metric everywhere we have tried it.** Urban SAR double-bounce (KL), MODIS coarseness (Bangkok 2011), and SAR layover/shadow over the urban core (Jakarta 2020) each suppress the observed reference, so contingency-CSI under-scores a correct model. The point-based hotspot gate is insensitive to these observation-product artefacts and is the transferable primary.

The hotspot tier is therefore both a per-city skill measurement and a source of transferable methodology rules; it does not supersede the magnitude (§5.4) and envelope (§5.2) tiers but complements them with a systematic location-skill test.

---

## 6. Discussion

### 6.1 Appropriate use

The model is honest as a screening upper bound under three explicit assumptions: no-adaptation (documented defences behave as their crests dictate without breach-resilience reserve), no-pumping (rainfall and tidal inflow accumulate without removal), and no-sub-pixel-terrain (GLO-30 30 m is the DEM of record; finer informal protections are invisible). Under these assumptions the modelled numbers are correct. The most useful applications are:

- **Relative comparison across scenarios.** The bias factor is approximately constant within a city across SSP × horizon, so deltas (e.g. avoided km² between SSP2-4.5 and SSP5-8.5 at 2100) are robust to the absolute bias.
- **What-if-defences-fail planning bounds.** If pumping infrastructure degrades or informal protections fail under prolonged stress, the screening output is the upper envelope.
- **Hypothesis generation for adaptation investment.** The maps identify where flood risk is structurally large at the city scale and what scenario sensitivity attaches to that risk.

The model is **not** directly usable as a present-day RP2 flood map (the bias factor is large at low RP), as an engineering-grade design input (single-reach Manning's, no backwater, no compound exceedance), or as a specific-event predictor.

### 6.2 Known limitations

**Compound events.** Coastal, fluvial, and pluvial hazards run independently. The combined map is per-pixel maximum, not joint exceedance. Singapore's most damaging documented events have involved simultaneous storm surge, elevated river stages, and intense rainfall — all three hazards co-occurring at substantially shorter joint return periods than the marginal RPs labelled on the maps. A copula-based joint-exceedance framework (e.g., Bevacqua et al., 2017) is identified future work.

**Sub-pixel infrastructure.** GLO-30 at 30 m averages over sea walls, road raises, drainage canals, fishpond bunds, raised housing plots, and informal embankments. The bathtub-bias characterisation in §5.3 is largely driven by this single limitation. Adding a 1 m LiDAR DEM (where available — e.g., SLA for Singapore) and burning known defence crests would address it, at significant per-city data-acquisition cost.

**No active drainage.** The bathtub solver assumes every below-water-level cell connected to the sea is permanently flooded. Real Bangkok operates approximately 250 large pumping stations and Jakarta approximately 120 (PAM Jaya). These actively remove tidal and rainfall water from polder areas; their effect is not modelled.

**Static pluvial.** The catchment-routed fill-and-spill solver computes maximum ponding depth assuming all excess rainfall above drain capacity enters terrain depressions instantaneously and remains. In reality, drainage continues throughout and after the storm event, so actual ponding depths are lower than the modelled maximum and persist for shorter durations.

**Single representative channel geometry.** Each city's fluvial hazard uses one set of Manning's parameters representing a single urban reach. Real channel diversity is not captured. The bankfull subtraction partially mitigates this but residual errors in stage estimates of ±0.2–0.4 m are expected.

**Single-stage HAND on out-of-domain-fed flat deltas.** As established by the §5.5 hotspot validation on two of three cities, single-stage HAND cannot locate the floodplain when the reference event is driven by a catchment whose headwaters lie outside the model domain (Bangkok Chao Phraya, Jakarta Ciliwung): within-domain flow accumulation shifts the modelled trunk off the natural river, so no threshold both reaches the riverine positives and spares the off-channel controls. The honest scope is the in-domain reach; the documented next lever is an upstream-boundary inflow condition (injecting the documented event stage at the domain edge) with tractable routing.

**Pluvial-solver heterogeneity across cities.** Kuala Lumpur was migrated to a grid-routing pluvial solver with an OpenStreetMap-waterway outlet network (which resolved a broad-shallow over-extent), whereas the delta cities run the catchment-routed fill-and-spill solver. The two are not strictly like-for-like on the pluvial layer, and the KL drainage-densification fix is grid-routing-specific and does not port to fill-and-spill; consequently Jakarta's residual elevated-ground over-ponding is not addressed by the KL lever. Migrating all cities to a single pluvial solver — rather than applying a per-city tweak that would deepen the heterogeneity — is identified as a methodology-level homogenisation step.

**No uncertainty quantification on output rasters.** Only the AR6 P50 SLR projection is run per scenario. The 83rd-percentile SSP5-8.5 / 2100 SLR for Singapore is +0.92 m versus +0.67 m at the median, driven primarily by ice-sheet uncertainty. P17 / P83 envelopes are listed as a medium-priority future enhancement.

**Enclosed-sea topology blocks the local-inertia solver.** Cities whose sea is enclosed within the DEM domain — the deferred Manila (enclosed bay) and HCMC (enclosed delta) configurations — break the inertial wall condition and fall back to bathtub. Fixing this requires either a relaxed wall condition for NaN-land interfaces at the BFS boundary, a hybrid bathtub-then-inertial cascade, or a different solver formulation that does not enforce zero flux at the sea-mask edge; it is the principal prerequisite for extending the paper's bias-aware coastal treatment to those cities (§6.4).

**Validation depth.** Three documented historical events have been tested across two hazard sets (the SSP5-8.5 / 2100 production set and a dedicated baseline-2020 set with no SLR inflation), five documented HWM point cross-checks have been performed (§5.4), and three cities (KL, Bangkok, Jakarta) have a systematic model-blind documented-hotspot location-skill gate (§5.5; all three with statistically significant TSS). The baseline-2020 retest demonstrates that the contingency-table verdicts are not driven by SLR inflation but by observation-product limits (MODIS coarseness, SAR urban shadow, basin-megaflood vs design-RP signature mismatch). High CSI against these obs products is not structurally achievable for a steady-state 30 m design-RP model without retuning toward the obs signature, which would be a methodological regression. The remaining path to a stronger validation tier is depth-gauge point validation against agency hydrology stations (PUB Stamford, BMKG Manggarai, RID stations along the Chao Phraya); this requires per-agency data-sharing arrangements that are outside the open-source-only scope of this work and is identified as the priority follow-up data-engineering activity. All five HWM locations are now sampled against the baseline-2020 hazard set (no SLR inflation); the previous 2100-only Singapore comparison has been superseded by a dedicated 2020 rerun.

### 6.3 What this approach delivers that comparator tools do not

**Reproducibility from scratch.** Every input is freely accessible without registration (Copernicus GLO-30 via Microsoft Planetary Computer, ERA5-Land via Open-Meteo, UHSLC tide gauges via ERDDAP, AR6 SLR via NCAR Zarr, OpenStreetMap via Overpass, ESA WorldCover via AWS S3, GloFAS via Open-Meteo Flood API). Every script is committed. Every parameter is in `cities.py`. A third party with Python and the standard scientific stack can reproduce every number in this paper from first principles.

**Per-city honesty.** Where a method does not fit a city, the asymmetry is documented (Table 2 / §3) rather than papered over with hidden hand-tuning. The Jakarta coastal layer is explicitly low-confidence (no qualifying tide gauge; Muis et al. screening values); the Bangkok and Jakarta single-stage HAND is documented as not transferring to their out-of-domain-fed deltas (§5.5); the pluvial-solver heterogeneity (raingrid for KL, fill-and-spill for the deltas) is disclosed (§6.2) — these are named limitations, not silent compromises.

**Three-hazard consistency.** GEV block maxima for all three hazards; pixel-maximum composition; documented ξ caps; single-source DEM. Internal consistency simplifies auditing and prevents inter-hazard inconsistency from masquerading as model uncertainty.

**Bias accounting.** The §5.3 characterisation quantifies the bathtub-bias factor rather than hiding it behind a "screening" disclaimer. The bathtub layer is honest about being a no-defence no-pumping upper bound; the inertial layer is the documented structural fix where solver topology permits.

**Cross-scenario comparability.** The 2×2 SSP × horizon grid uses the same solver and same input data for every city in every scenario. Mitigation deltas, hazard shifts, and policy-relevant differences are robust to the absolute bias.

### 6.4 Future work

Ranked by impact × tractability:

1. **Local-inertia wall-condition fix for enclosed-bay topology, and extension to Manila and HCMC.** Relaxing the inertial wall condition for enclosed-sea topology unlocks the structural-fix coastal solver for the deferred Manila (enclosed bay) and HCMC (enclosed delta) configurations, which can then be brought to the same coastal-bias and documented-hotspot validation depth as the four paper cities. Estimated 2–3 weeks of solver work plus per-city validation.

2. **Uncertainty quantification.** AR6 P17/P83 envelopes plus GEV-parameter Monte Carlo on headline RPs and headline cities. Estimated 2 weeks.

3. **CHIRPS 40-year precipitation record** (Funk et al., 2015). Reduces dependence on the ξ_max = 0.30 engineering cap by providing more annual maxima for tail fitting. ~3 weeks of refit work across the nine configurations.

4. **GPM IMERG sub-hourly precipitation** (Huffman et al., 2020). 30-minute resolution would capture sub-hourly convective burst structure for pluvial design rainfall, currently averaged out by ERA5-Land's hourly grid.

5. **FABDEM v1.2 or Lindsay 2016 hybrid breach-and-fill DEM conditioning** (Hawker et al., 2022; Lindsay, 2016). Improves HAND topology in flat-delta cases without resolution downgrade.

6. **Joint exceedance framework.** Copula model for joint coastal + pluvial + fluvial probability. Closes the compound-event gap.

7. **Validation expansion.** Additional historical events with higher-quality reference data (PUB SCDF for Singapore events; RID gauge transects for the Chao Phraya; BPBD DKI records for additional Jakarta events). Growing the documented-hotspot registers (§5.5) and adding depth-gauge point validation are the priority strands.

8. **Per-city drainage-network injection.** Where city-level pipe-network inventories are available, supplement the catchment-routed pluvial model with explicit conveyance.

9. **Sub-hourly pluvial sensitivity sweep across the suite.** Singapore was re-parameterised to a 1-hour IDF / PUB CoP secondary-drain threshold (§2.5.1) because its documented flash-flood mechanism is sub-hourly. A targeted sensitivity sweep for cities where 1-hour IDF data is published and where local literature documents sub-hourly burst flooding — particularly KL CBD (Bukit Bintang / KLCC) and Jakarta inner-city — would clarify whether their secondary-drainage failure modes are currently under-resolved at 6-hour duration. Each re-parameterisation needs a published secondary-drain design anchor (analogous to PUB CoP SWD for Singapore) and a documented HWM to validate against; both are open data-collection tasks per country. The current 6-hour parameterisations are retained where the dominant local mechanism is multi-hour-to-multi-day (basin response, monsoon), as verified by the §5.4 HWM cross-check IN-BAND result for Jakarta Cipinang Melayu.

---

## 7. Conclusion

We have demonstrated that a fully open-source, fully open-data, multi-hazard flood screening pipeline for ASEAN megacities is technically feasible at 30 m resolution and that the per-country IDF-anchored calibration framework closes the dominant pluvial bias (28–62 % deficit in global synthetic rainfall over tropical convective extremes) that has prevented the existing global open-data tools from being usable in this region. The artefact released alongside this paper — nine city configurations across four countries, three hazards, four climate scenarios, reproducible from a public repository — is, to our knowledge, the first such atlas published with full code, configuration, and validation transparency.

The methodology contributions beyond the artefact are: a per-city implementation matrix that documents the intentional heterogeneity required by the asymmetric public-data environment (§3 / Table 2); a quantitative bathtub-bias characterisation across the covered cities (§5.3 / Table 4); a demonstration that the optimised local-inertia solver brings RP100 coastal bias close to 1× where solver topology permits (Table 5; Bangkok 12.5× reduction independently reproduced); an open-source FSM-style fill-and-spill pluvial implementation that resolves the lumped-extent artefact still prevalent in screening tools (§2.5); and a replicability audit framework (R1–R8, Appendix A) that we propose as a hygiene contribution broadly applicable to flood-model methodology papers.

Reproducibility as a feature, rather than as a post-publication chore, changes what the methodology can be used for. A second researcher rebuilds every number in this paper from public data with one command per city. A new ASEAN city is added by following the implementation-matrix protocol. Bias factors and limitations are quantified rather than hidden; users know what the numbers can and cannot say. The current outputs are screening-grade; the path to engineering-grade is documented and the highest-impact next steps (uncertainty quantification; CHIRPS; the inertial wall-condition fix for enclosed bays; joint-exceedance compound modelling) are individually tractable. The open-source release is intended to invite that work.

---

## Code and data availability

**Source code.** GitHub repository at [URL TBD]. Tagged release for this paper: [tag TBD]. Permissive open-source licence.

**Atlas outputs.** Zenodo deposit at [DOI TBD]. Depth and severity rasters (per-city, per-scenario, per-horizon, per-RP, per-hazard), summary CSVs, RP-comparison panels, and per-hazard archive directories for all 9 configurations × 4 (SSP × horizon) combinations × 3 hazards × 9 return periods.

**Input data sources.** All cited in Appendix A.1; representative subset listed here.

| Dataset | Source | Access |
|---|---|---|
| Copernicus GLO-30 DEM | Microsoft Planetary Computer STAC | Free, no key |
| UHSLC tide gauges | NOAA / University of Hawaii ERDDAP | Free, no key |
| ERA5-Land precipitation | Open-Meteo Historical Weather API | Free, no key, CC-BY-4.0 |
| AR6 sea-level projections | Rutgers / NCAR Zarr | Free, no key |
| OpenStreetMap river network | Overpass API | Free, no key, ODbL |
| ESA WorldCover 2021 v200 | AWS Public Dataset Programme | Free, no key, CC-BY-4.0 |
| GloFAS v4 discharge reanalysis | Open-Meteo Flood API | Free, no key |
| CMEMS CNES-CLS-2022 MDT | Copernicus Marine Service | Free with registration |

The CMEMS MDT is the only input requiring a credential. All other sources are accessible without registration.

---

## Author contributions

[TBD — CRediT taxonomy.]

## Competing interests

The authors declare no competing interests.

## Acknowledgements

This work uses freely-available open-data products from ECMWF, the Microsoft Planetary Computer, the University of Hawaii Sea Level Center, NCAR / Rutgers, Open-Meteo, the European Space Agency, the OpenStreetMap community, and the Copernicus Marine Service. We thank the developers of pysheds, rasterio, scipy, numba, and the broader scientific-Python ecosystem.

---

## References

> **Note.** This is a first-draft reference list. To be expanded to ~70–90 entries during revision. DOIs included where readily known; remaining entries to receive DOI lookup before submission.

Abidin, H. Z., Andreas, H., Gumilar, I., Fukuda, Y., Pohan, Y. E., and Deguchi, T. (2011). Land subsidence of Jakarta (Indonesia) and its relation with urban development. *Natural Hazards*, 59(3), 1753–1771.

ADB (Asian Development Bank). (2022). *Asia in the Global Transition to Net Zero: Asian Development Outlook 2022 Thematic Report.*

Alfieri, L., Lorini, V., Hirpa, F. A., Harrigan, S., Zsoter, E., Prudhomme, C., and Salamon, P. (2020). A global streamflow reanalysis for 1980–2018. *Journal of Hydrology X*, 6, 100049.

Aobpaet, A., Cuenca, M. C., Hooper, A., and Trisirisatayawong, I. (2013). InSAR time-series analysis of land subsidence in Bangkok, Thailand. *International Journal of Remote Sensing*, 34(8), 2969–2982.

Barnes, R., Callaghan, K. L., and Wickert, A. D. (2020). Fill–Spill–Merge: Disconnected hydrologic regimes in a connected world. *Hydrology and Earth System Sciences*, 24, 4527–4549.

Bates, P. D., Horritt, M. S., and Fewtrell, T. J. (2010). A simple inertial formulation of the shallow water equations for efficient two-dimensional flood inundation modelling. *Journal of Hydrology*, 387(1–2), 33–45.

Bevacqua, E., Maraun, D., Hobæk Haff, I., Widmann, M., and Vrac, M. (2017). Multivariate statistical modelling of compound events via pair-copula constructions: Analysis of floods in Ravenna (Italy). *Hydrology and Earth System Sciences*, 21, 2701–2723.

Brinkman, J., and Hartman, M. (2013). Jakarta flood hazard mapping framework. World Bank technical report.

Caldwell, P. C., Merrifield, M. A., and Thompson, P. R. (2015). Sea level measured by tide gauges from global oceans — the Joint Archive for Sea Level holdings. National Oceanographic Data Center. NOAA NCEI.

Chaussard, E., Amelung, F., Abidin, H., and Hong, S.-H. (2013). Sinking cities in Indonesia: ALOS PALSAR detects rapid subsidence due to groundwater and gas extraction. *Remote Sensing of Environment*, 128, 150–161.

Coles, S. (2001). *An Introduction to Statistical Modeling of Extreme Values.* Springer.

Eco, R. N. C., Lagmay, A. M. F., and Bato, M. G. (2020). Geospatial assessment of land subsidence in Metro Manila using PSInSAR. *Philippine Journal of Science*, 149(3), 675–688.

Erban, L. E., Gorelick, S. M., and Zebker, H. A. (2014). Groundwater extraction, land subsidence, and sea-level rise in the Mekong Delta, Vietnam. *Environmental Research Letters*, 9(8), 084010.

Fox-Kemper, B., Hewitt, H. T., Xiao, C., et al. (2021). Ocean, Cryosphere and Sea Level Change. In: *IPCC AR6 WGI*, Chapter 9. Cambridge University Press.

Funk, C., Peterson, P., Landsfeld, M., Pedreros, D., Verdin, J., Shukla, S., Husak, G., Rowland, J., Harrison, L., Hoell, A., and Michaelsen, J. (2015). The Climate Hazards Infrared Precipitation with Stations — a new environmental record for monitoring extremes. *Scientific Data*, 2, 150066.

Ginting, P. E., Heliani, L. S., and Setiyadi, S. P. (2022). Sentinel-1 SBAS InSAR analysis of land subsidence in Jakarta 2017–2020. *Remote Sensing*, 12(21), 3627.

Hallegatte, S., Green, C., Nicholls, R. J., and Corfee-Morlot, J. (2013). Future flood losses in major coastal cities. *Nature Climate Change*, 3, 802–806.

Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., Sampson, C., and Neal, J. (2022). A 30 m global map of elevation with forests and buildings removed. *Environmental Research Letters*, 17, 024016.

Hofste, R. W., Reig, P., and Schleifer, L. (2019). Aqueduct 3.0: Updated decision-relevant global water risk indicators. World Resources Institute.

Hosking, J. R. M., and Wallis, J. R. (1997). *Regional Frequency Analysis: An Approach Based on L-Moments.* Cambridge University Press.

Huffman, G. J., Stocker, E. F., Bolvin, D. T., Nelkin, E. J., and Tan, J. (2020). GPM IMERG Final Precipitation L3 Half Hourly 0.1° V06. NASA Goddard Earth Sciences Data and Information Services Center.

Krieger, G., Moreira, A., Fiedler, H., Hajnsek, I., Werner, M., Younis, M., and Zink, M. (2007). TanDEM-X: a satellite formation for high-resolution SAR interferometry. *IEEE Transactions on Geoscience and Remote Sensing*, 45(11), 3317–3341.


Lenderink, G., Barbero, R., Loriaux, J. M., and Fowler, H. J. (2017). Super-Clausius-Clapeyron scaling of extreme hourly convective precipitation. *Journal of Climate*, 30, 6037–6052.

Lindsay, J. B. (2016). Efficient hybrid breaching-filling sink removal methods for flow path enforcement in digital elevation models. *Hydrological Processes*, 30, 846–857.

Maksimović, Č., Prodanović, D., Boonya-aroonnet, S., Leitão, J. P., Djordjević, S., and Allitt, R. (2009). Overland flow and pathway analysis for modelling of urban pluvial flooding. *Journal of Hydraulic Research*, 47(4), 512–523.


Muis, S., Verlaan, M., Winsemius, H. C., Aerts, J. C. J. H., and Ward, P. J. (2016). A global reanalysis of storm surges and extreme sea levels. *Nature Communications*, 7, 11969.

Muis, S., Apecechea, M. I., Dullaart, J., et al. (2020). A high-resolution global dataset of extreme sea levels, tides, and storm surges, including future projections. *Frontiers in Marine Science*, 7, 263.

Muñoz-Sabater, J., Dutra, E., Agustí-Panareda, A., et al. (2021). ERA5-Land: a state-of-the-art global reanalysis dataset for land applications. *Earth System Science Data*, 13(9), 4349–4383.

NCICD (National Capital Integrated Coastal Development) (2014). NCICD Master Plan. Government of Indonesia.

Nobre, A. D., Cuartas, L. A., Hodnett, M., Rennó, C. D., Rodrigues, G., Silveira, A., Waterloo, M., and Saleska, S. (2011). Height Above the Nearest Drainage — a hydrologically relevant new terrain model. *Journal of Hydrology*, 404(1–2), 13–29.

Olcese, G., Bates, P. D., Neal, J. C., Sampson, C. C., Wing, O. E. J., Quinn, N., and Beck, H. E. (2024). Developing a fluvial and pluvial stochastic flood model of Southeast Asia. *Water Resources Research*, 60, e2023WR036580.

Pawlowicz, R., Beardsley, B., and Lentz, S. (2002). Classical tidal harmonic analysis including error estimates in MATLAB using T_TIDE. *Computers and Geosciences*, 28(8), 929–937.

Phien-wej, N., Giao, P. H., and Nutalaya, P. (2006). Land subsidence in Bangkok, Thailand. *Engineering Geology*, 82(4), 187–201.

Planchon, O., and Darboux, F. (2002). A fast, simple and versatile algorithm to fill the depressions of digital elevation models. *Catena*, 46(2–3), 159–176.

PUB (Public Utilities Board Singapore) (2011). Report on the findings of the review panel for the Orchard Road and Stamford Canal floods. Singapore Government Technical Report.

PUB (Public Utilities Board Singapore) (2015). Coastal Adaptation Study. Singapore Government Technical Report.

PUB (Public Utilities Board Singapore) (2018). Code of Practice on Surface Water Drainage, 6th edition. Singapore: PUB, the National Water Agency. [Secondary drains designed for RP5 1h storm; tertiary drains RP2 1h.]

Rentschler, J., Salhab, M., and Jafino, B. A. (2022). Flood exposure and poverty in 188 countries. *Nature Communications*, 13, 3527.

Sampson, C. C., Smith, A. M., Bates, P. D., Neal, J. C., Alfieri, L., and Freer, J. E. (2015). A high-resolution global flood hazard model. *Water Resources Research*, 51(9), 7358–7381.

Schwanghart, W., and Scherler, D. (2014). TopoToolbox 2 — MATLAB-based software for topographic analysis and modeling in Earth surface sciences. *Earth Surface Dynamics*, 2, 1–7.

Sutanudjaja, E. H., van Beek, R., Wanders, N., et al. (2018). PCR-GLOBWB 2: a 5 arc-minute global hydrological and water resources model. *Geoscientific Model Development*, 11, 2429–2453.

Tellman, B., Sullivan, J. A., Kuhn, C., Kettner, A. J., Doyle, C. S., Brakenridge, G. R., Erickson, T. A., and Slayback, D. A. (2021). Satellite imaging reveals increased proportion of population exposed to floods. *Nature*, 596, 80–86.

Teng, J., Jakeman, A. J., Vaze, J., Croke, B. F. W., Dutta, D., and Kim, S. (2017). Flood inundation modelling: A review of methods, recent advances and uncertainty analysis. *Environmental Modelling and Software*, 90, 201–216.

Trinh, N. Q., Tran, T. T., and Le, H. T. (2017). Climate change impacts on the Saigon — Dong Nai river system: storm surge and SLR scenarios. SIWRR Technical Report.

Ward, P. J., Winsemius, H. C., Kuzma, S., Bierkens, M. F. P., Bouwman, A., de Moel, H., Diaz Loaiza, A., Eilander, D., Englhardt, J., Erkens, G., Gebremedhin, E., Iceland, C., Kooi, H., Ligtvoet, W., Muis, S., Scussolini, P., Sutanudjaja, E. H., van Beek, R., van Bemmel, B., van Huijstee, J., van Rijn, F., van Wesenbeeck, B., Vatvani, D., Verlaan, M., Tiggeloven, T., and Luo, T. (2020). Aqueduct Floods Methodology. World Resources Institute Technical Note.

Wessel, B., Huber, M., Wohlfart, C., Marschalk, U., Kosmann, D., and Roth, A. (2018). Accuracy assessment of the global TanDEM-X Digital Elevation Model with GPS data. *ISPRS Journal of Photogrammetry and Remote Sensing*, 139, 171–182.

Wing, O. E. J., Bates, P. D., Quinn, N. D., Savage, J. T. S., Uhe, P. F., and Cooper, A. (2024). A 30 m global flood inundation model for any climate scenario. *Water Resources Research*, 60, e2023WR036460.

Yamazaki, D., Ikeshima, D., Sosa, J., Bates, P. D., Allen, G. H., and Pavelsky, T. M. (2019). MERIT Hydro: a high-resolution global hydrography map based on latest topography dataset. *Water Resources Research*, 55, 5053–5073.

Zanaga, D., Van De Kerchove, R., Daems, D., De Keersmaecker, W., Brockmann, C., Kirches, G., Wevers, J., Cartus, O., Santoro, M., Fritz, S., Lesiv, M., Herold, M., Tsendbazar, N.-E., Xu, P., Ramoino, F., and Arino, O. (2022). ESA WorldCover 10 m 2021 v200. Zenodo. https://doi.org/10.5281/zenodo.7254221

---

## Appendix A — Replicability audit

[Render the §10 R1–R8 table from the methodology comparison document. Each row: gap name, current status, fix path, severity.]

## Appendix B — Per-city full RP tables

[Render the §2.6 (coastal), §3.5 (fluvial), §4.3 (pluvial baseline + extent) tables consolidated, one table per hazard, columns per city, rows per RP, at SSP5-8.5 / 2100.]

## Appendix C — Sensitivity to ξ_max cap

[One paragraph plus a small table. ξ_max = 0.30 is an engineering choice; effect on RP1000 stages is bounded and well-understood.]

## Appendix D — Reproduction run-commands

[One bash block per city showing the canonical run-command. Current as of 2026-05-24.]

---

*Draft v1.1 — 2026-05-26. ~8,100 words excluding references, tables, and appendices.*
