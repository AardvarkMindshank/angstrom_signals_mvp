"""Stage 7: Prism Scans as saved objects. The board's data, the board's actions, and the worker's per-scan assets,
alert channels, snoozes and quiet resume. Synthetic data, no database."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import prism
import prism_board as pb
import prism_scans as ps
import prism_view as pv
from tests.test_prism_scans import FakeStore, _evaluator

ROOT = Path(__file__).resolve().parent.parent
NOW = pd.Timestamp("2026-11-06 03:00", tz="UTC")
ASSETS = [("crypto", "bitcoin", "Bitcoin"), ("crypto", "solana", "Solana"), ("equity", "COIN", "Coinbase (COIN)")]
SET_DOC = prism.demo_sets()["demo:agree"]


def _saved(versions=(1, 2)):
    return [{"id": "cfg1", "kind": "set", "name": "COIN leads BTC", "owner_id": "me",
             "versions": [{"version": v, "body": SET_DOC} for v in versions]}]


def _stored(**over):
    base = {"id": "s1", "owner_id": "u1", "name": "COIN leads BTC", "set_body": SET_DOC,
            "set_source": {"key": "saved:cfg1:1", "config": "cfg1", "version": 1},
            "schedule": {"kind": "close", "timeframe": "1D"}, "alert_mode": "change",
            "notify": {"channel": "instant", "on_yes": True}, "paused": False,
            "assets": [{"group": "crypto"}], "snoozes": {}, "set_version": 1}
    return {**base, **over}


# ----------------------------------------------------------------------------------------------- board data

def test_library_lists_sets_groups_and_assets():
    choices = pb.set_choices(_saved(), "me")
    assert "saved:cfg1:2" in choices and "saved:cfg1:1" not in choices          # newest version only
    lib = pb.library(choices, ASSETS)
    assert {g["group"]: g["count"] for g in lib["groups"]} == {"watchlist": 3, "crypto": 2, "shares": 1}
    assert {"kind": "equity", "id": "COIN", "name": "Coinbase (COIN)", "market": "equity"} in lib["assets"]


def test_a_scan_card_shows_summary_details_and_an_update_badge():
    choices = pb.set_choices(_saved(), "me")
    runs = [{"market": "crypto", "cutoff": "2026-11-06T00:00:00+00:00", "status": "ok",
             "results": [{"asset": "Solana", "answer": "yes", "reason": "r1"},
                         {"asset": "Bitcoin", "answer": "no", "reason": "r2"}]},
            {"market": "crypto", "cutoff": "2026-11-05T00:00:00+00:00", "status": "failed", "results": None}]
    v = pb.view(_stored(snoozes={"crypto:solana": "2026-11-08T00:00:00+00:00"}), runs, ["crypto:solana"],
                choices, ASSETS, NOW)
    assert v["counts"] == {"yes": 1, "no": 1, "unknown": 0} and v["dots"] == ["failed", "yes"]
    assert v["update"] == {"key": "saved:cfg1:2", "version": 2} and v["version"] == "v1"
    assert v["asset_count"] == 2 and v["assets"] == [{"label": "All crypto", "group": True}]
    assert v["next_text"].startswith("next in") and v["yes_now"] == [{"key": "crypto:solana", "name": "Solana"}]
    assert v["snoozes"][0]["key"] == "crypto:solana" and [r["answer"] for r in v["results"]] == ["yes", "no"]
    manual = pb.view(_stored(schedule={"kind": "manual"}), [], [], choices, ASSETS, NOW)
    assert manual["next_text"] == "runs when you press Play" and not manual["scheduled"]
    session = pb.view(_stored(), runs, [], choices, ASSETS, NOW, {"title": "Run now", "rows": [
        {"asset": "Bitcoin", "answer": "unknown", "reason": "x"}]})
    assert session["results_title"] == "Run now" and session["results"][0]["answer"] == "unknown"


def test_next_run_follows_the_schedule():
    when = pb.next_run({"kind": "close", "timeframe": "1D"}, ["crypto"], NOW)
    assert when == pd.Timestamp("2026-11-07 00:10", tz="UTC")
    assert pb.next_run({"kind": "manual"}, ["crypto"], NOW) is None
    assert pb.scheduled_count([_stored(), _stored(paused=True), _stored(schedule={"kind": "manual"})]) == 1


def test_asset_edits_snoozes_duplicates_and_older_alert_settings():
    obj = pb.scan_object(_stored())
    out, problem = pb.add_asset(obj, {"kind": "equity", "id": "COIN"})
    assert problem is None and out["assets"] == [{"group": "crypto"}, {"kind": "equity", "id": "COIN"}]
    whole, _ = pb.add_asset(out, {"group": "watchlist"})
    assert whole["assets"] == [{"group": "watchlist"}]                          # covers everything else
    assert pb.remove_asset(whole, 0)[1]                                       # never empty
    assert pb.add_asset(obj, {"kind": "stock", "id": "X"})[1]
    snoozed = pb.snooze(obj, "crypto:solana", 3, NOW)
    assert ps.snoozed({"snoozes": snoozed["snoozes"]}, NOW) == {"crypto:solana"}
    assert pb.unsnooze(snoozed, "crypto:solana")["snoozes"] == {}
    assert pb.tidy_snoozes(pb.snooze(obj, "crypto:solana", 1, NOW - pd.Timedelta(days=5)), NOW)["snoozes"] == {}
    copy = pb.duplicate(obj, [obj["name"]])
    assert copy["name"] == obj["name"] + " (2)" and copy["schedule"] == {"kind": "manual"}
    assert pb.unique_name("Pullback", ["pullback", "Pullback (2)"]) == "Pullback (3)"
    assert pb.unique_name("New one", ["Pullback"]) == "New one"
    old = pb.scan_object(_stored(notify={"in_app": True, "email": False}))
    assert old["notify"]["channel"] == "account"
    assert pb.for_database(old)["notify"] == {"channel": "app", "on_yes": True, "on_no": False, "on_fail": False}


def test_schedule_and_alert_settings_from_the_board():
    assert pb.schedule_from({"runs": "4H"}) == ({"kind": "close", "timeframe": "4H"}, None)
    assert pb.schedule_from({"runs": "manual"}) == ({"kind": "manual"}, None)
    good, _ = pb.schedule_from({"runs": "times", "times": "08:00, 20:00", "days": "weekdays", "tz": "UTC"})
    assert good == {"kind": "times", "times": ["08:00", "20:00"], "days": "weekdays", "tz": "UTC"}
    assert pb.schedule_from({"runs": "times", "times": "25:00", "tz": "UTC"})[1]
    assert pb.notify_from({"channel": "digest", "on_no": True}) == {"channel": "digest", "on_yes": True,
                                                                    "on_no": True, "on_fail": False}
    assert pb.notify_from({"channel": "bogus"})["channel"] == "instant"


# ----------------------------------------------------------------------------------------------- board actions

class FakeDb:
    def __init__(self):
        self.calls = []

    def rpc(self, name, args):
        self.calls.append((name, json.loads(json.dumps(args, default=str))))

        class Out:
            data = "new-id"

            def execute(self):
                return self
        return Out()


class St:
    def __init__(self):
        self.session_state = {}


def test_board_actions_write_through_prism_put_scan():
    db, st = FakeDb(), St()
    choices = pb.set_choices(_saved(), "me")
    by_id = {"s1": _stored()}
    assert pv.handle(st, db, {"op": "create", "set": "saved:cfg1:2"}, by_id, choices, ASSETS, NOW)[0] == "ok"
    name, args = db.calls[-1]
    assert name == "prism_put_scan" and args["p_id"] is None and args["p_scan"]["schedule"] == {"kind": "manual"}
    assert st.session_state["prism_open_new"] == "new-id"
    assert pv.handle(st, db, {"op": "pause", "scan": "s1"}, by_id, choices, ASSETS, NOW)[0] == "ok"
    assert db.calls[-1][1]["p_scan"]["paused"] is True
    pv.handle(st, db, {"op": "alerts", "scan": "s1", "channel": "digest", "on_no": True}, by_id, choices, ASSETS, NOW)
    assert db.calls[-1][1]["p_scan"]["notify"]["channel"] == "digest"
    pv.handle(st, db, {"op": "update_set", "scan": "s1", "key": "saved:cfg1:2"}, by_id, choices, ASSETS, NOW)
    assert db.calls[-1][1]["p_scan"]["source"]["version"] == 2
    pv.handle(st, db, {"op": "delete", "scan": "s1"}, by_id, choices, ASSETS, NOW)
    assert db.calls[-1] == ("prism_delete_scan", {"p_id": "s1"})
    bad = pv.handle(st, db, {"op": "remove_asset", "scan": "s1", "index": 0}, by_id, choices, ASSETS, NOW)
    assert bad[0] == "error" and "at least one" in bad[1]
    assert pv.handle(st, db, {"op": "pause", "scan": "gone"}, by_id, choices, ASSETS, NOW)[0] == "error"


def test_play_runs_the_scan_assets_with_a_cooldown_and_a_size_limit(monkeypatch):
    st = St()
    seen = []
    monkeypatch.setattr(prism, "run_now", lambda doc, picked, **k: seen.append(picked) or [
        {"asset": n, "answer": "yes", "reason": "ok"} for _, _, n in picked])
    by_id = {"s1": _stored()}
    out = pv.handle(st, FakeDb(), {"op": "run", "scan": "s1"}, by_id, {}, ASSETS, NOW)
    assert out[0] == "ok" and seen[0] == [("crypto", "bitcoin", "Bitcoin"), ("crypto", "solana", "Solana")]
    assert st.session_state["prism_results"]["s1"]["rows"][0]["answer"] == "yes"
    again = pv.handle(st, FakeDb(), {"op": "run", "scan": "s1"}, by_id, {}, ASSETS, NOW)
    assert again[0] == "error" and "wait" in again[1]
    many = [("crypto", f"c{i}", f"C{i}") for i in range(prism.MAX_ASSETS + 1)]
    st.session_state["prism_last_run"] = 0
    big = pv.handle(st, FakeDb(), {"op": "run", "scan": "s1"}, by_id, {}, many, NOW)
    assert big[0] == "error" and "up to 40" in big[1]


# ----------------------------------------------------------------------------------------------- worker

WATCH = {"u1": ({"bitcoin": "Bitcoin", "solana": "Solana"}, {"COIN": "Coinbase"})}


def _run(scan, script, store=None, sent=None):
    store = store or FakeStore([scan])
    sent = sent if sent is not None else []
    ps.run_due_scans(store, watchlists=WATCH, prefs={}, evaluate=_evaluator(script), now=NOW,
                     send_email=lambda to, a, m: sent.append(m) or True, email_of=lambda uid: "me@example.com")
    return store, sent


def test_scans_read_their_own_assets_and_manual_scans_never_run_on_schedule():
    assert ps.scan_assets({"assets": [{"group": "shares"}, {"kind": "crypto", "id": "solana"}]}, WATCH["u1"],
                          "crypto") == [("crypto", "solana", "Solana")]
    assert ps.scan_assets({"assets": [{"group": "shares"}]}, WATCH["u1"], "equity") == \
        [("equity", "COIN", "Coinbase (COIN)")]
    assert ps.due_items([_stored(schedule={"kind": "manual"})], WATCH, NOW) == []
    assert [i[2] for i in ps.due_items([_stored()], WATCH, NOW)] == ["crypto"]       # crypto only: no share run


def test_alert_channels():
    yes = [{"bitcoin": "yes"}]
    store, sent = _run(_stored(notify={"channel": "instant", "on_yes": True}), yes)
    assert len(store.notes) == 1 and len(sent) == 1 and store.digested == [store.notes[0]["id"]]
    store, sent = _run(_stored(notify={"channel": "digest", "on_yes": True}), yes)
    assert len(store.notes) == 1 and not sent and not getattr(store, "digested", [])
    store, sent = _run(_stored(notify={"channel": "app", "on_yes": True}), yes)
    assert len(store.notes) == 1 and not sent and store.digested
    store, sent = _run(_stored(notify={"channel": "off", "on_yes": True}), yes)
    assert not store.notes and not sent and store.latched["s1"] == {"crypto:bitcoin"}   # still recorded


def test_turns_no_cant_run_snoozes_and_quiet_resume():
    scan = _stored(notify={"channel": "app", "on_yes": True, "on_no": True, "on_fail": True})
    store = FakeStore([scan])
    store.latched["s1"] = {"crypto:bitcoin"}
    _run(scan, [{"bitcoin": "no", "solana": "unknown"}], store)
    texts = [n["message"] for n in store.notes]
    assert any("no longer says Yes" in t for t in texts) and any("could not run properly" in t for t in texts)
    snoozed = _stored(snoozes={"crypto:bitcoin": (NOW + pd.Timedelta(days=1)).isoformat()})
    store, _ = _run(snoozed, [{"bitcoin": "yes", "solana": "yes"}])
    assert [n["asset_symbol"] for n in store.notes] == ["solana"] and store.latched["s1"] == {"crypto:bitcoin",
                                                                                               "crypto:solana"}
    quiet = _stored(quiet_next=True)
    store, sent = _run(quiet, [{"bitcoin": "yes"}])
    assert not store.notes and not sent and store.quiet_cleared == "s1" and store.latched["s1"] == {"crypto:bitcoin"}


def test_scans_saved_before_stage_7_keep_their_old_alert_behaviour():
    old = _stored(notify={"in_app": True, "email": True}, assets=None)
    store = FakeStore([old])
    sent = []
    ps.run_due_scans(store, watchlists=WATCH, prefs={"u1": {"instant_email": False}}, evaluate=_evaluator(
        [{}, {"bitcoin": "yes"}]), now=NOW, send_email=lambda *a: sent.append(a) or True, email_of=lambda u: "x@y")
    assert len(store.notes) == 1 and not sent                       # account setting: digest, as before


def test_sql_adds_columns_and_one_owner_only_function():
    sql = (ROOT / "sql" / "2026-11-08_prism_scan_objects.sql").read_text()
    for col in ("assets jsonb", "snoozes jsonb", "quiet_next boolean"):
        assert f"add column if not exists {col}" in sql
    assert sql.count("security definer") == 1 and "auth.uid()" in sql and "owner_id = me" in sql
    assert "'manual'" in sql and "if active >= 5" in sql and "was_paused and not v_paused" in sql
    assert "revoke all on function public.prism_put_scan(uuid, jsonb) from public, anon" in sql


def test_lattice_redraws_only_its_own_section_once_per_change():
    import lattice_component as lc
    import lattice_panel

    for js, name in ((lc.JS, "latticeGroup"), (lc.SET_JS, "latticeSet")):
        send = js[js.index("function send()"):js.index("function send()") + 200]
        assert f"{name}(component);" in send                     # drawn at once, before Python answers
    calls = []

    class St:
        def fragment(self, fn):
            calls.append("fragment")
            return fn

        def markdown(self, *a, **k):
            calls.append("drawn")

        def caption(self, *a, **k):
            pass

        def segmented_control(self, *a, **k):
            return "strategies"

        def info(self, *a, **k):
            pass
    lattice_panel.render(St(), None, [], "u")
    assert calls[:2] == ["fragment", "drawn"]                     # the whole section runs as a fragment
    st = type("S", (), {"session_state": {"k": {"model": "x"}}})()
    assert lattice_panel.pending(st, "k", "model") == "x" and lattice_panel.pending(st, "none", "model") is None
    for name in ("lattice_view.py", "lattice_set_view.py", "prism_view.py"):
        text = (ROOT / name).read_text()
        assert "st.rerun()" not in text and "lattice_panel.pending(" in text, name


def test_the_help_guide_covers_lattice_and_prism():
    app = (ROOT / "app.py").read_text()
    guide = app[app.index('with tracked_expander("📖 Help and guides"'):app.index("CRYPTO_WATCHLIST = prefs")]
    for words in ('"🧩 Lattice & Prism"', "Signal Groups", "Signal Sets", "Prism Scan", "All equities",
                  "Prism scan alerts", "5 scheduled scans", "Strategies"):
        assert words in guide, words
    assert "All shares" not in guide


def test_a_first_asset_takes_the_place_of_the_whole_watchlist():
    whole = {"assets": [{"group": "watchlist"}]}
    narrowed, problem = pb.add_asset(whole, {"kind": "crypto", "id": "bitcoin"})
    assert problem is None and narrowed["assets"] == [{"kind": "crypto", "id": "bitcoin"}]
    more, _ = pb.add_asset(narrowed, {"kind": "crypto", "id": "solana"})
    assert more["assets"] == [{"kind": "crypto", "id": "bitcoin"}, {"kind": "crypto", "id": "solana"}]
