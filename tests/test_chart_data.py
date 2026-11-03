import numpy as np
import pandas as pd
import pytest

import chart_data as cd

NY = "America/New_York"
US_SESSION = (NY, 9 * 60 + 30, 16 * 60)


def _bars(index, start_price=100.0):
    n = len(index)
    close = start_price + np.arange(n, dtype=float)
    return pd.DataFrame(
        {"open": close - 0.5, "high": close + 1, "low": close - 1, "close": close, "volume": np.ones(n) * 10},
        index=index,
    )


def _us_hourly(days):
    """Yahoo-style US 60-minute bars: 09:30, 10:30 ... 15:30 New York."""
    stamps = []
    for day in days:
        for hour in range(7):
            stamps.append(pd.Timestamp(f"{day} 09:30", tz=NY) + pd.Timedelta(hours=hour))
    return _bars(pd.DatetimeIndex(stamps))


# ---------------------------------------------------------------- availability

def test_matrix_marks_impossible_pairs():
    assert cd.availability("15m", "1M")[0]
    assert not cd.availability("15m", "3M")[0]
    assert not cd.availability("15m", "All")[0]
    assert cd.availability("1h", "1Y")[0]
    assert not cd.availability("1h", "All")[0]
    assert cd.availability("4h", "1Y")[0]
    assert not cd.availability("4h", "All")[0]
    assert cd.availability("1D", "All")[0]
    assert cd.availability("1W", "All")[0]
    assert not cd.availability("1W", "7D")[0]
    assert not cd.availability("1W", "1M")[0]


def test_unavailable_pairs_say_why_in_plain_words():
    ok, reason = cd.availability("15m", "1Y")
    assert not ok and "60 days" in reason and "15 minutes" in reason


def test_every_interval_has_some_usable_range():
    for interval in cd.INTERVALS:
        assert any(cd.availability(interval, r)[0] for r in cd.RANGES)


def test_nearest_range_suggests_but_keeps_usable_choice():
    assert cd.nearest_range("1D", "1Y") == "1Y"
    assert cd.nearest_range("15m", "1Y") == "1M"
    assert cd.nearest_range("1W", "7D") == "3M"


# ---------------------------------------------------------------- crypto 4h

def test_crypto_4h_uses_fixed_utc_blocks():
    index = pd.date_range("2026-10-01 00:00", periods=48, freq="1h", tz="UTC")
    out = cd.group_utc(_bars(index), 240)
    assert len(out) == 12
    assert list(out.index.hour[:6]) == [0, 4, 8, 12, 16, 20]
    first = out.iloc[0]
    assert first["open"] == 99.5 and first["close"] == 103.0
    assert first["high"] == 104.0 and first["low"] == 99.0
    assert first["volume"] == 40


def test_crypto_blocks_ignore_local_timezone_of_input():
    index = pd.date_range("2026-10-01 07:00", periods=8, freq="1h", tz="Asia/Bangkok")  # 00:00 UTC
    out = cd.group_utc(_bars(index), 240)
    assert [ts.hour for ts in out.index] == [0, 4]


def test_stray_live_row_joins_its_block():
    index = pd.DatetimeIndex(list(pd.date_range("2026-10-01 00:00", periods=3, freq="1h", tz="UTC"))
                             + [pd.Timestamp("2026-10-01 02:37:12", tz="UTC")])
    out = cd.group_utc(_bars(index), 60)
    assert len(out) == 3
    assert out.iloc[-1]["close"] == 103.0


# ---------------------------------------------------------------- equity sessions

def test_us_4h_matches_tradingview_session_blocks():
    out = cd.group_session(_us_hourly(["2026-10-05", "2026-10-06"]), 240, US_SESSION)
    local = [ts.strftime("%m-%d %H:%M") for ts in out.index]
    assert local == ["10-05 09:30", "10-05 13:30", "10-06 09:30", "10-06 13:30"]
    first, second = out.iloc[0], out.iloc[1]
    assert first["volume"] == 40 and second["volume"] == 30
    assert first["open"] == 99.5 and first["close"] == 103.0


def test_us_4h_never_spans_overnight_gap():
    out = cd.group_session(_us_hourly(["2026-10-05", "2026-10-06"]), 240, US_SESSION)
    assert out.iloc[1]["close"] == 106.0  # last bar of Monday
    assert out.iloc[2]["open"] == 106.5  # first bar of Tuesday


def test_dst_change_keeps_new_york_clock():
    # US clocks go back on 2026-11-01; 09:30 New York is 13:30 UTC before and 14:30 UTC after.
    out = cd.group_session(_us_hourly(["2026-10-30", "2026-11-02"]), 240, US_SESSION)
    utc_hours = [ts.tz_convert("UTC").hour for ts in out.index]
    assert utc_hours == [13, 17, 14, 18]
    assert all(ts.strftime("%H:%M") in ("09:30", "13:30") for ts in out.index)


def test_holiday_leaves_no_candle():
    # 2026-11-26 is Thanksgiving: Yahoo sends no bars, so no candles appear for it.
    out = cd.group_session(_us_hourly(["2026-11-25", "2026-11-27"]), 240, US_SESSION)
    assert sorted({ts.strftime("%m-%d") for ts in out.index}) == ["11-25", "11-27"]


def test_early_close_day_gives_short_afternoon_candle():
    stamps = [pd.Timestamp("2026-11-27 09:30", tz=NY) + pd.Timedelta(hours=h) for h in range(4)]
    stamps.append(pd.Timestamp("2026-11-27 13:30", tz=NY))  # market shuts at 13:00; Yahoo may still send a stub
    out = cd.group_session(_bars(pd.DatetimeIndex(stamps)), 240, US_SESSION)
    assert [ts.strftime("%H:%M") for ts in out.index] == ["09:30", "13:30"]


def test_bars_outside_regular_hours_are_dropped():
    stamps = [pd.Timestamp("2026-10-05 08:30", tz=NY), pd.Timestamp("2026-10-05 09:30", tz=NY),
              pd.Timestamp("2026-10-05 16:30", tz=NY)]
    out = cd.group_session(_bars(pd.DatetimeIndex(stamps)), 60, US_SESSION)
    assert [ts.strftime("%H:%M") for ts in out.index] == ["09:30"]


def test_session_guessed_from_bars_when_yahoo_sends_none():
    session = cd.session_from_bars(_us_hourly(["2026-10-05", "2026-10-06", "2026-10-07"]), 60)
    assert session == (NY, 570, 960)


def test_session_read_from_yahoo_metadata():
    open_utc = int(pd.Timestamp("2026-11-03 09:30", tz=NY).timestamp())
    close_utc = int(pd.Timestamp("2026-11-03 16:00", tz=NY).timestamp())
    meta = {"exchangeTimezoneName": NY,
            "currentTradingPeriod": {"regular": {"start": open_utc, "end": close_utc, "timezone": "EST"}}}
    zone, open_minute, close_minute = cd.session_from_metadata(meta)
    assert (open_minute, close_minute) == (570, 960)


def test_non_us_exchange_uses_its_own_open():
    tokyo = ("Asia/Tokyo", 9 * 60, 15 * 60 + 30)
    stamps = [pd.Timestamp("2026-10-05 09:00", tz="Asia/Tokyo") + pd.Timedelta(hours=h) for h in range(7)]
    out = cd.group_session(_bars(pd.DatetimeIndex(stamps)), 240, tokyo)
    assert [ts.strftime("%H:%M") for ts in out.index] == ["09:00", "13:00"]


# ---------------------------------------------------------------- daily and weekly

def test_weekly_groups_monday_to_sunday_and_labels_monday():
    index = pd.date_range("2026-10-05", periods=14, freq="1D", tz="UTC")  # Monday onwards
    out = cd.group_weekly(_bars(index))
    assert [ts.strftime("%Y-%m-%d") for ts in out.index] == ["2026-10-05", "2026-10-12"]
    assert out.iloc[0]["open"] == 99.5 and out.iloc[0]["close"] == 106.0
    assert out.iloc[0]["volume"] == 70


def test_weekly_equity_with_holiday_has_four_days():
    days = ["2026-11-23", "2026-11-24", "2026-11-25", "2026-11-27"]
    index = pd.DatetimeIndex([pd.Timestamp(d, tz=NY) for d in days])
    out = cd.group_weekly(_bars(index))
    assert len(out) == 1 and out.iloc[0]["volume"] == 40
    assert out.index[0].strftime("%Y-%m-%d") == "2026-11-23"


def test_daily_keeps_exchange_date_not_utc_date():
    index = pd.DatetimeIndex([pd.Timestamp("2026-10-05", tz=NY), pd.Timestamp("2026-10-06", tz=NY)])
    out = cd.group_daily(_bars(index))
    assert [ts.strftime("%Y-%m-%d") for ts in out.index] == ["2026-10-05", "2026-10-06"]


def test_intraday_is_never_built_from_daily():
    daily = _bars(pd.date_range("2026-01-01", periods=300, freq="1D", tz="UTC"))
    calls = []

    def fetch(symbol, interval, start, period):
        calls.append(interval)
        return (daily if interval == "1d" else cd._empty()), {}

    cd.CACHE.clear()
    out = cd.load_candles("crypto", "bitcoin", "1h", "1M", now=pd.Timestamp("2026-10-27", tz="UTC"), fetch=fetch)
    assert calls == ["60m"]
    assert out["error"] and out["candles"].empty


# ---------------------------------------------------------------- forming candle

def test_forming_candle_crypto_4h():
    index = pd.date_range("2026-10-01 00:00", periods=3, freq="4h", tz="UTC")
    df = _bars(index)
    during = cd.mark_forming(df, "4h", "crypto", now=pd.Timestamp("2026-10-01 09:00", tz="UTC"))
    after = cd.mark_forming(df, "4h", "crypto", now=pd.Timestamp("2026-10-01 12:00", tz="UTC"))
    assert list(during["forming"]) == [False, False, True]
    assert not after["forming"].any()


def test_forming_equity_afternoon_block_ends_at_close():
    df = cd.group_session(_us_hourly(["2026-10-05"]), 240, US_SESSION)
    at_1559 = cd.mark_forming(df, "4h", "equity", now=pd.Timestamp("2026-10-05 15:59", tz=NY), session=US_SESSION)
    at_1601 = cd.mark_forming(df, "4h", "equity", now=pd.Timestamp("2026-10-05 16:01", tz=NY), session=US_SESSION)
    assert at_1559["forming"].iloc[-1]
    assert not at_1601["forming"].iloc[-1]


def test_forming_equity_daily_until_close():
    df = cd.group_daily(_bars(pd.DatetimeIndex([pd.Timestamp("2026-10-05", tz=NY)])))
    open_day = cd.mark_forming(df, "1D", "equity", now=pd.Timestamp("2026-10-05 12:00", tz=NY), session=US_SESSION)
    closed = cd.mark_forming(df, "1D", "equity", now=pd.Timestamp("2026-10-05 16:05", tz=NY), session=US_SESSION)
    assert open_day["forming"].iloc[-1] and not closed["forming"].iloc[-1]


def test_confirmed_drops_only_the_forming_candle():
    index = pd.date_range("2026-10-01", periods=5, freq="1D", tz="UTC")
    df = cd.mark_forming(_bars(index), "1D", "crypto", now=pd.Timestamp("2026-10-05 10:00", tz="UTC"))
    assert len(cd.confirmed(df)) == 4


# ---------------------------------------------------------------- loading

def _hourly_crypto(days=40, end="2026-10-27 10:00"):
    index = pd.date_range(end=end, periods=days * 24, freq="1h", tz="UTC")
    return _bars(index)


def test_load_crypto_4h_keeps_warmup_and_marks_range_start():
    cd.CACHE.clear()
    now = pd.Timestamp("2026-10-27 10:30", tz="UTC")
    out = cd.load_candles("crypto", "bitcoin", "4h", "7D", now=now,
                          fetch=lambda *a: (_hourly_crypto(), {}))
    assert out["error"] is None
    candles = out["candles"]
    assert out["start"] >= now - pd.Timedelta(days=7)
    assert candles.index[0] < out["start"]  # warm-up candles before the range
    assert candles["forming"].iloc[-1] and candles["forming"].sum() == 1
    assert "UTC" in out["source"]


def test_load_too_few_candles_is_reported():
    cd.CACHE.clear()
    short = _hourly_crypto(days=1)
    out = cd.load_candles("crypto", "bitcoin", "4h", "7D", now=pd.Timestamp("2026-10-27 10:30", tz="UTC"),
                          fetch=lambda *a: (short.iloc[-8:], {}))
    assert out["error"] and "Only" in out["error"]


def test_load_unavailable_pair_does_not_fetch():
    called = []
    out = cd.load_candles("crypto", "bitcoin", "15m", "1Y", fetch=lambda *a: called.append(1))
    assert out["error"] and not called


def test_load_failed_fetch_is_a_plain_error():
    cd.CACHE.clear()

    def boom(*a):
        raise RuntimeError("rate limited")

    out = cd.load_candles("equity", "AAPL", "1h", "1M", fetch=boom)
    assert "rate limited" in out["error"]


def test_cache_shares_one_fetch():
    cd.CACHE.clear()
    calls = []

    def fetch(*a):
        calls.append(a)
        return _hourly_crypto(), {}

    now = pd.Timestamp("2026-10-27 10:30", tz="UTC")
    cd.load_candles("crypto", "bitcoin", "1h", "7D", now=now, fetch=fetch)
    cd.load_candles("crypto", "bitcoin", "4h", "7D", now=now, fetch=fetch)
    assert len(calls) == 1


def test_unknown_coin_on_yahoo_says_so():
    out = cd.load_candles("crypto", "some-coin-yahoo-lacks", "1h", "7D", fetch=lambda *a: None)
    assert out["error"]


def test_fetch_window_respects_yahoo_limits():
    today = pd.Timestamp("2026-11-03").date()
    start, _ = cd.fetch_window("15m", "1M", "crypto", today=today)
    assert (today - pd.Timestamp(start).date()).days <= 59
    start, _ = cd.fetch_window("1h", "1Y", "equity", today=today)
    assert (today - pd.Timestamp(start).date()).days <= 729
    assert cd.fetch_window("1D", "All", "equity") == (None, "max")


def test_display_seconds_show_exchange_clock_for_shares():
    index = pd.DatetimeIndex([pd.Timestamp("2026-10-05 09:30", tz=NY)])
    secs = cd.display_seconds(index, "1h", "equity", US_SESSION)
    assert pd.Timestamp(secs[0], unit="s").strftime("%H:%M") == "09:30"
    crypto = cd.display_seconds(pd.DatetimeIndex([pd.Timestamp("2026-10-05 04:00", tz="UTC")]), "4h", "crypto")
    assert pd.Timestamp(crypto[0], unit="s").strftime("%H:%M") == "04:00"
