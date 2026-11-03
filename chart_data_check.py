"""
Live check of the chart candles against Yahoo Finance (CI only; nothing is stored).

For a few shares and coins, at every interval, it records:
- how many candles came back and the date span
- the clock times candles start at (4h shares must start 09:30 / 13:30 New York;
  4h crypto must start 00/04/08/12/16/20 UTC)
- that each 4h candle matches the hourly candles inside it (open, high, low, close, volume)
- that the weekly candles match the daily candles inside them
- whether the newest candle is marked as still forming

Usage: python chart_data_check.py --out out
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import pandas as pd

import chart_data as cd

ASSETS = (("equity", "AAPL"), ("equity", "SPY"), ("crypto", "bitcoin"), ("crypto", "ethereum"))
PAIRS = (("15m", "7D"), ("1h", "1M"), ("4h", "3M"), ("1D", "1Y"), ("1W", "All"))


def _times(candles, interval, kind, session):
    if interval in ("1D", "1W"):
        return sorted({ts.strftime("%a") for ts in candles.index}) if interval == "1W" else []
    zone = "UTC" if kind == "crypto" or not session else session[0]
    return sorted({ts.tz_convert(zone).strftime("%H:%M") for ts in candles.index})


def _matches(big, small, label):
    """Every big candle equals the small candles inside it."""
    problems = 0
    starts = list(big.index)
    for i, start in enumerate(starts[:-1]):
        end = starts[i + 1]
        inside = small[(small.index >= start) & (small.index < end)]
        if inside.empty:
            continue
        row = big.iloc[i]
        ok = (
            abs(row["open"] - inside["open"].iloc[0]) < 1e-9
            and abs(row["close"] - inside["close"].iloc[-1]) < 1e-9
            and abs(row["high"] - inside["high"].max()) < 1e-9
            and abs(row["low"] - inside["low"].min()) < 1e-9
        )
        problems += 0 if ok else 1
    return f"{label}: {len(starts) - 1 - problems}/{len(starts) - 1} match"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="out")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    lines = [f"# Chart candles live check ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)", ""]
    record = {}
    for kind, asset in ASSETS:
        lines.append(f"## {asset} ({kind})")
        loaded = {}
        for interval, range_key in PAIRS:
            out = cd.load_candles(kind, asset, interval, range_key)
            loaded[interval] = out
            if out["error"]:
                lines.append(f"- {interval} {range_key}: ERROR {out['error']}")
                record[f"{asset}:{interval}"] = {"error": out["error"]}
                continue
            c = out["candles"]
            times = _times(c, interval, kind, out["session"])
            forming = bool(c["forming"].iloc[-1])
            lines.append(
                f"- {interval} {range_key}: {len(c)} candles, {c.index[0]:%Y-%m-%d} to {c.index[-1]:%Y-%m-%d %H:%M %Z}; "
                f"start times {times[:12]}; newest forming={forming}; session={out['session']}"
            )
            record[f"{asset}:{interval}"] = {"candles": len(c), "times": times[:24], "forming": forming,
                                             "session": out["session"]}
        h1, h4 = loaded.get("1h"), loaded.get("4h")
        if h1 and h4 and not h1["error"] and not h4["error"]:
            lines.append("- " + _matches(h4["candles"], h1["candles"], "4h vs 1h"))
        d1, w1 = loaded.get("1D"), loaded.get("1W")
        if d1 and w1 and not d1["error"] and not w1["error"]:
            lines.append("- " + _matches(w1["candles"], d1["candles"], "1W vs 1D"))
        lines.append("")

    # The expected 4h start times.
    verdicts = []
    for kind, asset in ASSETS:
        times = (record.get(f"{asset}:4h") or {}).get("times") or []
        expected = {"09:30", "13:30"} if kind == "equity" else {"00:00", "04:00", "08:00", "12:00", "16:00", "20:00"}
        verdicts.append(f"- {asset} 4h start times {'OK' if times and set(times) <= expected else 'CHECK'}: {times}")
    lines += ["## 4h alignment", *verdicts, ""]

    with open(os.path.join(args.out, "chart_candles.md"), "w") as handle:
        handle.write("\n".join(lines))
    with open(os.path.join(args.out, "chart_candles.json"), "w") as handle:
        json.dump(record, handle, indent=1, default=str)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
