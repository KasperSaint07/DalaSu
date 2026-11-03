"""Describe saved holdout errors by frozen vegetation proxies; never fit models."""
from __future__ import annotations

import argparse
import hashlib
import json
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

from .compare_models import MODEL_LABELS
from .metrics import evaluate
from .predictions import DEFAULT_PREDICTIONS_DIR, DEFAULT_TEST_PATH, load_canonical_predictions
from .actual_stages import validate_stage_labels

ROOT = Path(__file__).resolve().parents[3]
LABELS = ROOT / 'data/processed/phenology/test_labels.csv'
STAGES = ('proxy_low_vegetation', 'proxy_greenup', 'proxy_high_vegetation', 'proxy_decline', 'unknown')
SCORES = ('mae', 'rmse', 'bias', 'pearson_r2', 'r2_score', 'nse', 'kge')
SMALL_N = 30
PERIODS = ('2023–2024', '2023', '2024')


def join_labels(frames, labels):
    """Strict one-to-one joins retain unknown; no inner-join attrition."""
    from .predictions import check_same_dates
    if set(frames) != set(MODEL_LABELS):
        raise ValueError('Exactly seven models required')
    frames = {k: v.sort_values('date').reset_index(drop=True) for k, v in frames.items()}
    check_same_dates(frames)
    labels = labels.copy()
    required = ['date', 'crop', 'crop_status', 'proxy_stage', 'actual_stage', 'status', 'policy_version']
    if not set(required) <= set(labels):
        raise ValueError('Missing label columns')
    labels['date'] = pd.to_datetime(labels.date, format='%Y-%m-%d', errors='raise')
    if labels[required].isna().any().any() or labels.date.duplicated().any():
        raise ValueError('Missing labels or duplicate dates')
    if not labels.proxy_stage.isin(STAGES).all():
        raise ValueError('Unsupported proxy stage')
    validate_stage_labels(labels)
    reference = next(iter(frames.values()))
    if set(labels.date) != set(reference.date):
        raise ValueError('Label dates must equal canonical prediction dates')
    if not labels.date.dt.year.isin([2023, 2024]).all():
        raise ValueError('Unexpected year')
    for frame in frames.values():
        if frame.date.duplicated().any() or not np.isfinite(frame[['y_obs', 'y_pred']]).all().all():
            raise ValueError('Duplicate dates or non-finite predictions')
    return pd.concat([frame.merge(labels, on='date', validate='one_to_one').assign(model=model)
                      for model, frame in frames.items()], ignore_index=True)


def grouped_metrics(joined):
    rows, coverage = [], []
    for period in PERIODS:
        data = joined if period == PERIODS[0] else joined[joined.date.dt.year == int(period)]
        dates = data.drop_duplicates('date')
        total = len(dates)
        for stage in STAGES:
            cohort = dates[dates.proxy_stage == stage]
            context = '; '.join(f'{year}/{crop}/{status}: {len(g)}'
                                for (year, crop, status), g in cohort.assign(year=cohort.date.dt.year).groupby(['year', 'crop', 'crop_status']))
            common = dict(period=period, stage=stage, n=len(cohort), share=len(cohort)/total if total else np.nan,
                          crop_context=context or 'no observations',
                          crop_labels='; '.join(sorted({f'{r.crop} ({r.crop_status})' for r in cohort.itertuples()})), small_group=len(cohort) < SMALL_N,
                          date_hash=hashlib.sha256('\n'.join(cohort.date.sort_values().dt.strftime('%Y-%m-%d')).encode()).hexdigest())
            coverage.append({**common, 'actual_unknown_n': int(cohort.actual_stage.eq('unknown').sum())})
            for model in MODEL_LABELS:
                sub = data[(data.proxy_stage == stage) & (data.model == model)]
                if set(sub.date) != set(cohort.date) or len(sub) != len(cohort):
                    raise ValueError('Unequal group dates')
                scores = evaluate(sub.y_obs, sub.y_pred)
                scores['pearson_r2'] = scores.pop('r2')
                scores['r2_score'] = scores['nse']
                reasons = []
                if len(sub) == 0:
                    reasons.append('empty_group')
                elif len(sub) < 2:
                    reasons.append('fewer_than_two_observations')
                if len(sub):
                    if sub.y_obs.nunique() == 1: reasons.append('constant_observations')
                    if sub.y_pred.nunique() == 1: reasons.append('constant_predictions')
                    if sub.y_obs.mean() == 0: reasons.append('zero_observed_mean')
                rows.append({**common, 'model': model, **scores,
                             'undefined_metrics': ','.join(k for k in SCORES if not np.isfinite(scores[k])),
                             'undefined_reasons': ','.join(reasons)})
    return pd.DataFrame(rows), pd.DataFrame(coverage)


def paired_deltas(metrics):
    indexed = metrics.set_index(['period', 'stage', 'model'])
    if not indexed.index.is_unique: raise ValueError('Duplicate groups')
    rows = []
    for period in PERIODS:
        for stage in STAGES:
            for suffix, ml in [('rf', 'random_forest'), ('xgb', 'xgboost')]:
                model = 'hybrid_ndvi_' + suffix
                for baseline in ['hybrid_' + suffix, ml]:
                    h, b = indexed.loc[(period, stage, model)], indexed.loc[(period, stage, baseline)]
                    if h.n != b.n or h.date_hash != b.date_hash: raise ValueError('Unequal comparison cohorts')
                    rows.append(dict(period=period, stage=stage, model=model, baseline=baseline,
                                     n=int(h.n), small_group=bool(h.small_group),
                                     delta_mae=h.mae-b.mae, delta_rmse=h.rmse-b.rmse))
    return pd.DataFrame(rows)


def table(frame):
    def fmt(x):
        if isinstance(x, (float, np.floating)): return f'{x:.4f}' if np.isfinite(x) else 'N/A'
        return str(x).replace('|', '/').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(frame.columns) + ' |', '| ' + ' | '.join(['---']*len(frame.columns)) + ' |'] +
                     ['| ' + ' | '.join(fmt(x) for x in row) + ' |' for row in frame.itertuples(index=False, name=None)])


def crop_summary(frame, period):
    """Crop and evidence status from input labels, never assumed by year."""
    values = frame.loc[frame.period == period, 'crop_labels'].dropna()
    return '; '.join(sorted({part for value in values for part in value.split('; ') if part})) or 'no observations'


def chart(metrics, deltas):
    """Comparable scales across years; exact values and sample sizes in SVG."""
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="1700" viewBox="0 0 1500 1700">',
             '<title>NDVI proxy errors and paired differences</title><rect width="100%" height="100%" fill="white"/>']
    def text(x, y, s, size=13):
        parts.append(f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" fill="#15324b">{escape(str(s))}</text>')
    maximum = max(float(metrics.mae.max()), 1e-12)
    delta_max = max(float(deltas[['delta_mae', 'delta_rmse']].abs().max().max()), 1e-12)
    text(25, 30, 'NDVI vegetation proxies · errors in mm/day · * n < 30 · N/A = undefined', 20)
    for panel, period in enumerate(PERIODS):
        y = 70 + panel*535
        crop_label = ' · ' + crop_summary(metrics, period)
        text(25, y, period + crop_label + ' — MAE (shared colour scale)', 19)
        for col, stage in enumerate(STAGES): text(340+col*225, y+28, stage.replace('proxy_', ''), 14)
        for r, model in enumerate(MODEL_LABELS):
            yy = y+45+r*36
            text(25, yy+22, MODEL_LABELS[model])
            for col, stage in enumerate(STAGES):
                row = metrics[(metrics.period == period)&(metrics.stage == stage)&(metrics.model == model)].iloc[0]
                v = row.mae
                light = 96-45*v/maximum if np.isfinite(v) else 90
                parts.append(f'<rect x="{330+col*225}" y="{yy}" width="215" height="32" fill="hsl(205,65%,{light}%)"/>')
                text(340+col*225, yy+22, f'{v:.3f}  n={row.n}{"*" if row.small_group else ""}' if np.isfinite(v) else 'N/A n=0')
        text(25, y+320, 'NDVI minus reference: ΔMAE / ΔRMSE. Blue = lower MAE; orange = higher MAE.', 16)
        subset = deltas[deltas.period == period]
        for r, ((model, base), group) in enumerate(subset.groupby(['model', 'baseline'], sort=False)):
            yy = y+335+r*37
            text(25, yy+23, model.replace('hybrid_ndvi_', 'NDVI ')+' vs '+base)
            for col, stage in enumerate(STAGES):
                row = group[group.stage == stage].iloc[0]
                v = row.delta_mae
                fill = f'hsl({205 if v < 0 else 25},65%,{96-40*abs(v)/delta_max}%)' if np.isfinite(v) else '#eee'
                parts.append(f'<rect x="{330+col*225}" y="{yy}" width="215" height="33" fill="{fill}"/>')
                text(340+col*225, yy+23, f'{v:+.3f} / {row.delta_rmse:+.3f}' if np.isfinite(v) else 'N/A')
    return '\n'.join(parts+['</svg>'])


def report(metrics, deltas, coverage, context):
    lines = ['# Качество прогнозов по приближённым NDVI-фазам — US-Ne2', '',
             'Семь сохранённых моделей; тест 2023–2024. Модели и границы фаз не изменяются. '
             'Это описательный анализ по proxy_stage, а не подтверждение агрономических стадий. '
             'Низкая растительность не равнозначна подтверждённому вне вегетационному периоду. '
             'Фактические стадии учитываются отдельно в покрытии; результаты по ним здесь не подменяются NDVI.', '',
             'Все модели используют одинаковые даты и y_obs внутри каждой группы. '
             'unknown сохраняется как отдельная группа. Доли рассчитаны от тестовых дат соответствующего периода; '
             '731 календарный день содержит 561 тестовое наблюдение, 170 дней без ET не заполняются.', '',
             'MAE — основная метрика; MAE, RMSE, bias и их разности выражены в мм/день. '
             'Положительный bias означает завышение. Pearson r² — квадрат корреляции; R² совпадает с NSE. '
             'n < 30 отмечено small_group=True (описательное предупреждение, не тест значимости). '
             'N/A означает неопределённую метрику: причины сохранены в таблицах. '
             'Пустые группы сохранены с n=0. FAO-56 оценивает эталонную ET₀, сравниваемую здесь с фактической ET.', '',
             '## Покрытие разметки', '', table(coverage.drop(columns='date_hash')), '',
             '## Ошибки и разности', '', '![Ошибки по фазам](phenology_errors.svg)', '']
    for period in PERIODS:
        lines += [f'## {period}', '', table(metrics[metrics.period == period].drop(columns=['period', 'date_hash', 'share', 'crop_context'])), '',
                  'NDVI minus baseline: отрицательная разность означает меньшую ошибку.', '',
                  table(deltas[deltas.period == period].drop(columns='period')), '']
        for (model, baseline), group in deltas[deltas.period == period].groupby(['model', 'baseline'], sort=False):
            better = ', '.join(group.loc[group.delta_mae < 0, 'stage']) or 'нет'
            worse = ', '.join(group.loc[group.delta_mae > 0, 'stage']) or 'нет'
            lines.append(f'- {MODEL_LABELS[model]} против {MODEL_LABELS[baseline]}: MAE ниже в {better}; выше в {worse}.')
        lines.append('')
    lines += ['## Основные наблюдения', '']
    pooled = deltas[deltas.period == PERIODS[0]]
    for model in ['hybrid_ndvi_rf', 'hybrid_ndvi_xgb']:
        base = model.replace('hybrid_ndvi_', 'hybrid_')
        finite = pooled[(pooled.model == model) & (pooled.baseline == base)].dropna(subset=['delta_mae'])
        if len(finite):
            best = finite.loc[finite.delta_mae.idxmin()]
            lines.append(f'- {MODEL_LABELS[model]}: минимальная ΔMAE против v0 в {best.stage}: '
                         f'{best.delta_mae:+.4f} мм/день, n={best.n}. Отрицательный знак означает улучшение.')
    for stage in STAGES:
        counts = coverage[coverage.stage == stage]
        details = '; '.join(f'{r.period}: n={r.n}' for r in counts.itertuples())
        lines.append(f'- Состав {stage}: {details}.')
    decline = pooled[(pooled.stage == 'proxy_decline') & pooled.baseline.isin(['random_forest', 'xgboost'])]
    for row in decline.itertuples():
        lines.append(f'- Снижение NDVI: {MODEL_LABELS[row.model]} против {MODEL_LABELS[row.baseline]}: '
                     f'ΔMAE={row.delta_mae:+.4f}, ΔRMSE={row.delta_rmse:+.4f} мм/день.')
    high = deltas[(deltas.stage == 'proxy_high_vegetation') & (deltas.model == 'hybrid_ndvi_rf') &
                  (deltas.baseline == 'hybrid_rf') & (deltas.period != PERIODS[0])]
    for row in high.itertuples():
        lines.append(f'- Высокая растительность, {row.period}: NDVI RF против v0 RF, ΔMAE={row.delta_mae:+.4f} мм/день.')
    lines += ['', 'Знак и величина разностей зависят от группы, года и выбранной метрики. '
              'Объединение годов может скрывать противоположные направления изменений. '
              'Неравное число дат даёт годам разный вес в объединённой оценке. '
              'Различия требуют учёта культуры, погодного контекста и состава выборки; '
              'они не доказывают влияние стадии само по себе.', '']
    lines += ['## Контекст и интерпретация', '', table(context), '',
              'Культуры по входной разметке: ' + '; '.join(f'{p}: {crop_summary(metrics, p)}' for p in PERIODS[1:]) + '. '
              'Статус inferred_rotation означает предположение по севообороту. Год и культура смешаны: их эффекты нельзя разделить на двух годах одной станции. '
              'Сводные метрики взвешены числом дат, а не одинаковым весом годов; состав групп показан в crop_context. '
              'Различия ошибок могут отражать уровень и изменчивость ET, погоду, культуру, возраст снимков и состав доступных дат. '
              'Таблица контекста описывает только сохранённые тестовые даты; она не доказывает причинность.', '',
              'Разметка и Hybrid + NDVI используют связанный спутниковый сигнал: сравнение по таким группам '
              'не является независимой проверкой фенологии. Серийная зависимость ежедневных наблюдений '
              'ограничивает эффективный объём выборки. Статистическая значимость и переносимость не установлены. '
              'Группы unknown также неоднородны; причины неопределённости доступны в phenology_dates.csv. '
              'Пороговые правила зафиксированы ранее; результаты этого теста не используются для изменения моделей или границ фаз.', '',
              '## Воспроизведение', '', '```bash', 'PYTHONPATH=src python -m ml.evaluation.phenology', '```', '',
              'Входы: сохранённые прогнозы, test.csv и phenology/test_labels.csv. '
              'Хеши входов, кода и версии библиотек: phenology_manifest.json. '
              'Проверки: `PYTHONPATH=src python -m pytest tests/test_phenology_evaluation.py -q`.', '']
    return '\n'.join(lines)


def run(predictions_dir=DEFAULT_PREDICTIONS_DIR, test_path=DEFAULT_TEST_PATH, labels_path=LABELS, output_dir=DEFAULT_PREDICTIONS_DIR):
    frames = load_canonical_predictions(predictions_dir, test_path, required=tuple(MODEL_LABELS))
    joined = join_labels({m: frames[m] for m in MODEL_LABELS}, pd.read_csv(labels_path))
    metrics, coverage = grouped_metrics(joined)
    deltas = paired_deltas(metrics)
    dates = joined.drop_duplicates('date').drop(columns=['model', 'y_pred']).sort_values('date')
    weather = pd.read_csv(test_path, parse_dates=['date'])
    context_data = dates.merge(weather, on='date', validate='one_to_one')
    contexts = []
    for period in PERIODS:
        sub = context_data if period == PERIODS[0] else context_data[context_data.date.dt.year == int(period)]
        for stage in STAGES:
            group = sub[sub.proxy_stage == stage]
            contexts.append(dict(period=period, stage=stage, n=len(group), et_mean=group.y_obs.mean(),
                                 et_std=group.y_obs.std(ddof=0), tmax_mean=group.tmax_c.mean(),
                                 tmin_mean=group.tmin_c.mean(), radiation_mean=group.rn_mj_m2_day.mean(),
                                 precip_mean=group.precip_mm.mean(), ndvi_age_mean=group.ndvi_age_days.mean()))
    context = pd.DataFrame(contexts)
    inputs = [Path(test_path), Path(labels_path)] + [Path(predictions_dir)/f'predictions_{m}.csv' for m in MODEL_LABELS]
    inputs += [Path(__file__), Path(__file__).with_name('metrics.py'), Path(__file__).with_name('predictions.py')]
    manifest = {'policy': 'frozen proxies; no training or tuning; small_n=30',
                'label_policy_versions': sorted(dates.policy_version.unique().tolist()),
                'numpy': np.__version__, 'pandas': pd.__version__,
                'sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in [('metrics', metrics), ('deltas', deltas), ('coverage', coverage), ('dates', dates), ('joined', joined), ('context', context)]:
        frame.to_csv(output/f'phenology_{name}.csv', index=False, na_rep='NaN', date_format='%Y-%m-%d')
    (output/'phenology_comparison.md').write_text(report(metrics, deltas, coverage, context), encoding='utf-8')
    (output/'phenology_errors.svg').write_text(chart(metrics, deltas), encoding='utf-8')
    (output/'phenology_manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    return metrics, deltas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in [('predictions-dir', DEFAULT_PREDICTIONS_DIR), ('test-path', DEFAULT_TEST_PATH), ('labels-path', LABELS), ('output-dir', DEFAULT_PREDICTIONS_DIR)]:
        parser.add_argument('--'+name, type=Path, default=default)
    metrics, _ = run(**vars(parser.parse_args()))
    print(f'Wrote {len(metrics)} model/group rows, tables, SVG and report.')


if __name__ == '__main__':
    main()
