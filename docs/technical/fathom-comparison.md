# Methodology comparison: Fathom Global Flood Map vs this atlas

**Reference model:** Wing, O. E. J. *et al.* (2024), "A 30 m Global Flood Inundation Model
for Any Climate Scenario," *Water Resources Research* 60, e2023WR036460.
doi:10.1029/2023WR036460. (Saved: `docs/paper/References/[12] Water Resources Research -
2024 - Wing - A 30 m Global Flood Inundation Model for Any Climate Scenario.pdf`.)

**Prepared:** 2026-07-21. All Fathom claims below are quoted or paraphrased from the saved
PDF; all "this paper" claims are from `docs/technical/model-documentation.md`, the two
manuscripts (`docs/paper/ieee-kse2026.tex`, `docs/paper/safe2026-v5.tex`), and the code.

---

## The core divergence

Fathom and this atlas share the same hydraulic DNA but sit at opposite ends of the
generalist↔specialist axis. Fathom is a global, commercial, transfer-calibrated
generalist; this atlas is a four-city, open, per-country-calibrated specialist.

| | **Fathom (Wing 2024)** | **This paper** |
|---|---|---|
| Design goal | One consistent model for *every* terrestrial pixel on Earth, any RP, any scenario | Maximum fidelity for *four specific* ASEAN cities the global models serve worst |
| Calibration philosophy | Transfer from data-rich regions (US/UK gauges, maps) to data-poor via ML/regionalization | Calibrate *in-region*, per-country; refuse to transfer parameters between cities |
| Access | Commercial, closed, licensed | Open code + open data + reproducible |
| Coverage | Global (ex-Greenland/Antarctica) | Singapore, Kuala Lumpur, Bangkok, Jakarta |

---

## Dimension-by-dimension

| Axis | **Fathom** | **This paper** |
|---|---|---|
| Resolution | ~30 m (native compute 3 arcsec) | 30 m |
| Terrain | **FABDEM** (Hawker 2022) — Copernicus DEM with ML forest+building removal, a *global* bare-earth product | Copernicus GLO-30 corrected to bare-earth by a **per-city** building+canopy error model (`z_bare = z_DSM − b₀ − h_building − f·h_canopy`), the two params fit against held-out **ICESat-2 + GEDI** lidar, never transferred |
| Hydraulic engine | **LISFLOOD-FP**, Bates 2010 local-inertial 2D shallow-water, for *all three* perils | **Bates 2010 local-inertia** for coastal; HAND + fill-spill for fluvial/pluvial (not full hydrodynamics) |
| Fluvial forcing | ML **Regional Flood Frequency Analysis** — growth curves (Smith 2015) + index flood from catchment descriptors (CHELSA/MERIT) | **GloFAS** design discharge at matched RP |
| Fluvial routing | Full 2D hydraulic sim; channel capacity via **gradually-varied solver** (Neal 2021), not Manning | Discharge→stage via **Manning uniform-flow rating**, mapped by **HAND** referenced to the **main-stem trunk** (per-city accumulation threshold: ≥180 km² KL, ≥50 km² SG/JKT) |
| Pluvial forcing | IDF from **Global Sub-Daily Rainfall** (GSDR global gauges) | **National met-service IDF** (PUB/JPS/TMD/BMKG) — the "28–62% deficit" the global products carry |
| Pluvial routing | **Rain-on-grid** 2D hydraulic sim, 1/3/6 hr durations (capped at 6 hr to avoid double-counting small rivers) | **Regime-matched, steady-state**: fill-and-spill cascade (Bangkok) or HAND "handfill" (canal cities); WorldCover runoff coeff; no hydrograph timing/infiltration |
| Coastal forcing | Extreme-sea-level frequency (Sweet 2020) from **5 sources**: GESLA gauges, GTSM reanalysis, FES2014 tides, **ERA5 wave setup**, + MDT | **GEV** on UHSLC annual-max still-water levels (tide+surge) + AR6 SLR; no wave-setup term |
| Coastal datum | **MDT from HYBRID-CNES-CLS18-CMEMS2020** | **CNES-CLS MDT offset** (interim CNES-CLS18) — *same product family* |
| Defenses | Post-process removes floods more frequent than design standard; **FLOPROS** (Scussolini 2016) + GHSL urbanization where unknown | Explicit **seawalls + Bangkok pumped polder**; documented defence physics per city |
| Climate | **"Any scenario"** via change factors — CMIP6 HighResMIP/PRIMAVERA (pluvial), ISIMIP2b RCP8.5 GHMs (fluvial), SLR by time/warming | Discrete **SSP2-4.5 / SSP5-8.5 × 2050 / 2100** |
| Subsidence | Vertical land motion folded into coastal change factors | **Zone subsidence**, reported *separately* for sensitivity |
| Return periods | 10 RPs | RP 10 / 100 / 1000 (+present) |
| Uncertainty | Explicit likely-range bounds via sampling | Bootstrap CIs on validation skill; sensitivity analyses (t_end, Manning n, IDF duration) |
| Validation | **Grid CSI ≈ 0.75** vs ~10⁵ engineering flood maps (US/UK) + **water-level ~0.6 m** vs observed WLs | **Model-blind hotspot location-skill gate** (HR/CRR/**TSS**, bootstrap CI excludes 0); 3/4 cities pass + joint sens/spec bar; **bathtub-bias** characterization |

---

## Where they share DNA (worth stating in the paper)

1. **Same coastal solver lineage.** This atlas's local-inertia coastal engine *is* the
   Bates 2010 / LISFLOOD-FP formulation that Fathom runs for all perils. Not a lesser
   engine for coastal — the same one, applied locally.
2. **Same bare-earth premise.** Both reject the DSM and correct Copernicus to ground.
   Fathom buys the global FABDEM product; this atlas builds a per-city, lidar-calibrated
   correction — arguably *more* accurate where the lidar is dense (the "halves MAE"
   result), at the cost of not scaling.
3. **Same MDT product.** Fathom's datum uses HYBRID-CNES-CLS18-CMEMS2020; this atlas's
   offset is CNES-CLS18. The datum choice is literally the Fathom-grade one — citeable
   defensively.

---

## Where this atlas is genuinely differentiated (the contribution surface)

- **National IDF anchoring** — Fathom's pluvial rides on *global* GSDR gauges; this atlas
  uses each country's *published statutory* IDF. Clearest methodological edge; directly
  rebuts the "global products under-rain the tropics" gap.
- **Openness** — reproducible from free data vs a licensed black box.
- **Explicit, documented defences** — Fathom estimates protection from a global FLOPROS
  proxy; this atlas models Bangkok's actual pumped polder and named seawalls.
- **Honest urban-core validation** — the hotspot/TSS gate probes exactly where Fathom's
  grid CSI is blind (SAR/MODIS urban masking), and it is model-blind.

---

## Where Fathom is stronger (be candid in the paper)

- **Full hydrodynamics for pluvial/fluvial** (rain-on-grid + gradually-varied channels) vs
  steady-state HAND/fill-spill — Fathom resolves hydrograph timing and channel backwater
  this atlas does not.
- **Richer coastal forcing** — Fathom adds ERA5 wave setup; this atlas stops at
  tide+surge+SLR.
- **Continuous scenario space + formal uncertainty bounds** vs a discrete SSP×horizon grid.
- **Validation depth** — CSI 0.75 against wall-to-wall engineering maps is a benchmark this
  atlas cannot match (no such maps exist for these cities — the very reason it uses
  hotspots). See the CSI/benchmark note below.

---

## Note on CSI comparability (why "our CSI vs Fathom's 0.75" would mislead)

Fathom's CSI = TP/(TP+FP+FN) is a **grid-cell extent-overlap** metric computed against
~10⁵ engineering-grade local flood-map rasters (US/UK). This atlas computes CSI in the same
way in `scripts/validate_historical_events.py`, but only against **single-event remote-
sensing footprints** (SAR/MODIS), which exist for only two of the four cities on disk
(Bangkok MODIS 250 m THA2011; Jakarta Sentinel-1 SAR JKT2020) and systematically **blank
the dense urban core** (SAR layover/shadow; Kuala Lumpur **87.2%** of bbox masked in every
peak pass, leaving 455 km² assessable in which only 0.14 km² of flood was detected →
hit-rate-only "LIMITED" verdict; Singapore has no event-extent raster at all).
The grid-CSI gate thresholds (`CSI_PASS = 0.30`) already reflect this: they are set for
coarse footprints, nothing like Fathom's 0.75. **A Fathom-comparable grid CSI cannot
honestly be reported for these cities** — which is precisely why the primary validation is
the point-based hotspot/TSS gate that probes the urban core the remote-sensing benchmarks
miss.

> **KL exclusion figure corrected 2026-08-16.** This passage previously read "~69% of bbox
> masked", inherited from the `fetch_gfm_mys2021.py` header. Measured directly from the
> Copernicus GFM `exclusion_mask` asset over the Dec 19–22 peak passes, the true figure is
> **87.2%** (3,085 of 3,539 km²). The mask had never been downloaded — only
> `ensemble_flood_extent`, which codes `0 = not flooded` with no way to express *could not
> assess* — so the exclusion could not be measured at the time. Both are fixed; see
> `data/kuala_lumpur/manifest/observed_events.csv`.
>
> This matters beyond bookkeeping: scoring an extent metric without that mask counts model
> water in excluded urban areas as false positives against ground the sensor never saw. On
> the KL cell that produced a frequency bias of ~2,900 and a precision of 0.00. **No
> manuscript claim is affected** — neither paper reports any event-extent or CSI result, and
> the released Zenodo dataset ships no event-extent raster.

---

## Framing recommendation

Position this not as "we beat Fathom" but as: *the same physics (Bates 2010 solver,
bare-earth Copernicus, CNES-CLS MDT), re-instantiated open and regionally calibrated for
the cities global generalists systematically under-serve — trading Fathom's global reach
and full hydrodynamics for national-IDF fidelity, documented local defences, transparency,
and urban-core-honest validation.* Accurate, defensible, non-overclaiming.
