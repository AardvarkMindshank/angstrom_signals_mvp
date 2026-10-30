"""Options max pain for the asset open on the chart.

Stocks come from the Yahoo chain already used for prices. Bitcoin and Ethereum
come from Deribit's public options book. Nothing here touches the technical score.
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime, timezone

import requests

from data_fetchers import crypto_ticker

_TTL_SECONDS = 12 * 60 * 60
_ERROR_TTL_SECONDS = 90
_LAST_GOOD_SECONDS = 4 * 24 * 60 * 60   # covers a long weekend
_LAST_GOOD: dict[str, tuple[float, tuple]] = {}
_STALE: dict[str, float] = {}
_DERIBIT = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
_INSTRUMENT = re.compile(r"^(BTC|ETH)-(\d{1,2}[A-Z]{3}\d{2})-(\d+(?:\.\d+)?)-([CP])$")
_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
_MONTH_NAMES = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
# Success values live for 12 hours. Failures are kept briefly so a rerun does not hammer the source.
_cache: dict[str, tuple[float, object]] = {}


def options_market(kind: str, asset_id: str) -> str | None:
    """A cache key for an asset that has a chain here. Empty for other coins."""
    if kind == "Stock":
        ticker = str(asset_id or "").strip().upper()
        return f"stock:{ticker}" if ticker else None
    if kind == "Crypto":
        symbol = crypto_ticker(asset_id)
        if symbol in {"BTC", "ETH"}:
            return f"crypto:{symbol}"
    return None


def list_expiries(market: str, force: bool = False) -> tuple[list[tuple[str, str]], str | None]:
    """Nearest expiry first. Each pair is the value stored on the menu, then its label."""
    dates, error = _expiry_dates(market, force)
    if error:
        return [], error
    today = datetime.now(timezone.utc).date()
    pairs = []
    for expiry in dates:
        parsed = date.fromisoformat(expiry)
        if parsed < today:
            continue
        pairs.append((expiry, _label(parsed)))
    return pairs, None


def load_open_interest(
    market: str, expiry: str, force: bool = False,
) -> tuple[dict[float, float], dict[float, float], float | None, str | None]:
    """Call open interest, put open interest, the underlying price, and an error."""
    if market.startswith("stock:"):
        return _stock_chain(market.split(":", 1)[1], expiry, force)
    book, error = _crypto_book(market, force)
    if error:
        return {}, {}, None, error
    row = (book or {}).get(expiry) or {}
    return row.get("calls") or {}, row.get("puts") or {}, row.get("spot"), None


def pain_strike(calls: dict[float, float], puts: dict[float, float]) -> float | None:
    """The strike where open contracts would be worth the least. Not a price target."""
    strikes = sorted(set(calls) | set(puts))
    if not strikes:
        return None
    best_strike = None
    best_pain = None
    for settle in strikes:
        pain = 0.0
        for strike, amount in calls.items():
            if settle > strike:
                pain += (settle - strike) * amount
        for strike, amount in puts.items():
            if settle < strike:
                pain += (strike - settle) * amount
        if best_pain is None or pain < best_pain:
            best_pain = pain
            best_strike = settle
    return best_strike


def window_strikes(
    strikes: list[float], spot: float | None, level: float | None, limit: int = 40,
) -> list[float]:
    """Strikes to draw. The pain strike itself is always calculated from the full chain."""
    rows = sorted(set(strikes))
    if len(rows) <= limit:
        return rows
    anchors = [value for value in (spot, level) if value is not None]
    center = sum(anchors) / len(anchors) if anchors else rows[len(rows) // 2]
    nearest = sorted(rows, key=lambda strike: (abs(strike - center), strike))
    keep = set(nearest[:limit])
    if level is not None:
        keep.add(min(rows, key=lambda strike: (abs(strike - level), strike)))
    return sorted(keep)


def _expiry_dates(market: str, force: bool) -> tuple[list[str], str | None]:
    key = f"{market}:dates"
    cached = _read(key, force)
    if cached is not None:
        return cached
    if market.startswith("crypto:"):
        book, error = _crypto_book(market, force)
        dates = sorted(book) if book else []
    elif market.startswith("stock:"):
        dates, error = _stock_dates(market.split(":", 1)[1])
    else:
        dates, error = [], "This asset has no options chain here."
    _write(key, dates, error)
    return dates, error


def _crypto_book(market: str, force: bool) -> tuple[dict, str | None]:
    cached = _read(market, force)
    if cached is not None:
        return cached
    book, error = _deribit_book(market.split(":", 1)[1])
    _write(market, book, error)
    return book, error


def _stock_dates(ticker: str) -> tuple[list[str], str | None]:
    try:
        import yfinance as yf
        dates = [str(item)[:10] for item in (yf.Ticker(ticker).options or [])]
    except Exception:
        return [], "The options chain could not be loaded."
    if not dates:
        return [], "No listed expiries for this asset right now."
    return dates, None


def _stock_chain(
    ticker: str, expiry: str, force: bool,
) -> tuple[dict[float, float], dict[float, float], float | None, str | None]:
    key = f"stock:{ticker}:chain:{expiry}"
    cached = _read(key, force)
    if cached is not None:
        (calls, puts), error = cached
        return calls, puts, None, error
    try:
        import yfinance as yf
        chain = yf.Ticker(ticker).option_chain(expiry)
    except Exception:
        calls, puts, error = {}, {}, "The options chain could not be loaded."
        _write(key, (calls, puts), error)
        return calls, puts, None, error
    calls = _oi_frame(getattr(chain, "calls", None))
    puts = _oi_frame(getattr(chain, "puts", None))
    if calls or puts:
        _LAST_GOOD[key] = (time.time(), (calls, puts))
        _STALE.pop(key, None)
        _write(key, (calls, puts), None)
        return calls, puts, None, None
    # Yahoo sometimes blanks open interest for a while. Show the last figures it gave, if recent.
    saved = _LAST_GOOD.get(key)
    if saved and time.time() - saved[0] < _LAST_GOOD_SECONDS:
        _STALE[key] = saved[0]
        calls, puts = saved[1]
    _cache[key] = (time.time() - _TTL_SECONDS + _ERROR_TTL_SECONDS, ((calls, puts), None))
    return calls, puts, None, None


def stale_since(market: str, expiry: str) -> float | None:
    """When the figures now shown were fetched, if they are kept from earlier because Yahoo sent none."""
    if not market.startswith("stock:"):
        return None
    return _STALE.get(f"stock:{market.split(':', 1)[1]}:chain:{expiry}")


def _read(market: str, force: bool):
    if force:
        return None
    hit = _cache.get(market)
    if not hit:
        return None
    stored_at, payload = hit
    age = time.time() - stored_at
    book, error = payload
    limit = _ERROR_TTL_SECONDS if error else _TTL_SECONDS
    if age >= limit:
        return None
    return book, error


def _write(market: str, book: dict, error: str | None) -> None:
    _cache[market] = (time.time(), (book, error))


def _deribit_book(symbol: str) -> tuple[dict, str | None]:
    try:
        response = requests.get(
            _DERIBIT,
            params={"currency": symbol, "kind": "option"},
            timeout=20,
        )
        response.raise_for_status()
        rows = response.json().get("result") or []
    except Exception:
        return {}, "The options chain could not be loaded."
    if not isinstance(rows, list):
        return {}, "The options chain could not be loaded."
    return _rows_to_book(rows, symbol)


def _rows_to_book(rows: list, symbol: str) -> tuple[dict, str | None]:
    book: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        parsed = _INSTRUMENT.match(str(row.get("instrument_name") or ""))
        if not parsed or parsed.group(1) != symbol:
            continue
        amount = _number(row.get("open_interest"))
        if amount <= 0:
            continue
        expiry = _expiry_iso(parsed.group(2))
        if not expiry:
            continue
        slot = book.setdefault(expiry, {"calls": {}, "puts": {}, "spot": None})
        side = "calls" if parsed.group(4) == "C" else "puts"
        strike = round(float(parsed.group(3)), 4)
        slot[side][strike] = slot[side].get(strike, 0.0) + amount
        spot = _number(row.get("underlying_price"))
        if spot > 0:
            slot["spot"] = spot
    if not book:
        return {}, "No listed expiries for this asset right now."
    return book, None


def _oi_frame(frame) -> dict[float, float]:
    if frame is None or getattr(frame, "empty", True):
        return {}
    if "strike" not in frame.columns or "openInterest" not in frame.columns:
        return {}
    out: dict[float, float] = {}
    for strike, amount in zip(frame["strike"], frame["openInterest"]):
        size = _number(amount)
        price = _number(strike)
        if size <= 0 or price <= 0:
            continue
        key = round(price, 4)
        out[key] = out.get(key, 0.0) + size
    return out


def _expiry_iso(token: str) -> str | None:
    match = re.fullmatch(r"(\d{1,2})([A-Z]{3})(\d{2})", token)
    if not match:
        return None
    month = _MONTHS.get(match.group(2))
    if not month:
        return None
    try:
        parsed = date(2000 + int(match.group(3)), month, int(match.group(1)))
    except ValueError:
        return None
    return parsed.isoformat()


def _label(parsed: date) -> str:
    return f"{parsed.day} {_MONTH_NAMES[parsed.month - 1]} {parsed.year}"


def _number(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number != number:  # NaN
        return 0.0
    return number
