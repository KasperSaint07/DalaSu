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
| [Teammate full name] | Data pipeline, ML models |
| [Supervisor name] | Supervisor |

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

## Run and test

Not available yet. Instructions will be added with the first runnable module (FAO-56, `src/ml`).

Rebuild diagrams:

```
cd diagrams && java -jar plantuml.jar -tpng -o ../export src/*.puml
```

## Contributing

- Branches: `DAL-<n>-<short-name>`
- Commits: `DAL-<n>: <description>`
- Pull requests reference the task ID, describe how the change was checked, and are reviewed by the other team member.
- No secrets or personal data in the repository.
