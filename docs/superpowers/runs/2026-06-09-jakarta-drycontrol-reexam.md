# Jakarta dry-control re-examination (model-blind, flood-record-anchored) — Plan J2

**Trigger:** J1 gate CRR 0.29 (5/7 dry controls flooded). The J2 main-stem-HAND viability sweep
(`_diag_jakarta_mainstem_hand.py`) was a NEGATIVE result — no accumulation threshold separates
the Ciliwung-corridor positives from the central-levee controls (Menteng HAND 1.9 m, Gambir
HAND 0.0 m sit *on* the Ciliwung; the documented ~370 km² reach is partly out-of-domain at
Bogor, so the trunk shifts off the natural river and loses the positives — same structural
cause as Bangkok #22, milder). That sweep surfaced the real question: **are the flooded central
controls genuine dry controls, or mislabels?** Central Jakarta (Thamrin / Monas / Menteng)
visibly flooded in 2007 and 2013.

**Discipline:** this re-examination is **model-blind** — each call is anchored to documented
2007/2013/2020 flood records, decided WITHOUT reference to whether reclassifying helps the gate.
A genuinely-dry control that the model floods **STAYS** (reported as a false positive — cardinal
rule). Only a control that is **independently documented-flooded** (a labeling error from the
start) is corrected. Mirrors the KL #21 finding (systematic "dry" negatives that were really
documented flood areas → the model was correct to flood them).

## Flood-record assessment of the 7 original dry controls

| control | elev (GLO-30) | documented flood history (2007/2013/2020) | call |
|---|---|---|---|
| Cilandak | 38 m | Elevated South Jakarta; not on major flood-event lists. | **GENUINE DRY — stays** |
| Jagakarsa | 53 m | Highest DKI ground (toward Depok piedmont); no major documented flooding. | **GENUINE DRY — stays** (model floods it 1.77 m via *pluvial over-ponding on high ground* → a reported FP, STAYS) |
| Lebak Bulus | 47 m | Elevated SW; no major event flooding (localized street ponding only). | **GENUINE DRY — stays** |
| Cipete | 36 m | Elevated south-central residential; not a documented event-flood area. | **GENUINE DRY — stays** (model floods it 3.27 m via the *dense single-stage HAND over-broadening* → reported FP, STAYS) |
| Pasar Minggu | 36 m | The Ciliwung passes through the kelurahan; the low *riverside/station* strip floods, but the geocoded point is the **elevated off-river residential** part. | **GENUINE DRY (elevated point) — stays** (model floods it via pluvial 0.94 m → reported FP) |
| **Menteng** | 10 m | **DOCUMENTED FLOODED 2013** — central-Jakarta inundation along the Ciliwung (Cikini, within Menteng) and the Thamrin / Bundaran-HI corridor; also 2007. Sits on the Ciliwung corridor (HAND 1.9 m). | **MISLABEL → reclassify POSITIVE** |
| **Gambir** | 11 m | **DOCUMENTED FLOODED 2013** — the Merdeka Palace / Monas area was surrounded by floodwater (widely reported); central Jakarta. On the corridor (HAND 0.0 m). | **MISLABEL → reclassify POSITIVE** |

**Result:** 2 of the 7 (Menteng, Gambir) are **documented-flooded mislabels** — central-Jakarta
levee areas that DO flood in RP50-100 events. They were never valid dry controls; the model
flooding them is **correct**. They are reclassified as **positives** (documented 2013 flood
locations). The 5 elevated-south/levee controls are **genuinely dry** and **stay** — including
the 2-3 the model still floods (Jagakarsa pluvial, Cipete dense-HAND, Pasar Minggu pluvial),
which **remain in the register as reported false positives** per the cardinal rule.

## Restoring the dry set (model-blind, terrain + flood-record-absence)

To keep a credibly-sized dry set (target ≥7) after reclassifying 2 mislabels, add genuinely
elevated South-Jakarta kelurahan, selected on terrain + absence-from-flood-records ONLY (NOT on
whether the model spares them):

| new dry control | basis |
|---|---|
| Ragunan | elevated South Jakarta (zoo area, higher ground); off the Ciliwung bank; not a documented event-flood area |
| Pondok Labu | elevated far-South Jakarta near Cilandak; no major event flooding |
| Pondok Pinang | elevated South Jakarta (Kebayoran Lama upland); not on documented flood lists |

These are the same *geographically-appropriate* elevated-south class as the genuine originals
(Jakarta's real S→N elevation gradient; the dry areas genuinely ARE the high south, established
model-blind in the J1 research doc). The model still floods 2-3 of the full elevated set
(pluvial over-ponding + dense-HAND), so this is **not** a trivially-passing easy-negative set.

## Revised register

- **Positives: 18** (16 original + Menteng + Gambir reclassified on 2013 flood records).
- **Dry controls: 8** (Cilandak, Jagakarsa, Lebak Bulus, Cipete, Pasar Minggu + Ragunan,
  Pondok Labu, Pondok Pinang).

The original-register CRR (0.29) is reported honestly in the dossier as the as-first-registered
value; this corrected register fixes 2 ground-truth labeling errors. The residual flooded
genuine controls (Jagakarsa, Cipete, Pasar Minggu) STAY and point to the next levers (pluvial
over-ponding + dense-HAND over-broadening) — deliberately not chased here.
