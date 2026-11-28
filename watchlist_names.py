"""Keeps every member's crypto watchlist names in the one form the apps store them in, "Name (TICKER)"
(crypto_universe.coin_label): names saved before the rule, under an older rule ("Dogecoin", "Dot"), or of a coin since
renamed. The search list (crypto_universe table) gives the name and ticker of almost every coin, so this costs a
couple of database reads; a coin outside it is looked up on CoinGecko once, and never again once its name is right.
Run hourly by the worker (run_alerts.py); changes a row only when a name is wrong. Logs counts only."""
from __future__ import annotations

import re

import requests

LOOKUPS_PER_RUN = 10
_HAS_TICKER = re.compile(r"\(([^()]+)\)\s*$")


def _coingecko(coin_id: str) -> tuple[str, str] | None:
    from data_fetchers import _HEADERS

    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/coins/{coin_id}",
                         params={"localization": "false", "tickers": "false", "market_data": "false",
                                 "community_data": "false", "developer_data": "false"}, headers=_HEADERS, timeout=10)
        row = r.json() if r.status_code == 200 else {}
    except Exception:
        return None
    return (str(row.get("name") or ""), str(row.get("symbol") or "")) if isinstance(row, dict) and row.get("symbol") else None


def fixed(watch: dict, known: dict, lookup) -> dict:
    """The watchlist with each name in the stored form. known: {coin id: (name, ticker)}; lookup(id) -> (name,
    ticker) or None for a coin outside it whose saved name has no ticker yet (called at most LOOKUPS_PER_RUN times)."""
    from crypto_universe import coin_label

    out = {}
    for cid, saved in watch.items():
        saved = saved if isinstance(saved, str) else str(cid)
        got = known.get(cid)
        if got is None and not _HAS_TICKER.search(saved) and saved != saved.upper():
            got = lookup(cid)
            if got:
                known[cid] = got
        out[cid] = coin_label(*got) if got else saved
    return out


def tidy(supabase) -> None:
    try:
        uni = supabase.table("crypto_universe").select("coin_id, symbol, name").execute().data or []
        prefs = supabase.table("user_preferences").select("user_id, crypto_watchlist").execute().data or []
    except Exception as exc:
        print(f"Watchlist names skipped: {str(exc)[:120]}")
        return
    known = {r["coin_id"]: (r.get("name") or "", r.get("symbol") or "") for r in uni if r.get("coin_id") and r.get("symbol")}
    budget = [LOOKUPS_PER_RUN]

    def lookup(cid):
        if budget[0] <= 0:
            return None
        budget[0] -= 1
        return _coingecko(cid)

    changed = 0
    for row in prefs:
        watch = row.get("crypto_watchlist")
        if not isinstance(watch, dict) or not watch:
            continue
        better = fixed(watch, known, lookup)
        if better != watch:
            try:
                supabase.table("user_preferences").update({"crypto_watchlist": better}).eq("user_id", row["user_id"]).execute()
                changed += 1
            except Exception:
                pass
    if changed:
        print(f"Watchlist names: {changed} watchlists tidied")
