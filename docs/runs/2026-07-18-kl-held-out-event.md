# KL held-out event validation — 2024-10-15 DBKL flash-flood bulletin (run 2026-07-18)

Closes the standing recommendation from `docs/technical/adversarial-review-2026-07-09.md`
(C7, ranked follow-up #2): *"score one post-2022 documented flood absent from every
register"* against the shipped canal-HAND pluvial layer.

## Discipline (declared before scoring)

- **Event:** 15 October 2024 KL flash floods — a DBKL Traffic Information & Traffic Light
  Control Centre (KLCCC) bulletin naming 13 flooded areas after a >114 mm/h cloudburst
  (rainfall figure per DBKL, Malay Mail 2024/10/15 art. 153711; road list art. 153681;
  NST art. 1119953). Post-dates every frozen register (registers imported ≤ 2026-07-04
  from lists compiled ≤ 2024 flood-prone inventories; this specific event's roads were
  never register entries).
- **Geocoding:** Nominatim (the register's own geocoder), road-level query, first hit.
- **Exclusions, pre-registered:** (1) bulletin roads that ARE register positives dropped
  up front (Jalan Kuching; Lebuhraya Sultan Iskandar); (2) any geocoded point within
  **250 m** of a register positive dropped (5× the scoring radius) — this removed
  Jalan Genting Klang (92 m from the register's Setapak point). Frozen register:
  `data/kuala_lumpur/manifest/holdout_20241015.csv` — **10 positives**, all in-domain.
- **Protocol:** identical to the gate — present-day RP100 combined layer, ≥ 0.10 m,
  50 m radius. **One scoring run; the first number is the reported number.**
- No dry controls: a flood bulletin documents only where it flooded, so this is a
  hit-rate test only (CRR/TSS are degenerate at n_dry = 0).

## Result

```
holdout_20241015.csv @ RP100, 0.10 m, 50 m:   HR = 0.30  (3/10)
```

| Point | Result | Hazard | Nearest wet cell |
|---|---|---|---|
| Jalan Pantai Baru | **HIT** | pluvial | 0 m |
| Jalan Maharajalela | **HIT** | pluvial+fluvial | 30 m |
| Jalan Gombak | **HIT** | pluvial | 60 m |
| Jalan Tuanku Abdul Halim | miss | — | 180 m |
| Jalan Wangsa Maju (Sri Rampai) | miss | — | 180 m |
| Jalan Damansara | miss | — | 150 m |
| Salak Selatan | miss | — | 437 m |
| Jalan Pudu | miss | — | 509 m |
| Jalan Manjalara | miss | — | 509 m |
| Ukay Perdana | miss | — | 994 m |

Labeled sensitivity (diagnostic only, NOT the headline; roads are line features and the
bulletin names whole roads, while the register protocol geocodes one point): at 250 m
radius the same frozen set scores **HR = 0.60 (6/10)**. Both are below the 0.70 gate bar.

## Interpretation (both readings recorded)

1. **The register PASS does not transfer to a single-event road bulletin at gate
   protocol.** KL's register HR 0.71 is measured on 31 documented *recurrent* flood-prone
   localities; this event's list is a one-cloudburst road inventory. Three of ten roads
   hit; three more have modelled wet cells 150–180 m from the geocoded point —
   consistent with the known geometry that a "flooded road" is a line whose low point may
   sit hundreds of metres from its Nominatim centroid; four are genuine far misses.
2. **The far misses are consistent with the documented KL failure mode, not a new one:**
   sub-hourly convective waterlogging at 30 m is partly sub-grid (model-documentation
   §6.3.5, §10 item 2). A >114 mm/h cloudburst floods carriageways wherever inlet
   capacity is exceeded — including on grade, where no 30 m terrain signal exists.

## Consequence

Logged in `model-documentation.md` §10 item 3 and the adversarial-review addendum: the
canal-HAND layer's demonstrated skill is **register-class** (recurrent flood-prone
localities), and single-event generalisation at gate protocol is measured at 0.30 —
a bound, not a pass. Any claim about per-event prediction must carry this number.
No re-tuning was performed in response to this result.
