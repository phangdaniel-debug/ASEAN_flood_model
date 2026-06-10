# IEEE R10-HTC Conference Paper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended for this prose deliverable — a paper needs one coherent voice) or superpowers:subagent-driven-development. Steps use `- [ ]` checkboxes.

**Goal:** Produce a ~6-page IEEE two-column **short paper** (`docs/paper/ieee-r10htc.md`) condensed from the master journal draft, equity-of-access framed, plus a rendered Bangkok RP100 flood-map figure.

**Architecture:** A new self-contained Markdown file in IEEE section structure, written by condensing specific sections of `docs/paper/draft.md` (the single source of truth for every number). One real render task (Figure 2) reusing an existing flood-map renderer; Figures 1 and 3 are bracketed placeholder specs drawn later in the IEEE template. The master draft is NOT modified.

**Tech Stack:** Markdown; Python + rasterio/matplotlib for the one figure render. No model re-runs; no new claims.

**Discipline:** every number traces to `docs/paper/draft.md` (on `main`); carry its conservative wording (e.g. "tens of minutes per RP"); no Manila/HCMC content except the one deferred-cities sentence; leave author/affiliation as a clearly-marked placeholder.

**Reference inputs (read before starting):**
- Spec: `docs/superpowers/specs/2026-06-10-ieee-r10htc-paper-design.md`
- Master draft: `docs/paper/draft.md` — §§ cited per task below
- Hotspot numbers: master draft Table 7 (KL 0.76/0.86/0.62 PASS; Bangkok 0.56/0.86/0.42; Jakarta 0.89/0.50/0.39)
- Bias numbers: master draft Tables 4–5 (RP2 7–91×, RP100 1.7–25×; Bangkok 12.5× → ~1×)

---

### Task 1: Scaffold + front matter + abstract

**Files:** Create `docs/paper/ieee-r10htc.md`

- [ ] **Step 1: Create the file** with the IEEE front matter and section skeleton (all six section headings as empty `## N. Title`), plus this header block:

```markdown
# Open, Reproducible 30 m Multi-Hazard Flood Screening for Under-Resourced Southeast Asian Cities

**Authors:** [TBD — author list]
**Affiliations:** [TBD]
**Venue:** IEEE R10-HTC 2026 — Special Session 1 "Net Zero Integration"
**Format:** IEEE conference template, two-column, ~6 pages. Source of record: docs/paper/draft.md (extended journal form).

## Abstract
## I. Introduction
## II. Open Multi-Hazard Pipeline
## III. The Open Flood Atlas
## IV. Validation and Trustworthiness
## V. Impact and Limitations
## VI. Conclusion
## References
```

- [ ] **Step 2: Write the Abstract** (~180 words), structured: (1) the gap — commercial 30 m models (Fathom) are closed and their free tier excludes ASEAN megacities; bespoke city studies are not reproducible; open global products are ~10 km and lack pluvial; (2) the contribution — an open, free-data, reproducible 30 m coastal+fluvial+pluvial atlas for nine configurations across four ASEAN countries (Singapore, Malaysia, Thailand, Indonesia), per-country IDF-anchored, under SSP×horizon scenarios; (3) trustworthiness — a model-blind documented-hotspot gate yields statistically significant location skill in three cities, and a bathtub-bias characterisation (1.7–25× over-prediction) is fixed by a local-inertia solver (Bangkok 12.5×→~1×); (4) impact — open hazard information as a public good for under-resourced city agencies. End with a one-line keywords list incl. "humanitarian technology, flood risk, open data, decision support, climate adaptation."

- [ ] **Step 3: Commit.** `git add docs/paper/ieee-r10htc.md && git commit -m "feat(ieee): scaffold + abstract"`

---

### Task 2: §I Introduction + Table 1 (comparator)

**Files:** Modify `docs/paper/ieee-r10htc.md`

- [ ] **Step 1: Write §I** (~0.8 pg / ~450 words), condensing master draft §1.1. Two paragraphs: (a) **stakes** — ASEAN holds six of the ten cities most coastally exposed by 2100; ~750 M people, ~20 % of regional GDP on flood-exposed land; compounding SLR (+0.62 to +1.62 m AR6 P50 SSP5-8.5/2100), CC-rate rainfall intensification, 1–25 cm/yr subsidence; recent events (Thailand 2011, Jakarta 2020, KL 2021). (b) **the access gap** — the humanitarian core: the cities most exposed cannot obtain usable, affordable hazard maps because the only 30 m three-hazard model is commercial and its free tier *excludes them*, city studies are closed, and open global products are too coarse and pluvial-less. Close with the one-sentence contribution + that the paper covers four cities (SG/KL/Bangkok/Jakarta) with Manila/HCMC deferred (§V).

- [ ] **Step 2: Add Table 1 — comparator** (≤6 rows), condensed from master draft Table 1. Columns: Tool | Resolution | Hazards | Open code | Open data | Per-country IDF. Rows: **This work** (30 m / C+F+P / open / open / yes-4-services); Fathom 3.0 (30 m / CFP / closed / closed / global-synthetic; free tier excludes ASEAN megacities); Aqueduct Floods 4.0 (~10 km / C+F / open / open / none); GLOFRIS (~10 km / F / open / open / none); city engineering studies (high / various / closed / closed / per-city). Keep the "free tier excludes ASEAN" point in a footnote — it is the equity hook.

- [ ] **Step 3: Commit.** `git commit -am "feat(ieee): §I introduction + comparator table"`

---

### Task 3: §II Open multi-hazard pipeline + Figure 1 spec

**Files:** Modify `docs/paper/ieee-r10htc.md`

- [ ] **Step 1: Write §II** (~1.6 pg / ~850 words), condensing master draft §2 + §2.5.1 + §3. Structure as compact subsections or dense paragraphs:
  - **Open-data inputs (one paragraph + inline list):** GLO-30 DEM, ERA5-Land, UHSLC tide gauges, GloFAS v4, AR6 SLR, ESA WorldCover, OpenStreetMap — *all free, most without registration* (the reproducibility/equity point). Pure-Python stack.
  - **Per-country IDF anchoring (the key calibration):** national design-rainfall anchors (PUB / JPS-MSMA / TMD-RID / BMKG) replace global synthetic statistics that under-represent tropical convective extremes by 28–62 %; storm-duration matched per city (SG 1 h secondary-drain; others 6 h). This is the in-region calibration that makes the atlas usable where global models fail.
  - **Three hazards (one paragraph each, high level):** (i) **coastal** — UHSLC-GEV stage + AR6 SLR + MDT datum, routed by a Bates et al. (2010) local-inertia solver (bathtub fallback for enclosed-sea topology); (ii) **fluvial** — GloFAS-derived stage with bankfull subtraction, mapped via **main-stem HAND** referenced to the GloFAS-reach trunk (not channel-init / OSM, which over-broaden); (iii) **pluvial** — IDF excess routed by a catchment-routed fill-and-spill cascade (Barnes et al. 2020) with WorldCover per-cell runoff. Per-step detail → repo.
  - **Scenarios:** SSP2-4.5 / SSP5-8.5 × 2050 / 2100; subsidence-corrected DEM.
- [ ] **Step 2: Insert the Figure 1 placeholder spec** (bracketed): a pipeline data-flow schematic (inputs → per-hazard solvers → per-pixel-max composite + severity). Note in the plan: check whether the committed `docs/paper/figures/fig4_pipeline.png` is reusable; if so reference it, else leave the bracketed spec for drawing in the template.
- [ ] **Step 3: Commit.** `git commit -am "feat(ieee): §II pipeline + methods + Figure 1 spec"`

---

### Task 4: §III The atlas + Table 2 (extents) + Figure 2 (Bangkok map placeholder)

**Files:** Modify `docs/paper/ieee-r10htc.md`

- [ ] **Step 1: Write §III** (~1.1 pg / ~600 words), condensing master draft §4.1–4.2. One paragraph on the headline pattern (coastal-dominated flat deltas vs pluvial-dominated KL; the dominant-hazard column), one on the **policy signal** — the mitigation delta (avoided coastal RP100 land SSP2-4.5 vs SSP5-8.5 @2100, dominated by Bangkok −130 km²) as the cleanest single number for adaptation planning. Include the honest framing that Table 2 extents are screening upper bounds (no-pumping, no-sub-pixel) — forward-reference §IV/§V.

- [ ] **Step 2: Add Table 2 — RP100 combined extents**, the 4-primary-city subset of master draft Table 3: Singapore (130), Kuala Lumpur core (197), Bangkok klong (3,628; coastal-dominated), Jakarta (408), plus the Greater-KL and Greater-Jakarta composite rows if desired. Columns: City | Coastal | Fluvial | Pluvial | Combined | Dominant. Keep the Singapore-"fluvial"-is-canal-overflow footnote (one line).

- [ ] **Step 3: Insert Figure 2 placeholder** (bracketed spec) referencing the PNG path the render task (Task 7) will produce: `docs/paper/figures/ieee_fig2_bangkok_rp100.png` — "Bangkok RP100 combined-hazard depth (SSP5-8.5/2100), illustrating the screening flood envelope; the §IV bathtub-bias analysis shows the inertial-corrected coastal extent."

- [ ] **Step 4: Commit.** `git commit -am "feat(ieee): §III atlas + extents table + Figure 2 ref"`

---

### Task 5: §IV Validation & trustworthiness + Table 3 (hotspot gate) + Figure 3 spec

**Files:** Modify `docs/paper/ieee-r10htc.md`

- [ ] **Step 1: Write §IV** (~1.5 pg / ~800 words), condensing master draft §5.5 (headline) + §5.3 (brief). Lead with the **documented-hotspot gate**: one paragraph on the model-blind register method (frozen documented-flooded positives + documented-dry controls, geocoded + DEM-verified, never tuned to the gate; HR/CRR/TSS with bootstrap CI), then **Table 3** (master draft Table 7 verbatim: KL 17/7 → 0.76/0.86/0.62 PASS; Bangkok 16/7 → 0.56/0.86/0.42; Jakarta 18/8 → 0.89/0.50/0.39; all TSS CIs exclude zero). Then two compact findings: the **main-stem-HAND transferable rule** (reference HAND to the modelled-discharge trunk; KL fixed by physics) and the **dry-control discipline** (flooded genuine controls stay; only independently-documented mislabels corrected — the Jakarta Menteng/Gambir example, lifting TSS 0.16→0.39). State the honest verdict: significant skill in all three; the Bangkok HR and Jakarta CRR shortfalls are documented structural limits, not tuning failures.

- [ ] **Step 2: Add the bathtub-bias brief** (~one paragraph) from master draft §5.3: open bathtub coastal extent over-predicts documented present-day inundation 1.7–25× at RP100; the local-inertia solver brings it to ~1× where topology permits (Bangkok 12.5×→283 km², within ~30 % of the documented 2011 extent). Insert **Figure 3 placeholder spec**: bias-factor bars at RP2/RP100 by city with the inertial overlay (the Bangkok 12.5× is the headline). Add one clause each: IDF-anchor consistency (0 FAIL) and HWM depth check (3/5 in-band); note contingency-CSI is observation-limited (one clause) and omitted.

- [ ] **Step 3: Commit.** `git commit -am "feat(ieee): §IV validation + hotspot table + bias brief + Figure 3 spec"`

---

### Task 6: §V Impact & limitations + §VI Conclusion + References

**Files:** Modify `docs/paper/ieee-r10htc.md`

- [ ] **Step 1: Write §V** (~0.5 pg / ~280 words), condensing master draft §6.1/§6.2/§6.3. The **humanitarian close**: open, validated hazard maps as decision-support for under-resourced disaster-management and adaptation-planning agencies that cannot license commercial models; reproducible-from-free-data lowers the barrier. Then honest limits as one-liners: screening upper bound (no-pumping, no-sub-pixel, marginal-not-joint RP); the out-of-domain-HAND structural ceiling (Bangkok HR); pluvial-solver heterogeneity disclosed; Manila/HCMC deferred pending the enclosed-bay solver fix.

- [ ] **Step 2: Write §VI Conclusion** (~0.25 pg / ~140 words): first open + validated + reproducible 30 m multi-hazard ASEAN atlas; significant location skill in three cities; the open release invites extension. No new claims.

- [ ] **Step 3: Write References** — trim master draft's ~50 to ~20–25 IEEE-numbered cites actually used in this short paper (Bates 2010; Barnes 2020; Nobre 2011; Fox-Kemper/AR6 2021; Hallegatte 2013; Tellman 2021; Muis 2016/2020; Alfieri 2020; Muñoz-Sabater 2021; Zanaga 2022; Wing/Fathom 2024; Hofste/Ward Aqueduct; Sutanudjaja GLOFRIS; the city flood-event + IDF-source cites actually cited). Drop any not cited in this file.

- [ ] **Step 4: Commit.** `git commit -am "feat(ieee): §V impact + §VI conclusion + trimmed references"`

---

### Task 7: Render Figure 2 — Bangkok RP100 flood map

**Files:** Create `scripts/render_ieee_bangkok_floodmap.py`; produce `docs/paper/figures/ieee_fig2_bangkok_rp100.png`

- [ ] **Step 1: Inspect an existing renderer** to reuse its colormap/extent conventions: read `scripts/make_rp_flood_map.py` and `scripts/make_combined_flood_maps.py`. Confirm the Bangkok RP100 rasters exist: `outputs/bangkok_ssp585_2020/{coastal,fluvial,pluvial}/rp_100/*_depth_SSP5-8.5_2020_rp100.tif`.

- [ ] **Step 2: Write `scripts/render_ieee_bangkok_floodmap.py`** — load the three Bangkok RP100 depth rasters, per-pixel-max combine (mask nodata/NaN), plot with a perceptually-uniform depth colormap (e.g. `viridis`/`Blues`) over a light terrain/hillshade or plain background, add a scale bar, north arrow, colorbar (depth m), and a concise title; save 300 dpi PNG to `docs/paper/figures/ieee_fig2_bangkok_rp100.png`. Keep it single-panel and legible at column width.

- [ ] **Step 3: Run it** and verify the PNG is produced and non-trivial:
Run: `python scripts/render_ieee_bangkok_floodmap.py && python -c "from PIL import Image; im=Image.open('docs/paper/figures/ieee_fig2_bangkok_rp100.png'); print(im.size); assert im.size[0]>600"`
Expected: prints image size; assertion passes (PNG exists, reasonable resolution).

- [ ] **Step 4: Commit** (the figures dir is NOT gitignored). `git add scripts/render_ieee_bangkok_floodmap.py docs/paper/figures/ieee_fig2_bangkok_rp100.png && git commit -m "feat(ieee): render Figure 2 — Bangkok RP100 flood map"`

---

### Task 8: Final consistency + length pass

**Files:** Modify `docs/paper/ieee-r10htc.md`

- [ ] **Step 1: Numbers-match check.** Grep the new file for every quantitative claim and confirm each matches `docs/paper/draft.md`: hotspot triples (0.76/0.86/0.62, 0.56/0.86/0.42, 0.89/0.50/0.39), bias ranges (1.7–25×, 12.5×), extents (Table 2), mitigation −130 km², 28–62 %, nine configs / four countries. Fix any drift.

- [ ] **Step 2: Orphan + placeholder scan.**
Run: `grep -niE "manila|hcmc|ondoy|marikina|saigon|mekong|vung tau|NHESS|eleven|six countr" docs/paper/ieee-r10htc.md`
Expected: only the single deferred-cities sentence in §V mentions Manila/HCMC; no NHESS, no stale scope numbers. Confirm the only intentional placeholders are `[TBD — author...]`.

- [ ] **Step 3: Length estimate.** Word-count the body (excluding references): `python -c "import re,sys; t=open('docs/paper/ieee-r10htc.md',encoding='utf-8').read(); body=t.split('## References')[0]; print('words:', len(re.findall(r'\\w+', body)))"`. Target ~3,200–3,800 words body (≈6 two-column pages with 3 figs + 3 tables). If materially over, tighten §II/§IV prose; if well under, the cuts were too aggressive — restore a sentence of methods depth.

- [ ] **Step 4: Read-through** for one coherent voice and that the equity spine runs intro→impact. Fix flow.

- [ ] **Step 5: Commit.** `git commit -am "docs(ieee): final consistency + length pass"`

---

## Self-Review

**Spec coverage:** venue/format (header, Task 1) ✓; equity headline (abstract, §I, §V — Tasks 1/2/6) ✓; 4-city scope + Manila/HCMC deferred (Tasks 1/6/8) ✓; three hazards + main-stem HAND + per-country IDF (§II, Task 3) ✓; atlas + mitigation delta + Table 2 (Task 4) ✓; hotspot-gate headline + Table 3 + bathtub-bias brief (Task 5) ✓; Fig 1/3 placeholder specs (Tasks 3/5) + Fig 2 real render (Task 7) ✓; Tables 1/2/3 (Tasks 2/4/5) ✓; cuts (appendices/§3/§4.3/§5.2 — Tasks 3/4/5/6) ✓; numbers trace to master draft (Task 8) ✓; master draft unmodified (no task touches it) ✓.

**Placeholder scan:** the only deliberate placeholders are author/affiliation (spec §8 out-of-scope) and the Fig 1/3 bracketed specs (spec §5 — drawn in the template). Task 8 Step 2 enforces no others.

**Consistency:** figure paths consistent (`docs/paper/figures/ieee_fig2_bangkok_rp100.png` in Tasks 4 + 7); hotspot/bias numbers identical across tasks and to the master draft; table set (1 comparator, 2 extents, 3 hotspot) consistent between spec and plan.

## Execution Handoff
Plan complete. Recommended execution: **inline (executing-plans)** — a paper needs one coherent authorial voice, so fragmenting across fresh subagents would hurt flow; Task 7 (the figure render) is the only code step.
