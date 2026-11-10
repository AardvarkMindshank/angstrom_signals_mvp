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
BUDGET_SECONDS = 35 * 60
STALE_CLAIM = timedelta(minutes=60)
MAX_SENTIMENT = 10                  # news-sentiment runs per funnel pass (each one is a paid AI call)
FREQ = {"15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "12h": "12h", "1D": "1D"}
WORDS = {"15m": "15-minute", "30m": "30-minute", "1h": "1-hour", "4h": "4-hour", "12h": "12-hour", "1D": "daily",
         "1W": "weekly"}
ALERT_TYPE = "funnel"
OLD_NAMES = {("crypto", "long"): ("Trend longs ▲", "Trend crypto longs ▲"),
             ("crypto", "short"): ("Trend shorts ▼", "Trend crypto shorts ▼"),
             ("equity", "long"): ("Trend share longs ▲", "Trend equity longs ▲"),
             ("equity", "short"): ("Trend share shorts ▼", "Trend equity shorts ▼")}
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
    """The moment the newest closed (and settled) candle closed. Crypto: UTC blocks, weeks from Monday. Equities: New
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
    label = f["name"] if f["name"].rstrip().endswith(arrow) else f"{f['name']} {arrow}"
    return (f"Funnel “{label}”: new {side} Candidate{'s' if len(coins) > 1 else ''}: {names}{more}. "
            "Every stage holds, including the entry conditions. A coin to look at, not a recommendation.")[:500]


def run_funnel(store, f: dict, universe: dict[str, dict], evaluate, now: pd.Timestamp, log=print,
               out_of_time=lambda: False) -> dict:
    """One pass of one funnel. universe: coin id -> {symbol, name}. evaluate(set_body, assets, cutoff) -> rows.
    Places are saved after every stage, and no new stage starts once out_of_time() says so (the next pass picks up
    the stages left, at the same close)."""
    n = len(f["stages"])
    version = f.get("stages_version") or 1
    saved = store.coins(f["id"])
    states: dict[str, fn.CoinState] = {}
    for coin_id in universe:
        row = saved.get(coin_id)
        same = row is not None and row.get("stages_version") == version
        states[coin_id] = fn.CoinState.from_dict(row["state"] if same else None, n)
        if states[coin_id].left_pool:                       # back in the pool: start again
            states[coin_id] = fn.CoinState.new(n)
    # Assets that left the pool (the daily universe dropped them): kept as "left the pool", back to the start, never
    # alerted and never counted as failing a stage. One that returns starts again from the pool.
    gone = {}
    for coin_id, row in saved.items():
        if coin_id not in universe and row.get("stages_version") == version and not (row.get("state") or {}).get("left_pool"):
            gone[coin_id] = fn.CoinState(stages=fn.CoinState.new(n).stages, left_pool=True)
    if gone:
        store.save_coins(f["id"], version, gone)
        log(f"Funnel {f['name']}: {len(gone)} left the pool.")
    for coin_id, st in states.items():
        st.left_pool = False
    # A new or restarted version starts silently: its first pass sets every asset's place (and latches the Candidates
    # it finds) without a flood of "new Candidate" alerts (reviews of 10 Nov; ask "alert on first matches" to opt in).
    first_pass = not any(r.get("stages_version") == version for r in saved.values())
    summary = {"stages_run": 0, "failed": 0, "alerted": 0}
    keep = lambda: {c: st for c, st in states.items() if st.to_dict() != fn.CoinState.new(n).to_dict() or c in saved}
    for k, stage in enumerate(f["stages"]):
        if out_of_time():
            log(f"Funnel {f['name']}: out of time; stages from {k + 1} wait for the next pass.")
            summary["waiting"] = True
            break
        market = f.get("market") or "crypto"
        cutoff = latest_close(stage["timeframe"], now, market)
        coins = [c for c, st in states.items() if fn.reachable(st, k)]
        if not coins:                             # nothing reaches this stage yet: leave the close unclaimed, so
            continue                              # coins promoted later (at this close) are still checked
        run_id = store.claim(f["id"], k, cutoff, now)
        if run_id is None:
            continue
        began = time.monotonic()
        try:
            tally = {"yes": 0, "no": 0, "unknown": 0}
            for i in range(0, len(coins), CHUNK):
                part = [(market, c, universe[c].get("name") or c) for c in coins[i:i + CHUNK]]
                log(f"Funnel {f['name']} · stage {k + 1} ({stage['timeframe']}, close {cutoff:%d %b %H:%M} UTC): "
                    f"{i}/{len(coins)} checked, {time.monotonic() - began:.0f}s")
                for row in shared_evaluate(store, evaluate, stage["set_body"], part, cutoff, summary):
                    answer = row.get("answer") if row.get("answer") in tally else fn.UNKNOWN
                    tally[answer] += 1
                    fn.record(states[row["id"]], k, answer, cutoff.isoformat(), row.get("reason"),
                              flicker=f.get("flicker", True))
            store.finish(run_id, {"status": "ok", "finished_at": datetime.now(timezone.utc).isoformat(),
                                  "checked": len(coins), "answers": tally})
            store.save_coins(f["id"], version, keep())
            log(f"Funnel {f['name']} · stage {k + 1}: {len(coins)} checked in {time.monotonic() - began:.0f}s, {tally}")
            summary["stages_run"] += 1
        except Exception as exc:                 # this stage only; its coins keep their places
            summary["failed"] += 1
            log(f"Funnel {f['id']} stage {k + 1} failed: {str(exc)[:200]}")
            store.finish(run_id, {"status": "failed", "error": str(exc)[:500],
                                  "finished_at": datetime.now(timezone.utc).isoformat()})
    new = [c for c, st in states.items() if fn.alert_due(st)]
    if first_pass and not (f.get("alerts") or {}).get("first_matches"):
        summary["bootstrap"] = len(new)
        log(f"Funnel {f['name']}: first pass of this version; {len(new)} Candidates set without alerts.")
        new = []
    if new and (f.get("alerts") or {}).get("in_app", True):
        store.notify([{"user_id": f["owner_id"], "asset_symbol": f"funnel:{f['id']}", "asset_name": f["name"],
                       "alert_type": ALERT_TYPE,
                       "message": candidate_message(f, [(universe[c].get("symbol") or universe[c].get("ticker") or c,
                                                         universe[c].get("name") or c)
                                                        for c in new])}])
        summary["alerted"] = len(new)
    # News sentiment only for Candidates: new ones first, then the others still Candidates (refreshed only when their
    # reading is over 12 hours old). A coin that leaves the Candidates is no longer refreshed by the funnel.
    current = new + sorted(c for c, st in states.items()
                           if c not in new and fn.place(st)["status"] == fn.CANDIDATE and not fn.place(st)["pending"])
    if current and hasattr(store, "refresh_sentiment"):
        market = f.get("market") or "crypto"
        try:
            summary["sentiment"] = store.refresh_sentiment(
                market, [(c, universe[c].get("name") or c) for c in current[:MAX_SENTIMENT]], log)
        except Exception as exc:
            log(f"Funnel {f['name']}: sentiment for new Candidates failed: {str(exc)[:160]}")
    store.save_coins(f["id"], version, keep())                      # the alert latches
    return summary


def _code_id() -> str:
    try:
        from signal_library import certification

        return certification.code_hash()[:12]
    except Exception:
        return "uncertified"


def shared_evaluate(store, evaluate, doc: dict, assets: list[tuple], cutoff, summary: dict | None = None) -> list[dict]:
    """Answers for these assets at this close (docs/design/funnels_v2_spec.md, part 1): stored ones are read, the rest
    worked out and stored when finished. A failed check ("Not evaluated") is returned as Unknown and not stored, so a
    later funnel or pass at the same close tries again. Without a shared store (tests, or the table not installed yet)
    everything is worked out."""
    if not hasattr(store, "get_answers"):
        return evaluate(doc, assets, cutoff)
    import what_followed

    lh, code = what_followed.logic_hash(doc), _code_id()
    keys = {f"{kind}:{asset_id}": (kind, asset_id, name) for kind, asset_id, name in assets}
    try:
        stored = store.get_answers(lh, code, list(keys), cutoff)
    except Exception:
        stored = {}
    rows = [{"id": keys[k][1], "answer": a["answer"], "reason": a.get("reason"), "shared": True}
            for k, a in stored.items() if k in keys]
    missing = [keys[k] for k in keys if k not in stored]
    fresh = evaluate(doc, missing, cutoff) if missing else []
    rows += fresh
    key_of = {asset_id: f"{kind}:{asset_id}" for kind, asset_id, _ in missing}
    keep = [{"logic_hash": lh, "code_id": code, "asset_key": key_of[r["id"]], "cutoff": cutoff.isoformat(),
             "answer": r["answer"], "reason": (r.get("reason") or "")[:500] or None}
            for r in fresh if r.get("id") in key_of and r.get("answer") in ("yes", "no", "unknown")
            and not str(r.get("reason") or "").startswith("Not evaluated")]
    if keep:
        try:
            store.put_answers(keep)
        except Exception:
            pass
    if summary is not None:
        summary["shared"] = summary.get("shared", 0) + len(stored)
    return rows


def pool_members(universe: dict[str, dict], pool: dict | None, watchlist: set[str] | None = None) -> dict[str, dict]:
    """The funnel's own pool (spec: pools are versioned with the funnel): the eligible universe narrowed to the top N
    by market cap, a minimum daily volume, or the owner's watchlist only. {} keeps the whole universe."""
    pool = pool or {}
    out = dict(universe)
    if pool.get("watchlist_only"):
        wanted = {str(w).lower() for w in (watchlist or set())}
        out = {k: v for k, v in out.items() if str(k).lower() in wanted}
    if pool.get("min_volume") is not None:
        floor = float(pool["min_volume"])
        out = {k: v for k, v in out.items() if float(v.get("volume_usd") or 0) >= floor}
    if pool.get("top"):
        ranked = sorted(out.items(), key=lambda kv: kv[1].get("rank") or 10**6)[: int(pool["top"])]
        out = dict(ranked)
    return out


def fair_order(funnels: list[dict]) -> list[dict]:
    """Accounts take turns (spec part 3): each account's first funnel, then each one's second, and so on, so one
    account with many funnels cannot fill the hour. Within an account, funnels sharing their first stage's Set with
    other accounts come first (their answers serve more people)."""
    import what_followed

    use: dict[str, int] = {}
    for f in funnels:
        if f.get("stages"):
            h = what_followed.logic_hash(f["stages"][0].get("set_body") or {})
            use[h] = use.get(h, 0) + 1
    by_owner: dict[str, list[dict]] = {}
    for f in funnels:
        by_owner.setdefault(str(f.get("owner_id")), []).append(f)
    for owner, mine in by_owner.items():
        mine.sort(key=lambda f: -use.get(what_followed.logic_hash((f.get("stages") or [{}])[0].get("set_body") or {}), 0))
    out = []
    for turn in range(max((len(v) for v in by_owner.values()), default=0)):
        out += [mine[turn] for mine in by_owner.values() if turn < len(mine)]
    return out


def run_all(store, evaluate, now=None, log=print, budget_seconds=BUDGET_SECONDS, clock=time.monotonic) -> dict:
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    started = clock()
    out = {"funnels": 0, "waiting": 0}
    if hasattr(store, "rename_old_names"):
        try:
            store.rename_old_names()
        except Exception as exc:
            log(f"Renaming ready-made funnels failed: {str(exc)[:160]}")
    funnels = fair_order(store.active_funnels())
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
        members = universes[market]
        if f.get("pool"):
            watch = None
            if (f.get("pool") or {}).get("watchlist_only") and hasattr(store, "watchlist"):
                try:
                    watch = store.watchlist(f["owner_id"], market)
                except Exception:
                    watch = set()
            members = pool_members(members, f.get("pool"), watch)
        try:
            out[f["id"]] = run_funnel(store, f, members, evaluate, now, log,
                                      out_of_time=lambda: clock() - started > budget_seconds)
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
            rows = (self.db.table("equity_universe").select("ticker, name, rank, sector, next_earnings, volume_usd")
                    .eq("included", True).order("rank").execute().data or [])
            return {r["ticker"]: {**r, "symbol": r["ticker"]} for r in rows}
        rows = (self.db.table("crypto_universe").select("coin_id, symbol, name, rank, pair, volume_usd")
                .eq("included", True)
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
                return self._take_over(funnel_id, stage, cutoff, started)
            raise
        return rows[0]["id"] if rows else None

    def _take_over(self, funnel_id, stage, cutoff, started) -> int | None:
        """A claim for this close already exists. Run it again only if it failed, or if it has been 'running' for
        longer than STALE_CLAIM (the job that claimed it was stopped). The update is conditional on the row being
        unchanged, so two jobs never both take it."""
        rows = (self.db.table("funnel_runs").select("id, status, started_at").eq("funnel_id", funnel_id)
                .eq("stage", stage).eq("cutoff", cutoff.isoformat()).execute().data or [])
        if not rows:
            return None
        r = rows[0]
        stale = r["status"] == "running" and pd.Timestamp(r["started_at"]) < started - STALE_CLAIM
        if r["status"] != "failed" and not stale:
            return None
        got = (self.db.table("funnel_runs").update({"status": "running", "started_at": started.isoformat(),
                                                     "error": None, "finished_at": None})
               .eq("id", r["id"]).eq("started_at", r["started_at"]).execute().data or [])
        return r["id"] if got else None

    def finish(self, run_id, fields: dict) -> None:
        self.db.table("funnel_runs").update(fields).eq("id", run_id).execute()

    def refresh_sentiment(self, market: str, items: list[tuple[str, str]], log=print) -> int:
        """News sentiment for new Candidates when their shared reading is missing or older than 12 hours (the
        usual refresh window); the prices row is created first for an asset nobody watches yet. Returns how many
        were refreshed."""
        import shared_refresh as sr
        from market_store import asset_market_key, load_market_columns, row_timestamp, sentiment_refresh_due
        from sentiment import sentiment_ready

        if not sentiment_ready():
            return 0
        kind = "Crypto" if market == "crypto" else "Stock"
        done = 0
        for asset_id, name in items:
            key = asset_market_key(kind, asset_id)
            try:
                row = load_market_columns(self.db, [key], "sentiment_report, sentiment_updated_at").get(key)
                if row is None:
                    sr.ensure_new_asset(self.db, kind, asset_id, name, 400)     # prices and the first reading
                    done += 1
                    continue
                if not sentiment_refresh_due(row_timestamp(row, "sentiment_updated_at")):
                    continue
                sr._save_asset_sentiment(self.db, kind, asset_id, name, previous=sr._previous_report(row))
                done += 1
            except Exception as exc:
                log(f"Sentiment for {name} failed: {str(exc)[:160]}")
        return done

    def rename_old_names(self) -> None:
        """The ready-made funnels were first named "Trend longs ▲" (crypto) and "Trend share longs ▲" (equities); since
        10 Nov they say "crypto" and "equity" (one word everywhere). Funnels still carrying an old name, and their
        notes, take the new one."""
        for (market, direction), (old, new) in OLD_NAMES.items():
            rows = (self.db.table("funnels").select("id").eq("name", old).eq("market", market)
                    .eq("direction", direction).execute().data or [])
            for r in rows:
                self.db.table("funnels").update({"name": new}).eq("id", r["id"]).execute()
            notes = (self.db.table("user_notifications").select("id, message").eq("alert_type", ALERT_TYPE)
                     .eq("asset_name", old).execute().data or [])
            for n in notes:
                self.db.table("user_notifications").update({
                    "asset_name": new, "message": str(n.get("message") or "").replace(f"“{old}”", f"“{new}”")
                }).eq("id", n["id"]).execute()

    def watchlist(self, owner_id: str, market: str) -> set[str]:
        rows = (self.db.table("user_preferences").select("crypto_watchlist, stock_watchlist").eq("user_id", owner_id)
                .execute().data or [])
        if not rows:
            return set()
        lists = rows[0].get("crypto_watchlist" if market == "crypto" else "stock_watchlist") or {}
        return {str(k) for k in (lists.keys() if isinstance(lists, dict) else lists)}

    def get_answers(self, logic_hash: str, code_id: str, asset_keys: list[str], cutoff) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for i in range(0, len(asset_keys), 150):
            rows = (self.db.table("set_answers").select("asset_key, answer, reason").eq("logic_hash", logic_hash)
                    .eq("code_id", code_id).eq("cutoff", cutoff.isoformat()).in_("asset_key", asset_keys[i:i + 150])
                    .execute().data or [])
            out.update({r["asset_key"]: r for r in rows})
        return out

    def put_answers(self, rows: list[dict]) -> None:
        for i in range(0, len(rows), 200):
            self.db.table("set_answers").upsert(rows[i:i + 200], on_conflict="logic_hash,code_id,asset_key,cutoff",
                                                ignore_duplicates=True).execute()

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
        prefetch(doc, assets)
        run = display_run(supabase, max_steps=prism.steps_needed(doc), shortcut=True, candles=short_candles)
        return prism.run_now(doc, assets, live_context=None, replay=(run, cutoff))
    return evaluate


# How much history a funnel check loads per timeframe: enough for the longest average in the provided Sets (EMA 50
# settles in ~150 candles) plus the chart's 260 warm-up candles, instead of the longest range the chart offers.
# Loading a year of hourly candles per coin made the 1-hour stage take ~9 s a coin (10 Nov 2026).
FUNNEL_RANGE = {"15m": "7D", "30m": "1M", "1h": "1M", "4h": "3M", "12h": "1Y", "1D": "1Y", "1W": "All"}


def short_candles(kind: str, asset_id: str, timeframe: str):
    from signal_library.replay_display import live_candles

    return live_candles(kind, asset_id, timeframe, FUNNEL_RANGE.get(timeframe))


def prefetch(doc: dict, assets, workers: int = 8) -> None:
    """Load the candles every member needs for these assets at once (network-bound), into chart_data's cache, so the
    reconstruction that follows reads them from memory instead of one asset at a time."""
    from concurrent.futures import ThreadPoolExecutor

    timeframes = {m["ref"]["timeframe"] for m in doc.get("standalone") or []}
    for g in doc.get("groups") or []:
        timeframes |= {m["ref"]["timeframe"] for m in (g.get("snapshot") or {}).get("members") or []}
    jobs = [(a[0], a[1], tf) for a in assets for tf in timeframes]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda j: _quiet(short_candles, *j), jobs))


def _quiet(fn_, *args):
    try:
        return fn_(*args)
    except Exception:
        return None


def main() -> int:
    import os

    from supabase import create_client

    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    try:
        print(run_all(SupabaseStore(supabase), default_evaluate(supabase), log=lambda m: print(m, flush=True)))
    except Exception as exc:
        if "PGRST205" in str(exc) or "does not exist" in str(exc):
            print("Funnel tables not installed yet (sql/2026-11-17_funnels.sql).")
            return 0
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
