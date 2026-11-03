"""Independent arithmetic, cohort reconciliation and immutable-input checks."""
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import pytest

from ml.evaluation.phase4 import (
    MODELS, PAIRS, ROOT, PERIODS, aggregate, differences, run, score, stability, validate_features,
)
from ml.evaluation.phenology import join_labels, grouped_metrics, LABELS
from ml.evaluation.predictions import DEFAULT_PREDICTIONS_DIR, load_canonical_predictions
from ml.evaluation.seasonal import seasonal_metrics
from ml.evaluation.compare_models import MODEL_LABELS


def test_manual_scores_and_kge_components():
    actual = score([1, 2, 3], [2, 3, 4])
    assert actual['mae'] == actual['rmse'] == actual['bias'] == 1
    assert actual['kge_r'] == pytest.approx(1)
    assert actual['kge_alpha'] == 1
    assert actual['kge_beta'] == 1.5
    assert actual['kge'] == pytest.approx(.5)
    assert actual['nse'] == -.5
    for obs, pred, reason in [([], [], 'empty_group'), ([0], [1], 'fewer_than_two_pairs'),
                               ([2, 2], [2, 3], 'constant_observations'),
                               ([1, 2], [3, 3], 'constant_predictions'),
                               ([-1, 1], [-2, 2], 'zero_observed_mean')]:
        result = score(obs, pred)
        assert reason in result['undefined_reasons']
        assert np.isnan(result['kge'])


def synthetic_joined():
    dates = pd.to_datetime(['2023-01-01', '2023-01-02', '2024-06-01'])
    frames = {m: pd.DataFrame(dict(date=dates, y_obs=[1., 3., 2.], y_pred=[2., 4., 2.])) for m in MODEL_LABELS}
    frames['hybrid_xgb'].y_pred = [1., 3., 2.]
    # Negative bias becoming more negative is worse, even though delta_bias < 0.
    frames['hybrid_ndvi_rf'].y_pred = [0., 1., 2.]
    labels = pd.DataFrame(dict(date=dates, crop=['maize', 'maize', 'soybean'], crop_status='inferred_rotation',
                               proxy_stage=['unknown', 'unknown', 'proxy_greenup'], actual_stage='unknown',
                               status='unknown', policy_version='test'))
    return join_labels(frames, labels)


def test_pair_signs_counts_empty_and_bias():
    metrics, coverage = aggregate(synthetic_joined())
    delta = differences(metrics)
    row = delta.query("period == '2023' and dimension == 'overall' and comparison == 'algorithm_v0'").iloc[0]
    assert row.delta_mae == row.delta_rmse == -1
    assert row.mae_preferred == 'hybrid_xgb'
    row = delta.query("period == '2023' and dimension == 'overall' and comparison == 'ndvi_rf'").iloc[0]
    assert row.delta_bias == -2.5
    assert row.delta_abs_bias == .5
    assert row.delta_mae == .5
    assert coverage.query("period == '2023' and dimension == 'proxy_stage'").n.sum() == 2
    empty = delta.query("group == 'proxy_decline'")
    assert empty.n.eq(0).all() and empty.delta_mae.isna().all()
    assert empty.mae_preferred.eq('undefined').all()
    assert stability(delta).query("dimension == 'proxy_stage'").undefined_groups.str.contains('proxy_decline').all()
    bad = metrics.copy()
    bad.loc[0, 'date_hash'] = 'different'
    with pytest.raises(ValueError, match='Unequal paired dates'): differences(bad)
    with pytest.raises(ValueError, match='Duplicate'): differences(pd.concat([metrics, metrics.iloc[:1]]))


def test_metadata_contract_rejection(tmp_path):
    validate_features(ROOT/'models')
    for source in (ROOT/'models').rglob('*_metadata.json'):
        dest = tmp_path/source.relative_to(ROOT/'models')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    path = tmp_path/'hybrid_xgb_metadata.json'
    meta = json.loads(path.read_text())
    meta['features'] = meta['features'][:-1]
    path.write_text(json.dumps(meta))
    with pytest.raises(ValueError, match='Unequal feature'): validate_features(tmp_path)


def test_saved_metrics_reconcile_and_repeat(tmp_path, monkeypatch):
    import ml.evaluation.predictions as predictions
    def forbidden(*args, **kwargs): raise AssertionError('Inference forbidden')
    monkeypatch.setattr(predictions, 'predict_builtin', forbidden)
    inputs = [*DEFAULT_PREDICTIONS_DIR.glob('predictions_*.csv'), LABELS, * (ROOT/'models').rglob('*')]
    inputs = [p for p in inputs if p.is_file()]
    original = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    metrics, deltas = run(output_dir=tmp_path)
    assert len(metrics) == len(deltas) == 120
    frames = load_canonical_predictions(required=tuple(MODEL_LABELS))
    stage_metrics, _ = grouped_metrics(join_labels(frames, pd.read_csv(LABELS)))
    seasons = seasonal_metrics(frames)
    for row in metrics.itertuples():
        frame = frames[row.model]
        if row.period != PERIODS[0]: frame = frame[frame.date.dt.year == int(row.period)]
        if row.dimension == 'overall':
            residual = frame.y_pred.to_numpy()-frame.y_obs.to_numpy()
            assert row.n == len(residual)
            assert row.mae == pytest.approx(np.abs(residual).mean())
            assert row.rmse == pytest.approx(np.sqrt(np.mean(residual**2)))
        elif row.dimension == 'proxy_stage':
            other = stage_metrics[(stage_metrics.period == row.period)&(stage_metrics.stage == row.group)&(stage_metrics.model == row.model)].iloc[0]
            assert row.n == other.n
            for key in ['mae', 'rmse', 'bias', 'kge', 'nse']:
                assert getattr(row, key) == pytest.approx(other[key], nan_ok=True)
        elif row.period == PERIODS[0]:
            other = seasons[(seasons.season == row.group)&(seasons.model == row.model)].iloc[0]
            assert row.n == other.n
            assert row.mae == pytest.approx(other.mae)
        if np.isfinite(row.kge):
            assert row.kge == pytest.approx(1-np.sqrt((row.kge_r-1)**2+(row.kge_alpha-1)**2+(row.kge_beta-1)**2))
    for (period, model), group in metrics.groupby(['period', 'model']):
        overall = group[group.dimension == 'overall'].iloc[0]
        for dimension in ['season', 'proxy_stage']:
            subset = group[(group.dimension == dimension)&(group.n > 0)]
            assert subset.n.sum() == overall.n
            assert np.average(subset.mae, weights=subset.n) == pytest.approx(overall.mae)
            assert np.sqrt(np.average(subset.rmse**2, weights=subset.n)) == pytest.approx(overall.rmse)
    coverage = pd.read_csv(tmp_path/'phase4_coverage.csv')
    assert coverage.query("group == 'unknown'").n.tolist() == [210, 130, 80]
    for row in deltas.itertuples():
        subset = metrics[(metrics.period == row.period)&(metrics.dimension == row.dimension)&(metrics.group == row.group)].set_index('model')
        for key in ['mae', 'rmse', 'bias', 'abs_bias', 'kge']:
            assert getattr(row, 'delta_'+key) == pytest.approx(subset.loc[row.model, key]-subset.loc[row.reference, key], nan_ok=True)
    for path in tmp_path.glob('*.svg'): ET.fromstring(path.read_text())
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    run(output_dir=tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert original == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}


def test_output_alias_cannot_modify_labels(tmp_path):
    (tmp_path/'phase4_dates.csv').symlink_to(LABELS)
    with pytest.raises(ValueError, match='conflicting paths'): run(output_dir=tmp_path)
    assert not (tmp_path/'phase4_summary.md').exists()


@pytest.mark.parametrize('finite_model', [None, 'hybrid_xgb'])
def test_report_with_undefined_overall_kge(tmp_path, finite_model):
    predictions_dir = tmp_path/'predictions'
    predictions_dir.mkdir()
    for source in DEFAULT_PREDICTIONS_DIR.glob('predictions_*.csv'):
        frame = pd.read_csv(source)
        if source.stem != f'predictions_{finite_model}':
            frame['y_pred'] = 1.0
        frame.to_csv(predictions_dir/source.name, index=False)
    output = tmp_path/'output'
    metrics, deltas = run(predictions_dir=predictions_dir, output_dir=output)
    overall = metrics.query("period == '2023–2024' and dimension == 'overall'")
    report = (output/'phase4_summary.md').read_text()
    assert 'N/A' in report
    assert len(list(output.iterdir())) == 10
    for path in output.glob('*.svg'):
        ET.fromstring(path.read_text())
    if finite_model is None:
        assert overall.kge.isna().all()
        assert deltas.delta_kge.isna().all()
        assert 'KGE неопределён для всех моделей' in report
        assert 'Наибольший KGE' not in report
    else:
        assert overall.loc[overall.model != finite_model, 'kge'].isna().all()
        assert np.isfinite(overall.loc[overall.model == finite_model, 'kge']).all()
        assert 'Наибольший KGE среди вариантов с определённой метрикой имеет Hybrid v0 XGBoost' in report
