# KL present-day baseline run — 2026-06-04 (completed 2026-06-05)

**Command (hardened to reuse pre-built rasters; offline):**
```
run_city_pipeline.py --city kuala_lumpur --scenario SSP5-8.5 --horizon 2020 --delta-T 0.0 \
  --pluvial-model raingrid --coastal-solver bathtub \
  --no-fit-era5 --no-fit-coastal --no-fit-glofas \
  --no-sea-mask --no-build-river-raster --no-street-overlay --out-root outputs
```

**Solver choices (spec):** raingrid pluvial (HANDOFF: realistic for KL's steeper terrain),
bathtub coastal (screening upper bound; inertial shelved), `--delta-T 0.0` (present-day, no
climate scaling — built a fresh `hazard_levels_ssp585_2020.csv` from the baseline template, so
this run is UNAFFECTED by the limitation-#16 scenario-CSV bug). Reused existing
sea-mask / river-mask / HAND / runoff rasters; skipped network OSM + street overlays.

**Output (gitignored):** `outputs/kuala_lumpur_ssp585_2020/` — RP2…RP1000 depth+severity rasters
for coastal / fluvial / pluvial (9 RPs × 3 hazards × 2 raster types). Summary copied to
`2026-06-04-kl-baseline-summary.csv`.

## Gate results

- **Gate 1 — RP-monotonicity + mass-plausibility (`check_rp_monotonicity.py`, domain 3520.2 km²): PASS.**
  Per hazard, `flooded_area_km2` and `max_depth_m` non-decreasing with RP; wet fraction < 60% everywhere.
- **Gate 2 — scenario-forcing consistency (`validate_scenario_forcing_consistency.py`): FAIL = the known
  limitation #16** (27 problems in the ssp245/585 2050/2100 CSVs). This guard inspects the *future-scenario*
  CSVs, not the present-day baseline, so it does NOT gate this artifact. Regen scheduled for Plan 3.

## Summary highlights

| Hazard | RP2 | RP100 | RP1000 | Note |
|---|---|---|---|---|
| coastal | 0 km² | 0 km² | 0 km² | **≈0 everywhere — expected** (KL inland; coastal N/A per spec §6.1) |
| fluvial | 0 | 45.0 km² / 1.70 m | 87.7 km² / 4.16 m | dry < RP25 (bankfull subtraction), then monotone |
| pluvial | 97.4 km² / 1.60 m | 589 km² / 3.93 m | 696 km² / 4.53 m | monotone; see findings below |

## Findings carried to Plan 2 (validation) / Plan 3 (fixes)

1. **Coastal layer is identically zero.** Correct per spec for the inland city-centre, but confirm the
   domain actually reaches the Port Klang coast; if a meaningful coastal layer is wanted, the study extent
   must include the lower Klang Valley. Validation should treat KL coastal as N/A-with-rationale, not score it.
2. **Pluvial `max_depth_m` reaches 4.5 m, exceeding the documented 3.0 m ponding cap.** The
   `--max-ponding-depth-m` (default 3.0) cap was NOT enforced in this run (solver peaks of 3.6–4.5 m
   survived into the output). Investigate the cap wiring in `run_multihazard` raingrid path — likely a quick
   fix — before the realism claims of Plan 2. (Did not break monotonicity, so Gate 1 still passed.)
3. **Pluvial extent is large** (RP2 = 97 km²/2.8% of domain → RP1000 = 696 km²/19.8%). Plausibility is for
   the extent-CSI-vs-MYS2021-SAR check (Plan 2) to judge — do NOT eyeball-tune it here.
4. **Fluvial dry below RP25** — consistent with the Q_bf=98 m³/s bankfull subtraction in the KL config.

**Next:** Plan 2 — validation harness (extent-CSI vs MYS2021 SAR, hotspot register + hit-rate, point-depth,
bootstrap CIs, two-gate dossier), now grounded in these real baseline rasters.
