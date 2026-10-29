"""Write and read per-model test predictions in the common contract format.

Contract: every model writes ``reports/predictions_<model>.csv`` with columns
``date,y_obs,y_pred``: ISO dates (YYYY-MM-DD), observed ``et_obs_mm`` and the
model prediction in mm/day, one row per valid test day. All files must cover
the same dates so that every model is scored on identical observations.

This module creates the three built-in files (FAO-56 ET0 and the committed
Random Forest and XGBoost models). Other models, such as the hybrid, add their
own file to the same folder.

Run from the repository root with:
    python -m ml.evaluation.predictions
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from ..fao56.baseline import WIND_HEIGHT_M, add_et0
from ..train_ml import FEATURES

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TEST_PATH = PROJECT_ROOT / "data" / "processed" / "test.csv"
DEFAULT_MODELS_DIR = PROJECT_ROOT / "models"
DEFAULT_PREDICTIONS_DIR = PROJECT_ROOT / "reports"

EXPECTED_TEST_START = pd.Timestamp("2023-01-01")
EXPECTED_TEST_END = pd.Timestamp("2024-12-31")
PREDICTION_COLUMNS = ["date", "y_obs", "y_pred"]
FILE_PREFIX = "predictions_"
BASELINE_MODEL = "fao56_et0"
MODEL_FILES = {
    BASELINE_MODEL: None,
    "random_forest": "random_forest.joblib",
    "xgboost": "xgboost.json",
}
BUILTIN_MODELS = tuple(MODEL_FILES)
Y_OBS_TOLERANCE = 1e-6


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


def predictions_path(model: str, predictions_dir: Path | str = DEFAULT_PREDICTIONS_DIR) -> Path:
    """Path of the contract file for one model."""
    return Path(predictions_dir) / f"{FILE_PREFIX}{model}.csv"


def predict_builtin(
    test: pd.DataFrame,
    models_dir: Path | str = DEFAULT_MODELS_DIR,
) -> dict[str, np.ndarray]:
    """Predict the test days with FAO-56 ET0 and both committed ML-only models."""
    models_dir = Path(models_dir)
    predictions = {BASELINE_MODEL: add_et0(test, WIND_HEIGHT_M)["et0_mm"].to_numpy()}
    for model, filename in MODEL_FILES.items():
        if filename is None:
            continue
        model_path = models_dir / filename
        if not model_path.is_file():
            raise FileNotFoundError(f"Model not found: {model_path}. Re-run with --retrain.")
        if filename == "xgboost.json":
            estimator = XGBRegressor()
            estimator.load_model(model_path)
        else:
            estimator = joblib.load(model_path)
        predictions[model] = np.asarray(estimator.predict(test[FEATURES]), dtype=float)
    return predictions


def write_predictions(
    test: pd.DataFrame,
    predictions: dict[str, np.ndarray],
    predictions_dir: Path | str = DEFAULT_PREDICTIONS_DIR,
) -> list[Path]:
    """Write one contract file per model; every file has the same test dates."""
    predictions_dir = Path(predictions_dir)
    predictions_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for model, values in predictions.items():
        frame = pd.DataFrame(
            {
                "date": test["date"].dt.strftime("%Y-%m-%d"),
                "y_obs": test["et_obs_mm"].to_numpy(dtype=float),
                "y_pred": np.asarray(values, dtype=float),
            }
        )
        path = predictions_path(model, predictions_dir)
        frame.to_csv(path, index=False, columns=PREDICTION_COLUMNS)
        paths.append(path)
    return paths


def write_builtin_predictions(
    test_path: Path | str = DEFAULT_TEST_PATH,
    models_dir: Path | str = DEFAULT_MODELS_DIR,
    predictions_dir: Path | str = DEFAULT_PREDICTIONS_DIR,
) -> list[Path]:
    """Create the FAO-56, Random Forest and XGBoost prediction files."""
    test = load_test_data(test_path)
    return write_predictions(test, predict_builtin(test, models_dir), predictions_dir)


def read_prediction_file(path: Path | str) -> pd.DataFrame:
    """Read one contract file and validate its columns, dates and values."""
    path = Path(path)
    frame = pd.read_csv(path)
    if list(frame.columns) != PREDICTION_COLUMNS:
        raise ValueError(
            f"{path.name}: expected columns {PREDICTION_COLUMNS}, got {list(frame.columns)}"
        )
    try:
        frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path.name}: dates must be ISO YYYY-MM-DD") from exc
    if frame.empty:
        raise ValueError(f"{path.name}: no rows")
    if frame["date"].duplicated().any():
        raise ValueError(f"{path.name}: duplicate dates")
    if frame[["y_obs", "y_pred"]].isna().any().any():
        raise ValueError(f"{path.name}: missing y_obs or y_pred; write valid test days only")
    return frame.sort_values("date", kind="stable").reset_index(drop=True)


def check_same_dates(frames: dict[str, pd.DataFrame]) -> None:
    """Raise ValueError unless all files have identical date sets and y_obs."""
    reference_model, reference = next(iter(frames.items()))
    reference_dates = set(reference["date"])
    for model, frame in frames.items():
        dates = set(frame["date"])
        if dates != reference_dates:
            missing = sorted(reference_dates - dates)
            extra = sorted(dates - reference_dates)
            raise ValueError(
                f"{FILE_PREFIX}{model}.csv has {len(dates)} dates, "
                f"{FILE_PREFIX}{reference_model}.csv has {len(reference_dates)}; "
                "all prediction files must cover the same test days. "
                f"Missing: {_format_dates(missing)}; extra: {_format_dates(extra)}"
            )
        if not np.allclose(frame["y_obs"], reference["y_obs"], rtol=0, atol=Y_OBS_TOLERANCE):
            raise ValueError(
                f"{FILE_PREFIX}{model}.csv has different y_obs from "
                f"{FILE_PREFIX}{reference_model}.csv on the same dates"
            )


def _format_dates(dates: list[pd.Timestamp], limit: int = 5) -> str:
    if not dates:
        return "none"
    shown = ", ".join(date.date().isoformat() for date in dates[:limit])
    return shown + (f" and {len(dates) - limit} more" if len(dates) > limit else "")


def load_predictions(
    predictions_dir: Path | str = DEFAULT_PREDICTIONS_DIR,
    required: tuple[str, ...] = BUILTIN_MODELS,
) -> dict[str, pd.DataFrame]:
    """Read every predictions_*.csv in the folder, built-in models first.

    Raises FileNotFoundError naming the command to run if a required file is
    missing, and ValueError if the files cover different dates.
    """
    predictions_dir = Path(predictions_dir)
    found = {
        path.stem[len(FILE_PREFIX):]: path
        for path in sorted(predictions_dir.glob(f"{FILE_PREFIX}*.csv"))
    }
    missing = [model for model in required if model not in found]
    if missing:
        names = ", ".join(predictions_path(model, predictions_dir).name for model in missing)
        raise FileNotFoundError(
            f"Missing prediction file(s) in {predictions_dir}: {names}. "
            "Create the built-in files with `python -m ml.evaluation.predictions` "
            "(or run `python -m ml.evaluation.compare_models`); other models must "
            f"write {FILE_PREFIX}<model>.csv with columns {','.join(PREDICTION_COLUMNS)}."
        )
    order = [model for model in BUILTIN_MODELS if model in found]
    order += [model for model in found if model not in order]
    frames = {model: read_prediction_file(found[model]) for model in order}
    check_same_dates(frames)
    return frames


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    for path in write_builtin_predictions():
        print(f"Saved: {path}")


if __name__ == "__main__":
    main()
