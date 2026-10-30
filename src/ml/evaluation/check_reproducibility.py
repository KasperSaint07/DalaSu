"""Compare unrounded metrics from two prediction exports; fail outside tolerance."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .metrics import evaluate
from .predictions import read_prediction_file

METRICS = ('mae', 'rmse', 'bias', 'r2', 'nse', 'kge')


def check(first, second, models, atol=1e-6):
    if not np.isfinite(atol) or atol < 0:
        raise ValueError('Tolerance must be finite and nonnegative')
    rows = []
    for model in models:
        a, b = [read_prediction_file(Path(root) / f'predictions_{model}.csv')
                for root in (first, second)]
        pd.testing.assert_frame_equal(a[['date', 'y_obs']], b[['date', 'y_obs']], check_exact=True)
        if not np.isfinite(a.y_pred).all() or not np.isfinite(b.y_pred).all():
            raise ValueError('Predictions must be finite')
        scores = [evaluate(frame.y_obs, frame.y_pred) for frame in (a, b)]
        for metric in METRICS:
            delta = abs(scores[0][metric] - scores[1][metric])
            rows.append(dict(model=model, metric=metric, first=scores[0][metric],
                             second=scores[1][metric], absolute_difference=delta,
                             tolerance=atol, passed=bool(np.isfinite(delta) and delta <= atol)))
    return {'passed': all(row['passed'] for row in rows), 'checks': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('first', type=Path)
    parser.add_argument('second', type=Path)
    parser.add_argument('--models', nargs='+', default=['hybrid_ndvi_rf', 'hybrid_ndvi_xgb'])
    parser.add_argument('--atol', type=float, default=1e-6)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = check(args.first, args.second, args.models, args.atol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print('PASS' if result['passed'] else 'FAIL')
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
