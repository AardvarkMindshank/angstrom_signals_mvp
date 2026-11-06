"""
Writes the browser harness for the Prism Scans board (checked by prism_board_check.js in CI).

The harness stands in for Streamlit: it gives the board the data the page would send (three made-up scans) and
records each action the board sends back, so a real browser can click, tap and drag through it.

    python prism_board_check.py --out out/prism_board
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import prism
import prism_board as pb
import prism_component as pc

NOW = pd.Timestamp("2026-11-06 03:00", tz="UTC")
ASSETS = [("crypto", "bitcoin", "Bitcoin"), ("crypto", "solana", "Solana"), ("crypto", "chainlink", "Chainlink"),
          ("equity", "COIN", "Coinbase (COIN)"), ("equity", "NVDA", "NVIDIA (NVDA)")]


def board_data() -> dict:
    doc = prism.demo_sets()["demo:agree"]
    saved = [{"id": "cfg1", "kind": "set", "name": "COIN leads BTC", "owner_id": "me",
              "versions": [{"version": 1, "body": doc}, {"version": 2, "body": doc}]}]
    choices = pb.set_choices(saved, "me")
    base = {"owner_id": "me", "set_body": doc, "alert_mode": "change", "snoozes": {}, "set_version": 1}
    scans = [
        {**base, "id": "s1", "name": "COIN leads BTC", "set_source": {"key": "saved:cfg1:1", "config": "cfg1",
                                                                        "version": 1},
         "schedule": {"kind": "close", "timeframe": "1D"}, "notify": {"channel": "instant", "on_yes": True},
         "paused": False, "assets": [{"group": "crypto"}]},
        {**base, "id": "s2", "name": "Pullback in an uptrend", "set_source": {"key": "demo:agree"},
         "schedule": {"kind": "close", "timeframe": "4H"}, "notify": {"channel": "digest", "on_yes": True},
         "paused": False, "assets": [{"group": "watchlist"}],
         "snoozes": {"equity:NVDA": (NOW + pd.Timedelta(days=2)).isoformat()}},
        {**base, "id": "s3", "name": "Breakout with volume", "set_source": {"key": "demo:agree"},
         "schedule": {"kind": "manual"}, "notify": {"channel": "app", "on_yes": True}, "paused": True,
         "assets": [{"group": "shares"}, {"kind": "crypto", "id": "solana"}]},
    ]
    runs = {"s1": [{"market": "crypto", "cutoff": f"2026-11-0{d}T00:00:00+00:00", "status": "ok",
                    "results": [{"asset": "Solana", "answer": "yes" if d % 2 else "no", "reason": "COIN Trend Bullish"},
                                {"asset": "Bitcoin", "answer": "no", "reason": "Trend already Bullish"}]}
                   for d in range(1, 7)]}
    latches = {"s1": ["crypto:solana"]}
    return {"library": pb.library(choices, ASSETS), "zones": pb.ZONES, "scheduled": pb.scheduled_count(scans),
            "max_scheduled": pb.MAX_SCHEDULED, "open_new": None,
            "scans": [pb.view(s, runs.get(s["id"], []), latches.get(s["id"], []), choices, ASSETS, NOW)
                      for s in scans]}


def page(data: dict) -> str:
    script = pc.JS.replace("export default function prismBoard(component)", "window.prismBoard = function prismBoard(component)")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Prism board check</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{pc.CSS} body{{font-family:system-ui,sans-serif;margin:16px;background:#fff;color:#111}}</style></head>
<body><div id="host"></div><script>
{script}
window.sent = [];
window.boardData = {json.dumps(data)};
window.prismBoard({{data: window.boardData, parentElement: document.getElementById("host"),
  setTriggerValue: (k, v) => window.sent.push([k, JSON.parse(v)])}});
window.ready = true;
</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="out/prism_board")
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "board.html").write_text(page(board_data()))
    print(f"wrote {out / 'board.html'}")


if __name__ == "__main__":
    main()
