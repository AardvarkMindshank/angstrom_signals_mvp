"""📱 Push notifications: what a phone shows, and the worker step that sends each new notification once."""

import base64
from datetime import datetime, timedelta, timezone

import pytest

import push_notify as pn


class _Query:
    def __init__(self, db, table):
        self.db, self.table, self.filters, self.patch, self.kill = db, table, [], None, False

    def select(self, *_):
        return self

    def eq(self, col, val):
        self.filters.append(lambda r: str(r.get(col)) == str(val)); return self

    def is_(self, col, _null):
        self.filters.append(lambda r: r.get(col) is None); return self

    def gte(self, col, val):
        self.filters.append(lambda r: str(r.get(col)) >= str(val)); return self

    def in_(self, col, vals):
        self.filters.append(lambda r: str(r.get(col)) in {str(v) for v in vals}); return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_):
        return self

    def update(self, patch):
        self.patch = patch; return self

    def delete(self):
        self.kill = True; return self

    def execute(self):
        rows = [r for r in self.db[self.table] if all(f(r) for f in self.filters)]
        if self.patch is not None:
            for r in rows:
                r.update(self.patch)
        if self.kill:
            self.db[self.table] = [r for r in self.db[self.table] if r not in rows]
        return type("R", (), {"data": rows})()


class _Db:
    def __init__(self, **tables):
        self.tables = tables

    def table(self, name):
        return _Query(self.tables, name)


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")


def test_payload_titles_and_length():
    p = pn.note_payload({"id": 7, "alert_type": "funnel", "asset_name": "Trend crypto longs", "message": "x " * 200})
    assert p["title"] == "🔻 Funnel" and p["tag"] == "note-7" and len(p["body"]) <= 220 and p["body"].endswith("…")
    assert pn.note_payload({"alert_type": "trend_up", "asset_name": "Bitcoin", "message": "Up"})["title"] == "Angstrom · Bitcoin"


def test_sends_each_new_note_once_and_drops_gone_devices(keys):
    now = datetime(2026, 11, 14, 9, 0, tzinfo=timezone.utc)
    fresh, old = (now - timedelta(minutes=3)).isoformat(), (now - timedelta(hours=3)).isoformat()
    db = _Db(
        push_subscriptions=[{"id": 1, "user_id": "u1", "endpoint": "https://a", "p256dh": "k", "auth": "a"},
                            {"id": 2, "user_id": "u1", "endpoint": "https://gone", "p256dh": "k", "auth": "a"}],
        user_notifications=[{"id": 10, "user_id": "u1", "message": "new", "created_at": fresh, "pushed_at": None},
                            {"id": 11, "user_id": "u1", "message": "old", "created_at": old, "pushed_at": None},
                            {"id": 12, "user_id": "u2", "message": "no device", "created_at": fresh, "pushed_at": None}])
    calls = []

    class Gone(Exception):
        response = type("Resp", (), {"status_code": 410})()

    def webpush(subscription_info, data, **kw):
        calls.append((subscription_info["endpoint"], data))
        if subscription_info["endpoint"] == "https://gone":
            raise Gone()

    out = pn.run_pending(db, now=now, webpush=webpush, log=lambda m: None)
    assert out == {"notes": 1, "sent": 1, "gone": 1}
    assert [c[0] for c in calls] == ["https://a", "https://gone"]
    notes = {n["id"]: n for n in db.tables["user_notifications"]}
    assert notes[10]["pushed_at"] and notes[11]["pushed_at"] is None and notes[12]["pushed_at"] is None
    assert [s["id"] for s in db.tables["push_subscriptions"]] == [1]
    assert pn.run_pending(db, now=now, webpush=webpush, log=lambda m: None)["notes"] == 0      # once only


def test_nothing_without_keys(monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    assert pn.run_pending(_Db(), log=lambda m: None) == {"skipped": "no push keys"}


def test_key_pair_shape():
    pytest.importorskip("cryptography")
    public, private = pn.generate_keys()
    pad = lambda s: s + "=" * (-len(s) % 4)
    assert len(base64.urlsafe_b64decode(pad(public))) == 65 and len(base64.urlsafe_b64decode(pad(private))) == 32
