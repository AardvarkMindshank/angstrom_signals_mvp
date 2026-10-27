import math

import numpy as np
import pandas as pd

import backtest as bt


def frame(n=400, seed=0, drift=0.0003):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.015, n)))
    index = pd.date_range("2022-01-01", periods=n)
    return pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": 1.0},
        index=index,
    )


def test_forward_returns_use_the_lagged_entry():
    closes = pd.Series([100.0, 110.0, 121.0, 133.1])
    fwd = bt.forward_returns(closes, horizon=1, lag=1)
    # signal at t=0 enters at 110 and exits at 121
    assert math.isclose(fwd.iloc[0], 10.0)
    assert math.isnan(fwd.iloc[-1]) and math.isnan(fwd.iloc[-2])


def test_effective_n_and_noise_floor():
    assert bt.effective_n(30, 7) == 30 / 7
    assert bt.noise_floor(0) is None
    assert math.isclose(bt.noise_floor(100), 0.196)


def test_rank_correlation_perfect_and_degenerate():
    assert math.isclose(bt.rank_correlation([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
    assert math.isclose(bt.rank_correlation([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
    assert bt.rank_correlation([1, 1, 1, 1], [1, 2, 3, 4]) is None
    assert bt.rank_correlation([1, 2], [1, 2]) is None


def test_bucket_stats_counts_and_excess():
    scores = pd.Series([80, 80, 50, 20, 20, 50], dtype=float)
    fwd = pd.Series([2.0, 4.0, 0.0, -3.0, -1.0, 0.0])
    out = bt.bucket_stats(scores, fwd, bull=70, bear=30, horizon=1)
    assert out["n"] == 6
    assert out["high"]["n"] == 2 and math.isclose(out["high"]["mean_pct"], 3.0)
    assert out["low"]["n"] == 2 and math.isclose(out["low"]["mean_pct"], -2.0)
    assert out["middle"]["n"] == 2
    assert math.isclose(out["base_mean_pct"], 0.3333333333)
    assert out["high"]["up_rate"] == 1.0


def test_bucket_stats_ignores_missing_values():
    scores = pd.Series([80.0, float("nan"), 20.0])
    fwd = pd.Series([1.0, 5.0, float("nan")])
    out = bt.bucket_stats(scores, fwd, 70, 30, 1)
    assert out["n"] == 1 and out["low"]["n"] == 0


def test_score_series_never_sees_the_future():
    data = frame(260)
    seen = []

    def fn(window):
        seen.append((len(window), window.index[-1]))
        return 50.0

    scores = bt.score_series(data, score_fn=fn, warmup=200)
    assert len(scores) == 60
    for length, last in seen:
        assert data.index[length - 1] == last  # window ends on the day it scores


def test_peeking_signal_gains_nothing_because_of_the_lag():
    data = frame(500, seed=3)
    closes = data["close"]
    position = {d: i for i, d in enumerate(data.index)}

    def peek(window):
        i = position[window.index[-1]]
        if i + 1 >= len(closes):
            return 50.0
        return 100.0 if closes.iloc[i + 1] > closes.iloc[i] else 0.0

    report = bt.run_backtest(data, horizons=(1,), score_fn=peek)
    ic = report["horizons"][1]["rank_correlation"]
    assert abs(ic["ic"]) < 3 * ic["noise_floor"]


def test_strategy_hysteresis_and_costs():
    index = pd.date_range("2023-01-01", periods=8)
    closes = pd.Series([100, 100, 100, 110, 121, 121, 121, 121], index=index, dtype=float)
    scores = pd.Series([50, 75, 75, 75, 40, 40, 40, 40], index=index, dtype=float)
    free = bt.run_strategy(closes, scores, enter=70, exit_below=50, cost_bps=0)
    # enters at close of day 2 (signal day 1 + lag), earns day 3 and 4 moves
    assert math.isclose(free["strategy_return_pct"], (1.1 * 1.1 - 1) * 100, rel_tol=1e-9)
    assert free["position_changes"] == 2
    costly = bt.run_strategy(closes, scores, enter=70, exit_below=50, cost_bps=100)
    assert costly["strategy_return_pct"] < free["strategy_return_pct"]


def test_strategy_stays_flat_without_signal():
    data = frame(300)
    scores = pd.Series(50.0, index=data.index)
    out = bt.run_strategy(data["close"], scores, enter=70)
    assert out["strategy_return_pct"] == 0.0
    assert out["exposure_pct"] == 0.0


def test_run_backtest_report_shape_and_text():
    data = frame(320)
    report = bt.run_backtest(data, horizons=(1, 5), score_fn=lambda w: 50 + 40 * math.sin(len(w) / 7))
    assert set(report["horizons"]) == {1, 5}
    assert report["scored_days"] == 120
    text = bt.format_report(report, "test")
    assert "Next 5 days" in text and "Hold while the score says so" in text


def test_csv_loader(tmp_path):
    data = frame(50)
    path = tmp_path / "p.csv"
    data.rename_axis("Date").reset_index().to_csv(path, index=False)
    loaded = bt.load_prices(csv_path=str(path))
    assert list(loaded.columns) == ["open", "high", "low", "close", "volume"]
    assert len(loaded) == 50


# ------------------------------------------------------------------ factor test


def planted(n=700, seed=5, strength=0.01):
    """Prices where a known factor really does lead the return that follows the trade lag."""
    rng = np.random.default_rng(seed)
    signal = rng.normal(0, 1, n)
    noise = rng.normal(0, 0.01, n)
    returns = noise.copy()
    returns[2:] += strength * signal[:-2]  # signal at t drives the move from t+1 to t+2
    close = 100 * np.exp(np.cumsum(returns))
    index = pd.date_range("2020-01-01", periods=n)
    data = pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close, "volume": 1.0}, index=index
    )
    lookup = dict(zip(index, signal))
    junk = dict(zip(index, rng.normal(0, 1, n)))

    def detail(window):
        day = window.index[-1]
        return {
            "score": 50 + 10 * lookup[day],
            "contributions": {"RSI": lookup[day], "Stochastic": junk[day]},
        }

    return data, detail


def test_factor_report_finds_a_planted_signal_and_not_junk():
    data, detail = planted()
    details = bt.score_details(data, detail_fn=detail, warmup=50)
    report = bt.factor_report(details, data["close"], horizons=(1,))
    real = report["rows"]["RSI"][1]
    junk = report["rows"]["Stochastic"][1]
    assert real["ic"] > 3 * real["noise_floor"]
    assert abs(junk["ic"]) < 3 * junk["noise_floor"]
    assert report["rows"]["TOTAL SCORE"][1]["ic"] > 3 * real["noise_floor"]


def test_holds_up_needs_same_direction_and_size_on_every_asset():
    good = {"ic": 0.2, "noise_floor": 0.1}
    weak = {"ic": 0.05, "noise_floor": 0.1}
    flipped = {"ic": -0.2, "noise_floor": 0.1}
    assert bt.holds_up([good, good])
    assert not bt.holds_up([good, weak])
    assert not bt.holds_up([good, flipped])
    assert not bt.holds_up([])
    assert not bt.holds_up([{"ic": None, "noise_floor": 0.1}])


def test_factor_table_marks_only_the_real_factor():
    reports = {}
    for name, seed in (("A", 1), ("B", 2)):
        data, detail = planted(seed=seed)
        details = bt.score_details(data, detail_fn=detail, warmup=50)
        reports[name] = bt.factor_report(details, data["close"], horizons=(1,))
    text = bt.format_factor_report(reports, horizons=(1,))
    rsi_line = next(line for line in text.splitlines() if line.strip().startswith("RSI"))
    stoch_line = next(line for line in text.splitlines() if line.strip().startswith("Stochastic"))
    assert rsi_line.rstrip().endswith("YES")
    assert not stoch_line.rstrip().endswith("YES")


def test_score_details_never_sees_the_future():
    data, _ = planted(300)
    lengths = []

    def detail(window):
        lengths.append(len(window))
        return {"score": 50.0, "contributions": {}}

    bt.score_details(data, detail_fn=detail, warmup=100)
    assert lengths == list(range(101, 301))


# ------------------------------------------------------------------- volatility


def volatile(n=1500, seed=11, strength=1.5):
    """Move sizes that depend on a known factor |x| AND on slowly changing volatility."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, n)
    log_vol = np.zeros(n)
    for i in range(1, n):
        log_vol[i] = 0.98 * log_vol[i - 1] + 0.12 * rng.normal()
    sigma = 0.01 * np.exp(log_vol)
    sigma[2:] *= 1 + strength * np.abs(x[:-2])  # |x| at t sizes the move on day t+2
    returns = rng.normal(0, 1, n) * sigma
    close = 100 * np.exp(np.cumsum(returns))
    index = pd.date_range("2018-01-01", periods=n)
    data = pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close, "volume": 1.0}, index=index
    )
    lookup = dict(zip(index, x))
    junk = dict(zip(index, rng.normal(0, 1, n)))
    closes = data["close"]
    trailing = bt.trailing_activity(closes)

    def detail(window):
        day = window.index[-1]
        return {
            "score": 50 + 10 * lookup[day],
            "contributions": {"RSI": lookup[day], "Stochastic": junk[day]},
            "atr_pct": float(trailing.loc[day]) if trailing.loc[day] == trailing.loc[day] else float("nan"),
        }

    return data, detail


def test_forward_activity_matches_the_trade_window():
    closes = pd.Series([100.0, 100.0, 110.0, 110.0, 110.0, 121.0])
    act = bt.forward_activity(closes, horizon=1, lag=1)
    assert math.isclose(act.iloc[0], 10.0)  # signal day 0, trade at 1, moves on day 2 = +10%
    assert math.isclose(act.iloc[2], 0.0)
    assert math.isnan(act.iloc[-1])


def test_partial_rank_correlation_removes_the_control():
    rng = np.random.default_rng(0)
    z = rng.normal(size=600)
    x = z + rng.normal(scale=0.3, size=600)  # x is mostly z
    y = z + rng.normal(scale=0.3, size=600)  # y is mostly z
    assert bt.rank_correlation(x, y) > 0.7
    assert abs(bt.partial_rank_correlation(x, y, z)) < 0.15
    own = rng.normal(size=600)
    y2 = z + 0.8 * own
    assert bt.partial_rank_correlation(own, y2, z) > 0.4
    assert bt.partial_rank_correlation(z, y, z) is None  # x is the control


def test_volatility_test_finds_a_planted_driver_and_ignores_the_mirror():
    data, detail = volatile()
    details = bt.score_details(data, detail_fn=detail, warmup=50)
    report = bt.volatility_report(details, data["close"], horizons=(1,))
    real = report["rows"]["RSI strength"][1]
    junk = report["rows"]["Stochastic strength"][1]
    assert real["partial"] > 3 * real["noise_floor"]
    assert abs(junk["partial"]) < 3 * junk["noise_floor"]
    mirror = report["rows"]["ATR %"][1]["partial"]
    assert mirror is None or abs(mirror) < 3 * real["noise_floor"]
    persistence = report["rows"]["REFERENCE: trailing volatility"][1]["raw"]
    assert persistence > 0.15  # volatility really is sticky in this data


def test_volatility_table_marks_only_the_real_driver():
    reports = {}
    for name, seed in (("A", 1), ("B", 2)):
        data, detail = volatile(seed=seed)
        details = bt.score_details(data, detail_fn=detail, warmup=50)
        reports[name] = bt.volatility_report(details, data["close"], horizons=(1,))
    text = bt.format_volatility_report(reports, horizons=(1,))
    rsi = next(line for line in text.splitlines() if line.strip().startswith("RSI strength"))
    stoch = next(line for line in text.splitlines() if line.strip().startswith("Stochastic strength"))
    assert rsi.rstrip().endswith("YES")
    assert not stoch.rstrip().endswith("YES")
