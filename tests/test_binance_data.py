"""Binance spot candles for crypto (binance_data.py) and their use in chart_data, with Binance's answers faked."""

import pandas as pd

import binance_data as bn
import chart_data

PAIRS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "UNI": "UNIUSDT", "PEPE": "PEPEUSDT"}


def _rows(start_ms, step_ms, n, price=100.0):
    return [[start_ms + i * step_ms, str(price + i), str(price + i + 2), str(price + i - 1), str(price + i + 1), "5",
             start_ms + (i + 1) * step_ms - 1, str((price + i) * 5), 10, "0", "0", "0"] for i in range(n)]


def test_pair_from_yahoo_ticker_then_symbol_with_a_price_check():
    assert bn.pair_for("crypto", "bitcoin", "BTC-USD", pairs=PAIRS) == "BTCUSDT"
    assert bn.pair_for("equity", "AAPL", "AAPL", pairs=PAIRS) is None
    assert bn.pair_for("crypto", "x", "XMR-USD", pairs=PAIRS) is None                     # not on Binance
    price = {"UNIUSDT": 7.1, "PEPEUSDT": 0.00001}.get
    good = {"symbol": "uni", "current_price": 7.0}
    assert bn.pair_for("crypto", "uniswap", None, good, pairs=PAIRS, price_of=price) == "UNIUSDT"
    impostor = {"symbol": "pepe", "current_price": 0.5}                                    # same ticker, other coin
    assert bn.pair_for("crypto", "pepe-other", None, impostor, pairs=PAIRS, price_of=price) is None


def test_klines_pages_through_and_uses_quote_volume():
    step = bn.STEP_MS["1h"]
    begin = pd.Timestamp.now(tz="UTC").floor("h") - pd.Timedelta(hours=3000)
    start = int(begin.timestamp() * 1000)
    calls = []

    def get(path, params):
        calls.append(params["startTime"])
        done = (params["startTime"] - start) // step
        n = min(bn.LIMIT, 2500 - done)
        return _rows(params["startTime"], step, n) if n > 0 else []

    frame = bn.klines("BTCUSDT", "1h", begin, get=get)
    assert len(frame) == 2500 and len(calls) == 3
    assert frame.index.is_monotonic_increasing and str(frame.index.tz) == "UTC"
    assert frame["volume"].iloc[0] == 500.0                                                # USDT traded, not coins
    assert frame.index[1] - frame.index[0] == pd.Timedelta(hours=1)


def test_chart_data_prefers_binance_for_crypto(monkeypatch):
    chart_data.CACHE.clear()
    step = bn.STEP_MS["12h"]
    now = pd.Timestamp.now(tz="UTC").floor("12h")
    rows = _rows(int((now - pd.Timedelta(hours=12 * 799)).timestamp() * 1000), step, 800)
    monkeypatch.setattr(bn, "trading_pairs", lambda get=None: PAIRS)
    monkeypatch.setattr(bn, "klines", lambda pair, interval, start, get=None: pd.DataFrame({
        "open": [float(r[1]) for r in rows], "high": [float(r[2]) for r in rows], "low": [float(r[3]) for r in rows],
        "close": [float(r[4]) for r in rows], "volume": [float(r[7]) for r in rows]},
        index=pd.to_datetime([r[0] for r in rows], unit="ms", utc=True)))
    out = chart_data.load_candles("crypto", "bitcoin", "12h", "3M")
    assert out["error"] is None and "Binance spot BTC/USDT" in out["source"]
    assert bool(out["candles"]["forming"].iloc[-1]) and not out["candles"]["forming"].iloc[:-1].any()
    # A coin Binance does not list falls back to Yahoo (here: no Yahoo either, so a plain error).
    monkeypatch.setattr(bn, "coingecko_coin", lambda asset_id: None)
    gone = chart_data.load_candles("crypto", "some-unlisted-coin", "12h", "3M")
    assert gone["error"] and "Binance" in gone["error"]


def test_a_long_range_keeps_the_newest_candles():
    step = bn.STEP_MS["15m"]
    asked = []

    def get(path, params):
        asked.append(params["startTime"])
        return []

    bn.klines("BTCUSDT", "15m", pd.Timestamp("2018-01-01", tz="UTC"), get=get)
    first = pd.to_datetime(asked[0], unit="ms", utc=True)
    assert pd.Timestamp.now(tz="UTC") - first < pd.Timedelta(milliseconds=step * bn.LIMIT * bn.MAX_REQUESTS)
