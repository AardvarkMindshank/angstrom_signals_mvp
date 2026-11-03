"""
Fixtures for the browser test of the TradingView chart (chart_browser_check.js).

Builds payloads with lw_chart.build_payload from made-up candles. The indicator
columns are filled with simple stand-ins (rolling means and bounded waves) because
this test checks drawing, not formulas; the formulas stay in scoring.py.

Usage: python chart_browser_fixtures.py --out <folder>
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd

import chart_data
import chart_plan
import lw_chart


def _stand_in_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["close"]
    n = len(df)
    wave = np.sin(np.arange(n) / 9.0)
    df["sma_20"] = close.rolling(20).mean()
    df["sma_50"] = close.rolling(50).mean()
    df["sma_200"] = close.rolling(200).mean()
    std = close.rolling(20).std()
    df["BBU_20_2.0"] = df["sma_20"] + 2 * std
    df["BBL_20_2.0"] = df["sma_20"] - 2 * std
    df["ichi_tenkan"] = (df["high"].rolling(9).max() + df["low"].rolling(9).min()) / 2
    df["ichi_kijun"] = (df["high"].rolling(26).max() + df["low"].rolling(26).min()) / 2
    df["ichi_span_a"] = ((df["ichi_tenkan"] + df["ichi_kijun"]) / 2).shift(26)
    df["ichi_span_b"] = ((df["high"].rolling(52).max() + df["low"].rolling(52).min()) / 2).shift(26)
    df["rsi"] = 50 + 30 * wave
    df["MACD_12_26_9"] = close.ewm(span=12).mean() - close.ewm(span=26).mean()
    df["MACDs_12_26_9"] = df["MACD_12_26_9"].ewm(span=9).mean()
    df["MACDh_12_26_9"] = df["MACD_12_26_9"] - df["MACDs_12_26_9"]
    df["stoch_k"] = 50 + 45 * np.sin(np.arange(n) / 5.0)
    df["adx"] = 25 + 10 * np.cos(np.arange(n) / 13.0)
    df["obv"] = (np.sign(close.diff().fillna(0)) * df["volume"]).cumsum()
    df["obv_sma_20"] = df["obv"].rolling(20).mean()
    return df


def _candles(index, seed=1, start=100.0):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 1, len(index)).cumsum()
    close = start + steps
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.random(len(index))
    low = np.minimum(open_, close) - rng.random(len(index))
    volume = rng.integers(1000, 5000, len(index)).astype(float)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=index)


def crypto_4h(now=pd.Timestamp("2026-11-03 10:30", tz="UTC")):
    index = pd.date_range(end="2026-11-03 08:00", periods=600, freq="4h", tz="UTC")
    df = _stand_in_indicators(_candles(index))
    df = chart_data.mark_forming(df, "4h", "crypto", now=now)
    return df


def equity_daily():
    days = pd.bdate_range(end="2026-11-02", periods=500)
    index = pd.DatetimeIndex([pd.Timestamp(d, tz="UTC") for d in days])
    df = _stand_in_indicators(_candles(index, seed=2, start=180))
    df = chart_data.mark_forming(df, "1D", "equity", now=pd.Timestamp("2026-11-03 01:00", tz="UTC"),
                                 session=("America/New_York", 570, 960))
    return df


def equity_1h():
    stamps = []
    for day in pd.bdate_range(end="2026-11-02", periods=80):
        for hour in range(7):
            stamps.append(pd.Timestamp(f"{day.date()} 09:30", tz="America/New_York") + pd.Timedelta(hours=hour))
    df = _stand_in_indicators(_candles(pd.DatetimeIndex(stamps), seed=3, start=230))
    return chart_data.mark_forming(df, "1h", "equity", now=pd.Timestamp("2026-11-02 20:30", tz="UTC"),
                                   session=("America/New_York", 570, 960))


def payloads() -> dict:
    out = {}
    df = crypto_4h()
    every = ["sma200", "ichimoku", "macd", "stoch", "adx", "obv"]
    layout = chart_plan.plan(every, df.columns, overlay_curves=False)
    out["crypto_4h_all"] = lw_chart.build_payload(
        df, layout, kind="crypto", interval="4h", range_key="1M", range_start=df.index[-180],
        view_key="crypto:bitcoin|4h|1M", price_px=380, dark=False, title="Bitcoin",
        source="Test candles", liquidation={"status": "ok", "longs": [{"price": float(df["close"].iloc[-1]) * 0.95, "usd": 5e7}],
                                            "shorts": [{"price": float(df["close"].iloc[-1]) * 1.05, "usd": 2e7}]},
    )
    layout_over = chart_plan.plan(["stoch", "adx"], df.columns, overlay_curves=True)
    out["crypto_4h_overlay"] = lw_chart.build_payload(
        df, layout_over, kind="crypto", interval="4h", range_key="1M", range_start=df.index[-180],
        view_key="crypto:bitcoin|4h|1M", price_px=380, dark=True, title="Bitcoin", source="Test candles",
    )
    eq = equity_daily()
    layout_eq = chart_plan.plan([], eq.columns, overlay_curves=False)
    out["equity_daily_earnings"] = lw_chart.build_payload(
        eq, layout_eq, kind="equity", interval="1D", range_key="3M", range_start=eq.index[-65],
        view_key="equity:AAPL|1D|3M", price_px=380, title="Apple (AAPL)", source="Test candles",
        past_reports=[str(eq.index[-40].date())], next_report="2026-11-20",
        session=("America/New_York", 570, 960),
    )
    out["equity_daily_earnings"]["has_earnings"] = True
    h1 = equity_1h()
    out["equity_1h"] = lw_chart.build_payload(
        h1, chart_plan.plan(["macd"], h1.columns), kind="equity", interval="1h", range_key="1M",
        range_start=h1.index[-150], view_key="equity:AAPL|1h|1M", price_px=380, title="Apple (AAPL)",
        source="Test candles", session=("America/New_York", 570, 960),
    )
    return out


def live_payloads() -> dict:
    """The same four charts from live Yahoo candles with the real indicator library (CI only)."""
    from scoring import calculate_indicators

    def frame(kind, asset, interval, range_key):
        loaded = chart_data.load_candles(kind, asset, interval, range_key)
        if loaded["error"]:
            raise SystemExit(f"{asset} {interval} {range_key}: {loaded['error']}")
        candles = loaded["candles"]
        df = calculate_indicators(candles[["open", "high", "low", "close", "volume"]])
        df["forming"] = candles["forming"]
        return df, loaded

    out = {}
    df, info = frame("crypto", "bitcoin", "4h", "1M")
    every = ["sma200", "ichimoku", "macd", "stoch", "adx", "obv"]
    out["crypto_4h_all"] = lw_chart.build_payload(
        df, chart_plan.plan(every, df.columns), kind="crypto", interval="4h", range_key="1M",
        range_start=info["start"], view_key="crypto:bitcoin|4h|1M", title="Bitcoin", source=info["source"])
    out["crypto_4h_overlay"] = lw_chart.build_payload(
        df, chart_plan.plan(["stoch", "adx"], df.columns, overlay_curves=True), kind="crypto", interval="4h",
        range_key="1M", range_start=info["start"], view_key="crypto:bitcoin|4h|1M", dark=True, title="Bitcoin",
        source=info["source"])
    df, info = frame("equity", "AAPL", "1D", "3M")
    out["equity_daily_earnings"] = lw_chart.build_payload(
        df, chart_plan.plan([], df.columns), kind="equity", interval="1D", range_key="3M",
        range_start=info["start"], view_key="equity:AAPL|1D|3M", title="Apple (AAPL)", source=info["source"],
        session=info["session"], past_reports=[str(df.index[-40].date())])
    out["equity_daily_earnings"]["has_earnings"] = True
    df, info = frame("equity", "AAPL", "1h", "1M")
    out["equity_1h"] = lw_chart.build_payload(
        df, chart_plan.plan(["macd"], df.columns), kind="equity", interval="1h", range_key="1M",
        range_start=info["start"], view_key="equity:AAPL|1h|1M", title="Apple (AAPL)", source=info["source"],
        session=info["session"])
    df, info = frame("crypto", "ethereum", "15m", "1M")
    out["crypto_15m_large"] = lw_chart.build_payload(
        df, chart_plan.plan(every, df.columns), kind="crypto", interval="15m", range_key="1M",
        range_start=info["start"], view_key="crypto:ethereum|15m|1M", title="Ethereum", source=info["source"])
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="out")
    parser.add_argument("--live", action="store_true", help="live Yahoo candles and the real indicator library")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for name, payload in (live_payloads() if args.live else payloads()).items():
        with open(os.path.join(args.out, f"{name}.json"), "w") as handle:
            json.dump(payload, handle, separators=(",", ":"))
        print(name, lw_chart.payload_size(payload), "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
