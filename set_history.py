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
        raw = done[["open", "high", "low", "close", "volume"]]
        weekly = raw.resample("W-SUN", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        return {"frame": weekly.assign(forming=False), "session": None, "source": "stored (weekly from daily)"}

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
