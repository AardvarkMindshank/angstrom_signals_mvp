import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import funnel as fn
import funnel_rows as fr


def _funnel(n=4):
    return {"id": "f1", "name": "Up", "direction": "long",
            "stages": [{"label": f"S{i}", "timeframe": "1D"} for i in range(n)]}


def test_ago_wording():
    now = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
    assert fr.ago(None, now) == ""
    assert fr.ago((now - timedelta(seconds=20)).isoformat(), now) == "checked just now"
    assert fr.ago((now - timedelta(minutes=12)).isoformat(), now) == "checked 12 min ago"
    assert fr.ago((now - timedelta(hours=3)).isoformat(), now) == "checked 3 h ago"
    assert fr.ago((now - timedelta(days=4)).isoformat(), now) == "checked 4 days ago"
    assert fr.ago("not a time", now) == ""


def test_last_checked_takes_latest():
    runs = [None, {"finished_at": "2026-11-14T10:00:00+00:00"}, {"finished_at": "2026-11-14T11:00:00+00:00"}]
    assert fr.last_checked(runs) == "2026-11-14T11:00:00+00:00"
    assert fr.last_checked([None]) is None


def test_chips_order_and_new_badge():
    f = _funnel()
    chips = fr.chips(f, {}, new=2, hover={"candidate": "Every stage holds."})
    assert [c["key"] for c in chips] == ["stage:0", "stage:1", "stage:2", "flagged", "candidate"]
    assert chips[0]["icon"] == fn.STAGE_ICONS[0]
    assert chips[-1]["new"] == 2 and chips[-1]["hover"] == "Every stage holds."
    assert all(c["count"] == 0 for c in chips)


def test_order_puts_paused_last_and_default_pick():
    rows = [{"id": "a", "paused": True, "chips": [{"key": "stage:0", "count": 3}, {"key": "candidate", "count": 4}]},
            {"id": "b", "paused": False, "chips": [{"key": "stage:0", "count": 3}, {"key": "stage:1", "count": 1},
                                                   {"key": "candidate", "count": 0}]},
            {"id": "c", "paused": False, "chips": [{"key": "stage:0", "count": 3}, {"key": "candidate", "count": 1}]}]
    ordered = fr.order(rows)
    assert [r["id"] for r in ordered] == ["b", "c", "a"]
    assert fr.default_pick(ordered) == ("c", "candidate")
    assert fr.default_pick(ordered[:1]) == ("b", "stage:1")
    assert fr.default_pick([]) is None


def test_read_event_once_and_validated():
    state = {}
    raw = json.dumps({"kind": "pick", "funnel": "f1", "stage": "candidate", "nonce": 1})
    res = SimpleNamespace(go=raw)
    assert fr.read_event(res, "seen", state)["stage"] == "candidate"
    assert fr.read_event(res, "seen", state) is None
    bad = SimpleNamespace(go=json.dumps({"kind": "act", "action": "delete", "funnel": "f1", "nonce": 2}))
    assert fr.read_event(bad, "seen", state) is None
    ok = SimpleNamespace(go=json.dumps({"kind": "act", "action": "restart", "funnel": "f1", "nonce": 3}))
    assert fr.read_event(ok, "seen", state)["action"] == "restart"
