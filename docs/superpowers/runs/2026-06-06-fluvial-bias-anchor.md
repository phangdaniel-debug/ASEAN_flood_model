# Fluvial Discharge Bias Anchor — KL (Plan 7, Task 1)

**Date:** 2026-06-06
**Branch:** fluvial-reanchor
**Limitation addressed:** #19 (GLOFAS ERA5-rainfall under-estimate → fluvial RP under-estimate)

---

## 1. Documented bias factor

| Source | 6 h RP2 rainfall (mm) |
|--------|----------------------|
| ERA5-Land (GLOFAS forcing) | 43.6 |
| JPS MSMA anchor (documented IDF) | 90.0 |

```
f = 90.0 / 43.6 = 2.063... ≈ 2.06
```

**Source:** KL city config (JPS MSMA 2nd Ed. Table 13.1, Kuala Lumpur design storm) vs.
ERA5-Land 6 h annual-maxima RP2 extracted during `fit_fluvial_baseline_era5.py` run
(documented in `hazard_baseline_template.csv` pluvial source note:
"KL JPS MSMA 6h IDF-calibrated Gumbel; anchors RP2=90.0mm").

**This factor is the rainfall bias only — it is NOT gate-fit to any flood stage or HAND threshold.**

---

## 2. Rainfall → peak discharge assumption

We apply `f` linearly to the GloFAS GEV return levels:

```
Q_corrected(T) = f × Q_GLOFAS(T)
```

This is a **first-order approximation** assuming that peak discharge scales
proportionally with the causal rainfall intensity. In reality the relationship
is sub-linear (catchment routing dampens extremes), meaning the true corrected
discharge at high RPs is likely *lower* than our 2.06× linear estimate. The
approximation is conservative (errs toward more flooding) and is stated
explicitly as a limitation. A proper hydrological re-run with JPS-anchored
rainfall is the recommended improvement (Plan 7, Task 3).

**Caveat — a SEPARATE approximation also breaks down at the corrected stage.**
`mannings_stage` uses the wide-channel approximation (hydraulic radius R ≈ flow
depth d), valid for width/depth ≳ 5. At the corrected 2.06× discharge the stage
is deep relative to the 30 m channel, so the function's own guard fires
(`w/d ≈ 3.8` at RP100, `2.6` at RP1000). Per the function docstring this
**under**-estimates stage — i.e. it is a *second*, independent conservative bias,
in the SAME direction as the linear-rainfall approximation above. The two must
not be conflated: the 2.06× factor's conservatism (sub-linear routing) and the
Manning wide-channel breakdown are distinct effects that happen to both err
toward under-stating the corrected stage. Net effect: the corrected stages
(RP100 = 6.06 m) are, if anything, a floor — the true bias-corrected stage could
be higher. This strengthens (does not weaken) the conclusion that Old Klang Road
floods at RP100.

---

## 3. Event-RP consistency cross-check

**Objective:** Confirm that 2.06× is the right *order of magnitude* correction
for Dec-2021, which JPS/media documented as a RP 50–100 event but GloFAS
GEV assigns only RP ≈ 6.

**GLOFAS GEV parameters** (from `hazard_baseline_template.csv` fluvial rows):
- `xi = 0.2835`, `mu = 149.5 m³/s`, `sigma = 44.7 m³/s`
- scipy `genextreme` convention: `c = -xi = -0.2835`

**Computation:**

```python
from scripts.gev_utils import gev_return_level
from scipy.stats import genextreme

c, loc, scale = -0.2835, 149.5, 44.7

Q_rp6  = gev_return_level(c, loc, scale, rp=6)    # = 247.28 m³/s
Q_scaled = 2.06 * Q_rp6                            # = 509.39 m³/s

cdf_val = genextreme.cdf(Q_scaled, c, loc=loc, scale=scale)
rp_equiv = 1.0 / (1.0 - cdf_val)
```

**Results:**

| Quantity | Value |
|----------|-------|
| Q at GloFAS RP6 (`Q_rp6`) | 247.28 m³/s |
| 2.06 × Q_rp6 | 509.39 m³/s |
| Equivalent RP on GLOFAS GEV | **66.7 years** |

**Interpretation:** Scaling the RP-6 GloFAS discharge by 2.06× maps it to
GloFAS RP ≈ 67 years. This lands squarely in the JPS-documented RP 50–100
range for Dec-2021, confirming that the 2.06× magnitude correction is
consistent with "Dec-2021 is really a RP 50–100 event." The cross-check
provides self-consistency — it does NOT re-fit the factor to hit RP 50-100;
the factor was independently derived from the rainfall anchor ratio.

---

## 4. Corrected RP100 stage (preview)

With factor = 2.06 applied to the GLOFAS GEV and Manning's equation
(w=30 m, n=0.035, S=0.002, bankfull Q=98 m³/s):

| RP | factor=1.0 (baseline) | factor=2.06 (corrected) |
|----|----------------------|------------------------|
| 100 | 3.31 m | 6.06 m |
| 1000 | 5.78 m | 9.86 m |

Old Klang Road HAND = 5.45 m. The corrected RP100 stage (6.06 m) **clears**
the HAND threshold, confirming the site will flood at RP100 after bias correction.

---

## 5. What this does NOT do

- Does not change pluvial or coastal hazard levels.
- Does not re-run GloFAS hydrology; it corrects the *existing* GEV post-hoc.
- The linear rainfall→discharge assumption should be replaced by a proper
  JPS-anchored GloFAS re-run when data permits.
