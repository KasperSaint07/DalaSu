"""Field evidence cannot be replaced by proxies or unsupported daily labels."""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from ml.data.build_phenology import build
from ml.evaluation.actual_stages import DEFAULT_METADATA, stage_readiness, validate_stage_labels
from ml.evaluation.phase4 import ROOT, run


def field_fixture(tmp_path):
    """Synthetic evidence only, isolated from production records."""
    metadata = tmp_path/'metadata'
    shutil.copytree(DEFAULT_METADATA, metadata)
    path = metadata/'sources.json'
    sources = json.loads(path.read_text())
    sources['sources'].append(dict(id='synthetic_test', kind='field_record', url='test fixture'))
    path.write_text(json.dumps(sources))
    pd.DataFrame([dict(start_date='2023-06-01', end_date='2023-06-30', crop='maize',
                       stage='vegetative', source_id='synthetic_test',
                       evidence_locator='synthetic fixture, not real field evidence', status='observed')]
                 ).to_csv(metadata/'observed_intervals.csv', index=False)
    labels_dir = tmp_path/'labels'
    build(metadata_dir=metadata, output_dir=labels_dir)
    return metadata, labels_dir/'test_labels.csv'


def test_observed_groups_use_field_dates_for_all_models(tmp_path):
    metadata, path = field_fixture(tmp_path)
    output = tmp_path/'output'
    metrics, deltas = run(labels_path=path, metadata_dir=metadata, output_dir=output)
    labels = pd.read_csv(path)
    expected_dates = set(labels.loc[labels.actual_stage.eq('vegetative'), 'date'])
    assert 0 < len(expected_dates) < 561
    cohort = metrics.query("period == '2023–2024' and dimension == 'actual_stage' and group == 'vegetative'")
    assert len(cohort) == 7
    assert cohort.date_hash.nunique() == 1
    for row in cohort.itertuples():
        predictions = pd.read_csv(ROOT/'reports'/f'predictions_{row.model}.csv')
        selected = predictions[predictions.date.isin(expected_dates)]
        assert row.n == len(selected)
        assert row.mae == pytest.approx(np.abs(selected.y_pred-selected.y_obs).mean())
    paired = deltas.query("period == '2023–2024' and dimension == 'actual_stage' and group == 'vegetative'")
    scores = cohort.set_index('model')
    for row in paired.itertuples():
        assert row.delta_mae == pytest.approx(scores.loc[row.model, 'mae']-scores.loc[row.reference, 'mae'])
    readiness = json.loads((output/'phase4_readiness.json').read_text())
    assert readiness['actual_stage_status'] == 'partial'
    assert readiness['periods']['2023–2024']['observed_n'] == len(expected_dates)
    # Unknown stays in the denominator and never becomes an observed proxy.
    coverage = pd.read_csv(output/'phase4_coverage.csv')
    actual = coverage.query("period == '2023–2024' and dimension == 'actual_stage'")
    assert actual.n.sum() == 561
    assert actual.query("group == 'unknown'").n.iloc[0] == 561-len(expected_dates)


@pytest.mark.parametrize('mutation', ['unsupported', 'status', 'source', 'locator', 'stale'])
def test_invalid_evidence_fails_before_writing(tmp_path, mutation):
    metadata, path = field_fixture(tmp_path)
    labels = pd.read_csv(path)
    index = labels.index[labels.actual_stage.eq('vegetative')][0]
    if mutation == 'unsupported': labels.loc[index, 'actual_stage'] = 'proxy_greenup'
    elif mutation == 'status': labels.loc[index, 'status'] = 'approximate'
    elif mutation == 'source': labels.loc[index, 'actual_source'] = 'landsat_dal29'
    elif mutation == 'locator': labels.loc[index, 'evidence_locator'] = ''
    else:
        labels.loc[index, ['actual_stage', 'status']] = ['unknown', 'unknown']
    labels.to_csv(path, index=False)
    with pytest.raises(ValueError):
        run(labels_path=path, metadata_dir=metadata, output_dir=tmp_path/'output')
    assert not (tmp_path/'output').exists()


def test_readiness_full_coverage_does_not_claim_statistical_validation():
    dates = pd.DataFrame(dict(date=pd.to_datetime(['2023-01-01', '2024-06-01']),
                              actual_stage=['off_season', 'vegetative'], status='observed',
                              actual_source='synthetic', evidence_locator='fixture'))
    validate_stage_labels(dates)
    status = stage_readiness(dates)
    assert status['complete_test_stage_coverage']
    assert 'reproductive' in status['periods']['2024']['missing_stages']
    assert status['periods']['2024']['small_observed_groups'] == ['vegetative']


def test_strict_cli_writes_diagnostics_and_reports_incomplete(tmp_path):
    result = subprocess.run([sys.executable, '-m', 'ml.evaluation.phase4',
                             '--output-dir', str(tmp_path), '--require-complete-stages'],
                            env={**os.environ, 'PYTHONPATH': str(ROOT/'src')},
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert 'Incomplete field-stage evidence' in result.stderr
    assert (tmp_path/'phase4_readiness.json').exists()
    assert (tmp_path/'phase4_summary.md').exists()
