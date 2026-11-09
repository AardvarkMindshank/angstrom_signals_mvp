import json

import prism
import what_followed as wf
import what_followed_run as run


class _Query:
    def __init__(self, db, table):
        self.db, self.table, self.filters, self.update_fields = db, table, [], None

    def select(self, *_):
        return self

    def in_(self, col, values):
        self.filters.append(lambda r: r.get(col) in values)
        return self

    def eq(self, col, value):
        self.filters.append(lambda r: r.get(col) == value)
        return self

    def order(self, *_):
        return self

    def limit(self, *_):
        return self

    def update(self, fields):
        self.update_fields = fields
        return self

    def execute(self):
        rows = [r for r in self.db.rows if all(f(r) for f in self.filters)]
        if self.update_fields is not None:
            for r in rows:
                r.update(self.update_fields)
        return type("R", (), {"data": rows})()


class _Db:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        return _Query(self, name)


def _args(tmp_path):
    return type("A", (), {"out": str(tmp_path), "prices": "x"})()


def test_pick_queues_good_sets_and_refuses_the_rest(tmp_path, monkeypatch):
    docs = prism.demo_sets()
    good, news = docs["demo:pullback"], docs["demo:entry"]
    db = _Db([
        {"set_hash": wf.logic_hash(good), "set_body": good, "set_name": "Mine", "status": "queued"},
        {"set_hash": "0" * 24, "set_body": good, "set_name": "Wrong", "status": "queued"},
        {"set_hash": wf.logic_hash(news), "set_body": news, "set_name": "News", "status": "queued"},
    ])
    monkeypatch.setattr(run, "_client", lambda: db)
    run.pick_step(_args(tmp_path))
    queue = json.loads((tmp_path / "queue.json").read_text())
    assert list(queue) == [wf.logic_hash(good)] and queue[wf.logic_hash(good)]["name"] == "Mine"
    status = {r["set_name"]: r["status"] for r in db.rows}
    assert status == {"Mine": "running", "Wrong": "refused", "News": "refused"}
    assert "news sentiment" in next(r for r in db.rows if r["set_name"] == "News")["error"]


def test_a_study_on_part_of_the_assets_is_marked_failed(tmp_path, monkeypatch):
    h = wf.logic_hash(prism.demo_sets()["demo:pullback"])
    db = _Db([{"set_hash": h, "status": "running"}])
    (tmp_path / "queue.json").write_text(json.dumps({h: {"body": {}, "name": "Mine"}}))
    monkeypatch.setattr(run, "_client", lambda: db)
    monkeypatch.setenv("ANSWERS_RESULT", "failure")
    run.finish_step(_args(tmp_path))
    assert db.rows[0]["status"] == "failed" and "try again" in db.rows[0]["error"]


def test_a_finished_study_shows_on_the_set(monkeypatch):
    import perspectives

    doc = dict(prism.demo_sets()["demo:pullback"], name="My dip buyer")
    doc["groups"] = json.loads(json.dumps(doc["groups"]))
    doc["groups"][0]["subject"] = None                              # a different Set from the provided one
    h = wf.logic_hash(doc)
    result = {"start": "2014-09-17", "through": "2024-10-29", "sets": {h: {
        "type": "directional", "verdict": "Too few to judge", "episodes": 0, "weeks": 0, "tests": {}}}}
    db = _Db([{"set_hash": h, "result": result, "status": "done"}])
    monkeypatch.setitem(perspectives._shared, "at", 0.0)
    perspectives.load_studies(db, force=True)
    card = perspectives.followed_card(doc)
    assert card["verdict"] == "Too few to judge" and perspectives.evidence(doc)[0] == "🔬"


def test_only_daily_sets_without_news_can_be_studied():
    docs = prism.demo_sets()
    assert wf.studyable(docs["demo:pullback"]) == (True, "")
    four_hour = json.loads(json.dumps(docs["demo:pullback"]))
    four_hour["groups"][0]["snapshot"]["members"][0]["ref"]["timeframe"] = "4h"
    ok, why = wf.studyable(four_hour)
    assert not ok and "4h candles" in why


def test_market_context_does_not_stop_a_study():
    doc = json.loads(json.dumps(prism.demo_sets()["demo:pullback"]))
    doc["market_context"] = [{"key": "stables", "role": "context", "subject": "market:crypto",
                              "ref": {"id": "flows.stablecoin_supply", "version": 1, "timeframe": "1D"}}]
    assert wf.studyable(doc) == (True, "")
