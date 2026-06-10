# HANDOFF — ASEAN Flood-Risk Model (forked product line)

> **Purpose of this file.** This repo is a clean-slate fork from a ~2-month research
> repo. This document is the deep context the research history would otherwise carry.
> A fresh agent should read this once, then work from the code + validators — not from
> memory of the old repo. Keep this file updated as decisions are made.

Last updated: 2026-05-31. Fork commit: `7cc7952`.

---

## 1. Goal

A **commercial** product: open-data multi-hazard (coastal / fluvial / pluvial) flood
maps for ASEAN capitals — Singapore, Jakarta, Bangkok, Manila, Ho Chi Minh City,
Kuala Lumpur — at a quality a **bank or insurer** would accept. Built **incrementally**
(Singapore first). All inputs must be **commercial-safe**:

| Input | Source | License |
|---|---|---|
| DEM (surface) | Copernicus GLO-30 DSM | open, commercial-OK |
| Buildings | Google Open Buildings v3 | CC BY-4.0 |
| Land cover | ESA WorldCover | CC BY-4.0 |
| Rainfall | ERA5 / ERA5-Land | Copernicus, commercial-OK |
| River discharge | GLOFAS | Copernicus |
| Sea level | AR6 SLR projections, UHSLC/GESLA tide gauges | open |

**FABDEM is excluded** (CC BY-NC-SA — non-commercial). Bare-earth DEM is built DIY:
Open Buildings footprints → flag building cells → IDW infill → hydro-condition. See
`scripts/build_bareearth_dem.py`, `scripts/build_conditioned_dem.py`.

---

## 2. Why this fork exists — the process reset (READ THIS)

The previous repo spent ~2 months in an **eyeball-driven loop**: each modeling round,
some output "looked wrong" → tweak → something new looked wrong. Root cause: **no
objective definition of "done."** Success was the operator's eye, which is an infinite
loop because real flood maps also look weird (canals appear underground, flat deltas
get shallow sheets, low-RP coastlines barely flood).

**This fork is a reset on PROCESS, not a model rewrite. The rules:**

1. **"Done" is a number, not a feeling.** Every model decision is anchored to a
   documented fact — a drainage design standard, a local IDF curve, a known historical
   flood hotspot, or an observed event extent — **never** to visual plausibility.
2. **Validate against observed events.** A harness already exists (§4). Use it.
3. **Simplest model that passes is the default.** Bathtub coastal, HAND fluvial,
   rain-on-grid pluvial. Add complexity (local-inertial solver) **only where validation
   demonstrably requires it.** The inertial-with-floor hybrid (§9) is the cautionary
   tale: weeks spent gold-plating a solver on a DEM whose vertical error exceeds the
   depths being resolved.
4. If you're about to tweak because something "looks off" — **stop**, and tie it to a
   documented fact or a validation number instead.

---

## 3. The thesis (what makes it sellable / publishable)

**NOT** "better than Fathom/JBA everywhere" — not credible. They wrote the inertial
solver (Bates et al. 2010), built FABDEM, and validate globally.

**The defensible claim:** for *specific* cities, a **city-calibrated open model beats a
generic global vendor at capturing locally-documented flood behavior**, because it
encodes local drainage standards, local rainfall statistics, and local infrastructure
the global vendors omit by design.

This is a **comparative** claim → meaningless without a common yardstick → **validation
is mandatory, not optional.** The sellable sentence looks like: *"our model flags 8/10
documented PUB hotspots; the generic global model flags 4/10."*

**City-specific tweaking is legitimate IFF anchored to a documented fact** (a drain
capacity, an IDF curve, a hotspot). Anchored to the eyeball, it's the loop. Same
activity, opposite outcomes.

---

## 4. The validation harness (already built — use it first)

### Observed-event data — `data/<city>/flood_obs/`
| Event | City | Source | Type |
|---|---|---|---|
| `THA2011` | Bangkok | Dartmouth Flood Observatory (`DFO_3850`) | extent raster |
| `JKT2020` | Jakarta | ARIA-SG / Sentinel-1 SAR (EOS-ARIA) | extent vector |
| `MYS2021` | KL | Copernicus GFM SAR ensemble + UNOSAT | extent raster/vector |
| `PHL2009` | Manila (Ondoy) | COSMO-SkyMed (ITHACA) | extent vector |

### Validators — `scripts/validate_*.py`
- `validate_historical_events.py` — rasterizes observed polygons to DEM grid, sweeps
  (hazard, RP), reports **CSI / Hit-rate / FAR** with WARN/FAIL gates. Configured events:
  `JKT2020`, `MYS2021`. Extent-based — works for fluvial/coastal mega-events.
- `validate_pluvial_singapore.py` — compares max ponding depth per RP to **PUB anchors**:
  `RP10 = 0.07 m` (lower observed), `RP1000 = 0.76 m` (upper observed), engineering cap.
  Gates monotonicity + RP1000 band. **This is the Singapore pluvial yardstick.**
- `validate_hwm_points.py` — high-water-mark point validation.
- `validate_gev_against_nea_stations.py` — rainfall GEV fit vs NEA station stats.
- `validate_pluvial_idf_anchors.py`, `validate_fluvial_idf_anchors.py` — IDF anchoring.
- `validate_pluvial_all_cities.py`, `validate_fluvial_kl_dec2021.py`.

### Validation reality by hazard (IMPORTANT)
- **Singapore = urban flash-flood ponding**: small, transient, drains in hours.
  **SAR extent validation does NOT work.** Use: documented-hotspot hit-rate (PUB
  flood-prone lists + georeferenced news events — Orchard Rd / Liat Towers 2010-11
  ~0.3 m; Bukit Timah 2017) + point-depth sanity + cross-overlay vs free **WRI Aqueduct**.
- **Manila 2009 / Bangkok 2011 / Jakarta 2020 fluvial+coastal**: have SAR/EMS extent
  maps → compute real **CSI** there. These are where extent-based validation belongs.

---

## 5. Architecture & file map

```
model/
  flood_depth_model.py     # core depth/severity raster utilities
  hand_model.py            # HAND (Height Above Nearest Drainage) fluvial
  inertial_wave_model.py   # local-inertial shallow-water solver (Bates 2010) — run_inertial
  pluvial_model.py         # fill-spill depression-storage pluvial
  pluvial_rain_model.py    # rain-on-grid drainage-exceedance pluvial (the realistic one)
scripts/
  cities.py                # CityConfig registry — ALL per-city params live here
  run_city_pipeline.py     # end-to-end driver for one city (fetch→fit→DEM→route→viz)
  run_multihazard.py       # the hazard routing engine (coastal/fluvial/pluvial)
  build_bareearth_dem.py   # Open Buildings → bare-earth DTM
  build_conditioned_dem.py # hydro-conditioning (burn channels, fill noise pits)
  fetch_open_buildings.py  # Google Open Buildings v3 downloader (S2 L4 tiles)
  build_hand_raster.py, fit_fluvial_glofas.py, fetch_gesla_singapore.py, ...
  validate_*.py            # the harness (see §4)
tests/                     # pytest physics + unit tests
docs/                      # paper draft, methodology, superpowers specs/plans
data/<city>/               # per-city inputs + flood_obs + hazard CSVs
```

Regenerable (gitignored, NOT carried): `outputs/`, `cache/`, `logs/`.

---

## 6. Models & key constants

### Pluvial — two models exist
- **fill-spill** (`pluvial_model.py`): depression-storage. **Structurally wrong for
  Singapore** flash floods (which are drainage-exceedance ponding on OPEN low ground,
  not closed-depression storage). `MIN_DEPRESSION_AREA_CELLS = 9` guards DSM artefact pits.
- **rain-on-grid** (`pluvial_rain_model.py`): 2D local-inertial, per-cell face-averaged
  Manning's n, drainage-exceedance. `run_rain_on_grid(z, outlet_mask, net_rain_depth_m,
  n, storm_duration_s=3600, total_duration_s=5400)`. Post-process
  `denoise_min_cluster(depth, wet_threshold_m=0.05, min_cluster_cells=6)`.
  **This is the realistic mechanism for SG.** Select with `--pluvial-model raingrid`.

### Fluvial — HAND
HAND model; fluvial output **masks channel cells** (`depth = where(river_mask, 0, depth)`)
because ~40% of raw flood = canal cells flooded on any overbank, and ~51% of off-channel
flood was >1 m below local terrain (engineered below-grade canal beds → "underground"
appearance). Fix committed in research repo; carried here.

### Coastal — bathtub vs inertial
- **bathtub**: WSE-vs-DEM fill. Default for the batch. Fast, defensible.
- **inertial**: `run_inertial` — physically richer but see §9 saga.
- **WSE = MSL + tide + surge + SLR.** Datum is **EGM2008**; per-city `msl_to_egm2008_offset`
  in cities.py (Singapore = 1.1588 m). SLR (AR6): Singapore SSP5-8.5 2100 = **0.674 m**.

### Physical depth cap (coastal)
`phys_cap = max(0, level_m − max(0, bed)) + 0.2 m` (velocity-head margin); `depth =
min(depth, phys_cap)`. Added to kill inertial blow-up artefacts.

---

## 7. Singapore config highlights (`scripts/cities.py`, the reference city)

- UTM 48N (`EPSG:32648`); ERA5 point 1.2903, 103.8519; tide gauge UHSLC 699 Tanjong
  Pagar (39-yr record).
- `drain_capacity_mm = 50.0` — **effective** network threshold (PUB CoP secondary-drain
  RP5 nominal = 70 mm/1h, but limiting tertiary tier ≈ RP2 ~40 mm/1h; 50 mm chosen so
  ponding onset starts ~RP5, matching Orchard Rd 2010-11). Was 70, revised to 50.
- 1h IDF anchors: RP10 = 82 mm, RP100 = 120 mm (MSS/PUB). Gumbel μ=46 mm, σ=16 mm.
- `cn=85`, `runoff_coeff=0.75`, `mannings_n=0.040`, `catchment_km2=10`, `toc=0.5 h`.

---

## 8. Known issues & open threads (inherited from research repo)

1. **Manila pluvial is BROKEN (raingrid).** Summary shows ~1,820 km² wet at *every* RP
   with mean depth 1–10 cm — a domain-wide shallow sheet on the flat delta. The
   `wet_pixels`/`flooded_area` threshold used for raingrid output is effectively ~0–1 mm,
   not the 5 cm denoise threshold; the min-cluster denoise doesn't help because the sheet
   is spatially *continuous*, not speckle. **Fix direction:** depth-aware masking (strip
   <5 cm before counting/clustering) + align wet-threshold to denoise threshold. The
   solver itself is fine (real ponds reach 11 m). KL raingrid looks coherent by contrast
   (steeper terrain drains). *Do not trust Manila pluvial numbers until fixed.*
2. **Jakarta sea-mask build crashes** on Windows (access violation `3221225794` in
   `build_sea_mask.py`) — likely memory at Jakarta's larger domain. Uninvestigated.
3. **Inertial-with-floor coastal hybrid** — the saga. Goal: preserve permanent SLR
   floor (0 m EGM2008 is *below* MSL 1.16 m, so a recede-to-0 hydrograph wrongly drains
   SLR). Asymmetric hydrograph (gentle 0→peak ramp, peak→floor recession) + forced
   run-to-t_end + physical cap got it *working* but slow (~30 min/RP warm-chained) and
   still produced ~2000 unphysical cells before the cap. **Recommendation: shelve inertial,
   use bathtub coastal until validation proves bathtub insufficient.** Task #38 (unstarted):
   add `min_t_for_convergence` to `run_inertial` so warm-chained RPs exit after surge
   passes (~6 h) instead of always 8 h.
4. **RP500 == RP1000** in some fluvial summaries (Manila) — saturation at the same flagged
   WSE; benign but note it.
5. **TaskStop does not propagate to git-bash children on Windows** — the overnight batch
   (`run_overnight_batch.sh`) kept iterating after stop; had to kill the bash PID directly.
   Prefer running cities one at a time, not via the bash loop, on Windows.

### State of the overnight batch (research repo, for reference)
Manila ✅ (but pluvial broken per #1), Jakarta ✗ (crash #2), KL partial (coastal/fluvial
done, pluvial incomplete), HCMC/Bangkok not done. **None of these outputs were carried**
into the fork (outputs/ is gitignored) — regenerate as needed.

---

## 9. How to run

```bash
# one city, end to end (Windows: run cities individually, not the .sh loop)
python scripts/run_city_pipeline.py --city singapore \
    --scenario SSP5-8.5 --horizon 2100 \
    --pluvial-model raingrid --coastal-solver bathtub

# reuse cached baselines
#   --no-fit-era5 --no-fit-coastal

# validate
python scripts/validate_pluvial_singapore.py --out-dir outputs/singapore_ssp585_2100
python scripts/validate_historical_events.py --event MYS2021

pytest tests/ -q
```

---

## 10. Recommended first move in this fork

**Do not write model code yet.** Use the brainstorming skill. First:
1. Read `validate_pluvial_singapore.py` + `validate_historical_events.py` and the
   `flood_obs/` data to ground in what's already validated and the current numbers.
2. Decide Singapore-first scope (which hazards) and the **numeric pass/fail target** that
   defines "done" and substantiates the better-than-generic claim.
3. Output a scoping spec (`docs/superpowers/specs/`) before any implementation.

Build the documented-hotspot anchor table for Singapore pluvial (PUB lists + georeferenced
news events, ~10–20 points, a couple with depths) — that's the cheapest high-leverage step
and the yardstick everything else hangs off.

---

## 11. Squaring visual review with validation

Visual coherence is a real requirement — a bank won't accept a map that looks broken, and
some failure modes (Manila's domain-wide 1 cm sheet) are caught faster by eye than by any
metric. The danger is not *looking*; it's letting the eye become the optimization target.
That is what produced the 2-month loop. Square it with these rules.

**Eyes open tickets, numbers close them.** Eyeballing may *veto* (reject a map outright) and
*raise questions*. It may **never** *accept* a map or be the thing you tune against.
Acceptance is the numeric gate. "It looks right" is never a pass. This asymmetry is what
gives the loop a fixed point.

**The conversion rule.** When your eye flags something, you may NOT just nudge a parameter
until the picture improves. You must convert the observation into one of two things:
1. **A documented expectation → a new validation check** (e.g. "coastal should reach >500 m
   inland on this reclaimed stretch" becomes a point/extent assertion). The intuition is now
   a number future runs are tested against; you never re-eyeball it.
2. **A logged known-limitation** here or in a limitations register (e.g. "canals appear
   below-grade because the DTM captures engineered canal beds — real, not a bug"). Now the
   model won't try to "fix" reality next pass.

Forbidden: tweak → look → tweak → look. No exit condition.

**Structured, not freeform.** Run a fixed visual-QA checklist at checkpoints, not continuous
staring:
- Monotonicity: area/depth grow with RP? (catches Manila-type bugs instantly)
- Mass plausibility: wet area a sane fraction of the domain at this RP?
- Hazard separation: coastal/fluvial/pluvial in sensible places (coast/rivers/low ground)?
- No domain-wide thin sheets; no speckle; no single-cell spikes after the cap.
- Known hotspots lit; known dry ground dry.
- Coastline behaves (low RP barely floods, high RP creeps inland).
A failed item opens a ticket (→ conversion rule). A passed checklist is a gate, not a tuning
session.

**Cadence.** Look only at defined gates: (1) after a numeric validation run *passes*, as the
final coherence veto before "done"; (2) when validation *fails*, to localize where/why. Not
after every parameter nudge.

**"Done" is a two-gate AND.** A map is done only when it passes BOTH:
- **Numeric gate** — validators pass (hotspot hit-rate / CSI / PUB depth band / monotonicity), AND
- **Visual gate** — the fixed QA checklist passes (binary plausibility veto).

Both necessary, neither sufficient. The numeric gate stops the loop; the visual gate keeps
the product presentable and catches what validation has no ground truth for.
