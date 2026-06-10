# Jakarta J1 — Foundation + First Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Jakarta's four-manifest contract + a model-blind hotspot register, validate the **existing** Jakarta model present-day (no model changes), and deliver an honest first-gate verdict (hotspot HR/CRR/TSS primary + elevated JKT2020 extent-CSI support).

**Architecture:** Pure transfer — reuse the already-generalized `validate_hotspots.py --city`, `city_manifest.py`, `hotspot_scoring.py`, `combine_hazard_depth.py`, and `validate_historical_events.py` engines. The only new code is a Jakarta register builder (cloned from the Bangkok one) + four Jakarta manifest CSVs + a register test. KL + Bangkok stay regression-locked.

**Tech Stack:** Python 3, rasterio, click, numpy, pysheds (HAND already built), Nominatim geocoding, the v2.0 `run_multihazard` pipeline. Spec: `docs/superpowers/specs/2026-06-09-jakarta-validation-transfer-design.md`.

**Discipline:** model-blind register; documented anchors not gate-tuning; flooded dry controls STAY; KL/Bangkok regression-locked. Validation-first — fixes are J2+ follow-ons.

---

### Task 1: Jakarta static manifests + register research doc

**Files:**
- Create: `data/jakarta/manifest/gates.csv`
- Create: `data/jakarta/manifest/forcing_anchors.csv`
- Create: `data/jakarta/manifest/observed_events.csv`
- Create: `docs/superpowers/runs/2026-06-09-jakarta-hotspot-research.md`

- [ ] **Step 1: Write `gates.csv`** (mirrors Bangkok; CSI is an elevated *support* gate for Jakarta — the JKT2020 SAR is trustworthy)

```csv
hazard,metric,threshold,direction,citation
pluvial,hotspot_hit_rate,0.70,>=,"documented-hotspot hit-rate floor (Singapore/KL/Bangkok methodology precedent; Peirce/Hanssen-Kuipers TSS)"
pluvial,hotspot_crr,0.70,>=,"dry-control correct-reject-rate floor (specificity; Singapore/KL/Bangkok methodology)"
coastal,CSI,0.30,>=,"JKT2020 Sentinel-1 EOS-ARIA extent-CSI — ELEVATED support gate (Jakarta is the first city with a trustworthy SAR reference); WARN band Bates & De Roo 2000 / Bernhofen et al. 2018"
coastal,FAR,0.70,<=,"JKT2020 extent false-alarm-rate ceiling (prior bathtub run = 0.87, over-prediction; Pappenberger et al. 2007)"
coastal,POD,0.60,>=,"JKT2020 extent probability-of-detection floor (Wing et al. 2017)"
```

- [ ] **Step 2: Write `forcing_anchors.csv`** (documented provenance for the three hazards; values from `scripts/cities.py` jakarta + `docs/hazard_methodology_comparison.md`)

```csv
hazard,duration_h,anchor_rp,anchor_value,unit,source,citation
fluvial,24,10,3.34,m,GloFAS v4,"GloFAS v4 daily discharge at Ciliwung-Depok (-6.35N,106.84E); RP10 Manning stage above bed = 3.34 m (methodology 2026-05-12). Captures the Ciliwung sub-basin; Jakarta's other ~12 rivers are single-reach-unrepresented (#single-reach)"
coastal,24,100,1.0,m,Muis et al. 2016,"Global Extreme Sea Levels still-water RP100 screening for Jakarta Bay (no UHSLC gauge; uncertainty +/-0.2-0.3 m). Coastal maps QUALITATIVE; treat as screening-level"
pluvial,24,2,114.0,mm,ERA5-Land,"Existing Jakarta pluvial = ERA5-Land reanalysis via Open-Meteo (NOT IDF-calibrated, unlike KL/Bangkok) — a documented J1 provenance gap; RP2 24h ERA5-Land Gumbel (cities.py jakarta)"
pluvial,24,100,377.0,mm,BMKG 2020-01-01,"Jan-2020 record daily rainfall ~377 mm at Halim (BMKG) — documented extreme-event sanity anchor for the JKT2020 validation event (~RP50-100 locally)"
```

> Note: confirm the `pluvial` RP2 ERA5-Land value against `scripts/cities.py` jakarta config when implementing; if the committed config differs, use the config value and keep the citation. The row's PURPOSE is to record provenance — the ERA5-Land-not-IDF gap is the documented finding.

- [ ] **Step 3: Write `observed_events.csv`** (the JKT2020 SAR event; the SHP is already in-repo)

```csv
event_id,hazard,event_date,est_rp_low,est_rp_high,extent_path,source
JKT2020,pluvial,2020-01-01,50,100,data/jakarta/flood_obs/JKT2020/EOS_ARIA-SG_20200102_FPM_Indonesia_Floods_v1.5_SHP/EOS_ARIA-SG_20200102_FPM_Indonesia_Floods_v1.5_TIFF_shp.shp,"Sentinel-Asia EOS-ARIA-SG Sentinel-1 SAR flood proxy (2 Jan 2020). Jakarta New Year flood: record ~377 mm/24h rainfall (BMKG); 60+ deaths; extreme-pluvial-dominated event. RP50-100 locally"
```

- [ ] **Step 4: Write the register research doc** `docs/superpowers/runs/2026-06-09-jakarta-hotspot-research.md` — the model-blind sourcing rationale: recurrent documented flood kelurahan across 2007/2013/2020 spanning the three mechanisms (Ciliwung-corridor fluvial; monsoon pluvial incl. the famous 2020 Kemang/Cipinang Melayu; North-Jakarta rob), and the dry-control logic (elevated south toward Depok — geographically appropriate elevated negatives, *with* the explicit note that some affluent-south pockets like Kemang DO flood, so dry controls are the genuinely-high south + documented-dry central levee like Menteng). One paragraph per mechanism, each hotspot cited. This is the audit trail that the register was frozen BEFORE reading the model.

- [ ] **Step 5: Verify the three CSVs load** (no hotspots.csv yet, so the full manifest validator will report only the missing-hotspots issue)

Run: `python -c "import csv; [print(p, len(list(csv.DictReader(open(p))))) for p in ['data/jakarta/manifest/gates.csv','data/jakarta/manifest/forcing_anchors.csv','data/jakarta/manifest/observed_events.csv']]"`
Expected: `gates.csv 5`, `forcing_anchors.csv 4`, `observed_events.csv 1` (no exceptions).

- [ ] **Step 6: Commit**

```bash
git add data/jakarta/manifest/gates.csv data/jakarta/manifest/forcing_anchors.csv data/jakarta/manifest/observed_events.csv docs/superpowers/runs/2026-06-09-jakarta-hotspot-research.md
git commit -m "feat(jakarta): static manifests (gates/forcing/observed) + register research doc"
```

---

### Task 2: Jakarta register builder + SEED + offline test

**Files:**
- Create: `scripts/build_jakarta_hotspot_register.py` (clone of `scripts/build_bangkok_hotspot_register.py` with the diffs below)
- Create: `tests/test_jakarta_register.py`

- [ ] **Step 1: Clone the Bangkok builder**

```bash
cp scripts/build_bangkok_hotspot_register.py scripts/build_jakarta_hotspot_register.py
```

- [ ] **Step 2: Apply these EXACT constant + docstring diffs** in `scripts/build_jakarta_hotspot_register.py`

Replace the module docstring's city references with Jakarta, and replace the constants block:

```python
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEM_PATH = PROJECT_ROOT / "data" / "jakarta" / "copernicus_dem_utm48s.tif"   # uncorrected GLO-30 for geocode-verify
OUT_CSV = PROJECT_ROOT / "data" / "jakarta" / "manifest" / "hotspots.csv"

# Greater Jakarta (Jabodetabek core) viewbox to bias Nominatim (min_lon, min_lat, max_lon, max_lat)
VIEWBOX = (106.60, -6.40, 107.05, -6.05)

# DEM elevation expectations (m, GLO-30). DKI core is ~0-15 m; the south rises toward Depok.
# A documented POSITIVE landing implausibly high is a mis-geocode (rooftop / upland point).
POSITIVE_MAX_ELEV_M = 50.0
# Jakarta DOES have a real elevation gradient (unlike Bangkok's flat delta): dry controls are
# the genuinely-elevated south + documented-dry central levee. Soft elevation expectation only;
# the firm mis-geocode guard for a dry control is proximity to a positive (metres).
DRY_MIN_DIST_TO_POSITIVE_M = 50.0
```

And change the `_geocode` country filter from `"countrycodes": "th"` to `"countrycodes": "id"`.

- [ ] **Step 3: Replace the `SEED` list** with the model-blind Jakarta register (≥15 positives, ≥7 dry)

```python
SEED: list[tuple[str, str, str, str]] = [
    # --- Positives: Ciliwung-corridor fluvial (chronic 2007/2013/2020) ---
    ("Kampung Melayu", "Kampung Melayu, Jatinegara, Jakarta, Indonesia", "positive", "Ciliwung overflow; chronic 2007/2013/2020 flooding (BPBD DKI; news)"),
    ("Bukit Duri", "Bukit Duri, Tebet, Jakarta, Indonesia", "positive", "Ciliwung bank; recurrent inundation 2007/2013/2020 (news; academic)"),
    ("Kampung Pulo", "Kampung Pulo, Jatinegara, Jakarta, Indonesia", "positive", "Ciliwung meander; iconic chronic flood site (BPBD DKI)"),
    ("Cawang", "Cawang, Kramat Jati, Jakarta, Indonesia", "positive", "Ciliwung corridor; 2007/2013/2020 flooding (news)"),
    ("Rawajati", "Rawajati, Pancoran, Jakarta, Indonesia", "positive", "Ciliwung bank South Jakarta; recurrent (news)"),
    ("Bidara Cina", "Bidara Cina, Jatinegara, Jakarta, Indonesia", "positive", "Ciliwung corridor; recurrent (news)"),
    # --- Positives: monsoon pluvial / other rivers (2020-prominent) ---
    ("Cipinang Melayu", "Cipinang Melayu, Makasar, Jakarta, Indonesia", "positive", "East Jakarta; among worst-hit Jan-2020 (Sunter/Cipinang; news)"),
    ("Kemang", "Kemang, Mampang Prapatan, Jakarta, Indonesia", "positive", "Krukut river; affluent-South pocket flooded Jan-2020 (widely reported)"),
    ("Kelapa Gading", "Kelapa Gading, Jakarta, Indonesia", "positive", "North-East low pluvial basin; chronic ponding 2013/2020 (news)"),
    ("Grogol", "Grogol, Grogol Petamburan, Jakarta, Indonesia", "positive", "West Jakarta; Sekretaris/Grogol canal flooding 2020 (news)"),
    ("Cengkareng", "Cengkareng, Jakarta, Indonesia", "positive", "West Jakarta; Angke/Cengkareng drain flooding 2020 (news)"),
    # --- Positives: North Jakarta rob / coastal-subsidence ---
    ("Penjaringan", "Penjaringan, Jakarta, Indonesia", "positive", "North Jakarta polder below MSL; rob + 2007/2020 coastal flooding (BAPPENAS; news)"),
    ("Pluit", "Pluit, Penjaringan, Jakarta, Indonesia", "positive", "North Jakarta below sea level; chronic rob, pump-dependent (news)"),
    ("Muara Baru", "Muara Baru, Penjaringan, Jakarta, Indonesia", "positive", "North Jakarta fastest-subsiding; rob flooding (Banten Bay studies; news)"),
    ("Kalibaru", "Kalibaru, Cilincing, Jakarta, Indonesia", "positive", "North-East coast; rob + tidal flooding (news)"),
    ("Cilincing", "Cilincing, Jakarta, Indonesia", "positive", "North-East coastal kelurahan; rob (news)"),
    # --- Dry controls: genuinely-elevated south + documented-dry central levee ---
    ("Cilandak", "Cilandak, Jakarta, Indonesia", "dry", "Elevated South Jakarta; not on the 2007/2013/2020 flood lists (terrain-high control)"),
    ("Jagakarsa", "Jagakarsa, Jakarta, Indonesia", "dry", "Elevated far-South Jakarta; higher ground toward Depok (control)"),
    ("Lebak Bulus", "Lebak Bulus, Cilandak, Jakarta, Indonesia", "dry", "Elevated South Jakarta (control)"),
    ("Pasar Minggu", "Pasar Minggu, Jakarta, Indonesia", "dry", "South Jakarta upland away from Ciliwung bank (control)"),
    ("Menteng", "Menteng, Jakarta, Indonesia", "dry", "Central historical natural-levee core, built high; documented relatively dry (control)"),
    ("Gambir", "Gambir, Jakarta, Indonesia", "dry", "Central Monas/levee core; relatively dry (control)"),
    ("Cipete", "Cipete, Cilandak, Jakarta, Indonesia", "dry", "Elevated South Jakarta residential (control)"),
]
```

- [ ] **Step 3b: Write the failing test** `tests/test_jakarta_register.py` (clone of `tests/test_bangkok_register.py`)

```python
"""Pure-logic guards for the Jakarta hotspot register (no network)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_jakarta_hotspot_register import SEED
from scripts.city_manifest import validate_manifest


def test_candidate_list_shape_and_provenance():
    pos = [c for c in SEED if c[2] == "positive"]
    dry = [c for c in SEED if c[2] == "dry"]
    assert len(pos) >= 15, f"expected >=15 positives, got {len(pos)}"
    assert len(dry) >= 7, f"expected >=7 dry controls, got {len(dry)}"
    assert all(c[3].strip() for c in SEED), "every candidate must carry a source/provenance"
    assert {c[2] for c in SEED} == {"positive", "dry"}


def test_jakarta_manifest_valid_when_present():
    if not Path("data/jakarta/manifest/hotspots.csv").exists():
        pytest.skip("hotspots.csv not geocoded yet")
    assert validate_manifest("jakarta") == []
```

- [ ] **Step 4: Run the test — verify it passes the shape guard, skips the manifest guard**

Run: `python -m pytest tests/test_jakarta_register.py -v`
Expected: `test_candidate_list_shape_and_provenance PASSED`, `test_jakarta_manifest_valid_when_present SKIPPED` (hotspots.csv not built yet).

- [ ] **Step 5: Commit**

```bash
git add scripts/build_jakarta_hotspot_register.py tests/test_jakarta_register.py
git commit -m "feat(jakarta): hotspot register builder + SEED (model-blind) + offline guard test"
```

---

### Task 3: Geocode + DEM-verify → write `hotspots.csv`

**Files:**
- Create: `data/jakarta/manifest/hotspots.csv` (builder output)

- [ ] **Step 1: Dry-run the builder** (prints the geocode + elevation + flag table, writes nothing)

Run: `python scripts/build_jakarta_hotspot_register.py --dry-run`
Expected: a table with lon/lat/elev/flag per seed. Inspect: positives should land in DKI (elev ~0–15 m, north near 0); dry controls in the elevated south (elev higher) or central levee. Any `GEOCODE_FAILED`, `OUT_OF_DEM`, `REVIEW: positive high`, or dry-near-positive flags are noted.

- [ ] **Step 2: Adjudicate flags (model-blind).** For each flagged row, fix the geocode query (more specific) OR drop it with a documented reason in the research doc (mirror Bangkok's Nava Nakorn drop — out-of-domain → drop, don't force). Re-run `--dry-run` until the table is clean or every residual flag is documented. **Do NOT consult the model outputs when adjudicating** (model-blind).

- [ ] **Step 3: Write the register**

Run: `python scripts/build_jakarta_hotspot_register.py`
Expected: writes `data/jakarta/manifest/hotspots.csv` (columns `name,lon,lat,kind,confidence,source`); prints the final table.

- [ ] **Step 4: Verify the full manifest validates**

Run: `python -c "from scripts.city_manifest import validate_manifest; print(validate_manifest('jakarta'))"`
Expected: `[]` (all four manifests present + consistent).

- [ ] **Step 5: Run the register test (manifest guard now active)**

Run: `python -m pytest tests/test_jakarta_register.py -v`
Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add data/jakarta/manifest/hotspots.csv docs/superpowers/runs/2026-06-09-jakarta-hotspot-research.md
git commit -m "feat(jakarta): geocoded + DEM-verified hotspot register (NN positives + NN dry)"
```

---

### Task 4: Generate the present-day RP100 baseline (existing model, no changes)

**Files:**
- Produces: `outputs/jakarta_ssp585_2020/{pluvial,fluvial,coastal}/rp_100/*.tif`

- [ ] **Step 1: Pin the exact Jakarta run command.** Read `scripts/run_city_pipeline.py` for the `jakarta` block (DEM variant, sea-mask, coastal solver/seeds/MSL offset, pluvial model, `--fluvial-bankfull-rp`, inertial params) exactly as Bangkok B1 did. Record the resolved `run_multihazard` invocation in the dossier (Task 6). Use the **subsidence-corrected DEM** (`copernicus_dem_utm48s_subsidence_corrected.tif`), reuse the committed `data/jakarta/hazard_levels_ssp585_2020.csv`, and the AR6 offline cache (`--offline`).

- [ ] **Step 2: Run RP100 only** (the event-matched RP; full 9-RP deferred per spec §5). Invoke `run_multihazard` for `jakarta`, scenario SSP5-8.5, horizon 2020, RP 100, with `--fluvial-bankfull-rp 0` (v2.0 CSV convention, #20) and `--offline`. Output to `outputs/jakarta_ssp585_2020/`.

Expected: `pluvial/rp_100/`, `fluvial/rp_100/`, `coastal/rp_100/` depth rasters written. Note wall-time (the inertial coastal solver is ~50 min/RP — same as Bangkok).

- [ ] **Step 3: Sanity-check extents** (no gate yet — just plausibility)

Run: `python -c "import rasterio,numpy as np; [print(h, (lambda a: (np.isfinite(a)&(a>0.1)).sum()*900/1e6)(rasterio.open(f'outputs/jakarta_ssp585_2020/{h}/rp_100/{h}_depth_SSP5-8.5_2020_rp100.tif').read(1).astype(float))) for h in ('pluvial','fluvial','coastal')]"`
Expected: three positive km² extents printed (coastal concentrated in the subsiding north; fluvial along the Ciliwung; pluvial broad). Flag any that is ~0 or ~whole-domain for the diagnosis.

- [ ] **Step 4: Commit** (outputs are gitignored; commit only any committed inputs/notes touched)

```bash
git add -A data/jakarta outputs/.gitignore 2>/dev/null; git commit -m "chore(jakarta): present-day RP100 baseline generated (existing model)" --allow-empty
```

---

### Task 5: Validate — hotspot gate + JKT2020 extent-CSI

**Files:** none created (runs existing validators; numbers feed Task 6)

- [ ] **Step 1: Run the hotspot gate**

Run: `python scripts/validate_hotspots.py --city jakarta --out-dir outputs/jakarta_ssp585_2020 --rp 100`
Expected: prints `positives n=… hit-rate=…`, `dry n=… CRR=…`, `TSS=… 95% CI […]`, and `GATE PASS` or `GATE FAIL: …`. Record HR / CRR / TSS + CI verbatim.

- [ ] **Step 2: Per-hazard attribution.** For each missed positive and each flooded dry control, record which hazard layer (pluvial/fluvial/coastal) is responsible — reuse the sampling approach from `scripts/_diag_bangkok_trunk_hand.py` (sample each hazard raster at the register points). This is the diagnosis, not a fix.

- [ ] **Step 3: Run the JKT2020 extent-CSI support gate**

Run: `python scripts/validate_historical_events.py --event JKT2020 --out-dir outputs/jakarta_ssp585_2020`
Expected: prints CSI / H(POD) / FAR / Bias for the best-matching hazard+RP vs the EOS-ARIA Sentinel-1 polygon. Record verbatim. (Prior bathtub baseline: CSI 0.10 / H 0.34 / FAR 0.87 — note any change.)

- [ ] **Step 4: No commit** (measurement only; results documented in Task 6).

---

### Task 6: Dossier + limitations + memory + finish

**Files:**
- Create: `docs/superpowers/runs/2026-06-09-jakarta-validation-dossier.md`
- Modify: `docs/limitations_register.md` (append Jakarta entries)

- [ ] **Step 1: Write the dossier** with sections mirroring the Bangkok B1 dossier: §1 method (hotspot primary + elevated JKT2020 CSI; register provenance), §2 numeric gate (HR/CRR/TSS + CI table, the resolved `run_multihazard` command), §3 per-hazard + per-spot diagnosis, §4 JKT2020 extent-CSI result, §5 honest verdict + the documented, evidence-driven J2+ fixes (e.g. inertial coastal if bathtub FAR confirmed; multi-river fluvial; the ERA5-Land-not-IDF pluvial provenance gap; the qualitative-coastal caveat). Keep the cardinal rule explicit: flooded dry controls + missed positives STAY.

- [ ] **Step 2: Append Jakarta limitation rows** to `docs/limitations_register.md`: (a) coastal forcing qualitative (Muis screening, no gauge); (b) single-reach Ciliwung fluvial (other ~12 rivers unrepresented); (c) pluvial ERA5-Land not IDF-calibrated (unlike KL/Bangkok). Each as a numbered row in the existing table format, status "Known / characterised", dated 2026-06-09.

- [ ] **Step 3: Update memory** (`v2-spec-and-plans.md`): add a Jakarta J1 line with the verdict + the J2+ fix list, mirroring the Bangkok lines.

- [ ] **Step 4: Run the full test suite — confirm green + KL/Bangkok regression-locked**

Run: `python -m pytest -q`
Expected: all pass + Jakarta register tests added (≈237 passed, 1 skipped); KL + Bangkok gates unchanged.

- [ ] **Step 5: Commit + finish the branch**

```bash
git add docs/superpowers/runs/2026-06-09-jakarta-validation-dossier.md docs/limitations_register.md
git commit -m "docs(jakarta): J1 validation dossier + limitations + memory — honest first-gate verdict"
```
Then invoke **superpowers:finishing-a-development-branch** (verify tests → present the 4 options → execute).

---

## Self-Review

**Spec coverage:** §1 principle → Task 1–6 validation-first, no model changes ✓. §2 contrasts → coastal/CSI/fluvial each surfaced in gates+forcing+diagnosis ✓. §3 components → Task 2 builder (clone), Task 1 manifests, reuse engines ✓. §4 register → Task 1 research doc + Task 2 SEED (mechanism-spanning, elevated-south dry, Kemang-floods caveat) + Task 3 geocode/DEM-verify/drop-out-of-domain ✓. §5 gate → Task 5 hotspot RP100 + JKT2020 CSI ✓. §6 baseline → Task 4 existing config, subsidence DEM, `--fluvial-bankfull-rp 0`, `--offline`, RP100 ✓. §7 anticipated diagnoses → Task 5 attribution + Task 6 J2 list ✓. §8 testing → Task 2/3 register tests + Task 6 regression lock ✓. §9 deliverable → Task 6 dossier+limitations+memory+finish ✓. §10 out-of-scope → no model-change tasks present ✓.

**Placeholder scan:** CSV contents, SEED list, builder diffs, and test code are all concrete. The two soft spots are intentional + documented: Task 1 Step 2 ERA5-Land RP2 value (confirm-against-config note, purpose is provenance) and Task 4 Step 1 (pin exact flags from `run_city_pipeline.py` — the same evidence-driven pinning Bangkok B1 used, since the existing Jakarta flag set lives in that file). Both are "read the existing config and record it," not "decide later."

**Type consistency:** `SEED: list[tuple[str,str,str,str]]`, `validate_manifest('jakarta')`, raster path pattern `{hz}_depth_SSP5-8.5_2020_rp100.tif`, and `kind ∈ {positive,dry}` match the generalized engine + the Bangkok templates throughout.

## Execution Handoff
Plan J1 of N. After execution: evidence-driven J2 (the confirmed top fix — likely inertial coastal and/or multi-river fluvial) → future-scenario products → cross-city synthesis (KL+Bangkok+Jakarta).
