"""Tests for evaluation metrics on a small hand-computable example."""

import math

import numpy as np
import pandas as pd
import pytest

from ml.evaluation.metrics import bias, evaluate, mae, r2, rmse

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
#   (1 - SS_res/SS_tot would give 1 - 2/5 = 0.6, so this example also
#    distinguishes squared Pearson from NSE.)
OBS = [1.0, 2.0, 3.0, 4.0]
PRED = [2.0, 2.0, 4.0, 4.0]


def test_hand_example():
    assert rmse(OBS, PRED) == pytest.approx(math.sqrt(0.5))
    assert mae(OBS, PRED) == pytest.approx(0.5)
    assert bias(OBS, PRED) == pytest.approx(0.5)
    assert r2(OBS, PRED) == pytest.approx(0.8)


def test_bias_sign_underestimation():
    # pred - obs = [-1, -1] -> bias = -1 (prediction underestimates).
    assert bias([3.0, 5.0], [2.0, 4.0]) == pytest.approx(-1.0)


def test_evaluate_drops_nan_pairs():
    # Same example with one NaN in obs and one NaN in pred appended:
    # both extra pairs are dropped, so results equal the hand example with n = 4.
    obs = pd.Series(OBS + [np.nan, 5.0])
    pred = np.array(PRED + [3.0, np.nan])

    result = evaluate(obs, pred)

    assert set(result) == {"rmse", "mae", "r2", "bias", "n"}
    assert result["n"] == 4
    assert result["rmse"] == pytest.approx(math.sqrt(0.5))
    assert result["mae"] == pytest.approx(0.5)
    assert result["bias"] == pytest.approx(0.5)
    assert result["r2"] == pytest.approx(0.8)


def test_all_nan_gives_nan_and_zero_n():
    result = evaluate([np.nan, 1.0], [2.0, np.nan])
    assert result["n"] == 0
    assert all(math.isnan(result[key]) for key in ("rmse", "mae", "r2", "bias"))


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


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        evaluate([1.0, 2.0], [1.0])
