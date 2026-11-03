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
    assert {r.id for r in signal_inspector.market_refs()} == {"flows.btc_etf", "flows.stablecoin_supply"}


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
