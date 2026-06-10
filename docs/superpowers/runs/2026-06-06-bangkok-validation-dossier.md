# Bangkok Validation Dossier (Plan B1) — first validation, existing model

**Date:** 2026-06-06
**Run:** present-day Bangkok baseline, `outputs/bangkok_ssp585_2020/` (RP100 only — the
2011-event RP — generated for validation; full 9-RP baseline deferred, see §5). Model:
the **existing** Bangkok config (NO changes) — subsidence-corrected DEM, fill-spill pluvial,
inertial coastal, OSM-river HAND fluvial (`--fluvial-bankfull-rp 0` behaviour).
Validation-first per Plan B1.

## 1. Method

Primary gate: documented-hotspot **HR / CRR / TSS** via the generalized
`scripts/validate_hotspots.py --city bangkok` (unions pluvial ∨ fluvial ∨ coastal — Bangkok
is a delta, so coastal is included). Register: **16 in-domain 2011-flood positives + 7
defended-core dry controls**, model-blind (positives = documented 2011 inundation; dry
controls = the bunded CBD documented dry behind the King's-Dyke/sandbag line — the 2011
"tale of two cities"). Supporting diagnostic: the THA2011 extent-CSI.

## 2. Numeric gate (RP100, threshold 0.10 m, radius 50 m)

| Metric | Value | Floor | Verdict |
|---|---|---|---|
| Hit-rate (HR) | **0.62** (10/16) | 0.70 | FAIL |
| Correct-reject-rate (CRR) | **0.43** (3/7) | 0.70 | FAIL |
| TSS | **0.05** [95% CI −0.38, 0.48] | — | no significant skill |

**GATE FAIL.** RP100 hazard extents (sanity): coastal 135 km² (present-day, no SLR — cf. the
~283 km² SSP5-8.5/2100 +SLR benchmark), pluvial 466 km² (fill-spill), **fluvial 820 km² at
only 0.58 m overbank**.

## 3. Per-spot diagnosis — two clean, KL-identical fluvial failures

**(a) Fluvial OVER-broadening → CRR crash (0.43).** 4 of 7 defended-CBD dry controls —
**Silom, Sathorn, Sukhumvit, Pathum Wan/Siam** — are flooded **by the fluvial hazard at
exactly 0.58 m**. The old **OSM-river single-stage HAND** applies one uniform overbank stage
to every cell near any mapped channel; on the flat Bangkok delta this spreads 0.58 m of
"fluvial" water across the low-lying bunded core that documentably stayed dry in 2011. This
is **the same single-stage-HAND over-broadening artifact KL had** (Federal Hill, pre-Plan-8).

**(b) Fluvial UNDER-magnitude → HR miss (0.62).** 6 of 16 positives — **Sai Mai, Lam Luk Ka,
Bang Bua Thong, Pak Kret, Mueang Nonthaburi, Thawi Watthana** (outer Nonthaburi / Pathum
Thani belt) — are dry (0.00 m). The 0.58 m design-RP overbank cannot reproduce the
**basin-scale 2011 megaflood** that inundated these upstream districts (GLoFAS calls 2011
~RP6 — the ERA5 precipitation under-estimate, documented for Bangkok exactly as for KL). The
caught positives are the in-city low spots (Don Mueang, Bang Sue, Khlong Sam Wa, Bang Khen…)
picked up by pluvial ponding + near-channel fluvial.

The **same 0.58 m fluvial stage is simultaneously too broad and too weak** — the signature of
the combined single-stage-HAND + GLoFAS-bias double-issue.

## 4. Supporting diagnostic — THA2011 extent-CSI

Documented (prior full-scenario run, `validate_historical_events.py`): **THA2011 CSI 0.29 /
H 0.90 / FAR 0.70 (WARN)** — the model catches 90% of the MODIS-observed 2011 flood but
over-predicts (FAR 0.70). This is **consistent** with the hotspot finding: high catch (the
flood is broadly reproduced) but poor specificity (over-broad fluvial). A clean RP100 re-run
of the CSI is deferred with the full-baseline regen (§5).

## 5. Verdict + next (evidence-driven fixes — B2)

**Bangkok present-day FAILS the hotspot gate (HR 0.62 / CRR 0.43 / TSS 0.05).** But — exactly
as validation-first intends — the failure is **cleanly diagnosed** and maps **directly onto
the already-validated KL playbook**:

1. **Main-stem HAND (limitation #20)** — rebuild Bangkok's HAND from flow-accumulation
   channels at the Chao Phraya trunk scale (not raw OSM rivers), to stop the 0.58 m overbank
   flooding the defended CBD. Expected: CRR recovers (the defended core clears).
2. **Documented GLoFAS discharge bias (Plan 7 analog)** — Bangkok's 2011 = GLoFAS ~RP6 vs
   observed RP50–100; a documented TMD/ERA5 rainfall-bias factor raises the fluvial discharge
   so the outer basin-scale flooded districts are reached. Expected: HR recovers.

Both are **documented-fact-anchored** (the catchment-scale trunk; the rainfall-bias ratio),
not gate-tuned. **Cardinal rule:** the flooded defended-CBD dry controls **STAY** in the
register — they are a real finding (the steady-state model represents neither the 2011
emergency King's-Dyke defense nor a trunk-scale HAND), reported, never dropped to pass.

**Deferred:** the full 9-RP Bangkok baseline (the inertial coastal solver is ~50 min/RP →
~8 h for 9 RPs; an inertial-solver parallelization analogous to `--raingrid-workers` is the
matching perf lever). The RP100 validation above is sufficient for the verdict.

**Status:** Plan B1 (Bangkok foundation + first validation) COMPLETE — the generalized
multi-city validator, the four-manifest contract, and the model-blind register are in place,
and the first gate has revealed the exact, documented fixes Bangkok needs. The KL→Bangkok
transfer is working as designed.

---

## 6. Plan B2 — fluvial fix attempts + the structural ceiling (and a correction to the B1 premise)

B2 set out to recover HR + CRR with the KL playbook (main-stem HAND + documented bias).
**The evidence overturned the B1 premise** (§5: "bias raises discharge → HR recovers") and
is recorded honestly. Three fluvial methods were tested; all hit the *same* wall.

### 6.1 What the B1 premise got wrong
B1 read the HR miss as **under-magnitude** (the 0.58 m klong stage too weak; raise discharge).
That is wrong. The missed positives are the **northern Nonthaburi / Pathum Thani / Don-Mueang
belt**, and they did not flood from *in-domain* forcing — they flooded because the Chao
Phraya's **160,000 km² catchment overflowed far upstream (Ayutthaya)** and the flood wave
propagated **into** the 5,443 km² model domain from the north as an overland sheet. The
"~RP6 ERA5 under-estimate" framing was mis-transferred from **KL's Dec-2021** event; Bangkok
2011 is the **record outlier** in the GLoFAS series, not RP6. The HR gap is a
**boundary-condition** problem, not a discharge-magnitude problem.

### 6.2 Three methods, one wall (RP100, threshold 0.10 m, radius 50 m)

| Fluvial method | HR (fluvial→composite) | CRR | Why |
|---|---|---|---|
| B1 dense OSM-river HAND | 0.62 | 0.43 | over-broad: CBD khlong cells = HAND≈0 → core floods |
| **Hydrodynamic riverine** (inertial solver, per-cell WSE BC) | — | — | **intractable**: thin-film `q/h` CFL collapse along the domain-spanning channel (dt→0); **and** sustained-WSE equilibrium over-floods the flat, highly-connected delta (915k cells at t=0.09 h, still climbing) |
| Trunk-only HAND (acc≥100000) on **defended DEM** | 0.25 → **0.56** | **0.86** | excludes CBD khlongs + King's-Dyke burned → CRR fixed; but D8 routing **cannot connect the northern out-of-domain districts** to the in-domain trunk → they go NaN → missed |

The hydrodynamic attempt (the "rigorous, heavy" route) is the important negative: the
inertial solver built for **edge-injected coastal** fronts does not transfer to a
**domain-spanning fluvial source** — thousands of simultaneous wetting fronts collapse the
CFL timestep, and even if fixed, flat-delta equilibrium fills everything connected. Both the
solver mode (`model/inertial_wave_model.py` riverine array-BC, TDD'd) and the runner
(`scripts/build_riverine_fluvial.py`, head anchored to the documented 2011 floodplain depth
1.5–3 m — **not** the 7.11 m HAND-convention Manning-stage, a category error caught by the
bed-elevation diagnostic) are kept as a capability + recorded finding.

### 6.3 The validated composite + verdict

**Composite (pluvial ∨ trunk-HAND-fluvial ∨ coastal), defended DEM, RP100:**

| Metric | B1 | **B2** | Floor |
|---|---|---|---|
| HR | 0.62 (10/16) | **0.56 (9/16)** | 0.70 — **FAIL** |
| CRR | 0.43 (3/7) | **0.86 (6/7)** | 0.70 — **PASS** |
| TSS | 0.05 [−0.38, 0.48] (no skill) | **0.42 [0.04, 0.75]** (CI excludes 0) | — |

**B2 converted a "flood-everything" no-skill model (TSS 0.05) into one with significant
discriminative skill (TSS 0.42) and strong specificity (CRR 0.43→0.86).** The trunk-HAND on
the defended DEM removed the CBD over-broadening; the lone CRR miss is Sukhumvit (1.97 m
HAND, a borderline near-channel cell).

**The HR gate fails (0.56), and this is an HONEST STRUCTURAL CEILING, not a tuning target.**
The 7 missed positives are the out-of-domain-sourced northern districts — the connectivity
that protects the CBD (trunk-HAND) is the *same* connectivity that disconnects the northern
flood. No model driven by in-domain forcing + in-domain drainage topology can reach them.
This is **limitation #8 made quantitative**. Per the **cardinal rule**, the flooded dry
controls and the missed positives **STAY** in the register — the gate reveals the ceiling; we
do not tune to it. Recovering HR would require explicitly injecting the out-of-domain flood
as a **north-boundary inflow** (a documented-stage boundary condition + tractable routing) —
logged as the future lever, deliberately NOT forced here.

**Bangkok present-day verdict: CRR-strong, significantly skilful (TSS 0.42), HR-limited by
the documented out-of-domain Chao Phraya source (#8).** A legitimate honest ceiling in the
same spirit as KL's structural ceilings (§9–§11 of the KL dossier). The B2 fluvial
(`data/bangkok/hand_trunk_defended_utm47n.tif` → `outputs/.../fluvial/rp_100/`) supersedes
the B1 klong artifact (backed up alongside).
