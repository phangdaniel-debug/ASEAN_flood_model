# Open-data multi-hazard flood screening for ASEAN cities: a reproducible methodology with bias-aware solver selection

**Status:** Scaffold (2026-05-24). Target length 6,000–8,000 words.
**Target venues (rank order):** *NHESS* → *Environmental Modelling & Software* → *Earth System Science Data* (data-paper form).
**Headline novelty (refined after literature scan):** the artefact itself — a fully open-source, fully open-data, per-country-IDF-calibrated, 30 m, multi-hazard flood atlas for ASEAN megacities. Fathom 3.0 (Wing et al. 2024, *WRR*) is the only comparable-resolution global model and is closed-source / commercially licensed; every open-data alternative (Aqueduct 4.0, GLOFRIS) is ~10 km and lacks pluvial; the only published SEA-regional model (Olcese et al. 2024, *WRR*) lacks coastal. The pluvial solver itself (§2.5) is an integration of established fill-spill-merge methodology (Barnes et al. 2020) into a screening pipeline — described and cited but not framed as a novel hydraulic method.

**Authors:** TBD
**Keywords:** flood modelling, ASEAN, coastal flooding, fluvial flooding, pluvial flooding, open data, HAND, fill-and-spill, GEV, AR6 sea-level rise, reproducibility

---

## Abstract (target 250 words)

> *Four paragraphs — write last:*
>
> 1. **Context.** ASEAN flood risk is increasing under joint SLR, precipitation intensification, and ongoing subsidence in four of six megacities. Existing screening tools cover this region either at coarse resolution with limited hazards (Aqueduct Floods 4.0 — ~10 km, no pluvial), at fine resolution under commercial licence (Fathom 3.0 — 30 m globally, closed-source, free only for 16 World Bank developing countries that exclude the major ASEAN cities), or as bespoke per-city engineering studies that are not publicly reproducible.
> 2. **What we built.** A pipeline producing design-event coastal + fluvial + pluvial flood depth maps at 30 m for 11 city configurations across six countries (Singapore, Malaysia, Thailand, Indonesia, Philippines, Vietnam), under four SSP × horizon combinations, from exclusively public data and exclusively open-source code. To the best of our knowledge this is the first openly reproducible 30 m multi-hazard flood atlas calibrated to national IDF anchors for ASEAN megacities.
> 3. **Key methodological choices.** Per-country IDF anchoring against the six national meteorological services (PUB / JPS-MSMA / TMD-RID / BMKG / PAGASA Port Area / JICA 2011) eliminates the 28–62% bias that global synthetic rainfall statistics carry over tropical-convective extremes. GEV block maxima for all three hazards with documented ξ caps. HAND with bankfull subtraction for fluvial. An FSM-style catchment-routed fill-and-spill pluvial solver (Barnes et al. 2020) weighted by ESA WorldCover land cover. Bathtub and local-inertia coastal solvers (Bates et al. 2010) with per-city selection driven by quantified bias factors. AR6 SLR by tide-gauge station. Subsidence correction and engineered-defence DEM burn-in for the four subsidence-affected cities.
> 4. **Validation and limits.** IDF-anchor consistency passes 41/4/0 (PASS/WARN/FAIL) across the eleven configurations; four documented historical events tested with CSI / hit rate / false-alarm metrics. Bathtub coastal-extent bias quantified at 1.7–25× at RP100 vs published observations, brought close to 1× by the local-inertia solver where topology permits. Full replicability audit (R1–R8 gap analysis), source code, configuration data, and atlas outputs released.

---

## 1. Introduction (~700–900 words)

### 1.1 ASEAN flood risk and the gap in open screening tools

> Open with the scale of the exposure and the inadequacy of existing tools.
>
> - Demographics & exposure: ~750M people, ~50% urbanised within a decade, ~20% of regional GDP on flood-exposed land [need ADB / UN-Habitat figures].
> - Compound stressors: SLR (AR6 P50 +0.62–1.62 m by 2100 across the region), precipitation intensification, subsidence at 1–25 cm/yr in Jakarta / Manila / HCMC / Bangkok.
> - Recent major events: Bangkok 2011, Jakarta 2020, KL 2021, Marikina Ondoy 2009, HCMC 2008 — across hazard types, each city affected.
>
> The flood-screening tooling that *covers* ASEAN today falls in one of three categories. **Table 1** below shows that none hits the intersection of attributes this paper claims (open code + open data + 30 m + multi-hazard + per-country IDF calibration + ASEAN megacities).

**Table 1 — Comparator landscape for ASEAN-relevant flood screening tools.**

| Tool | Resolution | Coverage | Hazards | Code | Data | Licence | Per-country IDF calibration |
|---|---|---|---|---|---|---|---|
| **This work** | **30 m** | 11 ASEAN city configs (SG, MY, TH, ID, PH, VN) | Coastal + fluvial + **pluvial** | **Open** (GitHub) | **Open** (GLO-30, ERA5-Land, UHSLC, GloFAS, OSM, AR6 Zarr, WorldCover) | Permissive | **Yes** — six national meteorological services |
| **Fathom 3.0** (Wing et al. 2024, *WRR*) | 30 m | Global | C + F + P | Closed | Closed (FABDEM+) | Commercial; free for 16 specific developing countries (excludes the ASEAN megacities) | Global synthetic |
| **Aqueduct Floods 4.0** (WRI / Ward 2020) | ~10 km (5 arc-min) | Global | C + F (**no pluvial**) | Open methodology | Open data | CC | None |
| **GLOFRIS / PCR-GLOBWB 2** (Sutanudjaja et al. 2017) | ~10 km | Global | F (+ coastal extension) | Open | Open | CC | None |
| **Olcese et al. 2024** (*WRR*) | DEM-grade (Bristol stack) | SE Asia | F + P (**no coastal**) | Likely closed | Likely closed | Paywalled | None |
| **Moody's RMS Asia-Pacific** | Various | TH/MY/SG/ID | F + P | Closed | Closed | Commercial | Per-product |
| **JBA Global Flood Map** | Various | Global | C + F | Closed | Closed | Commercial | Per-product |
| **GTSM-ERA5** (Muis et al. 2020) | ~0.1° (~10 km) | Global | **C only** | Mixed | Open | CC | n/a |
| **LISFLOOD-FP** (Bates et al. 2010) | High | Configurable | F | Open | Bring-your-own | Open | Bring-your-own |
| **City-specific engineering** (NCICD / BMA / DPSI / MMDA / PUB) | High | Single city | Various | Closed | Closed | Proprietary | Per-city engineering |
| **PetaJakarta** (BPBD DKI / SMART) | Crowdsource | Jakarta | F + P (near-real-time) | Open | Crowdsourced | Open | Different problem (nowcasting) |

> Three observations from this table motivate this paper:
>
> 1. **No openly reproducible 30 m three-hazard model for ASEAN megacities currently exists.** Fathom 3.0 is the only comparable-resolution three-hazard model but is closed-source and the free-access tranche (16 specific countries via the World Bank) excludes the major ASEAN cities. The only ASEAN-focused regional model (Olcese et al. 2024) lacks the coastal hazard and was not released with open code. The only open-data global alternatives (Aqueduct, GLOFRIS) are ~10 km resolution and miss pluvial.
> 2. **No published flood model for the region uses per-country IDF anchoring for the pluvial hazard.** Global synthetic rainfall statistics (GloFAS, ERA5, MERRA-2) systematically under-represent tropical convective extremes by 28–62% relative to the national IDF curves published by PUB, JPS-MSMA, TMD/RID, BMKG, PAGASA, and JICA. This is the dominant correctable bias in pluvial screening for the region.
> 3. **No published flood-model methodology paper to date includes an end-to-end replicability audit** itemising every gap a third party would face. The R1–R8 framework (Appendix A) is a hygiene contribution applicable beyond this work.

> Brief contextual mentions of broader research-grade tools (LISFLOOD-FP, SFINCS, CaMa-Flood, ADCIRC, Delft3D) appear in §2 where each underlying method is cited. None of those tools provides an ASEAN-wide deployment; they are the building blocks an engineering study would use, not screening atlases.

### 1.2 Contributions

> The headline is the **artefact itself**: a fully open-source, fully open-data, calibrated, 30 m, multi-hazard flood atlas for ASEAN megacities — a combination that does not exist in the published literature (Table 1 / §1.1 comparator scan). The six specific contributions in descending order:
>
> 1. **The atlas as a deliverable.** Design-event flood depth maps at 30 m for 11 ASEAN city configurations across six countries, three hazards, four SSP × horizon combinations, reproducible end-to-end from a public GitHub repository. Fathom 3.0 is the only comparable-resolution competitor and is closed-source and commercially licensed; every other open-data ASEAN-relevant model is at least an order of magnitude coarser or missing a hazard. (§4)
> 2. **Per-country IDF anchoring across six national meteorological services** as the calibration framework. Global synthetic rainfall statistics carry a documented 28–62% deficit against published national IDF curves for tropical convective extremes; anchoring each country's pluvial GEV directly to PUB / JPS-MSMA / TMD-RID / BMKG / PAGASA Port Area / JICA 2011 closes that gap and is itself novel — no published global or regional model does this. (§2.5.1)
> 3. **Per-city implementation matrix.** Documents *why* each city uses the specific data source and solver it does — turning the unavoidable heterogeneity of public-data availability into a defensible design framework rather than hidden hand-tuning. We argue this asymmetric-but-documented approach is the right structural answer to the screening-vs-engineering trade-off in data-poor regions. (§3)
> 4. **Bathtub vs local-inertia bias characterisation.** Quantifies bathtub coastal over-prediction at 1.7–25× at RP100 across five tropical-delta cities by reconstructing present-day extents from the SSP5-8.5 / 2100 rasters and comparing against documented historical events; demonstrates the Bates et al. 2010 local-inertia formulation brings RP100 bias close to 1× where solver topology permits. (§5.3)
> 5. **Reproducibility audit (R1–R8).** Itemises every data source, every calibration anchor, every remaining gap a third party would encounter when reproducing the work. Designed as a model-paper hygiene contribution as much as a documentation artefact. (Appendix A)
> 6. **Open-source FSM-style fill-and-spill pluvial implementation.** Standard fill-spill-merge methodology (Barnes et al. 2020) integrated into a screening pipeline with WorldCover-derived per-cell runoff, resolving the lumped-depression-fill artefact (RP-invariant extent) that prevalent screening tools still exhibit. Not novel as a hydraulic method; valuable as a published open-source implementation in the screening context. (§2.5)

### 1.3 Paper structure

> §2 pipeline architecture and methods. §3 per-city implementation matrix and the case for intentional heterogeneity. §4 results across the SSP × horizon × city × hazard grid. §5 validation. §6 discussion: appropriate use, limitations, future work. §7 conclusion.

---

## 2. Pipeline architecture and methods (~2,500–3,000 words — the bulk)

### 2.1 Overview

> One paragraph + Figure 1.
>
> **Figure 1 — Pipeline architecture.** Per-city config (in `cities.py`) → DEM fetch (GLO-30 STAC) → optional subsidence correction → optional defence burn-in → sea-mask construction → OSM river raster → HAND → multi-hazard solver (`run_multihazard.py`) → severity classification → combined / street-overlay / scenario-progression maps. Annotate the per-step data products and the cities.py configuration surface.

### 2.2 Terrain

> ~250 words. Cite Krieger 2007 (TanDEM-X), Wessel 2018 (GLO-30 accuracy).
>
> - Copernicus GLO-30 DEM (TanDEM-X, ~2013 reference epoch), EGM2008 vertical datum, Microsoft Planetary Computer STAC.
> - Reprojected to local UTM zone at 30 m for each city.
> - Three optional in-place modifications applied before flood routing:
>   1. **Zone-based subsidence correction** (Jakarta, Manila, HCMC, Bangkok) from published InSAR / GPS literature [Phien-wej 2006, Aobpaet 2013, Eco 2020, Erban 2014]. Three latitude-band zones per city; mean correction −0.24 m (Bangkok) to −0.83 m (Jakarta).
>   2. **Engineered-defence crest burn-in** (5 cities). Documented defence polylines (sea walls, ring dykes, tide gates) buffered to ~3 cells, burned in as `max(DEM, crest_EGM2008)`. Crests are stored in `apply_flood_defenses.py:DEFENSE_CONFIGS` with provenance (BMA master plan, NCICD Phase A, MMDA, JICA, PUB).
>   3. **DEM artefact cleanup** (`scripts/_clean_dem_artefacts.py`). TanDEM-X spike-pixel removal via local-median replacement; applied to HCMC (3,691 spikes) and Manila (12 spikes), preserves original as `*_uncleaned.tif`.

### 2.3 Coastal hazard

> ~600 words.

#### 2.3.1 Sea-level statistics

> - UHSLC Research-Quality + Fast-Delivery tide gauges; 17–40 yr per city.
> - T_TIDE harmonic de-tiding [Pawlowicz 2002].
> - Annual maxima → MLE GEV fit with shape capped at ξ_max = 0.30 to prevent tail runaway on short records.
> - Jakarta has no qualifying RQ gauge ≥ 30 yr → fallback to Muis et al. 2016 literature values, treated explicitly as screening-only and flagged in the implementation matrix.
> - HCMC 31-yr Vung Tau record reconstructed across a 2002 datum shift (per-block de-mean before combining annual maxima).

#### 2.3.2 MDT offsets (CNES-CLS-2022)

> - Sample CMEMS CNES-CLS-2022 MDT at each gauge coordinate via `derive_msl_egm2008_offsets.py`.
> - Per-gauge offsets +0.998 m (Tanjung Priok) to +1.179 m (Ko Lak).
> - Applied to convert tide-gauge MSL anomalies onto the EGM2008 surface used by GLO-30.

#### 2.3.3 SLR projections

> - IPCC AR6 Zarr (NCAR / Rutgers public store), workflow `wf_1e` (includes ice-sheet uncertainty).
> - Per-station, per-scenario, P17 / P50 / P83 percentiles.
> - Δ computed per Monte Carlo sample then aggregated, not median-of-medians.

#### 2.3.4 Solvers

> - **Bathtub** — connected fill below target water surface, seeded from sea mask + optional tidal channels + per-city `--coastal-seed-latlon`. Sub-second runtime. Adequate for very flat coastal plains [Teng 2017].
> - **Local-inertia (Bates 2010 formulation)** — 2D shallow water with advection dropped (valid for Fr < 0.5). Numba-JIT kernels with bounding-box cropping (commit `fec1b4c`); Bangkok 6.1 M-cell grid runs in ~10 min wall-clock. Sea cells held at time-varying surge hydrograph (3 h ramp / 1 h hold / 2 h recession). Convergence on wet-cell mean depth change.

#### 2.3.5 Solver-selection rule

> - Bathtub bias factor (§5.3) drives the choice. When present-day bias > ~5× and topology permits, use local-inertia.
> - Manila and HCMC are forced to bathtub by `_BATHTUB_COASTAL_CITIES`: their enclosed-bay / enclosed-delta topology breaks the inertial wall condition (zero flux across NaN / land interfaces, no surge propagation path).
> - This is a known limitation, framed honestly rather than hidden — see §6.3.

### 2.4 Fluvial hazard

> ~500 words.

#### 2.4.1 Discharge baselines

> - **GloFAS v4 daily reanalysis** [Alfieri 2020] at a sub-basin point inside the city domain (~50–500 km² catchment), 28-year record (1997–2024), via Open-Meteo Flood API.
> - **ERA5-Land rainfall-runoff via SCS-CN + Manning's** for small canalised catchments where GloFAS routing (0.1°) is too coarse — Singapore (~10 km² PUB drains) and Bangkok klong (~5 km² urban sub-basin).
> - Per-city GEV-MLE fit to annual maxima with documented ξ caps.

#### 2.4.2 Bankfull subtraction

> - Rivers with permanent baseflow (KL, Bangkok CP, Manila, HCMC): subtract the Manning depth at Q_bf = minimum annual maximum discharge, so HAND inundation reflects depth above design capacity rather than total channel depth.
> - Rivers that are dry between events (Jakarta Ciliwung-Depok) or canalised (Singapore): no bankfull subtraction.

#### 2.4.3 HAND

> - Pysheds pit-fill → D8 flow direction → flow accumulation → channel delineation (FAC ≥ 500 cells ∪ OSM waterway features).
> - HAND[i,j] = z[i,j] − z[downstream channel cell along D8 path].
> - Inundation depth = max(0, stage − bankfull − HAND).
> - HAND is rebuilt from the defended DEM when `--flood-defenses` is on (defences genuinely block fluvial flow), and the resulting raster is suffixed `hand_<utm>_defended.tif` so the two scenarios are independently reproducible.

### 2.5 Pluvial hazard — catchment-routed fill-and-spill

> ~800 words. Open-source implementation of fill-spill-merge methodology (Barnes et al. 2020) integrated with WorldCover-derived per-cell runoff. Not a novel hydraulic method — valuable as a published, screening-grade implementation in a region where most screening tools still use the lumped depression-fill approximation that produces RP-invariant flood extent.

#### 2.5.1 The lumped-fill artefact this fixes

> - Standard lumped depression-fill model: ponding_cap = max(0, GEV(RP) − drain_capacity) × runoff_coeff / depression_area_fraction, clipped uniformly to every connected DEM depression.
> - Consequence: flood **extent** is identical at every RP (only depth scales), because the same scalar fills every depression regardless of its upslope catchment. Documented artefact; not a controversial finding.

#### 2.5.2 The two-stage replacement

> - **Stage 1 — IDF-anchored Gumbel baseline.** For each return period, excess_depth_m = max(0, GEV_6h(RP) − drain_capacity) / 1000. Per-city documented anchors: MSS (SG), JPS-MSMA (MY), TMD/RID (TH), BMKG (ID), PAGASA Port Area (PH), JICA 2011 (VN). Two-anchor Gumbel fit (RP2 + RP100 → μ, σ). Per-city drain_capacity_mm is the documented primary-drain design standard.
> - **Stage 2 — fill-and-spill routing (`model/pluvial_model.py`).**
>   1. **Runoff generation:** runoff_volume[cell] = excess_depth × runoff_coeff(cell) × cell_area. The runoff coefficient is read from an **ESA WorldCover 2021** 10 m land-cover raster (built-up 0.85, water 1.0, herbaceous wetland 0.70, cropland 0.40, tree cover 0.15; full mapping in `fetch_esa_worldcover.py`).
>   2. **Catchment supply:** runoff is routed by D8 flow direction on the raw DEM; each topographic depression accumulates the supply from its entire upslope catchment.
>   3. **Depression inventory:** identified from the pysheds-filled DEM. Features shallower than 0.5 m (DEM noise) or deeper than 3.0 m (quarries, valleys, reservoir basins, DEM artefacts) are excluded.
>   4. **Fill-and-spill cascade:** each depression fills along its hypsometric (area–elevation) curve until either supply is exhausted or pour-point is reached; overflow spills to the next depression along the conditioned-DEM flow field. Processed in topological order so total inflow is final before fill.

#### 2.5.3 Why this produces RP-dependent extent

> - At low RP, only depressions fed by the largest catchments fill enough to wet appreciable area.
> - At high RP, overflow cascades activate progressively more terrain.
> - The pre-2026-05-21 lumped model could not produce this behaviour because it ignored catchment supply.
> - Validated against Singapore PUB IDF: post-rollout RP10 mean depth 0.20 m, max 1.51 m — inside the PUB-documented 0.07–0.76 m range.
> - Cross-city: extent grows monotonically with RP for every city in the suite — **Figure 5**.

> **Figure 2 — Catchment-routed pluvial schematic.** Single-depression view (catchment, hypsometric curve, fill level, pour point); cascade view (downstream chain activating at higher RP). Suggested side panel: extent-vs-RP curves for the suite under lumped vs catchment-routed models.

#### 2.5.4 Limitations of this step

> - Static (no time-varying drainage rate within a storm event).
> - 30 m DEM cannot resolve sub-30 m depressions (basement entrances, road underpasses).
> - max_depression_depth_m = 3.0 m is an engineering filter; documented choice, not a calibration knob.
> - Catchment areas are computed on the raw DEM; defences are not applied to pluvial supply (defences are flood-routing barriers, not pluvial-storage modifications).

### 2.6 Sea-mask construction

> ~200 words.
>
> - BFS from raster boundary through z ≤ 0 pixels.
> - **NaN-BFS** also seeded from boundary NaN pixels (essential for GLO-30 where open ocean is NaN-coded, e.g. Manila Bay, HCMC delta).
> - **Interior seeds** for water bodies enclosed inside the DEM domain that have no z ≤ 0 path to the raster edge — Manila Bay (14.5°N, 120.9°E), Laguna de Bay (elevated freshwater, 14.41°N, 121.15°E ≤ 2.0 m), Saigon-Nha Be delta (10.668°N, 106.791°E), western Vam Co distributaries (10.647°N, 106.452°E).
> - **Pre-defence DEM source** — defences are flood-routing barriers, not redefinitions of what is ocean; building the sea mask from the defended DEM would let a burned tide-gate ridge sever a tidal channel from the sea, flipping the channel interior from sea to land (HCMC: 56k sea pixels lost = 50 km² spurious below-MSL "flooding"). Documented bug, fixed and tested.

### 2.7 Multi-hazard composition

> ~150 words.
>
> - Per-pixel max across coastal, fluvial, pluvial depths.
> - Severity classification 0–4 with thresholds aligned to JRC European flood damage functions and PUB flood advisory categories.
> - Per-pixel dominant hazard recorded for diagnostic colour-coding on combined maps.
> - 3 × 3 RP-comparison panels and street-overlay variants generated per city × scenario × horizon.

---

## 3. Per-city implementation matrix — why heterogeneity is the design (~700 words)

> The argument: a single uniform recipe would be cosmetically simpler but factually wrong, because the public-data environment is asymmetric. This section makes the asymmetry explicit and defends it.

### 3.1 Five reasons the implementation differs by city

> 1. **Public data availability is asymmetric.** Tide gauges: 17–40 yr available for SG / KL / BKK / Manila; Jakarta gauge ended 2004; HCMC has no in-city gauge; Bangkok has no Research-Quality station. National IDF curves: digitised and publicly accessible for SG (PUB) and VN (JICA); only on paper for PH / MY / TH / ID.
> 2. **Physical hydrology differs.** Singapore PUB canals (~10 km², dry between events) require different fluvial treatment than the Saigon River (200 m wide, permanent monsoon baseflow).
> 3. **Data-validation outcomes vary.** ERA5-Land passes Singapore IDF validation (−9.4%) but fails KL / Bangkok / Jakarta / Manila by 28–62%. Using ERA5-Land everywhere would knowingly produce wrong pluvial extents for 5 of 6 cities.
> 4. **GloFAS reanalysis has location-specific biases.** Bangkok GloFAS over-estimates discharge by 2.4× vs the RID Nakhon Sawan gauge → 0.42× bias correction applied. Other cities lack public gauge anchors → uncorrected with documented uncertainty.
> 5. **Record length and statistical tail behaviour vary.** Manila coastal: 17-yr record + strong Weibull GEV produces an implausibly compressed RP curve. HCMC Vung Tau: 31 yr with datum-shift correction enables a Fréchet fit capturing typhoon-driven heavy tail.

### 3.2 The per-city implementation matrix

> **Table 1 — Per-city data sources and methodological choices.** Three rows per city (coastal / fluvial / pluvial), each cell shows: source, fit method, key parameter, rationale, confidence rating (★ to ★★★★★).
>
> [Render from §7.1.1–7.1.3 of the methodology comparison doc.]

### 3.3 Decision protocol for adding a new ASEAN city

> One paragraph + flowchart. The matrix is a template — a new city is added by selecting from the same data sources and following the same defensibility tests (IDF anchor where digitised; GloFAS where catchment > local rainfall response scale; etc.).

---

## 4. Results — the ASEAN flood atlas (~1,500 words)

### 4.1 Cross-city headline (SSP5-8.5 2100, RP100)

> **Table 2 — Combined flood extents (km²) for each city.** Columns: coastal / fluvial / pluvial / total / dominant hazard.

### 4.2 Scenario sensitivity (2 × 2 SSP × horizon grid)

> Numbers from §6.4 of the methodology doc.
> Headline: ~370 km² of coastal RP100 land in the metro suite is *avoided* under SSP2-4.5 vs SSP5-8.5 at 2100, dominated by Bangkok (−130 km²) and HCMC (−102 km²).
>
> **Figure 3 — Mitigation-Δ visualisation.** Bar chart of avoided-flooded-area (RP100 SSP2-4.5/2100 minus SSP5-8.5/2100) per city, stacked by hazard.

### 4.3 City-by-city walk-through

> ~150 words each, with a representative RP-comparison panel.

#### 4.3.1 Bangkok

> The saturated-delta case. SSP5-8.5 2100 P50 SLR = 1.625 m. Post-subsidence DEM has 77% of cells below 4 m EGM2008. Bathtub at SSP5-8.5/2100 floods 3,546 km² at RP100 — physically correct for the no-defence no-pumping screening; the inertial solver brings this to ~280 km², consistent with documented 2011 megaflood extent (~200 km², Trinh 2017).

#### 4.3.2 Singapore

> The gold-standard validation case. MSS 6 h IDF / PUB 24 h IDF / UHSLC 699 39-yr — every baseline IDF-anchored. RP100 coastal 68 km², "fluvial" 97 km², pluvial 32 km². Confidence ★★★★★ across all three hazards.
>
> **Important framing.** Singapore has no natural-river fluvial flooding — 17 reservoirs dam the major water bodies and the Marina Barrage (2008) closes the Singapore + Kallang River system. The layer labelled "fluvial" for Singapore is **PUB primary canal-network overflow** (Bukit Timah, Stamford, Geylang concrete drains) under 24h-design rainfall via SCS-CN → Manning's → HAND. Distinct from natural-river flooding; corresponds to the PUB primary-drainage design framework (24h annual maxima). None of Singapore's documented major flood events (Orchard Road 2010, Bukit Timah 2017, Tampines 2010) were river-overtopping events. The same caveat applies to **Bangkok klong** (5 km² urban sub-basin canal-overflow — the Chao Phraya main-stem is the separate `bangkok_chao_phraya` config).

#### 4.3.3 Manila

> The enclosed-bay challenge. Bathtub-only solver due to Manila Bay topology (`_BATHTUB_COASTAL_CITIES`). Subsidence-corrected DEM with the deepest below-MSL pixel at −5.10 m (post-cleanup); the sea-mask interior-seed fix correctly classifies the bay as sea, leaving genuine subsided polders (Malabon / Navotas / KAMANAVA) as the residual flooded land.

#### 4.3.4 HCMC

> Dual-driver fluvial (Saigon main-stem + Mekong-backwater additive from Tan Chau, scaled per Trinh 2017). Coastal proxy from Vung Tau 130 km SE — explicit limitation. Post-DEM-cleanup runs sensibly under both clamp and no-clamp modes.

#### 4.3.5 KL / Greater KL composite

> Single-reach → multi-config: `kuala_lumpur` core + supplementary `klang_shah_alam` + `subang_langat` mosaicked by per-pixel depth max. GloFAS at Shah Alam (3.074°N, 101.578°E) with bankfull subtraction.

#### 4.3.6 Jakarta / Greater Jakarta composite

> Subsidence epicentre. Three latitude-band correction (−1.44 m / −0.72 m / −0.24 m, mean −0.83 m). Supplementary `tangerang` + `bekasi_depok` for outer metro. The smallest bathtub bias factor (1.7× at RP100) — bathtub is already close to physical reality because North Jakarta really *is* mostly unprotected polders below sea level.

> **Figure 4 — RP-comparison panels.** Six panels (one per primary city) showing the 3 × 3 RP grid at SSP5-8.5 / 2100.

### 4.4 Pluvial extent-vs-RP curves (the central new behaviour)

> **Figure 5 — Pluvial flood extent vs return period.** Eleven curves (one per city config) showing extent km² as a function of RP at SSP5-8.5 / 2100. The catchment-routed model produces a monotonically growing curve for every city; the dashed grey overlay shows the lumped-depression-fill result (flat at every RP) for two example cities. Pulls the §4.3 figures from the methodology comparison doc into a single comparison panel.

---

## 5. Validation (~1,500 words)

### 5.1 IDF-anchor consistency

> - `validate_pluvial_all_cities.py` re-derives each city's Gumbel from its two documented IDF anchors and checks the stored baseline.
> - Latest run (pre-catchment-routed migration): 41 PASS / 4 WARN / 0 FAIL across KL / Bangkok / Jakarta / Manila / HCMC. WARNs are physically correct floor-zone RPs (drain capacity > IDF at that RP).
> - Post-migration the validator targets the legacy `ponding_cap_m` baseline and needs updating to validate `excess_depth_m`; this is an open issue.

### 5.2 Historical-event validation (R4)

> Per `scripts/validate_historical_events.py`, contingency metrics on a (hazard, RP) × (event) sweep.
>
> | Event | Year | Source | Verdict | Best metrics |
> |---|---|---|---|---|
> | THA2011 | 2011 | Cloud-to-Street GFD (DFO 3850, MODIS) | **WARN** | coastal RP10, CSI 0.29, H 0.90, FAR 0.70, Bias 3.0 |
> | PHL2009 Ondoy | 2009 | UN-SPIDER COSMO-SkyMed (ITHACA shapefile) | **LIMITED-PASS** | best H 0.90 coastal; obs < 5 km² after SAR urban shadow |
> | MYS2021 | 2021 | Copernicus GFM Sentinel-1 (15-tile composite) | **LIMITED-PASS** | best H 0.42 pluvial; obs 0.1 km² after urban exclusion |
> | JKT2020 | 2020 | Sentinel-Asia EOS-ARIA (Sentinel-1) | **FAIL** | best CSI 0.10 pluvial; bathtub FAR ceiling 0.87 |
>
> Pattern: hit rates are high (model catches what really flooded) but false-alarm rates are also high (bathtub over-predicts in dense urban polders). The structural cause is bathtub + 30 m DEM, not solver tuning.
>
> **Figure 6 — Validation overlay.** THA2011 model coastal RP10 (greens) vs MODIS-derived flood (blues) over the Bangkok region, with H / CSI / FAR overlaid as a legend.

### 5.3 Bathtub-bias characterisation

> Reconstruct the present-day extent by subtracting the AR6 SLR delta from the SSP5-8.5 2100 raster (exact for spatially-uniform coastal stage), then compare against documented historical extents.
>
> | City | Pres-day RP2 modelled / documented | RP2 bias | RP100 bias |
> |---|---|---|---|
> | Singapore | 45 km² / ~0.5 km² | 91× | 25× |
> | Bangkok | 1,990 km² / ~30 km² | 66× | 12× |
> | Jakarta | 105 km² / ~15 km² | 7× | **1.7×** |
> | Manila | 911 km² / ~5 km² | **182×** | 9× |
> | HCMC | 545 km² / ~50 km² | 11× | 4× |
>
> Documented values from BMA / RID 2021 (Bangkok), Brinkman 2013 / NCICD 2014 (Jakarta), Lagmay 2017 (Manila), Trinh 2017 / SIWRR (HCMC), PUB 2015 (Singapore).
>
> Bias is largest at RP2 because real RP2 events are small and protected; it falls toward RP100 where bathtub and real extents both reach the unprotected delta.
>
> **Inertial-solver structural fix.** The Bates 2010 local-inertia formulation respects momentum and friction; an optimised implementation (Numba JIT, bbox crop, `fec1b4c`) runs the Bangkok 6.1 M-cell grid in ~10 min. Bathtub-vs-inertial across the 2 × 2 grid for Bangkok:
>
> [Reproduce §6.6.4 table; bathtub / inertial ratio 13–28× at RP2, 13–18× at RP100; bias factor recovery 7–110× → 3–8× at RP2, ≈1× at RP100.]
>
> Inertial blocked for Manila / HCMC by the enclosed-bay wall condition; recommended for Bangkok / Singapore production maps. This work runs the optimised inertial solver across Bangkok / Singapore / Jakarta on the current pipeline as a final benchmark.
>
> **Figure 7 — Bathtub-bias factors at RP2 and RP100.** Grouped bars per city; bathtub vs inertial overlay where solver-compatible.

---

## 6. Discussion (~1,200 words)

### 6.1 Appropriate use

> The model is honest as a screening upper bound under three explicit assumptions: no adaptation, no pumping, no sub-pixel terrain. Under these the modelled numbers are correct. Most useful as:
>
> - Relative comparison across scenarios (bias factor is approximately constant within a city across SSP × horizon → deltas are robust).
> - What-if-defences-fail planning bound.
> - Hypothesis generator for adaptation investment.

### 6.2 Known limitations

> - **Compound events not modelled.** Three hazards run independently; combined map is per-pixel max, not joint exceedance. Singapore's most damaging historical events have involved simultaneous surge + heavy rain + elevated rivers. A copula-based joint-exceedance framework is identified future work.
> - **Sub-pixel infrastructure invisible.** 30 m GLO-30 averages over sea walls, road raises, drainage canals, fishpond bunds, raised housing plots. The bathtub-bias factor (§5.3) is largely driven by this.
> - **No active drainage.** Bathtub assumes every below-WL cell is permanently flooded. Real Bangkok ~250 large pumping stations, Jakarta ~120 (PAM Jaya), HCMC ~70 (SCFC), Manila ~50 (MMDA) actively remove tidal / rainfall water from polders.
> - **Pluvial is static.** Catchment-routed fill-and-spill solves the spatial-extent artefact but does not model time-varying drainage rate within a storm.
> - **Single representative channel geometry for fluvial.** Manning's parameters represent one urban reach per city; real channel diversity is not captured. The bankfull subtraction partially mitigates this.
> - **No uncertainty quantification on output rasters.** Only AR6 P50 SLR is run; P17/P83 envelopes and GEV-parameter Monte Carlo would strengthen the policy-decision support.
> - **Manila / HCMC inertial blocked.** Enclosed-bay wall condition is an open solver question.
> - **Validation is limited.** Four historical events, one PASS, three LIMITED-PASS or worse. Reviewers will reasonably ask for more.

### 6.3 What this approach gets right that comparator tools don't

> - **Reproducibility from scratch** — every input free, every script committed, every parameter documented in `cities.py`.
> - **Honest per-city implementation matrix** — explicit asymmetry rather than hidden hand-tuning.
> - **Three-hazard consistency** — GEV block maxima everywhere; per-pixel max composition; single-source DEM.
> - **Bias accounting** — quantified, documented, not papered over.
> - **Cross-scenario and cross-horizon comparability** — the 2 × 2 grid is on the same solver and same data for every city.

### 6.4 Future work

> Ranked by impact × tractability:
>
> 1. **Inertial wall-condition fix for enclosed bays.** Unlocks Manila / HCMC on the structural solver; closes the largest remaining bias gap.
> 2. **Uncertainty quantification.** AR6 P17/P83 SLR envelopes + GEV-parameter MC on headline cities. ~2 weeks of work.
> 3. **CHIRPS 40-year precipitation record.** Reduces dependence on the ξ_max = 0.30 engineering cap that constrains the heavy-tail behaviour.
> 4. **IMERG sub-hourly precipitation.** Better resolution of storm-burst intensity for pluvial.
> 5. **MERIT Hydro DEM for HAND.** Better hydrologic conditioning improves fluvial extents in flat terrain.
> 6. **Compound exceedance framework.** Copula-based joint coastal + pluvial + fluvial probability.
> 7. **Validation expansion.** More events, more cities, more remote-sensing sources. Sentinel-1 GEE flood-mapping pipeline is partly built.
> 8. **Drainage network injection for pluvial.** Where city-level pipe-network inventories are available, supplement the catchment-routed model with explicit conveyance.

---

## 7. Conclusion (~250 words)

> Three paragraphs:
>
> 1. **What we showed.** Eleven ASEAN city configurations on a single reproducible pipeline using only public data; three hazards on consistent statistical foundation; novel catchment-routed pluvial solver that produces RP-dependent extent; per-city implementation matrix that defends intentional heterogeneity; bathtub-bias characterisation and the local-inertia structural fix; full replicability audit.
>
> 2. **What reproducibility-as-a-feature buys.** A second researcher can rebuild every number in this paper from public data with one command per city. A new ASEAN city can be added by following the implementation-matrix protocol. Bias factors and limitations are quantified rather than hidden — model users know what the numbers can and cannot say.
>
> 3. **Where it goes next.** The current outputs are screening-grade; the path to engineering-grade is documented and the highest-impact next steps are tractable (inertial wall-condition fix; uncertainty bracketing; longer-record precipitation). The open source code base invites contribution.

---

## Code and data availability

- **Source code:** GitHub repository [URL TBD]. Tagged release for this paper: [tag TBD].
- **Atlas outputs:** Zenodo DOI [TBD] — depth and severity rasters, summary CSVs, RP-comparison panels for all 11 × 4 × 3 combinations.
- **Input data sources:** Table A1 (Appendix A).

## Author contributions

> [TBD — typical CRediT taxonomy.]

## Competing interests

> [TBD.]

## Acknowledgements

> [TBD — IPCC AR6 team, UHSLC, Open-Meteo, ESA WorldCover, CMEMS, OpenStreetMap, Microsoft Planetary Computer, etc.]

---

## References (target ~60–80; stub list below)

> Build out properly during writing. Citations grouped by section for easy expansion.

**Methods — extreme value theory and GEV**
- Hosking & Wallis 1997. *Regional Frequency Analysis*. CUP.
- Coles 2001. *An Introduction to Statistical Modeling of Extreme Values*. Springer.

**Methods — fluvial / HAND**
- Nobre et al. 2011. HAND: hydrography. *Journal of Hydrology* 404:13–29.
- Bates et al. 2010. Inertial formulation of 2D SWE. *Journal of Hydrology* 387:33–45.
- Bates 2022 review.

**Methods — coastal solvers**
- Teng et al. 2017. Bathtub vs LISFLOOD-FP comparison. *NHESS* 17:1463–1482.
- Muis et al. 2016. *Global Extreme Sea Levels*. *Nature Communications* 7:11969.
- Muis et al. 2020. GTSM ERA5. *Earth's Future* 8:e2020EF001606.

**Methods — pluvial / fill-and-spill**
- Barnes, R., Callaghan, K. L., & Wickert, A. D. 2020. Fill–Spill–Merge: Disconnected hydrologic regimes in a connected world. *HESS* 24:4527–4549.
- Maksimović, Č., et al. 2009. Overland flow and pathway analysis for modelling of urban pluvial flooding. *Journal of Hydraulic Research* 47(4):512–523.
- Falconer, R. H., et al. 2009. Pluvial flooding: new approaches in flood warning, mapping and risk management. *J Flood Risk Mgmt*.

**Comparator flood-screening tools and global models**
- Wing, O. E. J., et al. 2024. A 30 m global flood inundation model for any climate scenario. *Water Resources Research* (Fathom 3.0).
- Ward, P. J., et al. 2020. Aqueduct Floods methodology. World Resources Institute (Aqueduct 4.0 update Hofste et al. 2019 / WRI 2023).
- Sutanudjaja, E. H., et al. 2018. PCR-GLOBWB 2: a 5 arc-minute global hydrological and water resources model. *GMD* 11:2429–2453.
- Olcese, G., et al. 2024. Developing a fluvial and pluvial stochastic flood model of Southeast Asia. *Water Resources Research*.
- Sampson, C. C., et al. 2015. A high-resolution global flood hazard model. *WRR* 51:7358–7381 (Fathom 1.0 lineage).
- Rentschler, J., et al. 2022. Flood exposure and poverty in 188 countries. *Nature Communications* 13:3527.

**Data sources — DEM, precipitation, SLR**
- Krieger et al. 2007. TanDEM-X mission.
- Wessel et al. 2018. GLO-30 accuracy. *ISPRS J* 139:171–182.
- Funk et al. 2015. CHIRPS. *Scientific Data* 2:150066.
- Munoz-Sabater et al. 2021. ERA5-Land. *ESSD* 13:4349.
- IPCC AR6 WGI Chapter 9 (Fox-Kemper et al. 2021).
- Alfieri et al. 2020. GloFAS.
- Zanaga et al. 2022. ESA WorldCover 2021 v200.

**Subsidence — by city**
- Phien-wej et al. 2006. Bangkok subsidence. *Engineering Geology* 82(4):187–201.
- Aobpaet et al. 2013. Bangkok PSInSAR. *Int J Remote Sensing* 34(8):2969–2982.
- Chaussard et al. 2013. Jakarta ALOS PALSAR. *RSE* 128:150–161.
- Abidin et al. 2011. Jakarta GPS. *Natural Hazards* 59(3):1753–1771.
- Erban et al. 2014. HCMC subsidence. *ERL* 9(8):084010.
- Eco et al. 2020. Manila PSInSAR. *Phil J Science* 149(3):675–688.
- Minderhoud et al. 2017. Mekong delta. *ERL* 12(6):064006.

**Validation — historical events / remote sensing**
- Tellman et al. 2021. Cloud-to-Street Global Flood Database. *Nature* 596:80–86.
- Lagmay et al. 2017. Manila Ondoy storm-surge. *J Flood Risk Mgmt* 10(2):190–200.
- Brinkman & Hartman 2013. North Jakarta polder *rob*. (BAPPENAS report.)
- Trinh et al. 2017. HCMC flooding under SLR. (SIWRR/MARD report.)
- NCICD 2014. National Capital Integrated Coastal Development Master Plan. (Government of Indonesia.)
- BMA 2012. Bangkok Drainage Master Plan.

**Comparator tools**
- Ward et al. 2020. Aqueduct Floods.
- Rentschler et al. 2022. Global flood exposure (World Bank).
- Sampson et al. 2015. Fathom global flood model.

---

## Appendix A — Replicability audit (R1–R8)

> Reproduce the §10 table from the methodology comparison doc. Status flags: which gaps are closed, which remain open. This is the headline differentiator for the data-paper framing.

## Appendix B — Per-city full RP tables

> Consolidate the §2, §3, §4 RP tables (coastal / fluvial / pluvial baselines) from the methodology comparison doc into one appendix table per hazard.

## Appendix C — Sensitivity to ξ_max cap

> One paragraph + small table. ξ_max = 0.30 is an engineering choice; effect on RP1000 stages is bounded and well-understood.

## Appendix D — Run-command examples

> One bash block per city — the §9 run commands from the methodology comparison doc, current as of the most recent rollout.

---

## Editor's notes (for the human author — delete before submission)

**What this scaffold is doing well**
- Lays out the seven-section structure conventional for NHESS / EMS.
- Pre-positions every figure and table.
- Inlines the §6.5 bathtub-bias finding (the strongest validation hook).
- Leaves the pluvial method as the headline novelty without dependence on a separate publication.

**Decisions still to make**
- **Target venue.** NHESS is the highest-impact-per-effort target (~60% acceptance, fast turnaround, well-aligned topic scope). EMS is more model-software-oriented and may want a code-availability framing. ESSD is data-paper form and would require flipping the structure to lead with the atlas.
- **Co-authors.** Adding a subject-matter coauthor in each country (PUB-affiliated for SG, JPS for MY, etc.) materially strengthens reviewer reception and citation reach.
- **Single paper vs sister methods paper.** Decision already taken to lead with the systems paper; keep "in prep" pointer to the standalone catchment-routed pluvial methods paper. If timing permits, submit the methods paper ~6 weeks before this one so it can be cited in proof.
- **Comparator-tool figure.** Add Aqueduct or Fathom side-by-side panel for at least one city — this is the single most effective figure for telling reviewers "we know what the alternatives look like and here's how ours differs".
- **Validation strategy before submission.** At least one of the LIMITED-PASS events needs to convert to PASS, or the validation section reads weaker than it should. Marikina Ondoy 2009 against a higher-quality fluvial reference (Project NOAH / DOST FloodMap) is the cleanest target.

**Sequence to first submission**
1. Write §2 (methods) and §3 (matrix) — the most fact-dense sections; data is already in `docs/hazard_methodology_comparison.md`.
2. Generate Figures 1, 2, 5, 7 — these are the cheapest and highest-information.
3. Run the inertial sensitivity for Singapore / Bangkok / Jakarta (in flight as of this scaffold) and lock the §5.3 numbers.
4. Convert one LIMITED-PASS event to PASS via better reference data, OR change the validation framing to "skill metrics across multiple events" rather than "PASS/FAIL gating".
5. Write §1 (intro), §4 (results), §5 (validation) drafts.
6. Write §6 (discussion), §7 (conclusion).
7. Abstract last.

**Estimated total effort to a submission-ready draft**
- Writing: ~3–4 weeks at 1 day / week
- Figures: ~2 weeks
- Validation expansion: ~4–6 weeks
- Co-author review cycles: ~2 weeks
- **Realistic submission window: 8–12 weeks from this scaffold.**
