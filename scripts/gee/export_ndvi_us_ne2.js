// DAL-29 v1.0.0 — paste this entire file into Google Earth Engine Code Editor.
// No private assets or imports. Run, then start ALL THREE exports in Tasks.
// ROI is a user-requested station buffer, NOT a verified field/flux footprint.
var CONFIG = {
  version: 'DAL-29-v1.0.0',
  longitude: -96.4701,
  latitude: 41.1649,
  bufferM: 100,
  start: '2015-01-01',
  endExclusive: '2025-01-01',
  crs: 'EPSG:32614', // UTM zone 14N; fixed common grid for both sensors.
  transform: [30, 0, 0, 0, -30, 0],
  minValidFraction: 0.80,
  driveFolder: 'DalaSu_DAL29'
};
var L8 = 'LANDSAT/LC08/C02/T1_L2';
var L9 = 'LANDSAT/LC09/C02/T1_L2';
var runUtc = ee.Date(Date.now()).format("yyyy-MM-dd'T'HH:mm:ss'Z'", 'UTC');
var station = ee.Geometry.Point([CONFIG.longitude, CONFIG.latitude]);
var roi = station.buffer(CONFIG.bufferM, 1);
var pixelArea = ee.Image.pixelArea();
function sumRegion(image) {
  return image.reduceRegion({
    reducer: ee.Reducer.sum(), geometry: roi,
    crs: CONFIG.crs, crsTransform: CONFIG.transform,
    maxPixels: 1000000, tileScale: 2
  });
}
var roiGridArea = ee.Number(sumRegion(pixelArea).get('area'));
function load(collectionId) {
  return ee.ImageCollection(collectionId)
    .filterBounds(roi).filterDate(CONFIG.start, CONFIG.endExclusive)
    .map(function(image) {
      return image.set('source_collection', collectionId)
        .set('source_image_id', image.id());
    });
}
// Do not filter by whole-scene cloud percentage: local ROI may still be clear.
var scenes = load(L8).merge(load(L9)).sort('system:time_start');
function sceneRow(item) {
  var image = ee.Image(item);
  // QA_PIXEL bits 0–5: fill, dilated cloud, cirrus, cloud, shadow, snow.
  var clear = image.select('QA_PIXEL').bitwiseAnd(63).eq(0);
  // Conservative: reject all saturation flags and terrain occlusion.
  clear = clear.and(image.select('QA_RADSAT').eq(0));
  var red = image.select('SR_B4').multiply(0.0000275).add(-0.2);
  var nir = image.select('SR_B5').multiply(0.0000275).add(-0.2);
  var denominator = nir.add(red);
  // Explicit physical-domain policy; do not silently clamp NDVI or reflectance.
  var physical = red.gte(0).and(red.lte(1))
    .and(nir.gte(0)).and(nir.lte(1)).and(denominator.gt(0.000001));
  var ndvi = nir.subtract(red).divide(denominator)
    .updateMask(clear.and(physical)).rename('ndvi');
  // Unmask outside the scene as well: denominator is always the FULL buffer.
  var valid = ndvi.mask().unmask(0, false);
  var sums = sumRegion(pixelArea.multiply(valid).rename('valid_area')
    .addBands(ndvi.unmask(0, false).multiply(pixelArea).rename('ndvi_area')));
  var area = ee.Number(sums.get('valid_area'));
  var fraction = area.divide(roiGridArea).max(0).min(1);
  var mean = ee.Algorithms.If(area.gt(0),
    ee.Number(sums.get('ndvi_area')).divide(area), null);
  var date = image.date();
  return ee.Feature(null, {
    site_id: 'US-Ne2',
    image_id: image.get('source_image_id'),
    product_id: image.get('LANDSAT_PRODUCT_ID'),
    satellite: image.get('SPACECRAFT_ID'),
    collection_id: image.get('source_collection'),
    processing_version: image.get('PROCESSING_SOFTWARE_VERSION'),
    product_generated: image.get('DATE_PRODUCT_GENERATED'),
    acquired_at_utc: date.format("yyyy-MM-dd'T'HH:mm:ss'Z'", 'UTC'),
    date: date.format('yyyy-MM-dd', 'UTC'),
    year: date.get('year'), month: date.get('month'),
    timestamp_ms: date.millis(),
    ndvi_mean: mean, valid_area_m2: area, valid_fraction: fraction,
    is_usable: ee.Number(ee.Algorithms.If(
      area.gt(0).and(fraction.gte(CONFIG.minValidFraction)), 1, 0)),
    buffer_m: CONFIG.bufferM, min_valid_fraction: CONFIG.minValidFraction,
    script_version: CONFIG.version, exported_at_utc: runUtc
  });
}
// A list map permits Image -> Feature conversion (ImageCollection.map does not).
var rows = ee.FeatureCollection(scenes.toList(scenes.size()).map(sceneRow))
  .sort('timestamp_ms');
var usable = rows.filter(ee.Filter.eq('is_usable', 1));
var coverage = ee.FeatureCollection(ee.List.sequence(2015, 2024).map(function(y) {
  y = ee.Number(y);
  var allYear = rows.filter(ee.Filter.eq('year', y));
  var good = usable.filter(ee.Filter.eq('year', y));
  var dates = ee.List(good.aggregate_array('date')).distinct().sort();
  var start = ee.Date.fromYMD(y, 1, 1);
  var end = start.advance(1, 'year');
  // Integer day positions; duplicate scenes on one day count as one observation.
  var positions = dates.map(function(d) { return ee.Date(d).difference(start, 'day'); });
  // Sentinels make no-observation years safe and include both year boundaries.
  var bounds = ee.List([-1]).cat(positions).add(end.difference(start, 'day'));
  var gaps = ee.List.sequence(1, bounds.size().subtract(1)).map(function(i) {
    i = ee.Number(i);
    return ee.Number(bounds.get(i)).subtract(ee.Number(bounds.get(i.subtract(1)))).subtract(1);
  });
  var missingMonths = ee.List.sequence(1, 12).removeAll(
    ee.List(good.aggregate_array('month')).distinct());
  return ee.Feature(null, {
    year: y, scenes_total: allYear.size(), scenes_usable: good.size(),
    landsat8_usable: good.filter(ee.Filter.eq('satellite', 'LANDSAT_8')).size(),
    landsat9_usable: good.filter(ee.Filter.eq('satellite', 'LANDSAT_9')).size(),
    unique_usable_dates: dates.size(),
    // Empty string for missing dates, not a fabricated date or zero NDVI.
    first_usable_date: dates.cat(['']).get(0),
    last_usable_date: ee.List(['']).cat(dates).get(dates.size()),
    months_without_usable: missingMonths.join(';'),
    max_consecutive_days_without_observation: gaps.reduce(ee.Reducer.max()),
    buffer_m: CONFIG.bufferM, min_valid_fraction: CONFIG.minValidFraction,
    script_version: CONFIG.version, exported_at_utc: runUtc
  });
}));
var metadata = ee.FeatureCollection([ee.Feature(roi, {
  site_id: 'US-Ne2', roi_type: 'approximate_station_buffer_not_field_boundary',
  coordinate_source: 'User supplied; not independently surveyed',
  longitude: CONFIG.longitude, latitude: CONFIG.latitude,
  buffer_m: CONFIG.bufferM, buffer_max_error_m: 1,
  start: CONFIG.start, end_exclusive: CONFIG.endExclusive,
  collections: L8 + ';' + L9, collection_version: 'Collection 2, Tier 1, Level 2',
  crs: CONFIG.crs, crs_transform: CONFIG.transform.join(','),
  min_valid_fraction: CONFIG.minValidFraction,
  qa_policy: 'QA_PIXEL bits 0-5 clear; QA_RADSAT == 0',
  reflectance_policy: 'DN*0.0000275-0.2; red/nir in [0,1]; sum > 1e-6',
  aggregation: 'area-weighted pixel NDVI mean on fixed 30m grid',
  roi_grid_area_m2: roiGridArea,
  script_version: CONFIG.version, exported_at_utc: runUtc
})]);
var prefix = 'ndvi_us-ne2_landsat_2015_2024';
Export.table.toDrive({
  collection: rows, description: prefix, folder: CONFIG.driveFolder,
  fileNamePrefix: prefix, fileFormat: 'CSV',
  selectors: ['site_id', 'image_id', 'product_id', 'satellite', 'collection_id',
    'processing_version', 'product_generated', 'acquired_at_utc', 'date',
    'year', 'month', 'timestamp_ms', 'ndvi_mean', 'valid_area_m2',
    'valid_fraction', 'is_usable', 'buffer_m', 'min_valid_fraction',
    'script_version', 'exported_at_utc']
});
Export.table.toDrive({
  collection: coverage, description: 'ndvi_coverage_by_year',
  folder: CONFIG.driveFolder, fileNamePrefix: 'ndvi_coverage_by_year',
  fileFormat: 'CSV',
  selectors: ['year', 'scenes_total', 'scenes_usable', 'landsat8_usable',
    'landsat9_usable', 'unique_usable_dates', 'first_usable_date',
    'last_usable_date', 'months_without_usable',
    'max_consecutive_days_without_observation', 'buffer_m',
    'min_valid_fraction', 'script_version', 'exported_at_utc']
});
Export.table.toDrive({
  collection: metadata, description: 'ndvi_us_ne2_run_metadata',
  folder: CONFIG.driveFolder, fileNamePrefix: 'ndvi_us_ne2_run_metadata',
  fileFormat: 'GeoJSON'
});
Map.centerObject(roi, 17);
Map.addLayer(roi, {color: '00FFFF'}, 'Approximate 100 m station buffer');
Map.addLayer(station, {color: 'FF0000'}, 'US-Ne2 supplied coordinate');
print('Run parameters', CONFIG);
print('All candidate scenes', scenes.size());
print('First rows (blank NDVI = no valid pixels)', rows.limit(10));
print('Annual coverage (all ten years)', coverage);
print(ui.Chart.feature.byFeature(usable, 'date', ['ndvi_mean'])
  .setChartType('ScatterChart').setOptions({
    title: 'US-Ne2: usable Landsat NDVI observations (no interpolation)',
    hAxis: {title: 'Acquisition date (UTC)'}, vAxis: {title: 'NDVI'}, pointSize: 3
  }));
