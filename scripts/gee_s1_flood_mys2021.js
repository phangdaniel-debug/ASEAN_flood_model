/**
 * Sentinel-1 SAR change-detection flood map -- KL / Selangor December 2021
 *
 * Paste into https://code.earthengine.google.com and click Run.
 * Then click Tasks tab -> Run to export to Google Drive.
 * Download s1_kl_flood_dec2021.tif and put it in:
 *   data/kl/flood_obs/MYS2021/s1_kl_flood_dec2021.tif
 *
 * Algorithm: per-pixel backscatter decrease (dB) between a pre-flood
 * baseline and the Dec 17-22 peak flood window. Pixels that drop more
 * than THRESH_DB are classified as flooded. Bypasses GFM urban exclusion.
 *
 * Pixel values: 1 = flood detected, 0 = not flooded, 255 = nodata
 *
 * Adjust THRESH_DB if results look over- or under-detected:
 *   -2 dB = aggressive (more flood pixels, more false positives)
 *   -3 dB = standard literature value (default)
 *   -5 dB = conservative (fewer false positives, may miss shallow floods)
 */

// -- Config ------------------------------------------------------------------
var KL_BBOX        = ee.Geometry.Rectangle([101.40, 2.90, 101.95, 3.42]);
var BASELINE_START = '2021-10-15';
var BASELINE_END   = '2021-12-15';   // pre-flood; avoids early Dec rainfall
var FLOOD_START    = '2021-12-17';
var FLOOD_END      = '2021-12-23';   // peak event; S-1B offline after Dec 23
var SCALE          = 20;             // metres -- matches GFM resolution
var THRESH_DB      = -3.0;           // dB; change this to adjust sensitivity

// -- Helper: build one S-1 IW VV collection ----------------------------------
function s1col(start, end, passDir) {
  return ee.ImageCollection('COPERNICUS/S1_GRD')
    .filterBounds(KL_BBOX)
    .filterDate(start, end)
    .filter(ee.Filter.eq('instrumentMode', 'IW'))
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
    .filter(ee.Filter.eq('orbitProperties_pass', passDir))
    .select('VV');
}

// -- Per-orbit flood mask -----------------------------------------------------
// GEE lazy eval: even if a collection is empty the median() returns an
// all-masked image, so subtraction and threshold give all-masked output.
// unmask(0) at the end turns those masked pixels to "not flooded".
function floodMaskForPass(passDir) {
  var base  = s1col(BASELINE_START, BASELINE_END, passDir).median();
  var flood = s1col(FLOOD_START,    FLOOD_END,    passDir).median();
  var diff  = flood.subtract(base);          // negative = backscatter drop
  return diff.lt(THRESH_DB)                  // 1 where drop > threshold
             .rename('flood')
             .unmask(0);                     // masked (no-data) pixels -> 0
}

// -- Build ASC + DESC union ----------------------------------------------------
var ascMask  = floodMaskForPass('ASCENDING');
var descMask = floodMaskForPass('DESCENDING');

// Union: flooded if either orbit detects it
var floodUnion = ascMask.Or(descMask).rename('flood');

// Pixels with no S-1 coverage at all remain 0 from unmask above, which is
// correct (we simply have no observation = assume not flooded).
// Cast to uint8 for compact GeoTIFF.
var combined = floodUnion.uint8().clip(KL_BBOX);

// -- Console output ------------------------------------------------------------
print('Threshold used:', THRESH_DB, 'dB');
print('Baseline:', BASELINE_START, '->', BASELINE_END);
print('Flood window:', FLOOD_START, '->', FLOOD_END);

// Count flood pixels and estimate area
var stats = combined.eq(1).reduceRegion({
  reducer: ee.Reducer.sum(),
  geometry: KL_BBOX,
  scale: SCALE,
  maxPixels: 1e9
});
var floodArea = ee.Number(stats.get('flood'))
                  .multiply(SCALE * SCALE)
                  .divide(1e6);
print('Flood pixels:', stats.get('flood'));
print('Flood area (km2):', floodArea);

// Count by orbit (diagnostic)
print('ASC  flood px:', ascMask.eq(1).reduceRegion({
  reducer: ee.Reducer.sum(), geometry: KL_BBOX, scale: SCALE, maxPixels: 1e9
}).get('flood'));
print('DESC flood px:', descMask.eq(1).reduceRegion({
  reducer: ee.Reducer.sum(), geometry: KL_BBOX, scale: SCALE, maxPixels: 1e9
}).get('flood'));

// -- Map visualisation ---------------------------------------------------------
Map.centerObject(KL_BBOX, 10);

// Pre/post backscatter (both orbits combined, for visual inspection)
var s1all = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(KL_BBOX)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .select('VV');

Map.addLayer(
  s1all.filterDate(BASELINE_START, BASELINE_END).median().clip(KL_BBOX),
  {min: -25, max: 0, palette: ['black', 'white']},
  'S-1 VV baseline (pre-flood)', false
);
Map.addLayer(
  s1all.filterDate(FLOOD_START, FLOOD_END).median().clip(KL_BBOX),
  {min: -25, max: 0, palette: ['black', 'white']},
  'S-1 VV flood peak (Dec 17-22)', false
);
Map.addLayer(
  s1all.filterDate(FLOOD_START, FLOOD_END).median()
       .subtract(s1all.filterDate(BASELINE_START, BASELINE_END).median())
       .clip(KL_BBOX),
  {min: -10, max: 5, palette: ['blue', 'white', 'red']},
  'Backscatter change (blue = drop = flood)', false
);
Map.addLayer(
  combined.selfMask(),
  {palette: ['0066FF'], opacity: 0.75},
  'Flood detected (S-1 change, thresh=' + THRESH_DB + ' dB)'
);

// -- Export to Drive -----------------------------------------------------------
Export.image.toDrive({
  image: combined,
  description: 's1_kl_flood_dec2021',
  folder: 'GEE_exports',
  fileNamePrefix: 's1_kl_flood_dec2021',
  region: KL_BBOX,
  scale: SCALE,
  crs: 'EPSG:4326',
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF'
});
print('Export task created -- click Tasks tab, then Run.');
