# DalaSu diagrams

This folder contains the PlantUML sources and current PNG/SVG exports for the proposed DalaSu system. The architecture is technology-neutral because the UI type, backend framework, database and push provider have not yet been selected.

## Files

- `context.puml` / `context.png` / `context.svg` — system boundary, users and external data/services.
- `use-case.puml` / `use-case.png` / `use-case.svg` — compact user-goal overview; related FRs are grouped to avoid visual overload.
- `component.puml` / `component.png` / `component.svg` — compact technology-neutral architecture and its main dependencies.

## Requirement coverage

The source of truth is `../docs/06-requirements.md`. The incorrect system name in its heading (`SuAqyl`) is interpreted as **DalaSu** in these diagrams.

| ID | Priority | Requirement | Diagram coverage |
|---|---|---|---|
| FR-01 | Must | FAO-56 Penman–Monteith ET₀ calculation | ET model experiment; Irrigation Core |
| FR-02 | Must | FAO-56 baseline evaluation on US-Ne2 | ET model experiment; ML Research Pipeline |
| FR-03 | Must | Random Forest and XGBoost models | ET model experiment; ML Pipeline |
| FR-04 | Must | Comparison of physical, ML-only and hybrid approaches | ET model experiment; ML Research Pipeline |
| FR-05 | Should | ETc = ET₀ × Kc for four crop stages | Irrigation recommendation; Irrigation Core |
| FR-06 | Should | Root-zone water balance and irrigation threshold | Irrigation recommendation; Irrigation Core |
| FR-07 | Should | Irrigation date and amount for seven days | Irrigation recommendation; Irrigation Core |
| FR-08 | Should | FAO-56 fallback when Sentinel-2 is stale | Irrigation recommendation; Irrigation Core |
| FR-09 | Should | Field, crop and planting-date registration | Manage field profile; Application Service and Operational Data |
| FR-10 | Could | Irrigation journal affects the next balance | Record irrigation; Application Service and Operational Data |
| FR-11 | Could | Push notification on irrigation day | Receive irrigation alert; Application Service and Push Provider |
| FR-12 | Could | Seasonal Dr and NDVI graph | View season analytics; Application Service and User Interface |
| FR-13 | Could | Kazakh and Russian interface | Select KZ/RU language; User Interface |
| FR-14 | Could | SHAP feature-contribution chart | Explain model result; ML Research Pipeline |
| FR-15 | Won't | Physics-informed neural network and Sentinel-1 | Explicitly outside the current release |

## Relationship rules checked

- `<<extend>>` points from optional or conditional behavior to its base use case.
- Model explanation extends an experiment only when an explanation is requested.
- Push notification is modelled as a separate asynchronous user scenario.
- `Could` use cases use the `«optional»` stereotype and a distinct colour.
- Component dependencies use dashed arrows from the consumer to the provider.

## Rebuild exports

Run from the repository root:

```bash
plantuml -charset UTF-8 -checkonly diagrams/*.puml
plantuml -charset UTF-8 -tsvg diagrams/*.puml
plantuml -charset UTF-8 -tpng diagrams/*.puml
```

PNG/SVG exports are current when their modification times are not older than the corresponding `.puml` files.

## Scope note

The diagrams describe the proposed target system, not a claim that every component is already implemented. Must and Should requirements form the main release scope; Could requirements are visibly optional. No specific web/mobile framework, API technology, database or notification vendor is assumed.
