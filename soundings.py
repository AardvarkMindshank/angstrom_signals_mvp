"""
Soundings (18 Nov 2026; the "Mined from moves" part of the Discovery lab design): start from the moves and look back.

Every sustained rise (and, separately, every fall) in the saved daily history is marked, then the signal readings at
the close before each move are searched for conditions, and pairs of conditions, that came before moves far more
often than usual. Anything found is a suspect, not a discovery: it must also hold on later years the search never
saw, on most coins, and survive the correction for how many conditions were tried.

Settings agreed with Angus (18 Nov 2026), to be tweaked later:
- A rise: price goes 2 typical moves (20-candle average true range) above the close within the next 6 daily
  candles, without first going 1 typical move below it. A fall is the mirror image. A candle that touches both is
  neither.
- Crypto first (the saved research coins), daily candles first.
- Search on history to the end of 2022; confirm on 2023 to 29 Oct 2024. Nothing from the protected hold-out
  (30 Oct 2024 on) is ever read: the saved prices are cut before it, and every move window must end before it.

How a condition is judged
- Each day the condition holds is compared with the same coin's usual chance of a move in the same year, on the
  same side of its 200-day average (the comparable days, as What followed does), so a bull year or a strong coin
  can't make a condition look good.
- The differences are pooled by calendar date and resampled in blocks of calendar days across all coins together
  (research_stats.studentised_test), because coins move together and consecutive days overlap.
- Lift = how often a move followed the condition / how often it usually followed on comparable days. 1 is noise.
- Search: Benjamini-Hochberg over every condition and pair tried (false discoveries kept to 10%), plus a minimum
  lift, enough days and enough coins.
- Themes: the survivors are mostly one idea in many forms ("heavy candle + overbought" in a dozen pairs), so they
  are grouped, using the search years only: the strongest survivor leads a theme, and any later one sharing a
  condition with it joins that theme. Only the lead of each theme (at most MAX_THEMES) is confirmed.
- Confirmation: the theme leads only, once, on the later years: lift still above 1, and Benjamini-Hochberg again
  over the leads (false discoveries kept to 10%).
- Either way: a condition can come before more rises AND more falls (a big move coming, direction unknown, such as
  price above the upper Bollinger band). Each result also shows the opposite move's lift on the later years, and one
  where both are raised is called "a bigger move either way", not a direction.

The readings are the certified signal library's own, replayed at each close with nothing later visible
(set_history.context_at), so no reading can see the move it is said to precede.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd

import research_stats as rs

# ------------------------------------------------------------------------------------------------------ settings
UP_ATR = 2.0                 # a rise: +2 typical moves...
STOP_ATR = 1.0               # ...before -1
WINDOW = 6                   # within 6 daily candles
ATR_DAYS = 20
TREND_DAYS = 200
SEARCH_END = pd.Timestamp("2022-12-31")
CUT = pd.Timestamp("2024-10-29")         # the last saved day; the hold-out starts on 30 Oct 2024
MIN_DAYS = 150               # days a condition must hold (search period, all coins)
MIN_COINS = 8                # coins it must hold on
MIN_LIFT = 1.25              # search: at least 25% more moves than usual
FDR = 0.10                   # search: share of false discoveries allowed among the finds
PAIR_SCREEN_LIFT = 1.3       # pairs are tested only when their plain lift is at least this
MAX_THEMES = 40              # theme leads taken to the confirmation
RUNS_SEARCH = 1000           # resamples per test in the search (screening)
RUNS_CONFIRM = 10_000
KAPPA = 1.2                  # variance inflation, as the research tests use (not yet calibrated for lift)

# ------------------------------------------------------------------------------------------------------ readings
# What is read at each daily close: (signal id, field, how it is cut into conditions, plain name).
# Labels give one condition per label; numbers are cut at fixed points (never tuned to the data); recency means
# "in the last 3 candles"; yes/no gives the yes.
READINGS = [
    ("trend.direction", "", ("label",), "Trend"),
    ("momentum.direction", "", ("label",), "Momentum"),
    ("regime.state", "", ("label",), "Regime"),
    ("structure.swings", "structure", ("label",), "Market structure"),
    ("ma.pair", "order", ("label",), "EMA 20 vs 50"),
    ("ma.pair", "crossed", ("label",), "EMA 20/50 cross"),
    ("ma.line", "position", ("label",), "Price vs its average"),
    ("ma.line", "slope", ("label",), "Average's slope"),
    ("ichimoku.position", "cloud", ("label",), "Ichimoku cloud"),
    ("candle.shape", "colour", ("label",), "Candle"),
    ("osc.stoch_rsi", "pair", ("label",), "Stoch RSI"),
    ("osc.stoch_rsi", "cross_up_from_low_ago", ("recent", 3), "Stoch RSI crossed up from low"),
    ("osc.stoch_rsi", "cross_down_from_high_ago", ("recent", 3), "Stoch RSI crossed down from high"),
    ("osc.stoch_ohlc4", "zone", ("label",), "Stochastic (OHLC4)"),
    ("osc.wavetrend", "zone", ("label",), "WaveTrend"),
    ("osc.wavetrend", "direction", ("label",), "WaveTrend direction"),
    ("osc.wavetrend", "turned_up_from_oversold", ("yes",), "WaveTrend turned up from oversold"),
    ("osc.wavetrend", "turned_down_from_overbought", ("yes",), "WaveTrend turned down from overbought"),
    ("flow.money", "direction", ("label",), "Money flow"),
    ("sonar.markers", "big_green_dot_ago", ("recent", 3), "Sonar big green dot"),
    ("sonar.markers", "big_red_dot_ago", ("recent", 3), "Sonar big red dot"),
    ("sonar.markers", "long_cross_ago", ("recent", 3), "Sonar long cross"),
    ("sonar.markers", "short_cross_ago", ("recent", 3), "Sonar short cross"),
    ("sonar.markers", "band", ("label",), "Sonar band"),
    ("rsi.level", "rsi", ("cut", [30, 70]), "RSI (14)"),
    ("stochastic.level", "stoch_k", ("cut", [20, 80]), "Stochastic %K"),
    ("bollinger.position", "position", ("cut", [0.0, 0.2, 0.8, 1.0]), "Bollinger position"),
    ("volume.relative", "", ("cut", [0.7, 1.5, 2.5]), "Volume vs usual"),
    ("volume.cmf", "", ("cut", [-0.1, 0.1]), "Chaikin money flow"),
    ("move.seven_day", "move_in_expected_units", ("cut", [-1.0, 1.0]), "7-day move vs expected"),
    ("macd.level", "standard_score", ("cut", [-0.3, 0.3]), "MACD line"),
    ("macd.acceleration", "standard_score", ("cut", [-0.3, 0.3]), "MACD histogram"),
    ("obv.balance", "standard_score", ("cut", [-0.3, 0.3]), "On-balance volume"),
    ("volume.heavy_candle", "heaviness", ("cut", [0.5]), "Heavy candle"),
    ("levels.zones", "support.0.distance_atr", ("cut", [1.0]), "Distance to support"),
    ("levels.zones", "resistance.0.distance_atr", ("cut", [1.0]), "Distance to resistance"),
    ("regime.observation", "adx", ("cut", [20, 40]), "ADX"),
    ("regime.observation", "band_width_percentile", ("cut", [20, 80]), "Band width percentile"),
    ("volatility.atr_trend", "ratio", ("cut", [0.8, 1.2]), "ATR vs its average"),
    ("shape.classic", "golden_cross_ago", ("recent", 5), "Golden cross"),
    ("shape.classic", "death_cross_ago", ("recent", 5), "Death cross"),
    ("shape.classic", "double_bottom_stage", ("label",), "Double bottom"),
    ("shape.classic", "double_top_stage", ("label",), "Double top"),
    # 🌊 Tides (18 Nov 2026): market-wide, the same for every coin on a day (signals_tides.py)
    ("tides.tide", "tide", ("label",), "Tide"),
    ("tides.tide", "sea", ("label",), "Sea state"),
    ("tides.tide", "wind", ("label",), "Wind for crypto"),
    ("tides.storm", "warning", ("yes",), "Major release within 2 days"),
    ("tides.current:dollar", "direction", ("label",), "US dollar"),
    ("tides.current:long_rates", "direction", ("label",), "Long rates"),
    ("tides.current:credit", "direction", ("label",), "Credit"),
    ("tides.current:fear", "direction", ("label",), "Fear (VIX)"),
]
TIDES = [r for r in READINGS if r[0].startswith("tides.")]
TIDE_STATES = ("in", "slack", "out")


def column(sig: str, field: str) -> str:
    return f"{sig}|{field}"


def signal_refs(readings=None):
    """One reference per reading's signal; "tides.current:dollar" is tides.current with current=dollar."""
    import signal_library as sl

    refs = {}
    for sig in dict.fromkeys(r[0] for r in (readings or READINGS)):
        sid, _, choice = sig.partition(":")
        d = [x for x in sl.REGISTRY.latest() if x.id == sid][0]
        refs[sig] = sl.SignalRef.make(d, "1D", **({"current": choice} if choice else {}))
    return refs


def tides_columns(days, kind: str = "crypto") -> pd.DataFrame:
    """The Tides readings at each daily close (market-wide: worked out once per day, not per coin). Same context
    time as set_history.context_at (the day's close plus 10 minutes), reading the saved Tides history."""
    import signal_library as sl
    from signal_groups.rules import resolve

    refs = signal_refs(TIDES)
    rows, index = [], []
    for day in pd.DatetimeIndex(days).unique().sort_values():
        stamp = day.tz_localize("UTC") if day.tzinfo is None else day
        ctx = sl.DataContext(kind, "market", now=stamp + pd.Timedelta(days=1, minutes=10))
        results = sl.evaluate(list(refs.values()), ctx)
        row = {}
        for sig, field, _, _ in TIDES:
            res = results.get(refs[sig].instance_key)
            value = None
            if res is not None and res.status in ("ok", "stale"):
                found, x = resolve(res.value, field or None)
                value = x if found else None
            row[column(sig, field)] = value
        rows.append(row)
        index.append(day)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(index))


def with_tides(table: pd.DataFrame, kind: str = "crypto", cache: dict | None = None) -> pd.DataFrame:
    """A readings table with the Tides columns added where it lacks them (tables saved before 18 Nov 2026)."""
    need = [column(sig, field) for sig, field, _, _ in TIDES if column(sig, field) not in table]
    if not need:
        return table
    cache = {} if cache is None else cache
    missing = [d for d in table.index if d not in cache]
    if missing:
        got = tides_columns(missing, kind)
        for d, row in got.iterrows():
            cache[d] = row.to_dict()
    extra = pd.DataFrame([cache[d] for d in table.index], index=table.index)
    return pd.concat([table, extra[need]], axis=1)


def readings_table(frame: pd.DataFrame, kind: str, symbol: str, start=None, warmup: int = 220) -> pd.DataFrame:
    """Every reading in READINGS at every finished daily close (nothing later visible), one row per day.
    frame: daily candles with indicators (scoring.calculate_indicators), already cut before the hold-out."""
    import set_history as sh
    import signal_library as sl
    from signal_groups.rules import resolve

    refs = signal_refs()
    index = frame.index
    first = index[min(warmup, len(index) - 1)] if start is None else pd.Timestamp(start)
    rows, days = [], []
    for day in index[index >= first]:
        ctx, last = sh.context_at(frame, kind, day, symbol)
        if pd.Timestamp(last) != pd.Timestamp(day):
            continue
        results = sl.evaluate(list(refs.values()), ctx)
        row = {}
        for sig, field, _, _ in READINGS:
            res = results.get(refs[sig].instance_key)
            value = None
            if res is not None and res.status in ("ok", "stale"):
                found, x = resolve(res.value, field or None)
                value = x if found else None
            row[column(sig, field)] = value
        rows.append(row)
        days.append(pd.Timestamp(day))
    return pd.DataFrame(rows, index=pd.DatetimeIndex(days))


# ------------------------------------------------------------------------------------------------------ moves
def typical_move(frame: pd.DataFrame, days: int = ATR_DAYS) -> pd.Series:
    prev = frame["close"].shift(1)
    tr = pd.concat([frame["high"] - frame["low"], (frame["high"] - prev).abs(), (frame["low"] - prev).abs()],
                   axis=1).max(axis=1)
    return tr.rolling(days, min_periods=days).mean()


def moves(frame: pd.DataFrame, up: float = UP_ATR, stop: float = STOP_ATR, window: int = WINDOW,
          cut=CUT) -> pd.DataFrame:
    """For every close: rise (1/0), fall (1/0), NaN where the window isn't complete before the cut; plus the
    comparison keys year and above (close above its 200-day average)."""
    frame = frame.sort_index()
    idx = frame.index
    naive = idx.tz_localize(None) if idx.tz is not None else idx
    high, low = frame["high"].to_numpy(float), frame["low"].to_numpy(float)
    close = frame["close"].to_numpy(float)
    atr = typical_move(frame).to_numpy(float)
    sma = frame["close"].rolling(TREND_DAYS, min_periods=TREND_DAYS).mean().to_numpy(float)
    last_ok = np.searchsorted(naive.to_numpy(), np.datetime64(pd.Timestamp(cut)), side="right") - 1
    n = len(close)
    rise, fall = np.full(n, np.nan), np.full(n, np.nan)
    for i in range(n):
        if i + window > last_ok or not (atr[i] > 0):
            continue
        a, c = atr[i], close[i]
        r = f = 0.0
        up_hit = down_hit = False
        for j in range(i + 1, i + window + 1):
            hi_up, lo_stop = high[j] >= c + up * a, low[j] <= c - stop * a      # rise test
            lo_dn, hi_stop = low[j] <= c - up * a, high[j] >= c + stop * a      # fall test
            if not up_hit:
                if hi_up and not lo_stop:
                    r, up_hit = 1.0, True
                elif lo_stop:
                    up_hit = True                                              # stopped (or both): no rise
            if not down_hit:
                if lo_dn and not hi_stop:
                    f, down_hit = 1.0, True
                elif hi_stop:
                    down_hit = True
            if up_hit and down_hit:
                break
        rise[i], fall[i] = r, f
    out = pd.DataFrame({"rise": rise, "fall": fall}, index=idx)
    out["year"] = naive.year
    out["above"] = np.where(np.isnan(sma), np.nan, (close > sma).astype(float))
    return out


# ------------------------------------------------------------------------------------------------------ conditions
def conditions(table: pd.DataFrame) -> dict[str, pd.Series]:
    """name -> boolean Series (NaN where the reading is missing), from the readings table."""
    out = {}
    for sig, field, how, plain in READINGS:
        col = column(sig, field)
        if col not in table:
            continue
        s = table[col]
        known = s.notna()
        kind = how[0]
        if kind == "label":
            for label in sorted({str(v) for v in s.dropna().unique()}):
                if label in ("none", "None", ""):
                    continue
                out[f"{plain}: {label.replace('_', ' ')}"] = _bool(s.astype(str) == label, known)
        elif kind == "yes":
            out[plain] = _bool(s == True, known)  # noqa: E712
        elif kind == "recent":
            num = pd.to_numeric(s, errors="coerce")
            out[f"{plain} in the last {how[1]} candles"] = _bool(num <= how[1] - 1, known)
        elif kind == "cut":
            num = pd.to_numeric(s, errors="coerce")
            cuts = how[1]
            known = num.notna()
            out[f"{plain} under {_fmt(cuts[0])}"] = _bool(num < cuts[0], known)
            for a, b in zip(cuts, cuts[1:]):
                out[f"{plain} {_fmt(a)} to {_fmt(b)}"] = _bool((num >= a) & (num < b), known)
            out[f"{plain} {_fmt(cuts[-1])} or more"] = _bool(num >= cuts[-1], known)
    return out


def _fmt(x) -> str:
    return f"{x:g}"


def _bool(mask: pd.Series, known: pd.Series) -> pd.Series:
    return mask.astype(float).where(known)


def family(name: str) -> str:
    """The reading a condition comes from (pairs never join two conditions of the same reading)."""
    for _, _, how, plain in READINGS:
        if name == plain or name.startswith(plain + ":") or name.startswith(plain + " "):
            return plain
    return name


# ------------------------------------------------------------------------------------------------------ the test
def panel(per_coin: dict[str, tuple[pd.DataFrame, pd.DataFrame]], target: str, start=None, end=None):
    """Long table: one row per coin and day with the outcome, its comparable-day usual rate and every condition.
    per_coin: symbol -> (readings table, moves table)."""
    parts = []
    for sym, (table, mv) in per_coin.items():
        m = mv.reindex(table.index)
        conds = pd.DataFrame(conditions(table), index=table.index)
        base = m[[target, "year", "above"]].copy()
        days = base.index.tz_localize(None) if base.index.tz is not None else base.index
        keep = base[target].notna() & base["above"].notna()
        if start is not None:
            keep &= days >= pd.Timestamp(start)
        if end is not None:
            keep &= days <= pd.Timestamp(end)
        base, conds = base[keep], conds[keep]
        if base.empty:
            continue
        # the usual rate: the same coin, year and side of the 200-day average (over all its days)
        base["usual"] = base.groupby(["year", "above"])[target].transform("mean")
        frame = pd.concat([base, conds], axis=1)
        frame["coin"] = sym
        frame["date"] = (days[keep]).normalize()
        parts.append(frame.reset_index(drop=True))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def judge(p: pd.DataFrame, mask: np.ndarray, target: str, runs: int, seed: int = rs.SEED) -> dict:
    """Lift and its block-resampled test for the rows where mask is true."""
    rows = p.loc[mask, ["date", target, "usual", "coin"]]
    n = len(rows)
    if n == 0:
        return {"days": 0}
    hit, usual = rows[target].to_numpy(float), rows["usual"].to_numpy(float)
    lift = hit.mean() / usual.mean() if usual.mean() > 0 else None
    out = {"days": int(n), "coins": int(rows["coin"].nunique()), "rate": float(hit.mean()),
           "usual": float(usual.mean()), "lift": lift}
    days = pd.DatetimeIndex(rows["date"])
    cal = pd.date_range(days.min(), days.max(), freq="D")
    diff = pd.Series(hit - usual, index=days).groupby(level=0).sum().reindex(cal, fill_value=0).to_numpy()
    cnt = pd.Series(1.0, index=days).groupby(level=0).sum().reindex(cal, fill_value=0).to_numpy()
    test = rs.studentised_test(diff, cnt, WINDOW, KAPPA, direction=1, runs=runs, seed=seed)
    out["p"] = test.get("p_value")
    out["diff"] = test.get("estimate")
    out["ci95"] = test.get("ci95")
    # how many coins show more moves than usual on their own (from 10 days)
    by = rows.groupby("coin")
    per = by[target].mean() / by["usual"].mean().replace(0, np.nan)
    enough = by.size() >= 10
    out["coins_up"] = int((per[enough] > 1).sum())
    out["coins_read"] = int(enough.sum())
    return out


def bh(p_values: list[float | None], q: float = FDR) -> list[bool]:
    """Benjamini-Hochberg: which tests pass with the share of false discoveries kept to q."""
    ps = [(p if p is not None else 1.0) for p in p_values]
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    cutoff = -1
    for rank, i in enumerate(order, 1):
        if ps[i] <= q * rank / m:
            cutoff = rank
    passed = [False] * m
    for rank, i in enumerate(order, 1):
        passed[i] = rank <= cutoff
    return passed


def search(p: pd.DataFrame, target: str, runs: int = RUNS_SEARCH, pairs: bool = True, log=print) -> list[dict]:
    """Every single condition, then pairs of conditions from different readings, on the search panel."""
    names = [c for c in p.columns if c not in ("date", target, "usual", "coin", "year", "above", "rise", "fall")]
    found = []
    singles = {}
    for name in names:
        col = p[name].to_numpy(float)
        mask = col == 1.0
        if mask.sum() < MIN_DAYS:
            continue
        singles[name] = mask
        r = judge(p, mask, target, runs)
        r.update({"condition": [name], "kind": "single"})
        found.append(r)
    log(f"{target}: {len(found)} single conditions tested")
    if pairs:
        tried = 0
        hit = p[target].to_numpy(float)
        usual = p["usual"].to_numpy(float)
        for a, b in itertools.combinations(sorted(singles), 2):
            if family(a) == family(b):
                continue
            mask = singles[a] & singles[b]
            n = int(mask.sum())
            tried += 1
            if n < MIN_DAYS:
                continue
            u = usual[mask].mean()
            lift = hit[mask].mean() / u if u > 0 else 0
            if lift < PAIR_SCREEN_LIFT:
                r = {"days": n, "lift": lift, "p": None, "screened_out": True}
            else:
                r = judge(p, mask, target, runs)
            r.update({"condition": [a, b], "kind": "pair"})
            found.append(r)
        log(f"{target}: {tried} pairs looked at")
    passed = bh([r.get("p") if not r.get("screened_out") else 1.0 for r in found])
    for r, ok in zip(found, passed):
        r["fdr_pass"] = bool(ok)
        r["search_pass"] = bool(ok and (r.get("lift") or 0) >= MIN_LIFT and r.get("coins", 0) >= MIN_COINS
                                and r.get("days", 0) >= MIN_DAYS)
    return found


def themes(survivors: list[dict], limit: int = MAX_THEMES) -> list[dict]:
    """Theme leads from the search survivors (search data only): strongest first by search p, then lift; a survivor
    sharing any condition with a lead joins that lead's theme. Each lead carries its theme's other members."""
    order = sorted(survivors, key=lambda r: ((r.get("p") if r.get("p") is not None else 1), -(r.get("lift") or 0)))
    leads: list[dict] = []
    for r in order:
        home = next((l for l in leads if set(l["condition"]) & set(r["condition"])), None)
        if home is not None:
            home["theme"].append(" + ".join(r["condition"]))
        elif len(leads) < limit:
            leads.append({**r, "theme": []})
    return leads


def confirm(p: pd.DataFrame, candidates: list[dict], target: str, runs: int = RUNS_CONFIRM) -> list[dict]:
    """The search survivors on the later years, once: same direction, Holm over the survivors."""
    out = []
    for r in candidates:
        mask = np.ones(len(p), bool)
        for name in r["condition"]:
            mask &= (p[name].to_numpy(float) == 1.0) if name in p else np.zeros(len(p), bool)
        c = judge(p, mask, target, runs) if mask.sum() else {"days": 0}
        out.append({**r, "confirm": c})
    ps = [(o["confirm"].get("p") if o["confirm"].get("days", 0) >= 30 else None) for o in out]
    passed = bh(ps) if ps else []
    for o, ok in zip(out, passed):
        c = o["confirm"]
        o["confirmed"] = bool(ok and (c.get("lift") or 0) > 1.0)
    return out


def opposite(p_other: pd.DataFrame, results: list[dict], other: str, runs: int = 300) -> None:
    """The opposite move's lift on the later years for each result (a rise condition's falls, and the reverse)."""
    for o in results:
        mask = np.ones(len(p_other), bool)
        for name in o["condition"]:
            mask &= (p_other[name].to_numpy(float) == 1.0) if name in p_other else np.zeros(len(p_other), bool)
        r = judge(p_other, mask, other, runs) if mask.sum() else {"days": 0}
        o["opposite"] = {"lift": r.get("lift"), "days": r.get("days", 0)}
        o["verdict"] = verdict(o)


EITHER_WAY = 1.25              # the opposite move raised this much too: a bigger move either way


def tide_split(p: pd.DataFrame, results: list[dict], target: str) -> None:
    """How each result did when the Tide was coming in, slack or going out (plain rates, no test: few Tide spells,
    so this describes, it does not prove). p: the panel over every year to the cut."""
    hit, usual = p[target].to_numpy(float), p["usual"].to_numpy(float)
    for o in results:
        mask = np.ones(len(p), bool)
        for name in o["condition"]:
            mask &= (p[name].to_numpy(float) == 1.0) if name in p else np.zeros(len(p), bool)
        split = {}
        for state in TIDE_STATES:
            col = f"Tide: {state}"
            if col not in p:
                continue
            m = mask & (p[col].to_numpy(float) == 1.0)
            n = int(m.sum())
            u = usual[m].mean() if n else 0
            split[state] = {"days": n, "lift": float(hit[m].mean() / u) if n and u > 0 else None,
                            "rate": float(hit[m].mean()) if n else None,
                            "coins": int(p.loc[m, "coin"].nunique()) if n else 0,
                            "spells": int(pd.Series(p.loc[m, "date"]).drop_duplicates().sort_values().diff()
                                          .gt(pd.Timedelta(days=5)).sum() + 1) if n else 0}
        o["tide_split"] = split


def verdict(o: dict) -> str:
    c = o.get("confirm") or {}
    if o.get("confirmed") and ((o.get("opposite") or {}).get("lift") or 0) >= EITHER_WAY:
        return "either_way"
    if o.get("confirmed"):
        spread = (c.get("coins_up", 0) / c["coins_read"]) if c.get("coins_read") else 0
        return "survivor" if spread >= 0.6 else "fragile"
    if (c.get("lift") or 0) > 1.0:
        return "not_confirmed"          # pointed the right way, but not strongly enough on the later years
    return "faded"                      # the later years showed no more moves than usual
