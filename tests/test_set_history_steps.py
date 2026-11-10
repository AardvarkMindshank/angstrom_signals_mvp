"""Visualize History fills older years in steps for every asset in turn (asked 10 Nov 2026): 3Y opens once every
asset has 3 years, then 10Y, then All."""

import pandas as pd

import set_history as sh


def _frame(years):
    idx = pd.date_range(end="2026-11-09", periods=365 * years, freq="1D", tz="UTC")
    return pd.DataFrame({"close": range(len(idx))}, index=idx)


def test_every_asset_reaches_3_years_before_any_goes_to_10(monkeypatch):
    frames = {"a": _frame(12), "b": _frame(12)}

    def answers(doc, frame, kind, asset_id, start=None, subjects=None, **k):
        first = pd.Timestamp(start) if start is not None else frame.index[60]
        return [(d.strftime("%Y-%m-%d"), "yes" if d.month % 2 else "no") for d in frame.index if d >= first]

    monkeypatch.setattr(sh, "daily_answers", answers)
    monkeypatch.setattr(sh, "load", lambda *a, **k: {})
    monkeypatch.setattr(sh, "save", lambda *a, **k: None)
    monkeypatch.setattr(sh, "history_for", lambda sb, doc, kind, i, fr: sh.spans(answers(doc, frames[i], kind, i)))
    monkeypatch.setattr(sh, "subjects_of", lambda doc: [])
    import column_answers
    monkeypatch.setattr(column_answers, "def_hash", lambda doc: "h")
    get = lambda kind, i: frames[i]
    strip = sh.quick_rows(None, {}, [("crypto", "a", "A"), ("crypto", "b", "B")], frames=get)
    assert strip["covered"] == 1 and sh.covers(strip, 1) and not sh.covers(strip, 3)
    sh.complete_row(None, {}, strip, frames=get)
    assert not sh.covers(strip, 3)                     # only A has 3 years so far
    sh.complete_row(None, {}, strip, frames=get)
    assert sh.covers(strip, 3) and not sh.covers(strip, 10)
    sh.complete_row(None, {}, strip, frames=get)
    sh.complete_row(None, {}, strip, frames=get)
    assert sh.covers(strip, 10) and not sh.covers(strip, 0)
    a = next(r for r in strip["rows"] if r["id"] == "a")
    assert a["spans"][0][0] <= "2016-11-20"           # ten years back, joined to the newer spans without gaps
    for (f1, l1, x1), (f2, l2, x2) in zip(a["spans"], a["spans"][1:]):
        assert x1 != x2 and pd.Timestamp(f2) - pd.Timestamp(l1) == pd.Timedelta(days=1)
    sh.complete_row(None, {}, strip, frames=get)
    sh.complete_row(None, {}, strip, frames=get)
    assert strip["pending"] == 0 and sh.covers(strip, 0)
