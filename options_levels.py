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


def load_rows(ticker: str, today: date) -> tuple[list[dict], list[str], str | None]:
    """Contract lines for the nearest expiries, the expiries used, and an error message."""
    ticker = str(ticker or "").strip().upper()

    def dates():
        try:
            import yfinance as yf
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
    for expiry in chosen:
        def chain(expiry=expiry):
            try:
                import yfinance as yf
                found = yf.Ticker(ticker).option_chain(expiry)
            except Exception:
                return [], "The options chain could not be loaded."
            out = []
            for kind, frame in (("call", getattr(found, "calls", None)), ("put", getattr(found, "puts", None))):
                if frame is None or getattr(frame, "empty", True):
                    continue
                for strike, oi, iv, volume in zip(
                    frame.get("strike", []), frame.get("openInterest", []),
                    frame.get("impliedVolatility", []), frame.get("volume", []),
                ):
                    if _num(strike) > 0 and _num(oi) > 0:
                        out.append({
                            "type": kind, "strike": round(_num(strike), 4), "oi": _num(oi),
                            "iv": _num(iv), "volume": _num(volume),
                        })
            return out, None

        lines, chain_error = _cached(("chain", ticker, expiry), chain)
        if chain_error:
            continue
        when = date.fromisoformat(expiry)
        rows += [dict(line, expiry=when) for line in lines]
    if not rows:
        return [], chosen, "These expiries show no open interest yet."
    return rows, chosen, None
