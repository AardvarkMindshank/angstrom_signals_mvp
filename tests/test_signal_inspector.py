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
