# KL Dry-Control Register Growth — Design Spec

**Date:** 2026-06-06
**Status:** approved (design)
**Goal:** Grow the KL hotspot register's **dry-control** set from **7 (all elevated)**
to **≥15** by adding ~8 **research-grounded low-lying hard negatives**, so the
specificity metrics (CRR, TSS) measure real discrimination rather than the trivial
"all negatives are hills" case, and so the now-significant TSS CI [0.25, 0.88]
tightens with a larger, harder negative set.

---

## 1. Problem

The KL hotspot gate scores HR (documented-flood positives flooded) and CRR
(documented-dry controls kept dry); TSS = HR + CRR − 1. After Plans 7–8 the
present-day combined field scores **HR 0.76 / CRR 0.86 / TSS 0.62 [0.25, 0.88]**
on **17 positives + 7 dry controls**.

**All 7 dry controls are elevated hills** (Bukit Tunku, Damansara Heights, Bukit
Antarabangsa, Bukit Gasing, Mont Kiara, Federal Hill, Bukit Kiara; DEM 60–156 m).
A model that floods nothing above ~6 m HAND trivially rejects all of them, so CRR
is **inflated by an easy negative set** — the Singapore #15 "negative-set
confound." The validation is not commercial-grade until specificity is tested
against **hard negatives**: low-lying KL areas that a naïve over-flooding model
*would* wet but that did not actually flood.

## 2. Approach (chosen: research-grounded hard negatives)

Add ~8 dry controls, **mostly low-lying**, sourced **model-blind** from flood
records, reaching **n_dry ≈ 15** (mix: the 7 existing elevated + ~8 new, of which
the majority are low-lying valley-floor sites).

### 2.1 Selection rule (model-blind — the cardinal discipline)

A candidate locality is admitted as a **dry control** iff ALL hold:
1. **Low-lying** (valley-floor; DEM/HAND comparable to the flooded positives, not a
   hill) — this is what makes it a *hard* negative. (Verification, not the label.)
2. **Absent from every documented flood source** used for positives (DBKL/DID/Scoop
   flood-hotspot lists; the comprehensive Klang Valley flood-prone lists).
3. **Not reported flooded in the Dec-2021 event** (cross-checked against Dec-2021
   Klang Valley flood reports / district lists).

The "dry" label is set by **flood-record absence (criteria 2–3)** — **never** by
the model's wet-mask or by terrain. Terrain (criterion 1) only ensures the negative
is *hard* and catches mis-geocodes.

### 2.2 Sources (model-blind)

- **DID Malaysia / DBKL flood-prone area lists** and **InfoBanjir**-type official
  records → the set of areas officially flagged flood-prone (candidates must be
  ABSENT from this).
- **Dec-2021 Klang Valley flood reports** (news + academic; e.g. which districts
  were inundated vs spared) → candidates must NOT appear as flooded.
- The existing positive sources (already enumerated in the register) → candidates
  must not collide with any positive.

Each new control records a **provenance string**: the source(s) consulted and the
one-line justification for the dry label (e.g. "low-lying planned township, absent
from DID flood-prone list + DBKL hotspot list; not in Dec-2021 inundation reports").

### 2.3 Honesty guard (cardinal — Singapore #15)

The dry set is finalized **before** looking at the model's output at those points.
After re-validation, **a hard negative that the model floods is a REAL specificity
miss → it STAYS in the register and is reported.** The negative set is **never**
curated to raise CRR. A CRR that *falls* on harder negatives is the more honest,
more defensible number, and is reported as such.

## 3. Components / changes

### 3.1 `scripts/build_kl_hotspot_register.py` (modify)
- The dry-control entries currently assume **elevated** (`DRY_MIN_ELEV_M = 60`; a
  low-lying dry control is flagged as a geocode error).
- Add a third `kind` value **`dry_lowlying`** alongside `positive` / `dry`
  (`dry` stays the elevated class). For `dry_lowlying`, the verification flag is
  **distance to the nearest documented flooded positive** (too close → likely
  mis-geocoded onto a flood spot → flag), NOT an elevation floor.
- Both `dry` and `dry_lowlying` map to the loader's negative class (see 3.2). The
  `kind` distinction is retained in the CSV `source`/a column for provenance and
  for the elevated-vs-hard split in reporting.
- Append the ~8 new controls (display name, geocode query, kind, provenance source)
  to the in-file candidate list.

### 3.2 `scripts/city_manifest.py` (verify/extend `load_hotspots_from_manifest`)
- The adapter maps register `kind` → Hotspot class. Confirm/extend so **both `dry`
  and `dry_lowlying`** map to the negative ("dry") class scored by
  `hotspot_scoring`. Positives unchanged. (If the manifest loader keys on
  `kind == "dry"`, broaden to `kind.startswith("dry")` or an explicit set.)

### 3.3 `data/kuala_lumpur/manifest/hotspots.csv` (regenerate)
- Re-run the builder (network: Nominatim, 1 req/s) to geocode the new controls and
  write the expanded register. Failed geocodes → empty coords + `confidence=failed`
  for manual follow-up (existing behavior).

### 3.4 Validation (no code change expected)
- `scripts/validate_hotspots_kl.py --rp 100` recombines the unchanged pluvial∨
  fluvial field and scores the **expanded** register. Report HR/CRR/TSS + bootstrap
  CI, and the elevated-vs-hard CRR split.

## 4. Data flow

```
research (model-blind) → candidate list in build_kl_hotspot_register.py
   → geocode (Nominatim) + DEM/HAND verify → hotspots.csv (n_dry≥15)
   → load_hotspots_from_manifest (dry + dry_lowlying → negative)
   → validate_hotspots_kl.py → HR/CRR/TSS + CI (+ elevated/hard split)
   → dossier §11 + limitation update
```

## 5. Testing

- **Builder:** a unit test that the candidate list has ≥15 dry (`dry` + `dry_lowlying`)
  entries and that every entry has a non-empty provenance source; a test that the
  `dry_lowlying` verification flag uses distance-to-positive, not elevation (e.g. a
  synthetic low-elevation `dry_lowlying` point far from positives is NOT flagged).
- **Loader:** a test that `load_hotspots_from_manifest` maps a `dry_lowlying` row to
  the negative class (so it is scored as a dry control).
- **No network in tests:** geocoding is not unit-tested (network); the builder's
  pure logic (counts, flag rule, provenance presence) is tested on the in-file list.
- Full suite stays green.

## 6. Success criteria

1. `n_dry ≥ 15` with a documented mix of elevated + low-lying hard negatives.
2. Every dry control is model-blind + carries a provenance source string.
3. The gate is re-run and reported **honestly** with the (tighter-n) CI and the
   elevated-vs-hard CRR split; flooded hard negatives are kept and reported.
4. Dossier §11 + a register-growth limitation entry document the method, the new
   numbers, and any hard-negative misses.

## 7. Out of scope (YAGNI)

- Growing the positive set (already 17, comprehensive).
- Re-running any raster (pluvial/fluvial unchanged; validation only re-scores).
- Scenario-forcing regen (#16), viz, AR6 offline-repeatability — separate items.

## 8. Risks

- **Undocumented flooding:** a low-lying "dry" control may have flooded without
  record → mislabeled negative. Mitigated by requiring absence from *multiple*
  flood sources + Dec-2021 cross-check, and by honestly documenting residual risk
  per control. A handful of mislabels bias CRR *downward* (conservative), not up.
- **Geocoding precision:** Nominatim ~city-block precision; the 50 m hit-radius
  already matches this (dossier). Mis-geocodes caught by the distance-to-positive
  flag + DEM check.
- **Network dependence:** Nominatim required for geocoding (already a project dep).
