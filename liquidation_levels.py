"""Estimated liquidation levels for crypto futures, from free Coinalyze data.

This is an estimate, built the way public liquidation heatmaps are, only simpler:

1. Each hour that open interest (all open futures positions, in USD) rises, the new
   positions are taken to have been opened near that hour's typical price.
2. They are split into longs and shorts with that hour's long/short ratio (half and
   half when there is none), and spread over common leverage levels.
3. A long at 25x is force-closed about 4% below its entry, a short about 4% above
   (less a small maintenance margin). That amount is added to the price bucket there.
4. When open interest falls, positions were closed, so every bucket shrinks by the
   same share. When the price trades through a bucket, those positions are gone.

What is left are the prices where the most positions would still be liquidated:
longs below the current price, shorts above. The leverage mix is an assumption,
so the levels are a rough guide and are not part of the score.
"""

from __future__ import annotations

import math
import time

import requests

API_BASE = "https://api.coinalyze.net/v1"
# Share of new positions assumed at each leverage. A guess, as in every public model.
LEVERAGE_MIX = {10: 0.35, 25: 0.30, 50: 0.20, 100: 0.15}
MAINTENANCE_MARGIN = 0.005
BUCKET_SHARE = 0.0025          # buckets are 0.25% of price wide
LOOKBACK_HOURS = 7 * 24
LEVELS_PER_SIDE = 5
PREFERRED_EXCHANGES = ("binance", "bybit", "okx")
MARKETS_PER_COIN = 3
REFRESH_SECONDS = 60 * 60


class RateLimited(Exception):
    """Coinalyze answered 429. Stop for this run; the next run carries on."""


# ---------------------------------------------------------------- the model

def _bucket(price: float) -> int:
    """Log-spaced bucket index, so a bucket is the same share of price everywhere."""
    return int(math.floor(math.log(price) / math.log1p(BUCKET_SHARE)))


def _bucket_price(index: int) -> float:
    return math.exp((index + 0.5) * math.log1p(BUCKET_SHARE))


def estimate_levels(bars: list[dict], oi: list[dict], ratios: list[dict] | None = None,
                    per_side: int = LEVELS_PER_SIDE) -> dict:
    """bars: [{t, h, l, c}], oi: [{t, c}] in USD, ratios: [{t, r}] longs per short.

    Returns {"price", "longs": [{"price", "usd"}], "shorts": [...]} with the
    strongest levels first. Longs sit below the price, shorts above.
    """
    by_time_oi = {int(row["t"]): float(row["c"]) for row in oi if _ok(row.get("c"))}
    by_time_ratio = {int(row["t"]): float(row["r"]) for row in (ratios or []) if _ok(row.get("r"))}
    longs: dict[int, float] = {}
    shorts: dict[int, float] = {}
    previous_oi = None
    last_close = None
    for bar in sorted(bars, key=lambda row: int(row["t"])):
        t = int(bar["t"])
        try:
            high, low, close = float(bar["h"]), float(bar["l"]), float(bar["c"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (high > 0 and low > 0 and close > 0):
            continue
        # The price traded through these levels this hour: those positions are gone.
        low_bucket, high_bucket = _bucket(low), _bucket(high)
        for index in [k for k in longs if k >= low_bucket]:
            del longs[index]
        for index in [k for k in shorts if k <= high_bucket]:
            del shorts[index]

        current_oi = by_time_oi.get(t)
        if current_oi is not None and previous_oi:
            change = current_oi - previous_oi
            if change > 0:
                entry = (high + low + close) / 3
                ratio = by_time_ratio.get(t)
                long_share = ratio / (1 + ratio) if ratio and ratio > 0 else 0.5
                for leverage, share in LEVERAGE_MIX.items():
                    amount = change * share
                    gap = 1 / leverage - MAINTENANCE_MARGIN
                    long_price = entry * (1 - gap)
                    short_price = entry * (1 + gap)
                    if long_price < low:
                        key = _bucket(long_price)
                        longs[key] = longs.get(key, 0.0) + amount * long_share
                    if short_price > high:
                        key = _bucket(short_price)
                        shorts[key] = shorts.get(key, 0.0) + amount * (1 - long_share)
            elif change < 0:
                keep = max(0.0, current_oi / previous_oi)
                for book in (longs, shorts):
                    for key in book:
                        book[key] *= keep
        if current_oi is not None:
            previous_oi = current_oi
        last_close = close

    def strongest(book: dict[int, float]) -> list[dict]:
        rows = sorted(book.items(), key=lambda item: item[1], reverse=True)[:per_side]
        return [{"price": round(_bucket_price(k), 8), "usd": round(v, 2)} for k, v in rows if v > 0]

    return {"price": last_close, "longs": strongest(longs), "shorts": strongest(shorts)}


def _ok(value) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number


# ---------------------------------------------------------------- Coinalyze

class Coinalyze:
    def __init__(self, api_key: str, session: requests.Session | None = None):
        self.key = api_key
        self.session = session or requests.Session()
        self.calls = 0

    def get(self, path: str, **params):
        params["api_key"] = self.key
        response = self.session.get(f"{API_BASE}{path}", params=params, timeout=20)
        if response.status_code == 429:
            raise RateLimited(response.headers.get("Retry-After", ""))
        response.raise_for_status()
        return response.json()

    def history(self, path: str, symbols: list[str], hours: int, **extra) -> dict[str, list[dict]]:
        now = int(time.time())
        self.calls += len(symbols)
        rows = self.get(
            path,
            symbols=",".join(symbols),
            interval="1hour",
            **{"from": now - hours * 3600, "to": now},
            **extra,
        ) or []
        return {str(row.get("symbol")): list(row.get("history") or []) for row in rows}


def pick_markets(markets: list[dict], exchanges: list[dict], coin: str, count: int = MARKETS_PER_COIN) -> list[dict]:
    """The coin's biggest stablecoin perpetual markets, on the preferred exchanges first."""
    names = {str(row.get("code")): str(row.get("name") or "").lower() for row in exchanges or []}
    coin = coin.upper()
    found = []
    for market in markets or []:
        if str(market.get("base_asset") or "").upper() != coin:
            continue
        if not market.get("is_perpetual") or str(market.get("margined") or "").upper() != "STABLE":
            continue
        exchange = names.get(str(market.get("exchange")), str(market.get("exchange") or "").lower())
        rank = next((i for i, name in enumerate(PREFERRED_EXCHANGES) if name in exchange), None)
        if rank is None:
            continue
        found.append((rank, str(market.get("quote_asset") or "") != "USDT", market))
    found.sort(key=lambda item: (item[0], item[1]))
    chosen, seen = [], set()
    for rank, _not_usdt, market in found:
        if rank in seen:
            continue
        seen.add(rank)
        chosen.append(market)
        if len(chosen) >= count:
            break
    return chosen


def combine_open_interest(histories) -> list[dict]:
    """Open interest added up across markets, only for hours every market reported.

    An hour missing from one market would otherwise look like positions closing.
    """
    tables = []
    for rows in histories:
        table = {int(row["t"]): float(row["c"]) for row in rows or [] if _ok(row.get("c"))}
        if table:
            tables.append(table)
    if not tables:
        return []
    shared = set.intersection(*(set(table) for table in tables))
    return [{"t": t, "c": sum(table[t] for table in tables)} for t in sorted(shared)]


def levels_for_coin(client: Coinalyze, markets: list[dict], hours: int = LOOKBACK_HOURS) -> dict:
    """Fetch the coin's data from its chosen markets and estimate its levels."""
    symbols = [str(m["symbol"]) for m in markets]
    oi_by_symbol = client.history("/open-interest-history", symbols, hours, convert_to_usd="true")
    lead = symbols[0]
    bars = client.history("/ohlcv-history", [lead], hours).get(lead, [])
    ratio_market = next((m for m in markets if m.get("has_long_short_ratio_data")), None)
    ratios = []
    if ratio_market:
        ratios = client.history("/long-short-ratio-history", [str(ratio_market["symbol"])], hours).get(
            str(ratio_market["symbol"]), []
        )
    oi = combine_open_interest(oi_by_symbol.values())
    result = estimate_levels(bars, oi, ratios)
    result["markets"] = symbols
    return result


# ---------------------------------------------------------------- worker step

def refresh_due(supabase, catalog: dict, api_key: str, crypto_ticker, budget: int = 30) -> None:
    """Update the stored levels of watched coins older than an hour, oldest first.

    Stays within Coinalyze's 40 calls a minute: a run spends at most `budget` calls,
    and a 429 answer ends the step until the next run. crypto_ticker maps a watchlist
    id to its ticker (SUI, BTC, ...).
    """
    from market_store import asset_market_key

    coins = [str(asset_id) for kind, asset_id in catalog if kind == "Crypto"]
    if not coins or not api_key:
        if coins and not api_key:
            print("Liquidation levels skipped: set the COINALYZE_API_KEY secret for the background worker.")
        return
    keys = {asset_market_key("Crypto", coin): coin for coin in coins}
    try:
        rows = (
            supabase.table("asset_market")
            .select("asset_key, liq_updated_at")
            .in_("asset_key", list(keys))
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print(f"Liquidation levels skipped. Run the latest supabase_rls.sql. {str(exc)[:160]}")
        return
    stamps = {str(row.get("asset_key")): _epoch(row.get("liq_updated_at")) for row in rows}
    now = time.time()
    due = sorted(
        (stamps.get(key) or 0.0, key)
        for key in keys
        if key in stamps and now - (stamps.get(key) or 0.0) >= REFRESH_SECONDS
    )
    if not due:
        return

    client = Coinalyze(api_key)
    try:
        markets = client.get("/future-markets")
        exchanges = client.get("/exchanges")
        client.calls += 2
    except RateLimited:
        print("Liquidation levels: Coinalyze rate limit reached; trying again next run.")
        return
    except Exception as exc:
        print(f"Liquidation levels: Coinalyze market list failed: {str(exc)[:160]}")
        return

    for _stamp, key in due:
        coin = keys[key]
        ticker = (crypto_ticker(coin) or "").upper()
        chosen = pick_markets(markets, exchanges, ticker) if ticker else []
        if client.calls + len(chosen) + 2 > budget:
            break
        stored_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if not chosen:
            record = {"status": "no_market", "ticker": ticker}
        else:
            try:
                record = levels_for_coin(client, chosen)
                record["status"] = "ok"
            except RateLimited:
                print("Liquidation levels: Coinalyze rate limit reached; trying again next run.")
                break
            except Exception as exc:
                record = {"status": "error", "detail": str(exc)[:200]}
        try:
            (
                supabase.table("asset_market")
                .update({"liq_levels": record, "liq_updated_at": stored_at})
                .eq("asset_key", key)
                .execute()
            )
            print(f"Liquidation levels for {ticker or coin}: {record.get('status')}")
        except Exception as exc:
            print(f"Liquidation levels for {ticker or coin} could not be saved: {str(exc)[:160]}")


def _epoch(value) -> float | None:
    from datetime import datetime

    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None
