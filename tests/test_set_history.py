"""A Set's answer on every past day, as bands behind the price chart (set_history.py)."""

import pandas as pd

import prism
import set_history as sh
from signal_library import certify as cf
from tests.replay_helpers import full_indicators


def _frame(seed=3, days=700):
    return full_indicators(cf.synthetic_crypto(days=days, seed=seed).histories["1D"].raw)


def test_every_day_is_answered_without_seeing_later_days():
    f = _frame()
    doc = prism.library_sets()["demo:squeeze"]
    days = sh.daily_answers(doc, f, "crypto", "x")
    assert len(days) == len(f) - 60 and {a for _, a in days} <= {"yes", "no", "unknown"}
    # The answer on a day is the same whether or not later days exist (no peeking ahead).
    cut = f.iloc[:500]
    early = dict(sh.daily_answers(doc, cut, "crypto", "x"))
    full = dict(days)
    assert all(full[d] == a for d, a in early.items())


def test_spans_join_days_and_extend():
    days = [("2024-01-01", "no"), ("2024-01-02", "no"), ("2024-01-03", "yes"), ("2024-01-04", "unknown")]
    s = sh.spans(days)
    assert s == [["2024-01-01", "2024-01-02", "no"], ["2024-01-03", "2024-01-03", "yes"],
                 ["2024-01-04", "2024-01-04", "unknown"]]
    s2 = sh.spans([("2024-01-05", "unknown"), ("2024-01-06", "yes")], s)
    assert s2[-2] == ["2024-01-04", "2024-01-05", "unknown"] and s2[-1][2] == "yes"
    assert sh.through(s2) == "2024-01-06"
    assert sh.summary(s2)["episodes"] == {"yes": 2, "no": 1, "unknown": 1}


def test_colours_follow_the_bars():
    s = [["2024-01-01", "2024-01-02", "no"], ["2024-01-03", "2024-01-05", "yes"], ["2024-01-06", "2024-01-06", "unknown"]]
    bars = ["2023-12-31", "2024-01-02", "2024-01-04", "2024-01-06", "2024-01-08"]
    assert sh.answers_for(bars, s) == [None, "no", "yes", "unknown", "unknown"]
    colours = sh.colours_for(bars, s)
    assert colours[0] is None and colours[1] is None and "34,197,94" in colours[2] and "245,158,11" in colours[3]
    assert "239,68,68" in sh.colours_for(bars, s, show_no=True)[1]


def test_weekly_and_pinned_members_answer():
    f = _frame(11, 900)
    days = dict(sh.daily_answers(prism.library_sets()["demo:alignment"], f, "crypto", "x"))
    assert "yes" in days.values() or "no" in days.values()          # weekly Trend works once enough weeks exist
    btc = dict(sh.daily_answers(prism.library_sets()["demo:btc_filter"], f, "crypto", "x",
                                subjects={("crypto", "bitcoin"): f}))
    assert {"yes", "no"} <= set(btc.values())
    lost = dict(sh.daily_answers(prism.library_sets()["demo:btc_filter"], f.iloc[:200], "crypto", "x"))
    assert set(lost.values()) == {"unknown"}                         # no Bitcoin history given: Unknown, never No
