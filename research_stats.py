"""Statistics for the hold-out validation (Sprint 1, Task 1). Pure numpy/pandas, no scoring code.

Why this module exists
- The first research run measured each stock against its own history with ranks taken over the
  whole sample. A calibration study on synthetic markets (no real effect at all) showed that this
  statistic leans in exactly the directions claimed: about +0.04 for Stretch and -0.05 for Trend at
  hold-out length, because a persistent signal and future returns share the sample's own average.
  Tests built on it gave false alarms 35-44% of the time instead of 5%.
- The replacements here use only information known at the time for the signal (a real-time
  percentile of the asset's own past values) and remove the market by ranking the forward returns
  across assets on the same date. Neither uses the sample's own averages, so the null is centred on
  zero by construction.
- p-values come from a studentised joint-date block bootstrap with a t reference (degrees of
  freedom = blocks - 1) and an inflation factor KAPPA chosen on synthetic markets so that the
  false-alarm rate does not exceed the nominal level. Confidence intervals and p-values are reported
  separately.

Nothing here reads prices or the hold-out by itself; callers pass in tables.
"""

from __future__ import annotations

import bisect
import math

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

LAG = 1                       # entry at the close after the signal (as backtest.py)
SEED = 20261031
RUNS = 10_000
ECDF_MIN_HISTORY = 250        # bars of the asset's own past before its percentile is trusted

# Variance inflation per statistic, from the calibration study (spec section 1.3). With these,
# synthetic null false-alarm rates were at or below nominal at 5%, 2.5% and 1%.
KAPPA = {"relative_timing": 1.2, "spread": 1.0, "forecast_gain": 1.2}


# ----------------------------------------------------------------------------- dates and leakage

def first_eligible_signal(index: pd.DatetimeIndex, start: pd.Timestamp, label_bars: int) -> pd.Timestamp:
    """First hold-out signal date whose trade uses no price a development label used.

    Development labels ran from the last development signal (bar p-1) to its exit at bar p-1+label_bars,
    where p is the first hold-out bar and label_bars = longest horizon + LAG. A hold-out signal at bar q
    enters at q+LAG, so it is clean when q+LAG > p-1+label_bars, i.e. q >= p + label_bars - LAG.
    """
    index = pd.DatetimeIndex(index).sort_values()
    p = int(index.searchsorted(pd.Timestamp(start)))
    q = p + label_bars - LAG
    if q >= len(index):
        raise ValueError("Not enough bars after the hold-out start for the embargo.")
    return index[q]


def forward_returns(closes: pd.Series, horizon: int, lag: int = LAG) -> pd.Series:
    """% change from the close at t+lag to the close at t+lag+horizon. NaN where those bars do not exist,
    so a series cut at a boundary never produces a label that reaches past it."""
    entry = closes.shift(-lag)
    exit_ = closes.shift(-(lag + horizon))
    return (exit_ / entry - 1.0) * 100.0


def move_size(closes: pd.Series, horizon: int, lag: int = LAG) -> pd.Series:
    """Average absolute daily % move over the same window forward_returns covers (t+lag+1 .. t+lag+h)."""
    moves = closes.pct_change().abs() * 100.0
    return moves.rolling(int(horizon)).mean().shift(-(lag + int(horizon)))


def trailing_move_size(closes: pd.Series, days: int = 14) -> pd.Series:
    """Average absolute daily % move over the last `days` days, known at the close."""
    return (closes.pct_change().abs() * 100.0).rolling(days).mean()


# ----------------------------------------------------------------------------- signal transforms

def expanding_percentile(values: pd.Series, min_history: int = ECDF_MIN_HISTORY) -> pd.Series:
    """Where today's value sits among the asset's OWN EARLIER values, minus 0.5 (range -0.5..0.5).

    Ties count half. Only bars before t are used, so it can be computed in real time and never looks
    at the future. NaN until min_history earlier values exist.
    """
    out = np.full(len(values), np.nan)
    seen: list[float] = []
    for i, v in enumerate(values.to_numpy(dtype=float)):
        if np.isnan(v):
            continue
        if len(seen) >= min_history:
            lo, hi = bisect.bisect_left(seen, v), bisect.bisect_right(seen, v)
            out[i] = (lo + 0.5 * (hi - lo)) / len(seen) - 0.5
        bisect.insort(seen, v)
    return pd.Series(out, index=values.index)


def cross_section_ranks(table: pd.DataFrame) -> pd.DataFrame:
    """Each date's values ranked across assets, centred and scaled to spread 1 (NaN where missing)."""
    ranks = table.rank(axis=1)
    centred = ranks.sub(ranks.mean(axis=1), axis=0)
    return centred.div(centred.std(axis=1, ddof=0).replace(0, np.nan), axis=0)


def time_ranks(table: pd.DataFrame) -> pd.DataFrame:
    """Each asset's values ranked over its own dates, centred and scaled to spread 1."""
    ranks = table.rank()
    centred = ranks - ranks.mean()
    return centred / centred.std(ddof=0).replace(0, np.nan)


# ----------------------------------------------------------------------------- statistics as row sums
# Every statistic is written as sum(numerator rows) / sum(denominator rows) over dates, so the bootstrap
# can resample dates jointly for all assets.

def relative_timing_rows(signal: pd.DataFrame, forward: pd.DataFrame, min_history: int = ECDF_MIN_HISTORY,
                         percentiles: pd.DataFrame | None = None) -> tuple[np.ndarray, np.ndarray, pd.Index]:
    """Primary statistic for Claim A.

    u = the signal's real-time percentile within the asset's own past (computed on the FULL signal
        history passed in, then restricted to dates where forward exists);
    v = the forward return's rank among all assets that date (removes the market's move).
    Statistic = mean of u*v*sqrt(12), about a rank correlation. Zero in expectation when no asset's
    signal says anything about how it will do against the others.
    """
    if percentiles is None:
        percentiles = pd.DataFrame({c: expanding_percentile(signal[c], min_history) for c in signal.columns})
    u = percentiles.reindex(forward.index)
    v = cross_section_ranks(forward.where(u.notna()))
    prod = (u * v) * math.sqrt(12.0)
    ok = prod.notna()
    num = prod.where(ok, 0.0).sum(axis=1).to_numpy()
    den = ok.sum(axis=1).to_numpy(dtype=float)
    keep = den > 0
    return num[keep], den[keep], forward.index[keep]


def pooled_time_series_rows(signal: pd.DataFrame, forward: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """The FIRST run's statistic (each asset ranked over the whole sample). Kept for comparison only:
    it is biased in small samples (see module docstring)."""
    keep = signal.notna() & forward.notna()
    a, b = time_ranks(signal.where(keep)), time_ranks(forward.where(keep))
    prod = (a * b).where(keep)
    return prod.fillna(0.0).sum(axis=1).to_numpy(), keep.sum(axis=1).to_numpy(dtype=float)


def spread_weights(signal: pd.DataFrame, min_assets: int = 8) -> pd.DataFrame:
    """+1/n on the top third and -1/n on the bottom third of each date (n = assets // 3).
    Ties are broken by column order, so the result never depends on chance."""
    w = np.zeros(signal.shape)
    vals = signal.to_numpy(dtype=float)
    for i in range(vals.shape[0]):
        row = vals[i]
        ok = np.where(~np.isnan(row))[0]
        if len(ok) < min_assets:
            continue
        third = len(ok) // 3
        order = ok[np.argsort(row[ok], kind="mergesort")]
        w[i, order[-third:]] = 1.0 / third
        w[i, order[:third]] = -1.0 / third
    return pd.DataFrame(w, index=signal.index, columns=signal.columns)


def spread_rows(signal: pd.DataFrame, forward: pd.DataFrame, min_assets: int = 8):
    """Primary statistic for Claim B: mean daily top-third minus bottom-third forward return (%)."""
    sig = signal.where(forward.notna())
    w = spread_weights(sig, min_assets)
    num = (w * forward.fillna(0.0)).sum(axis=1).to_numpy()
    den = (w.abs().sum(axis=1) > 0).to_numpy(dtype=float)
    keep = den > 0
    return num[keep], den[keep], signal.index[keep]


def forecast_gain_rows(candidate: pd.DataFrame, benchmark: pd.DataFrame, target: pd.DataFrame):
    """Primary statistic for Claim C: mean over assets of [rank corr(candidate, target) - rank corr(benchmark,
    target)], each asset over its own dates. Positive = the candidate ranks later move sizes better."""
    keep = candidate.notna() & benchmark.notna() & target.notna()
    c, b, y = (time_ranks(x.where(keep)) for x in (candidate, benchmark, target))
    d = ((c - b) * y).where(keep)
    counts = keep.sum()
    assets = counts[counts > 30].index
    per_asset = d[assets].div(counts[assets], axis=1)        # each asset's column sums to its own correlation
    num = per_asset.fillna(0.0).sum(axis=1).to_numpy()
    # sum(num) = sum of the assets' correlations; den spreads the asset count evenly over dates so that
    # sum(num) / sum(den) is their average, and a bootstrap resample of dates keeps that meaning.
    den = np.full(len(num), len(assets) / max(1, len(num)))
    return num, den


def rotation_null_mean(signal: pd.DataFrame, forward: pd.DataFrame, horizon: int, lookback: int = 200) -> float | None:
    """Diagnostic for the FIRST run's statistic: its average when forward returns are slid against the
    signals by offsets that keep the two windows apart (so no real effect can be present). A value far from
    zero is the small-sample bias the first-run statistic carries on this very data."""
    keep = signal.notna() & forward.notna()
    if keep.sum().sum() == 0:
        return None
    a = time_ranks(signal.where(keep)).where(keep).fillna(0.0).to_numpy()
    b = time_ranks(forward.where(keep)).where(keep).fillna(0.0).to_numpy()
    m = keep.to_numpy(dtype=float)
    n = len(a)
    offsets = np.arange(horizon + 2, n - (lookback + horizon + 2) + 1)
    if len(offsets) < 10:
        return None

    def xcorr(x, y):
        return np.fft.irfft((np.conj(np.fft.rfft(x, axis=0)) * np.fft.rfft(y, axis=0)).sum(axis=1), n=n)

    values = xcorr(a, b)[offsets] / np.maximum(xcorr(m, m)[offsets], 1.0)
    return float(values.mean())


# ----------------------------------------------------------------------------- inference

def block_draws(num: np.ndarray, den: np.ndarray, block: int, runs: int = RUNS, seed: int = SEED) -> np.ndarray:
    """Joint-date circular block bootstrap of sum(num)/sum(den)."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    n = len(num)
    block = max(1, min(int(block), n))
    nb = math.ceil(n / block)
    rng = np.random.default_rng(seed)
    out = np.empty(runs)
    for start in range(0, runs, 500):                       # chunks keep memory small
        m = min(500, runs - start)
        starts = rng.integers(0, n, size=(m, nb))
        idx = ((starts[:, :, None] + np.arange(block)) % n).reshape(m, -1)[:, :n]
        out[start:start + m] = num[idx].sum(1) / den[idx].sum(1)
    return out


def block_for(horizon: int) -> int:
    return max(20, 2 * int(horizon))


def studentised_test(num, den, horizon: int, kappa: float, direction: int = 1, mme: float | None = None,
                     runs: int = RUNS, seed: int = SEED) -> dict:
    """Estimate, 95% confidence interval and one-sided p-values for one primary statistic.

    - The bootstrap gives the standard error (sd of the resampled statistic), inflated by kappa.
    - The reference is Student's t with (number of blocks - 1) degrees of freedom.
    - p_value tests H0: effect <= 0 in the claimed direction (direction = +1 or -1).
    - p_vs_mme tests H0: effect <= the minimum meaningful effect (evidence it is ABOVE the threshold).
    - ci95 is two-sided and is a statement about the size of the effect, not a test.
    """
    num, den = np.asarray(num, float), np.asarray(den, float)
    if len(num) < 40 or den.sum() <= 0:
        return {"estimate": None}
    block = block_for(horizon)
    est = float(num.sum() / den.sum())
    se = float(block_draws(num, den, block, runs, seed).std(ddof=1)) * kappa
    df = max(1, math.ceil(len(num) / block) - 1)
    signed = direction * est
    out = {
        "estimate": est, "se": se, "kappa": kappa, "block": block, "df": df, "dates": int(len(num)),
        "ci95": (est - t_dist.ppf(0.975, df) * se, est + t_dist.ppf(0.975, df) * se),
        "one_sided_bound95": signed - t_dist.ppf(0.95, df) * se,          # in the claimed direction
        "one_sided_upper95": signed + t_dist.ppf(0.95, df) * se,
        "p_value": float(t_dist.sf(signed / se, df)) if se > 0 else None,
    }
    if mme is not None and se > 0:
        out["p_vs_mme"] = float(t_dist.sf((signed - mme) / se, df))
    return out


def holm(p_values: dict, alpha: float = 0.05) -> dict:
    """Holm step-down. Returns {name: passed} for the family."""
    order = sorted(p_values, key=lambda k: (p_values[k] is None, p_values[k] if p_values[k] is not None else 1))
    passed, m, still = {}, len(order), True
    for i, name in enumerate(order):
        p = p_values[name]
        ok = still and p is not None and p <= alpha / (m - i)
        passed[name] = bool(ok)
        still = ok
    return passed


def outcome(test: dict, holm_passed: bool, mme: float) -> str:
    """The outcome labels fixed in the spec (section 0 and 4)."""
    if test.get("estimate") is None:
        return "Not enough data"
    signed = test["one_sided_bound95"] + t_dist.ppf(0.95, test["df"]) * test["se"]
    if test["one_sided_upper95"] < 0:
        return "Contradicted"
    if holm_passed and signed >= mme:
        if test.get("p_vs_mme") is not None and test["p_vs_mme"] <= 0.05:
            return "Confirmed, clearly above the minimum"
        return "Confirmed"
    return "Inconclusive"


# ----------------------------------------------------------------------------- long-only crypto portfolio

def long_only_portfolio(signal: pd.DataFrame, closes: pd.DataFrame, top: int | str | None, period: int = 14,
                        cost_per_side: float = 0.002, lag: int = LAG, tranches: int | None = None) -> dict:
    """Staggered long-only portfolio with real holdings, drift, turnover and costs.

    - Tranche k (k = 0..tranches-1) re-selects on signal dates k, k+period, ... and trades at the NEXT
      close (signal close t, trade close t+lag). Its first holdings are bought at the first trade.
    - Selection: the `top` assets by signal among those with a signal at t and prices at t+lag ("third" =
      a third of the eligible assets, rounded down); top=None holds all of them (the equal-weight
      benchmark, run through the same code). Ties are broken by column order.
    - Between trades weights drift with prices. Trading cost = cost_per_side x sum(|new - drifted weight|)
      (buying from cash counts too).
    - Tranches are separate accounts with equal starting capital; the combined return is their capital-
      weighted total. They overlap in time and hold similar coins, so they are ONE portfolio for inference,
      never 14 independent experiments.
    Returns daily net and gross returns of the combined portfolio, and turnover figures.
    """
    tranches = tranches or period
    closes = closes.reindex(signal.index)
    rets = closes.pct_change().fillna(0.0).to_numpy()
    sig = signal.to_numpy(dtype=float)
    px = closes.to_numpy(dtype=float)
    n, k = sig.shape
    values = np.full(tranches, 1.0 / tranches)
    weights = np.zeros((tranches, k))
    started = np.zeros(tranches, bool)
    gross_daily, net_daily, traded_log = np.zeros(n), np.zeros(n), []
    for d in range(1, n):
        # 1) prices move from close d-1 to close d: every tranche's holdings drift
        total_before = values.sum()
        growth = (weights * rets[d]).sum(axis=1)
        values = values * (1 + growth)
        held = weights * (1 + rets[d])
        sums = held.sum(axis=1, keepdims=True)
        weights = np.divide(held, sums, out=np.zeros_like(held), where=sums > 0)
        gross = values.sum() / total_before - 1
        # 2) trades at close d for tranches whose signal date is d - lag
        t = d - lag
        cost_total = 0.0
        for j in range(tranches):
            if t < 0 or (t - j) % period:
                continue
            ok = ~np.isnan(sig[t]) & ~np.isnan(px[d])
            if ok.sum() == 0:
                continue
            target = np.zeros(k)
            idx = np.where(ok)[0]
            if top is not None:
                n_top = max(1, len(idx) // 3) if top == "third" else int(top)
                order = idx[np.argsort(sig[t, idx], kind="mergesort")]
                idx = order[-n_top:]
            target[idx] = 1.0 / len(idx)
            traded = np.abs(target - (weights[j] if started[j] else 0.0)).sum()
            c = cost_per_side * traded * values[j]
            values[j] -= c
            cost_total += c
            traded_log.append(traded)
            weights[j], started[j] = target, True
        gross_daily[d] = gross
        net_daily[d] = (values.sum() + 0.0) / total_before - 1   # after this day's costs
    traded = np.array(traded_log)
    first_trades = tranches
    later = traded[first_trades:] if len(traded) > first_trades else traded
    return {
        "net": pd.Series(net_daily, index=signal.index),
        "gross": pd.Series(gross_daily, index=signal.index),
        "mean_traded_per_rebalance": float(later.mean()) if len(later) else None,   # sum |dw|; one-way = half
        "rebalances": int(len(traded)),
    }


def buy_and_hold(close: pd.Series, index: pd.Index, cost_per_side: float = 0.002, lag: int = LAG) -> dict:
    """One asset bought at the close `lag` bars after the first date of `index`, then held. One purchase cost,
    no sale (it is still held at the end). Same output shape as long_only_portfolio."""
    px = close.reindex(index)
    r = px.pct_change().fillna(0.0).to_numpy()
    net = np.zeros(len(index))
    for d in range(lag + 1, len(index)):
        net[d] = r[d]
    if len(index) > lag:
        net[lag] = -cost_per_side            # bought at close `lag`
    series = pd.Series(net, index=index)
    return {"net": series, "gross": series.where(series.index != index[min(lag, len(index) - 1)], 0.0),
            "mean_traded_per_rebalance": 0.0, "rebalances": 1}


def portfolio_summary(strategy: dict, benchmark: dict, periods_per_year: int = 365, horizon_block: int = 28,
                      runs: int = 2000, skip: int = 15, period: int = 14, extra: dict | None = None) -> dict:
    """Net excess return a year (strategy minus benchmark), with a block-bootstrap band, plus drawdowns.
    The first `skip` days are left out: tranches are still buying in and partly hold cash."""
    strategy = {**strategy, "net": strategy["net"].iloc[skip:]}
    benchmark = {**benchmark, "net": benchmark["net"].iloc[skip:]}
    excess = strategy["net"] - benchmark["net"]
    est = float(excess.mean() * periods_per_year * 100)
    draws = block_draws(excess.to_numpy(), np.ones(len(excess)), horizon_block, runs) * periods_per_year * 100

    def drawdown(r):
        wealth = (1 + r).cumprod()
        return float((wealth / wealth.cummax() - 1).min() * 100)

    def per_year(r):
        return float(((1 + r).prod() ** (periods_per_year / max(1, len(r))) - 1) * 100)

    return {
        "excess_pct_a_year": est, "band95": (float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))),
        "strategy_pct_a_year": per_year(strategy["net"]),
        "benchmark_pct_a_year": per_year(benchmark["net"]),
        "strategy_max_drawdown_pct": drawdown(strategy["net"]),
        "benchmark_max_drawdown_pct": drawdown(benchmark["net"]),
        "strategy_traded_per_rebalance": strategy["mean_traded_per_rebalance"],
        "benchmark_traded_per_rebalance": benchmark["mean_traded_per_rebalance"],
        # one-way turnover a year: half the traded value per rebalance x rebalances a year of the whole book
        "strategy_one_way_turnover_a_year": (strategy["mean_traded_per_rebalance"] or 0) / 2 * periods_per_year / period,
        "benchmark_one_way_turnover_a_year": (benchmark["mean_traded_per_rebalance"] or 0) / 2 * periods_per_year / period,
        "against": {name: _against(strategy["net"], other["net"].iloc[skip:], periods_per_year, horizon_block, runs,
                                   per_year, drawdown) for name, other in (extra or {}).items()},
    }


def _against(strategy_net, other_net, periods_per_year, block, runs, per_year, drawdown) -> dict:
    """The strategy against another benchmark (e.g. Bitcoin held throughout), same dates."""
    other_net = other_net.reindex(strategy_net.index).fillna(0.0)
    excess = strategy_net - other_net
    draws = block_draws(excess.to_numpy(), np.ones(len(excess)), block, runs) * periods_per_year * 100
    return {"excess_pct_a_year": float(excess.mean() * periods_per_year * 100),
            "band95": (float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))),
            "benchmark_pct_a_year": per_year(other_net), "benchmark_max_drawdown_pct": drawdown(other_net)}


# ----------------------------------------------------------------------------- expected-move ranges

def fit_expected_move(atr_pct: pd.DataFrame, closes: pd.DataFrame, horizon: int,
                      coverages=(0.5, 0.8), lag: int = LAG) -> dict:
    """k such that |move from t+lag to t+lag+h| <= k * ATR% * sqrt(h) for the given share of asset-dates."""
    ratio = (forward_returns_table(closes, horizon, lag).abs() / (atr_pct * math.sqrt(horizon))).stack().dropna()
    ratio = ratio[np.isfinite(ratio)]
    return {c: float(ratio.quantile(c)) for c in coverages} | {"n": int(len(ratio))}


def coverage(atr_pct: pd.DataFrame, closes: pd.DataFrame, horizon: int, k: dict, lag: int = LAG) -> dict:
    move = forward_returns_table(closes, horizon, lag).abs()
    width = atr_pct * math.sqrt(horizon)
    out = {}
    for c, kk in k.items():
        if c == "n":
            continue
        inside = (move <= kk * width).where(move.notna() & width.notna())
        out[c] = float(inside.stack().mean())
    return out


def forward_returns_table(closes: pd.DataFrame, horizon: int, lag: int = LAG) -> pd.DataFrame:
    return pd.DataFrame({c: forward_returns(closes[c], horizon, lag) for c in closes.columns})
