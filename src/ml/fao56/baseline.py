"""FAO-56 Penman-Monteith baseline against measured daily ET at AmeriFlux US-Ne2.

Reads train.csv (2015-2022) and test.csv (2023-2024), computes daily reference
ET0 with et0_daily and compares it with et_obs_mm using evaluate(). Metrics are
reported for train and test, each overall and by meteorological season
(DJF, MAM, JJA, SON).

The physical model has no fitted parameters, so the test split is used only for
evaluation. The only site constant is the anemometer height (6.2 m, from
data/README.md), which is converted to 2 m by FAO-56 Eq. 47.

Limitations stated in the output:
- Decision D-1: reference ET0 (grass) is compared directly with measured actual
  ET of the maize/soybean field, without a crop coefficient Kc. Seasonal bias is
  therefore expected (Kc < 1 off-season, Kc > 1 at canopy peak).
- The data has only rh_mean_pct, so actual vapour pressure comes from FAO-56
  Eq. 19 instead of Eq. 17; in FAO-56 Example 18 this lowers ET0 by about 3%.
- Negative ET0 values (negative net radiation in winter) are not clipped.

Usage, from the repository root:
    $env:PYTHONPATH = "src"   # PowerShell; use `export PYTHONPATH=src` in bash
    python -m ml.fao56.baseline --data-dir data/processed
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ..evaluation.metrics import evaluate
from .penman_monteith import et0_daily

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "baseline_metrics.csv"

WIND_HEIGHT_M = 6.2
TRAIN_END = pd.Timestamp("2022-12-31")
TEST_START = pd.Timestamp("2023-01-01")
SEASONS = {
    12: "DJF", 1: "DJF", 2: "DJF",
    3: "MAM", 4: "MAM", 5: "MAM",
    6: "JJA", 7: "JJA", 8: "JJA",
    9: "SON", 10: "SON", 11: "SON",
}
SEASON_ORDER = ["DJF", "MAM", "JJA", "SON"]
METRIC_COLUMNS = [
    "split", "season", "n", "rmse", "mae", "r2", "bias",
    "mean_obs", "mean_et0", "n_neg_et0", "n_neg_obs",
]
NOTES = [
    "D-1: reference ET0 (grass) is compared with measured actual ET without Kc;",
    "     seasonal bias is expected (Kc < 1 off-season, Kc > 1 at canopy peak).",
    "Only rh_mean_pct is available: ea from FAO-56 Eq. 19 instead of Eq. 17,",
    "     ET0 is slightly underestimated (about 3% in FAO-56 Example 18).",
    f"Wind measured at {WIND_HEIGHT_M} m, converted to 2 m with FAO-56 Eq. 47 (x0.808).",
    "Negative ET0 and et_obs_mm values are kept (not clipped).",
    "No parameters are fitted; the test split is used for evaluation only.",
]


def load_split(path: Path) -> pd.DataFrame:
    """Read one split CSV and parse the date column."""
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
    return frame


def add_et0(frame: pd.DataFrame, wind_height_m: float = WIND_HEIGHT_M) -> pd.DataFrame:
    """Return a copy of frame with an et0_mm column [mm day-1] from FAO-56 PM."""
    out = frame.copy()
    out["et0_mm"] = et0_daily(
        out["tmax_c"],
        out["tmin_c"],
        out["rh_mean_pct"],
        out["ws_ms"],
        out["rn_mj_m2_day"],
        out["p_kpa"],
        wind_height_m=wind_height_m,
    )
    return out


def metrics_row(frame: pd.DataFrame, split: str, season: str) -> dict:
    """Metrics of et0_mm against et_obs_mm plus means and negative-value counts."""
    result = evaluate(frame["et_obs_mm"], frame["et0_mm"])
    return {
        "split": split,
        "season": season,
        **result,
        "mean_obs": frame["et_obs_mm"].mean(),
        "mean_et0": frame["et0_mm"].mean(),
        "n_neg_et0": int((frame["et0_mm"] < 0).sum()),
        "n_neg_obs": int((frame["et_obs_mm"] < 0).sum()),
    }


def compute_metrics(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Metrics table for train and test, overall and by season; frames need et0_mm."""
    rows = []
    for split, frame in [("train", train), ("test", test)]:
        rows.append(metrics_row(frame, split, "all"))
        seasons = frame["date"].dt.month.map(SEASONS)
        for season in SEASON_ORDER:
            rows.append(metrics_row(frame[seasons == season], split, season))
    return pd.DataFrame(rows, columns=METRIC_COLUMNS)


def run_baseline(
    data_dir: Path | str = DEFAULT_DATA_DIR,
    output_path: Path | str | None = DEFAULT_OUTPUT,
    wind_height_m: float = WIND_HEIGHT_M,
) -> pd.DataFrame:
    """Compute the FAO-56 baseline metrics; write CSV unless output_path is None."""
    data_dir = Path(data_dir)
    train = load_split(data_dir / "train.csv")
    test = load_split(data_dir / "test.csv")
    if train["date"].max() > TRAIN_END or test["date"].min() < TEST_START:
        raise ValueError("train must end by 2022-12-31 and test start from 2023-01-01")

    metrics = compute_metrics(add_et0(train, wind_height_m), add_et0(test, wind_height_m))
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metrics.to_csv(output_path, index=False, float_format="%.4f")
    return metrics


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="folder with train.csv and test.csv (default: data/processed)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="metrics CSV path (default: reports/baseline_metrics.csv)")
    args = parser.parse_args(argv)

    metrics = run_baseline(args.data_dir, args.output)
    print("FAO-56 Penman-Monteith baseline vs measured ET, US-Ne2 (mm/day)")
    print(f"Data: {args.data_dir}\n")
    print(metrics.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print("\nNotes:")
    for line in NOTES:
        print("  " + line)
    print(f"\nSaved: {args.output}")


if __name__ == "__main__":
    main()
