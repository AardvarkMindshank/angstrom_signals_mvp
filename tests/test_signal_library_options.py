"""The max pain signal (signal_library/signals_options.py) and its snapshots (options_snapshots.py)."""

from datetime import datetime, timezone

import pandas as pd

import options_snapshots as osn
from signal_library import certify as cf
from signal_library import replay as rp
from signal_library.context import DataContext
from signal_library.core import REGISTRY, SignalRef
from signal_library.engine import evaluate


def _rows(key="Stock|AAPL", taken="2026-11-16T15:00:00+00:00", spot=210.0, seen=None):
    out = []
    for expiry, pain in (("2026-11-18", 205.0), ("2026-11-20", 200.0), ("2026-12-18", 190.0)):
        out.append({"asset_key": key, "recorded_at": taken, "expiry": expiry, "spot": spot, "max_pain": pain,
                    "call_oi": 1000.0, "put_oi": 800.0, "source": "yahoo", "first_seen_at": seen or taken})
    return out


def _run(kind, asset, rows, now, **params):
    ref = SignalRef.make(REGISTRY.get("options.max_pain"), "1D", **params)
    ctx = DataContext(kind, asset, now=now, options_loader=lambda key: {"rows": rows} if rows else {"error": "none"})
    return evaluate([ref], ctx)[ref.instance_key]


def test_nearest_expiry_distance_side_and_days():
    got = _run("equity", "aapl", _rows(), pd.Timestamp("2026-11-17T12:00Z"))
    assert got.status == "ok"
    v = got.value
    assert v["max_pain"] == 205.0 and v["expiry"] == "18 Nov 2026"
    assert v["distance_pct"] == round((210 - 205) / 205 * 100, 4) and v["side"] == "above"
    assert v["expiry_week"] and 1.3 < v["days_to_expiry"] < 1.4      # settles 16:00 New York = 21:00 UTC
    assert v["put_call_ratio"] == 0.8 and v["subject_key"] == "Stock|AAPL"


def test_min_days_monthly_and_near():
    now = pd.Timestamp("2026-11-17T12:00Z")
    assert _run("equity", "AAPL", _rows(), now, min_days=2).value["expiry"] == "20 Nov 2026"
    monthly = _run("equity", "AAPL", _rows(), now, monthly=True).value
    assert monthly["expiry"] == "20 Nov 2026" and monthly["monthly_expiry"]          # third Friday
    assert _run("equity", "AAPL", _rows(), now, min_days=40).status == "missing_data"
    assert _run("equity", "AAPL", _rows(), now, near_pct=3.0).value["side"] == "at"   # 2.44% away


def test_unsupported_coins_missing_and_stale():
    now = pd.Timestamp("2026-11-17T12:00Z")
    assert _run("crypto", "solana", _rows("Crypto|solana"), now).status == "unsupported"
    assert _run("crypto", "bitcoin", [], now).status == "missing_data"
    btc = _rows("Crypto|bitcoin", taken="2026-11-16T20:00:00+00:00")
    got = _run("crypto", "bitcoin", btc, now)
    assert got.status == "stale" and "16 hours" in got.notes[0]       # crypto stale after 12 hours
    early = _run("equity", "AAPL", _rows(), pd.Timestamp("2026-11-16T14:00Z"))
    assert early.status == "missing_data"                               # snapshot taken after the evaluation time


def test_newest_snapshot_wins_and_replay_counts_receipt_time():
    old = _rows(taken="2026-11-16T15:00:00+00:00", spot=210.0)
    new = _rows(taken="2026-11-17T15:00:00+00:00", spot=180.0, seen="2026-11-17T18:00:00+00:00")
    now = pd.Timestamp("2026-11-17T16:00Z")
    assert _run("equity", "AAPL", old + new, now).value["price"] == 180.0             # live: taken by now
    run = rp.ReplayRun(rp.DISPLAY, lambda *a: {"error": "none"}, options=lambda key, as_of: {"rows": old + new},
                       check_certification=False)
    ref = SignalRef.make(REGISTRY.get("options.max_pain"), "1D")
    got = evaluate([ref], run.context("equity", "AAPL", now))[ref.instance_key]
    assert got.value["price"] == 210.0                                  # replay: the new one arrived at 18:00
    assert not rp.future_timestamps(got, now)


def test_suite_certifies_max_pain_with_late_data_poisoning():
    signals = cf.run_suite(cf.synthetic_options(days=60), indicators="tests.replay_helpers:simple_indicators",
                           cutoffs=10, timeframes=("1D",), log=lambda *a: None, only={"options.max_pain"})
    entry = signals["options.max_pain@1"]["1D"]
    assert entry["algorithm"] == "certified", entry["reason"]
    assert entry["checks"]["poison"] >= 20


def test_snapshot_rows_and_schedule():
    book = {"2026-11-20": {"calls": {100.0: 5.0, 110.0: 1.0}, "puts": {90.0: 2.0, 100.0: 4.0}, "spot": 104.0},
            "2026-11-27": {"calls": {}, "puts": {}}}
    rows = osn.snapshot_rows("Crypto|bitcoin", "2026-11-17T12:00:00+00:00", book, "deribit")
    assert len(rows) == 1 and rows[0]["max_pain"] == 100.0 and rows[0]["spot"] == 104.0
    assert rows[0]["call_oi"] == 6.0 and rows[0]["put_oi"] == 6.0 and rows[0]["strikes"] == 3
    tue = datetime(2026, 11, 17, 15, 0, tzinfo=timezone.utc)
    assert osn.equity_due(None, tue) and not osn.equity_due(tue.replace(hour=14, minute=31), tue)
    assert not osn.equity_due(None, tue.replace(hour=13))
    assert not osn.equity_due(None, datetime(2026, 11, 21, 15, tzinfo=timezone.utc))          # Saturday
    assert osn.crypto_due(tue.replace(hour=11), tue) and not osn.crypto_due(tue.replace(hour=13), tue)
    dates = ["2026-11-18", "2026-11-20", "2026-11-25", "2026-11-27", "2026-12-04", "2026-12-11", "2026-12-18"]
    assert osn.pick_equity_expiries(dates, tue) == dates[:5]            # the Nov 20 monthly is already among them
    many = ["2026-11-23", "2026-11-24", "2026-11-25", "2026-11-27", "2026-12-01", "2026-12-04", "2026-12-18"]
    assert osn.pick_equity_expiries(many, datetime(2026, 11, 21, tzinfo=timezone.utc)) == many[:5] + ["2026-12-18"]


class _Table:
    def __init__(self, db, name):
        self.db, self.name, self.rows = db, name, None

    def select(self, *a):
        return self

    def gte(self, *a):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a):
        return self

    def upsert(self, rows, **k):
        self.rows = rows
        return self

    def execute(self):
        if self.rows is not None:
            self.db.saved += self.rows
            return type("R", (), {"data": self.rows})()
        return type("R", (), {"data": self.db.existing})()


class _DB:
    def __init__(self, existing=()):
        self.existing, self.saved = list(existing), []

    def table(self, name):
        return _Table(self, name)


class _Chain:
    def __init__(self, ticker):
        self.options = ("2026-11-20", "2026-11-27")
        self.fast_info = {"last_price": 101.0}

    def option_chain(self, expiry):
        frame = pd.DataFrame({"strike": [95.0, 100.0, 105.0], "openInterest": [10, 30, 10]})
        return type("C", (), {"calls": frame, "puts": frame})()


def test_refresh_due_saves_crypto_and_equities_once():
    now = datetime(2026, 11, 17, 15, 0, tzinfo=timezone.utc)
    crypto = lambda symbol, now: ({"2026-11-20": {"calls": {100.0: 1.0}, "puts": {90.0: 1.0}, "spot": 99.0}}, None)
    db = _DB()
    out = osn.refresh_due(db, {("Stock", "aapl"): "Apple", ("Crypto", "solana"): "Solana"}, now=now, chain=_Chain,
                          crypto=crypto, log=lambda *a: None)
    keys = {r["asset_key"] for r in db.saved}
    assert keys == {"Crypto|bitcoin", "Crypto|ethereum", "Stock|AAPL"} and out["equities"] == 1
    assert all("first_seen_at" not in r for r in db.saved)              # the database sets it
    done = _DB([{"asset_key": k, "recorded_at": now.isoformat()} for k in keys])
    osn.refresh_due(done, {("Stock", "AAPL"): "Apple"}, now=now, chain=_Chain, crypto=crypto, log=lambda *a: None)
    assert done.saved == []
