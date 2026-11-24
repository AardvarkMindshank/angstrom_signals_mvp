"""Trial (24 Nov 2026), saves nothing: which articles each market's sentiment would pick, the current way and a new
way (several searches, ranked by how widely a story was reported in the last 24 hours), and the story of the day an
AI names from the new pick plus the day's actual moves. Public headlines only."""
import json
import time
from datetime import datetime, timezone

import ai_providers
import briefing
import news_filter
import sentiment

import re
# Pages that only list a price or a routine event are not news (trial 1: "ETH price at 6 PM CST", "Current price of
# Bitcoin for November 23", "Rings the Nasdaq opening bell").
NOT_NEWS = re.compile(r"\bprice (at|today|for|now)\b|current price of|live price|price chart|to usd\b|"
                      r"\bprice (index|quote)\b|rings? the .*(opening|closing) bell", re.I)

NEW = {
    "stock": ["stock market today", "Wall Street stocks", "Nasdaq", "S&P 500"],
    "crypto": ["crypto market today", "Bitcoin news", "crypto news", "crypto ETF"],
}
MOVES = {"stock": [("equity", "SPY", "S&P 500"), ("equity", "QQQ", "Nasdaq 100")],
         "crypto": [("crypto", "bitcoin", "Bitcoin"), ("crypto", "ethereum", "Ether")]}


def show(rows, title):
    print(f"\n  {title}")
    for i, r in enumerate(rows, 1):
        print(f"   {i}. [{r.get('published_at', '')[:16]}] x{1 + r.get('also_reported', 0)} "
              f"{r.get('title', '')[:110]} ({r.get('source', '')})")


def new_pick(key, now):
    raw = []
    for q in NEW[key]:
        try:
            raw += sentiment._fetch_raw(q)
        except Exception as exc:
            print(f"  search failed: {q}: {exc}")
    dropped = [r for r in raw if NOT_NEWS.search(str(r.get("title") or ""))]
    raw = [r for r in raw if not NOT_NEWS.search(str(r.get("title") or ""))]
    print(f"  Dropped as not news: {len(dropped)}, e.g. " + "; ".join(str(r.get('title'))[:60] for r in dropped[:3]))
    rows, _ = news_filter.clean_headlines(raw, now, {}, 400)
    day = now - 86400

    def rank(r):
        stamp = datetime.fromisoformat(r["published_at"]).timestamp()
        return (stamp >= day, r.get("also_reported", 0), stamp)

    return sorted(rows, key=rank, reverse=True)[:8], len(raw)


def main():
    now = time.time()
    when = datetime.now(timezone.utc)
    for spec in sentiment.MACRO_MOODS:
        key = spec["key"]
        print(f"\n=== {spec['label']} ===")
        old, _ = sentiment.gather_headlines(spec["query"], market=True)
        show(old, f"CURRENT way (one search: \"{spec['query']}\", 8 newest)")
        new, n = new_pick(key, now)
        show(new, f"NEW way ({len(NEW[key])} searches, {n} results, ranked by last-24h coverage)")
        moves = []
        for kind, asset, name in MOVES[key]:
            m = briefing._candle_moves(kind, asset, None, when)
            moves.append(f"{name}: {m.get('change_1d')}% on {m.get('last_day')}")
        print("\n  Actual moves: " + "; ".join(moves))
        lines = "\n".join(f"{i}. {r['title']} ({r.get('source')}, carried by {1 + r.get('also_reported', 0)} outlets)"
                          for i, r in enumerate(new, 1))
        ask = (f"These are today's most widely reported {spec['label'].lower()} headlines, and the market's actual "
               f"latest moves ({'; '.join(moves)}). Name the single story that best explains what is moving this "
               "market now. Reply with JSON only: {\"index\": n, \"why\": \"one plain sentence\", "
               "\"explains_moves\": true|false}. If none of the headlines explains the moves, set explains_moves false.\n"
               + lines)
        try:
            text, _ = ai_providers.chat("grok", "You pick the lead market story from headlines. Facts only.",
                                        [{"role": "user", "content": ask}], max_tokens=300, json_only=True)
            print("  Story of the day (Grok): " + text.strip())
        except Exception as exc:
            print(f"  Story of the day failed: {exc}")


if __name__ == "__main__":
    main()
