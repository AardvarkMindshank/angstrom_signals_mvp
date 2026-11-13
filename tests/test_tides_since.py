"""The date the Tide's current reading began: what Your take on Tides is keyed on, so takes and comments stay until
the Tide changes."""

import tides


def test_since_uses_saved_field():
    assert tides.since({"tide": {"since": "2026-10-01", "label": "rising"}}) == "2026-10-01"


def test_since_none_without_history():
    assert tides.since({}) is None
    assert tides.since({"tide": {"label": "rising", "history": []}}) is None


def test_since_rebuilt_from_history_matches_label():
    import pandas as pd

    days = pd.bdate_range("2026-01-01", periods=60)
    hist = [(d.date().isoformat(), -0.5) for d in days[:30]] + [(d.date().isoformat(), 0.5) for d in days[30:]]
    score = pd.Series([v for _, v in hist], index=days)
    shown = tides.persist(score.apply(tides.label_for))
    label = shown.iloc[-1]
    got = tides.since({"tide": {"label": label, "history": hist}})
    assert got is not None
    assert shown.loc[got] == label
    before = shown.loc[:got].iloc[:-1]
    assert before.empty or before.iloc[-1] != label
