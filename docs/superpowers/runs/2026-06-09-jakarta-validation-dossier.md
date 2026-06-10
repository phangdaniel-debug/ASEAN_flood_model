# Jakarta Validation Dossier (Plan J1) — first validation, existing model

**Date:** 2026-06-09
**Run:** present-day Jakarta baseline, `outputs/jakarta_ssp585_2020/` (RP100 only — the
JKT2020-event RP; full 9-RP deferred, see §6). Model: the **existing** Jakarta config (NO
changes) — subsidence-corrected DEM (`copernicus_dem_utm48s_subsidence_corrected.tif`),
fill-spill pluvial, **inertial** coastal (boundary-seeded; Jakarta Bay at the north edge),
single-stage Ciliwung HAND fluvial (`hand_utm48s.tif`, `--fluvial-bankfull-rp 0`).
Validation-first per the J1 spec.

**Resolved run command (run_multihazard, RP100-only CSV):** `--dem …_subsidence_corrected.tif
--fluvial-hand-raster hand_utm48s.tif --sea-mask-raster sea_mask_utm48s.tif
--tidal-channel-raster river_mask_utm48s.tif --tidal-burn-elevation 2.0 --coastal-solver
inertial --coastal-msl-egm2008 0.9976 --pluvial-model fillspill --pluvial-depth-cap 3.0
--runoff-coeff 0.80 --runoff-coeff-raster runoff_coeff_utm48s.tif --fluvial-bankfull-rp 0`.

## 1. Method

Primary gate: documented-hotspot **HR / CRR / TSS** via `scripts/validate_hotspots.py --city
jakarta` (unions pluvial ∨ fluvial ∨ coastal). Register: **16 recurrent, mechanism-spanning
positives + 7 dry controls**, model-blind (research doc
`…/runs/2026-06-09-jakarta-hotspot-research.md`): Ciliwung-corridor fluvial (Kampung Melayu,
Bukit Duri, Kampung Pulo, Cawang, Rawajati, Bidara Cina), monsoon pluvial / secondary rivers
(Cipinang Melayu, Kemang, Kelapa Gading, Grogol, Cengkareng), North-Jakarta rob/coastal
(Penjaringan, Pluit, Muara Baru, Kalibaru, Cilincing); dry controls = genuinely-elevated south
(Cilandak, Jagakarsa, Lebak Bulus, Pasar Minggu, Cipete) + documented-dry central natural-levee
(Menteng, Gambir). **Elevated support gate:** JKT2020 Sentinel-1 extent-CSI.

**Provenance note (resolved-as-found):** the J1 spec anticipated a "pluvial = ERA5-Land, not
IDF-calibrated" gap. **It is already closed** — the committed Jakarta pluvial baseline is a
**BMKG 6h IDF-calibrated Gumbel** (`hazard_baseline_template.csv` 2026-05-16; xi=0, μ=77.21 mm,
σ=21.26 mm; RP2=85 mm, RP100=175 mm). Only the `cities.py` docstring still describes the
superseded ERA5-Land path. So Jakarta's pluvial forcing is IDF-anchored like KL/Bangkok.

## 2. Numeric gate (RP100, threshold 0.10 m, radius 50 m)

| Metric | Value | Floor | Verdict |
|---|---|---|---|
| Hit-rate (HR) | **0.88** (14/16) | 0.70 | **PASS** |
| Correct-reject-rate (CRR) | **0.29** (2/7) | 0.70 | **FAIL** |
| TSS | **0.16** [95% CI −0.19, 0.57] | — | no significant skill (CI includes 0) |

**GATE FAIL (CRR).** RP100 hazard extents (existing model): pluvial **158.9 km²**, fluvial
**374.9 km²**, coastal **98.9 km²** (coastal matches the documented NCICD RP100 ~80 km² North
Jakarta benchmark — plausible). HR is strong out of the box; CRR crashes.

## 3. Per-spot diagnosis — the CRR failure is single-stage-HAND over-broadening (KL/Bangkok-identical)

Per-cell max depth (m) at each register point, by hazard:

| Dry control | pluvial | fluvial | coastal | verdict |
|---|---|---|---|---|
| Cilandak | 0.00 | 0.00 | 0.00 | **correct reject** ✓ |
| Lebak Bulus | 0.00 | 0.00 | 0.00 | **correct reject** ✓ |
| Jagakarsa (53 m elev) | **1.77** | 0.00 | 0.00 | FP — **pluvial over-pond on high ground** |
| Pasar Minggu | 0.94 | 1.28 | 0.00 | FP — pluvial + fluvial |
| Cipete (36 m elev) | 0.00 | **3.27** | 0.00 | FP — **fluvial** |
| Menteng (levee, 10 m) | 0.18 | **4.30** | 0.00 | FP — **fluvial** |
| Gambir (Monas, 11 m) | 0.00 | **4.30** | 0.00 | FP — **fluvial** |

**(a) Fluvial over-broadening → the CRR crash.** The fluvial layer applies a uniform **4.30 m**
RP100 overbank (= 3.91 m × 1.1 SSP585 factor) to every cell within 4.30 m of *any* mapped
channel via the **dense single-stage Ciliwung HAND** (`hand_utm48s.tif`). On flat, low Jakarta
this floods the central-levee core (Menteng, Gambir at 4.30 m) and even elevated Cipete — the
**exact** over-broadening artifact KL fixed with main-stem HAND (#20) and Bangkok hit at B1.
This single dense-HAND defect accounts for 4 of the 5 flooded dry controls.

**(b) Pluvial over-pond on high ground.** Jagakarsa (53 m, the highest dry control) floods 1.77 m
from the **fill-spill pluvial** — ponding on elevated terrain, the same mechanism as KL's Bukit
Antarabangsa (drainage/DEM-conditioning, not depth). Secondary CRR contributor.

## 4. Hit-rate — what the 2 misses are

14/16 positives caught. The 2 misses are both **documented structural** boundaries, not tuning
gaps:
- **Kemang** (DRY) — flooded Jan-2020 from the **Krukut** river, which is NOT the modeled
  Ciliwung reach (single-reach limitation; Jakarta's ~12 other rivers are unrepresented).
- **Penjaringan** (fluvial 0.07, coastal 0.00) — a North-Jakarta **rob** positive the coastal
  layer under-reaches. Coastal floods only Pluit (1.87 m) + Muara Baru (1.81 m) of the 5 north
  positives; the qualitative Muis-screening coastal forcing (no gauge, ±0.2–0.3 m) + subsidence
  leave the rob reach conservative.

## 5. Supporting gate — JKT2020 extent-CSI (and why it is weak for Jakarta too)

`validate_historical_events.py --event JKT2020`: best **CSI 0.07** (pluvial RP100, H 0.12, FAR
0.86; fluvial RP100 CSI 0.07, H 0.19, FAR 0.91). Obs area 186 km². **FAIL**, but the SAR's own
note is decisive: the EOS-ARIA Sentinel-1 proxy "captures peri-urban / open-water flood; **misses
urban floods inside central Jakarta SAR layover/shadow zones**." So the reference sees the
peri-urban open-water fringe (rice paddies, river floodplains) while the DKI-core model floods
the urban interior the SAR cannot see — a spatial-domain mismatch (low POD) plus SAR-inflated
FAR. **Jakarta's SAR is therefore only a partial improvement over KL's #17 urban-blindness**, and
the CSI is a weak support gate here; the urban-focused hotspot gate is the meaningful one.
(Consistent with the prior bathtub-era JKT2020 result CSI 0.10 / FAR 0.87.)

## 6. Verdict + next (evidence-driven fixes — J2)

**Jakarta present-day FAILS the hotspot gate on CRR (HR 0.88 / CRR 0.29 / TSS 0.16).** Exactly as
validation-first intends, the failure is **cleanly diagnosed** and maps **directly onto the
already-validated KL playbook**:

1. **Main-stem HAND (#20)** — rebuild Jakarta's fluvial HAND from flow-accumulation channels at
   the **Ciliwung GloFAS-reach catchment scale** (Depok, ~370 km²), NOT the dense OSM/river
   network, to stop the uniform 4.30 m overbank flooding the central-levee + elevated dry
   controls. Expected: CRR recovers. **Jakarta should transfer BETTER than Bangkok** — the
   GloFAS point (Ciliwung-Depok, −6.35 N) sits near/in the domain (a sub-basin anchor like KL's
   Shah Alam), unlike Bangkok's fully-out-of-domain Chao Phraya (#22).
2. **Pluvial over-pond on elevated ground (Jagakarsa)** — drainage densification / DEM
   hydro-conditioning (KL Plan 5 analog). Secondary CRR contributor.
3. **Coastal rob under-reach (Penjaringan)** + **Kemang/Krukut single-reach miss** — documented
   structural limits (qualitative coastal forcing; one modeled river). Report, do not tune.

**Cardinal rule:** the flooded dry controls (Menteng, Gambir, Cipete, Pasar Minggu, Jagakarsa)
and the 2 missed positives **STAY** in the register — they are the real findings the gate
revealed, reported, never dropped to pass.

**Deferred:** the full 9-RP Jakarta baseline (inertial coastal ~50 min/RP; the
`--raingrid-workers` pool carries over for pluvial). RP100 is sufficient for this verdict.

**Status:** Plan J1 (Jakarta foundation + first validation) COMPLETE — the generalized
multi-city validator, the four-manifest contract, and the model-blind register transfer cleanly,
and the first gate reveals the same documented main-stem-HAND fix KL already proved. The
KL→Bangkok→Jakarta transfer is working as designed; Jakarta is positioned to PASS in J2 because
its mega-river (Ciliwung) is in-domain, unlike Bangkok's.

---

## 7. Plan J2 — main-stem HAND DOESN'T transfer; the CRR fix was a register mislabel correction

J2 set out to apply the KL #20 main-stem-HAND fix. **The viability sweep overturned that premise**
(`scripts/_diag_jakarta_mainstem_hand.py`, `…/runs/2026-06-09-jakarta-drycontrol-reexam.md`):

**(a) Main-stem HAND does NOT transfer to Jakarta (NEGATIVE — Bangkok #22 pattern, milder).** No
accumulation threshold separates the Ciliwung-corridor positives from the central-levee controls:
at catchment ≤90 km² all 5 Ciliwung positives are reached but extent *grows* to 711 km² (vs the
existing 375) and Menteng (HAND 1.9 m) / Gambir (HAND 0.0 m) still flood; at ≥180 km² the levee
controls are spared but ALL positives are lost (HAND jumps to 12–24 m). Cause: the Ciliwung's
headwaters are out-of-domain (Bogor), so accumulation at the documented ~370 km² reach shifts off
the natural river. The existing dense HAND was kept (no fluvial change).

**(b) The real CRR culprit was a register mislabel.** The sweep showed Menteng/Gambir sit *on* the
Ciliwung corridor (HAND 0–2 m) — and central Jakarta (Thamrin/Monas/Menteng) is **documented
flooded in 2007 and 2013** (2013: Merdeka Palace surrounded by water; Bundaran-HI corridor). They
were **mislabeled dry controls** (the KL #21 pattern). Model-blind, flood-record-anchored
re-examination (the re-exam doc) reclassified Menteng + Gambir as **positives** and restored the
dry set with 3 genuinely-elevated South-Jakarta controls (Ragunan, Pondok Labu, Pondok Pinang),
selected on terrain + flood-record-absence, NOT on being spared.

**Revised gate (RP100, threshold 0.10 m, radius 50 m; 18 positives / 8 dry):**

| Metric | J1 | **J2 (register-corrected)** | Floor |
|---|---|---|---|
| HR | 0.88 (14/16) | **0.89 (16/18)** | 0.70 — PASS |
| CRR | 0.29 (2/7) | **0.50 (4/8)** | 0.70 — **FAIL** |
| TSS | 0.16 [−0.19, 0.57] (no skill) | **0.39 [0.03, 0.75]** (CI excludes 0) | — |

**Correcting 2 documented mislabels took Jakarta from no-skill (TSS 0.16) to significant
discriminative skill (TSS 0.39, CI now excludes zero).** The gate still FAILs on CRR, and the
residual is honest: of the 8 dry controls, the 4 still flooded are **3 pluvial over-pondings on
elevated South Jakarta** (Jagakarsa 1.77 m @53 m, Pondok Pinang 0.68 m, Pasar Minggu 0.94 m — the
KL Bukit-Antarabangsa fill-spill pattern) **+ 1 dense-HAND fluvial** (Cipete 3.27 m). These 4
genuine controls **STAY** in the register as reported FPs (cardinal rule). The 4 correct rejects
(Cilandak, Lebak Bulus, Ragunan, Pondok Labu) confirm the elevated-south set is not trivially
easy.

**Verdict: Jakarta present-day is significantly skilful (TSS 0.39) with strong HR (0.89), but
CRR-marginal (0.50) — NOT a clean PASS.** The residual is dominated by **fill-spill pluvial
over-ponding on elevated ground** (3 of 4), whose documented fix is the **KL Plan 5
drainage-densification / DEM hydro-conditioning** lever (deferred to J3, not chased here — forcing
it would be the forbidden tuning loop). Secondary: the dense single-stage HAND over-broadens
(Cipete) and **cannot be fixed by main-stem HAND** for Jakarta (the out-of-domain Ciliwung). The
flooded genuine controls + the 2 HR misses (Kemang/Krukut single-reach; Penjaringan rob
under-reach) STAY. **Two of three cities (Bangkok, Jakarta) now show that single-stage HAND does
not transfer to flat deltas fed by out-of-domain mega-rivers — a confirmed transferable limit.**
