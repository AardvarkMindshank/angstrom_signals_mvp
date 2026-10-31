"""Safeguards for the hold-out validation: leakage, embargo dates, calibration, Holm, outcomes, portfolio
accounting and expected-move fitting. Synthetic data only; no scoring code, no downloads."""

import math

import numpy as np
import pandas as pd
import pytest
from pandas.tseries.offsets import CustomBusinessDay

import research as rs
import research_stats as st


# ----------------------------------------------------------------------------- leakage and embargo

def test_first_eligible_signal_dates_match_the_spec():
    start = pd.Timestamp("2024-10-30")
    daily = pd.date_range("2024-01-01", "2026-10-30", freq="D")
    assert st.first_eligible_signal(daily, start, rs.LABEL_BARS) == pd.Timestamp("2024-11-29")
    nyse_2024 = ["2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27", "2024-06-19",
                 "2024-07-04", "2024-09-02", "2024-11-28", "2024-12-25"]
    trading = pd.date_range("2024-01-02", "2024-12-31", freq=CustomBusinessDay(holidays=nyse_2024))
    assert st.first_eligible_signal(trading, start, rs.LABEL_BARS) == pd.Timestamp("2024-12-12")


def test_embargo_is_exactly_tight():
    """The last development label ends on the first eligible signal's bar, so its trade (next bar) never
    overlaps; one bar earlier would overlap."""
    idx = pd.date_range("2024-01-01", periods=400, freq="D")
    start = idx[200]
    first = st.first_eligible_signal(idx, start, rs.LABEL_BARS)
    p, q = idx.get_loc(start), idx.get_loc(first)
    last_dev_label_exit = (p - 1) + rs.LABEL_BARS            # signal p-1, entry p, exit p-1+1+30
    assert q + st.LAG > last_dev_label_exit
    assert (q - 1) + st.LAG <= last_dev_label_exit


def make_frames(n=900, seed=0, tickers=("XOM", "JPM", "SOL-USD")):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    frames = {}
    for t in tickers:
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
        frames[t] = pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
                                  "volume": 1.0}, index=idx)
    return frames


def test_development_frames_never_hold_holdout_bars_and_labels_stop_at_the_boundary():
    frames = make_frames()
    start = frames["XOM"].index[600]
    dev = rs.development_frames(frames, start)
    assert all(f.index.max() < start for f in dev.values())
    labels = st.forward_returns(dev["XOM"]["close"], 30)
    assert labels.iloc[-31:].isna().all() and labels.iloc[:-31].notna().all()


def test_changing_holdout_prices_changes_nothing_in_development():
    """The core leakage guard: any development number must be identical whatever the hold-out did."""
    frames = make_frames()
    start = frames["XOM"].index[600]
    other = {t: f.copy() for t, f in frames.items()}
    for f in other.values():
        f.loc[f.index >= start, ["open", "high", "low", "close"]] *= 3.0
    a, b = rs.development_frames(frames, start), rs.development_frames(other, start)
    for t in frames:
        pd.testing.assert_frame_equal(a[t], b[t])
        for h in rs.HORIZONS:
            pd.testing.assert_series_equal(st.forward_returns(a[t]["close"], h), st.forward_returns(b[t]["close"], h))
            pd.testing.assert_series_equal(st.move_size(a[t]["close"], h), st.move_size(b[t]["close"], h))


def test_v1_labels_did_leak_which_is_what_v2_fixes():
    """Documents the v1 defect: labels built on the full series and cut afterwards DO change."""
    frames = make_frames()
    start = frames["XOM"].index[600]
    other = frames["XOM"].copy()
    other.loc[other.index >= start, "close"] *= 3.0
    v1_a = rs.development_view(st.forward_returns(frames["XOM"]["close"], 30).to_frame(), start)
    v1_b = rs.development_view(st.forward_returns(other["close"], 30).to_frame(), start)
    assert not v1_a.equals(v1_b)


def test_start_is_checked_against_the_spec():
    idx = pd.date_range("2016-01-01", "2026-10-30", freq="D")
    frames = {"X": pd.DataFrame({"close": 1.0}, index=idx)}
    assert rs.checked_start(frames) == rs.HOLDOUT_START
    with pytest.raises(SystemExit):
        rs.checked_start({"X": pd.DataFrame({"close": 1.0}, index=idx[:-5])})


def test_expanding_percentile_uses_only_the_past():
    rng = np.random.default_rng(1)
    s = pd.Series(rng.normal(size=600))
    u = st.expanding_percentile(s, min_history=250)
    assert u.iloc[:250].isna().all() and u.iloc[250:].between(-0.5, 0.5).all()
    changed = s.copy()
    changed.iloc[400:] = 1e6
    pd.testing.assert_series_equal(u.iloc[:400], st.expanding_percentile(changed, 250).iloc[:400])


# ----------------------------------------------------------------------------- bias and calibration

def null_market(rng, n=1100, k=20, window=100):
    r = 0.015 * (0.6 * rng.normal(size=(n, 1)) + 0.8 * rng.normal(size=(n, k)))
    close = pd.DataFrame(np.exp(np.cumsum(r, axis=0)))
    trend = np.sign(close - close.rolling(window).mean()) * 4 + (close.pct_change(7) * 40).clip(-4, 4)
    return close, trend


def test_first_run_statistic_is_biased_and_the_new_one_is_not():
    """No real effect anywhere. The v1 statistic on a short window leans towards 'Trend negative';
    the relative-timing statistic does not."""
    rng = np.random.default_rng(11)
    v1, v2 = [], []
    for _ in range(16):
        close, trend = null_market(rng, k=30)
        fwd = st.forward_returns_table(close, 14)
        pct = pd.DataFrame({c: st.expanding_percentile(-trend[c]) for c in trend.columns})
        window = slice(600, 1060)
        n1, d1 = st.pooled_time_series_rows(-trend.iloc[window], fwd.iloc[window])
        v1.append(n1.sum() / d1.sum())
        n2, d2, _ = st.relative_timing_rows(-trend, fwd.iloc[window], percentiles=pct)
        v2.append(n2.sum() / d2.sum())
    se1, se2 = np.std(v1) / 4, np.std(v2) / 4                     # 16 runs
    assert np.mean(v1) > 0.02 and np.mean(v1) > 3 * se1           # clearly leans one way
    assert abs(np.mean(v2)) < 2.5 * se2                           # centred on zero


def test_rotation_diagnostic_sees_the_bias():
    rng = np.random.default_rng(12)
    close, trend = null_market(rng)
    fwd = st.forward_returns_table(close, 14)
    window = slice(600, 1060)
    assert st.rotation_null_mean(-trend.iloc[window], fwd.iloc[window], 14, lookback=100) > 0.01


def ma_rows(rng, n=460, h=14, effect=0.0):
    """Rows like the real ones: a persistent signal times an overlapping h-day sum of noise."""
    sig = np.zeros(n + h + 1)
    for i in range(1, len(sig)):
        sig[i] = 0.95 * sig[i - 1] + rng.normal() * math.sqrt(1 - 0.95 ** 2)
    noise = rng.normal(size=n + h + 1)
    fwd = np.convolve(noise, np.ones(h), "valid")[: n + 1] / math.sqrt(h)
    return sig[:n] * (fwd[1:n + 1] + effect * sig[:n])


def test_studentised_test_holds_its_false_alarm_rate():
    rng = np.random.default_rng(5)
    p = [st.studentised_test(ma_rows(rng), np.ones(460), 14, st.KAPPA["relative_timing"], 1,
                             runs=300, seed=int(rng.integers(1e9)))["p_value"] for _ in range(200)]
    p = np.array(p)
    assert np.mean(p <= 0.05) <= 0.08 and np.mean(p <= 0.01) <= 0.03


def test_studentised_test_finds_a_real_effect_and_separates_ci_from_p():
    rng = np.random.default_rng(6)
    t = st.studentised_test(ma_rows(rng, effect=1.0), np.ones(460), 14, 1.2, 1, mme=0.02, runs=500)
    assert t["p_value"] < 0.01 and t["ci95"][0] > 0
    assert t["one_sided_bound95"] > t["ci95"][0]                    # one-sided bound is tighter than the CI's
    assert "p_vs_mme" in t and t["p_vs_mme"] >= t["p_value"]      # beating a threshold is harder than beating 0
    neg = st.studentised_test(-ma_rows(rng, effect=1.0), np.ones(460), 14, 1.2, -1, runs=500)
    assert neg["p_value"] < 0.01                                    # direction -1 tests 'negative'


def test_holm_step_down():
    p = {"a": 0.004, "b": 0.011, "c": 0.02, "d": 0.03, "e": 0.2}
    assert st.holm(p) == {"a": True, "b": True, "c": False, "d": False, "e": False}
    assert st.holm({"a": 0.02, "b": 0.001}) == {"b": True, "a": True}
    assert st.holm({"a": None, "b": 0.001}) == {"b": True, "a": False}


def test_outcome_labels():
    base = {"estimate": 0.03, "se": 0.01, "df": 15}
    tq = st.t_dist.ppf(0.95, 15)
    make = lambda est, p_mme: {**base, "estimate": est, "one_sided_bound95": est - tq * 0.01,
                               "one_sided_upper95": est + tq * 0.01, "p_vs_mme": p_mme}
    assert st.outcome(make(0.03, 0.2), True, 0.02) == "Confirmed"
    assert st.outcome(make(0.05, 0.01), True, 0.02) == "Confirmed, clearly above the minimum"
    assert st.outcome(make(0.015, 0.7), True, 0.02) == "Inconclusive"        # significant but below the minimum
    assert st.outcome(make(0.03, 0.2), False, 0.02) == "Inconclusive"        # failed Holm
    assert st.outcome(make(-0.03, 1.0), False, 0.02) == "Contradicted"


# ----------------------------------------------------------------------------- spread and forecast gain

def test_spread_breaks_ties_by_column_order_and_needs_enough_assets():
    sig = pd.DataFrame([[1.0] * 9, [1.0] * 7 + [np.nan] * 2], columns=list("abcdefghi"))
    w = st.spread_weights(sig)
    assert list(w.iloc[0]) == pytest.approx([-1 / 3] * 3 + [0] * 3 + [1 / 3] * 3)
    assert (w.iloc[1] == 0).all()                                             # 7 assets < 8


def test_forecast_gain_is_zero_for_a_copy_and_positive_for_a_better_forecast():
    rng = np.random.default_rng(3)
    target = pd.DataFrame(rng.normal(size=(300, 5)))
    bench = target + rng.normal(scale=2.0, size=target.shape)
    num, den = st.forecast_gain_rows(bench, bench, target)
    assert num.sum() / den.sum() == pytest.approx(0.0, abs=1e-12)
    num, den = st.forecast_gain_rows(target + rng.normal(scale=0.3, size=target.shape), bench, target)
    assert num.sum() / den.sum() > 0.3


# ----------------------------------------------------------------------------- long-only portfolio accounting

def test_entry_is_at_the_next_close():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    closes = pd.DataFrame({"A": [1.0, 2.0, 3.0, 3.0], "B": [1.0, 1.0, 1.0, 1.0]}, index=idx)
    sig = pd.DataFrame({"A": [9.0, 9, 9, 9], "B": [0.0, 0, 0, 0]}, index=idx)
    res = st.long_only_portfolio(sig, closes, 1, period=10, cost_per_side=0.0, tranches=1)
    # signal at close 0, bought at close 1 (price 2): the jump 1->2 is missed, the move 2->3 is earned
    assert res["gross"].iloc[1] == 0.0
    assert res["gross"].iloc[2] == pytest.approx(0.5)


def test_weights_drift_and_turnover_and_costs():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    closes = pd.DataFrame({"A": [1.0, 1.0, 2.0, 2.0, 2.0], "B": [1.0] * 5}, index=idx)
    sig = pd.DataFrame(1.0, index=idx, columns=["A", "B"])
    c = 0.01
    res = st.long_only_portfolio(sig, closes, None, period=2, cost_per_side=c, tranches=1)
    # day 1: buy 50/50 from cash, traded 1.0 -> cost 1% of 1.0
    assert res["net"].iloc[1] == pytest.approx(-0.01)
    # day 2: A doubles: value 0.99 * 1.5; weights drift to 2/3, 1/3 (no trade: signal day 1 is off-schedule)
    assert res["gross"].iloc[2] == pytest.approx(0.5)
    # day 3: rebalance from 2/3,1/3 to 1/2,1/2: traded 1/3, cost 1% of that
    assert res["net"].iloc[3] == pytest.approx(-c / 3)
    assert res["mean_traded_per_rebalance"] is not None


def test_strategy_holding_everything_equals_the_benchmark():
    rng = np.random.default_rng(2)
    idx = pd.date_range("2024-01-01", periods=120, freq="D")
    closes = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, 0.03, (120, 9)), axis=0)), index=idx)
    sig = pd.DataFrame(rng.normal(size=(120, 9)), index=idx)
    a = st.long_only_portfolio(sig, closes, 9, period=14, cost_per_side=0.002)
    b = st.long_only_portfolio(sig, closes, None, period=14, cost_per_side=0.002)
    pd.testing.assert_series_equal(a["net"], b["net"])
    summary = st.portfolio_summary(a, b, runs=200)
    assert summary["excess_pct_a_year"] == pytest.approx(0.0, abs=1e-9)


def test_tranches_are_staggered_and_combined_by_capital():
    idx = pd.date_range("2024-01-01", periods=30, freq="D")
    closes = pd.DataFrame({"A": np.linspace(1, 2, 30), "B": np.ones(30)}, index=idx)
    sig = pd.DataFrame({"A": np.where(np.arange(30) % 2, 1.0, -1.0), "B": 0.0}, index=idx)
    res = st.long_only_portfolio(sig, closes, 1, period=3, cost_per_side=0.001, tranches=3)
    # one tranche trades every day after the first three, so costs appear on every day
    assert res["rebalances"] == 29
    assert (res["net"].iloc[4:] < res["gross"].iloc[4:]).all()


# ----------------------------------------------------------------------------- expected-move ranges

def test_expected_move_multipliers_on_a_known_distribution():
    rng = np.random.default_rng(4)
    sigma = 0.02
    idx = pd.date_range("2020-01-01", periods=4000, freq="D")
    closes = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, sigma, (4000, 3)), axis=0)), index=idx)
    atr = pd.DataFrame(sigma * 100, index=idx, columns=closes.columns)
    k = st.fit_expected_move(atr, closes, 7)
    assert k[0.5] == pytest.approx(0.674, abs=0.05) and k[0.8] == pytest.approx(1.2816, abs=0.07)
    cover = st.coverage(atr, closes, 7, k)
    assert cover[0.5] == pytest.approx(0.5, abs=0.01) and cover[0.8] == pytest.approx(0.8, abs=0.01)


# ----------------------------------------------------------------------------- the whole development run

@pytest.fixture
def quick(monkeypatch):
    """Fewer bootstrap draws so the whole-run tests take seconds, not minutes."""
    real = rs.ratio_bootstrap
    monkeypatch.setattr(rs, "ratio_bootstrap", lambda *a, **k: real(*a, **{**k, "runs": 25}))
    monkeypatch.setattr(rs, "PRIMARY_DEV_RUNS", 60)
    real_pf = st.portfolio_summary
    monkeypatch.setattr(st, "portfolio_summary", lambda *a, **k: real_pf(*a, **{**k, "runs": 60}))


def fake_universe(seed=9):
    rng = np.random.default_rng(seed)
    stock_idx = pd.bdate_range("2021-09-01", "2026-10-29")
    coin_idx = pd.date_range("2022-06-01", "2026-10-30", freq="D")
    stocks = ["XOM", "JPM", "KO", "PG", "CVX", "BA", "GE", "IBM", "T", "VZ"]
    coins = ["SOL-USD", "ADA-USD", "XRP-USD", "LTC-USD", "DOT-USD", "BNB-USD", "TRX-USD", "XLM-USD", "ETC-USD",
             "BTC-USD"]
    frames, details = {}, {}
    for t in stocks + coins + ["^GSPC"]:
        idx = coin_idx if t.endswith("-USD") else stock_idx
        vol = 0.04 if t.endswith("-USD") else 0.015
        close = 100 * np.exp(np.cumsum(rng.normal(0, vol, len(idx))))
        frames[t] = pd.DataFrame({"open": close, "high": close * 1.02, "low": close * 0.98, "close": close,
                                  "volume": 1e6}, index=idx)
        if t == "^GSPC":
            continue
        d = pd.DataFrame(index=idx)
        for f in rs.FACTORS:
            d[f] = rng.integers(-4, 5, len(idx)).astype(float)
        d["score"] = 50 + d[list(rs.FACTORS)].sum(axis=1)
        d["x_adx"] = rng.uniform(10, 40, len(idx))
        d["x_atr_pct"] = vol * 100 * np.exp(rng.normal(0, 0.2, len(idx)))
        details[t] = rs.add_families(d)
    return frames, details


def test_development_run_end_to_end_never_touches_the_holdout(quick):
    frames, details = fake_universe()
    # poison every hold-out bar: if anything used them, numbers would be NaN or explode
    for t, f in frames.items():
        f.loc[f.index >= rs.HOLDOUT_START, ["open", "high", "low", "close"]] = np.nan
    for d in details.values():
        d.loc[d.index >= rs.HOLDOUT_START, :] = np.nan
    report = rs.run_experiments(frames, details, rs.HOLDOUT_START)
    assert report["method_version"] == 2
    p = report["primary_dev"]
    assert set(p["A"]) == {"A1", "A2"} and set(p["C"]) == {"C1", "C2"}
    for key in ("A1", "A2"):
        t = p["A"][key]["relative_timing"][rs.PRIMARY_HORIZON]
        assert t["estimate"] is not None and np.isfinite(t["p_value"]) and "p_vs_mme" in t
    assert np.isfinite(p["B"]["spread"][rs.PRIMARY_HORIZON]["estimate"])
    assert "base 0.20%" in p["B"]["long_only"]
    assert np.isfinite(p["C"]["C1"]["forecast_gain"]["trailing 14-day (primary)"]["estimate"])
    text = rs.format_primary(p) + rs.format_report(report, {w: {"window": w, "checked": 1, "max_difference": 0.0}
                                                             for w in rs.PARITY_WINDOWS})
    assert "Method v2" in text and "Long-only" in text and "Expected-move" in text


def test_development_run_ignores_holdout_values(quick):
    """Same universe, wildly different hold-out prices and scores: identical development report."""
    frames, details = fake_universe(seed=10)
    other_f = {t: f.copy() for t, f in frames.items()}
    other_d = {t: d.copy() for t, d in details.items()}
    for f in other_f.values():
        f.loc[f.index >= rs.HOLDOUT_START, ["open", "high", "low", "close"]] *= 5
    for d in other_d.values():
        d.loc[d.index >= rs.HOLDOUT_START, :] = -d.loc[d.index >= rs.HOLDOUT_START, :]
    a = rs.run_experiments(frames, details, rs.HOLDOUT_START)
    b = rs.run_experiments(other_f, other_d, rs.HOLDOUT_START)
    for r in (a, b):
        r.pop("generated_at")
    assert rs.format_primary(a["primary_dev"]) == rs.format_primary(b["primary_dev"])
    assert a["signals"] == b["signals"] and a["histogram"] == b["histogram"]


def reference_cross_sectional_by_date(sig, fwd, classes):
    """The first run's pandas implementation, verbatim, as the reference for the faster version."""
    rows = []
    for klass in sorted(set(classes.values())):
        members = [c for c in sig.columns if classes.get(c) == klass]
        if len(members) < rs.MIN_PANEL:
            continue
        s_all, f_all = sig[members], fwd[members]
        for date in s_all.index:
            s, f = s_all.loc[date], f_all.loc[date]
            keep = s.notna() & f.notna()
            if keep.sum() < rs.MIN_PANEL or s[keep].nunique() < 2:
                continue
            s, f = s[keep], f[keep]
            ic = s.rank().corr(f.rank())
            third = max(1, len(s) // 3)
            order = s.sort_values(kind="mergesort")
            spread = f[order.index[-third:]].mean() - f[order.index[:third]].mean()
            rows.append({"date": date, "class": klass, "ic": ic, "spread": spread})
    return pd.DataFrame(rows)


def test_faster_cross_section_matches_the_first_run_exactly():
    rng = np.random.default_rng(8)
    idx = pd.date_range("2024-01-01", periods=150, freq="D")
    cols = [f"S{i}" for i in range(12)] + [f"C{i}-USD" for i in range(10)]
    sig = pd.DataFrame(rng.integers(-3, 4, (150, 22)).astype(float), index=idx, columns=cols)   # many ties
    fwd = pd.DataFrame(rng.normal(size=(150, 22)), index=idx, columns=cols)
    sig = sig.mask(rng.random(sig.shape) < 0.1)
    fwd = fwd.mask(rng.random(fwd.shape) < 0.1)
    classes = {c: rs.asset_class(c) for c in cols}
    new, ref = rs.cross_sectional_by_date(sig, fwd, classes), reference_cross_sectional_by_date(sig, fwd, classes)
    pd.testing.assert_frame_equal(new.reset_index(drop=True), ref.reset_index(drop=True), check_exact=False,
                                  rtol=1e-12, atol=1e-12)
