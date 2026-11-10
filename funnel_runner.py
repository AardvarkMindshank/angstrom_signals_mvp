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


def latest_close(timeframe: str, now: pd.Timestamp) -> pd.Timestamp:
    """The start of the newest closed-and-settled candle's successor, i.e. the moment the last candle closed."""
    ready = now - SETTLE
    if timeframe == "1W":
        day = ready.floor("1D")
        return day - pd.Timedelta(days=day.weekday())
    return ready.floor(FREQ[timeframe])


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
        cutoff = latest_close(stage["timeframe"], now)
        run_id = store.claim(f["id"], k, cutoff, now)
        if run_id is None:
            continue
        coins = [c for c, st in states.items() if fn.reachable(st, k)]
        try:
            tally = {"yes": 0, "no": 0, "unknown": 0}
            for i in range(0, len(coins), CHUNK):
                part = [("crypto", c, universe[c].get("name") or c) for c in coins[i:i + CHUNK]]
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
                       "message": candidate_message(f, [(universe[c].get("symbol") or c, universe[c].get("name") or c)
                                                        for c in new])}])
        summary["alerted"] = len(new)
    store.save_coins(f["id"], version, {c: st for c, st in states.items()
                                        if st.to_dict() != fn.CoinState.new(n).to_dict() or c in saved})
    return summary


def run_all(store, evaluate, now=None, log=print, budget_seconds=BUDGET_SECONDS, clock=time.monotonic) -> dict:
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    started = clock()
    universe = store.universe()
    out = {"funnels": 0, "waiting": 0}
    if not universe:
        log("Funnel: the crypto universe is empty (has the crypto-universe job run?)")
        return out
    funnels = store.active_funnels()
    for i, f in enumerate(funnels):
        if clock() - started > budget_seconds:
            out["waiting"] = len(funnels) - i
            break
        try:
            out[f["id"]] = run_funnel(store, f, universe, evaluate, now, log)
            out["funnels"] += 1
        except Exception as exc:
            log(f"Funnel {f['id']} failed: {str(exc)[:200]}")
    return out


class SupabaseStore:
    """The funnel job's database access (service role)."""

    def __init__(self, supabase):
        self.db = supabase

    def universe(self) -> dict[str, dict]:
        rows = (self.db.table("crypto_universe").select("coin_id, symbol, name, rank").eq("included", True)
                .order("rank").execute().data or [])
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
