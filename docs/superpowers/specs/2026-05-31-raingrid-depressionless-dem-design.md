# Raingrid De-Pitted DEM Fix — Design Spec

> Approach: **surgical** (Approach B) — fill only spurious/unphysically-deep
> depressions, preserve genuine shallow hollows. (Earlier draft considered a
> fully-depressionless DEM, Approach A; superseded.)

**Date:** 2026-05-31
**Status:** Approved (brainstorming → spec).
**Anchors:** `HANDOFF.md` §6 (no pluvial depth cap; drain_capacity handles sub-surface drainage); the pluvial-yardstick first-measurement result (2026-05-31); `docs/limitations_register.md` finding #8.

> Follow-on to the pluvial-yardstick milestone. The yardstick's first measured
> number FAILED numeric gates 1–2 because the rain-on-grid pluvial field blows up
> at high RP. This spec fixes the diagnosed root cause. Re-measurement against the
> existing harness — not tuning — decides success.

---

## 1. Problem (diagnosed, not assumed)

The first SSP5-8.5/2100 raingrid run produced physically impossible max ponding
depths and a non-monotonic depth–RP curve:

| RP | 2 | 5 | 10 | 25 | 50 | 100 | 200 | 500 | 1000 |
|---|---|---|---|---|---|---|---|---|---|
| max depth (m) | 0.17 | 1.5 | 2.0 | 3.8 | 5.2 | 13.2 | 27.8 | 7.4 | 8.6 |

`validate_pluvial_singapore.py` → FAIL (RP1000 above the 3.0 m engineering cap;
non-monotonic). RP2–10 are plausible; RP25+ blow up.

**Root cause (diagnosed):** the blow-up is localized — at RP50 only ~40 cells
exceed 3 m, in a handful of clusters; the bulk field and the *mean* wet depth
near hotspots (~0.11–0.15 m) are plausible. The deep cells sit in **enclosed
depressions** of the raingrid DEM. Inspection of the worst cell showed the raw
Copernicus DSM contains a **spurious deep hole** (pixels at −21 to −23 m, on land,
ringed by 12–25 m terrain). The conditioning step (`build_conditioned_dem.py`)
fills only *shallow* noise pits (< 0.5 m) and **deliberately keeps "real basins"**,
so it preserved this artifact (and ~2,013 other enclosed depressions, 164 deeper
than 5 m, the deepest 72 m). Rain-on-grid then accumulates water in every such
depression with no overland outlet, and — because raingrid has **no physical
depth cap** (unlike coastal, `HANDOFF.md` §6) — the inertial solver overshoots
the basin rim, producing the 5–28 m spikes that dominate the max-depth gate.

**Why the comparative TSS is largely unaffected:** the hotspot hit-test is binary
(any cell ≥ 0.10 m within 150 m). The pits are a few dozen isolated cells; the
0.80 hit-rate / 0.63 TSS reflect the broad field, not the spikes. So this fix
targets the depth-band / monotonicity failure; the comparative finding (model
0.63 vs Aqueduct 0.00 vs naive-TWI 0.47) stands and is re-confirmed, not created,
by the fix.

---

## 2. Fix — surgically de-pitted DEM for rain-on-grid only

One change, at the DEM layer. The solver, the fill-spill model, the coastal /
fluvial paths, the conditioned DEM, and all scoring parameters are untouched.
**Approach B (surgical):** fill only the spurious / unphysically-deep
depressions, preserving genuine shallow hollows so real flood-prone lows can
still pond.

### 2.1 What

Produce a **surgically de-pitted** DEM and feed it to rain-on-grid as
`--pluvial-dem-raster`, in place of `copernicus_dem_utm48n_conditioned.tif`.
Starting from the conditioned DEM (which already filled <0.5 m noise pits),
**fill an enclosed depression iff** it meets either documented criterion:

- **(a) Artifact floor:** the depression's minimum elevation is **< 0 m** on
  land — a sub-sea-level inland floor is an unambiguous Copernicus DSM hole
  (Singapore land sits above EGM2008 sea level; MSL itself is +1.16 m EGM2008).
- **(b) Unphysically deep:** the depression's **max depth ≥ 3.0 m** — the
  `validate_pluvial_singapore.py` engineering cap, documented as "depths above
  this are unrealistic for Singapore urban ponding." A closed surface depression
  that could hold >3 m of water cannot represent realistic SG ponding.

**Keep** depressions with floor ≥ 0 m **and** max depth in [0.5, 3.0) m — these
are plausible real hollows; rain-on-grid may pond them up to their rim, which is
within the gate's allowed band.

Both thresholds (0 m, 3.0 m) are documented anchors, governed by the
scope-spec §4.5 refinement discipline (refine only against a documented fact,
pre-registered, never to flip a verdict).

### 2.2 Where

- `scripts/build_conditioned_dem.py` already labels enclosed depressions and
  computes per-depression max depth for the shallow-pit classification
  (~lines 79–91), and has the fully-filled surface (`filled`). Extend it with an
  optional `--raingrid-out PATH` (+ `--deep-pit-depth-m`, default 3.0) that emits
  a variant where, in addition to the existing <0.5 m noise fill, depressions
  meeting criterion (a) or (b) are set to the filled (spill) elevation, then
  flats resolved for routing. Output e.g. `copernicus_dem_utm48n_raingrid.tif`.
  The existing `_conditioned.tif` output is unchanged.
- `scripts/run_city_pipeline.py` (Singapore branch): when building the
  conditioned DEM, also request the raingrid output, and set `pluvial_dem_raster`
  to it (raingrid only). Coastal/fluvial DEMs unchanged.

### 2.3 Why this is anchored (not a hack)

- Filling **only** artifact/unphysical depressions removes the blow-up source
  (the −23 m DSM hole and the 164 basins deeper than 5 m) without flattening
  genuine shallow flood-prone hollows.
- Both fill criteria are tied to **documented facts** — EGM2008 sea level and the
  validator's 3.0 m engineering cap — not to a number chosen to make the gate
  pass.
- Real Singapore depressions that *are* kept drain in reality via the storm-drain
  network, already represented by subtracting `drain_capacity_mm` upfront
  (`HANDOFF.md` §7); keeping them bounded by their rim (<3 m) is consistent with
  that, while the unbounded artifact traps are removed.

### 2.4 What is preserved

Genuine shallow hollows (<3 m, above sea level) remain, so real flood-prone low
ground still ponds; and transient flat-ground ponding — the SG flash-flood
mechanism (`pluvial_rain_model.py` docstring) — still arises from the inertial
dynamics during the storm. Only the artifact / unphysically-deep traps that
caused the blow-up are removed.

---

## 3. Acceptance — numbers decide, then eyes (two-gate AND)

The fix is "done" only when re-measured against the existing harness. No tuning.

1. **Gate 1–2 (must now PASS)** — `validate_pluvial_singapore.py`:
   max ponding monotonically non-decreasing with RP, and RP1000 in
   [0.38, 3.0] m. This is the gate the blow-up fails today.
2. **Gate 3–4 (re-measure, must NOT regress)** —
   `validate_pluvial_hotspots_singapore.py` at RP50: hotspot **hit-rate ≥ 0.70**
   (currently 0.80). Preserving shallow hollows is intended to protect hit-rate;
   confirm it does.

   **Escalation, not tuning:** if gates 1–2 still fail after the surgical fill
   (e.g. kept ≤3 m basins still let the cap-free solver overshoot their rim, or
   monotonicity still breaks), the documented next step is to *lower the
   `--deep-pit-depth-m` threshold toward observed* (pre-registered in §4.5) or,
   failing that, escalate to the fully-depressionless Approach A. Each escalation
   is a documented, pre-registered change re-measured against the harness — never
   a tweak-look-tweak loop.
3. **Visual gate (§11)** — only after the numeric gates pass: no domain-wide thin
   sheet, monotone area/depth growth, hotspots lit / dry ground dry, no
   single-cell spikes.

### 3.1 Tests (TDD)

- Unit: a synthetic DEM with (i) a sub-sea-level pit, (ii) a >3 m pit, and
  (iii) a shallow ~1 m above-sea-level hollow yields a raingrid DEM where
  (i) and (ii) are raised to their spill level but (iii) is **preserved**.
- Unit: the emitted raingrid DEM has **no enclosed depression with floor < 0 m
  and none with max depth ≥ 3.0 m** (the two fill criteria are satisfied), while
  depressions in [0.5, 3.0) m above sea level may remain.
- Unit: non-depression terrain elevations are unchanged from the conditioned DEM.
- Regression: existing `tests/test_pluvial_rain.py` and the hotspot-scoring tests
  still pass.

---

## 4. Out of scope

- No physical depth cap on raingrid (the cause-fix was chosen over symptom
  suppression).
- No changes to the inertial solver, the fill-spill model, the `_conditioned.tif`
  output, or the coastal/fluvial hazards.
- No changes to scoring parameters (hit depth / radius / RP50 / TWI fraction) —
  those remain governed by the scope-spec §4.5 discipline.
- Re-running the comparative gate is for confirmation only; the gate-4 naive-TWI
  margin question (0.16 < 0.20) is a separate finding, not addressed here.

---

## 5. Definition of done

Re-run the pluvial-yardstick measurement (existing pipeline + the four checks)
on the surgically de-pitted raingrid DEM. Done when: gates 1–2 PASS, gate-3 hit-rate
≥ 0.70 (no regression), and the §11 visual checklist passes. Record the new
numbers in `docs/limitations_register.md` (resolve finding #8) and the scope-spec
§4.5 param-history if any parameter was touched (expected: none).
