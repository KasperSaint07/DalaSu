# DAL-28: residual hybrid v0

The hybrid predicts measured actual daily ET as `ET0 + residual_model(X)`.
The training target is `et_obs_mm - et0_mm`. ET0 is computed by the existing
`add_et0` implementation, including the wind conversion from 6.2 m to 2 m.
The original `ws_ms` feature is unchanged. Negative values are retained.
This learns a site-specific correction, including the difference between grass
reference ET0 and actual field ET; it is not a validation of FAO-56 itself.

## Architecture

- `ml.hybrid`: feature preparation, baseline composition, inference and model
  serialization. Inference requires only the eight meteorological/calendar
  features, not observed ET or dates.
- `ml.train_hybrid`: chronological training, nested evaluation and artifact export.
- `ml.train_ml`: shared feature order, date validator, estimator factories,
  search spaces and search configuration. Reuse keeps ML-only and hybrid aligned
  without changing the established ML-only workflow.

Training uses only `data/processed/train.csv` (2015-01-01 to 2022-12-31).
The validator fails on future dates, duplicates, missing/nonfinite values and
unexpected date bounds. Five outer folds evaluate a four-fold inner randomized
search with 16 candidates, MAE and seed 42. Both levels assert chronological
ordering. A final four-fold search fits the selected estimator on all training
rows. The holdout is read only after both models are fitted; its 561 dates must
match the canonical test file exactly. No test-based parameter selection occurs.

Inner MAE on residuals equals MAE on reconstructed ET. Outer metrics use actual
ET and reconstructed predictions. `r2` is squared Pearson correlation, matching
the existing comparison module; `r2_score` is sklearn's coefficient of
determination, also reported in CV. Do not conflate these metrics.

## Reproduce

Install the pinned dependencies in `requirements.txt`, then run from the root:

```bash
PYTHONPATH=src python -m ml.train_hybrid
python -m pytest -q
```

The default uses exactly the same eight ordered features as ML-only. Optional
ET0 as a ninth feature is a separate experiment:

```bash
PYTHONPATH=src python -m ml.train_hybrid --use-et0-feature
```

That mode automatically writes to `models/hybrid_with_et0/` and
`reports/hybrid_with_et0/`. Explicit `--models-dir` and `--reports-dir` overrides
are supported. ET0 is always added to the predicted residual, regardless of the
feature flag. Do not select the feature mode based on holdout scores.

## Artifacts and inference

Default artifacts:

- `models/hybrid_rf.joblib`, `models/hybrid_xgb.json`: residual estimators.
- `models/hybrid_rf_metadata.json`, `models/hybrid_xgb_metadata.json`: inference
  contracts with feature order, feature mode and wind measurement height.
- `models/hybrid_metadata.json`: run dates, seed, search settings, best parameters,
  dependency versions and input SHA-256 hashes.
- `reports/predictions_hybrid_rf.csv`, `reports/predictions_hybrid_xgb.csv`:
  `date,y_obs,y_pred`, one row per test day (DAL-31 aligns export with DAL-25).
  Diagnostic ET0 and residual components are in `reports/components_hybrid_*.csv`.
- `reports/hybrid_cv_fold_metrics.csv`, `reports/hybrid_cv_metrics.csv`:
  fold metrics/parameters and aggregate mean/sample standard deviation.
- `reports/hybrid_test_metrics.csv`: held-out scores.

Load the estimator through the wrapper so the baseline is not accidentally omitted:

```python
from pathlib import Path
from ml.hybrid import HybridPredictor

model = HybridPredictor.load(Path("models"), "rf")  # or "xgb"
predictions = model.predict(weather_frame)
components = model.predict_components(weather_frame)
```

Only load trusted joblib files. Persist the model and its metadata together.
A run verifies saved/reloaded predictions against in-memory predictions before
export. Numerical reproducibility may depend on dependency versions/platform.

Tests cover reconstruction without observed ET, negative residuals, wind
conversion, feature modes, RF/XGBoost serialization, cutoff rejection, both
levels of temporal CV, holdout dates and nonfinite inputs. Full hyperparameter
searches are deliberately excluded from the fast unit test suite.

ET0-feature exports use the experiment prefix `hybrid_with_et0` (for example,
`predictions_hybrid_with_et0_rf.csv`) both during training and when using
`python -m ml.evaluation.export_hybrid --models-dir models/hybrid_with_et0`.
The exporter selects `reports/hybrid_with_et0/` by default from model metadata.
An explicit reports-directory override preserves the distinct filenames.
