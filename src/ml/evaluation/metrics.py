"""Point-wise evaluation metrics for ET estimates against observations.

Every function takes observations first and predictions second, as array-like
inputs of equal length. Pairs where either value is NaN are dropped before the
metric is computed. If no valid pairs remain, metrics return NaN.
"""

import numpy as np


def _valid_pairs(obs, pred):
    """Return (obs, pred) as float arrays with NaN pairs removed.

    Raises ValueError if the inputs are not 1-D or differ in length.
    """
    obs = np.asarray(obs, dtype=float)
    pred = np.asarray(pred, dtype=float)
    if obs.ndim != 1 or pred.ndim != 1:
        raise ValueError("obs and pred must be 1-D")
    if obs.shape != pred.shape:
        raise ValueError(f"obs and pred must have the same length, got {obs.size} and {pred.size}")
    mask = ~(np.isnan(obs) | np.isnan(pred))
    return obs[mask], pred[mask]


def rmse(obs, pred):
    """Root mean square error, sqrt(mean((pred - obs)^2)), in the units of the inputs."""
    obs, pred = _valid_pairs(obs, pred)
    if obs.size == 0:
        return np.nan
    return float(np.sqrt(np.mean((pred - obs) ** 2)))


def mae(obs, pred):
    """Mean absolute error, mean(|pred - obs|), in the units of the inputs."""
    obs, pred = _valid_pairs(obs, pred)
    if obs.size == 0:
        return np.nan
    return float(np.mean(np.abs(pred - obs)))


def bias(obs, pred):
    """Mean bias, mean(pred - obs). Positive means the prediction overestimates."""
    obs, pred = _valid_pairs(obs, pred)
    if obs.size == 0:
        return np.nan
    return float(np.mean(pred - obs))


def r2(obs, pred):
    """Squared Pearson correlation between obs and pred, r^2.

    This is NOT sklearn.metrics.r2_score and NOT the Nash-Sutcliffe efficiency
    (NSE): both of those are 1 - SS_res / SS_tot, see nse(). r^2 only measures linear association and ignores systematic offset
    or scale error (pred = obs + 5 gives r^2 = 1); use bias for the offset.

    Returns NaN, without raising, if fewer than two pairs remain or either
    series is constant (zero variance).
    """
    obs, pred = _valid_pairs(obs, pred)
    if obs.size < 2:
        return np.nan
    obs_dev = obs - obs.mean()
    pred_dev = pred - pred.mean()
    denominator = np.sqrt(np.sum(obs_dev ** 2) * np.sum(pred_dev ** 2))
    if denominator == 0:
        return np.nan
    r = np.sum(obs_dev * pred_dev) / denominator
    return float(r ** 2)


def nse(obs, pred):
    """Nash-Sutcliffe efficiency, 1 - sum((obs - pred)^2) / sum((obs - mean(obs))^2).

    NSE = 1 is a perfect fit, NSE = 0 means the prediction is as good as the
    observed mean, and NSE < 0 means it is worse. Unlike r2(), NSE penalises
    systematic offset and scale error. It equals sklearn.metrics.r2_score.

    Returns NaN, without raising, if no pairs remain or obs is constant (zero
    variance), because the denominator is then zero and NSE is undefined.
    """
    obs, pred = _valid_pairs(obs, pred)
    if obs.size == 0:
        return np.nan
    ss_tot = np.sum((obs - obs.mean()) ** 2)
    if ss_tot == 0:
        return np.nan
    ss_res = np.sum((obs - pred) ** 2)
    return float(1.0 - ss_res / ss_tot)


def kge(obs, pred):
    """Kling-Gupta efficiency (Gupta et al. 2009).

    KGE = 1 - sqrt((r - 1)^2 + (alpha - 1)^2 + (beta - 1)^2), where r is the
    Pearson correlation, alpha = std(pred) / std(obs) and
    beta = mean(pred) / mean(obs). Both standard deviations use ddof=0; the
    choice cancels in alpha. KGE = 1 is a perfect fit.

    Returns NaN, without raising, if fewer than two pairs remain, either series
    is constant (r and alpha are undefined), or mean(obs) is zero (beta is
    undefined).
    """
    obs, pred = _valid_pairs(obs, pred)
    if obs.size < 2:
        return np.nan
    obs_std = obs.std()
    pred_std = pred.std()
    obs_mean = obs.mean()
    if obs_std == 0 or pred_std == 0 or obs_mean == 0:
        return np.nan
    r = np.mean((obs - obs_mean) * (pred - pred.mean())) / (obs_std * pred_std)
    alpha = pred_std / obs_std
    beta = pred.mean() / obs_mean
    return float(1.0 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2))


def evaluate(obs, pred):
    """Compute all metrics on the same valid pairs.

    Returns a dict with keys rmse, mae, r2, bias, nse, kge and n, where n is the
    number of (obs, pred) pairs left after dropping NaN.
    """
    obs, pred = _valid_pairs(obs, pred)
    return {
        "rmse": rmse(obs, pred),
        "mae": mae(obs, pred),
        "r2": r2(obs, pred),
        "bias": bias(obs, pred),
        "nse": nse(obs, pred),
        "kge": kge(obs, pred),
        "n": int(obs.size),
    }
