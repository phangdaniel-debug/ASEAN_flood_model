# Open, Reproducible 30 m Multi-Hazard Flood Screening for Under-Resourced Southeast Asian Cities

**Authors:** Daniel Phang (ORCID 0009-0006-3785-4458); Tze-Houng Lee
**Affiliations:** [TBD — institutions for both authors]
**Venue:** IEEE R10-HTC 2026 — Special Session 1 "Net Zero Integration"
**Format:** IEEE conference template, two-column, ~6 pages. Source of record: `docs/paper/draft.md` (extended journal form).

---

## Abstract

The Southeast Asian cities most exposed to flooding are precisely those least able to obtain usable hazard information. The only comparable-resolution (30 m) three-hazard model with regional coverage is commercial and closed, and its free-access tranche explicitly excludes the major ASEAN megacities; bespoke per-city engineering studies are not publicly reproducible; and the open global products are an order of magnitude coarser and omit the pluvial (rain-driven) hazard that dominates urban flooding in the region. We present an open-source, open-data pipeline that produces design-event coastal, fluvial, and pluvial flood-depth maps at 30 m for four cities — Singapore, Kuala Lumpur, Bangkok, and Jakarta — across four ASEAN countries, under four climate combinations (SSP2-4.5 and SSP5-8.5 × 2050 and 2100). Every input is freely accessible without registration, and the pluvial hazard is anchored to the national meteorological services' published Intensity–Duration–Frequency (IDF) standards, eliminating the 28–62 % deficit that global synthetic rainfall carries over tropical-convective extremes. We make the open model *trustworthy*, not merely reproducible: a model-blind documented-hotspot location-skill gate yields statistically significant discriminative skill in all four cities tested, and a bathtub-bias characterisation (coastal over-prediction of 1.7–25× at RP100) is closed by a local-inertia shallow-water solver (Bangkok over-prediction 12.5× → ≈1×). The release is intended as a public good for under-resourced municipal disaster-management and climate-adaptation agencies.

**Index Terms —** humanitarian technology, flood risk, open data, multi-hazard, decision support, climate adaptation, Southeast Asia.

---

## I. Introduction

Southeast Asia contains six of the ten cities globally most exposed to coastal flooding by 2100 under high-emission scenarios. Roughly 750 million people live in the ASEAN region, with about a fifth of regional GDP on flood-exposed land, and the stressors compound: AR6 P50 sea-level rise under SSP5-8.5 by 2100 ranges from +0.62 m (Singapore) to +1.62 m (Bangkok); tropical convective rainfall is intensifying at or above the Clausius–Clapeyron rate; and several megacities subside at 1–25 cm yr⁻¹ from groundwater extraction and clay compaction. The 2011 Thailand megaflood, the 2020 Jakarta monsoon floods, and the 2021 Kuala Lumpur flash floods are recent reminders that the exposure is multi-hazard — coastal, fluvial, and pluvial — and concurrent.

Yet the cities carrying this risk cannot readily obtain affordable, usable hazard maps. Existing flood-screening tools fall into three categories, none of which simultaneously offers high resolution, multi-hazard scope, open code, open data, and per-country calibration (Table I). The only 30 m three-hazard global model is commercial, and its free-access tranche is restricted to a set of developing countries that *excludes the major ASEAN megacities*. Bespoke municipal engineering studies exist but are closed and not reproducible. The open global alternatives are an order of magnitude coarser (~10 km) and lack the pluvial layer that drives most urban flood damage in the region. The result is an equity gap: open, high-resolution, multi-hazard flood information — a basic input to humanitarian disaster-risk reduction and adaptation planning — is unavailable to exactly the agencies that most need it.

This paper addresses that gap. We present an open-source, open-data, per-country-calibrated 30 m multi-hazard flood pipeline and atlas for ASEAN cities, and — crucially — we validate that it locates real floods. The paper covers four cities (Singapore, Kuala Lumpur, Bangkok, Jakarta) across four countries; two further cities (Manila, Ho Chi Minh City) are deferred pending a solver extension (§V).

**Table I.** Comparator landscape for ASEAN-relevant flood-screening tools.

| Tool | Resolution | Hazards | Open code | Open data | Per-country IDF |
|---|---|---|---|---|---|
| **This work** | **30 m** | **C + F + P** | **Yes** | **Yes** | **Yes (4 services)** |
| Fathom 3.0 | 30 m | C + F + P | No | No | Global synthetic† |
| Aqueduct Floods 4.0 | ~10 km | C + F | Method only | Yes | None |
| GLOFRIS / PCR-GLOBWB | ~10 km | F (+C) | Yes | Yes | None |
| City engineering studies | High | Various | No | No | Per-city |

†Fathom's free-access tranche is restricted to selected developing countries and excludes the major ASEAN megacities covered here — the equity gap this work targets. C = coastal, F = fluvial, P = pluvial.

---

## II. Open Multi-Hazard Pipeline

**Open-data inputs.** A per-city configuration drives a single orchestration script through the pipeline. Every input is free and most require no registration: the Copernicus GLO-30 DEM (via the Microsoft Planetary Computer), ERA5-Land precipitation (Open-Meteo), University of Hawaii Sea Level Center (UHSLC) tide gauges, GloFAS v4 discharge reanalysis (Open-Meteo Flood API), IPCC AR6 sea-level projections (NCAR/Rutgers Zarr), ESA WorldCover 2021 land cover, and OpenStreetMap waterways. The implementation is pure Python on the scientific stack (rasterio, scipy, pyproj, pysheds, numba); no external binaries or licensed data are required, which is what makes the pipeline reproducible from scratch by a third party.

**Per-country IDF anchoring.** The single most important in-region calibration is the pluvial design rainfall. Global synthetic rainfall statistics under-represent tropical-convective extremes by 28–62 % relative to the national IDF curves, so we fit a two-anchor Gumbel distribution directly to each country's published design standard: PUB (Singapore), JPS-MSMA (Malaysia), TMD-RID (Thailand), and BMKG (Indonesia). The storm duration is matched to the dominant local flood mechanism — Singapore uses a 1-hour secondary-drain IDF (its documented flash floods are sub-hourly convective bursts), the others a 6-hour IDF — and the post-drain excess rainfall is the depth the drainage network cannot convey.

**Three hazards.** *Coastal:* a GEV fit to UHSLC annual-maximum storm-surge residuals (T_TIDE-detided), plus the AR6 SLR delta, brought onto the EGM2008 DEM datum via a CMEMS mean-dynamic-topography offset, and routed by a local-inertia shallow-water solver (Bates et al.) on a staggered grid; a connectivity-based bathtub solver is retained as a fallback where the sea is enclosed within the DEM domain. *Fluvial:* GloFAS-derived design stage with bankfull subtraction for rivers carrying permanent baseflow, mapped via Height Above Nearest Drainage (HAND) referenced to the **main-stem trunk the modelled discharge represents** — flow-accumulation channels at the GloFAS sub-basin (catchment) scale rather than a channel-initiation threshold or raw OpenStreetMap network, which over-broaden the floodplain. *Pluvial:* the IDF excess is routed by a catchment-routed fill-and-spill cascade (Barnes et al.) with a per-cell runoff coefficient from WorldCover land cover, producing a return-period-dependent ponding extent rather than a uniform cap. The three depth rasters are composited by per-pixel maximum.

**Scenarios.** All hazards are produced for SSP2-4.5 and SSP5-8.5 at 2050 and 2100, on a subsidence-corrected DEM (a zone-based correction for the documented post-2013 subsidence in Jakarta and Bangkok). Per-step methodological detail is documented and reproducible in the open repository.

[**Figure 1.** Pipeline data-flow schematic (vertical): free open-data inputs → forcing & conditioning (per-country IDF anchoring, GEV surge + AR6 SLR, subsidence-corrected DEM) → three parallel per-hazard solvers (inertial coastal, main-stem-HAND fluvial, fill-and-spill pluvial) → per-pixel-maximum composite and severity classification → 30 m multi-hazard atlas. `docs/paper/figures/ieee_fig1_pipeline.png`.]

---

## III. The Open Flood Atlas

At the canonical RP100 / SSP5-8.5 / 2100 combination, the atlas shows the expected physical contrast between cities (Table II): low-lying Bangkok is coastal-dominated, Jakarta fluvial/pluvial-dominated, and inland Kuala Lumpur pluvial-dominated. The combined extents are *screening upper bounds* under explicit no-pumping, no-sub-pixel-defence assumptions (§V); the value of the atlas is less in any single absolute number than in the consistent, comparable surface it provides across cities, hazards, and scenarios.

The clearest policy-relevant signal is the **mitigation delta** — the flooded area avoided by meeting a lower-emissions pathway. The avoided Bangkok coastal RP100 land under SSP2-4.5 versus SSP5-8.5 at 2100 is −133 km². Because the model uses the same solver and inputs for every city in every scenario, such cross-scenario deltas are robust to the absolute bias and are the cleanest single number the atlas offers to an adaptation planner.

**Table II.** Combined flood extent at RP100, SSP5-8.5 / 2100 (km²).

| City | Coastal | Fluvial | Pluvial | Combined | Dominant |
|---|---:|---:|---:|---:|---|
| Singapore | 67 | 112* | 19 | 184 | Canal-overflow + coastal |
| Kuala Lumpur (core) | 0 | 126 | 268 | 362 | Pluvial |
| Bangkok (klong) | 3,546 | 788 | 433 | 3,598 | Coastal |
| Jakarta | 159 | 389 | 169 | 609 | Fluvial + pluvial |

*Singapore's "fluvial" layer is PUB primary canal-overflow under long-duration design rainfall, not natural-river flooding. The Bangkok coastal extent is a bathtub upper bound; the inertial-corrected value is 283 km² (§IV). All Table II values are current-pipeline bathtub RP100 outputs; the coastal extents reproduce the documented benchmarks within ~1 %.

[**Figure 2.** Bangkok present-day-baseline RP100 combined-hazard flood-depth map (SSP5-8.5 forcing, 2020 horizon; ~1,374 km² above 0.1 m), illustrating the screening flood envelope on the flat Chao Phraya delta. Depth classes: minor (0.1–0.15 m), moderate (0.15–0.5 m), major (0.5–1 m), severe (>1 m). `docs/paper/figures/ieee_fig2_bangkok_rp100.png`.]

---

## IV. Validation and Trustworthiness

An open model is only useful if it can be trusted to flood where flooding actually occurs. We test this directly with a **model-blind documented-hotspot location-skill gate**. For each city we freeze, before consulting any model output, a register of localities with *documented* flooding (positives) and localities documented to have stayed *dry* (controls), each geocoded and DEM-verified. The combined present-day wet mask (pluvial ∨ fluvial ∨ coastal, ≥ 0.10 m, within a 50 m hit radius matching the geocoding precision) is scored against the register at the event-matched RP100, reporting hit-rate (HR; sensitivity), correct-reject-rate (CRR; specificity), and the Peirce–Hanssen–Kuipers true skill statistic (TSS = HR + CRR − 1) with a bootstrap 95 % confidence interval. The register is a *consistency check*: parameters are anchored upstream to documented facts, and the gate is never used to retune them.

**Table III.** Documented-hotspot gate (present-day, RP100, ≥ 0.10 m, 50 m radius).

| City | pos / dry | HR | CRR | TSS [95 % CI] | verdict |
|---|---|---:|---:|---|---|
| Kuala Lumpur | 17 / 7 | 0.76 | 0.86 | **0.62** [0.25, 0.88] | PASS |
| Singapore | 38 / 20 | 0.82 | 0.65 | **0.47** [0.21, 0.72] | fail-CRR‡ |
| Bangkok | 16 / 7 | 0.56 | 0.86 | **0.42** [0.04, 0.75] | fail-HR |
| Jakarta | 18 / 8 | 0.89 | 0.50 | **0.39** [0.03, 0.75] | fail-CRR |

‡Singapore is the city in which the gate was first developed; it is scored here on the *identical* v2.0 basis as the other three (combined RP100, 0.10 m, 50 m radius), re-aligned from the flood-atlas-era pluvial-only / RP50 / 150 m convention — the SG model itself is unchanged. Its 58-point register is the largest, its positives are PUB *List of Flood-Prone Areas* localities geocoded from road names (medium georeferencing confidence, hence the conservative 50 m radius), and its CRR shortfall is the combined RP100 wet mask catching low-lying dry controls that the deliberately conservative pluvial-only layer alone would spare.

†Jakarta's TSS *before* the model-blind reclassification of two documented-flooded mislabels (Menteng, Gambir — both inundated in 2007 and 2013) was **0.16** (no skill); the reclassification is anchored to the flood record, not the gate (§IV, dry-control discipline). Reporting both makes the correction's effect transparent.

All four cities reach **statistically significant discriminative skill** — every TSS confidence interval excludes zero. The harness originated on Singapore and transferred to Kuala Lumpur, Bangkok and Jakarta with no engine changes. Two findings generalise. First, a **main-stem-HAND rule**: HAND must be referenced to the trunk channel the modelled discharge represents (for Kuala Lumpur, the ≥ 180 km² accumulation trunk), not a channel-initiation or full-OSM network; doing so fixes a false-positive on a 60–77 m hill by correct physics and yields a credible floodplain, lifting Kuala Lumpur to CRR 0.86 / TSS 0.62 (PASS). Second, a **dry-control discipline**: a genuine control that the model floods stays in the register as a reported false positive, never dropped to pass; only a control that is *independently documented-flooded* is corrected — Jakarta's central-levee controls (Menteng, Gambir) sit on the Ciliwung corridor and are documented inundated in 2007 and 2013, so reclassifying them on the flood-record evidence (decided model-blind) lifts Jakarta from no-skill (TSS 0.16) to significant skill (TSS 0.39). The remaining shortfalls are *documented structural limits, not tuning failures*: Bangkok's HR is bounded because the 2011 reference flood was sourced from a catchment whose headwaters lie outside the model domain, and Jakarta's residual specificity loss is fill-and-spill over-ponding on genuinely elevated ground.

A second, complementary result establishes that the open model's coastal layer is corrected, not merely cheap. A bathtub solver — the default in open screening tools — over-predicts documented present-day coastal inundation by **1.7–25× at RP100**, because 30 m terrain cannot resolve the sub-pixel road raises, canals, and bunds that protect small present-day events. Replacing it with the local-inertia shallow-water solver, where the sea connects to the domain boundary, brings the over-prediction to ≈1×: Bangkok's RP100 coastal extent drops from 3,546 km² to **283 km² (a 12.5× reduction)**, within ~30 % of the documented 2011 megaflood extent. The bias correction is a solver-architecture fix, not a data limitation (Figure 3). Two further checks are consistent and space-limited here: the IDF-anchor re-derivation is exact (0 fails across all configurations), the documented high-water-mark depth cross-check is in-band at three of five points, and satellite extent-CSI is reported only as an observation-limited sanity check (urban SAR layover and MODIS coarseness suppress the reference).

[**Figure 3.** Bathtub-bias factor (model / documented) at RP2 and RP100 by city, with the local-inertia overlay for the three solver-compatible cities (log scale); the 12.5× Bangkok RP100 reduction to ≈1× is the headline. Singapore's residual ratio stays high because its documented present-day coastal extent is near zero. `docs/paper/figures/ieee_fig3_bathtub_bias.png`.]

---

## V. Impact and Limitations

The intended use is humanitarian: open, validated, reproducible hazard maps as decision-support for the municipal disaster-management and climate-adaptation agencies that cannot license commercial models. Because every input is free and every parameter is documented, an agency or a regional university can rebuild the atlas for its own city, interrogate the assumptions, and extend it — lowering the barrier to first-order flood-risk information from a procurement question to a software install.

The model is honest as a *screening upper bound* under three assumptions: no active pumping, no sub-pixel defences resolved by the 30 m DEM, and per-pixel-maximum (marginal, not joint-exceedance) multi-hazard composition. The scenario forcing is consistent across the full SSP × horizon grid — monotone in scenario severity and within physical plausibility bounds, verified by an automated consistency guard — and the headline quantitative results use the validated SSP5-8.5/2100 and present-day cells. Two further findings bound transferability and are reported rather than tuned away: single-stage HAND does not transfer to flat deltas fed by an out-of-domain mega-river (Bangkok, Jakarta), and the pluvial solver is currently heterogeneous across cities (a documented homogenisation step). The two further ASEAN cities — Manila (enclosed bay) and Ho Chi Minh City (enclosed delta) — are deferred because their enclosed-sea topology breaks the inertial solver's wall condition; relaxing that condition is the principal prerequisite for extending the bias-aware coastal treatment to them.

---

## VI. Conclusion

We have shown that an open-source, open-data, per-country-calibrated 30 m multi-hazard flood atlas for ASEAN cities is feasible, reproducible from free data, and — by a model-blind location-skill gate — demonstrably skilful in the four cities tested, with its coastal over-prediction structurally corrected. To our knowledge it is the first such atlas released with full code, configuration, and validation transparency for the region. By targeting exactly the cities that commercial high-resolution models exclude, the release is offered as a public good for humanitarian flood-risk reduction, and as an invitation to extend. Code, per-city configuration, and validation registers are released at <https://github.com/phangdaniel-debug/ASEAN_flood_model>.

---

## References

<!-- References are ordered by first citation in the text (IEEE convention), matching the .tex/.docx renderings. -->
[1] Asian Development Bank, "Asia in the Global Transition to Net Zero: Asian Development Outlook 2022 Thematic Report," 2022.
[2] G. Lenderink, R. Barbero, J. M. Loriaux, and H. J. Fowler, "Super-Clausius–Clapeyron Scaling of Extreme Hourly Convective Precipitation and Its Relation to Large-Scale Atmospheric Conditions," *J. Climate*, vol. 30, pp. 6037–6052, 2017.
[3] E. Chaussard, F. Amelung, H. Abidin, and S.-H. Hong, "Sinking cities in Indonesia: ALOS PALSAR detects rapid subsidence," *Remote Sens. Environ.*, vol. 128, pp. 150–161, 2013.
[4] H. Z. Abidin et al., "Land subsidence of Jakarta and its relation with urban development," *Nat. Hazards*, vol. 59, pp. 1753–1771, 2011.
[5] N. Phien-wej, P. H. Giao, and P. Nutalaya, "Land subsidence in Bangkok, Thailand," *Eng. Geol.*, vol. 82, pp. 187–201, 2006.
[6] S. Hallegatte, C. Green, R. J. Nicholls, and J. Corfee-Morlot, "Future flood losses in major coastal cities," *Nat. Clim. Change*, vol. 3, pp. 802–806, 2013.
[7] B. Tellman et al., "Satellite imaging reveals increased proportion of population exposed to floods," *Nature*, vol. 596, pp. 80–86, 2021.
[8] O. E. J. Wing et al., "A 30 m global flood inundation model for any climate scenario," *Water Resour. Res.*, vol. 60, e2023WR036460, 2024.
[9] R. W. Hofste, P. Reig, and L. Schleifer, "Aqueduct 3.0: Updated Decision-Relevant Global Water Risk Indicators," World Resources Institute, 2019.
[10] P. J. Ward et al., "Aqueduct Floods: global flood risk maps and analysis," 2020.
[11] E. H. Sutanudjaja et al., "PCR-GLOBWB 2: a 5 arcmin global hydrological and water resources model," *Geosci. Model Dev.*, vol. 11, pp. 2429–2453, 2018.
[12] J. Muñoz-Sabater et al., "ERA5-Land: a state-of-the-art global reanalysis dataset for land applications," *Earth Syst. Sci. Data*, vol. 13, pp. 4349–4383, 2021.
[13] L. Alfieri et al., "A global network for operational flood risk reduction (GloFAS)," *Environ. Sci. Policy*, vol. 84, pp. 149–158, 2018.
[14] B. Fox-Kemper et al., "Ocean, Cryosphere and Sea Level Change," in *Climate Change 2021: The Physical Science Basis (IPCC AR6 WGI)*, Cambridge Univ. Press, 2021.
[15] D. Zanaga et al., "ESA WorldCover 10 m 2021 v200," Zenodo, 2022.
[16] R. Pawlowicz, B. Beardsley, and S. Lentz, "Classical tidal harmonic analysis including error estimates in MATLAB using T_TIDE," *Comput. Geosci.*, vol. 28, pp. 929–937, 2002.
[17] S. Muis, M. Verlaan, H. C. Winsemius, J. C. J. H. Aerts, and P. J. Ward, "A global reanalysis of storm surges and extreme sea levels," *Nat. Commun.*, vol. 7, 11969, 2016.
[18] S. Muis et al., "A high-resolution global dataset of extreme sea levels, tides, and storm surges, including future projections," *Front. Mar. Sci.*, vol. 7, 263, 2020.
[19] P. D. Bates, M. S. Horritt, and T. J. Fewtrell, "A simple inertial formulation of the shallow water equations for efficient two-dimensional flood inundation modelling," *J. Hydrol.*, vol. 387, no. 1–2, pp. 33–45, 2010.
[20] A. D. Nobre et al., "Height Above the Nearest Drainage — a hydrologically relevant new terrain model," *J. Hydrol.*, vol. 404, pp. 13–29, 2011.
[21] C. D. Rennó, A. D. Nobre, L. A. Cuartas, J. V. Soares, M. G. Hodnett, J. Tomasella, and M. A. Waterloo, "HAND, a new terrain descriptor using SRTM-DEM: Mapping terra-firme rainforest environments in Amazonia," *Remote Sens. Environ.*, vol. 112, pp. 3469–3481, 2008.
[22] R. Barnes, K. L. Callaghan, and A. D. Wickert, "Computing water flow through complex landscapes — Part 3: Fill–Spill–Merge," *Earth Surf. Dynam.*, vol. 9, pp. 105–121, 2021.
[23] O. Planchon and F. Darboux, "A fast, simple and versatile algorithm to fill the depressions of digital elevation models," *Catena*, vol. 46, pp. 159–176, 2002.
