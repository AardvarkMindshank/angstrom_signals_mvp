"""Trade Log (22 Nov 2026, spec v0.5): a member's closed trades from eToro (Binance later), set against what
MarketNavi read at entry and exit. This file holds the parts with no screen: reading eToro, turning its positions
into round trips, and the stats. The page is tradelog_view.py; the tables are sql/2026-12-08_trade_log.sql.

Rules from the spec:
- Read-only keys. eToro keys are made with Read permission; MarketNavi never places or changes a trade.
- One position until flat, with average entry and exit prices. eToro already reports each closed position whole;
  partial closes (parentPositionId) are merged back into their position.
- eToro takes its costs in the spread, so its "fees" are usually 0: the net result already includes them.
- Copied positions (socialTradeId) are kept and marked, and left out of stats unless the member includes them.
- Any figure resting on fewer than MIN_TRADES trades says so instead of reading as a pattern.
- Nothing here ever logs keys, trades or amounts (the repository and its logs are public).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

ETORO_API = "https://public-api.etoro.com/api/v1"
PAGE_SIZE = 100
MAX_PAGES = 200
MIN_TRADES = 10
ASSET_CLASSES = ("crypto", "stocks", "etfs", "indices", "commodities", "currencies", "other")


# ---- eToro ---------------------------------------------------------------------------------------------------

class EtoroError(Exception):
    """eToro refused or failed. The message never contains a key."""


def _headers(keys: dict) -> dict:
    return {"x-request-id": str(uuid.uuid4()), "x-api-key": keys["api_key"], "x-user-key": keys["user_key"],
            "Accept": "application/json"}


def _get(session, path: str, keys: dict, params: dict | None = None):
    r = session.get(f"{ETORO_API}{path}", headers=_headers(keys), params=params or {}, timeout=30)
    if r.status_code in (401, 403):
        raise EtoroError("eToro refused the key. Check it is a Read key for the real account.")
    if r.status_code == 429:
        raise EtoroError("eToro asked us to slow down. The next sync will carry on.")
    if r.status_code != 200:
        raise EtoroError(f"eToro answered HTTP {r.status_code}.")
    try:
        return r.json()
    except ValueError as exc:
        raise EtoroError("eToro sent something that is not JSON.") from exc


def _items(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for value in body.values():
            if isinstance(value, list):
                return value
    return []


def fetch_closed_positions(session, keys: dict, min_date: str = "2010-01-01") -> list[dict]:
    """Every closed position since min_date (YYYY-MM-DD), all pages."""
    out: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        batch = _items(_get(session, "/trading/info/trade/history", keys,
                            {"minDate": min_date, "page": page, "pageSize": PAGE_SIZE}))
        out += [b for b in batch if isinstance(b, dict)]
        if len(batch) < PAGE_SIZE:
            break
    return out


def fetch_instruments(session, keys: dict, ids) -> dict[int, dict]:
    """Display names, symbols and types for these instrument ids, in chunks."""
    ids = sorted({int(i) for i in ids if i is not None})
    found: dict[int, dict] = {}
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        body = _get(session, "/market-data/instruments", keys, {"instrumentIds": ",".join(map(str, chunk))})
        for item in (body or {}).get("instrumentDisplayDatas") or []:
            if isinstance(item, dict) and item.get("instrumentID") is not None:
                found[int(item["instrumentID"])] = item
    return found


def fetch_instrument_types(session, keys: dict) -> dict[int, str]:
    body = _get(session, "/market-data/instrument-types", keys)
    return {int(t["instrumentTypeID"]): str(t.get("instrumentTypeDescription") or "")
            for t in (body or {}).get("instrumentTypes") or [] if isinstance(t, dict) and "instrumentTypeID" in t}


def asset_class_of(description: str) -> str:
    """eToro's instrument type description → one of ASSET_CLASSES."""
    d = (description or "").lower()
    if "crypto" in d:
        return "crypto"
    if "etf" in d:
        return "etfs"
    if "stock" in d or "equit" in d:
        return "stocks"
    if "commodit" in d:
        return "commodities"
    if "currenc" in d or "forex" in d:
        return "currencies"
    if "ind" in d:
        return "indices"
    return "other"


# ---- round trips ---------------------------------------------------------------------------------------------

def _num(value) -> float | None:
    try:
        return None if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return None


def _when(value) -> datetime | None:
    if not value:
        return None
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _weighted(parts: list[dict], field: str) -> float | None:
    pairs = [(_num(p.get(field)), abs(_num(p.get("units")) or 0)) for p in parts]
    pairs = [(v, w) for v, w in pairs if v is not None]
    total = sum(w for _, w in pairs)
    if not pairs:
        return None
    return sum(v * w for v, w in pairs) / total if total else pairs[0][0]


def etoro_round_trips(positions: list[dict], instruments: dict[int, dict] | None = None,
                      types: dict[int, str] | None = None, asset_keys: dict | None = None) -> list[dict]:
    """eToro's closed positions → round trips (one position until flat). A part closed from a larger position
    (parentPositionId pointing at another position in the list) is merged into it."""
    instruments, types, asset_keys = instruments or {}, types or {}, asset_keys or {}
    by_id = {str(p.get("positionId")): p for p in positions if p.get("positionId") is not None}
    groups: dict[str, list[dict]] = {}
    for p in positions:
        pid = str(p.get("positionId"))
        parent = str(p.get("parentPositionId") or "")
        key = parent if parent and parent != "0" and parent in by_id else pid
        groups.setdefault(key, []).append(p)
    trips = []
    for key, parts in groups.items():
        opened = [t for t in (_when(p.get("openTimestamp")) for p in parts) if t]
        closed = [t for t in (_when(p.get("closeTimestamp")) for p in parts) if t]
        if not opened or not closed:
            continue
        first = min(parts, key=lambda p: _when(p.get("openTimestamp")) or max(opened))
        iid = first.get("instrumentId")
        info = instruments.get(int(iid)) if iid is not None else None
        info = info or {}
        invested = sum(_num(p.get("initialInvestment")) or _num(p.get("investment")) or 0 for p in parts)
        net = sum(_num(p.get("netProfit")) or 0 for p in parts)
        fees = sum(_num(p.get("fees")) or 0 for p in parts)
        symbol = str(info.get("symbolFull") or "")
        cls = asset_class_of(types.get(int(info["instrumentTypeID"]), "")) if info.get("instrumentTypeID") is not None else "other"
        trips.append({
            "platform": "etoro",
            "position_id": key,
            "instrument_id": "" if iid is None else str(iid),
            "symbol": symbol[:40],
            "name": str(info.get("instrumentDisplayName") or symbol or f"Instrument {iid}")[:120],
            "asset_class": cls,
            "asset_key": asset_keys.get((cls, symbol.upper())),
            "direction": "long" if first.get("isBuy", True) else "short",
            "opened_at": min(opened).isoformat(),
            "closed_at": max(closed).isoformat(),
            "entry_price": _weighted(parts, "openRate"),
            "exit_price": _weighted(parts, "closeRate"),
            "units": sum(abs(_num(p.get("units")) or 0) for p in parts),
            "invested_usd": invested or None,
            "leverage": max(_num(p.get("leverage")) or 1 for p in parts),
            "fees_usd": fees,
            "net_result_usd": round(net, 2),
            "result_pct": round(net / invested * 100, 2) if invested else None,
            "copied": any(_num(p.get("socialTradeId")) for p in parts),
            "parts": len(parts),
        })
    trips.sort(key=lambda t: t["closed_at"], reverse=True)
    return trips


# ---- stats ---------------------------------------------------------------------------------------------------

def _hold_days(trip: dict) -> float | None:
    a, b = _when(trip.get("opened_at")), _when(trip.get("closed_at"))
    return (b - a).total_seconds() / 86400 if a and b else None


def stats(trips: list[dict], include_copied: bool = False) -> dict:
    """The headline numbers for a set of round trips. `enough` is False below MIN_TRADES trades."""
    rows = [t for t in trips if include_copied or not t.get("copied")]
    results = [_num(t.get("net_result_usd")) or 0.0 for t in rows]
    wins = [r for r in results if r > 0]
    losses = [r for r in results if r < 0]
    win_holds = [h for t, r in zip(rows, results) if r > 0 for h in [_hold_days(t)] if h is not None]
    loss_holds = [h for t, r in zip(rows, results) if r < 0 for h in [_hold_days(t)] if h is not None]
    n = len(rows)
    return {
        "trades": n,
        "enough": n >= MIN_TRADES,
        "net": round(sum(results), 2),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / n * 100, 1) if n else None,
        "profit_factor": round(sum(wins) / -sum(losses), 2) if losses and wins else None,
        "expectancy": round(sum(results) / n, 2) if n else None,
        "avg_hold_win_days": round(sum(win_holds) / len(win_holds), 1) if win_holds else None,
        "avg_hold_loss_days": round(sum(loss_holds) / len(loss_holds), 1) if loss_holds else None,
        "fees": round(sum(_num(t.get("fees_usd")) or 0 for t in rows), 2),
    }


def stats_by(trips: list[dict], field: str, include_copied: bool = False) -> dict[str, dict]:
    """stats() for each value of a field (platform, asset_class, a snapshot's regime...)."""
    groups: dict[str, list[dict]] = {}
    for t in trips:
        groups.setdefault(str(t.get(field) or "unknown"), []).append(t)
    return {k: stats(v, include_copied) for k, v in sorted(groups.items())}


def equity_curve(trips: list[dict], include_copied: bool = False) -> list[tuple[str, float]]:
    """Running net result by close time, oldest first: [(closed_at, cumulative USD), ...]."""
    rows = sorted((t for t in trips if include_copied or not t.get("copied")), key=lambda t: t["closed_at"])
    total, out = 0.0, []
    for t in rows:
        total += _num(t.get("net_result_usd")) or 0.0
        out.append((t["closed_at"], round(total, 2)))
    return out
