# Climate-Scenario Flood Depth Model (Open Data + Open Method)

This starter project estimates flood depth rasters under climate scenarios (for example `SSP5-8.5`) using:

- Open terrain data (for example Copernicus DEM GLO-30 GeoTIFF)
- A transparent, baseline "bathtub" inundation method:
  - `depth = max(0, water_level - elevation)`
- Scenario-specific projected water levels supplied in a CSV you control (or auto-generated from public AR6 datasets)

## What this gives you

- A reproducible baseline model in Python
- Multi-hazard outputs split into `coastal`, `fluvial`, and `pluvial`
- Return-period products up to `1-in-1000`
- Depth severity products and summary metrics

## Methodology (public and reproducible)

The implemented method is the standard static inundation / bathtub approach used in many first-pass flood studies. It is intentionally simple and transparent.

- Terrain: DEM in meters (Copernicus DEM works well)
- Hazard forcing: projected water levels from public climate-impact studies or your own hydrodynamic workflow
- Computation: pixel-wise positive difference between scenario water level and DEM

## Important limitations

This baseline does **not** include:

- River/channel hydraulics or coastal dynamics
- Flow connectivity or barriers (levees, culverts)
- Time-varying hydrographs
- Vertical datum reconciliation automatically

For publication-grade hazard assessment, use this as a screening layer and then move to a 1D/2D hydraulic model.

## Project structure

- `model/flood_depth_model.py`: CLI model code
- `data/scenario_water_levels_example.csv`: input template (example numbers)
- `scripts/build_scenarios_from_ar6_zarr.py`: build scenario CSV from public IPCC AR6 Zarr projections
- `scripts/fetch_copernicus_dem.py`: fetch + clip Copernicus DEM from public STAC
- `scripts/build_singapore_hazard_levels.py`: build Singapore multi-hazard levels
- `scripts/run_singapore_multihazard.py`: run multi-hazard depth + severity rasters
- `requirements.txt`: Python dependencies

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Singapore-focused workflow

### 1) Fetch Singapore Copernicus DEM

```powershell
python scripts/fetch_copernicus_dem.py `
  --min-lon 103.57 `
  --min-lat 1.15 `
  --max-lon 104.10 `
  --max-lat 1.50 `
  --target-crs EPSG:32648 `
  --target-resolution 30 `
  --output data/singapore/copernicus_dem_utm48n.tif
```

### 2) Build Singapore hazard levels (coastal/fluvial/pluvial)

Input baseline template:

- `data/singapore_hazard_baseline_template.csv`
- Includes `return_period` values through `1000`
- Replace placeholder values with your public/local baseline dataset values

Build climate-adjusted levels:

```powershell
python scripts/build_singapore_hazard_levels.py `
  --baseline-hazards data/singapore_hazard_baseline_template.csv `
  --scenario SSP5-8.5 `
  --horizon 2100 `
  --lat 1.2903 `
  --lon 103.8519 `
  --percentile 50 `
  --baseline-year 2020 `
  --output data/singapore/hazard_levels_ssp585_2100.csv
```

Method in this step:

- `coastal`: baseline levels + IPCC AR6 public Zarr sea-level delta
- `fluvial`: baseline levels scaled by `--fluvial-factor` (default 1.10)
- `pluvial`: baseline levels scaled by `--pluvial-factor` (default 1.15)

### 3) Run multi-hazard depth + severity maps

Build a public river seed raster from OSM (required for corrected fluvial model):

```powershell
python scripts/build_river_raster_from_osm.py `
  --dem data/singapore/copernicus_dem_utm48n.tif `
  --place "Singapore" `
  --buffer-m 20 `
  --output data/singapore/river_mask_osm_utm48n.tif
```

```powershell
python scripts/run_singapore_multihazard.py `
  --dem data/singapore/copernicus_dem_utm48n.tif `
  --hazard-levels data/singapore/hazard_levels_ssp585_2100.csv `
  --scenario SSP5-8.5 `
  --horizon 2100 `
  --out-dir outputs/singapore_ssp585_2100 `
  --connectivity-neighbors 8 `
  --fluvial-river-raster data/singapore/river_mask_osm_utm48n.tif `
  --fluvial-max-distance-m 1500
```

## One-command run (Singapore)

Use the pipeline wrapper to run all 3 steps automatically:

```powershell
python scripts/run_singapore_pipeline.py `
  --scenario SSP5-8.5 `
  --horizon 2100 `
  --percentile 50 `
  --baseline-year 2020 `
  --fluvial-factor 1.10 `
  --pluvial-factor 1.15 `
  --connectivity-neighbors 8
```

Optional:

- `--baseline-hazards` to point to your curated baseline depth-frequency CSV
- `--seed-water-raster` for improved hydraulic connectivity seeding
- `--target-resolution` to change DEM output cell size
- `--fluvial-river-raster` to enable corrected HAND-based fluvial routing from rivers

Outputs are split by hazard and return period, for example:

- `outputs/singapore_ssp585_2100/coastal/rp_1000/...depth...tif`
- `outputs/singapore_ssp585_2100/fluvial/rp_1000/...depth...tif`
- `outputs/singapore_ssp585_2100/pluvial/rp_1000/...depth...tif`
- matching severity rasters
- summary table: `outputs/singapore_ssp585_2100/summary_SSP5-8.5_2100.csv`

Severity classes in output rasters:

- `0` no flood
- `1` minor `(0, 0.15] m`
- `2` moderate `(0.15, 0.50] m`
- `3` major `(0.50, 1.00] m`
- `4` severe `> 1.00 m`
- `255` nodata

## Fetch Copernicus DEM automatically

Download and clip Copernicus DEM tiles for a bbox:

```powershell
python scripts/fetch_copernicus_dem.py `
  --min-lon -74.30 `
  --min-lat 40.45 `
  --max-lon -73.60 `
  --max-lat 40.95 `
  --output data/copernicus_dem_nyc.tif
```

Optional reprojection to a meter-based CRS:

```powershell
python scripts/fetch_copernicus_dem.py `
  --min-lon -74.30 `
  --min-lat 40.45 `
  --max-lon -73.60 `
  --max-lat 40.95 `
  --target-crs EPSG:32618 `
  --target-resolution 30 `
  --output data/copernicus_dem_nyc_utm18n.tif
```

## Build scenario CSV from public AR6 data

You can generate scenario water levels directly from the public Rutgers/IPCC AR6 sea-level projection Zarr store.

Example (nearest tide-gauge location to your site):

```powershell
python scripts/build_scenarios_from_ar6_zarr.py `
  --lat 40.70 `
  --lon -74.01 `
  --scenario SSP2-4.5 `
  --scenario SSP5-8.5 `
  --horizon 2050 `
  --horizon 2100 `
  --percentile 50 `
  --baseline-year 2020 `
  --output data/scenarios_from_ar6.csv
```

Then use that CSV in the flood model with `--scenarios data/scenarios_from_ar6.csv`.

## End-to-end example (Singapore)

1) Fetch DEM
2) Build scenario water levels from AR6
3) Run flood model

```powershell
python scripts/fetch_copernicus_dem.py `
  --min-lon 103.57 `
  --min-lat 1.15 `
  --max-lon 104.10 `
  --max-lat 1.50 `
  --target-crs EPSG:32648 `
  --target-resolution 30 `
  --output data/singapore/copernicus_dem_utm48n.tif

python scripts/build_singapore_hazard_levels.py `
  --baseline-hazards data/singapore_hazard_baseline_template.csv `
  --scenario SSP5-8.5 `
  --horizon 2100 `
  --lat 1.2903 `
  --lon 103.8519 `
  --percentile 50 `
  --baseline-year 2020 `
  --output data/singapore/hazard_levels_ssp585_2100.csv

python scripts/run_singapore_multihazard.py `
  --dem data/singapore/copernicus_dem_utm48n.tif `
  --hazard-levels data/singapore/hazard_levels_ssp585_2100.csv `
  --scenario SSP5-8.5 `
  --horizon 2100 `
  --out-dir outputs/singapore_ssp585_2100 `
  --connectivity-neighbors 8
```

## Getting Copernicus DEM

You can download Copernicus DEM tiles from public portals, then mosaic/clip to your area of interest.

- Copernicus Data Space Ecosystem: [https://dataspace.copernicus.eu](https://dataspace.copernicus.eu)
- OpenTopography (often mirrors Copernicus products): [https://opentopography.org](https://opentopography.org)

After download, clip/reproject to a projected CRS (meters) before running this model.

## Next upgrades (recommended)

- Replace baseline templates with authority-grade Singapore depth-frequency datasets
- Add hazard-specific masks (coastline, drainage basins, river corridors)
- Monte Carlo uncertainty for level factors and AR6 percentiles
- Couple with a 2D solver (HEC-RAS 2D, LISFLOOD-FP, TELEMAC) for dynamic simulation
