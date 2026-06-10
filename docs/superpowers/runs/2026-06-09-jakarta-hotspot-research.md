# Jakarta flood hotspot research (model-blind) — Plan J1 Task 1

**Goal:** a model-blind documented-hotspot register for Jakarta — positives = localities
**documented flooded** in Jakarta's recurrent monsoon floods (the 2007, 2013 and 2020 New
Year events in particular); dry controls = the genuinely-elevated south + the documented-dry
central natural-levee core. The dry label comes from flood records and the real elevation
gradient, NEVER from the model's output. Selection is frozen here BEFORE any Jakarta model
raster is consulted (model-blind).

This doc is the audit trail proving the register was sourced to documented facts, not
reverse-engineered to pass a gate. The hotspots.csv it justifies is geocoded in a later J1
task (Task 1 deliberately does NOT create hotspots.csv).

## Key facts — Jakarta's flood mechanisms

Jakarta floods through three overlapping mechanisms, and a clean register must separate them:

1. **Ciliwung-corridor fluvial.** The Ciliwung drains ~370 km² from the Bogor / Puncak
   highlands through Depok into south-central Jakarta. Upstream Bogor rainfall (NOT local
   Jakarta rainfall) drives the corridor's worst floods; the riverbank kampungs between
   Kampung Melayu and Manggarai are inundated almost every major wet season. This is the
   river behind Jakarta's historic 2002, 2007 and 2013 floods (cf. cities.py jakarta /
   bekasi_depok notes).
2. **Monsoon pluvial / secondary rivers.** Extreme local convective rainfall (the Jan-2020
   New Year event delivered a record ~377 mm/24h at Halim, BMKG) overwhelms the engineered
   canal network (Banjir Kanal, ~RP5 design) and floods low-lying pockets across East and
   West Jakarta drained by the Cipinang, Sunter, Angke, Pesanggrahan and Grogol systems.
3. **North-Jakarta rob / coastal.** "Rob" (tidal flooding) plus extreme land subsidence
   (North Jakarta is sinking up to ~25 cm/yr; cities.py jakarta note) means the coastal
   strip floods from the sea behind/over the seawall independent of rainfall.

**The 2020 New Year flood is the validation event (JKT2020):** the worst single event in the
record-window, extreme-pluvial-dominated, with the Ciliwung corridor and East/West low pockets
inundated and ~60 deaths. The JKT2020 Sentinel-1 SAR proxy (EOS-ARIA-SG, 2 Jan 2020) is the
extent reference.

**Sources (documented flood records):** 2020 Jakarta floods (Wikipedia / BBC / Reuters /
Jakarta Post coverage, Jan 2020); 2013 Jakarta flood and 2007 Jakarta flood (Wikipedia; BNPB /
BPBD DKI Jakarta situation reports); World Bank "Bringing Jakarta out of the floods" / Jakarta
Urgent Flood Mitigation; Abidin et al. on Jakarta land subsidence; Ciliwung-corridor kampung
relocation reporting (Kampung Pulo / Bukit Duri normalisation, 2015-2016).

## Positives — mechanism (a): Ciliwung-corridor fluvial

Riverbank localities on the Ciliwung between Kampung Melayu and the Depok boundary, all
documented flooded in 2007/2013/2020:

| name | mechanism | source / note |
|------|-----------|----------------|
| Kampung Melayu | Ciliwung fluvial | Kampung Melayu / Manggarai floodgate area, inundated 2007/2013/2020 (BPBD; Jakarta Post) |
| Bukit Duri | Ciliwung fluvial | Ciliwung riverbank kampung; normalisation/relocation after 2013 floods (Jakarta Post) |
| Kampung Pulo | Ciliwung fluvial | iconic Ciliwung-bend flood kampung; recurrent inundation, 2015-16 relocation (Reuters) |
| Cawang | Ciliwung fluvial | East-Jakarta Ciliwung corridor, flooded 2013/2020 (BPBD) |
| Rawajati | Ciliwung fluvial | South-Jakarta riverbank, flooded 2020 (Jakarta Post / Kompas) |
| Bidara Cina | Ciliwung fluvial | Jatinegara Ciliwung-bend kampung, recurrent flooding (Kompas) |

## Positives — mechanism (b): monsoon pluvial / secondary rivers

Low-lying pockets flooded by extreme local rainfall and the secondary-river systems,
documented in Jan-2020 in particular:

| name | mechanism | source / note |
|------|-----------|----------------|
| Cipinang Melayu | pluvial / Sunter-Cipinang | East-Jakarta low pocket, one of the worst-hit areas Jan-2020 (Jakarta Post / BBC) |
| Kemang | pluvial (affluent-SOUTH POSITIVE) | affluent south pocket that DID flood Jan-2020 — built on a former Krukut floodplain; a POSITIVE, NOT a dry control (Jakarta Post; Reuters) |
| Kelapa Gading | pluvial / North-East low | chronic North-East flood basin, flooded 2020 (Jakarta Post) |
| Grogol | pluvial / Grogol-Angke | West-Jakarta, flooded 2020 (Kompas) |
| Cengkareng | pluvial / Angke-west | far-West low-lying, flooded 2020 (Kompas / BPBD) |

**Kemang caveat (load-bearing):** Kemang is wealthy and in the *south*, but it sits in a low
former-floodplain pocket of the Krukut and flooded conspicuously in Jan-2020. It is therefore
classified as a POSITIVE. This is the explicit reason Jakarta's dry controls cannot simply be
"the affluent south" — see the dry-controls caveat below.

## Positives — mechanism (c): North-Jakarta rob / coastal

Coastal strip flooded by tidal "rob" + subsidence, documented chronically and in 2020:

| name | mechanism | source / note |
|------|-----------|----------------|
| Penjaringan | coastal rob / subsidence | North-Jakarta, chronic tidal flooding + subsidence, flooded 2020 (Abidin et al.; Jakarta Post) |
| Pluit | coastal rob / subsidence | below-sea-level polder, chronic rob, pump-dependent (World Bank; Jakarta Post) |
| Muara Baru | coastal rob / subsidence | among fastest-subsiding points (~25 cm/yr), chronic rob (Abidin et al.; BBC) |
| Kalibaru | coastal rob | North-Jakarta Cilincing-adjacent coastal kampung, tidal flooding (Kompas) |
| Cilincing | coastal rob | far-North-East coastal, tidal flooding + subsidence (Kompas / BPBD) |

## Dry controls (documented-dry / genuinely-elevated) — model-blind

Two sets, both chosen from documented facts, NOT from model output:

**(i) Genuinely-elevated south** — Jakarta's south rises toward the Bogor piedmont, so these
are geographically appropriate high-ground negatives (a real elevation gradient, unlike KL #21
where low-lying negatives were unsourceable):

| name | basis | source / note |
|------|-------|----------------|
| Cilandak | elevated south | higher south-Jakarta ground, not in 2020 flood reports (DEM-verify in geocode task) |
| Jagakarsa | elevated south | southernmost Jakarta, highest DKI ground toward Depok piedmont |
| Lebak Bulus | elevated south | elevated south-west, outside documented 2020 inundation |
| Pasar Minggu | elevated south (off-river) | the off-Ciliwung elevated portion (NOT the riverbank strip) |
| Cipete | elevated south | elevated south-central, outside documented flood pockets |

**(ii) Documented-dry central natural levee** — the old-colonial core sited on the Ciliwung's
natural levee / higher central ground, historically the part that stays dry:

| name | basis | source / note |
|------|-------|----------------|
| Menteng | central natural levee | planned colonial-era district on higher central ground, documented-dry core |
| Gambir | central natural levee | Merdeka Square / Monas central high ground, documented-dry core |

## Discipline notes

- **Model-blind:** every positive is anchored to a documented 2007/2013/2020 flood record;
  every dry control is anchored to documented-dry status PLUS Jakarta's real south/levee
  elevation gradient. No Jakarta model raster (hazard_baseline / pluvial / coastal extent) was
  consulted to choose any spot. The list is frozen here; the model is read only at the
  validation step.
- **Jakarta's south has a REAL elevation gradient** (rising toward the Bogor piedmont), so
  elevated negatives are geographically appropriate here — this is materially different from
  KL limitation #21, where low-lying negatives could not be sourced. The Jakarta dry controls
  are genuinely-high ground, to be DEM-verified at geocode time.
- **BUT some affluent-south pockets flood (Kemang).** Wealth/southerliness alone does NOT make
  a dry control: Kemang is affluent-south yet flooded in Jan-2020 (low Krukut floodplain) and
  is therefore a POSITIVE. Dry controls must be the genuinely-HIGH south + DEM-verified, never
  "the rich south" by reputation.
- **Flooded dry control stays in and is reported** (cardinal rule, SG #15 / Bangkok B1): if a
  DEM-verified high-ground control turns out flooded in the model at the validation RP, that is
  a real reportable finding, not a reason to drop the control.
- **Count:** 16 positives (6 Ciliwung fluvial + 5 monsoon pluvial + 5 coastal rob) + 7 dry
  controls (5 elevated south + 2 central levee). Geocoding + DEM verification is a later J1 task.

## Provenance note surfaced during sourcing (cities.py vs committed baseline)

While confirming forcing-anchor provenance (Task 1 Step 2), the committed
`data/jakarta/hazard_baseline_template.csv` (2026-05-16) shows the Jakarta pluvial baseline is
now a **BMKG 6h IDF-calibrated Gumbel** (xi=0, mu=77.209 mm, sigma=21.258 mm; anchored RP2=85.0
mm, RP100=175.0 mm at 6h). The `scripts/cities.py` jakarta note still describes the
**superseded** ERA5-Land path (ERA5-Land 6h GEV RP2 = 33.3 mm, -60.8% vs BMKG, NOT
IDF-calibrated, dated 2026-04-26). The "ERA5-Land-not-IDF" provenance gap the J1 plan asked to
record was therefore the HISTORICAL state; it was CLOSED by the 2026-05-16 IDF re-fit. The
forcing_anchors.csv pluvial rows record the config-consistent committed values (6h RP2=85.0 mm,
RP100=175.0 mm) and document this superseded-note discrepancy in their citations rather than the
original 114.0 mm / 24h figure, which is not supported by the committed config. This note is the
audit trail for that deviation.
