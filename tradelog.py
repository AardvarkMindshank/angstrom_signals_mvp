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

import time
import uuid
from datetime import datetime, timezone

ETORO_API = "https://public-api.etoro.com/api/v1"
PAGE_SIZE = 100
MAX_PAGES = 1000                 # 12,000 trades at 100 a page is about 125 pages
MIN_TRADES = 10
ASSET_CLASSES = ("crypto", "stocks", "etfs", "indices", "commodities", "currencies", "other")


# ---- eToro ---------------------------------------------------------------------------------------------------

class EtoroError(Exception):
    """eToro refused or failed. The message never contains a key."""


def _headers(keys: dict) -> dict:
    return {"x-request-id": str(uuid.uuid4()), "x-api-key": keys["api_key"], "x-user-key": keys["user_key"],
            "Accept": "application/json"}


def _get(session, path: str, keys: dict, params: dict | None = None):
    for attempt in range(4):         # 504: eToro's own server timed out; 429: too fast. Wait and ask again.
        if attempt:
            time.sleep(10 * attempt)
        url = ETORO_API.rsplit("/v1", 1)[0] + path if path.startswith("/v2/") else ETORO_API + path
        r = session.get(url, headers=_headers(keys), params=params or {}, timeout=60)
        if r.status_code not in (504, 429):
            break
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


def fetch_closed_positions(session, keys: dict, min_date: str = "2010-01-01", stop_before: str | None = None,
                           workers: int = 1) -> list[dict]:
    """Every closed position since min_date (YYYY-MM-DD), all pages, newest first.

    eToro's pages can come back short (98 of 100) with more pages after them, so we read on until an EMPTY page, as
    eToro support advised (26 Nov 2026); stopping at the first short page had read only 98 of over 12,000 trades.
    A page that brings nothing new also ends it, in case eToro ever repeats a page. stop_before (an ISO date): stop
    once a whole page closed before it (the daily sync only needs the latest days). workers: pages read side by side
    (eToro takes a few seconds a page; two side by side halves the wait, and more makes eToro ask us to slow down)."""
    from concurrent.futures import ThreadPoolExecutor

    def one(page: int) -> list[dict]:
        return [b for b in _items(_get(session, "/trading/info/trade/history", keys,
                                       {"minDate": min_date, "page": page, "pageSize": PAGE_SIZE}))
                if isinstance(b, dict)]

    out: list[dict] = []
    seen: set = set()
    page = 1
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        while page <= MAX_PAGES:
            pages = list(range(page, min(page + max(1, workers), MAX_PAGES + 1)))
            for batch in (pool.map(one, pages) if workers > 1 else map(one, pages)):
                new = [b for b in batch if _pid(b) not in seen]
                if not new:
                    return out
                seen.update(_pid(b) for b in new)
                out += new
                closes = [str(b.get("closeTimestamp") or "") for b in new]
                if stop_before and closes and all(c and c < stop_before for c in closes):
                    return out
            page += len(pages)
    return out


def _pid(p: dict):
    return p.get("positionId") or p.get("positionID") or id(p)


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
            "reward": len(parts) == 1 and is_reward(first, symbol, cls, invested),
            "parts": len(parts),
            **exit_facts(first, max(parts, key=lambda p: _when(p.get("closeTimestamp")) or max(closed)),
                         invested, net),
        })
    trips.sort(key=lambda t: t["closed_at"], reverse=True)
    return trips


NEW_TRIP_FIELDS = ("stop_loss", "take_profit", "trailing_stop", "exit_kind", "risk_r", "reward")

# eToro pays crypto staking rewards (and passed on some airdrops) as small new positions, one a month per coin,
# credited in the first two weeks of the month. They aren't trades the member made: kept apart from every trade
# number (26 Nov 2026: 59 "Cardano trades" of $1 to $5 all closed on one day were monthly staking rewards).
STAKING = {"ADA", "SOL", "TRX", "DOT", "ETH", "ALGO", "ATOM", "XTZ", "AVAX", "NEAR", "POL", "MATIC", "ADA.X"}
AIRDROPS = {"LUNA2", "LUNA", "LUNC", "FLR", "SGB"}
REWARD_MAX_USD = 25.0


def is_reward(first: dict, symbol: str, asset_class: str, invested: float) -> bool:
    """A staking reward or airdrop position: an unleveraged crypto buy under $25 in a coin eToro stakes (credited in
    the first two weeks of a month) or one it airdropped. Never a copied position."""
    if asset_class != "crypto" or _num(first.get("socialTradeId")) or (_num(first.get("leverage")) or 1) != 1:
        return False
    if not first.get("isBuy", True) or not invested or invested >= REWARD_MAX_USD:
        return False
    sym = (symbol or "").upper()
    opened = _when(first.get("openTimestamp"))
    if sym in AIRDROPS:
        return True
    return sym in STAKING and opened is not None and opened.day <= 14
EXIT_TOLERANCE = 0.006          # a close within 0.6% of the stop or target counts as hitting it


def real_stop(entry: float | None, stop: float | None, leverage: float, is_long: bool) -> bool:
    """True when the stop loss was set by the trader, not eToro's far default (0 for an unleveraged buy, or about
    the margin's worth away for a leveraged trade)."""
    if not entry or not stop or stop <= 0:
        return False
    dist = (entry - stop) / entry if is_long else (stop - entry) / entry
    return 0 < dist < 0.8 / max(leverage or 1, 1)


def real_target(entry: float | None, target: float | None, is_long: bool) -> bool:
    """True when the take profit was set by the trader (eToro's default sits ten times or more away)."""
    if not entry or not target or target <= 0:
        return False
    gain = (target - entry) / entry if is_long else (entry - target) / entry
    return 0 < gain <= 2.0


def exit_facts(first: dict, last: dict, invested: float, net: float) -> dict:
    """Stop loss, take profit and trailing stop set on a trade, how it ended, and its result in R (multiples of
    the money at risk at the stop loss). R and the stop-loss ending only when the trader set a real stop."""
    entry, close = _num(first.get("openRate")), _num(last.get("closeRate"))
    stop, target = _num(last.get("stopLossRate")), _num(last.get("takeProfitRate"))
    trailing = bool(last.get("trailingStopLoss"))
    is_long = bool(first.get("isBuy", True))
    lev = _num(first.get("leverage")) or 1
    has_stop, has_target = real_stop(entry, stop, lev, is_long), real_target(entry, target, is_long)
    kind = "by_hand"
    if entry and close:
        if has_stop and abs(close - stop) / entry <= EXIT_TOLERANCE:
            kind = "trailing_stop" if trailing else "stop_loss"
        elif has_target and abs(close - target) / entry <= EXIT_TOLERANCE:
            kind = "take_profit"
    risk = None
    if has_stop and invested:
        risk = invested * lev * abs(entry - stop) / entry
    return {"stop_loss": stop if has_stop else None, "take_profit": target if has_target else None,
            "trailing_stop": trailing if has_stop else None, "exit_kind": kind,
            "risk_r": round(net / risk, 2) if risk else None}


def fetch_me(session, keys: dict) -> dict:
    return _get(session, "/me", keys) or {}


def fetch_daily_gain(session, keys: dict, username: str, today: str) -> list[list]:
    """eToro's own return for each day since the account began: [[YYYY-MM-DD, fraction], ...] (0.01 = 1%)."""
    body = _get(session, f"/v2/portfolios/{username}/gain/daily", keys, {"minDate": "2007-01-01", "maxDate": today})
    out = []
    for g in (body or {}).get("gains") or []:
        if isinstance(g, dict) and g.get("date") and _num(g.get("gain")) is not None:
            out.append([str(g["date"])[:10], _num(g["gain"])])
    return sorted(out)


def fetch_allocation(session, keys: dict, username: str, today: str) -> list[dict]:
    """Share of the account in cash and in each asset, one entry per month end (eToro keeps about 3 years)."""
    body = _get(session, f"/v2/portfolios/{username}/assets/history", keys,
                {"minDate": "2018-01-01", "maxDate": today, "count": 0})
    by_month: dict[str, dict] = {}
    for r in (body or {}).get("results") or []:
        if not isinstance(r, dict) or not r.get("date"):
            continue
        by_month[str(r["date"])[:7]] = r                     # the last day seen in each month
    out = []
    for month in sorted(by_month):
        r = by_month[month]
        assets = {str(a.get("symbol") or a.get("instrumentId")): _num(a.get("valuePct")) or 0
                  for a in r.get("assets") or [] if isinstance(a, dict)}
        out.append({"month": month, "cash": _num(r.get("cashOfTotalEquityPct")) or 0, "assets": assets})
    return out


def fetch_candles(session, keys: dict, instrument_id: int, interval: str = "OneDay", count: int = 1000) -> list:
    """[[YYYY-MM-DD, open, high, low, close], ...] oldest first, from eToro (at most 1,000 candles)."""
    body = _get(session, f"/market-data/instruments/{int(instrument_id)}/history/candles/asc/{interval}/{count}", keys)
    groups = (body or {}).get("candles") or []
    rows = (groups[0] or {}).get("candles") if groups and isinstance(groups[0], dict) else []
    return [[str(c["fromDate"])[:10], _num(c.get("open")), _num(c.get("high")), _num(c.get("low")), _num(c.get("close"))]
            for c in rows or [] if isinstance(c, dict) and c.get("fromDate")]


def trade_moves(trip: dict, candles: list) -> dict:
    """How much of the best price move a winning trade kept, and what the price did in the 20 trading days after
    it closed (positive = further in the trade's favour). None when the candles don't cover the trade."""
    if not candles:
        return {"kept_pct": None, "after20_pct": None}
    o, c = str(trip.get("opened_at"))[:10], str(trip.get("closed_at"))[:10]
    if candles[0][0] > o:
        return {"kept_pct": None, "after20_pct": None}
    long = trip.get("direction") != "short"
    entry, exit_ = _num(trip.get("entry_price")), _num(trip.get("exit_price"))
    inside = [k for k in candles if o <= k[0] <= c]
    after = [k for k in candles if k[0] > c]
    kept = None
    if inside and entry and exit_ and (_num(trip.get("net_result_usd")) or 0) > 0:
        best = max(k[2] for k in inside if k[2] is not None) if long else min(k[3] for k in inside if k[3] is not None)
        room = (best - entry) if long else (entry - best)
        made = (exit_ - entry) if long else (entry - exit_)
        if room > 0:
            kept = round(max(0.0, min(made / room, 1.0)) * 100, 1)
    later = None
    if len(after) >= 20 and exit_ and after[19][4]:
        move = after[19][4] / exit_ - 1
        later = round((move if long else -move) * 100, 2)
    return {"kept_pct": kept, "after20_pct": later}


def fetch_portfolio(session, keys: dict) -> dict:
    """The account as it is now: {"cash": USD, "pnl": open profit or loss, "positions": [raw open positions]}.
    Positions inside copy-trading funds are marked "_copied". eToro's trade history has closed trades only."""
    body = _get(session, "/trading/info/real/pnl", keys) or {}
    cp = body.get("clientPortfolio") or {} if isinstance(body, dict) else {}
    positions = [dict(p, _copied=bool(_num(p.get("mirrorID")))) for p in cp.get("positions") or []
                 if isinstance(p, dict)]
    for m in cp.get("mirrors") or []:
        positions += [dict(p, _copied=True) for p in (m or {}).get("positions") or [] if isinstance(p, dict)]
    return {"cash": _num(cp.get("credit")), "pnl": _num(cp.get("unrealizedPnL")), "positions": positions}


def etoro_open_positions(positions: list[dict], instruments: dict[int, dict] | None = None,
                         types: dict[int, str] | None = None, asset_keys: dict | None = None) -> list[dict]:
    """eToro's open positions → rows for trade_open_positions. Value = money in it (amount) + its profit or loss."""
    instruments, types, asset_keys = instruments or {}, types or {}, asset_keys or {}
    out = []
    for p in positions:
        if p.get("positionID") is None:
            continue
        iid = p.get("instrumentID")
        info = instruments.get(int(iid)) if iid is not None else None
        info = info or {}
        symbol = str(info.get("symbolFull") or "")
        cls = asset_class_of(types.get(int(info["instrumentTypeID"]), "")) if info.get("instrumentTypeID") is not None else "other"
        upnl = p.get("unrealizedPnL") if isinstance(p.get("unrealizedPnL"), dict) else {}
        pnl = _num(upnl.get("pnL")) if upnl else _num(p.get("pnL"))
        amount = _num(p.get("amount"))
        out.append({
            "platform": "etoro",
            "position_id": str(p["positionID"]),
            "instrument_id": "" if iid is None else str(iid),
            "symbol": symbol[:40],
            "name": str(info.get("instrumentDisplayName") or symbol or f"Instrument {iid}")[:120],
            "asset_class": cls,
            "asset_key": asset_keys.get((cls, symbol.upper())),
            "direction": "long" if p.get("isBuy", True) else "short",
            "opened_at": p.get("openDateTime") or None,
            "entry_price": _num(p.get("openRate")),
            "current_price": _num(upnl.get("closeRate")) if upnl else _num(p.get("closeRate")),
            "units": _num(p.get("units")),
            "invested_usd": amount,
            "value_usd": round(amount + (pnl or 0), 2) if amount is not None else None,
            "pnl_usd": round(pnl, 2) if pnl is not None else None,
            "leverage": _num(p.get("leverage")) or 1,
            "copied": bool(p.get("_copied")),
            "stop_loss": (_num(p.get("stopLossRate")) if real_stop(_num(p.get("openRate")), _num(p.get("stopLossRate")),
                                                                  _num(p.get("leverage")) or 1, p.get("isBuy", True))
                          else None),
            "overnight_fees_usd": _num(p.get("totalFees")),
        })
    out.sort(key=lambda r: -(r["value_usd"] or 0))
    return out


# ---- stats ---------------------------------------------------------------------------------------------------

def _hold_days(trip: dict) -> float | None:
    a, b = _when(trip.get("opened_at")), _when(trip.get("closed_at"))
    return (b - a).total_seconds() / 86400 if a and b else None


def stats(trips: list[dict], include_copied: bool = False) -> dict:
    """The headline numbers for a set of round trips. `enough` is False below MIN_TRADES trades."""
    rows = [t for t in trips if (include_copied or not t.get("copied")) and not t.get("reward")]
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


def invested_by_day(trips: list[dict], include_copied: bool = False,
                    open_positions: list[dict] | None = None) -> list[tuple[str, float, float]]:
    """Each day from the first open to the last close: (YYYY-MM-DD, money in open trades at the day's end, running
    net result of the trades closed by then). Built from each trade's open and close times and amount invested, so
    it shows the money put to work rising and falling over the years (26 Nov 2026). Not the account's full value:
    cash waiting in the account and the open trades' gains or losses before they closed are not in it.
    open_positions: trades still open count from the day they opened to today."""
    from datetime import timedelta
    rows = [t for t in trips if (include_copied or not t.get("copied"))
            and _when(t.get("opened_at")) and _when(t.get("closed_at"))]
    still = [o for o in (open_positions or []) if (include_copied or not o.get("copied")) and _when(o.get("opened_at"))]
    if not rows and not still:
        return []
    change: dict = {}
    result: dict = {}
    for o in still:                                   # trades still open: in the market from their open to today
        d = _when(o["opened_at"]).date()
        change[d] = change.get(d, 0.0) + (_num(o.get("invested_usd")) or 0.0)
    if still:
        change.setdefault(datetime.now(timezone.utc).date(), 0.0)
    for t in rows:
        o, c = _when(t["opened_at"]).date(), _when(t["closed_at"]).date()
        amount = _num(t.get("invested_usd")) or 0.0
        change[o] = change.get(o, 0.0) + amount
        change[c] = change.get(c, 0.0) - amount
        result[c] = result.get(c, 0.0) + (_num(t.get("net_result_usd")) or 0.0)
    day, last = min(change), max(change)
    held = total = 0.0
    out = []
    while day <= last:
        held += change.get(day, 0.0)
        total += result.get(day, 0.0)
        out.append((day.isoformat(), round(max(held, 0.0), 2), round(total, 2)))
        day += timedelta(days=1)
    return out


# ---- patterns (plain rules on the member's own numbers; no AI) ------------------------------------------------

def patterns(trips: list[dict], include_copied: bool = False) -> list[dict]:
    """Habits worth noticing, each with the number of trades it rests on. Only shown when there are enough trades
    (MIN_TRADES overall, and at least 5 on each side of a comparison); a description, never advice."""
    rows = [t for t in trips if include_copied or not t.get("copied")]
    found: list[dict] = []
    if len(rows) < MIN_TRADES:
        return found
    s = stats(rows, True)
    win, loss = s["avg_hold_win_days"], s["avg_hold_loss_days"]
    if win and loss and s["wins"] >= 5 and s["losses"] >= 5:
        if loss >= 1.5 * win:
            found.append({"kind": "hold_losers", "times": round(loss / win, 1), "trades": s["trades"]})
        elif win >= 1.5 * loss:
            found.append({"kind": "hold_winners", "times": round(win / loss, 1), "trades": s["trades"]})
    ordered = sorted(rows, key=lambda t: str(t.get("opened_at") or ""))
    after_loss, after_win = [], []
    for prev, nxt in zip(ordered, ordered[1:]):
        size = _num(nxt.get("invested_usd"))
        if not size or (_when(nxt.get("opened_at")) or datetime.min.replace(tzinfo=timezone.utc)) < (
                _when(prev.get("closed_at")) or datetime.max.replace(tzinfo=timezone.utc)):
            continue                                              # only trades opened after the previous one closed
        (after_loss if (_num(prev.get("net_result_usd")) or 0) < 0 else after_win).append(size)
    if len(after_loss) >= 5 and len(after_win) >= 5:
        ratio = (sum(after_loss) / len(after_loss)) / (sum(after_win) / len(after_win))
        if ratio >= 1.3 or ratio <= 0.77:
            found.append({"kind": "size_after_loss", "times": round(ratio, 1),
                          "trades": len(after_loss) + len(after_win)})
    by = {k: v for k, v in stats_by(rows, "asset_class", True).items() if v["trades"] >= MIN_TRADES}
    if len(by) >= 2:
        best = max(by, key=lambda k: by[k]["expectancy"] or 0)
        worst = min(by, key=lambda k: by[k]["expectancy"] or 0)
        if best != worst and (by[best]["expectancy"] or 0) > (by[worst]["expectancy"] or 0):
            found.append({"kind": "class_gap", "better": best, "worse": worst,
                          "trades": by[best]["trades"] + by[worst]["trades"]})
    return found
