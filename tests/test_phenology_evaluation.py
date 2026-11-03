"""Cohort integrity, independently calculated errors and reproducible artifacts."""
import hashlib
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import pytest

from ml.evaluation.phenology import join_labels, grouped_metrics, paired_deltas, run, MODEL_LABELS
from ml.evaluation.compare_models import compare_models


def sample():
    dates = pd.to_datetime(['2023-01-01', '2023-01-02', '2024-01-01'])
    frames = {m: pd.DataFrame(dict(date=dates, y_obs=[1., 3., 2.], y_pred=[2., 4., 2.])) for m in MODEL_LABELS}
    labels = pd.DataFrame(dict(date=dates, crop=['maize', 'maize', 'soybean'], crop_status='inferred_rotation',
                               proxy_stage=['unknown', 'unknown', 'proxy_greenup'], actual_stage='unknown',
                               status='unknown', policy_version='test'))
    return frames, labels


def test_manual_errors_empty_constant_and_years():
    frames, labels = sample()
    frames['hybrid_ndvi_rf']['y_pred'] = [1., 3., 2.]
    metrics, coverage = grouped_metrics(join_labels(frames, labels))
    row = metrics.query("period == '2023' and stage == 'unknown' and model == 'random_forest'").iloc[0]
    assert row.n == 2
    assert row.mae == row.rmse == row.bias == 1
    assert row.nse == 0
    assert row.pearson_r2 == pytest.approx(1)
    assert row.small_group
    empty = metrics.query("stage == 'proxy_decline'")
    assert empty.n.eq(0).all() and empty.mae.isna().all()
    constant = metrics.query("period == '2024' and stage == 'proxy_greenup'")
    assert constant.nse.isna().all()
    assert constant.undefined_reasons.str.contains('constant_observations').all()
    assert coverage.groupby('period').n.sum().to_dict() == {'2023': 2, '2023–2024': 3, '2024': 1}
    deltas = paired_deltas(metrics)
    row = deltas.query("period == '2023' and stage == 'unknown' and model == 'hybrid_ndvi_rf' and baseline == 'random_forest'").iloc[0]
    assert row.delta_mae == row.delta_rmse == -1


@pytest.mark.parametrize('mutation', ['missing_label', 'extra_label', 'duplicate_label', 'missing_stage', 'bad_stage', 'missing_model_date', 'duplicate_model_date', 'different_obs', 'infinite'])
def test_bad_joins_fail(mutation):
    frames, labels = sample()
    if mutation == 'missing_label': labels = labels.iloc[1:]
    elif mutation == 'extra_label':
        labels = pd.concat([labels, labels.iloc[:1].assign(date=pd.Timestamp('2024-02-01'))])
    elif mutation == 'duplicate_label': labels = pd.concat([labels, labels.iloc[:1]])
    elif mutation == 'missing_stage': labels.loc[0, 'proxy_stage'] = None
    elif mutation == 'bad_stage': labels.loc[0, 'proxy_stage'] = 'flowering'
    elif mutation == 'missing_model_date': frames['hybrid_rf'] = frames['hybrid_rf'].iloc[1:]
    elif mutation == 'duplicate_model_date': frames['hybrid_rf'] = pd.concat([frames['hybrid_rf'], frames['hybrid_rf'].iloc[:1]])
    elif mutation == 'different_obs': frames['hybrid_rf'].loc[0, 'y_obs'] = 99
    else: frames['hybrid_rf'].loc[0, 'y_pred'] = np.inf
    with pytest.raises(ValueError): join_labels(frames, labels)


def test_shuffled_rows_join_by_date():
    frames, labels = sample()
    frames['hybrid_rf'] = frames['hybrid_rf'].iloc[::-1]
    joined = join_labels(frames, labels.iloc[::-1])
    assert joined.groupby('date').y_obs.nunique().eq(1).all()


def test_real_data_reconciles_and_repeats(tmp_path, monkeypatch):
    import ml.evaluation.predictions as predictions
    def forbidden(*args, **kwargs): raise AssertionError('Inference forbidden')
    monkeypatch.setattr(predictions, 'predict_builtin', forbidden)
    inputs = list(predictions.DEFAULT_PREDICTIONS_DIR.glob('predictions_*.csv'))
    original = [hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs]
    metrics, deltas = run(output_dir=tmp_path)
    assert len(metrics) == 105 and len(deltas) == 60
    assert metrics.groupby(['period', 'stage']).n.nunique().eq(1).all()
    assert metrics.groupby(['period', 'stage']).date_hash.nunique().eq(1).all()
    coverage = pd.read_csv(tmp_path/'phenology_coverage.csv')
    assert coverage.groupby('period').n.sum().to_dict() == {'2023': 279, '2023–2024': 561, '2024': 282}
    assert coverage.query("stage == 'unknown'").set_index('period').n.to_dict() == {'2023': 130, '2023–2024': 210, '2024': 80}
    overall = compare_models().set_index('model')
    for model, group in metrics[metrics.period == '2023–2024'].groupby('model'):
        assert np.average(group.mae, weights=group.n) == pytest.approx(overall.loc[model, 'mae'])
        assert np.sqrt(np.average(group.rmse**2, weights=group.n)) == pytest.approx(overall.loc[model, 'rmse'])
    ET.fromstring((tmp_path/'phenology_errors.svg').read_text())
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    run(output_dir=tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert original == [hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs]
