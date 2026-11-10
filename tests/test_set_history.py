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


class _Db:
    """Enough of Supabase for set_history: one table kept in a dict."""

    def __init__(self):
        self.rows, self.writes = {}, 0

    def table(self, name):
        db = self

        class Q:
            def select(self, *a):
                return self

            def in_(self, *a):
                return self

            def upsert(self, row, **k):
                db.rows[(row["def_hash"], row["asset_key"])] = row
                db.writes += 1
                return self

            def execute(self):
                self.data = list(db.rows.values())
                return self
        return Q()


def test_history_is_saved_once_and_only_new_days_are_worked_out(monkeypatch):
    f = _frame(3, 500)
    doc = prism.library_sets()["demo:squeeze"]
    db = _Db()
    frames = {"full": f.iloc[:480]}
    first = sh.history_for(db, doc, "crypto", "x", frames=lambda k, i: frames["full"])
    assert db.writes == 1 and sh.through(first) == f.index[479].strftime("%Y-%m-%d")
    assert sh.history_for(db, doc, "crypto", "x", frames=lambda k, i: frames["full"]) == first and db.writes == 1
    calls = []
    real = sh.daily_answers
    monkeypatch.setattr(sh, "daily_answers", lambda *a, **k: calls.append(k.get("start")) or real(*a, **k))
    longer = f
    frames["full"] = longer
    again = sh.history_for(db, doc, "crypto", "x", frames=lambda k, i: frames["full"])
    assert db.writes == 2 and calls and calls[0] is not None            # only the new days
    assert sh.through(again) == longer.index[-1].strftime("%Y-%m-%d")


def test_strip_rows_cover_every_asset():
    f = _frame(11, 500)
    doc = prism.library_sets()["demo:squeeze"]
    seen = []
    strip = sh.strip_rows(None, doc, [("crypto", "a", "A"), ("equity", "b", "B")],
                          progress=lambda n, t, name: seen.append(name), frames=lambda k, i: None if i == "b" else f)
    assert [r["name"] for r in strip["rows"]] == ["A", "B"] and seen == ["A", "B"]
    assert strip["rows"][0]["spans"] and strip["rows"][1]["spans"] == []
    assert strip["start"] == strip["rows"][0]["spans"][0][0]


def test_first_look_is_the_last_year_then_older_years_fill_in():
    f = _frame(3, 900)
    doc = prism.library_sets()["demo:squeeze"]
    db = _Db()
    frames = lambda k, i: f
    strip = sh.quick_rows(db, doc, [("crypto", "a", "A"), ("crypto", "b", "B")], frames=frames)
    assert strip["pending"] == 2 and db.writes == 0                       # partial years are never saved
    first = pd.Timestamp(strip["start"])
    assert first >= f.index[-1].tz_localize(None) - pd.Timedelta(days=sh.QUICK_DAYS + 1)
    # Older years come in steps, every asset in turn (A to 3 years, B to 3 years, ...); a finished one is saved.
    assert sh.complete_row(db, doc, strip, frames) == "A"
    assert pd.Timestamp(strip["start"]) < first                          # A now reaches back further
    assert sh.complete_row(db, doc, strip, frames) == "B"
    for _ in range(4):
        sh.complete_row(db, doc, strip, frames)
    assert strip["pending"] == 0 and db.writes == 2 and sh.complete_row(db, doc, strip, frames) is None
    # Filled in by steps, the history is exactly the one worked out in one go.
    whole = sh.spans(sh.daily_answers(doc, f, "crypto", "a"))
    assert strip["rows"][0]["spans"] == whole
    # Next time both are saved: whole histories at once, nothing pending.
    again = sh.quick_rows(db, doc, [("crypto", "a", "A"), ("crypto", "b", "B")], frames=frames)
    assert again["pending"] == 0 and again["rows"][0]["spans"] == strip["rows"][0]["spans"]


def test_history_chart_panes_can_be_tapped():
    import history_chart as hc

    f = _frame(3, 500)
    doc = prism.library_sets()["demo:squeeze"]
    strip = sh.strip_rows(None, doc, [("crypto", "a", "A"), ("crypto", "b", "B")], frames=lambda k, i: f)
    data = hc.payload(strip, "crypto:b", 0, frames=lambda k, i: f)
    assert data["pane_keys"] == ["crypto:b", "crypto:a"] and data["log_scale"]
    assert len(data["panes"]) == 2 and data["series"][-1]["zones"]
