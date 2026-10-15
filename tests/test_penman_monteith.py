"""Tests for FAO-56 Penman-Monteith daily ET0.

Reference values come from FAO-56 Chapter 4, EXAMPLE 18 "Determination of ETo
with daily data" (Uccle, Brussels, 6 July; 50°48'N, 100 m a.s.l.), source:
https://www.fao.org/4/x0490e/x0490e08.htm
"""

import math

import numpy as np
import pandas as pd
import pytest

from ml.fao56.penman_monteith import (
    et0_daily,
    psychrometric_constant,
    saturation_vapour_pressure,
    slope_vapour_pressure_curve,
    wind_speed_2m,
)

# EXAMPLE 18 inputs, as printed in the book.
TMAX_C = 21.5
TMIN_C = 12.3
RH_MAX_PCT = 84.0
RH_MIN_PCT = 63.0
WS_10M_MS = 2.78  # 10 km/h measured at 10 m
WIND_HEIGHT_M = 10.0
P_KPA = 100.1
EA_KPA = 1.409  # book, Eq. 17 from RHmax/RHmin
RN_MJ_M2_DAY = 13.28  # book, Eq. 40

# EXAMPLE 18 answer: "ETo (Eq. 6) = 2.81 + 1.07 = 3.88 ~ 3.9 mm/day".
ET0_BOOK_MM_DAY = 3.9
TOLERANCE_MM_DAY = 0.1


def test_intermediate_values_match_example_18():
    assert wind_speed_2m(WS_10M_MS, WIND_HEIGHT_M) == pytest.approx(2.078, abs=0.005)
    assert saturation_vapour_pressure(TMAX_C) == pytest.approx(2.564, abs=0.001)
    assert saturation_vapour_pressure(TMIN_C) == pytest.approx(1.431, abs=0.001)
    assert slope_vapour_pressure_curve((TMAX_C + TMIN_C) / 2) == pytest.approx(0.122, abs=0.0005)
    assert psychrometric_constant(P_KPA) == pytest.approx(0.0666, abs=0.00005)


def test_et0_matches_example_18():
    # ea is passed exactly as in the book, so only Eq. 6 itself is tested here;
    # rh_mean_pct is ignored when ea_kpa is given.
    et0 = et0_daily(
        TMAX_C, TMIN_C, rh_mean_pct=np.nan, ws_ms=WS_10M_MS,
        rn_mj_m2_day=RN_MJ_M2_DAY, p_kpa=P_KPA,
        wind_height_m=WIND_HEIGHT_M, ea_kpa=EA_KPA,
    )
    assert et0 == pytest.approx(ET0_BOOK_MM_DAY, abs=TOLERANCE_MM_DAY)


def test_rh_mean_path_uses_eq_19():
    # Assumption: daily.csv has only RHmean, so ea comes from FAO-56 Eq. 19,
    # ea = RHmean/100 * es. With RHmean = (84 + 63) / 2 = 73.5 % this gives
    # ea ~ 1.468 kPa instead of the book's 1.409 kPa (Eq. 17), so ET0 is
    # ~0.1 mm/day lower than 3.88. Here we only check that the rh_mean path is
    # identical to passing the Eq. 19 vapour pressure explicitly.
    rh_mean = (RH_MAX_PCT + RH_MIN_PCT) / 2
    es = (saturation_vapour_pressure(TMAX_C) + saturation_vapour_pressure(TMIN_C)) / 2
    common = dict(ws_ms=WS_10M_MS, rn_mj_m2_day=RN_MJ_M2_DAY, p_kpa=P_KPA, wind_height_m=WIND_HEIGHT_M)

    from_rh = et0_daily(TMAX_C, TMIN_C, rh_mean_pct=rh_mean, **common)
    from_ea = et0_daily(TMAX_C, TMIN_C, rh_mean_pct=np.nan, ea_kpa=rh_mean / 100 * es, **common)

    assert from_rh == pytest.approx(from_ea, abs=1e-12)


def test_wind_height_2m_is_unchanged():
    assert wind_speed_2m(3.0) == 3.0


def test_scalar_nan_returns_nan_without_error():
    et0 = et0_daily(np.nan, TMIN_C, 70.0, 2.0, RN_MJ_M2_DAY, P_KPA)
    assert math.isnan(et0)


def test_series_input_keeps_index_and_propagates_nan():
    index = pd.date_range("2020-07-01", periods=3, freq="D")
    tmax = pd.Series([TMAX_C, np.nan, TMAX_C], index=index)
    tmin = pd.Series([TMIN_C, TMIN_C, TMIN_C], index=index)
    ea = pd.Series([EA_KPA, EA_KPA, EA_KPA], index=index)
    ws = pd.Series([WS_10M_MS, WS_10M_MS, np.nan], index=index)

    et0 = et0_daily(
        tmax, tmin, rh_mean_pct=np.nan, ws_ms=ws, rn_mj_m2_day=RN_MJ_M2_DAY,
        p_kpa=P_KPA, wind_height_m=WIND_HEIGHT_M, ea_kpa=ea,
    )

    assert isinstance(et0, pd.Series)
    assert et0.index.equals(index)
    assert et0.iloc[0] == pytest.approx(ET0_BOOK_MM_DAY, abs=TOLERANCE_MM_DAY)
    assert et0.iloc[1:].isna().all()
