# flood-v4.0 — clean-run handoff for the comprehensive SAFE 2026 paper

**Date:** 2026-06-19
**For:** a fresh model session that will (1) consolidate a clean, self-contained `flood-v4.0`
repo, (2) re-run the full bare-earth multi-hazard atlas, and (3) write the comprehensive SAFE
2026 paper. Source trees: `D:\GPTs\Projects\flood-v2.0` (flood pipeline + paper) and
`D:\GPTs\Projects\flood-v3.0` (bare-earth DEM pipeline).

**Conference:** SAFE 2026 (Sustainable Accounting, Finance and Economics), theme *Climate Risk,
Regulation and Financial Stability*. Current draft: `flood-v2.0/docs/paper/v2/safe2026-v4.tex`
(→ becomes `flood-v4.0/.../safe2026-v5.tex`).

> Read alongside: `flood-v2.0/docs/superpowers/runs/2026-06-17-v3dem-cross-city.md`,
> `...-v3dem-bangkok-pumped-polder.md`, `flood-v2.0/outputs_v3dem/HANDOFF_bare-earth-atlas.md`,
> and `flood-v3.0/dem/DEM_HANDOFF.md`. This file supersedes the bare-earth-atlas handoff for the
> clean-run scope and records the decisions taken in the 2026-06-19 requirements quiz.

---

## 0. Decisions taken (the quiz) — these are fixed for the clean run

| # | Decision | Choice |
|---|---|---|
| 1 | Repo | **Fresh consolidated `flood-v4.0`** — self-contained, Zenodo-ready; re-run everything from clean inputs. |
| 2 | RP scope | **3-RP grid: RP10 / RP100 / RP1000** per scenario-horizon. |
| 3 | Bangkok fluvial | **Single-stage trunk HAND with the corrected 0.5245 m relative-overbank stage**; report the out-of-domain HR ceiling as a documented limitation (no hydrodynamic mainstem build). |
| 4 | Terrain | **Bare-earth is the SOLE flood terrain** (DSM appears only as the comparison baseline in the DEM-accuracy table). |
| 5 | Subsidence (2050/2100) | **Hold present-day** subsidence-corrected terrain for all horizons; report a projected-subsidence **sensitivity** case separately. |
| 6 | Compound hazard | **Report both**: per-pixel-maximum (marginal, headline) **and** an independence-assumption joint-exceedance layer as a bound. |
| 7 | Validation registers | **~2× expansion** per city (~40–50 pts), model-blind, flood-record-anchored, frozen before scoring. |
| + | Comprehensiveness extras | DEM-accuracy results table, mitigation-delta analysis, register expansion, compound/joint exceedance — **all in scope**. |

The finer method choices (compound formula, register sourcing, subsidence rates, authorship/IEEE)
are now **resolved with concrete specifications in §12**.

---

## 1. Repo consolidation (`flood-v4.0` = self-contained)

Copy into `flood-v4.0/` (re-run outputs fresh; do NOT copy the `outputs_v3dem/` scratch as final):

- `model/` ← flood-v2.0 (pipeline: HAND, pluvial fill-spill + raingrid, inertial coastal, etc.).
- `scripts/` ← flood-v2.0 (`run_multihazard.py`, `validate_hotspots.py`, `build_hand_raster.py`,
  `apply_pumped_polder.py`, `apply_flood_defenses.py`, `build_drainage_network.py`,
  `_build_v3_hand.py`, render scripts `render_v2_fig*.py`). Drop the one-off `_diag_*`/`_probe_*`
  unless cited.
- `data/<city>/` ← flood-v2.0: masks (`sea_mask`, `river_mask`, `runoff_coeff`,
  `drainage_waterways` for KL), `manifest/hotspots.csv` (registers), `hazard_levels_*.csv`.
- `dem/<city>/` ← flood-v3.0: the adopted bare-earth DEMs (§3) + `calib*/calibration.json` +
  `dem_validation_*` + the build pipeline `dem/*.py` (for reproducibility).
- `dem/_hand/` ← flood-v2.0/outputs_v3dem/_dem: the bare-earth HANDs + KL raingrid DEM + Bangkok
  de-biased/defended DEM + polder mask (§3).
- `docs/` ← the dossiers above + the paper + figures.
- `repro/` ← env notes (`environment_sfincs.yml`), this handoff, a top-level README + `run_all.*`
  driver that regenerates the atlas from clean inputs.

Cities use the v2.0 directory names: `bangkok`, `jakarta`, `kuala_lumpur`, `singapore`.

## 2. Environment — two interpreters (do not cross)

- **Flood model / HAND / run_multihazard / validate_hotspots** → Python 3.14:
  `C:\Users\Daniel\AppData\Local\Python\pythoncore-3.14-64\python.exe` (pysheds 0.5 + full stack).
- **DEM build (calibrate/build/validate/condition/compose)** → `sfincs` conda env, env-PATH method:
  ```powershell
  $E="D:\GPTs\Python\envs\sfincs"; $env:PATH="$E\Library\bin;$E;$E\Scripts;"+$env:PATH
  $env:GDAL_DATA="$E\Library\share\gdal"; $env:PROJ_DATA="$E\Library\share\proj"
  ```
  Never call the env python directly (foreign-BLAS crash); never `mamba`.

## 3. Terrain — the bare-earth DEM layer (sole flood terrain)

All EGM2008 / UTM / 30 m, drop-in on each city's v2.0 grid. Per-city calibration NEVER reused.
All canopy on **ETH GlobalCanopyHeight 10 m 2020** (KL harmonised from Meta CHM — invariance-tested).

| City | Adopted DEM | Method | f / bias0 | Held-out accuracy / gate |
|---|---|---|---|---|
| Bangkok | `dem_bareearth_bangkok_present_conditioned.tif` **+ de-bias + polder** | ICESat-2-calib GLO-30 | 0.066 / +0.24 | MAE 1.35→0.74 m, bias +0.75→−0.30; urban −0.88 m → CBD de-bias required |
| Jakarta | `dem_bareearth_jakarta_present_conditioned.tif` | ICESat-2-calib GLO-30 | 0.102 / +0.585 | urban +0.25 m, PASS |
| Kuala Lumpur | `dem_bareearth_kl_eth_present_conditioned.tif` | ICESat-2-calib GLO-30, ETH canopy | 0.184 / +1.454 | urban +0.18 m; inland/coastal-zone FIX is spurious (KL inland) |
| Singapore | `dem_bareearth_singapore_present_conditioned.tif` | **DeltaDTM** (≤30 m) + ICESat-2 fill | — | DeltaDTM ~0.45 m global; ICESat-2 unusable here (see below) |

**Singapore = DeltaDTM (the key terrain finding).** ICESat-2/GEDI cannot validate dense, reclaimed
SG — its ATL08 ground is building/canopy-contaminated, and DeltaDTM (validated ~0.45 m) disagrees
with ATL08 by ~2 m (urban bias −2.6 m), proving the *lidar* is the noisy reference. So SG terrain
= DeltaDTM where it covers (all flood-relevant ≤30 m, 91 % of held-out pts) + ICESat-2 bare-earth
fill for the non-flood interior >30 m. Built by `flood-v3.0/dem/_build_sg_deltadtm_bareearth.py`.

**Bare-earth HANDs** (reuse v2 channel network, recompute on bare-earth via `_build_v3_hand.py`):
`jakarta_hand_v3.tif` (dense), `kl_hand_mainstem_v3eth.tif` (main-stem), `hand_trunk_v3_debiased.tif`
(Bangkok trunk on de-biased DEM), `singapore_hand_v3_deltadtm.tif` (median 2.31 m). KL also has
`kl_raingrid_v3eth.tif` (drain-burn transferred onto ETH terrain).

## 4. Forcing & the scenario grid

- **Present-day (2020):** corrected ΔT=0 GEV-CC forcing baked in `hazard_levels_ssp585_2020.csv`
  (fluvial/pluvial unscaled baseline; coastal = AR6 delta). This is the **validation** forcing.
- **2×2 future grid:** `hazard_levels_{ssp245,ssp585}_{2050,2100}.csv` (all four exist per city) —
  GEV-CC ΔT scaling for fluvial/pluvial + AR6 SLR delta for coastal.
- **3-RP slices:** for each of the 5 scenario-horizons build an RP-{10,100,1000}-only CSV
  (coastal+fluvial+pluvial rows present — the reader requires all three). Verify RP-monotonicity
  and 2020≤2050≤2100 with the existing scenario-forcing guard before running.
- **Subsidence:** the bare-earth DEMs carry **present-day** subsidence; use the same DEM for all
  horizons (decision #5). Add a **projected-subsidence sensitivity** for Jakarta (+ Bangkok) only,
  reported separately (do not bury it in the headline).
- **KL pluvial caveat:** under corrected present-day forcing KL pluvial net-excess ≈0 (RP100
  0.095 m) → pluvial extent ≈0 at present day for BOTH terrains. At 2050/2100 the pluvial forcing
  grows — re-check; KL's present-day gain is fluvial only.
- **Bangkok fluvial = 0.5245 m RP100 relative overbank** (the committed CSV), NOT the 6.46 m
  absolute mainstem stage (that was a bug — flooded 856 km² at 5.78 m median; corrected = 491 km²
  at ≤0.52 m). `--fluvial-bankfull-rp 0`.

## 5. The three hazards + solvers (per-city config in §9)

- **Coastal:** local-inertia shallow-water solver (`--coastal-solver inertial`), AR6 SLR delta +
  GEV surge. Bathtub retained only for the §8 bias comparison. **On bare-earth the inertial
  extent grows** (buildings removed expose low land) — Bangkok needs the pumped-polder floor
  (`apply_pumped_polder.py`, anchored to the BMA 80 mm/hr / 166-station design) or the accurate
  low terrain over-floods the bunded CBD. Jakarta's pumped districts genuinely flood (rob) → no
  polder there.
- **Fluvial:** GloFAS design discharge → stage → main-stem HAND (≥180 km² accumulation trunk).
  **Bangkok HR is bounded** by the out-of-domain Chao Phraya (limitation #22) — report, don't tune.
- **Pluvial:** IDF-anchored excess (per-country PUB/JPS/TMD/BMKG, 2-anchor Gumbel) routed by
  catchment fill-and-spill; KL uses the raingrid solver on the drain-burned DEM.

## 6. Compound / joint exceedance (decision #6)

Produce, per city × scenario-horizon × RP:
1. **Marginal (headline):** per-pixel-maximum of the three depth rasters (current method).
2. **Independence-joint (bound):** combine assuming hazard independence — e.g. per-pixel
   joint-exceedance probability / depth under independent marginals — as a transparent second
   layer. State the dependence assumption explicitly; it brackets the true (dependent) co-occurrence.
Report both extents; discuss that real coastal∧fluvial∧pluvial dependence (monsoon-surge-rain
co-timing) lies between the marginal-max and full-dependence cases.

## 7. Validation (the trust gate)

- **Method:** model-blind documented-hotspot gate (`validate_hotspots.py --city <c> --rp 100`):
  HR / CRR / TSS [BCa 95 % CI] + Fisher's exact; PASS = HR≥0.70 ∧ CRR≥0.70 ∧ TSS CI>0. Operating
  point: present-day, RP100, ≥0.10 m, 50 m radius, combined coastal∨fluvial∨pluvial.
- **Register expansion (decision #7):** ~2× each register (~40–50 pts), model-blind,
  flood-record-anchored positives + terrain-verified dry controls, **frozen before re-scoring**.
  Cardinal rule: flooded controls / missed positives STAY; never relabel to pass.
- **Scope:** validation is **present-day only** (registers are documented present-day events);
  2050/2100 are projections, explicitly unvalidated.
- **Per-city bare-earth gate to (re)produce:** Jakarta 0.94/0.62/0.57; KL 0.59/1.00/0.59 (ETH);
  Bangkok 0.44/1.00/0.44 (corrected fluvial); **Singapore = NOT YET RUN** — run on the DeltaDTM
  terrain + a same-config DSM control (the vendored SG gate 0.82/0.65/0.47 is flood-atlas-era, not
  current-engine, so it needs a current-engine baseline for a fair comparison).

## 8. Comprehensiveness extras (all in scope)

1. **DEM-accuracy results table:** per-city held-out MAE / bias for **DSM vs bare-earth vs
   DeltaDTM** (Bangkok 1.35→0.74 m anchor; SG = the ICESat-2-fails→DeltaDTM story; report the
   heterogeneity honestly). New paper table; supports the terrain contribution.
2. **Mitigation-delta:** per city, SSP2-4.5 vs SSP5-8.5 avoided-flood-area at 2100 (RP100), read
   off the **corrected inertial** layer (the bathtub delta is multiplicatively biased — see §8 of
   the current paper). The adaptation-finance headline number.
3. **Register expansion** — §7.
4. **Compound/joint exceedance** — §6.

## 9. Run matrix + per-city commands

**Grid:** 4 cities × 5 scenario-horizons (2020, {SSP245,SSP585}×{2050,2100}) × 3 RPs (10/100/1000)
× hazards. KL has no coastal. **Cost:** inertial coastal ≈30 min/run; KL raingrid slow at high RP.
Prioritise: (a) present-day RP100 validation (all cities) → (b) RP100 across the 2×2 → (c) fill
RP10/RP1000. Parallelise across cities; checkpoint after (a).

Run with pythoncore-3.14 from the repo root; score with `validate_hotspots.py`. Per-city flags
(present-day shown; swap the CSV per scenario-horizon, keep terrain fixed):

- **Jakarta:** `--coastal-solver inertial --coastal-msl-egm2008 0.9976 --no-clamp-negative-land
  --pluvial-model fillspill --pluvial-depth-cap 3.0 --runoff-coeff 0.80 --fluvial-bankfull-rp 0`,
  HAND `jakarta_hand_v3.tif`, masks `data/jakarta/{sea_mask,river_mask,runoff_coeff}_utm48s.tif`,
  `--tidal-burn-elevation 2.0`.
- **Kuala Lumpur (inland):** `--only-hazard-types fluvial,pluvial --pluvial-model raingrid
  --pluvial-dem-raster kl_raingrid_v3eth.tif --pluvial-depth-cap 3.0 --tidal-channel-raster
  data/kuala_lumpur/drainage_waterways_utm47n.tif --runoff-coeff 0.75 --fluvial-bankfull-rp 0`,
  HAND `kl_hand_mainstem_v3eth.tif`.
- **Bangkok:** DEM `bangkok_v3_debiased_defended.tif`, HAND `hand_trunk_v3_debiased.tif`,
  `--fluvial-bankfull-rp 0`, inertial coastal + masks; **then** `apply_pumped_polder.py --city
  bangkok` on the output. Fluvial stage 0.5245 m (RP100) from the committed CSV.
- **Singapore:** DEM `dem_bareearth_singapore_present_conditioned.tif`, HAND
  `singapore_hand_v3_deltadtm.tif`, masks `data/singapore/{sea_mask,river_mask,runoff_coeff}_utm48n.tif`,
  `--tidal-burn-elevation 2.0 --coastal-solver inertial --pluvial-model fillspill
  --pluvial-depth-cap 3.0 --runoff-coeff 0.75`. Also run a DSM control for the gate comparison.

## 10. Paper deliverables (SAFE v5)

Start from `safe2026-v4.tex`; make bare-earth the sole terrain (drop the DSM-vs-bare-earth §6
comparison framing — the DSM survives only in the §8.1 accuracy table). Regenerate:
- **Table — DEM accuracy** (§8.1, new).
- **Table — validation gate** (bare-earth, present-day, all 4 cities, expanded registers).
- **Table — extent atlas** (3-RP × 2×2, marginal; + the independence-joint bound).
- **Table/par — mitigation delta** (SSP245 vs 585, 2100, corrected layer).
- **Fig — bathtub→inertial on bare-earth** (note: gap WIDENS vs DSM; inertial is the
  terrain-independent fix; drop the backwards "DSM buildings drive over-prediction" wording).
- **Method:** fold in the DEM construction (error model `z_DSM ≈ ground + building + f·canopy`,
  per-city ICESat-2/GEDI calibration, SG=DeltaDTM rationale, canopy-product invariance).
- Keep "demonstrably skilful"; keep the 5 contributions (terrain is #5).

## 11. Honest caveats (must report, do not bury)

- Bangkok HR out-of-domain-bounded (0.44 ≈ DSM 0.42); bare-earth + pumps perfect CRR but cannot
  manufacture skill the forcing domain withholds. Fluvial = 0.5245 m (the 6.46 m run was a bug).
- Singapore terrain = DeltaDTM; ICESat-2 unusable (the switch IS the story, not a failure).
- KL pluvial ≈0 under corrected present-day forcing (forcing, not terrain).
- Bathtub bias widens on bare-earth; inertial is the fix on any terrain.
- Subsidence held present-day in the headline; projected case is a separate sensitivity.
- Compound layer's independence assumption brackets, not resolves, hazard dependence.
- Future horizons are projections, unvalidated; validation is present-day only.
- Per-city calibration never reused; canopy harmonised to ETH (KL invariance-tested).

## 12. Resolved specifications (the former open items)

### 12.1 Compound / joint exceedance — exact formula
Compute per pixel from the 3-RP per-hazard depth rasters. For hazard $i\in\{C,F,P\}$, the RP-{10,100,1000}
depths give an annual-exceedance-probability (AEP) curve $d_i(\mathrm{AEP})$ over AEP $\in\{0.1,0.01,0.001\}$;
interpolate/extrapolate **log-linearly in AEP** (clip outside the 10–1000 yr range).
- **Headline (marginal):** $D_\text{marg}(\mathrm{RP}) = \max_i d_i(1/\mathrm{RP})$ — the current per-pixel-max.
- **Independence-joint (computed bound):** combined exceedance of depth $d$ is
  $\mathrm{AEP}_\text{joint}(d) = 1 - \prod_i\!\big(1-\mathrm{AEP}_i(d)\big)$; invert at target AEP $\{0.1,0.01,0.001\}$
  to get the joint depth raster. It yields a **larger footprint at fixed RP** than the marginal (three
  independent flooding processes exceed any single one), bounding the "hazards as separate contributors" effect.
- **Report:** both extents, per city × scenario × RP. State plainly that the **true compound case (monsoon
  co-timing → depth addition) is bracketed below by independence and above by the sum-of-marginals
  $\sum_i d_i$ (full positive dependence)**; the sum-of-marginals is shown only as a discussed conservative
  envelope (dependence data is lacking — flagged as a limitation), not the headline.

### 12.2 Register-expansion sourcing per city (model-blind, frozen, geocoded, DEM-verified)
Current scored sizes → ~2× targets: Bangkok 23→~46, Jakarta 26→~52, KL 24→~48; **Singapore is already
large (58) — only modest top-up**. Compile from records **before** looking at any model output; keep the
cardinal rule (flooded controls / missed positives STAY). Sources per city:
- **Bangkok** — positives: 2011 Chao Phraya megaflood inundation (DFO_3850 already in repo; Komori 2012),
  BMA flood-incident reports, 2021/2022 monsoon news; the northern/outer districts + Chao Phraya corridor.
  Dry controls: documented-dry eastern/elevated districts; treat the reliably-pumped bunded CBD core as a
  *special* control (pump-dependent — note it).
- **Jakarta** — positives: 2007/2013/2020 floods (BNPB/BPBD; the existing `2026-06-09-jakarta-hotspot-research.md`),
  Ciliwung corridor, North-Jakarta rob, monsoon pluvial. Dry controls: elevated South Jakarta (Ragunan,
  Pondok Labu, Pondok Pinang…).
- **Kuala Lumpur** — positives: JPS/DID flood-prone locality lists, Dec-2021 floods (Taman Sri Muda, Shah Alam);
  promote the documented-flooded members of the existing `dry_diagnostic` set to positives where records
  support it. Dry controls: elevated hills (Bukit Tunku, Damansara Heights, Mont Kiara, Bukit Gasing).
- **Singapore** — positives: PUB flood-incident records (Stamford/Orchard 2010–2011, Bukit Timah canal,
  PUB flood-prone list). Dry controls: elevated interior.
**Execution:** a per-city model-blind research pass (the `deep-research` skill fits) → geocode → DEM-verify →
freeze CSV → only then score. This is a discrete clean-run task, NOT done in this handoff.

### 12.3 Projected-subsidence rates (sensitivity only; headline holds present-day — decision #5)
Project each city's **documented zone rate** linearly from 2020 to 2050 (+30 yr) and 2100 (+80 yr); apply
as an added lowering on the bare-earth DEM for the sensitivity run. **Caveat to state:** rates are declining
under groundwater regulation / sea-wall programmes (Jakarta) and the pumping ban (Bangkok), so the linear
extrapolation is a **HIGH-END bound, not a forecast**.
- **Jakarta** (Abidin 2011; Chaussard 2013) — N Jakarta ~10 cm/yr (range 10–25), Central ~5, South ~2 cm/yr.
  2050 additional ≈ −3.0/−1.5/−0.6 m; 2100 ≈ −8.0/−4.0/−1.6 m (N is extreme — present as upper bound).
  (Present-day correction already in the DEM: −1.44/−0.72/−0.24 m by band, mean −0.83 m.)
- **Bangkok** (Phien-wej 2006; Aobpaet 2013 PSInSAR) — N fringe 2.5, Central BMA 1.5, S/Samut Prakan 2.0 cm/yr.
  2050 additional ≈ −0.75/−0.45/−0.60 m; 2100 ≈ −2.0/−1.2/−1.6 m. (Present-day correction −0.30/−0.18/−0.24 m.)
- **KL / Singapore:** negligible subsidence — no projection.

### 12.4 Authorship / double-blind — DEFAULT SET (confirm if wrong)
Maintain both forms: **double-blind is the primary for submission** (the SAFE template/`safe2026-*.tex`
already carries the `\author{}` blanking note and an anonymised-repository plan), with the **named version
(Phang/NTU, Lee/NUS) as the camera-ready**. No further input needed unless SAFE 2026's policy is single-blind.

### 12.5 IEEE paper — DEFAULT SET (confirm if wrong)
**Out of scope for this clean run** (SAFE only). `ieee-r10htc-v2.tex` still carries the now-outdated
"FABDEM next step" limitation; once the SAFE clean run lands, the IEEE paper can be re-synced from the same
bare-earth results in a follow-up. Flagged, not actioned.

## 13. Key source inventory (to copy into flood-v4.0)

- DEMs: `flood-v3.0/dem/<city>/dem_bareearth_<city>_present_conditioned.tif`.
- HANDs + KL raingrid + Bangkok defended/polder: `flood-v2.0/outputs_v3dem/_dem/`.
- Pipeline + scripts + data + registers + paper: `flood-v2.0/`.
- DEM build pipeline + calibration: `flood-v3.0/dem/`.
- Dossiers: `flood-v2.0/docs/superpowers/runs/2026-06-17-v3dem-{cross-city,bangkok-pumped-polder}.md`.
