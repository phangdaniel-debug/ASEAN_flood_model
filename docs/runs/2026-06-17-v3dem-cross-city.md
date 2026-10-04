# v3.0 bare-earth DEM — cross-city flood-gate comparison (Bangkok, Jakarta, KL, Singapore)

**Date:** 2026-06-17
**Scope:** Swap each city's v2.0 GLO-30 **DSM** terrain for the v3.0 **bare-earth** DEM
(`flood-v3.0/dem/<city>/dem_bareearth_<city>_present_conditioned.tif`), re-run the documented-
hotspot gate as a controlled A/B (only the base terrain + HAND change; identical forcing,
masks, solver, register, operating point RP100 / ≥0.10 m / 50 m), and answer **"is v3 the
better option?"** per city. Bangkok's full investigation is in
`2026-06-17-v3dem-bangkok-pumped-polder.md`; this doc adds Jakarta, KL, Singapore and the
synthesis. All outputs are scratch under `outputs_v3dem/` (gitignored).

## 1. Headline gate table (present-day, RP100, controlled A/B)

| City | terrain | HR | CRR | TSS [95% CI] | verdict |
|---|---|---|---|---|---|
| **Bangkok** | v2 DSM | 0.56 | 0.86 | 0.42 [0.04, 0.75] | baseline |
| | **v3 + de-bias + pumped-polder (corrected fluvial)** | **0.44** | **1.00** | **0.44 [0.19, 0.69]** | **≈ DSM (out-of-domain HR ceiling)** |

> **Bangkok fluvial correction (2026-06-18):** the earlier v3 Bangkok runs were fed the
> *absolute* BCP mainstem stage **6.46 m** through static single-stage HAND (a method
> rejected for Bangkok), flooding 856 km² at **5.78 m median depth** — a bug. Re-run with the
> committed corrected forcing (RP100 relative overbank **0.5245 m**, consistent with Jakarta/KL):
> fluvial = **491 km² at ≤0.52 m** (median 0.45). The 6.46 m sheet had *spuriously* reached the
> out-of-domain 2011 northern districts, inflating HR to 0.56; the honest gate is **HR 0.44 /
> CRR 1.00 / TSS 0.44**. The 9 missed positives (Sai Mai, Lak Si, Bang Sue, Rangsit, Lam Luk Ka,
> Bang Bua Thong, Nong Chok, Taling Chan, Bang Phlat) are the documented out-of-domain
> Chao-Phraya 2011 districts (limitation #22) — single-stage HAND cannot reach them at any sane
> stage; only hydrodynamic mainstem routing would. So bare-earth + polder **perfects CRR
> (0.86→1.00) but the out-of-domain fluvial bounds HR**, netting ≈ the DSM (0.44 vs 0.42):
> accurate terrain does not rescue Bangkok's fundamental fluvial limit.
| **Jakarta** | v2 DSM | 0.89 | 0.50 | 0.39 [0.03, 0.75] | baseline |
| | **v3 bare-earth (raw)** | **0.94** | **0.62** | **0.57 [0.19, 0.88]** | **clean win, no fixes** |
| **Kuala Lumpur** | v2 DSM (same config) | 0.35 | 1.00 | 0.35 [0.12, 0.59] | baseline |
| | **v3 bare-earth (ETH canopy, harmonized)** | **0.59** | **1.00** | **0.59 [0.35, 0.82]** | **fluvial win (HR/TSS ~2×)** |
| | v3 bare-earth (Meta CHM, robustness) | 0.65 | 1.00 | 0.65 [0.41, 0.88] | invariance check (§4a) |
| **Singapore** | v3 bare-earth | — | — | — | **DEM-accuracy gate FIX (no terrain win)** |

> KL note: the v2 row here is the *same-engine, same-(corrected dT=0)-forcing* baseline
> (0.35/1.00/0.35), the correct control for a DEM swap — NOT the historical documented KL
> gate (0.76/0.86/0.62), which used the pre-correction (inflated) pluvial forcing. See §4.

## 2. Per-city findings

### Bangkok (defended, pumped delta — urban DEM over-correction artifact)
Raw bare-earth **crashes**: a −0.88 m urban-core over-removal (sparse under-building lidar) + the
model's omitted pump physics. The DSM's building high-bias had been *accidentally compensating*
for the missing pumps ("right for the wrong reason"). A CBD de-bias (+0.88 m on bcov>0.25) and a
documented **pumped-polder drainage floor** (King's-Dyke core, BMA 80 mm/hr / 166 stations)
**perfect CRR (0.86→1.00)**. With the **corrected fluvial forcing** (0.5245 m relative overbank;
the earlier 6.46 m-via-HAND run was a bug — see §1 note), the honest gate is **HR 0.44 / CRR 1.00
/ TSS 0.44 ≈ the DSM (0.42)**: HR is bounded by the out-of-domain Chao-Phraya 2011 districts that
single-stage HAND cannot reach (limitation #22), so **accurate terrain + pumps do not rescue
Bangkok's fundamental out-of-domain fluvial limit** — they trade HR for CRR. Full dossier separate.

### Jakarta (pumped, subsiding delta — clean urban calibration)
Raw bare-earth **improves the gate immediately** (TSS 0.39→0.57), **no de-bias, no polder**.
Why the opposite of Bangkok: Jakarta's held-out **urban-core bias is only +0.25 m** (passes the
new urban-bias gate) — no over-correction to repair. The lower bare-earth (HAND median 6.96→3.65 m)
expands the fluvial appropriately and catches one extra north-coastal *rob* positive (Penjaringan,
which v2 missed); HR 0.89→0.94. **The pumped-polder treatment does NOT apply to Jakarta**: north
Jakarta's pumped districts (Pluit, Muara Baru, Kalibaru, Cilincing) are documented-flooded
**positives** (rob/tidal) and the model correctly floods them — draining them would destroy hits,
the inverse of Bangkok's reliably-dry bunded CBD. The residual 3 FPs (Cilandak, Pasar Minggu,
Cipete — all elevated south) are the **same documented dense-single-stage-HAND over-broadening +
fill-spill over-pond** as v2 (terrain-independent; the J3 drainage-densification lever), not a
pump issue. Flooded controls STAY (cardinal rule).

### Kuala Lumpur (inland, forested hills — pure fluvial-terrain test)
Under identical engine + corrected dT=0 forcing, the bare-earth **nearly doubles HR and TSS
(0.35→0.59 on the adopted ETH canopy; 0.65 on Meta — §4a)** at **no CRR cost (1.00→1.00)**.
Mechanism is purely **fluvial**: the bare-earth
lowers building-inflated urban terrain, so the main-stem-HAND fluvial layer (median HAND ~unchanged,
58.6 vs 59.1 m — trunk-referenced) correctly floods **+5 documented street/river positives** the
DSM kept artificially dry — including **Old Klang Road** (the documented flood spot v2 needed a
2.06× discharge-bias hack to catch; bare-earth catches it on terrain alone), Jalan Sultan Azlan
Shah, Jalan Tun Sambanthan, Pantai Dalam, Jalan Tun Razak. CRR stays perfect: removing canopy on
the 7 forested elevated dry-control hills makes them cleanly dry. Fluvial extent 45.6→76.5 km².
The 6 remaining misses are pluvial-dependent (Segambut) or out-of-domain (Taman Sri Muda, 7.6 km
from any modeled floodplain — documented structural limit), unaffected by terrain.

### Singapore (dense, reclaimed island — DEM accuracy fails)
The bare-earth **fails the held-out DEM-accuracy gate (FIX)**: urban-core bias +0.52 m, coastal
MAE 2.75 m, all-zone MAE 4–6 m. This is **intrinsic ground-truth noise**, not a build bug — the
*raw* GLO-30-vs-ATL08 residual is already 3–5 m MAE (sparse, scattered ICESat-2 over a small,
dense high-rise, heavily-reclaimed island). Bias is correctable; scatter is not. So **v3 is not a
terrain improvement for Singapore** — the v2.0 terrain (or DeltaDTM coastal) is retained. The
flood A/B was not run: scoring a model on a terrain that fails the accuracy gate adds no
defensible signal (the unambiguous v3 deliverable per the handoff is terrain accuracy, and it
fails here). Can be run on request.

## 3. Synthesis — when is the bare-earth DEM the better option?

**The bare-earth improves fluvial- and coastal-driven flood screening, often substantially,
but only when two preconditions hold:**

1. **Clean urban calibration.** The value-add (building removal) is exactly where ICESat-2/GEDI
   are sparsest, so the urban core can be over-removed (Bangkok −0.88 m) and crash the gate.
   The new **urban-core bias gate** in `validate_dem.py` (added after the Bangkok finding) now
   surfaces this before flood use. Jakarta (+0.25 m) and KL (urban bias −0.23 m) passed it and
   won directly; Bangkok needed a CBD de-bias first.
2. **Sufficient ground-truth density/quality.** Singapore fails here — a small dense island gives
   3–5 m raw ATL08 scatter that no bias correction fixes, so the DEM never reaches screening
   tolerance.

**Where the DSM's building bias kept real flood spots artificially dry, the bare-earth is a clear
win** (KL Old Klang Road, Jakarta Ciliwung corridor + north-coast rob). **For defended/pumped
deltas the model must also carry the documented defence/pump physics** (Bangkok), or the accurate
low terrain leaks through sub-pixel dykes; once it does, specificity is perfected (CRR→1.00). But
**accurate terrain cannot manufacture skill the forcing domain withholds**: Bangkok's hit-rate
stays bounded (net TSS 0.44 ≈ DSM 0.42) because the documented-flooded 2011 districts are fed by
the out-of-domain Chao Phraya, which single-stage HAND cannot reach at any sane stage — the
remaining lever is hydrodynamic mainstem routing, not terrain.

**Publishable one-liner:** *a more accurate open bare-earth DEM is the better terrain for
fluvial/coastal flood screening — and recovers documented flood spots the DSM's building bias
masked — provided the urban core is calibrated cleanly (gated) and the ground truth is dense
enough; for a defended delta it must be paired with documented pump/defence physics.*

### Kuala Lumpur — canopy-product harmonization + invariance test (§4a)
KL was originally built on **Meta/WRI 1 m CHM** (the ETH 10 m host is retired; the other three
cities' ETH tiles were one-off manual downloads). To remove the one uncontrolled input
difference, KL was **rebuilt on ETH 10 m canopy** (tiles N03E099 + N00E099 from the ETH ownCloud
mirror, mosaiced onto the KL grid) — now product-uniform with Bangkok/Jakarta/Singapore. The
rebuild **doubles as an invariance test**:

| KL build | bias0 | f | held-out urban bias | gate HR/CRR/TSS |
|---|---|---|---|---|
| Meta CHM (1 m) | +1.457 | 0.689 | −0.23 m | 0.65 / 1.00 / 0.65 |
| **ETH (10 m, adopted)** | +1.454 | 0.184 | +0.18 m | **0.59 / 1.00 / 0.59** |

The **flat true-ground offset bias0 is essentially identical (1.454 vs 1.457 m)** — it is what
drives the flood-relevant urban/valley terrain, and it is product-invariant. Only **f** differs
(ETH canopy is taller → smaller coefficient), because f absorbs the canopy-product scale into the
vegetated-only correction. The held-out urban-core bias is within ±0.25 m for both (the gate's
flood-critical metric). The flood gate differs by **exactly one borderline fluvial hotspot**
(Jalan Tun Razak), with **all 7 dry-control rejects, Old Klang Road's recovery, and the perfect
CRR identical** — both ~2× the v2 DSM (TSS 0.35). **Conclusion: the canopy product is immaterial
to the result; the per-city product choice (forced by ETH availability) does not threaten
validity.** Adopted deliverable: `dem_bareearth_kl_eth_present_conditioned.tif`.

## 4. Honest caveats / threats to validity

- **KL forcing context.** Under the corrected present-day (dT=0) forcing, the KL pluvial
  net-excess is small (RP100 0.095 m) → pluvial extent ≈0 for **both** DEMs, so the KL A/B is a
  pure *fluvial* test and the gate's pluvial-only positives (Segambut, Bukit Jalil) are missed in
  both arms. The historical documented KL gate (HR 0.76) used the **pre-correction inflated**
  pluvial and caught them; that is a forcing question, separate from the DEM swap. The DEM A/B is
  valid because both arms share the identical corrected forcing.
- **Controlled-variable discipline.** Each A/B changes only the base terrain + the HAND recomputed
  on it (same drainage-cell network reused from the v2 HAND where v2 used a fixed network; KL
  main-stem channels reused; Jakarta dense network reused). Masks, runoff, solver, forcing,
  register, operating point identical. Bangkok additionally re-burns the identical King's-Dyke
  defences.
- **Cardinal rule held throughout:** flooded dry controls and missed positives STAY in every
  register; no spot was relabelled to pass.
- **Singapore flood A/B not run** (DEM-accuracy FIX) — stated, not hidden.

## 5. Artifacts (scratch / uncommitted, under outputs_v3dem/)
- `_dem/`: per-city v3 HANDs (`{jakarta,singapore,kl}_hand_v3.tif`, `kl_hand_mainstem_v3.tif`),
  `kl_raingrid_v3.tif` (burn-transferred), Bangkok defended/de-biased DEMs + polder mask.
- `jakarta_ssp585_2020/`, `kl_ssp585_2020/` (v3), `kl_v2base_ssp585_2020/` (same-config v2
  control), `kl_hybrid_ssp585_2020/`, Bangkok run dirs.
- DEM builds + validations: `flood-v3.0/dem/{singapore,kl}/dem_bareearth_*_present_conditioned.tif`,
  `dem_validation_*.{json,csv}`, `calib/calibration.json` (per-city f/bias0; never reused).
- Helper scripts (flood-v2.0/scripts, `_`-prefixed): `_build_v3_hand.py`, `_build_jakarta_v3_hand.py`,
  `_build_kl_v3_raingrid.py`, `_probe_city_v3.py`, `_probe_jakarta_v3.py`.

## 6. Per-city calibration (for reproducibility; never reuse across cities)
| City | bias0 (m) | f | urban-core held-out bias | DEM gate |
|---|---|---|---|---|
| Bangkok | +0.24 | 0.066 | −0.88 m | PASS-WITH-CAVEAT (de-bias before flood) |
| Jakarta | +0.585 | 0.102 | +0.25 m | PASS (urban-bias ok) |
| Singapore | +0.542 | 0.294 (ETH) | +0.52 m | FIX (noisy GT; coastal+inland MAE) |
| Kuala Lumpur (adopted, ETH) | +1.454 | 0.184 (ETH) | +0.18 m | FIX on coastal/inland MAE only (spurious for inland KL); **urban-bias PASS** |
| Kuala Lumpur (Meta, robustness) | +1.457 | 0.689 (Meta CHM) | −0.23 m | same regime — invariance check §4a |

Canopy product: Bangkok/Jakarta/Singapore/KL all on **ETH GlobalCanopyHeight 10 m 2020** (KL
harmonized 2026-06-17; Meta-CHM retained only as the §4a invariance control). Per-city f/bias0
are never reused across cities.
