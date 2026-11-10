"""
The equity universe for equity funnels (asked 10 Nov 2026): the S&P 500, with a quality gate, and every share left out
listed with its reason. Candles come from Yahoo Finance, as for every share in the app.

Gate: a price of at least MIN_PRICE, a median daily dollar volume over the last 30 sessions of at least MIN_DOLLAR_VOLUME,
and about 3 years of history (the weekly stage). The next earnings date is kept (shown in the Stage hover; prices can jump on a report).

Run: python equity_universe.py out/ [--save]   (GitHub runs it after the New York close; needs Wikipedia and Yahoo)
"""

from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

MIN_PRICE = 5.0
MIN_DOLLAR_VOLUME = 20_000_000
MIN_DAYS = 1100                  # about 3 years: the weekly stage reads EMA 50 on weekly candles (~150 weeks)
LIST_URLS = ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
             "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv")
RULES = {"list": "S&P 500", "min_price": MIN_PRICE, "min_dollar_volume": MIN_DOLLAR_VOLUME, "min_days": MIN_DAYS,
         "venue": "Yahoo Finance (US exchanges)"}
_HEADERS = {"User-Agent": "AngstromSignals/1.0 (market research dashboard)"}


def yahoo_ticker(symbol: str) -> str:
    """Wikipedia writes BRK.B; Yahoo writes BRK-B."""
    return str(symbol).strip().upper().replace(".", "-")


def constituents() -> list[dict]:
    """[{ticker, name, sector}] for the S&P 500: Wikipedia, else the datasets CSV on GitHub."""
    try:
        html = requests.get(LIST_URLS[0], headers=_HEADERS, timeout=30).text
        table = pd.read_html(io.StringIO(html))[0]
        return [{"ticker": yahoo_ticker(r["Symbol"]), "name": str(r["Security"]), "sector": str(r["GICS Sector"])}
                for _, r in table.iterrows()]
    except Exception as exc:
        print(f"Wikipedia list failed ({type(exc).__name__}); using the GitHub copy")
    table = pd.read_csv(io.StringIO(requests.get(LIST_URLS[1], headers=_HEADERS, timeout=30).text))
    name_col = "Security" if "Security" in table.columns else "Name"
    sector_col = "GICS Sector" if "GICS Sector" in table.columns else "Sector"
    return [{"ticker": yahoo_ticker(r["Symbol"]), "name": str(r[name_col]), "sector": str(r.get(sector_col) or "")}
            for _, r in table.iterrows()]


def quality(ticker: str, now: pd.Timestamp) -> dict | None:
    """Price, median dollar volume (30 sessions), days of history, market cap and next earnings, from Yahoo."""
    import yfinance as yf

    t = yf.Ticker(ticker)
    daily = t.history(period="5y", interval="1d", auto_adjust=False)
    if daily is None or daily.empty:
        return None
    recent = daily.tail(30)
    first = pd.Timestamp(daily.index[0])
    first = first.tz_convert("UTC") if first.tzinfo else first.tz_localize("UTC")
    out = {"price": float(daily["Close"].iloc[-1]),
           "volume_usd": float((recent["Close"] * recent["Volume"]).median()),
           "days": int((now.normalize() - first.normalize()).days),          # 5 years asked
           "market_cap": None, "next_earnings": None}
    try:
        out["market_cap"] = float(t.fast_info.get("market_cap") or 0) or None
    except Exception:
        pass
    try:
        cal = t.calendar
        dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
        upcoming = [pd.Timestamp(d) for d in (dates or []) if pd.Timestamp(d) >= now.normalize().tz_localize(None)]
        out["next_earnings"] = min(upcoming).strftime("%Y-%m-%d") if upcoming else None
    except Exception:
        pass
    return out


def build(shares=None, quality_of=None, now=None, pause: float = 0.0) -> dict:
    now = pd.Timestamp.now(tz="UTC") if now is None else now
    shares = constituents() if shares is None else shares
    quality_of = (lambda t: quality(t, now)) if quality_of is None else quality_of
    included, excluded = [], []
    for s in shares:
        base = {"ticker": s["ticker"], "name": s.get("name") or s["ticker"], "sector": s.get("sector")}
        try:
            q = quality_of(s["ticker"])
        except Exception as e:
            excluded.append({**base, "reason": f"Yahoo could not be read ({type(e).__name__})"})
            continue
        if pause:
            time.sleep(pause)
        if q is None:
            excluded.append({**base, "reason": "no prices on Yahoo Finance"})
        elif q["days"] < MIN_DAYS:
            excluded.append({**base, "reason": f"only {q['days']} days of history (the weekly stage needs about 3 "
                                               "years)"})
        elif q["price"] < MIN_PRICE:
            excluded.append({**base, "reason": f"price under ${MIN_PRICE:.0f} (${q['price']:.2f})"})
        elif q["volume_usd"] < MIN_DOLLAR_VOLUME:
            excluded.append({**base, "reason": f"thin trading (about ${q['volume_usd'] / 1e6:.0f}M a day; needs "
                                               f"${MIN_DOLLAR_VOLUME / 1e6:.0f}M)"})
        else:
            included.append({**base, "price": round(q["price"], 4), "volume_usd": round(q["volume_usd"]),
                             "market_cap": q.get("market_cap"), "next_earnings": q.get("next_earnings")})
    included.sort(key=lambda c: -(c.get("market_cap") or 0))
    for rank, c in enumerate(included, 1):
        c["rank"] = rank
    return {"built_at": now.isoformat(), "rules": {**RULES, "size": len(shares)}, "included": included,
            "excluded": excluded}


def summary(u: dict) -> str:
    reasons = pd.Series([e["reason"].split(" (")[0] for e in u["excluded"]]).value_counts()
    lines = [f"Equity universe: {len(u['included'])} usable of {u['rules']['size']} ({len(u['excluded'])} left out)"]
    lines += [f"  {n:4}  {r}" for r, n in reasons.items()]
    return "\n".join(lines)


def save(supabase, u: dict) -> int:
    rows = [{"ticker": c["ticker"], "name": c["name"], "sector": c.get("sector"), "rank": c["rank"], "included": True,
             "reason": None, "volume_usd": c["volume_usd"], "price": c["price"], "next_earnings": c.get("next_earnings"),
             "built_at": u["built_at"]} for c in u["included"]]
    rows += [{"ticker": c["ticker"], "name": c["name"], "sector": c.get("sector"), "rank": None, "included": False,
              "reason": c["reason"][:300], "volume_usd": None, "price": None, "next_earnings": None,
              "built_at": u["built_at"]} for c in u["excluded"]]
    for i in range(0, len(rows), 200):
        supabase.table("equity_universe").upsert(rows[i:i + 200]).execute()
    supabase.table("equity_universe").delete().lt("built_at", u["built_at"]).execute()
    return len(rows)


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("out")
    u = build(pause=0.05)
    out.mkdir(parents=True, exist_ok=True)
    (out / "equity_universe.json").write_text(json.dumps(u, indent=1))
    print(summary(u))
    if "--save" in argv and u["included"]:
        import os

        from supabase import create_client

        try:
            n = save(create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]), u)
            print(f"Saved {n} rows to equity_universe.")
        except Exception as exc:          # the table may not be installed yet (sql/2026-11-18_equity_funnels.sql)
            print(f"Not saved to the database: {str(exc)[:200]}")
    return 0 if u["included"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
