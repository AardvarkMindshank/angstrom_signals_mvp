import pytest

import signal_inspector
import signal_library as sl


def test_every_signal_has_a_readable_summary():
    from tests.test_signal_library_ta import _ctx  # synthetic candles for every timeframe
    ctx = _ctx()
    for ref in signal_inspector.asset_refs("crypto", "4h"):
        result = sl.evaluate([ref], ctx)[ref.instance_key]
        text = signal_inspector.summary(result)
        assert isinstance(text, str) and text


def test_asset_refs_respect_scope():
    crypto = {r.id for r in signal_inspector.asset_refs("crypto", "1D")}
    equity = {r.id for r in signal_inspector.asset_refs("equity", "1D")}
    assert "positioning.oi_price" in crypto and "positioning.oi_price" not in equity
    assert "mtf.alignment" in equity
    assert {r.id for r in signal_inspector.market_refs()} == {"flows.btc_etf", "flows.stablecoin_supply",
                                                              "sentiment.market"}


def _app():
    import signal_inspector
    import streamlit as st
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

    signal_inspector.render(st, Empty(), [("crypto", "bitcoin", "Bitcoin"), ("equity", "AAPL", "Apple (AAPL)")])


def test_inspector_runs_inside_streamlit():
    testing = pytest.importorskip("streamlit.testing.v1")
    app = testing.AppTest.from_function(_app, default_timeout=60)
    app.run()
    assert not app.exception
    assert not app.dataframe  # nothing runs before the button
    app.button[0].click().run()
    assert not app.exception
    assert app.dataframe, "results table"
    table = app.dataframe[0].value
    assert len(table) >= 15 and "Signal" in table.columns


def test_groups_tab_evaluates_a_starter_inside_streamlit():
    testing = pytest.importorskip("streamlit.testing.v1")
    app = testing.AppTest.from_function(_app, default_timeout=90)
    app.run()
    assert not app.exception
    evaluate = [b for b in app.button if b.label == "Evaluate"]
    assert len(evaluate) == 2  # signal inspector and Groups & Sets
    evaluate[1].click().run()
    assert not app.exception
    text = " ".join(m.value for m in app.markdown)
    assert "Trend Confirmation" in text and "status" in text
    assert any(len(d.value) >= 3 for d in app.dataframe)  # conditions or members table


def test_groups_inspector_helpers():
    import signal_groups as sg
    import signal_groups_inspector as gi

    assert sg.validate_set(gi.example_set()) == []
    assert gi._rpc_error(Exception("ERROR: beyond_capture_ceiling HINT ...")) == "beyond_capture_ceiling"

    class Broken:
        def table(self, name):
            raise RuntimeError('relation "analysis_configs" does not exist')

    saved, problem = gi.saved_configs(Broken())
    assert saved == [] and "2026-11-04_signal_groups.sql" in problem


def _app_with_reconstruction():
    import json
    import pathlib

    import streamlit as st

    from tests.live_golden import GOLDEN   # tests/fixtures/, found from a module with a real file path
    from tests.test_signal_inspector import _app

    stored = json.loads(pathlib.Path(GOLDEN).with_name("reconstruction.json").read_text())
    st.session_state.setdefault("siggroups_result", tuple(stored))
    _app()


def test_groups_tab_shows_a_stored_reconstruction():
    testing = pytest.importorskip("streamlit.testing.v1")
    app = testing.AppTest.from_function(_app_with_reconstruction, default_timeout=90)
    app.run()
    assert not app.exception
    text = " ".join(m.value for m in app.markdown) + " ".join(i.value for i in app.info)
    assert "As-of reconstruction" in text and "Reconstruction: partial" in text
    assert any("not a complete reconstruction" in w.value for w in app.warning)
    assert not [b for b in app.get("download_button")]   # reconstructions are not exported
