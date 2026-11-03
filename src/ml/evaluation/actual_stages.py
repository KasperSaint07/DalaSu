"""Validate field-stage evidence separately from satellite vegetation proxies."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..data.build_phenology import DEFAULT_METADATA, load_intervals, validate_policy

ACTUAL_STAGES = ('emergence', 'vegetative', 'reproductive', 'maturation', 'off_season', 'unknown')


def validate_stage_labels(labels):
    """A named actual stage must be observed and carry locatable provenance."""
    if not labels.actual_stage.isin(ACTUAL_STAGES).all():
        raise ValueError('Unsupported actual stage')
    if not labels.status.isin(['observed', 'approximate', 'unknown']).all():
        raise ValueError('Unsupported evidence status')
    observed = labels.actual_stage.ne('unknown')
    if not observed.equals(labels.status.eq('observed')):
        raise ValueError('Actual stages require observed status; proxies cannot substitute')
    if observed.any():
        for column in ('actual_source', 'evidence_locator'):
            if column not in labels or labels.loc[observed, column].isna().any():
                raise ValueError('Observed stages require source and evidence locator')
            if labels.loc[observed, column].astype(str).str.strip().isin(['', 'unknown']).any():
                raise ValueError('Observed stages require source and evidence locator')


def validate_stage_evidence(labels, metadata_dir=DEFAULT_METADATA):
    """Reconcile daily stages with registered, nonoverlapping field intervals.

    Checks traceability and stale exports, not the scientific truth of a record.
    Source contents must still be reviewed before importing an interval.
    """
    validate_stage_labels(labels)
    root = Path(metadata_dir)
    paths = [root/name for name in ('policy.json', 'sources.json', 'observed_intervals.csv')]
    policy = json.loads(paths[0].read_text())
    validate_policy(policy)
    records = json.loads(paths[1].read_text())['sources']
    sources = {r['id']: r for r in records}
    if len(sources) != len(records):
        raise ValueError('Duplicate source IDs')
    intervals = load_intervals(paths[2], sources, policy)
    expected = {}
    for interval in intervals:
        for day in pd.date_range(interval['start_date'], interval['end_date']):
            expected[day] = interval
    for row in labels.itertuples():
        interval = expected.get(pd.Timestamp(row.date))
        if interval is None:
            if row.actual_stage != 'unknown':
                raise ValueError('Actual stage has no registered field interval')
        elif (row.actual_stage != interval['stage'] or row.status != 'observed'
              or row.crop != interval['crop']
              or getattr(row, 'actual_source', None) != interval['source_id']
              or getattr(row, 'evidence_locator', None) != interval['evidence_locator']):
            raise ValueError('Daily stage differs from field evidence; rebuild phenology labels')
    return paths


def stage_readiness(dates):
    """Report coverage, never infer completion from availability of proxy labels."""
    periods = {}
    for period in ('2023–2024', '2023', '2024'):
        subset = dates if period == '2023–2024' else dates[dates.date.dt.year == int(period)]
        counts = {stage: int(subset.actual_stage.eq(stage).sum()) for stage in ACTUAL_STAGES}
        observed = len(subset) - counts['unknown']
        periods[period] = dict(n=len(subset), observed_n=observed, unknown_n=counts['unknown'],
                               observed_share=observed/len(subset) if len(subset) else 0,
                               stage_counts=counts,
                               missing_stages=[s for s in ACTUAL_STAGES[:-1] if not counts[s]],
                               small_observed_groups=[s for s in ACTUAL_STAGES[:-1] if 0 < counts[s] < 30])
    total = periods['2023–2024']
    complete = total['n'] > 0 and total['unknown_n'] == 0
    return dict(
        objective_4='complete_test_coverage' if complete else 'incomplete_field_evidence',
        objective_5='implemented',
        actual_stage_status='complete_test_coverage' if complete else 'partial' if total['observed_n'] else 'unavailable',
        complete_test_stage_coverage=complete,
        periods=periods,
        limitation='Coverage is not scientific validation or proof of significance; inspect missing stages and small groups.',
        next_action='Review stage-specific results and coverage.' if complete else
        'Obtain US-Ne2 field-stage intervals for 2023–2024, register sources, rebuild labels and rerun phase4.',
    )
