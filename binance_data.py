"""
Crypto candles from Binance's public market data (spot, against USDT), decided 10 Nov 2026: Binance for crypto
candles, Yahoo Finance for equities, for studies (history before 2017) and as the fallback for coins Binance does not
list.

* data-api.binance.vision is Binance's public market-data mirror: no account or key, reachable from our servers (GitHub
  runs in the US, where api.binance.com answers 451; the mirror answers 200, checked by .github/workflows/data-probe.yml).
* Every interval is Binance's own (15m, 30m, 1h, 4h, 12h, 1d, 1w), aligned to UTC like our crypto candles: 4h and 12h
  blocks start at 00:00 UTC, weeks on Monday.
* Volume is the quote volume (USDT traded), so it reads like Yahoo's dollar volume.
* A coin is matched to its Binance pair through its Yahoo ticker (BTC-USD -> BTCUSDT) or, for other coins, its CoinGecko
  symbol; a pair is used only if Binance lists it as trading, and (for symbol matches) only if its price agrees with
  CoinGecko's within PRICE_TOLERANCE, so a coin never borrows another coin's ticker.
"""

from __future__ import annotations

import threading
import time

import pandas as pd
import requests

BASE = "https://data-api.binance.vision"
INTERVAL = {"15m": "15m", "30m": "30m", "1h": "1h", "4h": "4h", "12h": "12h", "1D": "1d", "1W": "1w"}
STEP_MS = {"15m": 15 * 60_000, "30m": 30 * 60_000, "1h": 3_600_000, "4h": 4 * 3_600_000, "12h": 12 * 3_600_000,
           "1D": 86_400_000, "1W": 7 * 86_400_000}
LIMIT = 1000                        # candles per request (Binance's maximum)
MAX_REQUESTS = 12                   # per load: 12,000 candles is far more than any chart range needs
FIRST_DAY = pd.Timestamp("2017-07-01", tz="UTC")   # Binance opened in July 2017
PRICE_TOLERANCE = 0.05
QUOTE = "USDT"
_HEADERS = {"User-Agent": "AngstromSignals/1.0 (market research dashboard)"}


class _Timed:
    """A value kept for `ttl` seconds."""

    def __init__(self, ttl: float):
        self.ttl, self.at, self.value, self.lock = ttl, 0.0, None, threading.Lock()

    def get(self, make):
        with self.lock:
            if self.value is None or time.time() - self.at > self.ttl:
                fresh = make()
                if fresh is not None:
                    self.value, self.at = fresh, time.time()
            return self.value


def _get(path: str, params: dict | None = None, timeout: float = 15):
    r = requests.get(BASE + path, params=params or {}, headers=_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ----------------------------------------------------------------------------------------------- pairs

_PAIRS = _Timed(6 * 3600)


def trading_pairs(get=_get) -> dict[str, str]:
    """{base asset: pair} for every spot pair against USDT that is trading now (e.g. {"BTC": "BTCUSDT"})."""
    def make():
        try:
            info = get("/api/v3/exchangeInfo", {"permissions": "SPOT"})
        except Exception:
            return None
        return {s["baseAsset"]: s["symbol"] for s in info.get("symbols") or []
                if s.get("quoteAsset") == QUOTE and s.get("status") == "TRADING"}
    return _PAIRS.get(make) or {}


def pair_for(kind: str, asset_id: str, yahoo_symbol: str | None = None, coingecko: dict | None = None,
             pairs: dict | None = None, price_of=None) -> str | None:
    """The Binance pair for a coin, or None. `coingecko` (optional): {"symbol", "current_price"} for coins without a
    Yahoo ticker; then the pair must agree on price."""
    if kind != "crypto":
        return None
    pairs = trading_pairs() if pairs is None else pairs
    if yahoo_symbol and yahoo_symbol.upper().endswith("-USD"):
        base = yahoo_symbol.upper()[:-4]
        if base in pairs:
            return pairs[base]
    if coingecko and coingecko.get("symbol"):
        base = str(coingecko["symbol"]).upper()
        pair = pairs.get(base)
        if pair and price_of is not None:
            theirs, ours = price_of(pair), coingecko.get("current_price")
            if theirs and ours and abs(theirs / ours - 1) <= PRICE_TOLERANCE:
                return pair
    return None


# ----------------------------------------------------------------------------------------------- candles

def klines(pair: str, interval: str, start: pd.Timestamp | None, get=_get) -> pd.DataFrame:
    """Candles from `start` (or Binance's first) to now: open, high, low, close, volume (quote, USDT); index = candle
    start (UTC). The newest candle may still be forming (chart_data.mark_forming marks it)."""
    step = STEP_MS[interval]
    begin = max(pd.Timestamp(start) if start is not None else FIRST_DAY, FIRST_DAY)
    since = int(begin.timestamp() * 1000)
    rows: list = []
    for _ in range(MAX_REQUESTS):
        part = get("/api/v3/klines", {"symbol": pair, "interval": INTERVAL[interval], "startTime": since,
                                      "limit": LIMIT})
        if not part:
            break
        rows.extend(part)
        if len(part) < LIMIT:
            break
        since = int(part[-1][0]) + step
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"],
                            index=pd.DatetimeIndex([], tz="UTC"))
    frame = pd.DataFrame({
        "open": [float(r[1]) for r in rows], "high": [float(r[2]) for r in rows],
        "low": [float(r[3]) for r in rows], "close": [float(r[4]) for r in rows],
        "volume": [float(r[7]) for r in rows],
    }, index=pd.to_datetime([int(r[0]) for r in rows], unit="ms", utc=True))
    return frame[~frame.index.duplicated(keep="last")].sort_index()


_COINS: dict = {}


def coingecko_coin(asset_id: str) -> dict | None:
    """{"symbol", "current_price"} from CoinGecko for one coin id, kept for a day (for coins without a Yahoo ticker)."""
    hit = _COINS.get(asset_id)
    if hit and time.time() - hit[0] < 86_400:
        return hit[1]
    try:
        r = requests.get("https://api.coingecko.com/api/v3/coins/markets", headers=_HEADERS, timeout=10,
                         params={"vs_currency": "usd", "ids": asset_id, "per_page": 1, "page": 1})
        rows = r.json() if r.status_code == 200 else []
        found = {"symbol": rows[0].get("symbol"), "current_price": rows[0].get("current_price")} if rows else None
    except Exception:
        return None
    _COINS[asset_id] = (time.time(), found)
    return found


_PRICES = _Timed(60)


def last_price(pair: str, get=_get) -> float | None:
    def make():
        try:
            return {t["symbol"]: float(t["price"]) for t in get("/api/v3/ticker/price")}
        except Exception:
            return None
    return (_PRICES.get(make) or {}).get(pair)
