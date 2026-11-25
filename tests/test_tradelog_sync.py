"""Trade Log sync (tradelog_sync.py): when connections sync, what gets saved, and that failures back off."""

import time
from datetime import datetime, timedelta, timezone

import tradelog
import tradelog_sync as sync

NOW = datetime(2026, 11, 22, 8, tzinfo=timezone.utc)


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, table):
        self.db, self.table, self.filters, self.op, self.payload = db, table, [], "select", None

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self.filters.append((col, val))
        return self

    def gte(self, *_a):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a):
        return self

    def range(self, start, end):
        self.window = (start, end)
        return self

    def upsert(self, rows, on_conflict=None, **_k):
        self.op, self.payload, self.conflict = "upsert", rows if isinstance(rows, list) else [rows], on_conflict
        return self

    def update(self, fields):
        self.op, self.payload = "update", fields
        return self

    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        match = lambda r: all(r.get(c) == v for c, v in self.filters)
        if self.op == "select":
            got = [dict(r) for r in rows if match(r)]
            if getattr(self, "window", None):
                got = got[self.window[0]:self.window[1] + 1]
            return _Result(got)
        if self.op == "update":
            for r in rows:
                if match(r):
                    r.update(self.payload)
            return _Result(None)
        keys = self.conflict.split(",")
        for new in self.payload:
            old = next((r for r in rows if all(r.get(k) == new.get(k) for k in keys)), None)
            if old:
                old.update(new)
            else:
                rows.append({"id": len(rows) + 1, **new})
        return _Result(None)


class _Db:
    def __init__(self, keys):
        self.tables, self.keys, self.rpcs = {}, keys, []

    def table(self, name):
        return _Query(self, name)

    def rpc(self, name, params):
        self.rpcs.append((name, params))
        keys = self.keys
        return type("Call", (), {"execute": lambda _self: _Result(keys)})()


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


class _Session:
    def __init__(self, status=200):
        self.status = status

    def get(self, url, headers=None, params=None, timeout=None):
        if self.status != 200:
            return _Resp(self.status, {})
        if "trade/history" in url:
            return _Resp(200, [{"positionId": 7, "instrumentId": 1001, "isBuy": True, "openRate": 10, "closeRate": 12,
                                "units": 1, "initialInvestment": 10, "netProfit": 2, "fees": 0, "leverage": 1,
                                "socialTradeId": 0, "parentPositionId": 0, "openTimestamp": "2026-11-01T00:00:00Z",
                                "closeTimestamp": "2026-11-03T00:00:00Z"}])
        if "instrument-types" in url:
            return _Resp(200, {"instrumentTypes": [{"instrumentTypeID": 5, "instrumentTypeDescription": "Stocks"}]})
        if "instruments" in url:
            return _Resp(200, {"instrumentDisplayDatas": [{"instrumentID": 1001, "instrumentDisplayName": "NVIDIA",
                                                            "symbolFull": "NVDA", "instrumentTypeID": 5}]})
        return _Resp(200, {"data": []})


CONN = {"id": "c1", "user_id": "u1", "platform": "etoro", "status": "new", "last_sync_at": None,
        "refresh_requested_at": None}


def test_when_a_connection_is_due():
    assert sync.is_due(CONN, NOW)
    ok = {**CONN, "status": "ok", "last_sync_at": (NOW - timedelta(hours=2)).isoformat()}
    assert not sync.is_due(ok, NOW)
    assert sync.is_due({**ok, "refresh_requested_at": NOW.isoformat()}, NOW)
    assert sync.is_due({**ok, "last_sync_at": (NOW - timedelta(hours=25)).isoformat()}, NOW)
    assert not sync.is_due({**CONN, "status": "paused"}, NOW)
    failing = {**ok, "status": "failing"}
    assert not sync.is_due(failing, NOW)                      # a failing key waits a day, no retry every pass


def test_sync_saves_round_trips_and_snapshots_and_marks_ok():
    db = _Db({"api_key": "A", "user_key": "U"})
    db.tables["trade_connections"] = [dict(CONN)]
    summary = sync.sync_connection(db, dict(CONN), _Session(), sync.Inputs(db, _Session()), time.monotonic() + 60, NOW)
    assert summary == {"trades": 1, "snapshots": 2, "failed": False}
    [trip] = db.tables["trade_round_trips"]
    assert trip["user_id"] == "u1" and trip["connection_id"] == "c1" and trip["asset_key"] == "Stock|NVDA"
    assert {s["moment"] for s in db.tables["trade_snapshots"]} == {"entry", "exit"}
    conn = db.tables["trade_connections"][0]
    assert conn["status"] == "ok" and conn["refresh_requested_at"] is None and conn["history_from"] == "2026-11-01"
    # a second sync updates in place, no duplicates, and doesn't redo snapshots
    again = sync.sync_connection(db, dict(conn), _Session(), sync.Inputs(db, _Session()), time.monotonic() + 60, NOW)
    assert again["snapshots"] == 0 and len(db.tables["trade_round_trips"]) == 1


def test_refused_key_marks_failing_with_a_safe_message():
    db = _Db({"api_key": "SECRET-A", "user_key": "SECRET-U"})
    db.tables["trade_connections"] = [dict(CONN)]
    summary = sync.sync_connection(db, dict(CONN), _Session(401), sync.Inputs(db, _Session()), time.monotonic() + 60, NOW)
    conn = db.tables["trade_connections"][0]
    assert summary["failed"] and conn["status"] == "failing" and "SECRET" not in conn["last_error"]
    assert conn["last_sync_at"] == NOW.isoformat()


def test_snapshots_stop_at_the_deadline():
    db = _Db({"api_key": "A", "user_key": "U"})
    db.tables["trade_connections"] = [dict(CONN)]
    summary = sync.sync_connection(db, dict(CONN), _Session(), sync.Inputs(db, _Session()), time.monotonic() - 1, NOW)
    assert summary["trades"] == 1 and summary["snapshots"] == 0      # trades saved; snapshots next pass


def test_worker_step_reports_counts_only():
    db = _Db({"api_key": "A", "user_key": "U"})
    db.tables["trade_connections"] = [dict(CONN)]
    text = sync.run_from_worker(db, _Session(), budget_seconds=60)
    assert text.startswith("1 connections, 1 synced") and "NVDA" not in text and "NVIDIA" not in text
    assert tradelog.MIN_TRADES == 10


def test_snapshots_skip_copied_trades_and_read_every_page():
    db = _Db({"api_key": "A", "user_key": "U"})
    db.tables["trade_round_trips"] = (
        [{"id": i, "connection_id": "c1", "copied": False, "asset_key": None, "asset_class": "stocks",
          "opened_at": "2026-11-01T00:00:00Z", "closed_at": "2026-11-03T00:00:00Z"} for i in range(1, 4)]
        + [{"id": 99, "connection_id": "c1", "copied": True, "asset_key": None, "asset_class": "stocks",
            "opened_at": "2026-11-01T00:00:00Z", "closed_at": "2026-11-03T00:00:00Z"}])
    made = sync.fill_snapshots(db, dict(CONN), sync.Inputs(db, _Session()), time.monotonic() + 60)
    assert made == 6 and {r["round_trip_id"] for r in db.tables["trade_snapshots"]} == {1, 2, 3}
    rows = sync._pages(lambda: db.table("trade_round_trips").select("id"), page=2)
    assert len(rows) == 4                                       # read past a full first page
