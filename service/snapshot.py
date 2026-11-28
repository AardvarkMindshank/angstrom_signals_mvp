"""📸 Quick Snapshot for the new app: every part of the classic Quick Snapshot (app.py, _render_dashboard_body and
snapshot_view.py) worked out the same way, returned as plain data for the page to draw.

  tides    the Tides card: tide, how long it has held, sea, fear index, the winds, the next big event
  changes  what changed since the last visit: Trend colour borders you alert on, then the largest moves
  extremes the highest and lowest Trend in your own watchlist, per market
  moods    crypto and stock market sentiment, with the crowd's agree and disagree counts
  funnels  one tile per funnel: Candidates, Flagged, the stage counts, and what came in or left since the last visit
  markets  the markets strip: indices, VIX, yields, the dollar, gold, oil and crypto totals with a 30-day line

save=True keeps this visit's Trend readings and Candidates as the account's "last visit" (settings.score_visit and
settings.funnel_seen), as the classic page does once a session.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import i18n

_rows: dict = {}                 # asset key -> (stamp, fields): readings worked out here when none are stored
_lock = threading.Lock()


def _settings(db, uid: str) -> dict:
    rows = (db.table("user_preferences").select("settings, crypto_watchlist, stock_watchlist")
            .eq("user_id", uid).limit(1).execute().data or [])
    r = rows[0] if rows else {}
    return {"settings": r.get("settings") or {}, "crypto": r.get("crypto_watchlist") or {},
            "stock": r.get("stock_watchlist") or {}}


def _save_settings(db, uid: str, updates: dict) -> None:
    rows = db.table("user_preferences").select("settings").eq("user_id", uid).limit(1).execute().data or []
    merged = {**((rows[0] or {}).get("settings") or {} if rows else {}), **updates}
    db.table("user_preferences").update({"settings": merged}).eq("user_id", uid).execute()


def _num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------------------ your watchlist's readings

def _asset_rows(db, settings: dict, crypto: dict, stock: dict) -> list[dict]:
    """One entry per watchlist asset: Trend and its parts, price, the day's change, the last 8 closes, logo, the
    headline sentiment and the next earnings date."""
    import market_store as ms
    import signals_view
    import stored_readings
    from scoring import calculate_indicators

    wanted = []
    if settings.get("trade_crypto", True) is not False:
        wanted += [("Crypto", k, v if isinstance(v, str) else k) for k, v in crypto.items()]
    if settings.get("trade_equities", True) is not False:
        wanted += [("Stock", k, f"{v if isinstance(v, str) else k} ({k})") for k, v in stock.items()]
    shared = ms.load_shared_market(db, [ms.asset_market_key(kind, aid) for kind, aid, _ in wanted])
    out = []
    hour = datetime.now(timezone.utc).strftime("%Y-%m-%d %H")
    for kind, aid, name in wanted:
        key = ms.asset_market_key(kind, aid)
        row = shared.get(key) or {}
        frame = ms.frame_from_row(row)
        fields = None
        if frame is not None and len(frame) >= 15:
            fields = stored_readings.use(row, frame)
            if fields is None:
                stamp = (len(frame), float(frame["close"].iloc[-1]), hour)
                with _lock:
                    hit = _rows.get(key)
                if hit and hit[0] == stamp:
                    fields = hit[1]
                else:
                    try:
                        fields = signals_view.row_fields(calculate_indicators(frame), "crypto" if kind == "Crypto" else "equity")
                    except Exception:
                        fields = None
                    with _lock:
                        if len(_rows) > 3000:
                            _rows.clear()
                        _rows[key] = (stamp, fields)
        fields = fields or {}
        report, _ = ms.sentiment_from_row(row)
        from score_colours import sentiment_shown       # stored 0..100, shown -100..+100
        closes = [float(x) for x in (frame["close"].tail(8).tolist() if frame is not None and not frame.empty else [])]
        out.append({"type": kind, "key": aid, "symbol": name, "logo": row.get("logo_url") or "",
                    "trend": _num(fields.get("trend")), "trend_parts": fields.get("trend_parts") or {},
                    "price": _num(fields.get("latest_price")), "change_1d": _num(fields.get("change_1d")),
                    "closes": closes[-6:] if kind == "Stock" else closes,
                    "mood": sentiment_shown((report or {}).get("score")),
                    "next_earnings": str(row.get("next_earnings") or "")[:10] if kind == "Stock" else ""})
    return out


def _visit_key(kind, aid) -> str:
    return f"{kind}:{aid}"


def visit_snapshot(rows: list[dict]) -> dict:
    """As app._score_snapshot: Trend and its parts per asset, kept for the next visit."""
    import group_readings

    snap = {}
    for r in rows:
        if r["trend"] is None:
            continue
        factors = {str(k): round(float(v), 1) for k, v in (r.get("trend_parts") or {}).items() if _num(v) is not None}
        snap[_visit_key(r["type"], r["key"])] = {"trend": round(r["trend"], 1), "factors": factors,
                                                 "signals_version": group_readings.VERSION}
    return snap


def what_changed(rows: list[dict], baseline: dict | None, settings: dict) -> dict:
    """As app._what_changed_html: crossings of the Trend borders you alert on, then the three largest other moves."""
    import alerts as al

    if not isinstance(baseline, dict) or not baseline:
        return {"seen": False, "crossings": [], "moves": []}
    ticks = al.reading_crossings(settings, "trend")
    crossings, moves = [], []
    for r in rows:
        prev = baseline.get(_visit_key(r["type"], r["key"]))
        if not isinstance(prev, dict) or r["trend"] is None or _num(prev.get("trend")) is None:
            continue
        now_s, was = round(r["trend"], 1), round(float(prev["trend"]), 1)
        factors = {str(k): _num(v) or 0.0 for k, v in (r.get("trend_parts") or {}).items()}
        before = prev.get("factors") if isinstance(prev.get("factors"), dict) else {}
        best, shift = "", 0.0
        for k in set(before) | set(factors):
            d = (factors.get(k) or 0.0) - (_num(before.get(k)) or 0.0)
            if abs(d) > abs(shift):
                best, shift = k, d
        detail = i18n.t("Trend {was} to {now}.", was=f"{was:+.0f}", now=f"{now_s:+.0f}")
        if best and abs(shift) >= 0.05:
            detail += " " + i18n.t("{factor} moved it most ({change}).", factor=i18n.t(best), change=f"{shift:+.1f}")
        delta = round(now_s - was, 1)
        crossed = al.crossing_for(al.zone(was), al.zone(now_s), ticks)
        item = {"pick": f"{r['type']}|{r['key']}", "symbol": r["symbol"], "logo": r["logo"], "delta": delta,
                "was": was, "now": now_s, "detail": detail, "price": r["price"], "change_1d": r["change_1d"],
                "closes": r["closes"], "mood": r["mood"], "next_earnings": r["next_earnings"], "crossed": bool(crossed)}
        if crossed:
            item["title"] = i18n.t("{name} Trend {words}", name=r["symbol"], words=i18n.t(al.CROSSINGS[crossed][2]))
            crossings.append(item)
        elif abs(delta) >= 5:
            item["title"] = i18n.t("{name} Trend moved", name=r["symbol"])
            moves.append(item)
    crossings.sort(key=lambda i: abs(i["delta"]), reverse=True)
    moves.sort(key=lambda i: abs(i["delta"]), reverse=True)
    return {"seen": True, "crossings": crossings, "moves": moves[:3]}


def extremes(rows: list[dict]) -> dict:
    out = {}
    for kind, market in (("Crypto", "crypto"), ("Stock", "equity")):
        valid = sorted((r for r in rows if r["type"] == kind and r["trend"] is not None), key=lambda r: r["trend"],
                       reverse=True)
        if valid:
            pick = lambda r: {"pick": f"{kind}|{r['key']}", "symbol": r["symbol"], "logo": r["logo"], "trend": r["trend"]}  # noqa: E731
            out[market] = {"top": pick(valid[0]), "bottom": pick(valid[-1]) if len(valid) > 1 else None}
    return out


# -------------------------------------------------------------------------------------------------------- the Tides

def tides_card(db) -> dict | None:
    """As snapshot_view.tides_card, as data."""
    import macro_calendar as mc
    import snapshot_view as sv
    import tides as td

    snap = td.latest(db)
    t_ = (snap or {}).get("tide") or {}
    if t_.get("status") != "ok" or t_.get("label") not in td.TIDE_WORDS:
        return None
    name, plain, _icon = td.TIDE_WORDS[t_["label"]]
    card = {"label": t_["label"], "name": i18n.t(name), "plain": i18n.t(plain).capitalize(),
            "held": i18n.t("held {n} trading days", n=t_.get("held_days")) if t_.get("held_days") else "",
            "tiles": [], "winds": [], "event": None}
    sea = (snap or {}).get("sea") or {}
    if sea.get("status") == "ok":
        card["tiles"].append({"k": "⛵ " + i18n.t("Sea"), "v": i18n.t(str(sea["state"]).capitalize()),
                              "sub": i18n.t(str(sea.get("plain") or "").capitalize())})
    fear = ((snap or {}).get("currents") or {}).get("fear") or {}
    if fear.get("status") == "ok" and fear.get("value") is not None:
        week = fear.get("change_7")
        card["tiles"].append({"k": "😨 " + i18n.t("Fear (VIX)"), "v": f"{float(fear['value']):.1f}",
                              "sub": i18n.t("{change} pts this week", change=f"{float(week):+.1f}") if week is not None else ""})
    for key, icon in (("crypto", "🪙"), ("equity", "🏛️")):
        w = ((snap or {}).get("winds") or {}).get(key)
        if w:
            card["winds"].append({"icon": icon, "name": i18n.t(w.get("name") or key), "wind": str(w.get("wind") or ""),
                                  "word": i18n.t(str(w.get("wind") or "")),
                                  "drivers": ", ".join(td.mid(i18n.t(td.SPEC[k]["name"])) for k in w.get("drivers") or [] if k in td.SPEC)})
    e = sv.next_event()
    if e:
        card["event"] = {"icon": mc.pennants(e["tier"]) or "📅", "name": e.get("short") or e["name"],
                         "when": mc.when_words(e["at"])}
    return card


# -------------------------------------------------------------------------------------------------------- the moods

def moods(db, settings: dict) -> list[dict]:
    import market_store as ms
    from score_colours import sentiment_category_score, sentiment_shown

    def coverage(score):
        s = sentiment_category_score(score)
        return (i18n.t("Bullish coverage") if s >= 60 else i18n.t("Mildly bullish coverage") if s >= 53 else
                i18n.t("Mixed coverage") if s >= 47 else i18n.t("Mildly bearish coverage") if s >= 40 else
                i18n.t("Bearish coverage"))

    specs = ([("crypto", "Crypto market")] if settings.get("trade_crypto", True) is not False else []) + \
            ([("stock", "Stock market")] if settings.get("trade_equities", True) is not False else [])
    if not specs:
        return []
    stored = ms.load_market_moods(db) or {}
    crowd = ms.market_mood_crowd(db, [k for k, _ in specs])
    out = []
    for key, label in specs:
        report, _ = ms.sentiment_from_row(stored.get(key))
        score = _num((report or {}).get("score"))
        voice = dict(crowd.get(key) or {})
        if voice.get("alt_avg") is not None:
            voice["alt_avg"] = sentiment_shown(voice["alt_avg"])
        # Sentiment is stored 0..100 and shown -100..+100 (score_colours), as everywhere in the app.
        out.append({"key": key, "label": i18n.t(label), "score": sentiment_shown(score), "coverage": coverage(score) if score is not None else "",
                    "summary": " ".join(str((report or {}).get("summary") or "").split()), "crowd": voice})
    return out


# ------------------------------------------------------------------------------------------------------ the funnels

def funnel_tiles(db, uid: str, settings: dict) -> tuple[list[dict], dict]:
    """As app._snapshot_funnels: (tiles, Candidates now per funnel)."""
    import funnel as fn
    import funnel_view as fv
    import snapshot_view as sv

    trading = {"crypto": settings.get("trade_crypto", True) is not False,
               "equity": settings.get("trade_equities", True) is not False}
    funnels = [f for f in fv.load_funnels(db, uid) if trading.get(f.get("market") or "crypto")]
    baseline = settings.get("funnel_seen") if isinstance(settings.get("funnel_seen"), dict) else {}
    universes, tiles, now_seen = {}, [], {}
    for f in funnels:
        market = f.get("market") or "crypto"
        if market not in universes:
            universes[market] = fv.load_universe(db, market)
        uni = universes[market]
        try:
            states = fv.states(f, fv.load_coins(db, f["id"]))
        except Exception:
            continue
        pool = sum(1 for u in uni.values() if u.get("included"))
        cands = sorted(fv.coins_for("candidate", states), key=lambda c: (uni.get(c) or {}).get("rank") or 10**6)
        label = {c: str((uni.get(c) or {}).get("symbol") or c).upper() if market == "crypto" else str(c).upper() for c in cands}
        before = baseline.get(str(f["id"])) if str(f["id"]) in baseline else None
        new, gone = sv.candidate_changes(before, cands)
        k = fn.counts(states, len(f["stages"]))
        tiles.append({"id": f["id"], "name": f["name"], "market": market, "direction": f.get("direction"),
                      "paused": bool(f.get("paused")), "line": fv.counts_line(f, states, pool),
                      "candidates": k["candidate"], "flagged": k["flagged"],
                      "candidate_names": [label[c] for c in cands],
                      "candidate_keys": [("Crypto|" + c) if market == "crypto" else ("Stock|" + str(c).upper()) for c in cands],
                      "new": [label.get(c, str(c).upper()) for c in new],
                      "gone": [str((uni.get(c) or {}).get("symbol") or c).upper() for c in gone],
                      "seen": before is not None})
        now_seen[str(f["id"])] = cands
    order = ({"crypto": 0, "equity": 1}, {"short": 0, "long": 1})
    tiles.sort(key=lambda x: (order[0].get(x["market"], 2), order[1].get(x.get("direction"), 2), str(x["name"])))
    return tiles, now_seen


# ------------------------------------------------------------------------------------------------ the markets strip

def markets(db, settings: dict) -> dict:
    import market_overview as mo

    overview = mo.load_overview(db)
    crypto = settings.get("trade_crypto", True) is not False
    stocks = settings.get("trade_equities", True) is not False
    cards = []
    for c in mo.card_list(overview, crypto, stocks):
        key, unit = c["key"], c["unit"]
        hint = i18n.t(mo.HINTS.get(key, ""))
        place = mo.EXCHANGES[c["exchange"]][3] if c.get("open") is not None else ""
        if place:
            hint += " " + (i18n.t("{place} is open now (public holidays are not shown).", place=place) if c["open"]
                           else i18n.t("{place} is closed now (public holidays are not shown).", place=place))
        if key in mo.CRYPTO_KEYS:
            hint += " " + (i18n.t("The change is over the last 24 hours.") if key == "crypto_cap"
                           else i18n.t("The change is since 00:00 UTC.") if key in ("btc", "eth") else "")
        else:
            hint += " " + i18n.t("The change is since the previous close; while the market is closed it is the last "
                                 "trading session's move.")
        change = _num(c.get("change"))
        text = ""
        if change is not None:
            text = (i18n.t("{change:+.2f} pt", change=change) if unit in ("yield", "pct")
                    else f"{change:+.0f}" if unit == "points" else f"{change:+.1f}%")
        small = change is None or abs(change) < (0.005 if unit in ("yield", "pct") else 0.05)
        cards.append({"key": key, "group": c["group"], "label": i18n.t(c["label"]), "hint": hint.strip(),
                      "value": mo.value_text(key, unit, c["value"]), "change": text,
                      "tone": "flat" if small else ("up" if (change > 0) != bool(c["invert"]) else "down"),
                      "rising": None if small else change > 0,
                      "spark": [v for v in (_num(x) for x in c.get("spark") or []) if v is not None],
                      "invert": bool(c["invert"]), "open": c.get("open"),
                      "place_state": (i18n.t("{place} is open", place=place) if c.get("open") else i18n.t("{place} is closed", place=place)) if place else "",
                      "word": i18n.t(mo._fng_word(c["value"])) if key == "fng" else ""})
    return {"groups": [[g, i18n.t(h)] for g, h in mo.GROUPS], "cards": cards,
            "fetched_at": (overview or {}).get("fetched_at")}


# --------------------------------------------------------------------------------------------------------- together

def build(db, uid: str, lang: str, save: bool) -> dict:
    started = time.time()
    with i18n.using(lang):
        p = _settings(db, uid)
        s = p["settings"]
        out = {"errors": []}

        def part(name, fn, fallback):
            try:
                out[name] = fn()
            except Exception as exc:
                print(f"snapshot {name} failed: {type(exc).__name__}", flush=True)
                out[name] = fallback
                out["errors"].append(name)

        rows: list = []
        part("rows", lambda: _asset_rows(db, s, p["crypto"], p["stock"]), [])
        rows = out.pop("rows")
        part("changes", lambda: what_changed(rows, s.get("score_visit"), s), {"seen": False, "crossings": [], "moves": []})
        part("extremes", lambda: extremes(rows), {})
        part("tides", lambda: tides_card(db), None)
        part("moods", lambda: moods(db, s), [])
        seen: dict = {}

        def funnels():
            tiles, now = funnel_tiles(db, uid, s)
            seen.update(now)
            return tiles
        part("funnels", funnels, [])
        part("markets", lambda: markets(db, s), {"groups": [], "cards": []})
        out["trade"] = {"crypto": s.get("trade_crypto", True) is not False, "equity": s.get("trade_equities", True) is not False}
        if save:
            updates = {}
            snap = visit_snapshot(rows)
            if snap:
                updates["score_visit"] = snap
            if seen:
                updates["funnel_seen"] = seen
            if updates:
                try:
                    _save_settings(db, uid, updates)
                except Exception as exc:
                    print(f"snapshot save failed: {type(exc).__name__}", flush=True)
        print(f"snapshot: {len(rows)} assets in {time.time() - started:.1f}s", flush=True)
        return out
