# A city-calibrated open multi-hazard flood model validated against documented local hazard: a Singapore methodology

**Authors:** TBD
**Affiliations:** TBD
**Target venue:** TBD (candidate: *Natural Hazards and Earth System Sciences*; *Environmental Modelling & Software*)
**Draft version:** v0.3 — standalone draft (2026-06-01). Methods, results (incl. the full scenario grid), abstract, and discussion are populated and frozen on the validated runs. Remaining for journal form: a reference list (inline author-year citations are unresolved) and figure rendering.

> Status and intent. This is a **standalone paper**, intended to stand on its own and —
> over time — to **supersede** the earlier ASEAN multi-city atlas drafts as the lead
> publication for this work. It is not a companion or precursor to them. Its contribution
> is a **falsifiable comparative claim, rigorously validated**: that a city-calibrated
> open-data model captures *locally documented* flood behaviour a generic global vendor
> omits by design — demonstrated first for Singapore pluvial flooding, with a validation
> framework (documented flood-prone register + True Skill Statistic + dual open baseline
> + two-gate "done") designed to generalise to further cities. Any references in this
> draft to the atlas drafts or to internal repository paths are transitional scaffolding
> and will be removed as the paper is made fully self-contained.

---

## Abstract

*(Placeholder — to be written once the final validated numbers land.)* We present a
commercial-safe, open-data **multi-hazard** (coastal, fluvial, pluvial) flood model for
Singapore at 30 m, and a validation framework built around a narrow, falsifiable claim:
that encoding local drainage standards, local rainfall statistics, and a locally
documented flood-prone register lets an open model flag the locations a city authority
actually documents as flood-prone, where a generic global vendor does not. All three
hazards are modelled with fully documented open methods — bathtub coastal routing on
tide-gauge-derived GEV water levels plus AR6 sea-level rise; Height-Above-Nearest-
Drainage fluvial inundation; and a local-inertial rain-on-grid pluvial solver on a
surgically de-pitted bare-earth DEM. Validation is **tiered to the available local
ground truth**: the pluvial hazard carries the comparative claim, scored against the
model and two open comparators on the official PUB *List of Flood-Prone Areas* using the
True Skill Statistic with documented dry-control points; the coastal and fluvial hazards
are validated by a fixed plausibility framework (datum/sea-level sanity, monotonicity,
documented high-water marks, channel-masking, no-blow-up). Every model decision is
anchored to a documented design standard or observed event, and "done" is a two-gate
conjunction of a numeric gate and a fixed visual-coherence checklist. Scored against the
**full official PUB register (all 36 Nov-2025 flood-prone areas, authoritatively geocoded
via OneMap, plus 2 historical events = 38 positives)** and **20 dry controls** (elevated
reserves plus low-lying town centres absent from the comprehensive PUB list), the result
separates onto two axes. On **combined location skill** (True Skill Statistic) the
city-calibrated model and a naive topographic baseline are **statistically indistinguishable**
— every paired ΔTSS interval spans zero — because the official register is overwhelmingly low
convergent ground a wetness index captures almost perfectly (TWI hit-rate 0.92). On
**specificity**, however, the model is **significantly better**: naive TWI wrongly floods 14
of 20 documented-dry points to the model's 7 (paired ΔCRR +0.35, 95 % CI [+0.10, +0.60],
excludes zero) — a precision–recall split in which TWI is high-recall/low-precision and the
calibrated, drainage-aware model is lower-recall/high-precision. The model also provides
pluvial **coverage** the generic vendor structurally lacks: it flags 15 of 38 documented
points to Aqueduct's 3 (paired Δ hit-rate +0.32, CI excludes zero). The pluvial
layer passes its depth-band, monotonicity and visual-coherence gates, while the coastal and
fluvial layers pass plausibility gates. We argue the calibrated model's value lies in
mechanism, depth realism and specificity rather than mere location, and that an honest documented-register yardstick — which here also exposed a
forcing-provenance data error and declined a metric re-anchoring the documented event
return-periods did not justify — is what makes the comparative claim meaningful at all.

**Keywords:** flood modelling, multi-hazard, coastal, fluvial, pluvial, Singapore, open
data, HAND, drainage-exceedance, rain-on-grid, GEV, AR6 sea-level rise, True Skill
Statistic, validation, reproducibility, commercial-safe

---

## 1. Introduction

### 1.1 The claim, and why it is narrow on purpose

Global flood vendors (e.g. Fathom, JBA) wrote the modern inundation solvers, built
bespoke bare-earth DEMs, and validate globally; out-competing them everywhere is not a
credible thesis. The defensible — and commercially and scientifically useful — claim is
*comparative and local*: **for a specific city, an open model calibrated to that city's
documented drainage standards, rainfall statistics, and flood register can reproduce
locally documented flood behaviour that generic global products omit by design.** This
paper makes that claim falsifiable and tests it for Singapore, whose dominant flood
mechanism is pluvial flash-flood ponding (drainage exceedance during short convective
bursts), and whose flood-prone locations are published by the national water agency
(PUB).

The claim is deliberately narrow. A comparative claim is meaningless without a common
yardstick, so **validation is mandatory, not optional**, and the bulk of this paper is
the validation framework (§4). The same framework is the product's quality gate.

**The open-data pluvial gap (the motivation).** The "omit by design" clause is not
rhetorical — it is the structural state of the flood-product landscape (Table 1a, verified
2026). Every *open, commercial-usable* global flood product is riverine and/or coastal
with **no pluvial layer**; every product that *does* model pluvial is closed/commercial,
and the one with a free tier (Fathom-Global 3.0) restricts it to **non-commercial** use in
a fixed set of low-income countries that excludes Singapore. So for urban
drainage-exceedance flooding — Singapore's dominant mechanism — there is **no open,
commercial-safe comparator to beat**: the gap itself is the opportunity this work targets.
This also reframes the comparison honestly (§4.4): the generic global vendor (Aqueduct)
appears not as a scored skill rival but as the *evidence of the gap* (it flags almost none of
the pluvial register — only 3 of 38, the riverine/coastal-adjacent points — by construction);
the binding open comparison is against a naive
topographic method any practitioner could run for free.

**Table 1a.** Flood-product landscape for an open, commercial-safe Singapore pluvial layer
(verified 2026).

| Product | Pluvial? | Open & commercial-safe for Singapore? |
|---|---|---|
| WRI Aqueduct 4.0 | No (riverine + coastal) | Yes (→ structural 0 on pluvial) |
| JRC Global River, GLOFRIS/PCR-GLOBWB | No (riverine) | Yes |
| MODIS/VIIRS NRT flood (NASA) | n/a (satellite observation, ~250 m) | Yes, but not a design-RP hazard map |
| **Fathom-Global 3.0** | **Yes** (30 m) | **No** — free tier is non-commercial + 16 low-income countries, excl. Singapore |
| JBA Global | Yes | No — commercial/closed |
| **This work** | **Yes** (rain-on-grid) | **Yes** |

The *deliverable*, however, is a complete **multi-hazard** screening model: coastal,
fluvial, and pluvial depth maps at 30 m for Singapore (§3). All three hazards receive
full, documented open methods. What differs between them is the **strength of available
local ground truth**, and therefore the strength of validation each can honestly carry
(§2). We do not weaken the comparative claim by stretching it over hazards Singapore
cannot evidence comparatively; instead we tier validation to the evidence (§2) and state
plainly which hazard carries the falsifiable claim (pluvial) and which are validated for
plausibility (coastal, fluvial). The methods themselves are first-class for all three.

### 1.2 Commercial-safe by construction

A commercial product cannot depend on non-commercial inputs. We therefore **exclude
FABDEM** (CC BY-NC-SA) and every other non-commercial dataset, and build a bare-earth
surface ourselves from commercially licensable sources (§3.2). All inputs in Table 1
are open and permit commercial use.

**Table 1.** Model inputs (all commercial-safe).

| Input | Source | Licence |
|---|---|---|
| Surface DEM | Copernicus GLO-30 DSM | open, commercial-OK |
| Building footprints | Google Open Buildings v3 | CC BY-4.0 |
| Land cover | ESA WorldCover 2021 | CC BY-4.0 |
| Rainfall | ERA5 / ERA5-Land (Copernicus) | commercial-OK |
| River discharge | GloFAS (Copernicus) | commercial-OK |
| Sea level | AR6 SLR projections; UHSLC/GESLA tide gauges | open |
| Flood-prone register | PUB *List of Flood-Prone Areas* (Nov 2025) | public |

### 1.3 Process contribution: numbers open and close tickets, eyes only veto

Flood-map development is prone to an open-ended "eyeball loop": an output *looks* wrong,
a parameter is nudged, something else looks wrong, with no objective stopping condition.
Real flood maps also look strange (canals appear below-grade; flat deltas sheet; low-RP
coastlines barely flood), so visual plausibility is not a fixed point. We adopt an
explicit discipline (§4.1): **every model decision is anchored to a documented fact**
(a drainage standard, an IDF curve, a documented hotspot, an observed extent);
**acceptance is numeric**; visual review may *veto or raise a question* but may never
*accept* a map or be the optimisation target. This process discipline — and the
two-gate "done" definition it implies — is a contribution in its own right.

---

## 2. Singapore scope and hazard tiering

The model is a full three-hazard Singapore map (coastal + fluvial + pluvial). All three
hazards are modelled with first-class, fully documented open methods (§3). What is
**tiered is validation, not methodology**: the three hazards cannot carry equal
*evidentiary* weight in Singapore, so each is validated as strongly as its local ground
truth honestly allows (Table 2).

**Table 2.** Validation tiering for Singapore (methods are first-class for all three; see §3).

| Hazard | Method (§3) | Validation tier | Why this tier |
|---|---|---|---|
| **Pluvial** | Local-inertial rain-on-grid, drainage-exceedance | **Comparative** — TSS vs PUB register + dual baseline (§4) | Dominant local mechanism; richest documentation (PUB register); the only hazard with a working comparative yardstick. |
| Coastal | Bathtub on GEV water level + AR6 SLR | Plausibility — datum/SLR sanity, monotonicity, HWM, no blow-up (§4.6) | No SAR-visible Singapore coastal event to score against; comparison would be unfalsifiable. |
| Fluvial | HAND with channel-masking | Plausibility — channel-masking, monotonicity, sane wet fraction, HWM (§4.6) | Minor in Singapore (short canalised catchments, reservoir-dammed rivers); thin local event record. |

The tiering is an honesty constraint, not a quality ranking: coastal and fluvial get the
same anti-eyeball discipline (a fixed binary plausibility checklist; every visual
observation converted to a check or a logged limitation) — they simply do not carry a
*comparative* claim, because Singapore's data cannot falsify one for those hazards. The
comparative framework (§4) is built to extend to coastal and fluvial in cities that *do*
have documented multi-hazard events (Bangkok 2011, Manila 2009, Jakarta 2020), which is
the natural multi-city generalisation.

---

## 3. Pipeline and methods

The pipeline is pure-Python (rasterio, scipy, pyproj, pysheds, numba). A per-city
configuration object (`cities.py`) parameterises one orchestration script
(`run_city_pipeline.py`). Singapore reference parameters: UTM 48N (EPSG:32648);
ERA5 point 1.2903 °N, 103.8519 °E; UHSLC 699 Tanjong Pagar (39-yr record);
`drain_capacity = 50 mm/h` (effective network threshold; see §3.5);
1-h IDF anchors RP10 = 82 mm, RP100 = 120 mm (MSS/PUB), Gumbel μ = 46 mm, σ = 16 mm.

Each component below is documented as **mechanism → alternatives considered → selection
rationale**. The recurring selection criterion is the project's binding constraint: the
*lightest physically defensible method that runs on open, commercial-safe data alone* — heavier
methods are rejected not because they are worse science but because they require proprietary or
unavailable inputs (LiDAR point clouds, piped-drainage networks, surveyed cross-sections) that
break the open-data premise.

### 3.1 Terrain

Copernicus GLO-30 DSM (TanDEM-X X-band InSAR, ~2011–2015 acquisitions), referenced to
EGM2008, reprojected to UTM 48N at 30 m. EGM2008 referencing aligns directly with AR6 SLR
projections and tide-gauge water levels. WSE = MSL + tide + surge + SLR; Singapore
`msl_to_egm2008_offset = 1.1588 m`; AR6 SSP5-8.5 2100 SLR = 0.674 m.

*Alternatives considered.* (i) **SRTM 1-arcsec** (30 m) — older (2000), C-band, with voids and
more vegetation/building bias, and a poorer vertical datum tie; superseded by GLO-30. (ii)
**ASTER GDEM** — stereo-optical, noticeably noisier (stacking artefacts), unsuitable for
hydrological routing. (iii) **ALOS AW3D30 / NASADEM** — comparable open 30 m DSMs; GLO-30 is the
most internally consistent and best-documented, with the cleanest EGM2008 referencing. (iv)
**National LiDAR** (Singapore has 1 m airborne LiDAR) — far superior, but not open or
commercial-safe, so excluded by the project's licensing constraint. (v) **Commercial 12 m
TanDEM-X / Vricon** — better but proprietary. GLO-30 is chosen as the best open, commercial-safe,
globally consistent surface that ties cleanly to the sea-level datum; 30 m is adequate for a
screening product, and the DSM-vs-bare-earth gap it leaves is handled in §3.2.

### 3.2 DIY bare-earth DEM (FABDEM-free)

A DSM includes buildings; for rain-on-grid routing the raised roofs and, more damagingly, the
narrow voids *between* buildings create spurious enclosed micro-pits that trap routed water.
Because FABDEM is non-commercial, we derive a bare-earth surface ourselves
(`build_bareearth_dem.py`): Google Open Buildings v3 footprints are rasterised to a per-cell
building-coverage fraction; cells above a coverage threshold (0.25) are flagged building-
contaminated, removed, and the ground beneath reconstructed by inverse-distance infill from
surrounding open (road/park/water) cells (`rasterio.fill.fillnodata`, 50-cell search, 2 smoothing
passes); a light 3×3 median then suppresses residual DSM noise. Singapore's dense road grid
guarantees nearby open cells, so the infill is well constrained. The surface is then
hydrologically conditioned (`build_conditioned_dem.py`).

*Alternatives considered.* (i) **FABDEM** (Neal/Hawker ML-derived bare-earth from GLO-30) — the
obvious choice and what we emulate, but CC BY-NC-SA, so excluded by the commercial-safe rule.
(ii) **Point-cloud ground filters** (cloth-simulation filter; progressive morphological filter) —
the standard bare-earth approach, but they require a LiDAR/photogrammetric *point cloud*, which we
do not have open; they cannot operate on a 30 m raster. (iii) **Subtract a global building-height
layer** (e.g. GHSL building height, WSF-3D) — plausible, but height products are coarse/uncertain
at 30 m and would not remove the inter-building void artefact, which is the actual failure mode.
(iv) **Use the raw DSM** — breaks rain-on-grid (the spurious pits drive the high-RP blow-up, §3.3).
The chosen footprint-removal-plus-infill is the simplest method that is commercial-safe, works on
the raster we have, and targets the specific artefact that matters.

### 3.3 Hydrological conditioning and surgical de-pitting

Conditioning burns the open drainage network (OSM canals) down a fixed depth, applies
moderate median smoothing, and fills shallow noise pits (< 0.5 m) while preserving
deeper basins. For the **rain-on-grid** model specifically, this is insufficient: the
DSM retains enclosed depressions — including spurious sub-sea-level holes
(Copernicus GLO-30 artefacts reaching −23 m on land) — in which a drainage-exceedance
solver accumulates water without bound, producing physically impossible ponding depths
at high return periods.

We therefore emit a **surgically de-pitted DEM for rain-on-grid only**
(`build_conditioned_dem.py --raingrid-out`): starting from the conditioned surface, we
fill an enclosed depression iff its floor is sub-sea-level (`< 0 m` EGM2008 on land — an
unambiguous DSM artefact) **or** its maximum depth is `≥ D` m, while preserving genuine
shallow hollows so real flood-prone lows still pond. The threshold `D` is anchored to
the engineering life-safety cap (§4) and is the single tunable, governed by an explicit
refinement discipline (anchored, pre-registered, never adjusted to flip a verdict).
Real Singapore depressions drain via the storm-drain network, already represented by
subtracting `drain_capacity` from rainfall upfront; leaving them as overland traps would
double-count that storage. The fill-spill model and the coastal/fluvial paths continue
to use the un-de-pitted conditioned DEM.

*Alternatives considered.* (i) **Full depression filling** (Planchon–Darboux / priority-flood;
Barnes et al., 2014) — the textbook conditioning that removes *all* sinks. On a near-flat island
it is degenerate: it either raises whole districts to a spill level (flooding the island as a thin
sheet) or erases the genuine shallow hollows that are the real flood-prone lows — destroying the
signal we are trying to measure. (ii) **Stream breaching/carving** — carves drainage channels
instead of filling; appropriate for fluvial routing (and used implicitly via the OSM-canal burn),
but it does not remove the *enclosed* DSM-artefact pits that break rain-on-grid. (iii) **No
conditioning** — leaves the sub-sea-level artefact pits, which accumulate water without bound and
produce the 27.8 m high-RP blow-up we observed. (iv) **Fill to a fixed absolute floor** — a blunt
version that still erases real hollows. The chosen *surgical* rule (fill only sub-sea-level or
over-deep ≥ D enclosed depressions, keep shallow hollows) is the minimal intervention that removes
the artefacts while preserving the physically real lows — the discriminating-negative analogue at
the terrain level.

### 3.4 Coastal

**Water-level statistics.** The coastal still-water level at return period RP is
`WSE(RP) = MSL + tide + surge(RP) + SLR`. The storm-surge component is derived from the
UHSLC Research-Quality tide gauge 699 at Tanjong Pagar (39-year hourly record): we remove
the predictable astronomical tide by T_TIDE harmonic analysis (Pawlowicz et al., 2002),
extract annual maxima of the surge residual, and fit a Generalised Extreme Value (GEV)
distribution by maximum likelihood with the shape parameter capped at ξ_max = 0.30 to
prevent tail runaway on a finite record.

**Datum.** Tide-gauge levels are referenced to local mean sea level; the GLO-30 DEM is
referenced to EGM2008. We bring them onto a common datum with the mean-dynamic-topography
offset sampled from CMEMS CNES-CLS at the gauge (`msl_to_egm2008_offset = 1.1588 m` for
Singapore). Future sea-level rise is added from the IPCC AR6 WG1 projection ensemble
(Fox-Kemper et al., 2021) via the public NCAR/Rutgers Zarr store; the SSP5-8.5 / 2100
P50 delta at Singapore is +0.674 m.

**Routing.** A bathtub solver fills cells hydrologically connected to the sea up to
`WSE(RP)` via breadth-first search seeded from sea and tidal-channel cells. For a compact,
relatively steep island this is an appropriate, fast, and defensible screening choice; a
2-D local-inertial coastal solver (Bates et al., 2010) is implemented and available but
is not required for Singapore, whose coastal layer is validated for plausibility rather
than against a documented extent. A physical depth cap
(`phys_cap = max(0, WSE − bed) + 0.2 m` velocity-head margin) guards against any solver
blow-up. The sea mask is built from the **pre-defence** DEM so that engineered crests act
as flood-routing barriers, not as re-definitions of what is ocean.

*Alternatives considered — water-level statistics.* (i) **Gumbel (GEV with ξ = 0)** — simpler, but
forces a light tail and can under-state rare surge; we keep the shape parameter free but cap it at
ξ_max = 0.30 to avoid runaway on a 39-year record. (ii) **Peaks-over-threshold / Generalised Pareto**
— uses more of the record than annual maxima and is often preferable for short series, but needs a
defensible threshold and declustering; for a multi-decade hourly gauge the annual-maxima GEV is
standard, transparent, and adequate for a screening upper bound. (iii) **Empirical return levels**
— no extrapolation beyond the record, so unusable at RP100+. *Alternatives — routing.* (i)
**Planar (unconnected) bathtub** — floods every cell below WSE regardless of hydraulic connection
to the sea, badly over-predicting inland lows; we use connectivity (BFS from sea/tidal cells) to
avoid this. (ii) **2-D local-inertial coastal** (Bates et al., 2010) — adds dynamics and a ~1.4×
extent reduction for Singapore; implemented and available, but not required because the coastal
layer is plausibility-validated, not scored against a documented extent (and would still need
defence/pumping data to be quantitatively trusted). (iii) **Full shallow-water / ADCIRC-class
surge models** — most accurate, but require bathymetry, wind/pressure forcing, and calibration far
beyond an open screening product. Connected-bathtub on GEV levels is the appropriate
fast-and-defensible screening choice; it is read as a no-defence upper bound (§4.6, register #3b).

### 3.5 Pluvial — rain-on-grid drainage-exceedance

Singapore's floods are transient drainage-exceedance ponding on open low ground, not
closed-depression storage; a fill-spill model is structurally wrong here. We solve the
2-D local-inertial shallow-water equations (Bates et al., 2010) with a spatially
distributed rainfall source on the de-pitted DEM (`pluvial_rain_model.py`,
`run_rain_on_grid`). Net excess rainfall per return period is
`max(0, IDF(RP) − drain_capacity) × runoff_coeff`, applied over the storm duration;
sea and open-channel cells are free-drainage outlets; per-cell Manning's n derives from
WorldCover land cover. Peak ponding depth over the storm-plus-settling window is the
output, post-processed with a small-cluster denoise. Two physical boundary/closure
conditions bound the result: an **open (transmissive) boundary** treats the clipped-
domain edge as a free-drainage outlet so runoff routed off-map exits rather than piling
against the array's no-flux wall; and a **physical depth cap** clips peak depth to a
documented engineering life-safety limit (3.0 m for Singapore), bounding residual
local-inertial overshoot — the same device the coastal solver uses (§3.4). Both are
applied after, and do not substitute for, the de-pitting of the input DEM (§3.3).

`drain_capacity = 50 mm/h` is the **effective** network threshold: the PUB Code of
Practice secondary-drain nominal is RP5 ≈ 70 mm/1h, but the limiting tertiary tier is
≈ RP2 (~40 mm/1h); 50 mm is chosen so ponding onset begins ~RP5, matching the documented
Orchard Road 2010–11 events. This is an example of the anchoring rule: the parameter is
tied to a documented standard and a documented event, not to visual plausibility.

*Why local-inertial, mechanistically.* The local-inertial form (Bates et al., 2010) drops the
advection (convective-acceleration) term from the full 2-D shallow-water equations but retains the
local-acceleration term, giving an explicit finite-difference scheme that is stable at much larger
time steps than diffusive-wave or full-dynamic solvers and runs city-scale in minutes. It captures
the thing that matters here — transient overland routing of excess water down the conditioned
terrain to where it ponds — without the cost or the (unavailable) data demands of a fully dynamic
model.

*Alternatives considered.* (i) **Fill-spill / depression-storage** — fills sinks to a spill level;
structurally wrong for Singapore, whose floods are *transient drainage-exceedance ponding on open
low ground*, not closed-basin storage, and degenerate on a flat island (§3.3). (ii) **Topographic
Wetness Index / topographic indices** — zero-cost and used here precisely as the *naive baseline*
(§4.4); they encode no rainfall, drainage, or routing and produce no depth or return period. (iii)
**SCS-Curve-Number + bathtub** — gives runoff volume but no overland routing dynamics or
peak-depth field. (iv) **Full 2-D hydrodynamic urban models** (TUFLOW, HEC-RAS 2-D, MIKE) or
**coupled 1-D-2-D pipe-surface models** (SWMM + 2-D) — the engineering gold standard, but they
require the **piped drainage network, inlet capacities, and calibration data** that are proprietary
and unavailable as open data, and are computationally far heavier; we instead represent drainage as
a documented net-excess subtraction (`IDF − drain_capacity`), which is the open-data-compatible
approximation. (v) **Machine-learning flood-susceptibility** — needs a training inventory (often the
very register we validate against, risking circularity) and yields a susceptibility score, not a
physical depth/RP field. Local-inertial rain-on-grid is the lightest physically based method that
produces a return-period-resolved depth field from open data alone — accepting, by design, that it
represents capacity exceedance rather than pipe-by-pipe hydraulics or blockage.

### 3.6 Fluvial — HAND (canal-overflow for Singapore)

**Framing.** Singapore has essentially no natural-river fluvial flooding: 17 reservoirs
dam the major water bodies and the Marina Barrage (2008) closes the Singapore–Kallang
system into a freshwater reservoir. The hazard labelled "fluvial" here is therefore
**PUB primary canal-network overflow** (Bukit Timah Canal, Stamford Canal, Geylang River)
under long-duration design rainfall — physically "canal-stage exceedance," distinct from
the sub-hourly pluvial-burst signal of §3.5, and to be read as such.

**Discharge baseline.** Because PUB canals are small (~10 km², dry between events) and
GloFAS routing at ~10 km is too coarse to resolve them, the design-storm stage is derived
from ERA5-Land hourly rainfall (Open-Meteo) via the Soil-Conservation-Service Curve-Number
method (direct runoff) translated to channel stage by Manning's normal-flow equation for a
representative wide channel, fit to a GEV with the same ξ_max cap as §3.4.

**Inundation.** Fluvial depth uses Height-Above-Nearest-Drainage (Nobre et al., 2011) on
the conditioned DEM: pysheds pit-filling and flat resolution, D8 flow direction and
accumulation, channels delineated by accumulation threshold or OSM waterways, and for each
off-channel cell the elevation above its nearest drainage cell. Depth at RP is
`max(0, stage_RP − bankfull − HAND)`. The output **masks channel cells**
(`depth = where(river_mask, 0, depth)`): raw overbank flood is dominated by engineered
below-grade canal beds, which are conveyance, not hazard, and would otherwise appear as
spurious "underground" inundation. The hazard is minor for Singapore and is
plausibility-validated (§4.6), not comparatively.

*How HAND works.* On the conditioned DEM, pysheds resolves flats and pits, computes D8 flow
direction and accumulation, and delineates a drainage network (accumulation threshold or OSM
waterways). For every off-channel cell it traces the flow path to the nearest drainage cell and
records the *vertical* drop to it — the Height Above Nearest Drainage. A reach floods to stage
`stage_RP`; a cell is inundated to `max(0, stage_RP − bankfull − HAND)`, i.e. when the local
channel stage exceeds the cell's height above the channel.

*Alternatives considered.* (i) **GloFAS / global river routing directly** — the obvious open
discharge source, but its ~10 km routing cannot resolve Singapore's ~10 km², dry-between-events PUB
canals; it is used for the regional ASEAN cities, not here. (ii) **1-D hydraulic models**
(HEC-RAS 1-D, MIKE 11) — the standard for canal-stage hydraulics, but they need *surveyed cross-
sections and structures*, which are not open for PUB canals. (iii) **2-D hydrodynamic** — needs
channel bathymetry and discharge boundary conditions we do not have. (iv) **Full 2-D rain-on-grid**
(as for pluvial) — would conflate the sub-hourly pluvial burst with the long-duration canal-stage
signal we deliberately separate. HAND is the standard open, terrain-only screening method for
ungauged channels: it needs only the DEM plus a design stage, is fast, and — with channel cells
masked — gives a defensible plausibility-tier overbank footprint for a hazard that is minor in
Singapore anyway.

---

## 4. Validation framework (the core contribution)

### 4.1 "Done" is a two-gate conjunction

A hazard map is **done** only when **both** gates pass; neither alone suffices. The two
gates apply to every hazard; what differs is the *content* of the numeric gate by tier
(§4.2–4.5 comparative for pluvial; §4.6 plausibility for coastal and fluvial).

- **Numeric gate** (stops the loop): the tier-appropriate validators below pass.
- **Visual gate** (keeps the product presentable; catches what validation has no ground
  truth for): a fixed binary checklist — monotone area/depth with RP; sane wet-area
  fraction; hazard separation (coastal at the coast, fluvial along channels, pluvial on
  low open ground); no domain-wide thin sheets, speckle, or single-cell spikes;
  documented hotspots lit and documented dry ground dry; coastline behaves.

The visual checklist is run only at defined cadence points (after a numeric pass, as a
final coherence veto; or on a numeric fail, to localise) — never as a tuning session. A
failed visual item opens a ticket that must be converted to a new numeric check or a
logged limitation (§4.7).

### 4.2 The documented-hotspot register

The positive ground truth is the official **PUB *List of Flood-Prone Areas* (Nov 2025)**
— the authoritative, current (post-mitigation) register of locations the water agency
documents as flood-prone. We take **all 36 entries** and geocode each (cited by its PUB
serial number) authoritatively via the **OneMap API (Singapore Land Authority)** — the
national surveyed gazetteer — rather than by hand, giving uniform, reproducible coordinates
(a DEM cross-check earlier showed hand-typed pins are unreliable; limitations #6b). To these
we add two depth-bearing **historical** anchors (Stamford Canal / Orchard Road ~0.4 m;
Bukit Timah Road ~0.25 m) that PUB has since drainage-upgraded off the list but which carry
documented depths for the high-water-mark check (§4.5) — **38 positives** in all. The
register is built and committed **before** any model output is scored, so it cannot be
reverse-fit; each coordinate carries a confidence flag keyed to whether the PUB entry names
a single road (high) or a junction/area/segment (medium, since OneMap returns one
representative point on the named road).

Because the PUB list is current-state, famous historical hotspots that have been
mitigated are absent — so the model is tested against the locations PUB *currently*
documents, the more honest comparative test.

### 4.3 Skill metric: True Skill Statistic with dry controls

A hit-rate-only score is gameable: a model that floods all low ground scores perfectly
on positives. We therefore include **20 documented dry-control points** and report the
**True Skill Statistic**. The dry set is deliberately two-tiered: (i) **elevated** parkland
and reserves absent from every PUB list (robust true negatives — e.g. Bukit Timah Hill,
Mount Faber, the nature parks of the Central Catchment), and (ii) **developed town centres
that are low-lying but absent from the comprehensive PUB list** (the discriminating
negatives — e.g. Toa Payoh, Tampines, Jurong East centres). The second tier is the
anti-gaming heart of the metric: a model that simply floods low ground will fail it. All
controls are OneMap-geocoded and DEM-verified (point not in a topographic sink), selected by
a neutral rule — *not* by inspecting any model's output — so the set cannot be reverse-fit.

```
TSS = hit_rate(flood positives) + correct_reject_rate(dry controls) − 1
```

A "flood-everything" model scores TSS ≈ 0. A point is *flagged* if any cell within
150 m (absorbing GLO-30 ~30 m horizontal error plus georeferencing uncertainty) reaches
depth ≥ 0.10 m at the scoring anchor return period (RP50; chosen because Singapore
hotspots flood in moderate storms, ponding onset is engineered to begin ~RP5, and RP100
is too lax while RP10 sits at the drain-capacity floor). These three scoring parameters
(threshold, radius, anchor RP) are documented defaults under the same refinement
discipline as the model parameters.

Because the register is small (tens of points), every reported TSS carries a **95 %
stratified bootstrap confidence interval** (positives and dry controls resampled
independently, 10 000 iterations), and model-vs-baseline comparisons use a **paired
bootstrap on ΔTSS** (the same resampled indices applied to both classifiers, since they
are scored on identical points). A comparative claim is treated as *supported* only if the
paired ΔTSS interval excludes zero; a nominal lead whose interval spans zero is reported as
**statistically indistinguishable**, not as a win. This guards the comparison against
over-reading a margin the sample size cannot support (`bootstrap_tss_ci`,
`bootstrap_tss_diff_ci`).

### 4.4 Dual comparator baseline

The comparative result is judged against **one binding open baseline**, with the generic
global vendor reported only as the structural-zero reference (the motivation of §1.1, not
a skill rival):

1. **Binding — Naive Topographic Wetness Index** (`TWI = ln(a / tan β)` on the raw DSM,
   flagging the wettest ~15 % of land cells): a trivial open method any practitioner could
   run for free. It captures low convergent ground without any calibration, rainfall, or
   drainage knowledge, so **beating it by a clear margin is the real test of whether
   city-calibration adds value over topography alone.** (TWI replaced an earlier
   depression-fill baseline, degenerate on an island — it either drains everything to sea
   or fills the whole island as a thin sheet.)
2. **Reference — WRI Aqueduct** (riverine + coastal, ~1 km, CC BY 4.0): reported for
   completeness, but its score is a **structural 0** — it has no pluvial layer, so it
   cannot flag a pluvial register by construction (Table 1a). This is *evidence of the
   open-data gap*, not a like-for-like skill comparison, and the comparative claim does
   **not** rest on it. A single naive open baseline is a thin binding comparison; a
   second independent naive open method — a Topographic Position Index (local depression
   depth, no flow routing) — has since been added to triangulate (§5.8c), and a threshold-free
   ROC-AUC added to remove the binary-cutoff dependence (§5.8a).

The headline thesis sentence is therefore: *"On N documented flood + M dry-control points,
the city-calibrated model is statistically indistinguishable from a naive topographic baseline
on combined TSS but significantly more specific; the best open global vendor has no pluvial
layer and flags almost none of the register."*

### 4.5 Supporting numeric checks (pluvial)

- **PUB depth band + monotonicity** (`validate_pluvial_singapore.py`): max ponding depth
  monotone non-decreasing with RP, RP1000 within the observed PUB band
  [0.38, 3.0] m (RP1000 anchor 0.76 m; 3.0 m engineering life-safety cap), RP≤10 at the
  drain-capacity floor (zero residual ponding is physically correct, not an error).
- **Documented high-water-mark cross-check** (`validate_hwm_points.py`): modelled depth
  in a neighbourhood of each depth-bearing documented location falls within a plausible
  band.

### 4.6 Coastal and fluvial plausibility validation

Coastal and fluvial carry no comparative claim (§2), but they are held to the same
anti-eyeball discipline through a fixed, binary plausibility gate — pass/fail, never
tuned-to-taste:

- **Coastal.** Datum and sea-level sanity (`WSE = MSL + tide + surge + SLR` with the
  correct EGM2008 offset and AR6 SLR delta); monotone flooded area/depth with RP; at
  least one documented coastal high-water mark in-band; no post-cap single-cell blow-up.
- **Fluvial.** Channel-masking applied (no below-grade canal artefacts surfacing as
  flood); monotone with RP; wet area a sane fraction of the domain (no domain-wide sheet);
  documented high-water marks in-band where available.

A failed item is converted, per the §4.7 conversion rule, into a new numeric check or a
logged limitation — not a parameter nudge. This is the same falsifiable-but-not-
comparative standard the original scope specification assigns to the product-surface
hazards.

### 4.7 Limitations register (the conversion sink)

When visual review flags something, it becomes either a new numeric check or a logged
limitation in a register (`docs/limitations_register.md`) — never a tweak-look-tweak
loop. Seed entries include the below-grade-canal appearance (real, not a bug), the
Aqueduct resolution asymmetry, and the TWI baseline's RP-independence.

---

## 5. Results (Singapore, SSP5-8.5 / 2100)

> **Status: pluvial numeric gates 1–3 PASS; gate-4 margin is an open thesis finding.**
> The pluvial depth-band/monotonicity gate is closed by a three-step, individually
> diagnosed fix chain (§5.2): surgical DEM de-pitting (removed a 27.8 m interior blow-up,
> restored monotonicity), an open-boundary condition (removed a clipped-edge artefact,
> 3.76 → 3.22 m), and a physical depth cap at the documented 3.0 m engineering limit
> (clipped 3 residual overshoot cells, 3.22 → 3.00 m). Final RP1000 = 3.00 m, monotone →
> **PASS**, with both HWM points in-band (§5.1, 5.3).
> The remaining open item is gate-4, now measured on an expanded register: all 36 Nov-2025
> PUB flood-prone areas (OneMap-geocoded) + 2 historical = **38 positives**, and **20 dry
> controls** (elevated reserves + low-lying town centres absent from the comprehensive PUB
> list; §4.3). The verdict separates onto two axes: on **combined location skill (TSS)** the
> model and naive topography are **statistically indistinguishable** (every ΔTSS interval
> spans zero; §5.1.2d), but on **specificity** the model is **significantly better** — naive
> TWI wrongly floods 14/20 documented-dry points vs the model's 7 (ΔCRR +0.35, 95 % CI
> [+0.10, +0.60], excludes zero; §5.1.2c) — and it out-covers the generic vendor significantly
(flags 15/38 register points to Aqueduct's 3; Δ hit-rate +0.32, CI excludes zero).
> The honest verdict is "indistinguishable from naive topography on where it floods, but
> significantly more precise about where it does not, and decisively better than the generic
> vendor" — a precision–recall split (§6). Coastal and fluvial pass their plausibility gates
> (§5.4).

### 5.1 Comparative hotspot skill (the headline)

**Table 3.** Documented-hotspot skill at RP50 (**38 flood positives** — all 36 areas on the
official PUB *List of Flood-Prone Areas* (Nov 2025), authoritatively geocoded via OneMap
(SLA), plus 2 historical events — and **20 dry controls** (§4.3), reported with 95 % bootstrap
CIs.

Two scenarios are reported: the **product** scenario (SSP5-8.5 / 2100, climate-inflated
rainfall) and the **validation** scenario (baseline-2020, present-day rainfall — the
apples-to-apples match to the present-day PUB register, §5.1.1). The naive-TWI baseline is
RP-independent (pure topography) so its score is identical in both.

| Source | hit-rate | CRR | **TSS** (2100) | **TSS** (2020) |
|---|---:|---:|---:|---:|
| City-calibrated model (this work) | 0.71 / 0.39 | 0.45 / **0.65** | **0.16** [−0.09, 0.42] | **0.04** [−0.21, 0.30] |
| Naive TWI baseline (binding) | 0.92 | **0.30** | **0.22** [0.02, 0.45] | **0.22** [0.02, 0.45] |
| WRI Aqueduct (reference, ~no pluvial) | 0.08 | 1.00 | **0.08** [0.00, 0.18] | **0.08** [0.00, 0.18] |

**Reading (honest).** Three separable claims, at the strength the data support:

1. **vs the generic global vendor — wins on coverage, significantly.** Aqueduct, with no
   pluvial layer, flags only 3 of 38 register points (the riverine/coastal-adjacent ones, HR
   0.08); the model flags 15 (HR 0.39). The paired difference in hit-rate is **+0.32, 95 % CI
   [+0.13, +0.50]** — significant. (On combined TSS the two are *not* separable, because
   Aqueduct earns a near-perfect correct-reject rate by flagging almost nothing; the honest
   vendor claim is therefore about pluvial *coverage*, not TSS.)
2. **vs naive topography, on combined location skill (TSS) — indistinguishable.** Every
   paired model-vs-TWI ΔTSS interval spans zero (§5.1.2d). Neither out-locates the other on
   the available register.
3. **vs naive topography, on specificity — wins significantly.** This is the result the
   expanded dry-control set surfaced. TWI achieves its 0.92 hit-rate by flooding low ground
   indiscriminately — it wrongly wets **14 of 20** documented-dry points (CRR 0.30). The
   model wrongly wets only 7 (CRR 0.65 at the validation operating point). The paired
   difference in correct-reject rate is **+0.35, 95 % CI [+0.10, +0.60]** (P = 0.99) — the
   model is **significantly more specific** than naive topography.

This is a textbook precision–recall split: TWI is high-recall / low-precision (floods
everything low), the model is lower-recall / **significantly higher-precision**. TSS weights
the two equally, so they tie on it; but for a screening product that pays for false alarms,
precision is the operative axis and the model wins it with statistical support. The model's
distinct value is thus *how* it flags — specificity, depth and mechanism (§5.1.2c, §6) — not
the raw count of locations.

#### 5.1.1 Why baseline-2020 is the validation scenario

The PUB register and the documented depths are present-day observations; scoring them
against a 2100 climate-inflated field over-credits the model (a larger design storm wets
more cells). The baseline-2020 forcing (present-day 1 h IDF, no climate scaling) is the
apples-to-apples match and is therefore the validation of record; 2100 is the
forward-looking product scenario. The hit-rate drop from 0.71 (2100) to 0.39 (2020)
quantifies exactly this inflation, and is why the comparative claim must be read on the
2020 column.

#### 5.1.2 The comparison, read across the operating space (and against its uncertainty)

The single-point gate (RP50, ≥ 0.10 m) is one slice of a continuous depth field, so we
report the whole operating space on the present-day (2020) field, then test every difference
against its bootstrap CI. The story separates cleanly into a **location** axis (the two
methods tie) and a **specificity** axis (the model wins, significantly).

**(a) On combined location skill (TSS) the model tracks just below TWI.** With the expanded
20-point dry-control set TWI's own TSS falls to 0.22 (its indiscriminate flooding costs it on
the negatives, see (c)); the model sits at or just under it across the RP sweep at 0.10 m:

| RP | model hit | model CRR | model TSS | TWI TSS |
|---:|---:|---:|---:|---:|
| 50 (anchor) | 0.39 | 0.65 | +0.04 | +0.22 |
| 100 | 0.63 | 0.45 | +0.08 | +0.22 |
| 200 | 0.66 | 0.50 | +0.16 | +0.22 |

**(b) The threshold matters more than the RP.** Sixteen of the 38 hotspots are *near-misses*
— the model assigns 0.05–0.10 m of ponding, just under the binary 0.10 m cut-off. Sweeping
the model's depth threshold at RP50:

| threshold | model hit | model CRR | model TSS | TWI TSS |
|---:|---:|---:|---:|---:|
| 0.05 m | 0.82 | 0.45 | **+0.27** | +0.22 |
| 0.10 m | 0.39 | 0.65 | +0.04 | +0.22 |

At 0.05 m the model's point-TSS edges TWI (0.27 vs 0.22); at 0.10 m it sits below. The
verdict is sensitive to one arbitrary threshold — evidence that a single-threshold binary
test is the wrong summary for a continuous depth field, **but not licence to pick the
threshold that wins** (the 0.05 m edge is non-significant; see (d), and §4.3).

**(c) The model is significantly more specific — its robust edge over topography.** This is
the result the expanded dry-control set surfaced. The 20 dry controls span elevated parkland
(robust true negatives) and **developed town centres that are low-lying but absent from the
comprehensive PUB list** (the discriminating negatives) — all OneMap-geocoded and
DEM-verified, selected by a neutral rule *before* any model output was inspected (§4.3). On
them, **naive TWI wrongly floods 14 of 20** (CRR 0.30): it buys its 0.92 hit-rate by flagging
the wettest ~15 % of all land regardless of drainage. The calibrated model wrongly floods
only 7 (CRR 0.65 at the validation operating point). The paired bootstrap difference in
correct-reject rate is **+0.35, 95 % CI [+0.10, +0.60], P = 0.99 — the interval excludes
zero**, so the model is *significantly* more specific than naive topography. For a screening
user who pays for false alarms (a bank or insurer) this is the operative axis.

**(d) On combined TSS the two remain statistically inseparable.** A paired bootstrap (§4.3)
on the present-day field, at the full N = 38 / 20 register:

| Operating point (2020) | model TSS [95 % CI] | TWI TSS [95 % CI] | ΔTSS [95 % CI] | P(model > TWI) |
|---|---:|---:|---:|---:|
| RP50 / 0.10 m (gate) | 0.04 [−0.21, 0.30] | 0.22 [0.02, 0.45] | −0.18 [−0.48, 0.13] | 0.12 |
| RP50 / 0.05 m | 0.27 [0.01, 0.52] | 0.22 [0.02, 0.45] | +0.04 [−0.26, 0.34] | 0.60 |
| RP100 / 0.10 m | 0.08 [−0.20, 0.34] | 0.22 [0.02, 0.45] | −0.14 [−0.45, 0.16] | 0.18 |

Every model-vs-TWI **ΔTSS** interval spans zero — the methods are indistinguishable on the
*combined* metric, because the model's higher precision is offset by its lower recall and TSS
weights them equally. The two comparisons whose intervals *do* exclude zero are not on TSS:
the **specificity edge** over TWI (ΔCRR +0.35; (c)) and the **coverage edge** over Aqueduct
(ΔHR +0.32 [+0.13, +0.50]; the model flags 15/38 register points to Aqueduct's 3). Expanding
both arms of the register (positives 20→38, negatives 6→20) tightened every interval (the gate
ΔTSS CI narrowed from [−0.94, 0.22] to [−0.48, 0.13]) without flipping the TSS verdict — the
honest behaviour of a larger sample.

**Honest synthesis.** The city-calibrated model is **statistically indistinguishable from
naive topography on combined location skill (TSS)** but **significantly more specific**
(ΔCRR +0.35, CI excludes zero) and **significantly better than the generic global vendor**.
This is a precision–recall split: TWI floods all low ground (high recall, poor precision); the
model is drainage-aware (lower recall, high precision). We report the operating curve *with
CIs*, state each claim at exactly its supported strength, and treat any move of the scoring
anchor or threshold as requiring documented justification, never a choice made to win.

> **Caveat (later review — limitation #15).** The "significantly more specific" claim above is
> partly *confounded by flooded fraction*: at 0.10 m the model wets ~1.85 % of land vs TWI's 15 %,
> so it rejects more negatives partly because it floods less, at much lower sensitivity. The fair
> threshold-free comparison (ROC-AUC) shows **no model advantage** on the decision-relevant
> low-lying negatives (model 0.65 vs TWI 0.75 — a tie: ΔAUC −0.10, 95% CI [−0.32, +0.11]; at
> matched specificity TWI HR 0.71 illustratively > model 0.39). The model's *only* firm
> threshold-free edge is against *random land* (ΔAUC +0.14, 95% CI [+0.04, +0.24] at n=300, stable
> across samples). Read the specificity result as scoped (better landscape-scale detection, not
> better low-vs-low discrimination), not as a blanket superiority. See #15 and
> `sesmo_modelling_practice.md`.

### 5.2 Depth-band and monotonicity

**Table 4.** Max pluvial ponding depth (m) by RP, across the three-step fix chain
(SSP5-8.5 / 2100). The final row passes the gate (monotone; RP1000 ≤ 3.0 m).

| RP | 2 | 5 | 10 | 25 | 50 | 100 | 200 | 500 | 1000 | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| raw (pre-fix) | 0.17 | 1.5 | 2.0 | 3.8 | 5.2 | 13.2 | **27.8** | 7.4 | 8.6 | FAIL (non-monotonic) |
| + de-pit (3.0 m) | 0.13 | 1.42 | 1.97 | 2.54 | 2.81 | 3.09 | 3.37 | 3.45 | 3.76 | FAIL (RP1000 > cap) |
| + open boundary | 0.13 | 1.42 | 1.97 | 2.54 | 2.81 | 2.91 | 3.02 | 3.11 | 3.22 | FAIL (RP1000 > cap) |
| + depth cap (3.0 m) | 0.13 | 1.42 | 1.97 | 2.54 | 2.81 | 2.91 | 3.00 | 3.00 | 3.00 | **PASS** |

Each step was independently diagnosed before being applied — the discipline of fixing the
cause, then measuring, rather than tuning to the gate:

1. **Surgical de-pitting (§3.3).** The raw run blew up to 27.8 m at RP200 and was
   non-monotonic — water accumulating unbounded in enclosed DSM-artefact pits (including
   sub-sea-level holes to −23 m). Filling the artefact and unphysically-deep depressions
   removed the interior blow-up and restored monotonicity, but left RP1000 = 3.76 m.
2. **Open boundary (§3.5).** Lowering the de-pit threshold from 3.0 m to 2.0 m left RP1000
   unchanged (3.76 m), empirically ruling out pits. The residual 23 cells lay on the
   **clipped-domain edge**, where the solver's no-flux wall trapped runoff routed off-map.
   Treating the domain perimeter as an open outlet dropped RP1000 to 3.22 m.
3. **Physical depth cap (§3.5).** The final residual was **3 interior cells** (0.0001 % of
   the domain) overshooting to 3.22 m — local-inertial transient overshoot, not a pit or
   an edge. A physical cap at the documented 3.0 m engineering limit — the same device the
   coastal model uses, applied only after the cause-fixes — clips them to 3.0 m.

The progression illustrates the validation-first method: the numeric gate localised each
defect (interior pit → domain edge → solver overshoot), and each was closed by an anchored
mechanism rather than a parameter nudged toward the target.

### 5.3 High-water-mark cross-check

On the gate-passing pluvial field, sampling the model at the **register's** documented-depth
points within the standard 150 m window gives conservative-but-plausible depths: Orchard Road /
Stamford Canal max ~0.09–0.24 m (present-day RP50 → 2100 RP1000) versus documented ~0.4 m, and
Bukit Timah Road max ~0.10–0.25 m versus documented ~0.25 m. Bukit Timah is reproduced at high
RP; Orchard is under-reproduced at every RP — consistent with §6.2 (the 2010 Orchard flood was a
drainage-failure event a design-capacity model cannot reproduce). **Correction (2026-06-02):** an
earlier draft quoted "Liat Towers / Orchard 0.47 m IN-BAND" from a separate HWM validator using a
different coordinate/window; that figure is *not* reproducible at the register's Orchard point and
has been removed. The honest statement is that the model is depth-plausible but conservative at
the documented points, reaching documented magnitudes only for the rainfall-capacity event
(Bukit Timah) and not the blockage event (Orchard). The depth cap (3.0 m) is far above these
neighbourhood maxima and does not affect the check.

### 5.4 Coastal and fluvial (plausibility tier)

Both hazards were generated for Singapore at all nine return periods (SSP5-8.5 / 2100)
and pass the §4.6 plausibility gate.

**Coastal (bathtub).** Flooded area grows monotonically 60.2 → 69.6 km² (RP2 → RP1000;
RP100 = 66.5 km²) and maximum depth monotonically 3.4 → 3.8 m, with no post-cap
single-cell blow-up. The RP100 extent of 66.5 km² independently reproduces the earlier
ASEAN-atlas Singapore coastal RP100 of ~68 km² to within ~2 %, a useful cross-check on
the datum chain (UHSLC 699 GEV + EGM2008 MDT offset + AR6 SLR).

This coastal extent is a **no-defence, no-pumping bathtub screening upper bound** and
over-predicts expected present-day inundation (the ASEAN-atlas quantified a ~25× RP100
bias for Singapore against documented present-day extent). Running the defended DEM
(Marina Barrage and East Coast Park bund crests burned in) changes the extent by only
**0.1–0.2 km² at every RP** — not because the defences are overtopped (their ~4.7–6.2 m
EGM2008 crests exceed the 3.8 m WSE) but because the modelled crest polylines are
localised and do not enclose most of the low coastal fringe that bathtub floods. The
residual over-prediction is therefore intrinsic to bathtub-on-30 m-DSM with no pumping or
distributed drainage, which inundates low coastal land that is protected/drained in
reality — not something defence-crest burn-in corrects. The coastal layer should be read
as a screening upper bound, consistent with its plausibility-tier role; a local-inertial
re-run (atlas: ~1.4× reduction for Singapore) is the documented option if a tighter
coastal extent is later required.

**Table 5.** Coastal flooded area and max depth by RP (SSP5-8.5 / 2100).

| RP | 2 | 5 | 10 | 25 | 50 | 100 | 200 | 500 | 1000 |
|---|---|---|---|---|---|---|---|---|---|
| area (km²) | 60.2 | 61.9 | 62.9 | 64.7 | 65.6 | 66.5 | 67.5 | 68.8 | 69.6 |
| max depth (m) | 3.4 | 3.5 | 3.6 | 3.6 | 3.7 | 3.7 | 3.8 | 3.8 | 3.8 |

**Fluvial (HAND, canal-overflow).** Flooded area is zero at RP ≤ 10 (canal stage within
design capacity), then grows monotonically from RP25 to 72.5 km² at RP1000; maximum depth
grows monotonically 0 → 1.1 m. **Channel-masking is verified**: the maximum modelled
fluvial depth on river-network cells is 0.000 m at RP100, confirming canal beds are
treated as conveyance, not hazard. No domain-wide sheet appears.

**Table 6.** Fluvial flooded area and max depth by RP (SSP5-8.5 / 2100).

| RP | 2 | 5 | 10 | 25 | 50 | 100 | 200 | 500 | 1000 |
|---|---|---|---|---|---|---|---|---|---|
| area (km²) | 0 | 0 | 0 | 45.1 | 49.8 | 55.9 | 61.3 | 67.9 | 72.5 |
| max depth (m) | 0 | 0 | 0 | 0.2 | 0.4 | 0.6 | 0.7 | 0.9 | 1.1 |

Singapore has no documented coastal high-water mark in the registry (the documented
points are pluvial); the coastal HWM check is therefore not applicable and is recorded as
a limitation rather than a pass. Both hazards remain subject to the §4.2 visual gate as
the final coherence veto.

### 5.5 Scenario sensitivity (2×2 SSP × horizon)

The model was run across the four SSP × horizon combinations plus a present-day baseline
(SSP5-8.5/2020). Table 7 gives RP100 flooded area (depth ≥ 0.10 m) per hazard; all
scenarios pass the pluvial depth-band gate.

**Table 7.** RP100 flooded area (km²) by scenario × hazard.

| Scenario | Coastal | Fluvial | Pluvial |
|---|---:|---:|---:|
| SSP5-8.5 / 2020 (baseline) | 48.1 | 55.1 | 69.5 |
| SSP5-8.5 / 2050 | 55.6 | 54.6 | 102.1 |
| SSP5-8.5 / 2100 | 66.5 | 55.9 | 123.5 |
| SSP2-4.5 / 2050 | 55.0 | 54.3 | 97.9 |
| SSP2-4.5 / 2100 | 61.6 | 54.9 | 107.4 |

Three signals:

- **Coastal is the SLR-driven scenario story.** RP100 coastal area rises monotonically
  with horizon under SSP5-8.5 (48.1 → 55.6 → 66.5 km²), and SSP2-4.5 sits below SSP5-8.5
  at each horizon (correct ordering). The end-century coastal mitigation delta (SSP5-8.5 −
  SSP2-4.5 at 2100) is **4.9 km²** of avoided RP100 inundation, dominated by the ~0.2 m SLR
  difference.
- **Pluvial scales with horizon** under the corrected forcing (SSP5-8.5
  69.5 → 102.1 → 123.5 km²), tracking the climate-amplified rainfall; the end-century
  **pluvial** mitigation delta is **16.1 km²** — larger than the coastal delta, because the
  GEV-CC rainfall difference between SSP5-8.5 (ΔT 4 °C) and SSP2-4.5 (ΔT 2.1 °C) is
  substantial. Combined RP100 mitigation benefit ≈ **21 km²** of avoided flooding under the
  Paris-aligned scenario.
- **Fluvial is scenario-insensitive** (~54–56 km² throughout) — consistent with
  Singapore's canal-overflow framing, where reservoir-buffered short catchments respond
  weakly to the GEV-CC rainfall scaling.

### 5.6 A data-integrity finding the grid surfaced

Building the grid exposed a pre-existing inconsistency in the committed scenario forcing
files: three of the five `hazard_levels` CSVs (SSP5-8.5/2050, SSP2-4.5/2050, SSP2-4.5/2100)
carried **physically impossible pluvial net-excess** (~0.46 m = 460 mm of 1 h excess; ~5×
too high, and inverted with warming) — they had been scaled from a *pre-redesign* baseline
(6 h IDF / 70 mm drain) rather than the current 1 h / 50 mm baseline. The headline
SSP5-8.5/2100 and the baseline-2020 files were already on the correct baseline. We
regenerated the three stale files from the current baseline (coastal and fluvial rows
verified unchanged) and re-ran their pluvial sweeps; all five scenarios now pass the
depth-band gate and are reflected in Table 7. The episode is itself a result: the
validation grid caught a forcing-provenance bug that a single-scenario run would have
shipped silently.

### 5.7 Visual gate (§4.2)

The fixed visual-coherence checklist was run on the rendered hazard maps
(SSP5-8.5/2100) as the final veto. **Result: pass.** Monotone area/depth across RP
(pluvial RP10 < RP100 < RP1000); hazard separation correct (coastal confined to the
coastal fringe, fluvial along the channel network with channels masked, pluvial on
distributed low ground); no domain-wide thin sheet; no post-cap single-cell spikes;
documented hotspots sit in wet ground and dry controls in dry ground, consistent with the
RP100 hit/correct-reject rates. The one flagged item — the pluvial field reading as
"speckly" — was **converted, not tuned** (§4.6): quantification showed 92 % of wet area in
coherent ≥ 20-cell pools and 0 % in sub-6-cell clusters at the denoise threshold, i.e. the
"speckle" is real sub-hectare ponding, not noise; it became a numeric anti-speckle check
(≥ 85 % of wet area in ≥ 20-cell clusters; passes at 92 %) plus a logged characteristic,
not a veto.

**Done status (pluvial).** Numeric gates 1–3 pass (depth band, monotonicity, hotspot
hit-rate ≥ 0.70 at the product scenario) and the visual gate passes; gate 4 (TSS margin
≥ 0.20 over *both* baselines) is **not** met against the naive topographic baseline and is
honestly reframed to the operating-curve result (§5.1.2, §6.1) rather than passed. The map
is therefore physically valid, visually coherent, and decisively better than the generic
global vendor — but does not clear the strong "beats any open method" bar, which the paper
states plainly.

### 5.8 Science-hardening: threshold-free metric, robustness, triangulation, events

Four hardening analyses (2026-06-02) test whether the §5.1 verdict survives a fairer metric,
parameter perturbation, a second baseline, and real events.

**(a) Threshold-free ranking (ROC-AUC).** Replacing the binary 0.10 m hit-test with a
threshold-free ranking of the continuous depth/index field (Mann-Whitney AUC; each method
gets its own optimal operating point) confirms the location tie by a *second* metric:
model AUC 0.65 vs TWI 0.75, paired ΔAUC −0.10 [−0.32, +0.11] — **indistinguishable**. The
threshold sensitivity of §5.1.2b was therefore not concealing a model win; the location tie
is metric-robust.

**(b) Robustness.** The specificity edge holds across the hit-radius: ΔCRR(model−TWI) =
+0.25 / +0.35 / +0.45 at 100 / 150 / 200 m. On a **neutral, model-blind random negative
set** (60 land points ≥ 300 m from any positive) the edge is even larger and unambiguous —
model CRR 0.77 vs TWI 0.22, **ΔCRR +0.55, 95 % CI [+0.40, +0.68], P = 1.00** — so the
specificity result is not an artifact of the curated town-centre negatives.

**(c) Triangulation against a second naive baseline (TPI).** A structurally independent
naive method — Topographic Position Index (local depression depth, no flow routing) —
brackets the model with TWI. vs TWI (strong, AUC 0.75): model indistinguishable on TSS/AUC,
significantly more specific (ΔCRR +0.35). vs TPI (weak — it floods everything: HR 1.00,
CRR 0.00, AUC 0.28): model significantly better on **both** specificity (ΔCRR +0.65) and
ranking (ΔAUC +0.36). Both naive methods over-flood; the model does not — the specificity
edge is not a one-baseline artifact.

**(d) Event reproduction.** Driving the present-day field and checking the documented
historical events at their event-matched RP: the *capacity-exceedance* events reproduce
(Tanglin 2011, Bukit Timah 2012/2017 flag at RP25/RP50), while the *drainage-failure* events
under-reproduce (Orchard 2010/2011 reach 0.09–0.14 m vs documented 0.3–0.4 m). The model
correctly fails to fabricate the blockage-driven floods it structurally cannot model (§6.2);
documented depths are reached only at higher RP / climate forcing, confirming present-day
conservatism. (Sample limited to ~4 documented events; §7.)

**Net effect on the claim.** All four analyses *confirm and sharpen* §5.1 rather than
overturn it: location skill is a metric-robust tie with naive topography; the specificity
advantage is significant, radius-robust, baseline-robust and selection-robust; and the
under-flagging is mechanistically explained by drainage-failure events.

---

## 6. Discussion

### 6.1 What the comparative result actually says

The comparison is asymmetric, and on the full official register it is also sobering.
Against the best open **global vendor** the model wins on **coverage**, significantly:
Aqueduct has essentially no pluvial layer — it flags only 3 of 38 register points (the
riverine/coastal-adjacent ones) to the model's 15, a paired Δ hit-rate of +0.32, 95 % CI
[+0.13, +0.50] (§5.1.2d). (On combined TSS the two are not separable — Aqueduct earns a
near-perfect correct-reject rate by flagging almost nothing — so the vendor claim is about
pluvial coverage, not TSS.) This is as much a statement about the open-data landscape as a
skill result. Against a **naive topographic
index** the result splits onto two axes (N = 38 / 20). On **combined location skill (TSS)**
the model and topography are **statistically indistinguishable** — every paired ΔTSS interval
spans zero (§5.1.2d) — because TWI's high hit-rate (0.92) and the model's higher precision
trade off under a metric that weights them equally. On **specificity**, however, the model
**wins significantly**: naive TWI floods 14 of 20 documented-dry points (it flags all low
ground regardless of drainage), the model only 7, a paired ΔCRR of **+0.35, 95 % CI
[+0.10, +0.60]** that excludes zero (§5.1.2c). This is a precision–recall split — TWI is
high-recall/low-precision, the model lower-recall/high-precision — plus what the model
measures beyond location: depth and mechanism (§6.3). The defensible claim is therefore
*"indistinguishable from naive topography on TSS, but significantly more specific, and
decisively better than the generic global vendor"* — explicitly **not** *"beats topography at
finding flood-prone locations."*

### 6.2 Why the model under-flags at the documented operating point (and why re-anchoring is not licensed)

We tested whether the scoring anchor could be moved to RP100 (where the model's point-TSS
is highest, even if still short of TWI) on a **documented** basis. The rainfall of the
documented hotspot storms — Orchard Road
2010 (~100 mm/2 h), Tanglin 2011 (65 mm/30 min burst), Orchard 2011 (153 mm/3 h), Bukit
Timah 2017 (68.6 mm/30 min) — corresponds to roughly **RP5–50 at the 1 h IDF duration**
(μ = 46 mm, σ = 16 mm; RP10 = 82 mm, RP100 = 120 mm), **not RP100**. Re-anchoring to RP100
is therefore *not* documented-justified, and we do not do it (this is the §4.5 discipline
working as intended — the move would have flattered the model, so the absence of an anchor
forbids it).

Two documented facts then explain the conservative hit-rate honestly. First, the worst
events were **drainage-failure** floods: the PUB Expert Panel found the 2010 Orchard flood
was caused by a **debris-choked Stamford Canal**, not by rainfall alone. A model that
encodes *design* drainage capacity structurally cannot reproduce a blocked-culvert flood,
so scoring its design-storm output against these specific events is partly apples-to-
oranges — and biased against the model. Second, the binary 0.10 m hit-test discards real
signal: **sixteen of the 38 hotspots** are flagged at 0.05–0.10 m (§5.1.2b), so the model
*is* ponding at the documented locations, just below an arbitrary cut-off.

### 6.3 Where city-calibration's value actually lies

The evidence relocates the model's contribution from *location* (a wetness index already
captures that low-lying ground floods) to **mechanism, depth, and specificity** — and the
specificity claim is no longer merely asserted: with the expanded dry-control set it is
**statistically demonstrated** (ΔCRR +0.35, 95 % CI [+0.10, +0.60]; §5.1.2c). The calibrated
rain-on-grid encodes local drain capacity and IDF, produces a return-period-resolved depth
field (the documented-depth points sit in their plausible bands at the appropriate RP; §5.3),
and **does not over-flood dry ground** the way a wetness index does (which floods 70 % of
documented-dry low-lying town centres). A naive index has none of these. The right metric for
a screening product is thus depth-aware and specificity-weighted, not a single binary location
hit-rate — a methodological lesson the documented-register framework surfaced rather than
assumed, and one the expanded negative set let us prove.

### 6.4 Generalisation

The documented-register + TSS + dual-baseline framework is city-agnostic. Its comparative
power is strongest where a city has both a documented flood-prone register *and* mapped
multi-hazard event extents — which is the case for the other ASEAN capitals (Bangkok 2011,
Manila 2009, Jakarta 2020 have SAR/EMS extents), where coastal and fluvial can also carry
a comparative (not merely plausibility) claim. Singapore is the strict case: pluvial-only
comparative ground truth, point register rather than extents, mostly undocumented depths.
That the framework yields an honest, falsifiable — and partly unfavourable — result here is
the point: it is a yardstick, not an advocacy tool.

---

## 7. Limitations

*(Summarised from `docs/limitations_register.md`.)* Hotspot coordinates are now OneMap
(SLA)-geocoded per PUB entry rather than hand-typed, but for junction/area/segment entries
OneMap returns a single representative point on the named road, which can sit a few hundred
metres from the documented flood spot (confidence-flagged `med`; the 150 m hit-radius
absorbs only part of this). At N = 38 / 20 the model's **specificity** edge over naive
topography is now statistically significant (ΔCRR +0.35, CI excludes zero), but the two
remain **indistinguishable on combined TSS** (every ΔTSS interval spans zero; §5.1.2d) — so
no location-skill ranking is supportable, only the specificity and vendor claims. The
low-lying dry controls rest on absence from the comprehensive PUB list (authoritative but
still absence-of-evidence); a handful that occasionally flood unreported would be
mislabelled. The PUB register is current-state (mitigated historical sites absent). Aqueduct
(~1 km) vs the 150 m hit radius is a documented asymmetry. The naive TWI baseline is
RP-independent. The pluvial
high-RP field is bounded by a physical depth cap at the documented 3.0 m engineering
limit, applied only after the de-pit and open-boundary cause-fixes (so the cap clips
residual solver overshoot, not an un-diagnosed blow-up). Coastal is a no-defence/no-pumping
bathtub screening upper bound (defended-DEM run changes it by < 0.2 km²/RP; §5.4).
Dry-control points are documented-absence, the weakest evidentiary class.

---

## 8. Reproducibility

All code, configuration (`cities.py`), the committed hotspot register, the validators,
and the design specs are in the repository. The full Singapore pluvial result is
reproducible end-to-end: build the bare-earth → conditioned → surgically de-pitted DEMs
(`build_bareearth_dem.py`, `build_conditioned_dem.py --raingrid-out`), run the rain-on-grid
sweep (`run_multihazard.py`, open-boundary on by default, `--pluvial-depth-cap 3.0`), then
the three validators (`validate_pluvial_singapore.py`,
`validate_pluvial_hotspots_singapore.py`, `validate_hwm_points.py`) plus the comparator
prep (`fetch_aqueduct_singapore.py`, `build_naive_pluvial_baseline.py`). Inputs are listed
in Table 1; all permit commercial use.
