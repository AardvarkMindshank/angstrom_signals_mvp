"""Every change says exactly what it covers (audit, 23 Nov 2026): calendar weeks and months for shares too."""

import pandas as pd

import market_overview
import signals_view


def _frame(days, freq):
    idx = pd.date_range("2026-09-01", periods=days, freq=freq)
    return pd.DataFrame({"close": [100.0 + i for i in range(days)]}, index=idx)


def test_week_and_month_are_calendar_days_for_shares_and_crypto():
    shares = _frame(60, "B")                                   # weekdays only
    last = shares["close"].iloc[-1]
    week_ago = shares["close"][shares.index <= shares.index[-1] - pd.Timedelta(days=7)].iloc[-1]
    assert signals_view.change_since(shares, 7) == (last / week_ago - 1) * 100
    assert shares.index[-1] - shares.index[shares["close"] == week_ago][0] == pd.Timedelta(days=7)
    assert 20 <= len(signals_view.closes_since(shares, 30)) <= 23   # 30 calendar days of weekdays, not 30 closes
    coins = _frame(60, "D")
    assert len(signals_view.closes_since(coins, 30)) == 31
    assert signals_view.change_since(pd.DataFrame({"close": [1.0, 2.0]}), 7) is None   # no dates: no guess


def test_snapshot_lines_cover_about_30_days():
    item = market_overview.series_item(list(range(1, 60)), "index", market_overview.TRADING_DAY_POINTS)
    assert len(item["spark"]) == 22 and item["change"] == (59 / 58 - 1) * 100
