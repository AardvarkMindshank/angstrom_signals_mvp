"""The alerts worker reads the scans without their Set bodies and the recent claims once a run (17 Nov 2026)."""

from datetime import datetime, timezone

import pandas as pd

import prism_scans as ps


class _Q:
    def __init__(self, db, table):
        self.db, self.table, self.cols, self.action = db, table, None, "select"

    def select(self, cols):
        self.cols = cols
        return self

    def insert(self, payload):
        self.action, self.payload = "insert", payload
        return self

    def eq(self, *_):
        return self

    def gte(self, *_):
        return self

    def limit(self, *_):
        return self

    def execute(self):
        self.db.calls.append((self.action, self.table, self.cols))

        class R:
            pass
        r = R()
        if self.action == "insert":
            r.data = [{"id": 99}]
        elif self.table == "prism_scan_runs":
            r.data = [{"scan_id": 5, "market": "crypto", "cutoff": "2026-11-17T08:00:00+00:00"}]
        else:
            r.data = [{"id": 5, "set_body": {"x": 1}, "rearm": None}]
        return r


class _Db:
    def __init__(self):
        self.calls = []

    def table(self, name):
        return _Q(self, name)


def test_scans_are_read_without_their_bodies_and_bodies_by_id():
    db = _Db()
    store = ps.SupabaseStore(db)
    store.active_scans()
    assert db.calls[-1][2] == ps.SCAN_LIGHT and "set_body" not in ps.SCAN_LIGHT and "rearm" not in ps.SCAN_LIGHT
    assert store.bodies(5) == {"id": 5, "set_body": {"x": 1}, "rearm": None}


def test_a_claim_already_made_is_not_asked_for_again():
    db = _Db()
    store = ps.SupabaseStore(db)
    now = datetime(2026, 11, 17, 9, tzinfo=timezone.utc)
    made = pd.Timestamp("2026-11-17 08:00", tz="UTC")
    assert store.claim(5, "crypto", made, now) is None
    assert store.claim(5, "crypto", made.to_pydatetime(), now) is None
    assert [c[0] for c in db.calls] == ["select"]                 # one read, no inserts
    assert store.claim(5, "crypto", made + pd.Timedelta(hours=1), now) == 99
    assert store.claim(5, "crypto", made + pd.Timedelta(hours=1), now) is None   # this run just claimed it
    assert [c[0] for c in db.calls] == ["select", "insert"]


def test_the_funnel_saves_only_coins_whose_place_changed():
    import funnel as fn
    import funnel_runner as fr

    sent = []

    class Q:
        def select(self, *_):
            return self

        def eq(self, *_):
            return self

        def upsert(self, rows, **kw):
            sent.append((rows, kw))
            return self

        def execute(self):
            class R:
                data = [{"coin_id": "btc", "stages_version": 1, "state": fn.CoinState.new(2).to_dict(),
                         **{k: v for k, v in fn.place(fn.CoinState.new(2)).items() if k in ("status", "depth", "pending")}}]
            return R()

    class Db:
        def table(self, _):
            return Q()

    store = fr.SupabaseStore(Db())
    store.coins(7)
    store.save_coins(7, 1, {"btc": fn.CoinState.new(2)})
    assert sent == []                                            # unchanged: nothing written
    moved = fn.CoinState.new(2)
    fn.record(moved, 0, "yes", "2026-11-17T08:00:00+00:00", None)
    store.save_coins(7, 1, {"btc": moved, "eth": fn.CoinState.new(2)})
    assert [r["coin_id"] for r in sent[0][0]] == ["btc", "eth"] and sent[0][1] == {"returning": "minimal"}
    store.save_coins(7, 1, {"btc": moved})
    assert len(sent) == 1
