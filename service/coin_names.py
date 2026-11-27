"""One way to name a coin everywhere in the new app: "Name (TICKER)", e.g. "Solana (SOL)"; just "XRP" when the name is
the ticker. Watchlists keep whatever name the coin was added under ("Solana (SOL)", "Midnight", "maxxing"), so the
name and ticker come from CoinGecko (one request for the whole list, kept for a day), falling back to the saved
name without any bracket when CoinGecko can't be reached."""
from __future__ import annotations

import re
import threading
import time

import requests

_DAY = 24 * 3600
_lock = threading.Lock()
_known: dict[str, tuple[float, str, str]] = {}      # coin id -> (fetched at, name, ticker)
_tried: dict[str, float] = {}                         # coin id -> last failed look-up (not retried for an hour)


def _fetch(ids: list[str]) -> None:
    from data_fetchers import _HEADERS

    for i in range(0, len(ids), 200):
        part = ids[i:i + 200]
        try:
            r = requests.get("https://api.coingecko.com/api/v3/coins/markets",
                             params={"vs_currency": "usd", "ids": ",".join(part), "per_page": 250, "page": 1},
                             headers=_HEADERS, timeout=12)
            rows = r.json() if r.status_code == 200 else []
        except Exception:
            rows = []
        now = time.time()
        with _lock:
            for row in rows if isinstance(rows, list) else []:
                if isinstance(row, dict) and row.get("id"):
                    _known[str(row["id"])] = (now, str(row.get("name") or "").strip(), str(row.get("symbol") or "").strip().upper())
            for cid in part:
                if cid not in _known:
                    _tried[cid] = now


def _bare(saved: str) -> str:
    return re.sub(r"\s*\([^()]*\)\s*$", "", str(saved or "")).strip()


def label(coin_id: str, saved: str = "", name: str = "", ticker: str = "") -> str:
    name = (name or _bare(saved) or coin_id).strip()
    ticker = (ticker or "").strip().upper()
    if not ticker or name.upper() == ticker or name.upper().replace(" ", "") == ticker:
        return name
    return f"{name} ({ticker})"


def labels(watch: dict) -> dict[str, str]:
    """{coin id: "Name (TICKER)"} for a {coin id: saved name} watchlist."""
    now = time.time()
    ids = [str(c) for c in watch]
    with _lock:
        due = [c for c in ids if (c not in _known or now - _known[c][0] > _DAY) and now - _tried.get(c, 0) > 3600]
    if due:
        _fetch(due)
    out = {}
    with _lock:
        for cid, saved in watch.items():
            got = _known.get(str(cid))
            saved = saved if isinstance(saved, str) else ""
            out[cid] = label(str(cid), saved, got[1] if got else "", got[2] if got else _ticker_in(saved))
    return out


def _ticker_in(saved: str) -> str:
    m = re.search(r"\(([A-Za-z0-9.\-]{1,15})\)\s*$", saved or "")
    return m.group(1) if m else ""
