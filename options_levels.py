"""Options positioning for a stock: the stock-market cousin of liquidation levels.

Stocks have no published liquidation prices. What plays a similar role is how options
are positioned, because the market makers who sell options hedge by buying and selling
the stock:

- Call wall and put wall: the strikes with the most open call and put contracts. Prices
  often stall near them.
- Gamma exposure (GEX) per strike: how much hedging a 1% move would force there. The
  usual convention counts calls as positive and puts as negative (dealers assumed long
  calls and short puts). Positive overall tends to calm moves; negative tends to speed
  them up.
- Gamma flip: the price where total GEX changes sign.
- Put/call ratio: put open interest (or volume) for each call. Above 1 leans bearish.

Data comes from the Yahoo options chain already used for max pain, from the nearest few
expiries. Gamma is worked out with Black-Scholes from each contract's implied volatility.
Nothing here is part of the score.
"""

from __future__ import annotations

import math
import threading
import time
from datetime import date

RISK_FREE = 0.04
EXPIRIES_USED = 3
MAX_DAYS = 60
WINDOW = 0.15            # strikes within 15% of the price are shown
_TTL = 60 * 60           # a chain is reused for an hour
_ERROR_TTL = 90
_CACHE_LIMIT = 200
_cache: dict[tuple, tuple[float, object]] = {}
# Yahoo refuses bursts of parallel requests, so chains are fetched one at a time.
_YAHOO = threading.Lock()
_LAST_GOOD_SECONDS = 4 * 24 * 60 * 60
_last_good: dict[tuple, tuple[float, list]] = {}


# ---------------------------------------------------------------- maths

def bs_gamma(spot: float, strike: float, iv: float, years: float, rate: float = RISK_FREE) -> float:
    """Black-Scholes gamma (the same for calls and puts). 0 when the inputs cannot give one."""
    if spot <= 0 or strike <= 0 or iv <= 0 or years <= 0:
        return 0.0
    root = iv * math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * years) / root
    return math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi) / (spot * root)


def _gex(row: dict, spot: float, today: date) -> float:
    """Dollar gamma per 1% move for one contract line: calls positive, puts negative."""
    years = max(1, (row["expiry"] - today).days) / 365.0
    gamma = bs_gamma(spot, row["strike"], row["iv"], years)
    size = gamma * row["oi"] * 100 * spot * spot * 0.01
    return size if row["type"] == "call" else -size


def pick_expiries(dates, today: date, count: int = EXPIRIES_USED, max_days: int = MAX_DAYS) -> list[str]:
    """The nearest expiries after today, within max_days. Today's is skipped: on its last day
    an option often shows no open interest."""
    chosen = []
    for raw in sorted(str(d)[:10] for d in dates or []):
        try:
            when = date.fromisoformat(raw)
        except ValueError:
            continue
        if when <= today or (when - today).days > max_days:
            continue
        chosen.append(raw)
        if len(chosen) >= count:
            break
    return chosen


def summarize(rows: list[dict], spot: float, today: date) -> dict:
    """rows: {"type": "call"|"put", "strike", "oi", "iv", "volume", "expiry": date}.

    Returns the walls, the put/call ratios, net GEX, the gamma flip and per-strike detail
    for strikes within WINDOW of the price.
    """
    rows = [r for r in rows or [] if r.get("strike", 0) > 0 and r.get("oi", 0) >= 0]
    if not rows or not spot or spot <= 0:
        return {"ok": False}
    by_strike: dict[float, dict] = {}
    call_oi = put_oi = call_volume = put_volume = 0.0
    for row in rows:
        slot = by_strike.setdefault(row["strike"], {"call_oi": 0.0, "put_oi": 0.0, "gex": 0.0})
        gex = _gex(row, spot, today)
        slot["gex"] += gex
        if row["type"] == "call":
            slot["call_oi"] += row["oi"]
            call_oi += row["oi"]
            call_volume += row.get("volume") or 0.0
        else:
            slot["put_oi"] += row["oi"]
            put_oi += row["oi"]
            put_volume += row.get("volume") or 0.0
    near = {k: v for k, v in by_strike.items() if abs(k / spot - 1) <= WINDOW}
    call_wall = max(near, key=lambda k: near[k]["call_oi"], default=None) if near else None
    put_wall = max(near, key=lambda k: near[k]["put_oi"], default=None) if near else None
    if call_wall is not None and near[call_wall]["call_oi"] <= 0:
        call_wall = None
    if put_wall is not None and near[put_wall]["put_oi"] <= 0:
        put_wall = None
    return {
        "ok": True,
        "spot": spot,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "pcr_oi": put_oi / call_oi if call_oi else None,
        "pcr_volume": put_volume / call_volume if call_volume else None,
        "net_gex": sum(v["gex"] for v in by_strike.values()),
        "flip": gamma_flip(rows, spot, today),
        "strikes": [
            {"strike": k, "call_oi": v["call_oi"], "put_oi": v["put_oi"], "gex": v["gex"]}
            for k, v in sorted(near.items())
        ],
        "contracts": call_oi + put_oi,
    }


def gamma_flip(rows: list[dict], spot: float, today: date, steps: int = 61) -> float | None:
    """The price, within WINDOW of today's, where total GEX would change sign. None if it does not."""
    if spot <= 0:
        return None
    low, high = spot * (1 - WINDOW), spot * (1 + WINDOW)
    prices = [low + (high - low) * i / (steps - 1) for i in range(steps)]
    totals = [sum(_gex(row, price, today) for row in rows) for price in prices]
    best = None
    for i in range(1, steps):
        a, b = totals[i - 1], totals[i]
        if (a < 0 <= b) or (a > 0 >= b):
            cross = prices[i - 1] + (prices[i] - prices[i - 1]) * (abs(a) / (abs(a) + abs(b) or 1))
            if best is None or abs(cross - spot) < abs(best - spot):
                best = cross
    return best


# ---------------------------------------------------------------- data

def _cached(key, loader):
    hit = _cache.get(key)
    if hit:
        stored_at, (value, error) = hit
        if time.time() - stored_at < (_ERROR_TTL if error else _TTL):
            return value, error
    value, error = loader()
    if len(_cache) >= _CACHE_LIMIT:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (time.time(), (value, error))
    return value, error


def _num(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number else 0.0


def chain_lines(found) -> list[dict]:
    """Contract lines with open interest from one yfinance option_chain result."""
    out = []
    for kind, frame in (("call", getattr(found, "calls", None)), ("put", getattr(found, "puts", None))):
        if frame is None or getattr(frame, "empty", True) or "strike" not in frame.columns:
            continue
        size = len(frame)
        column = lambda name: list(frame[name]) if name in frame.columns else [0] * size
        for strike, oi, iv, volume in zip(
            column("strike"), column("openInterest"), column("impliedVolatility"), column("volume"),
        ):
            if _num(strike) > 0 and _num(oi) > 0:
                out.append({
                    "type": kind, "strike": round(_num(strike), 4), "oi": _num(oi),
                    "iv": _num(iv), "volume": _num(volume),
                })
    return out


def last_stale_from() -> float | None:
    """When the figures from the latest load_rows call were fetched, if kept from earlier."""
    return getattr(load_rows, "stale_from", None)


def load_rows(ticker: str, today: date) -> tuple[list[dict], list[str], str | None]:
    """Contract lines for the nearest expiries, the expiries used, and an error message."""
    ticker = str(ticker or "").strip().upper()

    def dates():
        try:
            import yfinance as yf
            with _YAHOO:
                return [str(d)[:10] for d in (yf.Ticker(ticker).options or [])], None
        except Exception:
            return [], "The options chain could not be loaded."

    listed, error = _cached(("dates", ticker), dates)
    if error:
        return [], [], error
    chosen = pick_expiries(listed, today)
    if not chosen:
        return [], [], "No options expiries in the next two months."
    rows: list[dict] = []
    failed = zero = 0
    stale_from = None
    for expiry in chosen:
        def chain(expiry=expiry):
            found = None
            for attempt in range(2):
                try:
                    import yfinance as yf
                    with _YAHOO:
                        found = yf.Ticker(ticker).option_chain(expiry)
                    break
                except Exception:
                    time.sleep(1.5 * (attempt + 1))
            if found is None:
                return [], "failed"
            lines = chain_lines(found)
            # An empty chain is kept only briefly, like an error, so it is asked for again soon.
            return lines, (None if lines else "empty")

        lines, chain_error = _cached(("chain", ticker, expiry), chain)
        if lines:
            _last_good[(ticker, expiry)] = (time.time(), lines)
        if chain_error == "empty":
            saved = _last_good.get((ticker, expiry))
            if saved and time.time() - saved[0] < _LAST_GOOD_SECONDS:
                stale_from = min(stale_from or saved[0], saved[0])
                rows += [dict(line, expiry=date.fromisoformat(expiry)) for line in saved[1]]
            else:
                zero += 1
            continue
        if chain_error:
            failed += 1
            continue
        when = date.fromisoformat(expiry)
        rows += [dict(line, expiry=when) for line in lines]
    if not rows:
        if failed:
            return [], chosen, "Yahoo did not send the options chain just now. Try again in a minute or two."
        return [], chosen, (
            "Yahoo is showing no open contracts for these expiries right now. It does this from time "
            "to time, often outside US trading hours; the figures come back once it refreshes."
        )
    load_rows.stale_from = stale_from
    return rows, chosen, None


# ---------------------------------------------------------------- short interest

_SHORT_TTL = 6 * 60 * 60   # published twice a month, so a few hours is plenty


def short_interest_from_info(info: dict) -> dict:
    """Short interest from a yfinance Ticker.info dict. Empty dict when Yahoo has none."""
    info = info or {}
    shares = _num(info.get("sharesShort"))
    if shares <= 0:
        return {}
    prior = _num(info.get("sharesShortPriorMonth"))
    stamp = _num(info.get("dateShortInterest"))
    as_of = None
    if stamp > 0:
        from datetime import datetime, timezone
        as_of = datetime.fromtimestamp(stamp, tz=timezone.utc).date()
    pct = _num(info.get("shortPercentOfFloat"))
    return {
        "shares": shares,
        "pct_float": pct if pct > 0 else None,
        "days_to_cover": _num(info.get("shortRatio")) or None,
        "change": (shares / prior - 1) if prior > 0 else None,
        "as_of": as_of,
    }


def load_short_interest(ticker: str) -> dict:
    ticker = str(ticker or "").strip().upper()
    key = ("short", ticker)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < (_SHORT_TTL if hit[1][0] else _ERROR_TTL):
        return hit[1][0]
    try:
        import yfinance as yf
        with _YAHOO:
            info = yf.Ticker(ticker).info
        value = short_interest_from_info(info)
    except Exception:
        value = {}
    if len(_cache) >= _CACHE_LIMIT:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (time.time(), (value, None))
    return value
