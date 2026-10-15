# FAO-56 baseline and ML-only comparison

## Setup and decision D-1

The common target is **measured actual evapotranspiration**, `et_obs_mm`, from
AmeriFlux US-Ne2. The evaluation uses the untouched 2023-01-01--2024-12-31 test split;
all models are scored on the same 561 daily observations. Random Forest
and XGBoost were fitted on 2015--2022 only. Metrics use observations first and
predictions second; positive bias means overestimation. Here `r²` is squared
Pearson correlation, as implemented in `src/ml/evaluation/metrics.py`.

**D-1: actual ET is the comparison target.** FAO-56 Penman--Monteith produces
grass reference evapotranspiration ET0, not crop actual ET. We deliberately use
ET0 without a crop coefficient (`Kc`) as the physical baseline and compare it
with measured actual ET. Therefore its error includes the ET0-to-actual-ET
mismatch and should not be interpreted as a validation of the FAO-56 equation
itself. Wind measured at 6.2 m is converted to 2 m with FAO-56 Eq. 47.

## Held-out metrics

| Model | n | RMSE, mm/day | MAE, mm/day | r² | Bias, mm/day |
|---|---:|---:|---:|---:|---:|
| FAO-56 ET0 | 561 | 1.644 | 1.113 | 0.474 | 0.917 |
| Random Forest ML-only | 561 | 0.588 | 0.412 | 0.879 | 0.125 |
| XGBoost ML-only | 561 | 0.595 | 0.398 | 0.879 | 0.119 |

Lower RMSE, MAE and absolute bias are better; higher `r²` is better.

## Conclusion

On the held-out period, **XGBoost ML-only** has the lowest MAE
(0.398 mm/day), a 64.2% reduction relative to
the FAO-56 ET0 baseline (1.113 mm/day). Both ML-only models
also have substantially lower RMSE and bias and higher correlation with actual
ET. FAO-56 ET0 overestimates actual ET on average (bias
+0.917 mm/day), which is consistent with using reference ET0
without seasonal crop coefficients. For this dataset, ML-only is the stronger
predictor of actual ET; ET0 remains an interpretable physical reference.

## Reproduction

From the repository root, after installing `requirements.txt`, regenerate the
trained models, metrics CSV and this report with one command:

```bash
PYTHONPATH=src python3 -m ml.evaluation.compare_models --retrain
```

The run uses fixed seed 42 and chronological nested time-series CV for model
selection. Without retraining, omit `--retrain` to reproduce the table from the
committed deterministic model artifacts. Outputs are
`reports/comparison_metrics.csv` and `reports/fao56_ml_comparison.md`.
