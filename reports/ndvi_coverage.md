# DAL-29: observed NDVI coverage and validation

## Result

The user executed the GEE export successfully in Chrome and supplied all three
original exports. Export timestamp: **2026-10-30T09:48:36Z**.
Local validation independently recalculated all ten annual rows from the scene CSV.
All checks passed. No observations were altered, filled or removed.

- Candidate scenes: **475**.
- Usable scenes (at least 80% valid buffer area): **280** (58.9%).
- Unique usable acquisition dates: **142**.
- Blank NDVI rows: **185**.
- Nonempty NDVI range, including low-coverage scenes: **0.150186–0.922920**.
- ROI: 100 m approximate buffer around longitude -96.4701, latitude 41.1649.
- Grid-weighted ROI area: 31275.043 m²; EPSG:32614 at 30 m.
- Collections: LANDSAT/LC08/C02/T1_L2 and LANDSAT/LC09/C02/T1_L2,
  Collection 2, Tier 1, Level 2; script version DAL-29-v1.0.0.

## Annual coverage

Usable dates, not scene counts, measure temporal coverage. Months are numbered
1–12. The maximum gap counts consecutive calendar days without a usable
observation, including the beginning and end of each year.

| Year | All scenes | Usable scenes | Usable dates | Max gap (days) | Months with no usable dates |
| --- | --- | --- | --- | --- | --- |
| 2015 | 31 | 18 | 9 | 79 | 2, 5, 7, 10, 11 |
| 2016 | 36 | 14 | 7 | 187 | 1, 7, 8, 9, 10, 11, 12 |
| 2017 | 41 | 28 | 14 | 47 | 3 |
| 2018 | 32 | 12 | 6 | 95 | 1, 2, 4, 8, 9, 11, 12 |
| 2019 | 33 | 22 | 11 | 74 | 1, 2, 11 |
| 2020 | 33 | 26 | 13 | 47 | 12 |
| 2021 | 39 | 18 | 10 | 79 | 1, 2, 4, 5 |
| 2022 | 79 | 55 | 28 | 47 | None |
| 2023 | 73 | 37 | 19 | 39 | 1 |
| 2024 | 78 | 50 | 25 | 39 | 3 |

## Interpretation and limits

All ten years contain usable observations, but this is not continuous or daily
coverage. In 2016 only seven dates pass the policy, the last on June 27; July
through December have none, producing a 187-day gap. In 2018 only six dates pass,
with a maximum 95-day gap. These gaps cannot support an assumption of regularly
observed canopy development. The export does not isolate which quality mask
caused each rejection; it would be unjustified to attribute every gap to clouds.

Many dates have adjacent WRS scene rows (028031 and 028032) from the same satellite
pass. They are distinct products, not duplicate scene identifiers, and their
NDVI estimates can differ. Do not treat them as independent daily samples when
joining weather/ET data. A later task must choose a documented daily aggregation
rule and handle missing observations without future-data leakage. No such join,
interpolation or model retraining is included here.

Landsat 9 supplements the record from 2021 onward. Temporal density is therefore
unequal across years. Winter gaps and growing-season gaps should not be treated
as equally informative; long summer gaps are particularly relevant to canopy
features. This buffer is neither a verified field boundary nor a dynamic flux
footprint. No independent geographic validation or radius sensitivity analysis
has been performed. NDVI is a vegetation signal, not a direct ET measurement.

## Validation and reproduction

Run from any directory:

```bash
python3 scripts/validate_ndvi.py
```

(Use an absolute script path when running outside the repository.) The validator
uses only the Python standard library, raises an error on a failed check, and
rebuilds this report and the checksum manifest only after successful validation.
Checks include unique IDs/products; chronological timestamps and date bounds;
collection/site/run metadata; finite NDVI and area ranges; area-to-fraction
consistency; missing-value and usability rules; and every annual coverage field.

GEE reproduction instructions and source rationale are in
`docs/12-ndvi-source-selection.md`. The original export retains short image IDs;
combine `collection_id + '/' + image_id` to resolve each asset. The supplied
export proves a successful run, but an independent second GEE execution and
numerical repeatability comparison have **not** been performed. Local consistency
checks do not independently recompute reflectance or validate the cloud mask.

The user's minimal GEE calls failed in Safari but succeeded in Chrome. Use Chrome
for the documented workflow; this observation does not establish a universal
Safari incompatibility.

## Files

- `data/raw/ndvi_us-ne2_landsat_2015_2024.csv`: unchanged original scene export.
- `reports/ndvi_coverage_by_year.csv`: byte-identical copy of the annual export.
- `data/geo/ndvi_us_ne2_run_metadata.geojson`: byte-identical geometry/run metadata.
- `reports/ndvi_checksums.json`: SHA-256 checksums for these three inputs.
- `scripts/gee/export_ndvi_us_ne2.js`: self-contained export code.

Source selection, raw export with acquisition dates, annual coverage and collection
version are delivered. The repeat-run comparison remains an explicitly recorded
verification limitation. Git commit/PR creation is not part of this validation run.
