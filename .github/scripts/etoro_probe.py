"""eToro connection test for the Trade Logbook (22 Nov 2026). Reads the account's closed-trade history with a Read
key and prints ONLY a shape summary: how many trades, which fields eToro sends, and counts of copied, leveraged and
partly closed positions. It never prints trades, prices, profits, amounts, instruments or keys, because this
repository and its workflow logs are public.

Needs the secrets ETORO_API_KEY and ETORO_USER_KEY (entered by the account owner in GitHub, never in chat).
API: GET https://public-api.etoro.com/api/v1/trading/info/trade/history?minDate=...&page=...&pageSize=...
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from collections import Counter

import requests

URL = "https://public-api.etoro.com/api/v1/trading/info/trade/history"
PAGE_SIZE = int(os.environ.get("PAGE_SIZE") or 100)
MAX_PAGES = 200


def fetch_page(api_key: str, user_key: str, min_date: str, page: int) -> tuple[int, object]:
    headers = {"x-request-id": str(uuid.uuid4()), "x-api-key": api_key, "x-user-key": user_key,
               "Accept": "application/json"}
    r = requests.get(URL, headers=headers, params={"minDate": min_date, "page": page, "pageSize": PAGE_SIZE},
                     timeout=30)
    try:
        body = r.json()
    except ValueError:
        body = None
    return r.status_code, body


def items_of(body) -> list:
    """The trades in a response: a bare list as documented, or a list inside a wrapper object."""
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for value in body.values():
            if isinstance(value, list):
                return value
    return []


def summarise(trades: list) -> list[str]:
    """Shape only: counts and field names, nothing about what was traded or for how much."""
    fields = Counter(k for t in trades if isinstance(t, dict) for k in t)
    years = sorted({str(t.get("closeTimestamp") or "")[:4] for t in trades if isinstance(t, dict)} - {""})
    has = lambda name: sum(1 for t in trades if isinstance(t, dict) and t.get(name) not in (None, 0, "", False))
    leveraged = sum(1 for t in trades if isinstance(t, dict) and (t.get("leverage") or 1) > 1)
    lines = [f"Closed trades read: {len(trades)}",
             f"Years covered: {years[0]} to {years[-1]}" if years else "Years covered: none",
             f"Distinct instruments: {len({t.get('instrumentId') for t in trades if isinstance(t, dict)})}",
             f"Copied (socialTradeId set): {has('socialTradeId')}",
             f"Part of a larger position (parentPositionId set): {has('parentPositionId')}",
             f"Leveraged (leverage above 1): {leveraged}",
             f"With fees reported: {has('fees')}",
             "Fields eToro sends (how many trades carry each):"]
    lines += [f"  {name}: {count}" for name, count in sorted(fields.items())]
    return lines


COUNTS_URL = "https://public-api.etoro.com/api/v1/data/positions/closed-events/history"


def history_counts(api_key: str, user_key: str) -> None:
    """eToro's own count of closed positions by year and asset type: shows how far back its records go."""
    headers = {"x-request-id": str(uuid.uuid4()), "x-api-key": api_key, "x-user-key": user_key,
               "Accept": "application/json"}
    r = requests.get(COUNTS_URL, headers=headers, params={"pageSize": 500}, timeout=30)
    if r.status_code != 200:
        print(f"History counts: eToro answered HTTP {r.status_code}")
        return
    rows = (r.json() or {}).get("results") or []
    print("eToro's own count of closed positions, by year and asset type:")
    for row in rows:
        print(f"  {row.get('closeYear')} {row.get('assetType')}: {row.get('closedPositionEvents')}")
    if not rows:
        print("  none")


def by_windows(api_key: str, user_key: str, years: int = 16) -> None:
    """eToro support (25 Nov 2026): each request must cover under a year from minDate, so read the history in windows
    of 364 days going back. Prints counts per window only."""
    from datetime import date, timedelta

    seen: set = set()
    start = date.today() - timedelta(days=365)
    print("Windows of under a year (eToro support's advice):")
    for k in range(years):
        min_date = (start - timedelta(days=364 * k)).isoformat()
        got: list = []
        for page in range(1, MAX_PAGES + 1):
            status, body = fetch_page(api_key, user_key, min_date, page)
            if status != 200:
                print(f"  minDate {min_date} page {page}: HTTP {status}")
                break
            batch = [b for b in items_of(body) if isinstance(b, dict)]
            got += batch
            if len(batch) < PAGE_SIZE:
                break
        ids = {t.get("positionId") or t.get("positionID") for t in got}
        new = ids - seen
        seen |= ids
        closes = sorted(str(t.get("closeTimestamp") or "")[:10] for t in got if t.get("closeTimestamp"))
        span = f"closes {closes[0]} to {closes[-1]}" if closes else "no closes"
        print(f"  minDate {min_date}: {len(got)} trades, {len(new)} not seen in a later window, {span}")
    print(f"Distinct positions across all windows: {len(seen)}")


def my_permissions(api_key: str, user_key: str) -> None:
    """GET /me: the permission scopes of this key (names only; no account ids)."""
    headers = {"x-request-id": str(uuid.uuid4()), "x-api-key": api_key, "x-user-key": user_key,
               "Accept": "application/json"}
    r = requests.get("https://public-api.etoro.com/api/v1/me", headers=headers, timeout=30)
    if r.status_code != 200:
        print(f"Permissions (/me): eToro answered HTTP {r.status_code}")
        return
    body = r.json() if r.content else {}
    def scopes(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if any(w in k.lower() for w in ("scope", "permission")):
                    yield k, v
                else:
                    yield from scopes(v)
    found = list(scopes(body))
    print("Permissions (/me): " + ("; ".join(f"{k}: {v}" for k, v in found) if found else
                                   f"no scope field; top-level fields {sorted(body) if isinstance(body, dict) else type(body).__name__}"))


def request_ids(api_key: str, user_key: str) -> None:
    """For eToro support (25 Nov 2026): the x-request-id and UTC time of two calls, with the trade count only."""
    from datetime import datetime, timezone

    print("Request IDs for eToro support:")
    for min_date in ("2025-11-25", "2010-12-14"):
        rid = str(uuid.uuid4())
        at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        r = requests.get(URL, headers={"x-request-id": rid, "x-api-key": api_key, "x-user-key": user_key,
                                       "Accept": "application/json"},
                         params={"minDate": min_date, "page": 1, "pageSize": PAGE_SIZE}, timeout=30)
        try:
            n = len(items_of(r.json()))
        except ValueError:
            n = 0
        print(f"  minDate={min_date} page=1 pageSize={PAGE_SIZE}: x-request-id {rid}, sent {at}, HTTP {r.status_code}, {n} trades")


def _one(rid, api_key, user_key, min_date, page):
    try:
        return requests.get(URL, headers={"x-request-id": rid, "x-api-key": api_key, "x-user-key": user_key,
                                          "Accept": "application/json"},
                            params={"minDate": min_date, "page": page, "pageSize": PAGE_SIZE}, timeout=120)
    except requests.RequestException:
        return None


def all_pages(api_key: str, user_key: str, min_date: str) -> None:
    """eToro support (26 Nov 2026): page on until an EMPTY page, not until a short one. Prints, per page, the
    x-request-id, the time, the HTTP status and row counts only. A 504 (eToro's server timing out) is tried again."""
    from datetime import datetime, timezone
    seen: set = set()
    trades: list = []
    print(f"All pages from minDate={min_date}, pageSize={PAGE_SIZE}, until an empty page:")
    for page in range(1, MAX_PAGES + 1):
        r = None
        for attempt in range(3):
            if attempt:
                time.sleep(10)
            rid = str(uuid.uuid4())
            at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            r = _one(rid, api_key, user_key, min_date, page)
            if r is not None and r.status_code != 504:
                break
            print(f"  page {page}: x-request-id {rid}, sent {at}, " + ("no answer" if r is None else "HTTP 504"))
        if r is None or r.status_code != 200:
            break
        try:
            batch = [t for t in items_of(r.json()) if isinstance(t, dict)]
        except ValueError:
            batch = []
        ids = {t.get("positionId") or t.get("positionID") for t in batch}
        new = ids - seen
        seen |= ids
        trades += [t for t in batch if (t.get("positionId") or t.get("positionID")) in new]
        closes = sorted(str(t.get("closeTimestamp") or "")[:10] for t in batch if t.get("closeTimestamp"))
        span = f", closes {closes[0]} to {closes[-1]}" if closes else ""
        print(f"  page {page}: x-request-id {rid}, sent {at}, HTTP 200, {len(batch)} rows, {len(new)} new{span}")
        if not batch or (not new and page > 3):
            break
    print(f"Distinct positions: {len(seen)}")
    print("\n".join(summarise(trades)[:7]))


def main() -> int:
    api_key, user_key = os.environ.get("ETORO_API_KEY", ""), os.environ.get("ETORO_USER_KEY", "")
    if not api_key or not user_key:
        print("Missing secrets: add ETORO_API_KEY and ETORO_USER_KEY in GitHub (Settings, Secrets, Actions).")
        return 1
    min_date = os.environ.get("MIN_DATE") or "2010-01-01"
    if os.environ.get("MODE") == "pages":
        all_pages(api_key, user_key, min_date)
        return 0
    trades: list = []
    for page in range(1, MAX_PAGES + 1):
        status, body = fetch_page(api_key, user_key, min_date, page)
        if status != 200:
            detail = body.get("message") or body.get("error") if isinstance(body, dict) else ""
            print(f"Page {page}: eToro answered HTTP {status}. {str(detail or '')[:160]}")
            if status in (401, 403):
                print("The key was refused: check that both keys are for the real account and have Read permission.")
            if page == 1:
                return 1
            break
        batch = items_of(body)
        if page == 1:
            shape = "list" if isinstance(body, list) else f"object with keys {sorted(body)}" if isinstance(body, dict) else "empty"
            print(f"Response shape: {shape}")
        trades += batch
        if len(batch) < PAGE_SIZE:
            break
    print(f"Pages read: {page} (page size {PAGE_SIZE})")
    print("\n".join(summarise(trades)))
    request_ids(api_key, user_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
