"""Prism · Run now (docs/design/lattice_prism.md §5.1, build stage 2). Synthetic data only."""

from __future__ import annotations

import copy

import pandas as pd
import pytest

import prism
import signal_groups as sg
from signal_library import DataContext, engine
from signal_library import certify as cf
from tests.replay_helpers import full_indicators


def setup_function(_):
    engine.clear_cache()


def _live(seed_of=None):
    def make(kind, asset_id):
        seed = (seed_of or {}).get(asset_id, sum(map(ord, asset_id)) % 7)
        frame = full_indicators(cf.synthetic_crypto(days=420, seed=seed).histories["1D"].raw)
        data = {"frame": frame.assign(forming=False), "session": None, "source": "test"}
        return DataContext(kind, asset_id, candle_loader=lambda k, a, tf: data,
                           sentiment_loader=lambda key: {"error": "no sentiment in this test"},
                           now=frame.index[-1] + pd.Timedelta(days=1))
    return make


ASSETS = [("crypto", "alpha", "Alpha"), ("crypto", "beta", "Beta"), ("crypto", "gamma", "Gamma")]


def test_demo_sets_are_valid_scannable_and_leave_the_starters_untouched():
    before = {a: sg.content_sha256(sg.starter(a)) for a in sg.STARTERS}
    for doc in prism.demo_sets().values():
        assert sg.validate_set(doc) == [] and sg.scannable(doc)
    assert {a: sg.content_sha256(sg.starter(a)) for a in sg.STARTERS} == before
    assert "outcomes" not in sg.starter("starter:trend")


def test_run_now_gives_one_row_per_asset_consistent_with_the_group_scores():
    doc = prism.demo_sets()["demo:agree"]
    rows = prism.run_now(doc, ASSETS, live_context=_live())
    assert [r["asset"] for r in rows] == ["Alpha", "Beta", "Gamma"]
    for r in rows:
        assert r["answer"] in ("yes", "no", "unknown") and r["path"] == "Live"
        assert set(r["lines"]) == {"decision.rule.all[0]", "decision.rule.all[1]"}
    ctx = _live()("crypto", "alpha")
    result = sg.evaluate_set(doc, ctx)
    trend = next(g["result"] for g in result["groups"] if g["key"] == "trend")
    expected = "bullish" if trend["score"]["value"] >= 0.3 else "bearish" if trend["score"]["value"] <= -0.3 else "neutral"
    assert trend["outcome"]["id"] == expected
    frame = prism.table(doc, rows)
    assert list(frame.columns) == ["Asset", "trend outcome is bullish", "flow outcome is bullish", "Answer",
                                   "How sure", "Why", "Data available"]


def test_missing_sentiment_gives_unknown_or_a_definite_no_never_a_guess():
    doc = prism.demo_sets()["demo:entry"]
    for r in prism.run_now(doc, ASSETS, live_context=_live()):
        assert r["lines"]["decision.rule.all[2]"].startswith("?")       # sentiment line undecided
        if r["answer"] == "no":
            assert r["how_sure"] == "Definite" and "could not change this" in r["reason"]
            assert "Asset sentiment" in r["reason"]
        else:
            assert r["answer"] == "unknown" and r["how_sure"] == "Undecided"
            assert "mood.score ≥ -20" in r["reason"] and r["available"] == "Partial"


def _result(answer, decisive, lines=None):
    return {"status": "ok", "groups": [], "standalone": [],
            "decision": {"answer": answer, "decisive": decisive, "lines": lines or decisive}}


def test_reasons_in_plain_words():
    yes = prism.row("A", _result("yes", [{"path": "p", "text": "trend outcome is bullish", "reading": "bullish",
                                         "value": "true"}]), "Live")
    assert (yes["how_sure"], yes["reason"]) == ("Definite", "Every line holds.")
    no = prism.row("A", _result("no", [{"path": "p", "text": "trend outcome is bullish", "reading": "neutral",
                                       "value": "false"}]), "Live")
    assert no["reason"] == "Fails on trend outcome is bullish (reading: neutral)." and no["lines"]["p"] == "✗ neutral"
    unknown = prism.row("A", _result("unknown", [{"path": "p", "text": "mood.score ≥ -20", "reading": None,
                                                 "value": "unknown"}]), "Live")
    assert unknown["how_sure"] == "Undecided" and unknown["reason"].startswith("Depends on mood.score")
    failed = prism.row("A", {"status": "invalid", "errors": ["bad"]}, "Live")
    assert failed["answer"] == "unknown" and failed["reason"] == "Not evaluated: bad"


def test_sets_without_a_decision_and_too_many_assets_are_refused():
    plain = copy.deepcopy(prism.demo_sets()["demo:agree"])
    del plain["decision"]
    with pytest.raises(ValueError, match="no decision"):
        prism.run_now(plain, ASSETS, live_context=_live())
    with pytest.raises(ValueError, match="At most"):
        prism.run_now(prism.demo_sets()["demo:agree"], ASSETS * 20, live_context=_live())


def test_a_refused_reconstruction_is_reported_for_that_asset_only():
    class Run:
        def context(self, kind, asset_id, as_of):
            if asset_id == "beta":
                raise RuntimeError("no candles before that date")
            return _live()(kind, asset_id)

    rows = prism.run_now(prism.demo_sets()["demo:agree"], ASSETS, live_context=None,
                         replay=(Run(), pd.Timestamp("2024-06-01", tz="UTC")))
    beta = next(r for r in rows if r["asset"] == "Beta")
    assert beta["reason"].startswith("Not evaluated") and beta["path"].startswith("Reconstruction as of 01 Jun 2024")


def _app():
    """The 🧩 Lattice · 🔎 Prism panel, switched on, with made-up candles and no database."""
    import streamlit as st

    import lattice_panel
    from signal_library import context
    from tests.test_signal_library_ta import _frame

    frames = {tf: _frame(f) for tf, f in (("15m", "15min"), ("1h", "1h"), ("4h", "4h"), ("1D", "1D"), ("1W", "7D"))}
    context.default_candle_loader = lambda kind, asset, tf: {"frame": frames[tf], "session": None, "source": "test"}

    class Empty:
        def __getattr__(self, name):
            return lambda *a, **k: self

        @property
        def data(self):
            return []

    st.session_state.setdefault("lattice_open", True)
    st.session_state.setdefault("lattice_section", "prism")
    lattice_panel.render(st, Empty(), [("crypto", "bitcoin", "Bitcoin"), ("equity", "AAPL", "Apple (AAPL)")], "test")


def test_prism_tab_runs_inside_streamlit():
    testing = pytest.importorskip("streamlit.testing.v1")
    app = testing.AppTest.from_function(_app, default_timeout=120)
    app.run()
    assert not app.exception
    run = [b for b in app.button if b.label == "Run now"]
    assert len(run) == 1
    run[0].click().run()
    assert not app.exception
    tables = [d.value for d in app.dataframe if "Answer" in d.value.columns]
    assert tables and len(tables[0]) == 2 and {"How sure", "Why", "Data available"} <= set(tables[0].columns)
    assert not [b for b in app.get("download_button") if "prism" in str(b.key)]   # display only: no export


def test_date_and_time_show_only_for_a_past_moment():
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent.joinpath("prism_view.py").read_text()
    when, form, guard, date = (src.index('"When"'), src.index('st.form("prism_form"'),
                               src.index('if mode != "Now":'), src.index('date_input("Date (UTC)"'))
    assert when < form < guard < date                     # chosen outside the form, so the page redraws at once
