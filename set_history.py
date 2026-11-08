"""
A Set's answer on every past day, as coloured bands behind the price chart (agreed plan, Stage B).

For each finished daily bar the Set is evaluated exactly as the dashboard would have evaluated it at that close
(group_readings.stored_context cuts the bars at that moment, so nothing later is seen). Consecutive days with the
same answer are joined into spans: [first day, last day, answer]. Spans are small however long the history, so they
are stored once per Set definition and asset (table set_history, shared by every account that looks) and only the
new days are worked out afterwards.

Bands cover the whole saved history, including the protected test period from 30 Oct 2024 (the owner's choice:
viewing only). Outcome studies, which measure, use only days before it (research rules).
"""

from __future__ import annotations

import pandas as pd

import group_readings as gr

ANSWERS = ("yes", "no", "unknown")
COLOURS = {"yes": "rgba(34,197,94,0.22)", "unknown": "rgba(245,158,11,0.22)", "no": None}
COLOURS_WITH_NO = {**COLOURS, "no": "rgba(239,68,68,0.10)"}


def _with_weekly(ctx, done: pd.DataFrame):
    """Weekly candles built from the finished days (Monday to Sunday), so weekly members answer too."""
    loader = ctx._candle_loader

    def load(kind, asset, tf):
        if tf != "1W":
            return loader(kind, asset, tf)
        from scoring import calculate_indicators

        raw = done[["open", "high", "low", "close", "volume"]]
        weekly = raw.resample("W-SUN", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        # The weekly readings need their indicator columns, as every other candle loader gives them; without them
        # weekly members (such as the weekly Trend) could never be read. The week holding the last day is still
        # forming unless that day is its Sunday, as in the live app.
        frame = calculate_indicators(weekly) if len(weekly) else weekly
        forming = pd.Series(False, index=frame.index)
        if len(frame) and pd.Timestamp(done.index[-1]).dayofweek != 6:
            forming.iloc[-1] = True
        frame = frame.assign(forming=forming)
        return {"frame": frame, "session": None, "source": "stored (weekly from daily)"}

    ctx._candle_loader = load
    return ctx


def context_at(frame: pd.DataFrame, kind: str, day: pd.Timestamp, asset_id: str):
    """The engine context at the close of `day` (its bar is finished, nothing later is seen)."""
    now = pd.Timestamp(day) + pd.Timedelta(days=1, minutes=10)
    if now.tzinfo is None:
        now = now.tz_localize("UTC")
    ctx, last = gr.stored_context(frame.loc[:pd.Timestamp(day)], kind, now, asset_id=asset_id)
    done = frame.loc[:last]
    return _with_weekly(ctx, done), last


def daily_answers(doc: dict, frame: pd.DataFrame, kind: str, asset_id: str, *, start=None,
                  subjects: dict | None = None, warmup: int = 60) -> list[tuple[str, str]]:
    """[(YYYY-MM-DD, answer)] for every finished day from `start` (default: after `warmup` bars).
    frame: daily bars with indicators (scoring.calculate_indicators). subjects: (kind, id) -> such a frame, for
    lines pinned to another asset."""
    import prism
    import signal_groups as sg

    subjects = subjects or {}
    index = frame.index
    first = index[min(warmup, len(index) - 1)] if start is None else pd.Timestamp(start)
    if first.tzinfo is None and index.tz is not None:
        first = first.tz_localize(index.tz)
    out = []
    for day in index[index >= first]:
        ctx, last = context_at(frame, kind, day, asset_id)
        if pd.Timestamp(last) != pd.Timestamp(day):
            continue

        def subject(k, i, day=day):
            other = subjects.get((k, i))
            if other is None:
                raise ValueError(f"No saved daily history for {i}.")
            return context_at(other, k, day, i)[0]

        try:
            result = sg.evaluate_set(doc, ctx, subject_context=subject)
            answer = prism.row("", result, "")["answer"]
        except Exception:
            answer = "unknown"
        out.append((pd.Timestamp(day).strftime("%Y-%m-%d"), answer if answer in ANSWERS else "unknown"))
    return out


def spans(days: list[tuple[str, str]], existing: list | None = None) -> list[list[str]]:
    """Join consecutive days with the same answer: [[first, last, answer], ...]. New days extend `existing`."""
    out = [list(s) for s in (existing or [])]
    for day, answer in days:
        if out and out[-1][2] == answer:
            out[-1][1] = day
        else:
            out.append([day, day, answer])
    return out


def through(span_list: list) -> str | None:
    return span_list[-1][1] if span_list else None


def answer_on(span_list: list, day: str) -> str | None:
    """The answer at the close of the latest worked-out day on or before `day` (YYYY-MM-DD)."""
    found = None
    for first, last, answer in span_list:
        if first > day:
            break
        found = answer if day <= last else answer
    return found


def colours_for(times_days: list[str], span_list: list, show_no: bool = False) -> list:
    """One colour (or None) per chart bar, from the answer that held on that bar's day."""
    palette = COLOURS_WITH_NO if show_no else COLOURS
    out, i = [], 0
    for day in times_days:
        while i + 1 < len(span_list) and span_list[i + 1][0] <= day:
            i += 1
        if not span_list or span_list[0][0] > day:
            out.append(None)
            continue
        out.append(palette[span_list[i][2]])
    return out


def answers_for(times_days: list[str], span_list: list) -> list:
    """One answer (or None) per chart bar."""
    out, i = [], 0
    for day in times_days:
        while i + 1 < len(span_list) and span_list[i + 1][0] <= day:
            i += 1
        out.append(None if not span_list or span_list[0][0] > day else span_list[i][2])
    return out


def summary(span_list: list) -> dict:
    """Days and episodes per answer, for the legend."""
    days = {a: 0 for a in ANSWERS}
    episodes = {a: 0 for a in ANSWERS}
    for first, last, answer in span_list:
        days[answer] += (pd.Timestamp(last) - pd.Timestamp(first)).days + 1
        episodes[answer] += 1
    return {"days": days, "episodes": episodes}


# ----------------------------------------------------------------------------------------------- stored spans

def asset_key(kind: str, asset_id: str) -> str:
    return f"{'crypto' if kind == 'crypto' else 'equity'}:{asset_id if kind == 'crypto' else str(asset_id).upper()}"


def load(supabase, hashes: list[str], keys: list[str]) -> dict:
    """(def hash, asset key) -> {"through", "spans"}; {} when the table is missing or unreadable."""
    if supabase is None or not hashes or not keys:
        return {}
    try:
        rows = (supabase.table("set_history").select("def_hash, asset_key, through, spans")
                .in_("def_hash", hashes).in_("asset_key", keys).execute().data or [])
    except Exception:
        return {}
    return {(r["def_hash"], r["asset_key"]): {"through": str(r["through"]), "spans": r.get("spans") or []}
            for r in rows}


def save(supabase, def_hash: str, key: str, span_list: list) -> bool:
    if supabase is None or not span_list:
        return False
    try:
        from market_store import MINIMAL

        supabase.table("set_history").upsert(
            {"def_hash": def_hash, "asset_key": key, "through": through(span_list), "spans": span_list},
            on_conflict="def_hash,asset_key", returning=MINIMAL).execute()
        return True
    except Exception:
        return False


def subjects_of(doc: dict) -> list[tuple[str, str]]:
    """Other assets the Set's lines are pinned to."""
    out = []
    for item in (doc.get("groups") or []) + (doc.get("standalone") or []):
        sub = item.get("subject")
        if sub and (sub.get("kind"), sub.get("id")) not in out:
            out.append((sub.get("kind"), sub.get("id")))
    return out


def bring_up_to_date(doc: dict, frame: pd.DataFrame, kind: str, asset_id: str, stored: dict | None,
                     subjects: dict | None = None) -> tuple[list, bool]:
    """(spans through the frame's last day, changed?). Only days after the stored ones are worked out."""
    span_list = list((stored or {}).get("spans") or [])
    last = pd.Timestamp(frame.index[-1]).strftime("%Y-%m-%d")
    done = through(span_list)
    if done and done >= last:
        return span_list, False
    start = None if not done else pd.Timestamp(done) + pd.Timedelta(days=1)
    new = daily_answers(doc, frame, kind, asset_id, start=start, subjects=subjects)
    return spans(new, span_list), bool(new)


# ----------------------------------------------------------------------------------------------- whole histories

_FRAMES: dict = {}


def full_daily(kind: str, asset_id: str) -> pd.DataFrame | None:
    """The asset's whole daily history with indicators, finished days only (Yahoo, "max"). Kept in memory for the
    day, shared by every account in this process."""
    import data_fetchers
    import signals_v2
    from scoring import calculate_indicators

    key = (kind, str(asset_id), pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d"))
    if key in _FRAMES:
        return _FRAMES[key]
    if kind == "crypto":             # a Yahoo pair such as BTC-USD (a bare "BTC" or "LINK" is a share, not the coin)
        coin = data_fetchers.resolve_crypto_id(asset_id)
        ticker = data_fetchers.YAHOO_TICKER_BY_ID.get(coin) or data_fetchers.YF_BY_COINGECKO_ID.get(coin)
        if ticker is None:
            try:
                symbol = data_fetchers._coingecko_symbol(coin)
                ticker = f"{symbol}-USD" if symbol else None
            except Exception:
                ticker = None
    else:
        ticker = str(asset_id).upper()
    frame = None
    if ticker:
        raw = data_fetchers._history_from_yahoo(ticker, "max")
        if raw is not None and len(raw) >= 80:
            raw.index = pd.to_datetime(raw.index, utc=True).normalize()
            raw = raw[~raw.index.duplicated(keep="last")]
            pos = signals_v2.last_completed_position(raw.index, kind)
            if pos is not None:
                frame = calculate_indicators(raw.iloc[: pos + 1])
    if len(_FRAMES) > 64:
        _FRAMES.clear()
    _FRAMES[key] = frame
    return frame


def history_for(supabase, doc: dict, kind: str, asset_id: str, frames=full_daily) -> list | None:
    """The Set's spans on one asset through its last finished day: stored ones brought up to date and saved."""
    from column_answers import def_hash

    frame = frames(kind, asset_id)
    if frame is None or frame.empty:
        return None
    h, key = def_hash(doc), asset_key(kind, asset_id)
    stored = load(supabase, [h], [key]).get((h, key))
    subjects = {}
    for sk, sid in subjects_of(doc):
        other = frames(sk, sid)
        if other is not None:
            subjects[(sk, sid)] = other
    span_list, changed = bring_up_to_date(doc, frame, kind, asset_id, stored, subjects)
    if changed:
        save(supabase, h, key, span_list)
    return span_list


def strip_rows(supabase, doc: dict, assets: list[tuple[str, str, str]], progress=None, frames=full_daily) -> dict:
    """Visualize History: one row per asset, {"rows": [{key, kind, id, name, spans}], "start", "end"}."""
    rows = []
    for n, (kind, asset_id, name) in enumerate(assets):
        if progress:
            progress(n, len(assets), name)
        try:
            span_list = history_for(supabase, doc, kind, asset_id, frames)
        except Exception:
            span_list = None
        rows.append({"key": asset_key(kind, asset_id), "kind": kind, "id": asset_id, "name": name,
                     "spans": span_list or []})
    firsts = [r["spans"][0][0] for r in rows if r["spans"]]
    lasts = [r["spans"][-1][1] for r in rows if r["spans"]]
    return {"rows": rows, "start": min(firsts) if firsts else None, "end": max(lasts) if lasts else None}


# ----------------------------------------------------------------------------------------------- quick first look

QUICK_DAYS = 400       # the last year, plus a little: the chart can open on 1Y while older years are worked out


def bounds(strip: dict) -> dict:
    firsts = [r["spans"][0][0] for r in strip["rows"] if r["spans"]]
    lasts = [r["spans"][-1][1] for r in strip["rows"] if r["spans"]]
    strip["start"] = min(firsts) if firsts else None
    strip["end"] = max(lasts) if lasts else None
    strip["pending"] = sum(1 for r in strip["rows"] if not r.get("full"))
    return strip


def quick_rows(supabase, doc: dict, assets: list[tuple[str, str, str]], progress=None, frames=full_daily) -> dict:
    """Visualize History, first look: assets whose history is saved come back whole (brought up to date with the new
    days); the others get just their last year, marked not "full" (complete_row does the rest, one at a time)."""
    from column_answers import def_hash

    h = def_hash(doc)
    keys = [asset_key(k, i) for k, i, _ in assets]
    stored = load(supabase, [h], keys)
    rows = []
    for n, (kind, asset_id, name) in enumerate(assets):
        if progress:
            progress(n, len(assets), name)
        key = asset_key(kind, asset_id)
        row = {"key": key, "kind": kind, "id": asset_id, "name": name, "spans": [], "full": True}
        try:
            frame = frames(kind, asset_id)
            if frame is None or frame.empty:
                rows.append(row)
                continue
            subjects = {(sk, sid): frames(sk, sid) for sk, sid in subjects_of(doc)}
            subjects = {k: v for k, v in subjects.items() if v is not None}
            if (h, key) in stored:
                row["spans"], changed = bring_up_to_date(doc, frame, kind, asset_id, stored[(h, key)], subjects)
                if changed:
                    save(supabase, h, key, row["spans"])
            else:
                start = frame.index[-1] - pd.Timedelta(days=QUICK_DAYS)
                row["spans"] = spans(daily_answers(doc, frame, kind, asset_id, start=start, subjects=subjects))
                row["full"] = False
        except Exception:
            pass
        rows.append(row)
    return bounds({"rows": rows})


def complete_row(supabase, doc: dict, strip: dict, frames=full_daily) -> str | None:
    """Work out the whole history of the next asset that only has its last year; returns its name (None when done)."""
    for row in strip["rows"]:
        if not row.get("full"):
            try:
                row["spans"] = history_for(supabase, doc, row["kind"], row["id"], frames) or row["spans"]
            except Exception:
                pass
            row["full"] = True
            bounds(strip)
            return row["name"]
    return None
