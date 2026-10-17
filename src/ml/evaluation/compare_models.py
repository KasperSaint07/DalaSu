"""Compare FAO-56 ET0 and ML-only models on the held-out test period.

Run from the repository root with:
    PYTHONPATH=src python3 -m ml.evaluation.compare_models

Add ``--retrain`` to rebuild the ML artifacts before evaluation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd
from xgboost import XGBRegressor

from ..fao56.baseline import WIND_HEIGHT_M, add_et0
from ..train_ml import FEATURES, main as train_ml
from .metrics import evaluate

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TEST_PATH = PROJECT_ROOT / "data" / "processed" / "test.csv"
DEFAULT_MODELS_DIR = PROJECT_ROOT / "models"
DEFAULT_METRICS_PATH = PROJECT_ROOT / "reports" / "comparison_metrics.csv"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "reports" / "fao56_ml_comparison.md"

EXPECTED_TEST_START = pd.Timestamp("2023-01-01")
EXPECTED_TEST_END = pd.Timestamp("2024-12-31")
MODEL_FILES = {
    "FAO-56 ET0": None,
    "Random Forest ML-only": "random_forest.joblib",
    "XGBoost ML-only": "xgboost.json",
}


def load_test_data(path: Path | str = DEFAULT_TEST_PATH) -> pd.DataFrame:
    """Load and validate the common held-out evaluation set."""
    frame = pd.read_csv(path)
    required = ["date", "et_obs_mm", *FEATURES]
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
    if frame["date"].duplicated().any():
        raise ValueError("Test data contains duplicate dates")
    if not frame["date"].is_monotonic_increasing:
        raise ValueError("Test data must be sorted chronologically")
    if frame["date"].min() != EXPECTED_TEST_START or frame["date"].max() != EXPECTED_TEST_END:
        raise ValueError(
            "Unexpected test period: expected "
            f"{EXPECTED_TEST_START.date()} through {EXPECTED_TEST_END.date()}"
        )
    if frame[required].isna().any().any():
        raise ValueError("Test data contains missing values")
    return frame


def compare_models(
    test: pd.DataFrame,
    models_dir: Path | str = DEFAULT_MODELS_DIR,
) -> pd.DataFrame:
    """Evaluate ET0 and both trained ML-only models on identical observations."""
    models_dir = Path(models_dir)
    predictions = {"FAO-56 ET0": add_et0(test, WIND_HEIGHT_M)["et0_mm"]}
    for label, filename in MODEL_FILES.items():
        if filename is not None:
            model_path = models_dir / filename
            if not model_path.is_file():
                raise FileNotFoundError(
                    f"Model not found: {model_path}. Re-run with --retrain."
                )
            if filename == "xgboost.json":
                model = XGBRegressor()
                model.load_model(model_path)
            else:
                model = joblib.load(model_path)
            predictions[label] = model.predict(test[FEATURES])

    rows = []
    for label in MODEL_FILES:
        row = {"model": label, **evaluate(test["et_obs_mm"], predictions[label])}
        rows.append(row)
    return pd.DataFrame(rows, columns=["model", "n", "rmse", "mae", "r2", "bias"])


def render_report(metrics: pd.DataFrame, test: pd.DataFrame) -> str:
    """Render the concise comparison report from computed data and metrics."""
    rounded = metrics.copy()
    for column in ["rmse", "mae", "r2", "bias"]:
        rounded[column] = rounded[column].map(lambda value: f"{value:.3f}")
    table_rows = [
        "| Model | n | RMSE, mm/day | MAE, mm/day | r² | Bias, mm/day |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    table_rows.extend(
        f"| {row.model} | {row.n} | {row.rmse} | {row.mae} | {row.r2} | {row.bias} |"
        for row in rounded.itertuples(index=False)
    )

    best_mae = metrics.loc[metrics["mae"].idxmin()]
    baseline = metrics.loc[metrics["model"] == "FAO-56 ET0"].iloc[0]
    mae_reduction = (baseline["mae"] - best_mae["mae"]) / baseline["mae"] * 100.0
    start = test["date"].min().date().isoformat()
    end = test["date"].max().date().isoformat()

    return f"""# FAO-56 baseline and ML-only comparison

## Setup and decision D-1

The common target is **measured actual evapotranspiration**, `et_obs_mm`, from
AmeriFlux US-Ne2. The evaluation uses the untouched {start}--{end} test split;
all models are scored on the same {len(test)} daily observations. Random Forest
and XGBoost were fitted on 2015--2022 only. Metrics use observations first and
predictions second; positive bias means overestimation. Here `r²` is squared
Pearson correlation, as implemented in `src/ml/evaluation/metrics.py`.

**D-1: actual ET is the comparison target.** FAO-56 Penman--Monteith produces
grass reference evapotranspiration ET0, not crop actual ET. We deliberately use
ET0 without a crop coefficient (`Kc`) as the physical baseline and compare it
with measured actual ET. Therefore its error includes the ET0-to-actual-ET
mismatch and should not be interpreted as a validation of the FAO-56 equation
itself. Wind measured at 6.2 m is converted to 2 m with FAO-56 Eq. 47.

## Held-out metrics

{chr(10).join(table_rows)}

Lower RMSE, MAE and absolute bias are better; higher `r²` is better.

## Conclusion

On the held-out period, **{best_mae['model']}** has the lowest MAE
({best_mae['mae']:.3f} mm/day), a {mae_reduction:.1f}% reduction relative to
the FAO-56 ET0 baseline ({baseline['mae']:.3f} mm/day). Both ML-only models
also have substantially lower RMSE and bias and higher correlation with actual
ET. FAO-56 ET0 overestimates actual ET on average (bias
{baseline['bias']:+.3f} mm/day), which is consistent with using reference ET0
without seasonal crop coefficients. For this dataset, ML-only is the stronger
predictor of actual ET; ET0 remains an interpretable physical reference.

## Reproduction

From the repository root, after installing `requirements.txt`, regenerate the
trained models, metrics CSV and this report with one command:

```bash
PYTHONPATH=src python3 -m ml.evaluation.compare_models --retrain
```

Windows PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m ml.evaluation.compare_models --retrain
```

XGBoost reproduces within a tolerance of ±0.003 mm/day MAE; Random Forest
matches exactly at the reported precision in the cross-environment audit.
The audit observed XGBoost MAE 0.4014 versus 0.3985; this tolerance describes
that observation, not a guarantee across every platform. XGBoost already uses
`n_jobs=1`; the cause of the difference has not been established.

The run uses fixed seed 42 and chronological nested time-series CV for model
selection. Without retraining, omit `--retrain` to reproduce the table from the
committed model artifacts (`random_forest.joblib` and `xgboost.json`). Outputs are
`reports/comparison_metrics.csv` and `reports/fao56_ml_comparison.md`.
"""


def run(
    test_path: Path | str = DEFAULT_TEST_PATH,
    models_dir: Path | str = DEFAULT_MODELS_DIR,
    metrics_path: Path | str = DEFAULT_METRICS_PATH,
    report_path: Path | str = DEFAULT_REPORT_PATH,
) -> pd.DataFrame:
    """Compute comparison metrics and write the CSV and Markdown report."""
    test = load_test_data(test_path)
    metrics = compare_models(test, models_dir)
    metrics_path = Path(metrics_path)
    report_path = Path(report_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(metrics_path, index=False, float_format="%.4f")
    report_path.write_text(render_report(metrics, test), encoding="utf-8")
    return metrics


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--retrain",
        action="store_true",
        help="retrain both ML-only models before evaluating the test split",
    )
    args = parser.parse_args(argv)
    if args.retrain:
        train_ml()
    metrics = run()
    print("FAO-56 ET0 and ML-only models vs measured actual ET (test 2023-2024)")
    print(metrics.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print(f"\nSaved: {DEFAULT_METRICS_PATH}")
    print(f"Saved: {DEFAULT_REPORT_PATH}")


if __name__ == "__main__":
    main()
