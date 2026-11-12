"""Fed, CPI and jobs days on the price chart (lw_chart.event_lines)."""

import pandas as pd

import lw_chart as lw


def _ev(kind, at):
    return {"kind": kind, "at": pd.Timestamp(at, tz="UTC").to_pydatetime()}


def test_a_past_event_sits_on_the_candle_that_holds_it():
    idx = pd.date_range("2026-01-01", periods=60, freq="D", tz="UTC")
    lines, extra = lw.event_lines(idx, "1D", "crypto", [_ev("cpi", "2026-01-14 13:30")])
    assert [(l["index"], l["label"]) for l in lines] == [(13, "CPI")] and extra == 0
    lines, _ = lw.event_lines(pd.date_range("2026-01-01", periods=60, freq="4h", tz="UTC"), "4h", "crypto",
                              [_ev("fomc", "2026-01-02 19:00")])
    assert lines[0]["index"] == 10            # the 16:00 candle


def test_equity_daily_candles_use_new_york_days():
    idx = pd.bdate_range("2026-01-05", periods=20).tz_localize("America/New_York").tz_convert("UTC")
    lines, _ = lw.event_lines(idx, "1D", "equity", [_ev("jobs", "2026-01-09 13:30")])
    assert lines[0]["index"] == 4             # Friday 9 Jan


def test_events_before_the_chart_are_left_out_and_unknown_kinds_ignored():
    idx = pd.date_range("2026-01-01", periods=10, freq="D", tz="UTC")
    lines, _ = lw.event_lines(idx, "1D", "crypto", [_ev("cpi", "2025-06-01"), _ev("ppi", "2026-01-05")])
    assert lines == []


def test_an_upcoming_event_is_drawn_ahead_with_its_date():
    now = pd.Timestamp.now(tz="UTC").normalize()
    idx = pd.date_range(end=now, periods=30, freq="D")
    lines, extra = lw.event_lines(idx, "1D", "crypto", [_ev("cpi", (now + pd.Timedelta(days=5, hours=13)).tz_localize(None))])
    assert lines[0]["index"] == 29 + 5 and lines[0]["label"].startswith("CPI ") and extra >= 5
    far = [_ev("cpi", (now + pd.Timedelta(days=40)).tz_localize(None))]
    assert lw.event_lines(idx, "1D", "crypto", far)[0] == []
