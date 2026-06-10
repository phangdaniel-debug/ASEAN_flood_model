# Reviewer Q&A — Anticipated Challenges and Honest Answers

**Companion to:** `docs/paper/ieee-r10htc.md` (IEEE R10-HTC short paper) and the extended journal
form `docs/paper/draft.md`.
**Purpose:** a rigorous, adversarial self-audit. Each entry is a challenge a tough reviewer
(hydrology / remote-sensing / disaster-risk) would raise, followed by an honest answer — the
defence where there is one, the concession where there is not. Section/figure references are to
the short paper unless noted. Numbers trace to the committed dossiers, the limitations register
(`docs/limitations_register.md`), and the methodology log (`docs/hazard_methodology_comparison.md`).

> **Framing principle used throughout:** the model is sold as an *open, reproducible, validated
> screening tool*, not an engineering design product. Many objections below are fatal to an
> engineering claim but acceptable for a screening claim — the answer is to hold that line, not
> to over-claim.

---

## 1. Contribution, novelty, framing

**Q1.1 — "This is just an integration of off-the-shelf methods (HAND, bathtub/local-inertia, GEV,
fill-spill-merge). Where is the novelty?"**
Conceded: no individual hydraulic method is new, and we say so (the FSM and local-inertia
formulations are explicitly attributed). The contribution is not a new solver but (a) the
*artefact* — the first openly reproducible 30 m three-hazard, per-country-IDF-calibrated atlas
for ASEAN, a combination that does not exist; (b) the per-country calibration framework that
closes the dominant pluvial bias; and (c) the **model-blind documented-hotspot validation
protocol** with two transferable findings (the main-stem-HAND rule and the out-of-domain-HAND
limit). For a *humanitarian-technology* venue, "assembled correctly, calibrated to local
standards, validated, and given away" is the contribution; novelty-of-method is not the bar.

**Q1.2 — "Is the equity framing substantiated, or rhetoric?"**
Substantiated by a checkable fact: the only comparable-resolution three-hazard model (Fathom)
restricts free access to a country list that excludes the ASEAN megacities we cover (Table I,
footnote). That is the literal access gap. The framing is a real procurement reality for
under-resourced city agencies, not a slogan.

**Q1.3 — "Why these four cities? Cherry-picked to the ones that pass?"**
No — and the paper is explicit that three of the four validated cities *fail* a gate floor (only
Kuala Lumpur clears both). The four are the ones for which (i) the Singapore-derived validation
harness applies and (ii) the inertial
coastal solver works (boundary-connected sea). Manila and HCMC are excluded *for a stated
structural reason* (enclosed-sea topology breaks the solver), not because they look bad — they
are named as deferred future work. If anything the selection retains the awkward cases (Bangkok's
HR ceiling, Jakarta's CRR shortfall) rather than hiding them.

---

## 2. Data selection

**Q2.1 — "Why GLO-30 (30 m DSM) rather than FABDEM or LiDAR? A DSM includes vegetation/buildings
and biases flood depth."**
Three reasons, all in the paper's spirit: global free coverage without registration (the
reproducibility/equity constraint — FABDEM is free but a derivative; LiDAR is per-city, costly,
and absent for most of the region), and explicit EGM2008 referencing that aligns directly with
AR6 SLR and tide-gauge datums. The DSM-vs-bare-earth bias is real and is the single largest
driver of the bathtub over-prediction (§5.3 / limitation: sub-pixel infrastructure). We *quantify*
that bias rather than hide it, and name FABDEM/Lindsay breach-and-fill conditioning as the
documented next step. For a screening upper bound, a DSM that floods conservatively is the
defensible default.

**Q2.2 — "Why per-country IDF for pluvial but reanalysis (ERA5-Land, GloFAS) for the drivers? Isn't
that inconsistent?"**
It is deliberate, not inconsistent. The pluvial *design rainfall* must match the national design
standard because global reanalysis under-represents tropical-convective extremes by 28–62 %
(measured per city against the national IDF anchor; §II) — using ERA5-Land directly would produce
knowingly-wrong pluvial extents in three of four countries. The reanalyses are used only where a
national digitised anchor does not exist or is not the controlling quantity (e.g. river discharge
time series, which no agency publishes openly except Thailand's RID). The choice axis is "use the
authoritative local standard where it exists; fall back to open global data, documented, where it
does not" — which is the per-city implementation matrix.

**Q2.3 — "The 28–62 % IDF deficit — how was it measured, and is it cherry-picked?"**
It is the percentage shortfall of the ERA5-Land design-duration return level versus the published
national IDF anchor, computed per city at RP10/RP100 (§II). It is a range across the four
countries (Singapore −9 %, the others 28–62 %), reported as a range, not a single flattering
number. The Singapore −9 % is included precisely because it is the small one.

**Q2.4 — "Jakarta has no qualifying tide gauge and uses Muis et al. (2016) screening values
(±0.2–0.3 m at RP100). Isn't the Jakarta coastal layer therefore unreliable?"**
Yes, and we label it so — explicitly "low-confidence, screening-only." This is disclosed in the
text and is why Jakarta's coastal layer under-reaches the North-Jakarta *rob* (tidal) hotspots in
validation (a stated miss, not a silent one). We do not present Jakarta coastal as quantitative.

**Q2.5 — "WorldCover-derived runoff coefficients — where do the values (0.85 impervious, 0.15 tree,
etc.) come from, and were they validated?"**
They are standard surface-hydrology literature values for the SCS/rational-method runoff
coefficient, mapped to land-cover classes; they are screening-grade and not city-calibrated. A
reviewer is right that they are not independently validated here — the honest answer is that the
pluvial *magnitude* is set by the IDF anchor (validated), while the runoff coefficient only
modulates the *spatial distribution* of where excess accumulates; the HWM and hotspot checks test
the combined output, and the Singapore Orchard Road and Jakarta Cipinang Melayu pluvial points
fall in-band.

**Q2.6 — "Why the AR6 `wf_1e` workflow and P50 only?"**
`wf_1e` includes ice-sheet uncertainty (the dominant tail driver). P50-only is a real limitation
— we report it as such (no output uncertainty quantification; P17/P83 envelopes are named future
work). For a screening atlas the median is the headline; the absence of an ensemble is disclosed,
not concealed.

---

## 3. Methodological heterogeneity (the most likely reviewer attack)

**Q3.1 — "Different cities use different solvers and parameters. This looks like per-city tuning to
make each city 'work'. How is this not over-fitting dressed up as 'intentional heterogeneity'?"**
This is the central objection and the extended paper devotes a section to it. The distinction is
between **parameters tuned to outputs** (forbidden) and **methods selected by documented data
availability and physical regime** (required). The heterogeneity axes are all *upstream* of any
result: which tide-gauge record qualifies (≥17 yr RQ), whether a national IDF is digitised,
catchment scale (rainfall-runoff vs GloFAS), and sea topology (boundary-connected vs enclosed).
None is chosen by looking at the flood map. The cardinal rule enforced throughout the underlying
work is "the validation gate is a consistency check, never a tuning target" — and the paper
demonstrably leaves two cities *failing* a gate rather than tuning them to pass. A uniform recipe
would be *cosmetically* cleaner but would knowingly produce wrong pluvial extents in three of four
countries (Q2.2). Transparent, documented heterogeneity is the honest response to an asymmetric
data environment.

**Q3.2 — "Why local-inertia coastal for some cities and bathtub for others?"**
Solver selection is by topology, not preference. The local-inertia (Bates et al.) solver requires
the sea to connect to the DEM boundary so surge can propagate inward; where the sea is enclosed
within the domain (Manila Bay, the HCMC delta) its wall condition yields zero flux and 0 km²,
which is wrong, so those cities fall back to bathtub. All three coastal cities in the paper are
boundary-connected and use inertial. This is a hard physical/numerical constraint, documented, and
is exactly why Manila/HCMC are deferred.

**Q3.3 — "Singapore uses a 1-hour IDF; everyone else 6-hour. Convenient?"**
It is mechanism-matched, and the choice was made to match the *documented event timescale*, then
validated. Singapore's damaging floods are sub-hourly convective bursts overwhelming secondary
drains (Orchard Road 2010–11; Bukit Timah 2017); the others' controlling events are multi-hour to
multi-day (Bangkok 2011 basin flood, Jakarta 2020 ~377 mm/24 h). The 1-hour re-parameterisation
was adopted because the 6-hour primary-drain configuration put Singapore's Orchard Road HWM 0.04 m
*above* the literature band; the 1-hour secondary-drain threshold brings it in-band (0.66 m vs the
0.2–0.7 m band). The duration is set by the mechanism and *checked against an HWM*, not chosen to
flatter an extent.

**Q3.4 — "The pluvial solver itself differs across cities (a grid-routing solver for KL, fill-and-
spill for the deltas). Doesn't that undermine cross-city comparison?"**
Conceded and disclosed (§V; limitation #26). This is the one heterogeneity we call a genuine
*gap* rather than a justified choice — KL was migrated to a grid-routing solver to fix a
broad-shallow over-extent, and that fix is solver-specific. We diagnosed (a cheap mechanism test)
that the delta cities' residual over-ponding is closed-depression fill on elevated ground, *not*
the missing-drainage mechanism the KL fix addresses, so porting the KL solver would not help them
— the correct, solver-agnostic fix is DEM hydro-conditioning, named as future work. We do not
claim the pluvial layer is strictly like-for-like across cities; the cross-scenario *deltas*
(which use the same solver per city) are the robust comparison, not absolute cross-city pluvial
extents.

---

## 4. Approach selection and parameter justification

**Q4.1 — "ξ_max GEV shape caps (0.30 generally, 0.15 for Bangkok discharge) — arbitrary?"**
Caps are anchored to record length and tail behaviour, not the gate. The 0.30 cap prevents
heavy-tail runaway on the short (17–40 yr) records; Bangkok's discharge cap is tightened to 0.15
because the 2011 megaflood is a single extreme outlier in a 28-yr record that would otherwise
inflate the Fréchet tail. The longer, better-behaved coastal tide-gauge records support the
standard 0.30. The choice rule (cap by record length/tail) is stated; a sensitivity appendix
exists in the extended form.

**Q4.2 — "Bangkok's 0.42× GloFAS discharge scale is a single-gauge calibration (RID C.2,
Nakhon Sawan). One gauge for a 160,000 km² basin?"**
Conceded as a Level-1 correction with stated caveats: it is a single-point rating-curve
calibration, the tidal-adjusted stage-discharge relationship is not applied, and Level-2 (direct
RID gauge annual-maximum stage) and Level-3 (2D hydraulic model) are named improvement paths. The
0.42× is anchored to the documented RID historical RP100 (3,500–4,500 m³ s⁻¹) versus the
GloFAS-implied ~4,800 — i.e. to an external gauge, not to the flood extent. It is the best
available open anchor; its uncertainty is disclosed.

**Q4.3 — "The KL fluvial 2.06× bias and the main-stem-HAND 180 km² threshold — these smell like
knobs turned until the model floods the right places."**
This is the sharpest fair challenge, and the underlying record was written precisely to refute it.
The 2.06× is anchored to a *rainfall* ratio (ERA5-Land 6 h RP2 43.6 mm vs JPS-MSMA 90 mm), an
independent documented number, not to the flood map. The 180 km² HAND threshold is anchored to the
*modelled-discharge catchment scale* (the GloFAS reach, ~500 km² upper Klang basin) — and the
discriminating evidence is that the *highest-scoring* configuration (a 2 km² channel-initiation
threshold, TSS 0.80) was **rejected** because it floods 25 % of the domain at physically absurd
depth. Rejecting the top-scoring config on physical grounds is the discipline working in the
direction *opposite* to gate-tuning. A reviewer who suspects tuning should be pointed at that
rejection.

**Q4.4 — "The 3.0 m pluvial ponding cap, the drain capacities — documented or invented?"**
Documented: the 3.0 m cap is the engineering ponding limit (a bank rejects 4.5 m urban surface
ponding on sight); drain capacities are the national secondary/primary-drain design standards
(PUB CoP, JPS RP5, etc.). These are design anchors, not fitted values.

---

## 5. Validation rigour and believability

**Q5.1 — "You report 'statistically significant skill' but three of four cities FAIL the gate
(Singapore CRR 0.65, Bangkok HR 0.56, Jakarta CRR 0.50). Calling that 'validated' is spin."**
We do not call them PASS — the table labels them fail-CRR / fail-HR explicitly, and only Kuala
Lumpur clears both 0.70 floors. "Statistically significant skill" is a precise, separate claim:
every one of the four TSS confidence intervals excludes zero, i.e. the model is doing better than
chance at *locating* floods, which is the honest positive result. The gate *floors* (0.70) are a
stricter operational bar that the other three miss for *named, non-tunable reasons*: Bangkok's
out-of-domain source catchment (HR), Jakarta's elevated-ground over-ponding (CRR), and Singapore's
combined RP100 wet mask catching low-lying dry controls that the conservative pluvial-only layer
would spare (CRR 0.65, marginal). The paper's claim is "significant location skill with documented
ceilings," not "passes." That is a defensible and unusually candid validation statement.

**Q5.2 — "Registers of 7–8 dry controls give enormous TSS confidence intervals (e.g. KL [0.25,
0.88]). The skill estimate is barely resolved."**
Conceded — the CIs are wide and we report them rather than point estimates alone. n is small
because *clean* documented-dry controls are genuinely scarce in flood-prone deltas (in KL,
low-lying ≈ flood-prone, so naming a low 'dry' site mislabels it). The honest position: the CI
excludes zero (the qualitative claim holds) but the magnitude is imprecise; growing the registers
is named as the priority validation strand. We do not over-interpret the point estimates.

**Q5.3 — "The hotspot gate is 'model-blind', but the authors built the register. Isn't that
circular — you chose which floods to test against?"**
The model-blindness is procedural and auditable: the register is sourced from documented flood
records and frozen *before* any model raster is consulted, and the selection criteria (documented
positives; documented-dry or terrain-high negatives; geocoded + DEM-verified) are stated. The
strongest evidence against circularity is that the frozen register then *flags the model's own
failures* (the flooded controls stay in as reported false positives; the missed positives stay
as misses). A register curated to flatter the model would not retain its own counter-evidence.
The one register edit made (reclassifying Jakarta's Menteng/Gambir) is the subject of Q5.4.

**Q5.4 — "Reclassifying Jakarta's Menteng/Gambir from dry controls to positives — after seeing the
model flood them — is moving the goalposts. It conveniently lifts TSS from 0.16 to 0.39."**
The most important integrity question, and the answer is that the reclassification is anchored to
*independent flood records*, not to the model. Central Jakarta (Menteng/Cikini, the Monas/Merdeka
Palace area) is documented inundated in 2007 and 2013 — these locations *are* documented-flooded,
so labelling them "dry controls" was a factual error from the start, and the model flooding them
is *correct*. The KL precedent (limitation #21) is identical: systematic "dry" negatives that
turned out to be documented flood areas were recognised as mislabels. The test for legitimacy is
"is the correction supported by a flood record decided model-blind?" — yes. The lift to 0.39 is a
*consequence*, not the *reason*. To address the appearance, the paper can (and the extended form
does) report both the as-first-registered value and the corrected value.

**Q5.5 — "The bathtub-bias 'fix': the inertial solver gives a *smaller* extent (283 vs 3,546 km²),
but smaller is not the same as *correct*. How do you know 283 is right, not just less wrong?"**
Fair. The evidence that 283 km² is *right* (not merely smaller) is external: it falls within ~30 %
of the documented 2011 Bangkok megaflood extent (~200 km², peer-reviewed), and it was
independently reproduced "to the kilometre" against an earlier benchmark on the pipeline. The
bathtub 3,546 km² is two orders of magnitude above any documented event — it cannot be right. So
the inertial solver moves the number from "physically impossible" to "within screening tolerance
of the observed event," which is the claim. We do not claim 283 is exact; we claim the bias is a
solver-architecture artefact, and demonstrate it on a documented event.

**Q5.6 — "30 % agreement with the documented extent is loose. Hydraulic models are held to CSI > 0.5
on inundation."**
Conceded for an *engineering* model; the paper is a *screening* model on a 30 m DSM with no
pumping and a single-reach channel — held to that bar it would fail, and we say the model is not
an engineering-grade product. For screening upper bounds, order-of-magnitude correctness on
documented events plus the point-skill (hotspot) and depth (HWM) checks are the appropriate tier.
The contingency-CSI is reported but explicitly *demoted* (Q5.7).

**Q5.7 — "Your satellite extent-CSI scores are terrible (0.07–0.29). Doesn't that mean the model is
simply wrong?"**
No, and this is a substantive point we make: the CSI is *observation-limited*, not
model-limited. Urban SAR (Sentinel-1, Jakarta 2020; Malaysia 2021) blanks dense city interiors via
layover/double-bounce — exactly the areas the model characterises — leaving only peri-urban
open-water; MODIS (Bangkok 2011) is 250 m and maps a multi-month basin envelope that a steady-state
design event cannot match. A correct model is *under-scored* by these references. This is why we
make the point-based hotspot gate (insensitive to those artefacts) the primary validation and
demote extent-CSI to a caveated sanity check. A reviewer who insists CSI is decisive is implicitly
assuming the SAR reference is complete, which it is not in dense-urban Asia.

**Q5.8 — "Don Mueang HWM is OVER (3.96 m modelled vs 2.3 m reported). The model over-predicts
depth."**
Disclosed and diagnosed: the RID 2.3 m was a road-grade gauge reading during recession; the GLO-30
30 m cell aggregates the depression floor and surrounds, giving a higher neighbourhood maximum —
the 1.3× overshoot is consistent with the same 30 m DEM-averaging that drives §5.3, not an
independent failure. We report it as OVER rather than dropping it.

---

## 6. Believability of specific results

**Q6.1 — "Bangkok RP2 floods ~3,300 km² at SSP5-8.5/2100 — a 50 %-annual event drowning the whole
delta is absurd."**
It is a real reviewer reflex and we pre-empt it with an epoch decomposition: by 2100 under
SSP5-8.5 P50 the RP2 *total water level* reaches ~4.15 m EGM2008 (GEV anomaly + MDT + 1.62 m SLR),
and 77 % of the subsidence-corrected Bangkok DEM sits below 4 m — so the same *frequency* event at
a 2.8 m-higher *background mean sea level* floods most of the delta. The frequency is unchanged;
the magnitude shifted. The number is the no-pumping no-defence upper bound, and we state the
intact-defence figure would be 100–400 km². This is a consequence of honest SLR accounting, not a
bug.

**Q6.2 — "Jakarta fluvial doubled (197 → 389 km²) between paper versions. Which is right, and does
that instability undermine confidence?"**
The change is a *known model improvement*, not instability: the 389 km² uses the v2.0 main-stem-
HAND-on-defended-DEM configuration that the validation work adopted; the 197 km² was the older
atlas configuration. We re-ran the cited cells specifically so every number reflects the current
pipeline (the provenance was audited and corrected). The honest caveat, stated in validation, is
that Jakarta's fluvial layer uses a dense-HAND that over-broadens (the source of its CRR shortfall)
— so 389 km² is a screening upper bound, consistent with the model's documented behaviour.

**Q6.3 — "The mitigation delta is −133 km² against a coastal extent of ~3,500 km² with a 1.7–25×
bias. A 4 % difference inside a 25× bias is noise."**
The defence is the constant-bias argument: the bathtub bias factor is approximately constant within
a city across SSP × horizon (same solver, same DEM, same below-threshold terrain), so it
*cancels* in a within-city scenario difference. The delta is therefore far more robust than either
absolute extent — which is exactly why we present the mitigation delta, not the absolute extents,
as the policy signal. A reviewer is right that the absolute extents are bias-dominated; the delta
is the bias-robust quantity.

**Q6.4 — "Calling Singapore's canal-overflow layer 'fluvial' is misleading — Singapore has no
rivers."**
We say so verbatim in a Table footnote and a framing note: Singapore's "fluvial" layer is PUB
*primary canal-network overflow* under long-duration design rainfall, not natural-river flooding,
and readers are told to interpret it as canal-stage exceedance. The label is retained for pipeline
uniformity but explicitly redefined. This is disclosure, not misdirection.

---

## 7. Reproducibility and openness claims

**Q7.1 — "You claim 'open code' but the repository URL is TBD and the outputs are gitignored. A
reviewer cannot reproduce anything today."**
Conceded and time-bound: the public repository + tagged release + Zenodo output deposit are a
release condition of publication (the URLs are placeholders pending camera-ready). Until then the
"open" claim is a commitment, not a present fact — and a reviewer is entitled to require the link
before acceptance. The pipeline *is* reproducible by construction (every input free, every
parameter in `cities.py`, no licensed data), but the artefact must actually be posted.

**Q7.2 — "CMEMS MDT requires registration — so it is not 'free, no key'."**
Correct, and we flag it as the single input needing a credential; all others are registration-free.
The MDT is a static per-gauge scalar offset (a handful of numbers), so reproduction is not gated on
bulk-downloading it, but the asymmetry is disclosed.

**Q7.3 — "Validation uses a present-day baseline but the product is future-scenario. Are you
validating the thing you ship?"**
Partly, and we are explicit about the seam. The location-skill validation (the headline) is on the
*present-day* hazard set, because documented flood events are present-day; the shipped atlas is the
SSP × horizon grid. The link is that the *method* is identical across horizons (only the forcing
delta changes), the scenario forcing is verified consistent across the grid by an automated guard,
and the headline Table II / mitigation cells were re-run on the current pipeline. We validate the
*method and the present-day state*; the future projection inherits the method's validation plus the
AR6 forcing, and we do not claim the 2100 extents are themselves validated against observations
(they cannot be).

---

## 8. Scope, generalisability, and statistical honesty

**Q8.1 — "Why is Singapore — your methodological 'origin' city — scored differently from the rest?"**
It is not, any longer. Singapore is now in Table III scored on the *identical* v2.0 operating point
as the others (combined RP100, 0.10 m, 50 m radius): HR 0.82 / CRR 0.65 / TSS 0.47 [0.21, 0.72] —
the second-highest TSS, and significant. We re-aligned it from the flood-atlas-era convention
(pluvial-only, RP50, 150 m radius) used when the engine was first developed there; the SG model
itself is unchanged, only the scoring convention. All four cities are therefore reported on one
basis, with Singapore additionally validated in the extended form by the HWM and IDF tiers.

**Q8.2 — "Four of six ASEAN megacities. Is a four-city study generalisable to 'ASEAN'?"**
We scope the claim to the four covered cities and four countries explicitly, and present the
two-city deferral as named future work with the specific blocker (enclosed-bay solver). The
*transferable rules* (main-stem-HAND referencing; the out-of-domain-HAND limit; the
extent-CSI-is-observation-limited finding) are framed as hypotheses tested on the available cities,
not as universal laws. We avoid over-generalising from four cities.

**Q8.3 — "The whole thing rests on documented-event ground truth that is sparse and qualitative.
Is the evidentiary base strong enough for any quantitative claim?"**
This is the honest core limitation and we state it: the strongest quantitative validation tier
(agency depth-gauge transects) is outside the open-source-only scope and is named as the priority
follow-up. The present claims are deliberately calibrated to the available evidence: *significant
location skill* (hotspot, with wide CIs), *order-of-magnitude depth agreement* (HWM, 3/5 in-band),
and *structural bias correction on a documented event* (Bangkok 12.5×). We do not make a
metric-accuracy claim the evidence cannot support.

---

## 9. Internal consistency and process integrity (pre-empting "did they audit their own work?")

**Q9.1 — "Were the reported numbers actually produced by the released pipeline, or are some stale?"**
This was audited during preparation: the headline Table II / mitigation cells were found to be
inherited from an earlier model version, and were **re-run on the current pipeline** before
finalising (the coastal extents reproduced the documented benchmarks within ~1 %, confirming the
flag sets). A separate scenario-forcing inconsistency (a climate-scaling defect in non-headline
SSP/horizon pluvial cells) was found and **fixed** (regenerated by anchor interpolation; an
automated guard now passes for all configurations). Both are documented in the limitations
register. The point: the provenance was checked, not assumed.

**Q9.2 — "The model failed several of its own gates and you kept the failures in. Why should I trust
a model its authors say is partly wrong?"**
Because that is the evidence it is *not* over-tuned. A model whose authors report its failures,
keep its counter-evidence in the register, reject its own highest-scoring (but physically absurd)
configuration, and quantify rather than hide its biases is more trustworthy as a screening tool
than one reporting only successes. The honesty *is* the validation argument.

---

## 10. Quick "kill-shot" objections and one-line answers

- **"Not engineering-grade."** Correct, never claimed; it is a screening upper bound (stated three
  ways in §V).
- **"No compound/joint exceedance."** Conceded; per-pixel-max is marginal-RP; a copula framework is
  named future work.
- **"No pumping modelled."** Conceded; it is the explicit no-pumping upper-bound assumption; Bangkok
  ~250 and Jakarta ~120 pumps are named.
- **"P50 only, no uncertainty bands."** Conceded; named future work.
- **"Single representative channel geometry."** Conceded; ±0.2–0.4 m residual stage error stated.
- **"30 m can't resolve sea walls/road raises."** Conceded; it is the dominant bathtub-bias driver,
  quantified in §5.3.
- **"Deferred cities make the title oversell 'ASEAN'."** Scope stated as four cities/four countries
  in the abstract and §I.

---

### How to use this document
For each likely reviewer comment, lead with the *concession* where one is due (it disarms the
reviewer and is true), then give the *scoped defence* (screening, not engineering; documented
anchor, not gate-tuning; observation-limited, not model-limited). The recurring, defensible spine:
**open + per-country-calibrated + honestly-validated + transparently-limited**, sold as a screening
public good — not as a hydraulic design product.
