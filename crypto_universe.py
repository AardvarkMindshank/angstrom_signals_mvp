"""
The crypto universe for the funnel (decided 10 Nov 2026, docs/research/funnel_brief_2026-11-10.md, point 6):
CoinGecko's top coins by market cap that trade on Binance spot against USDT, without stablecoins, wrapped, bridged or
staked copies, gold tokens and leveraged tokens, and only coins with enough trading and history for a credible reading.
Every coin left out is listed with its reason.

Run: python crypto_universe.py out/ [--top 200]   (needs Binance's public mirror and CoinGecko; GitHub runs it)
Writes out/crypto_universe.json:
  {"built_at", "rules", "included": [{id, symbol, name, rank, pair, volume_usd, listed_since, days}],
   "excluded": [{id, symbol, name, rank, reason}]}
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

import binance_data as bn

TOP = 500
MIN_VOLUME_USD = 250_000         # median daily USDT traded on Binance over the last 30 closed days (~$10k an hour)
MAX_QUIET_HOURS = 0.05           # share of the last 7 days' hourly candles with no trade at all (gappy candles)
MIN_DAYS = 200                   # daily candles on Binance: enough for the daily Sets (EMA 50 needs ~150)
MAX_GAP_DAYS = 0                 # closed days without trading in the last 30
NOT_COINS = ("stablecoins", "wrapped-tokens", "liquid-staking-tokens", "tokenized-gold", "bridged-tokens")
REASON = {
    "stablecoins": "stablecoin (follows a currency)",
    "wrapped-tokens": "wrapped copy of another coin",
    "liquid-staking-tokens": "staked copy of another coin",
    "tokenized-gold": "tracks gold",
    "bridged-tokens": "bridged copy of another coin",
}
RULES = {
    "top": TOP, "min_volume_usd": MIN_VOLUME_USD, "max_quiet_hours": MAX_QUIET_HOURS, "min_days": MIN_DAYS, "venue": "Binance spot, against USDT",
    "left_out": "stablecoins, wrapped, bridged and staked copies, gold tokens, leveraged tokens; coins not on "
                "Binance; thin trading; short history; days without trading",
}
_CG = "https://api.coingecko.com/api/v3/coins/markets"
_HEADERS = {"User-Agent": "AngstromSignals/1.0 (market research dashboard)"}


def _coingecko(params: dict, tries: int = 4) -> list:
    for attempt in range(tries):
        r = requests.get(_CG, params={"vs_currency": "usd", **params}, headers=_HEADERS, timeout=30)
        if r.status_code == 429:                            # free tier: wait and retry
            time.sleep(20 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("CoinGecko kept asking us to slow down")


def top_coins(n: int) -> list[dict]:
    rows: list = []
    page = 1
    while len(rows) < n:
        part = _coingecko({"order": "market_cap_desc", "per_page": 250, "page": page})
        if not part:
            break
        rows.extend(part)
        page += 1
    return rows[:n]


NOT_TRADABLE_WORDS = {"exchange-based": "another exchange's own token", "treasury": "tokenised fund",
                      "tokenized-stock": "tokenised share", "xstocks": "tokenised share",
                      "tokenized-asset": "tokenised asset", "real-world-assets": "real-world asset token"}
YAHOO_LEAVE_OUT = ("another exchange's own token", "tokenised fund", "tokenised share", "tokenised asset")


def labels() -> dict[str, str]:
    """{coingecko id: what it is} from CoinGecko's categories that explain a coin missing from Binance (the reason
    text, and which coins the Yahoo fallback leaves out). Category ids are found by keyword in CoinGecko's list."""
    try:
        r = requests.get("https://api.coingecko.com/api/v3/coins/categories/list", headers=_HEADERS, timeout=30)
        ids = [c["category_id"] for c in r.json()] if r.status_code == 200 else []
    except Exception:
        ids = []
    wanted = [(cid, word) for cid in ids for key, word in NOT_TRADABLE_WORDS.items() if key in cid]
    out: dict[str, str] = {}
    for category, word in wanted[:12]:
        try:
            for page in (1, 2):
                rows = _coingecko({"category": category, "per_page": 250, "page": page})
                for row in rows:
                    out.setdefault(row["id"], word)
                if len(rows) < 250:
                    break
        except Exception:
            pass
        time.sleep(3)
    print(f"Categories used for wording: {', '.join(c for c, _ in wanted[:12]) or 'none found'}; {len(out)} coins")
    return out


def not_coins() -> dict[str, str]:
    """{coingecko id: reason} for every coin in the excluded categories."""
    out: dict[str, str] = {}
    for category in NOT_COINS:
        try:
            for page in (1, 2):
                for row in _coingecko({"category": category, "per_page": 250, "page": page}):
                    out.setdefault(row["id"], REASON[category])
        except Exception:
            pass                                            # the name and price rules below still catch most
        time.sleep(3)
    return out


def _named_copy(coin: dict) -> str | None:
    name = str(coin.get("name") or "").lower()
    for word, reason in (("wrapped", REASON["wrapped-tokens"]), ("bridged", REASON["bridged-tokens"]),
                         ("staked", REASON["liquid-staking-tokens"])):
        if word in name:
            return reason
    if "leverag" in name or any(f"{x}x " in name + " " for x in (2, 3, 5)):
        return "leveraged token"
    return None


def _quiet_hours(pair: str, now: pd.Timestamp, get) -> float:
    """Share of the last 7 days' closed hourly candles in which nothing traded (or that are missing)."""
    hours = bn.klines(pair, "1h", now.floor("h") - pd.Timedelta(hours=169), get=get)
    hours = hours[hours.index < now.floor("h")].tail(168)
    return round(((hours["volume"] <= 0).sum() + max(0, 168 - len(hours))) / 168, 4)


YAHOO_MIN_VOLUME_USD = 1_000_000   # CoinGecko's 24h volume across all exchanges (Yahoo has no per-venue volume)
YAHOO_MAX_MISSING_HOURS = 0.05     # share of the last week's hourly candles Yahoo does not have


def yahoo_quality(ticker: str, now: pd.Timestamp) -> dict | None:
    """Days of daily history, the last close and the share of missing hourly candles last week, from Yahoo Finance;
    None when Yahoo has nothing for the ticker."""
    import yfinance as yf

    daily = yf.Ticker(ticker).history(period="max", interval="1d", auto_adjust=False)
    if daily is None or daily.empty:
        return None
    hourly = yf.Ticker(ticker).history(period="8d", interval="1h", auto_adjust=False)
    end = now.floor("h")
    have = 0 if hourly is None or hourly.empty else int(((hourly.index.tz_convert("UTC") >= end - pd.Timedelta(hours=168))
                                                          & (hourly.index.tz_convert("UTC") < end)).sum())
    first = pd.Timestamp(daily.index[0]).tz_convert("UTC") if daily.index.tz else pd.Timestamp(daily.index[0], tz="UTC")
    return {"days": int((now.normalize() - first.normalize()).days), "close": float(daily["Close"].iloc[-1]),
            "listed_since": first.strftime("%Y-%m-%d"), "missing_hours": round(max(0, 168 - have) / 168, 4)}


def yahoo_fallback(coin: dict, now: pd.Timestamp, check=yahoo_quality):
    """(yahoo ticker, None, quality) when the coin can be read from Yahoo with credible data, else
    (None, reason, None)."""
    import data_fetchers

    symbol = str(coin.get("symbol") or "").upper()
    ticker = (data_fetchers.YF_BY_COINGECKO_ID.get(coin["id"]) or data_fetchers.YAHOO_TICKER_BY_ID.get(coin["id"])
              or f"{symbol}-USD")
    volume = float(coin.get("total_volume") or 0)
    if volume < YAHOO_MIN_VOLUME_USD:
        return None, f"not on Binance, and thin trading elsewhere (about ${volume / 1e3:,.0f}k a day)", None
    try:
        q = check(ticker, now)
    except Exception as e:
        return None, f"not on Binance, and Yahoo could not be read ({type(e).__name__})", None
    if q is None:
        return None, "not on Binance or Yahoo Finance", None
    price = float(coin.get("current_price") or 0)
    if not price or abs(q["close"] / price - 1) > bn.PRICE_TOLERANCE:
        return None, f"not on Binance, and Yahoo's {ticker} is another coin (different price)", None
    if q["days"] < MIN_DAYS:
        return None, f"not on Binance, and only {q['days']} days on Yahoo (needs {MIN_DAYS})", None
    if q["missing_hours"] > YAHOO_MAX_MISSING_HOURS:
        return None, (f"not on Binance, and Yahoo's hourly candles are gappy ({q['missing_hours'] * 100:.0f}% of the "
                      "last week missing)"), None
    return ticker, None, q


def quality(pair: str, now: pd.Timestamp, get=bn._get) -> dict:
    """Listing day, days of history, the median daily USDT volume and days without trading (last 30 closed days)."""
    first = get("/api/v3/klines", {"symbol": pair, "interval": "1d", "startTime": 0, "limit": 1})
    recent = bn.klines(pair, "1D", now.normalize() - pd.Timedelta(days=31), get=get)
    recent = recent[recent.index < now.normalize()].tail(30)                # closed days only
    listed = pd.to_datetime(int(first[0][0]), unit="ms", utc=True) if first else None
    return {
        "listed_since": None if listed is None else listed.strftime("%Y-%m-%d"),
        "days": 0 if listed is None else int((now.normalize() - listed).days),
        "volume_usd": float(recent["volume"].median()) if len(recent) else 0.0,
        "gap_days": int((recent["volume"] <= 0).sum()) + max(0, 30 - len(recent)),
        "quiet_hours": _quiet_hours(pair, now, get),
    }


def build(top: int = TOP, coins=None, excluded_ids=None, pairs=None, price_of=None, quality_of=None, now=None,
          kinds=None, yahoo=None) -> dict:
    """yahoo(coin, now) -> (ticker, reason, quality): the fallback for coins Binance does not list (None: off)."""
    now = pd.Timestamp.now(tz="UTC") if now is None else now
    coins = top_coins(top) if coins is None else coins
    excluded_ids = not_coins() if excluded_ids is None else excluded_ids
    kinds = (labels() if coins is None else {}) if kinds is None else kinds
    pairs = bn.trading_pairs() if pairs is None else pairs
    price_of = bn.last_price if price_of is None else price_of
    quality_of = (lambda p: quality(p, now)) if quality_of is None else quality_of
    included, excluded, used_pairs = [], [], set()
    for rank, coin in enumerate(coins, 1):
        base = {"id": coin["id"], "symbol": str(coin.get("symbol") or "").upper(), "name": coin.get("name"),
                "rank": coin.get("market_cap_rank") or rank}

        def leave(reason):
            excluded.append({**base, "reason": reason})

        reason = excluded_ids.get(coin["id"]) or _named_copy(coin)
        if reason:
            leave(reason)
            continue
        pair = bn.pair_for("crypto", coin["id"], None, coin, pairs=pairs, price_of=price_of)
        if pair is None:
            what = kinds.get(coin["id"])
            if base["symbol"] in pairs:
                leave("Binance's coin with this ticker has a different price (another coin)")
            elif what in YAHOO_LEAVE_OUT or yahoo is None:
                leave(f"not traded on Binance against USDT" + (f" ({what})" if what else ""))
            else:
                ticker, why, q = yahoo(coin, now)
                if ticker is None:
                    leave(why)
                elif f"yahoo:{ticker}" in used_pairs:
                    leave(f"same Yahoo ticker as a bigger coin ({ticker})")
                else:
                    used_pairs.add(f"yahoo:{ticker}")
                    included.append({**base, "pair": f"yahoo:{ticker}", "volume_usd": round(float(coin.get("total_volume") or 0)),
                                     "listed_since": q["listed_since"], "days": q["days"]})
            continue
        if pair in used_pairs:
            leave(f"same Binance pair as a bigger coin ({pair})")
            continue
        try:
            q = quality_of(pair)
        except Exception as e:                                  # one coin failing never stops the build
            leave(f"Binance data could not be read ({type(e).__name__})")
            continue
        if q["days"] < MIN_DAYS:
            leave(f"only {q['days']} days on Binance (needs {MIN_DAYS})")
        elif q["volume_usd"] < MIN_VOLUME_USD:
            leave(f"thin trading on Binance (about ${q['volume_usd'] / 1e3:,.0f}k a day; needs "
                  f"${MIN_VOLUME_USD / 1e3:,.0f}k)")
        elif q["gap_days"] > MAX_GAP_DAYS:
            leave(f"{q['gap_days']} of the last 30 days without trading")
        elif q.get("quiet_hours", 0) > MAX_QUIET_HOURS:
            leave(f"gappy hourly candles ({q['quiet_hours'] * 100:.0f}% of the last week's hours without a trade)")
        else:
            used_pairs.add(pair)
            included.append({**base, "pair": pair, "volume_usd": round(q["volume_usd"]),
                             "listed_since": q["listed_since"], "days": q["days"]})
    return {"built_at": now.isoformat(), "rules": {**RULES, "top": len(coins)}, "included": included, "excluded": excluded}


def summary(u: dict) -> str:
    def kind(reason: str) -> str:
        if "days on Binance" in reason or "days on Yahoo" in reason:
            return "short history"
        if reason.startswith("not on Binance, and"):
            return "not on Binance; Yahoo " + ("thin" if "thin" in reason else "gappy" if "gappy" in reason
                                              else "another coin" if "another coin" in reason else "missing")
        return reason if reason.startswith("not traded") else reason.split(" (")[0]

    reasons = pd.Series([kind(e["reason"]) for e in u["excluded"]]).value_counts()
    yahoo = sum(1 for c in u["included"] if str(c.get("pair") or "").startswith("yahoo:"))
    lines = [f"Universe: {len(u['included'])} coins usable of the top {u['rules']['top']} "
             f"({len(u['included']) - yahoo} on Binance, {yahoo} from Yahoo; {len(u['excluded'])} left out)"]
    lines += [f"  {n:4}  {r}" for r, n in reasons.items()]
    return "\n".join(lines)


def register(rows) -> None:
    """Tell the candle loaders about the universe's checked sources: a Binance pair, or a Yahoo ticker for coins
    Binance does not list. rows: crypto_universe table rows (coin_id, pair) of included coins."""
    import data_fetchers

    binance, yahoo = {}, {}
    for r in rows:
        pair = str(r.get("pair") or "")
        if pair.startswith("yahoo:"):
            binance[r["coin_id"]] = None
            yahoo[r["coin_id"]] = pair[6:]
        elif pair:
            binance[r["coin_id"]] = pair
    bn.register(binance)
    for coin_id, ticker in yahoo.items():
        data_fetchers.YF_BY_COINGECKO_ID.setdefault(coin_id, ticker)


def save(supabase, u: dict) -> int:
    """Replace the crypto_universe table (sql/2026-11-17_funnels.sql) with this build."""
    rows = [{"coin_id": c["id"], "symbol": c["symbol"], "name": c["name"] or "", "rank": c["rank"], "included": True,
             "pair": c["pair"], "reason": None, "volume_usd": c["volume_usd"], "listed_since": c["listed_since"],
             "built_at": u["built_at"]} for c in u["included"]]
    rows += [{"coin_id": c["id"], "symbol": c["symbol"], "name": c["name"] or "", "rank": c["rank"], "included": False,
              "pair": None, "reason": c["reason"][:300], "volume_usd": None, "listed_since": None,
              "built_at": u["built_at"]} for c in u["excluded"]]
    for i in range(0, len(rows), 200):
        supabase.table("crypto_universe").upsert(rows[i:i + 200]).execute()
    supabase.table("crypto_universe").delete().lt("built_at", u["built_at"]).execute()   # coins no longer in the top
    return len(rows)


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("out")
    top = int(argv[argv.index("--top") + 1]) if "--top" in argv else TOP
    u = build(top, yahoo=yahoo_fallback)
    out.mkdir(parents=True, exist_ok=True)
    (out / "crypto_universe.json").write_text(json.dumps(u, indent=1))
    print(summary(u))
    if "--save" in argv and u["included"]:
        import os

        from supabase import create_client

        try:
            n = save(create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]), u)
            print(f"Saved {n} rows to crypto_universe.")
        except Exception as exc:          # the table may not be installed yet (sql/2026-11-17_funnels.sql)
            print(f"Not saved to the database: {str(exc)[:200]}")
    return 0 if u["included"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
