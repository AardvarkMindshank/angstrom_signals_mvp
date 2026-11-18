"""
Point-in-time Tides history (18 Nov 2026): every day's Tide, sea state, winds and currents as they could have been
read on that day, with nothing from later. It is what lets Sets, funnels and Soundings use Tides on past dates.

The maths is tides.py's, written for every day at once. Every step it takes is "causal" (a rolling window, a change
over the past, a percentile against the past 5 years, the 5-close persistence), so a day's reading only uses values
up to that day, provided each input series holds only what was known on each date. That is what this file ensures:

- Market prices (Yahoo: yields, dollar, VIX, gold, copper, oil, ETFs, Bitcoin, Ether): a close is known on its day.
- FRED daily series (2-year yield, the yield curve): FRED posts a day's value on the next business day, so each
  value is moved one business day later.
- Inflation: built from the unadjusted CPI index (CPIAUCNS, which is not revised: what was first printed is what is
  there now), and each month's figure is dated on the day it was first released (ALFRED's first-release dates).
- Storm warnings: the scheduled Fed decisions, CPI and jobs-report release dates (Fed calendars; ALFRED release
  dates for CPI and jobs). Unscheduled meetings (March 2020) are left out: nobody could have been warned of them.

Each row is "what was known once the US market had closed that day" (business days, carried over weekends).
A crypto daily close (midnight UTC) comes after that day's US close, so it reads that day's row. An equity daily
close is the US close itself, so it reads the row of the business day before (signal_library/signals_tides.py).

  python tides_history.py <out folder> [--end 2024-10-29]
      needs the internet (Yahoo, FRED) and FRED_API_KEY (ALFRED release dates); run on GitHub (tides-history.yml).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tides as td  # noqa: E402

START = "2008-01-01"                 # 5 years of warm-up before the first reading used (2015)
FIRST = pd.Timestamp("2013-01-01")   # rows kept from here
WINDOW = td.YEARS * 252
MIN = 252
HELP = 0.2                           # a contribution beyond +-0.2 is "helping" / "hurting" (as the winds' threshold)

# Scheduled FOMC decision days (federalreserve.gov, FOMC historical materials and calendars). Unscheduled ones
# (3 and 15 March 2020) are not here on purpose. Later dates are in macro_calendar.py.
FOMC = """
2015-01-28 2015-03-18 2015-04-29 2015-06-17 2015-07-29 2015-09-17 2015-10-28 2015-12-16
2016-01-27 2016-03-16 2016-04-27 2016-06-15 2016-07-27 2016-09-21 2016-11-02 2016-12-14
2017-02-01 2017-03-15 2017-05-03 2017-06-14 2017-07-26 2017-09-20 2017-11-01 2017-12-13
2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
2020-01-29 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
""".split()


# ------------------------------------------------------------------------------------------------ fetching

def fetch_yahoo(symbol: str, start: str, end: str) -> pd.Series:
    import yfinance as yf

    frame = yf.Ticker(symbol).history(start=start, end=end, interval="1d", auto_adjust=False)
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    s = frame["Close"].dropna()
    idx = pd.to_datetime(s.index)
    s.index = (idx.tz_localize(None) if idx.tz is not None else idx).normalize()
    return s[~s.index.duplicated(keep="last")].astype(float)


def fetch_first_releases(series_id: str, key: str) -> pd.DataFrame:
    """ALFRED: each observation's first-released value and the date it was released (output_type 4)."""
    import requests

    r = requests.get("https://api.stlouisfed.org/fred/series/observations", timeout=60, params={
        "series_id": series_id, "api_key": key, "file_type": "json", "output_type": 4,
        "realtime_start": "1990-01-01", "realtime_end": "9999-12-31", "observation_start": "2000-01-01"})
    r.raise_for_status()
    rows = [(o["date"], o["realtime_start"], o["value"]) for o in r.json()["observations"]]
    frame = pd.DataFrame(rows, columns=["month", "released", "value"])
    frame["month"] = pd.to_datetime(frame["month"])
    frame["released"] = pd.to_datetime(frame["released"])
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    return frame.dropna().sort_values("month").reset_index(drop=True)


def fetch(end: str, log=print) -> dict:
    yahoo, fred = td.symbols_needed()
    raw = {}
    for sym in sorted(yahoo):
        raw[sym] = fetch_yahoo(sym, START, end)
        log(f"{sym}: {len(raw[sym])} closes from {raw[sym].index.min().date() if len(raw[sym]) else '-'}")
    for sid in sorted(fred - {"CPIAUCSL"}):
        raw[f"fred:{sid}"] = td.fetch_fred(sid)
        log(f"FRED {sid}: {len(raw[f'fred:{sid}'])} values")
    key = os.environ.get("FRED_API_KEY", "")
    if not key:
        raise SystemExit("FRED_API_KEY is needed for the first-release dates (ALFRED)")
    raw["cpi"] = fetch_first_releases("CPIAUCNS", key)
    raw["jobs"] = fetch_first_releases("PAYEMS", key)
    log(f"CPI first releases: {len(raw['cpi'])}; jobs reports: {len(raw['jobs'])}")
    return raw


# ------------------------------------------------------------------------------------------------ point in time

def inflation_known(cpi: pd.DataFrame) -> pd.Series:
    """12-month inflation from the unadjusted index, dated on each month's first release."""
    by_month = cpi.set_index("month")["value"]
    yoy = (by_month / by_month.shift(12) - 1) * 100
    s = pd.Series(yoy.values, index=cpi.set_index("month")["released"].values).dropna()
    s.index = pd.DatetimeIndex(s.index)
    return s[~s.index.duplicated(keep="last")].sort_index()


def known_series(key: str, raw: dict, days: pd.DatetimeIndex) -> pd.Series:
    """The business-day series a current reads, holding on each day only what was known after that day's US close."""
    src = td.SPEC[key]["source"]
    limit = 5
    if src[0] == "yahoo":
        s = raw.get(src[1])
    elif src[0] == "fred":
        s = raw.get(f"fred:{src[1]}")
        if s is not None:
            s = s.copy()
            s.index = s.index + pd.offsets.BDay(1)        # FRED posts a day's value on the next business day
    elif src[0] == "fred_yoy":
        s, limit = inflation_known(raw["cpi"]), 40
    else:
        a, b = raw.get(src[1]), raw.get(src[2])
        s = None if a is None or b is None or a.empty or b.empty else (a / b).dropna()
    if s is None or s.empty:
        return pd.Series(np.nan, index=days)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.reindex(s.index.union(days)).ffill(limit=limit).reindex(days)


# ------------------------------------------------------------------------------------------------ maths, every day

def rolling_percentile(s: pd.Series) -> pd.Series:
    """tides.percentile for every day: share of the past 5 years below today's value (ties count half)."""
    roll = s.rolling(WINDOW, min_periods=MIN)
    return (roll.rank(method="average") - 0.5) / roll.count() * 100


def band_of(score: float) -> str | None:
    return None if score is None or (isinstance(score, float) and math.isnan(score)) else td.band(score)


def direction_of(m: float) -> str:
    return td.direction(None if m is None or (isinstance(m, float) and math.isnan(m)) else float(m))


def build(raw: dict, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The daily table (business days) and the storm-warning events."""
    first = min(s.index.min() for k, s in raw.items() if isinstance(s, pd.Series) and len(s))
    days = pd.bdate_range(first, pd.Timestamp(end))
    out = pd.DataFrame(index=days)
    contrib = {}
    for key in td.CURRENT_KEYS:
        spec = td.SPEC[key]
        s = known_series(key, raw, days)
        clean = s.dropna()
        mom = td.momentum_series(clean, spec["unit"]).reindex(days)
        score = rolling_percentile(clean).reindex(days)
        c = (mom.apply(lambda m: math.tanh(m) if pd.notna(m) else np.nan) * spec["sign"])
        contrib[key] = c
        out[f"{key}_value"] = s
        out[f"{key}_score"] = score.round(1)
        out[f"{key}_band"] = score.apply(band_of)
        out[f"{key}_dir"] = mom.apply(direction_of)
        out[f"{key}_contrib"] = c.round(3)
        out[f"{key}_effect"] = c.apply(lambda v: None if pd.isna(v) else
                                       "helping" if v > HELP else "hurting" if v < -HELP else "neutral")

    # The Tide: each family averages its voting currents, then the families' weighted average (tides.tide).
    fam = {}
    for f in td.FAMILIES:
        members = [k for k in td.CURRENT_KEYS if td.SPEC[k]["family"] == f and td.SPEC[k]["weight"]]
        if members:
            fam[f] = pd.concat([contrib[k] for k in members], axis=1).mean(axis=1, skipna=True)
    frame = pd.DataFrame(fam).dropna(how="all")
    weights = {f: td.FAMILIES[f][1] for f in frame}
    w = pd.DataFrame({f: frame[f].notna() * weights[f] for f in frame})
    score = ((frame.fillna(0) * pd.DataFrame(weights, index=frame.index)).sum(axis=1) / w.sum(axis=1)).dropna()
    shown = td.persist(score.apply(td.label_for))
    run_id = (shown != shown.shift()).cumsum()
    out["tide_score"] = score.round(3)
    out["tide_raw"] = score.apply(td.label_for)
    out["tide"] = shown
    out["tide_since"] = pd.Series(shown.index, index=shown.index).groupby(run_id).transform("min").dt.strftime("%Y-%m-%d")
    out["tide_held"] = shown.groupby(run_id).cumcount() + 1
    for f in fam:
        out[f"family_{f}"] = fam[f].round(3)

    # Sea state (tides.sea_state): VIX and Bitcoin's 30-day volatility, each against its own 5 years.
    parts = []
    vix = raw.get("^VIX")
    if vix is not None and len(vix):
        pv = rolling_percentile(vix.dropna())
        parts.append(pv.reindex(pv.index.union(days)).ffill(limit=5).reindex(days))
    btc = raw.get("BTC-USD")
    if btc is not None and len(btc):
        vol = td.realised_vol(btc).dropna()
        pv = rolling_percentile(vol)
        parts.append(pv.reindex(pv.index.union(days)).ffill(limit=5).reindex(days))
    sea = pd.concat(parts, axis=1).mean(axis=1, skipna=True)
    out["sea_score"] = sea.round(1)
    out["sea"] = sea.apply(lambda v: None if pd.isna(v) else next(n for top, n, _ in td.SEA_BANDS if v < top))

    # Winds (tides.winds): the average contribution of the currents declared for each market.
    for market, (_, keys) in td.MARKETS.items():
        v = pd.concat([contrib[k] for k in keys], axis=1).mean(axis=1, skipna=True)
        out[f"wind_{market}_score"] = v.round(3)
        out[f"wind_{market}"] = v.apply(lambda x: None if pd.isna(x) else
                                        "tailwind" if x > 0.2 else "headwind" if x < -0.2 else "calm")

    out = out[out.index >= FIRST]
    out.index.name = "date"
    return out, storm_events(raw, end)


def storm_events(raw: dict, end: str) -> pd.DataFrame:
    rows = [("fomc", d) for d in FOMC]
    rows += [("cpi", d.strftime("%Y-%m-%d")) for d in raw["cpi"]["released"]]
    rows += [("jobs", d.strftime("%Y-%m-%d")) for d in raw["jobs"]["released"]]
    ev = pd.DataFrame(rows, columns=["kind", "date"]).drop_duplicates()
    ev = ev[(ev["date"] >= "2012-01-01") & (ev["date"] <= (pd.Timestamp(end) + pd.Timedelta(days=60)).strftime("%Y-%m-%d"))]
    return ev.sort_values(["date", "kind"]).reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--end", default="2024-10-29")
    args = ap.parse_args()
    end_fetch = (pd.Timestamp(args.end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")   # Yahoo's end is exclusive
    raw = fetch(end_fetch)
    for k in list(raw):                       # nothing after the end date is kept past this line
        if isinstance(raw[k], pd.Series):
            raw[k] = raw[k][raw[k].index <= pd.Timestamp(args.end)]
        else:
            raw[k] = raw[k][raw[k]["released"] <= pd.Timestamp(args.end)]
    table, events = build(raw, args.end)
    folder = Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    table.to_csv(folder / "history.csv.gz")
    events.to_csv(folder / "events.csv", index=False)
    summary = {
        "end": args.end, "rows": len(table), "first": str(table.index.min().date()),
        "tide_days": table["tide"].value_counts().to_dict(),
        "tide_spells": int((table["tide"] != table["tide"].shift()).sum()),
        "sea_days": table["sea"].value_counts().to_dict(),
        "events": events["kind"].value_counts().to_dict(),
        "first_full_tide": str(table["tide"].dropna().index.min().date()),
        "missing_by_current": {k: int(table[f"{k}_contrib"].isna().sum()) for k in td.CURRENT_KEYS},
    }
    (folder / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
