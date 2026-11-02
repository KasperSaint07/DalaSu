"""Compare seven saved models by calendar season; never train or infer.

Run: PYTHONPATH=src python -m ml.evaluation.seasonal
"""
from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

from ..fao56.baseline import SEASONS, SEASON_ORDER
from .compare_models import MODEL_LABELS, METRIC_COLUMNS
from .metrics import evaluate
from .predictions import (
    DEFAULT_PREDICTIONS_DIR, DEFAULT_TEST_PATH, check_same_dates,
    load_canonical_predictions,
)

HYBRID_BASELINES = {
    "hybrid_rf": "random_forest", "hybrid_xgb": "xgboost",
    "hybrid_ndvi_rf": "random_forest", "hybrid_ndvi_xgb": "xgboost",
}
SCORE_COLUMNS = [c for c in METRIC_COLUMNS if c not in ("model", "n")]


def assign_seasons(dates: pd.Series) -> pd.Series:
    """One meteorological season per date, pooled across calendar years.

    December is DJF; no winter-year shifting or complete-winter filtering.
    Leap day is DJF. Reject missing dates rather than silently dropping them.
    """
    parsed = pd.to_datetime(dates, errors="raise")
    if parsed.isna().any():
        raise ValueError("Cannot assign a season to a missing date")
    return parsed.dt.month.map(SEASONS).rename("season")


def seasonal_metrics(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Score each common season, retaining empty/undefined groups explicitly."""
    if not frames:
        raise ValueError("No prediction frames")
    check_same_dates(frames)
    rows = []
    for model, frame in frames.items():
        if frame["date"].duplicated().any():
            raise ValueError("Duplicate dates")
        if not np.isfinite(frame[["y_obs", "y_pred"]].to_numpy(dtype=float)).all():
            raise ValueError("Non-finite observations or predictions")
        seasons = assign_seasons(frame["date"])
        for season in SEASON_ORDER:
            subset = frame.loc[seasons == season]
            scores = evaluate(subset.y_obs, subset.y_pred)
            scores["pearson_r2"] = scores.pop("r2")
            scores["r2_score"] = scores["nse"]
            undefined = ",".join(c for c in SCORE_COLUMNS if not np.isfinite(scores[c]))
            rows.append({"model": model, "season": season, **scores,
                         "undefined_metrics": undefined})
    return pd.DataFrame(rows, columns=["model", "season", *METRIC_COLUMNS[1:], "undefined_metrics"])


def seasonal_deltas(metrics: pd.DataFrame) -> pd.DataFrame:
    """Absolute differences in mm/day: hybrid minus corresponding ML-only."""
    indexed = metrics.set_index(["model", "season"])
    if not indexed.index.is_unique:
        raise ValueError("Duplicate model-season groups")
    rows = []
    for hybrid, baseline in HYBRID_BASELINES.items():
        for season in SEASON_ORDER:
            h, b = indexed.loc[(hybrid, season)], indexed.loc[(baseline, season)]
            if h.n != b.n:
                raise ValueError("Unequal seasonal sample counts")
            rows.append(dict(model=hybrid, baseline=baseline, season=season, n=int(h.n),
                             delta_mae=h.mae - b.mae, delta_rmse=h.rmse - b.rmse))
    return pd.DataFrame(rows)


def _number(value: float, signed: bool = False) -> str:
    return (f"{value:+.4f}" if signed else f"{value:.4f}") if np.isfinite(value) else "N/A"


def render_report(metrics: pd.DataFrame, deltas: pd.DataFrame) -> str:
    counts = metrics.groupby("season")["n"].first()
    lines = [
        "# Seasonal model comparison — US-Ne2, 2023–2024", "",
        f"All seven models use the same {int(counts.sum())} canonical observed dates. "
        "No predictions are regenerated and no models are retrained or tuned.", "",
        "## Protocol", "",
        "DJF = December–February; MAM = March–May; JJA = June–August; SON = September–November. "
        "Dates are pooled by calendar month across both test years, not grouped into complete winters. "
        "Every available test date belongs to exactly one season; absent daily observations are not filled.", "",
        "Metric definitions and the ET₀-versus-actual-ET limitation follow "
        "[the phase-3 report](fao56_ml_comparison.md). Pearson r² measures squared correlation; "
        "R² is the coefficient of determination and equals NSE. Positive bias means overestimation. "
        "MAE is the primary metric; all errors and deltas are in mm/day.", "",
        "N/A (NaN in CSV) denotes an undefined metric. Empty groups have n=0; constant observations "
        "make Pearson r², R²/NSE and KGE undefined. Constant predictions make Pearson r² and KGE "
        "undefined; zero observed mean also makes KGE undefined. The CSV lists undefined_metrics explicitly.", "",
        "## Seasonal errors", "", "![Seasonal MAE and RMSE](seasonal_errors.svg)", "",
    ]
    for season in SEASON_ORDER:
        lines += [f"### {season} — n={int(counts[season])}", "",
                  "| Model | n | MAE | RMSE | Pearson r² | R² | Bias | NSE | KGE |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for row in metrics.loc[metrics.season == season].itertuples():
            values = [getattr(row, c) for c in ["mae", "rmse", "pearson_r2", "r2_score", "bias", "nse", "kge"]]
            lines.append(f"| {MODEL_LABELS[row.model]} | {row.n} | " + " | ".join(map(_number, values)) + " |")
        lines.append("")
    lines += ["## Hybrid minus ML-only", "",
              "Negative differences mean improvement; positive differences mean worse performance. "
              "Comparisons use RF against RF and XGBoost against XGBoost on identical seasonal dates.", "",
              "| Hybrid | ML-only reference | Season | n | ΔMAE | ΔRMSE |",
              "|---|---|---|---:|---:|---:|"]
    for row in deltas.itertuples():
        lines.append(f"| {MODEL_LABELS[row.model]} | {MODEL_LABELS[row.baseline]} | {row.season} | "
                     f"{row.n} | {_number(row.delta_mae, True)} | {_number(row.delta_rmse, True)} |")
    lines += ["", "## Strongest and weakest seasons", "",
              "Ranked within each model by absolute MAE, with RMSE shown for context. "
              "These are descriptive error rankings, not proof of greater relative skill: "
              "ET magnitude, variability and sample counts differ between seasons.", "",
              "| Model | Lowest MAE season(s) | Highest MAE season(s) |",
              "|---|---|---|"]
    for model, group in metrics.groupby("model", sort=False):
        def extrema(minimize):
            best = group.mae.min() if minimize else group.mae.max()
            matches = group.loc[group.mae == best]
            return "; ".join(f"{r.season}: MAE {_number(r.mae)}, RMSE {_number(r.rmse)}, n={r.n}"
                             for r in matches.itertuples()) or "N/A"
        lines.append(f"| {MODEL_LABELS[model]} | {extrema(True)} | {extrema(False)} |")
    lines += ["", "## Hybrid findings", ""]
    for model, group in deltas.groupby("model", sort=False):
        for key, label in [("delta_mae", "MAE"), ("delta_rmse", "RMSE")]:
            better = ", ".join(group.loc[group[key] < 0, "season"]) or "none"
            worse = ", ".join(group.loc[group[key] > 0, "season"]) or "none"
            tied = ", ".join(group.loc[group[key] == 0, "season"]) or "none"
            unavailable = ", ".join(group.loc[~np.isfinite(group[key]), "season"]) or "none"
            lines.append(f"- {MODEL_LABELS[model]}, {label}: better than its ML-only counterpart in {better}; "
                         f"worse in {worse}; equal in {tied}; undefined in {unavailable} (unrounded differences).")
    lines += ["", "Results describe one station and two holdout years. Statistical significance and "
              "transferability are not established. Calendar seasons are not crop growth stages. "
              "The physical baseline estimates reference ET₀ without Kc, so its error includes target mismatch.",
              "", "## Reproduction", "", "```bash",
              "PYTHONPATH=src python -m ml.evaluation.seasonal", "```", "",
              "Outputs: seasonal_metrics.csv, seasonal_deltas.csv, seasonal_dates.csv, "
              "seasonal_errors.svg and seasonal_comparison.md in reports/. "
              "seasonal_dates.csv is the shared date-to-season audit used by every model.", ""]
    return "\n".join(lines)


def render_chart(metrics: pd.DataFrame) -> str:
    """Standalone labelled SVG heatmaps, requiring no optional plotting dependency."""
    models = list(MODEL_LABELS)
    width, height = 1080, 680
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<title>Seasonal MAE and RMSE on US-Ne2, 2023–2024</title>',
             '<desc>Seven models, four calendar seasons; lower errors are better. Each panel has its own scale.</desc>',
             '<rect width="100%" height="100%" fill="white"/>']
    def text(x, y, value, size=15, anchor="start"):
        parts.append(f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" '
                     f'text-anchor="{anchor}" fill="#16324a">{escape(str(value))}</text>')
    text(30, 38, "Seasonal prediction errors · US-Ne2 · 2023–2024", 24)
    text(30, 66, "Lower is better. Values in mm/day; separate colour scales for MAE and RMSE.")
    indexed = metrics.set_index(["model", "season"])
    for panel, key in enumerate(["mae", "rmse"]):
        left = 280 + panel * 400
        finite = metrics.loc[np.isfinite(metrics[key]), key]
        maximum = float(finite.max()) if len(finite) else 0
        text(left + 160, 108, key.upper(), 21, "middle")
        for col, season in enumerate(SEASON_ORDER):
            n = int(indexed.loc[(models[0], season), "n"])
            text(left + col * 88 + 41, 140, season, anchor="middle")
            text(left + col * 88 + 41, 162, f"n={n}", 12, "middle")
        for row, model in enumerate(models):
            y = 180 + row * 56
            if panel == 0:
                text(24, y + 31, MODEL_LABELS[model], 15)
            for col, season in enumerate(SEASON_ORDER):
                value = indexed.loc[(model, season), key]
                ratio = float(value / maximum) if np.isfinite(value) and maximum else 0
                rgb = tuple(round(a + ratio * (b-a)) for a, b in zip((239, 246, 255), (80, 159, 202)))
                fill = f"rgb{rgb}" if np.isfinite(value) else "#e5e7eb"
                x = left + col * 88
                parts.append(f'<rect x="{x}" y="{y}" width="82" height="50" rx="4" fill="{fill}"/>')
                text(x + 41, y + 31, f"{value:.3f}" if np.isfinite(value) else "N/A", 15, "middle")
        text(left, 601, f"Colour scale: 0 (light) → {maximum:.3f} (dark)", 13)
    text(30, 637, "Same observed dates within each season for all models. DJF pools Jan, Feb and Dec from both years.", 13)
    text(30, 660, "FAO-56 predicts reference ET₀; all errors are measured against actual ET. N/A = undefined.", 13)
    return "\n".join(parts + ["</svg>", ""])


def run(predictions_dir=DEFAULT_PREDICTIONS_DIR, test_path=DEFAULT_TEST_PATH,
        output_dir=DEFAULT_PREDICTIONS_DIR):
    frames = load_canonical_predictions(predictions_dir, test_path, required=tuple(MODEL_LABELS))
    metrics = seasonal_metrics(frames)
    deltas = seasonal_deltas(metrics)
    reference = next(iter(frames.values()))
    dates = reference[["date"]].copy()
    dates["season"] = assign_seasons(dates.date)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(output_dir / "seasonal_metrics.csv", index=False, na_rep="NaN")
    deltas.to_csv(output_dir / "seasonal_deltas.csv", index=False, na_rep="NaN")
    dates.to_csv(output_dir / "seasonal_dates.csv", index=False, date_format="%Y-%m-%d")
    (output_dir / "seasonal_comparison.md").write_text(render_report(metrics, deltas), encoding="utf-8")
    (output_dir / "seasonal_errors.svg").write_text(render_chart(metrics), encoding="utf-8")
    return metrics, deltas


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--predictions-dir", type=Path, default=DEFAULT_PREDICTIONS_DIR)
    parser.add_argument("--test-path", type=Path, default=DEFAULT_TEST_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_PREDICTIONS_DIR)
    args = parser.parse_args(argv)
    metrics, _ = run(args.predictions_dir, args.test_path, args.output_dir)
    print(metrics[["model", "season", "n", "mae", "rmse"]].to_string(index=False))
    print(f"Saved seasonal tables, date audit, chart and report to {args.output_dir}")


if __name__ == "__main__":
    main()
