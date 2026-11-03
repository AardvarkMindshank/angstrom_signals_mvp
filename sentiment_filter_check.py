"""Dry run of the headline filter on live Google News (no model calls, nothing stored).

For a few assets and both markets: how many headlines the feed returned, what each rule removed,
the coverage level, and the headlines that would be scored. Run in GitHub Actions (the feed is not
reachable from every environment).

    python sentiment_filter_check.py --out out
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import news_filter as nf
import sentiment as se

SEARCHES = [
    ("Crypto", "Bitcoin", "BTC"), ("Crypto", "Ethereum", "ETH"), ("Crypto", "Sui", "SUI"),
    ("Crypto", "Near Protocol", "NEAR"), ("Stock", "Apple Inc.", "AAPL"), ("Stock", "NVIDIA Corporation", "NVDA"),
    ("Stock", "Bank of America Corp", "BAC"), ("Stock", "Tesla, Inc.", "TSLA"),
]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    lines = ["# Headline filter dry run (live Google News, no model calls)", "",
             "| Search | Feed | Junk | Stale/undated | Off-topic | Same story | Publisher cap | Kept | Sources | Coverage |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    detail = []
    queries = [(se.sentiment_query(kind, name, ticker), False) for kind, name, ticker in SEARCHES]
    queries += [(spec["query"], True) for spec in se.MACRO_MOODS]
    for query, market in queries:
        try:
            raw = [x for search in ([query] if market else se.asset_searches(query)) for x in se._fetch_raw(search)]
        except Exception as exc:
            lines.append(f"| {query} | fetch failed: {str(exc)[:60]} |||||||||")
            continue
        kept, st = nf.clean_headlines(raw, time.time(), {} if market else nf.asset_terms(query), 8)
        lines.append(f"| {query} | {st['candidates']} | {st['junk']} | {st['stale'] + st['undated']} | "
                     f"{st['irrelevant']} | {st['duplicates']} | {st['same_source_cap']} | {st['events']} | "
                     f"{st['sources']} | {st['level']} |")
        detail += ["", f"## {query}", ""]
        detail += [f"- {k['source']}: {k['title']}" + (f" (also {k['also_reported']} more)" if k.get("also_reported") else "")
                   for k in kept]
        time.sleep(1)
    text = "\n".join(lines + detail) + "\n"
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "headline_filter.md").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
