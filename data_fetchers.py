"""
Market data for the dashboard and the alert worker.

Crypto tries Yahoo Finance first, then CoinGecko OHLC.
Equities come from Yahoo Finance.
Both functions return (dataframe, error_message). error_message is None on success.
"""

from __future__ import annotations

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

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SignalsDashboard/1.0)"}


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
    coin_id = (coin_id or "").strip().lower()
    if not coin_id:
        return pd.DataFrame(), "Missing crypto id."

    period = period_for_days(days)
    ticker = YF_BY_COINGECKO_ID.get(coin_id)
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
        f"No price history for '{coin_id}'. Use a CoinGecko id such as bitcoin or solana.{detail}"
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


def get_current_price_stock(ticker: str) -> float | None:
    try:
        stock = _yahoo().Ticker(ticker)
        return stock.fast_info.get("last_price") or stock.info.get("regularMarketPrice")
    except Exception:
        return None
