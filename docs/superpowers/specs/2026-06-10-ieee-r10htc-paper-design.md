# IEEE R10-HTC Conference Paper — Design Spec

**Date:** 2026-06-10
**Status:** Approved (brainstorming) → ready for implementation plan
**Deliverable:** a condensed, humanitarian-framed IEEE conference paper derived from the
master journal draft (`docs/paper/draft.md`), written as a NEW file
`docs/paper/ieee-r10htc.md`. The master draft is left intact as the extended reference.

## 1. Venue & hard constraints

- **Venue:** IEEE Region 10 Humanitarian Technology Conference (R10-HTC) 2026,
  **Special Session 1 "Net Zero Integration"** (sustainable infrastructure, geospatial
  monitoring, climate data analytics, decision-support systems — the flood-screening atlas
  fits this theme directly).
- **Format:** IEEE conference template, **two-column**, **~6 pages** (the binding limit;
  slightly over is acceptable per the author). Design to 6; do not pad.
- **Figures/tables budget:** 3 figures + 3 tables (comfortable at 6 pp). Listed in §5.
- **Source of truth for every number:** the master draft + the merged dossiers/limitations
  register on `main`. No new claims; nothing re-derived. Where the master draft was made
  conservative (e.g. the "tens of minutes per RP" runtime), carry that conservative wording.

## 2. Headline & framing (the spine)

**Equity of access.** Commercial 30 m flood models (Fathom 3.0) are closed-source and their
free tier *excludes the ASEAN megacities most exposed*; bespoke per-city engineering studies
are not publicly reproducible; the only open global products (Aqueduct, GLOFRIS) are an order
of magnitude coarser and lack a pluvial layer. The cities most at risk therefore cannot obtain
usable, affordable hazard maps. **This paper delivers an open, free-data, reproducible 30 m
multi-hazard alternative — and validates that it locates real floods.** The methodology and
validation are the "how we make it trustworthy" supporting act, not the headline.

The humanitarian thread runs through intro → impact: open hazard information as a public good
for under-resourced city disaster-management and adaptation-planning agencies in the region.

## 3. Scope (what the paper covers)

- **Four cities:** Singapore, Kuala Lumpur, Bangkok, Jakarta (nine configurations across four
  countries). Manila/HCMC are named once as deferred (enclosed-bay solver limitation).
- **Three hazards:** coastal (local-inertia solver), fluvial (main-stem HAND), pluvial
  (fill-and-spill). Per-country IDF anchoring is the in-region calibration story.
- **Validation headline:** the model-blind documented-hotspot location-skill gate (three
  cities, HR/CRR/TSS, all statistically significant skill). **Brief:** the bathtub-bias →
  inertial structural fix (1.7–25× over-prediction; Bangkok 12.5× → ~1×).

## 4. Section structure (~6 pp, two-column)

| § | Title | ~length | Content |
|---|---|---|---|
| Abstract | — | ~180 w | Gap (commercial models exclude these cities) → open alternative (4 cities, 3 hazards, free data, reproducible) → trustworthy (hotspot gate significant skill in 3 cities; bathtub-bias structural fix) → humanitarian impact. |
| I | Introduction | ~0.8 pg | ASEAN exposure + the access gap; the contribution. **Table 1 — comparator** (this work vs Fathom / Aqueduct / GLOFRIS / city studies: resolution × hazards × open-code × open-data × per-country IDF). |
| II | Open pipeline & methods | ~1.6 pg | Open-data inputs (GLO-30, ERA5-Land, UHSLC, GloFAS, AR6, WorldCover, OSM — all free); three hazards (inertial coastal; **main-stem-HAND** fluvial referenced to the GloFAS-reach trunk; fill-and-spill pluvial); **per-country IDF anchoring** (PUB/JPS-MSMA/TMD-RID/BMKG; the 28–62 % synthetic-rainfall deficit it corrects); SSP×horizon scenarios. Per-step depth → repo. **Figure 1 — pipeline schematic.** |
| III | The atlas | ~1.1 pg | Headline RP100 combined extents + the mitigation-delta scenario signal (avoided km² SSP2-4.5 vs SSP5-8.5 @2100, Bangkok −130 km²). **Table 2 — RP100 combined extents** (4 cities + Greater-KL/Greater-Jakarta composites). **Figure 2 — rendered Bangkok RP100 flood map** (visual impact). |
| IV | Validation & trustworthiness | ~1.5 pg | **Table 3 — documented-hotspot gate** (KL 0.76/0.86/0.62 PASS; Bangkok 0.56/0.86/0.42; Jakarta 0.89/0.50/0.39; all significant TSS) + model-blind register method (one paragraph) + the **main-stem-HAND transferable rule** + dry-control discipline (two sentences). Then the **bathtub-bias → inertial fix** with **Figure 3 — bias bars** (RP2/RP100 by city; Bangkok 12.5× headline). One line each on IDF-consistency (0 FAIL) and the HWM in-band check. |
| V | Impact & honest limitations | ~0.5 pg | Decision-support for under-resourced agencies (humanitarian close); screening-grade caveats (no-pumping, no-sub-pixel, marginal-not-joint RP); the out-of-domain-HAND structural ceiling (Bangkok HR; honest, not tuned); Manila/HCMC deferred (enclosed-bay solver). |
| VI | Conclusion | ~0.25 pg | Open + validated + reproducible; invitation to extend. |
| — | References | ~0.75 pg | ~20–25 key cites (trim the journal draft's ~50). |

## 5. Figures & tables (production specs)

**Real / renderable:**
- **Figure 2 — Bangkok RP100 flood map.** Rendered from a committed Bangkok output raster
  (combined or per-hazard depth at RP100). This is the one figure needing a render step; a
  rendering script + the output PNG are an implementation task. If a suitable raster/PNG is
  not readily available, fall back to a placeholder spec + repo pointer rather than block.

**Author-drawn (placeholder specs in the markdown, drawn in the IEEE template):**
- **Figure 1 — pipeline schematic** (data-flow boxes: inputs → per-hazard solvers → composite).
- **Figure 3 — bathtub-bias bars** (RP2/RP100 bias by city + inertial overlay; from Table 4/5
  numbers in the master draft).

**Tables (all from master-draft numbers):**
- **Table 1 — comparator** (subset of the master draft's Table 1, ≤6 rows).
- **Table 2 — RP100 combined extents** (the 4-city subset of the master draft's Table 3).
- **Table 3 — documented-hotspot gate** (the master draft's Table 7 verbatim).

## 6. Cuts from the journal draft (explicit)

- All appendices (R1–R8 replicability audit) → one sentence + repo/Zenodo pointer.
- §3 per-city implementation matrix → one paragraph folded into §II.
- §4.3 city-by-city walk-throughs → folded into Table 2 + one or two sentences.
- §5.1 IDF-consistency, §5.4 HWM → one line each; §5.2 historical-event CSI → omit (weakest
  tier; mention in one clause that contingency-CSI is observation-limited).
- Deep §2 method detail (subsidence zones, MDT sampling, sea-mask BFS, defence burn-in,
  TanDEM-X spike cleanup) → one clause each or omit.
- ξ-cap / GEV mechanics, the Singapore canal-overflow framing nuance → compress to a clause.

## 7. Deliverables

1. `docs/paper/ieee-r10htc.md` — the ~6-page condensed paper in IEEE-section structure,
   Markdown (the user converts to the IEEE LaTeX/Word template downstream).
2. `scripts/render_bangkok_floodmap.py` (or reuse an existing renderer) + the Figure-2 PNG,
   IF a committed Bangkok RP100 raster is available; otherwise a documented placeholder.
3. The master `docs/paper/draft.md` is unchanged (extended reference).

## 8. Out of scope

- Producing the IEEE LaTeX/Word template itself (the user owns final typesetting).
- Re-running any model or re-deriving any number.
- Author/affiliation content (TBD by the user) — leave clearly-marked placeholders.
- Figures 1 and 3 as final vector art (placeholder specs only; drawn in the template).
