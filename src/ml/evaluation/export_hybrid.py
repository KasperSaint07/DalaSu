"""Export canonical predictions from an existing Hybrid artifact without retraining."""
import argparse
from pathlib import Path
from ..hybrid import HybridPredictor
from ..hybrid_experiment import HybridExperiment
from ..train_ml import PROJECT_ROOT
from .predictions import load_test_data, write_predictions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models-dir', type=Path, default=PROJECT_ROOT / 'models')
    parser.add_argument('--reports-dir', type=Path)
    parser.add_argument('--test-path', type=Path)
    args = parser.parse_args(argv)
    for name in ('rf', 'xgb'):
        model = HybridPredictor.load(args.models_dir, name)
        experiment = HybridExperiment(bool(model.extra_features), model.use_et0_feature)
        prefix = experiment.name
        reports_dir = args.reports_dir if args.reports_dir is not None else experiment.reports_dir(PROJECT_ROOT)
        test_path = args.test_path if args.test_path is not None else experiment.data_dir(PROJECT_ROOT) / 'test.csv'
        test = load_test_data(test_path)
        reports_dir.mkdir(parents=True, exist_ok=True)
        components = model.predict_components(test)
        components.insert(0, 'date', test.date)
        components.to_csv(reports_dir / f'components_{prefix}_{name}.csv', index=False)
        write_predictions(test, {f'{prefix}_{name}': components.et_pred_mm}, reports_dir)


if __name__ == '__main__':
    main()
