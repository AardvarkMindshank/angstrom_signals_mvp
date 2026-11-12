"""
Tides: the macro layer (preview, 12 Nov 2026; brief https://claude.ai/artifact/HLR3SoaRRuXE11EF5kzCxy).

Twelve currents, each read from public daily data, give two separate readings:
- the Tide: how supportive or defensive conditions are for risk-taking (coming in, slack, going out);
- the Sea state: how turbulent they are (calm, moderate, rough, storm).

Every rule below is fixed and written down before any testing (decisions 4 and 9 of the review):
- Each current: its latest value, 7- and 30-day change, a 0-100 score against its own last 5 years of daily
  readings (named bands, as Glassnode does), and a momentum reading: the 30-day change divided by the typical size
  of a 30-day change over those 5 years. Its contribution is sign x tanh(momentum), between -1 and +1, where the sign
  says which way is risk-supportive. Rising / falling / flat: momentum above 0.5, below -0.5, else flat.
- Currents with weight 0 are shown but do not vote: gold (rising gold is not automatically risk-off), oil (demand
  or supply shock), the yield curve (rates must not vote three times).
- Each family averages its voting currents; the Tide is the weighted sum of the families (weights below, declared,
  to be reviewed against what we learn). Above +0.20 coming in, below -0.20 going out, else slack. A new label
  counts only once it has held for 5 daily closes (no whipsaw).
- Sea state: the average of the VIX's and Bitcoin's 30-day volatility scores against their own 5 years:
  under 40 calm, 40 to 65 moderate, 65 to 85 rough, 85 and over storm.
- Headwind or tailwind for a market: the average contribution of the currents declared relevant to it.
- Crypto Fear & Greed is shown on its own and never votes (it already sits inside the sentiment score).

Preview limits, said on the page: history is reconstructed from today's data (point-in-time recording starts with
the daily record); CPI uses revised data, not first prints; real-rate, auction and Fed-odds readings come later.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

YEARS = 5                       # each current is scored against its own last 5 years
MOMENTUM_DAYS = 30              # trading days
FLAT = 0.5                      # |momentum| below this = flat
TIDE_IN, TIDE_OUT = 0.20, -0.20
PERSIST = 5                     # daily closes a new Tide label must hold
SEA_BANDS = ((40, "calm", "low volatility"), (65, "moderate", "normal volatility"),
             (85, "rough", "high volatility"), (101, "storm", "extreme volatility"))
BANDS = ((20, "very low"), (40, "low"), (60, "normal"), (80, "high"), (101, "very high"))

FAMILIES = {   # key: (name, weight, icon)
    "money": ("Money and rates", 0.30, "🏦"),
    "havens": ("Safe havens and fear", 0.20, "🛡️"),
    "growth": ("Growth and credit", 0.30, "🏗️"),
    "rotation": ("Rotation", 0.20, "🔄"),
}

# key, name, family, icon, source, sign (+1: rising is risk-supportive), weight (0 = shown, does not vote), unit,
# what it measures, rising means, falling means
CURRENTS = (
    ("short_rates", "Short rates", "money", "⏱️", ("fred", "DGS2"), -1, 1, "pts",
     "2-year Treasury yield: where markets expect the Fed to take rates",
     "markets expect tighter money", "markets expect easier money"),
    ("long_rates", "Long rates", "money", "📏", ("yahoo", "^TNX"), -1, 1, "pts",
     "10-year Treasury yield: the cost of long-term borrowing",
     "borrowing costs rising, pressure on valuations", "borrowing costs easing"),
    ("curve", "Yield curve", "money", "〰️", ("fred", "T10Y2Y"), 1, 0, "pts",
     "10-year minus 2-year yield; below zero (inverted) has often come before recessions",
     "steepening", "flattening or inverting"),
    ("dollar", "US dollar", "money", "💵", ("yahoo", "DX-Y.NYB"), -1, 1, "%",
     "US dollar index against major currencies",
     "a stronger dollar, usually a weight on crypto, gold and global equities", "a weaker dollar"),
    ("inflation", "Inflation", "money", "🛒", ("fred_yoy", "CPIAUCSL"), -1, 1, "pts",
     "Consumer prices, change over 12 months (monthly release)",
     "inflation rising: pressure on the Fed to keep rates high", "inflation easing"),
    ("gold", "Gold", "havens", "🥇", ("yahoo", "GC=F"), 1, 0, "%",
     "Gold price: fear, inflation worry or a weak dollar; hurt by rising real rates",
     "gold rising", "gold falling"),
    ("fear", "Fear (VIX)", "havens", "😨", ("yahoo", "^VIX"), -1, 1, "pts",
     "VIX: what traders pay to protect against stock-market swings",
     "fear rising", "fear easing"),
    ("copper_gold", "Copper vs gold", "growth", "🔶", ("ratio", "HG=F", "GC=F"), 1, 1, "%",
     "Copper against gold: growth expectations against fear",
     "growth hopes beating fear", "fear beating growth hopes"),
    ("oil", "Oil", "growth", "🛢️", ("yahoo", "CL=F"), 1, 0, "%",
     "WTI crude oil: demand (when copper agrees) or a supply shock (when it does not)",
     "oil rising", "oil falling"),
    ("credit", "Credit", "growth", "🏛️", ("ratio", "HYG", "IEF"), 1, 1, "%",
     "Riskier company bonds against safe Treasuries (HYG vs IEF); falls when stress builds",
     "credit calm, risk appetite healthy", "credit stress building"),
    ("equity_rotation", "Equities vs bonds", "rotation", "📈", ("ratio", "SPY", "TLT"), 1, 1, "%",
     "US equities against long Treasury bonds (SPY vs TLT)",
     "money rotating into equities", "money rotating into bonds"),
    ("crypto_rotation", "Crypto rotation", "rotation", "🪙", ("ratio", "ETH-USD", "BTC-USD"), 1, 1, "%",
     "Ether against Bitcoin: money moving out along the crypto risk curve",
     "money moving from Bitcoin towards altcoins", "money retreating to Bitcoin"),
)
CURRENT_KEYS = tuple(c[0] for c in CURRENTS)
SPEC = {c[0]: dict(zip(("key", "name", "family", "icon", "source", "sign", "weight", "unit", "measures",
                        "rising", "falling"), c)) for c in CURRENTS}

# Which currents bear on which market, declared (decision 7: headwind or tailwind is per market and direction).
MARKETS = {
    "crypto": ("Crypto longs", ("dollar", "long_rates", "fear", "credit", "crypto_rotation")),
    "equity": ("Equity longs", ("long_rates", "fear", "credit", "copper_gold", "equity_rotation")),
}

EXTRA_SYMBOLS = ("BTC-USD", "XLY", "XLP", "IWM", "^TYX", "HG=F")


# ------------------------------------------------------------------------------------------------ data

def symbols_needed() -> tuple[set[str], set[str]]:
    yahoo, fred = set(EXTRA_SYMBOLS), set()
    for c in CURRENTS:
        src = c[4]
        if src[0] == "yahoo":
            yahoo.add(src[1])
        elif src[0] == "ratio":
            yahoo.update(src[1:])
        else:
            fred.add(src[1])
    return yahoo, fred


def fetch_yahoo(symbol: str, years: int = YEARS + 1) -> pd.Series:
    import yfinance as yf

    frame = yf.Ticker(symbol).history(period=f"{years}y", interval="1d", auto_adjust=False)
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    s = frame["Close"].dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize() if s.index.tz is not None else \
        pd.to_datetime(s.index).normalize()
    return s[~s.index.duplicated(keep="last")].astype(float)


def fetch_fred(series_id: str, session=None) -> pd.Series:
    """FRED's public CSV download (no key). Missing values are '.'."""
    import io

    import requests

    get = (session or requests).get
    r = get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": series_id}, timeout=20)
    r.raise_for_status()
    frame = pd.read_csv(io.StringIO(r.text))
    frame.columns = ["date", "value"]
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    s = frame.dropna().set_index(pd.to_datetime(frame.dropna()["date"]))["value"]
    return s.astype(float)


def fetch_all(log=print) -> dict[str, pd.Series]:
    yahoo, fred = symbols_needed()
    out = {}
    for sym in sorted(yahoo):
        try:
            out[sym] = fetch_yahoo(sym)
        except Exception as exc:
            log(f"Tides: {sym} not read ({str(exc)[:80]})")
    for sid in sorted(fred):
        try:
            out[f"fred:{sid}"] = fetch_fred(sid)
        except Exception as exc:
            log(f"Tides: FRED {sid} not read ({str(exc)[:80]})")
    return out


def series_for(key: str, raw: dict[str, pd.Series]) -> pd.Series:
    """The daily series a current reads (business days, carried forward over gaps of up to 5 days)."""
    src = SPEC[key]["source"]
    if src[0] == "yahoo":
        s = raw.get(src[1])
    elif src[0] == "fred":
        s = raw.get(f"fred:{src[1]}")
    elif src[0] == "fred_yoy":
        m = raw.get(f"fred:{src[1]}")
        s = None if m is None or m.empty else (m / m.shift(12) - 1).dropna() * 100
        if s is not None:
            s = s.copy()
            s.index = s.index + pd.offsets.MonthEnd(1) + pd.Timedelta(days=12)   # roughly when it is released
    else:
        a, b = raw.get(src[1]), raw.get(src[2])
        s = None if a is None or b is None or a.empty or b.empty else (a / b).dropna()
    if s is None or s.empty:
        return pd.Series(dtype=float)
    days = pd.bdate_range(s.index.min(), max(s.index.max(), pd.Timestamp.now().normalize()))
    return s.reindex(s.index.union(days)).ffill(limit=40 if src[0] == "fred_yoy" else 5).reindex(days).dropna()


# ------------------------------------------------------------------------------------------------ maths

def band(score: float | None) -> str | None:
    if score is None:
        return None
    return next(name for top, name in BANDS if score < top)


def change(s: pd.Series, days: int, unit: str) -> float | None:
    if len(s) <= days:
        return None
    a, b = float(s.iloc[-1 - days]), float(s.iloc[-1])
    if unit == "pts":
        return b - a
    return (b / a - 1) * 100 if a else None


def percentile(s: pd.Series, value: float | None = None) -> float | None:
    hist = s.iloc[-YEARS * 252:]
    if len(hist) < 252:
        return None
    v = float(hist.iloc[-1]) if value is None else value
    return float((hist < v).mean() * 100 + (hist == v).mean() * 50)


def momentum_series(s: pd.Series, unit: str) -> pd.Series:
    """30-day change over its typical size in the past 5 years (a z-score), for every day."""
    move = s.diff(MOMENTUM_DAYS) if unit == "pts" else np.log(s).diff(MOMENTUM_DAYS)
    scale = move.rolling(YEARS * 252, min_periods=252).std()
    return (move / scale).replace([np.inf, -np.inf], np.nan)


def direction(m: float | None) -> str:
    if m is None or (isinstance(m, float) and math.isnan(m)):
        return "unknown"
    return "rising" if m > FLAT else "falling" if m < -FLAT else "flat"


def read_current(key: str, s: pd.Series) -> dict:
    spec = SPEC[key]
    if s.empty or len(s) < 300:
        return {"key": key, "status": "missing", "name": spec["name"]}
    mom = momentum_series(s, spec["unit"])
    m = mom.iloc[-1]
    m = None if pd.isna(m) else float(m)
    score = percentile(s)
    contrib = (mom.apply(math.tanh) * spec["sign"]).dropna()
    return {
        "key": key, "status": "ok", "name": spec["name"], "family": spec["family"], "icon": spec["icon"],
        "value": float(s.iloc[-1]), "as_of": s.index[-1].date().isoformat(),
        "change_7": change(s, 5, spec["unit"]), "change_30": change(s, 21, spec["unit"]), "unit": spec["unit"],
        "score": None if score is None else round(score, 1), "band": band(score),
        "momentum": None if m is None else round(m, 3), "direction": direction(m),
        "contribution": None if m is None else round(spec["sign"] * math.tanh(m), 3),
        "weight": spec["weight"], "sign": spec["sign"],
        "spark": [round(float(v), 4) for v in s.iloc[-90:].tolist()],
        "history": contrib.iloc[-520:],      # for the waves view and the Tide history (not stored as is)
    }


def label_for(score: float) -> str:
    return "in" if score > TIDE_IN else "out" if score < TIDE_OUT else "slack"


def persist(raw_labels: pd.Series, days: int = PERSIST) -> pd.Series:
    """Hysteresis: the shown label changes only when a new raw label has held for `days` closes."""
    shown, current, run, last = [], None, 0, None
    for lab in raw_labels:
        run = run + 1 if lab == last else 1
        last = lab
        if current is None or (lab != current and run >= days):
            current = lab
        shown.append(current)
    return pd.Series(shown, index=raw_labels.index)


def tide(readings: dict[str, dict]) -> dict:
    """Family scores, the Tide's score history, its shown label (with persistence) and how long it has held."""
    fam_hist, fam_now = {}, {}
    for fam in FAMILIES:
        members = [r for r in readings.values() if r.get("status") == "ok" and r["family"] == fam and r["weight"]]
        if not members:
            continue
        frame = pd.concat([r["history"] for r in members], axis=1)
        fam_hist[fam] = frame.mean(axis=1, skipna=True)
        fam_now[fam] = float(np.nanmean([r["contribution"] for r in members if r["contribution"] is not None]))
    if not fam_hist:
        return {"status": "missing"}
    weights = {f: FAMILIES[f][1] for f in fam_hist}
    frame = pd.concat(fam_hist, axis=1).dropna(how="all")
    w = pd.DataFrame({f: frame[f].notna() * weights[f] for f in frame})
    score = (frame.fillna(0) * pd.DataFrame(weights, index=frame.index)).sum(axis=1) / w.sum(axis=1)
    score = score.dropna()
    shown = persist(score.apply(label_for))
    now_label = shown.iloc[-1]
    held = int((shown[::-1] != now_label).argmax()) if (shown != now_label).any() else len(shown)
    raw_now = label_for(float(score.iloc[-1]))
    return {"status": "ok", "score": round(float(score.iloc[-1]), 3), "label": now_label, "held_days": held,
            "raw_label": raw_now, "pending": raw_now != now_label,
            "families": {f: round(v, 3) for f, v in fam_now.items()},
            "history": [[d.date().isoformat(), round(float(v), 3)] for d, v in score.iloc[-520:].items()],
            "labels": [[d.date().isoformat(), lab] for d, lab in shown.iloc[-520:].items()]}


def realised_vol(prices: pd.Series, days: int = 30) -> pd.Series:
    return np.log(prices).diff().rolling(days).std() * math.sqrt(365)


def sea_state(raw: dict[str, pd.Series]) -> dict:
    parts = {}
    vix = raw.get("^VIX")
    if vix is not None and len(vix) > 300:
        parts["vix"] = percentile(vix)
    btc = raw.get("BTC-USD")
    if btc is not None and len(btc) > 330:
        vol = realised_vol(btc).dropna()
        parts["btc_vol"] = percentile(vol)
        parts["btc_vol_now"] = float(vol.iloc[-1]) * 100
    scores = [v for k, v in parts.items() if k in ("vix", "btc_vol") and v is not None]
    if not scores:
        return {"status": "missing"}
    score = float(np.mean(scores))
    name, plain = next((n, p) for top, n, p in SEA_BANDS if score < top)
    return {"status": "ok", "score": round(score, 1), "state": name, "plain": plain,
            "vix_score": parts.get("vix"), "btc_vol_score": parts.get("btc_vol"),
            "btc_vol": parts.get("btc_vol_now")}


def winds(readings: dict[str, dict]) -> dict[str, dict]:
    out = {}
    for market, (name, keys) in MARKETS.items():
        vals = [readings[k]["contribution"] for k in keys
                if readings.get(k, {}).get("status") == "ok" and readings[k]["contribution"] is not None]
        if not vals:
            continue
        v = float(np.mean(vals))
        word = "tailwind" if v > 0.2 else "headwind" if v < -0.2 else "neither"
        strongest = sorted(((readings[k]["contribution"], k) for k in keys
                            if readings.get(k, {}).get("contribution") is not None), key=lambda x: -abs(x[0]))[:2]
        out[market] = {"name": name, "score": round(v, 3), "wind": word, "drivers": [k for _, k in strongest]}
    return out


def extras(raw: dict[str, pd.Series]) -> dict:
    """Readings shown beside their current but not voting: 30-year yield, copper alone, sector and size rotation."""
    out = {}
    for key, sym, unit in (("long_30y", "^TYX", "pts"), ("copper", "HG=F", "%")):
        s = raw.get(sym)
        if s is not None and len(s) > 30:
            out[key] = {"value": float(s.iloc[-1]), "change_30": change(s, 21, unit)}
    for key, a, b in (("cyclical_defensive", "XLY", "XLP"), ("small_large", "IWM", "SPY")):
        if raw.get(a) is not None and raw.get(b) is not None and len(raw[a]) > 30:
            r = (raw[a] / raw[b]).dropna()
            out[key] = {"change_30": change(r, 21, "%"), "score": percentile(r)}
    return out


def snapshot(raw: dict[str, pd.Series], btc_dominance: float | None = None, fear_greed: float | None = None,
             now: datetime | None = None) -> dict:
    """Everything the panel shows, from the raw series. JSON-ready (the histories are cut to lists)."""
    readings = {k: read_current(k, series_for(k, raw)) for k in CURRENT_KEYS}
    t = tide(readings)
    out = {"computed_at": (now or datetime.now(timezone.utc)).isoformat(), "version": 1, "tide": t,
           "sea": sea_state(raw), "winds": winds(readings), "extras": extras(raw),
           "btc_dominance": btc_dominance, "fear_greed": fear_greed, "currents": {}}
    for k, r in readings.items():
        hist = r.pop("history", None)
        if hist is not None:
            r["wave"] = [round(float(v), 3) for v in hist.iloc[-260:].tolist()]
        out["currents"][k] = r
    return out


# ------------------------------------------------------------------------------------------------ words

TIDE_WORDS = {"in": ("Tide coming in", "risk-supportive", "🌊⬆"),
              "slack": ("Slack tide", "mixed", "🌊↔"),
              "out": ("Tide going out", "risk-defensive", "🌊⬇")}


def summary(snap: dict, upcoming: list[dict] | None = None, now: datetime | None = None) -> list[str]:
    """The factual daily note, from fixed templates (decision 16: facts from templates, checked for accuracy)."""
    lines = []
    t, sea = snap.get("tide") or {}, snap.get("sea") or {}
    if t.get("status") == "ok":
        name, plain, _ = TIDE_WORDS[t["label"]]
        line = f"{name} ({plain}) for {t['held_days']} trading days."
        if t.get("pending"):
            line += f" Readings now point to {TIDE_WORDS[t['raw_label']][0].lower()}; it changes once that holds 5 closes."
        lines.append(line)
    if sea.get("status") == "ok":
        lines.append(f"Sea state {sea['state']} ({sea['plain']}).")
    cur = [c for c in (snap.get("currents") or {}).values() if c.get("status") == "ok" and c.get("weight")]
    strong = sorted(cur, key=lambda c: -abs(c.get("contribution") or 0))[:3]
    if strong:
        bits = []
        for c in strong:
            word = SPEC[c["key"]][c["direction"]] if c["direction"] in ("rising", "falling") else "flat"
            pull = "supportive" if (c["contribution"] or 0) > 0 else "defensive"
            bits.append(f"{c['name'].lower()} {c['direction']} ({word}; {pull})")
        lines.append("Strongest currents: " + "; ".join(bits) + ".")
    for w in (snap.get("winds") or {}).values():
        if w["wind"] != "neither":
            lines.append(f"A {w['wind']} for {w['name'].lower()}, led by "
                         + " and ".join(SPEC[k]["name"].lower() for k in w["drivers"]) + ".")
    if upcoming:
        import macro_calendar as mc

        e = upcoming[0]
        lines.append(f"Next scheduled event: {e['name']} ({e['reference']}), {mc.when_words(e['at'], now)}.")
    return lines
