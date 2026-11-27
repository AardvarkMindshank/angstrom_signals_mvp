"""₿ Crypto Signals and 📈 Equity Signals for the new app: the classic watchlist tables (app.py, style_and_show_table and
_dynamic_view), worked out the same way and returned as data.

build(): one market's table, either the member's own watchlist or a funnel's assets at one stage ("Dynamic funnel"),
with every column: the chosen Signal Groups and Sets (table_columns.py), price, RSI, the period changes, market cap,
ATR, volume, rank, earnings, how many members watch it, the headline sentiment and the crowd, comments and the
30-day line.

columns(): what the column chooser can offer (the starter Groups, provided Sets, and the member's own and shared ones).
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import i18n

_cells: dict = {}                # (asset key, column fingerprint, stamp) -> evaluated column cells
_fields: dict = {}               # (asset key, stamp) -> readings worked out here
_lock = threading.Lock()
KEYS = {"crypto": ("funnel_pick", "funnel_stage", "crypto_table"), "equity": ("eq_funnel_pick", "eq_funnel_stage", "equity_table")}


def _num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _remember(store: dict, key, value, limit: int = 4000):
    with _lock:
        if len(store) > limit:
            store.clear()
        store[key] = value
    return value


def _prefs(db, uid: str) -> dict:
    rows = (db.table("user_preferences").select("settings, crypto_watchlist, stock_watchlist")
            .eq("user_id", uid).limit(1).execute().data or [])
    r = rows[0] if rows else {}
    return {"settings": r.get("settings") or {}, "crypto": r.get("crypto_watchlist") or {}, "stock": r.get("stock_watchlist") or {}}


def specs_for(db, settings: dict) -> list[dict]:
    """The account's chosen reading columns, resolved (as app._table_column_specs)."""
    import table_columns

    columns = table_columns.chosen(settings)
    saved = []
    if any(k.startswith("saved:") for part in columns.values() for k in part):
        import perspectives
        import signal_groups_inspector as gi

        saved, _ = gi.saved_configs(db)
        try:
            perspectives.load_studies(db)
        except Exception:
            pass
    return table_columns.resolve(columns, saved or [])


def _column_head(spec: dict) -> dict:
    import signals_v2
    import signals_view
    import table_columns

    if spec["cluster"]:
        c = signals_v2.CLUSTERS[spec["cluster"]]
        return {"key": spec["key"], "part": spec["part"], "cluster": spec["cluster"], "icon": c["icon"],
                "name": i18n.t(c["name"]), "hint": signals_view.header_hint(spec["cluster"])}
    return {"key": spec["key"], "part": spec["part"], "cluster": None, "icon": "", "name": spec["name"],
            "hint": table_columns.header(spec), "config": spec.get("config")}


# ---------------------------------------------------------------------------------------------------- the funnel view

def funnel_view(db, uid: str, market: str, settings: dict, pick: str | None, stage: str | None) -> dict:
    """As app._dynamic_view: the market's funnels (with their stage chips), the chosen one and stage, and the assets
    at that stage (largest first, at most funnel_view.SHOW_LIMIT)."""
    import funnel_rows
    import funnel_runner
    import funnel_view as fv
    import snapshot_view as sv

    funnels = [f for f in fv.load_funnels(db, uid) if (f.get("market") or "crypto") == market]
    out = {"funnels": [], "picked": None, "stage": None, "choices": [], "assets": {}, "states": {}, "f": None}
    if not funnels:
        return out
    universe = fv.load_universe(db, market)
    baseline = settings.get("funnel_seen") if isinstance(settings.get("funnel_seen"), dict) else {}
    pool = sum(1 for u in universe.values() if u.get("included"))
    rows, all_states = [], {}
    for f in funnels:
        try:
            coins, runs = fv.load_coins(db, f["id"]), fv.last_runs(db, f["id"], len(f["stages"]))
        except Exception:
            continue
        states = fv.states(f, coins)
        all_states[f["id"]] = (states, runs)
        before = baseline.get(str(f["id"])) if str(f["id"]) in baseline else None
        new, _ = sv.candidate_changes(before, fv.coins_for("candidate", states))
        rows.append({"id": f["id"], "name": f["name"], "direction": f["direction"],
                     "dir_icon": fv.fn.DIRECTION_ICONS.get(f["direction"], ""), "paused": bool(f.get("paused")),
                     "checked": funnel_rows.status(f, runs),
                     "chips": funnel_rows.chips(f, states, len(new), funnel_runner.hover(f))})
    rows = funnel_rows.order(rows)
    out["funnels"] = rows
    if not rows:
        return out
    ids = [r["id"] for r in rows]
    if pick not in ids:
        pick, stage = funnel_rows.default_pick(rows)
    f = next(x for x in funnels if x["id"] == pick)
    states, runs = all_states[f["id"]]
    choices = fv.picks(f, states, pool)
    if stage not in [k for k, _ in choices]:
        stage = "candidate" if fv.coins_for("candidate", states) else f"stage:{len(f['stages']) - 2}"
    shown = sorted(fv.coins_for(stage, states),
                   key=lambda c: (-fv.fn.place(states[c])["depth"], (universe.get(c) or {}).get("rank") or 10**6))
    out.update({"picked": pick, "stage": stage, "choices": [[k, v] for k, v in choices], "f": f, "states": states,
                "universe": universe, "line": fv.counts_line(f, states, pool), "health": fv.health(runs, f, states=states),
                "count": len(shown), "more": max(0, len(shown) - fv.SHOW_LIMIT),
                "assets": {c: (universe.get(c) or {}).get("name") or c for c in shown[:fv.SHOW_LIMIT]}})
    return out


# ---------------------------------------------------------------------------------------------------------- the rows

def _subject(db):
    """A Set line pinned to another asset (for example Bitcoin): that asset's stored daily bars."""
    import market_store as ms
    from group_readings import stored_context
    from scoring import calculate_indicators

    def ctx(engine_kind, subject_id):
        kind = "Crypto" if engine_kind == "crypto" else "Stock"
        key = ms.asset_market_key(kind, subject_id)
        frame = ms.frame_from_row(ms.load_shared_market(db, [key]).get(key))
        if frame is None or len(frame) < 15:
            raise ValueError(i18n.t("No stored daily bars for {subject_id}.", subject_id=subject_id))
        return stored_context(calculate_indicators(frame), kind, asset_id=subject_id)[0]
    return ctx


def _cell_out(spec: dict, cell: dict | None) -> dict | None:
    """One Group or Set cell with its hover words, as the classic cells word them."""
    import perspectives
    import table_columns as tc

    if cell is None and not tc.daily_only(spec.get("doc")):
        tfs = ", ".join(sorted(set(tc._timeframes(spec["doc"])) - {"1D"}))
        return {"waiting": True, "tip": f"{spec['name']}: reads {tfs} candles, so it is worked out in the background "
                                        "at each close; the first answer appears within the hour."}
    cell = cell or {}
    when, stale = tc.freshness(spec, cell)
    if spec["part"] == "groups":
        value, label = _num(cell.get("value")), cell.get("label")
        tip = f"{spec['name']}: " + ("no reading" if value is None else f"{value:+.0f}") + (f" · {label}" if label else "")
        if cell.get("why"):
            tip += f" · {cell['why']}"
        if cell.get("error"):
            tip += i18n.t(" · could not be worked out ({cell_error})", cell_error=cell["error"])
        return {"value": value, "label": label, "stale": stale, "tip": tip + (f" · {when}" if when else "")}
    answer = cell.get("answer") if cell.get("answer") in tc.ANSWER_MARK else "unknown"
    tip = f"{spec['name']}: {tc.ANSWER_HOVER[answer]}" + (f" · {cell['why']}" if cell.get("why") else "")
    if cell.get("available"):
        tip += " · " + " ".join(perspectives.data_mark(cell["available"]))
    tip += " · " + " ".join(perspectives.evidence(spec.get("doc"), spec.get("key")))
    if cell.get("error"):
        tip += i18n.t(" · could not be worked out ({cell_error})", cell_error=cell["error"])
    return {"answer": answer, "stale": stale, "tip": tip + (f" · {when}" if when else "")}


def rows_for(db, kind: str, watch: dict, specs: list[dict], fview: dict | None, own: dict) -> list[dict]:
    import column_answers
    import funnel_view as fv
    import market_store as ms
    import signals_view
    import stored_readings
    import table_columns as tc
    from group_readings import stored_context
    from scoring import calculate_indicators

    keys = [ms.asset_market_key(kind, aid) for aid in watch]
    shared = ms.load_shared_market(db, keys)
    counts, crowd, comments = {}, {}, {}
    try:
        counts = ms.holder_counts(db)
    except Exception:
        pass
    try:
        crowd = ms.sentiment_crowd(db, keys)
    except Exception:
        pass
    try:
        comments = ms.sentiment_comment_lists(db, keys)
    except Exception:
        pass
    extra = [c for c in specs if not c["cluster"]]
    fp = tc.fingerprint(specs)
    engine = "crypto" if kind == "Crypto" else "equity"
    intraday = {}
    later = [c for c in extra if c["doc"] is not None and not tc.daily_only(c["doc"])]
    if later:
        intraday = column_answers.load(db, sorted({column_answers.def_hash(c["doc"]) for c in later}),
                                       [f"{engine}:{a if kind == 'Crypto' else str(a).upper()}" for a in watch])
    subject = _subject(db)
    hour = datetime.now(timezone.utc).strftime("%Y-%m-%d %H")
    out = []
    for aid, name in watch.items():
        key = ms.asset_market_key(kind, aid)
        row = shared.get(key) or {}
        frame = ms.frame_from_row(row)
        symbol = (name if isinstance(name, str) else aid) if kind == "Crypto" else f"{name if isinstance(name, str) else aid} ({aid})"
        r = {"key": f"{kind}|{aid}", "id": aid, "symbol": symbol, "logo": row.get("logo_url") or "",
             "own": aid in own or str(aid).upper() in own, "cells": {}, "clusters": {}}
        if frame is not None and len(frame) >= 15:
            stamp = (len(frame), float(frame["close"].iloc[-1]), hour)
            fields = stored_readings.use(row, frame)
            if fields is None:
                hit = _fields.get((key, stamp))
                fields = hit if hit is not None else _remember(_fields, (key, stamp),
                                                                 signals_view.row_fields(calculate_indicators(frame), engine))
            clusters = ((fields.get("signals") or {}).get("clusters") or {})
            for c in ("trend", "stretch", "flow"):
                r["clusters"][c] = {"value": _num(fields.get(c)), "tip": signals_view.cluster_hint(c, clusters.get(c))}
            for k in ("rsi", "change_1d", "change_7d", "change_30d", "atr_pct", "volume_ratio"):
                r[k] = _num(fields.get(k))
            r["price"] = _num(fields.get("latest_price"))
            r["closes"] = [float(x) for x in (signals_view.closes_since(frame, 30) or frame["close"].tail(30).tolist())]
            if extra:
                hit = _cells.get((key, fp, stamp))
                if hit is None:
                    try:
                        ctx, last = stored_context(calculate_indicators(frame), kind, asset_id=aid)
                        as_of = f"{last:%-d %b %Y}"
                        hit = tc.evaluate(specs, ctx, subject_context=subject, as_of=as_of)
                    except Exception as exc:
                        hit = {c["key"]: {"error": str(exc)[:160]} for c in extra}
                    _remember(_cells, (key, fp, stamp), hit)
                cells = dict(hit)
                for c in later:
                    got = intraday.get((column_answers.def_hash(c["doc"]), f"{engine}:{aid if kind == 'Crypto' else str(aid).upper()}"))
                    if got is not None:
                        cells[c["key"]] = got
                r["cells"] = {c["key"]: _cell_out(c, cells.get(c["key"])) for c in extra}
        else:
            r["problem"] = i18n.t("Shared prices are not ready yet.")
        r["rank"] = row.get("market_rank") if kind == "Crypto" else None
        r["market_cap"] = _num(row.get("market_cap"))
        r["next_earnings"] = str(row.get("next_earnings") or "")[:10] if kind == "Stock" else ""
        from score_colours import sentiment_shown, sentiment_spread   # stored 0..100, shown -100..+100
        report, _ = ms.sentiment_from_row(row)
        r["mood"] = sentiment_shown((report or {}).get("score"))
        v = crowd.get(key) or {}
        r["crowd"] = {"up": v.get("up", 0), "down": v.get("down", 0), "alt_count": v.get("alt_count", 0),
                      "alt_avg": sentiment_shown(v.get("alt_avg")) if v.get("alt_avg") is not None else None,
                      "alt_spread": sentiment_spread(v.get("alt_spread")) if v.get("alt_spread") is not None else None}
        r["comments"] = len(comments.get(key) or [])
        r["holders"] = counts.get(key, 0)
        if fview and fview.get("f") is not None:
            st_ = fview["states"].get(str(aid) if kind == "Crypto" else str(aid).upper())
            if st_ is not None:
                info = fview["universe"].get(str(aid) if kind == "Crypto" else str(aid).upper()) or {}
                icon, hover, sort = fv.stage_cell(fview["f"], st_, info.get("pair") if kind == "Crypto" else "yahoo:" + str(aid).upper(),
                                                  earnings=info.get("next_earnings") if kind == "Stock" else None)
                r["stage"] = {"icon": icon, "tip": hover, "sort": sort}
        out.append(r)
    out.sort(key=lambda x: -((x["clusters"].get("trend") or {}).get("value") if (x["clusters"].get("trend") or {}).get("value") is not None else -1e9))
    return out


def build(db, uid: str, market: str, lang: str, mode: str | None, pick: str | None, stage: str | None) -> dict:
    started = time.time()
    with i18n.using(lang):
        p = _prefs(db, uid)
        s = p["settings"]
        kind = "Crypto" if market == "crypto" else "Stock"
        own = p["crypto"] if market == "crypto" else p["stock"]
        pick_key, stage_key, mode_key = KEYS[market]
        mode = mode or ("funnel" if s.get(mode_key) == "funnel" else "watchlist")
        pick = pick or s.get(pick_key)
        stage = stage or s.get(stage_key)
        specs = specs_for(db, s)
        fview = funnel_view(db, uid, market, s, pick, stage) if mode == "funnel" else None
        watch = fview["assets"] if fview is not None else own
        rows = rows_for(db, kind, watch, specs, fview, own)
        out = {"market": market, "mode": mode, "columns": [_column_head(c) for c in specs], "rows": rows,
               "flags": {"period": s.get("show_period_changes", True) is not False,
                         "extra": s.get("show_extra_metrics", True) is not False}}
        if fview is not None:
            out["funnel"] = {k: fview.get(k) for k in ("funnels", "picked", "stage", "choices", "line", "health", "count", "more")}
        print(f"signals: {market} {mode} {len(rows)} rows in {time.time() - started:.1f}s", flush=True)
        return out


def column_options(db, uid: str, lang: str) -> dict:
    import signal_groups_inspector as gi
    import table_columns

    with i18n.using(lang):
        p = _prefs(db, uid)
        try:
            saved, _ = gi.saved_configs(db)
        except Exception:
            saved = []
        groups, sets = table_columns.options(saved or [], uid)
        return {"groups": [[k if k.startswith("saved:") else k, v] for k, v in groups.items()],
                "sets": [[k, v] for k, v in sets.items()], "chosen": table_columns.chosen(p["settings"]),
                "max": table_columns.MAX_EACH}
