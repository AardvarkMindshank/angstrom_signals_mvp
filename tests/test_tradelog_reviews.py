"""Weekly reviews asked for in the new app (tradelog_reviews.py), written by the worker."""
import tradelog_reviews as tr


class _Q:
    def __init__(self, db, table):
        self.db, self.table, self.filters, self.payload = db, table, [], None

    def select(self, *_a):
        return self

    def eq(self, k, v):
        self.filters.append((k, v))
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a):
        return self

    def range(self, a, b):
        self.rng = (a, b)
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def execute(self):
        class R:
            pass
        r = R()
        if self.payload is not None:
            self.db.updates.append((self.table, self.payload, self.filters))
            r.data = []
            return r
        rows = self.db.rows.get(self.table, [])
        if getattr(self, "rng", (0, 0))[0] > 0:
            rows = []
        r.data = [x for x in rows if all(str(x.get(k.split("->>")[0]) if "->>" not in k else
                                             str((x.get("review") or {}).get("pending")).lower()) == str(v)
                                         for k, v in self.filters if k != "user_id")]
        return r


class _DB:
    def __init__(self, rows):
        self.rows, self.updates = rows, []

    def table(self, name):
        return _Q(self, name)


def test_a_pending_review_is_written_in_the_asked_language():
    trip = {"id": 1, "user_id": "u", "connection_id": "c", "name": "A", "asset_class": "crypto", "direction": "long",
            "opened_at": "2026-11-17T10:00:00Z", "closed_at": "2026-11-18T10:00:00Z", "net_result_usd": 12.0,
            "result_pct": 5.0, "invested_usd": 100.0, "leverage": 1, "copied": False, "fees_usd": 0}
    db = _DB({"trade_reviews": [{"user_id": "u", "week_start": "2026-11-16", "scope": "all", "language": "de",
                                 "review": {"pending": True, "zone": "Europe/Berlin"}}],
              "trade_round_trips": [trip], "trade_snapshots": [], "user_preferences": []})
    seen = {}

    def write(fact, provider, language="English"):
        seen.update(language=language, trades=len(fact["trades"]))
        return {"happened": "x", "pattern": "y", "question": "z", "cited": [], "plain": False}

    assert tr.run_pending(db, write).startswith("1 asked, 1 written")
    assert seen == {"language": "German", "trades": 1}
    table, payload, _ = db.updates[0]
    assert table == "trade_reviews" and "pending" not in payload["review"]


def test_a_week_with_no_trades_is_marked_empty_without_the_ai():
    db = _DB({"trade_reviews": [{"user_id": "u", "week_start": "2026-11-16", "scope": "all", "language": "en",
                                 "review": {"pending": True}}], "trade_round_trips": [], "trade_snapshots": []})
    assert "1 with no trades" in tr.run_pending(db, lambda *a, **k: 1 / 0)
    assert db.updates[0][1]["review"]["empty"] is True
