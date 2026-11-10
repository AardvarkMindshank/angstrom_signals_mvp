"""
The funnel on the page: the crypto table's "My Watchlist / Dynamic" switch, the stage picker with counts, and the
stage icon column (decision of 10 Nov 2026, docs/research/funnel_brief_2026-11-10.md). Reads the tables of
sql/2026-11-17_funnels.sql; the funnel job writes them. Nothing here touches Streamlit, so it is tested on its own.
"""

from __future__ import annotations

import pandas as pd

import funnel as fn
import funnel_runner as fr

MODES = ("My Watchlist", "Dynamic funnel")
MODE_CODES = {"My Watchlist": "watchlist", "Dynamic funnel": "funnel"}   # saved on the account (names may change)
SHOW_LIMIT = 30                         # assets in the table, largest by market cap (first loads fill shared prices)
CHART_LIMIT = 12                        # assets in "Open … in chart" (the largest by market cap)
PRICE_LIMIT = 40                        # per funnel, beyond its Candidates: assets whose prices the worker keeps fresh


def load_funnels(supabase, user_id) -> list[dict]:
    try:
        return (supabase.table("funnels").select("*").eq("owner_id", user_id).order("created_at")
                .execute().data or [])
    except Exception:                   # tables not installed yet
        return []


def load_coins(supabase, funnel_id) -> dict[str, dict]:
    rows = (supabase.table("funnel_coins").select("coin_id, stages_version, state, status, depth, pending, updated_at")
            .eq("funnel_id", funnel_id).execute().data or [])
    return {r["coin_id"]: r for r in rows}


def load_universe(supabase, market: str = "crypto") -> dict[str, dict]:
    try:
        if market == "equity":
            rows = (supabase.table("equity_universe").select("ticker, name, sector, rank, included, reason, "
                                                            "volume_usd, next_earnings, built_at")
                    .order("rank").execute().data or [])
            return {r["ticker"]: r for r in rows}
        rows = (supabase.table("crypto_universe").select("coin_id, symbol, name, rank, included, reason, pair, "
                                                        "volume_usd, built_at").order("rank").execute().data or [])
    except Exception:
        return {}
    import crypto_universe

    crypto_universe.register([r for r in rows if r.get("included")])
    return {r["coin_id"]: r for r in rows}


def last_runs(supabase, funnel_id, n_stages: int) -> list[dict | None]:
    rows = (supabase.table("funnel_runs").select("stage, cutoff, finished_at, status, checked, error")
            .eq("funnel_id", funnel_id).order("cutoff", desc=True).limit(40).execute().data or [])
    out: list = [None] * n_stages
    for r in rows:
        if 0 <= r["stage"] < n_stages and out[r["stage"]] is None:
            out[r["stage"]] = r
    return out


def states(f: dict, coins: dict[str, dict]) -> dict[str, fn.CoinState]:
    n, version = len(f["stages"]), f.get("stages_version") or 1
    return {c: fn.CoinState.from_dict(r["state"], n) for c, r in coins.items() if r.get("stages_version") == version}


def picks(f: dict, coin_states: dict[str, fn.CoinState], pool_size: int) -> list[tuple[str, str]]:
    """[(key, label)] for the stage picker, narrowest last: each stage reached, then Flagged and Candidates."""
    k = fn.counts(coin_states, len(f["stages"]))
    out = []
    for i, stage in enumerate(f["stages"][:-1]):
        out.append((f"stage:{i}", f"{fn.STAGE_ICONS[min(i, len(fn.STAGE_ICONS) - 1)]} {stage['label']} · {k['reached'][i]}"))
    out.append(("flagged", f"🚩 Flagged · {k['flagged']}"))
    out.append(("candidate", f"✅ Candidates · {k['candidate']}"))
    if k["pending"]:
        out.append(("pending", f"❔ Pending · {k['pending']}"))
    return out


def counts_line(f: dict, coin_states: dict[str, fn.CoinState], pool_size: int) -> str:
    """e.g. 120 → 41 → 18 → 9 → 2 ✅ / 7 🚩: the pool, then the coins holding each stage in a row."""
    k = fn.counts(coin_states, len(f["stages"]))
    steps = [str(pool_size)] + [str(x) for x in k["reached"][:-1]]
    line = " → ".join(steps) + f" → {k['candidate']} ✅ / {k['flagged']} 🚩"
    return line + (f" · {k['pending']} ❔" if k["pending"] else "")


def coins_for(pick: str, coin_states: dict[str, fn.CoinState]) -> list[str]:
    """The coins a picker choice shows, deepest first. stage:i = every coin holding stage i (and those before)."""
    chosen = []
    for c, st in coin_states.items():
        p = fn.place(st)
        if pick.startswith("stage:"):
            ok = p["depth"] > int(pick.split(":")[1])
        elif pick == "pending":
            ok = p["pending"]
        else:
            ok = p["status"] == pick and not p["pending"]
        if ok:
            chosen.append((p["depth"], c))
    return [c for _, c in sorted(chosen, key=lambda x: (-x[0], x[1]))]


def source_line(pair: str | None, market: str = "crypto") -> str | None:
    if not pair:
        return None
    if market == "equity":
        return f"Candles: Yahoo Finance ({pair.split(':', 1)[-1]}), New York trading hours."
    if str(pair).startswith("yahoo:"):
        return f"Candles: Yahoo Finance ({pair[6:]}), as Binance does not list this coin."
    return f"Candles: Binance spot ({pair})."


def earnings_line(day: str | None, now=None) -> str | None:
    """Shares: the next earnings report, when it is within two weeks (prices can jump on a report)."""
    if not day:
        return None
    try:
        left = (pd.Timestamp(day).date() - (now or pd.Timestamp.now(tz="UTC")).date()).days
    except Exception:
        return None
    if left < 0 or left > 14:
        return None
    when = "today" if left == 0 else "tomorrow" if left == 1 else f"in {left} days"
    return f"⚠️ Reports earnings {when} ({day}): prices can jump on a report."


def stage_cell(f: dict, st: fn.CoinState, pair: str | None = None, earnings: str | None = None,
               now=None) -> tuple[str, str, int]:
    """(icon text, hover, sort value) for the Stage column."""
    p = fn.place(st)
    words = fr.hover(f)
    arrow = fn.DIRECTION_ICONS[f["direction"]]
    stages = f["stages"]
    lines = []
    if p["status"] == fn.CANDIDATE:
        lines.append("Candidate: " + words["candidate"])
    elif p["status"] == fn.FLAGGED:
        lines.append("Flagged: " + words["flagged"])
    elif p["depth"]:
        lines.append(f"Holds {p['depth']} of {len(stages)} stages, up to {stages[p['depth'] - 1]['label']}.")
    else:
        lines.append("In the pool: the first stage does not hold yet.")
    if p["pending"]:
        lines.append("❔ Pending: data was missing at the last check, so it cannot move up until it is back.")
    if p["leaving"]:
        lines.append("One No at the last check: it stays until it fails twice in a row.")
    for i, s in enumerate(st.stages):
        if i > p["depth"]:
            lines.append(f"{stages[i]['label']}: not checked (an earlier stage must hold first).")
            break
        when = _when(s.checked_at)
        answer = {"yes": "Yes", "no": "No", "unknown": "Unknown"}.get(s.answer or "", "not checked yet")
        line = f"{stages[i]['label']}: {answer}" + (f" at the {when} close" if when else "")
        if s.line and s.answer in ("no", "unknown"):
            line += f" ({s.line})"
        lines.append(line + ".")
    market = f.get("market") or "crypto"
    if earnings_line(earnings, now):
        lines.append(earnings_line(earnings, now))
    if source_line(pair, market):
        lines.append(source_line(pair, market))
    icon = fn.icon(st)
    return f"{arrow}{icon}", "\n".join(lines), p["depth"] * 2 + (1 if p["status"] == fn.CANDIDATE else 0)


def _when(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        t = pd.Timestamp(iso).tz_convert("UTC")
    except Exception:
        return ""
    return f"{t.day} {t.strftime('%b %H:%M')} UTC"


def health(runs: list[dict | None], f: dict, now=None) -> str | None:
    """A plain warning when a stage's last run failed or is late (more than two of its candles), else None."""
    now = pd.Timestamp.now(tz="UTC") if now is None else now
    for i, r in enumerate(runs):
        stage = f["stages"][i]
        if r is None:
            continue
        if r.get("status") == "failed":
            return f"⚠️ The last {stage['label']} check failed: {(r.get('error') or '')[:120]}"
        step = pd.Timedelta(fr.FREQ.get(stage["timeframe"], "7D")) if stage["timeframe"] != "1W" else pd.Timedelta(days=7)
        if now - pd.Timestamp(r["cutoff"]) > 2 * step + pd.Timedelta(hours=1):
            return f"⚠️ The {stage['label']} stage has not been checked since {_when(r['cutoff'])}."
    return None


def watched_by_funnels(supabase) -> dict[tuple[str, str], str]:
    """{(kind, id): name} for every asset on a funnel's shortlist or beyond (Shortlist, Flagged, Candidate), in any
    account. The background worker keeps their shared prices fresh like watchlist assets (run_alerts.py), so a
    Dynamic funnel table fills in quickly. News sentiment stays with Candidates only (funnel_runner)."""
    funnels = supabase.table("funnels").select("id, market, stages, stages_version").execute().data or []
    out: dict[tuple[str, str], str] = {}
    names = {"crypto": None, "equity": None}
    for f in funnels:
        market = f.get("market") or "crypto"
        shortlist = max(1, len(f.get("stages") or []) - 2)       # holding the shortlist stage and those before it
        rows = (supabase.table("funnel_coins").select("coin_id, depth, stages_version").eq("funnel_id", f["id"])
                .gte("depth", shortlist).execute().data or [])
        rows = [r for r in rows if r.get("stages_version") == (f.get("stages_version") or 1)]
        if not rows:
            continue
        if names[market] is None:
            uni = load_universe(supabase, market)
            names[market] = {k: (v.get("name") or k, v.get("rank") or 10**6) for k, v in uni.items()}
        n = len(f.get("stages") or [])
        # Every Candidate, then the deepest and largest of the rest up to PRICE_LIMIT: a wide shortlist (say 150
        # coins in a falling market) must not turn the 5-minute price refresh into hundreds of lookups.
        rows.sort(key=lambda r: (r["depth"] < n, -r["depth"], names[market].get(r["coin_id"], ("", 10**6))[1]))
        rows = [r for i, r in enumerate(rows) if r["depth"] >= n or i < PRICE_LIMIT + sum(x["depth"] >= n for x in rows)]
        for r in rows:
            kind = "Crypto" if market == "crypto" else "Stock"
            asset = r["coin_id"] if market == "crypto" else str(r["coin_id"]).upper()
            out[(kind, asset)] = names[market].get(r["coin_id"], (r["coin_id"], 0))[0]
    return out
