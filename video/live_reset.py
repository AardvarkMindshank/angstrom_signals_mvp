"""Put the demo account back to a new account's state before the live-site videos are recorded (18 Nov 2026), so
every recording starts the same way and the "day 1" videos can build things from scratch.

Only the demo account is touched: the email must be DEMO_EMAIL and start with "demo@". It removes that account's own
Groups and Sets, its Prism scans (not the built-in alerts, which every account has), its funnels, its unsaved editor
drafts and its preferences row (watchlists and settings: the app makes a fresh one with the starting watchlists on
the next sign-in). The account itself, its sign-in and its NDA signature stay.

    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... DEMO_EMAIL=... python video/live_reset.py
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    from supabase import create_client

    email = str(os.environ.get("DEMO_EMAIL") or "").strip().lower()
    if not email.startswith("demo@"):
        sys.exit("DEMO_EMAIL must be the demo account (demo@...): nothing was changed.")
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    user = None
    page = 1
    while user is None:
        users = sb.auth.admin.list_users(page=page, per_page=200)
        if not users:
            break
        user = next((u for u in users if str(u.email or "").lower() == email), None)
        page += 1
    if user is None:
        sys.exit("The demo account was not found: nothing was changed.")
    uid = str(user.id)
    done = []
    for table, column, extra in (("analysis_configs", "owner_id", None), ("prism_scans", "owner_id", "custom"),
                                 ("funnels", "owner_id", None), ("editor_drafts", "owner_id", None),
                                 ("user_preferences", "user_id", None)):
        try:
            q = sb.table(table).delete().eq(column, uid)
            if extra == "custom":
                q = q.is_("builtin", "null")
            rows = q.execute().data or []
            done.append(f"{table}: {len(rows)} removed")
        except Exception as exc:
            done.append(f"{table}: not changed ({str(exc)[:120]})")
    print("Demo account reset. " + "; ".join(done))


if __name__ == "__main__":
    main()
