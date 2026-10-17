# ADR 0004: Compare FAO-56 ET0 with observed actual ET (D-1)

**Status:** Accepted

**Date:** 2026-10-17

## Context

FAO-56 Penman-Monteith gives reference evapotranspiration ET0 for a
hypothetical grass surface. It does not give the actual evapotranspiration of a
specific crop.

The project validates against AmeriFlux US-Ne2, an irrigated maize-soybean
rotation site (`data/README.md`). There actual ET is measured by eddy
covariance as latent heat flux `LE_F_MDS`. `src/ml/data/build_daily.py`
integrates LE over a fully covered day and divides by λ = 2.45 MJ/kg:

```
et_obs_mm = LE * 86400 / 2.45e6     (LE as daily mean, W/m²)
```

`et_obs_mm` is the target for both the FAO-56 baseline and the ML-only models,
so one common target is needed for a fair comparison.

## Decision

**D-1:** ET0 is compared directly with measured actual ET (`et_obs_mm`), without
a crop coefficient `Kc`. ET0 serves as an interpretable physical baseline, not
as a crop ET estimate.

Implemented in `src/ml/fao56/baseline.py` (output `reports/baseline_metrics.csv`)
and `src/ml/evaluation/compare_models.py` (output
`reports/fao56_ml_comparison.md`).

## Alternatives considered

- **A. ET0 without Kc vs actual ET** — chosen.
- **B. ETc = Kc × ET0 with FAO-56 tabulated Kc** — not chosen. `daily.csv` has
  no crop type or growth stage per day, so Kc would have to be set by hand.
- **C. Hybrid model (phase 2)** — ML corrects the residual error of the physical
  model. This is a continuation of A, not a replacement for it.

## Consequences

- The ET0 error includes the reference-versus-actual mismatch. The result is
  therefore **not** a validation of the FAO-56 equation itself.
- Seasonal bias is expected (Kc < 1 off-season, Kc > 1 at canopy peak). Test
  split 2023–2024, bias = mean(ET0 − et_obs_mm), from
  `reports/baseline_metrics.csv`:

  | Test season | n | Bias, mm/day |
  |---|---:|---:|
  | all | 561 | +0.9175 |
  | MAM | 119 | +1.9022 |
  | JJA | 105 | +0.4538 |

- On the same 561 test days the FAO-56 ET0 MAE is 1.113 mm/day, against 0.412
  (Random Forest) and 0.398 (XGBoost) for the ML-only models
  (`reports/fao56_ml_comparison.md`).
- Limitations of the ET0 calculation (`src/ml/fao56/baseline.py`):
  - Only `rh_mean_pct` is available, so actual vapour pressure `ea` comes from
    FAO-56 Eq. 19 (mean daily RH) instead of Eq. 17 (RHmax/RHmin). On FAO-56
    Example 18 this lowers ET0 by about 3%.
  - Wind measured at 6.2 m is converted to 2 m with FAO-56 Eq. 47.
- Literature caveat: the energy balance in eddy-covariance measurements usually
  does not close, which tends to underestimate measured LE. This is not
  corrected and was not assessed in this project.
- `r²` in this project is the squared Pearson correlation
  (`src/ml/evaluation/metrics.py`). It ignores systematic offset, so bias is
  always reported next to it.
