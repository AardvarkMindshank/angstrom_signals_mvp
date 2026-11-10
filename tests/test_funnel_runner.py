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

    def universe(self):
        return UNIVERSE

    def active_funnels(self):
        return [FUNNEL]

    def coins(self, fid):
        return {c: {"stages_version": v, "state": st.to_dict()} for c, (v, st) in self.saved.items()}

    def claim(self, fid, stage, cutoff, started):
        key = (fid, stage, cutoff)
        if key in self.runs:
            return None
        self.runs[key] = {}
        return key

    def finish(self, run_id, fields):
        self.runs[run_id].update(fields)

    def notify(self, rows):
        self.notes += rows

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
    ev, checked = _evaluate({0: {"bitcoin": "yes", "solana": "yes"}, 1: {"bitcoin": "yes", "solana": "yes"},
                             2: {"bitcoin": "yes", "solana": "yes"}, 3: {"bitcoin": "yes"}})
    now = pd.Timestamp("2026-11-10 00:20", tz="UTC")              # every stage has a close at 00:00
    out = fr.run_all(store, ev, now=now)
    assert out["f1"]["stages_run"] == 4
    assert sorted(checked[0]) == ["bitcoin", "dogecoin", "solana"] and sorted(checked[1]) == ["bitcoin", "solana"]
    places = {c: fn.place(st)["status"] for c, (_, st) in store.saved.items()}
    assert places == {"bitcoin": "candidate", "solana": "flagged", "dogecoin": "pool"}
    assert len(store.notes) == 1 and "Bitcoin (BTC)" in store.notes[0]["message"]
    # The same closes again: nothing is claimed twice, nothing alerts twice.
    assert fr.run_all(store, ev, now=now)["f1"]["stages_run"] == 0 and len(store.notes) == 1
    # An hour on, only the 1-hour stage is due, for the coins holding the first three stages.
    checked.clear()
    out = fr.run_all(store, ev, now=pd.Timestamp("2026-11-10 01:20", tz="UTC"))
    assert out["f1"]["stages_run"] == 1 and sorted(checked[3]) == ["bitcoin", "solana"]
    assert len(store.notes) == 1                                   # Bitcoin is still latched


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
