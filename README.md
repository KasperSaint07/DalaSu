# DalaSu

Machine learning irrigation advisor for small farms in Kazakhstan.

> Development of a machine learning-based application to optimize irrigation and assist small-scale farmers in Kazakhstan.

**Status:** pre-defense 1 (analysis, design, planning). No runnable code yet.

## About

DalaSu estimates how much water a field loses to evapotranspiration and recommends when and how much to irrigate. It combines the FAO-56 Penman-Monteith water balance with machine learning (Random Forest, XGBoost), using Sentinel-2 NDVI and weather data. No soil-moisture sensors are needed.

The method is validated against eddy-covariance measurements (AmeriFlux US-Ne2). The application targets smallholder farmers in southern Kazakhstan.

## Problem and users

- **Problem:** small farms often irrigate by schedule or by eye, which wastes water or costs yield. Existing tools rely on sensors or paid subscriptions. Local practice is being confirmed through interviews (`docs/02-evidence-of-relevance.md`).
- **Users:** smallholder and medium farmers (primary); advisors and cooperatives (secondary).
- **Expected outcomes:** a validated comparison of FAO-56, ML-only and hybrid models; a backend and mobile prototype; documentation and a paper draft.

## Team

| | Role |
|---|---|
| Madiyar Amanzhol | FAO-56 model, evaluation |
| Aldiyar Amangeldi | Data pipeline, ML models |
| Kuralay Makhmetova ] | Supervisor |

## Stack

Python, FastAPI, PostgreSQL + PostGIS, Flutter, scikit-learn, XGBoost, Google Earth Engine, Open-Meteo, SoilGrids.
Rationale: `docs/05-technology-comparison.md`, `docs/adr/`.

## Links

- [Task tracker (YouTrack)](https://dalasu.youtrack.cloud/projects/DAL)
- Prototype: [Figma link TBD] · wireframes in `docs/prototype/`
- Diagrams: `diagrams/export/`

## Documentation

| | | |
|---|---|---|
| 1 | Proposal | `docs/01-project-proposal.md` |
| 2 | Evidence of relevance | `docs/02-evidence-of-relevance.md` |
| 3 | Literature review | `docs/03-literature-review.md` |
| 4 | Existing systems | `docs/04-existing-systems-comparison.md` |
| 5 | Technology comparison | `docs/05-technology-comparison.md` |
| 6 | Requirements | `docs/06-requirements.md` |
| 7 | Architecture and diagrams | `docs/07-architecture.md` |
| 8 | UX and prototype | `docs/08-ux-prototype.md` |
| 9 | Verification plan | `docs/09-verification-and-evaluation-plan.md` |
| 10 | Project management | `docs/10-project-management-and-risks.md` |
| 11 | Supervisor feedback | `docs/11-supervisor-feedback.md` |

Current status and known limitations: `docs/00-pre-defense-1-submission.md`.

## Structure

```
docs/       documentation and ADRs
diagrams/   src/ (PlantUML), export/ (PNG, SVG)
src/        backend/, mobile/, ml/
tests/      automated tests
config/     configuration examples (placeholders only)
```

## Train ML-only ET models

From the repository root, reproduce the Random Forest and XGBoost training run with:

```bash
source .venv/bin/activate && pip install -r requirements.txt && python src/ml/train_ml.py
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

## Other development commands

Reproduce the held-out FAO-56 ET0 versus ML-only comparison, including model
training and the generated report:

```bash
PYTHONPATH=src python3 -m ml.evaluation.compare_models --retrain
```

Windows PowerShell (after installing `requirements.txt`):

```powershell
$env:PYTHONPATH="src"; python -m ml.evaluation.compare_models --retrain
```

Omit `--retrain` to evaluate the committed `random_forest.joblib` and native
`xgboost.json` models. XGBoost retraining has an observed MAE tolerance of
±0.003 mm/day; Random Forest matches at the reported precision.

This writes `reports/comparison_metrics.csv` and
`reports/fao56_ml_comparison.md`. The report documents decision D-1 and uses
measured actual ET as the common target.

Rebuild diagrams:

```
cd diagrams && java -jar plantuml.jar -tpng -o ../export src/*.puml
```

## Contributing

- Branches: `DAL-<n>-<short-name>`
- Commits: `DAL-<n>: <description>`
- Pull requests reference the task ID, describe how the change was checked, and are reviewed by the other team member.
- No secrets or personal data in the repository.
