"""Validate DAL-29 exports and rebuild the coverage report (standard library only)."""
import csv
import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/ndvi_us-ne2_landsat_2015_2024.csv'
COVERAGE = ROOT / 'reports/ndvi_coverage_by_year.csv'
META = ROOT / 'data/geo/ndvi_us_ne2_run_metadata.geojson'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    with RAW.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    with COVERAGE.open(newline='') as handle:
        yearly = list(csv.DictReader(handle))
    geo = json.loads(META.read_text())
    require(len(geo['features']) == 1, 'Expected one ROI')
    feature = geo['features'][0]
    meta = feature['properties']
    require(feature['geometry']['type'] == 'Polygon', 'Expected polygon ROI')
    ring = feature['geometry']['coordinates'][0]
    require(ring[0] == ring[-1], 'Polygon must be closed')
    require(meta['latitude'] == 41.1649 and meta['longitude'] == -96.4701,
            'Unexpected station coordinates')
    require(meta['buffer_m'] == 100 and meta['min_valid_fraction'] == 0.8,
            'Unexpected buffer or threshold')
    collections = {'LANDSAT_8': 'LANDSAT/LC08/C02/T1_L2',
                   'LANDSAT_9': 'LANDSAT/LC09/C02/T1_L2'}
    require(set(meta['collections'].split(';')) == set(collections.values()),
            'Unexpected collection metadata')
    require(meta['start'] == '2015-01-01' and meta['end_exclusive'] == '2025-01-01',
            'Unexpected date bounds')
    require(meta['crs'] == 'EPSG:32614' and meta['crs_transform'] == '30,0,0,0,-30,0',
            'Unexpected analysis grid')
    require(rows and len({r['image_id'] for r in rows}) == len(rows),
            'Missing or duplicate scene IDs')
    require(len({r['product_id'] for r in rows}) == len(rows), 'Duplicate product IDs')
    timestamps = []
    for r in rows:
        label = r['image_id']
        d = date.fromisoformat(r['date'])
        require(date(2015, 1, 1) <= d < date(2025, 1, 1), label + ': date range')
        require(int(r['year']) == d.year and int(r['month']) == d.month,
                label + ': date components')
        timestamp = int(r['timestamp_ms'])
        timestamps.append(timestamp)
        acquired = datetime.fromisoformat(r['acquired_at_utc'].replace('Z', '+00:00'))
        require(acquired.date() == d and
                abs(timestamp / 1000 - acquired.timestamp()) < 1,
                label + ': acquisition timestamp mismatch')
        require(r['satellite'] in collections and
                r['collection_id'] == collections[r['satellite']], label + ': collection')
        require(r['site_id'] == 'US-Ne2' and r['processing_version'] and r['product_id'],
                label + ': provenance')
        for key in ['script_version', 'exported_at_utc']:
            require(r[key] == meta[key], label + ': inconsistent ' + key)
        require(float(r['buffer_m']) == meta['buffer_m'] and
                float(r['min_valid_fraction']) == meta['min_valid_fraction'],
                label + ': inconsistent ROI policy')
        fraction, area = float(r['valid_fraction']), float(r['valid_area_m2'])
        require(math.isfinite(fraction) and 0 <= fraction <= 1, label + ': valid fraction')
        require(math.isfinite(area) and 0 <= area <= meta['roi_grid_area_m2'] + 1e-6,
                label + ': valid area')
        require(math.isclose(fraction, area / meta['roi_grid_area_m2'], abs_tol=1e-9),
                label + ': area/fraction mismatch')
        value = float(r['ndvi_mean']) if r['ndvi_mean'] else None
        require((value is None) == (area == 0), label + ': missing NDVI/area mismatch')
        require(value is None or (math.isfinite(value) and -1 <= value <= 1),
                label + ': NDVI range')
        require(r['is_usable'] in ('0', '1'), label + ': invalid flag')
        require(int(r['is_usable']) == int(value is not None and fraction >= 0.8),
                label + ': usability mismatch')
    require(timestamps == sorted(timestamps), 'Scenes are not chronologically ordered')
    require(len(yearly) == 10 and {int(float(r['year'])) for r in yearly} == set(range(2015, 2025)),
            'Expected one coverage row per year, 2015–2024')
    table = []
    for record in yearly:
        year = int(float(record['year']))
        all_rows = [r for r in rows if int(r['year']) == year]
        good = [r for r in all_rows if r['is_usable'] == '1']
        dates = sorted({date.fromisoformat(r['date']) for r in good})
        start, end = date(year, 1, 1), date(year + 1, 1, 1)
        positions = [-1] + [(d - start).days for d in dates] + [(end - start).days]
        gap = max(b - a - 1 for a, b in zip(positions, positions[1:]))
        missing = set(range(1, 13)) - {d.month for d in dates}
        expected = {'scenes_total': len(all_rows), 'scenes_usable': len(good),
                    'unique_usable_dates': len(dates),
                    'landsat8_usable': sum(r['satellite'] == 'LANDSAT_8' for r in good),
                    'landsat9_usable': sum(r['satellite'] == 'LANDSAT_9' for r in good),
                    'max_consecutive_days_without_observation': gap}
        for key, value in expected.items():
            require(float(record[key]) == value, f'{year}: {key} mismatch')
        require(record['first_usable_date'] == (dates[0].isoformat() if dates else '') and
                record['last_usable_date'] == (dates[-1].isoformat() if dates else ''),
                f'{year}: date bounds mismatch')
        actual_missing = {int(float(x)) for x in record['months_without_usable'].split(';') if x}
        require(actual_missing == missing, f'{year}: missing months mismatch')
        for key in ['script_version', 'exported_at_utc']:
            require(record[key] == meta[key], f'{year}: {key} mismatch')
        require(float(record['buffer_m']) == meta['buffer_m'] and
                float(record['min_valid_fraction']) == meta['min_valid_fraction'],
                f'{year}: ROI policy mismatch')
        table.append(f"| {year} | {len(all_rows)} | {len(good)} | {len(dates)} | {gap} | "
                     + (', '.join(map(str, sorted(missing))) or 'None') + ' |')
    good = [r for r in rows if r['is_usable'] == '1']
    values = [float(r['ndvi_mean']) for r in rows if r['ndvi_mean']]
    count_dates = len({r['date'] for r in good})
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [RAW, COVERAGE, META]}
    report = f'''# DAL-29: observed NDVI coverage and validation

## Result

The user executed the GEE export successfully in Chrome and supplied all three
original exports. Export timestamp: **{meta['exported_at_utc']}**.
Local validation independently recalculated all ten annual rows from the scene CSV.
All checks passed. No observations were altered, filled or removed.

- Candidate scenes: **{len(rows)}**.
- Usable scenes (at least 80% valid buffer area): **{len(good)}** ({len(good)/len(rows):.1%}).
- Unique usable acquisition dates: **{count_dates}**.
- Blank NDVI rows: **{sum(not r['ndvi_mean'] for r in rows)}**.
- Nonempty NDVI range, including low-coverage scenes: **{min(values):.6f}–{max(values):.6f}**.
- ROI: 100 m approximate buffer around longitude -96.4701, latitude 41.1649.
- Grid-weighted ROI area: {meta['roi_grid_area_m2']:.3f} m²; EPSG:32614 at 30 m.
- Collections: LANDSAT/LC08/C02/T1_L2 and LANDSAT/LC09/C02/T1_L2,
  Collection 2, Tier 1, Level 2; script version {meta['script_version']}.

## Annual coverage

Usable dates, not scene counts, measure temporal coverage. Months are numbered
1–12. The maximum gap counts consecutive calendar days without a usable
observation, including the beginning and end of each year.

| Year | All scenes | Usable scenes | Usable dates | Max gap (days) | Months with no usable dates |
| --- | --- | --- | --- | --- | --- |
''' + '\n'.join(table) + '''

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
'''
    (ROOT / 'reports/ndvi_coverage.md').write_text(report)
    (ROOT / 'reports/ndvi_checksums.json').write_text(json.dumps(hashes, indent=2) + '\n')
    print(f'PASS: {len(rows)} scenes; {len(good)} usable scenes; {count_dates} usable dates; all 10 annual rows match.')


if __name__ == '__main__':
    main()
