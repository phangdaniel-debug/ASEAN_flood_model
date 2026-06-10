# The verdict is in the test: naive baselines, dry controls, and operating points in open flood-model validation

*Submission type: Advances in Modelling Practice (problem-and-solution). Author, affiliation,
venue details TBD. Corresponding author: phang.daniel@gmail.com.*

---

## Abstract

Comparative validation of urban flood models is more fragile than it looks. Using a fully open
multi-hazard model for Singapore scored against the official PUB flood-prone register, we show
that the *same* model on the *same* data yields four different verdicts depending only on how the
test is set up. (i) Scored by hit-rate or ROC-AUC against the register alone, the model looks
"validated" (AUC 0.65). (ii) Add the naive baseline a practitioner would otherwise use — a
topographic wetness index (TWI) — and it scores *higher* (0.75): the calibrated model does not
out-locate free topography. (iii) Compare specificity at a fixed depth threshold and the model
looks "significantly more specific" (it floods 1.85% of land versus TWI's 15%) — but that is an
artifact of operating at far lower sensitivity; at matched specificity TWI's hit-rate (0.71) beats
the model's (0.39). (iv) The verdict even swings with the negatives chosen: against random land the
model discriminates significantly better (ΔAUC +0.14, 95% CI [+0.04, +0.24], stable across
samples), yet against low-lying-but-dry developed areas — the decision-relevant case — the two
are statistically indistinguishable (0.65 vs 0.75; ΔAUC −0.10, CI spans zero). We distil a *documented-register
benchmark* and a short checklist that make such comparisons honest: include naive baselines and two
tiers of documented dry controls, prefer threshold-free metrics, compare at matched operating
points, and attach paired bootstrap confidence intervals. The lesson is general: a flood model's
measured "skill" is as much a property of the test as of the model.

**Keywords:** flood model validation; modelling practice; naive baselines; ROC-AUC; operating point

---

## 1. The problem in practice

Comparative flood-model validation is usually reported as a single number — a hit-rate or a
ROC-AUC against an inventory of known flood locations — and read as evidence that the model works,
or that calibration beats a simpler alternative. That number is more fragile than it appears.

Most of what a flood register records is **low-lying convergent ground**, which *any* method that
flags low ground will capture; a model that floods the wettest fraction of the terrain, with no
rainfall and no calibration, can match a calibrated hydraulic model on such a test. And the
outcome of a comparison turns on choices that are rarely stated: whether a naive baseline is
included at all; which negatives (if any) are used; at what operating point the methods are
compared; and which metric. Change those, and — as we show below — the *same* model on the *same*
register can read as "validated," "no better than topography," "significantly more specific," or
"better only against the general landscape."

This is a problem of modelling *practice*, not of any one model, and it is cheap to fix. We
demonstrate it concretely on an open model for Singapore and give a small, reproducible discipline
that makes the comparison robust and honest.

## 2. The discipline: a documented-register benchmark

The benchmark has five ingredients, each closing one route by which a comparison misleads. Every
component is reproducible in any city that publishes a flood register.

**(a) Positives from an authoritative register.** Use the official register the responsible
authority maintains (for Singapore, the PUB *List of Flood-Prone Areas*), and geocode each entry
with an authoritative gazetteer rather than by hand; cross-check coordinates against the terrain,
because a hand-placed pin in the wrong hollow silently corrupts the score.

**(b) Documented dry controls — in two tiers, and treated as a design choice.** A hit-rate-only
score is gamed by flooding everything; documented *negatives* stop that. Include *elevated* sites
(robust true negatives) **and** low-lying developed areas conspicuously *absent* from the
comprehensive register (discriminating negatives). Crucially, **the negative set is itself a
choice that changes the verdict** (§3): a method can look strong against random land and weak
against low-lying-but-dry land. Report against both, and select all controls by a neutral rule
*before* inspecting any model output.

**(c) Naive open baselines.** Score, on identical points, the open methods a practitioner would
otherwise reach for: a *Topographic Wetness Index* (TWI = ln(a/tan β); Beven & Kirkby, 1979), and,
to triangulate, a second structurally independent index such as *Topographic Position Index*
(local depression depth). Beating these by a clear margin — not merely beating chance — is the
real test of whether calibration adds value.

**(d) Threshold-free metrics, compared at matched operating points.** Report a threshold-free
ROC-AUC (Hanley & McNeil, 1982), not only a single depth cutoff. A fixed cutoff **confounds
"specificity" with how much land a method floods**: a conservative model that wets little land will
reject most negatives regardless of skill. If a fixed operating point is reported, compare methods
at *matched* sensitivity or specificity, not at each method's arbitrary default. Pair this with the
gaming-resistant True Skill Statistic (TSS; Peirce, 1884; Hanssen & Kuipers, 1965) computed against
the dry controls.

**(e) Uncertainty.** Registers are modest (tens of points), so attach a **paired bootstrap
confidence interval** (Efron & Tibshirani, 1993) to every model-vs-baseline difference, and treat a
comparative claim as supported only when the interval excludes zero. Fix the scoring parameters
(neighbourhood radius, depth threshold, anchor return period) before seeing results.

## 3. Worked example: one model, four verdicts

**The model (the vehicle, not the contribution).** We built a fully open, commercial-safe,
*screening-grade* multi-hazard model for Singapore at 30 m: a local-inertial rain-on-grid pluvial
layer (Bates et al., 2010) on an independently derived bare-earth surface — Copernicus GLO-30
(ESA/Airbus, 2022) with buildings removed using Google Open Buildings footprints (Sirko et al.,
2021), avoiding the non-commercial FABDEM — plus Height-Above-Nearest-Drainage fluvial (Nobre et
al., 2011) and a bathtub coastal layer on tide-gauge GEV levels (Coles, 2001; Caldwell et al.,
2015) with AR6 sea-level rise (Fox-Kemper et al., 2021). The pluvial layer carries the comparison;
full model details are reported separately. One fact matters for what follows: the rain-on-grid is
forced by a *net-excess* depth (design rainfall minus design drainage capacity), which at a 50-year
return period is only ~4 cm, so the model floods just **1.85% of land** at ≥0.10 m — versus TWI's
15% by construction. It is, by design, conservative.

We score the pluvial layer against all 36 PUB flood-prone areas (authoritatively geocoded) plus two
depth-bearing historical events — 38 positives — and 20 documented dry controls. The same model and
data give four verdicts:

**Verdict 1 — "validated."** Hit-rate / ROC-AUC against the register alone: AUC 0.65. Reported on
its own, the model reads as validated.

**Verdict 2 — "no better than topography."** Add the naive wetness index on the same points: TWI
scores AUC 0.75, *higher* than the model, and the paired difference is not significant (ΔAUC −0.10,
95% CI [−0.32, +0.11]); the TSS comparison is likewise indistinguishable. The register is mostly
low convergent ground a free index already captures (its hit-rate is 0.92). The calibrated model
does not out-*locate* topography.

**Verdict 3 — "significantly more specific" (an operating-point artifact).** At a fixed 0.10 m
threshold the model correctly rejects 65% of dry controls versus TWI's 30%, which reads as a large
specificity win. But the model floods one-eighth the land of TWI, so it is being compared at a far
lower sensitivity. Hold specificity equal — threshold TWI to the same correct-reject rate — and
TWI's hit-rate is **0.71** against the model's **0.39**. The "advantage" is a property of the
operating point, not of discrimination.

**Verdict 4 — "better, but only against the general landscape."** The verdict swings with the
negatives chosen (Figure 1). Against random land the model discriminates flood-prone terrain
*significantly* better than TWI (ΔAUC +0.14, 95% CI [+0.04, +0.24] at n=300, point estimate
+0.12 to +0.28 and excluding zero in five of six random samples) — a genuine, threshold-free edge.
But against the low-lying-but-dry developed areas — the case that governs false alarms in a
low-lying city — the two are **statistically indistinguishable** (model 0.65, TWI 0.75; ΔAUC −0.10,
95% CI [−0.32, +0.11]): TWI is nominally higher, but the difference is within sampling noise. The
model finds flood-prone ground in the landscape better than a wetness index; it does *not*
distinguish flood-prone *low* ground from ordinary *low* ground any better than topography does.

![Figure 1. The comparative verdict swings with the negative set (present-day field, 38 flood positives). Left: against low-lying-but-dry developed areas (the decision-relevant negatives), the naive wetness index (TWI) is nominally higher than the calibrated model (AUC 0.75 vs 0.65) but the difference is not significant (paired ΔAUC −0.10, 95% CI [−0.32, +0.11]) — a tie. Right: against random land, the model ranks significantly better (0.76 vs 0.59; ΔAUC +0.14, CI excludes zero). The same two methods, opposite conclusions, from the choice of negatives alone.](figures/fig5_roc_flip.png)

**Figure 1.** The same two methods give opposite verdicts depending only on the negative set.

**Synthesis.** From one model and one register we obtained "validated," "no better than
topography," "significantly more specific," and "better only against random land" — the conclusion
was set by the test design, not by the model. The model's *defensible* value is not superior
location skill but the things a wetness index cannot provide at all: a physical depth field, an
explicit drainage mechanism, and climate-scenario projection. A validation that reports only a
hit-rate would have claimed far more.

## 4. Tangible takeaways

A checklist to make open flood-model comparisons honest and portable:

1. **Anchor positives to an authoritative, current register**; geocode with a real gazetteer (not
   hand-typed pins) and cross-check against the terrain.
2. **Always include at least one naive open baseline** (a wetness index). If free topography
   matches your model, calibration has not earned a location claim — say so.
3. **Include documented dry controls in two tiers** — elevated, and low-lying developed sites
   absent from the register — selected model-blind. **Report against both random and discriminating
   negatives, and expect the verdict to depend on which**: a model can win against the landscape and
   lose against low-lying-but-dry land.
4. **Prefer threshold-free metrics (ROC-AUC).** A fixed depth cutoff confounds "specificity" with
   how much land a model floods; a conservative model looks specific for the wrong reason.
5. **If you report a fixed operating point, compare at matched sensitivity or specificity** — never
   at each method's arbitrary default (15% wettest land for an index, a depth threshold for a
   model).
6. **Attach paired bootstrap confidence intervals**; claim a comparative result only when the
   interval excludes zero.
7. **Pre-register the scoring parameters** and resist moving them to improve the verdict.

## 5. Transferability and limitations

The benchmark is city-agnostic: every ingredient is reproducible wherever an authority publishes a
flood-prone register, and the whole test runs in seconds once the rasters exist. We demonstrate it
on a single city and a single comparative hazard (pluvial); establishing how strong a baseline
naive topography is *across* cities is the natural next study, strongest where mapped event extents
also exist (enabling an extent-based Critical Success Index). The register is modest (38 positives,
20 controls), so no model-vs-topography ranking is supportable in either direction with confidence —
which is itself the point. The contribution here is not the Singapore numbers but the practice: a
documented-register benchmark with naive baselines, two-tier dry controls, threshold-free metrics,
matched operating points and confidence intervals turns "my model flags the known flood spots" —
which proves little — into a defensible, reproducible statement about whether, and on which axis,
calibration adds value.

## Data and code availability

The model, the documented register (positives and dry controls), the validation code, and the
figure scripts are openly available at [repository / DOI — TBD]; reported numbers are frozen at
commit [hash — TBD]. All inputs are open and licensed for commercial use.

## References

Bates, P. D., Horritt, M. S., & Fewtrell, T. J. (2010). A simple inertial formulation of the
shallow water equations for efficient two-dimensional flood inundation modelling. *Journal of
Hydrology, 387*(1–2), 33–45.

Beven, K. J., & Kirkby, M. J. (1979). A physically based, variable contributing area model of
basin hydrology. *Hydrological Sciences Bulletin, 24*(1), 43–69.

Caldwell, P. C., Merrifield, M. A., & Thompson, P. R. (2015). *Sea level measured by tide gauges
from global oceans — the Joint Archive for Sea Level holdings (NCEI Accession 0019568).*
University of Hawaii Sea Level Center. https://doi.org/10.7289/V5V40S7W

Coles, S. (2001). *An introduction to statistical modeling of extreme values.* Springer.

Efron, B., & Tibshirani, R. J. (1993). *An introduction to the bootstrap.* Chapman & Hall/CRC.

European Space Agency, & Airbus. (2022). *Copernicus Global Digital Elevation Model (GLO-30).*
Copernicus DEM Product Handbook.

Fox-Kemper, B., Hewitt, H. T., Xiao, C., et al. (2021). Ocean, cryosphere and sea level change.
In *Climate change 2021: The physical science basis* (pp. 1211–1362). Cambridge University Press.

Hanley, J. A., & McNeil, B. J. (1982). The meaning and use of the area under a receiver operating
characteristic (ROC) curve. *Radiology, 143*(1), 29–36.

Hanssen, A. W., & Kuipers, W. J. A. (1965). On the relationship between the frequency of rain and
various meteorological parameters. *Mededelingen en Verhandelingen, 81.* KNMI.

Nobre, A. D., Cuartas, L. A., Hodnett, M., et al. (2011). Height Above the Nearest Drainage — a
hydrologically relevant new terrain model. *Journal of Hydrology, 404*(1–2), 13–29.

Peirce, C. S. (1884). The numerical measure of the success of predictions. *Science, 4*(93),
453–454.

PUB, Singapore's National Water Agency. (2025). *List of flood-prone areas in Singapore (as at
Nov 2025).* https://www.pub.gov.sg

Sirko, W., Kashubin, S., Ritter, M., et al. (2021). *Continental-scale building detection from
high-resolution satellite imagery* (arXiv:2107.12283).
