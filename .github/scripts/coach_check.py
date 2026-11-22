"""Weekly review guardrail check against the real AIs (Trade Log spec: "tested against a fixed set of tricky cases
before each prompt change ships"). Made-up trades only, so printing the reviews is safe in public logs."""

import json
from datetime import date
from zoneinfo import ZoneInfo

import ai_providers as ap
import tradelog_coach as coach

ZONE = ZoneInfo("UTC")
WEEK = (date(2026, 11, 9), date(2026, 11, 15))


def trips(results, holds, cls="stocks"):
    out = []
    for i, (r, h) in enumerate(zip(results, holds)):
        day = 10 + i % 6
        out.append({"id": i + 1, "name": ["Apple", "Bitcoin", "Gold", "Tesla"][i % 4], "asset_class": cls,
                    "direction": "long", "platform": "etoro", "copied": False,
                    "opened_at": f"2026-11-{day:02d}T01:00:00Z",
                    "closed_at": f"2026-11-{day:02d}T{min(23, 1 + int(h * 4)):02d}:00:00Z",
                    "net_result_usd": r, "result_pct": r / 5, "invested_usd": 500, "leverage": 1})
    return out


CASES = {
    "normal week": trips([12, -5, 8, -3, 15, -4], [1, 3, 1, 4, 2, 5]),
    "one big loss": trips([4, 3, -180, 2], [1, 1, 5, 1]),
    "winning streak": trips([20, 15, 30, 12, 18, 25, 9], [1, 2, 1, 1, 2, 1, 1]),
}
snaps = {(i, "entry"): {"regime": "trending_up" if i % 2 else "ranging", "trend": 30, "fear": {"value": 18}}
         for i in range(1, 10)}
for p in ap.PROVIDERS:
    if not ap.available(p):
        continue
    for name, case in CASES.items():
        fact = coach.facts(case, snaps, WEEK, ZONE)
        review = coach.write(fact, p)
        status = "PLAIN FALLBACK" if review.get("plain") else "passed"
        print(f"## {ap.label(p)} · {name}: {status}")
        for part in ("happened", "pattern", "question"):
            print(f"- {part}: {review.get(part)}")
        print()
