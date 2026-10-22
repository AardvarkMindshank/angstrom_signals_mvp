"""
Market data for the dashboard and the alert worker.

Crypto tries Yahoo Finance first, then CoinGecko OHLC.
Equities come from Yahoo Finance.
Both functions return (dataframe, error_message). error_message is None on success.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor

import requests
import pandas as pd


# CoinGecko ids are not Yahoo tickers. "polkadot" must become DOT-USD, not POLKADOT-USD.
YF_BY_COINGECKO_ID = {
    "bitcoin": "BTC-USD",
    "ethereum": "ETH-USD",
    "solana": "SOL-USD",
    "cardano": "ADA-USD",
    "ripple": "XRP-USD",
    "polkadot": "DOT-USD",
    "sui": "SUI-USD",
    "dogecoin": "DOGE-USD",
    "avalanche-2": "AVAX-USD",
    "chainlink": "LINK-USD",
    "litecoin": "LTC-USD",
    "tron": "TRX-USD",
    "shiba-inu": "SHIB-USD",
    "binancecoin": "BNB-USD",
    "the-open-network": "TON-USD",
    "stellar": "XLM-USD",
    "cosmos": "ATOM-USD",
    "uniswap": "UNI-USD",
    "near": "NEAR-USD",
    "aptos": "APT-USD",
    "internet-computer": "ICP-USD",
    "pepe": "PEPE-USD",
    "hedera-hashgraph": "HBAR-USD",
    "ethereum-classic": "ETC-USD",
    "bitcoin-cash": "BCH-USD",
    "arbitrum": "ARB-USD",
    "optimism": "OP-USD",
    "aave": "AAVE-USD",
    "maker": "MKR-USD",
    "filecoin": "FIL-USD",
    "injective-protocol": "INJ-USD",
    "sei-network": "SEI-USD",
    "bonk": "BONK-USD",
    "dogwifcoin": "WIF-USD",
    "floki": "FLOKI-USD",
    "matic-network": "MATIC-USD",
    "polygon-ecosystem-token": "POL-USD",
    "hyperliquid": "HYPE-USD",
    "render-token": "RENDER-USD",
    "fetch-ai": "FET-USD",
    "lido-dao": "LDO-USD",
    "mantle": "MNT-USD",
    "kaspa": "KAS-USD",
    "monero": "XMR-USD",
    "algorand": "ALGO-USD",
    "vechain": "VET-USD",
    "the-graph": "GRT-USD",
    "immutable-x": "IMX-USD",
    "bittensor": "TAO-USD",
    "jupiter-exchange-solana": "JUP-USD",
    "ondo-finance": "ONDO-USD",
    "worldcoin-wld": "WLD-USD",
}

# Yahoo retired the plain ticker for these. The number is Yahoo's own id.
YAHOO_TICKER_BY_ID = {
    "sui": "SUI20947-USD",
    "uniswap": "UNI7083-USD",
    "aptos": "APT21794-USD",
    "pepe": "PEPE24478-USD",
    "matic-network": "POL28321-USD",
    "polygon-ecosystem-token": "POL28321-USD",
    "hyperliquid": "HYPE32196-USD",
    "the-graph": "GRT6719-USD",
    "immutable-x": "IMX10603-USD",
    "bittensor": "TAO22974-USD",
}

# Tickers traders type, such as XLM, mapped back to the CoinGecko id used above.
COINGECKO_ID_BY_SYMBOL = {
    ticker.split("-")[0]: coin_id
    for coin_id, ticker in YF_BY_COINGECKO_ID.items()
}

# Common names whose CoinGecko id is not just the name with spaces turned into hyphens.
COINGECKO_ID_BY_NAME = {
    "avalanche": "avalanche-2",
    "binance": "binancecoin",
    "binance-coin": "binancecoin",
    "dogwifhat": "dogwifcoin",
    "fetch": "fetch-ai",
    "hedera": "hedera-hashgraph",
    "immutable": "immutable-x",
    "injective": "injective-protocol",
    "jupiter": "jupiter-exchange-solana",
    "lido": "lido-dao",
    "near-protocol": "near",
    "ondo": "ondo-finance",
    "polygon": "polygon-ecosystem-token",
    "render": "render-token",
    "sei": "sei-network",
    "shiba": "shiba-inu",
    "ton": "the-open-network",
    "toncoin": "the-open-network",
    "worldcoin": "worldcoin-wld",
}

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SignalsDashboard/1.0)"}


def _normalize_name(raw: str) -> str:
    text = (raw or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[.']", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"[^a-z0-9-]", "", text)
    return re.sub(r"-+", "-", text).strip("-")


def _pretty_name(raw: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[\s_-]+", (raw or "").strip()) if part)


def resolve_crypto_id(raw: str) -> str:
    """Accept a CoinGecko id (stellar), a ticker (XLM), or a name (Stellar)."""
    coin_id = (raw or "").strip().lower()
    if coin_id in YF_BY_COINGECKO_ID:
        return coin_id
    compact = re.sub(r"[^A-Za-z0-9]", "", coin_id).upper()
    if compact in COINGECKO_ID_BY_SYMBOL:
        return COINGECKO_ID_BY_SYMBOL[compact]
    name = _normalize_name(raw)
    if name in YF_BY_COINGECKO_ID:
        return name
    if name in COINGECKO_ID_BY_NAME:
        return COINGECKO_ID_BY_NAME[name]
    return coin_id


def find_crypto(raw: str) -> tuple[str, str] | None:
    """Resolve a ticker or name to (coin_id, label). None when nothing matches."""
    text = (raw or "").strip()
    if not text:
        return None
    coin_id = resolve_crypto_id(text)
    if coin_id in YF_BY_COINGECKO_ID:
        ticker = crypto_ticker(coin_id)
        if ticker and text.upper() == ticker:
            return coin_id, ticker
        return coin_id, _pretty_name(text)
    match = _search_coingecko(text)
    if not match:
        return None
    found_id, found_name, found_symbol = match
    if found_symbol and text.upper() == found_symbol.upper():
        return found_id, found_symbol.upper()
    return found_id, found_name or _pretty_name(text)


def _search_coingecko(query: str) -> tuple[str, str, str] | None:
    """Exact ticker, name, or id from CoinGecko search. Prefers the largest coin."""
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/search",
            params={"query": query.strip()},
            headers=_HEADERS,
            timeout=15,
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    coins = (response.json() or {}).get("coins") or []
    wanted_name = _normalize_name(query)
    wanted_symbol = re.sub(r"[^A-Za-z0-9]", "", query).upper()
    wanted_id = query.strip().lower()

    def rank(coin: dict) -> int:
        value = coin.get("market_cap_rank")
        return value if isinstance(value, int) else 10**9

    by_symbol = []
    by_name = []
    by_id = []
    for coin in coins:
        if not isinstance(coin, dict) or not coin.get("id"):
            continue
        symbol = str(coin.get("symbol") or "").upper()
        name = _normalize_name(str(coin.get("name") or ""))
        coin_id = str(coin.get("id") or "").lower()
        if wanted_symbol and symbol == wanted_symbol:
            by_symbol.append(coin)
        if wanted_name and name == wanted_name:
            by_name.append(coin)
        if coin_id in {wanted_id, wanted_name}:
            by_id.append(coin)
    pool = by_symbol or by_name or by_id
    if not pool:
        return None
    best = min(pool, key=rank)
    return str(best["id"]), str(best.get("name") or ""), str(best.get("symbol") or "").upper()


def crypto_ticker(raw: str) -> str | None:
    yahoo = YF_BY_COINGECKO_ID.get(resolve_crypto_id(raw))
    if not yahoo:
        return None
    return yahoo.split("-")[0]


def period_for_days(days: int) -> str:
    days = int(days or 200)
    if days <= 90:
        return "3mo"
    if days <= 180:
        return "6mo"
    if days <= 365:
        return "1y"
    return "2y"


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def _ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = _flatten_columns(df)
    renamed = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })
    if any(column not in renamed.columns for column in ("open", "high", "low", "close")):
        return pd.DataFrame()
    if "volume" not in renamed.columns:
        renamed = renamed.copy()
        renamed["volume"] = 0
    out = renamed[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
    return out.dropna(subset=["open", "high", "low", "close"])


def _yahoo():
    import yfinance as yf
    return yf


def _history_from_yahoo(ticker: str, period: str) -> pd.DataFrame:
    df = _yahoo().Ticker(ticker).history(period=period)
    if df is None or df.empty:
        return pd.DataFrame()
    return _ohlcv(df)


def _coingecko_symbol(coin_id: str) -> str | None:
    response = requests.get(
        f"https://api.coingecko.com/api/v3/coins/{coin_id}",
        params={
            "localization": "false",
            "tickers": "false",
            "market_data": "false",
            "community_data": "false",
            "developer_data": "false",
            "sparkline": "false",
        },
        headers=_HEADERS,
        timeout=15,
    )
    if response.status_code != 200:
        return None
    symbol = (response.json() or {}).get("symbol")
    return str(symbol).upper() if symbol else None


def _coingecko_days(days: int) -> int:
    allowed = (1, 7, 14, 30, 90, 180, 365)
    return min(allowed, key=lambda choice: abs(choice - int(days or 180)))


def _coingecko_ohlc(coin_id: str, days: int) -> pd.DataFrame:
    """Real open/high/low/close candles. Volume is not included by this endpoint."""
    response = requests.get(
        f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc",
        params={"vs_currency": "usd", "days": _coingecko_days(days)},
        headers=_HEADERS,
        timeout=15,
    )
    if response.status_code != 200:
        return pd.DataFrame()
    rows = response.json()
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp")
    df["volume"] = 0
    return _ohlcv(df)


def fetch_crypto_data(coin_id: str, days: int = 200) -> tuple[pd.DataFrame, str | None]:
    entered = (coin_id or "").strip()
    coin_id = resolve_crypto_id(entered)
    if not coin_id:
        return pd.DataFrame(), "Missing crypto id."

    period = period_for_days(days)
    ticker = YAHOO_TICKER_BY_ID.get(coin_id) or YF_BY_COINGECKO_ID.get(coin_id)
    yahoo_error = None

    if ticker is None:
        try:
            symbol = _coingecko_symbol(coin_id)
            if symbol:
                ticker = f"{symbol}-USD"
        except Exception as exc:
            yahoo_error = str(exc)

    if ticker:
        try:
            df = _history_from_yahoo(ticker, period)
            if len(df) >= 15:
                return df, None
            yahoo_error = f"Yahoo returned too little history for {ticker}."
        except Exception as exc:
            yahoo_error = str(exc)

    try:
        df = _coingecko_ohlc(coin_id, days)
        if len(df) >= 15:
            return df, None
    except Exception as exc:
        yahoo_error = str(exc)

    detail = f" ({yahoo_error})" if yahoo_error else ""
    return pd.DataFrame(), (
        f"No price history for '{entered or coin_id}'. Use a ticker such as XLM or a CoinGecko id such as stellar.{detail}"
    )


def fetch_stock_data(ticker: str, period: str = "1y") -> tuple[pd.DataFrame, str | None]:
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return pd.DataFrame(), "Missing ticker."
    try:
        df = _history_from_yahoo(ticker, period)
    except Exception as exc:
        return pd.DataFrame(), f"Could not load {ticker}: {exc}"
    if len(df) < 15:
        return pd.DataFrame(), f"No price history for {ticker}. Check the ticker symbol."
    return df, None


def get_current_price_crypto(coin_id: str) -> float | None:
    coin_id = resolve_crypto_id(coin_id)
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin_id, "vs_currencies": "usd"},
            headers=_HEADERS,
            timeout=5,
        )
        return response.json().get(coin_id, {}).get("usd")
    except Exception:
        return None


_LOGO_MISS: set[str] = set()


def _https_logo(url) -> str:
    if not isinstance(url, str):
        return ""
    cleaned = url.strip()
    if not cleaned.startswith("https://") or len(cleaned) > 500:
        return ""
    if any(mark in cleaned for mark in (" ", '"', "'", "<", ">", "\\")):
        return ""
    return cleaned


def finnhub_api_key() -> str:
    """Finnhub key from the environment, or from the Streamlit secrets."""
    key = (os.getenv("FINNHUB_API_KEY") or "").strip()
    if key:
        return key
    try:
        import streamlit as st
        key = str(st.secrets["finnhub"]["api_key"]).strip()
    except Exception:
        return ""
    if key:
        os.environ["FINNHUB_API_KEY"] = key
    return key


def _finite_cap(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number <= 0:
        return None
    return number


def format_market_cap(value) -> str:
    """Compact dollar size, such as $1.65T or $4.10B. A dash when unknown."""
    number = _finite_cap(value)
    if number is None:
        return "—"
    for suffix, scale in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if number >= scale:
            shown = number / scale
            if shown >= 100:
                text = f"{shown:.0f}"
            elif shown >= 10:
                text = f"{shown:.1f}"
            else:
                text = f"{shown:.2f}"
            return f"${text}{suffix}"
    return f"${number:,.0f}"


def crypto_market_caps(coin_ids) -> dict[str, float]:
    """Latest USD market cap from CoinGecko. One request for the whole list."""
    ids = []
    for coin_id in coin_ids or []:
        cleaned = str(coin_id or "").strip().lower()
        if cleaned and cleaned not in ids:
            ids.append(cleaned)
    if not ids:
        return {}
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "ids": ",".join(ids),
                "per_page": min(len(ids), 250),
                "page": 1,
                "sparkline": "false",
            },
            headers=_HEADERS,
            timeout=15,
        )
    except Exception:
        return {}
    if response.status_code != 200:
        return {}
    found = {}
    for item in response.json() or []:
        if not isinstance(item, dict):
            continue
        coin_id = str(item.get("id") or "").strip().lower()
        cap = _finite_cap(item.get("market_cap"))
        if coin_id and cap is not None:
            found[coin_id] = cap
    return found


def _stock_market_cap(symbol: str) -> float | None:
    try:
        value = _yahoo().Ticker(symbol).fast_info.market_cap
    except Exception:
        return None
    return _finite_cap(value)


def stock_market_caps(tickers) -> dict[str, float]:
    """Latest USD market cap from Yahoo. Missing tickers are left out."""
    symbols = []
    for ticker in tickers or []:
        symbol = str(ticker or "").strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    if not symbols:
        return {}
    found = {}
    workers = min(6, len(symbols))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for symbol, cap in zip(symbols, pool.map(_stock_market_cap, symbols)):
            if cap is not None:
                found[symbol] = cap
    return found


def crypto_logo_urls(coin_ids) -> dict[str, str]:
    """Small CoinGecko image for each coin. One request for the whole list."""
    ids = []
    for coin_id in coin_ids or []:
        cleaned = str(coin_id or "").strip().lower()
        if cleaned and cleaned not in ids:
            ids.append(cleaned)
    if not ids:
        return {}
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "ids": ",".join(ids),
                "per_page": min(len(ids), 250),
                "page": 1,
                "sparkline": "false",
            },
            headers=_HEADERS,
            timeout=15,
        )
    except Exception:
        return {}
    if response.status_code != 200:
        return {}
    found = {}
    for item in response.json() or []:
        if not isinstance(item, dict):
            continue
        url = _https_logo(item.get("image"))
        coin_id = str(item.get("id") or "").strip().lower()
        if coin_id and url:
            found[coin_id] = url
    return found


def stock_logo_url(ticker: str) -> str:
    """Logo address from Finnhub's company profile. Empty when Finnhub has none."""
    symbol = str(ticker or "").strip().upper()
    if not symbol or symbol in _LOGO_MISS:
        return ""
    key = finnhub_api_key()
    if not key:
        return ""
    try:
        response = requests.get(
            "https://finnhub.io/api/v1/stock/profile2",
            params={"symbol": symbol, "token": key},
            timeout=10,
        )
    except Exception:
        return ""
    if response.status_code != 200:
        return ""
    logo = _https_logo((response.json() or {}).get("logo"))
    if not logo:
        _LOGO_MISS.add(symbol)
    return logo


def get_current_price_stock(ticker: str) -> float | None:
    try:
        stock = _yahoo().Ticker(ticker)
        return stock.fast_info.get("last_price") or stock.info.get("regularMarketPrice")
    except Exception:
        return None
