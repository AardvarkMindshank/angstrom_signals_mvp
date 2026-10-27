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
DERIBIT_URL = "https://www.deribit.com/api/v2/public/get_funding_rate_history"
DERIBIT_INSTRUMENTS = {"BTC": "BTC-PERPETUAL", "ETH": "ETH-PERPETUAL"}
DERIBIT_CHUNK_DAYS = 30
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


def fetch_deribit_funding(instrument: str, start: pd.Timestamp, getter=None, pause: float = 0.1, now=None) -> pd.Series:
    """Hourly funding on a Deribit perpetual since start, in 30-day pieces.

    Used when Binance refuses the connection (it blocks many data-centre
    locations). Each hourly row is the funding charged for that hour, so
    daily_funding adds them up to a daily total just as it does for Binance.
    """
    if getter is None:
        import requests

        def getter(url, params):
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            return response.json()

    begin = pd.Timestamp(start)
    begin = begin.tz_localize("UTC") if begin.tzinfo is None else begin.tz_convert("UTC")
    stop = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz="UTC")
    stop = stop.tz_localize("UTC") if stop.tzinfo is None else stop.tz_convert("UTC")
    step = pd.Timedelta(days=DERIBIT_CHUNK_DAYS)
    times, rates = [], []
    cursor = begin
    for _ in range(150):  # about 12 years; just a runaway guard
        if cursor >= stop:
            break
        end = min(cursor + step, stop)
        payload = getter(DERIBIT_URL, {
            "instrument_name": instrument,
            "start_timestamp": int(cursor.timestamp() * 1000),
            "end_timestamp": int(end.timestamp() * 1000),
        })
        for row in (payload or {}).get("result") or []:
            try:
                times.append(pd.Timestamp(int(row["timestamp"]), unit="ms", tz="UTC"))
                rates.append(float(row["interest_1h"]))
            except (KeyError, TypeError, ValueError):
                continue
        cursor = end
        time.sleep(pause)
    if not times:
        return pd.Series(dtype=float)
    series = pd.Series(rates, index=pd.DatetimeIndex(times), dtype=float)
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


def _daily_closes(closes: pd.Series) -> pd.Series:
    """Closes on plain calendar dates: no time zone, one row per day.

    Funding days are plain dates, so price days carrying a time zone would
    match nothing and every result would come back empty.
    """
    closes = closes.copy()
    index = pd.DatetimeIndex(closes.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    closes.index = index.normalize()
    return closes[~closes.index.duplicated(keep="last")]


def funding_report(features: pd.DataFrame, closes: pd.Series, horizons=bt.DEFAULT_HORIZONS) -> dict:
    """Direction and move-size results for each feature and horizon."""
    closes = _daily_closes(closes)
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


# ---------------------------------------------------------------- for the dashboard

SUMMARY_HORIZONS = (3, 7, 14)


def funding_summary(daily: pd.Series, closes: pd.Series, horizons=SUMMARY_HORIZONS) -> dict | None:
    """Today's funding and whether extreme funding went with bigger moves for this coin.

    Uses the |level| feature, judged after removing trailing volatility, and reports the
    result for the whole history and for each half so a one-period effect is visible.
    """
    features = funding_features(daily)
    level = features[DIRECTION_FEATURES[0]].dropna()
    if len(level) < 400:
        return None
    closes = _daily_closes(closes)
    extreme = features[SIZE_FEATURES[0]].reindex(closes.index)
    control = bt.trailing_activity(closes)
    now = float(level.iloc[-1])
    block = {
        "level_now": round(now, 2),
        "extremeness_percentile": round(float((level.abs() < abs(now)).mean() * 100.0), 1),
        "days": int(len(level)),
        "since": str(level.index[0])[:10],
        "size": {},
    }
    for horizon in horizons:
        future = bt.forward_activity(closes, int(horizon))
        frame = pd.DataFrame({"x": extreme, "y": future, "z": control}).dropna()
        middle = len(frame) // 2
        block["size"][str(horizon)] = {
            "ic": _round(bt.partial_rank_correlation(frame["x"], frame["y"], frame["z"])),
            "noise": _round(bt.noise_floor(bt.effective_n(len(frame), int(horizon)))),
            "first_half": _round(bt.partial_rank_correlation(*(frame.iloc[:middle][c] for c in ("x", "y", "z")))),
            "second_half": _round(bt.partial_rank_correlation(*(frame.iloc[middle:][c] for c in ("x", "y", "z")))),
        }
    return block


def _round(value):
    return None if value is None or not math.isfinite(value) else round(float(value), 4)


def funding_text(block: dict | None) -> str | None:
    """Plain sentences from a funding_summary. Never claims direction."""
    if not block:
        return None
    now, pct = block.get("level_now"), block.get("extremeness_percentile")
    if now is None or pct is None:
        return None
    sizes = (block.get("size") or {}).values()
    passed = [
        info for info in sizes
        if info.get("ic") is not None and info.get("noise") is not None and info["ic"] >= info["noise"]
    ]
    both_halves = [
        info for info in passed
        if (info.get("first_half") or 0) > 0 and (info.get("second_half") or 0) > 0
    ]
    text = (
        f"Funding on this coin's perpetual futures is {now:+.0f}% a year, more extreme than {pct:.0f}% of days "
        f"since {block.get('since', '?')}."
    )
    if len(passed) >= 2 and len(both_halves) >= 2:
        text += (
            " For this coin, unusually high or low funding has been followed by bigger price moves over the next "
            "3 to 14 days, beyond what recent volatility already showed, in both halves of its history. "
            "That is about size, not direction."
        )
    elif len(passed) >= 2:
        text += (
            " For this coin, extreme funding has been followed by bigger moves, but mostly in one half of its "
            "history, so treat it as a weak hint. That is about size, not direction."
        )
    else:
        text += " For this coin, the link between extreme funding and the size of later moves was not clear in this test."
    return text
