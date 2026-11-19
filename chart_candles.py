"""
The chart's candle sizes: chart_data's (15m to 1W) plus monthly candles ("1Mo", asked 13 Nov 2026) and, for crypto,
5-minute candles ("5m", 19 Nov 2026: a beta tester spots divergence at the low on 5-minute candles).

5-minute candles come straight from Binance spot for the last 7 days only (about 2,300 candles with the warm-up). They
are not stored anywhere: no database traffic, the same small shared memory cache as the other sizes.

Monthly candles are built here from chart_data's daily candles, grouped into calendar months and labelled with the
1st, as TradingView does. They live in this module, not in chart_data.py, because chart_data.py is part of the
replay certification (signal_library/certification.py): changing it would switch off Prism's history replays
until the certification suite ran again. Only the chart uses monthly candles; no signal reads them.
"""

from __future__ import annotations

from i18n import t

from datetime import datetime, timezone

import pandas as pd

import chart_data

MONTHLY = "1Mo"
FIVE = "5m"
FIVE_RANGES = ("7D",)                      # 1 month of 5-minute candles would be ~8,900, over chart_data.MAX_CANDLES
FIVE_TTL = 30                              # seconds a fetch is shared before the newest candle is fetched again
INTERVALS = (FIVE,) + tuple(chart_data.INTERVALS) + (MONTHLY,)
INTERVAL_LABELS = {FIVE: "5 minutes", **chart_data.INTERVAL_LABELS, MONTHLY: "1 month"}
RANGES = chart_data.RANGES


def availability(interval: str, range_key: str) -> tuple[bool, str]:
    if interval == FIVE:
        if range_key not in chart_data.RANGE_DAYS:
            return False, f"Unknown range {range_key}."
        if range_key not in FIVE_RANGES:
            return False, "5-minute candles show the last 7 days only. Pick 7D."
        return True, ""
    if interval != MONTHLY:
        return chart_data.availability(interval, range_key)
    if range_key not in chart_data.RANGE_DAYS:
        return False, f"Unknown range {range_key}."
    days = chart_data.RANGE_DAYS[range_key]
    if days is not None and days < 366:
        return False, f"{chart_data.RANGE_LABELS[range_key]} holds too few monthly candles to read. Pick 1 year or more."
    return True, ""


def nearest_range(interval: str, range_key: str) -> str:
    if availability(interval, range_key)[0]:
        return range_key
    order = list(RANGES)
    start = order.index(range_key) if range_key in order else 0
    for step in range(1, len(order)):
        for index in (start - step, start + step):
            if 0 <= index < len(order) and availability(interval, order[index])[0]:
                return order[index]
    return chart_data.RANGE_DEFAULT


def group_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    """Calendar months, labelled with the 1st."""
    df = chart_data.group_daily(daily)
    if df.empty:
        return df
    first = df.index - pd.to_timedelta(df.index.day - 1, unit="D")
    return chart_data._ohlcv_groups(df, first)


def mark_forming(df: pd.DataFrame, now=None) -> pd.DataFrame:
    """A `forming` column: True for a last month that has not ended yet."""
    out = df.copy()
    out["forming"] = False
    if out.empty:
        return out
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    last = out.index[-1]
    last = last.tz_localize("UTC") if last.tzinfo is None else last
    if now < last + pd.offsets.MonthBegin(1):
        out.iloc[-1, out.columns.get_loc("forming")] = True
    return out


def from_daily(daily: pd.DataFrame, range_key: str, now=None) -> tuple[pd.DataFrame, pd.Timestamp | None, str]:
    """(monthly candles with `forming`, first candle of the range, error or "")."""
    candles = mark_forming(group_monthly(daily[["open", "high", "low", "close", "volume"]]), now)
    if candles.empty:
        return candles, None, t("No monthly candles.")
    days = chart_data.RANGE_DAYS[range_key]
    if days is None:
        start = candles.index[0]
    else:
        clock = pd.Timestamp(now or datetime.now(timezone.utc))
        clock = clock.tz_localize("UTC") if clock.tzinfo is None else clock.tz_convert("UTC")
        start = clock - pd.Timedelta(days=days)
    shown = candles[candles.index >= start]
    if len(shown) < chart_data.MIN_CANDLES:
        return candles, None, (t('Only {len_shown} monthly candles in {chart_data_range_labels_}. Pick a longer range.', len_shown=len(shown), chart_data_range_labels_=chart_data.RANGE_LABELS[range_key]))
    return candles, shown.index[0], ""


def five_minute(kind: str, asset_id: str, range_key: str, now=None, klines=None) -> dict:
    """The last 7 days of 5-minute candles from Binance spot, with chart_data's warm-up before them (crypto only)."""
    out = {"candles": chart_data._empty(), "start": None, "session": None, "source": "", "error": None}
    usable, reason = availability(FIVE, range_key)
    if not usable:
        return {**out, "error": reason}
    if kind != "crypto":
        return {**out, "error": t("5-minute candles are for crypto only. Pick 15m or longer for equities.")}
    try:
        import binance_data as bn

        pair = bn.pair_for(kind, asset_id, chart_data.yahoo_symbol(kind, asset_id), None)
        if pair is None:
            pair = bn.pair_for(kind, asset_id, None, bn.coingecko_coin(asset_id), price_of=bn.last_price)
    except Exception:
        pair = None
    if pair is None:
        return {**out, "error": t("Binance spot does not list this coin, so there are no 5-minute candles for it.")}
    clock = pd.Timestamp(now or datetime.now(timezone.utc))
    clock = clock.tz_localize("UTC") if clock.tzinfo is None else clock.tz_convert("UTC")
    range_start = clock - pd.Timedelta(days=chart_data.RANGE_DAYS[range_key])
    fetch_from = (range_start - pd.Timedelta(minutes=5 * chart_data.WARMUP_CANDLES)).floor("D")
    key = ("binance", pair, FIVE, fetch_from)
    candles = chart_data.CACHE.get(key, FIVE_TTL)
    if candles is None:
        try:
            candles = (klines or bn.klines)(pair, FIVE, fetch_from)
        except Exception:
            candles = None
        if candles is not None and not candles.empty:
            chart_data.CACHE.put(key, candles)
    if candles is None or candles.empty:
        return {**out, "error": t("Binance did not send 5-minute candles just now. Try again in a minute.")}
    candles = candles.copy()
    candles["forming"] = False
    if clock < candles.index[-1] + pd.Timedelta(minutes=5):
        candles.iloc[-1, candles.columns.get_loc("forming")] = True
    in_range = candles[candles.index >= range_start]
    if len(in_range) < chart_data.MIN_CANDLES:
        return {**out, "error": t("Too few 5-minute candles in the last 7 days for this coin.")}
    position = candles.index.get_loc(in_range.index[0])
    candles = candles.iloc[max(0, position - chart_data.WARMUP_CANDLES):].iloc[-chart_data.MAX_CANDLES:]
    label = pair.replace(bn.QUOTE, "/" + bn.QUOTE)
    return {**out, "candles": candles, "start": in_range.index[0],
            "source": f"Binance spot {label} 5 minutes candles (UTC)"}


def load_candles(kind: str, asset_id: str, interval: str, range_key: str, now=None, fetch=None) -> dict:
    """chart_data.load_candles, plus monthly candles grouped from all the daily ones, and 5-minute crypto candles."""
    if interval == FIVE:
        return five_minute(kind, asset_id, range_key, now=now)
    if interval != MONTHLY:
        return chart_data.load_candles(kind, asset_id, interval, range_key, now=now, fetch=fetch)
    usable, reason = availability(interval, range_key)
    if not usable:
        return {"candles": chart_data._empty(), "start": None, "session": None, "source": "", "error": reason}
    daily = chart_data.load_candles(kind, asset_id, "1D", "All", now=now, fetch=fetch)
    if daily["error"]:
        return daily
    candles, start, error = from_daily(daily["candles"], range_key, now)
    if error:
        return {**daily, "candles": chart_data._empty(), "start": None, "error": error}
    source = str(daily.get("source") or "")
    source = (source.replace("1 day candles", "daily candles") + ", grouped into calendar months").lstrip(", ")
    return {"candles": candles, "start": start, "session": None, "source": source, "error": None}
