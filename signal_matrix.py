"""Line the open asset's price up with each signal.

Signals v2 readings (Trend, Stretch, Flow and the two named views) are replayed from the stored daily
bars, each day using only the bars up to that day. Sentiment uses only
the readings already saved. A lead is how that signal lined up with the price
change that came after it.
"""

from __future__ import annotations

import itertools
import math
from datetime import datetime, timedelta, timezone

import pandas as pd

import signals_v2

MATRIX_DAYS = 30
LEAD_HORIZONS = (1, 3, 7)
_MIN_PAIRS = 8
# Forward returns over a horizon of h bars overlap, so n pairs carry roughly
# n / h independent observations. Below this a lead is shown but flagged.
_MIN_EFFECTIVE = 8
# A boundary count needs at least this many cases before it is called a record.
_MIN_CASES = 5


def weekend_edges(dates) -> list[str]:
    """Friday and Monday in the window, so each weekend sits between two lines.

    A holiday uses the last weekday before Saturday and the first weekday after Sunday.
    """
    days = []
    for raw in dates or []:
        try:
            days.append(datetime.strptime(str(raw)[:10], "%Y-%m-%d").date())
        except ValueError:
            continue
    present = {day.isoformat() for day in days}
    marks = []
    seen = set()

    def add(day):
        key = day.isoformat()
        if key in present and key not in seen:
            seen.add(key)
            marks.append(key)

    for index, day in enumerate(days):
        if day.weekday() >= 5:
            continue
        nxt = days[index + 1] if index + 1 < len(days) else None
        prev = days[index - 1] if index else None
        starts = day.weekday() == 4
        ends = day.weekday() == 0
        if nxt is not None and (nxt - day).days > 1:
            span = [day + timedelta(days=step) for step in range(1, (nxt - day).days)]
            if any(item.weekday() == 5 for item in span):
                starts = True
        if prev is not None and (day - prev).days > 1:
            span = [prev + timedelta(days=step) for step in range(1, (day - prev).days)]
            if any(item.weekday() == 6 for item in span):
                ends = True
        if starts or ends:
            add(day)
    return marks


# Technical rows: (name, where the value sits in a signals_v2 result). All run from -100 to +100.
TECHNICAL_ROWS = (
    ("📈 Trend", ("clusters", "trend")),
    ("🎯 Stretch", ("clusters", "stretch")),
    ("🔊 Flow", ("clusters", "flow")),
    ("Trend-following view", ("lenses", "trend_following")),
    ("Mean-reversion view", ("lenses", "mean_reversion")),
)


def _reading(result: dict, path) -> float | None:
    if not isinstance(result, dict) or result.get("status") != "ok":
        return None
    group, key = path
    return _number(((result.get(group) or {}).get(key) or {}).get("percent"))


def build_matrix(
    frame,
    kind: str,
    sentiment,
    horizon: int,
    days: int = MATRIX_DAYS,
    include_mix: bool = False,
) -> dict:
    """Price and one value per signal for each of the last days.

    Every row is on -100..+100 (scale "reading"); sentiment rows are converted from their stored 0..100
    and marked "sentiment". sentiment maps a row name
    to (day, score) readings. Days before the first reading stay empty. After
    that, the last reading stays on each later price day until the next one.

    Each row carries its lead plus how much data stands behind it: pairs (days
    with both a signal and a later price), effective_n (pairs divided by the
    horizon, because overlapping returns are not independent), noise_floor (the
    size a correlation must pass to stand out from chance at that effective n)
    and reliable (enough effective data, and the lead passes the floor).

    include_mix is off by default. Searching every pair and triple of signals
    for the best correlation on 30 days mostly finds noise, so the result is
    only computed when asked for.
    """
    indicated = frame
    if frame is None or getattr(frame, "empty", True):
        return _empty()
    if "rsi" not in frame.columns:
        from scoring import calculate_indicators

        indicated = calculate_indicators(frame)
    if indicated is None or len(indicated) < 15 or "close" not in indicated.columns:
        return _empty()

    start = max(14, len(indicated) - max(1, int(days)))
    now_utc = datetime.now(timezone.utc)
    dates = []
    closes = []
    rows = [{"name": name, "values": [], "scale": "reading"} for name, _path in TECHNICAL_ROWS]
    for end in range(start, len(indicated)):
        window = indicated.iloc[: end + 1]
        close = _number(indicated.iloc[end].get("close"))
        if close is None:
            continue
        when = pd.Timestamp(indicated.index[end])
        dates.append(when.strftime("%Y-%m-%d"))
        closes.append(close)
        # A past day's own bar is finished, so judge "finished" at that day's end, not now.
        day_end = when.to_pydatetime().replace(tzinfo=None) + timedelta(days=1, hours=6)
        judged_at = min(pd.Timestamp(day_end, tz="UTC").to_pydatetime(), now_utc)
        result = signals_v2.score(window, kind, now=judged_at)
        for slot, (_name, path) in zip(rows, TECHNICAL_ROWS):
            slot["values"].append(_reading(result, path))

    placed = sentiment if isinstance(sentiment, dict) else {}
    for name, points in placed.items():
        # Sentiment is stored 0..100 and shown on -100..+100 like everything else (the lead is unchanged:
        # a correlation does not move when a series is rescaled).
        shown = [None if v is None else max(-100.0, min(100.0, v * 2.0 - 100.0)) for v in _align(dates, points)]
        rows.append({"name": name, "values": shown, "scale": "reading", "sentiment": True})

    returns = _forward_returns(closes, horizon)
    for row in rows:
        row["lead"] = _correlation(row["values"], returns)
        row.update(_support(row["values"], returns, row["lead"], horizon))
    mix = _best_mix(rows, returns) if include_mix else None
    return {"dates": dates, "closes": closes, "rows": rows, "mix": mix, "horizon": int(horizon)}


def _support(values, returns, lead, horizon: int) -> dict:
    """How much independent data is behind a lead, and whether it clears noise."""
    pairs = sum(1 for value, move in zip(values, returns) if value is not None and move is not None)
    effective = pairs / max(1, int(horizon))
    floor = 1.96 / math.sqrt(effective) if effective > 0 else None
    reliable = (
        lead is not None
        and floor is not None
        and effective >= _MIN_EFFECTIVE
        and abs(lead) >= floor
    )
    return {"pairs": pairs, "effective_n": effective, "noise_floor": floor, "reliable": reliable}


def _empty() -> dict:
    return {"dates": [], "closes": [], "rows": [], "mix": None, "horizon": 1}




def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or math.isinf(number):
        return None
    return number


def _align(dates, points) -> list[float | None]:
    """Put each reading on its day and keep it until a newer one.

    A reading dated on a day with no price bar still fills the next price day.
    Days before the first reading stay empty.
    """
    readings = []
    for item in points or []:
        if not isinstance(item, (tuple, list)) or len(item) < 2:
            continue
        day = str(item[0])[:10]
        score = _number(item[1])
        if day and score is not None:
            readings.append((day, score))
    readings.sort()
    values = []
    index = 0
    current = None
    for day in dates:
        while index < len(readings) and readings[index][0] <= day:
            current = readings[index][1]
            index += 1
        values.append(current)
    return values


def boundary_lines(
    scores,
    closes,
    bull: float = 70,
    bear: float = 30,
    horizons=LEAD_HORIZONS,
) -> list[str]:
    """Plain counts for one signal over this window (a reading line such as +50 / -50, or a score line).

    A case is a day whose score is on that side of the boundary and whose price
    that many days later is already in the window. Higher means the later close
    was above the close that day. Lower means it was below. Each count sits
    beside the base rate, the same move across every day with a later price,
    because a rising asset is higher most days whatever the score says. A side
    with fewer than _MIN_CASES cases is reported as too few to judge.
    """
    signed = float(bear) < 0

    def level(value: float) -> str:
        number = float(value)
        if signed:
            return f"{int(number):+d}" if number.is_integer() else f"{number:+.1f}"
        if number.is_integer():
            return str(int(number))
        return f"{number:.1f}"

    def sentence(prefix: str, counts: list[tuple[int, int, int, int, int]]) -> str:
        parts = []
        for horizon, hits, total, base_hits, base_total in counts:
            unit = "day" if int(horizon) == 1 else "days"
            if not total:
                outcome = "in none"
            elif total < _MIN_CASES:
                outcome = f"in {hits} of only {total} cases, too few to judge"
            else:
                outcome = f"in {hits} of {total} cases"
            if total and base_total:
                outcome += f" (all days: {base_hits} of {base_total})"
            parts.append(f"{int(horizon)} {unit} later {outcome}")
        if len(parts) == 1:
            body = parts[0]
        elif len(parts) == 2:
            body = f"{parts[0]} and {parts[1]}"
        else:
            body = ", ".join(parts[:-1]) + ", and " + parts[-1]
        return f"{prefix} {body}."

    high = []
    low = []
    for horizon in horizons:
        returns = _forward_returns(closes, horizon)
        high_hits = high_total = low_hits = low_total = 0
        up_days = down_days = known = 0
        for score, move in zip(scores or [], returns):
            if move is None:
                continue
            known += 1
            if move > 0:
                up_days += 1
            elif move < 0:
                down_days += 1
            if score is None:
                continue
            if score >= bull:
                high_total += 1
                if move > 0:
                    high_hits += 1
            if score <= bear:
                low_total += 1
                if move < 0:
                    low_hits += 1
        high.append((int(horizon), high_hits, high_total, up_days, known))
        low.append((int(horizon), low_hits, low_total, down_days, known))
    return [
        sentence(f"Above {level(bull)}, higher", high),
        sentence(f"At or below {level(bear)}, lower", low),
    ]


def _forward_returns(closes, horizon: int) -> list[float | None]:
    step = max(1, int(horizon))
    returns = []
    for index, close in enumerate(closes):
        later = index + step
        if later >= len(closes) or close in (None, 0):
            returns.append(None)
            continue
        nxt = closes[later]
        if nxt is None:
            returns.append(None)
            continue
        returns.append((nxt - close) / abs(close) * 100.0)
    return returns


def _correlation(values, returns) -> float | None:
    pairs = [
        (value, move)
        for value, move in zip(values, returns)
        if value is not None and move is not None
    ]
    if len(pairs) < _MIN_PAIRS:
        return None
    left = [item[0] for item in pairs]
    right = [item[1] for item in pairs]
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    numer = sum((item - mean_left) * (move - mean_right) for item, move in pairs)
    spread_left = math.sqrt(sum((item - mean_left) ** 2 for item in left))
    spread_right = math.sqrt(sum((move - mean_right) ** 2 for move in right))
    if spread_left == 0 or spread_right == 0:
        return None
    return numer / (spread_left * spread_right)


def _best_mix(rows, returns) -> dict | None:
    usable = [row for row in rows if row.get("lead") is not None]
    best_single = max((abs(row["lead"]) for row in usable), default=0.0)
    chosen = None
    for size in (2, 3):
        if len(usable) < size:
            continue
        for group in itertools.combinations(usable, size):
            combined = _average_rows(group)
            lead = _correlation(combined, returns)
            if lead is None or abs(lead) <= best_single:
                continue
            if chosen is None or abs(lead) > abs(chosen["lead"]):
                chosen = {
                    "names": [row["name"] for row in group],
                    "values": combined,
                    "lead": lead,
                }
    return chosen


def _average_rows(group) -> list[float | None]:
    length = len(group[0]["values"])
    combined = []
    for index in range(length):
        values = [row["values"][index] for row in group]
        if any(value is None for value in values):
            combined.append(None)
            continue
        combined.append(sum(values) / len(values))
    return combined
