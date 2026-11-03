import ast
import json
import pathlib

import numpy as np
import pandas as pd

import chart_browser_fixtures as fx
import chart_data
import chart_plan
import lw_chart

ROOT = pathlib.Path(__file__).resolve().parents[1]
NY = ("America/New_York", 570, 960)


def _payload(**kw):
    df = kw.pop("df", None)
    if df is None:
        df = fx.crypto_4h()
    picks = kw.pop("picks", ["sma200", "ichimoku", "macd", "stoch", "adx", "obv"])
    overlay = kw.pop("overlay", False)
    layout = chart_plan.plan(picks, df.columns, overlay_curves=overlay)
    args = dict(kind="crypto", interval="4h", range_key="1M", range_start=df.index[-180], view_key="k")
    args.update(kw)
    return lw_chart.build_payload(df, layout, **args), df, layout


def test_payload_is_json_and_aligned():
    payload, df, _ = _payload()
    json.dumps(payload)
    n = len(df)
    assert len(payload["times"]) == n and all(len(col) == n for col in payload["ohlc"])
    for s in payload["series"]:
        for field in ("values", "a", "b"):
            if field in s:
                assert len(s[field]) == n
    assert payload["times"] == sorted(payload["times"])


def test_indicator_values_are_the_frames_own_values():
    """No new formulas: the chart sends exactly the columns it was given."""
    payload, df, _ = _payload()
    by_id = {s["id"]: s for s in payload["series"]}
    i = len(df) - 5
    assert by_id["rsi"]["values"][i] == round(float(df["rsi"].iloc[i]), 2)
    assert by_id["sma200"]["values"][i] == round(float(df["sma_200"].iloc[i]), 8)
    assert by_id["macd"]["values"][i] == round(float(df["MACD_12_26_9"].iloc[i]), 8)


def test_gaps_become_none():
    payload, df, _ = _payload()
    sma200 = next(s for s in payload["series"] if s["id"] == "sma200")["values"]
    assert sma200[0] is None and sma200[-1] is not None


def test_panes_follow_chart_plan():
    payload, _, layout = _payload()
    assert len(payload["panes"]) == 1 + len(layout["panels"])
    used = {s["pane"] for s in payload["series"]}
    assert used == set(range(len(payload["panes"])))
    assert payload["panes"][layout["panels"].index("rsi") + 1]["fixed"] == [0, 100]


def test_overlay_mode_puts_bounded_curves_on_price_pane():
    payload, _, layout = _payload(picks=["stoch", "adx"], overlay=True)
    by_id = {s["id"]: s for s in payload["series"]}
    for key in ("rsi", "stoch", "adx"):
        assert by_id[key]["pane"] == 0 and by_id[key]["scale"] == "osc"
    assert len(payload["panes"]) == 2  # price + volume


def test_forming_flag_and_range_start():
    payload, df, _ = _payload()
    assert payload["forming"] is True
    assert payload["start_index"] == len(df) - 180


def test_liquidation_lines_scale_with_money():
    record = {"status": "ok", "longs": [{"price": 90, "usd": 1e8}, {"price": 85, "usd": 1e7}],
              "shorts": [{"price": 110, "usd": "bad"}]}
    payload, _, _ = _payload(liquidation=record)
    lines = payload["price_lines"]
    assert [l["price"] for l in lines] == [90.0, 85.0]
    assert lines[0]["width"] > lines[1]["width"]
    assert lines[0]["color"].startswith("rgba(239,68,68")


def test_earnings_past_and_next():
    df = fx.equity_daily()
    past = str(df.index[-30].date())
    payload, _, _ = _payload(df=df, picks=[], kind="equity", interval="1D", session=NY,
                             past_reports=[past, "1990-01-01"], next_report="2026-11-20")
    styles = [v["style"] for v in payload["vlines"]]
    assert styles == ["dotted", "dashed"]
    assert payload["vlines"][0]["index"] == len(df) - 30
    ahead = int(np.busday_count(df.index[-1].date(), pd.Timestamp("2026-11-20").date()))
    assert payload["vlines"][1]["index"] == len(df) - 1 + ahead
    assert payload["right_offset"] > ahead


def test_next_earnings_far_away_does_not_stretch_the_chart():
    df = fx.equity_daily()
    payload, _, _ = _payload(df=df, picks=[], kind="equity", interval="1D", session=NY, next_report="2027-03-01")
    assert payload["right_offset"] == 0 and payload["vlines"] == []


def test_intraday_shares_show_exchange_clock():
    df = fx.equity_1h()
    payload, _, _ = _payload(df=df, picks=[], kind="equity", interval="1h", session=NY, range_start=df.index[-50])
    first = pd.Timestamp(payload["times"][0], unit="s")
    assert first.strftime("%H:%M") == "09:30"
    assert payload["clock"] == "New York time"
    assert payload["intraday"] is True


def test_dark_theme_matches_plotly_surface():
    assert lw_chart.theme(True)["bg"] == "#262730"
    assert lw_chart.theme(False)["bg"] == "#ffffff"


def test_pane_heights_keep_price_choice():
    assert lw_chart.pane_heights(500, ["volume", "rsi"])[0] == 500
    assert all(h >= lw_chart.MIN_PANEL_PX for h in lw_chart.pane_heights(380, ["volume", "rsi", "macd", "stoch", "adx", "obv"]))


def test_payload_size_stays_reasonable():
    payload, df, _ = _payload()
    per_candle = lw_chart.payload_size(payload) / len(df)
    # Every indicator on: well under 1 KB per candle, so the largest chart (about 3,300 15m candles) stays near 1 MB.
    assert per_candle < 400


# ---------------------------------------------------------------- wiring in app.py

SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")


def test_app_still_parses_and_keeps_plotly():
    ast.parse(SOURCE)
    assert "st.plotly_chart(fig, width=\"stretch\")" in SOURCE
    assert "CHART_ENGINE_DEFAULT = CHART_ENGINE_TV" in SOURCE
    assert "CHART_ENGINE_PLOTLY" in SOURCE.split("CHART_ENGINES = (")[1].split(")")[0]


def test_engine_interval_and_range_are_saved_to_the_account():
    assert "CHART_ENGINE_SETTING: chart_engine," in SOURCE
    assert 'saved_engine = settings.get(CHART_ENGINE_SETTING)' in SOURCE
    assert 'CHART_ENGINE_SETTING = "price_chart"' in SOURCE
    for old in ("chart_engine", "chart_style"):
        assert f'key="{old}"' not in SOURCE and f'session_state.get("{old}"' not in SOURCE
    assert 'key="price_chart"' in SOURCE
    assert 'save_account_settings({"chart_interval": interval, "chart_range": range_key})' in SOURCE
    for key in ("price_chart", "chart_interval", "chart_range"):
        assert f'    "{key}",\n' in SOURCE  # cleared when another account logs in


def test_readings_and_other_sections_use_daily_bars():
    """Trend, Stretch, Flow, the matrix, max pain and leverage never see intraday candles."""
    for needle in (
        "show_signal_matrix(asset_type, asset_key, title, daily_chart)",
        'show_max_pain(asset_type, asset_key, title, float(daily_chart["close"].iloc[-1]))',
        'show_leverage(asset_type, asset_key, title, float(daily_chart["close"].iloc[-1]))',
        "else daily_chart",
    ):
        assert needle in SOURCE


def test_indicators_are_calculated_on_the_chosen_candles():
    block = SOURCE[SOURCE.index("def _tv_candles"): SOURCE.index("def _tv_chart")]
    assert "calculate_indicators(candles[" in block


def test_library_is_vendored_with_licence():
    folder = ROOT / "static" / "lwc"
    lib = (folder / "lightweight-charts.standalone.production.js").read_text(encoding="utf-8")[:300]
    assert "Apache License 2.0" in lib and "v5.2.1" in lib
    assert "Apache License" in (folder / "LICENSE").read_text(encoding="utf-8")
    assert lw_chart.LIBRARY_PATH == "/app/static/lwc/lightweight-charts.standalone.production.js"
    assert "enableStaticServing = true" in (ROOT / ".streamlit" / "config.toml").read_text()


def test_component_keeps_attribution_logo():
    js = (ROOT / "lw_chart.js").read_text(encoding="utf-8")
    assert "attributionLogo: true" in js
    assert "pinch: true" in js and "mouseWheel: true" in js
