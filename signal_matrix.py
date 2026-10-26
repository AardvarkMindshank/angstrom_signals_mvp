"""Line the open asset's price up with each signal set.

Technical scores are replayed from the stored daily bars. Sentiment uses only
the readings already saved. A lead is how that signal lined up with the price
change that came after it.
"""

from __future__ import annotations

import itertools
import math
from datetime import datetime, timedelta

import pandas as pd

from scoring import calculate_indicators, compute_score

MATRIX_DAYS = 30
LEAD_HORIZONS = (1, 3, 7)
_MIN_PAIRS = 8


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


def build_matrix(frame, weight_sets, sentiment, horizon: int, days: int = MATRIX_DAYS) -> dict:
    """Price and one value per signal for each of the last days.

    weight_sets is (name, weights) in display order. sentiment maps a row name
    to (day, score) readings. Days before the first reading stay empty. After
    that, the last reading stays on each later price day until the next one.
    """
    indicated = frame
    if frame is None or getattr(frame, "empty", True):
        return _empty()
    if "rsi" not in frame.columns:
        indicated = calculate_indicators(frame)
    if indicated is None or len(indicated) < 15 or "close" not in indicated.columns:
        return _empty()

    start = max(14, len(indicated) - max(1, int(days)))
    dates = []
    closes = []
    rows = [{"name": name, "values": []} for name, _weights in weight_sets]
    for end in range(start, len(indicated)):
        window = indicated.iloc[: end + 1]
        close = _number(indicated.iloc[end].get("close"))
        if close is None:
            continue
        when = pd.Timestamp(indicated.index[end])
        dates.append(when.strftime("%Y-%m-%d"))
        closes.append(close)
        for slot, (_name, weights) in zip(rows, weight_sets):
            slot["values"].append(_score_of(compute_score(window, weights)))

    placed = sentiment if isinstance(sentiment, dict) else {}
    for name, points in placed.items():
        rows.append({"name": name, "values": _align(dates, points)})

    returns = _forward_returns(closes, horizon)
    for row in rows:
        row["lead"] = _correlation(row["values"], returns)
    mix = _best_mix(rows, returns)
    return {"dates": dates, "closes": closes, "rows": rows, "mix": mix, "horizon": int(horizon)}


def _empty() -> dict:
    return {"dates": [], "closes": [], "rows": [], "mix": None, "horizon": 1}


def _score_of(result) -> float | None:
    if not isinstance(result, dict) or result.get("label") == "Insufficient data":
        return None
    return _number(result.get("score"))


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
    """Plain counts for the TA score over this window.

    A case is a day whose score is on that side of the boundary and whose price
    that many days later is already in the window. Higher means the later close
    was above the close that day. Lower means it was below.
    """
    def level(value: float) -> str:
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return f"{number:.1f}"

    def sentence(prefix: str, counts: list[tuple[int, int, int]]) -> str:
        parts = []
        for horizon, hits, total in counts:
            unit = "day" if int(horizon) == 1 else "days"
            outcome = f"in {hits} of {total} cases" if total else "in none"
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
        for score, move in zip(scores or [], returns):
            if score is None or move is None:
                continue
            if score >= bull:
                high_total += 1
                if move > 0:
                    high_hits += 1
            if score <= bear:
                low_total += 1
                if move < 0:
                    low_hits += 1
        high.append((int(horizon), high_hits, high_total))
        low.append((int(horizon), low_hits, low_total))
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
