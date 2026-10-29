"""Keep the signed-in database session fresh while a page stays open.

A sign-in token lasts about an hour. The page can sit open longer than that and keep
redrawing small pieces of itself, and those redraws reuse the client made at the last full
load. Once its token ran out, every shared read came back empty with no message: logos,
watching counts, sentiment and earnings dates all went blank until the person logged out
and in again.

FreshClient wraps the database client. Before each query it looks at when the token runs
out and, if that is near, swaps in a new one and stores it for the next page load.
It only does this from the page's own thread. A background job never refreshes, because a
refresh token works once and a second use of it would end the login.
"""

from __future__ import annotations

import base64
import json
import threading
import time

REFRESH_MARGIN_SECONDS = 120
_LOCK = threading.Lock()
_QUERY_METHODS = ("table", "from_", "rpc")


def token_expiry(token) -> float | None:
    """When a sign-in token runs out, in seconds since 1970. None if it cannot be read."""
    try:
        payload = str(token).split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp")
        return float(exp) if exp is not None else None
    except Exception:
        return None


def needs_refresh(token, now: float | None = None, margin: float = REFRESH_MARGIN_SECONDS) -> bool:
    expiry = token_expiry(token)
    if expiry is None:
        return False
    return expiry - (time.time() if now is None else now) < margin


class FreshClient:
    def __init__(self, client, get_tokens, store_tokens, in_page_thread=lambda: True, skip_refresh=lambda refresh: False, on_failure=lambda exc: None):
        self._client = client
        self._get = get_tokens
        self._store = store_tokens
        self._in_page = in_page_thread
        self._skip = skip_refresh
        self._failed = on_failure

    def _ensure_fresh(self) -> None:
        try:
            if not self._in_page():
                return
            access, refresh = self._get()
            if not access or not refresh or self._skip(refresh) or not needs_refresh(access):
                return
            with _LOCK:
                access, refresh = self._get()
                if not needs_refresh(access):
                    return
                restored = self._client.auth.set_session(access, refresh)
                session = getattr(restored, "session", None)
                if session is not None and session.access_token and session.refresh_token:
                    self._client.postgrest.auth(session.access_token)
                    self._store(session.access_token, session.refresh_token)
        except Exception as exc:
            print(f"Could not refresh the database session: {exc}")
            self._failed(exc)

    def __getattr__(self, name):
        if name in _QUERY_METHODS:
            self._ensure_fresh()
        return getattr(self._client, name)
