"""Tests for evaluation metrics on a small hand-computable example."""

import math

import numpy as np
import pandas as pd
import pytest

from ml.evaluation.metrics import bias, evaluate, kge, mae, nse, r2, rmse
from ml.fao56.baseline import DEFAULT_DATA_DIR, add_et0, load_split

# Hand calculation for obs = [1, 2, 3, 4], pred = [2, 2, 4, 4]:
#   errors pred - obs       = [1, 0, 1, 0]
#   bias = (1+0+1+0)/4      = 0.5   (positive: prediction overestimates)
#   mae  = (1+0+1+0)/4      = 0.5
#   rmse = sqrt((1+0+1+0)/4) = sqrt(0.5) = 0.70710678
#   r2 (squared Pearson):
#     mean(obs) = 2.5, deviations = [-1.5, -0.5, 0.5, 1.5], sum of squares = 5
#     mean(pred) = 3,  deviations = [-1, -1, 1, 1],         sum of squares = 4
#     sum of products = 1.5 + 0.5 + 0.5 + 1.5 = 4
#     r = 4 / sqrt(5 * 4) = 0.894427, r2 = 16 / 20 = 0.8
#   nse = 1 - SS_res / SS_tot = 1 - 2/5 = 0.6, so this example also
#     distinguishes squared Pearson from NSE.
#   kge (std with ddof=0):
#     r = 2/sqrt(5), alpha = std(pred)/std(obs) = sqrt(4/4) / sqrt(5/4) = 2/sqrt(5),
#     beta = mean(pred)/mean(obs) = 3 / 2.5 = 1.2
#     kge = 1 - sqrt(2 * (1 - 2/sqrt(5))^2 + 0.2^2) = 0.7504179
OBS = [1.0, 2.0, 3.0, 4.0]
PRED = [2.0, 2.0, 4.0, 4.0]


def test_hand_example():
    assert rmse(OBS, PRED) == pytest.approx(math.sqrt(0.5))
    assert mae(OBS, PRED) == pytest.approx(0.5)
    assert bias(OBS, PRED) == pytest.approx(0.5)
    assert r2(OBS, PRED) == pytest.approx(0.8)
    assert nse(OBS, PRED) == pytest.approx(0.6)
    r = 2 / math.sqrt(5)
    assert kge(OBS, PRED) == pytest.approx(1 - math.sqrt(2 * (1 - r) ** 2 + 0.2 ** 2))
    assert kge(OBS, PRED) == pytest.approx(0.7504179, abs=1e-7)


def test_scale_error_example():
    # obs = [1, 2, 3], pred = 2 * obs = [2, 4, 6]:
    #   nse: SS_res = 1 + 4 + 9 = 14, SS_tot = 1 + 0 + 1 = 2 -> 1 - 14/2 = -6
    #   kge: r = 1, alpha = 2, beta = 2 -> 1 - sqrt(0 + 1 + 1) = 1 - sqrt(2)
    obs = [1.0, 2.0, 3.0]
    pred = [2.0, 4.0, 6.0]
    assert nse(obs, pred) == pytest.approx(-6.0)
    assert kge(obs, pred) == pytest.approx(1 - math.sqrt(2))
    assert r2(obs, pred) == pytest.approx(1.0)


def test_perfect_prediction():
    obs = [0.5, 1.0, 3.0, 4.5]
    assert nse(obs, obs) == pytest.approx(1.0)
    assert kge(obs, obs) == pytest.approx(1.0)


def test_bias_sign_underestimation():
    # pred - obs = [-1, -1] -> bias = -1 (prediction underestimates).
    assert bias([3.0, 5.0], [2.0, 4.0]) == pytest.approx(-1.0)


def test_evaluate_drops_nan_pairs():
    # Same example with one NaN in obs and one NaN in pred appended:
    # both extra pairs are dropped, so results equal the hand example with n = 4.
    obs = pd.Series(OBS + [np.nan, 5.0])
    pred = np.array(PRED + [3.0, np.nan])

    result = evaluate(obs, pred)

    assert set(result) == {"rmse", "mae", "r2", "bias", "nse", "kge", "n"}
    assert result["n"] == 4
    assert result["rmse"] == pytest.approx(math.sqrt(0.5))
    assert result["mae"] == pytest.approx(0.5)
    assert result["bias"] == pytest.approx(0.5)
    assert result["r2"] == pytest.approx(0.8)
    assert result["nse"] == pytest.approx(0.6)
    assert result["kge"] == pytest.approx(0.7504179, abs=1e-7)
    assert nse(obs, pred) == pytest.approx(0.6)
    assert kge(obs, pred) == pytest.approx(0.7504179, abs=1e-7)


def test_all_nan_gives_nan_and_zero_n():
    result = evaluate([np.nan, 1.0], [2.0, np.nan])
    assert result["n"] == 0
    assert all(math.isnan(result[key]) for key in ("rmse", "mae", "r2", "bias", "nse", "kge"))


def test_r2_ignores_offset():
    # pred = obs + 5: perfect correlation, so r2 = 1 while bias = 5.
    obs = [1.0, 2.0, 3.0]
    pred = [6.0, 7.0, 8.0]
    assert r2(obs, pred) == pytest.approx(1.0)
    assert bias(obs, pred) == pytest.approx(5.0)


@pytest.mark.parametrize(
    "obs, pred",
    [
        ([2.0, 2.0, 2.0], [1.0, 2.0, 3.0]),  # constant obs
        ([1.0, 2.0, 3.0], [2.0, 2.0, 2.0]),  # constant pred
    ],
)
def test_r2_constant_series_gives_nan(obs, pred):
    # Zero variance -> Pearson correlation undefined -> NaN, no exception or warning.
    with np.errstate(all="raise"):
        assert math.isnan(r2(obs, pred))


@pytest.mark.parametrize(
    "obs, pred",
    [
        ([2.0, 2.0, 2.0], [1.0, 2.0, 3.0]),  # constant obs: NSE and KGE undefined
        ([5.0], [4.0]),  # single pair: obs has zero variance
    ],
)
def test_nse_kge_zero_obs_variance_gives_nan(obs, pred):
    with np.errstate(all="raise"):
        assert math.isnan(nse(obs, pred))
        assert math.isnan(kge(obs, pred))


def test_kge_degenerate_cases_give_nan():
    with np.errstate(all="raise"):
        # Constant pred: correlation undefined, but NSE is still defined.
        assert math.isnan(kge([1.0, 2.0, 3.0], [2.0, 2.0, 2.0]))
        assert nse([1.0, 2.0, 3.0], [2.0, 2.0, 2.0]) == pytest.approx(0.0)
        # mean(obs) = 0: beta undefined.
        assert math.isnan(kge([-1.0, 0.0, 1.0], [-1.0, 0.0, 2.0]))


@pytest.mark.parametrize("metric", [rmse, mae, bias, r2, nse, kge, evaluate])
def test_length_mismatch_raises(metric):
    with pytest.raises(ValueError, match="same length"):
        metric([1.0, 2.0], [1.0])


def test_fao56_et0_test_split_regression():
    # FAO-56 ET0 vs observed ET on the held-out 2023-2024 split: project values
    # from reports/baseline_metrics.csv and reports/comparison_metrics.csv.
    test = add_et0(load_split(DEFAULT_DATA_DIR / "test.csv"))
    result = evaluate(test["et_obs_mm"], test["et0_mm"])

    assert result["n"] == 561
    assert result["nse"] == pytest.approx(-0.02235, abs=5e-5)
    assert result["rmse"] == pytest.approx(1.6439, abs=5e-5)
    assert result["mae"] == pytest.approx(1.1133, abs=5e-5)
    assert result["r2"] == pytest.approx(0.4736, abs=5e-5)
    assert result["bias"] == pytest.approx(0.9175, abs=5e-5)
