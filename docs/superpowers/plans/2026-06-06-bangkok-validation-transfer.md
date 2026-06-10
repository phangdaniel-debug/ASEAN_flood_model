# Bangkok Validation Transfer (Plan B1 of N)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring **Bangkok** to KL's validated standard, validation-first — generalize the hotspot validator for multi-city reuse, build Bangkok's four-manifest contract + a model-blind documented-hotspot register (2011 positives + defended-core dry controls), generate the present-day baseline with the *existing* Bangkok model, run the **HR/CRR/TSS** gate (pluvial∨fluvial∨coastal) with THA2011 extent-CSI as support, and produce an honest verdict. Spec: `docs/superpowers/specs/2026-06-06-bangkok-validation-transfer-design.md`.

**Architecture:** Validation-first (KL rhythm): build the gate, run it against the current model, let it reveal fixes. No model changes this round. The validator becomes city-parameterized (`--city`) and unions whatever hazard rasters exist (KL: pluvial+fluvial; Bangkok: +coastal).

**Tech Stack:** Python 3, pandas, rasterio, click, pytest; Nominatim (geocoding); existing `scripts/{validate_hotspots_kl,build_kl_hotspot_register,city_manifest,combine_hazard_depth,hotspot_scoring,run_multihazard,validate_historical_events}.py`.

**Discipline (cardinal):** hotspot selection is model-blind — positives from 2011-flood records, dry controls from documented-defended/spared areas; the dry label NEVER comes from the model's wet-mask. The gate reveals fixes; it is never tuned to.

---

### Task 1: Generalize the hotspot validator to `--city` (TDD; KL regression-locked)

**Files:** Create `scripts/validate_hotspots.py`; rewrite `scripts/validate_hotspots_kl.py` as a thin wrapper; Test `tests/test_validate_hotspots_general.py`.

- [ ] **Step 1 (failing test):** `tests/test_validate_hotspots_general.py` — assert the generalized CLI reproduces KL's current numbers AND that it unions only the hazards that exist:
```python
import sys; from pathlib import Path
import re
from click.testing import CliRunner
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.validate_hotspots import cli, _hazard_rasters

OUT = Path("outputs/kuala_lumpur_ssp585_2020")

def _parse(output):
    hr = float(re.search(r"hit-rate=([0-9.]+)", output).group(1))
    crr = float(re.search(r"CRR=([0-9.]+)", output).group(1))
    return hr, crr

import pytest
@pytest.mark.skipif(not OUT.exists(), reason="KL outputs absent")
def test_kl_via_general_matches_known_gate():
    r = CliRunner().invoke(cli, ["--city", "kuala_lumpur", "--out-dir", str(OUT), "--rp", "100"])
    assert r.exit_code == 0, r.output
    hr, crr = _parse(r.output)
    assert abs(hr - 0.76) < 0.01 and abs(crr - 0.86) < 0.01   # KL gate unchanged

def test_hazard_rasters_unions_only_existing(tmp_path):
    (tmp_path / "pluvial" / "rp_100").mkdir(parents=True)
    (tmp_path / "pluvial" / "rp_100" / "pluvial_depth_SSP5-8.5_2020_rp100.tif").write_bytes(b"x")
    found = _hazard_rasters(tmp_path, "SSP5-8.5", 2020, 100)
    assert [p.parent.parent.name for p in found] == ["pluvial"]   # fluvial/coastal absent -> excluded
```

- [ ] **Step 2:** Implement `scripts/validate_hotspots.py` by generalizing the KL validator. Key change — a helper that unions only existing hazard rasters (so KL = pluvial+fluvial, Bangkok = +coastal):
```python
def _hazard_rasters(out_dir, scenario, horizon, rp):
    """Return the list of EXISTING per-hazard depth rasters for this RP."""
    found = []
    for hz in ("pluvial", "fluvial", "coastal"):
        p = out_dir / hz / f"rp_{rp}" / f"{hz}_depth_{scenario}_{horizon}_rp{rp}.tif"
        if p.exists():
            found.append(p)
    return found
```
The `cli` gains `@click.option("--city", required=True)` and uses `load_hotspots_from_manifest(city)`; the body becomes:
```python
    rasters = _hazard_rasters(out_dir, scenario, horizon, rp)
    if not rasters:
        click.echo(f"[error] no hazard rasters found under {out_dir} for rp{rp}", err=True); sys.exit(2)
    combined = combine_depth_rasters(rasters, out_dir / "_validation" / f"combined_rp{rp}.tif")
    hotspots = load_hotspots_from_manifest(city)
```
Keep every other option (`--rp/--scenario/--horizon/--depth-threshold/--radius-m/--hr-floor/--crr-floor`), the `skill_scores`/`bootstrap_tss_ci` reporting, and the gate/exit-code logic identical to `validate_hotspots_kl.py`.

- [ ] **Step 3:** Replace `scripts/validate_hotspots_kl.py` body with a thin back-compat wrapper:
```python
"""Back-compat shim — KL hotspot validation is now scripts/validate_hotspots.py --city kuala_lumpur."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.validate_hotspots import cli
if __name__ == "__main__":
    cli(default_map={"city": "kuala_lumpur"})
```
(If `default_map` injection is awkward with the required `--city`, instead make `validate_hotspots_kl.py` `import sys; sys.argv += ["--city","kuala_lumpur"]; from scripts.validate_hotspots import cli; cli()` — pick whichever passes the regression test; the requirement is that the old `validate_hotspots_kl.py --out-dir … --rp 100` invocation still works and prints the same numbers.)

- [ ] **Step 4:** Run the test + the full suite. Confirm KL gate unchanged (HR 0.76 / CRR 0.86). Commit.
```bash
cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_validate_hotspots_general.py -q && python -m pytest tests/ -q 2>&1 | tail -3
git add scripts/validate_hotspots.py scripts/validate_hotspots_kl.py tests/test_validate_hotspots_general.py
git commit -m "feat: generalize hotspot validator to --city (unions existing hazards; KL regression-locked) — Bangkok transfer

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 2: Research the Bangkok 2011 hotspots (model-blind) + provenance

**Files:** Create `docs/superpowers/runs/2026-06-06-bangkok-hotspot-research.md`

- [ ] **Step 1:** Web-research the **2011 Thailand flood in the Bangkok Metropolitan Region**, model-blind. Compile: (a) **positives** — documented-inundated localities (e.g. Don Muang, Rangsit, Sai Mai, Bang Khen, Lak Si, Nava Nakorn / Bang Kadi industrial estates, Bang Bua Thong, Pak Kret, Min Buri / eastern suburbs) from academic + agency + news sources; (b) **dry controls** — the documented-DEFENDED inner core that stayed dry behind the King's-Dyke/flood-wall line (e.g. Silom, Sathorn, Sukhumvit, Siam/Pathum Wan CBD) **plus** any elevated controls. For EACH candidate record: name, a Nominatim geocode query, kind (positive/dry), and the **source(s) + one-line justification**. Aim for ~15 positives + ~7 dry controls (KL parity). **Do NOT consult the model's flood rasters.** Note the defended/undefended 2011 line as the key dry-control rationale. Commit.

### Task 3: Bangkok register builder + four-manifest contract (TDD on the pure logic)

**Files:** Create `scripts/build_bangkok_hotspot_register.py` (mirrors `build_kl_hotspot_register.py`); Create `data/bangkok/manifest/{forcing_anchors,gates,observed_events,hotspots}.csv`; Test `tests/test_bangkok_register.py`.

- [ ] **Step 1 (failing test):** `tests/test_bangkok_register.py` — pure-logic guards (no network): the builder's candidate list has ≥15 positives + ≥7 dry; every candidate has a non-empty `source`; `validate_manifest("bangkok")` returns no problems once the four CSVs exist.
```python
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_bangkok_hotspot_register import CANDIDATES
from scripts.city_manifest import validate_manifest

def test_candidate_list_shape_and_provenance():
    pos = [c for c in CANDIDATES if c[2] == "positive"]
    dry = [c for c in CANDIDATES if c[2] == "dry"]
    assert len(pos) >= 15 and len(dry) >= 7
    assert all(c[3].strip() for c in CANDIDATES)   # every spot has a source

def test_bangkok_manifest_valid_when_present():
    import pytest
    if not (Path("data/bangkok/manifest/hotspots.csv").exists()):
        pytest.skip("manifest not built yet")
    assert validate_manifest("bangkok") == []
```

- [ ] **Step 2:** Write `scripts/build_bangkok_hotspot_register.py` — copy `build_kl_hotspot_register.py`, set `DEM_PATH = data/bangkok/copernicus_dem_utm47n.tif`, `OUT_CSV = data/bangkok/manifest/hotspots.csv`, a Bangkok `VIEWBOX = (100.30, 13.45, 100.95, 14.20)`, and replace `CANDIDATES` with the Task-2 list `(display_name, geocode_query, kind, source)`. Keep `_geocode` + `_dem_elev` + the `--dry-run` table. **Dry-control verification:** Bangkok's defended-core dry controls are LOW-lying (the whole delta is flat), so DON'T require `elev ≥ 60 m` — drop the `DRY_MIN_ELEV_M` elevation gate (it assumed KL hills); instead just record DEM elevation in the verification table and flag a dry control only if it lands within ~50 m of a positive (mis-geocode). Document this in the file header.
- [ ] **Step 3:** Create the other three manifests by mirroring KL's:
  - `data/bangkok/manifest/gates.csv` — copy `data/kuala_lumpur/manifest/gates.csv` (same HR/CRR floors 0.70, TSS reporting).
  - `data/bangkok/manifest/forcing_anchors.csv` + `observed_events.csv` — mirror KL's schema with Bangkok values (forcing anchors from `cities.py` bangkok block + the methodology doc; observed_events = the 2011 megaflood row with its event-RP note). Keep minimal but schema-valid (`validate_manifest` only checks columns + non-empty for required files).
- [ ] **Step 4:** Run the pure-logic test (green) + commit the builder, tests, and the three non-geocoded manifests.
```bash
cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_bangkok_register.py -q
git add scripts/build_bangkok_hotspot_register.py tests/test_bangkok_register.py data/bangkok/manifest/gates.csv data/bangkok/manifest/forcing_anchors.csv data/bangkok/manifest/observed_events.csv
git commit -m "feat: Bangkok hotspot register builder + manifests (2011 positives + defended-core dry controls) — Bangkok transfer

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 4: Geocode the register + terrain-verify

**Files:** produces `data/bangkok/manifest/hotspots.csv`

- [ ] **Step 1:** Dry-run the builder (Nominatim, 1 req/s): `python scripts/build_bangkok_hotspot_register.py --dry-run 2>&1 | tail -40`. Inspect: every candidate geocoded (no `failed`); positives land low (valley/suburb), dry controls land in the CBD; none flagged as mis-geocoded. Replace any failed/mis-placed candidate from the Task-2 reserve list (still model-blind) and note it.
- [ ] **Step 2:** Write the register for real: `python scripts/build_bangkok_hotspot_register.py`. Confirm `validate_manifest("bangkok")` clean and counts (≥15 positive, ≥7 dry). Commit `data/bangkok/manifest/hotspots.csv`.

### Task 5: Generate the present-day Bangkok baseline (existing model; offline; parallel)

**Files:** produces (gitignored) `outputs/bangkok_ssp585_2020/`

- [ ] **Step 1:** Generate the present-day Bangkok rasters with the **existing** model config (NO model changes) — pluvial (raingrid) ∨ fluvial (HAND) ∨ coastal (inertial), offline (committed `hazard_levels_ssp585_2020.csv`, AR6 cache), using `--raingrid-workers 0` (Plan-10 ~2.6×). Mirror the `cities.py` `bangkok` config's solver/raster inputs (sea mask, river mask, runoff, subsidence-corrected DEM, inertial coastal). Inspect the exact flags from how Bangkok was last run (`run_city_pipeline.py --city bangkok` defaults, or the documented `run_multihazard` Bangkok command). Long (~2–3 h); background. Confirm completion + monotonicity + plausible extents (the methodology doc benchmarks Bangkok inertial RP100 ≈ a few hundred km²).
- [ ] **Step 2:** Confirm all three hazard rasters exist for rp_100 under `outputs/bangkok_ssp585_2020/{pluvial,fluvial,coastal}/rp_100/`.

### Task 6: Validate + dossier + memory

- [ ] **Step 1:** Run the gate: `python scripts/validate_hotspots.py --city bangkok --out-dir outputs/bangkok_ssp585_2020 --rp 100`. Capture HR/CRR/TSS + bootstrap CI. (RP100 ≈ the 2011 event RP; note the documented GLoFAS-RP6-vs-observed-RP50-100 caveat.)
- [ ] **Step 2 (support):** Run/quote the THA2011 extent-CSI: `python scripts/validate_historical_events.py` (THA2011 event) — record CSI / H / FAR against the 2011 MODIS raster as the supporting diagnostic.
- [ ] **Step 3 (per-spot):** For each hotspot, sample the combined RP100 depth (reuse the KL per-spot diagnostic pattern). Report which positives are caught, which dry controls stay dry, and—if coastal over-floods the lower delta—whether any gulf-adjacent dry control is falsely flooded (a real finding, not hidden).
- [ ] **Step 4:** Write `docs/superpowers/runs/2026-06-06-bangkok-validation-dossier.md`: scope/method, the numeric gate table (HR/CRR/TSS + CI), the THA2011 CSI support, per-spot diagnostics, and an **honest verdict** (PASS / marginal / FAIL-with-diagnosed-causes). Enumerate any model fixes the gate calls for (deferred to follow-on plans, each to be anchored to a documented fact). Commit. Update memory (`v2-spec-and-plans.md`): Bangkok transfer started, first-validation result, next fixes.

---

## Self-Review
**Spec coverage:** generalize validator (T1, spec §4.1) → research positives+dry-controls (T2, §4.3) → builder + manifests (T3, §4.2/4.3) → geocode/verify (T4) → present-day baseline existing-model (T5, §4.5) → validate + CSI + dossier (T6, §4.5/4.6). ✓
**Placeholder scan:** the validator generalization shows the exact `_hazard_rasters` + cli body; the register builder mirrors a named existing file with the concrete Bangkok VIEWBOX + the dropped-elevation-gate change; the 2011 candidate localities are produced by the research task with cited sources (not invented in the plan). Run/commit commands are explicit. ✓
**Discipline:** model-blind hotspot sourcing (T2 forbids consulting rasters; dry label from 2011 records); existing-model validation-first (no pre-applied fixes); KL regression-locked generalization (T1 test); honest verdict (T6). ✓

## Execution Handoff
Plan B1 of N (Bangkok). After execution: finish branch → evidence-driven fix plans (main-stem HAND / fluvial bias / drainage / coastal — only as the gate calls for them) → then Jakarta. The generalized `validate_hotspots.py --city` + the manifest contract are now the reusable multi-city harness.
