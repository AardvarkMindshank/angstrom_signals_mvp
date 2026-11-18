"""
Equities for Soundings (18 Nov 2026): a fixed random sample of the companies that were in the S&P 500 at the start
of 2016, including those that later left the index (taken over, shrunk, went bust), so the results are not flattered
by looking only at today's winners.

Membership on the start date is rebuilt from Wikipedia's S&P 500 page: today's list, with every change since then
undone (companies added later are taken out, companies removed later are put back). Prices: Yahoo Finance daily
candles to the end date. Companies Yahoo no longer has (often taken over) are counted and named in the summary.

  python soundings_equity_prices.py <out folder> [--sample 200] [--start 2016-01-04] [--end 2024-10-29]

Saved as <TICKER>.csv.gz (date, open, high, low, close, volume), cut at the end date: nothing from the protected
hold-out (from 30 Oct 2024) is ever downloaded into the files.
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
import time
from pathlib import Path

import pandas as pd
import requests

URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
HEADERS = {"User-Agent": "AngstromSignals/1.0 (market research dashboard)"}
SEED = 2016
MIN_DAYS = 750
WARMUP_FROM = "2013-01-01"
# Same company, new ticker (Yahoo keeps the history under the new one).
RENAMED = {"FB": "META", "ABC": "COR", "COG": "CTRA", "PKI": "RVTY", "TMK": "GL", "UTX": "RTX", "CBS": "PARA",
           "HRS": "LHX", "BHGE": "BKR", "ARNC": "HWM", "ANTM": "ELV", "HCP": "PEAK", "KORS": "CPRI", "LUK": "JEF",
           "WLTW": "WTW", "DISCA": "WBD", "PCLN": "BKNG", "RHT": "RHT", "HRB": "HRB", "SYMC": "GEN", "NLOK": "GEN",
           "FISV": "FI", "GPS": "GAP", "CTL": "LUMN", "XEC": "CTRA", "MYL": "VTRS", "TSO": "ANDV", "BBT": "TFC",
           "STI": "TFC", "ADS": "BFH", "HFC": "DINO", "WRK": "SW", "ESRX": "ESRX", "PX": "LIN", "DPS": "KDP",
           "COV": "COV", "GGP": "GGP", "DTV": "DTV", "BXLT": "BXLT", "TE": "TE", "CMCSK": "CMCSA", "FOXA": "FOXA",
           "PCL": "PCL", "AGN": "AGN"}


def yahoo(symbol) -> str:
    return str(symbol).strip().upper().replace(".", "-")


HISTORY_REPO = "https://api.github.com/repos/fja05680/sp500/contents"


def members_from_history(day: pd.Timestamp) -> tuple[list[str], dict] | None:
    """The S&P 500 on a date from the open dataset github.com/fja05680/sp500 (dated lists of every member since
    1996). None when it can't be read."""
    try:
        files = requests.get(HISTORY_REPO, headers=HEADERS, timeout=30).json()
        f = sorted((x for x in files if str(x.get("name", "")).startswith("S&P 500 Historical Components")
                    and str(x["name"]).endswith(".csv")), key=lambda x: x["name"])[-1]
        table = pd.read_csv(io.StringIO(requests.get(f["download_url"], headers=HEADERS, timeout=60).text))
        table["date"] = pd.to_datetime(table["date"])
        row = table[table["date"] <= day].iloc[-1]
        members = sorted({yahoo(x) for x in str(row["tickers"]).split(",") if x.strip()})
        latest = table.iloc[-1]
        now = {yahoo(x) for x in str(latest["tickers"]).split(",") if x.strip()}
        return members, {"source": f["name"], "as_of": str(row["date"].date()), "left_since": len(set(members) - now)}
    except Exception as exc:
        print(f"membership history not available ({type(exc).__name__}: {exc}); trying Wikipedia", flush=True)
        return None


def members_on(day: pd.Timestamp) -> tuple[list[str], dict]:
    got = members_from_history(day)
    if got:
        return got
    html = requests.get(URL, headers=HEADERS, timeout=30).text
    tables = pd.read_html(io.StringIO(html))
    print("Wikipedia tables:", [list(t.columns)[:6] for t in tables], flush=True)
    now = {yahoo(s) for s in tables[0]["Symbol"]}
    def flat(t):
        t = t.copy()
        t.columns = [" ".join(str(x) for x in c).strip() if isinstance(c, tuple) else str(c) for c in t.columns]
        return t

    # the changes table: the one with Added and Removed columns (its position on the page has moved before)
    changes = next(flat(t) for t in tables[1:]
                   if any("added" in str(c).lower() for c in flat(t).columns)
                   and any("removed" in str(c).lower() for c in flat(t).columns))
    print("changes table columns:", list(changes.columns), flush=True)
    date_col = next(c for c in changes.columns if "date" in c.lower() or "effective" in c.lower())
    added_col = next(c for c in changes.columns if "added" in c.lower() and "ticker" in c.lower())
    removed_col = next(c for c in changes.columns if "removed" in c.lower() and "ticker" in c.lower())
    changes["when"] = pd.to_datetime(changes[date_col], errors="coerce")
    later = changes[changes["when"] > day].sort_values("when", ascending=False)
    members = set(now)
    for _, row in later.iterrows():                 # undo each change, newest first
        a, r = row[added_col], row[removed_col]
        if isinstance(a, str) and a.strip():
            members.discard(yahoo(a))
        if isinstance(r, str) and r.strip():
            members.add(yahoo(r))
    left = sorted(members - now)
    return sorted(members), {"today": len(now), "changes_undone": int(len(later)), "left_since": len(left)}


def candidates(symbol: str) -> list[str]:
    """The dataset marks a former member with the month it left (AET-201811): try the plain ticker, and a known
    new ticker for the same company."""
    base = symbol.split("-20")[0] if "-20" in symbol else symbol
    out = [RENAMED.get(base, base), base]
    return list(dict.fromkeys(out))


def fetch(symbol: str, end: pd.Timestamp) -> tuple[str, pd.DataFrame]:
    """(the ticker the prices were found under, the prices)."""
    for name in candidates(symbol):
        d = _fetch(name, end)
        if not d.empty:
            return name, d
    return symbol, pd.DataFrame()


def _fetch(symbol: str, end: pd.Timestamp) -> pd.DataFrame:
    import yfinance as yf

    frame = None
    for attempt in range(4):
        try:
            frame = yf.Ticker(symbol).history(start=WARMUP_FROM, end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                                              interval="1d", auto_adjust=True)
            if frame is not None and not frame.empty:
                break
        except Exception:
            pass
        time.sleep(3 + 5 * attempt)                      # Yahoo refuses bursts: wait and try again
    if frame is None or frame.empty:
        return pd.DataFrame()
    idx = pd.to_datetime(frame.index)
    idx = (idx.tz_localize(None) if idx.tz is not None else idx).normalize()
    d = pd.DataFrame({"date": idx, "open": frame["Open"].values, "high": frame["High"].values,
                      "low": frame["Low"].values, "close": frame["Close"].values, "volume": frame["Volume"].values})
    d = d[d["date"] <= end].dropna(subset=["close"])           # nothing from the hold-out is kept past this line
    d = d[d["close"] > 0].drop_duplicates("date", keep="last")
    d["date"] = d["date"].dt.strftime("%Y-%m-%d")
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--sample", type=int, default=200)
    ap.add_argument("--start", default="2016-01-04")
    ap.add_argument("--end", default="2024-10-29")
    args = ap.parse_args()
    end = pd.Timestamp(args.end)
    folder = Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    members, info = members_on(pd.Timestamp(args.start))
    print(f"S&P 500 on {args.start}: {len(members)} companies ({info['left_since']} have left the index since); "
          f"from {info.get('source', 'Wikipedia')}")
    chosen = sorted(random.Random(SEED).sample(members, min(args.sample, len(members))))
    manifest = {"source": "Yahoo Finance daily (adjusted); S&P 500 membership rebuilt from Wikipedia",
                "start_members": args.start, "end": args.end, "seed": SEED, "sample": len(chosen), **info,
                "files": {}, "missing": [], "too_short": []}
    for sym in chosen:
        time.sleep(0.6)
        found, d = fetch(sym, end)
        if d.empty:
            manifest["missing"].append(sym)
            continue
        if len(d) < MIN_DAYS:
            manifest["too_short"].append(sym)
            continue
        sym = found                                     # named by the ticker it trades (or last traded) under
        d.to_csv(folder / f"{sym}.csv.gz", index=False)
        stopped = pd.Timestamp(d["date"].iloc[-1]) < end - pd.Timedelta(days=7)
        manifest["files"][sym] = {"bars": len(d), "first": d["date"].iloc[0], "last": d["date"].iloc[-1],
                                  "stopped_early": bool(stopped)}
        print(f"{sym:<7} {d['date'].iloc[0]} to {d['date'].iloc[-1]}{'  (stopped trading before the end)' if stopped else ''}",
              flush=True)
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"\n{len(manifest['files'])} saved of {len(chosen)} sampled; Yahoo has no prices for {len(manifest['missing'])}: "
          f"{', '.join(manifest['missing'])}; too short: {', '.join(manifest['too_short']) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
