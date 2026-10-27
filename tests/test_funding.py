import numpy as np
import pandas as pd

import backtest as bt
import funding as fd


def rows(start="2024-01-01", n=30, rate=0.0001):
    base = pd.Timestamp(start, tz="UTC")
    out = []
    for i in range(n):
        out.append({"symbol": "BTCUSDT", "fundingTime": int((base + pd.Timedelta(hours=8 * i)).timestamp() * 1000) + 1, "fundingRate": str(rate)})
    return out


def test_symbol_mapping():
    assert fd.binance_symbol("BTC-USD") == "BTCUSDT"
    assert fd.binance_symbol("xrp-usd") == "XRPUSDT"


def test_parse_records_skips_bad_rows_and_sorts():
    data = rows(n=3)
    data.append({"fundingTime": "x"})
    data.reverse()
    series = fd.parse_records(data)
    assert len(series) == 3 and series.index.is_monotonic_increasing
    assert fd.parse_records([]).empty


def test_daily_funding_sums_per_utc_date_and_needs_two_payments():
    series = fd.parse_records(rows(n=7))  # 3 payments on days 1 and 2, 1 payment on day 3
    daily = fd.daily_funding(series)
    assert list(daily.index) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]
    assert abs(daily.iloc[0] - 0.0003) < 1e-12


def test_fetch_pages_until_the_data_runs_out():
    all_rows = rows(n=2500)
    calls = []

    def getter(url, params):
        calls.append(params["startTime"])
        picked = [r for r in all_rows if r["fundingTime"] >= params["startTime"]]
        return picked[: params["limit"]]

    series = fd.fetch_binance_funding("BTCUSDT", pd.Timestamp("2024-01-01"), getter=getter, pause=0)
    assert len(series) == 2500
    assert len(calls) == 3


def test_features_never_use_the_future():
    rng = np.random.default_rng(1)
    index = pd.date_range("2022-01-01", periods=500)
    daily = pd.Series(rng.normal(0.0003, 0.0002, 500), index=index)
    full = fd.funding_features(daily)
    cut = fd.funding_features(daily.iloc[:300])
    pd.testing.assert_frame_equal(full.iloc[:300], cut, check_exact=False)


def market(n=900, seed=3, strength=0.01, driven=True):
    """Prices where yesterday's funding level really drives the next move (if driven)."""
    rng = np.random.default_rng(seed)
    index = pd.date_range("2020-01-01", periods=n)
    level = pd.Series(np.cumsum(rng.normal(0, 0.00002, n)) + 0.0003, index=index)
    smooth = level.rolling(7).mean()  # the same 7-day average the feature uses
    signal = ((smooth - smooth.mean()) / smooth.std()).fillna(0)
    returns = rng.normal(0, 0.01, n)
    if driven:
        returns[2:] -= strength * signal.values[:-2]  # crowded funding -> weaker price (contrarian)
    close = 100 * np.exp(np.cumsum(returns))
    prices = pd.Series(close, index=index)
    return level, prices


def test_funding_test_finds_a_planted_link_across_coins_and_ignores_none():
    reports_real, reports_none = {}, {}
    for name, seed in (("A", 1), ("B", 2), ("C", 3)):
        level, prices = market(seed=seed, driven=True)
        reports_real[name] = fd.funding_report(fd.funding_features(level), prices, horizons=(1,))
        level, prices = market(seed=seed, driven=False)
        reports_none[name] = fd.funding_report(fd.funding_features(level), prices, horizons=(1,))
    feature = fd.DIRECTION_FEATURES[0]
    real = [reports_real[n]["direction"][feature][1] for n in reports_real]
    none = [reports_none[n]["direction"][feature][1] for n in reports_none]
    assert bt.holds_up(real)
    assert not bt.holds_up(none)
    assert all(item["ic"] < 0 for item in real)  # contrarian sign recovered


def test_report_text_lists_coins_and_marks_holds():
    reports = {}
    for name, seed in (("AAA-USD", 1), ("BBB-USD", 2)):
        level, prices = market(seed=seed)
        reports[name] = fd.funding_report(fd.funding_features(level), prices, horizons=(1,))
    text = fd.format_funding_report(reports, horizons=(1,))
    assert "DIRECTION, next 1 day" in text and "MOVE SIZE, next 1 day" in text
    line = next(l for l in text.splitlines() if l.strip().startswith("Funding level"))
    assert line.rstrip().endswith("YES")


def sized_market(n=1500, seed=4, strength=2.0):
    """Daily funding whose extremeness really sizes the next moves."""
    rng = np.random.default_rng(seed)
    index = pd.date_range("2019-01-01", periods=n)
    level = pd.Series(np.cumsum(rng.normal(0, 0.00003, n)) * 1.0, index=index)  # signed, wanders around 0
    smooth = level.rolling(7).mean()
    size = (smooth.abs() / smooth.abs().std()).fillna(0)
    sigma = 0.01 * (1 + strength * size.values)
    sigma = np.roll(sigma, 2)
    returns = rng.normal(0, 1, n) * sigma
    prices = pd.Series(100 * np.exp(np.cumsum(returns)), index=index)
    return level, prices


def test_summary_finds_extremeness_that_sizes_moves_and_both_halves_agree():
    level, prices = sized_market()
    block = fd.funding_summary(level, prices)
    assert block["days"] > 1000 and 0 <= block["extremeness_percentile"] <= 100
    seven = block["size"]["7"]
    assert seven["ic"] > seven["noise"]
    assert seven["first_half"] > 0 and seven["second_half"] > 0
    text = fd.funding_text(block)
    assert "size, not direction" in text and "both halves" in text


def test_summary_on_noise_says_not_clear():
    rng = np.random.default_rng(9)
    index = pd.date_range("2019-01-01", periods=1500)
    level = pd.Series(np.cumsum(rng.normal(0, 0.00003, 1500)), index=index)
    prices = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 1500))), index=index)
    text = fd.funding_text(fd.funding_summary(level, prices))
    assert "not clear" in text


def test_funding_text_one_sided_and_empty():
    block = {"level_now": 40.0, "extremeness_percentile": 95.0, "since": "2020-01-01", "days": 900,
             "size": {"3": {"ic": 0.2, "noise": 0.1, "first_half": 0.3, "second_half": -0.1},
                      "7": {"ic": 0.2, "noise": 0.1, "first_half": 0.3, "second_half": -0.1}}}
    assert "one half" in fd.funding_text(block)
    assert fd.funding_text(None) is None
    assert fd.funding_text({}) is None


def test_too_little_funding_returns_none():
    index = pd.date_range("2024-01-01", periods=100)
    daily = pd.Series(0.0003, index=index)
    assert fd.funding_summary(daily, pd.Series(100.0, index=index)) is None
