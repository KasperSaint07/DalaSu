# DAL-31: Hybrid + NDVI validation

## Experiment

Training: 2407 rows, 2015–2022; holdout: 561 canonical dates, 2023–2024.
Eight v0 features plus exactly two NDVI features, no ET0 predictor.
Residual target and ET0 reconstruction unchanged. Both models use nested
TimeSeriesSplit (5 outer / 4 inner), 16 candidates, MAE selection, seed 42.
Median imputation is fitted within each CV training fold, including inner folds.
The 13 initially missing NDVI rows are retained. NDVI provenance is excluded.
The holdout is read after both final fits. The baseline is the saved DAL-28 v0
model, re-exported without retraining or changing its predictions.

## Held-out comparison

Errors and bias are in mm/day; r² is squared Pearson correlation.

| Model | MAE | RMSE | Bias | r² | NSE | KGE |
|---|---:|---:|---:|---:|---:|---:|
| hybrid_rf | 0.431587 | 0.624450 | 0.103893 | 0.863123 | 0.852487 | 0.899020 |
| hybrid_ndvi_rf | 0.414459 | 0.601038 | 0.112970 | 0.874159 | 0.863340 | 0.898176 |
| hybrid_xgb | 0.412442 | 0.600067 | 0.087806 | 0.872575 | 0.863782 | 0.910152 |
| hybrid_ndvi_xgb | 0.387753 | 0.556918 | 0.106872 | 0.894998 | 0.882667 | 0.902371 |

## Вывод о вкладе NDVI

На 561 общей тестовой дате US-Ne2 за 2023–2024 добавление ndvi_last и ndvi_age_days улучшило Hybrid относительно v0: MAE RF снизилась с 0,431587 до 0,414459 мм/день (на 3,97%), MAE XGBoost — с 0,412442 до 0,387753 мм/день (на 5,99%); RMSE снизилась соответственно с 0,624450 до 0,601038 и с 0,600067 до 0,556918 мм/день. При этом положительный bias вырос у обеих моделей, а KGE немного снизился, поэтому улучшение не охватывает все метрики. Hybrid + NDVI XGBoost также превзошёл сохранённый ML-only XGBoost по MAE и RMSE, тогда как RF остался немного хуже ML-only RF. Результат показывает полезный вклад двух NDVI-признаков в этом эксперименте с повторным подбором параметров, но не доказывает статистическую значимость или переносимость на другие станции и годы; настройки не выбирались по тестовым метрикам.

## Reproducibility

Two independent full training runs completed in the same environment.
All 12 metric checks passed the predeclared absolute tolerance of 1e-6;
maximum observed difference: 0. Run metadata, input hashes,
best parameters and library versions match exactly. This tolerance applies
within the recorded environment, not arbitrarily different library/platform versions.
94 tests passed, including fold-local imputation, NDVI missingness and ranges,
RF/XGBoost serialization, chronology and the prediction export contract.

## Evidence

- `hybrid_ndvi_deltas.csv`: unrounded pairwise differences (NDVI minus v0).
- `hybrid_ndvi_reproducibility.json`: per-model, per-metric repeat-run audit.
- `hybrid_ndvi_repeat/`: second-run predictions, CV/test scores and run metadata.
- `hybrid_ndvi_cv_fold_metrics.csv`: first-run fold metrics and selected parameters.
- `../models/hybrid_ndvi/hybrid_metadata.json`: first-run configuration and input hashes.
- `comparison_metrics.csv` and `fao56_ml_comparison.md`: common seven-model comparison.

Commands and acceptance policy are in the README DAL-31 section. The saved
repeat evidence can be checked without retraining:

```bash
PYTHONPATH=src python -m ml.evaluation.check_reproducibility \
  reports reports/hybrid_ndvi_repeat \
  --output /tmp/dal31-recheck.json
```
