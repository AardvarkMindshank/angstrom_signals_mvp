"""Dry run of capital-flow collection against the live feeds (no database, nothing stored).

Confirms each active source still parses: row counts, date range, the latest values, and the required
attribution. Run in GitHub Actions (the feeds are not reachable from every environment).

    python capital_flows_check.py --out out
"""

from __future__ import annotations

import argparse
from pathlib import Path

import capital_flows as cf


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    lines = ["# Capital flows dry run (live feeds, nothing stored)", ""]
    failed = False
    for source in cf.active_sources():
        spec = cf.SOURCES[source]
        try:
            rows = cf.fetch(source)
        except Exception as exc:
            lines += [f"## {spec['name']}: FAILED", "", str(exc)[:300], ""]
            failed = True
            continue
        if not rows:
            lines += [f"## {spec['name']}: no rows parsed (format change?)", ""]
            failed = True
            continue
        dates = sorted({r["observed_date"] for r in rows})
        series = sorted({(r["series"], r["subject"]) for r in rows})
        headline = [r for r in rows if r["subject"] in ("BTC", "ALL") and r["series"] in ("etf_net_flow", "stablecoin_supply")]
        headline.sort(key=lambda r: r["observed_date"])
        lines += [f"## {spec['name']}", "",
                  f"- Rows: {len(rows)}; days: {len(dates)} ({dates[0]} to {dates[-1]}); series: {len(series)}",
                  f"- Licence: {spec['licence']}; commercial use: {spec['commercial_use']}; "
                  f"redistribution: {spec['redistribution']}",
                  "- Latest values:"]
        lines += [f"  - {r['observed_date']} {r['series']} {r['subject']}: {r['value']:,.0f} {r['unit']}" for r in headline[-5:]]
        lines.append("")
    text = "\n".join(lines) + "\n"
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "capital_flows.md").write_text(text)
    print(text)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
