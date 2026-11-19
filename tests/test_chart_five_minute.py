import pandas as pd

import binance_data as bn
import chart_candles as cc


def _candles(days=9):
    end = pd.Timestamp.now(tz="UTC").floor("5min")
    idx = pd.date_range(end - pd.Timedelta(days=days), end, freq="5min")
    return pd.DataFrame({"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 5.0}, index=idx)


def test_five_minute_is_crypto_and_7_days_only():
    assert cc.INTERVALS[0] == "5m"
    assert cc.availability("5m", "7D") == (True, "")
    assert not cc.availability("5m", "1M")[0]
    assert cc.nearest_range("5m", "3M") == "7D"
    assert "crypto only" in cc.load_candles("equity", "AAPL", "5m", "7D")["error"]


def test_five_minute_candles_with_warm_up(monkeypatch):
    monkeypatch.setattr(bn, "pair_for", lambda *a, **k: "BTCUSDT")
    df = _candles()
    out = cc.five_minute("crypto", "bitcoin", "7D", klines=lambda pair, interval, start: df[df.index >= start])
    assert out["error"] is None
    shown = out["candles"][out["candles"].index >= out["start"]]
    assert 2000 <= len(shown) <= 2020 and len(out["candles"]) - len(shown) == 260
    assert bool(out["candles"]["forming"].iloc[-1]) and "5 minutes" in out["source"]
