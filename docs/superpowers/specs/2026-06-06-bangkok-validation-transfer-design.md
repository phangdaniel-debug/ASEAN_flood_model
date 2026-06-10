# Bangkok Validation Transfer — Design Spec

**Date:** 2026-06-06
**Status:** approved (design)
**Goal:** Bring **Bangkok** to KL's validated standard, **validation-first**: build the
four-manifest contract + a documented-hotspot register, generalize the validation
harness for multi-city reuse, and run the documented-hotspot **HR / CRR / TSS** gate
against the *existing* Bangkok model (pluvial ∨ fluvial ∨ coastal), with the THA2011
extent-CSI as a supporting diagnostic. Let the gate reveal what to fix; do not pre-apply
KL-specific model changes.

---

## 1. Context

flood-v2.0 was seeded from flood-atlas, so Bangkok already has substantial infrastructure:
`data/bangkok/` has the Copernicus DEM (+ subsidence-corrected + defended variants), a
HAND raster, `hazard_baseline_template.csv` + scenario `hazard_levels_*.csv`, river/sea/
runoff masks, and `cities.py` configs (`bangkok` urban + `bangkok_chao_phraya` mainstem).
It also already has the **2011 megaflood reference raster**
(`data/bangkok/flood_obs/THA2011/DFO_3850_From_20110805_to_20120109.tif`, Dartmouth/
Cloud-to-Street MODIS) and an existing extent-CSI result (`validate_historical_events.py`:
THA2011 CSI 0.29 / H 0.90 / FAR 0.70, WARN — model catches 90% of observed flood but
over-predicts; the multi-month megaflood ≠ a steady-state design-RP snapshot).

**What Bangkok lacks** (the KL gold standard to transfer): the four-manifest contract, a
documented-hotspot register, and the HR/CRR/TSS hotspot gate.

**Bangkok advantages over KL:** (a) extent-CSI is viable (THA2011 raster) where KL's was
SAR-blind (#17); (b) the 2011 flood had a sharp **defended/undefended boundary** — the
bunded inner core (Silom/Sathorn/Sukhumvit) stayed dry while the northern/eastern suburbs
(Don Muang, Rangsit, Sai Mai, Nava Nakorn) flooded — giving **natural low-lying dry
controls**, so KL's #21 problem (low-lying negatives unsourceable) largely does not bite.

## 2. Scope

**In scope (this effort):** foundation + first validation run + honest verdict.
**Out of scope (deferred to evidence-driven follow-up plans):** the model fixes themselves
(main-stem HAND, fluvial bias, drainage densification, etc.) — applied only if/when the
gate evidence calls for them, each anchored to a documented fact, exactly as KL went
foundation → validation → fix-to-pass.

**City config:** `bangkok` (the primary urban config). `bangkok_chao_phraya` (mainstem
proxy) and the Greater-BKK composite are out of scope here.

## 3. Approach (chosen: validation-first on the existing model)

Build the gate, run it against the current Bangkok model, and let it reveal failures —
rather than pre-applying KL-specific fixes that may not fit a flat delta. Mirrors the KL
rhythm (Plan 1 foundation → Plan 2 validation → Plan 3+ fix-to-pass).

## 4. Components

### 4.1 Generalize the validator (DRY for multi-city)
- `scripts/validate_hotspots_kl.py` → `scripts/validate_hotspots.py` with a `--city <slug>`
  option. Reads `data/<slug>/manifest/hotspots.csv` via `load_hotspots_from_manifest(slug)`
  (already city-parameterized), discovers the city's output dir, combines its **available**
  hazards (pluvial ∨ fluvial ∨ coastal — whichever rasters exist), scores HR/CRR/TSS +
  bootstrap CI against the manifest gate floors. Reuses `hotspot_scoring` +
  `combine_hazard_depth` unchanged.
- Back-compat: keep `validate_hotspots_kl.py` working (either a thin wrapper that calls the
  generalized CLI with `--city kuala_lumpur`, or leave it and add the new general script;
  decided in the plan). KL's gate result must be unchanged (regression check).

### 4.2 Bangkok four-manifest contract
- `data/bangkok/manifest/{forcing_anchors,gates,observed_events,hotspots}.csv` following the
  KL schema enforced by `scripts/city_manifest.py` (`validate_manifest("bangkok")` passes).
  `gates.csv` carries the same HR/CRR floors (0.70) + TSS reporting as KL (Singapore
  methodology precedent).

### 4.3 Bangkok hotspot register (the key new, discipline-sensitive artifact)
- **Positives:** documented 2011-flood-inundated locations (Don Muang, Rangsit, Sai Mai,
  Nava Nakorn industrial estate, Bang Bua Thong, Pathum Thani fringe, etc.), sourced from
  2011-event records (academic/news/agency), geocoded via Nominatim, DEM-verified per #6b.
- **Dry controls:** documented-defended/spared areas that stayed dry in 2011 — the bunded
  inner core (Silom, Sathorn, Sukhumvit, the CBD) — a mix of the genuinely-low defended
  core (hard negatives, unlike KL) + any elevated controls. Model-blind: the dry label
  comes from documented non-flooding in 2011, never from the model's output.
- Built by a `scripts/build_bangkok_hotspot_register.py` (mirrors
  `build_kl_hotspot_register.py`: in-file candidate list with provenance, Nominatim geocode,
  DEM verification table, writes `data/bangkok/manifest/hotspots.csv`).
- Provenance recorded per spot. Target n ≥ ~15 positives + ~7 dry controls (KL parity),
  honestly scoped to whatever is defensibly documented.

### 4.4 Combined wet-mask (coastal included)
- The generalized combiner unions pluvial ∨ fluvial ∨ **coastal** at the scored RP. Coastal
  is included because Bangkok is a delta (the lower domain near the Gulf floods coastally);
  KL excluded it (inland, coastal = 0).

### 4.5 Run + validate
- Present-day baseline: the existing `outputs/bangkok_ssp585_2020/` (regenerate if absent or
  stale, using the existing `hazard_levels_ssp585_2020.csv` + the existing Bangkok model
  config — no model changes this round). The raingrid pluvial uses `--raingrid-workers`
  (the Plan-10 win) for speed; AR6 stays offline via the cache.
- Score at the **2011-event RP** (~RP100), carrying the documented caveat that GLoFAS calls
  2011 ~RP6 (ERA5 under-estimate) vs observed RP50-100 — the same fluvial-RP tension KL had;
  the gate may expose it.
- Supporting diagnostic: the existing THA2011 extent-CSI / H / FAR (`validate_historical_events.py`).

### 4.6 Bangkok validation dossier
- `docs/superpowers/runs/2026-06-06-bangkok-validation-dossier.md`: scope/method, the
  numeric gate table (HR/CRR/TSS + CI), the THA2011 CSI support, per-spot diagnostics, and
  an **honest verdict** (PASS / marginal / FAIL-with-diagnosed-causes). Whatever the gate
  shows is the result; fixes are the next plans.

## 5. Data flow

```
2011 records (model-blind) → build_bangkok_hotspot_register.py (geocode + DEM-verify)
  → data/bangkok/manifest/hotspots.csv (+ the other 3 manifests)
  → existing Bangkok model rasters (pluvial∨fluvial∨coastal, present-day)
  → validate_hotspots.py --city bangkok → HR/CRR/TSS + CI
  → + THA2011 extent-CSI (support) → Bangkok validation dossier + verdict
```

## 6. Testing

- **Manifest:** `validate_manifest("bangkok")` returns no problems (columns + non-empty).
- **Generalized validator:** a regression test that `validate_hotspots.py --city kuala_lumpur`
  reproduces KL's current HR/CRR/TSS exactly (no behavioural change from the generalization).
- **Register builder:** pure-logic tests (≥15 positives, every spot has provenance; the
  DEM-verification flag works) without network (geocoding not unit-tested).
- **Loader:** `load_hotspots_from_manifest("bangkok")` maps positive→flood, dry→dry.
- Full suite stays green.

## 7. Success criteria

1. `data/bangkok/manifest/` complete + `validate_manifest("bangkok")` clean.
2. Bangkok hotspot register built model-blind with provenance (positives from 2011 records,
   dry controls from documented-defended areas), geocoded + DEM-verified.
3. `validate_hotspots.py --city bangkok` runs and reports HR/CRR/TSS + CI; KL regression
   unchanged.
4. THA2011 extent-CSI reported as support.
5. Bangkok validation dossier with an honest verdict; fixes (if needed) enumerated for
   follow-on plans.

## 8. Risks

- **Geocoding precision** (Nominatim ~city-block) — same as KL; use the ~50 m hit-radius
  unless Bangkok's coarser district geography argues for a documented different value.
- **2011 megaflood vs design-RP mismatch** — a multi-month basin event is not a steady RP;
  the hotspot gate (point-based) is more robust to this than extent-CSI, which is why
  hotspots are primary and CSI is support.
- **Stale/absent present-day Bangkok rasters** — regenerate with the existing config (no
  model change) before validating; flag if the existing model has obvious issues.
- **Coastal inclusion** could over-flood the lower delta and falsely flood gulf-adjacent
  dry controls — if so, that's a real finding for the verdict (not hidden).
