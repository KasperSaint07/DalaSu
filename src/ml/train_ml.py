"""Train direct daily evapotranspiration models with nested time-series CV."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import RegressorMixin
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from xgboost import XGBRegressor


SEED = 42
FEATURES = [
    "tmax_c",
    "tmin_c",
    "rh_mean_pct",
    "ws_ms",
    "rn_mj_m2_day",
    "p_kpa",
    "precip_mm",
    "doy",
]
TARGET = "et_obs_mm"
DATE_COLUMN = "date"
EXPECTED_START = pd.Timestamp("2015-01-01")
TRAINING_CUTOFF = pd.Timestamp("2022-12-31")
N_OUTER_SPLITS = 5
N_INNER_SPLITS = 4
N_SEARCH_ITERATIONS = 16

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRAIN_PATH = PROJECT_ROOT / "data" / "processed" / "train.csv"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"


def load_and_validate_training_data(path: Path = TRAIN_PATH) -> pd.DataFrame:
    """Load the sole permitted dataset and validate its schema and date range."""
    if not path.is_file():
        raise FileNotFoundError(f"Training data not found: {path}")

    frame = pd.read_csv(path)
    required_columns = [DATE_COLUMN, TARGET, *FEATURES]
    missing_columns = sorted(set(required_columns) - set(frame.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    if frame.empty:
        raise ValueError("Training data is empty")
    if frame[required_columns].isna().any().any():
        null_counts = frame[required_columns].isna().sum()
        raise ValueError(
            f"Missing values found: {null_counts[null_counts > 0].to_dict()}"
        )

    try:
        frame[DATE_COLUMN] = pd.to_datetime(
            frame[DATE_COLUMN], format="%Y-%m-%d", errors="raise"
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Dates must use valid YYYY-MM-DD values") from exc

    if frame[DATE_COLUMN].duplicated().any():
        duplicates = frame.loc[
            frame[DATE_COLUMN].duplicated(keep=False), DATE_COLUMN
        ].dt.strftime("%Y-%m-%d")
        raise ValueError(f"Duplicate dates found: {duplicates.tolist()[:10]}")

    frame = frame.sort_values(DATE_COLUMN, kind="stable").reset_index(drop=True)
    actual_start = frame[DATE_COLUMN].iloc[0]
    actual_end = frame[DATE_COLUMN].iloc[-1]
    if actual_end > TRAINING_CUTOFF:
        raise ValueError(
            f"Training data contains dates after {TRAINING_CUTOFF.date()}: "
            f"maximum is {actual_end.date()}"
        )
    if actual_start != EXPECTED_START or actual_end != TRAINING_CUTOFF:
        raise ValueError(
            "Unexpected training period: expected "
            f"{EXPECTED_START.date()} through {TRAINING_CUTOFF.date()}, got "
            f"{actual_start.date()} through {actual_end.date()}"
        )

    numeric_columns = [TARGET, *FEATURES]
    converted = frame[numeric_columns].apply(pd.to_numeric, errors="coerce")
    if converted.isna().any().any():
        invalid_counts = converted.isna().sum()
        raise ValueError(
            "Non-numeric feature or target values found: "
            f"{invalid_counts[invalid_counts > 0].to_dict()}"
        )
    if not np.isfinite(converted.to_numpy(dtype=float)).all():
        raise ValueError("Infinite feature or target values found")
    frame[numeric_columns] = converted
    return frame


def model_specs() -> dict[str, tuple[RegressorMixin, dict[str, list[Any]]]]:
    """Return deterministic estimators and bounded hyperparameter spaces."""
    return {
        "random_forest": (
            RandomForestRegressor(random_state=SEED, n_jobs=1),
            {
                "n_estimators": [200, 400, 600, 800],
                "max_depth": [None, 8, 12, 16, 24],
                "min_samples_split": [2, 4, 8, 12],
                "min_samples_leaf": [1, 2, 4, 8],
                "max_features": [1.0, "sqrt", 0.7],
            },
        ),
        "xgboost": (
            XGBRegressor(
                objective="reg:squarederror",
                random_state=SEED,
                n_jobs=1,
                tree_method="hist",
            ),
            {
                "n_estimators": [200, 400, 600, 800],
                "max_depth": [2, 3, 4, 6, 8],
                "learning_rate": [0.01, 0.03, 0.05, 0.1],
                "subsample": [0.7, 0.85, 1.0],
                "colsample_bytree": [0.7, 0.85, 1.0],
                "min_child_weight": [1, 3, 5, 8],
                "reg_lambda": [0.5, 1.0, 2.0, 5.0],
            },
        ),
    }


def make_search(
    estimator: RegressorMixin,
    parameter_space: dict[str, list[Any]],
    cv: TimeSeriesSplit,
) -> RandomizedSearchCV:
    """Build a reproducible time-aware hyperparameter search."""
    return RandomizedSearchCV(
        estimator=estimator,
        param_distributions=parameter_space,
        n_iter=N_SEARCH_ITERATIONS,
        scoring="neg_mean_absolute_error",
        n_jobs=-1,
        cv=cv,
        refit=True,
        random_state=SEED,
        return_train_score=False,
        error_score="raise",
    )


def assert_chronological_split(
    dates: pd.Series, train_indices: np.ndarray, validation_indices: np.ndarray
) -> None:
    """Fail fast if a CV split leaks future observations into training."""
    if train_indices.max() >= validation_indices.min():
        raise RuntimeError("Time-series CV indices are not chronological")
    if dates.iloc[train_indices].max() >= dates.iloc[validation_indices].min():
        raise RuntimeError("Time-series CV dates are not chronological")


def nested_cv(
    frame: pd.DataFrame,
    model_name: str,
    estimator: RegressorMixin,
    parameter_space: dict[str, list[Any]],
) -> list[dict[str, Any]]:
    """Evaluate one model with outer evaluation and inner tuning splits."""
    features = frame[FEATURES]
    target = frame[TARGET]
    dates = frame[DATE_COLUMN]
    outer_cv = TimeSeriesSplit(n_splits=N_OUTER_SPLITS)
    fold_results: list[dict[str, Any]] = []

    for fold, (train_indices, validation_indices) in enumerate(
        outer_cv.split(features), start=1
    ):
        assert_chronological_split(dates, train_indices, validation_indices)
        inner_cv = TimeSeriesSplit(n_splits=N_INNER_SPLITS)
        search = make_search(estimator, parameter_space, inner_cv)
        search.fit(features.iloc[train_indices], target.iloc[train_indices])
        predictions = search.predict(features.iloc[validation_indices])

        fold_results.append(
            {
                "model": model_name,
                "fold": fold,
                "train_start": dates.iloc[train_indices].min().date().isoformat(),
                "train_end": dates.iloc[train_indices].max().date().isoformat(),
                "validation_start": dates.iloc[validation_indices]
                .min()
                .date()
                .isoformat(),
                "validation_end": dates.iloc[validation_indices]
                .max()
                .date()
                .isoformat(),
                "n_train": len(train_indices),
                "n_validation": len(validation_indices),
                "mae": mean_absolute_error(
                    target.iloc[validation_indices], predictions
                ),
                "rmse": np.sqrt(
                    mean_squared_error(target.iloc[validation_indices], predictions)
                ),
                "r2": r2_score(target.iloc[validation_indices], predictions),
            }
        )
    return fold_results


def aggregate_metrics(fold_metrics: pd.DataFrame) -> pd.DataFrame:
    """Summarize outer-fold metrics for each model."""
    summary = (
        fold_metrics.groupby("model", sort=False)[["mae", "rmse", "r2"]]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.columns = [
        "model",
        "mae_mean",
        "mae_std",
        "rmse_mean",
        "rmse_std",
        "r2_mean",
        "r2_std",
    ]
    return summary


def to_json_compatible(value: Any) -> Any:
    """Convert NumPy scalar values from searches to standard JSON values."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_compatible(item) for item in value]
    return value


def main() -> None:
    frame = load_and_validate_training_data()
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    all_fold_results: list[dict[str, Any]] = []
    final_best_params: dict[str, dict[str, Any]] = {}

    for model_name, (estimator, parameter_space) in model_specs().items():
        print(f"Running nested time-series CV for {model_name}...", flush=True)
        all_fold_results.extend(
            nested_cv(frame, model_name, estimator, parameter_space)
        )

        print(f"Fitting final search for {model_name}...", flush=True)
        final_search = make_search(
            estimator,
            parameter_space,
            TimeSeriesSplit(n_splits=N_INNER_SPLITS),
        )
        final_search.fit(frame[FEATURES], frame[TARGET])
        final_best_params[model_name] = to_json_compatible(final_search.best_params_)
        if model_name == "xgboost":
            final_search.best_estimator_.save_model(MODELS_DIR / "xgboost.json")
        else:
            joblib.dump(final_search.best_estimator_, MODELS_DIR / f"{model_name}.joblib")

    fold_metrics = pd.DataFrame(all_fold_results)
    summary_metrics = aggregate_metrics(fold_metrics)
    fold_metrics.to_csv(REPORTS_DIR / "train_cv_fold_metrics.csv", index=False)
    summary_metrics.to_csv(REPORTS_DIR / "train_cv_metrics.csv", index=False)

    with (REPORTS_DIR / "best_params.json").open("w", encoding="utf-8") as output:
        json.dump(final_best_params, output, indent=2, sort_keys=True)
        output.write("\n")

    metadata = {
        "seed": SEED,
        "features": FEATURES,
        "target": TARGET,
        "actual_start_date": frame[DATE_COLUMN].min().date().isoformat(),
        "actual_end_date": frame[DATE_COLUMN].max().date().isoformat(),
        "row_count": len(frame),
        "cv_type": "nested TimeSeriesSplit",
        "outer_folds": N_OUTER_SPLITS,
        "inner_folds": N_INNER_SPLITS,
        "hyperparameter_search": "RandomizedSearchCV",
        "search_iterations": N_SEARCH_ITERATIONS,
        "selection_metric": "MAE",
        "uses_corrected_base_precipitation": True,
        "precipitation_source": "AmeriFlux BASE P_PI_F_1_1_1",
        "wind_speed_source": "FLUXNET WS_F",
        "wind_measurement_height_m": 6.2,
        "net_radiation_source": "FLUXNET NETRAD",
        "integrated_variables_require_full_day": True,
    }
    with (REPORTS_DIR / "training_metadata.json").open(
        "w", encoding="utf-8"
    ) as output:
        json.dump(metadata, output, indent=2)
        output.write("\n")

    print("\nOuter-fold CV summary:")
    print(summary_metrics.to_string(index=False))


if __name__ == "__main__":
    main()
