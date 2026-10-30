# DAL-30: backward-only daily NDVI features

## Reproduce

From the repository root, with the project's Python environment available:

```bash
python src/ml/data/build_ndvi.py
```

This reads `data/processed/daily.csv` and the unchanged DAL-29 scene CSV,
then writes `data/processed/ndvi/{daily,train,test}.csv` and
`ndvi_build_report.json`. No GEE access or hourly data download is needed.
The original weather/ET dataset is preserved. The report records input SHA-256
hashes, policy version, station, calendar offset, row counts and missingness.
Identical inputs and arguments produce byte-identical outputs at the same paths.

Full hourly reconstruction also supports the same feature implementation:

```bash
python src/ml/data/build_daily.py \
  --fluxnet-input /path/to/US-Ne2_FLUXNET_FLUXMET_HR.csv \
  --precip-input /path/to/US-Ne2_BASE_HR.csv \
  --ndvi-input data/raw/ndvi_us-ne2_landsat_2015_2024.csv \
  --output-dir data/processed/ndvi
```

Omitting `--ndvi-input` preserves the original hourly-builder behavior.
The existing model feature lists are unchanged; training on NDVI and handling
missing features inside an estimator pipeline are subsequent work.

## Architecture and extension points

- `ndvi.py`: immutable normalized `Observation`, DAL-29 CSV adapter, and pure
  backward join. No file writes or model dependencies in the join.
- `build_ndvi.py`: input validation, reproducible output, and existing US-Ne2
  chronological split policy. This CLI deliberately processes one station at a time.
- `build_daily.py`: optional integration after hourly aggregation, before splitting.

The join indexes each site separately and uses binary search per daily row.
It preserves input row order and does not mutate inputs. A new satellite adapter
can emit the same normalized observations without changing the join. Mixed-site
rows are supported by the core through `site_id`; the CLI requires one matching
station. For additional stations, supply the station ID and its fixed standard-time
offset, and configure a separate dataset/split pipeline. The hourly builder's
weather schema and date range remain specific to US-Ne2; this task does not
claim a universal multi-station ingestion system.

## Selection and quality policy

The adapter checks required columns, scene identity uniqueness per site, UTC
timestamp/date consistency, finite NDVI in [-1, 1], and valid coverage fractions.
Only `is_usable=1` scenes enter the index. Such scenes must have nonempty NDVI
and meet their exported `min_valid_fraction`. Inconsistent usable rows fail;
rejected scenes cannot overwrite the last usable observation.

Within each station/calendar date, choose greatest `valid_fraction`, then latest
acquisition timestamp, then lexicographically greatest `image_id`. This resolves
adjacent Landsat scenes reproducibly without treating them as independent daily
samples or averaging overlapping pixels. Input file order is irrelevant.

For daily date D, select the latest observation with snapshot date <= D.

| Column | Meaning |
| --- | --- |
| `ndvi_last` | Selected scene's NDVI, without additional rounding |
| `ndvi_age_days` | Integer calendar days since the selected observation |
| `snapshot_date` | Selected observation's station-calendar date |
| `ndvi_image_id` | Scene ID for tracing back to the immutable DAL-29 input |

No future interpolation, backward fill, zero imputation, or expiration threshold
is used. Until the first usable observation all four fields are empty CSV cells
(read as missing values by pandas). Rows remain present. Across long gaps the
last NDVI remains unchanged while its age increases. Never treat an empty cell
as NDVI=0 or age=0.

## Calendar and causal scope

US-Ne2 uses a fixed UTC-6 station-standard-time calendar in this pipeline, without
DST; the CLI exposes `--utc-offset-hours` (default -6). Acquisition timestamps are
converted to this calendar before selecting days. Daily weather dates remain as
supplied by the existing builder. All usable scenes in the current export fall on
the same UTC and UTC-6 date, verified by a regression test. Confirm the hourly
product's time convention when substituting source products.

This is a retrospective daily feature with same-day observations allowed by the
issue's `snapshot_date <= date` requirement. It does not establish that an image
was published or available before a particular morning forecast. Operational
forecasting requires an availability timestamp and an explicit prediction cutoff.
Historical collection reprocessing is also outside this acquisition-date guarantee.

Features are attached before the existing chronological split (train 2015–2022;
test 2023–2024). Using a 2022 observation in early 2023 is valid. Within test, newer
observations become usable as their dates are reached. No target values or fitted
statistics are used by the join.

## Verified result

The current inputs produce 2,968 daily rows: 2,407 train and 561 test.
The first usable snapshot is 2015-01-16. Thirteen retained daily rows before it
have missing NDVI (the weather dataset does not retain every calendar day).
Maximum snapshot age is 207 days, including a gap across a year boundary.
These stale values are deliberately exposed through age, not hidden by filling.

The real-data test checks every row against an independent latest-scene selection,
original column preservation, train/test concatenation, dates, ages and provenance.
Other tests cover missing starts, empty histories, same-day matches, long gaps,
scene ties, site isolation, invalid quality, future-data invariance and hourly CLI
integration. Run:

```bash
python -m pytest tests/test_ndvi.py -q
python -m pytest -q
```

Full production hourly reconstruction was not run: original AmeriFlux hourly
files were not present in `data/raw`. Its CLI integration is tested with synthetic
complete daily intervals. The real DAL-30 build uses the existing processed daily
file and the actual DAL-29 export.

## Input safety and adapter contract

Both dataset entry points check all input/output paths before writing. Resolved
paths, symbolic links and existing hard links must not alias inputs or other
outputs. This includes the NDVI build report in the enrichment entry point.
Daily and exported scene dates must be canonical `YYYY-MM-DD`; ISO week dates
and compact dates are rejected. The enrichment builder also checks that train
and test concatenate to the complete daily dataset before writing any output.

Normalized `Observation` instances validate nonempty station/scene IDs, finite
NDVI and coverage ranges, timezone-aware acquisition timestamps, and agreement
between the observation day and acquisition time in an explicit fixed-offset
calendar (`utc_offset_hours`, default UTC). New adapters must provide the station
calendar offset when their day differs from UTC. These invariants apply even
when an adapter bypasses the DAL-29 CSV reader.
