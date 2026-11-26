"""Trade Log insights: the ready-made summaries the new Trade Log page reads (26 Nov 2026).

The background job works these out after a sync, from the member's own rows, and keeps one small JSON document per
scope ("all" or one connection), whose trades ("own", "copied", "all") and period ("1y", "3y", "5y", "all") in
trade_insights. The page reads one document and draws it; nothing heavy happens in the browser.

What each part answers (docs: "Trade Log: what eToro's data can tell a trader"):
- account: return, yearly average, deepest fall, best and worst year, and Bitcoin and the S&P 500 over the same days,
  from eToro's daily return (deposits and withdrawals don't move it). Account-wide: the same for every "whose".
- curve, drawdown, monthly: the same daily return as a growth-of-$100 line, its fall below each high, and a month grid.
- closed: the closed-trade numbers (net result, win rate, profit factor, holds) for the chosen trades.
- compare: own trades against copied ones, side by side.
- edge: net result, win rate and count by asset class, direction, leverage, hold time, market regime at entry and day.
- assets: the five best and five worst assets by net result.
- risk, exits, moves: results in R (multiples of the money at risk at a real stop loss), how trades ended, how much of
  the best move winners kept and the price 20 trading days after.
- habits: plain checks on the member's own trades (never copied ones: those decisions were someone else's).
- allocation: share of the account by asset each month (eToro keeps about three years).
- open: open positions grouped by asset, spare cash and the market reading for each asset now.

Every number is computed here from the rows; the page only formats. Texts are keys with numbers, so the page can say
them in the member's language.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from statistics import median

PERIODS = {"1y": 365, "3y": 3 * 365, "5y": 5 * 365, "all": None}
WHOSE = ("own", "copied", "all")
MIN_CELL = 5                     # trades a box needs before it can be called an edge or a leak


def _num(v) -> float | None:
    try:
        return None if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return None


def _when(v) -> datetime | None:
    if not v:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _r(v, digits=2):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(v, digits)


# ---- closed trades -----------------------------------------------------------------------------------------------

def closed_stats(trips: list[dict]) -> dict:
    res = [_num(t.get("net_result_usd")) or 0.0 for t in trips]
    wins = [r for r in res if r > 0]
    losses = [r for r in res if r < 0]

    def hold(sel):
        days = [(_when(t["closed_at"]) - _when(t["opened_at"])).total_seconds() / 86400
                for t, r in zip(trips, res) if sel(r) and _when(t.get("opened_at")) and _when(t.get("closed_at"))]
        return _r(sum(days) / len(days), 1) if days else None
    n = len(trips)
    return {"trades": n, "net": _r(sum(res)), "wins": len(wins), "losses": len(losses),
            "win_rate": _r(len(wins) / n * 100, 1) if n else None,
            "profit_factor": _r(sum(wins) / -sum(losses)) if wins and losses else None,
            "average": _r(sum(res) / n) if n else None,
            "hold_win_days": hold(lambda r: r > 0), "hold_loss_days": hold(lambda r: r < 0),
            "fees": _r(sum(_num(t.get("fees_usd")) or 0 for t in trips))}


def _cell(label: str, trips: list[dict]) -> dict:
    s = closed_stats(trips)
    return {"label": label, "net": s["net"], "win_rate": s["win_rate"], "trades": s["trades"]}


def _band_hold(t: dict) -> str:
    a, b = _when(t.get("opened_at")), _when(t.get("closed_at"))
    d = (b - a).total_seconds() / 86400 if a and b else 0
    return "under_day" if d < 1 else "week" if d < 7 else "month" if d < 28 else "longer"


def _band_lev(t: dict) -> str:
    lev = _num(t.get("leverage")) or 1
    return "none" if lev <= 1 else "x2" if lev <= 2 else "above_2"


def _day(t: dict) -> str:
    a = _when(t.get("opened_at"))
    wd = a.weekday() if a else 0
    return "mon_thu" if wd < 4 else "fri" if wd == 4 else "weekend"


def market_state(readings: dict | None) -> str | None:
    """MarketNavi's reading → up-trend, down-trend or sideways: a trending regime takes its side from Trend."""
    r = readings or {}
    regime, trend = str(r.get("regime") or ""), _num(r.get("trend"))
    if not regime:
        return None
    if regime == "trending_up":
        return "up"
    if regime == "trending_down":
        return "down"
    if regime == "trending" and trend is not None:
        return "up" if trend > 0 else "down"
    return "side"


def edge(trips: list[dict], snaps: dict) -> dict:
    """Net result, win rate and count by six dimensions, and the strongest edge and leak (boxes with ≥ MIN_CELL)."""
    def group(fn, order):
        cells = []
        for key in order:
            sel = [t for t in trips if fn(t) == key]
            if sel:
                cells.append(_cell(key, sel))
        return cells

    def regime(t):
        return market_state(snaps.get((t.get("id"), "entry"))) or "unknown"
    classes = ("crypto", "stocks", "etfs", "indices", "commodities", "currencies", "other")
    rows = [
        {"dim": "asset_class", "cells": group(lambda t: t.get("asset_class") or "other", classes)},
        {"dim": "direction", "cells": group(lambda t: t.get("direction") or "long", ("long", "short"))},
        {"dim": "leverage", "cells": group(_band_lev, ("none", "x2", "above_2"))},
        {"dim": "held", "cells": group(_band_hold, ("under_day", "week", "month", "longer"))},
        {"dim": "regime", "cells": [c for c in group(regime, ("up", "side", "down", "unknown")) if c["label"] != "unknown"]},
        {"dim": "day", "cells": group(_day, ("mon_thu", "fri", "weekend"))},
    ]
    rows = [r for r in rows if r["cells"]]
    # A box holding nearly all the trades ("long", say) says nothing about where the edge is: leave those out.
    flat = [(r["dim"], c) for r in rows for c in r["cells"]
            if c["trades"] >= MIN_CELL and len(r["cells"]) > 1
            and c["trades"] <= 0.85 * sum(x["trades"] for x in r["cells"])]
    best = max(flat, key=lambda x: x[1]["net"], default=None)
    worst = min(flat, key=lambda x: x[1]["net"], default=None)
    return {"rows": rows,
            "edge": {"dim": best[0], **best[1]} if best and best[1]["net"] > 0 else None,
            "leak": {"dim": worst[0], **worst[1]} if worst and worst[1]["net"] < 0 else None}


def assets(trips: list[dict], n: int = 5) -> dict:
    by: dict[str, list] = {}
    for t in trips:
        by.setdefault(str(t.get("name") or t.get("symbol") or "?"), []).append(_num(t.get("net_result_usd")) or 0)
    rows = sorted(({"name": k, "net": _r(sum(v)), "trades": len(v)} for k, v in by.items()), key=lambda x: -x["net"])
    best = [r for r in rows if r["net"] > 0][:n]
    worst = [r for r in reversed(rows) if r["net"] < 0][:n]
    return {"best": best, "worst": list(reversed(worst))}


def risk(trips: list[dict]) -> dict:
    with_r = [t for t in trips if _num(t.get("risk_r")) is not None]
    buckets = {}
    for t in with_r:
        b = max(-5, min(5, int(math.floor(_num(t["risk_r"]) + 0.5))))
        buckets[b] = buckets.get(b, 0) + 1
    worst = min(with_r, key=lambda t: _num(t["risk_r"]), default=None)
    risks = [abs((_num(t.get("net_result_usd")) or 0) / _num(t["risk_r"])) for t in with_r if _num(t["risk_r"])]
    sizes = [(_num(t.get("invested_usd")) or 0) for t in with_r]
    return {"trades": len(trips), "with_stop": len(with_r),
            "stop_share": _r(len(with_r) / len(trips) * 100, 1) if trips else None,
            "hist": [{"r": k, "count": buckets.get(k, 0)} for k in range(-5, 6)],
            "median_risk_usd": _r(median(risks)) if risks else None,
            "median_risk_pct": _r(median(r / s * 100 for r, s in zip(risks, sizes) if s), 1) if risks and any(sizes) else None,
            "worst": {"r": _num(worst["risk_r"]), "name": worst.get("name"), "closed": str(worst.get("closed_at"))[:10]}
            if worst else None}


def exits(trips: list[dict]) -> dict:
    kinds = ("stop_loss", "take_profit", "trailing_stop", "by_hand")
    known = [t for t in trips if t.get("exit_kind")]
    out = []
    for k in kinds:
        sel = [t for t in known if t["exit_kind"] == k]
        if not sel:
            continue
        rs = [_num(t.get("risk_r")) for t in sel if _num(t.get("risk_r")) is not None]
        out.append({"kind": k, "share": _r(len(sel) / len(known) * 100, 1), "trades": len(sel),
                    # an average in R only when most of these trades had a real stop; otherwise in dollars
                    "avg_r": _r(sum(rs) / len(rs), 2) if len(rs) >= max(3, 0.5 * len(sel)) else None,
                    "avg_usd": _r(sum(_num(t.get("net_result_usd")) or 0 for t in sel) / len(sel))})
    return {"known": len(known), "kinds": out}


def moves(trips: list[dict]) -> dict:
    kept = [_num(t.get("kept_pct")) for t in trips if _num(t.get("kept_pct")) is not None]
    after = [_num(t.get("after20_pct")) for t in trips if _num(t.get("after20_pct")) is not None and
             (_num(t.get("net_result_usd")) or 0) > 0]
    return {"kept_median": _r(median(kept), 1) if len(kept) >= 5 else None, "kept_trades": len(kept),
            "after20_winners": _r(sum(after) / len(after), 1) if len(after) >= 5 else None, "after_trades": len(after)}


def habits(own: list[dict]) -> list[dict]:
    """Plain checks on the member's own trades. Each: key, kind (good / bad / neutral) and its numbers."""
    out = []
    if len(own) < 20:
        return out
    trips = sorted(own, key=lambda t: _when(t["opened_at"]))
    res = {id(t): _num(t.get("net_result_usd")) or 0 for t in trips}
    # 1. Trading again soon after a loss
    closes = sorted((_when(t["closed_at"]), res[id(t)]) for t in trips if _when(t.get("closed_at")))
    after, other = [], []
    j, last_loss = 0, None
    for t in trips:
        o = _when(t["opened_at"])
        while j < len(closes) and closes[j][0] <= o:
            if closes[j][1] < 0:
                last_loss = closes[j][0]
            j += 1
        (after if last_loss and o - last_loss <= timedelta(hours=6) else other).append(res[id(t)])
    if len(after) >= 10 and other:
        a, b = sum(after) / len(after), sum(other) / len(other)
        out.append({"key": "after_loss", "kind": "bad" if a < b and a < 0 else "good" if a >= b else "neutral",
                    "trades": len(after), "total": _r(sum(after)), "avg_after": _r(a), "avg_other": _r(b)})
    # 2. Holding losers against winners
    s = closed_stats(trips)
    if s["hold_win_days"] and s["hold_loss_days"]:
        ratio = s["hold_loss_days"] / s["hold_win_days"] if s["hold_win_days"] else None
        if ratio and (ratio >= 1.3 or ratio <= 0.77):
            out.append({"key": "hold_losers" if ratio >= 1.3 else "cut_losers", "kind": "bad" if ratio >= 1.3 else "good",
                        "ratio": _r(ratio if ratio >= 1.3 else 1 / ratio, 1), "loss_days": s["hold_loss_days"],
                        "win_days": s["hold_win_days"]})
    # 3. Busy days
    per_day: dict = {}
    for t in trips:
        per_day.setdefault(_when(t["opened_at"]).date(), []).append(res[id(t)])
    busy = [v for v in per_day.values() if len(v) >= 10]
    quiet = [v for v in per_day.values() if len(v) <= 3]
    if len(busy) >= 3 and quiet:
        bt, qt = sum(sum(v) for v in busy), sum(sum(v) for v in quiet)
        out.append({"key": "busy_days", "kind": "bad" if bt < 0 <= qt else "good" if bt > 0 else "neutral",
                    "days": len(busy), "total": _r(bt), "quiet_total": _r(qt)})
    # 4. Size after a winning streak
    sizes = [_num(t.get("invested_usd")) or 0 for t in trips]
    typical = median([x for x in sizes if x]) if any(sizes) else 0
    streak_next = []
    run = 0
    for i, t in enumerate(trips[:-1]):
        run = run + 1 if res[id(t)] > 0 else 0
        if run >= 3:
            streak_next.append(trips[i + 1])
    if len(streak_next) >= 5 and typical:
        grow = median(_num(t.get("invested_usd")) or 0 for t in streak_next) / typical - 1
        wr = sum(1 for t in streak_next if res[id(t)] > 0) / len(streak_next) * 100
        if abs(grow) >= 0.2:
            out.append({"key": "streak_size", "kind": "neutral" if wr >= (s["win_rate"] or 0) - 5 else "bad",
                        "grow_pct": _r(grow * 100, 0), "win_rate": _r(wr, 0), "usual_win_rate": s["win_rate"],
                        "trades": len(streak_next)})
    # 5. Leverage
    lev = [t for t in trips if (_num(t.get("leverage")) or 1) > 2]
    if len(lev) >= MIN_CELL:
        lt = sum(res[id(t)] for t in lev)
        if lt < 0:
            out.append({"key": "leverage", "kind": "bad", "trades": len(lev), "total": _r(lt),
                        "rest_total": _r(sum(res.values()) - lt)})
    # 6. Concentration of losses
    by: dict = {}
    for t in trips:
        if res[id(t)] < 0:
            by[str(t.get("name") or "?")] = by.get(str(t.get("name") or "?"), 0) + res[id(t)]
    total_loss = sum(by.values())
    if by and total_loss < 0:
        name, worst = min(by.items(), key=lambda x: x[1])
        share = worst / total_loss
        if share >= 0.3:
            out.append({"key": "loss_concentration", "kind": "bad", "name": name, "share": _r(share * 100, 0),
                        "total": _r(worst)})
    # 7. Patience: the best hold band
    bands: dict = {}
    for t in trips:
        bands.setdefault(_band_hold(t), []).append(res[id(t)])
    good = [(k, v) for k, v in bands.items() if len(v) >= MIN_CELL and sum(v) > 0]
    if good:
        k, v = max(good, key=lambda x: sum(x[1]))
        out.append({"key": "best_hold", "kind": "good", "band": k, "trades": len(v), "total": _r(sum(v)),
                    "win_rate": _r(sum(1 for x in v if x > 0) / len(v) * 100, 0)})
    return out


# ---- the account as a whole (eToro's daily return) ---------------------------------------------------------------

def _weekly(points: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Keep one point a week (the last of each ISO week) plus the very last point."""
    out, seen = [], None
    for d, v in points:
        wk = date.fromisoformat(d).isocalendar()[:2]
        if out and seen == wk:
            out[-1] = (d, v)
        else:
            out.append((d, v))
        seen = wk
    return out


def _bench_on(series: list, day: str) -> float | None:
    """The benchmark's last weekly close on or before a day."""
    best = None
    for d, c in series:
        if d <= day:
            best = c
        else:
            break
    return best


def account(daily_gain: list, benchmarks: dict, start: str | None) -> dict | None:
    """Growth of $100, drawdown, monthly grid and headline numbers from eToro's daily return since `start`."""
    pts = [(d, g) for d, g in daily_gain if (start is None or d >= start) and g is not None]
    if len(pts) < 20:
        return None
    level, idx, peak = 100.0, [], 100.0
    dd, deepest, deep_from, deep_to, peak_day = [], 0.0, None, None, pts[0][0]
    under_since, longest = None, 0
    for d, g in pts:
        level *= 1 + g
        idx.append((d, level))
        if level >= peak:
            if under_since:
                longest = max(longest, (date.fromisoformat(d) - date.fromisoformat(under_since)).days)
            peak, peak_day, under_since = level, d, None
        else:
            under_since = under_since or peak_day
        x = level / peak - 1
        dd.append((d, x))
        if x < deepest:
            deepest, deep_from, deep_to = x, peak_day, d
    if under_since:
        longest = max(longest, (date.fromisoformat(pts[-1][0]) - date.fromisoformat(under_since)).days)
    first, last = pts[0][0], pts[-1][0]
    years_n = max((date.fromisoformat(last) - date.fromisoformat(first)).days / 365.25, 1 / 365)
    total = level / 100 - 1
    by_year, by_month = {}, {}
    for d, g in pts:
        by_year[d[:4]] = by_year.get(d[:4], 1.0) * (1 + g)
        by_month[d[:7]] = by_month.get(d[:7], 1.0) * (1 + g)
    years = {y: v - 1 for y, v in by_year.items()}
    full_years = {y: v for y, v in years.items() if y != last[:4] and y != first[:4]} or years
    bench = {}
    for name, series in (benchmarks or {}).items():
        a, b = _bench_on(series, first), _bench_on(series, last)
        if a and b:
            bench[name] = {"total": _r((b / a - 1) * 100, 1)}
    curve = []
    for d, v in _weekly(idx):
        row = {"d": d, "acc": _r(v, 2)}
        for name, series in (benchmarks or {}).items():
            a, c = _bench_on(series, first), _bench_on(series, d)
            row[name] = _r(c / a * 100, 2) if a and c else None
        curve.append(row)
    dd_weekly = [{"d": d, "dd": _r(v * 100, 2)} for d, v in _weekly(dd)]
    best_y = max(full_years, key=full_years.get)
    worst_y = min(full_years, key=full_years.get)
    return {
        "from": first, "to": last,
        "total_pct": _r(total * 100, 1),
        "yearly_pct": _r(((1 + total) ** (1 / years_n) - 1) * 100, 1) if total > -1 else None,
        "deepest": {"pct": _r(deepest * 100, 1), "from": deep_from, "to": deep_to},
        "longest_under_days": longest,
        "now_below_high_pct": _r(dd[-1][1] * 100, 1),
        "best_year": {"year": best_y, "pct": _r(full_years[best_y] * 100, 1)},
        "worst_year": {"year": worst_y, "pct": _r(full_years[worst_y] * 100, 1)},
        "bench": bench,
        "curve": curve, "drawdown": dd_weekly,
        "years": {y: _r(v * 100, 1) for y, v in sorted(years.items())},
        "months": {m: _r((v - 1) * 100, 1) for m, v in sorted(by_month.items())},
    }


def allocation(rows: list[dict], start: str | None, top: int = 4) -> dict | None:
    rows = [r for r in rows or [] if start is None or r["month"] >= start[:7]]
    if not rows:
        return None
    weight: dict = {}
    for r in rows:
        for k, v in (r.get("assets") or {}).items():
            weight[k] = weight.get(k, 0) + (v or 0)
    names = [k for k, _ in sorted(weight.items(), key=lambda x: -x[1])[:top]]
    months = []
    for r in rows:
        a = r.get("assets") or {}
        parts = [{"name": k, "pct": _r((a.get(k) or 0) * 100, 1)} for k in names]
        other = sum(v or 0 for k, v in a.items() if k not in names)
        months.append({"month": r["month"], "parts": parts, "other": _r(other * 100, 1), "cash": _r((r.get("cash") or 0) * 100, 1)})
    return {"names": names, "months": months}


def open_now(opened: list[dict], conns: list[dict], regimes: dict) -> dict | None:
    if not any(c.get("portfolio_at") for c in conns):
        return None
    cash = sum(_num(c.get("cash_usd")) or 0 for c in conns)
    by: dict = {}
    for o in opened:
        by.setdefault(str(o.get("name") or o.get("symbol") or "?"), []).append(o)
    rows = []
    for name, ps in by.items():
        inv = sum(_num(p.get("invested_usd")) or 0 for p in ps)
        val = sum(_num(p.get("value_usd")) or 0 for p in ps)
        stops = []
        for p in ps:
            s, cur = _num(p.get("stop_loss")), _num(p.get("current_price"))
            if s and cur:
                stops.append((s - cur) / cur * 100 if p.get("direction") != "short" else (cur - s) / cur * 100)
        fees = [(_num(p.get("overnight_fees_usd")) or 0) for p in ps]
        key = next((p.get("asset_key") for p in ps if p.get("asset_key")), None)
        rows.append({"name": name, "positions": len(ps), "invested": _r(inv), "value": _r(val), "pnl": _r(val - inv),
                     "stop_pct": _r(max(stops), 1) if stops and len(stops) == len(ps) else None,
                     "stops_set": len(stops), "fees": _r(sum(fees)),
                     "now": market_state(regimes.get(key)) if key else None,
                     "copied": all(p.get("copied") for p in ps)})
    rows.sort(key=lambda r: -(r["value"] or 0))
    inv = sum(r["invested"] or 0 for r in rows)
    val = sum(r["value"] or 0 for r in rows)
    biggest = rows[0] if rows else None
    when = max((c["portfolio_at"] for c in conns if c.get("portfolio_at")), default=None)
    return {"cash": _r(cash), "invested": _r(inv), "value": _r(val), "pnl": _r(val - inv),
            "pnl_pct": _r((val - inv) / inv * 100, 1) if inv else None, "account": _r(val + cash),
            "positions": sum(r["positions"] for r in rows), "assets": len(rows),
            "largest": {"name": biggest["name"], "pct": _r(biggest["value"] / (val + cash) * 100, 0)}
            if biggest and (val + cash) else None,
            "rows": rows, "as_at": when}


# ---- one document ------------------------------------------------------------------------------------------------

def _whose(trips: list[dict], whose: str) -> list[dict]:
    return trips if whose == "all" else [t for t in trips if bool(t.get("copied")) == (whose == "copied")]


def build(trips: list[dict], snaps: dict, opened: list[dict], conns: list[dict], series: dict, regimes: dict,
          whose: str, period: str, today: date) -> dict:
    days = PERIODS[period]
    start = (today - timedelta(days=days)).isoformat() if days else None
    closed_in = [t for t in trips if start is None or str(t.get("closed_at") or "")[:10] >= start]
    rewards = [t for t in closed_in if t.get("reward")]
    in_period = [t for t in closed_in if not t.get("reward")]     # staking rewards and airdrops aren't trades
    chosen = _whose(in_period, whose)
    own = _whose(in_period, "own")
    acct = account(series.get("daily_gain") or [], series.get("benchmarks") or {}, start)
    return {
        "whose": whose, "period": period, "start": start, "today": today.isoformat(),
        "account": acct,
        "closed": closed_stats(chosen),
        "compare": {"own": closed_stats(own), "copied": closed_stats(_whose(in_period, "copied"))},
        "edge": edge(chosen, snaps),
        "assets": assets(chosen),
        "risk": risk(chosen),
        "exits": exits(chosen),
        "moves": moves(chosen),
        "habits": habits(own),
        "allocation": allocation(series.get("allocation") or [], start),
        "open": open_now(_whose(opened, whose), conns, regimes),
        "rewards": {"count": len(rewards),
                    "credited": _r(sum(_num(t.get("invested_usd")) or 0 for t in rewards)),
                    "result": _r(sum(_num(t.get("net_result_usd")) or 0 for t in rewards))},
    }


# ---- the worker's step -------------------------------------------------------------------------------------------

def _rows(supabase, table: str, cols: str, user_id: str, *order: str) -> list:
    from tradelog_sync import _pages

    def query():
        q = supabase.table(table).select(cols).eq("user_id", user_id)
        for o in order or ("id",):
            q = q.order(o)
        return q
    return _pages(query)


def compute_for(supabase, user_id: str, conns: list[dict], inputs, now: datetime) -> int:
    """Work out and keep every document for one member. Returns how many were written."""
    trips = _rows(supabase, "trade_round_trips", "*", user_id)
    snaps = {}
    for s in _rows(supabase, "trade_snapshots", "round_trip_id,moment,readings", user_id, "round_trip_id", "moment"):
        snaps[(s["round_trip_id"], s["moment"])] = s.get("readings") or {}
    try:
        opened = _rows(supabase, "trade_open_positions", "*", user_id)
    except Exception:
        opened = []
    series_rows = supabase.table("trade_series").select("connection_id,kind,data").eq("user_id", user_id).execute().data or []
    regimes = {}
    for key in {o.get("asset_key") for o in opened if o.get("asset_key")}:
        rec = inputs.record(key) if inputs else {}
        if rec:
            regimes[key] = rec[max(rec)] or {}
    scopes = [("all", trips, opened, conns)] + ([(c["id"], [t for t in trips if t["connection_id"] == c["id"]],
                                                  [o for o in opened if o["connection_id"] == c["id"]], [c])
                                                 for c in conns] if len(conns) > 1 else [])
    written = 0
    for scope, ts, os_, cs in scopes:
        ids = {c["id"] for c in cs}
        series: dict = {}
        for r in series_rows:
            if r["connection_id"] in ids and r["kind"] not in series:
                series[r["kind"]] = r["data"]
        if len(cs) > 1:                       # several accounts: no single daily return to show
            series.pop("daily_gain", None)
            series.pop("allocation", None)
        docs = [{"user_id": user_id, "scope": scope, "whose": w, "period": p,
                 "data": build(ts, snaps, os_, cs, series, regimes, w, p, now.date()),
                 "computed_at": now.isoformat()} for w in WHOSE for p in PERIODS]
        supabase.table("trade_insights").upsert(docs, on_conflict="user_id,scope,whose,period").execute()
        written += len(docs)
    keep = {"all"} | ({c["id"] for c in conns} if len(conns) > 1 else set())
    for old in {r["scope"] for r in (supabase.table("trade_insights").select("scope").eq("user_id", user_id)
                                     .execute().data or [])} - keep:
        supabase.table("trade_insights").delete().eq("user_id", user_id).eq("scope", old).execute()
    return written


def refresh_stale(supabase, conns: list[dict], inputs, now: datetime, progressed: set | None = None) -> int:
    """Work the documents out again for members whose data changed since they were last worked out: a sync or new
    open positions, or (at most every 30 minutes) snapshots or price moves filled in this pass; and once a day.
    Nothing until the insights SQL has been run (the table is checked first, so the worker doesn't read every trade
    each pass for nothing)."""
    try:
        supabase.table("trade_insights").select("user_id").limit(1).execute()
    except Exception:
        return 0
    progressed = progressed or set()
    by_user: dict = {}
    for c in conns:
        by_user.setdefault(c["user_id"], []).append(c)
    written = 0
    for user_id, cs in by_user.items():
        last = min((_when(c.get("insights_at")) for c in cs), default=None, key=lambda x: x or datetime.min.replace(tzinfo=timezone.utc))
        changed = max((_when(c.get(k)) for c in cs for k in ("last_sync_at", "portfolio_at") if c.get(k)), default=None)
        due = last is None or (changed and changed > last) \
            or (user_id in progressed and now - last >= timedelta(minutes=30)) or now - last >= timedelta(hours=24)
        if not due or not any(c.get("status") == "ok" for c in cs):
            continue
        written += compute_for(supabase, user_id, [c for c in cs if c.get("status") != "paused"], inputs, now)
        for c in cs:
            supabase.table("trade_connections").update({"insights_at": now.isoformat()}).eq("id", c["id"]).execute()
    return written
