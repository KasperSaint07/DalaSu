# 01. Project Proposal: DalaSu

## 1. Team and Roles

| Member | Role | Area of responsibility |
|---|---|---|
| Madiyar Amanzhol | Developer, backend and model evaluation | US-Ne2 data preprocessing; FAO-56 ET₀ function and baseline; evaluation module (RMSE, R²); backend in Python/FastAPI and database; Kazakhstan weather data; paper text |
| Aldiyar Amangeldi | Developer, ML and mobile application | AmeriFlux data download and `daily.csv`; Random Forest and XGBoost (ML-only); Sentinel-2/NDVI via Google Earth Engine; final model comparison; mobile application; NDVI layer for Kazakhstan; paper text |

The scientific supervisor receives a separate description of individual contribution from each member.

## 2. Topic

- **EN:** Development of a machine learning-based application to optimize irrigation and assist small-scale farmers in Kazakhstan
- **RU:** Разработка приложения на основе машинного обучения для оптимизации орошения и поддержки малых фермерских хозяйств Казахстана
- **KZ:** Қазақстандағы суаруды оңтайландыру және шағын фермерлерге қолдау көрсетуге арналған машиналық оқыту негізіндегі қосымшаны әзірлеу

Working project name: **DalaSu**.

## 3. Goal

To create a system that estimates the water lost by a field through evapotranspiration using the FAO-56 Penman-Monteith standard and tells the farmer when and how much to irrigate. The FAO-56 method is supplemented by ML calibration (Random Forest, XGBoost) using satellite and weather data. Soil moisture sensors are not required.

Testable scientific hypothesis: the hybrid model is more accurate than pure FAO-56 when compared with direct eddy covariance measurements (US-Ne2). This is a hypothesis, not a promise: the result may turn out differently, and in that case it will be described as it is (see NFR-02 in `06-requirements.md`).

## 4. Project Scope

Priorities correspond to the requirements in `06-requirements.md` (MoSCoW).

**Included, mandatory (Must):**
- ET₀ calculation by FAO-56 from weather data (FR-01);
- baseline ET₀ estimation on US-Ne2 data with RMSE and R² against eddy covariance (FR-02);
- Random Forest and XGBoost models for ET₀ (FR-03);
- comparison of the FAO-56 baseline and the two hybrid models, reproducible with one command (FR-04).

**Included if time allows (Should):**
- ETc = ET₀ × Kc from FAO-56 tables (FR-05);
- root zone water balance and irrigation threshold (FR-06);
- "when and how much to irrigate" recommendation for 7 days (FR-07);
- fallback mode without a fresh Sentinel-2 image (FR-08);
- registration of field, crop and planting date (FR-09).

**Desirable (Could):** irrigation diary, push notifications, season chart with NDVI, interface in Kazakh and Russian, SHAP analysis (FR-10…FR-14).

**Not included in this version (Won't):**
- physics-informed neural network and Sentinel-1 (FR-15);
- quantitative validation on Kazakhstan data (NFR-08).

**Scientific paper and coursework:** only ET₀ (not ETc), two ML models against FAO-56, validation on a single station US-Ne2 with a chronological split of the sample. The Kazakhstan layer is not part of the paper and belongs to the full diploma.

## 5. Constraints

- **Validation.** There is no eddy covariance station in Kazakhstan, so only qualitative checking (consistency with the NDVI trend) is possible for the Kazakhstan part. Quantitative accuracy in Kazakhstan is not claimed.
- **Single station.** Results are obtained on US-Ne2 (Nebraska, USA) and do not prove generalizability to other regions.
- **Kc coefficients.** The FAO-56 table values are global and are not calibrated for local varieties.
- **Satellite data.** Sentinel-2 arrives with a delay of about 5 days and depends on cloud cover; in that case the system works on pure FAO-56.
- **Data.** Only free sources are used: Open-Meteo, Sentinel-2, SoilGrids, AmeriFlux data (NFR-06).
- **US-Ne2 data** require cleaning of gaps and outliers; the share of gaps after cleaning will be documented (NFR-03).
- **Pilot field** in Kazakhstan has not been found yet.
- **Water and yield savings are not promised.** No percentage of water savings or yield increase is claimed until it has been measured on a real field.
- **Analogues.** The market is not empty: in Kazakhstan there is the free state application AgroData and the Egistic platform. For the comparison with analogues see `04-existing-systems-comparison.md`.
