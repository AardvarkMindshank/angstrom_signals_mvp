"""
A wider coin set for Soundings (18 Nov 2026): the 100 most traded coins on Binance over 2018-2024, including the ones
that later collapsed or were delisted (Terra, FTX's token and others), so the results are not flattered by looking
only at coins that survived.

Source: Binance's public market-data archive (data.binance.vision): daily candles per month, USDT pairs. The archive
keeps delisted pairs, which is why it is used here rather than today's coin list.

  python soundings_prices.py <out folder> [--top 100] [--end 2024-10-29]

How the coins are chosen (fixed in advance, not tuned on results):
1. Every USDT spot pair in the archive, less stablecoins, wrapped coins and leveraged tokens.
2. Trading volume (in USDT) sampled in six months: June of 2018, 2019, 2020, 2021, 2022 and 2023; a month a coin was
   not listed counts as zero. Coins are ranked by the average, so a coin needs to have been big for years, or very
   big for a while, to make the list.
3. The top N by that rank, keeping only coins with at least 400 daily candles before the end date.

Saved as <COIN>-USD.csv.gz (date, open, high, low, close, volume), the same format as the research prices, cut at the
end date: nothing from the protected hold-out (from 30 Oct 2024) is ever downloaded into the files.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd
import requests

LIST_URL = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
FILE_URL = "https://data.binance.vision/data/spot/monthly/klines/{s}/1d/{s}-1d-{m}.zip"
SAMPLE_MONTHS = ("2018-06", "2019-06", "2020-06", "2021-06", "2022-06", "2023-06")
STABLE = {"USDC", "BUSD", "TUSD", "PAX", "USDP", "DAI", "FDUSD", "USDS", "USDSB", "SUSD", "UST", "USTC", "EUR", "GBP",
          "AUD", "TRY", "BRL", "RUB", "NGN", "UAH", "BIDR", "IDRT", "BVND", "BKRW", "PAXG", "AEUR", "EURI", "XUSD",
          "USD1", "BFUSD", "VAI", "USDE", "RLUSD"}
WRAPPED = {"WBTC", "WBETH", "BETH", "WETH", "STETH", "WSTETH", "BTCB"}
LEVERAGED = re.compile(r"(UP|DOWN|BULL|BEAR)USDT$")
COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades",
           "taker_base", "taker_quote", "ignore"]
MIN_DAYS = 400
GAP_DAYS = 10            # a longer break in trading splits a pair: Binance reused LUNA for Terra 2.0 after Terra fell


def segments(d: pd.DataFrame) -> list[pd.DataFrame]:
    """The pair's candles split at long breaks in trading, so a coin relisted under an old ticker is never joined
    onto the coin that collapsed (LUNA, May 2022). The first part keeps the ticker; later parts get 2, 3..."""
    if d.empty:
        return []
    dates = pd.to_datetime(d["date"])
    cut = (dates.diff().dt.days >= GAP_DAYS).cumsum()
    return [part for _, part in d.groupby(cut.values)]


def list_pairs(session: requests.Session) -> list[str]:
    """Every USDT spot pair that has daily monthly files in the archive (delisted ones included)."""
    pairs, marker = [], ""
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    while True:
        r = session.get(LIST_URL, params={"delimiter": "/", "prefix": "data/spot/monthly/klines/", "marker": marker},
                        timeout=60)
        r.raise_for_status()
        root = ElementTree.fromstring(r.content)
        got = [p.find("s3:Prefix", ns).text for p in root.findall("s3:CommonPrefixes", ns)]
        pairs += [g.rstrip("/").split("/")[-1] for g in got]
        if root.find("s3:IsTruncated", ns).text != "true" or not got:
            break
        marker = got[-1]
    keep = []
    for p in sorted(set(pairs)):
        if not p.endswith("USDT") or LEVERAGED.search(p):
            continue
        base = p[:-4]
        if base in STABLE or base in WRAPPED or not base:
            continue
        keep.append(p)
    return keep


def month_file(session: requests.Session, pair: str, month: str) -> pd.DataFrame | None:
    for attempt in range(3):
        try:
            r = session.get(FILE_URL.format(s=pair, m=month), timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                raw = z.read(z.namelist()[0]).decode()
            frame = pd.read_csv(io.StringIO(raw), header=None, names=COLUMNS)
            if not str(frame.iloc[0, 0]).isdigit():                     # some files carry a header row
                frame = frame.iloc[1:]
            frame = frame.apply(pd.to_numeric, errors="coerce").dropna(subset=["open_time", "close"])
            unit = "us" if frame["open_time"].iloc[0] > 1e14 else "ms"   # the archive moved to microseconds in 2025
            frame["date"] = pd.to_datetime(frame["open_time"], unit=unit).dt.normalize()
            return frame
        except Exception:
            time.sleep(2 + 3 * attempt)
    return None


def rank(session, pairs: list[str], log=print) -> list[tuple[str, float, int]]:
    def score(pair):
        vols, seen = [], 0
        for m in SAMPLE_MONTHS:
            f = month_file(session, pair, m)
            vols.append(float(f["quote_volume"].mean()) if f is not None and len(f) else 0.0)
            seen += f is not None
        return pair, sum(vols) / len(vols), seen

    with ThreadPoolExecutor(8) as pool:
        out = list(pool.map(score, pairs))
    out.sort(key=lambda x: -x[1])
    log(f"ranked {len(out)} pairs")
    return out


def months_between(first: str, last: str) -> list[str]:
    return [p.strftime("%Y-%m") for p in pd.period_range(first, last, freq="M")]


def history(session, pair: str, end: pd.Timestamp) -> pd.DataFrame:
    parts = []
    with ThreadPoolExecutor(6) as pool:
        for f in pool.map(lambda m: month_file(session, pair, m), months_between("2017-07", end.strftime("%Y-%m"))):
            if f is not None and len(f):
                parts.append(f)
    if not parts:
        return pd.DataFrame()
    d = pd.concat(parts)
    d = d[d["date"] <= end]                       # nothing from the hold-out is kept past this line
    d = d.drop_duplicates("date", keep="last").sort_values("date")
    d = d[(d["close"] > 0) & (d["high"] >= d["low"])]
    return pd.DataFrame({"date": d["date"].dt.strftime("%Y-%m-%d"), "open": d["open"], "high": d["high"],
                         "low": d["low"], "close": d["close"], "volume": d["quote_volume"]})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--end", default="2024-10-29")
    args = ap.parse_args()
    end = pd.Timestamp(args.end)
    folder = Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    pairs = list_pairs(session)
    print(f"{len(pairs)} USDT pairs in the archive (after leaving out stablecoins and leveraged tokens)", flush=True)
    ranked = rank(session, pairs)
    chosen, manifest = [], {"end": args.end, "source": "data.binance.vision spot daily klines (USDT pairs)",
                            "rule": "top by average USDT volume in June 2018-2023 (0 when not listed)", "files": {}}
    for pair, vol, seen in ranked:
        if len(chosen) >= args.top:
            break
        whole = history(session, pair, end)
        parts = segments(whole)
        if not any(len(p) >= MIN_DAYS for p in parts):
            print(f"  {pair}: only {len(whole)} candles before the end, left out", flush=True)
            continue
        for n, d in enumerate(parts):
            if len(d) < MIN_DAYS or len(chosen) >= args.top:
                continue
            sym = pair[:-4] + ("" if n == 0 else str(n + 1)) + "-USD"
            d.to_csv(folder / f"{sym}.csv.gz", index=False)
            delisted = pd.Timestamp(d["date"].iloc[-1]) < end - pd.Timedelta(days=5)
            manifest["files"][sym] = {"pair": pair, "bars": len(d), "first": d["date"].iloc[0],
                                      "last": d["date"].iloc[-1], "avg_volume_sampled": round(vol),
                                      "months_sampled": seen, "stopped_early": delisted,
                                      "part": n + 1, "parts": len(parts)}
            chosen.append(sym)
            print(f"{len(chosen):>3} {sym:<12} {d['date'].iloc[0]} to {d['date'].iloc[-1]}"
                  f"{'  (stopped trading before the end)' if delisted else ''}"
                  f"{'  (a later listing under the same ticker)' if n else ''}", flush=True)
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=1))
    stopped = [s for s, m in manifest["files"].items() if m["stopped_early"]]
    print(f"\n{len(chosen)} coins saved; {len(stopped)} stopped trading before the end: {', '.join(stopped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
