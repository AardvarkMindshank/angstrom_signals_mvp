"""Trade Log sync (spec v0.5): runs in the 5-minute background worker (run_alerts.py), after its other work.

A connection is synced when it is new (just connected), when its member pressed Refresh, or once a day. Each sync
reads the broker's closed positions with the member's read-only key (from Vault, server only), saves them as round
trips, then works out snapshots for trades that don't have them yet, within a time budget (the rest next pass).
A failing key pauses until the next day instead of retrying every pass; a full history is never re-imported on a
schedule tighter than daily.

Logs carry counts only: never keys, names, symbols, prices or amounts (the repository and its logs are public).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import tradelog
import tradelog_snapshots

DAILY = timedelta(hours=24)
PASS_BUDGET_SECONDS = 90
FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=0&format=json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _when(value) -> datetime | None:
    return tradelog_snapshots._when(value)


def is_due(conn: dict, now: datetime) -> bool:
    if conn.get("status") == "paused":
        return False
    if conn.get("status") == "new" or conn.get("refresh_requested_at"):
        return True
    last = _when(conn.get("last_sync_at"))
    return last is None or now - last >= DAILY


def due_connections(supabase, now: datetime) -> list[dict]:
    rows = supabase.table("trade_connections").select("*").execute().data or []
    return [r for r in rows if is_due(r, now)]


# ---- loading what snapshots need (one read per asset per pass) ----------------------------------------------

class Inputs:
    """Data for snapshots, read on first use and kept for the rest of the pass."""

    def __init__(self, supabase, session):
        self.supabase, self.session = supabase, session
        self._bars, self._record, self._sentiment = {}, {}, {}
        self._fear_greed = self._vix = None

    def bars(self, asset_key: str):
        if asset_key not in self._bars:
            from market_store import frame_from_records

            rows = (self.supabase.table("asset_market").select("prices").eq("asset_key", asset_key)
                    .limit(1).execute().data or [])
            prices = (rows[0] or {}).get("prices") if rows else None
            self._bars[asset_key] = frame_from_records(prices) if prices else None
        return self._bars[asset_key]

    def record(self, asset_key: str) -> dict:
        if asset_key not in self._record:
            rows = (self.supabase.table("readings_daily").select("day,trend,stretch,flow,regime,first_seen_at")
                    .eq("asset_key", asset_key).execute().data or [])
            self._record[asset_key] = {str(r["day"])[:10]: r for r in rows}
        return self._record[asset_key]

    def sentiment(self, subject_key: str, since: str):
        if subject_key not in self._sentiment:
            rows = (self.supabase.table("sentiment_history").select("recorded_at,score")
                    .eq("subject_key", subject_key).gte("recorded_at", since).execute().data or [])
            self._sentiment[subject_key] = [(r["recorded_at"], r["score"]) for r in rows]
        return self._sentiment[subject_key]

    def fear_greed(self):
        if self._fear_greed is None:
            try:
                data = self.session.get(FEAR_GREED_URL, timeout=20).json().get("data") or []
                self._fear_greed = [(datetime.fromtimestamp(int(d["timestamp"]), timezone.utc).date().isoformat(),
                                     float(d["value"])) for d in data]
            except Exception:
                self._fear_greed = []
        return self._fear_greed

    def vix(self):
        if self._vix is None:
            try:
                rows = (self.supabase.table("tides_snapshots").select("body").order("computed_at", desc=True)
                        .limit(1).execute().data or [])
                wave = (((rows[0] or {}).get("body") or {}).get("currents") or {}).get("fear", {}).get("wave") if rows else None
                self._vix = [(d, v) for d, v in (wave or [])]
            except Exception:
                self._vix = []
        return self._vix


def asset_keys_for(supabase, instruments: dict, types: dict) -> dict:
    """(asset class, eToro symbol) → MarketNavi's asset key, for assets MarketNavi follows."""
    out = {}
    coins = {}
    try:
        for r in supabase.table("crypto_universe").select("coin_id,symbol,rank").execute().data or []:
            sym = str(r.get("symbol") or "").upper()
            if sym and (sym not in coins or (r.get("rank") or 10**9) < coins[sym][1]):
                coins[sym] = (r["coin_id"], r.get("rank") or 10**9)
    except Exception:
        coins = {}
    for info in instruments.values():
        symbol = str(info.get("symbolFull") or "").upper()
        cls = tradelog.asset_class_of(types.get(int(info.get("instrumentTypeID") or -1), ""))
        if cls == "crypto" and symbol in coins:
            out[(cls, symbol)] = f"Crypto|{coins[symbol][0]}"
        elif cls in ("stocks", "etfs") and symbol and symbol.replace("-", "").isalnum():
            out[(cls, symbol)] = f"Stock|{symbol}"
    return out


# ---- one connection ------------------------------------------------------------------------------------------

def _update(supabase, conn_id: str, **fields) -> None:
    supabase.table("trade_connections").update(fields).eq("id", conn_id).execute()


BENCHMARKS = {"btc": 100000, "spx": 27}          # eToro's Bitcoin and SPX500 instruments


def _fetch_series(session, keys: dict, now: datetime) -> dict:
    """eToro's daily return and allocation history for the account, and weekly benchmark prices. Each part is
    skipped quietly when eToro doesn't give it (a key without that permission, or the service down)."""
    today = now.date().isoformat()
    out: dict = {}
    try:
        user = str((tradelog.fetch_me(session, keys) or {}).get("username") or "")
    except tradelog.EtoroError:
        user = ""
    if user:
        for kind, fetch in (("daily_gain", tradelog.fetch_daily_gain), ("allocation", tradelog.fetch_allocation)):
            try:
                out[kind] = fetch(session, keys, user, today)
            except tradelog.EtoroError:
                pass
    bench = {}
    for name, iid in BENCHMARKS.items():
        try:
            bench[name] = [[d, c] for d, _o, _h, _l, c in tradelog.fetch_candles(session, keys, iid, "OneWeek", 1000)
                           if c]
        except tradelog.EtoroError:
            pass
    if bench:
        out["benchmarks"] = bench
    return out


def _save_series(supabase, conn: dict, series: dict, now: datetime) -> None:
    """Keep the series (one row per kind). Quietly skipped until the insights SQL is run."""
    for kind, data in series.items():
        if not data:
            continue
        try:
            supabase.table("trade_series").upsert({"connection_id": conn["id"], "user_id": conn["user_id"],
                                                   "kind": kind, "data": data, "read_at": now.isoformat()},
                                                  on_conflict="connection_id,kind").execute()
        except Exception as exc:
            print(f"Trade Log series skipped: {type(exc).__name__}")
            return


def _upsert_trips(supabase, rows: list[dict]) -> None:
    """Save the round trips. Columns added by a later SQL file may not exist yet: drop the newest first ("reward"),
    then all of them, so whatever has been run is still filled."""
    drops = [(), ("reward",), tradelog.NEW_TRIP_FIELDS]
    level = 0
    for start in range(0, len(rows), 200):
        while True:
            part = [{k: v for k, v in r.items() if k not in drops[level]} for r in rows[start:start + 200]]
            try:
                supabase.table("trade_round_trips").upsert(part, on_conflict="connection_id,position_id").execute()
                break
            except Exception:
                if level == len(drops) - 1:
                    raise
                level += 1


def _save_open(supabase, conn: dict, portfolio: dict, rows: list[dict], now: datetime) -> None:
    """Replace this connection's open positions and note its cash. Quietly skipped until the SQL is run."""
    try:
        table = supabase.table("trade_open_positions")
        table.delete().eq("connection_id", conn["id"]).execute()
        rows = [{**r, "user_id": conn["user_id"], "connection_id": conn["id"], "read_at": now.isoformat()}
                for r in rows]
        for start in range(0, len(rows), 200):
            try:
                supabase.table("trade_open_positions").insert(rows[start:start + 200]).execute()
            except Exception:                       # before the insights SQL: without the newer columns
                rows = [{k: v for k, v in r.items() if k not in ("stop_loss", "overnight_fees_usd")} for r in rows]
                supabase.table("trade_open_positions").insert(rows[start:start + 200]).execute()
        _update(supabase, conn["id"], cash_usd=portfolio.get("cash"), open_pnl_usd=portfolio.get("pnl"),
                portfolio_at=now.isoformat())
    except Exception as exc:
        print(f"Trade Log open positions skipped: {type(exc).__name__}")


def sync_connection(supabase, conn: dict, session, inputs: Inputs, deadline: float, now: datetime) -> dict:
    """Import one connection's closed trades and as many missing snapshots as time allows. Counts only."""
    summary = {"trades": 0, "snapshots": 0, "failed": False}
    if conn.get("platform") != "etoro":
        return summary
    keys = supabase.rpc("tradelog_connection_keys", {"p_id": conn["id"]}).execute().data
    if not isinstance(keys, dict) or not keys.get("api_key") or not keys.get("user_key"):
        _update(supabase, conn["id"], status="failing", last_error="The saved key is incomplete. Connect again.",
                last_sync_at=now.isoformat(), refresh_requested_at=None)
        summary["failed"] = True
        return summary
    try:
        # A daily sync reads back a week before the last one; a new connection or a Refresh reads everything.
        last = _when(conn.get("last_sync_at"))
        recent = conn.get("status") == "ok" and last is not None and not conn.get("refresh_requested_at")
        stop = (last - timedelta(days=7)).isoformat()[:10] if recent else None
        positions = tradelog.fetch_closed_positions(session, keys, stop_before=stop, workers=2)
        try:                                               # what is open now (26 Nov 2026)
            portfolio = tradelog.fetch_portfolio(session, keys)
        except tradelog.EtoroError:
            portfolio = None
        ids = {p.get("instrumentId") for p in positions} | {p.get("instrumentID") for p in
                                                           (portfolio or {}).get("positions", [])}
        ids.discard(None)
        instruments = tradelog.fetch_instruments(session, keys, ids) if ids else {}
        types = tradelog.fetch_instrument_types(session, keys) if ids else {}
        series = _fetch_series(session, keys, now)
    except tradelog.EtoroError as exc:
        _update(supabase, conn["id"], status="failing", last_error=str(exc)[:300], last_sync_at=now.isoformat(),
                refresh_requested_at=None)
        summary["failed"] = True
        return summary
    finally:
        keys = None                                          # don't keep the key around longer than needed
    keys_map = asset_keys_for(supabase, instruments, types)
    trips = tradelog.etoro_round_trips(positions, instruments, types, keys_map)
    if portfolio is not None:
        _save_open(supabase, conn, portfolio, tradelog.etoro_open_positions(portfolio["positions"], instruments,
                                                                            types, keys_map), now)
    rows = [{**t, "user_id": conn["user_id"], "connection_id": conn["id"]} for t in trips]
    _upsert_trips(supabase, rows)
    _save_series(supabase, conn, series, now)
    summary["trades"] = len(rows)
    earliest = min((t["opened_at"] for t in trips), default=None)
    _update(supabase, conn["id"], status="ok", last_error="", last_sync_at=now.isoformat(), refresh_requested_at=None,
            history_from=earliest[:10] if earliest else None)
    summary["snapshots"] = fill_snapshots(supabase, conn, inputs, deadline)
    return summary


def _pages(make_query, page: int = 1000) -> list:
    """Every row of a query, a page at a time. make_query() builds a fresh query (with a stable order)."""
    out: list = []
    while True:
        got = make_query().range(len(out), len(out) + page - 1).execute().data or []
        out += got
        if len(got) < page or len(out) >= 200_000:
            return out


def fill_snapshots(supabase, conn: dict, inputs: Inputs, deadline: float) -> int:
    """Snapshots for this connection's trades that have none yet, newest first, until the deadline."""
    # The member's own trades only: copied trades (often thousands of small ones) get no snapshot, which keeps the
    # table and each pass small (26 Nov 2026). Read in pages: Supabase returns at most 1,000 rows per ask, and a
    # capped "done" list had the worker rewriting the same snapshots every pass.
    trips = _pages(lambda: supabase.table("trade_round_trips").select("id,asset_key,asset_class,opened_at,closed_at")
                   .eq("connection_id", conn["id"]).eq("copied", False).order("closed_at", desc=True))
    if not trips:
        return 0
    done = {(r["round_trip_id"], r["moment"]) for r in
            _pages(lambda: supabase.table("trade_snapshots").select("round_trip_id,moment")
                   .eq("user_id", conn["user_id"]).order("round_trip_id").order("moment"))}
    since = (min(_when(t["opened_at"]) for t in trips) - timedelta(days=4)).isoformat()
    made = 0
    for trip in trips:
        for moment in ("entry", "exit"):
            if (trip["id"], moment) in done:
                continue
            if time.monotonic() > deadline:
                return made
            key = trip.get("asset_key")
            crypto = trip.get("asset_class") == "crypto"
            snap = tradelog_snapshots.snapshot(
                trip, moment, bars=inputs.bars(key) if key else None, kind="Crypto" if crypto else "Stock",
                record=inputs.record(key) if key else {},
                asset_sentiment=inputs.sentiment(key, since) if key else None,
                market_sentiment=inputs.sentiment("crypto" if crypto else "stock", since),
                fear_greed=inputs.fear_greed() if crypto else None, vix=None if crypto else inputs.vix())
            supabase.table("trade_snapshots").upsert({
                "round_trip_id": trip["id"], "moment": moment, "user_id": conn["user_id"], **snap,
            }, on_conflict="round_trip_id,moment").execute()
            made += 1
    return made


def fill_moves(supabase, conn: dict, session, deadline: float) -> int:
    """For the member's own trades: how much of the best move each kept and the price 20 trading days after it
    closed, from eToro's daily candles (one ask per asset, the last 1,000 days). Until the deadline; returns the
    number of trades done. Quietly nothing before the insights SQL is run."""
    try:
        todo = _pages(lambda: supabase.table("trade_round_trips")
                      .select("id,instrument_id,direction,opened_at,closed_at,entry_price,exit_price,net_result_usd")
                      .eq("connection_id", conn["id"]).eq("copied", False).eq("moves_checked", False).order("id"))
    except Exception:
        return 0
    if not todo or time.monotonic() > deadline:
        return 0
    keys = supabase.rpc("tradelog_connection_keys", {"p_id": conn["id"]}).execute().data
    if not isinstance(keys, dict) or not keys.get("api_key"):
        return 0
    by_asset: dict[str, list] = {}
    for t in todo:
        by_asset.setdefault(str(t.get("instrument_id") or ""), []).append(t)
    done = 0
    try:
        for iid, trips in by_asset.items():
            if time.monotonic() > deadline:
                break
            try:
                candles = tradelog.fetch_candles(session, keys, int(iid)) if iid.isdigit() else []
            except tradelog.EtoroError:
                candles = []
            for t in trips:
                supabase.table("trade_round_trips").update({**tradelog.trade_moves(t, candles),
                                                            "moves_checked": True}).eq("id", t["id"]).execute()
                done += 1
    finally:
        keys = None
    return done


def run_from_worker(supabase, session=None, budget_seconds: float = PASS_BUDGET_SECONDS) -> str:
    """The worker's step: due connections, then leftover snapshots, all within the budget. Returns counts."""
    import requests

    session = session or requests.Session()
    now, deadline = _now(), time.monotonic() + budget_seconds
    try:
        conns = supabase.table("trade_connections").select("*").execute().data or []
    except Exception as exc:                                  # the tables not added yet
        return f"not set up ({str(exc)[:80]})"
    inputs = Inputs(supabase, session)
    synced = trades = snaps = failed = 0
    progressed: set = set()
    for conn in conns:
        if time.monotonic() > deadline:
            break
        if is_due(conn, now):
            s = sync_connection(supabase, conn, session, inputs, deadline, now)
            synced += 1
            trades += s["trades"]
            snaps += s["snapshots"]
            failed += s["failed"]
        elif conn.get("status") == "ok" and now - (_when(conn.get("last_sync_at")) or now) < timedelta(days=2):
            made = fill_snapshots(supabase, conn, inputs, deadline)      # finishing a recent import's snapshots
            made += fill_moves(supabase, conn, session, deadline)
            snaps += made
            if made:
                progressed.add(conn["user_id"])
    try:
        import tradelog_insights

        tradelog_insights.refresh_stale(supabase, conns, inputs, now, progressed)
    except Exception as exc:                                  # never let the summaries stop the worker
        print(f"Trade Log insights skipped: {type(exc).__name__}: {str(exc)[:120]}")
    return f"{len(conns)} connections, {synced} synced ({failed} failing), {trades} trades, {snaps} new snapshots"
