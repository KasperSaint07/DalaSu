"""Reproduce phase-4 synthesis from saved forecasts; no training or tuning."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

from ..data.validation import validate_output_paths
from .compare_models import MODEL_LABELS
from .actual_stages import ACTUAL_STAGES, DEFAULT_METADATA, stage_readiness, validate_stage_evidence
from .metrics import evaluate
from .phenology import LABELS, PERIODS, ROOT, SCORES, SMALL_N, STAGES, join_labels, table
from .predictions import DEFAULT_PREDICTIONS_DIR, DEFAULT_TEST_PATH, load_canonical_predictions
from .seasonal import SEASON_ORDER, assign_seasons

MODELS = ('hybrid_rf', 'hybrid_xgb', 'hybrid_ndvi_rf', 'hybrid_ndvi_xgb')
PAIRS = (
    ('algorithm_v0', 'hybrid_xgb', 'hybrid_rf'),
    ('algorithm_ndvi', 'hybrid_ndvi_xgb', 'hybrid_ndvi_rf'),
    ('ndvi_rf', 'hybrid_ndvi_rf', 'hybrid_rf'),
    ('ndvi_xgb', 'hybrid_ndvi_xgb', 'hybrid_xgb'),
)
GROUPS = ([('overall', 'all')] + [('season', s) for s in SEASON_ORDER]
          + [('proxy_stage', s) for s in STAGES] + [('actual_stage', s) for s in ACTUAL_STAGES])
COMPONENTS = ('kge_r', 'kge_alpha', 'kge_beta')


def phase4_readiness(dates):
    """The accepted scope uses frozen NDVI proxies, not observed crop stages."""
    result = stage_readiness(dates)
    proxy_periods = {}
    for period in PERIODS:
        subset = dates if period == PERIODS[0] else dates[dates.date.dt.year == int(period)]
        counts = {stage: int(subset.proxy_stage.eq(stage).sum()) for stage in STAGES}
        proxy_periods[period] = dict(n=len(subset), stage_counts=counts,
                                    classified_n=len(subset)-counts['unknown'],
                                    unknown_n=counts['unknown'],
                                    small_groups=[s for s in STAGES if 0 < counts[s] < SMALL_N])
    available = all(proxy_periods[PERIODS[0]]['stage_counts'][s] > 0 for s in STAGES if s != 'unknown')
    result.update(scope='seasonal_and_frozen_ndvi_proxy_analysis', scope_agreed_on='2026-11-03',
                  objective_4='implemented_with_ndvi_proxies' if available else 'insufficient_proxy_groups',
                  phase4_status='complete_for_agreed_proxy_scope' if available else 'incomplete_proxy_coverage',
                  proxy_periods=proxy_periods,
                  limitation='NDVI phases are approximate vegetation states, not observed agronomic stages. Unknown dates remain a separate group; no statistical significance is claimed.',
                  next_action='Use seasonal, NDVI-proxy and RF/XGBoost comparisons in the report; field records are optional for a future actual-stage extension.')
    return result


def validate_features(models_dir):
    """Inspect saved contracts, without loading or executing estimators."""
    metadata, paths = {}, []
    for model in MODELS:
        directory = Path(models_dir)/'hybrid_ndvi' if '_ndvi_' in model else Path(models_dir)
        filename = model.replace('hybrid_ndvi_', 'hybrid_') + '_metadata.json'
        path = directory/filename
        item = json.loads(path.read_text())
        if (item['target'] != 'et_obs_mm - et0_mm' or
                item['prediction'] != 'et0_mm + residual_pred_mm' or item['use_et0_feature']):
            raise ValueError('Unexpected residual reconstruction or ET0 feature contract')
        if len(item['features']) != len(set(item['features'])):
            raise ValueError('Duplicate features')
        metadata[model] = item
        paths.append(path)
    for left, right in [('hybrid_rf', 'hybrid_xgb'), ('hybrid_ndvi_rf', 'hybrid_ndvi_xgb')]:
        for key in ['features', 'wind_height_m', 'target', 'prediction', 'use_et0_feature']:
            if metadata[left][key] != metadata[right][key]:
                raise ValueError(f'Unequal feature/reconstruction contracts: {left}, {right}, {key}')
    base, ndvi = metadata['hybrid_rf'], metadata['hybrid_ndvi_rf']
    if ndvi['features'] != base['features'] + ['ndvi_last', 'ndvi_age_days']:
        raise ValueError('NDVI must add exactly ndvi_last and ndvi_age_days')
    if base['wind_height_m'] != ndvi['wind_height_m']:
        raise ValueError('Different physical baseline wind height')
    return metadata, paths


def score(obs, pred):
    obs, pred = np.asarray(obs, float), np.asarray(pred, float)
    scores = evaluate(obs, pred)
    scores['pearson_r2'] = scores.pop('r2')
    scores['r2_score'] = scores['nse']
    scores['abs_bias'] = abs(scores['bias'])
    scores.update({key: np.nan for key in COMPONENTS})
    reasons = []
    if len(obs) == 0:
        reasons.append('empty_group')
    else:
        if len(obs) < 2: reasons.append('fewer_than_two_pairs')
        if np.std(obs) == 0: reasons.append('constant_observations')
        if np.std(pred) == 0: reasons.append('constant_predictions')
        if np.mean(obs) == 0: reasons.append('zero_observed_mean')
        if np.std(obs) > 0:
            scores['kge_alpha'] = np.std(pred)/np.std(obs)
            if np.std(pred) > 0:
                scores['kge_r'] = float(np.corrcoef(obs, pred)[0, 1])
        if np.mean(obs) != 0:
            scores['kge_beta'] = np.mean(pred)/np.mean(obs)
    scores['undefined_metrics'] = ','.join(k for k in (*SCORES, *COMPONENTS) if not np.isfinite(scores[k]))
    scores['undefined_reasons'] = ','.join(reasons)
    return scores


def aggregate(joined):
    """All groups come from one common labelled date cohort, including unknown."""
    joined = joined.copy()
    joined['season'] = assign_seasons(joined.date)
    rows, coverage = [], []
    for period in PERIODS:
        data = joined if period == PERIODS[0] else joined[joined.date.dt.year == int(period)]
        dates = data.drop_duplicates('date')
        for dimension, group in GROUPS:
            cohort = dates if dimension == 'overall' else dates[dates[dimension] == group]
            digest = hashlib.sha256('\n'.join(cohort.date.sort_values().dt.strftime('%Y-%m-%d')).encode()).hexdigest()
            crops = '; '.join(f'{year}/{crop}/{status}: {len(g)}' for (year, crop, status), g in
                              cohort.assign(year=cohort.date.dt.year).groupby(['year', 'crop', 'crop_status']))
            common = dict(period=period, dimension=dimension, group=group, n=len(cohort),
                          date_hash=digest, small_group=len(cohort) < SMALL_N,
                          crop_context=crops or 'no observations')
            coverage.append({**common, 'share': len(cohort)/len(dates) if len(dates) else np.nan,
                             'proxy_unknown_n': int(cohort.proxy_stage.eq('unknown').sum()),
                             'actual_unknown_n': int(cohort.actual_stage.eq('unknown').sum()),
                             'actual_observed_n': int((cohort.status.eq('observed') & cohort.actual_stage.ne('unknown')).sum())})
            for model in (MODEL_LABELS if dimension == 'actual_stage' else MODELS):
                sub = data[(data.model == model) & data.date.isin(cohort.date)]
                if len(sub) != len(cohort) or set(sub.date) != set(cohort.date):
                    raise ValueError('Unequal dates in group')
                rows.append({**common, 'model': model, **score(sub.y_obs, sub.y_pred)})
    return pd.DataFrame(rows), pd.DataFrame(coverage)


def differences(metrics):
    indexed = metrics.set_index(['period', 'dimension', 'group', 'model'])
    if not indexed.index.is_unique: raise ValueError('Duplicate model/group')
    rows = []
    for period in PERIODS:
        for dimension, group in GROUPS:
            for comparison, model, reference in PAIRS:
                left, right = indexed.loc[(period, dimension, group, model)], indexed.loc[(period, dimension, group, reference)]
                if left.n != right.n or left.date_hash != right.date_hash:
                    raise ValueError('Unequal paired dates')
                row = dict(period=period, dimension=dimension, group=group, comparison=comparison,
                           model=model, reference=reference, n=int(left.n), date_hash=left.date_hash,
                           small_group=bool(left.small_group))
                row.update({'delta_'+key: left[key]-right[key] for key in (*SCORES, 'abs_bias', *COMPONENTS)})
                row['mae_preferred'] = ('undefined' if not np.isfinite(row['delta_mae']) else
                                        model if row['delta_mae'] < 0 else reference if row['delta_mae'] > 0 else 'tie')
                row['undefined_deltas'] = ','.join(key for key, value in row.items() if key.startswith('delta_') and not np.isfinite(value))
                rows.append(row)
    return pd.DataFrame(rows)


def stability(deltas):
    rows = []
    for (period, dimension, comparison), group in deltas[deltas.dimension != 'overall'].groupby(['period', 'dimension', 'comparison'], sort=False):
        for metric in ('mae', 'rmse', 'abs_bias', 'kge'):
            values = group['delta_'+metric]
            better = values > 0 if metric == 'kge' else values < 0
            worse = values < 0 if metric == 'kge' else values > 0
            rows.append(dict(period=period, dimension=dimension, comparison=comparison, metric=metric,
                             better_groups=', '.join(group.loc[better, 'group']) or 'none',
                             worse_groups=', '.join(group.loc[worse, 'group']) or 'none',
                             tied_groups=', '.join(group.loc[values == 0, 'group']) or 'none',
                             undefined_groups=', '.join(group.loc[~np.isfinite(values), 'group']) or 'none'))
    return pd.DataFrame(rows)


def render_chart(deltas, period):
    selected = deltas[deltas.period == period]
    chart_groups = [(d, g) for d, g in GROUPS if d != 'actual_stage']
    panel_height = 50 + ((len(chart_groups) + 4) // 5)*92
    width, height = 1300, 110 + len(PAIRS)*panel_height
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
             '<title>Phase 4 paired errors</title><rect width="100%" height="100%" fill="white"/>']
    def text(x, y, value, size=13):
        parts.append(f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" fill="#17344c">{escape(str(value))}</text>')
    text(25, 30, f'US-Ne2 · {period} · paired ΔMAE / ΔRMSE (mm/day)', 22)
    text(25, 56, 'Algorithm: XGBoost − RF. NDVI: with NDVI − v0. Negative = lower error; * n < 30.')
    scale = max(float(deltas[['delta_mae', 'delta_rmse']].abs().max().max()), 1e-12)
    for panel, (comparison, _, _) in enumerate(PAIRS):
        y = 90 + panel*panel_height
        text(25, y, comparison, 18)
        for index, (dimension, group) in enumerate(chart_groups):
            col, row_index = index % 5, index // 5
            x, yy = 25 + col*255, y+20+row_index*92
            row = selected[(selected.dimension == dimension)&(selected.group == group)&(selected.comparison == comparison)].iloc[0]
            label = ('actual: ' if dimension == 'actual_stage' else '') + group.replace('proxy_', '')
            text(x, yy+15, label+f' · n={row.n}{"*" if row.small_group else ""}')
            val = row.delta_mae
            fill = f'hsl({205 if val < 0 else 25},60%,{96-45*abs(val)/scale}%)' if np.isfinite(val) else '#eee'
            parts.append(f'<rect x="{x}" y="{yy+25}" width="240" height="42" fill="{fill}"/>')
            text(x+12, yy+51, f'{val:+.4f} / {row.delta_rmse:+.4f}' if np.isfinite(val) else 'N/A', 16)
    text(25, height-15, 'Colour encodes ΔMAE only; common scale across years. NDVI proxies are not observed crop stages.')
    return '\n'.join(parts+['</svg>'])


def render_report(metrics, deltas, coverage, stable, metadata, readiness):
    overall = metrics[(metrics.period == PERIODS[0]) & (metrics.dimension == 'overall')]
    overall_deltas = deltas[(deltas.period == PERIODS[0]) & (deltas.dimension == 'overall')]
    total = coverage[(coverage.period == PERIODS[0]) & (coverage.dimension == 'overall')].iloc[0]
    best = overall.loc[overall.mae.idxmin()]
    # Field-stage diagnostics remain in CSV, outside the agreed proxy report.
    stable = stable[stable.dimension != 'actual_stage']
    deltas = deltas[deltas.dimension != 'actual_stage']
    lines = ['# Итоговый отчёт фазы 4 — коррекция остатка FAO-56', '',
             f'US-Ne2, тест 2023–2024, n={total.n}. Минимальная общая MAE: {MODEL_LABELS[best.model]}, '
             f'{best.mae:.6f} мм/день. Это описательный результат на сохранённой тестовой выборке, не доказательство статистического превосходства.', '',
             f'**Статус фазы 4: {readiness["phase4_status"]}.** '
             'По решению пользователя от 03.11.2026 используются сезонный анализ и уже зафиксированные NDVI-фазы. '
             'Это уточнение исходного growth-stage analysis: NDVI-фазы — приближённые состояния растительности, '
             'а не подтверждённые агрономические стадии. Полевые записи не являются условием завершения согласованного объёма. '
             f'NDVI-фаза определена для {total.n-total.proxy_unknown_n}/{total.n} дней; остальные сохранены как unknown. '
             'Статус и покрытие по годам: `phase4_readiness.json`.', '',
             '## Протокол', '',
             'Оценивается итоговая ET = FAO-56 ET₀ + прогноз остатка, а не остаток сам по себе. '
             'RF и XGBoost сравниваются внутри одинаковых наборов признаков; соответствие проверяется по метаданным. '
             'Четыре гибрида используют одинаковые даты и наблюдения. Семь исходных файлов проверяются общим загрузчиком. '
             'Никакое пересечение с молчаливой потерей дат не допускается.', '',
             'Метрики пересчитаны из сохранённых прогнозов полной точности; округлённые итоговые CSV не используются как вход. '
             'Основная метрика — MAE. RMSE сильнее реагирует на крупные ошибки. Bias = mean(pred − obs); '
             'его улучшение оценивается по |bias|, а не по уменьшению знакового значения. '
             'Pearson r² — квадрат корреляции, R² = NSE. KGE учитывает корреляцию r, отношение стандартных отклонений α '
             'и отношение средних β: KGE = 1 − sqrt((r−1)²+(α−1)²+(β−1)²). Идеал каждого компонента — 1.', '',
             'Разности: XGBoost − RF внутри версии; NDVI − v0 внутри алгоритма. Для MAE/RMSE/|bias| меньше лучше, '
             'для KGE/NSE/R² больше лучше. Знак Δbias сам по себе не задаёт победителя. '
             'Общий результат рассчитывается по всем датам, не усреднением групповых метрик. '
             'n < 30 — предупреждение о малой группе, не порог значимости. N/A означает неопределённую метрику; '
             'CSV содержит причины (пустая группа, недостаточно пар, постоянные значения или нулевое среднее наблюдений).', '',
             'Признаки v0: ' + ', '.join(metadata['hybrid_rf']['features']) + '. NDVI добавляет ndvi_last и ndvi_age_days. '
             'Сравнение NDVI отражает версии с отдельным обучением и подбором параметров на train/CV, '
             'а не изолированный причинный эффект двух признаков при фиксированных параметрах.', '',
             '## Итоговая таблица', '', table(overall[['model', 'n', *SCORES, 'abs_bias']]), '',
             '## Общие разности и компромиссы', '',
             table(overall_deltas[['comparison', 'n', *['delta_'+s for s in SCORES], 'delta_abs_bias']]), '',
             table(overall[['model', *COMPONENTS, 'kge']]), '']
    for row in overall_deltas.itertuples():
        lines.append(f'- {row.comparison}: ΔMAE={row.delta_mae:+.6f}, ΔRMSE={row.delta_rmse:+.6f}, '
                     f'Δbias={row.delta_bias:+.6f}, Δ|bias|={row.delta_abs_bias:+.6f}, ΔKGE={row.delta_kge:+.6f}. '
                     f'Меньшая MAE: {row.mae_preferred}.')
    lines += ['', '### Что меняется между алгоритмами и при добавлении NDVI', '']
    indexed_overall = overall.set_index('model')
    for comparison, model, reference in PAIRS:
        left, right = indexed_overall.loc[model], indexed_overall.loc[reference]
        percentage = 100*(left.mae/right.mae-1) if right.mae != 0 else np.nan
        lines.append(f'- {MODEL_LABELS[model]} относительно {MODEL_LABELS[reference]}: '
                     f'изменение MAE {percentage:+.2f}%. '
                     f'Корреляция r {right.kge_r:.4f} → {left.kge_r:.4f}; '
                     f'отклонение α от 1: {abs(right.kge_alpha-1):.4f} → {abs(left.kge_alpha-1):.4f}; '
                     f'отклонение β от 1: {abs(right.kge_beta-1):.4f} → {abs(left.kge_beta-1):.4f}.')
    finite_kge = overall[np.isfinite(overall.kge)]
    if finite_kge.empty:
        lines += ['', 'KGE неопределён для всех моделей (N/A); выбрать лучший вариант по KGE невозможно.', '']
    else:
        lines += ['', 'Наибольший KGE среди вариантов с определённой метрикой имеет ' +
                  MODEL_LABELS[finite_kge.loc[finite_kge.kge.idxmax(), 'model']] + '. '
                  'Таким образом, выбор по KGE может отличаться от выбора по MAE/RMSE.', '']
    for row in stable[(stable.period == PERIODS[0]) & (stable.metric == 'mae')].itertuples():
        lines.append(f'- {row.comparison}, {row.dimension}, объединённые годы: меньшая MAE левой модели в '
                     f'{row.better_groups}; большая в {row.worse_groups}; равная в {row.tied_groups}.')
    lines += ['', 'Снижение абсолютных ошибок не гарантирует улучшения KGE: компоненты среднего и разброса могут '
              'удаляться от 1 даже при росте корреляции. Для каждого сравнения компоненты и их разности сохранены в CSV. '
              'Выбор лучшего алгоритма здесь относится к MAE; он не означает превосходства по всем критериям.', '',
              '## Устойчивость по сезонам и NDVI-фазам', '',
              'В таблицах better/worse означает преимущество/ухудшение левой модели сравнения (XGBoost либо версия с NDVI). '
              'Число выигранных групп не заменяет общую метрику: группы различаются по числу дат и уровню ET. '
              'DJF объединяет январь, февраль и декабрь календарного года; полные зимние сезоны не реконструируются.', '']
    for period in PERIODS:
        lines += [f'### {period}', '', f'![Разности {period}](phase4_deltas_{period}.svg)', '',
                  table(stable[(stable.period == period)].drop(columns='period')), '',
                  'Разности основных показателей (все метрики доступны в CSV):', '',
                  table(deltas[deltas.period == period][['dimension', 'group', 'comparison', 'n', 'small_group',
                        'delta_mae', 'delta_rmse', 'delta_bias', 'delta_abs_bias', 'delta_kge']]), '']
    lines += ['## Покрытие, культура и неизвестные стадии', '',
              table(coverage[coverage.dimension != 'actual_stage'].drop(columns='date_hash')), '',
              f'Unknown NDVI: {total.proxy_unknown_n}/{total.n} ({100*total.proxy_unknown_n/total.n:.2f}%). '
              f'Неизвестные фактические стадии: {total.actual_unknown_n}/{total.n}; подтверждённые: {total.actual_observed_n}. '
              'Unknown включён в метрики отдельной группой. Культуры и статусы в таблице получены из разметки; '
              'inferred_rotation означает предположение по севообороту, а не полевое подтверждение.', '',
              '## Objective 4 — Seasonal and NDVI-derived vegetation-phase analysis', '',
              'В согласованном объёме выполнены сезонный анализ и сравнение по фиксированным NDVI-фазам: '
              'низкая растительность, рост NDVI, высокая растительность, снижение NDVI и отдельная группа unknown. '
              'Правила разметки не подбирались по ошибкам holdout и в этой работе не менялись. '
              'Низкий NDVI не доказывает отсутствие культуры; высокий NDVI не устанавливает цветение. '
              'Фактические стадии остаются неподтверждёнными и не входят в критерий завершения выбранного варианта. '
              'Покрытие и малые группы по годам перечислены в phase4_readiness.json.', '',
              '## Objective 5 — Random Forest vs XGBoost as residual-correction component', '',
              f'По общей MAE среди четырёх гибридов лучший результат у {MODEL_LABELS[best.model]}. '
              'Попарные преимущества и исключения перечислены для каждой версии, сезона, NDVI-фазы и года. '
              'Вклад NDVI оценён отдельно для RF и XGBoost; вывод о пользе ограничен конкретными метриками, '
              'а не всеми показателями одновременно. Этот анализ не используется для повторной настройки по holdout.', '',
              '## Ограничения', '',
              'Одна станция US-Ne2 и тестовые годы 2023–2024. Статистическая значимость не проверялась; '
              'доверительные интервалы и причинные эффекты не заявляются. Даты серийно зависимы. '
              'Культура и год смешаны, а доступность ET/снимков и размеры групп неодинаковы: '
              'межгодовое изменение ошибки нельзя приписать одной фазе. '
              'Разметка и NDVI-гибриды используют связанный спутниковый сигнал, поэтому это не независимая проверка фенологии. '
              'FAO-56 даёт эталонную ET₀, а коррекция обучена относительно наблюдаемой фактической ET. '
              'Переносимость на Казахстан, другие станции и годы, водосбережение и качество решений о поливе не проверялись.', '',
              '## Результаты и воспроизведение', '',
              '- [Все метрики и KGE-компоненты](phase4_metrics.csv)',
              '- [Все попарные разности](phase4_deltas.csv)',
              '- [Устойчивость преимуществ](phase4_stability.csv)',
              '- [Дополнительная диагностика фактических стадий (вне согласованного объёма)](phase4_actual_stage_metrics.csv)',
              '- [Статус полноты и покрытие стадий](phase4_readiness.json)',
              '- [Аудит дат](phase4_dates.csv) и [покрытие](phase4_coverage.csv)',
              '- [Входы, метаданные и хеши кода](phase4_manifest.json)',
              '- [Общее сравнение фазы 3](fao56_ml_comparison.md)',
              '- [Сезонный анализ](seasonal_comparison.md)',
              '- [Анализ по NDVI-фазам](phenology_comparison.md)',
              '- [Проверка NDVI-гибридов](hybrid_ndvi_validation.md)', '',
              'Из корня репозитория в установленном окружении:', '', '```bash',
              'PYTHONPATH=src python -m ml.evaluation.phase4',
              'PYTHONPATH=src python -m pytest tests/test_phase4.py tests/test_phenology_evaluation.py -q', '```', '',
              'Дополнительное воспроизведение исходных анализов:', '', '```bash',
              'PYTHONPATH=src python -m ml.evaluation.compare_models --from-files',
              'PYTHONPATH=src python -m ml.evaluation.seasonal',
              'PYTHONPATH=src python -m ml.evaluation.phenology', '```', '',
              'Скрипт phase4 сам рассчитывает все срезы из прогнозов; предварительный запуск других отчётов не требуется. '
              'Модели, прогнозы и границы фаз не изменяются. Параметры CLI позволяют указать входные и выходную директории.', '']
    return '\n'.join(lines)


def run(predictions_dir=DEFAULT_PREDICTIONS_DIR, test_path=DEFAULT_TEST_PATH, labels_path=LABELS,
        models_dir=ROOT/'models', output_dir=DEFAULT_PREDICTIONS_DIR, metadata_dir=DEFAULT_METADATA):
    metadata, metadata_paths = validate_features(models_dir)
    frames = load_canonical_predictions(predictions_dir, test_path, required=tuple(MODEL_LABELS))
    joined = join_labels({m: frames[m] for m in MODEL_LABELS}, pd.read_csv(labels_path))
    evidence_paths = validate_stage_evidence(joined.drop_duplicates('date'), metadata_dir)
    metrics, coverage = aggregate(joined)
    deltas = differences(metrics)
    stable = stability(deltas)
    dates = joined.drop_duplicates('date').drop(columns=['model', 'y_pred']).sort_values('date')
    dates['season'] = assign_seasons(dates.date)
    readiness = phase4_readiness(dates)
    output = Path(output_dir)
    products = {f'phase4_{name}.csv': frame.to_csv(index=False, na_rep='NaN', date_format='%Y-%m-%d')
                for name, frame in [('metrics', metrics), ('deltas', deltas), ('coverage', coverage), ('stability', stable), ('dates', dates)]}
    products['phase4_actual_stage_metrics.csv'] = metrics[metrics.dimension == 'actual_stage'].to_csv(index=False, na_rep='NaN')
    products['phase4_readiness.json'] = json.dumps(readiness, indent=2, ensure_ascii=False)+'\n'
    products['phase4_summary.md'] = render_report(metrics, deltas, coverage, stable, metadata, readiness)
    for period in PERIODS: products[f'phase4_deltas_{period}.svg'] = render_chart(deltas, period)
    inputs = [Path(test_path), Path(labels_path), *metadata_paths, *evidence_paths]
    inputs += [Path(predictions_dir)/f'predictions_{m}.csv' for m in MODEL_LABELS]
    inputs += [Path(__file__).with_name(f'{name}.py') for name in ['phase4', 'metrics', 'predictions', 'phenology', 'seasonal', 'compare_models']]
    inputs += [Path(__file__).with_name('actual_stages.py'), ROOT/'src/ml/data/validation.py', ROOT/'src/ml/data/build_phenology.py']
    manifest = dict(protocol='saved predictions only; no training, tuning, or stage changes; small_n=30',
                    python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__,
                    features=metadata, label_policy_versions=sorted(dates.policy_version.unique().tolist()),
                    objectives_status={k: readiness[k] for k in ('objective_4', 'objective_5')},
                    sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
    products['phase4_manifest.json'] = json.dumps(manifest, indent=2, ensure_ascii=False)+'\n'
    validate_output_paths(inputs, [output/name for name in products])
    output.mkdir(parents=True, exist_ok=True)
    for name, content in products.items(): (output/name).write_text(content, encoding='utf-8')
    return metrics, deltas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in [('predictions-dir', DEFAULT_PREDICTIONS_DIR), ('test-path', DEFAULT_TEST_PATH),
                          ('labels-path', LABELS), ('models-dir', ROOT/'models'), ('output-dir', DEFAULT_PREDICTIONS_DIR),
                          ('metadata-dir', DEFAULT_METADATA)]:
        parser.add_argument('--'+name, type=Path, default=default)
    parser.add_argument('--require-complete-stages', action='store_true',
                        help='write diagnostics, then exit 2 if any test day lacks an observed actual stage')
    args = vars(parser.parse_args())
    require_complete = args.pop('require_complete_stages')
    metrics, deltas = run(**args)
    print(f'Phase 4: {len(metrics)} metric rows, {len(deltas)} comparisons; report and SVGs written.')
    readiness = json.loads((Path(args['output_dir'])/'phase4_readiness.json').read_text())
    print(f'Actual growth-stage evidence: {readiness["actual_stage_status"]}.')
    if require_complete and not readiness['complete_test_stage_coverage']:
        parser.exit(2, 'Incomplete field-stage evidence. Diagnostics written; see phase4_readiness.json.\n')


if __name__ == '__main__':
    main()
