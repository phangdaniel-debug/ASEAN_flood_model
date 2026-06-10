# Major-River-Referenced HAND (Plan 8 of N)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the single-stage HAND **over-broadening** exposed in Plan 7 — the corrected fluvial floods **Bukit Persekutuan / Federal Hill** (a 60–77 m hill) by 4 m because the OSM-river-referenced HAND assigns its cells to a **hillside tributary (~60 m DEM)** that does not carry the Klang main-stem discharge. Re-reference HAND to **flow-accumulation channels above a channel-initiation contributing-area threshold (1.8 km²)** so minor rivulets are excluded; re-run the corrected fluvial and re-validate. Expected: Federal Hill returns to dry (**CRR 0.71→~0.86**) while **Old Klang Road and all true positives stay flooded** (**HR ~0.76**, TSS up) → a clean, real PASS.

**Architecture:** HAND = height above *nearest drainage*. The defect is in the *drainage definition*: `data/kuala_lumpur/hand_utm47n.tif` references the OSM river mask, which includes sub-catchment hillside streams. We rebuild HAND from a drainage mask derived by **flow accumulation** (`model.hand_model.derive_drainage_mask_from_accumulation` + `compute_hand`, both already in the codebase and used by `scripts/build_hand_raster.py`) at a threshold that retains channels carrying significant flow. The fluvial pipeline is unchanged — only the `--fluvial-hand-raster` input swaps. Pluvial is untouched.

**Discipline guards (hard-won):**
- The accumulation threshold is anchored to **channel-initiation hydrology** (~1–2 km² contributing area; Montgomery & Dietrich range for humid terrain), **NOT** to the gate. The viability test (`docs/superpowers/runs/2026-06-06-major-river-hand-viability.md`) shows the gate-positives are a **consistency check** (all must be preserved) — coarser thresholds that over-prune and drop a real positive (Segambut at ≥9 km²) are rejected on *physical* grounds (they delete a channel a documented flood sat on), not because the gate dips.
- Verify the fix is **real, not cosmetic**: Federal Hill must go dry **because its HAND rose** (it routes to the far main stem), AND every documented positive must stay flooded. If a positive is lost, the threshold is too coarse → report, do not lower it just to keep the positive while also keeping Federal Hill (that would be gate-fitting).
- Do **not** edit the hotspot register to exclude Federal Hill — CRR must recover by the model getting the physics right, never by reclassifying an inconvenient control.

**Fast iteration:** fluvial is HAND inundation (minutes), not the slow raingrid. The only slow-ish step is the one-off pysheds accumulation+HAND build (~2–3 min). Offline (no AR6). Reuse the Plan-7 offline command with `--only-hazard-types fluvial`.

**Tech Stack:** Python 3, numpy, rasterio, pysheds 0.5, scipy, click, pytest. Key files: `model/hand_model.py` (`compute_hand`, `derive_drainage_mask_from_accumulation`), `scripts/build_hand_raster.py` (`--acc-threshold` path), `scripts/run_multihazard.py` (`--fluvial-hand-raster`, `--fluvial-bankfull-rp 0`), `scripts/validate_hotspots_kl.py`.

**Inputs already on disk:** `data/kuala_lumpur/copernicus_dem_utm47n.tif` (DEM), `data/kuala_lumpur/hazard_levels_ssp585_2020_fluvbias.csv` (corrected factor-2.06 fluvial stages, committed in Plan 7), `data/kuala_lumpur/sea_mask_utm47n.tif`, `data/kuala_lumpur/drainage_waterways_utm47n.tif` (channel-mask for fluvial). The corrected pluvial rasters in `outputs/kuala_lumpur_ssp585_2020/pluvial/` are unchanged and reused by the validator.

---

### Task 1: Record the channel-initiation threshold anchor (analytical)

**Files:** Create `docs/superpowers/runs/2026-06-06-major-river-hand-anchor.md`

- [ ] **Step 1:** Record the threshold and its anchor. State: (a) the defect (OSM-river HAND references a ~60 m hillside tributary near Federal Hill → spurious 4 m flood from the main-stem stage); (b) the chosen `acc_threshold = 2000 px @ 30 m = 1.8 km²` contributing area, anchored to the channel-initiation contributing-area range for humid/tropical terrain (~1–2 km²; cite Montgomery & Dietrich 1988 *Nature* / 1992, the standard source-area channel-head relation), explicitly **not** the gate; (c) the sensitivity from the viability run (2000 fixes Federal Hill AND keeps all positives; ≥10000 over-prunes and drops Segambut Dalam — physically wrong because Segambut sits on a real, flow-bearing tributary). Reference `docs/superpowers/runs/2026-06-06-major-river-hand-viability.md` for the per-spot numbers. Commit.

```bash
cd /d/GPTs/Projects/flood-v2.0
git add docs/superpowers/runs/2026-06-06-major-river-hand-anchor.md docs/superpowers/runs/2026-06-06-major-river-hand-viability.md
git commit -m "docs: channel-initiation HAND threshold anchor (1.8 km2) + viability evidence (Plan 8)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Build the major-river HAND raster (with a key-spot regression test)

**Files:**
- Create: `data/kuala_lumpur/hand_major_utm47n.tif` (via the existing `scripts/build_hand_raster.py --acc-threshold`)
- Create: `tests/test_kl_major_river_hand.py`

- [ ] **Step 1: Build the raster.** Run the existing builder's accumulation path (no code change needed):

```bash
cd /d/GPTs/Projects/flood-v2.0
python scripts/build_hand_raster.py \
  --dem data/kuala_lumpur/copernicus_dem_utm47n.tif \
  --acc-threshold 2000 \
  --output data/kuala_lumpur/hand_major_utm47n.tif
```
Expected: prints "Derived drainage mask: ~55,547 cells", writes the raster, shape (1924, 2045), CRS EPSG:32647 (aligned to the DEM — `build_hand_raster.py` preserves the DEM profile).

- [ ] **Step 2: Write the regression test** (locks the physics invariant — the fix must come from HAND geometry, model-blind to the gate). Create `tests/test_kl_major_river_hand.py`:

```python
import math
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.warp import transform as rio_transform

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAND = Path("data/kuala_lumpur/hand_major_utm47n.tif")
OVERBANK_RP100 = 6.06  # corrected factor-2.06 RP100 overbank stage (m)

# (label, lon, lat, expect_floods_at_overbank)
SPOTS = [
    ("Federal Hill (dry control)", 101.67906, 3.13859, False),  # hill — must NOT flood
    ("Old Klang Road (+)",         101.65920, 3.08261, True),   # documented target — must flood
    ("Masjid Jamek (+)",           101.69518, 3.14894, True),
    ("Kampung Baru (+)",           101.70300, 3.16300, True),
]


def _hand_min(ds, hand, lon, lat, radius_m=50.0):
    xs, ys = rio_transform("EPSG:4326", ds.crs, [lon], [lat])
    col_f, row_f = ~ds.transform * (xs[0], ys[0])
    row, col = int(math.floor(row_f)), int(math.floor(col_f))
    rr = int(math.ceil(radius_m / abs(ds.transform.e)))
    rc = int(math.ceil(radius_m / abs(ds.transform.a)))
    r0, r1 = max(0, row - rr), min(ds.height, row + rr + 1)
    c0, c1 = max(0, col - rc), min(ds.width, col + rc + 1)
    block = hand[r0:r1, c0:c1]
    finite = np.isfinite(block)
    return float(np.nanmin(block)) if finite.any() else float("nan")


@pytest.mark.skipif(not HAND.exists(), reason="major-river HAND not built yet")
@pytest.mark.parametrize("label,lon,lat,floods", SPOTS)
def test_major_river_hand_floodplain_separation(label, lon, lat, floods):
    with rasterio.open(HAND) as ds:
        hand = ds.read(1).astype("float64")
        nod = ds.nodata
        if nod is not None:
            hand = np.where(hand == nod, np.nan, hand)
        hmin = _hand_min(ds, hand, lon, lat)
    assert np.isfinite(hmin), f"{label}: no finite HAND in window"
    if floods:
        assert hmin < OVERBANK_RP100, f"{label}: HAND_min {hmin:.2f} should flood at {OVERBANK_RP100} m"
    else:
        # Federal Hill must be well clear of the overbank stage (real separation, not borderline).
        assert hmin > OVERBANK_RP100 + 5.0, f"{label}: HAND_min {hmin:.2f} too low — hill still floods"
```

- [ ] **Step 3: Run the test to verify it passes** (the raster from Step 1 makes it green):

Run: `cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_kl_major_river_hand.py -q`
Expected: 4 passed. Federal Hill HAND ≈ 22.9 m (> 11.06), the three positives < 6.06 m. If Federal Hill fails (HAND still low), STOP — the threshold did not exclude its tributary; report rather than lowering the flood bar.

- [ ] **Step 4: Commit:**

```bash
cd /d/GPTs/Projects/flood-v2.0
git add data/kuala_lumpur/hand_major_utm47n.tif tests/test_kl_major_river_hand.py
git commit -m "feat: major-river-referenced KL HAND (accumulation 1.8 km2) + floodplain-separation test (Plan 8)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Re-run the corrected fluvial with the major-river HAND (fast, offline)

**Files:** produces (gitignored) `outputs/kl_fluvbias_majorhand/fluvial/`

- [ ] **Step 1:** Run offline `run_multihazard` with the corrected CSV, the **new** HAND, and `--fluvial-bankfull-rp 0` (the CSV already encodes overbank above the documented Q_bf=98 — no further subtraction). Fluvial-only via `--only-hazard-types fluvial` (full 3-hazard CSV satisfies the completeness guard; only fluvial is computed → no raingrid):

```bash
cd /d/GPTs/Projects/flood-v2.0
python scripts/run_multihazard.py \
  --dem data/kuala_lumpur/copernicus_dem_utm47n.tif \
  --hazard-levels data/kuala_lumpur/hazard_levels_ssp585_2020_fluvbias.csv \
  --scenario SSP5-8.5 --horizon 2020 \
  --out-dir outputs/kl_fluvbias_majorhand \
  --sea-mask-raster data/kuala_lumpur/sea_mask_utm47n.tif \
  --fluvial-hand-raster data/kuala_lumpur/hand_major_utm47n.tif \
  --tidal-channel-raster data/kuala_lumpur/drainage_waterways_utm47n.tif \
  --fluvial-bankfull-rp 0 \
  --only-hazard-types fluvial
```
Expected: writes fluvial rp_2…rp_1000; RP100 `max_depth_m` = 6.0594 m (= overbank stage; monotone in RP). Confirm via:
```bash
python -c "import pandas as pd; d=pd.read_csv('outputs/kl_fluvbias_majorhand/summary_SSP5-8.5_2020.csv'); print(d[['return_period','water_level_m','flooded_area_km2','max_depth_m']].to_string(index=False))"
```
Monotonicity: `flooded_area_km2` and `max_depth_m` strictly increase with RP.

- [ ] **Step 2:** Swap the major-river fluvial into the validation output dir (the corrected pluvial there is unchanged and reused). Back up the Plan-7 (old-HAND) fluvial first:

```bash
cd /d/GPTs/Projects/flood-v2.0
rm -rf outputs/_ref_fluv_oldhand && mkdir -p outputs/_ref_fluv_oldhand
cp -r outputs/kuala_lumpur_ssp585_2020/fluvial outputs/_ref_fluv_oldhand/fluvial
rm -rf outputs/kuala_lumpur_ssp585_2020/fluvial
cp -r outputs/kl_fluvbias_majorhand/fluvial outputs/kuala_lumpur_ssp585_2020/fluvial
ls outputs/kuala_lumpur_ssp585_2020/fluvial/rp_100/
```

---

### Task 4: Re-validate — Federal Hill dry, Old Klang Road + all positives flooded

- [ ] **Step 1:** Run the gate (validator recombines the unchanged pluvial with the new fluvial):

```bash
cd /d/GPTs/Projects/flood-v2.0
python scripts/validate_hotspots_kl.py --out-dir outputs/kuala_lumpur_ssp585_2020 --rp 100
```
Expected: **HR ≈ 0.76, CRR ≈ 0.86, TSS up (~0.60), CI excludes 0, GATE PASS.**

- [ ] **Step 2 (decisive per-spot):** Reuse the Plan-7 diagnostic, repointed at the new fluvial, to confirm the mechanism:

```bash
cd /d/GPTs/Projects/flood-v2.0
python scripts/_diag_fluvbias_perspot.py
```
(If `scripts/_diag_fluvbias_perspot.py` references the old corrected dir, edit its `FL_AFTER` to `outputs/kl_fluvbias_majorhand/fluvial/...` first.) Confirm, explicitly: **Federal Hill flAFT = 0.00 (dry, FP removed)**; **Old Klang Road flAFT ≈ 0.60 (WET)**; Masjid Jamek / Jln Tun Razak / Kampung Baru / Segambut / Bulatan Datuk Onn / Jln Rahmat all WET; Taman Sri Muda still 0.00 (out-of-domain, expected). Report the full table.

- [ ] **Step 3:** Honest verdict. Did the major-river HAND give a clean PASS — Federal Hill dry **because HAND rose** (not because anything was reclassified), all positives preserved, HR ≥ 0.70 AND CRR ≥ 0.70 with TSS CI excluding 0? If any positive was lost, report it (the threshold is too coarse — do not re-tune to the gate). If Federal Hill is still wet, report it (the tributary survived the threshold). State the before/after (old-HAND vs major-HAND) HR/CRR/TSS explicitly.

---

### Task 5: Document — dossier §10 + limitation updates + memory

**Files:** `docs/superpowers/runs/2026-06-05-kl-validation-dossier.md`, `docs/limitations_register.md`, memory.

- [ ] **Step 1:** Dossier §10: the full Plan 7→8 arc — (a) the fluvial-bankfull double-subtraction bug (`--fluvial-bankfull-rp 10` vs CSV already removing Q_bf=98 → `rp0` fix); (b) the documented 2.06× discharge bias restoring Old Klang Road; (c) the single-stage HAND over-broadening at Federal Hill and the major-river (1.8 km²) HAND fix; (d) the before/after gate table (old committed 0.65/0.86 → corrected-old-HAND 0.76/0.71 → **major-HAND 0.76/0.86**); (e) Old Klang Road and Federal Hill per-spot depths at each stage. Verdict: if clean PASS, state **KL present-day is validated (HR & CRR ≥ floor, significant TSS)**.

- [ ] **Step 2:** Limitations register:
  - **#19** (Old Klang Road over-drain): mark **resolved** via the fluvial path (documented bias + major-river HAND), with the pluvial design-capacity ceiling noted as the separate structural limit it is.
  - **New limitation (single-stage HAND scope):** HAND fluvial applies one basin-wide overbank stage; it must be referenced to flow-accumulation channels (≥1.8 km² for KL) or it over-broadens onto minor-stream-adjacent elevated terrain. This is the **transferable** rule for Bangkok/Jakarta (build their HAND from accumulation channels, not raw OSM rivers).
  - **New/extend (fluvial-bankfull config):** the hazard-levels CSV already encodes overbank above documented Q_bf; `run_multihazard --fluvial-bankfull-rp` must be **0** for these CSVs (non-zero double-subtracts). Note the default (10) is wrong for v2.0 KL CSVs.
  - **Taman Sri Muda out-of-domain:** the Dec-2021 epicentre is 7.6 km from the nearest modeled HAND floodplain cell → a channel-network-coverage / retention-pond-failure miss, not a discharge problem. Permanent HR ceiling of ~1 positive at documented forcing.

- [ ] **Step 3:** Commit, then update memory (`v2-spec-and-plans.md`) with the Plan 7+8 outcome and the new transferable HAND rule:

```bash
cd /d/GPTs/Projects/flood-v2.0
git add docs/superpowers/runs/2026-06-05-kl-validation-dossier.md docs/limitations_register.md
git commit -m "docs: dossier 10 + limitations — KL fluvial validated (bias + major-river HAND); single-stage HAND scope rule (Plan 8)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:** anchor the threshold (T1) → build major-river HAND + regression test (T2, the physics invariant) → fast offline re-run (T3) → decisive re-validation incl. Federal Hill + all positives (T4) → document + transferable rule + memory (T5). ✓ The mitigation chosen in the Plan-7 disposition ("mitigate HAND artifact first") is fully realised.

**Placeholder scan:** all commands are concrete with real paths + expected numbers from the viability run (Federal Hill 22.9 m; positives < 6.06 m; threshold 2000 px = 1.8 km²); the test asserts the physics invariant, not a hand-picked pass. No TODOs. ✓

**Discipline:** threshold anchored to channel-initiation hydrology, gate-positives as consistency check not selection criterion (Plan 3 lesson); fix verified real via HAND-rose mechanism + all-positives-preserved guard (Plan 4/5 lesson); register NOT edited to drop Federal Hill (no reclassification); offline re-run (AR6 flakiness). ✓

## Execution Handoff

Plan 8 of N. Fast iteration (no raingrid; one ~3-min pysheds build). After execution: final review → finish the `fluvial-reanchor` branch (this completes the Plan 7 arc) → remaining KL work (dry-control register n≥15; #16 scenario regen; SSP5-8.5 2100 + viz; AR6 offline-repeatability) → transfer the KL template (incl. the accumulation-HAND rule) to Bangkok + Jakarta.
