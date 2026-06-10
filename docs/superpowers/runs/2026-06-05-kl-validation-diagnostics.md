# KL validation diagnostics — 2026-06-05

Run of two existing validators as **diagnostics** (NOT gates) to document extent-CSI non-viability for KL and confirm the IDF-anchor under-shoot that motivated IDF-calibrated forcing.

## Extent-CSI vs MYS2021 SAR (diagnostic, NOT a gate)

```
Running: MYS2021 - KL floods Dec 2021 — local Copernicus GFM Sentinel-1 ensemble (replaces UNOSAT FL20220112MYS Pahang/Johor — geographic mismatch)
========================================================================
Historical event validation: MYS2021 - KL floods Dec 2021 — local Copernicus GFM Sentinel-1 ensemble (replaces UNOSAT FL20220112MYS Pahang/Johor — geographic mismatch)
  City       : kuala_lumpur
  Source     : raster: data/kl/flood_obs/MYS2021/gfm_kl_composite_dec2021.tif
  Obs note   : Copernicus GFM Sentinel-1 ensemble (16-22 Dec 2021).  Urban SAR exclusion masks ~69% of the KL bbox (SAR double-bounce indistinguishable from open water in dense built-up areas).  Composite captures only ~0.14 km^2 of peri-urban flood — useful as a lower-bound spatial cross-check, not a representative obs set.
  Obs. area  : 0.1 km2  (flood polygons rasterized to 30 m grid)
  Flood thr  : 0.10 m
  RP range   : fluvial RP10-RP200, pluvial RP10-RP200
========================================================================
  Hazard        RP     CSI       H     FAR    Bias  Verdict
------------------------------------------------------------------------
  fluvial       10    0.00    0.00    0.00    0.00  INFO
  fluvial       25    0.00    0.00    1.00  200.21  INFO
  fluvial       50    0.00    0.00    1.00  259.35  INFO
  fluvial      100    0.00    0.00    1.00  323.68  INFO
  fluvial      200    0.00    0.00    1.00  403.85  INFO
  pluvial       10    0.00    0.09    1.00  1483.87  INFO
  pluvial       25    0.00    0.09    1.00  2041.27  INFO
  pluvial       50    0.00    0.09    1.00  2464.50  INFO
  pluvial      100    0.00    0.09    1.00  2817.67  INFO  <- best H
  pluvial      200    0.00    0.09    1.00  3122.59  INFO
------------------------------------------------------------------------
Best match : pluvial RP100  (CSI=0.00, H=0.09, FAR=1.00, Bias=2817.67)
  -> Verdict: LIMITED-FAIL
========================================================================

OVERALL: FAIL - 1 event(s) below CSI/H thresholds: MYS2021
```

The near-zero CSI is an expected reference-coverage artefact, not a model failure. The MYS2021 GFM SAR composite holds only ~345 flood pixels (~0.14 km²) across the KL bbox because SAR double-bounce in dense urban/built-up areas is indistinguishable from open water, so the urban Klang Valley is masked out (~69% exclusion); the UNOSAT FL20220112MYS vector that was the original event candidate covers Pahang/Johor, not the Klang Valley, and was therefore replaced with the local GFM composite. A CSI computed against a 0.14 km² reference over a 3,520 km² domain is statistically meaningless — the denominator is essentially zero. KL is therefore validated the same way as Singapore (an urban flash-flood city where SAR is unreliable): documented-hotspot hit-rate is the primary numeric gate, supplemented by point-depth and IDF-anchor cross-checks; extent-CSI is run only as a caveated diagnostic and is logged as limitation #17.

## IDF-anchor cross-check (diagnostic)

```
================================================================================
Pluvial IDF anchor validation (tolerance +/- 25%)
================================================================================
City                    RP      Anchor     ERA5-Land      Dev  Verdict
--------------------------------------------------------------------------------
  [kuala_lumpur] downloading ERA5-Land (no cache yet) ...
  ERA5-Land 2001-2005 ... 43,824 valid obs
  ERA5-Land 2006-2010 ... 43,824 valid obs
  ERA5-Land 2011-2015 ... 43,824 valid obs
  ERA5-Land 2016-2020 ... 43,848 valid obs
  ERA5-Land 2021-2024 ... 35,064 valid obs
  [info] GEV shape xi=1.5495 clamped to 0.3000 (xi_max=0.3). Re-fitting with fixed shape.
kuala_lumpur             2        90.0          45.8   -49.1%  FAIL
================================================================================
FAIL: 1 city(ies) outside +/-25%:
  - kuala_lumpur: ERA5=45.8 mm vs anchor 90.0 mm (-49.1%; source: JPS Malaysia RP2 6h (80-100 range))

Document the deviation in scripts/cities.py notes.
Do NOT introduce a multiplicative scaling factor (re-creates the precip_scale problem).
```

ERA5-Land under-shoots the JPS Malaysia RP2 6h anchor (90 mm) by ~49%, returning only 45.8 mm — a known reanalysis bias in convection-dominated tropical cities where ERA5-Land's 9 km grid smears the intense convective cells that drive KL's flash-flood regime. This under-shoot is precisely why the baseline uses IDF-calibrated Gumbel forcing (anchored to the JPS 90 mm value, `scripts/cities.py` KL pluvial entry) rather than raw ERA5-Land statistics. The FAIL verdict here confirms that ERA5-Land alone would produce a ~2× under-estimate of pluvial forcing, validating the deliberate choice of JPS-anchored IDF. The GEV shape clamping (xi=1.55 → 0.30) further signals that ERA5-Land heavy-tail behaviour is not well-characterised for this location, consistent with sparse extreme-event sampling in the reanalysis. This validator is a confirmatory diagnostic only — the IDF anchoring is already baked into the committed baseline CSV.
