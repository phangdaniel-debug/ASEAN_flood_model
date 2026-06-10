# Main-Stem HAND Threshold Anchor — KL (Plan 8, Task 1, CORRECTED)

**Date:** 2026-06-06
**Branch:** fluvial-reanchor
**Limitation addressed:** spurious main-stem flooding of a 60–77 m hill (Bukit
Persekutuan / Federal Hill) introduced by the Plan 7 corrected fluvial.

> **Correction note.** An earlier version of this doc anchored the threshold to
> *channel-initiation* hydrology (~1.8 km², Montgomery & Dietrich) and selected
> `acc_threshold = 2000 px`. **That was wrong.** The channel-initiation network is
> spatially *complete*, and a single basin-wide overbank stage applied over a
> complete HAND raster floods every valley within 6 m of any channel → an
> implausible **875 km² (25% of domain)** RP100 fluvial extent at 4 m mean depth.
> The point-spot viability test (HAND_min at a handful of pins) missed this
> because it never checked global extent. The corrected anchor below references
> HAND to the **main-stem trunk** the GLOFAS discharge actually represents. The
> superseded channel-initiation evidence is preserved (with a correction header)
> in `2026-06-06-major-river-hand-viability.md` as an honest record of the misstep.

---

## 1. The defect

The Plan 7 corrected fluvial (documented 2.06× rainfall-bias factor) correctly
restored flooding at **Old Klang Road** (a documented hotspot) but also flooded
**Bukit Persekutuan (Federal Hill)** — a 60–77 m elevation **hill** used as a
dry control — by **4 m**, dropping CRR 0.86 → 0.71.

**Root cause.** HAND in `data/kuala_lumpur/hand_utm47n.tif` is referenced to the
**OSM river mask**, which includes a **hillside tributary at ~60 m DEM within
50 m of the Federal Hill pin** (14 river cells, DEM 51–66 m, median 60 m). D8
HAND correctly assigns Federal Hill's cells to that in-basin tributary, giving
HAND ≈ 0–2 m, so the **Klang trunk** overbank stage (6.06 m at RP100) floods the
hill. But that hillside rivulet does **not** carry the GLOFAS-modeled trunk
discharge — the OSM mask conflates a local rivulet with the modeled river.

A second, deeper finding (Plan 8): the old HAND's *bounded* extent (~116 km²) was
itself an **artifact of incomplete OSM river coverage** — only ~20% of the domain
had a mapped OSM river, so the other 80% was NaN and never flooded. It was never a
principled floodplain envelope. Any *complete* channel network (accumulation-
derived) removes that accidental bound and over-floods unless the channel
definition is restricted to the **trunk the discharge represents**.

---

## 2. The documented discharge scale (the anchor)

The KL fluvial discharge GEV is **not** a local-rivulet quantity. Per
`scripts/cities.py` (lines 285–344), the GLOFAS v4 source is **Klang R. at Shah
Alam (3.074N, 101.578E)**, chosen because it is *"the only public GloFAS reach
that captures the full upper Klang basin (**~500 km²**: upper Sg. Klang + Sg.
Gombak + all city-centre tributaries)."* The upstream **Jalan Duta point
(3.174N, 101.683E, ~50 km²) was tested and rejected** — it *"misses the Gombak
and tributary contributions, giving RP2 = 43 m³/s … too low to produce any HAND
model inundation."* Shah Alam RP2 ≈ 165 m³/s (Q_bf = 98 m³/s, RP100 ≈ 573 m³/s).

**Therefore the overbank stage we apply (6.06 m at RP100) is the stage of the
~500 km² Klang trunk.** HAND must be referenced to the **trunk channels that
carry this basin-scale discharge**, not to every accumulation rivulet.

---

## 3. The threshold and its anchor

**Chosen threshold:** `acc_threshold = 200000 px @ 30 m = 180 km²` contributing area.

```
200000 cells × (30 m × 30 m) = 200000 × 900 m² = 1.8 × 10⁸ m² = 180 km²
```

HAND (`data/kuala_lumpur/hand_mainstem_utm47n.tif`) is referenced to
flow-accumulation channels with **upstream catchment ≥ 180 km²** — a substantial
fraction (~36%) of the modeled ~500 km² Klang trunk reach. This selects the
**Sg. Klang / Sg. Gombak / Sg. Kerayong / Sg. Damansara trunk network** and
excludes:
- the **Federal Hill hillside rivulet** (catchment 2–9 km², per the threshold
  sweep — it disappears between thr=2000 and thr=10000), and
- all **sub-trunk tributaries** smaller than the modeled basin scale, consistent
  with the project's own documented rejection of the ~50 km² Jalan Duta reach as
  *"too low … misses the Gombak and tributary contributions"* — i.e. the project
  already judged that <~50 km² reaches do not represent "the Klang."

**Forward-anchored, not gate-fit.** The threshold is derived *forward* from the
documented ~500 km² modeled-discharge scale (cities.py) and the documented ~50 km²
"too-small" rejection, choosing a trunk-scale fraction of the modeled basin. It is
**not** searched for a gate-maximising value. The hotspot gate
(HR 0.76 / CRR 0.86 / TSS 0.62) is a **consistency check**, not the selection
criterion.

---

## 4. Extent-vs-threshold trade-off (the structural limitation)

The decisive evidence the point-spot viability missed — RP100 fluvial extent and
the two diagnostic spots across the full accumulation-threshold range
(`scripts/_diag_hand_extent_tradeoff.py`; HAND_min in 50 m window, overbank 6.06 m;
domain land = 3520 km²):

| thr (px) | catchment | drainage cells | RP100 extent | extent % | Federal Hill | Old Klang Rd | Segambut (fluvial) |
|---------:|----------:|---------------:|-------------:|---------:|:------------:|:------------:|:------------------:|
| 2,000    | 1.8 km²   | 55,547         | **993 km²**  | 28% ✗    | dry          | FLD          | FLD                |
| 10,000   | 9 km²     | 22,730         | 717 km²      | 20% ✗    | dry          | FLD          | dry                |
| 50,000   | 45 km²    | 8,785          | 392 km²      | 11%      | dry          | FLD          | dry                |
| **200,000** | **180 km²** | **3,002**   | **117 km²**  | **3% ✓** | **dry**      | **FLD**      | dry                |

**What this shows.** Single-stage HAND + a uniform overbank stage cannot be
simultaneously *complete* (every basin gets a channel) and *bounded* (credible
extent). Lower thresholds keep more tributary positives but over-flood
catastrophically (28% of the domain); higher thresholds bound the extent to the
trunk floodplain but reference only the trunk. The **180 km² trunk-scale choice**
gives a credible **~100 km² (3%)** extent that matches the trunk Klang floodplain.
The exact threshold within the trunk regime carries genuine modeling uncertainty —
this is the **single-stage-HAND structural limit**, documented as such, not hidden.

**Segambut Dalam** is missed by the trunk fluvial (it sits on a sub-trunk
tributary the ~500 km² GEV does not represent) but is **still a validation hit via
the pluvial model** (0.22 m) — so no documented positive is lost. Tributary-scale
fluvial flooding is honestly outside the scope of a basin-trunk GLOFAS discharge,
analogous to Taman Sri Muda being outside the modeled HAND floodplain.

---

## 5. Discipline guard — this is NOT gate-fitting

Project rule: *"done is a number, not a feeling"*; **never tune a parameter to
pass the gate.**

The 180 km² trunk threshold is anchored on grounds **independent of the gate**:
1. The documented modeled-discharge scale (~500 km² upper Klang basin, cities.py).
2. The documented rejection of the ~50 km² upstream reach as too small to be "the
   Klang" — so the channel network must be trunk-scale, not tributary-scale.
3. The Federal Hill rivulet (2–9 km²) is excluded by a wide margin on catchment
   grounds, not because it is a dry control.

That the gate-positives remain hits at 180 km² (12 via fluvial + Segambut via
pluvial) is a **consistency check**, not the selection criterion. We did not
search thresholds for a gate maximum — `thr=2000` actually scores the *highest*
gate (TSS 0.80) but is **rejected** because its 875 km² extent is physically
absurd. Rejecting the highest-scoring configuration on physical grounds is the
strongest possible evidence the threshold is not gate-fit.

---

## 6. What this task does / does NOT do

- **Does:** records the corrected trunk-scale threshold (180 km²), its documented
  discharge-scale anchor, and the extent-vs-threshold trade-off. Documentation only.
- **Does NOT:** modify source code. The HAND raster build, fluvial re-run, and
  re-validation are the subsequent Plan 8 tasks.
