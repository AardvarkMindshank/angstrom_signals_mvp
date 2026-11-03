"""The selected-asset Analysis card: real evaluator results turned into words, and the card inside Streamlit."""

import json
import pathlib

import pytest

import analysis_card as ac
import signal_groups as sg
from signal_library import engine
from tests.test_signal_groups import TREND_OK, _eval

ROOT = pathlib.Path(__file__).resolve().parents[1]


def setup_function(_):
    engine.clear_cache()


class NoDb:
    """A Supabase client whose every call fails, like a missing table or a network error."""

    def table(self, name):
        raise RuntimeError(f'relation "{name}" does not exist')

    def rpc(self, *a, **k):
        raise RuntimeError("no database")


def _full_loader(missing=()):
    from tests.test_signal_library_ta import _frame

    frames = {tf: _frame(f) for tf, f in (("15m", "15min"), ("1h", "1h"), ("4h", "4h"), ("1D", "1D"), ("1W", "7D"))}

    def loader(kind, asset, tf):
        if tf in missing:
            return {"error": f"no {tf} candles"}
        return {"frame": frames[tf], "session": None, "source": "test"}
    return loader


# ------------------------------------------------------------------------------- scored and unscored Groups

def test_example_set_runs_through_the_real_evaluator():
    doc = ac.example_set()
    result = ac.evaluate(doc, "crypto", "bitcoin", NoDb(), candle_loader=_full_loader())
    assert result["score"] is None  # no Set score
    entries = ac.group_entries(doc, result)
    assert [e["key"] for e in entries] == ["trend", "reversal"]
    trend, reversal = (e["result"] for e in entries)
    assert trend["score"] is not None and reversal["score"] is None
    rows = ac.group_row(entries[0]) + ac.group_row(entries[1])
    assert "No score" in rows and "Is there a trend" in rows
    # Evidence is removed before the result is kept in the session.
    assert "\"evidence\":" not in json.dumps(result)
    # The score shown is the evaluator's own number.
    if trend["score"]["value"] is not None:
        assert f"{round(trend['score']['value'] * 100):+d}" in ac.score_html(trend)


def test_withheld_score_says_why():
    r = _eval(sg.starter("starter:trend-confirmation"), {**TREND_OK, "structure_1d": "MISSING", "trend_4h": "MISSING"})
    assert r["status"] == "insufficient"
    html = ac.score_html(r)
    assert "Score withheld" in html and "Not enough of the scoring signals" in html
    row = ac.group_row({"key": "trend", "purpose": "", "result": r})
    assert "Not enough data" in row


# ------------------------------------------------------------------------------- conditions, vetoes, unknowns

def test_confirmations_and_unknown_veto_are_shown_apart_from_the_score():
    r = _eval(sg.starter("starter:trend-confirmation"),
              {**TREND_OK, "structure_1d": {"structure": "up"}, "regime_1d": "MISSING"})
    assert r["status"] == "veto_unknown" and r["score"]["value"] > 0
    chips = ac.condition_chips(r)
    assert "Bullish confirmed: Met" in chips and "Bearish confirmed: Not met" in chips and "Ranging veto: Unknown" in chips
    assert "Veto: Daily regime is ranging" in chips  # the hover says what kind of condition it is
    details = ac.group_details(r)
    assert details.index("Confirmations") < details.index("Vetoes")
    assert ac.SEPARATE_NOTE.split(":")[0] in details
    row = ac.group_row({"key": "trend", "purpose": "", "result": r})
    assert "Veto unknown" in row and "Evaluated" not in row  # a positive score does not read as cleared


def test_active_veto():
    r = _eval(sg.starter("starter:trend-confirmation"), {**TREND_OK, "regime_1d": {"state": "ranging"}})
    assert r["status"] == "vetoed"
    assert "Ranging veto: Active" in ac.condition_chips(r) and "Vetoed" in ac.group_row({"key": "t", "result": r})


# ------------------------------------------------------------------------------- missing, incorrect, stale data

def test_missing_and_unmappable_values_are_explained():
    doc = sg.starter("starter:trend-confirmation")
    doc["members"][2]["when_unavailable"] = "neutral"
    r = _eval(doc, {**TREND_OK, "structure_1d": {"structure": "nonsense"}, "trend_4h": "MISSING"})
    details = ac.group_details(r)
    assert "could not be mapped to a score" in details  # an unexpected value is not turned into a number
    assert "Data missing" in details and "Left out of the score" in details
    assert "Counted as neutral" in details
    assert "No usable data from: trend_4h" in details


def test_stale_signal_is_not_counted_and_says_so():
    from tests.test_signal_groups import _ctx, _results, _result

    doc = sg.starter("starter:trend-confirmation")
    results = _results(doc, TREND_OK)
    stale_key = next(k for k in results if "trend.direction" in k and "1D" in k)
    stale = _result("up", "stale")
    stale.notes = ["Last candle is 3 days old"]
    results[stale_key] = stale
    r = sg.evaluate_group(doc, _ctx(), results=results)
    row = next(m for m in r["members"] if m["key"] == "trend_1d")
    assert row["state"] == "excluded"
    details = ac.group_details(r)
    assert "Out of date: Last candle is 3 days old" in details


def test_missing_candles_make_the_set_report_unavailable_signals():
    doc = ac.example_set()
    result = ac.evaluate(doc, "crypto", "bitcoin", NoDb(), candle_loader=_full_loader(missing=("4h",)))
    trend = ac.group_entries(doc, result)[0]["result"]
    assert "momentum_4h" in trend["diagnostics"]["timing"]["unavailable"]
    assert any(c["state"] == "unknown" for c in trend["conditions"])


# ------------------------------------------------------------------------------- asset-specific context

def test_bitcoin_context_is_labelled_and_not_shown_for_shares():
    doc = ac.example_set()
    crypto = ac.evaluate(doc, "crypto", "ethereum", NoDb(), candle_loader=_full_loader())
    html = ac.context_html(crypto, "crypto", "Ethereum")
    assert "Market backdrop (Bitcoin)" in html and "not a reading of Ethereum" in html
    assert "More on Ethereum" in html and "Timeframe alignment" in html
    shares = ac.evaluate(doc, "equity", "AAPL", NoDb(), candle_loader=_full_loader())
    assert shares["market_context"][0]["skipped"].startswith("applies to crypto")
    assert "Bitcoin" not in ac.context_html(shares, "equity", "Apple (AAPL)")


# ------------------------------------------------------------------------------- Set selection and errors

def test_saved_sets_fall_back_to_the_built_in_set():
    sets, problem = ac.readable_sets(NoDb())
    assert [k for k, _, _ in sets] == [ac.EXAMPLE_KEY] and "could not be loaded" in problem


def test_saved_sets_are_listed_at_their_current_version():
    body = ac.example_set()

    class Query:
        def __init__(self, rows):
            self.rows = rows

        def __getattr__(self, name):
            return lambda *a, **k: self

        def execute(self):
            return type("R", (), {"data": self.rows})()

    class Db:
        def table(self, name):
            if name == "analysis_configs":
                return Query([{"id": "c1", "name": "Mine", "current_version": 2}])
            return Query([{"config_id": "c1", "version": 1, "body": {"old": True}},
                          {"config_id": "c1", "version": 2, "body": body}])

    sets, problem = ac.readable_sets(Db())
    assert problem is None and sets[1] == ("saved:c1:2", "Mine (v2)", body)


def test_invalid_set_is_reported_not_evaluated():
    bad = ac.example_set()
    bad["score"] = {"method": "weighted_mean"}
    result = ac.evaluate(bad, "crypto", "bitcoin", NoDb(), candle_loader=_full_loader())
    assert result["status"] == "invalid" and result["errors"]


def _app(fail=False):
    import streamlit as st

    import analysis_card
    from tests.test_analysis_card import NoDb, _full_loader

    loader = _full_loader()
    if fail:
        def loader(*a):
            raise MemoryError("boom")
        analysis_card.evaluate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("evaluator crashed"))
    analysis_card.render(st, NoDb(), "Crypto", "bitcoin", "Bitcoin", candle_loader=loader)


def test_card_runs_inside_streamlit_only_on_request():
    testing = pytest.importorskip("streamlit.testing.v1")
    app = testing.AppTest.from_function(_app, default_timeout=90)
    app.run()
    assert not app.exception
    assert "analysis_result" not in app.session_state  # nothing evaluated before the button
    [go] = [b for b in app.button if b.label == "Analyse"]
    go.click().run()
    assert not app.exception
    stored = app.session_state["analysis_result"]
    assert stored[0] == ("crypto", "bitcoin", ac.EXAMPLE_KEY) and stored[3] is None
    labels = [e.label for e in app.expander]
    assert any("Trend Confirmation" in x for x in labels) and any("Reversal Evidence" in x for x in labels)


def test_card_shows_an_error_when_evaluation_fails():
    testing = pytest.importorskip("streamlit.testing.v1")
    app = testing.AppTest.from_function(_app, kwargs={"fail": True}, default_timeout=60)
    app.run()
    [b for b in app.button if b.label == "Analyse"][0].click().run()
    assert not app.exception
    assert any("could not be completed" in w.value for w in app.warning)


# ------------------------------------------------------------------------------- isolation

def test_existing_readings_and_alerts_do_not_import_the_card():
    for name in ("signals_v2.py", "signals_view.py", "scoring.py", "alerts.py", "signal_inspector.py",
                 "signal_groups_inspector.py"):
        path = ROOT / name
        if path.exists():
            assert "analysis_card" not in path.read_text(encoding="utf-8"), name


def test_app_shows_the_card_to_admins_only_and_after_the_existing_readings():
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    at = text.index("analysis_card.render(")
    gate = text.rindex("if _is_admin():", 0, at)
    assert at - gate < 400
    assert text.index("st.html(signals_view.asset_card(result))") < gate
    assert text.count("analysis_card.render(") == 1


def test_readings_are_tidied():
    assert ac.tidy("last high 114.9389960682998 at 2026-10-30T20:00:00+00:00") == "last high 114.94 at 2026-10-30 20:00 UTC"
    assert ac.tidy("ER 0.239, ADX 27.155553") == "ER 0.239, ADX 27.156"
