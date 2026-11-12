"""
The macro calendar for Tides: scheduled high-impact releases, each with its impact tier, and a "storm warning" flag
when one is near. Dates come from the official schedules (checked 12 Nov 2026):

- Federal Reserve: FOMC meetings 2026 and the tentative 2027 schedule (federalreserve.gov press release, 5 Sep 2025).
  The decision is at 14:00 New York on the second day.
- BLS: Consumer Price Index, Employment Situation (jobs) and Producer Price Index, all at 08:30 New York
  (bls.gov/schedule/news_release/cpi.htm, empsit.htm, ppi.htm).
- Added by hand: deadlines with no official schedule (a government funding deadline).

GDP, retail sales and Treasury auctions are the next to add (BEA, Census and TreasuryDirect schedules).

Tiers (pennants): 2 = major (Fed, CPI, jobs), 1 = notable (PPI), "flag" = an extreme or unusual event.
A storm warning means "a scheduled event is near"; it never forecasts what the event will do.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
WINDOW_BEFORE = timedelta(hours=24)       # default storm-warning window (decision 11, 12 Nov 2026)
WINDOW_AFTER = timedelta(hours=24)

KINDS = {
    "fomc": {"name": "Fed rate decision", "short": "Fed", "tier": 2, "icon": "🏛️",
             "why": "The Federal Reserve sets short-term interest rates; the biggest single scheduled mover."},
    "cpi": {"name": "CPI inflation", "short": "CPI", "tier": 2, "icon": "🛒",
            "why": "Consumer prices: the Fed's main input; moves rates, the dollar, gold and crypto."},
    "jobs": {"name": "Jobs report", "short": "Jobs", "tier": 2, "icon": "👷",
             "why": "US employment and wages: growth and wage-pressure signal (nonfarm payrolls)."},
    "ppi": {"name": "Producer prices", "short": "PPI", "tier": 1, "icon": "🏭",
            "why": "Prices paid by producers: an early read on inflation in the pipeline."},
    "deadline": {"name": "Deadline", "short": "Deadline", "tier": "flag", "icon": "⚠️",
                 "why": "A one-off deadline with no regular schedule (added by hand)."},
}

# (kind, date, New York time, reference, note)
EVENTS = (
    # Past Fed decisions, for the markers on the Tides timeline (Fed calendars 2024 to 2026).
    ("fomc", "2024-12-18", "14:00", "December 2024 meeting", ""),
    ("fomc", "2025-01-29", "14:00", "January 2025 meeting", ""),
    ("fomc", "2025-03-19", "14:00", "March 2025 meeting", ""),
    ("fomc", "2025-05-07", "14:00", "May 2025 meeting", ""),
    ("fomc", "2025-06-18", "14:00", "June 2025 meeting", ""),
    ("fomc", "2025-07-30", "14:00", "July 2025 meeting", ""),
    ("fomc", "2025-09-17", "14:00", "September 2025 meeting", ""),
    ("fomc", "2025-10-29", "14:00", "October 2025 meeting", ""),
    ("fomc", "2025-12-10", "14:00", "December 2025 meeting", ""),
    ("fomc", "2026-01-28", "14:00", "January meeting", ""),
    ("fomc", "2026-03-18", "14:00", "March meeting", ""),
    ("fomc", "2026-04-29", "14:00", "April meeting", ""),
    ("fomc", "2026-06-17", "14:00", "June meeting", ""),
    ("fomc", "2026-07-29", "14:00", "July meeting", ""),
    ("fomc", "2026-09-16", "14:00", "September meeting", ""),
    ("fomc", "2026-10-28", "14:00", "October meeting", ""),
    ("fomc", "2026-12-09", "14:00", "December meeting", ""),
    ("fomc", "2027-01-27", "14:00", "January meeting", "tentative"),
    ("fomc", "2027-03-17", "14:00", "March meeting", "tentative"),
    ("fomc", "2027-04-28", "14:00", "April meeting", "tentative"),
    ("fomc", "2027-06-09", "14:00", "June meeting", "tentative"),
    ("fomc", "2027-07-28", "14:00", "July meeting", "tentative"),
    ("fomc", "2027-09-15", "14:00", "September meeting", "tentative"),
    ("fomc", "2027-10-27", "14:00", "October meeting", "tentative"),
    ("fomc", "2027-12-08", "14:00", "December meeting", "tentative"),
    ("cpi", "2026-11-10", "08:30", "October 2026", ""),
    ("cpi", "2026-12-10", "08:30", "November 2026", ""),
    ("cpi", "2027-01-13", "08:30", "December 2026", ""),
    ("cpi", "2027-02-11", "08:30", "January 2027", ""),
    ("cpi", "2027-03-10", "08:30", "February 2027", ""),
    ("cpi", "2027-04-13", "08:30", "March 2027", ""),
    ("cpi", "2027-05-12", "08:30", "April 2027", ""),
    ("cpi", "2027-06-10", "08:30", "May 2027", ""),
    ("cpi", "2027-07-14", "08:30", "June 2027", ""),
    ("cpi", "2027-08-11", "08:30", "July 2027", ""),
    ("cpi", "2027-09-14", "08:30", "August 2027", ""),
    ("cpi", "2027-10-14", "08:30", "September 2027", ""),
    ("cpi", "2027-11-10", "08:30", "October 2027", ""),
    ("cpi", "2027-12-10", "08:30", "November 2027", ""),
    ("jobs", "2026-11-06", "08:30", "October 2026", ""),
    ("jobs", "2026-12-04", "08:30", "November 2026", ""),
    ("jobs", "2027-01-08", "08:30", "December 2026", ""),
    ("jobs", "2027-02-05", "08:30", "January 2027", ""),
    ("jobs", "2027-03-05", "08:30", "February 2027", ""),
    ("jobs", "2027-04-02", "08:30", "March 2027", ""),
    ("jobs", "2027-05-07", "08:30", "April 2027", ""),
    ("jobs", "2027-06-04", "08:30", "May 2027", ""),
    ("jobs", "2027-07-02", "08:30", "June 2027", ""),
    ("jobs", "2027-08-06", "08:30", "July 2027", ""),
    ("jobs", "2027-09-03", "08:30", "August 2027", ""),
    ("jobs", "2027-10-08", "08:30", "September 2027", ""),
    ("jobs", "2027-11-05", "08:30", "October 2027", ""),
    ("jobs", "2027-12-03", "08:30", "November 2027", ""),
    ("ppi", "2026-11-13", "08:30", "October 2026", ""),
    ("ppi", "2026-12-15", "08:30", "November 2026", ""),
    ("ppi", "2027-01-14", "08:30", "December 2026", ""),
    ("ppi", "2027-02-12", "08:30", "January 2027", ""),
    ("ppi", "2027-03-12", "08:30", "February 2027", ""),
    ("ppi", "2027-04-14", "08:30", "March 2027", ""),
    ("ppi", "2027-05-13", "08:30", "April 2027", ""),
    ("ppi", "2027-06-11", "08:30", "May 2027", ""),
    ("ppi", "2027-07-15", "08:30", "June 2027", ""),
    ("ppi", "2027-08-10", "08:30", "July 2027", ""),
    ("ppi", "2027-09-10", "08:30", "August 2027", ""),
    ("ppi", "2027-10-15", "08:30", "September 2027", ""),
    ("ppi", "2027-11-12", "08:30", "October 2027", ""),
    ("ppi", "2027-12-15", "08:30", "November 2027", ""),
    ("deadline", "2026-12-11", "00:00", "US government funding runs out", "added by hand"),
)


def _moment(day: str, clock: str) -> datetime:
    h, m = (int(x) for x in clock.split(":"))
    return datetime.fromisoformat(day).replace(hour=h, minute=m, tzinfo=NEW_YORK).astimezone(timezone.utc)


def events() -> list[dict]:
    out = []
    for kind, day, clock, ref, note in EVENTS:
        k = KINDS[kind]
        out.append({"kind": kind, "at": _moment(day, clock), "name": k["name"], "short": k["short"],
                    "tier": k["tier"], "icon": k["icon"], "why": k["why"], "reference": ref, "note": note})
    return sorted(out, key=lambda e: e["at"])


def upcoming(now: datetime | None = None, days: int = 21) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    return [e for e in events() if now - WINDOW_AFTER <= e["at"] <= now + timedelta(days=days)]


def storm_warning(now: datetime | None = None, majors_only: bool = False) -> dict | None:
    """The nearest event whose window (24 hours before to 24 hours after) contains now, or None."""
    now = now or datetime.now(timezone.utc)
    near = [e for e in events() if e["at"] - WINDOW_BEFORE <= now <= e["at"] + WINDOW_AFTER
            and (not majors_only or e["tier"] in (2, "flag"))]
    return min(near, key=lambda e: abs((e["at"] - now).total_seconds())) if near else None


def pennants(tier) -> str:
    """Maritime warning flags: one pennant notable, two major, a square flag extreme."""
    return {1: "🚩", 2: "🚩🚩", "flag": "🟥"}.get(tier, "")


def when_words(at: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    seconds = (at - now).total_seconds()
    if seconds < 0:
        hours = -seconds / 3600
        return f"{hours:.0f} hours ago" if hours < 48 else f"{hours / 24:.0f} days ago"
    hours = seconds / 3600
    if hours < 1:
        return "within the hour"
    if hours < 48:
        return f"in {hours:.0f} hours"
    return f"in {hours / 24:.0f} days"
