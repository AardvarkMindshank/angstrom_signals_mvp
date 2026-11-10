"""
"What followed": what happened after a Set turned Yes, against comparable ordinary days (agreed plan, Stage B;
decisions after the 8 Nov review: docs/research/what_followed_brief_2026-11-08.md).

It describes the past. It is not a trade test and not a forecast.

- An episode starts on a fresh Yes: a Yes right after a No, with at least GAP No candles since the last Yes. Unknown
  candles do not count towards the gap.
- Each outcome is measured from the close of the candle after the Yes (LAG = 1, as the research code), over HORIZON
  completed candles, in the asset's typical move (20-candle average true range at the Yes close):
    gain first  rose one typical move before falling one (+1), the other way (-1), neither or both in one candle (0)
    move        where price ended, in typical moves
    higher      ended higher (1) or not (0)
    size        how far it ended either way (for Sets that do not point one way, such as Squeeze)
- Comparable days: the same asset's No days in the same year, on the same side of the 200-candle average.
  Each episode's outcome minus the average of its comparable days is its difference.
- Every outcome window ends before the protected hold-out (30 Oct 2024).
- Differences are pooled by calendar date and resampled in calendar blocks across all assets together
  (research_stats.studentised_test), corrected for the number of tests with Holm, then checked for consistency across
  three periods and between coins and shares.

Breakdowns (decided after the reviews of 10 Nov, docs/research/study_enhancements_brief_2026-11-10.md):
- Coins and equities: the same test on each part. Their tests join the pooled tests in one Holm family, and a part
  gets a verdict only once the test is shown to keep its false-positive rate on parts (SPLIT_VERDICTS, set after the
  calibration run in what_followed_calibrate.py). A direct comparison says whether the two parts differ.
- Periods: the three fixed periods side by side, as information.
- Asset by asset: numbers only (from MIN_ASSET episodes), no verdicts or marks, in name order. One luck line counts
  assets outside the range that random No days give them, against how many do so when every asset's episode dates
  are slid together by the same random offset (which keeps assets moving together and episodes bunching in time).
- Concentration: distinct days and weeks behind the episodes, and the largest asset's share.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

import research_stats as rs

METHOD = "what-followed-2"            # 2: coins/equities parts, periods, assets, luck line
HORIZON = 10
GAP = 5
ATR_DAYS = 20
TREND_DAYS = 200
LAG = rs.LAG
MIN_WEEKS = 40               # episodes in at least this many different weeks, else "Too few to judge"
MIN_COMPARABLE = 20          # comparable days needed in an episode's year and trend side
MIN_PART = 10                # episodes needed for a period, or for coins or shares, to count in the consistency check
KAPPA = 1.2
MIN_ASSET = 15               # episodes an asset needs before its numbers are shown
SHIFTS = 200                 # random offsets for the luck line
PART_KINDS = (("coins", "crypto"), ("equities", "equity"))
SPLIT_VERDICTS = True        # coins / equities verdicts: on since the calibration run of 10 Nov passed (docs/research/study_calibration_2026-11-10.md)
HOLDOUT = pd.Timestamp("2024-10-30")
PERIODS = (("before 2019", None, "2018-12-31"), ("2019 to 2021", "2019-01-01", "2021-12-31"),
           ("2022 to Oct 2024", "2022-01-01", None))
VERDICTS = ("Too few to judge", "No clear difference", "Some difference, not established", "Consistent difference")
FILTER_NOTE = "A filter for other Sets: it is not studied on its own."

# What each provided Set is asked: one direction ("directional"), the size of the move ("neutral"), or nothing on its
# own ("filter"). Anyone's own Sets are directional.
SET_TYPE = {"demo:squeeze": "neutral", "demo:btc_filter": "filter"}
MEASURES = {"directional": ("first", "move"), "neutral": ("size",)}
WORDS = {"first": "Gain first", "move": "Move after 10 candles", "higher": "Finished higher",
         "size": "Size of the move"}


def logic_hash(doc: dict) -> str:
    """Fingerprint of what a Set checks, ignoring its name and description: a renamed copy keeps its study, any
    change to its logic does not."""
    from column_answers import def_hash

    return def_hash({k: v for k, v in (doc or {}).items() if k not in ("name", "purpose", "description", "notes")})


from study_history import SAVED_SINCE  # noqa: E402

NO_HISTORY = {"sentiment": "news sentiment", "positioning": "hourly positioning", "flows": "fund flows"}


def studyable(doc: dict | None) -> tuple[bool, str]:
    """(can it be studied, why not). Studies use saved daily prices only: every part that decides the answer must
    read daily or weekly candles of a coin or share, not news sentiment or positioning, which have no saved history
    yet. Market-wide readings (fund flows, market sentiment) can only sit in a Set's market context, which never
    changes its Yes or No, so they do not stop a study."""
    import perspectives
    import signal_library as sl

    if not doc:
        return False, "There is no saved Set to study."
    if not (doc.get("groups") or doc.get("standalone") or doc.get("members")):
        return False, "This Set has no parts yet."
    for ref, _ in perspectives._refs(doc):
        tf = (ref or {}).get("timeframe", "1D")
        if tf not in ("1D", "1W"):
            return False, (f"It reads {tf} candles; studies use saved daily prices, so only Sets that read daily or "
                           "weekly candles can be studied.")
        try:
            definition = sl.REGISTRY.get(ref["id"], ref.get("version", 1))
        except Exception:
            return False, f"One of its parts ({(ref or {}).get('id', '?')}) is not in the signal library."
        if ref["id"] in SAVED_SINCE:              # daily positioning: filled in from Coinalyze (study_history.py)
            continue
        if definition.category in NO_HISTORY:
            return False, f"It uses {NO_HISTORY[definition.category]}, which has no saved history to study yet."
        if str(getattr(definition, "scope", "") or "").startswith("market:"):
            return False, "It uses a market-wide reading, which has no saved history to study."
    return True, ""


def set_type(key: str) -> str:
    return SET_TYPE.get(key, "directional")


# ----------------------------------------------------------------------------------------------- episodes

def episodes(answers: pd.Series, gap: int = GAP) -> pd.DatetimeIndex:
    """Fresh Yes dates. answers: "yes" / "no" / "unknown" by date, in order."""
    out, quiet, previous = [], gap, None
    for day, answer in answers.items():
        if answer == "yes":
            if previous == "no" and quiet >= gap:
                out.append(day)
            quiet = 0
        elif answer == "no":
            quiet += 1
        previous = answer
    return pd.DatetimeIndex(out)


# ----------------------------------------------------------------------------------------------- outcomes

def typical_move(frame: pd.DataFrame, days: int = ATR_DAYS) -> pd.Series:
    """Average true range over the last `days` candles, known at each close."""
    prev = frame["close"].shift(1)
    tr = pd.concat([frame["high"] - frame["low"], (frame["high"] - prev).abs(), (frame["low"] - prev).abs()],
                   axis=1).max(axis=1)
    return tr.rolling(days, min_periods=days).mean()


def outcomes(frame: pd.DataFrame, horizon: int = HORIZON, lag: int = LAG, holdout=HOLDOUT) -> pd.DataFrame:
    """For every candle: first, move, higher, size (NaN where the window is not complete before the hold-out), and
    the comparison keys year and above (close above its 200-candle average)."""
    frame = frame.sort_index()
    idx = frame.index
    naive = idx.tz_localize(None) if idx.tz is not None else idx
    keep = naive < pd.Timestamp(holdout)
    high = frame["high"].to_numpy(float)[keep]
    low = frame["low"].to_numpy(float)[keep]
    close = frame["close"].to_numpy(float)[keep]
    atr = typical_move(frame).to_numpy(float)[keep]
    sma = frame["close"].rolling(TREND_DAYS, min_periods=TREND_DAYS).mean().to_numpy(float)[keep]
    n = len(close)
    first = np.full(n, np.nan)
    move = np.full(n, np.nan)
    for i in range(n):
        e, end = i + lag, i + lag + horizon
        if end >= n or not (atr[i] > 0):
            continue
        entry, a = close[e], atr[i]
        move[i] = (close[end] - entry) / a
        hit = 0.0
        for j in range(e + 1, end + 1):
            up, down = high[j] >= entry + a, low[j] <= entry - a
            if up or down:
                hit = 0.0 if (up and down) else (1.0 if up else -1.0)
                break
        first[i] = hit
    out = pd.DataFrame({"first": first, "move": move}, index=idx[keep])
    out["up_first"] = np.where(np.isnan(first), np.nan, (first > 0).astype(float))
    out["down_first"] = np.where(np.isnan(first), np.nan, (first < 0).astype(float))
    out["higher"] = np.where(np.isnan(move), np.nan, (move > 0).astype(float))
    out["size"] = np.abs(move)
    out["year"] = naive[keep].year
    out["above"] = np.where(np.isnan(sma), np.nan, (close > sma).astype(float))
    return out


ALL_MEASURES = ("first", "up_first", "down_first", "move", "higher", "size")


def differences(answers: pd.Series, table: pd.DataFrame, measures=ALL_MEASURES) -> pd.DataFrame:
    """One row per episode with its outcomes, the comparable-day averages and the differences."""
    answers = answers.reindex(table.index)
    starts = episodes(answers.dropna())
    ordinary = table[(answers == "no") & table["move"].notna() & table["above"].notna()]
    groups = ordinary.groupby(["year", "above"])
    means = groups[list(measures)].mean()
    counts = groups.size()
    rows = []
    for day in starts:
        row = table.loc[day]
        if np.isnan(row["move"]) or np.isnan(row["above"]):
            continue
        key = (row["year"], row["above"])
        if counts.get(key, 0) < MIN_COMPARABLE:
            continue
        rec = {"date": day}
        for m in measures:
            rec[m] = row[m]
            rec[f"{m}_usual"] = means.loc[key, m]
            rec[f"{m}_diff"] = row[m] - means.loc[key, m]
        rows.append(rec)
    return pd.DataFrame(rows)


def daily_differences(answers: pd.Series, table: pd.DataFrame, measure: str) -> pd.Series:
    """The difference from comparable days on every No day that has them: what a random No day would show. Used by
    the luck line."""
    answers = answers.reindex(table.index)
    ordinary = table[(answers == "no") & table["move"].notna() & table["above"].notna()]
    if ordinary.empty:
        return pd.Series(dtype=float)
    groups = ordinary.groupby(["year", "above"])
    means, counts = groups[measure].mean(), groups.size()
    keys = pd.MultiIndex.from_arrays([ordinary["year"], ordinary["above"]])
    usual = means.reindex(keys).to_numpy(float)
    enough = counts.reindex(keys).fillna(0).to_numpy() >= MIN_COMPARABLE
    out = pd.Series(ordinary[measure].to_numpy(float) - usual, index=ordinary.index)
    return out[enough & ~np.isnan(out.to_numpy())]


# ----------------------------------------------------------------------------------------------- pooling and tests

def _naive(days) -> pd.DatetimeIndex:
    days = pd.DatetimeIndex(days)
    return days.tz_localize(None) if days.tz is not None else days


def by_date(rows: pd.DataFrame, column: str) -> tuple[np.ndarray, np.ndarray]:
    """Sum of differences and count of episodes for every calendar date from the first episode to the last (zeros
    where none), so whole calendar stretches are resampled across all assets together."""
    days = _naive(rows["date"]).normalize()
    calendar = pd.date_range(days.min(), days.max(), freq="D")
    sums = pd.Series(rows[column].to_numpy(float), index=days).groupby(level=0).sum()
    counts = pd.Series(1.0, index=days).groupby(level=0).sum()
    return sums.reindex(calendar, fill_value=0).to_numpy(), counts.reindex(calendar, fill_value=0).to_numpy()


def test(rows: pd.DataFrame, measure: str, runs: int = rs.RUNS, seed: int = rs.SEED) -> dict:
    """Average difference with its 95% interval and a two-sided p-value."""
    num, den = by_date(rows, f"{measure}_diff")
    # A block of calendar days is 2 x the horizon in candles, and shares trade about 5 days in 7.
    horizon = math.ceil(HORIZON * 7 / 5)
    if len(num) < 40 or den.sum() <= 0:
        return {"estimate": None}
    est = float(num.sum() / den.sum())
    out = rs.studentised_test(num, den, horizon, KAPPA, direction=1 if est >= 0 else -1, runs=runs, seed=seed)
    if out.get("p_value") is not None:
        out["p_two_sided"] = min(1.0, 2 * out["p_value"])
    return out


def weeks(rows: pd.DataFrame) -> int:
    """Different calendar weeks with at least one episode: episodes in the same week count once here."""
    if rows.empty:
        return 0
    days = _naive(rows["date"])
    return int(pd.Series(days.to_period("W")).nunique())


def consistency(rows: pd.DataFrame, measure: str, sign: float) -> dict:
    """Does the difference point the same way in each period, and in coins and shares?"""
    days = _naive(rows["date"])
    parts = []
    for name, start, end in PERIODS:
        mask = np.ones(len(rows), bool)
        if start:
            mask &= days >= pd.Timestamp(start)
        if end:
            mask &= days <= pd.Timestamp(end)
        parts.append((name, rows.loc[mask, f"{measure}_diff"]))
    for name, kind in (("coins", "crypto"), ("shares", "equity")):
        parts.append((name, rows.loc[rows["kind"] == kind, f"{measure}_diff"]))
    checked = [(n, float(v.mean())) for n, v in parts if len(v) >= MIN_PART]
    same = [n for n, v in checked if np.sign(v) == np.sign(sign) and v != 0]
    periods_checked = [n for n, _ in checked if n not in ("coins", "shares")]
    return {"checked": [n for n, _ in checked], "same_way": same,
            "all_same": len(periods_checked) >= 2 and len(same) == len(checked)}


def verdict(n_weeks: int, tests: dict, passed: dict, consistent: dict) -> tuple[str, str | None]:
    """(verdict, the measure it rests on). tests/passed/consistent: measure -> result."""
    if n_weeks < MIN_WEEKS or not tests or all(t.get("estimate") is None for t in tests.values()):
        return VERDICTS[0], None
    for m in tests:
        if passed.get(m) and consistent.get(m, {}).get("all_same"):
            return VERDICTS[3], m
    for m in tests:
        p = tests[m].get("p_two_sided")
        if passed.get(m) or (p is not None and p <= 0.05):
            return VERDICTS[2], m
    return VERDICTS[1], None


def concentration(rows: pd.DataFrame, top: int = 3) -> list[tuple[str, float]]:
    shares = rows["asset"].value_counts(normalize=True)
    return [(a, round(float(s), 3)) for a, s in shares.head(top).items()]


def core(kind: str) -> str:
    """The measure a breakdown is read on: gain first, or size for Sets that do not point one way."""
    return "size" if kind == "neutral" else "first"


def _calendar_sums(rows: pd.DataFrame, column: str, calendar: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    days = _naive(rows["date"]).normalize()
    sums = pd.Series(rows[column].to_numpy(float), index=days).groupby(level=0).sum()
    counts = pd.Series(1.0, index=days).groupby(level=0).sum()
    return sums.reindex(calendar, fill_value=0).to_numpy(), counts.reindex(calendar, fill_value=0).to_numpy()


def compare(rows: pd.DataFrame, measure: str, runs: int = rs.RUNS, seed: int = rs.SEED) -> dict | None:
    """Coins minus equities, resampled in the same calendar blocks for both (so days that move both markets stay
    together). {estimate, ci95, p_two_sided, differ}; None when either part has too few weeks."""
    from scipy.stats import t as t_dist

    coins, shares = rows[rows["kind"] == "crypto"], rows[rows["kind"] == "equity"]
    if weeks(coins) < MIN_WEEKS or weeks(shares) < MIN_WEEKS:
        return None
    days = _naive(rows["date"]).normalize()
    calendar = pd.date_range(days.min(), days.max(), freq="D")
    nc, dc = _calendar_sums(coins, f"{measure}_diff", calendar)
    ne, de = _calendar_sums(shares, f"{measure}_diff", calendar)
    n = len(calendar)
    block = min(rs.block_for(math.ceil(HORIZON * 7 / 5)), n)
    nb = math.ceil(n / block)
    rng = np.random.default_rng(seed)
    draws = []
    for start in range(0, runs, 500):
        m = min(500, runs - start)
        idx = ((rng.integers(0, n, size=(m, nb))[:, :, None] + np.arange(block)) % n).reshape(m, -1)[:, :n]
        a, b = dc[idx].sum(1), de[idx].sum(1)
        ok = (a > 0) & (b > 0)
        draws.append(nc[idx].sum(1)[ok] / a[ok] - ne[idx].sum(1)[ok] / b[ok])
    draws = np.concatenate(draws)
    est = float(nc.sum() / dc.sum() - ne.sum() / de.sum())
    se = float(draws.std(ddof=1)) * KAPPA if len(draws) > 1 else 0.0
    df = max(1, nb - 1)
    if se <= 0:
        return {"estimate": est, "ci95": None, "p_two_sided": None, "differ": False}
    p = float(min(1.0, 2 * t_dist.sf(abs(est) / se, df)))
    q = float(t_dist.ppf(0.975, df))
    return {"estimate": est, "ci95": [est - q * se, est + q * se], "p_two_sided": p, "differ": p <= 0.05}


def periods(rows: pd.DataFrame, kind: str) -> list[dict]:
    """The three fixed periods side by side, as information (no verdicts)."""
    days = _naive(rows["date"])
    out = []
    for name, start, end in PERIODS:
        mask = np.ones(len(rows), bool)
        if start:
            mask &= days >= pd.Timestamp(start)
        if end:
            mask &= days <= pd.Timestamp(end)
        part = rows.loc[mask]
        rec = {"name": name, "episodes": int(len(part)), "weeks": weeks(part)}
        if len(part) >= MIN_PART:
            rec["plain"] = plain_numbers(part, kind)
            rec["difference"] = float(part[f"{core(kind)}_diff"].mean())
        out.append(rec)
    return out


def per_asset(rows: pd.DataFrame, kind: str) -> list[dict]:
    """One row per asset in name order: its episodes, and its numbers beside its own comparable days from MIN_ASSET
    episodes. No verdicts, marks or ranks."""
    out = []
    for asset, part in sorted(rows.groupby("asset"), key=lambda kv: kv[0]):
        rec = {"asset": asset, "kind": str(part["kind"].iloc[0]), "episodes": int(len(part))}
        if len(part) >= MIN_ASSET:
            rec["plain"] = plain_numbers(part, kind)
        out.append(rec)
    return out


def luck(rows: pd.DataFrame, backdrop: dict, measure: str, shifts: int = SHIFTS, seed: int = rs.SEED) -> dict | None:
    """How many assets sit outside the range random No days give them, and how many typically do by chance.

    backdrop: asset -> daily differences on its No days (daily_differences). Every asset's episode dates are slid by
    the same random number of days (wrapping round the studied span), so assets that move together and episodes that
    bunch in time stay that way. An asset's range is the middle 95% of its slid averages; the chance count is how many
    assets fall outside their range on a typical slide."""
    counts = rows["asset"].value_counts()
    assets = sorted(a for a, n in counts.items() if n >= MIN_ASSET and a in backdrop and len(backdrop[a]))
    if len(assets) < 5:
        return None
    starts = [_naive(backdrop[a].index).min() for a in assets]
    ends = [_naive(backdrop[a].index).max() for a in assets]
    origin, span = min(starts), (max(ends) - min(starts)).days + 1
    margin = 3 * HORIZON
    if span <= 4 * margin:
        return None
    rng = np.random.default_rng(seed)
    offsets = rng.integers(margin, span - margin, size=shifts)
    observed = np.empty(len(assets))
    slid = np.full((shifts, len(assets)), np.nan)
    for j, a in enumerate(assets):
        mine = rows[rows["asset"] == a]
        observed[j] = float(mine[f"{measure}_diff"].mean())
        series = backdrop[a]
        days = np.asarray((_naive(series.index).normalize() - origin).days)
        values = series.to_numpy(float)
        eps = np.asarray((_naive(mine["date"]).normalize() - origin).days)
        for i, k in enumerate(offsets):
            target = np.sort((eps + k) % span)
            pos = np.searchsorted(days, target)
            ok = pos < len(days)
            pos, target = pos[ok], target[ok]
            near = (days[pos] - target) <= 4             # the next No day within a few days (weekends, Yes runs)
            if near.sum() >= MIN_ASSET // 2:
                slid[i, j] = values[pos[near]].mean()
    lo, hi = np.nanpercentile(slid, 2.5, axis=0), np.nanpercentile(slid, 97.5, axis=0)
    outside = (observed < lo) | (observed > hi)
    by_chance = ((slid < lo) | (slid > hi)).sum(axis=1)
    return {"checked": len(assets), "unusual": int(outside.sum()), "chance": int(round(float(np.mean(by_chance)))),
            "chance_exact": float(np.mean(by_chance)),
            "chance_high": int(round(float(np.percentile(by_chance, 90)))), "measure": measure}


def spread(rows: pd.DataFrame) -> dict:
    """How concentrated the episodes are: distinct days and weeks, and the busiest week's share."""
    days = _naive(rows["date"]).normalize()
    by_week = pd.Series(days.to_period("W")).value_counts(normalize=True)
    return {"days": int(days.nunique()), "weeks": weeks(rows),
            "top_week_share": round(float(by_week.iloc[0]), 3) if len(by_week) else 0.0}


def _part_summary(rows: pd.DataFrame, kind: str, tests: dict, passed: dict, cons: dict) -> dict:
    n_weeks = weeks(rows)
    out = {"episodes": int(len(rows)), "weeks": n_weeks,
           "assets": int(rows["asset"].nunique()) if len(rows) else 0}
    if SPLIT_VERDICTS:
        out["verdict"], out["rests_on"] = verdict(n_weeks, tests, passed, cons)
    else:
        out["verdict"] = VERDICTS[0] if n_weeks < MIN_WEEKS else None
    if len(rows) >= MIN_PART:
        out["plain"] = plain_numbers(rows, kind)
    out["tests"] = {m: _slim(t, passed.get(m), cons.get(m)) for m, t in tests.items()}
    return out


def study(per_set: dict, types: dict, runs: int = rs.RUNS, seed: int = rs.SEED,
          backdrops: dict | None = None) -> dict:
    """per_set: set key -> DataFrame of episodes (differences() rows plus "asset" and "kind" columns).
    types: set key -> directional / neutral / filter. Holm covers every test of every studied Set together."""
    tests, p_values = {}, {}
    for key, rows in per_set.items():
        kind = types.get(key, "directional")
        if kind == "filter" or rows is None or rows.empty:
            continue
        for m in MEASURES[kind]:
            tests[(key, m)] = test(rows, m, runs, seed)
            p_values[(key, m)] = tests[(key, m)].get("p_two_sided")
            for part, asset_kind in PART_KINDS:
                sub = rows[rows["kind"] == asset_kind]
                if weeks(sub) < MIN_WEEKS:
                    continue
                tests[(key, m, part)] = test(sub, m, runs, seed)
                if SPLIT_VERDICTS:                   # one family with the pooled tests, once calibrated
                    p_values[(key, m, part)] = tests[(key, m, part)].get("p_two_sided")
    passed = rs.holm(p_values) if p_values else {}
    out = {}
    for key, rows in per_set.items():
        kind = types.get(key, "directional")
        if kind == "filter":
            out[key] = {"type": kind, "verdict": None, "note": FILTER_NOTE}
            continue
        rows = rows if rows is not None else pd.DataFrame()
        n_weeks = weeks(rows)
        mine = {m: tests[(key, m)] for m in MEASURES[kind] if (key, m) in tests}
        cons = {m: consistency(rows, m, t["estimate"]) for m, t in mine.items() if t.get("estimate") is not None}
        word, rests_on = verdict(n_weeks, mine, {m: passed.get((key, m)) for m in mine}, cons)
        summary = {"type": kind, "verdict": word, "rests_on": rests_on, "episodes": int(len(rows)),
                   "weeks": n_weeks}
        if not rows.empty:
            summary.update({
                "assets": int(rows["asset"].nunique()),
                "coins": int((rows["kind"] == "crypto").sum()), "shares": int((rows["kind"] == "equity").sum()),
                "coin_assets": int(rows.loc[rows["kind"] == "crypto", "asset"].nunique()),
                "share_assets": int(rows.loc[rows["kind"] == "equity", "asset"].nunique()),
                "top_assets": concentration(rows),
                "first": _naive(rows["date"]).min().strftime("%Y-%m-%d"),
                "last": _naive(rows["date"]).max().strftime("%Y-%m-%d"),
                "plain": plain_numbers(rows, kind),
            })
        summary["tests"] = {m: _slim(t, passed.get((key, m)), cons.get(m)) for m, t in mine.items()}
        if not rows.empty:
            parts = {}
            for part, asset_kind in PART_KINDS:
                sub = rows[rows["kind"] == asset_kind]
                if sub.empty:
                    continue
                its = {m: tests[(key, m, part)] for m in MEASURES[kind] if (key, m, part) in tests}
                its_cons = {m: consistency(sub, m, t["estimate"]) for m, t in its.items()
                            if t.get("estimate") is not None}
                parts[part] = _part_summary(sub, kind, its, {m: passed.get((key, m, part)) for m in its}, its_cons)
            summary["parts"] = parts
            summary["compare"] = compare(rows, core(kind), runs, seed)
            summary["periods"] = periods(rows, kind)
            summary["per_asset"] = per_asset(rows, kind)
            summary["spread"] = spread(rows)
            back = (backdrops or {}).get(key)
            summary["luck"] = luck(rows, back, core(kind), seed=seed) if back else None
        out[key] = summary
    return {"method": METHOD, "horizon": HORIZON, "gap": GAP, "family": len(p_values),
            "split_verdicts": SPLIT_VERDICTS, "sets": out}


def plain_numbers(rows: pd.DataFrame, kind: str) -> dict:
    """The numbers the card shows, beside the same numbers for comparable days. Averages, so they always agree
    with the tests (which compare averages)."""
    if kind == "neutral":
        return {"size": float(rows["size"].mean()), "size_usual": float(rows["size_usual"].mean())}
    return {"gain_first": float(rows["up_first"].mean()), "gain_first_usual": float(rows["up_first_usual"].mean()),
            "loss_first": float(rows["down_first"].mean()), "loss_first_usual": float(rows["down_first_usual"].mean()),
            "move": float(rows["move"].mean()), "move_usual": float(rows["move_usual"].mean()),
            "higher": float(rows["higher"].mean()), "higher_usual": float(rows["higher_usual"].mean())}


def _slim(t: dict, passed, cons) -> dict:
    keep = {k: t.get(k) for k in ("estimate", "ci95", "p_two_sided", "df", "block")}
    if keep.get("ci95") is not None:
        keep["ci95"] = [float(x) for x in keep["ci95"]]
    keep["holm_passed"] = bool(passed)
    keep["consistency"] = cons
    return keep
