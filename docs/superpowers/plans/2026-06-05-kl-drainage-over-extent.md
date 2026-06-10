# KL Pluvial Over-Extent Fix — Denser Drainage (Plan 5 of N)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the diagnosed root cause of the KL pluvial broad-shallow over-extent — a too-sparse drainage outlet network — by adding realistic drainage, so the model stops ponding water in local lows kilometres from any outlet. If specificity (CRR) improves, it must do so because the model is **more correct**, validated honestly.

**The diagnosis (established 2026-06-05, decisive):** the raingrid pluvial drains only at major OSM rivers + sea = **1.1% of the domain**; the **median RP100 wet cell is 4.7 km from any outlet** (95% >300 m, 85% >1 km), and 44% of wet cells are DEM local minima. KL's dense urban monsoon-drain/culvert network — which actually conveys stormwater to rivers — is unrepresented, so water ponds broadly. This is the broad-shallow extent and the dry-control false-positives (Bukit Antarabangsa's base). NOT depth (the cap was irrelevant), NOT a numerical artifact.

**Approach (user decision):** **OSM-first, DEM-derived fallback.** Try densifying from OSM drainage (drains/ditches/canals + roads as storm-drain proxies); if the network is still too sparse (extent still broad), add a DEM-derived flow-accumulation channel network to fill the gaps.

**Discipline guards (non-negotiable, learned from Plan 4):**
- The drainage density is **calibrated to a documented fact** (KL/MSMA urban drainage density, or the published Dec-2021 event character) — **NEVER** to whatever makes the gate pass. Tuning drainage until CRR clears the floor is the forbidden loop.
- Any extent reduction must be **physically sensible** (real drainage routing water to rivers), not the model under-computing. Verify the new field still floods the *documented* hotspots (HR must hold) — a fix that drops both false-positives AND true positives is over-draining, and is rejected.

**Re-run mechanics (from Plan 4):** the full `run_city_pipeline` re-fetches the AR6 zarr (flaky network, breaks re-runs). Use the **direct offline `run_multihazard`** invocation (validated in Plan 4) for all re-runs in this plan — it uses the committed `hazard_levels_ssp585_2020.csv` + cached rasters. OSM fetch (Task 1) does need network (Overpass).

**Tech Stack:** Python 3, osmnx, numpy, scipy, pysheds, rasterio, click, pytest. All open data.

**Key existing files to extend:** `scripts/build_river_raster_from_osm.py` (OSM `waterway:True` fetch + culvert filter), `scripts/build_conditioned_dem.py` (burns the drainage network into the raingrid DEM), `scripts/build_hand_raster.py` (D8 flow accumulation via pysheds — the source for DEM-derived drainage).

---

### Task 1: Fetch + quantify OSM drainage density for KL (does OSM suffice?)

**Files:**
- Create: `scripts/_diagnose_drainage_density.py` (reusable measurement)
- Produces (gitignored): a candidate denser drainage raster + a density report

- [ ] **Step 1: Measure the CURRENT drainage density (baseline)** — write `scripts/_diagnose_drainage_density.py` that, given an outlet/drainage raster + the DEM, reports: outlet-cell count, % of land, and the distance-to-nearest-outlet distribution (median/p90) over land and over a given wet raster. Run it on the current network to reproduce the baseline:
```bash
cd /d/GPTs/Projects/flood-v2.0
python scripts/_diagnose_drainage_density.py \
  --drainage data/kuala_lumpur/river_mask_utm47n.tif --drainage-value 1 \
  --sea data/kuala_lumpur/sea_mask_utm47n.tif --sea-is-zero \
  --dem data/kuala_lumpur/copernicus_dem_utm47n_raingrid.tif \
  --wet outputs/kuala_lumpur_ssp585_2020/pluvial/rp_100/pluvial_depth_SSP5-8.5_2020_rp100.tif
```
Expected (reproduces the diagnosis): outlets ≈ 42,873 (1.1%); median wet-cell distance ≈ 4710 m.

- [ ] **Step 2: Fetch the full OSM drainage for the KL bbox** — extend `build_river_raster_from_osm.py` (or a thin wrapper) to fetch ALL `waterway` features (`drain`, `ditch`, `canal`, `stream`, `river`) AND, as storm-drain proxies, the OSM road network (`highway` lines) for the KL bbox (min_lon=101.40, min_lat=2.90, max_lon=101.95, max_lat=3.42), rasterised to the raingrid DEM grid. Produce `data/kuala_lumpur/drainage_osm_dense_utm47n.tif`. (Network-dependent; if Overpass is unreachable, retry/backoff and report.)

- [ ] **Step 3: Measure the OSM-dense drainage density + DECIDE**

Run `_diagnose_drainage_density.py` on the OSM-dense raster. **Decision gate:**
- If the median wet-cell distance-to-outlet drops to **≤ ~300 m** (the hotspot hit-radius scale) and the network looks like a real urban drainage mesh → OSM suffices; skip the DEM-derived fallback (Task 2 Step 3).
- If it's still **> ~500 m** (OSM urban-drain coverage is sparse, as suspected) → proceed to the DEM-derived fallback.

Record the measured density + the decision (do NOT decide by what helps the gate — decide by drainage density vs the documented target in Task 4).

- [ ] **Step 4: Commit the measurement tool + the density report**
```bash
cd /d/GPTs/Projects/flood-v2.0
git add scripts/_diagnose_drainage_density.py
git commit -m "feat: drainage-density diagnostic (distance-to-outlet); KL OSM-dense fetch + measurement

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Build the densified drainage network (OSM + DEM-derived fallback)

**Files:**
- Modify/extend: `scripts/build_conditioned_dem.py` (accept a richer drainage raster to burn)
- Create: `scripts/build_drainage_network.py` (combine OSM + DEM-derived channels at a tunable density)
- Produces (gitignored): `data/kuala_lumpur/drainage_combined_utm47n.tif`, a rebuilt `copernicus_dem_utm47n_raingrid.tif`

- [ ] **Step 1: DEM-derived channel network (the fallback)** — write `scripts/build_drainage_network.py` that computes D8 flow accumulation on the conditioned DEM (reuse the pysheds path in `build_hand_raster.py`; note the `np.in1d→np.isin` shim, limitation #7) and thresholds it at a configurable **accumulation threshold** (drainage density knob) to define channels. Combine (union) with the OSM-dense raster from Task 1. Output `data/kuala_lumpur/drainage_combined_utm47n.tif`. The threshold is a CLI param `--accum-threshold` (calibrated in Task 4; start with a value giving ~2–4 km/km² density, a typical urban range).

- [ ] **Step 2: Rebuild the raingrid conditioned DEM with the combined drainage burned** — run `build_conditioned_dem.py` (extending it if needed to accept `--drainage-raster <combined>`) so the densified channels are burned into the raingrid DEM, giving water a routed path to rivers. Output overwrites `copernicus_dem_utm47n_raingrid.tif` (back up the old one first to `*_predrainage.tif`).

- [ ] **Step 3: Re-measure density** — run `_diagnose_drainage_density.py` on the combined network; confirm the median land/wet distance-to-outlet is now in the target range (Task 4). Record.

- [ ] **Step 4: Commit the builders** (rasters are gitignored)
```bash
cd /d/GPTs/Projects/flood-v2.0
git add scripts/build_drainage_network.py scripts/build_conditioned_dem.py
git commit -m "feat: densified drainage network (OSM + DEM-derived flow-accumulation channels)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Re-run the pluvial with denser drainage; measure the extent reduction

**Files:** produces (gitignored) regenerated `outputs/kuala_lumpur_ssp585_2020/pluvial/`

- [ ] **Step 1: Back up the current (sparse-drainage) pluvial rasters** to `outputs/_ref_sparse_pluvial/` for before/after comparison.

- [ ] **Step 2: Re-run pluvial offline via direct `run_multihazard`** (the Plan-4 offline command — `--dem`, `--hazard-levels data/kuala_lumpur/hazard_levels_ssp585_2020.csv`, `--pluvial-model raingrid`, `--pluvial-dem-raster <rebuilt raingrid DEM>`, `--pluvial-depth-cap 3.0`, the densified `--tidal-channel-raster`/outlets, cached HAND/sea/runoff). Long compute (raingrid; ~hours — run in background). NOTE: do NOT use any early-stop (limitation #18 — rejected).

- [ ] **Step 3: Measure the extent reduction** — compare new vs `_ref_sparse_pluvial`: flooded-area km² per RP, and the median wet-cell distance-to-outlet (should fall sharply). Expected: substantial extent reduction concentrated in the far-from-outlet local lows. Confirm depths still capped ≤ 3.0 m and monotonicity holds.

---

### Task 4: Calibrate the drainage density to a documented fact (NOT the gate)

**Files:**
- Modify (tracked): `data/kuala_lumpur/manifest/forcing_anchors.csv` or a new `drainage` manifest note documenting the calibration anchor

- [ ] **Step 1: Establish the documented calibration anchor** — source a defensible target for KL drainage density: the DID/MSMA urban drainage design density for the Klang Valley, OR a hydrological norm for dense-urban catchments (drainage density ~2–5 km/km²), OR the documented Dec-2021 inundation character. Record the chosen anchor + citation. **This is the target — not "whatever passes the gate."**

- [ ] **Step 2: Sweep the accumulation threshold** (Task 2 `--accum-threshold`) across ~3 values bracketing the anchor density; for each, measure drainage density + the resulting pluvial extent. Pick the threshold whose **density matches the documented anchor**. Record the sweep table + the chosen value + WHY (the density match), explicitly stating the gate result is NOT the selection criterion.

- [ ] **Step 3: Commit the calibration record**
```bash
cd /d/GPTs/Projects/flood-v2.0
git add data/kuala_lumpur/manifest/
git commit -m "feat: KL drainage-density calibration anchored to documented urban drainage density

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Re-validate the hotspot gate — honestly

**Files:** produces captured validation numbers

- [ ] **Step 1: Run the hotspot validator** at the operating point (RP100, 50 m) on the densified-drainage pluvial:
```bash
cd /d/GPTs/Projects/flood-v2.0
python scripts/validate_hotspots_kl.py --out-dir outputs/kuala_lumpur_ssp585_2020 --rp 100
```
Capture HR / CRR / TSS+CI / GATE verbatim.

- [ ] **Step 2: The over-draining check (the discipline guard)** — confirm **HR did NOT collapse** (the documented hotspots — Taman Sri Muda, Masjid Jamek, etc. — must still flood). If HR fell materially alongside CRR rising, the drainage is over-draining (washing out real floods) → the density is too high → return to Task 4 and re-anchor (do NOT accept it). A legitimate fix raises CRR (fewer dry-control false-positives) while HR holds.

- [ ] **Step 3: Compare per-control** — re-check the four prior false-positive dry controls (Bukit Antarabangsa, Mont Kiara, Bukit Kiara, Damansara Heights): with realistic drainage, their bases should now drain → correctly dry. Record which resolved.

---

### Task 6: Document — dossier §8 + limitation update

**Files:**
- Modify (tracked): `docs/superpowers/runs/2026-06-05-kl-validation-dossier.md` (add §8: drainage fix + re-validation)
- Modify (tracked): `docs/limitations_register.md` (update the over-extent finding's status)

- [ ] **Step 1: Append dossier §8** with: the diagnosis recap (4.7 km median distance-to-outlet), the drainage densification (OSM + DEM-derived, calibrated to the documented anchor), the before/after extent + distance-to-outlet, and the honest re-validation (HR/CRR/TSS before vs after). State the verdict plainly: did realistic drainage move KL from boundary toward robust, and is the improvement real (HR held)? If it didn't fully resolve, say so and scope the residual.

- [ ] **Step 2: Commit**
```bash
cd /d/GPTs/Projects/flood-v2.0
git add docs/superpowers/runs/2026-06-05-kl-validation-dossier.md docs/limitations_register.md
git commit -m "docs: KL drainage-densification fix + honest re-validation (dossier 8)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage:** the over-extent fix = diagnose-confirmed (done) → densify drainage (Tasks 1–2, OSM-first + DEM fallback per the user choice) → re-run + measure (Task 3) → calibrate to a fact (Task 4) → honest re-validation with an over-draining guard (Task 5) → document (Task 6). ✓

**2. Placeholder scan:** measurement/command steps are concrete; the genuinely-investigative parts (OSM sufficiency decision, density calibration) are framed as documented-fact-anchored DECISIONS with explicit criteria, not "TBD". The calibration anchor must be sourced in Task 4 Step 1 (a real number + citation), not invented.

**3. Discipline consistency:** every guard from the project's hard-won lessons is encoded — calibrate to a fact not the gate (Plan 3 lesson), verify the fix is real not under-computing (Plan 4 lesson: HR-must-hold over-draining check), use offline re-runs (Plan 4 AR6 flakiness), no early-stop (limitation #18).

---

## Execution Handoff

Plan 5 of N. After execution: final review → finish branch → remaining substantive work (grow dry-control register to n≥15; #16 scenario regen; fluvial event-RP re-anchoring; SSP5-8.5 2100 + viz; and the AR6-offline-repeatability robustness fix).
