          Copernicus GFM -- December 2021 Malaysia Flood (MYS2021)
          ========================================================
          Source   : EODC STAC API (https://stac.eodc.eu/api/v1)
          Collection: GFM (Global Flood Monitoring, ensemble product)
          Asset    : ensemble_flood_extent
          Event    : December 2021 Selangor/KL flood
            Tropical Depression 29 made landfall 16 Dec 2021
            Peak displacement: 17-22 Dec 2021 (~70,000 evacuated)
          Domain   : KL pipeline bbox (101.4, 2.9, 101.95, 3.42)

          Sentinel-1 acquisition dates:
            2021-12-16
2021-12-19
2021-12-20
2021-12-21
2021-12-22

          Composite file: gfm_kl_composite_dec2021.tif
            Pixel = 1 (flood) if flooded in ANY Dec 17-22 pass.
            Pixel = 255 (nodata) if excluded in all passes.
            Pixel = 0 otherwise (not flooded).

          Pixel values in raw/gfm_kl_*.tif:
            0 = not flooded
            1 = observed flood extent
            2 = permanent/seasonal water
            3 = excluded (cloud, layover, shadow)
            255 = nodata

          CRS: EPSG:4326  |  Resolution: ~20 m
          Projection: Equi7Grid (original) -> reprojected to WGS84

          Urban exclusion limitation:
            GFM excludes ~69% of the KL bbox via urban masking (SAR
            double-bounce from buildings). Composite flood pixels = 345
            (~0.14 km2). Usable only for peri-urban / agricultural areas.

          Use for R4 historical validation (partial):
            validate_historical_events.py --city kuala_lumpur                 --event MYS2021                 --obs-file data/kl/flood_obs/MYS2021/gfm_kl_composite_dec2021.tif

          Citation: Copernicus Emergency Management Service (CEMS),
            Global Flood Monitoring (GFM) product.
            https://global-flood.emergency.copernicus.eu/
