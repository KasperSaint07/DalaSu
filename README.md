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
