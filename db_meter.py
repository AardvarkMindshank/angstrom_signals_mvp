"""📏 How much each part of Angstrom asks of the database (17 Nov 2026).

Supabase's free plan allows 5 GB of data out a month and 1 GB of logs, and every request writes a log line. In
November both went over, so this counts, per table or database function, the requests made and the bytes that came
back. It wraps the web library every Supabase call goes through (httpx), so nothing else changes.

    import db_meter; db_meter.install()      # once, at start
    db_meter.report("alerts run")            # a short table in the job's log

The app shows the same counts in Admin → Page timing.
"""

from __future__ import annotations

import re
import threading

_LOCK = threading.Lock()
_STATS: dict[str, list[int]] = {}         # "GET asset_market" -> [requests, bytes]
_INSTALLED = [False]
_PATH = re.compile(r"/(rest|auth|storage|functions)/v1/(rpc/)?([^/?]+)")


def _key(request) -> str | None:
    url = str(request.url)
    if "supabase" not in url:
        return None
    found = _PATH.search(url)
    if not found:
        return f"{request.method} other"
    kind, rpc, name = found.groups()
    if kind == "rest":
        name = f"rpc {name}" if rpc else name
    else:
        name = f"{kind} {name}"
    return f"{request.method} {name}"


def install() -> None:
    """Count every Supabase request from now on (safe to call more than once)."""
    if _INSTALLED[0]:
        return
    try:
        import httpx
    except ImportError:
        return
    original = httpx.Client.send

    def send(self, request, *args, **kwargs):
        response = original(self, request, *args, **kwargs)
        try:
            key = _key(request)
            if key:
                size = len(response.content or b"")
                with _LOCK:
                    entry = _STATS.setdefault(key, [0, 0])
                    entry[0] += 1
                    entry[1] += size
        except Exception:
            pass
        return response

    httpx.Client.send = send
    _INSTALLED[0] = True


def snapshot() -> dict[str, tuple[int, int]]:
    with _LOCK:
        return {k: (v[0], v[1]) for k, v in _STATS.items()}


def since(before: dict) -> dict[str, tuple[int, int]]:
    """What was asked between an earlier snapshot and now."""
    now = snapshot()
    out = {}
    for key, (n, size) in now.items():
        n0, s0 = before.get(key, (0, 0))
        if n > n0:
            out[key] = (n - n0, size - s0)
    return out


def totals(stats: dict) -> tuple[int, int]:
    return sum(v[0] for v in stats.values()), sum(v[1] for v in stats.values())


def lines(stats: dict, top: int = 15) -> list[str]:
    """Biggest first: 'GET asset_market: 12 requests, 1,834 KB'."""
    ordered = sorted(stats.items(), key=lambda kv: (kv[1][1], kv[1][0]), reverse=True)
    return [f"{key}: {n} request{'s' if n != 1 else ''}, {size / 1024:,.0f} KB" for key, (n, size) in ordered[:top]]


def report(label: str, stats: dict | None = None) -> None:
    stats = snapshot() if stats is None else stats
    n, size = totals(stats)
    print(f"📏 Database use, {label}: {n} requests, {size / 1024:,.0f} KB")
    for line in lines(stats):
        print("   " + line)
