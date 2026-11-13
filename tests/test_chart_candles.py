"""Monthly candles for the chart (chart_candles.py), kept out of the certified chart_data.py."""

import pandas as pd

import chart_candles as cc
import chart_data


def _daily(start="2023-01-01", end="2025-04-15"):
    days = pd.date_range(start, end, freq="1D", tz="UTC")
    n = len(days)
    return pd.DataFrame({"open": [float(i) for i in range(n)], "high": [i + 2.0 for i in range(n)],
                         "low": [float(i) for i in range(n)], "close": [i + 1.0 for i in range(n)],
                         "volume": [1.0] * n}, index=days)


def test_intervals_and_ranges():
    assert cc.INTERVALS[:-1] == chart_data.INTERVALS and cc.INTERVALS[-1] == "1Mo"
    assert cc.availability("1Mo", "1Y")[0] and cc.availability("1Mo", "All")[0]
    for short in ("7D", "1M", "3M"):
        assert not cc.availability("1Mo", short)[0]
    assert cc.nearest_range("1Mo", "3M") == "1Y"
    assert cc.availability("1D", "7D") == chart_data.availability("1D", "7D")


def test_months_group_and_last_one_forms():
    m = cc.group_monthly(_daily("2025-01-01"))
    assert [d.day for d in m.index] == [1, 1, 1, 1] and m["volume"].tolist() == [31.0, 28.0, 31.0, 15.0]
    assert m["open"].iloc[1] == 31 and m["close"].iloc[1] == 59 and m["high"].iloc[1] == 60
    f = cc.mark_forming(m, now=pd.Timestamp("2025-04-20", tz="UTC"))
    assert f["forming"].tolist() == [False, False, False, True]
    assert not cc.mark_forming(m, now=pd.Timestamp("2025-05-01", tz="UTC"))["forming"].iloc[-1]


def test_range_cut_keeps_history_for_indicators():
    candles, start, error = cc.from_daily(_daily(), "1Y", now=pd.Timestamp("2025-04-20", tz="UTC"))
    assert error == "" and start == pd.Timestamp("2024-05-01", tz="UTC")
    assert candles.index[0] == pd.Timestamp("2023-01-01", tz="UTC")


def test_monthly_loads_through_daily_candles():
    def fetch(symbol, yahoo_interval, start, period):
        assert yahoo_interval == "1d"
        return _daily("2015-01-01", "2025-04-15"), {}

    out = cc.load_candles("equity", "AAPL", "1Mo", "1Y", now=pd.Timestamp("2025-04-20", tz="UTC"), fetch=fetch)
    assert out["error"] is None and out["session"] is None
    assert "calendar months" in out["source"]
    assert out["candles"]["forming"].iloc[-1]
    assert cc.load_candles("equity", "AAPL", "1Mo", "3M", fetch=fetch)["error"]
