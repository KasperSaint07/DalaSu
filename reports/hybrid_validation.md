# DAL-28 validation results

All models evaluated on the same 561 held-out dates (2023--2024).
ML-only artifacts were re-evaluated locally without retraining.
Errors are in mm/day.

| Model | Days | MAE | RMSE | Bias |
|---|---:|---:|---:|---:|
| FAO-56 ET0 | 561 | 1.113261 | 1.643921 | 0.917452 |
| Random Forest ML-only | 561 | 0.411629 | 0.588497 | 0.125245 |
| XGBoost ML-only | 561 | 0.398492 | 0.595494 | 0.118865 |
| Hybrid rf | 561 | 0.431587 | 0.624450 | 0.103893 |
| Hybrid xgb | 561 | 0.412442 | 0.600067 | 0.087806 |

The default eight-feature hybrids improve on the physical baseline but do not
outperform the corresponding ML-only models in MAE. Hybrid bias is lower.
No hyperparameters or feature modes were selected using these holdout scores.
The optional ET0 feature mode is covered by integration tests; a full search
for that additional experiment was not performed.

Both exported CSV files passed exact date alignment, reconstruction and
saved-model prediction checks. Training used 2407 rows from 2015--2022,
nested TimeSeriesSplit 5 x 4, 16 candidates and seed 42.
