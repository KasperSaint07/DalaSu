"""Train residual RF/XGBoost on 2015--2022, then evaluate held-out 2023--2024."""
from __future__ import annotations

import argparse
import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import r2_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

from .evaluation.metrics import evaluate
from .hybrid_experiment import HybridExperiment
from .hybrid import HybridPredictor, prepare_features, NDVI_FEATURES
from .evaluation.predictions import load_test_data, write_predictions
from .train_ml import (
    FEATURES, SEED, N_OUTER_SPLITS, N_INNER_SPLITS, N_SEARCH_ITERATIONS,
    PROJECT_ROOT, TRAIN_PATH, assert_chronological_split,
    load_and_validate_training_data, make_search, model_specs, to_json_compatible,
)


def checked_splits(dates, n_splits):
    splits = list(TimeSeriesSplit(n_splits=n_splits).split(dates))
    for train, validation in splits:
        assert_chronological_split(dates, train, validation)
    return splits


def train_model(frame, estimator, parameter_space, use_et0_feature=False, extra_features=()):
    features, et0 = prepare_features(frame, use_et0_feature, extra_features)
    if extra_features:
        estimator = Pipeline([("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                              ("model", estimator)])
        parameter_space = {f"model__{key}": value for key, value in parameter_space.items()}
    residual = frame["et_obs_mm"] - et0
    dates = frame["date"]
    folds = []
    for fold, (train, validation) in enumerate(checked_splits(dates, N_OUTER_SPLITS), 1):
        print(f"  Outer fold {fold}/{N_OUTER_SPLITS}", flush=True)
        search = make_search(estimator, parameter_space,
                             checked_splits(dates.iloc[train], N_INNER_SPLITS))
        search.fit(features.iloc[train], residual.iloc[train])
        prediction = et0.iloc[validation].to_numpy() + search.predict(features.iloc[validation])
        obs = frame["et_obs_mm"].iloc[validation]
        folds.append({"fold": fold, "train_start": str(dates.iloc[train].min().date()),
                      "train_end": str(dates.iloc[train].max().date()),
                      "validation_start": str(dates.iloc[validation].min().date()),
                      "validation_end": str(dates.iloc[validation].max().date()),
                      "n_train": len(train), **evaluate(obs, prediction),
                      "r2_score": r2_score(obs, prediction),
                      "best_params": json.dumps(to_json_compatible(search.best_params_), sort_keys=True)})
    print("  Final four-fold search on all training data", flush=True)
    final = make_search(estimator, parameter_space, checked_splits(dates, N_INNER_SPLITS))
    final.fit(features, residual)
    return HybridPredictor(final.best_estimator_, use_et0_feature, extra_features), folds, final.best_params_


def validate_test(frame, reference):
    if len(frame) != 561 or not frame["date"].reset_index(drop=True).equals(reference["date"].reset_index(drop=True)):
        raise ValueError("Test must contain exactly the canonical 561 dates in order")
    prepare_features(frame)
    if not np.isfinite(frame["et_obs_mm"].to_numpy(dtype=float)).all():
        raise ValueError("Test observations must be finite")


def run(train_path=None, test_path=None,
        models_dir=None, reports_dir=None,
        use_et0_feature=False, use_ndvi=False):
    experiment = HybridExperiment(use_ndvi=use_ndvi, use_et0_feature=use_et0_feature)
    data_dir = experiment.data_dir(PROJECT_ROOT)
    train_path = Path(train_path) if train_path is not None else data_dir / "train.csv"
    test_path = Path(test_path) if test_path is not None else data_dir / "test.csv"
    models_dir = Path(models_dir) if models_dir is not None else experiment.models_dir(PROJECT_ROOT)
    reports_dir = (Path(reports_dir) if reports_dir is not None else
                   experiment.reports_dir(PROJECT_ROOT))
    extra_features = NDVI_FEATURES if use_ndvi else ()
    prefix = experiment.name
    frame = load_and_validate_training_data(train_path)
    if use_ndvi:
        canonical = load_and_validate_training_data(TRAIN_PATH)
        pd.testing.assert_frame_equal(frame[canonical.columns], canonical, check_exact=True)
        prepare_features(frame, use_et0_feature, extra_features)
    reports_dir.mkdir(parents=True, exist_ok=True)
    folds, parameters, fitted = [], {}, {}
    for model_name, (estimator, space) in model_specs().items():
        name = {"random_forest": "rf", "xgboost": "xgb"}[model_name]
        print(f"Training hybrid {name}", flush=True)
        model, results, best = train_model(frame, estimator, space, use_et0_feature, extra_features)
        model.save(models_dir, name)
        fitted[name] = model
        parameters[name] = to_json_compatible(best)
        folds.extend({"model": name, **result} for result in results)
    # Holdout is first read only after all model selection and fitting are complete.
    test = load_test_data(test_path)
    reference = load_test_data(PROJECT_ROOT / "data/processed/test.csv")
    validate_test(test, reference)
    pd.testing.assert_frame_equal(test[reference.columns], reference, check_exact=True)
    metrics = []
    for name, model in fitted.items():
        restored = HybridPredictor.load(models_dir, name)
        components = restored.predict_components(test)
        np.testing.assert_allclose(components["et_pred_mm"], model.predict(test), rtol=1e-7, atol=1e-7)
        output = pd.concat([test[["date", "et_obs_mm"]], components], axis=1)
        output.to_csv(reports_dir / f"components_{prefix}_{name}.csv", index=False)
        write_predictions(test, {f"{prefix}_{name}": components["et_pred_mm"]}, reports_dir)
        metrics.append({"model": f"{prefix}_{name}", **evaluate(test["et_obs_mm"], components["et_pred_mm"])})
    fold_frame = pd.DataFrame(folds)
    fold_frame.to_csv(reports_dir / f"{prefix}_cv_fold_metrics.csv", index=False)
    summary = fold_frame.groupby("model")[["mae", "rmse", "r2", "r2_score", "bias"]].agg(["mean", "std"])
    summary.columns = ["_".join(column) for column in summary.columns]
    summary.to_csv(reports_dir / f"{prefix}_cv_metrics.csv")
    metrics = pd.DataFrame(metrics)
    metrics.to_csv(reports_dir / f"{prefix}_test_metrics.csv", index=False)
    metadata = {"seed": SEED, "features": FEATURES + (["et0_mm"] if use_et0_feature else []) + list(extra_features),
                "use_ndvi": use_ndvi, "missing_policy": "fold-local median" if use_ndvi else "reject",
                "use_et0_feature": use_et0_feature, "training_start": str(frame.date.min().date()),
                "training_end": str(frame.date.max().date()), "training_rows": len(frame),
                "test_rows": len(test), "outer_splits": N_OUTER_SPLITS, "inner_splits": N_INNER_SPLITS,
                "search_iterations": N_SEARCH_ITERATIONS, "selection_metric": "MAE",
                "best_params": parameters, "wind_height_m": 6.2,
                "versions": {p: version(p) for p in ["numpy", "pandas", "scikit-learn", "xgboost", "joblib"]},
                "data_sha256": {"train": hashlib.sha256(train_path.read_bytes()).hexdigest(),
                                "test": hashlib.sha256(test_path.read_bytes()).hexdigest()},
                "r2_definition": "Squared Pearson correlation; r2_score is sklearn coefficient of determination"}
    (models_dir / "hybrid_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(metrics.to_string(index=False), flush=True)
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--use-et0-feature", action="store_true")
    parser.add_argument("--use-ndvi", action="store_true")
    parser.add_argument("--models-dir", type=Path)
    parser.add_argument("--reports-dir", type=Path)
    args = parser.parse_args(argv)
    run(models_dir=args.models_dir, reports_dir=args.reports_dir,
        use_et0_feature=args.use_et0_feature, use_ndvi=args.use_ndvi)


if __name__ == "__main__":
    main()
