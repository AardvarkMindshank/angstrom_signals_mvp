"""Sanity check, run by .github/workflows/data-probe.yml: Binance spot daily closes against Yahoo Finance's for a few
coins (UTC days both), and how many coins in our list Binance can serve."""

import sys

import pandas as pd

import binance_data as bn

COINS = [("bitcoin", "BTC-USD"), ("ethereum", "ETH-USD"), ("solana", "SOL-USD"), ("ripple", "XRP-USD"),
         ("dogecoin", "DOGE-USD")]


def main() -> int:
    pairs = bn.trading_pairs()
    print(f"Binance spot USDT pairs trading: {len(pairs)}")
    worst = 0.0
    for asset_id, ticker in COINS:
        pair = bn.pair_for("crypto", asset_id, ticker, pairs=pairs)
        b = bn.klines(pair, "1D", pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=60))["close"]
        import yfinance as yf
        y = yf.Ticker(ticker).history(period="3mo", interval="1d", auto_adjust=False)["Close"]
        y.index = pd.to_datetime(y.index).tz_convert("UTC").normalize() if y.index.tz else pd.to_datetime(y.index).tz_localize("UTC")
        both = pd.concat([b.rename("binance"), y.rename("yahoo")], axis=1).dropna().iloc[:-1]   # drop today's forming day
        gap = (both["binance"] / both["yahoo"] - 1).abs()
        worst = max(worst, gap.max())
        print(f"{ticker:9} {pair:9} days {len(both):3}  median gap {gap.median()*100:.3f}%  max {gap.max()*100:.3f}%")
    print(f"Largest daily close gap: {worst*100:.3f}% (USDT vs USD and different venues, so about a tenth of a percent is normal)")
    return 0 if worst < 0.02 else 1


if __name__ == "__main__":
    sys.exit(main())
