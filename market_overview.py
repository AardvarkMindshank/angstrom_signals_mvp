"""Market overview: major indices, risk gauges and crypto totals for the top of Quick Snapshot.

One fetch is shared by every account. The background worker refreshes it about every 15 minutes
and saves it (table market_overview); the page reads the saved copy, and fetches it itself only
when the saved copy is missing or old.

Sources: Yahoo Finance (indices, VIX, yields, dollar, gold, oil, Bitcoin, Ether), CoinGecko
(total crypto market cap and Bitcoin's share), Alternative.me (crypto Fear & Greed).
"""

from __future__ import annotations

import html
import math
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


REFRESH_SECONDS = 15 * 60
STALE_SECONDS = 60 * 60
SPARK_POINTS = 30

# key, label, Yahoo symbol, group, unit, exchange (for the open/closed dot), invert colours
SPECS = (
    ("spx", "S&P 500", "^GSPC", "stocks", "index", "nyse", False),
    ("ndx", "Nasdaq", "^IXIC", "stocks", "index", "nyse", False),
    ("dji", "Dow Jones", "^DJI", "stocks", "index", "nyse", False),
    ("ftse", "FTSE 100", "^FTSE", "stocks", "index", "lse", False),
    ("dax", "DAX", "^GDAXI", "stocks", "index", "xetra", False),
    ("n225", "Nikkei 225", "^N225", "stocks", "index", "tse", False),
    ("hsi", "Hang Seng", "^HSI", "stocks", "index", "hkex", False),
    ("vix", "VIX", "^VIX", "macro", "index", "", True),
    ("us10y", "US 10-year", "^TNX", "macro", "yield", "", False),
    ("dxy", "US dollar", "DX-Y.NYB", "macro", "index", "", False),
    ("gold", "Gold", "GC=F", "macro", "usd", "", False),
    ("oil", "Oil (WTI)", "CL=F", "macro", "usd", "", False),
    ("btc", "Bitcoin", "BTC-USD", "crypto", "usd", "", False),
    ("eth", "Ether", "ETH-USD", "crypto", "usd", "", False),
)

HINTS = {
    "spx": "The 500 largest US companies. The usual yardstick for the US stock market.",
    "ndx": "Nasdaq Composite: US stocks with a heavy tilt to technology.",
    "dji": "Dow Jones Industrial Average: 30 large US companies.",
    "ftse": "The 100 largest companies on the London Stock Exchange.",
    "dax": "The 40 largest German companies.",
    "n225": "Japan's main stock index.",
    "hsi": "Hong Kong's main stock index.",
    "vix": "The 'fear index': how big a move options traders expect in the S&P 500 over the next month. "
           "Rising means more fear; under about 15 is calm, over about 25 is stressed.",
    "us10y": "The US 10-year government bond yield, in percent. Rising yields tend to weigh on stocks "
             "and crypto. The change is in percentage points.",
    "dxy": "The US dollar against six major currencies. A stronger dollar often weighs on crypto and commodities.",
    "gold": "Gold, US dollars per ounce (front-month future). Often bought as a safe haven.",
    "oil": "US crude oil (WTI), US dollars per barrel (front-month future).",
    "btc": "Bitcoin in US dollars.",
    "eth": "Ether in US dollars.",
    "crypto_cap": "The value of all cryptocurrencies together, with the change over 24 hours.",
    "btc_dom": "Bitcoin's share of the whole crypto market. Rising often means money moving to safety within crypto.",
    "fng": "Crypto Fear & Greed, 0 to 100: below 25 extreme fear, above 75 extreme greed.",
}

# Trading hours, local time. Weekends are closed; public holidays are not tracked.
EXCHANGES = {
    "nyse": ("America/New_York", ((9, 30), (16, 0)), None, "New York"),
    "lse": ("Europe/London", ((8, 0), (16, 30)), None, "London"),
    "xetra": ("Europe/Berlin", ((9, 0), (17, 30)), None, "Frankfurt"),
    "tse": ("Asia/Tokyo", ((9, 0), (15, 30)), ((11, 30), (12, 30)), "Tokyo"),
    "hkex": ("Asia/Hong_Kong", ((9, 30), (16, 0)), ((12, 0), (13, 0)), "Hong Kong"),
}


def market_open(exchange: str, now: datetime | None = None) -> bool | None:
    """True while the exchange is in its trading hours on a weekday. None for an unknown exchange."""
    spec = EXCHANGES.get(exchange)
    if not spec:
        return None
    zone, (start, end), lunch, _name = spec
    local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(zone))
    if local.weekday() >= 5:
        return False
    minutes = local.hour * 60 + local.minute
    if not (start[0] * 60 + start[1] <= minutes < end[0] * 60 + end[1]):
        return False
    if lunch and lunch[0][0] * 60 + lunch[0][1] <= minutes < lunch[1][0] * 60 + lunch[1][1]:
        return False
    return True


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def series_item(closes, unit: str) -> dict | None:
    """Value, day change and sparkline points from a list of daily closes (oldest first)."""
    values = [v for v in (_finite(c) for c in closes or []) if v is not None]
    if not values:
        return None
    last = values[-1]
    before = values[-2] if len(values) >= 2 else None
    change = None
    if before:
        change = (last - before) if unit == "yield" else (last / before - 1) * 100
    return {"value": last, "change": change, "spark": [round(v, 6) for v in values[-SPARK_POINTS:]]}


def _yahoo_closes() -> dict[str, list[float]]:
    """Daily closes for each symbol, one at a time (the same way the rest of the app reads Yahoo).
    A symbol that fails is skipped."""
    import yfinance as yf

    out = {}
    for _key, _label, symbol, *_rest in SPECS:
        try:
            frame = yf.Ticker(symbol).history(period="3mo", interval="1d", auto_adjust=False)
            closes = frame["Close"].dropna().tolist() if frame is not None and not frame.empty else []
        except Exception as exc:
            print(f"Market overview: {symbol} failed: {str(exc)[:100]}")
            continue
        if closes:
            out[symbol] = closes
    return out


def _get(url: str, **params):
    from market_gauges import _session
    response = _session().get(url, params=params or None, timeout=15)
    response.raise_for_status()
    return response.json()


def _crypto_global() -> dict:
    data = _get("https://api.coingecko.com/api/v3/global").get("data") or {}
    return {
        "cap": _finite((data.get("total_market_cap") or {}).get("usd")),
        "cap_change": _finite(data.get("market_cap_change_percentage_24h_usd")),
        "btc_dom": _finite((data.get("market_cap_percentage") or {}).get("btc")),
    }


def _fear_greed() -> list[float]:
    rows = _get("https://api.alternative.me/fng/", limit=SPARK_POINTS).get("data") or []
    values = [_finite(row.get("value")) for row in rows]
    return [v for v in reversed(values) if v is not None]   # oldest first


def fetch_overview() -> dict:
    """Every reading that could be fetched. A source that fails is left out; the rest still show."""
    items = {}
    try:
        closes = _yahoo_closes()
    except Exception as exc:
        print(f"Market overview: Yahoo failed: {str(exc)[:160]}")
        closes = {}
    for key, _label, symbol, _group, unit, _exchange, _invert in SPECS:
        item = series_item(closes.get(symbol), unit)
        if item:
            items[key] = item
    try:
        crypto = _crypto_global()
        if crypto.get("cap"):
            items["crypto_cap"] = {"value": crypto["cap"], "change": crypto.get("cap_change"), "spark": []}
        if crypto.get("btc_dom"):
            items["btc_dom"] = {"value": crypto["btc_dom"], "change": None, "spark": []}
    except Exception as exc:
        print(f"Market overview: CoinGecko failed: {str(exc)[:160]}")
    try:
        fng = _fear_greed()
        if fng:
            items["fng"] = {"value": fng[-1], "change": (fng[-1] - fng[-2]) if len(fng) > 1 else None, "spark": fng}
    except Exception as exc:
        print(f"Market overview: Fear & Greed failed: {str(exc)[:160]}")
    return {"items": items, "fetched_at": time.time()}


# ---------------------------------------------------------------- saving and reading

def save_overview(supabase, overview: dict) -> bool:
    if not overview.get("items"):
        return False
    try:
        supabase.table("market_overview").upsert({
            "id": "latest",
            "data": overview,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="id").execute()
        return True
    except Exception as exc:
        print(f"Market overview not saved. Run the latest supabase_rls.sql. {str(exc)[:160]}")
        return False


def load_overview(supabase) -> dict | None:
    try:
        rows = supabase.table("market_overview").select("data").eq("id", "latest").limit(1).execute().data or []
    except Exception:
        return None
    data = (rows[0] or {}).get("data") if rows else None
    return data if isinstance(data, dict) and data.get("items") else None


def refresh_due(supabase) -> None:
    """Worker step: fetch and save when the saved copy is older than REFRESH_SECONDS."""
    saved = load_overview(supabase)
    if saved and time.time() - float(saved.get("fetched_at") or 0) < REFRESH_SECONDS:
        return
    overview = fetch_overview()
    if save_overview(supabase, overview):
        print(f"Market overview saved: {len(overview['items'])} readings")


# ---------------------------------------------------------------- display

_GREEN, _GREEN_BG = "#15803d", "#dcfce7"
_RED, _RED_BG = "#b91c1c", "#fee2e2"
_GREY, _GREY_BG = "#6b7280", "#f3f4f6"


def value_text(key: str, unit: str, value: float) -> str:
    if key == "crypto_cap":
        return f"${value / 1e12:.2f}T" if value >= 1e12 else f"${value / 1e9:.0f}B"
    if key == "btc_dom":
        return f"{value:.1f}%"
    if unit == "yield":
        return f"{value:.2f}%"
    if key == "fng":
        return f"{value:.0f}"
    prefix = "$" if unit == "usd" else ""
    if value >= 1000:
        return f"{prefix}{value:,.0f}"
    return f"{prefix}{value:,.2f}"


def change_pill(change, unit: str, invert: bool = False) -> str:
    if change is None:
        return ""
    if unit == "yield":
        text = f"{change:+.2f} pt"
    elif unit == "points":
        text = f"{change:+.0f}"
    else:
        text = f"{change:+.1f}%"
    small = abs(change) < (0.005 if unit == "yield" else 0.05)
    up = change > 0
    if small:
        fg, bg, arrow = _GREY, _GREY_BG, ""
    elif up != invert:
        fg, bg, arrow = _GREEN, _GREEN_BG, "▲ " if up else "▼ "
    else:
        fg, bg, arrow = _RED, _RED_BG, "▲ " if up else "▼ "
    if small:
        arrow = ""
    return (
        f"<span style='display:inline-block;padding:1px 7px;border-radius:999px;background:{bg};color:{fg};"
        f"font-size:0.75rem;font-weight:700;white-space:nowrap;'>{arrow}{html.escape(text.lstrip('+-') if arrow else text)}</span>"
    )


def spark_svg(values, invert: bool = False, width: int = 84, height: int = 24) -> str:
    points = [v for v in (_finite(x) for x in values or []) if v is not None]
    if len(points) < 2:
        return ""
    low, high = min(points), max(points)
    span = (high - low) or 1.0
    last = len(points) - 1
    path = " ".join(
        f"{2 + (width - 4) * i / last:.1f},{2 + (height - 4) * (1 - (v - low) / span):.1f}"
        for i, v in enumerate(points)
    )
    rising = points[-1] >= points[0]
    colour = _GREEN if rising != invert else _RED
    # Stretches to the card's width; the line keeps its shape.
    return (
        f"<svg viewBox='0 0 {width} {height}' preserveAspectRatio='none' aria-hidden='true' "
        f"style='display:block;width:100%;height:{height}px;'>"
        f"<polyline fill='none' stroke='{colour}' stroke-width='1.5' stroke-linejoin='round' "
        f"stroke-linecap='round' vector-effect='non-scaling-stroke' points='{path}'/></svg>"
    )


def _fng_word(value: float) -> str:
    if value < 25:
        return "Extreme fear"
    if value < 45:
        return "Fear"
    if value <= 55:
        return "Neutral"
    if value <= 75:
        return "Greed"
    return "Extreme greed"


def card_list(overview: dict | None, crypto: bool, stocks: bool, now: datetime | None = None) -> list[dict]:
    """The cards to show, in order, for the markets this account trades."""
    items = (overview or {}).get("items") or {}
    cards = []
    groups = []
    if stocks:
        groups += ["stocks", "macro"]
    if crypto:
        groups.append("crypto")
        if not stocks:
            groups.insert(0, "macro_crypto")
    for key, label, _symbol, group, unit, exchange, invert in SPECS:
        wanted = group in groups or (group == "macro" and "macro_crypto" in groups and key in ("vix", "dxy", "us10y"))
        if not wanted or key not in items:
            continue
        cards.append({"key": key, "label": label, "unit": unit, "exchange": exchange, "invert": invert,
                      "group": group, **items[key]})
    if crypto:
        for key, label, unit in (("crypto_cap", "Crypto market cap", "usd"), ("btc_dom", "Bitcoin share", "pct"),
                                 ("fng", "Fear & Greed", "points")):
            if key in items:
                cards.append({"key": key, "label": label, "unit": unit, "exchange": "", "invert": False,
                              "group": "crypto", **items[key]})
    for card in cards:
        card["open"] = market_open(card["exchange"], now) if card["exchange"] else None
    return cards


def overview_html(overview: dict | None, crypto: bool, stocks: bool, now: datetime | None = None) -> str:
    """The strip of cards. Empty when nothing has been fetched yet."""
    cards = card_list(overview, crypto, stocks, now)
    if not cards:
        return ""
    parts = [
        # A grid on wide screens; one row you swipe sideways on a phone.
        "<style>.ang-mkt{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;}"
        "@media (max-width:640px){.ang-mkt{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;"
        "padding-bottom:4px;}.ang-mkt>div{flex:0 0 150px;scroll-snap-align:start;}}</style>",
        "<div class='ang-mkt'>",
    ]
    for card in cards:
        key, unit = card["key"], card["unit"]
        hint = HINTS.get(key, "")
        dot = ""
        if card["open"] is not None:
            place = EXCHANGES[card["exchange"]][3]
            state = "open" if card["open"] else "closed"
            dot = (
                f"<span title='{html.escape(place)} is {state}' style='display:inline-block;width:8px;height:8px;"
                f"border-radius:50%;margin-right:5px;vertical-align:1px;"
                f"background:{'#22c55e' if card['open'] else '#cbd5e1'};'></span>"
            )
            hint = f"{hint} {place} is {state} now (public holidays are not shown)."
        value = value_text(key, unit, card["value"])
        sub = ""
        if key == "fng":
            sub = f"<span style='font-size:0.75rem;color:{_GREY};'>{_fng_word(card['value'])}</span>"
        pill = change_pill(card.get("change"), unit, card["invert"])
        spark = spark_svg(card.get("spark"), card["invert"])
        parts.append(
            f"<div class='ang-card' title='{html.escape(hint, quote=True)}' "
            "style='min-width:0;padding:8px 10px;margin:0;'>"
            f"<div class='ang-kicker' style='white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{dot}{html.escape(card['label'])}</div>"
            "<div style='display:flex;align-items:baseline;gap:6px;flex-wrap:wrap;margin:2px 0;'>"
            f"<span style='font-weight:700;font-size:1.05rem;'>{html.escape(value)}</span>{pill}{sub}</div>"
            f"{spark}</div>"
        )
    parts.append("</div>")
    return "".join(parts)
