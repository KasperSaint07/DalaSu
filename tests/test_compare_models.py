"""Tests for the prediction-file contract and the common model comparison."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from xgboost import XGBRegressor

from ml.evaluation.compare_models import compare_models, render_report, run
from ml.evaluation.predictions import (
    PREDICTION_COLUMNS,
    load_predictions,
    predict_builtin,
    write_predictions,
)
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


def write_sample_models(models_dir: Path) -> None:
    joblib.dump(ConstantModel(1.0), models_dir / "random_forest.joblib")
    xgb = XGBRegressor(n_estimators=1, max_depth=1, n_jobs=1, base_score=3.0)
    xgb.fit(sample_test()[FEATURES], np.full(2, 3.0))
    xgb.save_model(models_dir / "xgboost.json")


def write_sample_predictions(predictions_dir: Path) -> None:
    test = sample_test()
    write_predictions(
        test,
        {"fao56_et0": [2.0, 2.0], "random_forest": [1.0, 1.0], "xgboost": [3.0, 3.0]},
        predictions_dir,
    )


def test_builtin_predictions_use_same_observations(tmp_path: Path):
    write_sample_models(tmp_path)
    paths = write_predictions(sample_test(), predict_builtin(sample_test(), tmp_path), tmp_path)

    assert [path.name for path in paths] == [
        "predictions_fao56_et0.csv",
        "predictions_random_forest.csv",
        "predictions_xgboost.csv",
    ]
    frame = pd.read_csv(tmp_path / "predictions_random_forest.csv")
    assert list(frame.columns) == PREDICTION_COLUMNS
    assert frame["date"].tolist() == ["2023-01-01", "2024-12-31"]

    metrics = compare_models(tmp_path).set_index("model")
    assert list(metrics.index) == ["fao56_et0", "random_forest", "xgboost"]
    assert (metrics["n"] == 2).all()
    assert metrics.loc["random_forest", "mae"] == pytest.approx(1.0)
    assert metrics.loc["xgboost", "mae"] == pytest.approx(1.0)
    assert metrics.loc["random_forest", "bias"] == pytest.approx(-1.0)
    assert metrics.loc["xgboost", "bias"] == pytest.approx(1.0)


def test_metrics_table_has_all_six_metrics(tmp_path: Path):
    write_sample_predictions(tmp_path)
    metrics = compare_models(tmp_path)

    assert list(metrics.columns) == ["model", "n", "rmse", "mae", "r2", "bias", "nse", "kge"]
    # obs = [1, 3], FAO-56 pred = [2, 2]: errors [1, -1], SS_tot = 2.
    row = metrics.set_index("model").loc["fao56_et0"]
    assert row["rmse"] == pytest.approx(1.0)
    assert row["bias"] == pytest.approx(0.0)
    assert row["nse"] == pytest.approx(0.0)


def test_extra_model_file_is_compared(tmp_path: Path):
    write_sample_predictions(tmp_path)
    pd.DataFrame(
        {"date": ["2023-01-01", "2024-12-31"], "y_obs": [1.0, 3.0], "y_pred": [1.0, 3.0]}
    ).to_csv(tmp_path / "predictions_hybrid.csv", index=False)

    metrics = compare_models(tmp_path).set_index("model")

    assert list(metrics.index) == ["fao56_et0", "random_forest", "xgboost", "hybrid"]
    assert metrics.loc["hybrid", "nse"] == pytest.approx(1.0)
    assert metrics.loc["hybrid", "kge"] == pytest.approx(1.0)


def test_date_set_mismatch_raises(tmp_path: Path):
    write_sample_predictions(tmp_path)
    pd.DataFrame(
        {"date": ["2023-01-01", "2024-12-30"], "y_obs": [1.0, 3.0], "y_pred": [1.0, 3.0]}
    ).to_csv(tmp_path / "predictions_hybrid.csv", index=False)

    with pytest.raises(ValueError, match=r"predictions_hybrid\.csv.*same test days.*2024-12-31"):
        compare_models(tmp_path)


def test_different_observations_raise(tmp_path: Path):
    write_sample_predictions(tmp_path)
    pd.DataFrame(
        {"date": ["2023-01-01", "2024-12-31"], "y_obs": [1.0, 4.0], "y_pred": [1.0, 3.0]}
    ).to_csv(tmp_path / "predictions_hybrid.csv", index=False)

    with pytest.raises(ValueError, match=r"predictions_hybrid\.csv has different y_obs"):
        compare_models(tmp_path)


def test_missing_predictions_file_gives_helpful_message(tmp_path: Path):
    write_sample_predictions(tmp_path)
    (tmp_path / "predictions_xgboost.csv").unlink()

    with pytest.raises(
        FileNotFoundError,
        match=r"predictions_xgboost\.csv.*python -m ml\.evaluation\.predictions",
    ):
        load_predictions(tmp_path)


def test_wrong_columns_raise(tmp_path: Path):
    write_sample_predictions(tmp_path)
    pd.DataFrame(
        {"date": ["2023-01-01", "2024-12-31"], "obs": [1.0, 3.0], "pred": [1.0, 3.0]}
    ).to_csv(tmp_path / "predictions_hybrid.csv", index=False)

    with pytest.raises(ValueError, match=r"predictions_hybrid\.csv: expected columns"):
        compare_models(tmp_path)


def test_report_states_d1_contract_and_reproduction_command():
    metrics = pd.DataFrame(
        [
            ["fao56_et0", 2, 2.0, 1.5, 0.5, 1.0, -0.1, 0.2],
            ["random_forest", 2, 1.0, 0.8, 0.8, 0.1, 0.7, 0.8],
            ["xgboost", 2, 1.1, 0.9, 0.8, 0.2, 0.6, 0.7],
        ],
        columns=["model", "n", "rmse", "mae", "r2", "bias", "nse", "kge"],
    )

    report = render_report(metrics, sample_test()["date"])

    assert "D-1: actual ET is the comparison target" in report
    assert "ET0 without a crop coefficient" in report
    assert "python -m ml.evaluation.compare_models" in report
    assert "--retrain" in report
    assert "46.7% reduction" in report
    assert "| NSE | KGE |" in report
    assert "`predictions_fao56_et0.csv`" in report
    assert "date,y_obs,y_pred" in report
    assert "±0.003" in report
    assert "xgboost.json" in report


def test_run_from_files_writes_outputs(tmp_path: Path):
    write_sample_predictions(tmp_path)
    metrics = run(
        predictions_dir=tmp_path,
        metrics_path=tmp_path / "comparison_metrics.csv",
        report_path=tmp_path / "report.md",
        write_predictions=False,
    )

    assert len(metrics) == 3
    assert (tmp_path / "comparison_metrics.csv").is_file()
    assert "2023-01-01--2024-12-31" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_missing_native_xgboost_suggests_retraining(tmp_path: Path):
    joblib.dump(ConstantModel(1.0), tmp_path / "random_forest.joblib")
    with pytest.raises(FileNotFoundError, match=r"xgboost.json.*--retrain"):
        predict_builtin(sample_test(), tmp_path)
