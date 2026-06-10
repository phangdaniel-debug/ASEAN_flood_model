# Singapore-First Scope & "Done" Definition — Design Spec

**Date:** 2026-05-31
**Status:** Approved (brainstorming → spec). Precedes any model-code change.
**Anchors:** `HANDOFF.md` §§3, 4, 10, 11.

> This spec defines *what "done" means* for the Singapore milestone and the
> artifacts that measure it. It deliberately does **not** change model code.
> No model parameter is touched until the hotspot table and its validator exist
> and produce a first measured number.

---

## 1. Goal of this milestone

Ship a **full three-hazard Singapore flood map (pluvial + coastal + fluvial)**
whose **pluvial** layer carries a *measured, comparative* claim — "a
city-calibrated open model beats a generic global vendor at locally-documented
flood behaviour" (`HANDOFF.md` §3) — and whose coastal/fluvial layers are
plausibility-validated product surface.

"Done" is a **two-gate AND** (`HANDOFF.md` §11): numeric gate AND visual gate.
Neither alone suffices. The numeric gate stops the loop; the visual gate keeps
the product presentable and catches what validation has no ground truth for.

---

## 2. Hazard tiering (equal map coverage, unequal evidentiary weight)

| Hazard | Role | Numeric gate | Rationale |
|---|---|---|---|
| **Pluvial** | **Thesis anchor** | Strict + comparative (§4) | Only SG hazard with rich local documentation + a working validator; carries the better-than-generic claim. |
| **Coastal** | Product surface | Plausibility (§5) | No SAR-visible SG coastal event exists. Bathtub default (`HANDOFF.md` §6/§9); inertial stays shelved unless this gate fails. |
| **Fluvial** | Product surface | Plausibility (§5) | SG fluvial is minor (short canalized catchments); weak local documentation → no honest comparative claim. |

**Discipline applies to all three.** Coastal and fluvial may NOT be tuned to
"look right." Each gets a fixed binary plausibility checklist; any eyeball
observation is converted to a check or a logged limitation (`HANDOFF.md` §11
conversion rule). They simply do not get a *comparative* gate, because the SG
data cannot honestly support one for those hazards.

---

## 3. Current validation state (grounding — what exists today)

- `validate_pluvial_singapore.py` — PUB **depth-band** check: RP1000 max depth in
  `[0.38, 3.0] m` (anchor 0.76 m × (1−0.50) lower, engineering cap 3.0 m upper);
  RP≤10 at drain-capacity floor → WARN (physically correct, not a fail);
  **monotonicity** of max depth across RP. Single-number-per-RP; says nothing
  about *where* water is. **Reused unchanged** as gates 1–2.
- `validate_historical_events.py` — CSI/H/FAR vs SAR extent. Configured only for
  Jakarta/KL/Bangkok/Manila. **No Singapore event** (SG flash floods drain in
  hours; SAR cannot see them). Not used for SG pluvial.
- `validate_hwm_points.py` — per-point plausibility band. **Exactly one SG point**
  today (Stamford Canal / Orchard Rd, pluvial RP100, band 0.2–0.7 m).
- **Missing (the gap this milestone fills):** the documented-hotspot hit-rate
  table + validator named in `HANDOFF.md` §4/§10. The comparative thesis hangs
  on it and it does not exist yet.

---

## 4. Pluvial "done" definition (the thesis-anchor gate)

A pluvial map is **done** only when **BOTH** gates pass.

### 4.1 Numeric gate — all four must hold

1. **PUB depth band** — `validate_pluvial_singapore.py`, unchanged.
2. **Monotonicity** — `validate_pluvial_singapore.py`, unchanged.
3. **Hotspot hit-rate (NEW)** — on the documented SG hotspot table (§6), at the
   anchor RP, our model's hit-rate on *positive* points **≥ 0.70**.
4. **Comparative margin (NEW)** — our **skill score (TSS, §4.3)** exceeds **both**
   baselines (§7) by **≥ 0.20** each.

### 4.2 Visual gate — fixed §11 checklist (binary veto)

Monotone area/depth with RP; sane wet-area fraction; hazard separation
(coastal/fluvial/pluvial in sensible places); no domain-wide thin sheets, no
speckle, no single-cell spikes after the cap; known hotspots lit and known dry
ground dry; coastline behaves (low RP barely floods, high RP creeps inland).

**Cadence (only at defined gates):** (1) after a numeric pass — final coherence
veto before "done"; (2) on a numeric fail — to localize where/why. **Never** a
tuning session, never after a parameter nudge. A failed item opens a ticket →
conversion rule (§9).

### 4.3 Anti-gaming: TSS + dry control points

Hit-rate alone is gameable — a "flood-all-low-ground" model scores high by
flooding everything. So the hotspot table carries **two classes**: documented
flood-prone **positives** and documented reliably-dry **negatives** (§6). The
headline skill metric is the **True Skill Statistic (Peirce skill score)**:

```
TSS = hit_rate(positives) + correct_reject_rate(negatives) − 1
```

A model that floods the whole island scores TSS ≈ 0. This is what makes "beats
the naive baseline" a real claim rather than an artifact, and it is the binding
discriminator against the naive open baseline (§7).

### 4.4 Fixed scoring parameters

- **"Hit" definition:** ≥ 1 cell with depth **≥ 0.10 m** (consistent with the
  `validate_historical_events.py` flood threshold) within **150 m** of the point
  (absorbs Copernicus GLO-30 ~30 m horizontal + PUB/news georef error).
- **Anchor RP for scoring:** **RP50.** PUB hotspots flood in *moderate* storms;
  ponding onset is engineered to start ~RP5 (`drain_capacity_mm = 50`). RP100 is
  too lax (everything floods); RP10 sits at the drain floor. RP50 is the
  discriminating middle. The **full RP-sweep hit-rate curve** is reported as
  supporting evidence (not gated).

### 4.5 Refining the scoring parameters (discipline)

The three params in §4.4 (hit depth, radius, anchor RP) are expected to be
refined as we see real results — but refinement must stay anchored, or it
becomes the eyeball loop one level up (tuning the *yardstick* until the model
passes, instead of tuning the model until the picture looks right). Rules:

1. **Anchor to a documented fact, never to an outcome.** A radius change is
   legitimate only if tied to a measured georef/DEM uncertainty; an anchor-RP
   change only if tied to documented storm severity of the events; a depth-
   threshold change only if tied to a documented ponding-onset depth. "150 m
   made us pass" is forbidden; "the news photos geolocate to ±200 m, so the
   radius was too tight" is allowed.
2. **Pre-register before re-scoring.** State the new value and its documented
   justification *before* re-running, not after seeing which value passes.
3. **Never fail→pass a model by moving the yardstick.** If a param change flips
   a verdict, that is a flag to scrutinise the change, not to keep it.
4. **Log every change** in a param-history block here (old → new, date,
   documented justification, and the verdict before/after) so the audit trail
   shows the yardstick was not reverse-fit.

**Param history:**
- 2026-05-31 — initial scoring values: hit depth 0.10 m / radius 150 m / anchor RP50.
- 2026-05-31 — naive-baseline TWI flag fraction set to **15 % wettest land cells**
  (initial pre-registered default; justification: SG flood-prone ground is a small
  fraction of land area). Not yet refined against any result.

---

## 5. Coastal & fluvial plausibility gates (product-surface tier)

Binary, fixed, non-tunable. No comparative claim.

**Coastal:**
- WSE/datum sanity: `WSE = MSL + tide + surge + SLR`, EGM2008 datum, SG
  `msl_to_egm2008_offset = 1.1588 m`, AR6 SSP5-8.5 2100 SLR = 0.674 m — all
  numerically correct in the run config.
- Monotonicity of flooded area/depth with RP.
- ≥ 1 documented coastal HWM point in-band (`validate_hwm_points.py`).
- No post-`phys_cap` blow-up cells (single-cell spikes).
- Solver: **bathtub** (default). Inertial stays shelved (`HANDOFF.md` §9) unless
  this gate demonstrably fails on bathtub.

**Fluvial:**
- Channel-masking applied (`depth = where(river_mask, 0, depth)`, `HANDOFF.md` §6).
- Monotonicity with RP.
- Wet area a sane fraction of the domain (no domain-wide sheet).
- No below-grade canal artefacts surfacing as flood (logged as known limitation
  if present, not "fixed" — `HANDOFF.md` §6/§11).

---

## 6. The Singapore hotspot anchor table (NEW artifact)

**File:** `data/singapore/flood_obs/hotspots/sg_pluvial_hotspots.csv`
A single committed, attributed table — same discipline as the
`validate_hwm_points.py` registry. **Built before looking at model output**, so
it cannot be reverse-fit to our raster.

**Schema (one row per point):**

| column | meaning |
|---|---|
| `label` | human-readable location name |
| `lon`, `lat` | WGS84 coordinates |
| `class` | `flood` (positive) or `dry` (negative control) |
| `documented_depth_m` | optional; present for points with a cited depth |
| `anchor_rp` | RP at which the point is scored (default 50) |
| `source` | citation: PUB list entry, dated news report, or documented absence |
| `georef_confidence` | qualitative: high / med / low |

**Composition (~24–28 points):**
- **Positives (~18–22):** primarily the **PUB official "List of Flood-Prone
  Areas as at Nov 2025"** (36 entries; each table row cites its S/N) — the
  authoritative, *current* (post-mitigation) flood-prone register. Plus two
  depth-bearing **historical** anchors (Orchard/Stamford Canal ~0.4 m; Bukit
  Timah Rd ~0.25 m) that are no longer on the PUB list but feed
  `validate_hwm_points.py`. Note: the PUB list is current-state, so famous
  historical hotspots that PUB has since drainage-upgraded (Orchard, Bukit
  Timah Rd) are absent — the model is therefore tested against the locations
  PUB *currently* documents, which is the more honest comparative test.
- **Negatives (~5–8):** reliably-dry control points — elevated/never-listed
  ground (e.g. Bukit Timah Hill, Telok Blangah ridge, central catchment high
  ground). Sourced as "absent from every PUB flood list AND no news flood
  record" — documented *absence*, attributed.

**Sourcing rule (`HANDOFF.md` §3/§11):** every point anchored to a citable
source. **No point added because the map looks like it should flood there.**

---

## 7. Dual comparator baseline (NEW)

Both scored against the **same** table, same "hit" definition, same anchor RP,
same TSS metric.

1. **WRI Aqueduct** — free global vendor; riverine + coastal inundation rasters
   only (**no pluvial layer**), ~1 km resolution. Expected ~0 on pluvial
   positives → demonstrates "generic vendors omit pluvial by design"
   (`HANDOFF.md` §3, verbatim). The *rhetorical* comparison. Commercial-safe.
2. **Naive open baseline — Topographic Wetness Index (TWI) threshold.** A
   trivial open method any competitor could run for free, computed on the raw
   Copernicus DSM: `TWI = ln(a / tan β)`, where `a` is specific catchment area
   (from pysheds D8 flow accumulation) and `β` is local slope (pysheds
   `cell_slopes`). The wettest cells (high TWI = low-lying, convergent ground —
   where flat urban ponding actually occurs) are flagged flooded; output is a
   scorable pseudo-depth raster (flagged cells = a nominal depth above the hit
   threshold, all else 0). No calibration, no drainage network. The *binding*
   comparison; the TSS + dry-control design is what prevents it from winning by
   flooding all low ground.

   **Why not depression-fill (the original §7.2 plan):** depression-fill on the
   raw DSM is *degenerate on Singapore's island geometry* — treating the sea as
   an outlet drains nearly everything (the island is small and radially drained),
   while walling the sea off turns the whole island into one basin that fills to
   a domain-wide thin sheet (the Manila §8.1 failure mode). Moreover most SG
   pluvial hotspots are **not** topographic depressions; they are flat low urban
   ground that floods on drainage exceedance — which depression-storage
   structurally cannot represent. TWI captures low convergent ground without the
   island pathology, keeping the naive baseline genuinely distinct from Aqueduct.

   **TWI threshold is a scoring parameter** governed by §4.5 discipline. Default:
   the wettest **15 %** of finite land cells by TWI are flagged (a documented,
   pre-registered default reflecting that SG flood-prone ground is a small
   fraction of land area; logged in the §4.5 param-history, refined only under
   the anchored rules, never to flip a verdict).

**Headline thesis sentence (output of the validator):**
> "On N documented Singapore flood locations, the city-calibrated model achieves
> TSS = X; the best free global vendor (Aqueduct) = Y; a naive open method = Z."

**Known asymmetry (logged, not smoothed):** Aqueduct ~1 km resolution vs 150 m
hit radius — documented in the report, not silently resampled away.

---

## 8. Artifacts: build vs reuse

**New:**
- `data/singapore/flood_obs/hotspots/sg_pluvial_hotspots.csv` — the attributed
  table (§6).
- `scripts/validate_pluvial_hotspots_singapore.py` — loads the table, samples the
  model raster + both baselines, computes hit-rate / correct-reject / **TSS**,
  applies numeric gates 3 & 4, prints the comparative report, exit-code gated.
- A small Aqueduct fetch/clip prep script (commercial-safe download → SG bbox),
  and the naive-baseline generator (TWI-threshold on the raw DSM, §7.2).

**Reused unchanged:**
- `validate_pluvial_singapore.py` — numeric gates 1–2.
- `validate_hwm_points.py` — extended with the depth-bearing SG points from §6.
- `pluvial_rain_model.py` (raingrid) — **no model code touched** until the table
  + validator exist and a first number is measured.

---

## 9. Out of scope / risks / limitations register

**Out of scope this milestone:**
- Other cities (Jakarta, Bangkok, Manila, KL, HCMC).
- Inertial coastal solver — stays shelved (`HANDOFF.md` §9).
- Fluvial/coastal *comparative* claims.

**Risks:**
- Aqueduct ~1 km vs 150 m radius — documented asymmetry (§7).
- Dry-control points are arguable — mitigated by requiring documented absence and
  keeping the count modest so a few disputes don't swing TSS.
- Aqueduct download/licensing path must be verified commercial-safe before use.

**Limitations register:** a `docs/` note where converted eyeball-observations
land (`HANDOFF.md` §11 conversion rule), seeded with the known canal-below-grade
and Manila-sheet entries.

---

## 10. Definition of done for this milestone (summary)

The Singapore three-hazard map is **done** when:
1. **Pluvial** passes its full numeric gate (§4.1: depth band + monotonicity +
   hit-rate ≥ 0.70 + TSS margin ≥ 0.20 over both baselines) **AND** the §4.2
   visual checklist.
2. **Coastal** passes its plausibility gate (§5) **AND** the relevant visual
   checklist items.
3. **Fluvial** passes its plausibility gate (§5) **AND** the relevant visual
   checklist items.
4. The hotspot table (§6) and comparative validator (§7–8) are committed, and the
   headline thesis sentence is produced from a real run.
