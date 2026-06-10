# KL Dry-Control Hardening — research + systematic model-blind methodology (Plan 9)

**Date:** 2026-06-06
**Goal:** harden the KL dry-control set (was 7, all elevated hills) so CRR/TSS test
*real* specificity, not the trivial "all negatives are hilltops" case.

---

## 1. Research finding — KL flood/dry separation is terrain-driven

Web research (DBKL hotspot lists; Oct-2024 flash-flood road lists; Dec-2021 event
reports) shows that in KL **low-lying ≈ flood-prone**: Cheras, Setapak, Sri Petaling,
Gombak, Batu Caves, OUG, Taman Desa, Salak South and most valley-floor areas all
carry flood history. The reliably-dry areas genuinely **are** the elevated ones.

**Consequence for the negative set.** "Research-grounded *named* low-lying dry
controls" are scarce and risky: labelling a specific valley-floor locality "dry"
from absence-of-mention would likely mislabel it (undocumented flooding). So instead
of asserting named low-lying negatives, we use a **systematic model-blind sampler**
that defines hard negatives by terrain + flood-record criteria — never by the
model's flood output, and never by a fragile per-place "did it flood?" claim.

Sources consulted (model-blind — flood records, not model output):
- DBKL 14-hotspot list (Scoop 2024); Oct-2024 KL flash-flood roads (Malay Mail/NST).
- Dec-2021 Klang Valley event reports (ISEAS 2022/26; Wikipedia; Selangor Journal).
- 18 additional flood-prone areas geocoded → `data/kuala_lumpur/_flood_exclusions.json`
  (combined with the 17 register positives = **35 documented flood locations**).

## 2. Systematic hard-negative methodology

`scripts/build_systematic_dry_controls.py` selects control points by these criteria
(all model-blind — terrain + flood records only):

1. **Above the RP100 fluvial stage** — main-stem HAND in **[6.5, 20] m**. > 6.06 m so
   they are NOT on the trivially-flooded fluvial floodplain (avoids circularity:
   we are not just re-deriving HAND); < ~20 m so they are **lower than the existing
   30 m+ hilltop controls** → genuinely *harder* negatives. Tests whether the
   **pluvial** model (raingrid depression ponding) or a residual HAND artifact
   spuriously floods terrain-plausible NON-floodplain valley-flank sites.
2. **Not on a channel** (`drainage_waterways` cell ⇒ excluded) — a drain is not dry land.
3. **> 1 km from every one of the 35 documented flood locations** — the "dry" label
   rests on *flood-record absence*, model-blind.
4. **Urban-core bbox** (lon 101.62–101.75, lat 3.05–3.22) — where the model is active
   and flooding is plausible (a fair, hard test region).
5. **Spatially thinned** — ≥ 2.5 km between controls, 12 selected, ordered by
   greatest distance-to-flood first.

**Order of operations (discipline):** selection is computed from terrain + flood
records and **frozen BEFORE** the model's flood rasters are consulted. The model is
read only at the validation step (§4). The negative set is **never** curated by the
model's output.

## 3. The 12 systematic hard negatives

| # | Reverse-geocoded locality | lat | lon | HAND (m) | DEM (m) | km to nearest flood |
|---|---------------------------|-----|-----|---------:|--------:|--------------------:|
| 1 | Bandar Puchong Jaya | 3.0507 | 101.6204 | 10.1 | 20.1 | 4.87 |
| 2 | Kampung Baru Kuala Ampang | 3.1659 | 101.7494 | 9.9 | 47.0 | 4.79 |
| 3 | Bandar Sunway | 3.0735 | 101.6197 | 9.2 | 21.2 | 4.51 |
| 4 | Seksyen 19 (PJ) | 3.1133 | 101.6311 | 18.5 | 30.5 | 4.25 |
| 5 | Jinjang | 3.2076 | 101.6637 | 14.7 | 51.8 | 3.81 |
| 6 | Taman Kosmo Jaya | 3.2019 | 101.6855 | 8.7 | 45.8 | 2.90 |
| 7 | Semarak | 3.1782 | 101.7292 | 19.1 | 56.1 | 2.87 |
| 8 | Zon Perindustrian Seksyen 51 | 3.0906 | 101.6351 | 11.2 | 23.2 | 2.82 |
| 9 | Jinjang (north) | 3.2158 | 101.6419 | 19.9 | 56.1 | 2.65 |
| 10 | Bukit Tandang | 3.0629 | 101.6399 | 9.1 | 23.9 | 2.62 |
| 11 | Seputeh | 3.1197 | 101.7048 | 18.3 | 35.5 | 2.33 |
| 12 | Taman OUG | 3.0791 | 101.6780 | 19.9 | 37.1 | 2.03 |

(Coords + metadata: `data/kuala_lumpur/_systematic_dry_controls.json`.) These are
genuinely *hard*: valley-elevation (DEM 20–56 m), HAND only 9–20 m (far lower than
the 30–156 m hilltop controls), inside the active urban domain.

## 4. Honest caveats (residual risk — accepted, conservative)

- **Undocumented-flood / mislabel risk.** "> 1 km from a *documented* flood" does not
  prove a site never floods. Several controls sit in districts with broader flood
  history (Puchong, Sunway, OUG, Jinjang). If such a site *did* flood undocumented
  and the model floods it, it is counted (wrongly) as a specificity *miss* — i.e. the
  mislabel biases **CRR downward (conservative)**. A *high* CRR on this set is
  therefore strong evidence; a *low* CRR flags either real over-extent or mislabels
  to investigate, not a silent pass.
- **The flooded-negative-STAYS rule (cardinal, SG #15).** Any of these the model
  floods is reported by name with its depth and **kept** in the register. The set is
  frozen; it is never trimmed to raise CRR.
- **Reverse-geocoded names are cosmetic;** the controls are defined by their
  coordinates + the four terrain/record criteria, which are deterministic and
  reproducible from the committed rasters + `_flood_exclusions.json`.
