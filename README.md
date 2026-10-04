# ASEAN multi-hazard flood atlas — code for the SAFE 2026 release

The code behind the open 30 m flood maps for **Singapore, Kuala Lumpur, Bangkok and Jakarta**
presented at SAFE 2026: coastal, river (fluvial) and rain (pluvial) flood depth for the present
day and for SSP2-4.5 and SSP5-8.5 at 2050 and 2100, at the 10-, 100- and 1,000-year return
periods.

- **Maps and inputs:** Zenodo, concept DOI
  [10.5281/zenodo.20821455](https://doi.org/10.5281/zenodo.20821455), CC BY 4.0.
- **This repository:** the pipeline that produced them, the terrain calibration, the frozen
  validation lists and the regression tests, under GPL-3.0-or-later.

This snapshot is tagged `safe2026-v4.0`. Earlier versions of the project remain in the history
of this repository. A later revision is in preparation and is not yet public.

## What's here

```
model/            flood solvers: height above drainage (river), fill-and-spill and drain overflow
                  (rain), local inertia (coast), depth combination
scripts/          pipeline drivers, forcing builders, validators and figure renderers
dem/              bare-earth terrain build and its ICESat-2 calibration, with the sampled
                  ground-truth points
data/<city>/      forcing tables (hazard_levels_*.csv), manifests and the frozen validation lists
repro/            environment files and the end-to-end run scripts
tests/            regression suite for the engine
docs/technical/   model documentation, the adversarial review and the new-city runbook
docs/runs/        notes behind the main method decisions
```

`HANDOFF_safe-paper-clean-run.md` is the full specification of the run that produced the maps.

## Reproducing

1. Large rasters (terrain, height above drainage, masks) and all outputs are not in git. Get the
   data archive from Zenodo; its `inputs/` folders carry the rasters the atlas runs on, and
   `repro/DATA_MANIFEST.md` lists where each one goes.
2. `python -m pytest tests/` runs the engine's regression suite, which doesn't need the
   Zenodo data (Python 3.14; see `repro/environment.yml` and `repro/ENV_NOTES.md`).
3. `repro/reproduce_gate.sh` re-scores the location test on the released present-day maps.
4. `repro/run_atlas_fixed.sh` (or `repro/run_all.ps1` on Windows) rebuilds the atlas. Set the
   interpreter path at the top of the script first. The coastal solves take hours.

Rebuilding the terrain from scratch needs a separate environment (`repro/environment_sfincs.yml`)
and the source data listed in `repro/DATA_MANIFEST.md`; the calibrated terrain itself ships in
the Zenodo archive.

## Not included

- The papers and the presentation materials.
- Third-party flood observations that can't be redistributed here: the Global Flood Database
  (CC BY-NC) record for Bangkok 2011, and the EOS-ARIA flood proxy map for Jakarta 2020. The
  validation scripts name their sources; `scripts/validate_historical_events.py` downloads the
  Jakarta map itself.

## Limits

This is a screening tool for triage, not for designing assets or settling losses. Its known
limits are set out in `docs/technical/model-documentation.md` (§10) and
`docs/limitations_register.md`. Among them: river floods that start outside a city's mapped
area aren't reached, flooding smaller than 30 m isn't resolved, input uncertainty isn't carried
through to the maps, and only the present day can be validated.

## Licence and citation

Code and configuration: GPL-3.0-or-later (`LICENSE`). The maps and inputs on Zenodo: CC BY 4.0.
Third-party inputs keep their own licences: Copernicus GLO-30, ERA5, GloFAS, IPCC AR6 sea-level
projections, ESA WorldCover, OpenStreetMap, ICESat-2, ETH canopy height and DeltaDTM.

Please cite the software (`CITATION.cff`) and the data record.
