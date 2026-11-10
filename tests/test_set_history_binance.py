"""Visualize History's daily frames (set_history.full_daily): a coin known only by its Binance pair reads Binance's
daily candles, never a guessed Yahoo ticker that may be another coin."""

import numpy as np
import pytest
import pandas as pd

import binance_data as bn
import data_fetchers
import set_history as sh


def test_a_binance_only_coin_reads_binance(monkeypatch):
    pytest.importorskip("pandas_ta")             # calculate_indicators (installed in CI)
    days = pd.date_range("2024-01-01", periods=300, freq="1D", tz="UTC")
    close = np.linspace(1, 2, 300)
    frame = pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
                          "volume": np.full(300, 1e6)}, index=days)
    monkeypatch.setitem(bn.KNOWN_PAIRS, "sentient-test", "SENTUSDT")
    monkeypatch.setattr(bn, "klines", lambda pair, interval, start, get=None: frame if pair == "SENTUSDT" else None)
    guessed = []
    monkeypatch.setattr(data_fetchers, "_coingecko_symbol", lambda c: guessed.append(c) or "SENT")
    monkeypatch.setattr(data_fetchers, "_history_from_yahoo", lambda t, p: pd.DataFrame())
    sh._FRAMES.clear()
    out = sh.full_daily("crypto", "sentient-test")
    assert out is not None and len(out) >= 290 and not guessed
