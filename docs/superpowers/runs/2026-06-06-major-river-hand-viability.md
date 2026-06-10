# Major-river-referenced HAND — viability evidence (pre-Plan 8)

> **SUPERSEDED / CORRECTION (2026-06-06).** This doc concluded `acc_threshold=2000`
> (1.8 km², channel-initiation) was the winner **based on point-spot HAND only** —
> it never checked global extent. It is WRONG: thr=2000 produces an implausible
> **875 km² (25% of domain)** RP100 fluvial extent because a complete accumulation
> network + uniform overbank stage over-floods. The corrected anchor references
> HAND to the **main-stem trunk** (≥180 km² catchment, thr=200000) — see
> `2026-06-06-major-river-hand-anchor.md` §2–4. This doc is retained as an honest
> record of the misstep (the point-spot test was too narrow).

**Problem (from Plan 7).** The corrected fluvial (factor-2.06 documented bias, `--fluvial-bankfull-rp 0`)
restores **Old Klang Road** (the documented HR target, 0→0.60 m) but **over-broadens onto Bukit
Persekutuan (Federal Hill)** — a 60–77 m **hill** that the single-stage HAND model floods by 4 m,
dropping CRR 0.86→0.71. Diagnosed cause: HAND in `data/kuala_lumpur/hand_utm47n.tif` is referenced
to the OSM river mask, which **includes a hillside tributary at ~60 m DEM within 50 m of the Federal
Hill pin** (14 river cells, DEM 51–66 m, median 60 m). D8 HAND correctly assigns Federal Hill's
cells to that in-basin tributary → HAND ≈ 0–2 m → the **Klang main-stem** overbank stage (6.06 m)
floods it. But that tributary does **not** carry the GLOFAS-modeled main-stem discharge.

**Principled mitigation.** Reference HAND only to channels that carry the modeled discharge —
i.e. **flow-accumulation channels above a channel-initiation contributing-area threshold** — so
minor hillside rivulets are excluded and Federal Hill's cells route to the (far, low) main stem.

**Viability test** (`scripts/_viability_majorriver_hand.py`, accumulation drainage via
`derive_drainage_mask_from_accumulation` + `compute_hand`, HAND_min in 50 m window, overbank 6.06 m):

| Spot (class)            | thr=2000 (1.8 km²) | thr=10000 (9 km²) | thr=50000 (45 km²) |
|-------------------------|--------------------|-------------------|--------------------|
| Federal Hill (dry)      | **22.86 → dry ✓**  | 32.05 → dry       | 32.05 → dry        |
| Old Klang Road (+)      | 0.50 → FLOODS ✓    | 5.45 → FLOODS     | 5.45 → FLOODS      |
| Masjid Jamek (+)        | 1.96 → FLOODS ✓    | 1.96 → FLOODS     | 1.96 → FLOODS      |
| Jln Tun Razak (+)       | 2.58 → FLOODS ✓    | 2.58 → FLOODS     | 2.58 → FLOODS      |
| Kampung Baru (+)        | 0.00 → FLOODS ✓    | 0.00 → FLOODS     | 0.00 → FLOODS      |
| Segambut Dalam (+)      | 0.00 → FLOODS ✓    | **17.68 → dry ✗** | **19.39 → dry ✗**  |

**Selection.** `acc_threshold = 2000 px` (= 2000 × 900 m² = **1.8 km²** contributing area):
- Fixes Federal Hill (sub-threshold hillside catchment dropped → HAND 2→22.9 m → stays dry).
- **Preserves every true positive** (all flood).
- Coarser thresholds (≥9 km²) over-prune and **lose Segambut Dalam** (a documented positive on a
  smaller tributary) → too aggressive.

The threshold is anchored to **channel-initiation hydrology** (the contributing area at which a
permanent channel forms; ~1–2 km² is a standard humid-tropics value, Montgomery & Dietrich 1988/1992
range). The gate-positives are a **consistency check** (must be preserved), NOT the selection
criterion — discipline guard against gate-fitting the threshold.

**Conclusion: the mitigation is viable.** Proceed to Plan 8 (build major-river HAND at 1.8 km²,
re-run corrected fluvial, re-validate; expected Federal Hill dry → CRR restored ~0.86, Old Klang Road
floods → HR ~0.76, TSS up, clean PASS).
