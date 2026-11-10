"""
Runs every active funnel (funnel.py has the rules; sql/2026-11-17_funnels.sql the tables). Called by the funnel job
(.github/workflows/funnel.yml) once an hour, a few minutes after the hour so the closed candles have reached Binance.

Each pass, for each funnel, stage by stage from the first:
1. the stage is due when its latest candle close (UTC; weeks start Monday) has no run yet. Claiming the run is one
   unique row per (funnel, stage, close), so a retry or a second job never repeats it or its alerts. Missed closes
   are not back-filled: a late pass checks the latest one;
2. only the coins that hold every stage before it are checked (point-in-time at the close, through the same
   reconstruction Prism scans use), and their answers go through funnel.record;
3. after all stages, coins that newly became Candidates are alerted in one message per funnel (latched until they
   leave), and every coin's place is saved.
The coins are the crypto universe's included coins (the crypto-universe job). A failure is recorded for that stage
only; its coins keep their places.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pandas as pd

import funnel as fn

SETTLE = timedelta(minutes=8)
BUDGET_SECONDS = 25 * 60
FREQ = {"15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "12h": "12h", "1D": "1D"}
WORDS = {"15m": "15-minute", "30m": "30-minute", "1h": "1-hour", "4h": "4-hour", "12h": "12-hour", "1D": "daily",
         "1W": "weekly"}
ALERT_TYPE = "funnel"
CHUNK = 40                                      # prism.MAX_ASSETS


NEW_YORK = "America/New_York"
# NYSE full holidays and early closes (13:00). Extend each year; tests/test_funnel_runner.py fails when the coming
# year is missing, so it can't be forgotten.
US_HOLIDAYS = {
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
    "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05", "2027-09-06",
    "2027-11-25", "2027-12-24",
}
US_EARLY_CLOSE = {"2026-11-27", "2026-12-24", "2027-11-26"}
STEP_MINUTES = {"15m": 15, "30m": 30, "1h": 60, "4h": 240, "12h": 720}


def _session_closes(timeframe: str, day) -> list[pd.Timestamp]:
    """The candle closes of one New York trading day (candles counted from the 09:30 open, as the chart builds them)."""
    key = day.strftime("%Y-%m-%d")
    if day.weekday() >= 5 or key in US_HOLIDAYS:
        return []
    open_ = pd.Timestamp(f"{key} 09:30", tz=NEW_YORK)
    close = pd.Timestamp(f"{key} {'13:00' if key in US_EARLY_CLOSE else '16:00'}", tz=NEW_YORK)
    if timeframe in ("1D", "1W"):
        return [close]
    step = pd.Timedelta(minutes=STEP_MINUTES[timeframe])
    ends, t = [], open_ + step
    while t < close:
        ends.append(t)
        t += step
    return ends + [close]


def latest_close(timeframe: str, now: pd.Timestamp, market: str = "crypto") -> pd.Timestamp:
    """The moment the newest closed (and settled) candle closed. Crypto: UTC blocks, weeks from Monday. Shares: New
    York sessions, holidays skipped; a week closes on its last trading day."""
    ready = now - SETTLE
    if market != "equity":
        if timeframe == "1W":
            day = ready.floor("1D")
            return day - pd.Timedelta(days=day.weekday())
        return ready.floor(FREQ[timeframe])
    local = ready.tz_convert(NEW_YORK)
    for back in range(0, 15):
        day = (local - pd.Timedelta(days=back)).date()
        closes = [c for c in _session_closes(timeframe, pd.Timestamp(day)) if c <= local]
        if not closes:
            continue
        if timeframe == "1W":                   # the last trading day of that week must be over
            later = [pd.Timestamp(day) + pd.Timedelta(days=d) for d in range(1, 5 - pd.Timestamp(day).weekday())]
            if any(_session_closes("1D", x) for x in later):
                continue
        return closes[-1].tz_convert("UTC")
    raise ValueError("no New York close in the last two weeks")


def hover(f: dict) -> dict:
    stages = f["stages"]
    names = [WORDS.get(s["timeframe"], s["timeframe"]) for s in stages[:-1]]
    agree = ", ".join(names[:-1]) + f" and {names[-1]}" if len(names) > 1 else names[0]
    entry = WORDS.get(stages[-1]["timeframe"], stages[-1]["timeframe"])
    return {"flagged": fn.FLAGGED_HOVER.format(stages=agree, entry=entry),
            "candidate": fn.CANDIDATE_HOVER.format(entry=entry)}


def candidate_message(f: dict, coins: list[tuple[str, str]]) -> str:
    arrow = fn.DIRECTION_ICONS[f["direction"]]
    names = ", ".join(f"{name} ({symbol})" for symbol, name in coins[:12])
    more = f" and {len(coins) - 12} more" if len(coins) > 12 else ""
    side = "long" if f["direction"] == "long" else "short"
    return (f"Funnel “{f['name']}” {arrow}: new {side} Candidate{'s' if len(coins) > 1 else ''}: {names}{more}. "
            "Every stage holds, including the entry conditions. A coin to look at, not a recommendation.")[:500]


def run_funnel(store, f: dict, universe: dict[str, dict], evaluate, now: pd.Timestamp, log=print) -> dict:
    """One pass of one funnel. universe: coin id -> {symbol, name}. evaluate(set_body, assets, cutoff) -> rows."""
    n = len(f["stages"])
    version = f.get("stages_version") or 1
    saved = store.coins(f["id"])
    states: dict[str, fn.CoinState] = {}
    for coin_id in universe:
        row = saved.get(coin_id)
        same = row is not None and row.get("stages_version") == version
        states[coin_id] = fn.CoinState.from_dict(row["state"] if same else None, n)
    summary = {"stages_run": 0, "failed": 0, "alerted": 0}
    for k, stage in enumerate(f["stages"]):
        market = f.get("market") or "crypto"
        cutoff = latest_close(stage["timeframe"], now, market)
        run_id = store.claim(f["id"], k, cutoff, now)
        if run_id is None:
            continue
        coins = [c for c, st in states.items() if fn.reachable(st, k)]
        try:
            tally = {"yes": 0, "no": 0, "unknown": 0}
            for i in range(0, len(coins), CHUNK):
                part = [(market, c, universe[c].get("name") or c) for c in coins[i:i + CHUNK]]
                for row in evaluate(stage["set_body"], part, cutoff):
                    answer = row.get("answer") if row.get("answer") in tally else fn.UNKNOWN
                    tally[answer] += 1
                    fn.record(states[row["id"]], k, answer, cutoff.isoformat(), row.get("reason"),
                              flicker=f.get("flicker", True))
            store.finish(run_id, {"status": "ok", "finished_at": datetime.now(timezone.utc).isoformat(),
                                  "checked": len(coins), "answers": tally})
            summary["stages_run"] += 1
        except Exception as exc:                 # this stage only; its coins keep their places
            summary["failed"] += 1
            log(f"Funnel {f['id']} stage {k + 1} failed: {str(exc)[:200]}")
            store.finish(run_id, {"status": "failed", "error": str(exc)[:500],
                                  "finished_at": datetime.now(timezone.utc).isoformat()})
    new = [c for c, st in states.items() if fn.alert_due(st)]
    if new and (f.get("alerts") or {}).get("in_app", True):
        store.notify([{"user_id": f["owner_id"], "asset_symbol": "", "asset_name": f["name"], "alert_type": ALERT_TYPE,
                       "message": candidate_message(f, [(universe[c].get("symbol") or universe[c].get("ticker") or c,
                                                         universe[c].get("name") or c)
                                                        for c in new])}])
        summary["alerted"] = len(new)
    store.save_coins(f["id"], version, {c: st for c, st in states.items()
                                        if st.to_dict() != fn.CoinState.new(n).to_dict() or c in saved})
    return summary


def run_all(store, evaluate, now=None, log=print, budget_seconds=BUDGET_SECONDS, clock=time.monotonic) -> dict:
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    started = clock()
    out = {"funnels": 0, "waiting": 0}
    funnels = store.active_funnels()
    universes: dict[str, dict] = {}
    for i, f in enumerate(funnels):
        if clock() - started > budget_seconds:
            out["waiting"] = len(funnels) - i
            break
        market = f.get("market") or "crypto"
        if market not in universes:
            try:
                universes[market] = store.universe(market)
            except Exception as exc:
                log(f"Funnel: the {market} universe could not be read: {str(exc)[:160]}")
                universes[market] = {}
        if not universes[market]:
            log(f"Funnel: the {market} universe is empty (has the {market}-universe job run?)")
            continue
        try:
            out[f["id"]] = run_funnel(store, f, universes[market], evaluate, now, log)
            out["funnels"] += 1
        except Exception as exc:
            log(f"Funnel {f['id']} failed: {str(exc)[:200]}")
    return out


class SupabaseStore:
    """The funnel job's database access (service role)."""

    def __init__(self, supabase):
        self.db = supabase

    def universe(self, market: str = "crypto") -> dict[str, dict]:
        if market == "equity":
            rows = (self.db.table("equity_universe").select("ticker, name, rank, sector, next_earnings")
                    .eq("included", True).order("rank").execute().data or [])
            return {r["ticker"]: {**r, "symbol": r["ticker"]} for r in rows}
        rows = (self.db.table("crypto_universe").select("coin_id, symbol, name, rank, pair").eq("included", True)
                .order("rank").execute().data or [])
        import crypto_universe

        crypto_universe.register(rows)
        return {r["coin_id"]: r for r in rows}

    def active_funnels(self) -> list[dict]:
        return self.db.table("funnels").select("*").eq("paused", False).execute().data or []

    def coins(self, funnel_id) -> dict[str, dict]:
        rows = self.db.table("funnel_coins").select("*").eq("funnel_id", funnel_id).execute().data or []
        return {r["coin_id"]: r for r in rows}

    def claim(self, funnel_id, stage, cutoff, started) -> int | None:
        try:
            rows = (self.db.table("funnel_runs").insert({"funnel_id": funnel_id, "stage": stage,
                                                         "cutoff": cutoff.isoformat(),
                                                         "started_at": started.isoformat()}).execute().data or [])
        except Exception as exc:
            if "duplicate" in str(exc).lower() or "23505" in str(exc):
                return None
            raise
        return rows[0]["id"] if rows else None

    def finish(self, run_id, fields: dict) -> None:
        self.db.table("funnel_runs").update(fields).eq("id", run_id).execute()

    def notify(self, rows: list[dict]) -> None:
        if rows:
            self.db.table("user_notifications").insert(rows).execute()

    def save_coins(self, funnel_id, version, states: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for coin_id, st in states.items():
            p = fn.place(st)
            rows.append({"funnel_id": funnel_id, "coin_id": coin_id, "stages_version": version,
                         "state": st.to_dict(), "status": p["status"], "depth": p["depth"],
                         "pending": p["pending"], "updated_at": now})
        for i in range(0, len(rows), 200):
            self.db.table("funnel_coins").upsert(rows[i:i + 200]).execute()


def default_evaluate(supabase):
    import prism
    from signal_library.replay_display import display_run

    def evaluate(doc, assets, cutoff):
        run = display_run(supabase, max_steps=prism.steps_needed(doc), shortcut=True)
        return prism.run_now(doc, assets, live_context=None, replay=(run, cutoff))
    return evaluate


def main() -> int:
    import os

    from supabase import create_client

    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    try:
        print(run_all(SupabaseStore(supabase), default_evaluate(supabase)))
    except Exception as exc:
        if "PGRST205" in str(exc) or "does not exist" in str(exc):
            print("Funnel tables not installed yet (sql/2026-11-17_funnels.sql).")
            return 0
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
