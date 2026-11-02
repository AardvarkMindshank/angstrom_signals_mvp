"""The signals v2 HTML pieces: they must show what the engine says, and nothing it does not."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import signals_v2 as v2  # noqa: E402
import signals_view as view  # noqa: E402
import test_signals_v2 as fx  # noqa: E402

LATER = datetime(2030, 1, 1, tzinfo=timezone.utc)


def result(**kw):
    return v2.score(fx.fixture(**kw), "Stock", LATER)


def test_row_fields_has_readings_display_fields_and_no_score():
    frame = fx.fixture()
    row = view.row_fields(frame, "Stock", LATER)
    assert "score" not in row and "contributions" not in row
    for key in ("trend", "stretch", "flow"):
        assert row[key] is None or -100 <= row[key] <= 100
    assert row["signals"]["version"] == v2.VERSION
    assert row["latest_price"] and row["atr_pct"] > 0
    assert row["label"] == "" and row["reasons"] == []
    assert set(row["trend_parts"]) <= set(v2.COMPONENT_NAMES.values())


def test_row_fields_with_too_little_data_says_no_data():
    row = view.row_fields(fx.fixture(n=10), "Stock", LATER)
    assert row["label"] == "No data" and row["reasons"] and row["trend"] is None


def test_table_cell_sorts_by_the_reading_and_opens_the_breakdown():
    frame = fx.fixture()
    row = view.row_fields(frame, "Stock", LATER)
    cell = view.table_cell("trend", row, "Stock|AAA")
    assert f"data-sort='{float(row['trend']):.4f}'" in cell
    assert "data-pick='Stock|AAA|breakdown'" in cell
    assert "not a forecast" in cell


def test_missing_reading_is_a_dash_not_zero():
    cell = view.table_cell("flow", {"flow": None, "signals": None})
    assert "data-sort=''" in cell and "—" in cell and "+0" not in cell


def test_mini_bar_is_centred_and_directional():
    up, down = view.mini_bar(60, 64), view.mini_bar(-60, 64)
    assert "left:32px" in up and "left:32px" not in down.split("background:")[1]


def test_card_shows_badges_context_and_never_a_score():
    out = result()
    card = view.asset_card(out)
    assert "Not validated" in card
    assert "/100" not in card and "Score" not in card
    assert "Range" in card  # ATR% context chip


def test_stock_volatility_is_the_only_validated_claim():
    out = result()
    card = view.asset_card(out)
    assert "Tested: size only" in card  # stock ATR% context chip
    crypto = v2.score(fx.fixture(), "Crypto", LATER)
    assert "Tested: size only" not in view.asset_card(crypto)


def test_breakdown_lists_every_component_lenses_and_version():
    out = result()
    text = view.breakdown(out)
    for name in v2.COMPONENT_NAMES.values():
        assert name in text
    for spec in v2.LENSES.values():
        assert spec["name"] in text
    assert out["fingerprint"] in text
    assert "not validated" in text


def test_missing_volume_shows_as_missing_in_the_breakdown():
    out = v2.score(fx.fixture(volume=False), "Crypto", LATER)
    assert "No data from this source" in view.breakdown(out)


def test_explainer_does_not_claim_direction_was_shown():
    text = view.EXPLAINER.lower()
    assert "none of the directional readings has been shown to predict" in text
    assert "version " not in text and "v1" not in text and "v2" not in text


def test_table_survives_a_watchlist_with_a_missing_reading():
    import pandas as pd

    good = view.row_fields(fx.fixture(), "Stock", LATER)
    bad = {"trend": None, "stretch": None, "flow": None, "signals": None}
    frame = pd.DataFrame([good, bad]).sort_values("trend", ascending=False, na_position="last")
    for _, row in frame.iterrows():
        row_dict = {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in row.items()}
        for key in v2.CLUSTERS:
            view.table_cell(key, row_dict, "Stock|AAA")
    assert view.signed(51.0) == "+51" and view.signed(float("nan")) == "—"
