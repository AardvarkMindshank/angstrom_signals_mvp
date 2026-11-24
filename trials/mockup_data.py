"""Mock-up data (24 Nov 2026), read only: the app's stored market sentiment cards exactly as saved, and today's facts
as the daily briefing gathers them. Written to out/mockup.json (public market data only)."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from supabase import create_client

import briefing


def main():
    db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    when = datetime.now(timezone.utc)
    rows = db.table("market_mood").select("market_key, sentiment_updated_at, sentiment_report").execute().data
    out = {"made_at": when.isoformat(), "facts": briefing.general_facts(db, when),
           "markets": {r["market_key"]: r for r in rows}}
    Path("out").mkdir(exist_ok=True)
    Path("out/mockup.json").write_text(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
