"""Prism scheduled scans (docs/design/lattice_prism.md §5.2, build stage 3). No database, no network."""

from __future__ import annotations

import itertools
import re
from pathlib import Path

import pandas as pd
import pytest

import digest
import prism
import prism_scans as ps

UTC = "UTC"


def T(text):
    return pd.Timestamp(text, tz=UTC)


# ----------------------------------------------------------------------------------------------- schedules

@pytest.mark.parametrize("now,tf,market,expected", [
    ("2026-11-05 00:09", "1D", "crypto", "2026-11-04 00:00"),     # 10-minute settle not yet passed
    ("2026-11-05 00:11", "1D", "crypto", "2026-11-05 00:00"),
    ("2026-11-05 13:00", "4H", "crypto", "2026-11-05 12:00"),
    ("2026-11-05 12:05", "4H", "crypto", "2026-11-05 08:00"),
    ("2026-11-05 13:00", "1W", "crypto", "2026-11-02 00:00"),     # Monday 00:00 UTC
    ("2026-11-05 21:15", "1D", "equity", "2026-11-05 21:00"),     # 16:00 New York after the clocks changed
    ("2026-11-05 21:05", "1D", "equity", "2026-11-04 21:00"),
    ("2026-10-28 20:30", "1D", "equity", "2026-10-28 20:00"),     # 16:00 New York in summer time
    ("2026-11-08 12:00", "1D", "equity", "2026-11-06 21:00"),     # Sunday: Friday's close
    ("2026-11-05 13:00", "1W", "equity", "2026-10-30 20:00"),     # last Friday close
    ("2026-11-05 13:00", "4H", "equity", "2026-11-04 21:00"),     # shares are checked at the daily close
])
def test_candle_close_cutoffs(now, tf, market, expected):
    assert ps.latest_cutoff({"kind": "close", "timeframe": tf}, market, T(now)) == T(expected)


def test_set_times_follow_the_zone_and_the_days():
    sched = {"kind": "times", "times": ["08:00", "20:00"], "tz": "Asia/Bangkok", "days": "weekdays"}
    assert ps.latest_cutoff(sched, "crypto", T("2026-11-05 02:00")) == T("2026-11-05 01:00")   # 08:00 Bangkok
    assert ps.latest_cutoff(sched, "crypto", T("2026-11-05 00:30")) == T("2026-11-04 13:00")   # 20:00 the day before
    assert ps.latest_cutoff(sched, "equity", T("2026-11-08 12:00")) == T("2026-11-06 13:00")   # Sunday: Friday 20:00
    mondays = {**sched, "days": [0]}
    assert ps.latest_cutoff(mondays, "crypto", T("2026-11-05 02:00")) == T("2026-11-02 13:00")


def test_schedules_are_validated_and_described():
    assert ps.validate_schedule({"kind": "close", "timeframe": "1D"}) == []
    assert ps.validate_schedule({"kind": "close", "timeframe": "15m"})
    assert ps.validate_schedule({"kind": "times", "times": ["25:00"], "tz": "Asia/Bangkok"})
    assert ps.validate_schedule({"kind": "times", "times": ["1:00", "2:00", "3:00", "4:00", "5:00"], "tz": "UTC"})
    assert ps.validate_schedule({"kind": "times", "times": ["08:00"], "tz": "Mars/Base"})
    assert ps.validate_schedule({"kind": "times", "times": ["08:00"], "tz": "UTC", "days": [9]})
    assert ps.describe_schedule({"kind": "close", "timeframe": "4H"}) == "every 4-hour close"
    assert ps.describe_schedule({"kind": "times", "times": ["08:00"], "tz": "UTC", "days": [0, 4]}) == \
        "at 08:00 (UTC), Mon, Fri"


def test_running_faster_than_the_members_change_is_a_warning():
    doc = prism.demo_sets()["demo:agree"]
    assert "same answer until the next daily close" in ps.schedule_warning({"kind": "close", "timeframe": "4H"}, doc)
    assert ps.schedule_warning({"kind": "close", "timeframe": "1D"}, doc) is None


# ----------------------------------------------------------------------------------------------- latches

def test_alert_plan_truth_table():
    answers = {"a": "yes", "b": "yes", "c": "no", "d": "no", "e": "unknown", "f": "failed"}
    latched = {"b", "c", "e", "f"}
    opens, releases, notify = ps.plan_alerts(answers, latched, "change")
    assert (opens, releases, notify) == (["a"], ["c"], ["a"])
    opens, releases, notify = ps.plan_alerts(answers, latched, "every")
    assert (opens, releases, notify) == (["a"], ["c"], ["a", "b"])


# ----------------------------------------------------------------------------------------------- worker

class FakeStore:
    def __init__(self, scans):
        self.scans = scans
        self.runs = {}
        self.latched = {}
        self.notes = []
        self.ids = itertools.count(1)
        self.emailed = []

    def active_scans(self):
        return [s for s in self.scans if not s.get("paused")]

    def claim(self, scan_id, market, cutoff, started):
        key = (scan_id, market, cutoff)
        if key in self.runs:
            return None
        self.runs[key] = {"id": next(self.ids), "status": "running"}
        return self.runs[key]["id"]

    def finish(self, run_id, fields):
        run = next(r for r in self.runs.values() if r["id"] == run_id)
        run.update(fields)

    def latches(self, scan_id):
        return set(self.latched.get(scan_id, set()))

    def open_latches(self, scan_id, keys, cutoff):
        self.latched.setdefault(scan_id, set()).update(keys)

    def release_latches(self, scan_id, keys):
        self.latched.setdefault(scan_id, set()).difference_update(keys)

    def notify(self, rows):
        out = [{**r, "id": next(self.ids)} for r in rows]
        self.notes += out
        return out

    def mark_emailed(self, note_id, when):
        self.emailed.append(note_id)

    def touch(self, scan_id, when):
        pass

    def expire_and_prune(self, now):
        pass


def _scan(i=1, mode="change", email=True, schedule=None):
    return {"id": f"s{i}", "owner_id": "u1", "name": f"Scan {i}", "set_body": {"name": "x"}, "set_version": 1,
            "schedule": schedule or {"kind": "close", "timeframe": "1D"}, "alert_mode": mode,
            "notify": {"in_app": True, "email": email}, "paused": False}


WATCH = {"u1": ({"bitcoin": "Bitcoin", "solana": "Solana"}, {})}


def _evaluator(script):
    """script: list of {asset id: answer} per call."""
    calls = iter(script)

    def evaluate(doc, assets, cutoff):
        answers = next(calls)
        rows = [{"kind": k, "id": i, "asset": n, "answer": answers.get(i, "unknown"), "how_sure": "Definite",
                 "reason": f"{i} {answers.get(i)}", "available": "Complete"} for k, i, n in assets]
        return rows, {"cutoff": str(cutoff)}
    return evaluate


def test_first_yes_alerts_once_unknown_keeps_the_latch_and_only_no_releases_it():
    store = FakeStore([_scan()])
    script = [{"bitcoin": "yes", "solana": "no"}, {"bitcoin": "unknown", "solana": "no"},
              {"bitcoin": "yes", "solana": "no"}, {"bitcoin": "no", "solana": "no"}, {"bitcoin": "yes", "solana": "no"}]
    ev = _evaluator(script)
    notified = []
    for day in range(5):
        now = T("2026-11-05 00:30") + pd.Timedelta(days=day)
        out = ps.run_due_scans(store, watchlists=WATCH, prefs={}, evaluate=ev, now=now)
        notified.append(out["notified"])
    assert notified == [1, 0, 0, 0, 1]
    assert [n["asset_symbol"] for n in store.notes] == ["bitcoin", "bitcoin"]
    assert all(n["alert_type"] == "prism" and n["message"].startswith("Prism: “Scan 1” says Yes") for n in store.notes)


def test_a_cutoff_runs_once_even_if_the_worker_runs_again():
    store = FakeStore([_scan()])
    ev = _evaluator([{"bitcoin": "yes"}])
    first = ps.run_due_scans(store, watchlists=WATCH, prefs={}, evaluate=ev, now=T("2026-11-05 00:30"))
    second = ps.run_due_scans(store, watchlists=WATCH, prefs={}, evaluate=ev, now=T("2026-11-05 00:35"))
    assert (first["ran"], second["ran"], second["skipped_claimed"], len(store.notes)) == (1, 0, 1, 1)


def test_every_run_mode_repeats_while_yes():
    store = FakeStore([_scan(mode="every")])
    ev = _evaluator([{"bitcoin": "yes"}, {"bitcoin": "yes"}])
    for day in range(2):
        ps.run_due_scans(store, watchlists=WATCH, prefs={}, evaluate=ev, now=T("2026-11-05 00:30") + pd.Timedelta(days=day))
    assert len(store.notes) == 2


def test_a_failing_scan_is_recorded_and_does_not_stop_the_others():
    store = FakeStore([_scan(1), _scan(2)])

    def evaluate(doc, assets, cutoff):
        if evaluate.calls == 0:
            evaluate.calls += 1
            raise RuntimeError("provider down")
        return _evaluator([{"bitcoin": "yes"}])(doc, assets, cutoff)
    evaluate.calls = 0
    out = ps.run_due_scans(store, watchlists=WATCH, prefs={}, evaluate=evaluate, now=T("2026-11-05 00:30"),
                           log=lambda *_: None)
    statuses = sorted(r["status"] for r in store.runs.values())
    assert (out["failed"], out["ran"], statuses) == (1, 1, ["failed", "ok"])
    failed = next(r for r in store.runs.values() if r["status"] == "failed")
    assert "provider down" in failed["error"]
    assert "s1" not in store.latched                       # the failed run latched nothing
    assert store.latched["s2"] == {"crypto:bitcoin"}


def test_the_time_budget_leaves_the_rest_for_the_next_pass():
    store = FakeStore([_scan(1), _scan(2), _scan(3)])
    ticks = iter([0, 0, 1000, 1000, 1000])        # start, first scan, then over budget
    out = ps.run_due_scans(store, watchlists=WATCH, prefs={}, evaluate=_evaluator([{}, {}, {}]),
                           now=T("2026-11-05 00:30"), budget_seconds=240, clock=lambda: next(ticks),
                           log=lambda *_: None)
    assert out["ran"] == 1 and out["waiting"] == 2


def test_instant_email_follows_the_alert_settings():
    sent = []
    send = lambda to, name, msg: sent.append((to, name)) or True
    for instant, email_on, expect in ((True, True, 1), (False, True, 0), (True, False, 0)):
        sent.clear()
        store = FakeStore([_scan(email=email_on)])
        ps.run_due_scans(store, watchlists=WATCH, prefs={"u1": {"instant_email": instant}},
                         evaluate=_evaluator([{"bitcoin": "yes"}]), now=T("2026-11-05 00:30"),
                         send_email=send, email_of=lambda uid: "drew@example.com")
        assert (len(sent), len(store.emailed)) == (expect, expect)


def test_crypto_and_shares_are_separate_runs_at_their_own_closes():
    watch = {"u1": ({"bitcoin": "Bitcoin"}, {"aapl": "Apple"})}
    items = ps.due_items([_scan()], watch, T("2026-11-05 21:15"))
    assert [(i[2], str(i[0])) for i in items] == [("crypto", "2026-11-05 00:00:00+00:00"),
                                                   ("equity", "2026-11-05 21:00:00+00:00")]
    assert items[1][3] == [("equity", "AAPL", "Apple (AAPL)")]
    assert ps.due_items([_scan()], {"u1": ({}, {})}, T("2026-11-05 21:15")) == []
    assert ps.due_items([_scan(schedule={"kind": "bad"})], watch, T("2026-11-05 21:15")) == []


def test_results_are_grouped_for_the_page():
    run = {"status": "ok", "cutoff": "2026-11-05T00:00:00+00:00", "opened": ["crypto:a"],
           "results": [{"kind": "crypto", "id": "a", "answer": "yes"}, {"kind": "crypto", "id": "b", "answer": "yes"},
                       {"kind": "crypto", "id": "c", "answer": "unknown"}, {"kind": "crypto", "id": "d", "answer": "no"}]}
    g = ps.group_results([run, {"status": "failed", "market": "equity"}])
    assert [len(g[k]) for k in ("new_yes", "still_yes", "unknown", "no", "failed")] == [1, 1, 1, 1, 1]


# ----------------------------------------------------------------------------------------------- digest, SQL, screen

def test_digest_gains_a_prism_section_only_when_there_are_prism_notes():
    config = {"digest_tz": "UTC", "enabled": True}
    plain_before = digest.render_digest([], [], config, "https://app")
    assert digest.render_digest([], [], config, "https://app", prism=[]) == plain_before
    note = {"asset_symbol": "bitcoin", "asset_name": "Bitcoin", "alert_type": "prism",
            "message": "Prism: “Daily check” says Yes. Every line holds.", "created_at": "2026-11-05T00:12:00+00:00"}
    subject, page, text = digest.render_digest([], [], config, "https://app", prism=[note])
    assert subject == "Angstrom daily summary: 1 Prism match" and "Prism scans (1)" in text and "Bitcoin" in page


def test_sql_is_rerunnable_owner_only_and_claims_once():
    sql = Path(__file__).resolve().parent.parent.joinpath("sql", "2026-11-06_prism_scans.sql").read_text()
    assert "unique (scan_id, market, cutoff)" in sql
    assert len(re.findall(r"create table if not exists", sql)) == 3
    assert sql.count("security definer") == 3 and "public.is_admin()" in sql
    assert "revoke all on public.prism_scans, public.prism_scan_runs, public.prism_scan_latches from anon, authenticated" in sql
    for line in re.findall(r"create policy[^\n]+", sql):
        assert "drop policy if exists" in sql.split(line)[0].rsplit("\n", 3)[-2]
    assert "if active >= 5" in sql


def _app_scheduled():
    import streamlit as st

    from tests.test_signal_inspector import _app as inspector_app

    st.session_state.setdefault("prism_view", "⏰ Scheduled scans")
    inspector_app()


def test_scheduled_scans_view_renders_inside_streamlit():
    testing = pytest.importorskip("streamlit.testing.v1")
    app = testing.AppTest.from_function(_app_scheduled, default_timeout=120)
    app.run()
    assert not app.exception
    assert [b for b in app.button if "Save scan" in b.label]
