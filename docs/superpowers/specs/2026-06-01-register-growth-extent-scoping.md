# Scoping note: growing the validation register (extent data + N levers)

**Date:** 2026-06-01
**Context:** Bootstrap CIs (limitations register #12) show the 20-positive / 6-control
pluvial register cannot statistically separate the city-calibrated model from naive
topography in either direction. N — especially *informative* N — is the binding lever on
the comparative claim. This note scopes the options.

## 0. Current state (verified)

- **No flood-extent data exists on disk.** No `.shp`/`.geojson`/`.gpkg`/extent raster
  anywhere under `data/singapore`. The register is point-only:
  `data/singapore/flood_obs/hotspots/sg_pluvial_hotspots.csv` (20 flood + 6 dry).
- Hand-typed coordinate expansion is **ruled out** (register #6b): a 6-point manual
  addition failed a DEM elevation cross-check (2/6 mis-located). Any growth must be
  geocoded/surveyed.

## 1. Why extent data is the highest-value lever (in principle)

A single mapped flood polygon converts to thousands of pixel-level samples, enabling a
**Critical Success Index** (CSI = TP / (TP+FP+FN)) against a true extent rather than a
binary point-hit TSS, and collapses the bootstrap CIs by 1–2 orders of magnitude in N.
This is the only lever that changes the *statistical regime*, not just the point count.

## 2. The hard truth for **pluvial** extent capture

Urban flash-pluvial floods are intrinsically hostile to remote extent mapping:

| Source | Feasibility for SG pluvial | Why |
|---|---|---|
| Sentinel-1 SAR (C-band) | **Low** | 6–12 day revisit, ~sub-hourly flood duration; the 2010/2011 Orchard events predate S-1 (launched 2014). SAR also struggles in dense urban (layover, smooth-road double-bounce). |
| Sentinel-2 / optical | **Very low** | Cloud cover during the storm; water recedes before the next clear pass. |
| PlanetScope (daily) | **Low–med** | Daily revisit helps, but still cloud-limited and post-2017 only; licensing (not commercial-safe by default). |
| **PUB / news-mapped graphics** (post-event maps, Straits Times graphics) | **Med** | Manual georeferencing of published flood maps → digitised polygons. Effort-heavy, confidence moderate, but commercial-safe and event-specific. **Best pluvial-extent path.** |
| Geotagged UGC (photos, social) | **Low–med** | Point-level, not extent; variable georef. Feeds the *point* register, not CSI. |

**Conclusion:** there is no cheap satellite extent product for SG pluvial. Extent-based
CSI is realistic for **fluvial/coastal slow floods** (and for other cities — §4), not for
Singapore flash pluvial. We should not over-invest in a SAR pipeline for the pluvial claim.

### 2a. Verified availability (checked 2026-06-02, not just reasoned)

A search of the standard off-the-shelf extent archives confirms **no ready-made authoritative
flood-extent polygon exists for any Singapore event**:

- **Copernicus EMS Rapid Mapping** — activatable only by designated civil-protection /
  humanitarian authorities (mostly EU + partner states); Singapore self-manages flood
  response and has **no EMS activation**. No SG flood perimeter products.
- **Global Flood Database v1** (Tellman et al. 2021, MODIS 250 m, 2000–2018, ~913 events from
  the Dartmouth Flood Observatory catalogue) — catalogues large *regional/riverine* events.
  Singapore's flash-pluvial floods are sub-250 m and sub-daily, are not in the DFO catalogue,
  and the 250 m pixel could not resolve the 150 m hotspot test even if one were. **No usable
  SG event.**
- **New Sentinel-1 global flood DB** (Nature Comms 2025, 10 m) — better resolution but the
  6–12 day SAR revisit cannot catch a flood that drains in hours; no SG flash-pluvial event
  is expected and none was surfaced.
- **data.gov.sg — PUB "Flood Alerts across Singapore" API** — real-time **point** sensor
  alerts (water-level gauges), **not** extent polygons and **not** depth. Useful only as a
  *dated point-occurrence* feed (could confirm which register entries actively flood, and add
  timestamps), never for extent-based CSI.

- **ArcGIS Online "Singapore_Floods_WFL1"** (item `7174768e…`, layers "Flood Prone Areas
  2014/1970", polygons) — **checked and rejected**. It *is* polygon data, but: a personal
  account with no attribution; all 60 polygons have **null `Name`** and no source/date/depth
  field; and the 2014 total area is **5.88 km² (≈ 588 ha) — ~16× the official PUB ~36 ha
  figure for 2014**. Unverifiable provenance + gross area inflation fail the anchoring
  discipline. It would also be harmful as a CSI mask: a 588 ha "flood-prone" blob rewards
  over-flooding (any model wetting low ground scores high CSI; naive TWI scores higher
  still), so it cannot discriminate skill. Not usable as anchored ground truth.

**Net:** extent-based validation is **not available** for Singapore pluvial, by both archive
search and the underlying physics (flash, sub-hourly, under storm cloud). DIY paths (GEE
Sentinel-1 change-detection on a specific recent event date; hand-digitising a PUB/news
post-event map) are low-yield and either miss the flash peak or produce a low-authority
hand-drawn polygon — not worth the build for the pluvial comparative claim.

## 3. The realistic pluvial N levers (ranked)

1. **Geocode the point register up (positives).** PUB historical flood-incident records +
   geolocated news-archive reports (Straits Times, CNA), run through a proper geocoder
   (OneMap SG API — authoritative, free, commercial-safe), not manual pins. Target: 20 → 40–60
   positives. Each tagged with `georef_confidence` and event date/return-period where known.
2. **Dry controls via PUB list-diff (negatives).** Diff the PUB flood-prone list versions
   (e.g. Apr-2025 vs Nov-2025 vs historical) to extract **de-listed (resolved) areas** —
   documented to no longer flood at the design standard. Geocode via OneMap. *Caveat to log:*
   de-listed sites may still be topographically low (drainage fixed, not terrain), so a
   design-capacity model may still flag them — they test "model represents drainage upgrades"
   (it does not), which is itself an informative negative, not a clean specificity control.
3. **Reclaimed / modern-drainage negatives** (Marina South, Punggol, Tampines, Tuas):
   low-lying, post-2011 drainage code, never on any list. Weaker (absence-of-evidence), tag
   `low`, use only to diversify negative terrain types.
4. **Bootstrap CIs (done).** Already reporting — quantifies what each N increment buys.

Levers 1+2 together could plausibly take the register to ~50/20 and meaningfully tighten the
ΔTSS CI — enough to *resolve* whether the model genuinely beats topography.

## 4. The strongest form: cross-city extent (separate scope)

Bangkok 2011, Jakarta 2020, Manila 2009 have **mapped multi-hazard event extents** (fluvial
+ coastal) in the literature / UNOSAT / Copernicus EMS archives. Extending the comparative
framework to those cities is where coastal/fluvial can carry a *comparative* (CSI) claim, not
just plausibility — and where extent-based N is actually attainable. This is a multi-city
scope decision, tracked against the paper-strategy memory (Singapore-first, then generalise).

## 5. Recommendation

- **Do not** build a SAR/optical pipeline for SG pluvial extent (poor ROI; §2).
- **Do** pursue levers 1+2 (OneMap-geocoded PUB historical incidents + de-listed areas) as
  the next register-growth task — it is the realistic path to a statistically resolvable
  pluvial comparative verdict.
- **Defer** cross-city extent (§4) to the multi-city generalisation phase; it is the right
  home for extent-based CSI and for coastal/fluvial comparative claims.

## Effort estimate (lever 1+2)

- OneMap geocoder integration + a small `fetch_pub_historical_incidents` scraper: ~0.5–1 day.
- Manual source curation (which incidents/de-listings, with citations): ~1 day.
- Re-score + bootstrap + paper update: ~0.5 day.
- **Total ~2–2.5 days** to roughly double the register on a defensible, geocoded basis.
