# 09. Verification and Evaluation Plan

**Project:** DalaSu
**Date:** 2026-10-23
**Status:** Pre-defense 1. Items marked **Done** are backed by files in this repository. Items marked **Planned** or **Proposed** have no result yet.

## 1. Purpose

This plan states how the project aim will be shown to be achieved: which checks are run, which metrics are used, under which conditions, and against which baseline. It covers two things:

1. **Verification:** is the software built correctly (unit tests, reproducibility, requirement checks).
2. **Evaluation:** does the method work well enough (model accuracy against the baseline, and later, usefulness to farmers).

The scientific hypothesis from [the proposal](../project-proposal.md) is that a model using weather data predicts evapotranspiration more accurately than the plain FAO-56 calculation when compared with direct eddy covariance measurements (US-Ne2). It is a hypothesis, not a promise. If the result is different, it is reported as it is.

## 2. Baselines

| Baseline | What it is | Status |
|---|---|---|
| B1: FAO-56 ET₀ | FAO-56 Penman-Monteith reference evapotranspiration, **without** a crop coefficient, compared with measured actual ET (decision D-1, [ADR 0004](adr/0004-compare-et0-with-observed-et.md)) | **Done** (`reports/baseline_metrics.csv`) |
| B2: FAO-56 ETc | ET₀ × Kc from FAO-56 tables (alternative B in ADR 0004). A fairer physical baseline because it targets actual crop ET | **Proposed.** Needs a crop and growth stage for each day of the US-Ne2 record, which `daily.csv` does not contain |
| B3: Farmer's usual practice | Date and amount of watering the farmer would choose without the tool | **Planned** for a field pilot (section 7); no pilot field exists yet |

**Why B1 alone is not enough.** B1 compares a reference-surface quantity with actual crop ET, so its error includes that mismatch (ADR 0004). The gap between B1 and the ML models therefore overstates how much ML improves on a properly parameterised FAO-56 calculation. Adding B2 would make the comparison fairer. Until B2 exists, results are reported as "ML-only against FAO-56 ET₀ without Kc" and not as "ML beats FAO-56".

## 3. Verification: tests and checks

| Area | Check | Tool and location | Status |
|---|---|---|---|
| FAO-56 equations | ET₀ and intermediate values match FAO-56 Example 18; humidity path (Eq. 19); wind-height handling; missing values propagate | `tests/test_penman_monteith.py` (6 tests) | Tests exist; run result to be recorded before the tag |
| Metrics | RMSE, MAE, r², bias on a hand-computed example; sign of bias; NaN pairs dropped; length mismatch raises | `tests/test_metrics.py` (7 tests) | Tests exist; run result to be recorded before the tag |
| Baseline | Metrics on a hand example; end-to-end run with NaN; default data directory; **test period is rejected in training data** | `tests/test_baseline.py` (4 tests) | Tests exist; run result to be recorded before the tag |
| Comparison | All models are scored on the same observations; report states D-1 and the reproduction command; missing XGBoost artifact gives a hint to retrain | `tests/test_compare_models.py` (3 tests) | Tests exist; run result to be recorded before the tag |
| Data leakage | Training reads only 2015–2022; script stops with an error if training data extends past 2022-12-31 | `src/ml/train_ml.py` (as described in README) | Done |
| Reproducibility | Fixed seed 42; one command regenerates models, metrics CSV and report; clean install following the README gives the same metrics | `python -m ml.evaluation.compare_models --retrain` (about 18 minutes) | Done, with a stated tolerance (section 5) |

Run all tests with `python -m pytest` from the repository root (see the README). The total is 20 test functions in 4 files. Before the tag is created, the team must run them on a clean checkout and record the result in the pull request.

## 4. Metrics

All metrics compare observed values first and predictions second. Positive bias means overestimation. Here r² is the squared Pearson correlation, as implemented in `src/ml/evaluation/metrics.py`.

| Metric | Unit | Use |
|---|---|---|
| RMSE | mm/day | Main accuracy metric; penalises large errors. Used for the hypothesis check |
| MAE | mm/day | Typical error; also the model-selection metric in cross-validation |
| Bias | mm/day | Systematic over- or underestimation |
| r² | – | Agreement of day-to-day variation; ignores constant offset, so it is read together with bias |

Metrics for the application (planned, no measurements yet):

| Metric | Target | Source |
|---|---|---|
| Recommendation response time for one field | ≤ 3 s | NFR-05 |
| Difference of own ET₀ from Open-Meteo ET₀ on the test set | ≤ 0.3 mm/day | FR-01 |
| Fraction of days with valid data after cleaning | Reported, no threshold | NFR-03 (section 5) |

## 5. Measurement conditions

**Data.** AmeriFlux US-Ne2 (irrigated maize-soybean rotation site, Nebraska, USA), daily values built from hourly data; provenance and rebuild steps are in `data/README.md`.

| Item | Value |
|---|---|
| Training period | 2015-01-01 to 2022-12-31, 2407 daily rows |
| Test period | 2023-01-01 to 2024-12-31, 561 daily rows, not used in training or tuning |
| Split | Chronological, no shuffling; all models are scored on the same 561 days |
| Features (ML-only) | `tmax_c`, `tmin_c`, `rh_mean_pct`, `ws_ms`, `rn_mj_m2_day`, `p_kpa`, `precip_mm`, `doy` |
| Target | `et_obs_mm` (actual ET from latent heat flux) |
| Model selection | Nested time-series cross-validation (5 outer, 4 inner folds), randomized search with 16 iterations, selection metric MAE |
| Seed | 42 |

**Data completeness (NFR-03).** Days are kept only if they have enough valid intervals: at least 80% coverage for means and extrema, and complete coverage for integrated quantities (latent heat, net radiation, precipitation). Retained days: 2407 of 2922 in the training period (82.4%) and 561 of 731 in the test period (76.7%). This rule checks completeness, not measurement quality, and does not separate measured from gap-filled intervals (`data/README.md`).

**Reproducibility tolerance.** Random Forest matches exactly at the reported precision across environments. XGBoost was observed to differ by up to 0.003 mm/day in MAE (0.4014 against 0.3985); the cause is not established, and the tolerance describes that observation, not a guarantee.

**Application measurements (planned).** Response time is to be measured on a documented machine (CPU, memory, Python version), with a fixed one-field request, a warm-up run, and at least 30 requests. The proposed report is the median and the 95th percentile. This is a proposal, not a measurement.

## 6. Acceptance criteria for the method

| ID | Criterion | Result so far |
|---|---|---|
| A1 | ML-only RMSE on the test period is lower than the RMSE of B1 (FAO-56 ET₀) | **Met on US-Ne2.** FAO-56 ET₀ 1.644; Random Forest 0.588; XGBoost 0.595 mm/day (`reports/comparison_metrics.csv`) |
| A2 | Result is reproducible by one command from a clean install | Done, within the tolerance in section 5 |
| A3 | Cross-validation and test results are consistent (no sign of overfitting to the tuning folds) | Consistent: cross-validation MAE 0.449 (Random Forest) and 0.446 (XGBoost); test MAE 0.412 and 0.398 mm/day |
| A4 | Result against B2 (FAO-56 ETc with Kc) | **Not done** (section 2) |
| A5 | Qualitative check of Kazakhstan output against the NDVI trend | **Not done** (no Sentinel-2 pipeline yet) |

Held-out results (561 days):

| Model | RMSE | MAE | r² | Bias |
|---|---:|---:|---:|---:|
| FAO-56 ET₀ (B1) | 1.644 | 1.113 | 0.474 | +0.917 |
| Random Forest ML-only | 0.588 | 0.412 | 0.879 | +0.125 |
| XGBoost ML-only | 0.595 | 0.398 | 0.879 | +0.119 |

By season, FAO-56 ET₀ is weakest in spring (test period, March–May: RMSE 2.46 mm/day, bias +1.90). A seasonal breakdown for the ML models is not yet in `reports/` and is **Proposed**.

## 7. Evaluation with users (planned)

The farmer survey ([02](02-evidence-of-relevance.md)) shows that respondents want to test recommendations on a small part of their plot and compare them with their usual watering. This is planned as a field pilot after the pre-defense. **No pilot field has been found and there are no results.**

Proposed design:
- One small plot with the recommended date and amount against the farmer's usual practice (baseline B3).
- Record, per irrigation event: recommended date and amount, date and amount actually applied, and a simple soil check (for example, a hand check at spade depth, or a probe if available).
- Report differences descriptively. Water savings and yield effects are not claimed until measured on a real field.
- Water supply by canal schedule limits the choice of dates for many farmers (survey); the pilot must record these limits.

## 8. Known limits of the evaluation

- **Single station.** US-Ne2 is one irrigated maize-soybean site in the USA. The test is a test in time, not in space. It does not show accuracy for southern Kazakhstan, and there is no eddy covariance station in Kazakhstan.
- **Reference-versus-actual target (D-1).** See section 2.
- **Inputs not available in the app.** The ML-only models use tower-measured net radiation and wind measured at 6.2 m. A deployed application would have to obtain its inputs from weather services such as Open-Meteo. Accuracy with such inputs has not been tested; this is a risk for transferring the result to the product.
- **Hybrid model.** Requirement NFR-02 speaks of a hybrid model, but the implemented and evaluated models are ML-only. The hybrid model is a later phase. The requirement text should be aligned with this before the committee sees both.
- **Test period length.** Two years, 561 valid days; gaps are not random (23.3% of test days were rejected by the completeness rule).

## 9. Schedule and responsibilities

| Step | Owner | When |
|---|---|---|
| Run the test suite on a clean checkout and record the result | Both | Before the `prob-period-1` tag |
| Seasonal breakdown for ML models | Aldiyar (ML models) | After pre-defense 1 |
| Baseline B2 (needs crop and growth stage per day) | Madiyar (FAO-56 baseline) | After pre-defense 1, if data allows |
| Response time measurement | Madiyar (backend) | After the API exists |
| Field pilot | Both | After a pilot field is found |

Owners follow the roles in [the proposal](../project-proposal.md) and are to be confirmed by the team.
