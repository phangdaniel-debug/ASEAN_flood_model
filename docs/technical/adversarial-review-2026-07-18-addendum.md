# Adversarial review — 2026-07-18 addendum: closing C5/C6 (coastal sensitivity) and C7 (held-out)

Closes the top three ranked follow-ups from `adversarial-review-2026-07-09.md`:
- **#1** the C5+C6 coastal sensitivity bracket (Manning `n` and surge-window `t_end`);
- **#2** the held-out-event validation (in `docs/runs/2026-07-18-kl-held-out-event.md`);
- **#3** the physical bracketing of the handfill base stages (in model-doc §6.3.2).

This file records #1. All runs: Bangkok SSP5-8.5/2100 RP100, inertial, coastal-only,
**non-polder** (the clean single-solver basis), `repro/coastal_c6_bracket.sh`. The
non-polder shipped baseline is 919.9 km² at ≥0.10 m (the polder cell, 852.8 km², drains
the CBD and is not a single-solver comparator).

## C6 — surge-window (`t_end`) sensitivity: the finding that matters

| Run | t_end | extent (km²) | Δ vs 8 h | converged? | steps |
|---|---|---|---|---|---|
| shipped | 8 h | 919.9 | — | no (floor active) | 12,602 |
| tend16 | 16 h | 1086.2 | **+18.1%** | no (still filling) | 26,831 |

Doubling the window grows the extent **+18.1%, monotonically** (0 cells dropped, 166 km²
added), and it is **still not converged at 16 h**. So the shipped 8 h extent is a **lower
bound**, not an equilibrium.

**Why it grows — diagnosed, not assumed.** Of the 166 km² added between 8 h and 16 h,
**98.8% has bed elevation below the permanent SLR floor** (MSL 1.18 + SLR 1.62 = 2.804 m
EGM; added-cell median bed 1.47 m). The growth is the **SLR floor filling inland**, not
surge-peak truncation. This refines the 2026-07-09 review's assumption that the floor
component is not duration-limited: `subsea_init` pre-floods only below-**MSL** land, so the
**MSL-to-floor band** (1.18–2.804 m) must propagate in dynamically, and at 16 h it still is.

**What this means for the paper's bathtub-vs-inertial claim.** Decomposing the non-polder
bathtub (4418.8 km²) by the same floor:

| Bathtub component | km² | Behaviour |
|---|---|---|
| below SLR floor (< 2.804 m) | 3675.6 | inertial **approaches this as t_end→∞**; the real barrier keeping it dry is the dike + pumps, not solver travel-time |
| above SLR floor (≥ 2.804 m) | 743.2 | **durable** surge-transient over-prediction — no finite 6 h surge reaches it; a genuine solver-architecture artifact independent of t_end |

So the headline ratio is t_end-sensitive: **4.8× at 8 h → 4.1× at 16 h**, and lower
asymptotically. The top-line conclusion **survives robustly** — even the 16 h inertial
(1086 km²) is ~4× below the bathtub, and the durable above-floor artifact (743 km²) alone
is ~8× the surge-transient inertial signal. But the *precise multiple* "5.2×" is specific
to the 8 h window and, for the defended Bangkok cell, conflates three effects: defence
physics (the shipped polder), solver architecture (the durable 743 km²), and t_end
truncation of the SLR-floor fill (the sub-floor remainder).

**Disposition: OPEN → quantified.** The truncation term is now measured (≥ +18% at 16 h,
not yet asymptotic). Recommendation carried to the paper decision list (does **not** block,
does **not** silently change any number): state that the inertial extent is reported at
t_end = 8 h and is a lower bound on the SLR-floor equilibrium; if a single number is wanted
for the *durable* solver-architecture over-prediction, it is the above-floor 743 km²
(t_end-independent), not the full 8 h ratio.

## C5 — coastal Manning `n` sensitivity on the DEFENDED, overtopping-driven case

The 2026-07-12 closure measured `n` only on undefended Jakarta (n 0.06→0.10: −6.1%). This
adds the defended Bangkok-2100 case the review asked for, where overland friction governs
how far the overtopping surge propagates behind the dike — so friction should bite harder.

| Run | n | t_end | extent (km²) | Δ vs n=0.06 | IoU vs n=0.06 |
|---|---|---|---|---|---|
| n003 | 0.03 | 8 h | 1300.0 | **+41.3%** | 0.708 |
| shipped | 0.06 | 8 h | 919.9 | — | 1.000 |
| n010 | 0.10 | 8 h | 710.2 | **−22.8%** | 0.772 |

The defended case is **far more friction-sensitive** than undefended Jakarta. The same
`n` 0.06→0.10 step that moved Jakarta only −6.1% moves Bangkok **−22.8%**; the full
0.03–0.10 bracket spans 1300→710 km² (a factor of 1.8). Physically correct — behind a dike
the flooded area *is* the distance the overtopping jet runs before friction arrests it, so
`n` is first-order; on Jakarta's already-below-sea bowl the water is there regardless of
friction.

**This corrects a generalisation in the 2026-07-12 C5 closure.** That closure — measured on
undefended Jakarta — concluded "a +67% roughness change moves the headline extent by ~6%,
an order of magnitude below the bathtub↔inertial gap." That holds for undefended coasts but
**does not generalise to defended deltas**: on Bangkok the same change moves extent ~23%,
and friction is a first-order lever, not a screening-tolerance afterthought. Two things keep
this from undermining the shipped product: (1) the shipped Bangkok cell uses the **polder**,
which removes the friction-sensitive overtopping interior (the CBD) from the scored extent;
(2) even the n=0.03 extreme (1300 km²) is ~3.4× below the bathtub (4419 km²), so the
solver-choice conclusion is unchanged. But the honest statement is now regime-split: the
Manning lever is **≈±6% on undefended subsided coasts, ≈±25–40% on defended overtopping
deltas** — and the latter is a disclosed sensitivity, not a closed one, on any future
non-polder defended-delta cell.

## Net

Both C5 and C6 are now **measured, not asserted**, and each surfaced a caveat the
single-case earlier work had missed:
- **C6:** the 8 h inertial extent is t_end-truncated (+18% at 16 h, still filling); the
  growth is SLR-floor propagation, and the durable solver-artifact over-prediction is the
  above-floor 743 km², not the full 8 h ratio.
- **C5:** the Manning lever is regime-dependent — ~±6% undefended (Jakarta) but ≈±25–40%
  on defended deltas (Bangkok); the 2026-07-12 "friction barely matters" line is corrected
  to that regime split.

Neither overturns a shipped number (the Bangkok polder cell removes the friction- and
t_end-sensitive interior; every alternative is still ~3–4× below the bathtub). Both belong
in the paper's disclosure. Two items now warrant a paper-side **decision** (neither actioned
here — out of scope for a sensitivity pass):
1. Frame the bathtub-vs-inertial ratio as t_end = 8 h-specific, and/or report the durable
   above-floor over-prediction (743 km²) as the t_end-independent figure.
2. Replace the Jakarta-only "friction ~6%" reassurance with the regime split.

`run_multihazard` now prints `converged`/`n_steps` per coastal cell so any future run
records which regime it is in. Bracket outputs: `outputs/_diag/c6_bracket/{tend16,n003,n010}`.
