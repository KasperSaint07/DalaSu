"""Season assignment, comparable samples and saved-prediction regression checks."""
import hashlib
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import pytest

from ml.evaluation.compare_models import MODEL_LABELS, compare_models
from ml.evaluation.predictions import DEFAULT_PREDICTIONS_DIR
from ml.evaluation.seasonal import (
    assign_seasons, seasonal_metrics, seasonal_deltas, run, render_chart, render_report,
)


def test_all_months_boundaries_and_leap_day():
    dates = pd.Series(pd.to_datetime([f"2024-{m:02d}-01" for m in range(1, 13)] +
                                    ["2024-02-29", "2023-12-31", "2024-03-01"]))
    assert assign_seasons(dates).tolist() == [
        "DJF", "DJF", "MAM", "MAM", "MAM", "JJA", "JJA", "JJA", "SON", "SON", "SON", "DJF",
        "DJF", "DJF", "MAM",
    ]


def test_missing_date_rejected():
    with pytest.raises(ValueError, match="missing date"):
        assign_seasons(pd.Series([pd.Timestamp("2023-01-01"), pd.NaT]))


def sample_frames():
    dates = pd.to_datetime(["2023-01-01", "2023-02-01", "2023-03-01", "2023-04-01"])
    return {model: pd.DataFrame(dict(date=dates, y_obs=[1., 3., 2., 2.],
                                     y_pred=[2., 4., 2., 2.])) for model in MODEL_LABELS}


def test_hand_calculated_metrics_and_undefined_groups():
    frames = sample_frames()
    frames["hybrid_rf"]["y_pred"] = [1., 3., 2., 2.]
    metrics = seasonal_metrics(frames)
    indexed = metrics.set_index(["model", "season"])
    winter = indexed.loc[("random_forest", "DJF")]
    assert winter.n == 2
    assert winter.mae == winter.rmse == winter.bias == 1
    assert winter.pearson_r2 == pytest.approx(1)
    assert winter.r2_score == winter.nse == 0
    spring = indexed.loc[("random_forest", "MAM")]
    assert spring.mae == 0
    assert np.isnan(spring.nse)
    assert "r2_score" in spring.undefined_metrics
    summer = indexed.loc[("random_forest", "JJA")]
    assert summer.n == 0
    assert np.isnan(summer.mae)
    deltas = seasonal_deltas(metrics).set_index(["model", "season"])
    assert deltas.loc[("hybrid_rf", "DJF"), "delta_mae"] == -1
    assert deltas.loc[("hybrid_rf", "DJF"), "delta_rmse"] == -1
    assert "N/A" in render_report(metrics, deltas.reset_index())
    ET.fromstring(render_chart(metrics))


@pytest.mark.parametrize("mutation", ["date", "obs", "duplicate", "infinite"])
def test_noncomparable_frames_rejected(mutation):
    frames = sample_frames()
    frame = frames["hybrid_rf"]
    if mutation == "date":
        frame.loc[0, "date"] = pd.Timestamp("2023-01-02")
    elif mutation == "obs":
        frame.loc[0, "y_obs"] += 1
    elif mutation == "duplicate":
        frame.loc[0, "date"] = frame.loc[1, "date"]
    else:
        frame.loc[0, "y_pred"] = np.inf
    with pytest.raises(ValueError):
        seasonal_metrics(frames)


def test_saved_cohort_coverage_deltas_and_reproducibility(tmp_path, monkeypatch):
    import ml.evaluation.predictions as predictions
    def forbidden(*args, **kwargs):
        raise AssertionError("Inference is forbidden")
    monkeypatch.setattr(predictions, "predict_builtin", forbidden)
    paths = sorted(DEFAULT_PREDICTIONS_DIR.glob("predictions_*.csv"))
    def hashes():
        return [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    original = hashes()
    metrics, deltas = run(output_dir=tmp_path)
    assert len(metrics) == 28
    assert len(deltas) == 16
    assert set(metrics.model) == set(MODEL_LABELS)
    assert metrics.groupby("model").n.sum().eq(561).all()
    assert metrics.groupby("season").n.nunique().eq(1).all()
    dates = pd.read_csv(tmp_path / "seasonal_dates.csv")
    assert len(dates) == dates.date.nunique() == 561
    assert dates.season.notna().all()
    overall = compare_models().set_index("model")
    for model, group in metrics.groupby("model"):
        # Weighted MAE and pooled squared RMSE must recover the full holdout.
        assert np.average(group.mae, weights=group.n) == pytest.approx(overall.loc[model, "mae"])
        assert np.sqrt(np.average(group.rmse**2, weights=group.n)) == pytest.approx(overall.loc[model, "rmse"])
    indexed = metrics.set_index(["model", "season"])
    for row in deltas.itertuples():
        assert row.delta_mae == pytest.approx(indexed.loc[(row.model, row.season), "mae"] -
                                               indexed.loc[(row.baseline, row.season), "mae"])
    outputs = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    run(output_dir=tmp_path)
    assert outputs == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert hashes() == original
    ET.fromstring((tmp_path / "seasonal_errors.svg").read_text())


def test_missing_model_fails_before_writing(tmp_path):
    with pytest.raises(FileNotFoundError):
        run(predictions_dir=tmp_path, output_dir=tmp_path / "output")
    assert not (tmp_path / "output").exists()
