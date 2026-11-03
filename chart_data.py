"""
Candles for the price chart at 15-minute, 1-hour, 4-hour, daily and weekly intervals.

Only the chart uses this module. Trend, Stretch, Flow, alerts and evidence keep
reading the shared daily bars, so nothing here changes a signal.

Where the candles come from
- 15m: Yahoo 15-minute bars. Yahoo keeps about 60 days of them.
- 1h:  Yahoo 60-minute bars. Yahoo keeps about 730 days of them.
- 4h:  Yahoo has no 4-hour bars, so 60-minute bars are grouped:
       crypto in fixed UTC blocks (00:00, 04:00, 08:00 ...);
       shares from the session open (US: 09:30-13:30 and 13:30-16:00 New York),
       so a 4-hour candle never spans the overnight gap. This matches TradingView.
- 1D:  Yahoo daily bars.
- 1W:  daily bars grouped into Monday-to-Sunday weeks.

Intraday candles are never made from daily bars. When Yahoo does not keep enough
history for an interval and range, the pair is reported as unavailable instead of
being quietly replaced by something else.
"""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

import pandas as pd

INTERVALS = ("15m", "1h", "4h", "1D", "1W")
RANGES = ("7D", "1M", "3M", "1Y", "All")
INTERVAL_DEFAULT = "1D"
RANGE_DEFAULT = "3M"

INTERVAL_LABELS = {
    "15m": "15 minutes",
    "1h": "1 hour",
    "4h": "4 hours",
    "1D": "1 day",
    "1W": "1 week",
}
RANGE_LABELS = {"7D": "7 days", "1M": "1 month", "3M": "3 months", "1Y": "1 year", "All": "all history"}
RANGE_DAYS = {"7D": 7, "1M": 31, "3M": 92, "1Y": 366, "All": None}

# Yahoo interval, how far back Yahoo keeps it (days, None = no limit), and the
# step of the candles we build (minutes; None = calendar day or week).
_SOURCE = {
    "15m": ("15m", 59, 15),
    "1h": ("60m", 729, 60),
    "4h": ("60m", 729, 240),
    "1D": ("1d", None, None),
    "1W": ("1d", None, None),
}

# Fewer candles than this in the chosen range is too few to read.
MIN_CANDLES = 6
# Candles kept before the chosen range so indicators such as SMA 200 and
# Ichimoku are already settled when the range starts. You can also scroll back to them.
WARMUP_CANDLES = 260
# The most candles sent to the browser in one go.
MAX_CANDLES = 4000

_US_OPEN = (9, 30)
_US_CLOSE = (16, 0)


# --------------------------------------------------------------------------
# Which interval and range pairs work
# --------------------------------------------------------------------------

def availability(interval: str, range_key: str) -> tuple[bool, str]:
    """(usable, reason). The reason is a plain sentence when not usable."""
    if interval not in _SOURCE:
        return False, f"Unknown interval {interval}."
    if range_key not in RANGE_DAYS:
        return False, f"Unknown range {range_key}."
    _yahoo_interval, keep_days, _step = _SOURCE[interval]
    days = RANGE_DAYS[range_key]
    if keep_days is not None and (days is None or days > keep_days + 1):
        kept = "about 60 days" if interval == "15m" else "about 2 years"
        return False, (
            f"{INTERVAL_LABELS[interval]} candles only go back {kept}, "
            f"so {RANGE_LABELS[range_key]} cannot be shown at this interval."
        )
    if interval == "1W" and days is not None and days < 92:
        return False, f"{RANGE_LABELS[range_key]} holds too few weekly candles to read. Pick 3 months or more."
    return True, ""


def matrix() -> dict[str, dict[str, tuple[bool, str]]]:
    return {interval: {r: availability(interval, r) for r in RANGES} for interval in INTERVALS}


def nearest_range(interval: str, range_key: str) -> str:
    """The closest usable range when the chosen pair does not work. Used only
    to suggest a choice; the chart says what changed rather than switching silently."""
    if availability(interval, range_key)[0]:
        return range_key
    order = list(RANGES)
    start = order.index(range_key) if range_key in order else 0
    for step in range(1, len(order)):
        for index in (start - step, start + step):
            if 0 <= index < len(order) and availability(interval, order[index])[0]:
                return order[index]
    return RANGE_DEFAULT


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------

def _minutes(hour_minute) -> int:
    return int(hour_minute[0]) * 60 + int(hour_minute[1])


def session_from_metadata(meta: dict | None):
    """(timezone name, open minute, close minute) from Yahoo's history metadata, or None."""
    if not isinstance(meta, dict):
        return None
    tz = meta.get("exchangeTimezoneName")
    regular = ((meta.get("currentTradingPeriod") or {}).get("regular") or {})
    try:
        start = int(regular["start"])
        end = int(regular["end"])
        zone = regular.get("timezone") or tz
        start_local = pd.Timestamp(start, unit="s", tz="UTC").tz_convert(zone)
        end_local = pd.Timestamp(end, unit="s", tz="UTC").tz_convert(zone)
        return (str(zone), start_local.hour * 60 + start_local.minute, end_local.hour * 60 + end_local.minute)
    except Exception:
        return None


def session_from_bars(df: pd.DataFrame, step: int):
    """Open and close guessed from the bars themselves: the usual first bar time
    and the usual last bar end. Used when Yahoo sends no session details."""
    if df is None or df.empty or df.index.tz is None:
        return None
    local = df.index
    days = pd.Series(local, index=local).groupby(local.date)
    firsts = days.min()
    lasts = days.max()
    first_minutes = (firsts.dt.hour * 60 + firsts.dt.minute).mode()
    last_minutes = (lasts.dt.hour * 60 + lasts.dt.minute).mode()
    if first_minutes.empty or last_minutes.empty:
        return None
    open_minute = int(first_minutes.iloc[0])
    close_minute = int(last_minutes.iloc[0]) + int(step)
    # A US-style day ends on the half hour; an hour bar starting 15:30 ends at 16:00.
    if str(local.tz) in ("America/New_York", "US/Eastern") and close_minute > _minutes(_US_CLOSE):
        close_minute = _minutes(_US_CLOSE)
    return (str(local.tz), open_minute, close_minute)


# --------------------------------------------------------------------------
# Grouping bars into candles
# --------------------------------------------------------------------------

def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])


def _ohlcv_groups(df: pd.DataFrame, keys) -> pd.DataFrame:
    grouped = df.groupby(keys, sort=True)
    out = pd.DataFrame({
        "open": grouped["open"].first(),
        "high": grouped["high"].max(),
        "low": grouped["low"].min(),
        "close": grouped["close"].last(),
        "volume": grouped["volume"].sum(min_count=1).fillna(0.0),
    })
    return out.dropna(subset=["open", "high", "low", "close"])


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return _empty()
    keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    out = df[keep].apply(pd.to_numeric, errors="coerce")
    if "volume" not in out.columns:
        out["volume"] = 0.0
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def group_utc(df: pd.DataFrame, step: int) -> pd.DataFrame:
    """Crypto: fixed blocks counted from midnight UTC (4h -> 00, 04, 08, 12, 16, 20)."""
    df = _clean(df)
    if df.empty:
        return df
    index = df.index.tz_convert("UTC") if df.index.tz is not None else df.index.tz_localize("UTC")
    df = df.set_axis(index)
    starts = index.floor(f"{int(step)}min")
    return _ohlcv_groups(df, starts)


def group_session(df: pd.DataFrame, step: int, session) -> pd.DataFrame:
    """Shares: blocks counted from each day's session open in the exchange's own time,
    so no candle spans the overnight gap. Bars outside the regular session are dropped."""
    df = _clean(df)
    if df.empty or not session:
        return df
    zone, open_minute, close_minute = session
    index = df.index.tz_convert(zone) if df.index.tz is not None else df.index.tz_localize("UTC").tz_convert(zone)
    df = df.set_axis(index)
    minute_of_day = index.hour * 60 + index.minute
    inside = (minute_of_day >= open_minute) & (minute_of_day < close_minute)
    df = df[inside]
    if df.empty:
        return _empty()
    index = df.index
    minute_of_day = index.hour * 60 + index.minute
    block = (minute_of_day - open_minute) // int(step)
    midnight = index.normalize()
    starts = midnight + pd.to_timedelta(open_minute + block * int(step), unit="m")
    return _ohlcv_groups(df, starts)


def group_daily(df: pd.DataFrame) -> pd.DataFrame:
    """One candle per calendar date, labelled at midnight UTC of that date."""
    df = _clean(df)
    if df.empty:
        return df
    index = df.index
    dates = index.tz_localize(None).normalize() if index.tz is not None else index.normalize()
    return _ohlcv_groups(df.set_axis(dates.tz_localize("UTC")), dates.tz_localize("UTC"))


def group_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """Monday-to-Sunday weeks, labelled with the Monday (TradingView does the same).
    A week with a holiday simply has fewer days in it."""
    df = group_daily(daily)
    if df.empty:
        return df
    monday = df.index - pd.to_timedelta(df.index.weekday, unit="D")
    return _ohlcv_groups(df, monday)


# --------------------------------------------------------------------------
# The candle that is still forming
# --------------------------------------------------------------------------

def candle_end(start: pd.Timestamp, interval: str, kind: str, session=None) -> pd.Timestamp:
    """When a candle that started at `start` is complete."""
    step = _SOURCE[interval][2]
    if interval == "1D":
        if kind == "crypto" or not session:
            return start + pd.Timedelta(days=1)
        zone, _open, close_minute = session
        day = pd.Timestamp(start.date(), tz=zone)
        return (day + pd.Timedelta(minutes=close_minute)).tz_convert("UTC")
    if interval == "1W":
        if kind == "crypto" or not session:
            return start + pd.Timedelta(days=7)
        zone, _open, close_minute = session
        friday = pd.Timestamp((start + pd.Timedelta(days=4)).date(), tz=zone)
        return (friday + pd.Timedelta(minutes=close_minute)).tz_convert("UTC")
    end = start + pd.Timedelta(minutes=step)
    if kind != "crypto" and session:
        zone, _open, close_minute = session
        local = start.tz_convert(zone)
        close = local.normalize() + pd.Timedelta(minutes=close_minute)
        end = min(end.tz_convert(zone), close)
    return end.tz_convert("UTC") if end.tzinfo is not None else end.tz_localize("UTC")


def mark_forming(df: pd.DataFrame, interval: str, kind: str, now=None, session=None) -> pd.DataFrame:
    """Add a `forming` column: True only for a last candle that has not finished yet."""
    out = df.copy()
    out["forming"] = False
    if out.empty:
        return out
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    last = out.index[-1]
    last = last.tz_localize("UTC") if last.tzinfo is None else last
    if now < candle_end(last, interval, kind, session):
        out.iloc[-1, out.columns.get_loc("forming")] = True
    return out


def confirmed(df: pd.DataFrame) -> pd.DataFrame:
    """Only finished candles. Readings shown as 'latest' use these."""
    if df is None or df.empty or "forming" not in df.columns:
        return df
    return df[~df["forming"].astype(bool)]


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def yahoo_symbol(kind: str, asset_id: str) -> str | None:
    if kind == "crypto":
        from data_fetchers import YAHOO_TICKER_BY_ID, YF_BY_COINGECKO_ID, resolve_crypto_id

        coin = resolve_crypto_id(asset_id)
        return YAHOO_TICKER_BY_ID.get(coin) or YF_BY_COINGECKO_ID.get(coin)
    symbol = str(asset_id or "").strip().upper()
    return symbol or None


def _warmup_days(interval: str, kind: str) -> int:
    step = _SOURCE[interval][2]
    if interval == "1W":
        return WARMUP_CANDLES * 7
    if interval == "1D":
        return WARMUP_CANDLES if kind == "crypto" else math.ceil(WARMUP_CANDLES * 7 / 5)
    per_day = (24 * 60 / step) if kind == "crypto" else max(1.0, 390 / step)
    days = WARMUP_CANDLES / per_day
    return math.ceil(days if kind == "crypto" else days * 7 / 5) + 1


def fetch_window(interval: str, range_key: str, kind: str, today=None) -> tuple[str | None, str | None]:
    """(start date, period) for the Yahoo request. One of them is None."""
    yahoo_interval, keep_days, _step = _SOURCE[interval]
    days = RANGE_DAYS[range_key]
    if days is None:
        return None, "max"
    want = days + _warmup_days(interval, kind)
    # Round up to a few fixed windows so 1h and 4h (both built from hourly bars)
    # and nearby ranges share one cached fetch.
    for window in (59, 120, 240, 400, 729, 1100, 1500, 2200, 4000):
        if want <= window:
            want = window
            break
    if keep_days is not None:
        want = min(want, keep_days)
    today = today or datetime.now(timezone.utc).date()
    return (today - timedelta(days=want)).isoformat(), None


class _Cache:
    """A small shared cache, so several people looking at the same chart cause one fetch.
    Entries expire quickly because the newest candle keeps changing."""

    def __init__(self, size: int = 24):
        self.size = size
        self.items: OrderedDict = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key, ttl: float):
        with self.lock:
            item = self.items.get(key)
            if not item:
                return None
            saved, value = item
            if time.time() - saved > ttl:
                self.items.pop(key, None)
                return None
            self.items.move_to_end(key)
            return value

    def put(self, key, value) -> None:
        with self.lock:
            self.items[key] = (time.time(), value)
            self.items.move_to_end(key)
            while len(self.items) > self.size:
                self.items.popitem(last=False)

    def clear(self) -> None:
        with self.lock:
            self.items.clear()


CACHE = _Cache()
_TTL = {"15m": 60, "60m": 120, "1d": 300}


def _yahoo_fetch(symbol: str, yahoo_interval: str, start: str | None, period: str | None):
    """Raw Yahoo bars plus Yahoo's session details. Regular hours only."""
    from data_fetchers import _ohlcv, _yahoo

    ticker = _yahoo().Ticker(symbol)
    kwargs = {"interval": yahoo_interval, "auto_adjust": False, "prepost": False}
    if start:
        kwargs["start"] = start
    else:
        kwargs["period"] = period or "max"
    raw = ticker.history(**kwargs)
    meta = {}
    try:
        meta = dict(ticker.history_metadata or {})
    except Exception:
        meta = {}
    if raw is None or raw.empty:
        return _empty(), meta
    bars = _ohlcv(raw)
    return bars, meta


def build_candles(raw: pd.DataFrame, interval: str, kind: str, meta: dict | None = None):
    """Turn raw Yahoo bars into the candles for `interval`. Returns (candles, session)."""
    step = _SOURCE[interval][2]
    if interval in ("1D", "1W"):
        session = None
        if kind != "crypto":
            zone = (meta or {}).get("exchangeTimezoneName") or (str(raw.index.tz) if raw.index.tz is not None else None)
            session = session_from_metadata(meta) or ((zone, _minutes(_US_OPEN), _minutes(_US_CLOSE)) if zone else None)
        candles = group_daily(raw) if interval == "1D" else group_weekly(raw)
        return candles, session
    if kind == "crypto":
        return group_utc(raw, step), None
    base_step = 15 if interval == "15m" else 60
    session = session_from_metadata(meta) or session_from_bars(_clean(raw), base_step)
    return group_session(raw, step, session), session


def load_candles(kind: str, asset_id: str, interval: str, range_key: str, now=None, fetch=None) -> dict:
    """Everything the chart needs about the candles.

    Returns a dict with:
      candles   DataFrame (open, high, low, close, volume, forming), index = candle start (UTC)
      start     first candle of the chosen range (earlier candles are warm-up history)
      session   (timezone, open minute, close minute) for shares, else None
      source    a plain sentence saying where the candles came from
      error     a plain sentence, or None
    """
    out = {"candles": _empty(), "start": None, "session": None, "source": "", "error": None}
    usable, reason = availability(interval, range_key)
    if not usable:
        out["error"] = reason
        return out
    symbol = yahoo_symbol(kind, asset_id)
    if not symbol:
        out["error"] = "Yahoo Finance has no candles for this coin, so only the shared daily chart is available."
        return out
    yahoo_interval = _SOURCE[interval][0]
    start, period = fetch_window(interval, range_key, kind)
    key = (symbol, yahoo_interval, start, period)
    cached = CACHE.get(key, _TTL.get(yahoo_interval, 120))
    if cached is None:
        try:
            raw, meta = (fetch or _yahoo_fetch)(symbol, yahoo_interval, start, period)
        except Exception as exc:
            out["error"] = f"Could not load {INTERVAL_LABELS[interval]} candles for {symbol} ({exc})."
            return out
        cached = (raw, meta)
        if raw is not None and not raw.empty:
            CACHE.put(key, cached)
    raw, meta = cached
    if raw is None or raw.empty:
        out["error"] = f"Yahoo Finance returned no {INTERVAL_LABELS[interval]} candles for {symbol}."
        return out

    candles, session = build_candles(raw, interval, kind, meta)
    if candles.empty:
        out["error"] = f"No {INTERVAL_LABELS[interval]} candles for {symbol} in this range."
        return out
    candles = mark_forming(candles, interval, kind, now=now, session=session)

    days = RANGE_DAYS[range_key]
    if days is None:
        range_start = candles.index[0]
    else:
        clock = pd.Timestamp(now or datetime.now(timezone.utc))
        clock = clock.tz_localize("UTC") if clock.tzinfo is None else clock.tz_convert("UTC")
        range_start = clock - pd.Timedelta(days=days)
    in_range = candles[candles.index >= range_start]
    if len(in_range) < MIN_CANDLES:
        out["error"] = (
            f"Only {len(in_range)} {INTERVAL_LABELS[interval]} candles in {RANGE_LABELS[range_key]} for {symbol}. "
            "Pick a longer range or a shorter interval."
        )
        return out
    first_shown = in_range.index[0]
    position = candles.index.get_loc(first_shown)
    keep_from = max(0, position - WARMUP_CANDLES)
    candles = candles.iloc[keep_from:]
    if len(candles) > MAX_CANDLES:
        candles = candles.iloc[-MAX_CANDLES:]
        first_shown = max(first_shown, candles.index[0])

    if interval == "4h":
        how = "fixed 4-hour UTC blocks" if kind == "crypto" else "4-hour blocks from the session open"
        source = f"Yahoo Finance 1-hour candles grouped into {how}"
    elif interval == "1W":
        source = "Yahoo Finance daily candles grouped into Monday-to-Sunday weeks"
    else:
        source = f"Yahoo Finance {INTERVAL_LABELS[interval]} candles"
    if kind != "crypto" and interval not in ("1D", "1W"):
        source += ", regular trading hours only"

    out.update({"candles": candles, "start": first_shown, "session": session, "source": source})
    return out


def display_seconds(index: pd.DatetimeIndex, interval: str, kind: str, session=None) -> list[int]:
    """Times for the chart axis. Crypto shows UTC; shares show the exchange's own
    clock (as TradingView does), so 09:30 New York reads 09:30. Daily and weekly
    candles are dates, shown at midnight."""
    if interval in ("1D", "1W") or kind == "crypto" or not session:
        utc = index.tz_convert("UTC") if index.tz is not None else index
        return [int(ts.timestamp()) for ts in utc]
    zone = session[0]
    local = index.tz_convert(zone).tz_localize(None)
    return [int(ts.replace(tzinfo=timezone.utc).timestamp()) for ts in local]
