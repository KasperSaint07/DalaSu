# DAL-29: NDVI source selection and Earth Engine export

## Status

The self-contained script is `scripts/gee/export_ndvi_us_ne2.js` (v1.0.0).
The user successfully executed the export in Chrome on 2026-10-30. All three
exports are now present and validated: 475 scenes, 280 usable scenes, 142 unique
usable dates. All ten annual rows match an independent local recalculation.
See `reports/ndvi_coverage.md` and run `python3 scripts/validate_ndvi.py` to repeat
the checks. A second independent GEE run has not been compared numerically.

## Source decision

Use Landsat 8 and 9 Collection 2, Tier 1, Level 2 surface reflectance:

- `LANDSAT/LC08/C02/T1_L2`: available from March 2013; provides the full requested time span.
- `LANDSAT/LC09/C02/T1_L2`: available from October 2021; adds observations in later years.

Both have 30 m optical pixels and a nominal 16-day revisit per satellite. Actual
clear-sky coverage at the station must be measured, not inferred from nominal revisit.
Export the satellite identifier to make the change in sampling density visible.

| Alternative | Reason for not selecting it for this historical extraction |
| --- | --- |
| Sentinel-2 SR Harmonized (`COPERNICUS/S2_SR_HARMONIZED`) | Red/NIR pixels are 10 m, but the SR collection begins in March 2017 and cannot supply 2015–2016. This is a statement about the SR collection, not all Sentinel-2 products. |
| MODIS MOD13Q1 v6.1 (`MODIS/061/MOD13Q1`) | Covers the period but has 250 m pixels and 16-day composites. A 100 m-radius buffer is smaller than one nominal MODIS pixel; mixed land cover is a substantial concern. Composite start dates also are not individual acquisition dates. |

This is a historical US-Ne2 source choice. It does not prevent later use of
Sentinel-2 for the application's contemporary Kazakhstan field monitoring.

## Region and fixed parameters

The user supplied latitude 41.1649, longitude -96.4701. GEE takes coordinates in
**longitude, latitude** order: `[-96.4701, 41.1649]`.

The script constructs a geodesic 100 m-radius buffer (1 m geometry error margin),
approximately 3.14 ha or 35 nominal 30 m pixel areas. This is a pragmatic starting
region, not an empirically optimal radius. It reduces mixing compared with a much
larger buffer, but may still contain roads, structures or adjacent fields.
It is neither a surveyed field boundary nor the weather-dependent eddy-covariance
footprint. Coordinates have not been independently surveyed or verified here.
Inspect the displayed region in the Code Editor satellite basemap before export.
If needed, compare radii 60, 100 and 150 m with separate export names; do not choose
the radius based on held-out ET prediction scores.

- Interval: 2015-01-01 inclusive to 2025-01-01 exclusive.
- Grid: EPSG:32614, transform `[30, 0, 0, 0, -30, 0]`.
- Default nearest-neighbour sampling; no smoothing or temporal interpolation.
- Usable observation: at least 80% of the complete buffer's grid-weighted area
  has valid NDVI. This is a declared initial quality policy, not a validated optimum.

## Processing policy

Keep every intersecting candidate scene; do not reject by whole-scene cloud cover.
Mask QA_PIXEL bits 0–5 (fill, dilated cloud, cirrus, cloud, cloud shadow, snow).
Require QA_RADSAT == 0, conservatively rejecting all saturation and terrain occlusion.
Water is not separately removed; no additional aerosol QA filtering is applied.
Residual atmospheric contamination remains possible.

Scale red SR_B4 and NIR SR_B5 as `DN * 0.0000275 - 0.2` **before** computing NDVI.
The additive offset does not cancel in the denominator. Require both reflectances
in [0, 1] and their sum > 1e-6. Compute `(NIR - RED) / (NIR + RED)` explicitly.
Negative NDVI remains valid; negative reflectance is rejected by the stated policy.
No clipping of resulting NDVI is performed.

Report the area-weighted mean of pixel NDVI, not NDVI of mean reflectances.
Use the same fixed grid for numerator and denominator. Pixels outside scene
footprints or removed by masks count against the *entire* ROI area.
`valid_area_m2` is preferable to an integer pixel count because boundary pixels
contribute fractional area. `valid_fraction` is in [0, 1].

The raw export retains rejected scenes. A nonempty NDVI can coexist with
`is_usable=0` if valid coverage is below 80%. If no pixels remain, NDVI is blank,
valid area/fraction are zero, and is_usable is zero. Never turn blank NDVI into zero.
Rows are per scene; multiple scenes can share a date. Unique-date counts in the
annual export prevent overstating temporal coverage.

## Run and retrieve

1. Open https://code.earthengine.google.com/ and select the activated Cloud Project.
2. Create a new script and paste the complete contents of
   `scripts/gee/export_ndvi_us_ne2.js`. No uploaded assets or private imports are needed.
3. Click **Run**. Inspect the region, parameters, first rows and coverage table.
   If the console reports an error, resolve it before treating any results as final.
4. In **Tasks**, click **Run** and confirm each of the THREE table exports.
5. Wait until each task completes. Download files from Google Drive folder
   `DalaSu_DAL29`, retaining the originals without spreadsheet reformatting.
6. Place the results as follows:

| Export | Repository destination |
| --- | --- |
| `ndvi_us-ne2_landsat_2015_2024.csv` | `data/raw/ndvi_us-ne2_landsat_2015_2024.csv` |
| `ndvi_coverage_by_year.csv` | `reports/ndvi_coverage_by_year.csv` |
| `ndvi_us_ne2_run_metadata.geojson` | `data/geo/ndvi_us_ne2_run_metadata.geojson` |

Drive names can acquire suffixes on repeat runs: verify filenames and run timestamps.
The repository ignores other raw files but explicitly permits this NDVI CSV.
To include only the intended NDVI file in a later commit, stage it using:

```bash
git add data/raw/ndvi_us-ne2_landsat_2015_2024.csv
```

Do not stage unrelated raw data or all existing staged changes blindly.

## Output interpretation and acceptance checks

The scene table includes acquisition date/time in UTC, source asset ID, product ID,
collection ID, processing version/product generation metadata, satellite, NDVI,
valid area/fraction, usability, buffer radius, threshold, script version and run time.
UTC acquisition dates are preserved; any later join to station-local daily data
must document its time-zone policy. There is no daily imputation in this task.

The annual CSV must contain all ten years, even if a year has zero usable scenes.
It reports total/usable scene counts, sensor-specific usable counts, unique usable
dates, first/last usable dates, months without observations and the longest run of
calendar days without a usable observation. That last metric includes year edges;
a year with no observations has a 365/366-day gap, and adjacent observation dates
have zero intervening missing days.

After downloading, verify:

- source asset IDs are unique; dates lie within the configured interval;
- all nonempty NDVI values are in [-1, 1]; valid fractions are in [0, 1];
- usable rows have nonempty NDVI and meet the area threshold;
- annual counts and date summaries agree with the raw CSV;
- repeat execution agrees on image IDs and scientific values (within numerical
  precision); run timestamps are expected to differ;
- preserve original CSV, GeoJSON metadata and script revision together. The catalog
  can be reprocessed, so a collection version alone does not freeze input assets.

The actual coverage results and limitations are in `reports/ndvi_coverage.md`.
The GEE script also displays an observation scatter chart. This task does not
modify existing daily weather data, train/test splits or model training.

## Official references

- https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC08_C02_T1_L2
- https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC09_C02_T1_L2
- https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED
- https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13Q1
