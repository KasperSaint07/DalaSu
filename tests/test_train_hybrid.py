"""Contract and leakage regression tests for DAL-28."""
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

from ml.hybrid import HybridPredictor, prepare_features
from ml.fao56.baseline import add_et0
from ml.train_ml import FEATURES, TRAIN_PATH, load_and_validate_training_data
from ml.train_hybrid import checked_splits, validate_test, PROJECT_ROOT


@pytest.fixture
def frame():
    return pd.read_csv(TRAIN_PATH).head(40)


class ConstantResidual:
    def predict(self, features):
        return np.full(len(features), -1.25)


def test_prediction_is_et0_plus_residual_without_observations(frame):
    frame = frame.drop(columns="et_obs_mm")
    prediction = HybridPredictor(ConstantResidual()).predict_components(frame)
    np.testing.assert_allclose(prediction.et_pred_mm, add_et0(frame).et0_mm - 1.25)
    assert (prediction.et_pred_mm < 0).any()  # No accidental clipping.


@pytest.mark.parametrize("enabled", [False, True])
def test_feature_contract_and_wind_conversion(frame, enabled):
    original = frame.copy(deep=True)
    features, et0 = prepare_features(frame, enabled)
    assert list(features.columns) == FEATURES + (["et0_mm"] if enabled else [])
    np.testing.assert_allclose(features.ws_ms, frame.ws_ms)
    np.testing.assert_allclose(et0, add_et0(frame, 6.2).et0_mm)
    assert not np.allclose(et0, add_et0(frame, 2.0).et0_mm)
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("name", ["rf", "xgb"])
def test_serialization_round_trip(frame, tmp_path, enabled, name):
    estimator = (RandomForestRegressor(n_estimators=3, random_state=42) if name == "rf"
                 else XGBRegressor(n_estimators=3, max_depth=2, n_jobs=1, random_state=42))
    features, et0 = prepare_features(frame, enabled)
    estimator.fit(features, frame.et_obs_mm - et0)
    model = HybridPredictor(estimator, enabled)
    model.save(tmp_path, name)
    restored = HybridPredictor.load(tmp_path, name)
    np.testing.assert_allclose(model.predict(frame), restored.predict(frame))


def test_training_rejects_future_data(tmp_path):
    frame = pd.read_csv(TRAIN_PATH)
    frame.loc[len(frame)] = frame.iloc[-1]
    frame.loc[len(frame) - 1, "date"] = "2023-01-01"
    path = tmp_path / "train.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="after 2022-12-31"):
        load_and_validate_training_data(path)


def test_nested_splits_are_chronological():
    dates = load_and_validate_training_data().date
    outer = checked_splits(dates, 5)
    assert len(outer) == 5
    for train, validation in outer:
        assert dates.iloc[train].max() < dates.iloc[validation].min()
        inner_dates = dates.iloc[train]
        inner = checked_splits(inner_dates, 4)
        assert len(inner) == 4
        for fitting, tuning in inner:
            assert inner_dates.iloc[fitting].max() < inner_dates.iloc[tuning].min()


def test_canonical_holdout_dates():
    frame = pd.read_csv(PROJECT_ROOT / "data/processed/test.csv", parse_dates=["date"])
    validate_test(frame, frame)
    changed = frame.copy()
    changed.loc[0, "date"] += pd.Timedelta(days=1)
    with pytest.raises(ValueError, match="canonical 561"):
        validate_test(changed, frame)
    with pytest.raises(ValueError, match="canonical 561"):
        validate_test(frame.iloc[:-1], frame)


def test_nonfinite_inputs_rejected(frame):
    frame.loc[0, "ws_ms"] = np.inf
    with pytest.raises(ValueError, match="finite"):
        prepare_features(frame)


def test_zero_residual_recovers_baseline(frame):
    class ZeroResidual:
        def predict(self, features):
            return np.zeros(len(features))
    np.testing.assert_allclose(HybridPredictor(ZeroResidual()).predict(frame), add_et0(frame).et0_mm)


@pytest.mark.parametrize("enabled", [False, True])
def test_training_pipeline_targets_residuals_and_exports_same_dates(tmp_path, monkeypatch, enabled):
    import ml.train_hybrid as training
    from sklearn.model_selection import RandomizedSearchCV

    original_train = load_and_validate_training_data()
    _, et0 = prepare_features(original_train)
    expected_residual = original_train.et_obs_mm - et0
    fits = []

    class AuditedSearch(RandomizedSearchCV):
        def fit(self, X, y, **kwargs):
            np.testing.assert_allclose(y, expected_residual.loc[X.index])
            assert original_train.loc[X.index, "date"].max() <= pd.Timestamp("2022-12-31")
            assert list(X.columns) == FEATURES + (["et0_mm"] if enabled else [])
            fits.append(len(X))
            return super().fit(X, y, **kwargs)

    monkeypatch.setattr(training, "model_specs", lambda: {
        "random_forest": (RandomForestRegressor(n_estimators=2, max_depth=2, random_state=42), {}),
        "xgboost": (XGBRegressor(n_estimators=2, max_depth=2, n_jobs=1, random_state=42), {}),
    })
    monkeypatch.setattr(training, "make_search", lambda estimator, space, cv:
                        AuditedSearch(estimator, space, n_iter=1, cv=cv,
                                      scoring="neg_mean_absolute_error", random_state=42))
    training.run(models_dir=tmp_path / "models", reports_dir=tmp_path / "reports", use_et0_feature=enabled)
    assert len(fits) == 12  # Five outer searches plus final search, for both models.
    reference = pd.read_csv(PROJECT_ROOT / "data/processed/test.csv")
    for name in ["rf", "xgb"]:
        output = pd.read_csv(tmp_path / "reports" / f"predictions_hybrid_{name}.csv")
        assert len(output) == 561
        pd.testing.assert_series_equal(output.date, reference.date)
        np.testing.assert_allclose(output.et_pred_mm, output.et0_mm + output.residual_pred_mm)
