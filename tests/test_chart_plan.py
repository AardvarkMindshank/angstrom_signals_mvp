from chart_plan import MAX_EXTRA_PANELS, available, plan

FULL = ["close", "rsi", "sma_200", "ichi_span_a", "ichi_span_b", "MACD_12_26_9", "stoch_k", "adx", "obv"]


def test_default_is_price_and_volume():
    out = plan([], FULL)
    assert out["panels"] == ["volume"]
    assert out["overlays"] == []
    assert abs(sum(out["heights"]) - 1) < 1e-9


def test_choices_split_into_overlays_and_panels():
    out = plan(["ichimoku", "sma200", "macd", "adx"], FULL)
    assert out["overlays"] == ["sma200", "ichimoku"]
    assert out["panels"] == ["volume", "macd", "adx"]
    assert len(out["heights"]) == 1 + len(out["panels"])
    assert abs(sum(out["heights"]) - 1) < 1e-9


def test_missing_data_is_skipped_not_drawn():
    out = plan(["sma200", "obv"], ["close", "obv"])
    assert out["overlays"] == []
    assert out["skipped"] == ["sma200"]
    assert out["panels"] == ["volume", "obv"]


def test_too_many_panels_are_cut():
    out = plan(["rsi", "macd", "stoch", "adx", "obv", "stochrsi"], FULL + ["stochrsi_k", "stochrsi_d"])
    assert len(out["panels"]) == 1 + MAX_EXTRA_PANELS
    out = plan(["macd", "stoch", "adx", "obv", "sma200"], FULL + ["x"])
    assert out["skipped"] == []


def test_unknown_keys_ignored_and_available_order():
    assert plan(["nope"], FULL)["panels"] == ["volume"]
    assert available(FULL) == ["sma200", "ichimoku", "rsi", "macd", "stoch", "adx", "obv"]
    assert available(["close"]) == []


def test_overlay_moves_bounded_curves_onto_the_price_panel():
    out = plan(["rsi", "stoch", "adx", "macd", "obv"], FULL, overlay_curves=True)
    assert out["secondary"] == ["rsi", "stoch", "adx"]
    assert out["panels"] == ["volume", "macd", "obv"]
    assert len(out["heights"]) == 1 + len(out["panels"])
    assert abs(sum(out["heights"]) - 1) < 1e-9


def test_overlay_off_keeps_everything_below():
    out = plan(["rsi", "stoch"], FULL)
    assert out["secondary"] == []
    assert out["panels"] == ["volume", "rsi", "stoch"]


def test_rsi_is_off_unless_picked():
    assert "rsi" not in plan(["stoch"], FULL)["panels"]
    assert "rsi" not in plan(["stoch"], FULL, overlay_curves=True)["secondary"]


def test_overlay_without_rsi_data_keeps_volume_only():
    out = plan([], ["close"], overlay_curves=True)
    assert out["secondary"] == []
    assert out["panels"] == ["volume"]
