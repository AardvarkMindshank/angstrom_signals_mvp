"""Mock-up data (24 Nov 2026), saves nothing to the app: today's facts as the daily briefing gathers them, and each
market's sentiment report scored exactly as the app scores it, but from the new article pick. Written to
out/mockup.json (public market data only)."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from supabase import create_client

import ai_providers
import briefing
import sentiment
import news_trial as trial


def main():
    db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    now, when = time.time(), datetime.now(timezone.utc)
    out = {"made_at": when.isoformat(), "facts": briefing.general_facts(db, when), "markets": {}}
    real = sentiment.gather_headlines
    for spec in sentiment.MACRO_MOODS:
        key = spec["key"]
        picks, _ = trial.new_pick(key, now)
        stats = {"candidates": len(picks)}
        sentiment.gather_headlines = lambda q, market=False, limit=8, _p=picks, _s=stats: (_p, _s)
        report = sentiment.analyze_market_mood(key, spec["label"], spec["query"], True, force=True)
        sentiment.gather_headlines = real
        moves = []
        for kind, asset, name in trial.MOVES[key]:
            m = briefing._candle_moves(kind, asset, None, when)
            moves.append({"name": name, "change_1d": m.get("change_1d"), "day": m.get("last_day")})
        lines = "\n".join(f"{i}. {r['title']} ({r.get('source')}, carried by {1 + r.get('also_reported', 0)} outlets)"
                          for i, r in enumerate(picks, 1))
        ask = (f"These are today's most widely reported {spec['label'].lower()} headlines, and the market's actual "
               f"latest moves ({json.dumps(moves)}). Name the single story that best explains what is moving this "
               "market now. Reply with JSON only: {\"index\": n, \"why\": \"one plain sentence\", "
               "\"explains_moves\": true|false}. If none of the headlines explains the moves, set explains_moves false.\n"
               + lines)
        text, _ = ai_providers.chat("grok", "You pick the lead market story from headlines. Facts only.",
                                    [{"role": "user", "content": ask}], max_tokens=300, json_only=True)
        out["markets"][key] = {"label": spec["label"], "report": report, "moves": moves, "lead": text}
        print(spec["label"], "score", report.get("score"), "ok", report.get("ok"), "lead", text[:160])
    Path("out").mkdir(exist_ok=True)
    Path("out/mockup.json").write_text(json.dumps(out, default=str, indent=1))


if __name__ == "__main__":
    main()
