# DalaSu

Machine learning irrigation advisor for small farms in Kazakhstan.

> Development of a machine learning-based application to optimize irrigation and assist small-scale farmers in Kazakhstan.

**Status:** pre-defense 1. FAO-56 baseline and ML-only models are implemented and compared on a held-out test period; pre-defense 1 documentation (sections 1–11) is in `docs/`.

## About

DalaSu estimates how much water a field loses to evapotranspiration and recommends when and how much to irrigate. It combines the FAO-56 Penman-Monteith water balance with machine learning (Random Forest, XGBoost), using weather data now and Sentinel-2 NDVI in the next phase. No soil-moisture sensors are needed.

The method is being validated against eddy-covariance measurements (AmeriFlux US-Ne2). The application targets smallholder farmers in southern Kazakhstan.

## Problem and users

- **Problem:** small farms often irrigate by schedule or by eye, which wastes water or costs yield. Existing tools rely on sensors or paid subscriptions.
- **Users:** smallholder and medium farmers (primary); advisors and cooperatives (secondary).
- **Expected outcomes:** a validated comparison of FAO-56, ML-only and hybrid models; a backend and mobile prototype; documentation and a paper draft.

## Team

| | Role |
|---|---|
| Madiyar Amanzhol | FAO-56 model, evaluation |
| Aldiyar Amangeldi | Data pipeline, ML models |
| Kuralay Makhmetova | Supervisor |

## Planned stack

Python, FastAPI, PostgreSQL, Flutter, scikit-learn, XGBoost, Google Earth Engine, Open-Meteo, SoilGrids. PostGIS is an optional extension for future field geometry and spatial queries.

FastAPI, PostgreSQL, and Flutter were confirmed on 2026-10-22; application implementation is pending. See the [technology comparison](docs/05-technology-comparison.md) for alternatives and tradeoffs.

## Links

- [Task tracker (YouTrack)](https://dalasu.youtrack.cloud/projects/DAL)
- [Design file (Figma)](https://www.figma.com/design/LNJk5OnjblriAknZx3etPN/)
- [Mobile prototype](https://www.figma.com/proto/LNJk5OnjblriAknZx3etPN/DalaSu?node-id=2-3324&starting-point-node-id=2%3A3324&scaling=scale-down)
- [Web prototype](https://www.figma.com/proto/LNJk5OnjblriAknZx3etPN/DalaSu?node-id=2-3660&starting-point-node-id=2%3A3660&scaling=scale-down)
- Submission tag: `prob-period-1`

## Documentation

Pre-defense 1 documents are in `docs/`. Diagram sources are in `diagrams/`. Decision records are in `docs/adr/`.

| # | Document |
|---|---|
| 1 | [Project proposal](docs/01-project-proposal.md) |
| 2 | [Evidence of relevance](docs/02-evidence-of-relevance.md) |
| 3 | [Literature review](docs/03-literature-review.md) |
| 4 | [Existing systems comparison](docs/04-existing-systems-comparison.md) |
| 5 | [Technology comparison](docs/05-technology-comparison.md) |
| 6 | [Requirements specification](docs/06-requirements.md) |
| 7 | Architecture and diagrams |
| 8 | [UX and prototype](docs/08-prototype.md) |
| 9 | [Verification and evaluation plan](docs/09-verification-and-evaluation-plan.md) |
| 10 | [Project management and risks](docs/10-project-management-and-risks.md) |
| 11 | [Supervisor feedback](docs/11-supervisor-feedback.md) |


Diagram sources (PlantUML) are in [`diagrams/`](diagrams/).

- [ADR 0001: FastAPI backend](docs/adr/0001-use-fastapi-for-backend.md)
- [ADR 0002: PostgreSQL storage](docs/adr/0002-use-postgresql-for-storage.md)
- [ADR 0003: Flutter mobile client](docs/adr/0003-use-flutter-for-mobile.md)
- [ADR 0004: ET0 versus observed actual ET](docs/adr/0004-compare-et0-with-observed-et.md)

## Structure

```
data/              data provenance (README.md) and processed daily splits
models/            trained ML-only models (random_forest.joblib, xgboost.json)
reports/           generated metrics and comparison report
src/ml/data/       daily dataset builder
src/ml/evaluation/ metrics and FAO-56 vs ML comparison
src/ml/fao56/      FAO-56 Penman-Monteith ET0 and baseline
tests/             automated tests
docs/              pre-defense documents 01–11
docs/adr/          architecture decision records
diagrams/          PlantUML sources and rendered diagrams
requirements.txt   pinned dependencies
pyproject.toml     package metadata for an editable install
```

## Setup and tests

Run all commands from the repository root.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
python -m pytest
```

bash / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python -m pytest
```

After `pip install -e .` the commands below are the same on every OS and need no
`PYTHONPATH`.

## Run FAO-56 baseline

```
python -m ml.fao56.baseline
```

The metrics are written to `reports/baseline_metrics.csv`. Decision D-1 (ET0
without a crop coefficient compared with measured actual ET) is described in
[ADR 0004](docs/adr/0004-compare-et0-with-observed-et.md).

## Train ML-only ET models

Reproduce the Random Forest and XGBoost training run with:

```
python -m ml.train_ml
```

The script directly predicts daily `et_obs_mm` from meteorological features. It uses
nested `TimeSeriesSplit` cross-validation without shuffling, tunes both models only on
`data/processed/train.csv` from 2015--2022, and saves models under `models/` and CV
reports under `reports/`. The held-out 2023--2024 test period is neither loaded nor
used during training. The script stops with an error if the training data extends past
2022-12-31.

`precip_mm` comes from the AmeriFlux BASE `P_PI_F_1_1_1` hourly amounts, summed
by day. The old FLUXNET `P_F` is not used because its 2015--2024 values were
filled entirely from the unsuitable `P_ERA` series. `ws_ms` is the original
mean FLUXNET `WS_F` measured at 6.2 m; conversion to 2 m belongs only to a
FAO-56 ET0 calculation, not to this ML-only training pipeline. See
[`data/README.md`](data/README.md) for provenance and rebuild instructions.

## Compare FAO-56 and ML-only models

Reproduce the held-out comparison from the committed
`random_forest.joblib` and native `xgboost.json` models with one command:

```
python -m ml.evaluation.compare_models
```

**Predictions contract.** Every model writes
`reports/predictions_<model>.csv` with columns `date,y_obs,y_pred`: ISO dates
(`YYYY-MM-DD`), observed `et_obs_mm` and the prediction in mm/day, one row per
valid test day (561 rows for 2023–2024). The built-in files are
`predictions_fao56_et0.csv`, `predictions_random_forest.csv` and
`predictions_xgboost.csv`; create only them with
`python -m ml.evaluation.predictions`. A new model, such as the hybrid, adds its
own `predictions_<model>.csv` to `reports/` and is picked up automatically.

`compare_models` first regenerates the three built-in files, then reads every
`reports/predictions_*.csv`, stops with an error unless all files have the same
dates and `y_obs`, and computes RMSE, MAE, r², bias, NSE and KGE per model.

- `--retrain` retrains both ML-only models first (about 18 minutes) and then
  regenerates their prediction files. XGBoost retraining has an observed MAE
  tolerance of ±0.003 mm/day; Random Forest matches at the reported precision.
- `--from-files` skips regeneration and only reads the existing files.

This writes `reports/comparison_metrics.csv` and
`reports/fao56_ml_comparison.md`. The report documents decision D-1 and uses
measured actual ET as the common target.

## Contributing

- Branches: `DAL-<n>-<short-name>`
- Commits: `DAL-<n>: <description>`
- Pull requests reference the task ID, describe how the change was checked, and are reviewed by the other team member.
- No secrets or personal data in the repository.

## DAL-31: Hybrid + NDVI

The residual RF and XGBoost use the original eight features plus `ndvi_last`
and `ndvi_age_days`. ET0 computation and the DAL-28 training procedure are
unchanged: 2015–2022 training, nested chronological CV (5 outer / 4 inner
folds), 16 randomized candidates, seed 42, selection by MAE. The 561 held-out
2023–2024 dates are read after both models have been fitted. NDVI is joined
backward only by DAL-30; provenance columns are not predictors.

Thirteen initial training rows have missing NDVI. A median imputer is fitted
inside each search fold, then saved with the final estimator. No rows are
removed and no test statistics are used. Weather and target values must match
the canonical data exactly. ET0 is not an additional feature in this experiment.

From the repository root, using the environment with `requirements.txt` installed:

```bash
python src/ml/data/build_ndvi.py
PYTHONPATH=src python -m ml.train_hybrid --use-ndvi
# Re-export existing v0 models to the common predictions contract:
PYTHONPATH=src python -m ml.evaluation.export_hybrid
PYTHONPATH=src python -m ml.evaluation.compare_models
python -m pytest -q
```

Models and preprocessing are stored together in `models/hybrid_ndvi/`.
The v0 artifacts remain in `models/`; old schema-v1 models remain loadable.
Schema-v2 metadata records feature order and serialization format. NDVI
pipelines use joblib for both estimators; only load trusted artifacts.
`reports/predictions_hybrid_ndvi_{rf,xgb}.csv` contain exactly
`date,y_obs,y_pred`, as required by DAL-25. Diagnostic components are separate
`components_hybrid_ndvi_*.csv` files. The v0 export now follows this same
contract. CV fold scores, selected parameters, aggregate scores and test
metrics use the `hybrid_ndvi_` prefix. Input hashes and library versions are
recorded in `models/hybrid_ndvi/hybrid_metadata.json`.

To regenerate NDVI predictions without training:

```bash
PYTHONPATH=src python -m ml.evaluation.export_hybrid \
  --models-dir models/hybrid_ndvi --test-path data/processed/ndvi/test.csv
PYTHONPATH=src python -m ml.evaluation.compare_models --from-files
```

### Repeat-training acceptance check

Run a second complete search and fit into separate directories:

```bash
PYTHONPATH=src python -m ml.train_hybrid --use-ndvi \
  --models-dir /tmp/dal31-repeat/models --reports-dir /tmp/dal31-repeat/reports
PYTHONPATH=src python -m ml.evaluation.check_reproducibility \
  reports /tmp/dal31-repeat/reports \
  --output reports/hybrid_ndvi_reproducibility.json
```

The acceptance tolerance is **absolute difference <= 1e-6 for each of MAE,
RMSE, bias, r², NSE and KGE**, separately for RF and XGBoost, with identical
input data, seed and dependency versions in the same environment. MAE, RMSE
and bias use mm/day; the other metrics are dimensionless. Dates and observed
values must match exactly. The checker recomputes metrics from full-precision
predictions, writes every difference and exits nonzero on failure. This is a
repeat-training check, not merely a reload of an existing estimator; it is
not a cross-platform guarantee. The older ML-only XGBoost tolerance is not
used for this experiment. Here r² is squared Pearson correlation, not sklearn
R²; NSE equals the latter for these complete observations.

See [DAL-31 results](reports/hybrid_ndvi_validation.md) for the measured NDVI
contribution and repeat-run evidence. Feature preparation, training, inference,
export and reproducibility checking are separate reusable components; future
feature groups should extend the explicit feature contract and validation,
without duplicating the training/CV loop.

### Measured result

На 561 общей тестовой дате US-Ne2 за 2023–2024 добавление ndvi_last и ndvi_age_days улучшило Hybrid относительно v0: MAE RF снизилась с 0,431587 до 0,414459 мм/день (на 3,97%), MAE XGBoost — с 0,412442 до 0,387753 мм/день (на 5,99%); RMSE снизилась соответственно с 0,624450 до 0,601038 и с 0,600067 до 0,556918 мм/день. При этом положительный bias вырос у обеих моделей, а KGE немного снизился, поэтому улучшение не охватывает все метрики. Hybrid + NDVI XGBoost также превзошёл сохранённый ML-only XGBoost по MAE и RMSE, тогда как RF остался немного хуже ML-only RF. Результат показывает полезный вклад двух NDVI-признаков в этом эксперименте с повторным подбором параметров, но не доказывает статистическую значимость или переносимость на другие станции и годы; настройки не выбирались по тестовым метрикам.

Two independent full runs passed all 12 metric checks; maximum absolute difference was 0 (tolerance 1e-6).

### Isolated ET0 feature experiments

Training and export share the same experiment identity. Optional ET0-feature
runs use `hybrid_with_et0` or `hybrid_ndvi_with_et0` in prediction/component
filenames and default to the corresponding subdirectory under `reports/`.
The exporter reads this mode from the saved model metadata, not the directory
name. For example:

```bash
PYTHONPATH=src python -m ml.evaluation.export_hybrid \
  --models-dir models/hybrid_with_et0
PYTHONPATH=src python -m ml.evaluation.export_hybrid \
  --models-dir models/hybrid_ndvi_with_et0
```

The second command automatically selects the NDVI test data. Explicit
`--test-path` and `--reports-dir` overrides remain available. Even when all
experiments are explicitly exported into the same reports directory, their
prediction names remain distinct, so an ET0-feature export does not replace
Hybrid v0 or Hybrid + NDVI predictions.
