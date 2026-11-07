"""
Daily prices for past-moment scans in the training videos, from the saved price files (reports branch,
data/prices/<ticker>.csv.gz), cut at 29 Oct 2024 as each file is read: nothing from the protected hold-out (from
30 Oct 2024) is ever loaded. The folder comes from DEMO_PRICES.
"""

from __future__ import annotations

import os

import pandas as pd

from signal_library.replay import RECONSTRUCTED, RECONSTRUCTED_LIMITED, CandleHistory

CUT = pd.Timestamp("2024-10-29")
CRYPTO = {"bitcoin": "BTC-USD", "ethereum": "ETH-USD", "solana": "SOL-USD", "ripple": "XRP-USD",
          "binancecoin": "BNB-USD", "cardano": "ADA-USD", "dogecoin": "DOGE-USD", "avalanche-2": "AVAX-USD",
          "chainlink": "LINK-USD"}
EQUITIES = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "NFLX", "JPM"]
_cache: dict = {}


def folder() -> str:
    return os.environ.get("DEMO_PRICES", "data/prices").rstrip("/")


def frame(symbol: str) -> pd.DataFrame:
    if symbol not in _cache:
        d = pd.read_csv(f"{folder()}/{symbol}.csv.gz", parse_dates=["date"])
        d = d[d["date"] <= CUT]                     # nothing from the hold-out is kept past this line
        d = d.set_index(pd.DatetimeIndex(d["date"]).tz_localize("UTC"))[["open", "high", "low", "close", "volume"]]
        _cache[symbol] = d
    return _cache[symbol]


def candles(kind: str, asset_id: str, timeframe: str):
    """The replay's candle source: daily candles only (the video Sets read 1D)."""
    if timeframe not in ("1D", "1W"):
        return {"error": "Only daily candles are saved (weekly are built from them)."}
    symbol = CRYPTO.get(asset_id, asset_id)
    try:
        raw = frame(symbol)
    except FileNotFoundError:
        return {"error": f"No saved prices for {symbol}."}
    if timeframe == "1W":                            # weeks built from the saved days (Monday to Sunday)
        raw = raw.resample("W-SUN", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    quality = RECONSTRUCTED if kind == "crypto" else RECONSTRUCTED_LIMITED
    return CandleHistory(raw, timeframe, kind, None, {"provider": "saved daily prices (reports branch)",
                                                      "quality": quality, "limitations": []})
