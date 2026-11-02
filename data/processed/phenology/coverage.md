# Phenology label coverage — US-Ne2

Actual agronomic stages and NDVI proxies are separate. An approximate label is not field validation.

Calendar coverage: 731 days. Canonical test coverage: 561 dates. The other 170 calendar days have no retained ET test observation; no ET is filled.

| Year | Test dates | Observed stages | NDVI proxies | Unknown final labels | Unknown actual stages |
|---|---:|---:|---:|---:|---:|
| 2023 | 279 | 0 | 149 | 130 | 279 |
| 2024 | 282 | 0 | 202 | 80 | 282 |

## Label counts on test dates

| Year | Label | Count |
|---|---|---:|
| 2023 | proxy_decline | 35 |
| 2023 | proxy_greenup | 19 |
| 2023 | proxy_high_vegetation | 65 |
| 2023 | proxy_low_vegetation | 30 |
| 2023 | unknown | 130 |
| 2024 | proxy_decline | 23 |
| 2024 | proxy_greenup | 17 |
| 2024 | proxy_high_vegetation | 43 |
| 2024 | proxy_low_vegetation | 119 |
| 2024 | unknown | 80 |

## Missing or ambiguous proxy evidence

| Year | Reason | Count |
|---|---|---:|
| 2023 | ambiguous_midrange | 68 |
| 2023 | high_training_quantile | 65 |
| 2023 | low_training_quantile | 30 |
| 2023 | negative_ndvi_change | 35 |
| 2023 | positive_ndvi_change | 19 |
| 2023 | stale_snapshot | 12 |
| 2023 | trend_gap_too_large | 50 |
| 2024 | ambiguous_midrange | 74 |
| 2024 | high_training_quantile | 43 |
| 2024 | low_training_quantile | 119 |
| 2024 | negative_ndvi_change | 23 |
| 2024 | positive_ndvi_change | 17 |
| 2024 | stale_snapshot | 6 |

## Frozen rule fit

- Low threshold: 0.21829911; high: 0.70156933.
- Training: 98 unique selected snapshots, 2015-01-16 through 2022-12-29.
- No test ET, model predictions or errors are used; no stage-error comparison is performed here.
- Source audit and rule definitions: [method](../../../docs/14-phenology-labels.md).
- Unknown runs and all non-overlapping calendar intervals: label_intervals.csv.
- Full actual-stage coverage: False. Do not claim actual-stage analysis is complete when evidence is missing.
