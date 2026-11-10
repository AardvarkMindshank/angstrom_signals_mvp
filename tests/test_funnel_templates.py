"""The ready-made funnels (funnel_templates.py) are valid, scannable Sets on the right timeframes, and answer on data."""

import numpy as np
import pandas as pd

import funnel_templates as ft
import signal_groups as sg
from signal_library import DataContext, engine


def test_every_stage_is_a_valid_scannable_set():
    for direction in ("long", "short"):
        f = ft.trend_funnel(direction)
        assert [s["timeframe"] for s in f["stages"]] == ["1D", "12h", "4h", "1h"]
        for s in f["stages"]:
            assert sg.validate_set(s["set_body"]) == [] and sg.scannable(s["set_body"])
            assert all(m["ref"]["timeframe"] == s["timeframe"] for m in s["set_body"]["standalone"])


def test_the_trend_stage_answers_on_a_rising_market():
    engine.clear_cache()
    n = 400
    close = np.r_[np.linspace(100, 200, n), 0]
    frame = pd.DataFrame({"open": close * 0.999, "high": close * 1.01, "low": close * 0.99, "close": close,
                          "volume": np.full(n + 1, 100.0)},
                         index=pd.date_range("2024-01-01", periods=n + 1, freq="12h", tz="UTC"))
    frame["forming"] = False
    frame.iloc[-1, frame.columns.get_loc("forming")] = True
    ctx = DataContext("crypto", "bitcoin", candle_loader=lambda *a: {"frame": frame, "session": None, "source": "t"})
    up = sg.evaluate_set(ft.trend_set("12h", "long"), ctx)["decision"]["answer"]
    down = sg.evaluate_set(ft.trend_set("12h", "short"), ctx)["decision"]["answer"]
    assert (up, down) == ("yes", "no")


def test_the_entry_check_reads_every_line():
    engine.clear_cache()
    rng = np.random.default_rng(5)
    n = 400
    close = np.r_[100 * np.exp(np.cumsum(rng.normal(0.001, 0.01, n))), 0]
    frame = pd.DataFrame({"open": np.r_[close[0], close[:-1]], "high": close * 1.01, "low": close * 0.99,
                          "close": close, "volume": np.full(n + 1, 100.0)},
                         index=pd.date_range("2024-01-01", periods=n + 1, freq="1h", tz="UTC"))
    frame["forming"] = False
    frame.iloc[-1, frame.columns.get_loc("forming")] = True
    ctx = DataContext("crypto", "bitcoin", candle_loader=lambda *a: {"frame": frame, "session": None, "source": "t"})
    result = sg.evaluate_set(ft.entry_set("long"), ctx)
    assert result["decision"]["answer"] in ("yes", "no")              # every member read: never Unknown here
