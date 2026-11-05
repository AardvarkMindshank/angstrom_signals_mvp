"""
Headline sentiment as Signal Library signals (docs/design/library_completion.md, sections 4 and 9).

    sentiment.market   the whole crypto or stock market (subject market:crypto or market:stocks)
    sentiment.asset    one watchlist asset

Read from sentiment_history (append-only, one row per update). Scores are stored on 0..100 and shown on
-100..+100 (score_colours.sentiment_value), the scale the app uses everywhere.
- No observation is missing data, never a neutral 0. A thin-news observation is reported as thin.
- Staleness (older than 36 hours) and the 7-day change are measured from the evaluation time: now, or the replay
  cutoff T.
- Availability: in a replay, an observation counts only from first_seen_at, the time the database received it
  (sql/2026-11-05_sentiment_first_seen.sql). recorded_at alone is not proof, because the writing function accepts
  times up to 30 days back. Without first_seen_at the signals are live only.
"""

from __future__ import annotations

import pandas as pd

from score_colours import sentiment_shown, sentiment_value

from .core import (
    CONFIRMED, MISSING, OBSERVATION, OK, SCOPE_ASSET, STALE, SignalResult, iso, signal,
)

STALE_HOURS = 36
SOURCE = "Google News headlines scored by an AI model (Angstrom headline sentiment)"
LIMITATIONS = ("AI-scored headlines, not validated as predictive. Days with thin news can swing the score. History "
               "starts on 3 Nov 2026 and is replayable only from when each score first reached the database.")


def subject_key(ctx) -> str:
    if ctx.kind == "market":
        return {"crypto": "crypto", "stocks": "stock"}.get(ctx.asset_id, ctx.asset_id)
    identity = str(ctx.asset_id or "").strip()
    return f"Stock|{identity.upper()}" if ctx.kind == "equity" else f"Crypto|{identity.lower()}"


def _point(row):
    shown = sentiment_value(row.get("score"))
    try:
        when = pd.Timestamp(row.get("recorded_at"))
        when = when.tz_localize("UTC") if when.tzinfo is None else when.tz_convert("UTC")
    except (TypeError, ValueError):
        return None
    return None if shown is None else (when, shown, row)


def _evaluate(ctx, label: str):
    key = subject_key(ctx)
    loaded = ctx.sentiment(key)
    if loaded.get("error"):
        return SignalResult(ref={}, subject=ctx.subject, status=MISSING, notes=[loaded["error"]])
    now = ctx.now
    points = sorted((p for p in (_point(r) for r in loaded.get("rows") or []) if p and p[0] <= now),
                    key=lambda p: p[0])
    if not points:
        return SignalResult(ref={}, subject=ctx.subject, status=MISSING,
                            notes=[f"No {label} sentiment recorded by {iso(now)}."])
    when, shown, row = points[-1]
    week_ago = [p for p in points if p[0] <= now - pd.Timedelta(days=7)]
    change = None if not week_ago else round(shown - week_ago[-1][1], 4)
    age_h = (now - when).total_seconds() / 3600
    coverage = row.get("coverage")
    value = {
        "score": round(shown, 4), "shown": sentiment_shown(row.get("score")),
        "score_stored_0_100": float(row.get("score")), "recorded_at": iso(when), "age_hours": round(age_h, 2),
        "change_7d": change, "coverage": coverage, "thin_news": coverage == "thin",
        "events": row.get("events"), "sources": row.get("sources"), "model": row.get("model"),
        "subject_key": key,
        "recent": [{"recorded_at": iso(p[0]), "score": round(p[1], 4)} for p in points[-10:]],
    }
    seen = row.get("first_seen_at")
    stale = age_h > STALE_HOURS
    notes = []
    if stale:
        notes.append(f"The newest score is {age_h:.0f} hours old (stale after {STALE_HOURS}).")
    if coverage == "thin":
        notes.append("This score rests on thin news (few independent stories); it is not a neutral reading.")
    return SignalResult(
        ref={}, subject=ctx.subject, status=STALE if stale else OK, confirmation=CONFIRMED, value=value,
        observed_at=iso(when), available_at=iso(seen) if seen else iso(when),
        evidence={"observations_read": len(points), "first_seen_recorded": seen is not None},
        provenance=[SOURCE + (f", model {row.get('model')}" if row.get("model") else "")], notes=notes)


COMMON = dict(category="sentiment", output=OBSERVATION, unit="-100..+100", timeframes=("1D",),
              requires=("sentiment",), limitations=LIMITATIONS,
              polarity="positive = headlines lean positive (descriptive)")


@signal(id="sentiment.market", version=1, name="Market headline sentiment", scope="market:crypto|stocks", **COMMON,
        calculation=("The latest stored headline-sentiment score for the whole crypto market (subject market:crypto) "
                     "or stock market (market:stocks), on -100..+100 (stored 0..100; shown = 2 x stored - 100), with "
                     "its time, coverage (thin or ok), model, the change from the newest score at least 7 days before "
                     "the evaluation time, and the last 10 scores. Stale after 36 hours."),
        interpretation="Whether recent market headlines read positive or negative. Descriptive.")
def sentiment_market(ctx, timeframe, params):
    return _evaluate(ctx, f"{ctx.asset_id}-market")


@signal(id="sentiment.asset", version=1, name="Asset headline sentiment", scope=SCOPE_ASSET, **COMMON,
        calculation=("The latest stored headline-sentiment score for this asset, on -100..+100 (stored 0..100), with "
                     "its time, coverage (thin or ok), model, the change from the newest score at least 7 days "
                     "before the evaluation time, and the last 10 scores. Stale after 36 hours."),
        interpretation="Whether recent headlines about this asset read positive or negative. Descriptive.")
def sentiment_asset(ctx, timeframe, params):
    return _evaluate(ctx, "asset")
