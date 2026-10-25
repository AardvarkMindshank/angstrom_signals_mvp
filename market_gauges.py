"""Public readings for the whole-market sentiment sections.

Google headlines stay the extra sources. These groups are the feeds that can
be read without a paid terminal. A named source that needs a key or has no
stable free feed is left as a short note, never a made-up number.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

_TTL_SECONDS = 12 * 60 * 60
_RETRY_SECONDS = 120
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SignalsDashboard/1.0)"}
_CACHE: dict[str, tuple[float, float, list[dict]]] = {}

_MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def market_gauge_groups(market_key: str) -> list[dict]:
    """Three reading groups for crypto or stock. Cached for 12 hours when any value lands."""
    if market_key not in ("crypto", "stock"):
        return []
    cached = _CACHE.get(market_key)
    now = time.time()
    if cached and now - cached[0] < cached[1]:
        return cached[2]
    raw = _load_raw(market_key)
    groups = _crypto_groups(raw) if market_key == "crypto" else _stock_groups(raw)
    ttl = _TTL_SECONDS if any(group.get("items") for group in groups) else _RETRY_SECONDS
    _CACHE[market_key] = (now, ttl, groups)
    return groups


def gauge_brief(groups: list[dict]) -> str:
    """Plain lines for the market prompt. Notes about missing feeds stay off this list."""
    lines = []
    for group in groups or []:
        items = group.get("items") or []
        if not items:
            continue
        lines.append(str(group.get("title") or "Readings") + ":")
        for item in items:
            detail = str(item.get("detail") or "").strip()
            source = str(item.get("source") or "").strip()
            tail = ". ".join(part for part in (detail, source) if part)
            lines.append(f"- {item.get('name')}: {item.get('value')}" + (f". {tail}" if tail else ""))
    return "\n".join(lines)


def _load_raw(market_key: str) -> dict:
    jobs = {
        "crypto": ("M2SL", "WALCL", "DFF", "DGS10", "DXY", "FNG", "CG"),
        "stock": ("DFF", "T10YIE", "UMCSENT", "MICH", "VIXCLS", "CNN", "AV", "POLY"),
    }[market_key]
    raw: dict = {}
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {name: pool.submit(_fetch_one, name) for name in jobs}
        for name, future in futures.items():
            try:
                raw[name] = future.result()
            except Exception:
                raw[name] = None
    return raw


def _fetch_one(name: str):
    if name == "DXY":
        return _yahoo_last("DX-Y.NYB")
    if name == "FNG":
        return _fear_greed()
    if name == "CG":
        return _coingecko()
    if name == "CNN":
        return _cnn()
    if name == "AV":
        return _alpha_sectors()
    if name == "POLY":
        return _polygon_breadth()
    return _fred_tail(name)


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(_HEADERS)
    return session


def _secret_key(env_name: str, section: str) -> str:
    """A vendor key from the worker environment, or from the Streamlit secrets."""
    key = (os.getenv(env_name) or "").strip().strip('"').strip("'")
    if key:
        return key
    try:
        import streamlit as st
        key = str(st.secrets[section]["api_key"]).strip()
    except Exception:
        return ""
    if key:
        os.environ[env_name] = key
    return key


def _fred_api_key() -> str:
    return _secret_key("FRED_API_KEY", "fred")


def _fred_tail(series_id: str):
    key = _fred_api_key()
    if key:
        fetched = _fred_api_tail(series_id, key)
        if fetched:
            return fetched
    return _fred_csv_tail(series_id)


def _fred_api_tail(series_id: str, key: str):
    """The last two published observations. The key stays out of any error text."""
    response = _session().get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 8,
        },
        timeout=15,
    )
    if response.status_code != 200:
        return None
    try:
        observations = response.json().get("observations") or []
    except ValueError:
        return None
    rows = []
    for item in observations:
        if not isinstance(item, dict):
            continue
        date = str(item.get("date") or "").strip()
        raw = str(item.get("value") or "").strip()
        if not date or raw in {"", "."}:
            continue
        try:
            rows.append((date, float(raw)))
        except ValueError:
            continue
        if len(rows) >= 2:
            break
    if not rows:
        return None
    previous = rows[1] if len(rows) > 1 else None
    return rows[0], previous


def _fred_csv_tail(series_id: str):
    response = _session().get(
        "https://fred.stlouisfed.org/graph/fredgraph.csv",
        params={"id": series_id},
        timeout=15,
    )
    response.raise_for_status()
    rows = []
    for line in response.text.splitlines()[1:]:
        date, _, raw = line.partition(",")
        raw = raw.strip()
        if not date or raw in {"", "."}:
            continue
        try:
            rows.append((date.strip(), float(raw)))
        except ValueError:
            continue
    if not rows:
        return None
    previous = rows[-2] if len(rows) > 1 else None
    return rows[-1], previous


def _yahoo_last(symbol: str):
    response = _session().get(
        "https://query1.finance.yahoo.com/v8/finance/chart/" + quote(symbol),
        params={"range": "10d", "interval": "1d"},
        timeout=15,
    )
    response.raise_for_status()
    result = (response.json().get("chart") or {}).get("result") or []
    if not result:
        return None
    meta = result[0].get("meta") or {}
    price = meta.get("regularMarketPrice")
    if price is None:
        return None
    previous = meta.get("previousClose")
    if previous is None:
        previous = meta.get("chartPreviousClose")
    stamp = meta.get("regularMarketTime")
    try:
        date = datetime.fromtimestamp(int(stamp), timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        date = ""
    prior = (None, float(previous)) if previous is not None else None
    return (date, float(price)), prior


def _fear_greed():
    response = _session().get("https://api.alternative.me/fng/", params={"limit": 2}, timeout=15)
    response.raise_for_status()
    rows = (response.json().get("data") or [])[:2]
    if not rows:
        return None
    return rows


def _coingecko():
    response = _session().get("https://api.coingecko.com/api/v3/global", timeout=15)
    response.raise_for_status()
    data = response.json().get("data") or {}
    dominance = (data.get("market_cap_percentage") or {}).get("btc")
    change = data.get("market_cap_change_percentage_24h_usd")
    if dominance is None and change is None:
        return None
    return {"btc": dominance, "change": change}


def _cnn():
    response = _session().get(
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        timeout=15,
    )
    response.raise_for_status()
    block = response.json().get("fear_and_greed") or {}
    if block.get("score") is None:
        return None
    return block


_DENIED = object()


def _alpha_sectors():
    """Best and worst US sector over the last day. One Alpha Vantage call."""
    key = _secret_key("ALPHAVANTAGE_API_KEY", "alphavantage")
    if not key:
        return None
    try:
        response = _session().get(
            "https://www.alphavantage.co/query",
            params={"function": "SECTOR", "apikey": key},
            timeout=20,
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        print(f"Alpha Vantage sectors skipped: HTTP {response.status_code}.")
        return None
    try:
        body = response.json()
    except ValueError:
        print("Alpha Vantage sectors skipped: the response was not JSON.")
        return None
    sides = _sector_sides(body)
    if sides:
        return sides
    names = ",".join(str(name) for name in list(body)[:8]) if isinstance(body, dict) else "not-json"
    print(f"Alpha Vantage sectors skipped: {names}.")
    return None


def _sector_sides(body: dict):
    if not isinstance(body, dict):
        return None
    block = body.get("Rank B: 1 Day Performance")
    if not isinstance(block, dict):
        block = None
        for name, value in body.items():
            if "1 day" in str(name).lower() and isinstance(value, dict):
                block = value
                break
    if not block:
        return None
    parsed = []
    for name, raw in block.items():
        text = str(raw).strip().replace("%", "").replace("+", "")
        try:
            parsed.append((str(name).strip(), float(text)))
        except ValueError:
            continue
    if not parsed:
        return None
    parsed.sort(key=lambda row: row[1])
    refreshed = str((body.get("Meta Data") or {}).get("Last Refreshed") or "")
    date = refreshed[:10] if len(refreshed) >= 10 and refreshed[4] == "-" else ""
    return {"lead": (*parsed[-1], date), "lag": (*parsed[0], date)}


def _alpha_sector_items(payload) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    rows = []
    for label, side in (("Leading sector", payload.get("lead")), ("Lagging sector", payload.get("lag"))):
        if not side or len(side) < 3:
            continue
        name, change, date = side[0], side[1], side[2]
        detail = "1-day performance"
        stamp = _stamp(str(date))
        if stamp:
            detail = f"{detail} · {stamp}"
        rows.append(_reading(
            label,
            f"{name} {change:+.2f}%",
            detail,
            "Alpha Vantage",
            "https://www.alphavantage.co/",
            "",
            str(date)[:10],
        ))
    if len(rows) == 2 and rows[0]["value"] == rows[1]["value"]:
        return rows[:1]
    return rows


def _polygon_breadth():
    """How many US stocks rose or fell in the last session. One Polygon call when the day is known."""
    key = _secret_key("POLYGON_API_KEY", "polygon")
    if not key:
        return None
    today = datetime.now(timezone.utc).date()
    for ago in range(8):
        day = today - timedelta(days=ago)
        if day.weekday() >= 5:
            continue
        body = _polygon_json(
            f"/v2/aggs/grouped/locale/us/market/stocks/{day.isoformat()}",
            key,
            {"adjusted": "true"},
        )
        if body is _DENIED:
            break
        counted = _breadth_from_grouped(body, day.isoformat())
        if counted:
            return counted
    body = _polygon_json("/v2/aggs/ticker/SPY/prev", key, {"adjusted": "true"})
    if body is _DENIED:
        return None
    return _spy_from_prev(body)


def _polygon_json(path: str, key: str, params: dict):
    """JSON from Polygon. The key stays out of any error text."""
    query = dict(params)
    query["apiKey"] = key
    try:
        response = _session().get("https://api.polygon.io" + path, params=query, timeout=25)
    except requests.RequestException:
        return None
    if response.status_code in {401, 403, 429}:
        return _DENIED
    if response.status_code != 200:
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    status = str(body.get("status") or "").upper()
    if status in {"ERROR", "NOT_AUTHORIZED"}:
        return _DENIED
    return body


def _breadth_from_grouped(body, day: str):
    if not isinstance(body, dict):
        return None
    up = down = 0
    for row in body.get("results") or []:
        if not isinstance(row, dict):
            continue
        try:
            opened = float(row.get("o"))
            closed = float(row.get("c"))
        except (TypeError, ValueError):
            continue
        if closed > opened:
            up += 1
        elif closed < opened:
            down += 1
    total = up + down
    if total < 100:
        return None
    return {"kind": "breadth", "up": up, "down": down, "total": total, "date": day}


def _spy_from_prev(body):
    if not isinstance(body, dict):
        return None
    results = body.get("results") or []
    if not results or not isinstance(results[0], dict):
        return None
    row = results[0]
    try:
        opened = float(row.get("o"))
        closed = float(row.get("c"))
    except (TypeError, ValueError):
        return None
    date = ""
    try:
        date = datetime.fromtimestamp(int(row.get("t")) / 1000, timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        date = ""
    return {"kind": "spy", "open": opened, "close": closed, "date": date}


def _polygon_items(payload) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    date = str(payload.get("date") or "")
    stamp = _stamp(date)
    if payload.get("kind") == "breadth":
        total = int(payload.get("total") or 0)
        if total <= 0:
            return []
        rows = []
        for name, count in (("US stocks higher", payload.get("up")), ("US stocks lower", payload.get("down"))):
            try:
                count = int(count)
            except (TypeError, ValueError):
                continue
            share = f"{count / total * 100:.0f}% of the last session"
            detail = f"{share} · {stamp}" if stamp else share
            rows.append(_reading(
                name,
                f"{count:,}",
                detail,
                "Polygon",
                "https://massive.com/stocks",
                "",
                date[:10],
            ))
        return rows
    if payload.get("kind") != "spy":
        return []
    try:
        opened = float(payload.get("open"))
        closed = float(payload.get("close"))
    except (TypeError, ValueError):
        return []
    detail = _move_phrase(closed, opened, "open", "percent")
    if stamp:
        detail = f"{detail} · {stamp}" if detail else stamp
    return [_reading(
        "S&P 500 (SPY)",
        f"{closed:,.2f}",
        detail,
        "Polygon",
        "https://massive.com/stocks",
        "",
        date[:10],
    )]


def _crypto_groups(raw: dict) -> list[dict]:
    return [
        {
            "title": "Global liquidity & central bank trackers",
            "items": _present(
                _money_item(
                    "US M2 money supply",
                    raw.get("M2SL"),
                    "month",
                    lambda value: f"${value / 1000:.1f}T",
                    "https://fred.stlouisfed.org/series/M2SL",
                ),
                _money_item(
                    "Fed balance sheet",
                    raw.get("WALCL"),
                    "week",
                    lambda value: f"${value / 1_000_000:.2f}T",
                    "https://fred.stlouisfed.org/series/WALCL",
                ),
                _rate_item(
                    "Federal funds rate",
                    raw.get("DFF"),
                    "day",
                    "https://fred.stlouisfed.org/series/DFF",
                ),
            ),
            "note": (
                "A current four-bank global M2 composite (Fed, ECB, Bank of Japan, and PBOC) "
                "is not a free series, so this group uses the Fed's own published figures."
            ),
        },
        {
            "title": "Currency & yield indicators",
            "items": _present(
                _level_item(
                    "US Dollar Index (DXY)",
                    raw.get("DXY"),
                    "session",
                    lambda value: f"{value:.2f}",
                    "ICE",
                    "https://finance.yahoo.com/quote/DX-Y.NYB/",
                ),
                _rate_item(
                    "10-year Treasury yield",
                    raw.get("DGS10"),
                    "day",
                    "https://fred.stlouisfed.org/series/DGS10",
                ),
            ),
            "note": "",
        },
        {
            "title": "Crypto-specific sentiment & flows",
            "items": _present(_fear_item(raw.get("FNG")), *_coin_items(raw.get("CG"))),
            "note": (
                "Funding rates, open interest, liquidations, and ETF flows need Coinglass or Arkham, "
                "which are not connected."
            ),
        },
    ]


def _stock_groups(raw: dict) -> list[dict]:
    return [
        {
            "title": "Macroeconomic policy & inflation trackers",
            "items": _present(
                _rate_item(
                    "Federal funds rate",
                    raw.get("DFF"),
                    "day",
                    "https://fred.stlouisfed.org/series/DFF",
                ),
                _rate_item(
                    "10-year breakeven inflation",
                    raw.get("T10YIE"),
                    "day",
                    "https://fred.stlouisfed.org/series/T10YIE",
                ),
                _points_item(
                    "Michigan consumer sentiment",
                    raw.get("UMCSENT"),
                    "month",
                    lambda value: f"{value:.1f}",
                    "https://fred.stlouisfed.org/series/UMCSENT",
                    "Michigan",
                ),
                _rate_item(
                    "Michigan inflation expectation",
                    raw.get("MICH"),
                    "month",
                    "https://fred.stlouisfed.org/series/MICH",
                    "Michigan",
                ),
            ),
            "note": (
                "CME FedWatch probabilities and the Conference Board survey are not on a free feed here. "
                "The Michigan survey is the consumer reading that is."
            ),
        },
        {
            "title": "Market-wide sentiment & breadth indicators",
            "items": _present(
                _cnn_item(raw.get("CNN")),
                _points_item(
                    "CBOE VIX",
                    raw.get("VIXCLS"),
                    "day",
                    lambda value: f"{value:.2f}",
                    "https://fred.stlouisfed.org/series/VIXCLS",
                    "CBOE",
                ),
            ),
            "note": "",
        },
        {
            "title": "Institutional & professional data providers",
            "items": _present(*_alpha_sector_items(raw.get("AV")), *_polygon_items(raw.get("POLY"))),
            "note": "Bloomberg Terminal and Refinitiv are not connected.",
        },
    ]


def _present(*items) -> list[dict]:
    return [item for item in items if item]


def _money_item(name, pair, period, formatter, href):
    return _move_item(name, pair, period, formatter, "percent", "FRED", href, "")


def _percent(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".") + "%"


def _rate_item(name, pair, period, href, source="FRED"):
    return _move_item(name, pair, period, _percent, "points", source, href, "")


def _points_item(name, pair, period, formatter, href, source="FRED"):
    return _move_item(name, pair, period, formatter, "points", source, href, "")


def _level_item(name, pair, period, formatter, source, href):
    return _move_item(name, pair, period, formatter, "percent", source, href, "")


def _move_item(name, pair, period, formatter, kind, source, href, tone):
    if not pair:
        return None
    latest, previous = pair
    date, value = latest
    prior_value = previous[1] if previous else None
    detail = _move_phrase(value, prior_value, period, kind)
    stamp = _stamp(date)
    if stamp:
        detail = f"{detail} · {stamp}" if detail else stamp
    return _reading(name, formatter(value), detail, source, href, tone, date[:10] if date else "")


def _fear_item(rows):
    if not rows:
        return None
    latest = rows[0]
    try:
        value = float(latest.get("value"))
    except (TypeError, ValueError):
        return None
    label = str(latest.get("value_classification") or "").strip()
    previous = None
    if len(rows) > 1:
        try:
            previous = float(rows[1].get("value"))
        except (TypeError, ValueError):
            previous = None
    detail = _move_phrase(value, previous, "day", "points")
    iso = ""
    try:
        iso = datetime.fromtimestamp(int(latest.get("timestamp")), timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        iso = ""
    stamp = _stamp(iso) if iso else ""
    if stamp:
        detail = f"{detail} · {stamp}" if detail else stamp
    shown = f"{value:.0f}" + (f" · {label}" if label else "")
    return _reading(
        "Crypto Fear & Greed",
        shown,
        detail,
        "Alternative.me",
        "https://alternative.me/crypto/fear-and-greed-index/",
        _tone(label),
        iso,
    )


def _coin_items(payload):
    if not payload:
        return []
    items = []
    dominance = payload.get("btc")
    if dominance is not None:
        try:
            items.append(_reading(
                "Bitcoin dominance",
                f"{float(dominance):.1f}%",
                "Share of the total crypto market cap",
                "CoinGecko",
                "https://www.coingecko.com/en/global-charts",
                "",
            ))
        except (TypeError, ValueError):
            pass
    change = payload.get("change")
    if change is not None:
        try:
            moved = float(change)
        except (TypeError, ValueError):
            moved = None
        if moved is not None:
            items.append(_reading(
                "Crypto market cap, 24h",
                f"{moved:+.1f}%",
                "Change in total crypto market cap over the last 24 hours",
                "CoinGecko",
                "https://www.coingecko.com/en/global-charts",
                "",
            ))
    return items


def _cnn_item(block):
    if not block:
        return None
    try:
        score = float(block.get("score"))
    except (TypeError, ValueError):
        return None
    rating = str(block.get("rating") or "").strip()
    previous = block.get("previous_close")
    try:
        previous = float(previous) if previous is not None else None
    except (TypeError, ValueError):
        previous = None
    detail = _move_phrase(score, previous, "close", "points")
    shown = f"{score:.0f}" + (f" · {rating.title()}" if rating else "")
    iso = str(block.get("timestamp") or "")[:10]
    if len(iso) < 10 or iso[4] != "-" or iso[7] != "-":
        iso = ""
    return _reading(
        "CNN Fear & Greed",
        shown,
        detail,
        "CNN",
        "https://edition.cnn.com/markets/fear-and-greed",
        _tone(rating),
        iso,
    )


def _reading(name, value, detail, source, href, tone, published: str = "") -> dict:
    return {
        "name": name,
        "value": value,
        "detail": detail,
        "source": source,
        "href": href,
        "tone": tone,
        "published": published,
    }


def _move_phrase(latest: float, previous: float | None, period: str, kind: str) -> str:
    if previous is None:
        return ""
    delta = latest - previous
    if kind == "percent":
        if previous == 0:
            return ""
        pct = abs(delta / previous) * 100
        if pct < 0.005:
            return f"Unchanged from the prior {period}"
        word = "Up" if delta > 0 else "Down"
        shown = f"{pct:.2f}".rstrip("0").rstrip(".") if pct < 1 else f"{pct:.1f}"
        return f"{word} {shown}% from the prior {period}"
    if abs(delta) >= 1 and abs(delta - round(delta)) < 0.05:
        places = 0
    elif abs(delta) >= 1:
        places = 1
    else:
        places = 2
    if abs(delta) < 0.005:
        return f"Unchanged from the prior {period}"
    word = "Up" if delta > 0 else "Down"
    return f"{word} {abs(delta):.{places}f} points from the prior {period}"


def _stamp(iso_date: str) -> str:
    try:
        parsed = datetime.strptime(iso_date[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return f"{parsed.day} {_MONTHS[parsed.month - 1]} {parsed.year}"


def _tone(label: str) -> str:
    text = label.lower()
    if "greed" in text:
        return "greed"
    if "fear" in text:
        return "fear"
    if text:
        return "neutral"
    return ""
