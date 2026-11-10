"""
Run "What followed" on the saved daily prices (reports branch, data/prices), before the protected hold-out.

The provided Sets (results go into data/what_followed.json by hand, after checking):
  python what_followed_run.py answers <prices> <out> --shard i/n [--sets k1,k2] [--limit N]
      the daily Yes / No / Unknown of each Set on each asset (out/answers/<set>/<asset>.json)
  python what_followed_run.py study <prices> <out>
      outcomes, comparable days and the tests (out/what_followed.json), plus a plain summary on stdout

People's own Sets, queued by "Study this Set" (table set_studies; workflow set-studies.yml):
  python what_followed_run.py pick <prices> <out>       queued rows -> out/queue.json, marked running
  python what_followed_run.py answers <prices> <out> --queue out/queue.json --shard i/n
  python what_followed_run.py finish <prices> <out>     one study per Set, written back to set_studies
pick and finish need SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import what_followed as wf  # noqa: E402

START = "2014-09-17"           # the first day Yahoo has Bitcoin: every asset is studied over the same years
CUT = pd.Timestamp("2024-10-29")
LIBRARY = ["demo:pullback", "demo:rally", "demo:alignment", "demo:breakout", "demo:squeeze", "demo:range_low",
           "demo:near_support", "demo:overextended", "demo:btc_filter"]
PICK = 3                       # Sets per run
STUCK_HOURS = 6                # a "running" row older than this is picked again


def symbols(prices: str) -> list[str]:
    """Coins and shares; not the S&P 500 index (_GSPC), which is saved as the market benchmark, not an asset."""
    return sorted(p.name[:-7] for p in Path(prices).glob("*.csv.gz") if not p.name.startswith("_"))


def kind_of(symbol: str) -> str:
    return "crypto" if symbol.endswith("-USD") else "equity"


def raw(prices: str, symbol: str) -> pd.DataFrame:
    d = pd.read_csv(f"{prices}/{symbol}.csv.gz", parse_dates=["date"])
    d = d[d["date"] <= CUT]                         # nothing from the hold-out is kept past this line
    d = d.set_index(pd.DatetimeIndex(d["date"]).tz_localize("UTC"))[["open", "high", "low", "close", "volume"]]
    return d[~d.index.duplicated(keep="last")].sort_index()


def saved_symbol(kind: str, asset_id: str) -> str | None:
    """The saved price file for an asset a Set is pinned to (such as Bitcoin for a market filter)."""
    if kind != "crypto":
        return str(asset_id).upper()
    sys.path.insert(0, str(Path(__file__).resolve().parent / "video"))
    from saved_prices import CRYPTO

    if asset_id in CRYPTO:
        return CRYPTO[asset_id]
    try:
        import data_fetchers

        coin = data_fetchers.resolve_crypto_id(asset_id)
        return data_fetchers.YAHOO_TICKER_BY_ID.get(coin) or data_fetchers.YF_BY_COINGECKO_ID.get(coin)
    except Exception:
        return None


def _docs(args) -> dict:
    """key -> (doc, name, type): the queued Sets, or the provided library."""
    if getattr(args, "queue", ""):
        queue = json.loads(Path(args.queue).read_text())
        return {k: (v["body"], v["name"], "directional") for k, v in queue.items()}
    import prism

    docs = prism.demo_sets()
    keys = args.sets.split(",") if getattr(args, "sets", "") else LIBRARY
    return {k: (docs[k], docs[k]["name"], wf.set_type(k)) for k in keys}


def _folder(out: str, key: str) -> Path:
    return Path(out) / "answers" / key.replace(":", "_")


def answers_step(args) -> int:
    import set_history as sh
    import study_history
    from scoring import calculate_indicators

    docs = {k: v for k, v in _docs(args).items() if v[2] != "filter"}
    saved = study_history.SavedHistory(Path(args.prices).parent)        # derivatives/ beside prices/
    i, n = (int(x) for x in args.shard.split("/"))
    mine = [s for j, s in enumerate(symbols(args.prices)) if j % n == i]
    if args.limit:
        mine = mine[: args.limit]
    subject_frames: dict = {}
    for key, (doc, _, _) in docs.items():
        for kind, asset_id in sh.subjects_of(doc):
            symbol = saved_symbol(kind, asset_id)
            if symbol and (kind, asset_id) not in subject_frames and Path(args.prices, f"{symbol}.csv.gz").exists():
                subject_frames[(kind, asset_id)] = calculate_indicators(raw(args.prices, symbol))
    for symbol in mine:
        t0 = time.time()
        frame = calculate_indicators(raw(args.prices, symbol))
        for key, (doc, _, _) in docs.items():
            out = _folder(args.out, key) / f"{symbol}.json"
            if out.exists():
                continue
            t1 = time.time()
            days = sh.daily_answers(doc, frame, kind_of(symbol), symbol, start=START, subjects=subject_frames,
                                    history=saved)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({"set": key, "hash": wf.logic_hash(doc), "symbol": symbol,
                                       "spans": sh.spans(days)}))
            print(f"{symbol} {key}: {len(days)} days in {time.time() - t1:.0f}s", flush=True)
        print(f"{symbol} done in {time.time() - t0:.0f}s", flush=True)
    return 0


def _answers_series(spans: list) -> pd.Series:
    parts = [pd.Series(a, index=pd.date_range(f, l, freq="D")) for f, l, a in spans]
    return pd.concat(parts) if parts else pd.Series(dtype=object)


def episode_rows(prices: str, out: str, key: str, tables: dict, backdrop: dict | None = None,
                 measure: str = "first") -> pd.DataFrame:
    """Every episode of one Set across the assets, with its outcomes and comparable days. backdrop (if given) is
    filled with each asset's differences on its No days, for the luck line."""
    folder = _folder(out, key)
    parts = []
    for f in sorted(folder.glob("*.json")) if folder.exists() else []:
        if f.name.startswith("_"):
            continue
        rec = json.loads(f.read_text())
        symbol = rec["symbol"]
        if symbol not in tables:
            t = wf.outcomes(raw(prices, symbol))
            t.index = t.index.tz_localize(None).normalize()
            tables[symbol] = t
        answers = _answers_series(rec["spans"])
        answers.index = answers.index.normalize()
        rows = wf.differences(answers, tables[symbol])
        if backdrop is not None:
            backdrop[symbol] = wf.daily_differences(answers, tables[symbol], measure)
        if rows.empty:
            continue
        rows["asset"], rows["kind"] = symbol, kind_of(symbol)
        parts.append(rows)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _finish(result: dict) -> dict:
    result["through"] = CUT.strftime("%Y-%m-%d")
    result["start"] = START
    return result


def _print(result: dict) -> None:
    for key, s in result["sets"].items():
        print(f"\n{s.get('name', key)}: {s['verdict'] or s.get('note')}")
        if s.get("episodes"):
            print(f"  {s['episodes']} episodes in {s['weeks']} weeks, {s['assets']} assets "
                  f"({s['coins']} coin, {s['shares']} share episodes); top {s['top_assets']}")
            print("  " + ", ".join(f"{k} {v:.3f}" for k, v in s["plain"].items()))
            for m, t in s["tests"].items():
                print(f"  {m}: estimate {t['estimate']}, 95% {t['ci95']}, p {t['p_two_sided']}, Holm "
                      f"{t['holm_passed']}, consistency {t['consistency']}")


def study_step(args) -> int:
    """The provided library, one family of tests across all its Sets."""
    docs = _docs(args)
    tables: dict = {}
    backdrops = {key: {} for key in docs}
    per_set = {key: episode_rows(args.prices, args.out, key, tables, backdrops[key], wf.core(docs[key][2]))
               for key in docs}
    result = _finish(wf.study(per_set, {k: v[2] for k, v in docs.items()}, backdrops=backdrops))
    for key, s in result["sets"].items():
        s["name"] = docs[key][1]
        s["hash"] = wf.logic_hash(docs[key][0])
    Path(args.out, "what_followed.json").write_text(json.dumps(result, indent=1, default=float))
    _print(result)
    return 0


# ----------------------------------------------------------------------------------------------- the queue

def _client():
    from supabase import create_client

    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _now() -> str:
    return pd.Timestamp.now(tz="UTC").isoformat()


def pick_step(args) -> int:
    """Queued Sets (and any stuck while running) -> out/queue.json. Sets that cannot be studied are refused with
    the reason; a body whose fingerprint does not match its row is refused too."""
    db = _client()
    rows = (db.table("set_studies").select("set_hash, set_body, set_name, status, started_at, requested_by")
            .in_("status", ["queued", "running"]).order("requested_at").limit(20).execute().data or [])
    stuck = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=STUCK_HOURS)
    queue = {}
    for r in rows:
        if r["status"] == "running" and r.get("started_at") and pd.Timestamp(r["started_at"]) > stuck:
            continue
        if len(queue) >= PICK:
            break
        body = r["set_body"] or {}
        if wf.logic_hash(body) != r["set_hash"]:
            _update(db, r["set_hash"], status="refused", error="The Set did not match its fingerprint.")
            continue
        ok, why = wf.studyable(body)
        if not ok:
            _update(db, r["set_hash"], status="refused", error=why, finished_at=_now())
            _tell(db, r.get("requested_by"), r.get("set_name") or "", f"can't be studied: {why}")
            continue
        _update(db, r["set_hash"], status="running", started_at=_now())
        queue[r["set_hash"]] = {"body": body, "name": r.get("set_name") or "", "by": r.get("requested_by")}
    Path(args.out).mkdir(parents=True, exist_ok=True)
    Path(args.out, "queue.json").write_text(json.dumps(queue))
    print(f"{len(queue)} Set(s) to study")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"work={'yes' if queue else 'no'}\n")
    return 0


def _tell(db, user_id, name: str, what: str) -> None:
    """🔬 A note in the person's notifications (the list on the left) when their study is done, refused or failed."""
    if not user_id:
        return
    try:
        db.table("user_notifications").insert({
            "user_id": user_id, "asset_symbol": "", "asset_name": name or "Your Set", "alert_type": "study",
            "message": f"What followed for “{name or 'your Set'}” {what}"[:500]}).execute()
    except Exception as exc:                        # a note that can't be written never stops the study
        print(f"note not written: {exc}")


def _update(db, set_hash: str, **fields) -> None:
    db.table("set_studies").update(fields).eq("set_hash", set_hash).execute()


def finish_step(args) -> int:
    """One study per queued Set (its own small family of tests), written back."""
    db = _client()
    queue = json.loads(Path(args.out, "queue.json").read_text())
    if os.environ.get("ANSWERS_RESULT", "success") != "success":       # a study on part of the assets is not one
        for key, item in queue.items():
            _update(db, key, status="failed", finished_at=_now(),
                    error="The study could not finish this time. Tap Study this Set to try again.")
            _tell(db, item.get("by"), item.get("name"), "could not finish this time. Tap Study this Set to try again.")
        print("answers did not finish: marked failed")
        return 0
    tables: dict = {}
    for key, item in queue.items():
        try:
            back: dict = {}
            rows = episode_rows(args.prices, args.out, key, tables, back, wf.core("directional"))
            result = _finish(wf.study({key: rows}, {key: "directional"}, backdrops={key: back}))
            s = result["sets"][key]
            s["name"], s["hash"] = item["name"], key
            result["sets"] = {key: s}
            _update(db, key, status="done", result=json.loads(json.dumps(result, default=float)),
                    method=wf.METHOD, finished_at=_now(), error=None)
            verdict = s.get("verdict") or s.get("note") or "ready"
            _tell(db, item.get("by"), item.get("name"),
                  f"is ready: {verdict}. Open the Set in Signal Sets to read it.")
            _print(result)
        except Exception as exc:                                    # one Set never stops the others
            _update(db, key, status="failed", error=str(exc)[:480], finished_at=_now())
            _tell(db, item.get("by"), item.get("name"), "could not finish this time. Tap Study this Set to try again.")
            print(f"{key}: failed: {exc}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("step", choices=["answers", "study", "pick", "finish"])
    p.add_argument("prices")
    p.add_argument("out")
    p.add_argument("--shard", default="0/1")
    p.add_argument("--sets", default="")
    p.add_argument("--queue", default="")
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args(argv)
    return {"answers": answers_step, "study": study_step, "pick": pick_step, "finish": finish_step}[args.step](args)


if __name__ == "__main__":
    raise SystemExit(main())
