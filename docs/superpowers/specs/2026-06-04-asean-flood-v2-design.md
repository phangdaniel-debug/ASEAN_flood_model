# ASEAN Flood Model v2.0 — Design Spec

**Date:** 2026-06-04
**Status:** Approved design (brainstorming output); pending writing-plans.
**Lineage:** Seeds from `flood-atlas` (validated Singapore reference). `flood-v1.0` is
reference-only (mined for catalogued anomalies; its eyeball-tuned parameters are never ported).

---

## 1. Goal

Extend the validated open-data multi-hazard flood model from Singapore to ASEAN capitals at a
quality a **bank or insurer** would accept. All inputs remain **commercial-safe open data**.

- **Hazards:** pluvial, fluvial, coastal.
- **Pilot (this spec's primary scope):** **Kuala Lumpur**, end-to-end, as the reference template.
- **Next (same machinery, separate spec/plan cycles):** Bangkok, Jakarta.
- **Later (transfer target):** Hong Kong, Manila, Ho Chi Minh City.
- **Products:** present-day return-period suite **RP2…RP1000** (depth + severity rasters per
  hazard) **plus one headline future scenario (SSP5-8.5, 2100)**.
- **Deliverable scope:** rasters + per-city **validation dossier** + **viz suite** (for the
  visual gate). No web explorer / no paper in pilot scope (deferred).

### Governing discipline (inherited, non-negotiable)
- **"Done" is a number, not a feeling.** Every model decision anchors to a documented fact
  (design standard, IDF/DDF curve, documented hotspot, observed event extent), never to visual
  plausibility.
- **Two-gate "done":** a map is done only when it passes the **numeric gate** (validators) **AND**
  the **visual-QA checklist** (binary plausibility veto). Both necessary, neither sufficient.
- **§11 conversion rule:** when the eye flags something it becomes either a **new numeric check**
  or a **logged known-limitation** — never a tweak→look→tweak loop. The eye may *veto*, never *accept*.

---

## 2. Locked decisions (from brainstorming 2026-06-04)

| # | Decision | Choice |
|---|---|---|
| 1 | Workspace | Seed `flood-v2.0` from `flood-atlas`; `flood-v1.0` reference-only |
| 2 | Sequencing | One city end-to-end first (pilot), then replicate |
| 3 | Validation bar | Pre-registered **quantitative per-hazard gates** with bootstrap CIs |
| 4 | Pilot city | **Kuala Lumpur** |
| 5 | Scenario breadth | Present-day RP suite + **one future (SSP5-8.5 2100)** |
| 6 | Deliverable | Rasters + validation dossier + viz |
| 7 | Forcing fix | **IDF/DDF-anchored design storms** (national standards) + reanalysis for shape; IMERG as supplementary high-RP cross-check |

---

## 3. Workspace setup

- `flood-v2.0` seeded from `flood-atlas` at current HEAD.
- **Carry:** `model/`, `scripts/` (generic pipeline + validators), `cities.py` (all six target
  cities already registered), `docs/` (`limitations_register.md`, `validation_workflow.md`,
  `paper/methodology_singapore.md`), `data/<city>/` configs + observed-event rasters
  (MYS2021, JKT2020, THA2011 already present).
- **Leave behind (regenerable, gitignored):** `outputs/`, `cache/`, `logs/`.
- **Discipline docs inherited:** `HANDOFF.md` two-gate rule + §11 conversion rule. Start a v2.0
  changelog/handoff for new decisions.
- **Git:** `flood-v2.0` is not yet a repo. Repo init + seed is the **first implementation task**;
  this spec is committed at that point. (No implementation actions taken during brainstorming.)

---

## 4. Homogeneous architecture (the transferability contract)

`CityConfig` (in `cities.py`) remains the **single source of per-city truth**; the pipeline
(fetch → fit → DEM → route → viz → validate) stays generic. Formalize a city as "complete and
validatable" only when it has its `CityConfig` **plus four open-data manifests**:

1. **Forcing anchors** — national design-rainfall standard as per-RP/per-duration anchors:
   Malaysia **MSMA / HP1 (Hydrological Procedure No. 1)**; Thailand **RID DDF**; Indonesia
   **SNI 2415 / PUSAIR IDF**; plus datum (EGM2008 + MDT offset) and SLR (AR6).
2. **Observed events** — SAR/CEMS extent rasters/vectors + metadata (date, estimated RP, source,
   hazard type).
3. **Hotspot register** — documented flood-prone points (national-agency flood-prone lists +
   georeferenced events) **and dry controls**, each with a confidence flag, **geocoded — never
   hand-pinned** (limitation #6b).
4. **Validation gates** — pre-registered numeric pass/fail thresholds per hazard, committed
   **before** the run.

**"Add a city" recipe:** fill `CityConfig` + 4 manifests → run generic pipeline → auto-validate
against committed gates. A schema/checklist enforces all four exist, so "done" is mechanical.

**Homogeneity acceptance test:** *zero model-code changes between cities; only `CityConfig` +
manifests differ.* Any city needing a code fork flags a missing abstraction in the generic layer.

---

## 5. Hazard methodologies (generic; KL is the proving ground)

### 5.1 Pluvial — rain-on-grid, drainage-exceedance (`pluvial_rain_model.py`)
- Net-excess rainfall = **IDF-anchored design depth − drainage capacity**, routed 2D with
  per-cell Manning's n. KL: JPS 70 mm/6 h primary-drain capacity.
- **Carry SG resolutions:** de-pit conditioning, open-boundary drainage, 3.0 m physical depth
  cap, ≥6-cell denoise at 0.05 m.
- **New fix — depth-aware masking:** strip <5 cm *before* counting/clustering, to preempt the
  Manila-type domain-wide thin sheet on flat deltas (forward-looking for Jakarta/Bangkok).

### 5.2 Fluvial — HAND + GLOFAS (`hand_model.py`)
- HAND inundation from RP discharge with bankfull subtraction; channel cells masked
  (limitation #1). KL: GLOFAS at Klang R. @ Shah Alam (~500 km²), Q_bf = 98 m³/s.
- **New fix — event-RP re-anchoring:** GLOFAS (reanalysis-forced) ranks Dec 2021 as RP~6 while
  JPS implies RP50–100. Bias-correct the fluvial RP scale so the documented event sits at its
  documented RP — otherwise an RP100 event is validated against an RP6 model and "fails" for the
  wrong reason. Re-anchoring uses the IDF/DDF basin-rainfall standard, not the eyeball.

### 5.3 Coastal — bathtub + hydrologic connectivity
- WSE = MSL + tide + surge + SLR on **EGM2008** datum (KL MDT offset +1.0226 m). Framed honestly
  as a **no-pumping / no-defence screening upper bound** (limitation #3b); inertial solver remains
  shelved (HANDOFF §9).
- **KL geography note:** city centre is inland; coastal is meaningful only in the SW
  Klang/Port Klang strip and ≈0 inland. The near-zero inland coastal layer is a *correct* output;
  the coastal validation must not penalize it.
- **Subsidence correction** (`apply_subsidence_correction.py`) becomes a **standard delta-city
  step** — critical for Jakarta (~10–25 cm/yr), minor for KL. Vintage-aware DEM.

---

## 6. Commercial-grade validation framework (centre of gravity)

Pre-registered numeric gates per hazard, committed **before** the run; **every metric reported
with bootstrap confidence intervals** (per SG limitation #12). **Every threshold is citable**
(§9 References).

### 6.1 KL gate table

| Hazard | Primary gate | Reference data | Threshold | Citation |
|---|---|---|---|---|
| Fluvial (primary extent target) | **Extent CSI / POD / FAR** vs SAR at event-RP, scored against the **fluvial+pluvial combined** wet mask (MYS2021 was a rainfall/riverine event) | `data/kl/flood_obs/MYS2021/gfm_kl_composite_dec2021.tif` (present) | CSI ≥ 0.40 (≥0.60 good); POD ≥ 0.60; FAR ≤ 0.40 | Bates & De Roo 2000; Pappenberger 2007; Wing 2017; Bernhofen 2018 |
| Coastal | Extent CSI **only where meaningful** (Klang/Port Klang strip); reported **N/A with rationale** for the inland centre (≈0 by geography) — not forced to a metric | MYS2021 SAR (coastal sub-extent) or N/A | CSI ≥ 0.40 where scored; else documented N/A | as above; limitation #3b framing |
| Pluvial | **IDF-anchor band**: modelled RP-depth within the **published IDF 90% confidence band** | MSMA / HP1 IDF curve (+ NOAA Atlas 14 method) | within source IDF 90% CI | source IDF study's own published CI; NOAA Atlas 14 |
| Pluvial | **Hotspot hit-rate** + dry-control specificity (CRR) | KL JPS/DID flood-prone register + dry controls (to build) | hit-rate target set on register build; CRR reported with CI | Singapore methodology §6 (hit-radius protocol) |
| Point-depth | Modelled vs observed at gauges/HWM | JPS Dec 2021 peak stages (e.g. Ladang Edinburgh 6.91 m) | RMSE < 0.5 m (primary); MAE < 0.3 m; \|bias\| < 0.2 m | Wing 2017/2021 (depth RMSE benchmark) |

### 6.2 Supplementary (not part of the gate)
- **WRI Aqueduct cross-overlay** (free vendor; riverine + coastal only) — substantiates the
  "beats generic vendor" comparative narrative. Supplementary because the chosen bar is
  quantitative gates, not a vendor benchmark. (Aqueduct has no pluvial layer — limitation #4.)

### 6.3 Two-gate "done"
- **Numeric gate:** all §6.1 gates pass (point estimate and CI considered).
- **Visual gate:** fixed QA checklist passes as a binary veto — monotonicity (area/depth grow with
  RP), mass-plausibility (wet area a sane domain fraction), hazard-separation (coastal/fluvial/
  pluvial in sensible places), no domain-wide thin sheets, no speckle, no post-cap single-cell
  spikes, known hotspots lit / known dry ground dry.
- Anything the eye flags → new numeric check or logged limitation (§11 conversion rule).

### 6.4 Key upgrade over current state
Today's `validate_fluvial_kl_dec2021.py` is only a **discharge-RP cross-check** (Option B). v2.0
adds the actual **extent-CSI** validation against the SAR composite — the robust, commercially
credible piece currently missing for KL.

---

## 7. Anomaly-improvement register (the "suggest improvements" requirement)

1. **IDF/DDF-anchored forcing** — fixes the documented −51.5% rainfall under-prediction (KL
   pluvial FAIL → re-anchored). *Master fix; the transferability lever.*
2. **Depth-aware pluvial masking** — preempts the Manila domain-wide-sheet bug (limitation #2) on
   flat deltas.
3. **Fluvial event-RP re-anchoring** — stops validating real RP100 events against an RP6 model.
4. **Subsidence as a standard delta-city step** — vintage-aware DEM for Jakarta/Bangkok.
5. **Scenario-forcing consistency enforced up front** (limitation #9) — one consistent pluvial fit,
   monotone across scenarios, before any future-scenario run.
6. **Extent-CSI + bootstrap CIs** replace eyeball/discharge-only acceptance.
7. *(Deferred to its city)* Jakarta sea-mask crash fix — tiling/memory (HANDOFF §8.2).

---

## 8. Deliverables, scope boundaries, risks

### 8.1 Pilot deliverables (KL)
- Present-day **RP2…RP1000** depth + severity rasters for pluvial, fluvial, coastal.
- **SSP5-8.5 2100** scenario for the same.
- Per-city **validation dossier** (gate table + CIs + two-gate result + limitations register entries).
- **Viz suite** for the visual gate (per-hazard per-RP maps; combined maps).

### 8.2 Out of scope (pilot)
- Web explorer / interactive atlas; publishable manuscript; full SSP scenario grid
  (SSP2-4.5 × 2050/2100, SSP5-8.5 × 2050); inertial coastal solver.

### 8.3 Risks / open items (resolve during planning or flag)
- **KL pluvial hotspot register does not yet exist** — must be built from JPS/DID flood-prone
  lists + dry controls, geocoded (not hand-pinned). Hit-rate target set on build.
- **IDF source acquisition** — MSMA / HP1 design curves must be sourced and digitized as the
  forcing anchor; confirm open/citable availability.
- **Event-RP for MYS2021** — the SAR composite is multi-date (16–22 Dec 2021); fix the
  event-RP comparison scenario and the composite-vs-peak-snapshot handling explicitly.
- **Coastal CSI for KL** — Dec 2021 was fluvial/pluvial-driven; coastal CSI may be near-zero by
  geography. Validate coastal where it is meaningful (Klang/Port Klang) or report as N/A with
  rationale rather than forcing a metric.

---

## 9. References (threshold citations)

- **Bates, P.D. & De Roo, A.P.J. (2000).** A simple raster-based model for flood inundation
  simulation. *J. Hydrol.* 236:54–77. — foundational binary inundation verification (CSI/F²).
- **Pappenberger, F. et al. (2007).** Uncertainty in calibration of effective roughness in
  HEC-RAS using inundation observations. *J. Hydrol.* 337:11–23. — CSI/extent verification practice.
- **Wing, O.E.J. et al. (2017).** Validation of a 30 m resolution flood hazard model of the
  conterminous US. *Water Resour. Res.* 53:7968–7986. — CSI/hit-rate + depth-error benchmarks for
  coarse-resolution models (CSI ~0.6+ good; depth RMSE ~0.5 m).
- **Bernhofen, M.V. et al. (2018).** A first collective validation of global fluvial flood models.
  *Environ. Res. Lett.* 13:104007. — global-model CSI ~0.4–0.6 typical (acceptable-band anchor).
- **NOAA Atlas 14 / national IDF studies** — publish 90% confidence intervals on design-rainfall
  depths; source of the pluvial IDF-band tolerance.
- **Malaysia MSMA (Urban Stormwater Management Manual) / HP1 (Hydrological Procedure No. 1)** —
  KL design-rainfall (IDF) and drainage-capacity anchors.
- **Singapore methodology** (`docs/paper/methodology_singapore.md`) — hotspot hit-radius protocol;
  bootstrap-CI reporting convention (limitation #12).
