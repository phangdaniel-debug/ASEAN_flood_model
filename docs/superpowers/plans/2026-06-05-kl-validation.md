# KL Validation Harness (Plan 2 of 3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the commercial-grade validation harness for the Kuala Lumpur present-day baseline, with the **documented-hotspot hit-rate as the primary gate** (extent-CSI is non-viable for KL — see below), all metrics carrying bootstrap CIs, assembled into a per-city two-gate validation dossier.

**Architecture:** KL reuses Singapore's pure scoring engine `scripts/hotspot_scoring.py` (sample_hit / skill_scores / bootstrap_tss_ci) unchanged — only a thin adapter maps the four-manifest `hotspots.csv` schema (`name,lon,lat,kind,confidence,source`) to the engine's `Hotspot` dataclass. A combined pluvial∨fluvial wet mask at the event-matched RP is scored against the committed KL register (17 positives + 7 dry controls). Extent-CSI vs the MYS2021 SAR is run but **demoted to a caveated, reference-limited diagnostic** and logged as a limitation. The dossier aggregates gate results + CIs + the visual-gate checklist.

**Tech Stack:** Python 3, numpy, scipy, pandas, rasterio, click, pytest. All open data.

**Why hotspot-primary, not extent-CSI (decisive finding 2026-06-05):** the MYS2021 GFM SAR composite holds only **345 flood pixels (~0.14 km²)** across the whole KL bbox (raw tiles mostly nodata over the urban Klang Valley — SAR is blind to urban flash flooding), and the UNOSAT vector covers Pahang/Johor (wrong region). A CSI against a 0.14 km² reference is meaningless. KL is therefore validated exactly like Singapore (urban flash-flood city): documented-hotspot hit-rate primary + point-depth + IDF-anchor. Logged as limitation #17.

**Prerequisite already done (committed `35ca7fd` on branch `kl-validation`):** the KL hotspot register `data/kuala_lumpur/manifest/hotspots.csv` — 17 geocoded, DEM-verified positives + 7 dry controls (`scripts/build_kl_hotspot_register.py`).

**Inputs present:** baseline rasters `outputs/kuala_lumpur_ssp585_2020/{pluvial,fluvial}/rp_<N>/*_depth_*.tif`; event RP from `observed_events.csv` (MYS2021 est_rp 50–100 → score at **RP100** primary, RP50 secondary).

**Scope note:** Plan 2 of 3. The fluvial event-RP re-anchoring, the pluvial depth-cap wiring fix (run-record finding #2), the limitation-#16 scenario regen, and SSP5-8.5 2100 + viz remain **Plan 3**.

---

### Task 1: Manifest → Hotspot adapter + KL hotspot gates

**Files:**
- Modify: `scripts/city_manifest.py` (add `load_hotspots_from_manifest`)
- Modify: `data/kuala_lumpur/manifest/gates.csv` (add hotspot hit-rate / CRR gates)
- Test: `tests/test_hotspot_adapter.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_hotspot_adapter.py`:
```python
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.city_manifest import load_hotspots_from_manifest


def test_adapter_maps_manifest_to_hotspots(tmp_path):
    mdir = tmp_path / "kuala_lumpur" / "manifest"
    mdir.mkdir(parents=True)
    pd.DataFrame([
        {"name": "Taman Sri Muda", "lon": 101.5345, "lat": 3.0325,
         "kind": "positive", "confidence": "high", "source": "Dec 2021"},
        {"name": "Bukit Gasing", "lon": 101.6594, "lat": 3.0915,
         "kind": "dry", "confidence": "high", "source": "control"},
    ]).to_csv(mdir / "hotspots.csv", index=False)

    hs = load_hotspots_from_manifest("kuala_lumpur", data_root=tmp_path)
    by_cls = {h.cls for h in hs}
    assert by_cls == {"flood", "dry"}                      # kind→cls mapping
    sri_muda = next(h for h in hs if h.label == "Taman Sri Muda")
    assert sri_muda.cls == "flood"
    assert sri_muda.lon == 101.5345 and sri_muda.lat == 3.0325
    # engine fields that the manifest doesn't carry default safely:
    assert sri_muda.documented_depth_m is None
    assert sri_muda.georef_confidence == "high"


def test_adapter_skips_failed_geocode_rows(tmp_path):
    mdir = tmp_path / "kuala_lumpur" / "manifest"
    mdir.mkdir(parents=True)
    pd.DataFrame([
        {"name": "good", "lon": 101.7, "lat": 3.1, "kind": "positive",
         "confidence": "high", "source": "x"},
        {"name": "failed", "lon": "", "lat": "", "kind": "positive",
         "confidence": "failed", "source": "x"},
    ]).to_csv(mdir / "hotspots.csv", index=False)
    hs = load_hotspots_from_manifest("kuala_lumpur", data_root=tmp_path)
    assert [h.label for h in hs] == ["good"]               # blank-coord row dropped
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_hotspot_adapter.py -q`
Expected: FAIL — `ImportError: cannot import name 'load_hotspots_from_manifest'`.

- [ ] **Step 3: Add the adapter to `scripts/city_manifest.py`**

Append to `scripts/city_manifest.py` (after the existing functions):
```python
def load_hotspots_from_manifest(slug: str, data_root: Path = Path("data")):
    """Adapt the four-manifest hotspots.csv to hotspot_scoring.Hotspot objects.

    Maps: name→label, kind(positive→"flood"/dry→"dry"), confidence→georef_confidence.
    The manifest carries no documented depth or anchor RP, so those default to
    None / 0. Rows with a blank lon/lat (geocode failures, confidence=="failed")
    are skipped — they must not enter the hit-rate / CRR.
    """
    import pandas as pd
    from scripts.hotspot_scoring import Hotspot

    path = manifest_dir(slug, data_root) / MANIFEST_FILENAMES["hotspots"]
    df = pd.read_csv(path)
    out = []
    for _, r in df.iterrows():
        if pd.isna(r["lon"]) or pd.isna(r["lat"]) or str(r["lon"]).strip() == "":
            continue
        cls = "flood" if str(r["kind"]).strip() == "positive" else "dry"
        out.append(Hotspot(
            label=str(r["name"]).strip(),
            lon=float(r["lon"]), lat=float(r["lat"]),
            cls=cls, documented_depth_m=None, anchor_rp=0,
            source=str(r["source"]).strip(),
            georef_confidence=str(r["confidence"]).strip(),
        ))
    return out
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_hotspot_adapter.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Add the hotspot gates to the KL gates manifest**

Append these two rows to `data/kuala_lumpur/manifest/gates.csv` (keep the existing rows):
```csv
pluvial,hotspot_hit_rate,0.70,>=,"documented-hotspot hit-rate floor (Singapore methodology precedent; Peirce/Hanssen-Kuipers TSS)"
pluvial,hotspot_crr,0.70,>=,"dry-control correct-reject-rate floor (specificity; Singapore methodology)"
```

- [ ] **Step 6: Verify the manifest still validates + commit**

Run:
```bash
cd /d/GPTs/Projects/flood-v2.0
python -c "import sys;sys.path.insert(0,'.');from scripts.city_manifest import validate_manifest;print(validate_manifest('kuala_lumpur'))"
python -m pytest tests/ -q 2>&1 | tail -3
git add scripts/city_manifest.py tests/test_hotspot_adapter.py data/kuala_lumpur/manifest/gates.csv
git commit -m "feat: manifest->Hotspot adapter + KL hotspot hit-rate/CRR gates

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
Expected: `validate_manifest` returns `[]`; suite green.

---

### Task 2: Combined wet-mask builder

**Context:** MYS2021 was a rainfall/riverine event, so the model field scored against the register is the **per-cell max of the pluvial and fluvial depth rasters** at the event RP. This is a small, testable raster op.

**Files:**
- Create: `scripts/combine_hazard_depth.py`
- Test: `tests/test_combine_hazard_depth.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_combine_hazard_depth.py`:
```python
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.combine_hazard_depth import combine_depth_arrays


def test_elementwise_max_preserves_nan_where_both_nan():
    a = np.array([[0.0, 0.5, np.nan]], dtype=np.float32)
    b = np.array([[0.3, 0.2, np.nan]], dtype=np.float32)
    out = combine_depth_arrays([a, b])
    assert out[0, 0] == 0.3
    assert out[0, 1] == 0.5
    assert np.isnan(out[0, 2])


def test_nan_in_one_layer_takes_the_other():
    a = np.array([[np.nan, 0.4]], dtype=np.float32)
    b = np.array([[0.7, np.nan]], dtype=np.float32)
    out = combine_depth_arrays([a, b])
    assert out[0, 0] == 0.7
    assert out[0, 1] == 0.4
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_combine_hazard_depth.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Create `scripts/combine_hazard_depth.py`:
```python
"""Combine per-hazard depth rasters into a single wet field (per-cell max).

Used by the validation harness: the model field scored against documented
hotspots for a rainfall/riverine event is the max of the pluvial and fluvial
depths at the event RP. NaN (nodata) is treated as "no contribution" unless
ALL layers are NaN at that cell, which stays NaN.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio


def combine_depth_arrays(arrays: list[np.ndarray]) -> np.ndarray:
    """Element-wise max across float arrays; NaN only where every layer is NaN."""
    stack = np.stack([a.astype(np.float64) for a in arrays], axis=0)
    all_nan = np.all(np.isnan(stack), axis=0)
    out = np.nanmax(stack, axis=0)
    out[all_nan] = np.nan
    return out.astype(np.float32)


def combine_depth_rasters(raster_paths: list[Path], out_path: Path) -> Path:
    """Read aligned depth rasters, write their per-cell max to ``out_path``."""
    arrays, profile = [], None
    for p in raster_paths:
        with rasterio.open(p) as ds:
            arrays.append(ds.read(1))
            if profile is None:
                profile = ds.profile
    combined = combine_depth_arrays(arrays)
    profile.update(dtype="float32", count=1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(combined, 1)
    return out_path
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_combine_hazard_depth.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
cd /d/GPTs/Projects/flood-v2.0
git add scripts/combine_hazard_depth.py tests/test_combine_hazard_depth.py
git commit -m "feat: combined pluvial+fluvial wet-mask builder (per-cell max)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: KL hotspot hit-rate validator (the primary gate)

**Context:** Ties Tasks 1–2 and the `hotspot_scoring` engine together: build the combined RP100 wet mask, score the KL register, report HR / CRR / TSS with bootstrap CIs, and gate against the manifest thresholds. This is the centrepiece of KL validation.

**Files:**
- Create: `scripts/validate_hotspots_kl.py`
- Test: `tests/test_validate_hotspots_kl.py`

- [ ] **Step 1: Write the failing test** (tests the pure gate logic, not the raster I/O)

Create `tests/test_validate_hotspots_kl.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.validate_hotspots_kl import evaluate_gate


def test_gate_passes_when_hr_and_crr_meet_floor():
    ok, reasons = evaluate_gate(hit_rate=0.82, crr=0.86,
                                hr_floor=0.70, crr_floor=0.70)
    assert ok and reasons == []


def test_gate_fails_and_reports_each_shortfall():
    ok, reasons = evaluate_gate(hit_rate=0.55, crr=0.40,
                                hr_floor=0.70, crr_floor=0.70)
    assert not ok
    assert any("hit-rate" in r for r in reasons)
    assert any("crr" in r.lower() for r in reasons)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_validate_hotspots_kl.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Create `scripts/validate_hotspots_kl.py`:
```python
"""KL documented-hotspot validation — the primary gate (Plan 2).

Builds the combined pluvial+fluvial wet mask at the event RP, scores the
committed KL hotspot register (17 positives + 7 dry controls) with the
Singapore hotspot_scoring engine, reports hit-rate / CRR / TSS with bootstrap
CIs, and gates against the manifest hotspot thresholds.

Usage
-----
    python scripts/validate_hotspots_kl.py \
        --out-dir outputs/kuala_lumpur_ssp585_2020 --rp 100

Exit codes: 0 = gate PASS; 1 = gate FAIL; 2 = inputs missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.city_manifest import load_hotspots_from_manifest
from scripts.combine_hazard_depth import combine_depth_rasters
from scripts.hotspot_scoring import hit_vectors, skill_scores, bootstrap_tss_ci


def evaluate_gate(hit_rate: float, crr: float,
                  hr_floor: float, crr_floor: float) -> tuple[bool, list[str]]:
    """Pure gate: HR and CRR must each meet their floor. Returns (ok, reasons)."""
    reasons: list[str] = []
    if hit_rate < hr_floor:
        reasons.append(f"hit-rate {hit_rate:.2f} below floor {hr_floor:.2f}")
    if crr < crr_floor:
        reasons.append(f"crr {crr:.2f} below floor {crr_floor:.2f}")
    return (not reasons), reasons


@click.command()
@click.option("--out-dir", type=click.Path(path_type=Path), required=True,
              help="Pipeline output dir, e.g. outputs/kuala_lumpur_ssp585_2020")
@click.option("--rp", type=int, default=100, show_default=True,
              help="Event-matched return period to score (MYS2021 ~ RP50-100).")
@click.option("--scenario", default="SSP5-8.5", show_default=True)
@click.option("--horizon", type=int, default=2020, show_default=True)
@click.option("--depth-threshold", type=float, default=0.10, show_default=True)
@click.option("--radius-m", type=float, default=150.0, show_default=True)
@click.option("--hr-floor", type=float, default=0.70, show_default=True)
@click.option("--crr-floor", type=float, default=0.70, show_default=True)
def cli(out_dir: Path, rp: int, scenario: str, horizon: int,
        depth_threshold: float, radius_m: float, hr_floor: float, crr_floor: float):
    pluvial = out_dir / "pluvial" / f"rp_{rp}" / f"pluvial_depth_{scenario}_{horizon}_rp{rp}.tif"
    fluvial = out_dir / "fluvial" / f"rp_{rp}" / f"fluvial_depth_{scenario}_{horizon}_rp{rp}.tif"
    for p in (pluvial, fluvial):
        if not p.exists():
            click.echo(f"[error] missing raster: {p}", err=True)
            sys.exit(2)

    combined = combine_depth_rasters([pluvial, fluvial], out_dir / "_validation" / f"combined_rp{rp}.tif")
    hotspots = load_hotspots_from_manifest("kuala_lumpur")
    flood_hits, dry_hits = hit_vectors(
        hotspots, combined, radius_m=radius_m, depth_threshold_m=depth_threshold)
    res = skill_scores(flood_hits, dry_hits)
    tss_pt, tss_lo, tss_hi = bootstrap_tss_ci(flood_hits, dry_hits)

    n_pos, n_dry = len(flood_hits), len(dry_hits)
    click.echo(f"KL hotspot validation @ RP{rp} (threshold {depth_threshold} m, radius {radius_m} m)")
    click.echo(f"  positives n={n_pos}  hits={sum(flood_hits)}  hit-rate={res.hit_rate:.2f}")
    click.echo(f"  dry n={n_dry}  correct-rejects={sum(1 for h in dry_hits if not h)}  CRR={res.correct_reject_rate:.2f}")
    click.echo(f"  TSS={tss_pt:.2f}  95% CI [{tss_lo:.2f}, {tss_hi:.2f}]")

    ok, reasons = evaluate_gate(res.hit_rate, res.correct_reject_rate, hr_floor, crr_floor)
    if ok:
        click.echo("GATE PASS")
        sys.exit(0)
    click.echo("GATE FAIL:")
    for r in reasons:
        click.echo(f"  - {r}")
    sys.exit(1)


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /d/GPTs/Projects/flood-v2.0 && python -m pytest tests/test_validate_hotspots_kl.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the validator against the real baseline and capture the result**

Run: `cd /d/GPTs/Projects/flood-v2.0 && python scripts/validate_hotspots_kl.py --out-dir outputs/kuala_lumpur_ssp585_2020 --rp 100`
Capture the verbatim output (HR / CRR / TSS + CI + GATE verdict). **This is a real measurement — record whatever it shows.** A FAIL is a legitimate result to carry into the dossier (Task 5) and Plan 3, NOT something to tune away. Note in particular whether the known pluvial over-extent (RP100 floods ~17% of domain) inflates HR while depressing CRR — if so, that is a finding for the depth-cap fix (run-record finding #2).

- [ ] **Step 6: Commit**

```bash
cd /d/GPTs/Projects/flood-v2.0
git add scripts/validate_hotspots_kl.py tests/test_validate_hotspots_kl.py
git commit -m "feat: KL documented-hotspot validator (HR/CRR/TSS + bootstrap CI, primary gate)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Extent-CSI (demoted) + IDF-anchor coverage — run, capture, log

**Context:** Two existing validators run against KL for completeness; both are *diagnostic*, not the gate. Extent-CSI is reference-limited (SAR sparsity); IDF-anchor confirms the pluvial forcing matches MSMA.

**Files:**
- Create: `docs/superpowers/runs/2026-06-05-kl-validation-diagnostics.md` (captured outputs)
- Modify: `docs/limitations_register.md` (add #17 — SAR extent non-viable for KL)

- [ ] **Step 1: Run extent-CSI vs MYS2021 SAR and capture verbatim**

Run: `cd /d/GPTs/Projects/flood-v2.0 && python scripts/validate_historical_events.py --event MYS2021 --out-dir outputs/kuala_lumpur_ssp585_2020 2>&1 | tee /tmp/kl_csi.txt`
Expected: a low/near-zero CSI (the SAR reference is ~0.14 km²). Capture the table verbatim — do NOT treat the low CSI as a model failure; it is a reference-coverage artefact.

- [ ] **Step 2: Run the IDF-anchor cross-check for KL and capture**

Run: `cd /d/GPTs/Projects/flood-v2.0 && python scripts/validate_pluvial_idf_anchors.py --city kuala_lumpur 2>&1 | tee /tmp/kl_idf.txt`
Expected: the RP2 6h anchor (~90 mm) vs the ERA5-Land GEV (documented to under-shoot ~-50%; the IDF-calibrated Gumbel in the baseline CSV is what the model actually uses). Capture verbatim and interpret: this confirms *why* the IDF-anchored forcing was necessary.

- [ ] **Step 3: Write the diagnostics record**

Create `docs/superpowers/runs/2026-06-05-kl-validation-diagnostics.md` containing: the verbatim extent-CSI output, the verbatim IDF-anchor output, and a 3–4 sentence interpretation of each (extent-CSI = reference-limited, not a model verdict; IDF-anchor = motivates the forcing fix). Paste the actual captured text from Steps 1–2 (no placeholders).

- [ ] **Step 4: Log limitation #17**

Append a row to `docs/limitations_register.md` (after #16):
```markdown
| 17 | **Extent-CSI is non-viable for KL (SAR blind to urban flash flooding).** The MYS2021 GFM SAR composite holds only 345 flood pixels (~0.14 km²) across the KL bbox (raw tiles mostly nodata over the dense urban Klang Valley); the UNOSAT FL20220112MYS vector covers Pahang/Johor, not the Klang Valley. A CSI against a 0.14 km² reference is meaningless, so KL is validated like Singapore (urban flash-flood city): documented-hotspot hit-rate primary + point-depth + IDF-anchor. Extent-CSI is run as a caveated diagnostic only. **Conversion:** hotspot hit-rate is the committed numeric gate (Task 3); this row is the logged limitation. | Known / accepted (SAR limit) | KL SAR sparsity check 2026-06-05 |
```

- [ ] **Step 5: Commit**

```bash
cd /d/GPTs/Projects/flood-v2.0
git add docs/superpowers/runs/2026-06-05-kl-validation-diagnostics.md docs/limitations_register.md
git commit -m "docs: KL validation diagnostics (extent-CSI demoted, IDF-anchor) + limitation #17

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Two-gate KL validation dossier

**Context:** Assemble the commercial-grade dossier: the numeric gate table (with CIs), the visual-gate checklist result (reuse `check_rp_monotonicity` from Plan 1), the register provenance, and the honest limitations. This is the sellable artifact.

**Files:**
- Create: `docs/superpowers/runs/2026-06-05-kl-validation-dossier.md`

- [ ] **Step 1: Assemble the dossier**

Create `docs/superpowers/runs/2026-06-05-kl-validation-dossier.md` with these sections, filled from the ACTUAL captured results of Tasks 3–4 (no placeholders — paste real numbers):
1. **Scope & method** — KL present-day baseline; hotspot-primary validation (cite the SAR-sparsity reason, limitation #17); register = 17 positives + 7 dry controls, geocoded + DEM-verified (limitation #6b).
2. **Numeric gate table** — per gate (hotspot HR, hotspot CRR, TSS±CI, IDF-anchor): threshold, observed value, PASS/FAIL, citation (pull thresholds + citations from `data/kuala_lumpur/manifest/gates.csv`).
3. **Two-gate verdict** — numeric gate (Task 3 result) AND visual gate (`check_rp_monotonicity` PASS from the Plan-1 baseline). State the combined verdict.
4. **Diagnostics (not gating)** — extent-CSI result + why it's reference-limited; IDF-anchor result.
5. **Known limitations carried** — #16 (scenario forcing), #17 (SAR extent), pluvial depth-cap (run-record finding #2), coastal=0 (inland). Each with its Plan-3 disposition.

- [ ] **Step 2: Commit**

```bash
cd /d/GPTs/Projects/flood-v2.0
git add docs/superpowers/runs/2026-06-05-kl-validation-dossier.md
git commit -m "docs: KL two-gate validation dossier (Plan 2 deliverable)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (against `2026-06-04-asean-flood-v2-design.md` §6 + the recalibration):**
- §6.1 hotspot hit-rate + dry-control CRR → Tasks 1–3 (adapter, wet-mask, validator). ✓
- §6 bootstrap CIs → Task 3 (`bootstrap_tss_ci`). ✓
- §6.1 point-depth → folded into Task 4/dossier where documented depths exist (Taman Sri Muda); KL metric-depth ground truth is sparse (limitation #14 analogue) — noted, not over-promised. ✓
- §6.1 extent-CSI → Task 4, **demoted** per the SAR-sparsity finding (limitation #17). ✓ (recalibration, not a gap)
- §6.2 Aqueduct cross-overlay → deferred (supplementary, not gating) — acceptable for Plan 2.
- §6.3 two-gate "done" → Task 5 dossier (numeric Task 3 AND visual `check_rp_monotonicity`). ✓
- IDF-anchor coverage → Task 4. ✓

**2. Placeholder scan:** Code steps show complete code; run steps show exact commands. Tasks 4–5 dossier/diagnostics steps explicitly require pasting ACTUAL captured outputs (the one place "fill from real results" is correct, since the numbers don't exist until the validator runs). No "TBD/TODO".

**3. Type/contract consistency:** `load_hotspots_from_manifest` returns `hotspot_scoring.Hotspot` (cls "flood"/"dry") consumed by `hit_vectors`/`skill_scores` (which filter on `cls=="flood"`/`"dry"`) — consistent. `combine_depth_rasters(paths, out)` signature matches the Task-3 call. `evaluate_gate(hit_rate, crr, hr_floor, crr_floor)` matches its test. Raster path template matches the Plan-1 pipeline output convention (`{hazard}_depth_{scenario}_{horizon}_rp{rp}.tif`, verified against the real `outputs/kuala_lumpur_ssp585_2020/`).

---

## Execution Handoff

Plan 2 of 3. After execution: final branch review → finish branch → Plan 3 (fluvial event-RP re-anchoring, pluvial depth-cap fix, limitation-#16 scenario regen, SSP5-8.5 2100, viz).
