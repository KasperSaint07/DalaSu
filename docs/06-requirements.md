# 06. DalaSu System Requirements (DAL-16)

MoSCoW priorities: **M** (Must), **S** (Should), **C** (Could), **W** (Won't in this version).
Every requirement is verifiable: it has a number or an acceptance criterion.

## Functional requirements (FR)

| ID | Requirement | Acceptance criterion | Priority |
|---|---|---|---|
| FR-01 | ET₀ calculation by FAO-56 Penman-Monteith from meteorological data | Deviation from Open-Meteo ET₀ ≤ 0.3 mm/day on the test set; unit tests on FAO-56 Example 18 pass | M |
| FR-02 | Baseline ET₀ estimate on US-Ne2 data | RMSE and R² against eddy covariance are calculated | M |
| FR-03 | Random Forest and XGBoost models for ET₀ | Both models are trained, RMSE/R² metrics are recorded in `reports/` | M |
| FR-04 | Comparison of the FAO-56 baseline and hybrid models | RMSE/R² table for 3 approaches; the result is reproducible with one command | M |
| FR-05 | ETc = ET₀ × Kc calculation from FAO-56 tables | Kc is defined for 4 stages for each supported crop | S |
| FR-06 | Root-zone water balance (Dr) and irrigation threshold | Dr is calculated by the FAO-56 formula; test on a reference example | S |
| FR-07 | Recommendation "when and how much to irrigate" | For a field, the date and amount (mm) are given for the next 7 days | S |
| FR-08 | Fallback mode without a fresh Sentinel-2 image | If there is no image for > 5 days, the recommendation is built on pure FAO-56 without error | S |
| FR-09 | Registration of field, crop and planting date | The field is saved and restored after restart | S |
| FR-10 | Irrigation journal | A recorded irrigation is taken into account in the next Dr calculation | C |
| FR-11 | Push notifications with a recommendation | The notification arrives on the day of the recommended irrigation | C |
| FR-12 | Season chart with NDVI | The chart shows moisture deficit and NDVI for the season | C |
| FR-13 | Kazakh and Russian interface | All screens are translated into both languages | C |
| FR-14 | SHAP feature-importance analysis | A feature contribution chart is built for the best model | C |
| FR-15 | Physics-informed neural network, Sentinel-1 | — | W |

## Non-functional requirements (NFR)

| ID | Requirement | Acceptance criterion | Priority |
|---|---|---|---|
| NFR-01 | Reproducibility | Fixed seed; a clean install and run following the README give the same metrics | M |
| NFR-02 | Accuracy of the hybrid model | Hybrid RMSE is lower than FAO-56 baseline RMSE on the US-Ne2 test set | M |
| NFR-03 | Data correctness | US-Ne2 outliers and gaps are processed; the share of gaps after cleaning is documented | M |
| NFR-04 | Code quality | Tests pass via `pytest`; runs without manual setup (pyproject.toml) | M |
| NFR-05 | Recommendation response time | API response ≤ 3 s for a request for one field | S |
| NFR-06 | Data cost | Only free sources are used (Open-Meteo, Sentinel-2, SoilGrids) | S |
| NFR-07 | Explainability | The contribution of moisture deficit and precipitation is shown for the recommendation | C |
| NFR-08 | Quantitative validation on Kazakhstan data | — (there is no eddy covariance station in Kazakhstan; validation is qualitative) | W |
