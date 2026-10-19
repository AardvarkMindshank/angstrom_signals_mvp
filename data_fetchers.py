"""
Data fetchers for the Phase 1 MVP.
- Crypto: CoinGecko (free, no key required for basic use)
- Stocks: yfinance (free)
"""

import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

import time

def fetch_crypto_data(coin_id: str, days: int = 200) -> pd.DataFrame:
    """
    Fetch crypto data. Tries yfinance first (more reliable), falls back to CoinGecko.
    coin_id examples: 'bitcoin', 'ethereum', 'solana', 'cardano', 'ripple'
    """
    # Map CoinGecko-style ids to yfinance tickers
    yf_map = {
        "bitcoin": "BTC-USD",
        "ethereum": "ETH-USD",
        "solana": "SOL-USD",
        "cardano": "ADA-USD",
        "ripple": "XRP-USD",
    }
    yf_ticker = yf_map.get(coin_id.lower(), f"{coin_id.upper()}-USD")

    # Try yfinance first
    try:
        period = "1y" if days > 180 else "6mo"
        df = yf.Ticker(yf_ticker).history(period=period)
        if not df.empty and len(df) > 30:
            df = df.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"
            })
            return df[["open", "high", "low", "close", "volume"]].dropna()
    except Exception as e:
        print(f"yfinance failed for {coin_id}: {e}")

    # Fallback to CoinGecko
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SignalsDashboard/1.0)"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            prices = data.get("prices", [])
            volumes = data.get("total_volumes", [])
            if prices:
                df = pd.DataFrame(prices, columns=["timestamp", "close"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.set_index("timestamp", inplace=True)
                df["open"] = df["close"].shift(1).fillna(df["close"])
                df["high"] = df["close"]
                df["low"] = df["close"]
                if volumes:
                    vol_df = pd.DataFrame(volumes, columns=["timestamp", "volume"])
                    vol_df["timestamp"] = pd.to_datetime(vol_df["timestamp"], unit="ms")
                    vol_df.set_index("timestamp", inplace=True)
                    df = df.join(vol_df["volume"], how="left")
                else:
                    df["volume"] = 0
                return df[["open", "high", "low", "close", "volume"]].dropna()
    except Exception as e:
        print(f"CoinGecko fallback failed for {coin_id}: {e}")

    return pd.DataFrame()


def fetch_stock_data(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """
    Fetch OHLCV data for a stock using yfinance.
    ticker examples: 'AAPL', 'MSFT', 'TSLA'
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        if df.empty:
            return pd.DataFrame()
        # yfinance returns columns: Open, High, Low, Close, Volume
        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })
        return df[["open", "high", "low", "close", "volume"]].dropna()
    except Exception as e:
        print(f"Error fetching stock {ticker}: {e}")
        return pd.DataFrame()


def get_current_price_crypto(coin_id: str) -> float | None:
    """Quick current price for a crypto."""
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": coin_id, "vs_currencies": "usd"}
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        return data.get(coin_id, {}).get("usd")
    except:
        return None


def get_current_price_stock(ticker: str) -> float | None:
    """Quick current price for a stock."""
    try:
        stock = yf.Ticker(ticker)
        return stock.fast_info.get("last_price") or stock.info.get("regularMarketPrice")
    except:
        return None
