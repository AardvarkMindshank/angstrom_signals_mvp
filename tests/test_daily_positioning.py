import numpy as np
import pandas as pd

import liquidation_levels as ll
import signal_library as sl
import study_history
import what_followed as wf


def _record(funding, ls=None, start="2023-01-01"):
    days = pd.date_range(start, periods=len(funding), freq="D", tz="UTC")
    return {"status": "ok", "markets": ["BTCUSDT_PERP.A"], "updated_at": days[-1].isoformat(),
            "daily": {"t": [int(d.timestamp()) for d in days], "funding": list(funding),
                      "ls": list(ls if ls is not None else [1.0] * len(funding))}}


def _eval(signal_id, record, now, **params):
    ctx = sl.DataContext("crypto", "bitcoin", derivatives_loader=lambda k, a: record, now=now)
    ref = sl.SignalRef.make(sl.REGISTRY.get(signal_id, 1), "1D", **params)
    return sl.evaluate([ref], ctx)[ref.instance_key]


def test_funding_ranks_the_recent_average_and_reads_only_finished_days():
    funding = [0.01] * 300 + [0.05] * 7 + [9.9]            # the last day is still running at `now`
    rec = _record(funding)
    now = pd.Timestamp("2023-01-01", tz="UTC") + pd.Timedelta(days=307, hours=12)
    got = _eval("positioning.funding", rec, now)
    assert got.status == "ok", got.notes
    assert got.value["funding_latest"] == 0.05 and got.value["funding_average"] == 0.05
    assert got.value["average_rank"] >= 90 and got.value["reading"] == "crowded longs"


def test_long_short_reading_and_change():
    ls = list(np.linspace(1.0, 2.0, 200)) + [3.0]
    rec = _record([0.01] * len(ls), ls)
    now = pd.Timestamp("2023-01-01", tz="UTC") + pd.Timedelta(days=len(ls), hours=1)
    got = _eval("positioning.long_short", rec, now, days=7)
    assert got.status == "ok" and got.value["ratio_latest"] == 3.0
    assert got.value["reading"] == "more longs than usual" and round(got.value["ratio_change"], 3) > 1


def test_too_little_history_gives_no_reading():
    got = _eval("positioning.funding", _record([0.01] * 20), pd.Timestamp("2023-01-21 12:00", tz="UTC"))
    assert got.status == "ok" and got.value["average_rank"] is None and got.value["reading"] is None


def test_saved_history_never_shows_a_later_day(tmp_path):
    (tmp_path / "derivatives").mkdir()
    dates = pd.date_range("2021-01-01", periods=100, freq="D")
    pd.DataFrame({"date": dates, "price": 1.0, "oi": None, "oi_lead": None, "ls": 1.2, "funding": range(100),
                  "liq_long": 0, "liq_short": 0, "markets": "BTCUSDT_PERP.A"}).to_csv(
        tmp_path / "derivatives" / "BTC-USD.csv.gz", index=False)
    saved = study_history.SavedHistory(tmp_path)
    rec = saved.derivatives_at("BTC-USD", pd.Timestamp("2021-02-10", tz="UTC"))("crypto", "BTC-USD")
    last = pd.Timestamp(rec["daily"]["t"][-1], unit="s", tz="UTC")
    assert last == pd.Timestamp("2021-02-10", tz="UTC") and rec["daily"]["funding"][-1] == 40.0
    assert "error" in saved.derivatives_at("ETH-USD", "2021-02-10")("crypto", "ETH-USD")
    assert "error" in saved.derivatives_at("BTC-USD", "2021-02-10")("equity", "AAPL")


def test_daily_positioning_can_be_studied_hourly_cannot():
    daily = {"standalone": [{"ref": {"id": "positioning.funding", "version": 1, "timeframe": "1D"}}]}
    assert wf.studyable(daily) == (True, "")
    hourly = {"standalone": [{"ref": {"id": "positioning.oi_price", "version": 1, "timeframe": "1h"}}]}
    assert not wf.studyable(hourly)[0]


def test_live_record_carries_a_daily_series():
    daily = ll.build_daily([{"t": 86400, "c": 0.01}, {"t": 0, "c": 0.02}], [{"t": 86400, "r": 1.5}])
    assert daily == {"t": [0, 86400], "funding": [0.02, 0.01], "ls": [None, 1.5]}
