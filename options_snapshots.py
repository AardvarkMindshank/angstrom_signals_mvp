"""
Options max-pain snapshots, kept so the max pain signal has a history (signal_library/signals_options.py).

Nobody publishes past open interest by strike, so we record it ourselves: the background worker calls refresh_due
every pass, and it saves a snapshot when one is due.
- Bitcoin and Ethereum: Deribit's public options book (one request per coin), every 4 hours, each expiry up to
  100 days ahead.
- Equities on a watchlist or a funnel shortlist: Yahoo option chains (one request per expiry), once per US trading
  day after 14:30 UTC (open interest is settled overnight and published before the open), the next 5 expiries
  within 70 days plus the nearest monthly. At most EQUITY_MAX equities, oldest snapshot first, within a time budget,
  so a long list is finished over several passes.

Rows go to options_pain (sql/2026-11-21_options_pain.sql), one per expiry, with the underlying price at the time.
first_seen_at is set by the database, never by this code: replays count a row only from then.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import max_pain

CRYPTO = {"bitcoin": "BTC", "ethereum": "ETH"}
CRYPTO_EVERY_HOURS = 4
CRYPTO_DAYS = 100
EQUITY_AFTER_UTC = (14, 30)
EQUITY_EXPIRIES = 5
EQUITY_DAYS = 70
EQUITY_MAX = 80
BUDGET_SECONDS = 75


def snapshot_rows(asset_key: str, recorded_at: str, book: dict, source: str, spot=None) -> list[dict]:
    """{expiry: {calls, puts, spot}} -> one options_pain row per expiry with a max-pain strike."""
    rows = []
    for expiry, slot in sorted(book.items()):
        calls, puts = slot.get("calls") or {}, slot.get("puts") or {}
        pain = max_pain.pain_strike(calls, puts)
        if pain is None:
            continue
        price = slot.get("spot") or spot
        rows.append({"asset_key": asset_key, "recorded_at": recorded_at, "expiry": expiry,
                     "spot": float(price) if price else None, "max_pain": float(pain),
                     "call_oi": round(sum(calls.values()), 4), "put_oi": round(sum(puts.values()), 4),
                     "strikes": len(set(calls) | set(puts)), "source": source})
    return rows


def crypto_book(symbol: str, now: datetime) -> tuple[dict, str | None]:
    book, error = max_pain._deribit_book(symbol)
    if error:
        return {}, error
    last = (now + timedelta(days=CRYPTO_DAYS)).date().isoformat()
    return {e: s for e, s in book.items() if now.date().isoformat() <= e <= last}, None


def _third_friday(day) -> bool:
    return (day.weekday() == 4 and 15 <= day.day <= 21) or (day.weekday() == 3 and 14 <= day.day <= 20)


def pick_equity_expiries(dates: list[str], now: datetime) -> list[str]:
    from datetime import date

    ahead = [d for d in sorted(dates) if now.date().isoformat() <= d <= (now + timedelta(days=EQUITY_DAYS)).date().isoformat()]
    chosen = ahead[:EQUITY_EXPIRIES]
    monthly = next((d for d in sorted(dates) if d >= now.date().isoformat() and _third_friday(date.fromisoformat(d))), None)
    if monthly and monthly not in chosen:
        chosen.append(monthly)
    return chosen


def equity_book(ticker: str, now: datetime, chain=None) -> tuple[dict, float | None, str | None]:
    """{expiry: {calls, puts}}, the last price, and an error. chain(ticker) -> yfinance.Ticker (tests pass a fake)."""
    try:
        if chain is None:
            import yfinance as yf

            chain = yf.Ticker
        t = chain(ticker)
        dates = [str(d)[:10] for d in (t.options or [])]
    except Exception as exc:
        return {}, None, f"no option dates ({str(exc)[:80]})"
    if not dates:
        return {}, None, "no listed options"
    book = {}
    for expiry in pick_equity_expiries(dates, now):
        try:
            got = t.option_chain(expiry)
        except Exception:
            continue
        calls, puts = max_pain._oi_frame(getattr(got, "calls", None)), max_pain._oi_frame(getattr(got, "puts", None))
        if calls or puts:
            book[expiry] = {"calls": calls, "puts": puts}
    spot = None
    try:
        spot = float(t.fast_info["last_price"])
    except Exception:
        try:
            spot = float(t.history(period="5d")["Close"].dropna().iloc[-1])
        except Exception:
            spot = None
    if not book:
        return {}, spot, "open interest was blank"
    return book, spot, None


def latest_snapshots(supabase, since: datetime) -> dict[str, datetime]:
    rows = (supabase.table("options_pain").select("asset_key, recorded_at").gte("recorded_at", since.isoformat())
            .order("recorded_at", desc=True).limit(10000).execute().data or [])
    out: dict[str, datetime] = {}
    for r in rows:
        when = datetime.fromisoformat(str(r["recorded_at"]).replace("Z", "+00:00"))
        if r["asset_key"] not in out or when > out[r["asset_key"]]:
            out[r["asset_key"]] = when
    return out


def equity_due(last: datetime | None, now: datetime) -> bool:
    if now.weekday() >= 5 or (now.hour, now.minute) < EQUITY_AFTER_UTC:
        return False
    return last is None or last.date() < now.date()


def crypto_due(last: datetime | None, now: datetime) -> bool:
    return last is None or now - last >= timedelta(hours=CRYPTO_EVERY_HOURS) - timedelta(minutes=10)


def save(supabase, rows: list[dict]) -> int:
    if not rows:
        return 0
    supabase.table("options_pain").upsert(rows, on_conflict="asset_key,expiry,recorded_at",
                                          ignore_duplicates=True).execute()
    return len(rows)


def refresh_due(supabase, catalog, now: datetime | None = None, chain=None, crypto=None, log=print) -> dict:
    """catalog: {(kind, id): name} with kind Crypto or Stock (watchlists and funnel shortlists). Returns counts."""
    now = now or datetime.now(timezone.utc)
    started = time.time()
    try:
        last = latest_snapshots(supabase, now - timedelta(days=4))
    except Exception as exc:
        log(f"Options snapshots skipped (run sql/2026-11-21_options_pain.sql): {str(exc)[:120]}")
        return {"saved": 0}
    stamp = now.replace(microsecond=0).isoformat()
    saved, failed = 0, []
    for coin, symbol in CRYPTO.items():
        key = f"Crypto|{coin}"
        if not crypto_due(last.get(key), now):
            continue
        book, error = (crypto or crypto_book)(symbol, now)
        if error:
            failed.append(f"{symbol}: {error}")
            continue
        saved += save(supabase, snapshot_rows(key, stamp, book, "deribit"))
    tickers = sorted({str(i).upper() for k, i in catalog if k == "Stock"})
    due = [t for t in tickers if equity_due(last.get(f"Stock|{t}"), now)]
    due.sort(key=lambda t: (last.get(f"Stock|{t}") is not None, last.get(f"Stock|{t}") or now, t))
    done = 0
    for ticker in due[:EQUITY_MAX]:
        if time.time() - started > BUDGET_SECONDS:
            break
        book, spot, error = equity_book(ticker, now, chain)
        if error:
            failed.append(f"{ticker}: {error}")
            continue
        saved += save(supabase, snapshot_rows(f"Stock|{ticker}", stamp, book, "yahoo", spot))
        done += 1
    if saved or failed:
        log(f"Options snapshots: {saved} rows saved ({done} equities); "
            f"{len(failed)} not taken{': ' + '; '.join(failed[:5]) if failed else ''}")
    return {"saved": saved, "equities": done, "failed": failed, "left": max(0, len(due) - done)}
