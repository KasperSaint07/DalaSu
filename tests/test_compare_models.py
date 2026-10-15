"""Tests for the common FAO-56 and ML-only comparison."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from ml.evaluation.compare_models import compare_models, render_report
from ml.train_ml import FEATURES


class ConstantModel:
    def __init__(self, value: float):
        self.value = value

    def predict(self, features):
        return np.full(len(features), self.value)


def sample_test() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-01-01", "2024-12-31"]),
            "et_obs_mm": [1.0, 3.0],
            "tmax_c": [10.0, 20.0],
            "tmin_c": [2.0, 10.0],
            "rh_mean_pct": [70.0, 60.0],
            "ws_ms": [2.0, 3.0],
            "rn_mj_m2_day": [5.0, 10.0],
            "p_kpa": [97.0, 97.0],
            "precip_mm": [0.0, 0.0],
            "doy": [1, 366],
        }
    )


def test_compare_models_uses_same_observations(tmp_path: Path):
    for filename, value in [
        ("random_forest.joblib", 1.0),
        ("xgboost.joblib", 3.0),
    ]:
        joblib.dump(ConstantModel(value), tmp_path / filename)

    metrics = compare_models(sample_test(), tmp_path).set_index("model")

    assert list(metrics.index) == [
        "FAO-56 ET0",
        "Random Forest ML-only",
        "XGBoost ML-only",
    ]
    assert (metrics["n"] == 2).all()
    assert metrics.loc["Random Forest ML-only", "mae"] == pytest.approx(1.0)
    assert metrics.loc["XGBoost ML-only", "mae"] == pytest.approx(1.0)
    assert metrics.loc["Random Forest ML-only", "bias"] == pytest.approx(-1.0)
    assert metrics.loc["XGBoost ML-only", "bias"] == pytest.approx(1.0)


def test_report_states_d1_and_reproduction_command(tmp_path: Path):
    metrics = pd.DataFrame(
        [
            ["FAO-56 ET0", 2, 2.0, 1.5, 0.5, 1.0],
            ["Random Forest ML-only", 2, 1.0, 0.8, 0.8, 0.1],
            ["XGBoost ML-only", 2, 1.1, 0.9, 0.8, 0.2],
        ],
        columns=["model", "n", "rmse", "mae", "r2", "bias"],
    )

    report = render_report(metrics, sample_test())

    assert "D-1: actual ET is the comparison target" in report
    assert "ET0 without a crop coefficient" in report
    assert "PYTHONPATH=src python3 -m ml.evaluation.compare_models --retrain" in report
    assert "46.7% reduction" in report
