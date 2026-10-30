# FAO-56, ML-only and Hybrid comparison

## Setup and decision D-1

The common target is **measured actual evapotranspiration**, `et_obs_mm`, from
AmeriFlux US-Ne2. The evaluation uses the untouched 2023-01-01--2024-12-31 test split;
all models are scored on the same 561 daily observations. Random Forest
and XGBoost were fitted on 2015--2022 only. Metrics use observations first and
predictions second; positive bias means overestimation. Here `r²` is squared
Pearson correlation, as implemented in `src/ml/evaluation/metrics.py`; NSE is
the Nash--Sutcliffe efficiency and KGE the Kling--Gupta efficiency (Gupta et
al. 2009).

Each model is read from `reports/predictions_<model>.csv` with columns
`date,y_obs,y_pred`; the comparison stops with an error unless all files cover
identical dates.

**D-1: actual ET is the comparison target.** FAO-56 Penman--Monteith produces
grass reference evapotranspiration ET0, not crop actual ET. We deliberately use
ET0 without a crop coefficient (`Kc`) as the physical baseline and compare it
with measured actual ET. Therefore its error includes the ET0-to-actual-ET
mismatch and should not be interpreted as a validation of the FAO-56 equation
itself. Wind measured at 6.2 m is converted to 2 m with FAO-56 Eq. 47.

## Held-out metrics

| Model | File | n | RMSE, mm/day | MAE, mm/day | r² | Bias, mm/day | NSE | KGE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| FAO-56 ET0 | `predictions_fao56_et0.csv` | 561 | 1.644 | 1.113 | 0.474 | 0.917 | -0.022 | 0.290 |
| Random Forest ML-only | `predictions_random_forest.csv` | 561 | 0.588 | 0.412 | 0.879 | 0.125 | 0.869 | 0.894 |
| XGBoost ML-only | `predictions_xgboost.csv` | 561 | 0.595 | 0.398 | 0.879 | 0.119 | 0.866 | 0.894 |
| Hybrid + NDVI RF | `predictions_hybrid_ndvi_rf.csv` | 561 | 0.601 | 0.414 | 0.874 | 0.113 | 0.863 | 0.898 |
| Hybrid + NDVI XGBoost | `predictions_hybrid_ndvi_xgb.csv` | 561 | 0.557 | 0.388 | 0.895 | 0.107 | 0.883 | 0.902 |
| Hybrid v0 RF | `predictions_hybrid_rf.csv` | 561 | 0.624 | 0.432 | 0.863 | 0.104 | 0.852 | 0.899 |
| Hybrid v0 XGBoost | `predictions_hybrid_xgb.csv` | 561 | 0.600 | 0.412 | 0.873 | 0.088 | 0.864 | 0.910 |

Lower RMSE, MAE and absolute bias are better; higher `r²`, NSE and KGE are
better (NSE = KGE = 1 is a perfect fit). NSE below 0 means the model is worse
than predicting the observed mean.

## Conclusion

On the held-out period, **Hybrid + NDVI XGBoost** has the lowest MAE
(0.388 mm/day), a 65.2% reduction relative to
the FAO-56 ET0 baseline (1.113 mm/day). Models with lower RMSE
than the baseline: Random Forest ML-only, XGBoost ML-only, Hybrid + NDVI RF, Hybrid + NDVI XGBoost, Hybrid v0 RF, Hybrid v0 XGBoost. FAO-56 ET0 overestimates actual ET on
average (bias +0.917 mm/day, NSE -0.022), which
is consistent with using reference ET0 without seasonal crop coefficients. ET0
remains an interpretable physical reference.

## Reproduction

From the repository root, after `pip install -r requirements.txt` and
`pip install -e .`, regenerate the built-in prediction files, metrics CSV and
this report from the committed models with one command:

```
python -m ml.evaluation.compare_models
```

Add `--retrain` to retrain both ML-only models first (about 18 minutes), or
`--from-files` to only read the existing `reports/predictions_*.csv` files.

XGBoost reproduces within a tolerance of ±0.003 mm/day MAE; Random Forest
matches exactly at the reported precision in the cross-environment audit.
The audit observed XGBoost MAE 0.4014 versus 0.3985; this tolerance describes
that observation, not a guarantee across every platform. XGBoost already uses
`n_jobs=1`; the cause of the difference has not been established.

The run uses fixed seed 42 and chronological nested time-series CV for model
selection. Without `--retrain` the table comes from the committed model
artifacts (`random_forest.joblib` and `xgboost.json`). Outputs are
`reports/predictions_fao56_et0.csv`, `reports/predictions_random_forest.csv`,
`reports/predictions_xgboost.csv`, `reports/comparison_metrics.csv` and
`reports/fao56_ml_comparison.md`.
