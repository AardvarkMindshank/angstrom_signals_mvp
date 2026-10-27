"""Does crypto perpetual-futures funding say anything about what price does next?

Funding is the payment between long and short traders on a perpetual contract.
When it is high, longs are paying a lot to stay long (a crowded trade); when it
is very negative, shorts are. Two questions, tested on years of history:

1. Direction: does funding line up with the return that follows?
2. Move size: does extreme funding line up with bigger moves, once recent
   volatility is removed (volatility is sticky, so it must not be mistaken for signal)?

Only data settled before the end of each daily bar is used, and trades happen
one bar after the signal, exactly as in backtest.py.
"""

from __future__ import annotations

import math
import time

import pandas as pd

import backtest as bt

BINANCE_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
PAGE = 1000
DIRECTION_FEATURES = (
    "Funding level (7d avg, annualized %)",
    "Funding percentile (180d)",
    "Funding change (7d)",
)
SIZE_FEATURES = (
    "Funding extremeness |level|",
    "Funding percentile distance from middle",
    "Funding change size |change|",
)


def binance_symbol(ticker: str) -> str:
    """BTC-USD -> BTCUSDT."""
    base = str(ticker).upper().replace("-USD", "").replace("-USDT", "").strip()
    return f"{base}USDT"


def parse_records(rows) -> pd.Series:
    """Binance rows -> funding rate per settlement, indexed by UTC time."""
    times, rates = [], []
    for row in rows or []:
        try:
            times.append(pd.to_datetime(int(row["fundingTime"]), unit="ms", utc=True))
            rates.append(float(row["fundingRate"]))
        except (KeyError, TypeError, ValueError):
            continue
    if not times:
        return pd.Series(dtype=float)
    series = pd.Series(rates, index=pd.DatetimeIndex(times), dtype=float)
    return series[~series.index.duplicated(keep="last")].sort_index()


def fetch_binance_funding(symbol: str, start: pd.Timestamp, getter=None, pause: float = 0.15) -> pd.Series:
    """All funding settlements since start. Pages of 1000 until the data runs out."""
    if getter is None:
        import requests

        def getter(url, params):
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            return response.json()

    stamp = pd.Timestamp(start)
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    cursor = int(stamp.timestamp() * 1000)
    chunks = []
    for _ in range(40):  # about 100 years of 8-hour payments; just a runaway guard
        rows = getter(BINANCE_URL, {"symbol": symbol, "startTime": cursor, "limit": PAGE})
        if not rows:
            break
        chunks.append(parse_records(rows))
        last = int(rows[-1]["fundingTime"])
        if len(rows) < PAGE or last <= cursor:
            break
        cursor = last + 1
        time.sleep(pause)
    if not chunks:
        return pd.Series(dtype=float)
    series = pd.concat(chunks)
    return series[~series.index.duplicated(keep="last")].sort_index()


def daily_funding(series: pd.Series) -> pd.Series:
    """Total funding rate settled on each UTC date. Needs at least two payments that day."""
    if series is None or series.empty:
        return pd.Series(dtype=float)
    days = series.index.tz_convert("UTC").tz_localize(None).normalize()
    grouped = series.groupby(days)
    total, count = grouped.sum(), grouped.count()
    return total[count >= 2]


def funding_features(daily: pd.Series) -> pd.DataFrame:
    """Features known by the close of each day. Annualized percent for readability."""
    level = daily.rolling(7).mean() * 365 * 100.0
    percentile = level.rolling(180).apply(lambda window: float((window[:-1] < window[-1]).mean()), raw=True)
    change = level - level.shift(7)
    return pd.DataFrame({
        DIRECTION_FEATURES[0]: level,
        DIRECTION_FEATURES[1]: percentile,
        DIRECTION_FEATURES[2]: change,
        SIZE_FEATURES[0]: level.abs(),
        SIZE_FEATURES[1]: (percentile - 0.5).abs(),
        SIZE_FEATURES[2]: change.abs(),
    })


def funding_report(features: pd.DataFrame, closes: pd.Series, horizons=bt.DEFAULT_HORIZONS) -> dict:
    """Direction and move-size results for each feature and horizon."""
    closes = closes.copy()
    closes.index = pd.DatetimeIndex(closes.index).normalize()
    closes = closes[~closes.index.duplicated(keep="last")]
    both = features.reindex(closes.index).dropna(how="all")
    control = bt.trailing_activity(closes).reindex(both.index)
    report = {"days": int(both.dropna().shape[0]), "direction": {}, "size": {}}
    for horizon in horizons:
        fwd = bt.forward_returns(closes, int(horizon)).reindex(both.index)
        future = bt.forward_activity(closes, int(horizon)).reindex(both.index)
        pair = pd.DataFrame({"x": both[DIRECTION_FEATURES[0]], "y": fwd}).dropna()
        noise = bt.noise_floor(bt.effective_n(len(pair), int(horizon)))
        for name in DIRECTION_FEATURES:
            report["direction"].setdefault(name, {})[int(horizon)] = {
                "ic": bt.rank_correlation(both[name], fwd), "noise_floor": noise,
            }
        for name in SIZE_FEATURES:
            report["size"].setdefault(name, {})[int(horizon)] = {
                "ic": bt.partial_rank_correlation(both[name], future, control), "noise_floor": noise,
            }
    return report


def format_funding_report(reports: dict[str, dict], horizons=bt.DEFAULT_HORIZONS) -> str:
    names = list(reports)
    lines = [
        "Funding test: does perpetual-futures funding say anything about what price does next?",
        "Numbers are rank correlations. 'holds' needs the same direction and a size beyond the noise on EVERY coin.",
        "Direction: with the return that follows. Move size: with how big the moves that follow are, after removing",
        "what trailing 14-day volatility already tells you.",
        "",
        "Days of funding data used: " + ", ".join(f"{n} {reports[n]['days']}" for n in names),
    ]
    for key, title, features in (("direction", "DIRECTION", DIRECTION_FEATURES), ("size", "MOVE SIZE", SIZE_FEATURES)):
        for horizon in horizons:
            lines.append("")
            lines.append(f"{title}, next {horizon} day{'s' if horizon != 1 else ''}")
            width = max(len(f) for f in features)
            lines.append(f"  {'feature':<{width}}" + "".join(f"{n[:9]:>10}" for n in names) + f"{'noise':>8}  holds")
            for feature in features:
                cells_src = [reports[n][key].get(feature, {}).get(int(horizon), {}) for n in names]
                cells = "".join(f"{bt._num(item.get('ic')):>10}" for item in cells_src)
                floors = [item.get("noise_floor") for item in cells_src if item.get("noise_floor") is not None]
                noise = f"±{max(floors):.2f}" if floors else "-"
                mark = "YES" if bt.holds_up(cells_src) else ""
                lines.append(f"  {feature:<{width}}{cells}{noise:>8}  {mark}")
    lines.append("")
    lines.append(
        "Reading it: 6 features, 4 horizons and several coins means a few rows can look good by luck. Trust a "
        "feature only if it holds at several horizons and on most coins, and the sign makes sense "
        "(crowded longs followed by weaker returns would be the contrarian reading)."
    )
    return "\n".join(lines)


def run_funding(frames: dict, horizons) -> dict:
    """frames maps ticker -> price frame. Returns the per-coin reports."""
    reports = {}
    for ticker, frame in frames.items():
        start = frame.index[0]
        symbol = binance_symbol(ticker)
        print(f"Funding for {symbol} ...", flush=True)
        series = fetch_binance_funding(symbol, start)
        daily = daily_funding(series)
        if len(daily) < 400:
            print(f"{ticker}: only {len(daily)} days of funding; skipped.")
            continue
        reports[ticker] = funding_report(funding_features(daily), frame["close"], horizons)
    return reports
