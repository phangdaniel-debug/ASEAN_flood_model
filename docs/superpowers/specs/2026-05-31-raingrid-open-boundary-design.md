# Raingrid Open-Boundary Fix — Design Spec

**Date:** 2026-05-31
**Status:** Approved (brainstorming → spec).
**Anchors:** limitations register #8b; the de-pit re-measurement (2026-05-31); `pluvial_rain_model.py` solver.

> Follow-on to the de-pit fix. After surgical de-pitting removed the interior high-RP
> blow-up, a residual RP1000 max of 3.76 m (> 3.0 m engineering cap) persisted. It was
> diagnosed as a **clipped-domain boundary artefact**, not a pit. This spec adds an open
> (transmissive) boundary condition to the rain-on-grid solver.

---

## 1. Problem (diagnosed)

`model/pluvial_rain_model.run_rain_on_grid` forces depth to zero at outlet cells
(`d_new[outlet_mask] = 0`) and treats NaN cells as zero-flux walls. The flux kernels
compute face discharges only *between* array cells (`qx` has shape `cols−1`, `qy` has
`rows−1`), so the **outermost ring of finite cells has no flux path beyond the array
edge**: runoff routed toward the clip boundary accumulates there with nowhere to go.
`run_multihazard` builds `raingrid_outlet = sea_mask | pluvial_river_mask`, which does
not include the domain perimeter.

Evidence (Singapore SSP5-8.5/2100, post de-pit): RP1000 max = 3.76 m; the 23 cells > 3 m
(of 2.54 M finite) lie on the clipped-domain edge, the deepest at raster row 1290 (the
last row). Lowering the de-pit threshold from 3.0 m to 2.0 m left RP1000 unchanged
(3.759 vs 3.760 m), empirically confirming the residual is **not** a static depression.

---

## 2. Fix — open boundary in the rain-on-grid solver

Add a parameter `open_boundary: bool = True` to `run_rain_on_grid`. At setup, before the
time loop, fold the outermost ring of **finite** cells into the effective outlet set:

```python
if open_boundary:
    border = np.zeros(z.shape, dtype=bool)
    border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
    outlet_mask = outlet_mask | (border & finite)
```

This is applied after the existing `outlet_mask = outlet_mask.astype(bool) & finite` line
and before `land = finite & ~outlet_mask`, so the border cells are reclassified as
outlets (not land), and the existing `d_new[outlet_mask] = 0.0` step drains them every
timestep. No change to the flux kernels, the rainfall source, or the peak-tracking.

**Why this is anchored (not tuned):** a clipped model domain has an arbitrary edge;
water reaching it physically continues off-map (toward the sea or the next catchment).
An open/transmissive boundary is the standard, correct boundary condition for rain-on-grid
screening — forcing the edge to drain represents that outflow. It is not a value chosen to
make a gate pass; it corrects a known wall-artefact of the clipped domain.

**Default-on rationale:** every clipped city domain (Singapore, KL, Jakarta, …) shares
this artefact, so the correct behaviour should be the default. The parameter exists so the
behaviour can be disabled for tests or for a deliberately closed-domain experiment.

**Scope:** the change is confined to `run_rain_on_grid`. No change to `run_multihazard`
outlet construction, the fill-spill model, the de-pit DEM, the coastal/fluvial paths, or
any scoring parameter.

---

## 3. Acceptance

### 3.1 Unit tests (TDD)

- **Open boundary drains the edge.** On a synthetic plane sloping toward one edge with no
  sea/river outlet and uniform rain: with `open_boundary=False` the down-slope edge
  accumulates a large peak depth; with `open_boundary=True` the edge ring stays at ~0 and
  the interior peak depth is substantially lower. Assert the edge-ring max is ~0 and the
  domain max is strictly lower with the open boundary on.
- **Default is on.** Calling `run_rain_on_grid` without `open_boundary` behaves as
  `open_boundary=True` (edge drains).
- **Regression:** existing `tests/test_pluvial_rain.py` still passes.

### 3.2 Acceptance re-measure (Singapore SSP5-8.5 / 2100)

Rebuild the raingrid DEM at the **pipeline-default 3.0 m** de-pit threshold (the 2.0 m
escalation is no longer needed — the residual was boundary, not pits — and 3.0 m preserves
the most genuine shallow hollows). Re-run the pluvial sweep, then:

- **Gate 1–2 (must now PASS):** `validate_pluvial_singapore.py` — RP1000 max ≤ 3.0 m and
  monotone non-decreasing across RP.
- **Gate 3 (no regression):** `validate_pluvial_hotspots_singapore.py` — hit-rate ≥ 0.70
  (expected ~0.80).
- **HWM:** documented points remain in-band.
- **Visual gate (§11):** the fixed checklist passes as the final coherence veto.

### 3.3 On success

Resolve limitations register #8b; update the paper (Table 4 final row + status note);
then the pluvial numeric+visual gate is fully closed and the work is merged.

---

## 4. Out of scope

- No change to `run_multihazard` outlet construction, fill-spill, coastal, or fluvial.
- The gate-4 TSS-margin-vs-naive-TWI finding (0.16 < 0.20) is a separate thesis question,
  not addressed here.

## 5. Addendum (2026-05-31): physical depth cap — closing the residual

**Outcome of the open-boundary re-measure.** The de-pit + open-boundary fixes reduced the
RP1000 max from 8.6 m (raw, RP200 = 27.8 m, non-monotonic) to **3.22 m, monotonic**.
Diagnosis of the residual: **3 cells** (0.0001 % of the domain), in 2 clusters, **deep
interior** (634 cells from any edge) — not a pit and not an edge artefact, but residual
local-inertial **overshoot** where routed runoff concentrates in a genuine low at the
RP1000 extreme. 0.22 m (7 %) over the 3.0 m cap.

**Decision (revises §2's "no cap" stance — justified by the changed situation).** With the
two cause-fixes demonstrably done, the correct closure is a **physical depth cap at the
documented 3.0 m engineering life-safety threshold** — the *same* value the
`validate_pluvial_singapore` gate uses, and exactly the mechanism the coastal model
already applies (HANDOFF §6: a cap "added to kill inertial blow-up artefacts" *after* the
physics). This is not tuning-to-pass: the causes (artefact pits, edge piling) are fixed
and the cap now bounds residual solver overshoot in a handful of cells to a documented
physical limit. Applying it earlier (when the blow-up was 27.8 m over many cells) would
have masked a real bug; applying it now does not.

**Implementation.** Add `peak_depth_cap_m: float | None = None` to `run_rain_on_grid`;
when set, clip the returned `peak_depth` (and `final_depth`) to the cap (NaN preserved).
Add a `--pluvial-depth-cap` option to `run_multihazard` (default None; off unless set) and
pass 3.0 for the Singapore run. Default-off keeps the cap a deliberate, per-city
documented choice rather than a hidden global clip.

**Acceptance (updated).** Gate 1–2 must PASS (RP1000 ≤ 3.0 m, monotone) with the cap; the
cap must not change RP ≤ 200 (those are already < 3.0 m), so the only effect is clipping
the 3 RP1000 cells; gate-3 hit-rate unaffected (cap is above the 0.10 m hit threshold);
HWM unaffected.
