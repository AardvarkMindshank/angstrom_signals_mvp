"""The Trend, Stretch and Flow alerts as built-in Prism scans."""

import pandas as pd
import pytest

import alerts as al
import builtin_alerts as ba
import signal_groups as sg


def test_six_scans_follow_the_alert_settings():
    creates, updates = ba.plan_sync("u1", {}, {"flow_alert_on": True})
    by = {c["builtin"]: c for c in creates}
    assert set(by) == set(ba.BUILTINS) and not updates
    assert by["trend_up"]["set_source"]["mode"] == "borders" and by["trend_up"]["notify"]["channel"] == "account"
    assert by["trend_up"]["set_source"]["crossings"] == ["up_p20", "up_p50", "flip_up"]      # the defaults, upward
    assert by["trend_down"]["set_source"]["crossings"] == ["dn_m20", "dn_m50", "flip_dn"]
    assert by["stretch_up"]["notify"]["channel"] == "off"          # off unless switched on, as before
    assert by["flow_down"]["notify"]["channel"] == "account"
    assert all(c["quiet_next"] for c in creates)                   # the first run records quietly
    assert all(c["schedule"] == {"kind": "close", "timeframe": "1D"} for c in creates)


def test_sets_say_yes_past_the_line_and_rearm_20_back():
    up, down = ba.set_doc("trend_up", 50), ba.set_doc("trend_down", 50)
    assert sg.scannable(up) and not sg.validate_set(up) and not sg.validate_set(down)
    assert up["decision"]["rule"] == {"group": "trend", "score": {"gte": 0.5}}
    assert down["decision"]["rule"] == {"group": "trend", "score": {"lte": -0.5}}
    assert ba.rearm_doc("trend_up", 50)["decision"]["rule"] == {"group": "trend", "score": {"lte": 0.3}}
    assert ba.rearm_doc("trend_down", 50)["decision"]["rule"] == {"group": "trend", "score": {"gte": -0.3}}
    assert ba.rearm_level(15) == -5 and ba.rearm_level(5) == -5    # never past the opposite line


def test_sync_changes_the_ticks_and_switches_quietly():
    first, _ = ba.plan_sync("u1", {}, {})
    existing = {c["builtin"]: {**c, "id": c["builtin"], "set_version": 1} for c in first}
    existing["stretch_up"]["notify"] = {"channel": "off"}
    _, updates = ba.plan_sync("u1", existing, {"trend_crossings": ["up_p50", "dn_m20"], "stretch_alert_on": True})
    changes = dict(updates)
    assert changes["trend_up"]["set_source"]["crossings"] == ["up_p50"] and changes["trend_up"]["set_version"] == 2
    assert changes["trend_down"]["set_source"]["crossings"] == ["dn_m20"]
    _, none_down = ba.plan_sync("u1", existing, {"trend_crossings": ["up_p50"]})
    assert dict(none_down)["trend_down"]["notify"]["channel"] == "off"        # nothing ticked downward: not run
    assert changes["stretch_up"]["notify"]["channel"] == "account" and changes["stretch_up"]["quiet_next"]
    assert "flow_up" not in changes


def test_open_alerts_carry_over_as_latches():
    scans = [{"id": "s1", "builtin": "trend_up"}, {"id": "s2", "builtin": "trend_down"}]
    old = [{"asset_symbol": "bitcoin", "alert_type": al.TREND_UP},
           {"asset_symbol": "aapl", "alert_type": al.TREND_UP + "_HELD"},
           {"asset_symbol": "signals:v2-start", "alert_type": al.TREND_UP + "_HELD"},
           {"asset_symbol": "solana", "alert_type": al.TREND_DOWN},
           {"asset_symbol": "market:crypto", "alert_type": al.BULLISH}]
    seeds = ba.seed_latches(scans, old, {"AAPL": "Apple"})
    assert {(s["scan_id"], s["asset_key"]) for s in seeds} == {
        ("s1", "crypto:bitcoin"), ("s1", "equity:AAPL"), ("s2", "crypto:solana")}


def test_plan_opens_once_and_rearms_only_on_the_rearm_set():
    rows = [{"kind": "crypto", "id": "a", "answer": "yes", "rearm": "no"},
            {"kind": "crypto", "id": "b", "answer": "no", "rearm": "no"},     # a wobble: still latched
            {"kind": "crypto", "id": "c", "answer": "no", "rearm": "yes"},    # back 20 points: re-armed
            {"kind": "crypto", "id": "d", "answer": "yes", "rearm": "no"}]
    opens, releases = ba.plan(rows, {"crypto:b", "crypto:c", "crypto:d"})
    assert opens == ["crypto:a"] and releases == ["crypto:c"]


def test_bars_ready_at_each_close():
    crypto_cut = pd.Timestamp("2026-11-07 00:00", tz="UTC")
    assert ba.bars_ready(pd.Timestamp("2026-11-06"), "crypto", crypto_cut)
    assert not ba.bars_ready(pd.Timestamp("2026-11-05"), "crypto", crypto_cut)
    share_cut = pd.Timestamp("2026-11-06 16:00", tz="America/New_York").tz_convert("UTC")
    assert ba.bars_ready(pd.Timestamp("2026-11-06"), "equity", share_cut)
    assert not ba.bars_ready(pd.Timestamp("2026-11-05"), "equity", share_cut)


def test_notes_keep_the_old_words_and_respect_the_channel():
    row = {"id": "AAPL", "asset": "Apple (AAPL)", "value": 62.4}
    n = ba.note("u1", "trend_up", row, "account", "2026-11-07T00:10:00Z")
    assert n["alert_type"] == al.TREND_UP and n["asset_symbol"] == "aapl" and n["message"].startswith("Trend turned up: +62")
    assert "emailed_at" not in n and "digested_at" not in n
    assert "emailed_at" in ba.note("u1", "trend_up", row, "digest", "t") and "digested_at" not in ba.note("u1", "trend_up", row, "digest", "t")
    assert {"emailed_at", "digested_at"} <= set(ba.note("u1", "trend_up", row, "app", "t"))


class FakeStore:
    def __init__(self, latched=()):
        self.claims, self.latched, self.inserted, self.resolved, self.finished = set(), set(latched), [], [], []
        self.quiet_cleared = []

    def claim(self, scan_id, market, cutoff, now):
        key = (scan_id, market, cutoff)
        if key in self.claims:
            return None
        self.claims.add(key)
        return len(self.claims)

    def latches(self, scan_id):
        return set(self.latched)

    def open_latches(self, scan_id, keys, cutoff):
        self.latched |= set(keys)

    def release_latches(self, scan_id, keys):
        self.latched -= set(keys)

    def resolve(self, owner, alert_type, ids):
        self.resolved += ids

    def notes(self, rows):
        self.inserted += rows
        return rows

    def clear_quiet(self, scan_id):
        self.quiet_cleared.append(scan_id)

    def finish(self, run_id, fields):
        self.finished.append(fields)

    def touch(self, scan_id, now):
        pass

    def last_zones(self, scan_id, market):
        done = [f for f in self.finished if f.get("status") == "ok"]
        if not done:
            return None
        return {f"{r['kind']}:{r['id']}": r for r in done[-1]["results"]}

    def retire(self, owner, reading, ids):
        self.retired = getattr(self, "retired", []) + list(ids)


class FakeReadings:
    def __init__(self, last):
        self.last = last

    def context(self, kind, asset_id):
        return ("ctx", self.last)


def _scan(**extra):
    row = ba.scan_row("u1", "trend_up", 20, True, ["up_p20", "up_p50", "flip_up"])
    return {**row, "id": "s1", "quiet_next": False, **extra}


@pytest.fixture
def answers(monkeypatch):
    table = {}

    def fake(builtin, assets, readings):
        return [{"kind": k, "id": i, "asset": n, "value": table[i], "zone": al.zone(table[i])} for k, i, n in assets]
    monkeypatch.setattr(ba, "zones", fake)
    return table


def _run(store, assets, now, **scan):
    return ba.run_account(store, "u1", [_scan(**scan)], (assets, {}), FakeReadings(pd.Timestamp(now) - pd.Timedelta(hours=24, minutes=15)), now=pd.Timestamp(now))


def test_a_new_colour_alerts_once_it_holds_at_the_next_close(answers):
    store = FakeStore()
    coins = {"bitcoin": "Bitcoin", "solana": "Solana"}
    answers.update({"bitcoin": 10.0, "solana": 30.0})
    first = _run(store, coins, "2026-11-07 00:15+00:00")
    assert first["ran"] == 1 and not first["notes"]                 # the first run notes the colours quietly
    answers.update({"bitcoin": 25.0, "solana": 31.0})               # Bitcoin turns bullish, once
    assert not _run(store, coins, "2026-11-08 00:15+00:00")["notes"]
    answers.update({"bitcoin": 27.0})                               # held at the next close: alert
    out = _run(store, coins, "2026-11-09 00:15+00:00")
    assert [n["asset_symbol"] for n in out["notes"]] == ["bitcoin"]
    assert out["notes"][0]["message"].startswith("Trend turns bullish (leaves neutral): +27 (Uptrend), was no clear trend")
    assert store.retired == ["bitcoin"]
    assert not _run(store, coins, "2026-11-10 00:15+00:00")["notes"]                    # no new crossing
    again = _run(store, coins, "2026-11-10 00:20+00:00")
    assert again["ran"] == 0                                        # the same close never runs twice


def test_a_flicker_never_alerts_and_a_jump_is_one_alert(answers):
    store = FakeStore()
    coins = {"bitcoin": "Bitcoin"}
    answers["bitcoin"] = -30.0
    _run(store, coins, "2026-11-07 00:15+00:00")
    answers["bitcoin"] = 5.0                                        # one close in neutral, then back
    _run(store, coins, "2026-11-08 00:15+00:00")
    answers["bitcoin"] = -28.0
    assert not _run(store, coins, "2026-11-09 00:15+00:00")["notes"]
    answers["bitcoin"] = 60.0                                       # bearish to strongly bullish: one flip alert
    _run(store, coins, "2026-11-10 00:15+00:00")
    out = _run(store, coins, "2026-11-11 00:15+00:00")
    assert len(out["notes"]) == 1 and "flips from bearish to bullish" in out["notes"][0]["message"]


def test_waits_for_the_closed_bar_then_runs_quietly_when_switched_on(answers):
    answers.update({"bitcoin": 70.0})
    store = FakeStore(latched={"crypto:bitcoin"})
    early = pd.Timestamp("2026-11-07 00:15", tz="UTC")
    out = ba.run_account(store, "u1", [_scan()], ({"bitcoin": "Bitcoin"}, {}),
                         FakeReadings(pd.Timestamp("2026-11-05")), now=early)
    assert out["ran"] == 0                                          # yesterday's bar hasn't arrived
    quiet = ba.run_account(store, "u1", [_scan(quiet_next=True)], ({"bitcoin": "Bitcoin"}, {}),
                           FakeReadings(pd.Timestamp("2026-11-06")), now=early)
    assert quiet["ran"] == 1 and not quiet["notes"] and store.quiet_cleared
    assert store.latched == set()                                   # the old single-line latches are let go


def test_an_alert_that_is_off_does_not_run(answers):
    store = FakeStore()
    off = _scan(notify={"channel": "off"})
    out = ba.run_account(store, "u1", [off], ({"bitcoin": "Bitcoin"}, {}), FakeReadings(pd.Timestamp("2026-11-06")),
                         now=pd.Timestamp("2026-11-07 00:15", tz="UTC"))
    assert out["ran"] == 0 and not store.claims


def test_the_scan_reads_exactly_the_dashboard_numbers():
    """The built-in Set, run on the stored bars, agrees with the dashboard's Trend reading on every day."""
    import group_readings as gr
    from signal_library import certify as cf
    from signal_library import engine
    from tests.replay_helpers import full_indicators

    frame = full_indicators(cf.synthetic_crypto(days=420, seed=11).histories["1D"].raw)
    checked = 0
    for pos in range(260, len(frame) + 1, 7):
        window = frame.iloc[:pos]
        now = window.index[-1] + pd.Timedelta(days=3)
        engine.clear_cache()
        dashboard = gr.score(window, "crypto", now)["clusters"]["trend"]["value"]

        class Stored(ba.Readings):
            def context(self, kind, asset_id):
                return gr.stored_context(window, kind, now, asset_id=asset_id)

        engine.clear_cache()
        row = ba.evaluate(ba.set_doc("trend_up", 20), ba.rearm_doc("trend_up", 20), "trend_up",
                          [("crypto", "x", "X")], Stored(None))[0]
        if dashboard is None:
            continue
        assert row["value"] == pytest.approx(dashboard * 100, abs=1e-9)
        assert row["answer"] == ("yes" if dashboard * 100 >= 20 else "no")
        assert row["rearm"] == ("yes" if dashboard * 100 <= 0 else "no")
        checked += 1
    assert checked > 10
