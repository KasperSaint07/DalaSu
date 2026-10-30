"""NDVI feature, fold-local preprocessing and persistence contracts."""
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor
from ml.hybrid import HybridPredictor, NDVI_FEATURES, prepare_features
from ml.train_ml import PROJECT_ROOT, FEATURES


@pytest.fixture
def frame():
    return pd.read_csv(PROJECT_ROOT / 'data/processed/ndvi/train.csv').head(80)


@pytest.mark.parametrize('name', ['rf', 'xgb'])
def test_missing_ndvi_roundtrip_and_inference(frame, tmp_path, name):
    X, et0 = prepare_features(frame, extra_features=NDVI_FEATURES)
    assert list(X) == FEATURES + list(NDVI_FEATURES)
    assert X.ndvi_last.isna().sum() == 13
    estimator = (RandomForestRegressor(n_estimators=3, random_state=42) if name == 'rf'
                 else XGBRegressor(n_estimators=3, n_jobs=1, random_state=42))
    pipeline = Pipeline([('imputer', SimpleImputer(strategy='median', keep_empty_features=True)), ('model', estimator)])
    pipeline.fit(X.iloc[:40], (frame.et_obs_mm-et0).iloc[:40])
    np.testing.assert_allclose(pipeline['imputer'].statistics_[-2:], X.iloc[:40, -2:].median())
    model = HybridPredictor(pipeline, extra_features=NDVI_FEATURES)
    model.save(tmp_path, name)
    restored = HybridPredictor.load(tmp_path, name)
    inputs = frame.drop(columns=['date', 'et_obs_mm', 'snapshot_date', 'ndvi_image_id'])
    np.testing.assert_allclose(model.predict(inputs), restored.predict(inputs))
    assert np.isfinite(restored.predict(inputs)).all()


@pytest.mark.parametrize('column,value', [('ndvi_last', 2), ('ndvi_last', np.inf),
                                          ('ndvi_age_days', -1), ('ndvi_age_days', 0.5)])
def test_invalid_ndvi(frame, column, value):
    frame[column] = frame[column].astype(float)
    frame.loc[20, column] = value
    with pytest.raises(ValueError):
        prepare_features(frame, extra_features=NDVI_FEATURES)


def test_ndvi_training_pipeline(tmp_path, monkeypatch):
    import ml.train_hybrid as training
    from sklearn.model_selection import RandomizedSearchCV
    calls = []
    class AuditedImputer(SimpleImputer):
        def fit(self, X, y=None):
            calls.append(tuple(X.index))
            result = super().fit(X, y)
            np.testing.assert_allclose(self.statistics_[-2:], X.iloc[:, -2:].median())
            return result
    monkeypatch.setattr(training, 'SimpleImputer', AuditedImputer)
    monkeypatch.setattr(training, 'model_specs', lambda: {
        'random_forest': (RandomForestRegressor(n_estimators=2, random_state=42), {'max_depth':[2]}),
        'xgboost': (XGBRegressor(n_estimators=2, n_jobs=1, random_state=42), {'max_depth':[2]})})
    monkeypatch.setattr(training, 'make_search', lambda estimator, space, cv:
        RandomizedSearchCV(estimator, space, n_iter=1, cv=cv, scoring='neg_mean_absolute_error'))
    # A local audited class cannot be pickled: restore the standard imputer before saving.
    original_save = HybridPredictor.save
    def save(self, directory, name):
        self.estimator['imputer'].__class__ = SimpleImputer
        original_save(self, directory, name)
    monkeypatch.setattr(HybridPredictor, 'save', save)
    data = PROJECT_ROOT / 'data/processed/ndvi'
    training.run(data/'train.csv', data/'test.csv', tmp_path/'models', tmp_path/'reports', use_ndvi=True)
    assert len(calls) == 60  # 2 models x 6 searches x (4 folds + refit)
    assert max(map(len, calls)) == 2407
    assert min(map(len, calls)) < 401
    for name in ('rf', 'xgb'):
        output = pd.read_csv(tmp_path/'reports'/f'predictions_hybrid_ndvi_{name}.csv')
        assert list(output) == ['date','y_obs','y_pred']
        assert len(output) == 561
