from chart_plan import MAX_EXTRA_PANELS, available, plan

FULL = ["close", "sma_200", "ichi_span_a", "ichi_span_b", "MACD_12_26_9", "stoch_k", "adx", "obv"]


def test_default_is_price_volume_rsi():
    out = plan([], FULL)
    assert out["panels"] == ["volume", "rsi"]
    assert out["overlays"] == []
    assert abs(sum(out["heights"]) - 1) < 1e-9


def test_choices_split_into_overlays_and_panels():
    out = plan(["ichimoku", "sma200", "macd", "adx"], FULL)
    assert out["overlays"] == ["sma200", "ichimoku"]
    assert out["panels"] == ["volume", "rsi", "macd", "adx"]
    assert len(out["heights"]) == 1 + len(out["panels"])
    assert abs(sum(out["heights"]) - 1) < 1e-9


def test_missing_data_is_skipped_not_drawn():
    out = plan(["sma200", "obv"], ["close", "obv"])
    assert out["overlays"] == []
    assert out["skipped"] == ["sma200"]
    assert out["panels"] == ["volume", "rsi", "obv"]


def test_too_many_panels_are_cut():
    out = plan(["macd", "stoch", "adx", "obv"], FULL)
    assert len(out["panels"]) == 2 + MAX_EXTRA_PANELS
    out = plan(["macd", "stoch", "adx", "obv", "sma200"], FULL + ["x"])
    assert out["skipped"] == []


def test_unknown_keys_ignored_and_available_order():
    assert plan(["nope"], FULL)["panels"] == ["volume", "rsi"]
    assert available(FULL) == ["sma200", "ichimoku", "macd", "stoch", "adx", "obv"]
    assert available(["close"]) == []
