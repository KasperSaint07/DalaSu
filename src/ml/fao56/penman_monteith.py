"""FAO-56 Penman-Monteith reference evapotranspiration (ET0), daily time step.

Equations follow Allen et al. (1998), FAO Irrigation and Drainage Paper 56,
Chapter 3 (parameters) and Chapter 4 (Eq. 6, daily ET0).

All functions accept scalars, numpy arrays or pandas Series. NaN inputs
propagate to NaN outputs and never raise.
"""

import numpy as np


def saturation_vapour_pressure(t_c):
    """Saturation vapour pressure e°(T) [kPa] at air temperature t_c [°C] (FAO-56 Eq. 11)."""
    return 0.6108 * np.exp(17.27 * t_c / (t_c + 237.3))


def slope_vapour_pressure_curve(t_c):
    """Slope of the saturation vapour pressure curve Δ [kPa/°C] at t_c [°C] (FAO-56 Eq. 13)."""
    return 4098.0 * saturation_vapour_pressure(t_c) / (t_c + 237.3) ** 2


def psychrometric_constant(p_kpa):
    """Psychrometric constant γ [kPa/°C] for atmospheric pressure p_kpa [kPa] (FAO-56 Eq. 8)."""
    return 0.665e-3 * p_kpa


def wind_speed_2m(ws_ms, wind_height_m=2.0):
    """Convert wind speed ws_ms [m/s] measured at wind_height_m [m] to 2 m height [m/s].

    Uses the FAO-56 logarithmic wind profile (Eq. 47). Returns ws_ms unchanged
    when wind_height_m == 2.0.
    """
    if wind_height_m <= 0.1:
        raise ValueError("wind_height_m must be greater than 0.1 m for FAO-56 Eq. 47")
    if wind_height_m == 2.0:
        return ws_ms
    return ws_ms * 4.87 / np.log(67.8 * wind_height_m - 5.42)


def et0_daily(
    tmax_c,
    tmin_c,
    rh_mean_pct,
    ws_ms,
    rn_mj_m2_day,
    p_kpa,
    wind_height_m=2.0,
    ea_kpa=None,
):
    """Daily grass reference evapotranspiration ET0 by FAO-56 Penman-Monteith (Eq. 6).

    Parameters
    ----------
    tmax_c : float or array-like
        Daily maximum air temperature [°C].
    tmin_c : float or array-like
        Daily minimum air temperature [°C].
    rh_mean_pct : float or array-like
        Daily mean relative humidity [%]. Used to derive actual vapour pressure
        with FAO-56 Eq. 19: ea = RHmean / 100 * (e°(Tmax) + e°(Tmin)) / 2.
        Eq. 19 is less accurate than Eq. 17 (RHmax/RHmin), which needs data
        that daily.csv does not provide. Ignored when ea_kpa is given.
    ws_ms : float or array-like
        Daily mean wind speed [m/s] measured at wind_height_m.
    rn_mj_m2_day : float or array-like
        Net radiation at the crop surface [MJ m-2 day-1].
    p_kpa : float or array-like
        Atmospheric pressure [kPa].
    wind_height_m : float, default 2.0
        Height of the wind measurement [m]; converted to 2 m with FAO-56 Eq. 47.
    ea_kpa : float or array-like, optional
        Actual vapour pressure [kPa]. Overrides rh_mean_pct when given.

    Returns
    -------
    float or array-like
        ET0 [mm day-1], same shape (and index, for pandas Series) as the inputs.
        Soil heat flux G is taken as 0 for the daily step (FAO-56 Eq. 42).
        The result is not clipped: negative Rn can give slightly negative ET0.
    """
    with np.errstate(invalid="ignore"):
        t_mean = (tmax_c + tmin_c) / 2.0
        es = (saturation_vapour_pressure(tmax_c) + saturation_vapour_pressure(tmin_c)) / 2.0
        if ea_kpa is None:
            ea_kpa = rh_mean_pct / 100.0 * es

        delta = slope_vapour_pressure_curve(t_mean)
        gamma = psychrometric_constant(p_kpa)
        u2 = wind_speed_2m(ws_ms, wind_height_m)
        g = 0.0

        numerator = 0.408 * delta * (rn_mj_m2_day - g) + gamma * 900.0 / (t_mean + 273.0) * u2 * (es - ea_kpa)
        denominator = delta + gamma * (1.0 + 0.34 * u2)
        return numerator / denominator
