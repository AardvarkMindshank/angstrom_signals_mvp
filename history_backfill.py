"""
Daily history for studies of Sets that read positioning or fund flows (What followed), saved beside the prices on the
reports branch. Like the saved prices it stops at 29 Oct 2024, so the protected hold-out is never stored here.

  data/derivatives/<COIN>-USD.csv.gz   date, price, oi, oi_lead, ls, funding, liq_long, liq_short (Coinalyze, daily)
  data/flows/stablecoin_supply.csv.gz  date, value (DefiLlama, total stablecoins in US$)

Coinalyze keeps daily data for good ("For daily timeframe/granularity we do not delete the old data"); its hourly
data covers only the last 1,500 to 2,000 points. The markets are the ones the app uses live (liquidation_levels:
the coin's biggest stablecoin perpetuals on Binance, Bybit and OKX). oi adds them up on days every market reported;
oi_lead is the first market alone, which goes back further.

These are filled in after the fact, not recorded on each day. Sources rarely revise these numbers, but a study that
uses them says so.

  python history_backfill.py <out folder> [--coins BTC,ETH] [--prices <saved prices folder>]
Needs COINALYZE_API_KEY.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capital_flows  # noqa: E402
import liquidation_levels as ll  # noqa: E402

CUT = pd.Timestamp("2024-10-29")
FROM = int(pd.Timestamp("2014-01-01", tz="UTC").timestamp())
PAUSE = 1.7                      # Coinalyze allows 40 calls a minute; each symbol counts as one


class Daily(ll.Coinalyze):
    def daily(self, path: str, symbols: list[str], **extra) -> dict[str, list[dict]]:
        out: dict = {}
        for s in symbols:                                   # one at a time keeps the pace simple
            for attempt in range(4):
                try:
                    rows = self.get(path, symbols=s, interval="daily",
                                    **{"from": FROM, "to": int(time.time())}, **extra) or []
                    break
                except ll.RateLimited as wait:
                    time.sleep(float(str(wait) or 60) + 1)
            else:
                rows = []
            self.calls += 1
            time.sleep(PAUSE)
            out.update({str(r.get("symbol")): list(r.get("history") or []) for r in rows})
        return out


def coin_history(client: Daily, markets: list[dict]) -> pd.DataFrame:
    symbols = [str(m["symbol"]) for m in markets]
    lead = symbols[0]
    oi_by = client.daily("/open-interest-history", symbols, convert_to_usd="true")
    bars = client.daily("/ohlcv-history", [lead]).get(lead, [])
    ratio_market = next((m for m in markets if m.get("has_long_short_ratio_data")), None)
    ratios = (client.daily("/long-short-ratio-history", [str(ratio_market["symbol"])]).get(str(ratio_market["symbol"]), [])
              if ratio_market else [])
    funding = client.daily("/funding-rate-history", [lead]).get(lead, [])
    liqs = list(client.daily("/liquidation-history", symbols, convert_to_usd="true").values())
    series = ll.build_series(bars, ll.combine_open_interest(oi_by.values()), ratios, funding, liqs)
    frame = pd.DataFrame(series)
    if frame.empty:
        return frame
    lead_oi = {int(r["t"]): float(r["c"]) for r in oi_by.get(lead, []) if ll._ok(r.get("c"))}
    frame["oi_lead"] = [lead_oi.get(int(t)) for t in frame["t"]]
    frame["date"] = pd.to_datetime(frame.pop("t"), unit="s", utc=True).dt.tz_localize(None).dt.normalize()
    frame = frame[frame["date"] <= CUT]                    # nothing from the hold-out is kept
    frame["markets"] = "|".join(symbols)
    return frame[["date", "price", "oi", "oi_lead", "ls", "funding", "liq_long", "liq_short", "markets"]]


def coins(prices: str | None, wanted: str) -> list[str]:
    if wanted:
        return [c.strip().upper() for c in wanted.split(",") if c.strip()]
    return sorted(p.name[:-11] for p in Path(prices or "data/prices").glob("*-USD.csv.gz"))


def stablecoins(out: Path) -> int:
    payload = requests.get(capital_flows.SOURCES["defillama_stablecoins"]["url"],
                           headers=capital_flows._HEADERS, timeout=60).json()
    rows = capital_flows.parse_defillama_total(payload)
    frame = pd.DataFrame([{"date": r["observed_date"], "value": r["value"]} for r in rows])
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[frame["date"] <= CUT].sort_values("date")
    (out / "flows").mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "flows" / "stablecoin_supply.csv.gz", index=False)
    print(f"stablecoin supply: {len(frame)} days, {frame['date'].min():%Y-%m-%d} to {frame['date'].max():%Y-%m-%d}")
    return len(frame)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("--coins", default="")
    p.add_argument("--prices", default="")
    args = p.parse_args(argv)
    out = Path(args.out)
    stablecoins(out)
    client = Daily(os.environ["COINALYZE_API_KEY"].strip())
    markets = client.get("/future-markets")
    exchanges = client.get("/exchanges")
    (out / "derivatives").mkdir(parents=True, exist_ok=True)
    for coin in coins(args.prices, args.coins):
        chosen = ll.pick_markets(markets, exchanges, coin)
        if not chosen:
            print(f"{coin}: no perpetual market on Binance, Bybit or OKX")
            continue
        frame = coin_history(client, chosen)
        if frame.empty:
            print(f"{coin}: no data")
            continue
        frame.to_csv(out / "derivatives" / f"{coin}-USD.csv.gz", index=False)
        filled = {c: frame.loc[frame[c].notna(), "date"].min().strftime("%Y-%m-%d") if frame[c].notna().any()
                  else "none" for c in ("oi", "oi_lead", "ls", "funding")}
        print(f"{coin}: {len(frame)} days from {frame['date'].min():%Y-%m-%d}; first oi {filled['oi']}, "
              f"oi_lead {filled['oi_lead']}, long/short {filled['ls']}, funding {filled['funding']}; "
              f"markets {chosen[0]['symbol']}…", flush=True)
    print(f"Coinalyze calls: {client.calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
