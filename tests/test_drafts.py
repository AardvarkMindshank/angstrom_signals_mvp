"""Unsaved editor changes kept per account (drafts.py)."""

import drafts as dr


class _Q:
    def __init__(self, db, op=None, row=None):
        self.db, self.op, self.row, self.f = db, op, row, {}

    def select(self, *a):
        self.op = "select"
        return self

    def upsert(self, row, **k):
        return _Q(self.db, "upsert", row)

    def delete(self):
        return _Q(self.db, "delete")

    def eq(self, k, v):
        self.f[k] = v
        return self

    def limit(self, n):
        return self

    def execute(self):
        self.db.calls.append(self.op)
        if self.db.broken:
            raise RuntimeError("relation editor_drafts does not exist")
        if self.op == "upsert":
            self.db.rows[(self.row["owner_id"], self.row["kind"], self.row["draft_key"])] = self.row
            return type("R", (), {"data": [self.row]})()
        key = (self.f.get("owner_id"), self.f.get("kind"), self.f.get("draft_key"))
        if self.op == "delete":
            self.db.rows.pop(key, None)
            return type("R", (), {"data": []})()
        got = self.db.rows.get(key)
        return type("R", (), {"data": [got] if got else []})()


class _DB:
    def __init__(self, broken=False):
        self.rows, self.calls, self.broken = {}, [], broken

    def table(self, name):
        assert name == "editor_drafts"
        return _Q(self)


def test_remember_restore_forget_and_no_needless_writes():
    db, state = _DB(), {}
    base, edited = {"name": "Mine", "stages": [1, 2, 3]}, {"name": "Mine", "stages": [1, 2, 3, 4]}
    dr.remember(state, db, "u1", "funnel", "f1", base, base)
    assert db.calls == [] and not db.rows                          # unchanged: nothing stored
    dr.remember(state, db, "u1", "funnel", "f1", edited, base)
    dr.remember(state, db, "u1", "funnel", "f1", edited, base)
    assert db.calls == ["upsert"]                                  # the same change is stored once
    fresh = {}                                                     # another browser, later
    body, at = dr.restore(fresh, db, "u1", "funnel", "f1")
    assert body == edited and at
    assert dr.restore(fresh, db, "u2", "funnel", "f1") is None     # another account sees nothing
    dr.remember(fresh, db, "u1", "funnel", "f1", base, base)       # edited back to where it started
    assert not db.rows


def test_editor_load_track_and_save():
    db, state = _DB(), {"model": {"name": "Start"}}
    clean = dict
    dr.after_load(state, db, "u1", "set", "saved:c1", "model", clean)
    assert state["_draft_base_set"] == ("saved:c1", {"name": "Start"}) and "_draft_restored_set" not in state
    dr.remember(state, db, "u1", "set", "saved:c1", {"name": "Changed"}, state["_draft_base_set"][1])
    again = {"model": {"name": "Start"}}                           # the editor opened again elsewhere
    dr.after_load(again, db, "u1", "set", "saved:c1", "model", clean)
    assert again["model"] == {"name": "Changed"} and again["_draft_restored_set"][0] == "saved:c1"
    dr.saved(again, db, "u1", "set", "saved:c1")
    assert not db.rows and "_draft_restored_set" not in again


def test_without_the_table_editing_still_works():
    db, state = _DB(broken=True), {}
    dr.remember(state, db, "u1", "group", "new", {"a": 1}, {"a": 0})
    assert dr.restore(state, db, "u1", "group", "new") is None
    dr.forget(state, db, "u1", "group", "new")
    dr.after_load({"m": {}}, db, "u1", "group", "new", "m", dict)
    assert dr.when("2026-11-11T15:10:00+00:00") == "11 Nov 15:10 UTC" and dr.when("") == "earlier"
