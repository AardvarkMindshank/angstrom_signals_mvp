"""Method v3 rule: a date with no valid forward target is not an observation. It must not appear in any
statistic's rows, so it cannot inflate the reported sample size or the degrees of freedom.

The frozen hold-out (tag holdout-spec-v1, method v2) broke this rule for C1/C2: 8 trailing empty rows were
counted (471 and 701 dates instead of 463 and 693; C2 df 35 instead of 34). That result stands as recorded;
these tests stop it happening again."""

import math

import numpy as np
import pandas as pd
import pytest

import research_stats as st

H = 7


def panel(n=300, k=6, seed=0, tail=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n + tail, freq="D")
    a = pd.DataFrame(rng.normal(size=(n + tail, k)), index=idx)
    b = a + rng.normal(scale=1.5, size=a.shape)
    y = a.abs() + rng.normal(scale=0.5, size=a.shape)
    if tail:
        y.iloc[-tail:] = np.nan                      # no valid target at the end, as with forward windows
    return a, b, y


def test_forecast_gain_drops_dates_without_a_target():
    a, b, y = panel(tail=H + 1)
    num, den = st.forecast_gain_rows(a, b, y)
    assert len(num) == len(den) == 300               # the 8 empty trailing dates are gone


def test_forecast_gain_estimate_unchanged_by_the_fix():
    a, b, y = panel(tail=H + 1)
    num, den = st.forecast_gain_rows(a, b, y)
    clean_num, clean_den = st.forecast_gain_rows(a.iloc[:-(H + 1)], b.iloc[:-(H + 1)], y.iloc[:-(H + 1)])
    assert num.sum() / den.sum() == pytest.approx(clean_num.sum() / clean_den.sum(), abs=1e-12)
    np.testing.assert_allclose(num, clean_num)


def test_reported_dates_and_df_count_valid_dates_only():
    a, b, y = panel(n=463, tail=H + 1, seed=3)
    num, den = st.forecast_gain_rows(a, b, y)
    t = st.studentised_test(num, den, H, 1.2, 1, runs=200)
    assert t["dates"] == 463
    assert t["df"] == math.ceil(463 / st.block_for(H)) - 1           # 24 blocks -> 23
    a2, b2, y2 = panel(n=693, tail=H + 1, seed=4)
    t2 = st.studentised_test(*st.forecast_gain_rows(a2, b2, y2), H, 1.2, 1, runs=200)
    assert t2["dates"] == 693 and t2["df"] == math.ceil(693 / st.block_for(H)) - 1   # 35 blocks -> 34


@pytest.mark.parametrize("builder", ["spread", "relative_timing", "forecast_gain"])
def test_every_statistic_ignores_trailing_dates_without_targets(builder):
    """Adding dates that have signals but no forward target must change nothing: not the rows, not the
    estimate, not the count, not the degrees of freedom."""
    rng = np.random.default_rng(9)
    n, tail, k = 400, 15, 10
    idx = pd.date_range("2023-01-01", periods=n + tail, freq="D")
    sig = pd.DataFrame(rng.normal(size=(n + tail, k)), index=idx, columns=[f"C{i}-USD" for i in range(k)])
    fwd = pd.DataFrame(rng.normal(size=(n + tail, k)), index=idx, columns=sig.columns)
    fwd.iloc[-tail:] = np.nan

    def rows(s, f):
        if builder == "spread":
            num, den, _ = st.spread_rows(s, f)
        elif builder == "relative_timing":
            num, den, _ = st.relative_timing_rows(s, f, min_history=50)
        else:
            num, den = st.forecast_gain_rows(s, s.rank(), f)
        return num, den

    full, short = rows(sig, fwd), rows(sig.iloc[:-tail], fwd.iloc[:-tail])
    assert len(full[0]) == len(short[0])
    np.testing.assert_allclose(full[0], short[0])
    ta = st.studentised_test(*full, 14, 1.0, 1, runs=100, seed=1)
    tb = st.studentised_test(*short, 14, 1.0, 1, runs=100, seed=1)
    assert ta["dates"] == tb["dates"] and ta["df"] == tb["df"]
    assert ta["estimate"] == pytest.approx(tb["estimate"], abs=1e-12)
