<!-- ============================================================================
DRAFT-STATUS  (machine-readable progress marker; the 3am resume task lapsed — maintained manually)
STATUS: complete on equations/parameters; §11.4 now carries an explicit PROVENANCE CLASS for
        every parameter (LITERATURE / STANDARD / MEASURED / PHYSICAL-NUMERICAL /
        SCREENING CHOICE / GATE-SELECTED) so every assumption states its source or says
        plainly that it has none. §6.3.5 REWRITTEN 2026-07-13 as the two gate-arbitrated
        decisions (Stage 1 fillspill-vs-handfill base; Stage 2 canal-HAND retrofit with its
        equations, the 4-city assessment, the selection rule, and the shipped per-city
        configuration + current gate). CLOSED 2026-07-13: the Stage-2 post-processes are now
        folded into repro/run_atlas_fixed.sh (canal-HAND → bridge-closing → summary/severity
        regen), so driver, outputs, and this document describe one configuration.
LAST-UPDATED: 2026-07-19 +08:00 (compiled a full cross-document reference ledger [KSE/SAFE/
        model-doc] and, from what it surfaced: fixed the ADB report's citation year in both
        papers, 2022->2023, matching the report's actual publication date; added the [R17]/
        [R28]/[R29] in-text brackets that were missing next to their own discussion in the
        body -- Copernicus DEM §4.1, DeltaDTM §4, Chao Phraya §7.4/§10 -- so §12's numbering
        and the in-text citations no longer disagree; resolved R28's stale [verify] flag with
        a confirmed DOI. See 2026-07-17 entry below for the prior review.)
LAST-UPDATED (previous): 2026-07-17 +08:00 (full accuracy review vs code: §7.4 gate table
        re-baselined to the shipped post-retrofit atlas (3 PASS, not 2); §8 extents re-measured
        from the shipped rasters and the Table-2 quote corrected to the actual paper values;
        R7/R8 duplicate reference numbers fixed, orphaned T_TIDE entry removed; §10.3 dangling
        refs fixed; handfill stage-scaling documented as SHIPPED and the driver's Stage-1
        lines given --pluvial-hand-stage-baseline so a clean rebuild reproduces it)
STYLE: EXPANSIVE. Capture the MATHEMATICS (governing equations, discretisations,
       derivations) AND the implementation methodology, with explicit head-to-head
       method comparisons. Section 6 is the depth target to match: it gives full
       equations for the inertial scheme, HAND mapping, and the fill-spill cascade,
       plus inertial-vs-bathtub, HAND-vs-alternatives, handfill-vs-fillspill. Bring
       Sections 4, 5, 7 up to that same mathematical standard.
OWNER-NOTE: detailed technical documentation for the flood-v4.0 multi-hazard model.
SECTIONS:
   1. Overview & scope ........................ DONE
   2. System architecture & pipeline .......... DONE
   3. Input data & licensing .................. DONE
   4. Terrain: bare-earth DEM construction .... DONE (§4.1 error model Eq, (b0,f)
        calibration, sea-mask/HAND — variables + rationale + references)
   5. Forcing & climate scenarios ............. DONE (§5.1–5.4 GEV surge, Manning
        stage, two-anchor Gumbel IDF, uniform-CC scaling — variables + refs)
   6. Hazard models ........................... DONE (EXPANSIVE — math + 3 comparisons)
   7. Validation: model-blind hotspot gate .... DONE (EXPANSIVE — hit test, HR/CRR/TSS,
        percentile bootstrap; BCa→percentile reconciled in the paper 2026-06-22)
   8. Outputs & atlas structure ............... DONE (extents filled 2026-06-23)
   9. Reproducibility ......................... DONE (CLI verified)
  10. Limitations & known issues ............. DONE
  11. Appendices ............................. DONE (+ §11.4 parameter register:
        every solver/gate constant with rationale + reference)
  12. References ............................. DONE (R1–R29; tool cites marked [verify])
NEXT: ONLY Section 8 remains — fill every "[pending rebuild]"/"[verify]" extent with
      the real km² from outputs/_fixed_atlas/*_ssp585_2020_rp100/summary_*.csv
      (Bangkok via its _polder sibling) once Jakarta + Bangkok finish; then set
      Section 8 to DONE and STATUS: complete.
SOURCES (authoritative, in priority order):
  - docs/paper/safe2026-v5.tex          (full manuscript — the canonical description)
  - docs/paper/safe2026-abstract.tex    (distilled, current gate table)
  - repro/run_atlas_fixed.sh            (exact per-city CLI parameters)
  - scripts/run_multihazard.py          (solver implementation + CLI)
  - scripts/validate_hotspots.py        (the gate)
  - scripts/_fix_*.py                    (DEM/sea-mask/HAND construction)
  - CLAUDE.md + the auto-memory index    (project conventions, the plausibility fixes)
============================================================================ -->

# Flood-v4.0 — Multi-Hazard Flood Screen: Technical Documentation

> Open, validated, 30 m coastal + fluvial + pluvial design-event flood-depth model
> for four Southeast Asian cities (Singapore, Kuala Lumpur, Bangkok, Jakarta),
> present-day and four climate scenarios. This document describes the model as
> implemented; the companion manuscript (`docs/paper/safe2026-v5.tex`) gives the
> scientific framing and results.
>
> **New to flood modelling?** Start with the **plain-language glossary in §11.2** — it
> defines every term used here (coastal/fluvial/pluvial, bathtub vs inertial, HAND, return
> period, the trust scores, …) in everyday language. The parameter register in §11.4 opens
> with a plain-language reading guide, and each parameter group there starts with an *"in
> plain terms"* line, so a non-specialist can follow what every setting does without reading
> the equations.

---

## 1. Overview & scope

> **In plain terms.** This document describes a computer model that draws flood maps. For each
> 30-metre square of ground in four cities it answers one question — *how deep would the water
> be?* — and it answers it three times over: once for the sea coming inland, once for rivers
> overflowing, and once for rain falling faster than the drains can take it. It then keeps the
> worst of the three. It repeats all of that for several severities of event and for two
> future climate pathways. Everything it uses is free and public, so anyone can rebuild it and
> check the answer — which is the point.

**Purpose.** Produce a license-clean, third-party-reproducible screen of physical
flood hazard at a resolution (30 m) and hazard coverage (three perils) that no
*open* product currently offers for these cities, so that exposure can be
screened, priced, and disclosed by agencies that cannot license a commercial
surface.

**Coverage.**
- **Cities:** Singapore, Kuala Lumpur (+ Port Klang), Bangkok, Jakarta.
- **Hazards:** coastal (tide + surge + sea-level rise), fluvial (river), pluvial
  (rain-driven / drainage-overwhelm).
- **Resolution:** 30 m, on a per-city UTM grid.
- **Return periods (RP):** 10, 100, 1000 year design events.
- **Scenarios:** present day (treated as SSP5-8.5 / 2020) plus four forward
  combinations — SSP2-4.5 and SSP5-8.5 × 2050 and 2100.
- **Primary output:** per-hazard flood **depth** (metres) rasters + a per-pixel
  **combined** (max-of-hazards) layer + a **compound** joint-exceedance layer.

**Design philosophy.** Every input is free and openly licensed; terrain is the
dominant residual bias so the sole flood surface is an openly-constructed
bare-earth DEM; and trust is established not by reproducibility alone but by a
**pre-registered, model-blind location-skill gate** that scores documented
flooded/dry localities under a discipline that forbids re-tuning.

**Method principle — regime-matching, not one-size-fits-all.** Solvers and
referencing are matched to each city's physical flood regime rather than applied
uniformly (see §6). The clearest example: the pluvial layer uses *fill-spill*
(depression storage) on depression-dominated terrain and a HAND-based *handfill*
(near-drainage rain pooling) on canal-dense cities — the choice is made on
terrain physics, and adopting the wrong one measurably degrades the validation
gate (documented in §6.3 and §10).

---

## 2. System architecture & pipeline

Data flow, left to right:

```
  free inputs ──► terrain build ──► forcing build ──► hazard solvers ──► validation ──► atlas
  (DEM, ERA5,      (bare-earth      (design events:    (coastal/         (model-blind    (depth +
   GloFAS, AR6,     DEM + sea-mask   RP × scenario      fluvial/           hotspot gate,   combined +
   WorldCover,      + HAND + defence  hazard_levels     pluvial, per-      HR/CRR/TSS)     compound
   IDF)             crests)           CSVs)             city config)                       rasters)
```

**Repositories / directory layout (working tree `D:\GPTs\Projects\flood-v4.0`):**
- `dem/` — flood terrain. `dem/<city>/` per-city conditioned bare-earth DEMs;
  `dem/_hand/` derived Height-Above-Nearest-Drainage rasters; `dem/_diag/`
  derived diagnostics including the seawall-raised DEMs. *Derived rasters under
  `dem/_hand`, `dem/_diag`, and `sea_mask_*_framefix` are git-ignored and
  regenerated by committed scripts.*
- `data/<city>/` — per-city forcing (`hazard_levels_<scenario>_rp<rp>.csv`),
  sea-masks, river/drainage masks, runoff-coefficient rasters, and the validation
  `manifest/` (hotspot registers).
- `scripts/` — the model (`run_multihazard.py`), the gate (`validate_hotspots.py`),
  the terrain/sea-mask/HAND/defence construction (`_fix_*.py`,
  `apply_pumped_polder.py`), and visualisation (`_viz_*.py`).
- `repro/` — resumable end-to-end drivers (`run_atlas_fixed.sh`,
  `run_fixed_coastal_rp100.sh`).
- `outputs/` — model outputs (see §8).
- `docs/` — this documentation, the paper, and the limitations register.

**Two-interpreter rule.** The flood model runs under a dedicated Python 3.14
interpreter (`C:/Users/Daniel/AppData/Local/Python/pythoncore-3.14-64/python.exe`),
kept separate from the geospatial-preprocessing environment. All `scripts/` and
`repro/` calls invoke that interpreter explicitly.

---

## 3. Input data & licensing

All inputs are free to use and redistribute, which is what makes the atlas
license-clean and rebuildable from scratch by a third party.

| Input | Role | Source / licence |
|---|---|---|
| Copernicus GLO-30 DEM | base elevation surface (pre-correction) | ESA, free |
| ICESat-2 (ATL08) + GEDI L2A | lidar ground truth for DEM calibration | NASA, open |
| ERA5-Land | meteorological reanalysis (rainfall context) | Copernicus C3S, free |
| GloFAS | fluvial discharge / river return levels | Copernicus EMS, free |
| IPCC AR6 sea-level projections | scenario sea-level rise by SSP × horizon | IPCC, open |
| ESA WorldCover | land-cover → runoff coefficient / impervious raster | ESA, CC-BY |
| National IDF standards | design rainfall the pluvial layer is anchored to | each national met service |

**Why national IDF matters.** Global-synthetic design rainfall under-states the
four national Intensity–Duration–Frequency standards by a large margin (a
~28–62 % deficit), so the pluvial forcing is anchored to each country's published
IDF rather than to a global product. This is the single most important reason the
pluvial layer is credible here.

---

## 4. Terrain: bare-earth DEM construction

> **In plain terms.** Water runs downhill, so the ground-height map is the single most
> important input. The problem: satellites measure the height of whatever they see from
> above, which over a city means rooftops and treetops, not the ground. Buildings therefore
> look like dry hills, and streets that really flood get hidden underneath them. This section
> is how we strip the buildings and trees off to recover the real ground level, and how we
> check the result against laser height measurements taken from two space missions. We do the
> stripping separately for each city and never reuse one city's settings on another.

**Rationale.** Terrain is the dominant residual bias in a flood screen, and the
raw Copernicus surface includes buildings and canopy. Existing bare-earth products
either carry a non-commercial licence or are too coarse, so the model builds its
own.

**Method.** The Copernicus surface is corrected to ground by a **per-city
building-and-canopy error model** calibrated against *held-out* ICESat-2 and GEDI
lidar, roughly halving terrain error while remaining license-clean. The corrected,
hydrologically-conditioned DEM is the sole flood surface.

#### 4.1 The error model

The Copernicus GLO-30 surface `z_DSM` [R17] over-states ground by the building and canopy it
contains:

```
 z_DSM(x,y)  ≈  z_ground(x,y)  +  h_building(x,y)  +  f · h_canopy(x,y)
```

`z_ground` (the wanted bare-earth) is recovered by subtracting the two bias terms and a
flat offset. **Variables, with rationale and reference:**

| Symbol | Meaning | Value / source | Rationale | Reference |
|---|---|---|---|---|
| `h_building` | fractional-coverage building height | Google Open Buildings | per-pixel building bias; masked + back-filled from true-ground neighbours | Sirko et al. 2021 [R13] |
| `h_canopy` | canopy height (10 m) | ETH global CHM | the vegetation bias term | Lang et al. 2023 [R12] |
| `f` | canopy-penetration coefficient ∈ [0,1] | fit per city; **0.07–0.29** | radar partially penetrates canopy, so only a fraction of `h_canopy` is bias; fitted not assumed | this work |
| `b0` | flat true-ground offset | fit per city; **+0.24 … +1.46 m** | residual datum/systematic offset after the two bias terms | this work |
| datum | vertical reference | **EGM2008** | the GLO-30 native datum; all WSEs/MSL offsets share it | — |
| subsidence δ | per-city present-day subsidence | published InSAR rates | applied to the present-day surface; projected-subsidence reported separately | Chaussard 2013, Abidin 2011, Phien-wej 2006 [R20–22] |

**Calibration.** The two free parameters `(b0, f)` are fit **per city** against held-out
**ICESat-2 ATL08** [R14] and **GEDI L2A** [R15] spaceborne-lidar ground returns, and are
**never transferred between cities** — the discipline that makes "one method, four cities"
honest rather than four bespoke tunings. Against held-out lidar the bare-earth roughly
halves mean-absolute terrain error and removes the high bias (Bangkok MAE 1.43→0.78 m,
bias +1.00→−0.14 m). The fit is product-invariant: re-deriving KL on a second canopy model
moves `b0` by 3 mm. Rationale for *not* using FABDEM [R11] (the standard open bare-earth):
its non-commercial licence cannot back an openly-redistributable atlas.

**Per-city specialisation.**
- **Bangkok / Jakarta / Kuala Lumpur:** the building-and-canopy error model is
  fit and applied directly; the result is the `_conditioned` / `_debiased` DEM.
- **Singapore (hybrid).** Spaceborne-lidar ground truth over dense, reclaimed
  Singapore is too noisy to calibrate the error model. Substituting the best
  independently-validated open bare-earth product (DeltaDTM [R28]) for the *low* terrain
  and compositing *high* ground from the surface model turns the weakest case into
  a validated one. Without this, the uncorrected product's coverage-capped hills
  collapse their height-above-drainage and spuriously flood the island's highest
  dry controls.

**Coastal defences baked into the terrain.** Continuous coastal/riverbank defences
are sub-grid in the raw DEM, so a continuous-coastline crest is raised onto the
DEM at each city's **citable, contemporaneous design crest** (above MSL):

| City | Crest (m above MSL) | Provenance |
|---|---|---|
| Singapore | +3.0 | PUB pre-2011 reclamation standard (the East Coast is pre-2011; +4 m is post-2011 only) |
| Bangkok | +2.10 | BMA dike crest (UNESCAP) |
| Jakarta | +2.0 | existing wall ≈1–2 m (Muara Baru 2 m); coastal here is subsidence-dominated, so crest barely changes the result |

Built by `scripts/_fix_coastal_seawall.py` → `dem/_diag/<city>_seawall.tif`.

**Sea-mask construction + frame-fix.** The sea-mask is value **1 = land, 0 = sea**
(note: inverted from its name). The raw NaN-BFS sea-mask sweeps the DEM's nodata
border frame (W/E/N edges) into "sea", which the coastal solver then seeds from,
producing spurious lateral-edge flooding. `scripts/_fix_sea_mask_frame.py` strips
the frame by morphological opening and unions the real ≤0 m water back in
(`data/<city>/sea_mask_*_framefix.tif`). This matters specifically for the
**inertial** coastal solver (frame seeds bypass attenuation), less so for a
bathtub fill.

**HAND rasters.** Height-Above-Nearest-Drainage rasters (`dem/_hand/`) are derived
from the conditioned DEM for the fluvial and pluvial referencing in §6. A
**main-stem** HAND restricts "drainage" to channels above a flow-accumulation
threshold (≥50 km² catchment), versus a **dense** HAND that treats the full
canal/drain network as channel. Built by
`derive_drainage_mask_from_accumulation` and the `scripts/_fix_*_mainstem_hand.py`
helpers.

---

## 5. Forcing & climate scenarios

> **In plain terms.** "Forcing" is how much water the model is told to throw at the city:
> how high the sea rises, how much river flow arrives, how hard it rains. Those numbers come
> from tide-gauge records, river-flow archives and each country's own official design-rainfall
> standard. They are also the *only* thing that changes between scenarios — the model itself
> is byte-for-byte identical for the present day and for 2100, so any difference you see
> between two maps is the climate input, never a change of method.
>
> A note on "return period": **RP100** does not mean "once every 100 years". It means a
> severity with a 1-in-100 chance of being exceeded *in any given year*. Two RP100 events can
> land in consecutive years without anything being wrong.

**Design events.** Each hazard is driven at three return periods (RP 10, 100,
1000). The forcing for a given `(city, scenario, RP)` cell is stored as
`data/<city>/hazard_levels_<scenario>_rp<rp>.csv` — these are the committed,
tracked inputs the atlas driver consumes.

**Scenario stems** (driver `SCEN` array):

| Stem | Label | Horizon |
|---|---|---|
| `ssp585_2020` | present day (read as SSP5-8.5) | 2020 |
| `ssp245_2050` | SSP2-4.5 | 2050 |
| `ssp245_2100` | SSP2-4.5 | 2100 |
| `ssp585_2050` | SSP5-8.5 | 2050 |
| `ssp585_2100` | SSP5-8.5 | 2100 |

→ 4 cities × 5 stems × 3 RPs = **60 atlas cells**.

Each `(hazard, RP)` row's `water_level_m` is built as below; the GEV/Gumbel maths live
in `scripts/gev_utils.py`, the assembly in `scripts/build_hazard_levels.py`.

#### 5.1 Coastal still-water level (`water_level_m` = peak WSE)

```
 WSE_coastal(RP, scenario) = MSL_offset + surge_GEV(RP) + SLR_delta(scenario)     (tide folded into the gauge baseline)
```

| Variable | Value / source | Rationale | Reference |
|---|---|---|---|
| WSE_GEV(RP) | GEV fit to **UHSLC annual-maximum total still-water levels** (tide + surge, **de-meaned to local MSL — not de-tided**; the tide dominates and must be retained), `ppf(1−1/RP)` | annual-maxima GEV of total water level is the standard extreme-value basis for coastal design levels; consistent with global extreme-sea-level reanalyses | `fetch_uhslc_gauge.py`; Muis 2016/2020 [R9,R10] |
| GEV shape ξ | MLE, **clamped to [−0.5, 0.30]** | unclamped MLE allowed heavy Fréchet tails → unphysical RP1000; 0.30 validated vs PUB ponding 0.07–0.76 m | this work |
| MSL_offset | SG 1.1588 · JKT 0.9976 · BKK 1.1785 m | converts the EGM2008 DEM datum to local MSL; observed, **not gate-tuned** | derive_msl_egm2008_offsets.py |
| SLR_delta | **AR6** tide-gauge zarr, p50, by SSP×horizon, **added** to baseline | scenario sea-level rise is an additive mean shift on the still-water level | IPCC AR6 [R6] |

Present-day RP10→RP100 rises only ≈0.15 m (tide-dominated), so the coastal hazard is
severe even at RP10 and grows slowly with RP.

#### 5.2 Fluvial design stage (`water_level_m` = stage above channel bed)

GloFAS design **discharge** is converted to a **stage** via Manning's wide-rectangular
inversion (`gev_utils.mannings_stage`):

```
 Q ≈ (1/n)·w·d^(5/3)·√S   ⇒   d = (Q·n / (w·√S))^(3/5)
```

| Variable | Meaning | Source / rationale | Reference |
|---|---|---|---|
| `Q` | design peak discharge (m³ s⁻¹) | GloFAS v4 reanalysis design return levels | Alfieri 2018 [R30] |
| `n` | channel Manning roughness | per-city channel value | Manning [R26] |
| `w` | channel width (m) | per-city | — |
| `S` | channel slope (m/m) | per-city, from the DEM | — |
| `d` | stage above bed (the fluvial `water_level_m`) | mapped through HAND in §6.2 | — |

(`w/d > 5` wide-channel assumption is checked and warned on violation.)

#### 5.3 Pluvial net excess rain (`water_level_m` = excess depth, m)

Design rainfall comes from each **national IDF** standard, fit with a **two-anchor
Gumbel** (`_refit_pluvial_ifd.fit_gumbel`); two (RP, depth) anchors *exactly* determine
the two Gumbel parameters:

```
 y_T = −ln(−ln(1 − 1/T));   σ = (x_b−x_a)/(y_b−y_a);   μ = x_a − σ·y_a
 design_rain(RP) = μ + σ·y_RP
 excess_depth_m  = max(0, design_rain(RP) − drainage_loss) / 1000        (runoff coeff applied later, in-model)
```

| Variable | Value (per city) | Rationale | Reference |
|---|---|---|---|
| IDF anchors `(RP_a,x_a),(RP_b,x_b)` | e.g. KL: (2 yr, 90 mm),(100 yr, 165 mm) | the published national IDF design-rainfall standard | PUB / JPS-MSMA / TMD-RID / BMKG [R23] |
| Gumbel ξ | **0** (Gumbel, not GEV) | the standard form for IDF design rainfall; two anchors fix μ,σ exactly | — |
| drainage_loss | e.g. KL 70 mm | the drain-capacity threshold removed before ponding (drainage design level) | national drainage standard [R23] |
| runoff coeff `C` | raster (WorldCover); SG/KL 0.75, JKT 0.80 | impervious fraction → runoff; **applied once, in the model** (verified, no double-count) | Zanaga 2022 [R16] |

National IDF anchoring closes a **28–62 %** design-rainfall deficit that global-synthetic
products carry over the tropics — the single most important reason the pluvial layer is
credible here.

#### 5.4 Climate scaling (future scenarios)

| Hazard | Scaling | Rationale | Reference |
|---|---|---|---|
| Coastal | **additive** AR6 SLR delta (§5.1) | SLR is a mean-level shift | IPCC AR6 [R6] |
| Fluvial / Pluvial | **multiplicative first-order Clausius–Clapeyron**: `factor = (1+cc·ΔT)^h` | warmer air holds ~`cc` more moisture per °C; **uniform across RP** (see note) | Lenderink 2017 [R5] |

```
 cc  = 0.07 / °C            (Clausius–Clapeyron, sub-daily tropical rainfall)
 h   = 1.0  (pluvial, linear rain→stage)   |   0.6  (fluvial, Manning Q^0.6)
 ΔT  by scenario:  SSP2-4.5/2050 ≈ 1.0 °C ·  SSP2-4.5/2100 ≈ 2.1 °C
                   SSP5-8.5/2050 ≈ 1.5 °C ·  SSP5-8.5/2100 ≈ 4.0 °C        (rel. 2020; AR6 SPM)
```

> **Important (implementation fact).** `build_hazard_levels._gev_cc_factor` perturbs the
> GEV by scaling *both* location and scale by `α=(1+cc·ΔT)`. Because GEV is a
> location-scale family, the quantile ratio is **exactly α for every return period** — a
> *uniform* first-order CC intensification, **not** return-period-specific or super-CC.
> (The paper §3(iv) and the code docstring were corrected to say so, 2026-06-22.)

---

## 6. Hazard models

All three hazards are produced by `scripts/run_multihazard.py`, which dispatches to
solver modules under `model/`: `inertial_wave_model.py` (coastal), `flood_depth_model.py`
(HAND/bathtub/connectivity), `pluvial_model.py` (fill-spill cascade), and
`pluvial_rain_model.py` (rain-on-grid). The per-city invocation is encoded in
`repro/run_atlas_fixed.sh`. Outputs are written per hazard under
`<out>/<hazard>/rp_<rp>/<hazard>_depth_<scenario>_<horizon>_rp<rp>.tif`.

### 6.0 Common notation and forcing decomposition

Throughout this section (for everyday definitions of Manning's `n`, WSE, HAND, and the rest,
see the plain-language glossary, §11.2):

| Symbol | Meaning | Units |
|---|---|---|
| `z(x,y)` | bed elevation (the bare-earth flood DEM), NaN = nodata/wall | m (EGM2008) |
| `d(x,y,t)` | water depth above bed | m |
| `η = z + d` | water-surface elevation (WSE) | m |
| `q` | unit discharge across a cell interface (depth-integrated velocity, `q = u·h`) | m² s⁻¹ |
| `h_f` | flow depth at an interface = `max(η_L,η_R) − max(z_L,z_R)` | m |
| `n` | Manning's roughness coefficient | s m^(−1/3) |
| `g` | gravitational acceleration = 9.806 | m s⁻² |
| `HAND(x,y)` | height above nearest drainage | m |
| `Δx,Δy,Δt` | grid spacing (30 m) and timestep | m, s |

**One forcing field, three interpretations.** Each `(hazard, RP)` row of the
`hazard_levels` CSV carries a single `water_level_m`, but its meaning differs per
hazard — this is the central wiring fact of the model:

- **Coastal** — `water_level_m` is the **peak still-water level** (absolute WSE, in
  the DEM datum) = MSL + tide + surge + SLR. It is the *boundary condition*, not the
  answer; depth is solved.
- **Fluvial** — `water_level_m` is the **river stage at the return period**, above
  which the *overbank* excess `max(0, stage_RP − bankfull)` is mapped through HAND.
- **Pluvial** — `water_level_m` is the **net excess rain depth** `(design_rain −
  drainage_loss)`, later multiplied by a per-cell runoff coefficient to become a
  runoff volume.

The **runoff coefficient** `C(x,y)` (from WorldCover land cover, `--runoff-coeff-raster`,
scalar fallback `--runoff-coeff`) scales rain to runoff: per-cell runoff volume =
`excess × C × cell_area`.

### 6.1 Coastal — local-inertia shallow water *vs* bathtub

> **In plain terms.** There are two ways to work out how far the sea gets inland. The quick
> way — the "bathtub" — fills every low spot connected to the sea, instantly, as though the
> city were a bath. It has no notion of momentum, friction, or time, so it floods ground
> fifteen kilometres inland at the same moment as the shoreline. The slower way, which we use,
> steps the water forward in time with momentum and friction, so land the water cannot
> physically reach during a six-hour surge stays dry.
>
> This matters more than it sounds. Behind a working sea defence the two answers differ by
> about five times, because the bathtub leaks through canals that a 30-metre map cannot
> resolve and quietly floods the whole protected interior. Every headline coastal number in
> this atlas is read off the slower, physical solver.

This is the headline methodological choice. The atlas computes coastal inundation
with a **2-D local-inertia shallow-water solver** (`model/inertial_wave_model.py`,
`--coastal-solver inertial`), and explicitly rejects the **bathtub** (connectivity)
fill that open tools default to. The two are derived below, with the reason the
bathtub over-predicts.

#### 6.1.1 The shallow-water equations and the local-inertia simplification

The full 2-D shallow-water (Saint-Venant) momentum equation for unit discharge `q`
in the x-direction is

```
 ∂q/∂t  +  ∂(q²/h)/∂x  +  g·h·∂η/∂x  +  g·n²·q·|q|/h^(7/3)  =  0
 (local accel)  (advection)   (pressure grad)      (friction)
```

For slowly-evolving flood waves at **low Froude number** (`Fr = u/√(gh) ≪ 1` — true
for coastal/urban flatland inundation), the nonlinear **advection** term
`∂(q²/h)/∂x` is negligible and is dropped. Discretising the remaining three terms
explicitly in time and solving for `q^{n+1}` gives the **Bates, Horritt & Fewtrell
(2010)** update used here:

```
                q^n  −  g · h_f · (∂η/∂x) · Δt
 q^{n+1}  =  ───────────────────────────────────────
              1  +  g · n² · |q^n| · Δt / h_f^(7/3)
```

where `h_f = max(η_L,η_R) − max(z_L,z_R)` is the interface flow depth (the
"two-cell" depth that lets water cross a sill only when the higher WSE exceeds the
higher bed). The numerator advances momentum under the **water-surface-slope
pressure gradient**; the denominator applies **Manning friction** semi-implicitly
(it appears as `q^{n+1}` in friction but `q^n·|q^n|` in the quadratic, which keeps
the scheme stable without a matrix solve). Mass is then conserved by the explicit
**continuity** update:

```
 d^{n+1}_{i,j} = d^n_{i,j} − (Δt/Δx)(q_x,{i,j} − q_x,{i,j−1})
                            − (Δt/Δy)(q_y,{i,j} − q_y,{i−1,j})        , clipped ≥ 0
```

**Stability (CFL).** The explicit scheme requires `Δt ≤ α · min(Δx,Δy) / (√(g·d) +
|u|)` with safety factor `α = CFL_ALPHA = 0.7`. The solver recomputes `Δt` adaptively
every step (`_adaptive_dt`) from the current max gravity-wave celerity `√(g·d)` and
max interface velocity, capped at `--inertial-dt-max` (default 30 s). Sea
(Dirichlet) cells are excluded from the CFL test so their large depths don't throttle
the land timestep.

**Implementation.** Hot kernels (`_flux_x/_flux_y/_continuity`) are JIT-compiled with
`numba` (`@njit(parallel=True, fastmath=True)`) when available, with verified pure-numpy
fallbacks. The domain is auto-cropped to the bounding box of cells that can ever wet
(`sea ∪ {z ≤ peak_WL}` + 32-cell pad), often halving per-step cost. `g = 9.806`,
`MIN_DEPTH = 1 mm` (interfaces shallower than this carry no flux).

#### 6.1.2 Boundary condition — surge hydrograph on an SLR floor

Sea cells are held at a **time-varying Dirichlet WSE** `wl_fn(t)` (`_surge_hydrograph`),
a synthetic asymmetric triangular surge riding on a **permanent still-water floor**:

```
 floor   = MSL_EGM2008 + SLR            (this row's coastal_delta_m)
 0 → 3h         : linear ramp  0 → peak_WSE   (gentle start; a dry-bed step shocks
                                               the explicit scheme)
 3h → 4h        : hold at peak_WSE
 4h → 6h        : linear recession peak_WSE → floor   (NOT → 0)
```

The recession stops at the floor, **not zero**, so sea-connected land below MSL+SLR
stays inundated after the surge withdraws — the physically correct persistent SLR
signal. When `floor > 0` the early-convergence test is disabled (`convergence_window`
set huge) so the solver actually simulates the full ramp/hold/recession rather than
exiting on the sub-tolerance warm-start state.

**Warm-start.** Two stacked initialisers cut steps-to-solution 3–5×: (1) `subsea_init`
pre-floods below-MSL land to the floor (steady-state start), and (2) the **previous
RP's** peak depth seeds the next RP so only the surge *increment* must be resolved.
RPs are therefore run in ascending order with depth chained forward.

**Post-hoc physical cap.** Narrow inlets/steep gradients can numerically amplify a few
cells during the sustained peak hold. Depth is capped at

```
 d ≤ (peak_WSE − bed) + 0.2 m                      (2026-06-24: bed, NOT max(0,bed))
```

the static maximum plus a velocity-head margin (`≈ ½v²/g` for v = 2 m s⁻¹) — removing
artefacts without touching genuine depths or bulk extent. **The `bed` (not `max(0,bed)`)
form is essential on subsided coasts:** clamping the bed at 0 caps below-MSL cells at the
water level itself and silently under-states the water column in Jakarta's below-sea-level
polders (the cap fix of 2026-06-24; see §10 and the depth caveat in §6.1.3). Note the
resulting depths are *equilibrium-fill* values — the full column from surge surface to
bed — which is the damage-relevant depth where a polder is sea-connected but an upper
bound where active pumping holds it lower. The inertial solver
resolves connectivity intrinsically, so **no BFS connectivity filter** is applied to its
output (unlike bathtub).

#### 6.1.3 The bathtub method, and why it over-predicts

The bathtub depth (`flood_depth_bathtub`) is purely static:

```
 d(x,y) = max(0, WL − z(x,y))
```

followed by a **connectivity filter** (`connected_flood_mask`): a 4/8-connected BFS
from the sea boundary (and tidal-channel seeds) keeps only flooded cells hydraulically
connected to open water, discarding isolated inland lows. There is **no momentum, no
friction, and no time** — every cell connected to the sea and below `WL` floods to the
full `WL − z`, regardless of how far inland it is or what gradient/roughness the water
would have to traverse to get there.

This is the over-prediction mechanism, and it is an artifact of **solver architecture,
not 30 m resolution**: on a gradient- and defence-rich delta, a momentum-and-friction
solver leaves far-field low ground dry within a 6-hour surge because the water cannot
physically arrive and persist, whereas the bathtub floods it instantly. The gap is
**regime-dependent**, up to ≈5× on the Bangkok delta. Every headline coastal exposure
figure is read off the **inertial** layer.

| | bathtub | local-inertia (this model) |
|---|---|---|
| Pressure gradient (backwater) | ✗ static flat WSE | ✓ `g·h·∂η/∂x` |
| Mass conservation | ✗ none | ✓ strict continuity |
| Friction / travel time | ✗ instantaneous | ✓ Manning `n`, finite surge window |
| Connectivity | BFS post-filter (4/8) | intrinsic to the 2-D solve |
| Velocity / `h·v` hazard | ✗ | ✓ (optional) |
| RP100 bias on defended delta | up to ~5× high | reference |
| Cost | seconds | ~30 min/RP/city (inertial) |

`--coastal-solver bathtub` is retained as a fast screening fallback (and is used when
no sea-mask is available); it is **not** used for the published atlas.

#### 6.1.4 Datum, negative land, defences

- **Datum.** WSEs are referenced to local MSL via per-city EGM2008 offsets
  (`--coastal-msl-egm2008`): Singapore 1.1588, Jakarta 0.9976, Bangkok 1.1785.
- **Negative land.** Jakarta/Bangkok pass `--no-clamp-negative-land`: genuine below-MSL
  land exists (Jakarta subsidence) and clamping would erase real exposure.
- **Defences.** Continuous coastal crests are baked into the DEM (§4); Bangkok adds the
  pumped-polder post-process (§6.1.5).

#### 6.1.5 Pumped polders (Bangkok only)

Bangkok's King's-Dyke CBD stays dry behind pumped polders, so
`scripts/apply_pumped_polder.py` dries documented polder rings in post-processing
(`<out>_polder` — the scored/published composite). Tested for Jakarta and **rejected**:
Jakarta's Pluit/Muara Baru polders genuinely flood at RP100 and the flooded dry control
there (Cipete) is fluvial, not coastal — so the polder fix is Bangkok-only.

### 6.2 Fluvial — HAND referencing *vs* other methods

> **In plain terms.** River flooding is handled by asking, for every point in the city, "how
> far above the river am I?" — then raising the river by the design amount and seeing what
> ends up underwater. The subtlety is *which* river. A city is threaded with hundreds of small
> drains as well as a few big rivers, and the flow figure we have describes only the big ones.
> Measure height above every little drain and you flood the whole city; measure height above
> the main trunk the flow actually belongs to and you get something sensible. That choice is
> the substance of this section.

#### 6.2.1 What HAND is

**HAND** (Height Above Nearest Drainage; Rennó et al. 2008, Nobre et al. 2011) is a
terrain transform: every cell's vertical height above the channel cell its D8 flow
path drains to. It renormalises absolute elevation into *elevation relative to the
local river*, which is the natural vertical reference for river flooding. It is
computed once per city from the conditioned DEM: D8 flow directions on the pit-/
flat-resolved surface, a drainage network defined by flow-accumulation threshold, and
for each cell the drop to its nearest network cell along the flow path.

#### 6.2.2 Depth mapping (the model)

Fluvial depth is a **static stage-minus-HAND** map (`flood_depth_hand`), but the stage
is the **overbank excess above bankfull**, not the raw return-period stage:

```
 overbank   = max(0, stage_RP − bankfull_stage)         (--fluvial-bankfull-rp sets bankfull; 0 here)
 d(x,y)     = max(0, overbank − HAND(x,y))
 d(channel) = 0                                          (burned channel cells masked — see below)
```

Cells with `HAND < overbank` flood, to a depth that is greatest at the channel
(`HAND ≈ 0`) and tapers to zero at the inundation edge (`HAND = overbank`). Subtracting
bankfull first means a return period only inundates the floodplain by the *excess* over
the channel's design conveyance — below bankfull, the river is in-bank and the
floodplain is dry.

**Channel masking.** HAND is 0 on the burned channel network, so every channel cell
would "flood" on any overbank — but a canal carrying water is *conveyance*, not
inundation, and many channels are below-grade (engineered beds), which would make the
map appear to flood "underground". Channel cells are therefore zeroed
(`depth = where(river_mask, 0, depth)`), mirroring the pluvial treatment of channels as
sinks.

#### 6.2.3 Main-stem *vs* dense-network drainage — the threshold that matters

The single most consequential fluvial parameter is the **flow-accumulation threshold**
that defines "drainage" (`derive_drainage_mask_from_accumulation`):

- **Dense HAND** — the full canal/drain network is "channel". On canal-dense cities this
  labels a huge fraction of land as `HAND ≈ 0` (Singapore's dense hybrid HAND: 96.5 km²
  ≈ 19 % of land), so a modest stage floods ~40 % of the island and the *fluvial* layer
  silently **absorbs the pluvial hotspots** — the failure that crashed Singapore's gate
  from 0.84 to 0.13 when fluvial was reduced naively.
- **Main-stem HAND** — only channels draining above a **per-city accumulation threshold**
  count: **≥50 km²** for Singapore and Jakarta, **≥180 km²** (the larger Klang trunk) for
  Kuala Lumpur. The stage then floods land within reach of the *trunk* river, not of every
  minor drain. This corrects the fluvial extent (SG fluvial 180→28 km², channel
  96.5→2.8 km²) and forces the pluvial hazard onto the pluvial layer where it belongs.

Per-city HAND rasters: Singapore `singapore_hand_v3_mainstem`, Jakarta
`jakarta_hand_v3_mainstem`, Bangkok `hand_trunk_v3_debiased`, KL `kl_hand_mainstem_v3eth`
(already main-stem at ≈0.9 % channel).

**Provenance and reproducibility (all four now resolved; 2026-07-18).** Every raster in the
repo is git-ignored by convention; the *primary* inputs (bare-earth DEMs, masks, forcing)
ship in the Zenodo archive's `inputs/`, and committed scripts regenerate the *derived* ones.
The four fluvial HANDs sit in two categories:

- **Script-derived** (regenerated by the atlas driver from committed inputs): Singapore
  `scripts/_fix_sg_mainstem_hand.py`, Jakarta `_fix_jakarta_mainstem_hand.py`, and — as of
  2026-07-18 — **KL `scripts/_fix_kl_trunk_hand.py`**. A plain flow-accumulation threshold
  does **not** reproduce the KL trunk (a ≥180 km² threshold gives only ~3 km² of channel and
  IoU 0.82 against the shipped HAND — the shipped Klang trunk is a denser v2-lineage
  network), so the topology is shipped as an explicit **frozen drainage mask**
  (`data/kuala_lumpur/trunk_drainage_mask_utm47n.tif`, 12,362 channel cells) and the builder
  computes `compute_hand(DEM, mask)` from it. Verified: **regenerates the shipped raster to
  max|Δ| = 0 (bit-identical)**; the mask now ships in the KL Zenodo inputs.
- **Primary frozen input** (shipped in the archive, not script-derived): Bangkok
  `hand_trunk_v3_debiased`. Its drainage is the v2 Chao-Phraya-trunk network **plus an
  opaque debiasing step** that no committed script reverses (from-mask and from-accumulation
  rebuilds reach only IoU ≈ 0.65 and would change the shipped fluvial layer). It is therefore
  shipped as a primary frozen input in the Bangkok Zenodo `inputs/` — **the same category as
  the bare-earth DEMs**, which likewise have no in-repo builder and ship as frozen inputs.
  This is a documented, bounded provenance limitation, not an availability gap: the exact
  raster is obtainable and the Bangkok fluvial result reproduces from it.

> **Flat-delta note.** Even a main-stem HAND keeps a large fluvial footprint on a
> low-gradient delta, because everything sits within the trunk stage of the river
> (Jakarta fluvial ≈181 km²). This is physical, not a bug — the whole delta *is* the
> Ciliwung floodplain.

#### 6.2.4 HAND *vs* the alternatives

| Method | Physics | Cost | Why not (for this screen) |
|---|---|---|---|
| **HAND** (used) | static stage on drainage-relative terrain | ~seconds | the screening sweet spot — topographically coherent, no routing, scales to 60 cells |
| Bathtub fluvial | `max(0, stage − z)` + BFS from channel | seconds | references absolute elevation, not the river; floods any low ground at `z < stage` even if it is nowhere near a river |
| 2-D hydrodynamic (inertial, array BC) | full local-inertia with a **per-cell channel WSE field** held as Dirichlet (the solver *supports* this — `wl_boundary` as an ndarray) and spill routed onto the floodplain | ~30 min/RP | overkill for design-event *screening*; needs reach-by-reach channel geometry/discharge the open forcing doesn't resolve at 30 m |
| Full hydraulic model (HEC-RAS etc.) | 1-D/2-D coupled, surveyed cross-sections | hours–days | not license-clean, not rebuildable from free data, not scalable to the atlas |

HAND is chosen because it captures the dominant control on fluvial extent — *height
above the river* — at screening cost and from free terrain, while the heavier options
need data the open pipeline cannot supply uniformly across four countries. The inertial
*riverine* path exists in the code (array boundary condition) for future per-reach work.

### 6.3 Pluvial — four models, regime-matched

> **In plain terms.** This is flooding caused purely by rain arriving faster than the ground
> and the drains can carry it away — the "flash flood" that global flood products usually
> leave out entirely, and the biggest single hazard in three of our four cities. Rain floods a
> city in one of two ways, and which one depends on the shape of the land. On flat ground with
> lots of hollows, water collects in the hollows and spills from one to the next; that is
> Bangkok. In cities threaded with canals and open drains, water backs up along the drainage
> network and floods the low land beside it; that is Kuala Lumpur, Singapore and Jakarta. We
> use a different method for each, because using the wrong one measurably lowers the trust
> score in §7.

Pluvial (rain-driven) flooding is where method choice matters most, because the
physical mechanism differs by terrain: water either **collects in closed basins**
(depression storage) or **backs up beside overwhelmed drains** (drainage-overwhelm).
`run_multihazard.py` implements four `--pluvial-model` options. Two are in production
use — `fillspill` and `handfill` — and two are alternatives (`raingrid`, `legacy`). All
share the same forcing: `water_level_m` is the net excess rain depth, scaled by the
per-cell runoff coefficient `C`.

> **⚠ The atlas is built in two stages.** §6.3.1–6.3.5 below document the solvers and the
> *original* regime assignment (fill-spill: Bangkok, KL; handfill: Singapore, Jakarta),
> which is what the **Stage-1 solve loop** in `repro/run_atlas_fixed.sh` invokes. That
> Stage-1 atlas is then modified by the two applies below, and the outputs/paper reflect
> the post-retrofit state. Since 2026-07-13 both run inside the same driver as **STAGE 2**,
> so one command reproduces the shipped product:
>
> 1. **Canal-HAND retrofit (2026-07-04)** — a HAND handfill referenced to the *real mapped
>    drain network* (not a synthetic dense net), applied under a selection rule rather than
>    blanket-applied. Measured verdicts: **KL applied** (unioned per-pixel with its
>    depression cascade), **Jakarta applied**, **Singapore rejected** (its shipped pluvial
>    already scores strongly), **Bangkok rejected** (pumped flat delta — CRR collapses).
>    The rule: retrofit only where the shipped pluvial-only HR is demonstrably low **and**
>    the register's dry controls sit topographically above its positives; on flat pumped
>    deltas engineered drainage decouples flooding from topography, so no HAND variant can
>    discriminate. Run docs: `docs/runs/2026-07-04-*canal-hand-pluvial.md`.
> 2. **Pluvial closing (2026-07-07)** — see `docs/runs/`.
>
> **§6.3.5 documents both stages and states the shipped post-retrofit configuration** —
> read it for what the atlas and paper actually report. Gate numbers quoted inside
> §6.3.1–6.3.4 are **Stage-1 (pre-retrofit)** values, retained because they are the
> evidence that selected each city's *base* solver.

#### 6.3.1 `fillspill` — catchment-routed fill-and-spill cascade

The production depression-storage model (`model/pluvial_model.py`) is a
topologically-ordered **fill-and-spill cascade** — a screening-grade approximation of
Barnes et al. (2020) Fill-Spill-Merge — not a lumped fill. It is built once per city
(`build_pluvial_topography`) and routed per RP (`route_pluvial_rp`).

**Step 1 — depression inventory.** Pit-fill the DEM (`filled`), then label connected
components (8-connectivity) of `filled − dem > 0`. Each component is a depression, kept
only if it passes three physical filters that screen out DEM noise and non-ponding
features:

```
 depth   d(x,y) = filled(x,y) − dem(x,y)
 keep depression  iff  0.5 m ≤ max(d) ≤ 3.0 m   and   area ≥ 9 cells (≈0.8 ha)
```

(`< 0.5 m` = noise; `> 3.0 m` = quarry/valley/reservoir/artefact, excluded like sea;
`< 9 cells` = sub-pixel inter-building voids in the GLO-30 DSM.)

**Step 2 — hypsometric curve.** Each depression stores its cell bed elevations sorted
ascending. Its **volume–level** relation is

```
 V(h) = cell_area · Σ_i max(0, h − bed_i)            (capacity = V(pour_elev))
```

inverted analytically (`_fill_level`) to find the water level `h` that holds a given
inflow volume.

**Step 3 — catchment supply.** Per-cell runoff volume `excess · C · cell_area` is routed
by **D8 steepest descent** on the raw DEM; every cell is credited to the depression its
flow path terminates in (`compute_catchment_supply`, via terminal-label propagation in
ascending-elevation order). Runoff that terminates in an excluded/edge sink is dropped
(it drains away, exactly as sea/river sinks do).

**Step 4 — spill cascade.** Each depression's overflow destination is found by walking
the *conditioned* D8 field until it reaches another depression or a sea/river sink
(`build_spill_graph`). Depressions are then filled in **topological order**
(`run_cascade`): if total inflow ≥ capacity, the depression fills to its pour elevation
and the surplus cascades to its downstream destination; otherwise it fills partially via
the inverted hypsometric curve. Processing downstream-after-upstream guarantees each
depression's inflow is final before it fills.

**Step 5 — paint depth.** `d = max(0, level_d − bed)` for each depression's cells; cells
below `WET_THRESHOLD_M = 0.05 m` are set dry.

This is **RP-dependent** (extent grows with return period) and **parameter-light** — no
free stage parameter, just the runoff excess. It is physically correct exactly where
flooding *is* basin storage: **flat depression-dominated deltas** (Bangkok) and any
terrain whose lows are genuine closed basins.

#### 6.3.2 `handfill` — rain pooling near open drainage

On canal-dense cities most excess rain never enters a closed basin — it sheets down open
gradients and **backs up at low points beside saturated drains**. `fillspill`
structurally reports almost no ponding there (Singapore: 1/38 hotspots). `handfill`
models this drainage-overwhelm regime as a **HAND stage on the dense network**:

```
 d(x,y) = max(0, stage − HAND_dense(x,y))                  (flood_depth_hand on the dense HAND)
 d = 0   where  river_mask  OR  HAND_dense < 0.05 m        (channels = conveyance, not flood)
 d = min(d, depth_cap)                                     (life-safety flash-flood bound)
```

It reuses the HAND depth kernel (§6.2.2) but on the **dense** HAND (the full drain
network, not the trunk), so it floods the low land *adjacent to every open drain* to a
rain-driven `stage`. Two parameters: `--pluvial-hand-stage` sets the flood-prone
**extent**, `--pluvial-depth-cap` bounds the **depth** (without the cap, `stage − HAND`
over-deepens right next to drains). Production values: Singapore (hybrid HAND, stage
1.5 m, cap 0.5 m), Jakarta (`jakarta_hand_v3`, stage 2.5 m, cap 1.0 m). Result *(Stage-1,
pre-retrofit)*: Singapore pluvial 15→95 km² (present-day), gate HR 0.13→0.71 PASS; Jakarta
TSS 0.66→0.76 PASS. Jakarta's base layer was subsequently unioned with a canal-HAND layer
(Stage 2, §6.3.5), lifting its gate to 0.85/0.92/**0.77**; Singapore's base layer ships
unchanged.

**Return-period / climate scaling (2026-06-22).** With a *fixed* stage the handfill layer
is **forcing-invariant** — it ignores `water_level_m`, so the SG/Jakarta pluvial extent was
identical at every RP and every scenario (SG 95.1 km², Jakarta 168.0 km² everywhere). The
opt-in flag `--pluvial-hand-stage-baseline <excess_m>` fixes this: the effective stage
scales with this row's rain excess, `stage_eff = stage × clip(level_m / baseline, 0.4, 2.5)`,
where `baseline` is the present-day RP100 excess the stage was calibrated against (SG 0.0696,
Jakarta 0.1300). At `level_m == baseline` the stage is unchanged, so the **present-day RP100
gate is preserved by construction**; other RPs/scenarios now respond (SG 49→95→129;
Jakarta 108→168→217 km² at RP10/100/1000, pre-closing). **The shipped atlas carries the
scaled layer** (measured: SG pluvial 56.7/111.2/150.2 km² at RP10/100/1000 present-day,
≥0.10 m) — historically applied post-rebuild by `repro/rerun_handfill_scaled.sh`, and since
2026-07-17 produced directly by the driver, whose SG/Jakarta lines pass
`--pluvial-hand-stage-baseline` (0.069602 / 0.129999) in Stage 1.

**Physical bracket on the base stages (anchored 2026-07-18; review C7 follow-up #3).**
The base stages were chosen with gate visibility (§10 item 3); the external standards do
not *pin* either value, but they **bracket** it, which bounds the choice physically:

- **Singapore 1.5 m.** The dense-HAND reference surface sits at the DEM's drain elevation
  (engineered beds read below grade — limitations register #1), so the stage is the height
  of ponding *above the drain bed*: drain depth + surcharge above bank. PUB's Code of
  Practice on Surface Water Drainage requires roadside drains ≥ 0.6 m deep, classes ordinary
  open drains by ≤ 1 m / > 1 m depth (i.e. metre-deep drains are routine), sets freeboard at
  **15 % of drain depth** (CoP §7.3.4), and designs minor catchments (< 100 ha) to a 10-yr
  storm (CoP §7.1.3) — beyond which the drain surcharges. A 1.0–1.2 m outlet drain
  surcharged to bank-top plus ponding within PUB's own documented 0.07–0.76 m range spans
  **≈ 1.1–2.0 m above the bed**; 1.5 m sits mid-band.
- **Jakarta 2.5 m.** BNPB's reporting for the January-2020 monsoon event — the design-class
  event for this layer — recorded 268 flooded locations at depths **0.2–2.5 m**, six
  kampungs ≥ 2 m (Cipinang Melayu peaking ≈ 4 m). The 2.5 m stage is the top of BNPB's
  city-wide band: the layer floods land up to, and not beyond, the documented envelope of
  the design-class event. (Indonesian practice — SNI 03-2406-1991 / Pd T-02-2006-B — sets
  drain freeboard at 5–30 % of flow depth, same order as PUB's 15 %.)
- **KL / Jakarta canal-HAND stage_ref (0.5 / 0.3 m, §6.3.5).** MSMA (2nd ed., ch. 26)
  dimensions lined open drains at 0.5–1.2 m with 50–300 mm freeboard; the 0.5 m and 0.3 m
  reference stages are the depth class of the *mapped minor-drain network* they are
  referenced to, not the metre-deep outlet class above.

The honest provenance statement is therefore **GATE-SELECTED within a standards-bracketed
range**: the bracket comes from PUB/MSMA/SNI + the BNPB event record; the specific value
inside the bracket was chosen with gate visibility. §11.4 carries this classing.

#### 6.3.3 `raingrid` — 2-D rain-on-grid (alternative)

The most physical pluvial option (`model/pluvial_rain_model.py`): the **same
local-inertia solver as the coastal model** (§6.1.1), but with a distributed **rainfall
source term** instead of a sea boundary:

```
 net rain rate = (excess · C) / storm_duration        applied to land cells while t < storm
 d^{n+1} += rain_rate · Δt                              (source, on top of the SWE update)
 outlets (sea ∪ open channels): d = 0 each step         (free-drainage sinks)
```

Manning's `n` is spatially variable (land-cover-derived, `≈ clip(0.11 − 0.08·C, 0.03,
0.10)`). Drains can be made **finite-capacity** (`--drain-conveyance-m-s`): a perfect-sink
mask (sea + major rivers) drains freely while minor channels shed only
`conveyance · Δt` per step and pond the remainder when overwhelmed. Output is the **peak**
depth over a storm-plus-settling window (default 1 h storm + 0.5 h settle), denoised
(`denoise_min_cluster`, drop < 6-cell ≈0.5 ha speckle) and floored at 0.05 m. RPs are
solved in a process pool (`--raingrid-workers`). *Not* in production: on steep terrain it
over-drains (KL → ~0 pluvial), and where it works it is far costlier than `handfill` for
a similar result.

#### 6.3.4 `legacy` — lumped depression fill (deprecated)

The original model (`flood_depth_pluvial_ponding`): `d = min(WL, filled − dem)`. RP-frozen
extent (the depression footprint is identical at every RP, only depth scales), superseded
by `fillspill`. Retained for reproducing earlier results.

#### 6.3.5 Model selection — two gate-arbitrated decisions

The shipped pluvial layer is the result of **two** decisions, taken three months apart and
both arbitrated by the model-blind register rather than by preference. Stage 1 chose the
*base* solver per city (2026-06); Stage 2 retrofitted a **canal-HAND** layer onto two of
the four (2026-07-04). Both are documented here because the second changes what several
earlier sections imply.

##### Stage 1 — `fillspill` *vs* `handfill` (the base layer)

Regime-matching is **empirically validated, not stylistic**: forcing the wrong model
measurably degrades the model-blind gate (expanded register, present-day RP100). These are
the **pre-retrofit** scores that selected each city's base solver:

| City | Regime | fill-spill TSS [95% CI] | handfill TSS [95% CI] | base solver |
|---|---|---|---|---|
| Singapore | canal-dense island | fails (1/38 hotspots) | **0.61** [0.41, 0.79] PASS | handfill |
| Jakarta | canal-dense delta | 0.66 | **0.76** [0.61, 0.91] PASS | handfill |
| Kuala Lumpur | steep, sub-grid | **0.65** [0.48, 0.81] | 0.51 [0.23, 0.76] | fill-spill |
| Bangkok | flat khlong delta | **0.34** [0.19, 0.50] | 0.37 **[−0.01, 0.72]** | fill-spill |

The two failure modes are instructive and **opposite**:

- **Bangkok (handfill fails).** On a flat khlong-laced delta *everything* is within
  1.5 m of a drain, so handfill floods ≈617 km² (vs fill-spill's 179) — most of the
  delta. HR rises spuriously (flood-everything) but specificity collapses and the **TSS
  CI crosses zero** — it loses statistical significance. Fill-spill's depression
  geometry preserves specificity (CRR 1.00).
- **KL (handfill underperforms).** Handfill gives a more *coherent-looking* map (3.5k
  zones vs fill-spill's 12k tiny pits) and slightly higher HR, but floods two dry
  controls, dropping TSS 0.65→0.51. The spotty fill-spill is gate-optimal precisely
  because its scattered pits dodge the dry controls. KL's flash floods are fundamentally
  **sub-grid** at 30 m; neither model is ideal, and fill-spill is retained for the gate.
- **Singapore / Jakarta (handfill wins decisively).** Canal-dense, bounded terrain where
  the hotspots sit beside open drains — exactly handfill's regime — so it lifts both
  cities over the PASS bar where fill-spill cannot represent the mechanism at all.

**Stage-1 decision rule.** Use `fillspill` for depression-dominated terrain (closed basins:
flat deltas, steep pits) and `handfill` for canal-dense cities whose flooding is
drainage-overwhelm beside open drains. See §10 for the open caveat that handfill's
`stage` was effectively gate-selected and needs re-anchoring to a documented value.

##### Stage 2 — the canal-HAND retrofit (2026-07-04)

Stage 1's `handfill` references a **synthetic dense HAND**. Stage 2 asks a sharper
question: reference the stage to the **real, mapped drain network** instead. The retrofit
adds a canal-HAND layer **unioned per-pixel** with the city's existing (Stage-1) layer, so
it can only *add* wet cells:

```
 pluvial_new(x,y) = max( pluvial_shipped(x,y),  clip(stage_cell − HAND_canal(x,y), 0, cap) )
 d = 0 on channels                                   (conveyance, as everywhere else)
 HAND_canal        = height above the MAPPED drain network (OSM / river mask)
 stage_cell        = stage_ref × clip(cell excess / baseline_excess, lo, hi)
```

| City | `HAND_canal` network | `stage_cell` | cap |
|---|---|---|---|
| Kuala Lumpur | `drainage_waterways_utm47n`, **pruned to drains with ≥0.5 km² flow accumulation** | `0.5 m × (excess/0.095)`, clip [0.4, 2.5] | 3.0 m |
| Jakarta | `river_mask_utm48s`, **unpruned (full network)** | `0.3 m × (excess/0.130)`, clip [0.15, 1.5] | 3.0 m |

**Why the pruning differs is physical, not tuning.** KL is hilly: unpruned, headwater
ditches carry `HAND_canal ≈ 0` onto the ridges and flood the high dry controls (Federal
Hill, TTDI). An accumulation prune removes ditches that are not conveyance. Jakarta is a
flat delta whose canals are *all* engineered conveyance — there are no hill headwater
ditches to remove, and the gate is insensitive to pruning there. **Rule: prune in hilly
cities; do not prune on deltas.**

**The 4-city assessment — tested on all four *before* applying to any:**

| City | shipped pluvial-only HR | dry-control geometry | canal-HAND verdict |
|---|---|---|---|
| Kuala Lumpur | **0.13** (under-powered) | all high ground (min 49.7 m) | **applied** |
| Jakarta | 0.64 | high ground (min 31.9 m) | **applied** — strict win, TSS improves |
| Singapore | 0.71 (already strong) | moderate relief (min 6.7 m) | **rejected** — TSS 0.61 → 0.39–0.54 across every variant |
| Bangkok | 0.25 | degenerate (all controls < 5 m) | **rejected** — CRR 1.00 → 0.43, TSS 0.34 → 0.02 |

> **Stage-2 selection rule (the transferable finding).** Retrofit canal-HAND **only**
> where (a) the shipped pluvial-only HR is demonstrably low **and** (b) the register's dry
> controls sit meaningfully **higher** than its positives — i.e. topographic position
> relative to drainage is informative. **Both are checkable before building anything.**
> The two rejections explain why: on a **flat pumped delta** (Bangkok) engineered drainage
> decouples flooding from topography, so *no* HAND variant can discriminate — it floods the
> low dry controls and specificity collapses; in an **already-skilful, heavily-drained**
> city (Singapore) it only adds false alarms.

**Measured effect of the two applications:**

| | KL shipped → retrofit | Jakarta shipped → retrofit |
|---|---|---|
| pluvial extent (RP100/2020) | 37.9 → **246** km² | 163 → **245** km² |
| largest contiguous patch | 0.18 → **6.5** km² | — |
| documented flash-flood streets hit | 13 % → **55 %** | — |
| gate HR / CRR / TSS | 0.65/1.00/0.65 → **0.71/0.92/0.63** | 0.76/1.00/0.76 → **0.85/0.92/0.77** |

KL trades a hill dry-control (CRR 1.00→0.92) for three recovered documented streets
(Segambut Dalam, Jalan Tun Razak, Bangsar); TSS is **parity within the ±0.16 bootstrap CI**
while HR rises 0.06 — the layer stops being near-redundant (pre-retrofit NO-PLUVIAL HR 0.58
vs ALL 0.65). Jakarta is a **strict win** — the headline TSS improves. Both scale monotonically
with RP (KL ≈224→315 km², Jakarta 179→342 km² across RP10→RP1000/2100). *(All extents in
this subsection are as measured at the 2026-07-04 retrofit, before the 2026-07-07
bridge-closing scaled every city's pluvial extent ×1.20–1.28; the shipped present-day
values are in §8.)*

##### Shipped per-city configuration (post-retrofit — what the atlas and paper report)

| City | Base solver (Stage 1) | Canal-HAND (Stage 2) | Shipped pluvial | Gate HR/CRR/TSS |
|---|---|---|---|---|
| Singapore | `handfill` (hybrid HAND, stage 1.5 m **scaled**, baseline 0.0696, cap 0.5 m) | rejected | base only | 0.71 / 0.90 / **0.61** |
| Kuala Lumpur | `fillspill` (cap 3.0 m) | **applied** (pruned ≥0.5 km²) | `max(base, canal-HAND)` | 0.71 / 0.92 / **0.63** |
| Bangkok | `fillspill` (cap 3.0 m) | rejected | base only | 0.34 / 1.00 / **0.34** |
| Jakarta | `handfill` (stage 2.5 m **scaled**, baseline 0.1300, cap 1.0 m) | **applied** (unpruned) | `max(base, canal-HAND)` | 0.85 / 0.92 / **0.77** |

("scaled" = the RP/climate stage-scaling of §6.3.2, `stage × clip(excess/baseline, 0.4,
2.5)`; both handfill cities ship it, and the driver's Stage-1 lines carry the
`--pluvial-hand-stage-baseline` flag so a clean rebuild reproduces it.)

**Implementation note (STAGE 2 of the driver).** Since 2026-07-13 the retrofit runs inside
`repro/run_atlas_fixed.sh` as **STAGE 2**, after the Stage-1 solve loop. The order is
load-bearing:

1. **canal-HAND applies** (`scripts/_apply_kl_canal_pluvial.py`,
   `_apply_jakarta_canal_pluvial.py`) — idempotent: each recomputes from the pristine
   `*.tif.orig` sidecar, so a resumed or repeated run is safe.
2. **bridge-closing** (`_apply_city_pluvial_closing.py`, all four cities) — backs the
   *current* raster up to `*.preclose` once and closes that. It must run **after** the
   applies, and must never read `*.orig`.
3. **summary/severity regen** (`_regen_pluvial_summary_severity.py`) — must run **last**, so
   the CSVs and severity rasters describe the final depths.

The regen is **read-only on the depth raster**. It formerly also re-masked each cell to the
footprint stored in `*.orig` — a one-time repair for footprint damage the 2026-07-04 apply
introduced, correct only while the regen ran immediately after that apply. Once the closing
exists it is actively destructive: `*.orig` predates the canal-HAND, whereas the closing
deliberately keeps bridged cells falling *outside* that footprint, so re-masking silently
deleted them (measured on `jakarta_ssp585_2100_rp100`: pluvial extent cut 337.2 → 334.4 km²
at ≥ 0.10 m, −2.81 km², taking the cell off its published Table-II value of 337). Removed
2026-07-13: the depth the chain leaves is authoritative, and this step only derives the
severity raster and the summary row from it.

**Singapore's gate is new, not changed.** The SG register
(`hotspots_expanded.csv`, PUB *List of Flood-Prone Areas* Nov 2025 — 38 positives / 20 dry
controls) was imported 2026-07-04; SG scores 0.71/0.90/0.61 **with no model change** — a
validation result the model previously lacked, not a retrofit effect.

**Runoff coefficient.** Common to all four: `--runoff-coeff-raster` (WorldCover-derived)
with scalar fallback `--runoff-coeff` (Singapore/KL 0.75, Jakarta 0.80).

---

## 7. Validation: model-blind hotspot gate

> **In plain terms.** A model that is easy to rebuild can still be wrong, so this is the part
> where we try to catch it being wrong. For each city we wrote down two lists: places
> documented to have flooded, and places documented to have stayed dry. Then we checked whether
> the model floods the first list and leaves the second alone.
>
> Two rules make it a real test rather than a formality. The lists are **frozen before** the
> final scoring, so the model cannot be quietly adjusted until it agrees. And nothing is
> reclassified once frozen — if the model floods a place on the frozen dry list, that counts
> against it permanently. (Two Jakarta labels were corrected on documented flood records before
> the final freeze; the published list records both, and Jakarta passes either way — see
> `docs/presentation/SAFE2026-FAQ.md`, F8.) Three scores come out: how many real flood spots
> it catches, how many dry spots it correctly leaves alone, and a single combined number where
> 0 is no skill and 1 is perfect.

**Principle.** Trust is established by a **pre-registered, model-blind
location-skill gate** (`scripts/validate_hotspots.py`, math in
`scripts/hotspot_scoring.py`), not by reproducibility alone. A frozen register of
documented-**flooded** ("positive") and documented-**dry** ("control") localities is
scored against the model's combined flood layer. The register is fixed before scoring
and the model is never tuned against it.

#### 7.1 The buffered hit test

Each register entry is a georeferenced point `(lon, lat)` with class ∈ {flood, dry}.
A point scores a **hit** (`sample_hit`) iff any cell within a radius buffer exceeds the
depth threshold:

```
 hit(point) = TRUE   iff   ∃ cell ∈ window(point, r) : depth(cell) ≥ τ
 τ = 0.10 m (depth threshold)        r = 50 m (hit radius)
```

The window is the pixel box `±⌈r/res⌉` cells about the point (at 30 m, `r = 50 m → ±2`
cells), and the test is `≥ τ` over finite cells in that box. A point outside the raster,
or with no finite cells in its window, scores `FALSE` (a miss for a flood point, a
correct rejection for a dry point). The buffer absorbs geocoding/DEM co-registration
error; `τ = 0.10 m` is the nuisance-flood threshold.

#### 7.2 Skill metrics (`skill_scores`)

With `H` = hits among `P` flood positives and `F` = false-alarms among `N` dry controls:

```
 HR  (hit rate / sensitivity)         = H / P
 CRR (correct-reject rate / specificity) = (N − F) / N = 1 − F/N
 TSS (True Skill / Peirce statistic)  = HR + CRR − 1   ∈ [−1, 1]
```

`TSS = 0` is no skill (random/flood-everything/dry-everything); `TSS = 1` is perfect.
TSS is used because it is **prevalence-independent** and rewards specificity equally to
sensitivity — the **dry-control discipline**: inflating HR by flooding more area
immediately raises `F` and crashes CRR, so the gate cannot be gamed by over-prediction.
(Edge cases: empty positives → HR 0; empty negatives → CRR 1.)

#### 7.3 Confidence interval — stratified bootstrap (`bootstrap_tss_ci`)

The TSS uncertainty is a **stratified percentile bootstrap** (not analytic). Positives
and negatives are independent samples, so each of `n_boot = 10,000` iterations resamples
them **separately** with replacement and recomputes TSS:

```
 for b in 1..10000:
   HR*_b  = mean(resample(flood_hits, P))         # P draws with replacement
   CRR*_b = 1 − mean(resample(dry_hits, N))       # N draws with replacement
   TSS*_b = HR*_b + CRR*_b − 1
 CI_95 = [ quantile(TSS*, 0.025) , quantile(TSS*, 0.975) ]     # percentile method
```

Deterministic (`seed = 12345`). **Significant discriminative skill ⇔ the 95 % CI
excludes zero.** 

> **Reconciled (2026-06-22).** The implementation is a *stratified percentile* bootstrap
> (`np.quantile` on the resampled TSS) — there is no bias-correction `z₀` or acceleration
> `â` term, so it is **not** BCa. An earlier paper draft called it "BCa"; the manuscript
> (`safe2026-v5.tex`) now reads "stratified percentile bootstrap", matching the code and
> this section.

#### 7.4 Gate criteria

Two gate forms exist in the codebase:

- **Absolute PASS gate** (`evaluate_gate`, the headline) — pre-registered and stricter:

  ```
  PASS  ⇔  HR ≥ 0.70  AND  CRR ≥ 0.70          (--hr-floor, --crr-floor)
  ```

- **Baseline-margin gate** (`passes_numeric_gate`, for "beats the open-baseline"
  claims) — `HR ≥ floor` AND TSS exceeds every baseline's TSS by a margin (default
  0.20), tested with a **paired** stratified bootstrap (`bootstrap_tss_diff_ci`:
  resample one index set, apply to both classifiers, so shared sampling noise cancels)
  and a threshold-free **ROC-AUC** companion (`roc_auc` = Mann-Whitney `P(score_flood >
  score_dry)`, with `bootstrap_auc_diff_ci`).

**Present-day results** (RP100, ≥0.10 m, 50 m radius, expanded/frozen registers —
the **shipped post-retrofit atlas**, re-baselined 2026-07-12; Fisher = one-sided exact;
reproduce with `repro/reproduce_gate.sh`):

| City | pos/dry | HR | CRR | TSS [95% CI] | Fisher p | status |
|---|---|---|---|---|---|---|
| Jakarta | 33/12 | 0.85 | 0.92 | **0.77** [0.54, 0.94] | 4.5×10⁻⁶ | **PASS** |
| Kuala Lumpur | 31/12 | 0.71 | 0.92 | **0.63** [0.38, 0.84] | 2.6×10⁻⁴ | **PASS** (narrowest) |
| Singapore* | 38/20 | 0.71 | 0.90 | **0.61** [0.41, 0.79] | 7.9×10⁻⁶ | **PASS** |
| Bangkok† | 32/7 | 0.34 | 1.00 | 0.34 [0.19, 0.50] | 0.077 | positive, **not robustly significant** (see †) |

\* Singapore = hybrid bare-earth + main-stem fluvial + handfill pluvial.
† Bangkok's HR is bounded by the **out-of-domain** Chao Phraya catchment [R29] and sub-30 m
street flooding. Its skill is **not robustly significant**: the frozen 7-control stratum is
degenerate (7/7 correct → zero CRR variance, Fisher p = 0.077, marginal), and **expanding it
to 10 documented dry controls (2026-07-18) flips the result to TSS 0.24 [−0.02, 0.47],
Fisher p = 0.137 — CI crosses zero** (`docs/runs/2026-07-18-bangkok-control-expansion.md`).
The flip turns on one borderline riverside control (Grand Palace, transient ankle water in
2011 held dry by pumping). This **corroborates the SAFE abstract's "positive but marginal in
the fourth city"** — Bangkok is not counted among the three significant cities.
All of Singapore / KL / Jakarta clear the stricter PASS bar and are significant by the exact
test; Bangkok is the disclosed *structural* shortfall (§10), not a tuning failure.
The **Stage-1 (pre-retrofit)** gate — Jakarta 0.76/1.00/0.76, KL 0.65/1.00/0.65 —
lives in §6.3.5, where it is the evidence that selected each city's base solver.

---

## 8. Outputs & atlas structure

> **In plain terms.** What you actually download is a folder per city, per climate scenario,
> per severity. Inside each are image-like map files (GeoTIFFs) that open in any GIS tool —
> one per hazard, holding the water depth in metres for every 30-metre square — plus a
> "severity" version that bins those depths into classes, and a small spreadsheet summarising
> how much area flooded and how deep it got.
>
> One thing to know before comparing numbers: the summary spreadsheets count any cell with
> water at all, while the manuscript counts only cells at least 10 cm deep. The same map
> legitimately yields two different area figures. Neither is wrong — the depth files are the
> authoritative thing, and both numbers can be recomputed from them.

**Per-cell output directory:** `outputs/_fixed_atlas/<city>_<stem>_rp<rp>/`
(Bangkok adds a `_polder` sibling holding the polder-dried composite that is the
one scored/published). Inside, per hazard:

```
<cell>/<hazard>/rp_<rp>/<hazard>_depth_<scenario>_<horizon>_rp<rp>.tif   # depth (m)
<cell>/<hazard>/rp_<rp>/<hazard>_severity_<...>.tif                       # classed severity
<cell>/summary_<label>_<horizon>.csv                                      # per-hazard extent/stats
```

**Derived layers.**
- **Combined** = per-pixel **max** of coastal, fluvial, pluvial depth (computed for
  the maps in `_viz_*`; conceptually the screening layer).
- **Compound** = a joint-exceedance layer whose *footprint* is dependence-robust
  while its *depth* amplifies into the tail.

**Headline extents (shipped post-retrofit atlas, measured from the rasters
2026-07-17).** Present-day RP100, per hazard, **≥ 0.10 m** (the manuscript's reporting
convention; the shipped `summary_*.csv` count at the engine's `> 0` and therefore read
higher — the convention note ships in every Zenodo README), km²:

| City | Coastal | Fluvial | Pluvial |
|---|---|---|---|
| Singapore | 0.9 | 28.5 | 111.2 |
| Kuala Lumpur | — (inland) | 70.2 | 296.2 |
| Jakarta | 182.1 | 180.9 | 297.6 |
| Bangkok (polder composite) | 68.0 | 349.1 | 229.1 |

The canonical headline (paper Table 2) is **SSP5-8.5/2100 RP100**: Singapore 2/37/133,
KL 0/87/326, Bangkok 853/377/326, Jakarta 229/214/337 (coastal/fluvial/pluvial;
verified raster-to-table 2026-07-13).

- **Bathtub bias** (full model domain, SSP5-8.5/2100, same basis as Table 2): the
  connectivity bathtub over-predicts the inertial coastal extent by **1.2×** (Jakarta,
  229→283 km²) to **5.2×** (Bangkok, 853→4,432 km²). The inertial bars equal the Table 2
  coastal extents exactly. The defended-coast ratio is effectively unbounded at present-day
  (the dike holds the design surge, so the inertial footprint approaches zero), so the bias
  is reported at the 2100 horizon where both layers are substantial (§6.1.3). Earlier drafts
  clipped this comparison to the city admin boundary (7.6×/1.6×), which did not reconcile
  with the full-domain Table 2 extents and was dropped.
- **KL pluvial** 0→41.7 km² *(Stage-1; the fill-spill fix — the "0" was the raingrid-drain
  bug)* → **296** km² shipped (canal-HAND retrofit + closing, §6.3.5).
- **Singapore** fluvial 180→**28.5** km² (main-stem) + pluvial 15→95 *(Stage-1 handfill)*
  → **111** shipped (stage scaling + closing).
- **Mitigation delta:** meeting SSP2-4.5 rather than SSP5-8.5 avoids ≈**92** km² of
  Bangkok's 100-year coastal exposure by 2100.
- **Compound (Jakarta present RP100):** joint footprint 502.1 vs marginal 501.9 km²
  (dependence-robust; independence adds ≲0.2 km² in every city — KL exactly 0); depth
  amplification +0.10 m (RP100) → +1.47 m (RP1000, 90th pct +3.26 m). Re-derived
  2026-07-12 on the post-retrofit atlas (canal-HAND 07-04 + pluvial closing 07-07); the
  larger pluvial grew the marginal from 396.5 km² and diluted the RP1000 mean amp from
  +1.67 m (the earlier depth-capped value; +1.45 m pre-cap).

---

## 9. Reproducibility

**End-to-end rebuild.** `bash repro/run_atlas_fixed.sh` regenerates the full atlas
(60 cells). It is **resumable**: any `(city, stem, rp)` whose summary CSV already
exists is skipped, so an interrupted run continues where it stopped. It first
regenerates the cheap derived rasters (sea-mask frame-fix, seawall DEMs,
main-stem HANDs) idempotently, then runs the Stage-1 solve loop, then the **STAGE 2
post-solve chain** (canal-HAND applies → bridge-closing → summary/severity regen,
in that load-bearing order — §6.3.5), so one command reproduces the shipped product.

**Present-day RP100 fast slice.** `bash repro/run_fixed_coastal_rp100.sh` produces
just the present-day RP100 verification outputs (the visual/gate slice).

**Interpreter.** All runs use the Python 3.14 interpreter named in §2.

**Representative invocation** (Singapore, from the driver — flags verified against
`scripts/run_multihazard.py --help`, 2026-06-21):

```
python scripts/run_multihazard.py --dem dem/_diag/singapore_seawall.tif \
  --fluvial-hand-raster dem/_hand/singapore_hand_v3_mainstem.tif \
  --hazard-levels data/singapore/hazard_levels_<stem>_rp<rp>.csv \
  --scenario <label> --horizon <hz> --out-dir <out> \
  --coastal-solver inertial --coastal-msl-egm2008 1.1588 \
  --sea-mask-raster data/singapore/sea_mask_utm48n_framefix.tif \
  --tidal-channel-raster data/singapore/river_mask_utm48n.tif --tidal-burn-elevation 2.0 \
  --pluvial-model handfill --pluvial-hand-raster dem/_hand/singapore_hand_v3_hybrid.tif \
  --pluvial-hand-stage 1.5 --pluvial-hand-stage-baseline 0.069602 --pluvial-depth-cap 0.5 \
  --runoff-coeff-raster data/singapore/runoff_coeff_utm48n.tif --runoff-coeff 0.75 \
  --fluvial-bankfull-rp 0
```

All flags above are confirmed present. `--clamp-negative-land` is a
boolean-optional action, so `--no-clamp-negative-land` (used for Jakarta/Bangkok)
is its negation.

**Other notable flags** (`run_multihazard.py --help`), for tuning the solvers:
- Coastal/inertial: `--coastal-seed-latlon`, `--seed-water-raster`,
  `--inertial-dt-max`, `--inertial-t-end`, `--inertial-convergence-tol`,
  `--manning-raster`, `--connectivity-neighbors`.
- Pluvial/rain: `--pluvial-dem-raster`, `--rain-storm-hours`, `--rain-total-hours`,
  `--drain-conveyance-m-s`, `--raingrid-workers`.
- Fluvial: `--major-river-raster`.
- Scope: `--only-hazard-types` (e.g. `fluvial,pluvial` for inland KL).

---

## 10. Limitations & known issues

> **In plain terms.** This is a *screening* tool. It is built to tell you which places and
> which scenarios deserve a closer look — not to size a flood wall, settle an insurance claim,
> or design a building. Three limits matter most for anyone using it without reading the rest
> of this document.
>
> It cannot see flooding driven from outside the mapped area, which is why Bangkok's score is
> capped: the river that flooded it in 2011 rises well upstream of the map's edge. It cannot
> see flooding smaller than 30 metres across, which is most street-corner flash flooding. And
> it reports a *plausible* severity, not a range — we have not carried the uncertainty in the
> input data through to the maps, so treat the depths as an upper-bound screen rather than a
> best estimate with error bars.
>
> Everything below is reported rather than quietly fixed. Several items are things our own
> adversarial reviews found and we chose to disclose.

1. **Bangkok hit-rate is forcing-bounded, not terrain-bounded.** Accurate terrain
   cannot manufacture skill the forcing domain withholds: Bangkok's HR (0.34) is
   capped by the out-of-domain Chao Phraya mega-river [R29] and by sub-30 m street
   flooding. More accurate terrain helps a flood screen only *conditionally*.

2. **KL pluvial is resolution-bounded and looks spotty.** KL's flash floods are
   sub-grid; `fillspill` on steep terrain ponds in ~12,000 tiny disconnected pits.
   It is retained because it is gate-optimal (perfect CRR), but the map reads as
   speckle — an honest artifact of representing sub-grid flash floods at 30 m, not
   a model error.

3. **Handfill `stage` — gate-selected base; now standards-bracketed, with a measured
   held-out bound.** The Singapore (1.5 m) and Jakarta (2.5 m) *base* stages were chosen
   from the gate trade-off, which brushes against the "never tune to the gate" principle.
   Two mitigations executed 2026-07-18 (review C7 follow-ups):
   - **Bracketing:** external standards bracket both values (SG 1.5 ∈ ≈[1.1, 2.0] m from
     PUB CoP drain geometry + freeboard + documented ponding; JKT 2.5 = top of the BNPB
     Jan-2020 0.2–2.5 m band) — the values are physically bounded, but the choice *within*
     the bracket saw the gate. Full derivation §6.3.2.
   - **Held-out event test (measured, logged, not re-tuned):** the 2024-10-15 DBKL
     flash-flood bulletin (10 roads absent from every register) scores **HR 0.30** at gate
     protocol (0.60 at road-scale 250 m radius) against the shipped layer —
     `docs/runs/2026-07-18-kl-held-out-event.md`. The register PASS is **register-class
     skill** (recurrent flood-prone localities); single-event road-bulletin generalisation
     is measured and bounded at 0.30, consistent with the sub-grid convective failure mode
     (item 2). Any per-event prediction claim must carry this number.
   Separately, the fixed stage made the layer **ignore the forcing** — resolved by the
   stage-scaling (§6.3.2), now passed directly by the driver's Stage-1 lines
   (`--pluvial-hand-stage-baseline`, 2026-07-17). [Residual: the within-bracket selection
   remains gate-visible — disclose in the paper's methods; the held-out number is the
   quantitative disclosure.]

4. **Uniform coastal crest is a simplification.** A single continuous crest per
   city is more conservative than documented per-segment crests; production should
   move to per-segment crests for realistic residual flooding behind defences.

5. **Jakarta coastal is real, not an artifact.** The persistent coastal depth is
   chronic below-sea-level subsidence; it should not be "corrected" away.

### 10.1 Adversarial methodology review — Round 3 (2026-07-09)

A third adversarial round ([full record](adversarial-review-2026-07-09.md)) challenged the
rationale behind every major methodological choice and the cross-city heterogeneity,
building on the two referee stress-tests (gate statistics; elevation-null and stage
sensitivity). Outcomes:

- **Four paper claims corrected in `ieee-kse2026.tex`** — most materially, the
  mitigation-delta mechanism: on the bare-earth atlas the connectivity bathtub *saturates*
  the flat Bangkok delta under both 2100 pathways (avoided area ≈35 km² vs the inertial
  92 km²), so it *washes out* the scenario signal rather than inflating it as the
  DSM-era-derived sentence claimed. Also fixed: the abstract's DSM-bias mechanism (the
  high bias **masks** documented flooding — measured bathtub extents are *larger* on bare
  earth — it does not drive over-prediction; the solver does), a stale pluvial-limitations
  sentence, and the KL pluvial union description.
- **Two "looks-wrong-but-isn't" audit traps documented:** `--fluvial-bankfull-rp 0` in the
  release script (bankfull subtraction is baked upstream in `fit_fluvial_glofas.py`;
  run-time 0 avoids double-subtraction), and Jakarta's pumped-polder rings existing in
  `apply_pumped_polder.py` but deliberately unapplied (Pluit/rob flooding is documented to
  defeat the pumps; Bangkok's 2011-proven pump core is the only drained polder — the
  asymmetry follows the evidence).
- **Heterogeneity register** (review §3): the per-city differences split into
  evidence-driven choices (terrain recipe, pump floor, canal pruning, IDF durations, depth
  caps — each with a documented anchor) and deliberately homogeneous simplifications
  (coastal Manning n = 0.06, the 3-1-2 h surge hydrograph) whose *uniformity* is the
  untested assumption.
- **Two OPEN sensitivity items** logged (not blocking): coastal n ∈ {0.03, 0.10} and
  t_end = 16 h bracket for Bangkok 2100; held-out-event validation of the canal-HAND
  layer remains the standing pre-submission recommendation (with item 3 above, the base-stage
  re-anchoring).

### 10.2 Addendum — Round-3 follow-ups closed (2026-07-18)

The three ranked follow-ups from the Round-3 review are now executed
([full record](adversarial-review-2026-07-18-addendum.md); held-out run in
[docs/runs/2026-07-18-kl-held-out-event.md](../runs/2026-07-18-kl-held-out-event.md)):

- **C6 (t_end):** measured — Bangkok-2100 inertial extent grows **+18 % at t_end = 16 h**,
  still not converged; 98.8 % of the added area is below the permanent SLR floor, so it is
  floor-fill propagation, not surge truncation. The 8 h extent is a lower bound; the durable
  (t_end-independent) bathtub over-prediction is the **above-floor 743 km²**, not the full
  8 h ratio. Two paper-side framing decisions logged (do not change any shipped number).
- **C5 (Manning), regime split:** the friction lever is **≈±6 % undefended (Jakarta)** but
  **≈±25–40 % on defended deltas (Bangkok:** n=0.03/0.06/0.10 → 1300/920/710 km²). The
  earlier "friction ~6 %" reassurance was undefended-only and is corrected.
- **C7 (held-out event):** the 2024-10-15 DBKL bulletin (10 held-out roads) scores
  **HR 0.30** at gate protocol — register skill is register-class, single-event
  generalisation is bounded (§10 item 3). Handfill base stages now standards-bracketed (§6.3.2).
- **C13 (Bangkok degenerate control stratum):** expanding the 7-control stratum to 10
  documented dry controls flips Bangkok from bootstrap-significant to **TSS 0.24
  [−0.02, 0.47], Fisher p 0.077→0.137** — confirming the significance was stratum-fragile,
  and corroborating the paper's "positive but marginal" framing. Not re-tuned; the paper's
  frozen register is untouched (`docs/runs/2026-07-18-bangkok-control-expansion.md`). §7.4
  Bangkok row corrected to "not robustly significant".
- **C14 (KL IDF-duration sensitivity):** the KL gate is **byte-identical** across the
  design-depth bracket. Running the KL pluvial at RP100 excess 65 / 95 / 130 mm (spanning a
  1-hour-duration design to the current) moves the base fill-spill extent only −22 % at the
  1-hour end (29.4 vs 37.9 km²) and the shipped-dominant canal-HAND extent only
  **−5.4 %/+10 %** (246 / 260 / 287 km²) — because the canal-HAND stage
  `clip(0.5·excess/0.095, 0.4, 2.5)` floor-clips at 0.40 m at the 1-hour end. Scored at gate
  protocol, the 1-hour end (stage 0.40, pluvial 68.5 km²) and the current design (stage 0.50,
  89.5 km²) give **identical HR 0.65 / CRR 0.92 / TSS 0.56** (no-closing basis; the closing
  lifts both equally to the shipped 0.71/0.92/0.63): the design-depth cut removes only the
  shallowest far-from-drain cells, which are neither documented flood streets nor dry
  controls. The IDF-duration choice is immaterial to KL's validation. (A definitive 1-hour
  refit still needs the MSMA station IDF coefficients, not in the repo; the bracket bounds
  the answer regardless.)

(See also `docs/limitations_register.md`.)

---

## 11. Appendices

### 11.1 Per-city configuration (from `repro/run_atlas_fixed.sh`)

| Param | Singapore | Jakarta | Bangkok | Kuala Lumpur |
|---|---|---|---|---|
| Flood DEM | `_diag/singapore_seawall` | `_diag/jakarta_seawall` | `_diag/bangkok_seawall` | `kl/dem_bareearth_kl_eth_present_conditioned` |
| Fluvial HAND | `singapore_hand_v3_mainstem` | `jakarta_hand_v3_mainstem` | `hand_trunk_v3_debiased` | `kl_hand_mainstem_v3eth` |
| Coastal solver | inertial | inertial | inertial | — (inland) |
| MSL-EGM2008 | 1.1588 | 0.9976 | 1.1785 | — |
| Sea-mask | `sea_mask_utm48n_framefix` | `sea_mask_utm48s_framefix` | `sea_mask_utm47n_framefix` | `sea_mask_utm47n` |
| Pluvial model | handfill | handfill | fillspill | fillspill |
| Pluvial HAND / stage / cap | hybrid / 1.5 / 0.5 | `jakarta_hand_v3` / 2.5 / 1.0 | — / — / 3.0 | — / — / 3.0 |
| Handfill stage baseline (§6.3.2) | 0.069602 | 0.129999 | — | — |
| Runoff coeff | 0.75 | 0.80 | raster | 0.75 |
| Coastal crest (m MSL) | +3.0 | +2.0 | +2.10 | — |
| Polder post-process | — | — | yes | — |
| Hazards | coastal+fluvial+pluvial | coastal+fluvial+pluvial | coastal+fluvial+pluvial | fluvial+pluvial |

### 11.2 Glossary (plain-language)

Everyday definitions of the terms and symbols used above, grouped by topic. Where a term
also has a precise technical meaning, the section that defines it rigorously is noted.

**The three flood types ("hazards").**
- **Coastal flooding** — the sea coming inland: high tide, plus a storm surge, plus
  long-term sea-level rise. (§6.1)
- **Fluvial flooding** — a river overflowing its banks. (§6.2)
- **Pluvial flooding** — rain falling faster than the ground and drains can carry it away,
  so it ponds in low spots or backs up beside drains. This is the "flash-flood" type that
  global products usually leave out, and it is the dominant hazard in three of our four
  cities. (§6.3)

**Terrain (the ground the water flows over).**
- **DEM** (Digital Elevation Model) — a grid of ground-height numbers, one per 30 m square.
  The single most important input, because water runs downhill.
- **DSM vs bare-earth DEM** — the raw satellite surface (**DSM**) includes the tops of
  buildings and trees; the **bare-earth** version strips those off to leave the true
  ground. We build our own bare-earth surface (§4) because buildings and trees would
  otherwise look like high, dry land and hide real floods.
- **Subsidence** — land slowly sinking, here mostly from groundwater pumping. North Jakarta
  sinks up to ~25 cm per year (locally 20–28), which matters as much as sea-level rise —
  a decade of it outweighs a century of AR6 sea-level rise at that spot. Bangkok now sinks
  1–2 cm per year, having historically reached ~12 cm per year before pumping controls.
  Only Jakarta and Bangkok get a subsidence correction, because only they have documented
  InSAR rates; Singapore and Kuala Lumpur have no comparable signal. (§5.4, §11.1)
- **HAND** (Height Above Nearest Drainage) — how high a spot sits above the nearest river
  or drain it flows to: 0 m means you are in the channel, a large value means you are
  safely above it. A natural "how flood-prone" ruler. *Main-stem* HAND measures height
  above the big river trunks only; *dense* HAND measures height above every small drain
  too. (§6.2)

**How the water is simulated ("solvers").**
- **Bathtub vs inertial** — two ways to spread the water. **Bathtub** instantly fills every
  connected low spot up to the water level, like a filling bath — fast, but it over-floods,
  because real water needs time and meets friction as it travels. **Inertial**
  (local-inertia shallow-water, Bates 2010) moves the water step by step with momentum and
  friction, so far-inland low ground the water cannot physically reach within a ~6-hour
  surge stays dry. We use inertial for the coast; the two can differ ~5x on a defended
  delta. (§6.1)
- **fill-spill vs handfill** — two ways to model rain ponding. **fill-spill** collects rain
  in closed basins and spills the overflow to the next basin downhill (suits flat,
  pit-dominated Bangkok). **handfill** floods the low land beside every drain (suits
  canal-dense cities where rain backs up along drains). Terrain sets the choice, and using
  the wrong one measurably lowers the trust score. (§6.3)
- **Manning's n** — one number for how rough the ground is, i.e. how much it slows moving
  water. Smooth pavement ~0.03, vegetated floodplain ~0.10; we use 0.06. Rougher ground =
  water spreads less far. (§6.1, §11.4)
- **Surge hydrograph** — the shape of a storm surge over time: how fast it rises, how long
  it holds at its peak, how it falls back. We use a generic 3 h-rise / 1 h-hold / 2 h-fall
  shape. (§6.1.2)
- **CFL / timestep** — a numerical safety rule: the simulation may only advance time in
  steps small enough that water never jumps more than one cell at once, or the maths becomes
  unstable. `CFL_ALPHA = 0.7` is that safety margin. (§6.1.1, §11.4)

**Design events and forcing (what drives the flood).**
- **Return period (RP)** — how rare an event is. "RP100" (100-year) means a severity with a
  1-in-100 chance of being exceeded in *any given year* — not "once every 100 years." We
  map RP10, RP100, and RP1000.
- **MSL / WSE / EGM2008** — **MSL** is mean sea level (the average the tide swings around);
  **WSE** is water-surface elevation (the actual height of the water surface at a moment);
  **EGM2008** is the global height reference (the "zero") every elevation is measured from.
- **GEV / Gumbel** — standard statistical curves describing how extremes (the biggest surge
  or heaviest rain of the year) get rarer as they get larger. We fit them to observed
  records to read off the RP100 severity. (§5.1, §5.3)
- **IDF** (Intensity-Duration-Frequency) — a country's official design-rainfall standard:
  how much rain falls in a given time span at a given return period. Anchoring to each
  national IDF closes a 28-62% gap that global rainfall data carries in this region. (§5.3)
- **Runoff coefficient** — the fraction of rain that runs off rather than soaking in. Paved
  city ~0.75-0.80; it scales rainfall into flood volume. (§5.3, §6.0)

**The trust test (validation).**
- **Hotspot register** — a frozen list of real places documented to flood (*positives*) and
  documented to stay dry (*controls*). Fixed before scoring, so the model cannot be quietly
  tuned to match it. (§7)
- **HR / CRR / TSS** — the three trust scores. **HR** (hit rate) = fraction of known flood
  spots the model floods (sensitivity). **CRR** (correct-reject rate) = fraction of known
  dry spots the model correctly leaves dry (specificity). **TSS** (true-skill statistic) =
  HR + CRR − 1, one number from −1 to 1 where 0 is no skill and 1 is perfect. (§7.2)
- **Significant vs PASS** — **significant** is the weaker bar (the model tells flood from dry
  better than chance); **PASS** is the stricter, pre-registered bar (HR and CRR both at
  least 0.70). Three of the four cities PASS. (§7.4)
- **Expanded register** — the larger frozen hotspot list behind the headline scores (vs a
  smaller base list).

**Other.**
- **Polder** — a low area kept dry by embankments and pumps. Bangkok's pumped city-centre
  polder is modelled as staying dry; Jakarta's flooding polders are not. (§6.1.5)
- **Frame-fix** — a fix that removes a data-border artefact from the sea-mask so the coastal
  solver does not flood inward from the edge of the map. (§4)

### 11.3 Script index (descriptions verified from each file's header, 2026-06-21)

- `scripts/run_multihazard.py` — the three-hazard solver + CLI.
- `scripts/validate_hotspots.py` — "Documented-hotspot validation — the primary
  gate (Plan 2)", generalised to a `--ci` bootstrap confidence interval.
- `scripts/_fix_coastal_seawall.py` — "Fix coastal over-prediction: burn a
  continuous coastline seawall crest into" the DEM.
- `scripts/_fix_sea_mask_frame.py` — "Fix spurious coastal edge-flooding: the
  build_sea_mask NaN-BFS sweeps the" nodata border into sea; strip it.
- `scripts/_fix_sg_mainstem_hand.py` — "Fix SG fluvial over-prediction: rebuild
  the Singapore HAND against a" main-stem drainage network.
- `scripts/_fix_jakarta_mainstem_hand.py` — "Jakarta main-stem HAND: rebuild HAND
  against a main-stem drainage network".
- `scripts/apply_pumped_polder.py` — "Apply a documented pumped-polder drainage
  floor to a present-day flood composite" (Bangkok).
- `scripts/_viz_make_maps_fixed.py` — "Leaflet flood-map of the FIXED present-day
  verification run (outputs/_fixed)".
- `repro/run_atlas_fixed.sh`, `repro/run_fixed_coastal_rp100.sh` — drivers.

### 11.4 Parameter register (every computing step)

Every numerical parameter in the model, grouped by computing step, with value, rationale,
and reference. DEM and forcing parameters are tabulated in §4.1 and §5.1–5.4; this register
covers the solver and gate constants. Source of truth: the module named in each section.

> **How to read this register (plain-language).** A "parameter" is a single number the
> model uses — think of it as one setting on a dial. Each row names the dial, gives the
> value we set it to, says why, and — in the last column — labels **where that number comes
> from** so you can judge how much to trust it. The label matters more than it looks: it
> separates numbers pinned to outside evidence (published science, official design
> standards, or values we measured from data) from numbers that are our own engineering
> judgement with no external source. One label, **GATE-SELECTED**, marks the honest weak
> spot — a value we chose while we could see how it moved the trust score. The whole point
> of labelling every number this way is that a reader can see, at a glance, which settings
> are anchored and which are judgement calls, rather than having to take the model on faith.

**Provenance classes.** Every parameter is explicitly classed, so that a reader can tell
what is anchored to external evidence from what is an engineering choice. A value with no
literature source says so — that is the honest statement of a screening assumption, and it
is what makes the assumption auditable rather than hidden:

| Class | In plain terms — how much is it anchored? | Meaning | Example |
|---|---|---|---|
| **LITERATURE** | Backed by published science | value (or its range) is taken from published, citable science | Manning `n = 0.06` ← Chow 1959 / Arcement & Schneider 1989 |
| **STANDARD** | Backed by an official design standard | value comes from a published national/engineering design standard | IDF anchors ← PUB / JPS-MSMA / TMD-RID / BMKG; defence crests |
| **MEASURED** | We derived it from real data (not the trust test) | value is fitted/derived from observed data *in this work*, never from the gate | `(b0, f)` ← held-out ICESat-2/GEDI; MSL offsets; GEV fits |
| **PHYSICAL/NUMERICAL** | A law of physics or a computing requirement | a physical constant or a scheme-stability requirement | `g`; CFL `α = 0.7` ← Bates 2010 |
| **SCREENING CHOICE** | Our judgement call, reasoned but unsourced | engineering judgment with a stated rationale but **no literature source**; the residual assumption class | depression filters; surge-hydrograph shape; velocity-head margin |
| **GATE-SELECTED** | Judgement call that saw the trust score — the disclosed weak spot | chosen with validation-gate visibility — **a disclosed weakness**, flagged for re-anchoring | handfill `stage` (§10 item 3) |

Where a SCREENING CHOICE has been sensitivity-tested, the measured range is given in its
row; where it has not, the row says so (these are the open items in §10.1's review).

**Coastal — inertial solver (`model/inertial_wave_model.py`, §6.1)**

*In plain terms: the settings for the coastal flood simulation — how the water flows (gravity,
roughness), how long the storm surge lasts, and the numerical safety limits that keep the
simulation stable. Most are physics or computing requirements, not free choices.*

| Param | Value | Rationale | Reference |
|---|---|---|---|
| `g` | 9.806 m s⁻² | standard gravity | **PHYSICAL** — constant |
| `CFL_ALPHA` | 0.7 | explicit-scheme Courant safety factor (<1); `Δt ≤ α·Δx/(√(gd)+\|u\|)` | **NUMERICAL** — Bates 2010 [R1] (stability requirement of the explicit scheme, not a free knob) |
| `MIN_DEPTH` | 1×10⁻³ m | dry-interface threshold (no flux below) | **NUMERICAL** — wetting/drying floor; 3 orders below the 0.10 m reporting threshold so it cannot affect extent |
| `n` (Manning) | 0.06 s·m^(−1/3), spatially uniform | urban/coastal floodplain roughness; developed-floodplain tables give 0.05–0.15, so 0.06 is a low-mid value | **LITERATURE** — Chow 1959 [R7] (standard n tables); Arcement & Schneider 1989 [R8] (USGS WSP 2339 floodplain-roughness guide). *Not* Bates 2010, which sources the solver, not the roughness. **Sensitivity measured, regime-dependent.** Undefended (C5, `repro/coastal_manning_sensitivity.sh`): n=0.06/0.08/0.10 → Jakarta present-RP100 182.1/177.1/171.1 km² (−6.1 % at 0.10), IoU 0.94. Defended (2026-07-18, `repro/coastal_c6_bracket.sh`): n=0.03/0.06/0.10 → Bangkok-2100 1300.0/919.9/710.2 km² (**+41 %/−23 %**) — behind a dike the extent *is* the overtopping run-out distance, so friction is first-order. **The lever is ≈±6 % undefended but ≈±25–40 % on defended deltas**; the shipped Bangkok cell uses the polder (removes the sensitive interior), and even n=0.03 stays ~3.4× below the bathtub. See the 2026-07-18 addendum |
| `dt_max` | 30 s | timestep ceiling; the adaptive CFL test reduces it further | **NUMERICAL** — ceiling only; CFL binds in practice |
| `t_end` | 8 h (`--inertial-t-end`) | must exceed the 6 h surge window so the peak is captured and the surface settles | **SCREENING CHOICE** — set from the hydrograph length (below). **Sensitivity measured 2026-07-18** (C6 closed, `repro/coastal_c6_bracket.sh`): Bangkok-2100 extent grows +18.1% at t_end=16 h and is still not converged; 98.8% of the added area is below the permanent SLR floor, so this is SLR-floor propagation (the 8 h extent is a lower bound on the floor equilibrium), not surge-peak truncation. See the 2026-07-18 addendum |
| `convergence_tol` | 1×10⁻³ m | early-stop on mean \|Δd\|; 100× below the 0.10 m reporting threshold | **NUMERICAL** — cannot move reported extent |
| `convergence_window` | 100 (disabled when SLR floor > 0) | forces the full surge simulation whenever a permanent floor exists | **NUMERICAL** — correctness guard, not a tuning knob |
| surge hydrograph | 3 h ramp / 1 h hold / 2 h recession, on the MSL+SLR floor | asymmetric ramp avoids dry-bed shock; recession stops at the floor to preserve the permanent SLR signal | **SCREENING CHOICE — synthetic shape, no literature source.** A real surge hydrograph is site- and storm-specific; this is a generic design envelope. The *peak* (which sets extent) is forced by `water_level_m`; the shape affects only how long the peak is held. *Duration sensitivity untested* (review item C6, §10.1) |
| physical cap | (peak_WSE − **bed**) + 0.2 m | strips inlet wave-amplification; 0.2 ≈ ½v²/g at v = 2 m s⁻¹ | SCREENING CHOICE (velocity-head margin from first principles). **Fixed 2026-06-24**: was `max(0,bed)`, which under-capped below-MSL depth on subsided coasts; Jakarta coastal re-solved (§6.1.1) |
| crop pad | 32 cells | solver-bbox buffer | performance |

**Fluvial — HAND (`flood_depth_model.flood_depth_hand`, §6.2)**

*In plain terms: how the river-flood layer decides which land counts as "near the river." The
accumulation threshold sets how big a channel must be to count as a real river trunk (rather
than a small drain), so the flood is tied to the main river, not to every ditch.*

| Param | Value | Rationale | Reference |
|---|---|---|---|
| accumulation threshold | ≥50 km² (SG, JKT); ≥180 km² (KL, Klang trunk) | main-stem trunk, not dense canals | HAND [R2,R3]; this work |
| `--fluvial-bankfull-rp` | 0 (production) | full design stage mapped via HAND (no overbank subtraction) | this work |
| channel mask | channel cells → 0 | conveyance ≠ inundation | this work |

**Pluvial — fill-spill cascade (`model/pluvial_model.py`, §6.3.1)**

*In plain terms: the rain-ponding model's rules for what counts as a real basin that collects
water — deep enough to not be noise, shallow/small enough to not be a quarry or lake — and how
deep ponding is allowed to get. These are judgement calls, each with a stated reason.*

| Param | Value | Rationale | Reference |
|---|---|---|---|
| `WET_THRESHOLD_M` | 0.05 m | cells shallower are set dry | **SCREENING CHOICE** — below the 0.10 m reporting threshold, so it cannot move reported extent |
| `MIN_DEPRESSION_DEPTH_M` | 0.5 m | reject depressions shallower than the DEM's own noise as spurious | **SCREENING CHOICE — no literature source.** Rationale: GLO-30's local (cell-to-cell) vertical noise makes sub-0.5 m "basins" indistinguishable from DSM artefact. *Swept 0.4–0.8 m in the v5 country work: every level that de-speckles loses a documented hotspot somewhere — no threshold separates noise from signal, so the data raster is left pristine and speckle is handled at display level* |
| `MAX_DEPRESSION_DEPTH_M` | 3.0 m | exclude quarries/valleys/reservoirs — not urban rain ponding | **SCREENING CHOICE — no literature source.** Rationale: a >3 m closed basin is a landform or waterbody, not a street-scale ponding site; excluded like the sea |
| `MIN_DEPRESSION_AREA_CELLS` | 9 (≈0.8 ha) | drop sub-pixel inter-building voids | **SCREENING CHOICE** — resolvability argument: <9 cells at 30 m is at/below the DSM's ability to define a basin |
| depth cap | 3.0 m (BKK, KL) | upper bound on ponded depth | **SCREENING CHOICE — no literature source.** A life-safety/plausibility bound on a steady-state model that has no outlet timing; binds rarely |
| depression fill | pysheds (priority-flood family) | hydrological conditioning | Wang & Liu 2006 [R19] / pysheds [R27]; cascade after Barnes 2021 [R4] *(paper cites Planchon–Darboux [R18] — reconcile)* |

**Pluvial — handfill (`flood_depth_hand` on dense HAND, §6.3.2)**

*In plain terms: the rain-flood model for canal-dense cities — how high rain pools beside the
drains (the "stage"), how that pooling scales up with bigger storms, and a cap on how deep it
can get. The stage is the one setting that saw the trust score, so it is flagged and
standards-bracketed rather than presented as externally fixed.*

| Param | Value | Rationale | Reference |
|---|---|---|---|
| `--pluvial-hand-stage` | 1.5 m (SG), 2.5 m (JKT) | rain-pool extent above drainage (base, present-RP100) | **GATE-SELECTED within a standards-bracketed range** (2026-07-18, §6.3.2): SG 1.5 ∈ ≈[1.1, 2.0] m (PUB CoP drain depths + 15 % freeboard + documented 0.07–0.76 m ponding); JKT 2.5 = top of BNPB Jan-2020 0.2–2.5 m depth band. Held-out single-event HR 0.30 (§10 item 3) |
| `--pluvial-hand-stage-baseline` | 0.0696 (SG), 0.1300 (JKT) | present-RP100 excess; enables RP/climate stage scaling `stage×clip(level/baseline,0.4,2.5)` | this work, 2026-06-22 (§6.3.2) |
| `--pluvial-depth-cap` | 0.5 m (SG), 1.0 m (JKT) | documented flash-flood depth bound | flash-flood records |
| near-channel mask | HAND < 0.05 m, + river_mask → 0 | channels = conveyance | this work |

**Pluvial — raingrid (alternative, `model/pluvial_rain_model.py`, §6.3.3)**

*In plain terms: an alternative, more physical rain model (not used in the shipped atlas) —
how long the storm runs and how rough the ground is. Listed for completeness.*

| Param | Value | Rationale | Reference |
|---|---|---|---|
| storm_duration | 3600 s (1 h) | matches 1 h IDF parameterisation | [R23] |
| total_duration | 5400 s (1.5 h) | storm + settling to capture peak | this work |
| Manning `n` | clip(0.11 − 0.08·C, 0.03, 0.10) | land-cover-derived roughness | this work |
| denoise min_cluster | 6 cells (≈0.5 ha) | drop ponding speckle | this work |
| depth floor | 0.05 m | strip sub-threshold sheet | this work |

**Validation gate (`scripts/hotspot_scoring.py`, §7)**

*In plain terms: the scoring rules for the trust test — how deep water must be to count as
"flooded" (0.10 m), how close a prediction must land to a real flood site to count as a hit
(50 m), and the pass mark. All fixed before scoring, which is what makes the test honest.*

| Param | Value | Rationale | Reference |
|---|---|---|---|
| depth threshold `τ` | 0.10 m | a cell counts as "flooded" at ≥0.10 m | **SCREENING CHOICE — no literature source.** Rationale: below ~0.1 m the depth is within model/DEM noise and is not damaging; 0.1 m is also the conventional minimum mapped depth in global flood-hazard products. **Pre-registered before scoring** and applied identically to every city/RP |
| hit radius `r` | 50 m → ±2 px **square** window at 30 m | absorbs geocoding + co-registration error (§7.1) | **SCREENING CHOICE**, anchored to an external quantity: Nominatim geocoding precision (~one city block). **Fixed before scoring and never varied to move a verdict** — this is the discipline that matters more than the value |
| `n_boot` | 10,000 | stable percentile CI | **LITERATURE** — Efron & Tibshirani [R25] |
| `seed` | 12345 | deterministic reproducibility | **NUMERICAL** — any fixed seed; stated so results are bit-reproducible |
| PASS | HR ≥ 0.70 ∧ CRR ≥ 0.70 ∧ TSS CI > 0 | pre-registered joint sensitivity/specificity bar | **SCREENING CHOICE (pre-registered)** — 0.70 is a conventional "useful skill" bar, not a derived constant; fixed *before* scoring, which is what makes it a gate rather than a fit. TSS = Peirce [R24]. Exact one-sided Fisher p reported alongside (the bootstrap flatters an all-correct control stratum) |
| baseline margin | 0.20 | "beats open baseline" gate | **SCREENING CHOICE** — pre-registered margin |

---

## 12. References

Most entries match the manuscript bibliography (`docs/paper/safe2026-v5.tex`). Entries
marked **[verify]** are tool/product citations I did not confirm to an exact reference.

- **[R1]** Bates, Horritt & Fewtrell (2010), *A simple inertial formulation of the shallow water equations*, J. Hydrol. 387:33–45.
- **[R2]** Nobre et al. (2011), *Height Above the Nearest Drainage*, J. Hydrol. 404:13–29.
- **[R3]** Rennó et al. (2008), *HAND, a new terrain descriptor… SRTM-DEM*, Remote Sens. Environ. 112:3469–3481.
- **[R4]** Barnes, Callaghan & Wickert (2021), *Computing water flow through complex landscapes — Part 3: Fill–Spill–Merge*, Earth Surf. Dynam. 9:105–121.
- **[R5]** Lenderink et al. (2017), *Super-Clausius–Clapeyron scaling of extreme hourly convective precipitation*, J. Climate 30:6037–6052.
- **[R6]** IPCC AR6 WGI / Fox-Kemper et al. (2021), *Ocean, Cryosphere and Sea Level Change*.
- **[R7]** Chow, V.T. (1959), *Open-Channel Hydraulics*, McGraw-Hill — standard Manning's n tables; developed/urban overbank n ≈ 0.05–0.15.
- **[R8]** Arcement & Schneider (1989), *Guide for Selecting Manning's Roughness Coefficients for Natural Channels and Flood Plains*, USGS Water-Supply Paper 2339 — the standard floodplain-roughness selection guide.
- **[R9]** Muis et al. (2016), *A global reanalysis of storm surges and extreme sea levels*, Nat. Commun. 7:11969.
- **[R10]** Muis et al. (2020), *A high-resolution global dataset of extreme sea levels…*, Front. Mar. Sci. 7:263.
- **[R11]** Hawker et al. (2022), *A 30 m global map of elevation with forests and buildings removed (FABDEM)*, Environ. Res. Lett. 17:024016.
- **[R12]** Lang et al. (2023), *A high-resolution canopy height model of the Earth*, Nat. Ecol. Evol. 7:1778–1789.
- **[R13]** Sirko et al. (2021), *Continental-scale building detection… (Google Open Buildings)*, arXiv:2107.12283.
- **[R14]** Neuenschwander & Pitts (2019), *The ATL08 land and vegetation product for ICESat-2*, Remote Sens. Environ. 221:247–259.
- **[R15]** Dubayah et al. (2020), *The Global Ecosystem Dynamics Investigation (GEDI)*, Sci. Remote Sens. 1:100002.
- **[R16]** Zanaga et al. (2022), *ESA WorldCover 10 m 2021 v200*, Zenodo doi:10.5281/zenodo.7254221.
- **[R17]** ESA & Airbus (2022), *Copernicus DEM GLO-30*, doi:10.5270/ESA-c5d3d65.
- **[R18]** Planchon & Darboux (2002), *A fast, simple and versatile algorithm to fill the depressions of DEMs*, Catena 46:159–176.
- **[R19]** Wang & Liu (2006), *An efficient method for identifying and filling surface depressions* (priority-flood family) — **[verify: confirm pysheds' exact fill algorithm]**.
- **[R20]** Chaussard et al. (2013), *Sinking cities in Indonesia*, Remote Sens. Environ. 128:150–161.
- **[R21]** Abidin et al. (2011), *Land subsidence of Jakarta…*, Nat. Hazards 59:1753–1771.
- **[R22]** Phien-wej, Giao & Nutalaya (2006), *Land subsidence in Bangkok, Thailand*, Eng. Geol. 82:187–201.
- **[R23]** National IDF / drainage standards: PUB (Singapore), JPS-MSMA (Malaysia), TMD-RID (Thailand), BMKG (Indonesia).
- **[R24]** Peirce (1884), *The numerical measure of the success of predictions*, Science 4:453–454 (true-skill / Peirce skill statistic).
- **[R25]** Efron & Tibshirani (1993), *An Introduction to the Bootstrap*, Chapman & Hall.
- **[R26]** Manning (1891), *On the flow of water in open channels and pipes*, Trans. ICE Ireland.
- **[R27]** pysheds (M. Bartos), simplified flow-modelling library — **[verify exact citation/version]**.
- **[R28]** Pronk, Hooijer, Eilander et al. (2024), *DeltaDTM: A global coastal digital terrain model*, Sci. Data 11:273, doi:10.1038/s41597-024-03091-9 (Singapore hybrid low terrain).
- **[R29]** Komori et al. (2012), *Characteristics of the 2011 Chao Phraya River flood*, Hydrol. Res. Lett. 6:41–46.
- **[R30]** Alfieri et al. (2018), *A global network for operational flood risk reduction (GloFAS)*, Environ. Sci. Policy 84:149–158.

*(Numbering note, 2026-07-17: [R7]/[R8] were each accidentally assigned twice; Alfieri
moved to [R30] and the orphaned T_TIDE entry (Pawlowicz 2002) was removed — the coastal
forcing is de-meaned annual-maximum total water level, never harmonically de-tided, so
T_TIDE is not used anywhere in the pipeline.)*
