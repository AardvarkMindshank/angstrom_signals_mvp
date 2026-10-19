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

def fetch_crypto_data(coin_id: str, days: int = 90) -> pd.DataFrame:
    """
    Fetch OHLCV-like data for a crypto from CoinGecko.
    Includes stronger retry/backoff for rate limits.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days,
        "interval": "daily"
    }
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SignalsDashboard/1.0)"}

    for attempt in range(4):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=20)
            if response.status_code == 429:
                wait = 3 * (attempt + 1)
                print(f"Rate limited on {coin_id}, waiting {wait}s...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            data = response.json()

            prices = data.get("prices", [])
            volumes = data.get("total_volumes", [])

            if not prices:
                # Try once more after a short pause
                if attempt < 3:
                    time.sleep(2)
                    continue
                return pd.DataFrame()

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

            df = df[["open", "high", "low", "close", "volume"]].dropna()
            return df
        except Exception as e:
            print(f"Error fetching crypto {coin_id} (attempt {attempt+1}): {e}")
            if attempt == 3:
                return pd.DataFrame()
            time.sleep(2)
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
