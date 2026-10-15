"""Tests for the FAO-56 baseline script on small hand-made data."""

import math

import numpy as np
import pandas as pd
import pytest

from ml.fao56.baseline import (
    DEFAULT_DATA_DIR,
    METRIC_COLUMNS,
    compute_metrics,
    run_baseline,
)
from ml.fao56.penman_monteith import et0_daily

COLUMNS = ["date", "et_obs_mm", "tmax_c", "tmin_c", "rh_mean_pct", "ws_ms",
           "rn_mj_m2_day", "p_kpa", "precip_mm", "doy"]


def test_compute_metrics_hand_example():
    # et0_mm is given directly, so the metrics can be checked by hand.
    # train: one day per season (Jan, Apr, Jul, Oct), obs = [1, 2, 3, 4], et0 = [2, 2, 4, 4]
    #   errors = [1, 0, 1, 0] -> bias = 0.5, mae = 0.5, rmse = sqrt(0.5)
    #   r2 (squared Pearson) = 16 / (5 * 4) = 0.8  (see test_metrics.py)
    #   by season: DJF +1, MAM 0, JJA +1, SON 0
    # test: one day per season, et0 - obs = DJF +1, MAM +2, JJA -1, SON +2
    #   bias = (1 + 2 - 1 + 2) / 4 = 1.0, mae = 6 / 4 = 1.5,
    #   rmse = sqrt((1 + 4 + 1 + 4) / 4) = sqrt(2.5)
    train = pd.DataFrame({
        "date": pd.to_datetime(["2020-01-10", "2020-04-10", "2020-07-10", "2020-10-10"]),
        "et_obs_mm": [1.0, 2.0, 3.0, 4.0],
        "et0_mm": [2.0, 2.0, 4.0, 4.0],
    })
    test = pd.DataFrame({
        "date": pd.to_datetime(["2023-12-15", "2023-04-15", "2023-07-15", "2023-10-15"]),
        "et_obs_mm": [0.5, 1.0, 5.0, 1.0],
        "et0_mm": [1.5, 3.0, 4.0, 3.0],
    })

    metrics = compute_metrics(train, test).set_index(["split", "season"])

    row = metrics.loc[("train", "all")]
    assert row["n"] == 4
    assert row["bias"] == pytest.approx(0.5)
    assert row["mae"] == pytest.approx(0.5)
    assert row["rmse"] == pytest.approx(math.sqrt(0.5))
    assert row["r2"] == pytest.approx(0.8)

    for season, error in [("DJF", 1.0), ("MAM", 0.0), ("JJA", 1.0), ("SON", 0.0)]:
        assert metrics.loc[("train", season), "n"] == 1
        assert metrics.loc[("train", season), "bias"] == pytest.approx(error)

    row = metrics.loc[("test", "all")]
    assert row["n"] == 4
    assert row["bias"] == pytest.approx(1.0)
    assert row["mae"] == pytest.approx(1.5)
    assert row["rmse"] == pytest.approx(math.sqrt(2.5))

    for season, error in [("DJF", 1.0), ("MAM", 2.0), ("JJA", -1.0), ("SON", 2.0)]:
        assert metrics.loc[("test", season), "n"] == 1
        assert metrics.loc[("test", season), "bias"] == pytest.approx(error)


def _write_split(path, dates, tmax):
    n = len(dates)
    frame = pd.DataFrame({
        "date": dates,
        "et_obs_mm": np.linspace(1.0, 4.0, n),
        "tmax_c": tmax,
        "tmin_c": [12.0] * n,
        "rh_mean_pct": [70.0] * n,
        "ws_ms": [3.0] * n,
        "rn_mj_m2_day": [-0.5] + [12.0] * (n - 1),
        "p_kpa": [97.0] * n,
        "precip_mm": [0.0] * n,
        "doy": [1] * n,
    }, columns=COLUMNS)
    frame.to_csv(path, index=False)
    return frame


def test_run_baseline_end_to_end_with_nan(tmp_path):
    train = _write_split(tmp_path / "train.csv",
                         ["2021-01-05", "2021-04-05", "2021-07-05", "2021-10-05"],
                         [5.0, np.nan, 28.0, 18.0])
    _write_split(tmp_path / "test.csv",
                 ["2023-01-05", "2023-04-05", "2023-07-05", "2023-10-05"],
                 [5.0, 15.0, 28.0, 18.0])
    output = tmp_path / "reports" / "baseline_metrics.csv"

    metrics = run_baseline(tmp_path, output)

    assert list(metrics.columns) == METRIC_COLUMNS
    assert list(zip(metrics["split"], metrics["season"])) == [
        (split, season)
        for split in ("train", "test")
        for season in ("all", "DJF", "MAM", "JJA", "SON")
    ]
    assert output.is_file()

    rows = metrics.set_index(["split", "season"])
    train_row = rows.loc[("train", "all")]
    assert train_row["n"] == 3  # the NaN tmax day is dropped, no exception
    assert rows.loc[("train", "MAM"), "n"] == 0  # the only MAM day is NaN
    assert math.isnan(rows.loc[("train", "MAM"), "rmse"])
    assert rows.loc[("test", "all"), "n"] == 4

    # ET0 uses the 6.2 m anemometer height; check the bias against a direct call.
    expected_et0 = et0_daily(train["tmax_c"], train["tmin_c"], train["rh_mean_pct"],
                             train["ws_ms"], train["rn_mj_m2_day"], train["p_kpa"],
                             wind_height_m=6.2)
    valid = expected_et0.notna()
    expected_bias = (expected_et0[valid] - train["et_obs_mm"][valid]).mean()
    assert train_row["bias"] == pytest.approx(expected_bias)


def test_default_data_dir_is_processed():
    assert DEFAULT_DATA_DIR.parts[-2:] == ("data", "processed")


def test_run_baseline_rejects_test_period_in_train(tmp_path):
    _write_split(tmp_path / "train.csv", ["2022-12-30", "2023-01-02"], [10.0, 10.0])
    _write_split(tmp_path / "test.csv", ["2023-07-05", "2023-07-06"], [28.0, 28.0])
    with pytest.raises(ValueError):
        run_baseline(tmp_path, output_path=None)
