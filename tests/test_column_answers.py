"""Background answers for table columns that read 4-hour, hourly or weekly candles (column_answers.py)."""

import pandas as pd

import column_answers as ca
import table_columns as tc


def _doc(tf):
    return {"members": [{"ref": {"signal": "rsi", "timeframe": tf}}]}


def _spec(tf, part="groups"):
    return {"key": "saved:g1", "part": part, "name": "Fast", "config": "g1", "version": 1, "cluster": None,
            "doc": _doc(tf)}


def test_cadence_is_the_shortest_timeframe_but_at_least_hourly():
    assert ca.cadence(_doc("4h")) == 240
    assert ca.cadence(_doc("1h")) == 60
    assert ca.cadence(_doc("15m")) == 60
    assert ca.cadence({"members": [{"ref": {"timeframe": "1D"}}, {"ref": {"timeframe": "4h"}}]}) == 240
    assert ca.def_hash(_doc("4h")) == ca.def_hash(_doc("4h")) != ca.def_hash(_doc("1h"))


def test_cutoffs_crypto_every_close_shares_held_at_the_new_york_close():
    now = pd.Timestamp("2026-11-04 13:07", tz="UTC")          # Wednesday
    assert ca.cutoff(_doc("4h"), "crypto", now) == pd.Timestamp("2026-11-04 12:00", tz="UTC")
    assert ca.cutoff(_doc("4h"), "crypto", now - pd.Timedelta(hours=2)) == pd.Timestamp("2026-11-04 08:00", tz="UTC")
    assert ca.cutoff(_doc("1h"), "crypto", now) == pd.Timestamp("2026-11-04 12:00", tz="UTC")
    # 13:00 UTC is before the 9:30 New York open: held at Tuesday's close.
    assert ca.cutoff(_doc("1h"), "equity", now) == pd.Timestamp("2026-11-03 16:00", tz="America/New_York")
    # Saturday: held at Friday's close.
    sat = pd.Timestamp("2026-11-07 15:00", tz="UTC")
    assert ca.cutoff(_doc("1h"), "equity", sat) == pd.Timestamp("2026-11-06 16:00", tz="America/New_York")
    # During trading: the last hourly close.
    mid = pd.Timestamp("2026-11-04 17:15", tz="UTC")
    assert ca.cutoff(_doc("1h"), "equity", mid) == pd.Timestamp("2026-11-04 17:00", tz="UTC")


class _Q:
    def __init__(self, db, name):
        self.db, self.name, self.op = db, name, "select"

    def __getattr__(self, attr):
        return lambda *a, **k: self

    def upsert(self, rows, **k):
        self.op, self.rows = "upsert", rows
        return self

    def execute(self):
        if self.op == "upsert":
            self.db.saved += self.rows
            self.data = None
        else:
            self.data = self.db.tables.get(self.name, [])
        return self


class _Db:
    def __init__(self, tables):
        self.tables, self.saved = tables, []

    def table(self, name):
        return _Q(self, name)


def test_worker_saves_only_due_answers(monkeypatch):
    doc = _doc("4h")
    db = _Db({"analysis_configs": [{"id": "g1", "kind": "group", "name": "Fast", "owner_id": "u",
                                    "starter_alias": None, "current_version": 1}],
              "analysis_config_versions": [{"config_id": "g1", "version": 1, "body": doc}],
              "column_answers": []})
    prefs = [{"user_id": "u", "settings": {"table_columns": {"groups": ["saved:g1"], "sets": []}},
              "crypto_watchlist": {"bitcoin": "Bitcoin"}, "stock_watchlist": {"AAPL": "Apple"}}]
    monkeypatch.setattr(tc, "resolve", lambda cols, saved: [dict(_spec("4h"), doc=doc)])
    monkeypatch.setattr(ca, "evaluate", lambda spec, assets, at, run: {
        f"{k}:{i}": {"value": 40.0, "label": "Bullish"} for k, i, _ in assets})
    import signal_library.replay_display as rd
    monkeypatch.setattr(rd, "display_run", lambda *a, **k: object())
    now = pd.Timestamp("2026-11-04 13:07", tz="UTC")
    got = ca.run_from_worker(db, prefs, now=now, log=lambda *_: None)
    assert got == {"columns": 1, "answers_saved": 2}
    assert {r["asset_key"] for r in db.saved} == {"crypto:bitcoin", "equity:AAPL"}
    # Already answered at these cutoffs: nothing more to do.
    db.tables["column_answers"] = [{"def_hash": r["def_hash"], "asset_key": r["asset_key"], "cutoff": r["cutoff"]}
                                   for r in db.saved]
    db.saved = []
    assert ca.run_from_worker(db, prefs, now=now, log=lambda *_: None)["answers_saved"] == 0
    # Daily-only choices cost the worker nothing.
    assert ca.run_from_worker(db, [{"settings": {}}], now=now) == {"columns": 0}


def test_cells_show_as_of_stale_mark_and_waiting_dash():
    spec = _spec("4h")
    now = pd.Timestamp("2026-11-04 13:07", tz="UTC")
    words, stale = tc.freshness(spec, {"as_of": "2026-11-04T08:00:00+00:00"}, now=now)
    assert "as of 08:00 UTC" in words and "4-hour" in words and not stale
    words, stale = tc.freshness(spec, {"as_of": "2026-11-03T08:00:00+00:00"}, now=now)
    assert stale and "out of date" in words
    assert "⏳" in tc.group_cell(spec, {"value": 10.0, "label": "Neutral", "as_of": "2026-11-03T08:00:00+00:00"})
    waiting = tc.group_cell(spec, None)
    assert "—" in waiting and "background" in waiting
    assert "—" in tc.set_cell(_spec("1h", "sets"), None)
    daily = dict(_spec("1D"))
    assert tc.freshness(daily, {"as_of": "6 Nov 2026"}) == ("as of the 6 Nov 2026 daily close", False)
