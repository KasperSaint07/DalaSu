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
identical dates and observations (absolute tolerance 1e-6 mm/day).

**D-1: actual ET is the comparison target.** FAO-56 Penman--Monteith produces
grass reference evapotranspiration ET0, not crop actual ET. We deliberately use
ET0 without a crop coefficient (`Kc`) as the physical baseline and compare it
with measured actual ET. Therefore its error includes the ET0-to-actual-ET
mismatch and should not be interpreted as a validation of the FAO-56 equation
itself. Wind measured at 6.2 m is converted to 2 m with FAO-56 Eq. 47.

## Metric definitions

For observations y, predictions p and errors e = p - y on the same n dates:

| CSV column | Definition | Preferred value |
|---|---|---|
| `rmse` | sqrt(mean(e²)) | Lower; mm/day |
| `mae` | mean(abs(e)) | Lower; mm/day; primary metric |
| `pearson_r2` | corr(y, p)² | Higher; linear association only |
| `r2_score` | 1 - sum(e²) / sum((y - mean(y))²) | Higher; coefficient of determination |
| `bias` | mean(e) | Closer to zero; mm/day |
| `nse` | 1 - sum(e²) / sum((y - mean(y))²) | Higher; Nash–Sutcliffe efficiency |
| `kge` | 1 - sqrt((r-1)² + (alpha-1)² + (beta-1)²) | Higher; Kling–Gupta efficiency (2009) |

For KGE, r = corr(y,p), alpha = std(p)/std(y), beta = mean(p)/mean(y);
standard deviations use ddof=0. R² and NSE are numerically identical for this
single-output evaluation on the same observations; they are not independent
evidence. Pearson r² is different: p = y + 5 gives Pearson r² = 1 despite
bias = +5 mm/day and potentially negative R²/NSE.

Constant observations make Pearson r², R²/NSE and KGE undefined (NaN), even
for perfect predictions. Constant predictions make Pearson r² and KGE
undefined, but R²/NSE can remain defined. KGE is also undefined for zero
observed mean. The comparison rejects missing/non-finite values rather than
silently dropping different dates per model. The low-level metric functions
allow paired NaN removal for other callers.

Historical training/CV CSVs and the compatibility function `r2()` retain their
original squared-Pearson meaning. The final comparison uses explicit column
names `pearson_r2` and `r2_score`; historical artifacts are not relabelled as R².

## Held-out metrics

| Model | File | n | RMSE, mm/day | MAE, mm/day | Pearson r² | R² | Bias, mm/day | NSE | KGE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FAO-56 ET0 | `predictions_fao56_et0.csv` | 561 | 1.644 | 1.113 | 0.474 | -0.022 | 0.917 | -0.022 | 0.290 |
| Random Forest ML-only | `predictions_random_forest.csv` | 561 | 0.588 | 0.412 | 0.879 | 0.869 | 0.125 | 0.869 | 0.894 |
| XGBoost ML-only | `predictions_xgboost.csv` | 561 | 0.595 | 0.398 | 0.879 | 0.866 | 0.119 | 0.866 | 0.894 |
| Hybrid + NDVI RF | `predictions_hybrid_ndvi_rf.csv` | 561 | 0.601 | 0.414 | 0.874 | 0.863 | 0.113 | 0.863 | 0.898 |
| Hybrid + NDVI XGBoost | `predictions_hybrid_ndvi_xgb.csv` | 561 | 0.557 | 0.388 | 0.895 | 0.883 | 0.107 | 0.883 | 0.902 |
| Hybrid v0 RF | `predictions_hybrid_rf.csv` | 561 | 0.624 | 0.432 | 0.863 | 0.852 | 0.104 | 0.852 | 0.899 |
| Hybrid v0 XGBoost | `predictions_hybrid_xgb.csv` | 561 | 0.600 | 0.412 | 0.873 | 0.864 | 0.088 | 0.864 | 0.910 |

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

### Best model by metric

| Metric | Best model(s), before rounding | Value |
|---|---|---:|
| MAE | Hybrid + NDVI XGBoost | 0.387753 |
| RMSE | Hybrid + NDVI XGBoost | 0.556918 |
| Absolute bias | Hybrid v0 XGBoost | 0.087806 |
| Pearson r² | Hybrid + NDVI XGBoost | 0.894998 |
| R² / NSE | Hybrid + NDVI XGBoost | 0.882667 |
| KGE | Hybrid v0 XGBoost | 0.910152 |

The overall MAE winner need not minimize bias or maximize KGE. Conclusions
are descriptive for one station and the 2023–2024 holdout; statistical
significance and transfer to other stations have not been established.
No model or hyperparameter is selected or refitted by this comparison.

## Reproduction

From the repository root, reproduce the final seven-model CSV and report
from saved predictions without inference or training:

```
PYTHONPATH=src python -m ml.evaluation.compare_models --from-files --phase3
```

`--phase3` requires all seven specified models and validates their dates and
observations against `data/processed/test.csv`, including its 561-row size.
The general command without `--phase3` also supports additional model files.
Without `--from-files`, built-in predictions are regenerated from saved models;
`--retrain` explicitly retrains ML-only models and is not part of this audit.

XGBoost reproduces within a tolerance of ±0.003 mm/day MAE; Random Forest
matches exactly at the reported precision in the cross-environment audit.
The audit observed XGBoost MAE 0.4014 versus 0.3985; this tolerance describes
that observation, not a guarantee across every platform. XGBoost already uses
`n_jobs=1`; the cause of the difference has not been established.

The original training used seed 42 and chronological nested time-series CV.
The command above only writes `reports/comparison_metrics.csv` and
`reports/fao56_ml_comparison.md`. Saved predictions and model artifacts remain
unchanged. The cross-environment audit above concerns regenerated predictions,
not recomputation of metrics from the fixed CSV files.
