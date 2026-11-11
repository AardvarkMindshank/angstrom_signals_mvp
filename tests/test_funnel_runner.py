"""The funnel job (funnel_runner.py) with a fake database and fake Set answers."""

import pandas as pd

import funnel as fn
import funnel_runner as fr

STAGES = [{"label": "Daily", "timeframe": "1D", "set_body": {"n": 0}}, {"label": "12h", "timeframe": "12h",
          "set_body": {"n": 1}}, {"label": "Shortlist", "timeframe": "4h", "set_body": {"n": 2}},
          {"label": "Entry", "timeframe": "1h", "set_body": {"n": 3}}]
FUNNEL = {"id": "f1", "owner_id": "u1", "name": "Trend longs", "direction": "long", "stages": STAGES,
          "flicker": True, "stages_version": 1}
UNIVERSE = {"bitcoin": {"symbol": "BTC", "name": "Bitcoin"}, "solana": {"symbol": "SOL", "name": "Solana"},
            "dogecoin": {"symbol": "DOGE", "name": "Dogecoin"}}


class Store:
    def __init__(self):
        self.runs, self.saved, self.notes = {}, {}, []

    def universe(self, market="crypto"):
        return UNIVERSE if market == "crypto" else {"AAPL": {"symbol": "AAPL", "name": "Apple"}}

    def active_funnels(self):
        return [FUNNEL]

    def coins(self, fid):
        return {c: {"stages_version": v, "state": st.to_dict()} for c, (v, st) in self.saved.items()}

    def claim(self, fid, stage, cutoff, started, **kw):
        key = (fid, stage, cutoff)
        if key in self.runs:
            return None
        self.runs[key] = {}
        return key

    def finish(self, run_id, fields):
        self.runs[run_id].update(fields)

    def notify(self, rows):
        self.notes += rows

    def refresh_sentiment(self, market, items, log=print):
        self.sentiment = getattr(self, "sentiment", []) + [i[0] for i in items]
        return len(items)

    def save_coins(self, fid, version, states):
        self.saved.update({c: (version, st) for c, st in states.items()})


def _evaluate(answers):
    """answers: {stage: {coin: answer}}; checked: what each stage was asked about."""
    checked = {}

    def evaluate(doc, assets, cutoff):
        checked.setdefault(doc["n"], []).extend(a[1] for a in assets)
        return [{"id": a[1], "answer": answers[doc["n"]].get(a[1], "no"), "reason": "line"} for a in assets]
    return evaluate, checked


def test_one_pass_narrows_and_alerts_once():
    store = Store()
    store.saved["dogecoin"] = (1, fn.CoinState.new(4))          # the funnel has run before: not its first pass
    ev, checked = _evaluate({0: {"bitcoin": "yes", "solana": "yes"}, 1: {"bitcoin": "yes", "solana": "yes"},
                             2: {"bitcoin": "yes", "solana": "yes"}, 3: {"bitcoin": "yes"}})
    now = pd.Timestamp("2026-11-10 00:20", tz="UTC")              # every stage has a close at 00:00
    out = fr.run_all(store, ev, now=now)
    assert out["f1"]["stages_run"] == 4
    assert sorted(checked[0]) == ["bitcoin", "dogecoin", "solana"] and sorted(checked[1]) == ["bitcoin", "solana"]
    places = {c: fn.place(st)["status"] for c, (_, st) in store.saved.items()}
    assert places == {"bitcoin": "candidate", "solana": "flagged", "dogecoin": "pool"}
    assert len(store.notes) == 1 and "Bitcoin (BTC)" in store.notes[0]["message"]
    assert store.sentiment == ["bitcoin"]                         # news sentiment for the new Candidate only
    # The same closes again: nothing is claimed twice, nothing alerts twice.
    assert fr.run_all(store, ev, now=now)["f1"]["stages_run"] == 0 and len(store.notes) == 1
    # An hour on, only the 1-hour stage is due, for the coins holding the first three stages.
    checked.clear()
    out = fr.run_all(store, ev, now=pd.Timestamp("2026-11-10 01:20", tz="UTC"))
    assert out["f1"]["stages_run"] == 1 and sorted(checked[3]) == ["bitcoin", "solana"]
    # Bitcoin is still latched (no new alert) and still a Candidate, so it stays on the sentiment list (refreshed
    # only when its reading is over 12 hours old); Solana, never a Candidate, never is.
    assert len(store.notes) == 1 and store.sentiment == ["bitcoin"] * 3     # one per pass; the store skips fresh ones


def test_a_new_version_starts_silently():
    store = Store()                                              # nothing saved yet: the first pass of this version
    ev, _ = _evaluate({0: {"bitcoin": "yes"}, 1: {"bitcoin": "yes"}, 2: {"bitcoin": "yes"}, 3: {"bitcoin": "yes"}})
    out = fr.run_all(store, ev, now=pd.Timestamp("2026-11-10 00:20", tz="UTC"), log=lambda *_: None)
    assert store.notes == [] and out["f1"]["bootstrap"] == 1
    assert fn.place(store.saved["bitcoin"][1])["status"] == "candidate" and store.saved["bitcoin"][1].latched


def test_a_coin_that_leaves_the_candidates_gets_no_more_sentiment():
    store = Store()
    ev, _ = _evaluate({0: {"bitcoin": "yes"}, 1: {"bitcoin": "yes"}, 2: {"bitcoin": "yes"}, 3: {"bitcoin": "yes"}})
    fr.run_all(store, ev, now=pd.Timestamp("2026-11-10 00:20", tz="UTC"))
    ev2, _ = _evaluate({3: {}})                                    # the 1-hour entry says No twice
    fr.run_all(store, ev2, now=pd.Timestamp("2026-11-10 01:20", tz="UTC"))
    fr.run_all(store, ev2, now=pd.Timestamp("2026-11-10 02:20", tz="UTC"))
    before = list(store.sentiment)
    fr.run_all(store, ev2, now=pd.Timestamp("2026-11-10 03:20", tz="UTC"))
    assert store.sentiment == before


def test_a_failed_stage_keeps_places_and_is_recorded():
    store = Store()

    def broken(doc, assets, cutoff):
        raise RuntimeError("Binance down")
    out = fr.run_all(store, broken, now=pd.Timestamp("2026-11-10 00:20", tz="UTC"), log=lambda *_: None)
    assert out["f1"]["failed"] == 1 and any(r.get("status") == "failed" for r in store.runs.values())


def test_closes_and_wording():
    now = pd.Timestamp("2026-11-10 13:05", tz="UTC")              # 12h close at 12:00 is settled
    assert fr.latest_close("12h", now) == pd.Timestamp("2026-11-10 12:00", tz="UTC")
    assert fr.latest_close("1h", pd.Timestamp("2026-11-10 13:05", tz="UTC")) == pd.Timestamp("2026-11-10 12:00", tz="UTC")
    h = fr.hover(FUNNEL)
    assert h["flagged"] == ("On the shortlist: the daily, 12-hour and 4-hour agree; waiting for the 1-hour entry "
                            "conditions.")


def test_share_closes_follow_the_new_york_session():
    ny = lambda t: pd.Timestamp(t, tz="America/New_York")
    # Tuesday 10 Nov 2026, 12:00 New York: last hourly close 11:30, last 4-hour close the day before at 16:00.
    now = ny("2026-11-10 12:00").tz_convert("UTC")
    assert fr.latest_close("1h", now, "equity") == ny("2026-11-10 11:30").tz_convert("UTC")
    assert fr.latest_close("4h", now, "equity") == ny("2026-11-09 16:00").tz_convert("UTC")
    assert fr.latest_close("1D", now, "equity") == ny("2026-11-09 16:00").tz_convert("UTC")
    # The week closes on Friday 6 Nov.
    assert fr.latest_close("1W", now, "equity") == ny("2026-11-06 16:00").tz_convert("UTC")
    # Thanksgiving (26 Nov) is skipped; the next day closes early at 13:00.
    friday = ny("2026-11-27 18:00").tz_convert("UTC")
    assert fr.latest_close("1D", friday, "equity") == ny("2026-11-27 13:00").tz_convert("UTC")
    assert fr.latest_close("1D", ny("2026-11-26 18:00").tz_convert("UTC"), "equity") == ny("2026-11-25 16:00").tz_convert("UTC")
    # A week with a Friday holiday (Good Friday, 3 Apr 2026) closes on Thursday.
    assert fr.latest_close("1W", ny("2026-04-04 12:00").tz_convert("UTC"), "equity") == ny("2026-04-02 16:00").tz_convert("UTC")


def test_the_holiday_list_covers_the_coming_year():
    year = pd.Timestamp.now().year + (1 if pd.Timestamp.now().month >= 11 else 0)
    assert any(d.startswith(str(year)) for d in fr.US_HOLIDAYS), f"Add the NYSE holidays for {year}"


def test_an_equity_funnel_checks_shares():
    store = Store()
    seen = []

    def ev(doc, assets, cutoff):
        seen.extend(assets)
        return [{"id": a[1], "answer": "yes"} for a in assets]
    eq = {**FUNNEL, "id": "f2", "market": "equity"}
    store.active_funnels = lambda: [eq]
    fr.run_all(store, ev, now=pd.Timestamp("2026-11-10 22:00", tz="UTC"))
    assert seen and all(a[0] == "equity" and a[1] == "AAPL" for a in seen)


def test_shared_answers_are_read_not_worked_out_again():
    class Shared(Store):
        def __init__(self):
            super().__init__()
            self.answers = {}

        def get_answers(self, lh, code, keys, cutoff):
            return {k: v for (h, c, k, t), v in self.answers.items() if (h, c, t) == (lh, code, cutoff.isoformat())
                    and k in keys}

        def put_answers(self, rows):
            for r in rows:
                self.answers[(r["logic_hash"], r["code_id"], r["asset_key"], r["cutoff"])] = r

    store = Shared()
    calls = []

    def ev(doc, assets, cutoff):
        calls.extend(a[1] for a in assets)
        return [{"id": a[1], "answer": "yes" if a[1] != "dogecoin" else "unknown",
                 "reason": "Not evaluated: provider down" if a[1] == "dogecoin" else "ok"} for a in assets]
    now = pd.Timestamp("2026-11-10 00:20", tz="UTC")
    stage = STAGES[0]["set_body"]
    fr.shared_evaluate(store, ev, stage, [("crypto", c, c) for c in ("bitcoin", "dogecoin")], fr.latest_close("1D", now))
    assert calls == ["bitcoin", "dogecoin"]
    rows = fr.shared_evaluate(store, ev, stage, [("crypto", c, c) for c in ("bitcoin", "dogecoin")],
                              fr.latest_close("1D", now))
    assert calls == ["bitcoin", "dogecoin", "dogecoin"]         # the failure is tried again; Bitcoin is read
    assert {r["id"]: r["answer"] for r in rows} == {"bitcoin": "yes", "dogecoin": "unknown"}
    renamed = {**stage, "name": "Another name"}
    fr.shared_evaluate(store, ev, renamed, [("crypto", "bitcoin", "b")], fr.latest_close("1D", now))
    assert calls.count("bitcoin") == 1                          # a renamed copy shares the answer


def test_leaving_the_pool_is_not_a_failure_and_returning_starts_again():
    store = Store()
    store.saved["dogecoin"] = (1, fn.CoinState.new(4))
    ev, _ = _evaluate({0: {"bitcoin": "yes", "solana": "yes"}, 1: {"bitcoin": "yes", "solana": "yes"},
                       2: {"bitcoin": "yes", "solana": "yes"}, 3: {"bitcoin": "yes", "solana": "yes"}})
    fr.run_all(store, ev, now=pd.Timestamp("2026-11-10 00:20", tz="UTC"))
    notes = len(store.notes)
    gone = dict(UNIVERSE)
    gone.pop("solana")
    store.universe = lambda market="crypto": gone
    fr.run_all(store, ev, now=pd.Timestamp("2026-11-10 01:20", tz="UTC"), log=lambda *_: None)
    sol = store.saved["solana"][1]
    assert sol.left_pool and fn.place(sol)["depth"] == 0 and len(store.notes) == notes
    store.universe = lambda market="crypto": UNIVERSE
    fr.run_all(store, ev, now=pd.Timestamp("2026-11-10 02:20", tz="UTC"), log=lambda *_: None)
    assert not store.saved["solana"][1].left_pool


def test_accounts_take_turns():
    fs = [{"id": f"a{i}", "owner_id": "a", "stages": STAGES} for i in range(3)] + [{"id": "b0", "owner_id": "b",
                                                                                    "stages": STAGES}]
    assert [f["id"] for f in fr.fair_order(fs)][:2] in (["a0", "b0"], ["a1", "b0"], ["a2", "b0"])


def test_pool_rules():
    uni = {c: {"rank": r, "volume_usd": v} for c, r, v in (("btc", 1, 9e9), ("eth", 2, 5e9), ("tiny", 300, 3e5),
                                                           ("doge", 9, 8e8))}
    assert set(fr.pool_members(uni, {"top": 2})) == {"btc", "eth"}
    assert set(fr.pool_members(uni, {"min_volume": 1e6})) == {"btc", "eth", "doge"}
    assert set(fr.pool_members(uni, {"watchlist_only": True}, {"doge", "tiny"})) == {"doge", "tiny"}
    assert fr.pool_members(uni, {}) == uni


def test_the_account_switch_stops_funnel_alerts():
    store = Store()
    store.saved["dogecoin"] = (1, fn.CoinState.new(4))           # not the first pass
    store.alerts_on = lambda owner: False
    ev, _ = _evaluate({0: {"bitcoin": "yes"}, 1: {"bitcoin": "yes"}, 2: {"bitcoin": "yes"}, 3: {"bitcoin": "yes"}})
    fr.run_all(store, ev, now=pd.Timestamp("2026-11-10 00:20", tz="UTC"))
    assert store.notes == [] and fn.place(store.saved["bitcoin"][1])["status"] == "candidate"


def test_a_new_version_checks_the_current_close_again():
    run = {"status": "ok", "started_at": "2026-11-11T00:05:00+00:00", "answers": {"yes": 3, "version": 1}}
    assert fr.earlier_version(run, 2, None) and not fr.earlier_version(run, 1, None)
    old = {"status": "ok", "started_at": "2026-11-11T00:05:00+00:00", "answers": {"yes": 3}}      # before versions
    assert fr.earlier_version(old, 2, "2026-11-11T16:00:00+00:00")
    assert not fr.earlier_version(old, 2, "2026-11-10T16:00:00+00:00")       # ran after the last save
    assert not fr.earlier_version({**run, "status": "running"}, 2, None)    # stale-claim rules handle running ones
    assert not fr.earlier_version(run, None, None)


def test_the_same_close_twice_counts_once():
    st = fn.CoinState.new(4)
    fn.record(st, 0, fn.YES, "2026-11-10T00:00:00+00:00")
    fn.record(st, 0, fn.NO, "2026-11-11T00:00:00+00:00")
    fn.record(st, 0, fn.NO, "2026-11-11T00:00:00+00:00")                     # a re-run of the same close
    assert st.stages[0].held and st.stages[0].no_run == 1
    fn.record(st, 0, fn.NO, "2026-11-12T00:00:00+00:00")
    assert not st.stages[0].held
