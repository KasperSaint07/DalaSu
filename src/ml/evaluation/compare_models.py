"""Compare FAO-56 ET0, ML-only and other models on the held-out test period.

Every model is read from ``reports/predictions_<model>.csv`` (columns
``date,y_obs,y_pred``, see ``ml.evaluation.predictions``). Before reading, the
FAO-56, Random Forest and XGBoost files are regenerated from the committed
models; files of other models in the folder are compared as they are.

Run from the repository root with:
    python -m ml.evaluation.compare_models

Add ``--retrain`` to rebuild the ML artifacts before predicting, or
``--from-files`` to only read the existing prediction files.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ..train_ml import main as train_ml
from .metrics import evaluate
from .predictions import (
    BASELINE_MODEL,
    DEFAULT_MODELS_DIR,
    DEFAULT_PREDICTIONS_DIR,
    DEFAULT_TEST_PATH,
    load_predictions,
    load_canonical_predictions,
    load_test_data,
    write_builtin_predictions,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_METRICS_PATH = PROJECT_ROOT / "reports" / "comparison_metrics.csv"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "reports" / "fao56_ml_comparison.md"

METRIC_COLUMNS = ["model", "n", "rmse", "mae", "pearson_r2", "r2_score", "bias", "nse", "kge"]
MODEL_LABELS = {
    BASELINE_MODEL: "FAO-56 ET0",
    "random_forest": "Random Forest ML-only",
    "xgboost": "XGBoost ML-only",
    "hybrid_rf": "Hybrid v0 RF",
    "hybrid_xgb": "Hybrid v0 XGBoost",
    "hybrid_ndvi_rf": "Hybrid + NDVI RF",
    "hybrid_ndvi_xgb": "Hybrid + NDVI XGBoost",
}

__all__ = ["compare_models", "load_test_data", "render_report", "run", "main"]


def compare_models(predictions_dir: Path | str = DEFAULT_PREDICTIONS_DIR) -> pd.DataFrame:
    """Metrics of every predictions_*.csv file, all on the same test days."""
    frames = load_predictions(predictions_dir)
    rows = [
        {"model": model, **evaluate(frame["y_obs"], frame["y_pred"])}
        for model, frame in frames.items()
    ]
    for row in rows:
        row["pearson_r2"] = row.pop("r2")
        row["r2_score"] = row["nse"]
    return pd.DataFrame(rows, columns=METRIC_COLUMNS)


def _label(model: str) -> str:
    return MODEL_LABELS.get(model, model)


def render_report(metrics: pd.DataFrame, dates: pd.Series) -> str:
    """Render the concise comparison report from computed metrics and test dates."""
    rounded = metrics.copy()
    for column in ["rmse", "mae", "pearson_r2", "r2_score", "bias", "nse", "kge"]:
        rounded[column] = rounded[column].map(lambda value: f"{value:.3f}")
    table_rows = [
        "| Model | File | n | RMSE, mm/day | MAE, mm/day | Pearson r² | R² | Bias, mm/day | NSE | KGE |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    table_rows.extend(
        f"| {_label(row.model)} | `predictions_{row.model}.csv` | {row.n} | {row.rmse} "
        f"| {row.mae} | {row.pearson_r2} | {row.r2_score} | {row.bias} | {row.nse} | {row.kge} |"
        for row in rounded.itertuples(index=False)
    )

    best_mae = metrics.loc[metrics["mae"].idxmin()]
    baseline = metrics.loc[metrics["model"] == BASELINE_MODEL].iloc[0]
    mae_reduction = (baseline["mae"] - best_mae["mae"]) / baseline["mae"] * 100.0
    better_rmse = [
        _label(row.model)
        for row in metrics.itertuples(index=False)
        if row.model != BASELINE_MODEL and row.rmse < baseline["rmse"]
    ]
    better_rmse_text = ", ".join(better_rmse) if better_rmse else "none"
    winner_rows = []
    for key, label, minimize in [
        ("mae", "MAE", True), ("rmse", "RMSE", True),
        ("bias", "Absolute bias", True), ("pearson_r2", "Pearson r²", False),
        ("r2_score", "R² / NSE", False), ("kge", "KGE", False),
    ]:
        values = metrics[key].abs() if key == "bias" else metrics[key]
        best = values.min() if minimize else values.max()
        winners = metrics.loc[values == best, "model"].map(_label)
        winner_rows.append(f"| {label} | {', '.join(winners) or 'Undefined'} | {best:.6f} |")
    start = dates.min().date().isoformat()
    end = dates.max().date().isoformat()

    return f"""# FAO-56, ML-only and Hybrid comparison

## Setup and decision D-1

The common target is **measured actual evapotranspiration**, `et_obs_mm`, from
AmeriFlux US-Ne2. The evaluation uses the untouched {start}--{end} test split;
all models are scored on the same {len(dates)} daily observations. Random Forest
and XGBoost were fitted on 2015--2022 only. Metrics use observations first and
predictions second; positive bias means overestimation. Here `r²` is squared
Pearson correlation, as implemented in `src/ml/evaluation/metrics.py`; NSE is
the Nash--Sutcliffe efficiency and KGE the Kling--Gupta efficiency (Gupta et
al. 2009).

Each model is read from `reports/predictions_<model>.csv` with columns
`date,y_obs,y_pred`; the comparison stops with an error unless all files cover
identical dates and observations (absolute tolerance 1e-6 mm/day).

**D-1: actual ET is the comparison target.** FAO-56 Penman--Monteith produces
grass reference evapotranspiration ET0, not crop actual ET. We deliberately use
ET0 without a crop coefficient (`Kc`) as the physical baseline and compare it
with measured actual ET. Therefore its error includes the ET0-to-actual-ET
mismatch and should not be interpreted as a validation of the FAO-56 equation
itself. Wind measured at 6.2 m is converted to 2 m with FAO-56 Eq. 47.

## Metric definitions

For observations y, predictions p and errors e = p - y on the same n dates:

| CSV column | Definition | Preferred value |
|---|---|---|
| `rmse` | sqrt(mean(e²)) | Lower; mm/day |
| `mae` | mean(abs(e)) | Lower; mm/day; primary metric |
| `pearson_r2` | corr(y, p)² | Higher; linear association only |
| `r2_score` | 1 - sum(e²) / sum((y - mean(y))²) | Higher; coefficient of determination |
| `bias` | mean(e) | Closer to zero; mm/day |
| `nse` | 1 - sum(e²) / sum((y - mean(y))²) | Higher; Nash–Sutcliffe efficiency |
| `kge` | 1 - sqrt((r-1)² + (alpha-1)² + (beta-1)²) | Higher; Kling–Gupta efficiency (2009) |

For KGE, r = corr(y,p), alpha = std(p)/std(y), beta = mean(p)/mean(y);
standard deviations use ddof=0. R² and NSE are numerically identical for this
single-output evaluation on the same observations; they are not independent
evidence. Pearson r² is different: p = y + 5 gives Pearson r² = 1 despite
bias = +5 mm/day and potentially negative R²/NSE.

Constant observations make Pearson r², R²/NSE and KGE undefined (NaN), even
for perfect predictions. Constant predictions make Pearson r² and KGE
undefined, but R²/NSE can remain defined. KGE is also undefined for zero
observed mean. The comparison rejects missing/non-finite values rather than
silently dropping different dates per model. The low-level metric functions
allow paired NaN removal for other callers.

Historical training/CV CSVs and the compatibility function `r2()` retain their
original squared-Pearson meaning. The final comparison uses explicit column
names `pearson_r2` and `r2_score`; historical artifacts are not relabelled as R².

## Held-out metrics

{chr(10).join(table_rows)}

Lower RMSE, MAE and absolute bias are better; higher `r²`, NSE and KGE are
better (NSE = KGE = 1 is a perfect fit). NSE below 0 means the model is worse
than predicting the observed mean.

## Conclusion

On the held-out period, **{_label(best_mae['model'])}** has the lowest MAE
({best_mae['mae']:.3f} mm/day), a {mae_reduction:.1f}% reduction relative to
the FAO-56 ET0 baseline ({baseline['mae']:.3f} mm/day). Models with lower RMSE
than the baseline: {better_rmse_text}. FAO-56 ET0 overestimates actual ET on
average (bias {baseline['bias']:+.3f} mm/day, NSE {baseline['nse']:.3f}), which
is consistent with using reference ET0 without seasonal crop coefficients. ET0
remains an interpretable physical reference.

### Best model by metric

| Metric | Best model(s), before rounding | Value |
|---|---|---:|
{chr(10).join(winner_rows)}

The overall MAE winner need not minimize bias or maximize KGE. Conclusions
are descriptive for one station and the 2023–2024 holdout; statistical
significance and transfer to other stations have not been established.
No model or hyperparameter is selected or refitted by this comparison.

## Reproduction

From the repository root, reproduce the final seven-model CSV and report
from saved predictions without inference or training:

```
PYTHONPATH=src python -m ml.evaluation.compare_models --from-files --phase3
```

`--phase3` requires all seven specified models and validates their dates and
observations against `data/processed/test.csv`, including its 561-row size.
The general command without `--phase3` also supports additional model files.
Without `--from-files`, built-in predictions are regenerated from saved models;
`--retrain` explicitly retrains ML-only models and is not part of this audit.

XGBoost reproduces within a tolerance of ±0.003 mm/day MAE; Random Forest
matches exactly at the reported precision in the cross-environment audit.
The audit observed XGBoost MAE 0.4014 versus 0.3985; this tolerance describes
that observation, not a guarantee across every platform. XGBoost already uses
`n_jobs=1`; the cause of the difference has not been established.

The original training used seed 42 and chronological nested time-series CV.
The command above only writes `reports/comparison_metrics.csv` and
`reports/fao56_ml_comparison.md`. Saved predictions and model artifacts remain
unchanged. The cross-environment audit above concerns regenerated predictions,
not recomputation of metrics from the fixed CSV files.
"""


def run(
    test_path: Path | str = DEFAULT_TEST_PATH,
    models_dir: Path | str = DEFAULT_MODELS_DIR,
    predictions_dir: Path | str = DEFAULT_PREDICTIONS_DIR,
    metrics_path: Path | str = DEFAULT_METRICS_PATH,
    report_path: Path | str = DEFAULT_REPORT_PATH,
    write_predictions: bool = True,
    phase3: bool = False,
) -> pd.DataFrame:
    """Write built-in predictions (optional), then the metrics CSV and report."""
    if write_predictions:
        write_builtin_predictions(test_path, models_dir, predictions_dir)
    if phase3:
        load_canonical_predictions(predictions_dir, test_path, required=tuple(MODEL_LABELS))
    metrics = compare_models(predictions_dir)
    dates = load_predictions(predictions_dir)[BASELINE_MODEL]["date"]
    metrics_path = Path(metrics_path)
    report_path = Path(report_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(metrics_path, index=False, float_format="%.4f")
    report_path.write_text(render_report(metrics, dates), encoding="utf-8")
    return metrics


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--retrain",
        action="store_true",
        help="retrain both ML-only models, then regenerate predictions and evaluate",
    )
    group.add_argument(
        "--from-files",
        action="store_true",
        help="only read the existing reports/predictions_*.csv files",
    )
    parser.add_argument("--phase3", action="store_true", help="validate the final seven-model, 561-day comparison")
    args = parser.parse_args(argv)
    if args.retrain:
        train_ml()
    metrics = run(write_predictions=not args.from_files, phase3=args.phase3)
    print("Model predictions vs measured actual ET (test 2023-2024)")
    print(metrics.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print(f"\nSaved: {DEFAULT_METRICS_PATH}")
    print(f"Saved: {DEFAULT_REPORT_PATH}")


if __name__ == "__main__":
    main()
