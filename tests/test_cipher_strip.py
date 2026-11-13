"""🌀 Market Cipher B strip (free VuManChu version), between the price chart and volume. Chart only."""

import numpy as np
import pandas as pd

import chart_browser_fixtures as fx
import chart_plan
import lw_chart
from chart_indicators import add_chart_only, cipher_b


def _frame():
    return add_chart_only(fx.crypto_4h())


def test_columns_and_dots_follow_the_waves():
    df = _frame()
    w1, w2 = df["mc_wt1"], df["mc_wt2"]
    assert np.allclose((w1 - w2).dropna(), df["mc_vwap"].dropna())
    up = (w1 > w2) & (w1.shift(1) <= w2.shift(1))
    assert (df["mc_cross"] == 1).equals(up)
    assert (df["mc_buy"] == (up & (w2 <= -53))).all()
    assert not (df["mc_buy"] & df["mc_sell"]).any()



def test_strip_sits_between_price_and_volume():
    df = _frame()
    layout = chart_plan.plan(["obv", "cipher"], df.columns)
    assert layout["panels"][:2] == ["cipher", "volume"]
    payload = lw_chart.build_payload(df, layout, kind="crypto", interval="4h", range_key="3M")
    pane = payload["panes"][1]
    assert pane["fixed"] == [-105, 105] and pane["height"] > payload["panes"][2]["height"]
    ids = {s["id"]: s for s in payload["series"] if s["pane"] == 1}
    assert {"mc_wt1", "mc_wt2", "mc_vwap", "mc_mf_in", "mc_mf_out", "mc_bar", "mc_rsi", "mc_sk", "mc_dots",
            "mc_buy"} <= set(ids)
    assert len(ids["mc_sk"]["colors"]) == len(df)
    assert all(v is None or v == -96.5 for v in ids["mc_buy"]["values"])
    assert [v is not None for v in ids["mc_sell"]["values"]] == df["mc_sell"].tolist()
    assert any(g["value"] == 60 for g in payload["guides"])


def test_off_unless_picked():
    df = _frame()
    assert "cipher" not in chart_plan.plan([], df.columns)["panels"]
