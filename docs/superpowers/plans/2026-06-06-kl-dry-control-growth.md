# KL Dry-Control Register Growth (Plan 9 of N)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the KL dry-control set from **7 (all elevated)** to **≥15** by adding ~8 **research-grounded low-lying hard negatives**, defeating the easy-negative confound so CRR/TSS measure real specificity, and tighten the TSS CI. Spec: `docs/superpowers/specs/2026-06-06-kl-dry-control-growth-design.md`.

**Architecture:** Research model-blind hard negatives (low-lying KL localities absent from every flood record) → extend the register builder to support a `dry_lowlying` class (verified by distance-to-positive, not elevation) → regenerate `hotspots.csv` via Nominatim → confirm the loader scores both dry classes as negatives → re-validate and report honestly (a flooded hard negative STAYS and is reported). No raster re-runs.

**Tech Stack:** Python 3, pandas, rasterio, click, pytest; Nominatim (network); WebSearch/WebFetch for the research.

**Discipline (cardinal):** the dry set is fixed **before** looking at the model's wet-mask at those points; a hard negative the model floods is a REAL miss → keep + report it; NEVER curate the negative set to raise CRR (Singapore #15).

**Key files:** `scripts/build_kl_hotspot_register.py` (candidate list + verification), `scripts/city_manifest.py` (`load_hotspots_from_manifest`), `data/kuala_lumpur/manifest/hotspots.csv`, `scripts/validate_hotspots_kl.py`, `data/kuala_lumpur/hand_mainstem_utm47n.tif` + `copernicus_dem_utm47n.tif` (terrain check), `docs/superpowers/runs/2026-06-05-kl-validation-dossier.md`, `docs/limitations_register.md`.

---

### Task 1: Research the hard negatives (model-blind) + record provenance

**Files:** Create `docs/superpowers/runs/2026-06-06-kl-dry-control-research.md`

- [ ] **Step 1:** Web-research model-blind low-lying KL dry-control candidates. Consult: (a) DID Malaysia / DBKL **flood-prone area lists** + InfoBanjir-type records; (b) **Dec-2021 Klang Valley flood reports** (which districts inundated vs spared); (c) the positive-set sources already in the register. Identify **~10 candidate low-lying KL localities** (to yield ≥8 after geocode/verify drops) that are: low-lying (valley-floor, NOT hills), **absent from every flood-prone/hotspot list**, and **not reported flooded in Dec-2021**. For EACH candidate record in the doc: name, a Nominatim geocode query string, a one-line dry-label justification, and the **source(s) consulted** (URLs/citations). Prefer planned/well-drained townships and areas explicitly described as spared. Explicitly note any candidate carrying undocumented-flood risk.
- [ ] **Step 2:** Sanity-spread: ensure the candidates are geographically distributed across the KL/Klang Valley domain (not clustered), and that none collides with an existing positive (within ~300 m). Record the final ~8–10 in a clean table. **Do NOT consult the model's flood rasters at any point.** Commit the research doc.

```bash
cd /d/GPTs/Projects/flood-v2.0
git add docs/superpowers/runs/2026-06-06-kl-dry-control-research.md
git commit -m "docs: model-blind research for KL low-lying hard dry-controls (Plan 9)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 2: Extend the register builder for low-lying dry controls (TDD)

**Files:** Modify `scripts/build_kl_hotspot_register.py`; Test `tests/test_kl_register_drycontrols.py`

- [ ] **Step 1 (failing test):** Create `tests/test_kl_register_drycontrols.py` asserting the **pure logic** (no network):
  - the in-file candidate list has **≥15** entries with kind in {`dry`,`dry_lowlying`} (7 existing elevated + ≥8 new);
  - **every** `dry`/`dry_lowlying` candidate has a non-empty `source` provenance string;
  - the `dry_lowlying` verification flag is **distance-to-nearest-positive** based, not elevation: a synthetic `dry_lowlying` point at low elevation but **far** (>300 m) from all positives is NOT flagged, while one **within** ~50 m of a positive IS flagged. (Test the helper function directly; refactor the flag into a pure function `flag_dry_lowlying(lon, lat, positives, min_dist_m=300)` if not already callable.)

```bash
cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_kl_register_drycontrols.py -q
```
Expected: FAIL (function/entries absent).

- [ ] **Step 2: Implement.**
  - Add the ~8 researched candidates to the in-file candidate list with `kind="dry_lowlying"` and their provenance `source` strings (from Task 1).
  - Add a pure helper `flag_dry_lowlying(lon, lat, positives, min_dist_m=300.0) -> bool` (True = suspicious: too close to a documented positive → likely mis-geocode onto a flood spot).
  - In the verification/print path: for `kind=="dry"` keep the existing `DRY_MIN_ELEV_M=60` elevated check; for `kind=="dry_lowlying"` use `flag_dry_lowlying` instead (do NOT require high elevation — low elevation is expected and correct for a hard negative). Keep writing failed geocodes with empty coords + `confidence=failed`.
- [ ] **Step 3:** Run the test → PASS. Then full suite: `python -m pytest tests/ -q 2>&1 | tail -3` (expect prior count + new tests). Commit:
```bash
git add scripts/build_kl_hotspot_register.py tests/test_kl_register_drycontrols.py
git commit -m "feat: dry_lowlying hard-negative class in KL register builder (distance-to-positive flag) — Plan 9

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 3: Loader maps both dry classes to the negative class (TDD)

**Files:** Modify `scripts/city_manifest.py` (`load_hotspots_from_manifest`); Test `tests/test_manifest_drylowlying.py` (or extend the existing manifest test)

- [ ] **Step 1 (failing test):** Assert that a manifest row with `kind="dry_lowlying"` is loaded as a **negative/dry** Hotspot (same class as `kind="dry"`), and a `positive` row stays positive. Build a tiny temp manifest CSV with one of each and call `load_hotspots_from_manifest` (or its row-mapping helper) directly.
```bash
cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_manifest_drylowlying.py -q
```
Expected: FAIL if the loader keys strictly on `kind == "dry"`.

- [ ] **Step 2: Implement.** In `load_hotspots_from_manifest`, broaden the dry mapping from `kind == "dry"` to `kind in {"dry","dry_lowlying"}` (or `str(kind).startswith("dry")`). Positives unchanged; blank-coord rows still skipped.
- [ ] **Step 3:** Test PASS + full suite green. Commit:
```bash
git add scripts/city_manifest.py tests/test_manifest_drylowlying.py
git commit -m "feat: load_hotspots_from_manifest maps dry_lowlying -> negative class — Plan 9

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 4: Regenerate the register (geocode) + terrain verification table

**Files:** regenerate `data/kuala_lumpur/manifest/hotspots.csv`

- [ ] **Step 1:** Dry-run the builder to see the geocode + verification table without writing:
```bash
cd /d/GPTs/Projects/flood-v2.0 && python scripts/build_kl_hotspot_register.py --dry-run 2>&1 | tail -40
```
Inspect: every new `dry_lowlying` geocoded (no `failed`); each is **low-lying** (record DEM elev + main-stem HAND via a quick check below); none flagged by `flag_dry_lowlying`. If a candidate failed to geocode or landed on a hill/flood spot, replace it from the Task-1 reserve list (still model-blind) and note it.
- [ ] **Step 2:** Terrain confirmation (verification, not selection) — print DEM elevation + `hand_mainstem_utm47n.tif` HAND at each new control to confirm they are genuinely low-lying hard negatives (HAND comparable to flooded positives, not 30+ m hills):
```bash
python - <<'PY'
import sys; sys.path.insert(0,'.')
import rasterio, numpy as np, math
from rasterio.warp import transform as T
import pandas as pd
df=pd.read_csv('data/kuala_lumpur/manifest/hotspots.csv')
dem=rasterio.open('data/kuala_lumpur/copernicus_dem_utm47n.tif'); hnd=rasterio.open('data/kuala_lumpur/hand_mainstem_utm47n.tif')
def samp(ds,lon,lat):
    xs,ys=T('EPSG:4326',ds.crs,[lon],[lat]); c,r=~ds.transform*(xs[0],ys[0]); a=ds.read(1)
    v=a[int(r),int(c)]; nod=ds.nodata
    return float('nan') if (nod is not None and v==nod) else float(v)
for _,x in df[df.kind.astype(str).str.startswith('dry')].iterrows():
    if pd.isna(x.lon): print(f"{x['name'][:34]:34s} FAILED geocode"); continue
    print(f"{x['name'][:34]:34s} {x.kind:12s} DEM={samp(dem,x.lon,x.lat):6.1f}m HAND={samp(hnd,x.lon,x.lat):6.1f}m")
PY
```
Record the table. (Low-lying controls should show low HAND — they are *meant* to be hard.)
- [ ] **Step 3:** Write the register for real (drop `--dry-run`): `python scripts/build_kl_hotspot_register.py`. Confirm `n_dry ≥ 15`. Commit:
```bash
git add data/kuala_lumpur/manifest/hotspots.csv
git commit -m "data: KL register grown to n_dry>=15 (research-grounded low-lying hard negatives) — Plan 9

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 5: Re-validate — honest report (flooded hard negatives STAY)

- [ ] **Step 1:** `python scripts/validate_hotspots_kl.py --out-dir outputs/kuala_lumpur_ssp585_2020 --rp 100`. Capture HR/CRR/TSS + bootstrap CI on the expanded register.
- [ ] **Step 2 (the decisive split):** Report the **elevated-vs-hard CRR split** — of the new low-lying hard negatives, how many stayed dry vs got flooded by the model? Use the per-spot diagnostic pattern (sample the combined RP100 raster at each new control). **Any flooded hard negative is a REAL specificity miss — it stays in the register; report it by name with its depth.** Do NOT remove it to raise CRR.
- [ ] **Step 3:** Honest verdict: does the expanded (harder) negative set keep TSS significant (CI excludes 0) with a tighter interval, or does CRR fall on hard negatives (exposing over-extent the easy set hid)? Either outcome is a real result — state it plainly. Note that HR is unchanged (positives untouched).

### Task 6: Document — dossier §11 + limitation + memory

- [ ] **Step 1:** Dossier §11: the confound (all-elevated negatives), the research-grounded hard-negative method (model-blind sources), the new register (n_dry≥15, elevated/hard split), the before/after gate (7→15 dry: HR/CRR/TSS + CI), and any named hard-negative misses. Verdict: is KL specificity now demonstrated against hard negatives?
- [ ] **Step 2:** Limitations register: add/extend an entry — "KL dry-control set hardened to n≥15 with research-grounded low-lying negatives; CRR is now a *hard*-specificity number (cf. SG #12/#15)." Note residual undocumented-flood risk per control.
- [ ] **Step 3:** Commit; update memory (`v2-spec-and-plans.md`) Plan 9 outcome + advance the NEXT-work list.
```bash
git add docs/superpowers/runs/2026-06-05-kl-validation-dossier.md docs/limitations_register.md
git commit -m "docs: dossier 11 + limitation — KL dry-controls hardened to n>=15 (hard-specificity CRR) — Plan 9

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review
**Spec coverage:** research model-blind hard negatives (T1) → builder `dry_lowlying` class + flag (T2, TDD) → loader mapping (T3, TDD) → regenerate + terrain-verify (T4) → honest re-validation incl. elevated/hard split (T5) → document (T6). ✓ Covers spec §2–6.
**Placeholder scan:** the candidate localities are produced by the research task (T1) with cited sources, not invented here; the flag helper, loader change, and validation commands are concrete. No TBDs. ✓
**Discipline:** model-blind selection (T1 forbids consulting rasters); flooded-hard-negative-STAYS guard (T5); terrain used for verification not labeling (T4); honesty in the verdict (T5/T6). ✓

## Execution Handoff
Plan 9 of N. After execution: finish branch → remaining KL work: (2) scenario-forcing #16 regen (note pluvial raster regen is perf-blocked #18 — regen the hazard-LEVELS, defer rasters or parallelize), (3) SSP5-8.5 2100 + viz + dossier finalization, (4) AR6 offline-repeatability. Then transfer the KL template (incl. main-stem-HAND rule #20) to Bangkok + Jakarta.
