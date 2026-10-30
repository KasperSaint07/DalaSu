"""Exporting optional feature experiments must not replace baseline predictions."""
import pandas as pd
import pytest
from ml.evaluation import export_hybrid
from ml.hybrid_experiment import HybridExperiment


@pytest.mark.parametrize('ndvi', [False, True])
@pytest.mark.parametrize('et0', [False, True])
@pytest.mark.parametrize('override', [False, True])
def test_export_preserves_other_experiments(tmp_path, monkeypatch, ndvi, et0, override):
    monkeypatch.setattr(export_hybrid, 'PROJECT_ROOT', tmp_path)
    expected_name = ('hybrid_ndvi' if ndvi else 'hybrid') + ('_with_et0' if et0 else '')
    reports = tmp_path/'reports'
    reports.mkdir()
    sentinels = {}
    for prefix in ('hybrid', 'hybrid_ndvi'):
        for name in ('rf', 'xgb'):
            path = reports/f'predictions_{prefix}_{name}.csv'
            path.write_text('existing experiment\n')
            sentinels[path] = path.read_bytes()
    test = pd.DataFrame({'date': pd.to_datetime(['2023-01-01']), 'et_obs_mm': [1.]})
    reads = []
    def load_test(path):
        reads.append(path)
        return test.copy()
    class Model:
        extra_features = ('ndvi_last', 'ndvi_age_days') if ndvi else ()
        use_et0_feature = et0
        def predict_components(self, frame):
            return pd.DataFrame({'et0_mm':[2.], 'residual_pred_mm':[-0.5], 'et_pred_mm':[1.5]})
    monkeypatch.setattr(export_hybrid, 'load_test_data', load_test)
    monkeypatch.setattr(export_hybrid.HybridPredictor, 'load', lambda *args: Model())
    argv = ['--models-dir', str(tmp_path/'arbitrary-model-location')]
    if override:
        argv += ['--reports-dir', str(reports)]
    export_hybrid.main(argv)
    target = reports if override or not et0 else reports/expected_name
    for name in ('rf', 'xgb'):
        output = pd.read_csv(target/f'predictions_{expected_name}_{name}.csv')
        assert output.y_pred.tolist() == [1.5]
        assert list(output) == ['date', 'y_obs', 'y_pred']
        assert (target/f'components_{expected_name}_{name}.csv').is_file()
    for path, content in sentinels.items():
        if et0 or not path.name.startswith(f'predictions_{expected_name}_'):
            assert path.read_bytes() == content
    expected_data = tmp_path/'data/processed'/('ndvi' if ndvi else '')/'test.csv'
    assert reads == [expected_data, expected_data]
    experiment = HybridExperiment(ndvi, et0)
    assert experiment.name == expected_name
    assert experiment.reports_dir(tmp_path) == (reports/expected_name if et0 else reports)
