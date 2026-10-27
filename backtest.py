"""Walk-forward backtest of the technical score against later price.

The Signal matrix looks at 30 days. That is too short to say much. This script
replays the same score over years of daily bars and answers three plain questions:

1. When the score was high (or low), what did price do next, compared with
   what price did on an average day?
2. Does the score rank days in the right order (rank correlation), and does
   that hold in both halves of the history?
3. If you only held while the score said so, after costs, how would that
   compare with buy and hold?

Nothing here looks ahead. The score on day t uses bars up to and including t.
Trades happen one bar later (LAG), at the next close, so a signal is never
traded at the price that produced it. Forward returns over h bars overlap, so
the effective number of observations is roughly n / h; that is what the noise
floors use.

Usage:
    python backtest.py --ticker BTC-USD --period 5y
    python backtest.py --csv prices.csv --bull 65 --bear 35 --horizons 1,5,10
    python backtest.py --ticker AAPL --json report.json

A CSV needs a date column plus open, high, low, close (volume is optional).
"""

from __future__ import annotations

import argparse
import json
import math
import sys

import numpy as np
import pandas as pd

WARMUP = 200  # bars before the first score, so SMA 200 and Ichimoku are filled
LAG = 1  # bars between the signal close and the trade
DEFAULT_HORIZONS = (1, 3, 7, 14)


# --------------------------------------------------------------------------- data


def load_prices(ticker: str | None = None, period: str = "5y", csv_path: str | None = None) -> pd.DataFrame:
    """Daily bars with lowercase open/high/low/close/volume columns and a date index."""
    if csv_path:
        frame = pd.read_csv(csv_path)
        frame.columns = [str(name).strip().lower() for name in frame.columns]
        date_col = "date" if "date" in frame.columns else frame.columns[0]
        frame[date_col] = pd.to_datetime(frame[date_col], utc=True).dt.tz_localize(None)
        frame = frame.set_index(date_col)
    elif ticker:
        import yfinance as yf  # imported here so the maths works without it

        frame = yf.download(ticker, period=period, interval="1d", auto_adjust=True, progress=False)
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        frame.columns = [str(name).strip().lower() for name in frame.columns]
        frame.index = pd.to_datetime(frame.index).tz_localize(None)
    else:
        raise ValueError("Give a ticker or a CSV file.")
    needed = ["open", "high", "low", "close"]
    missing = [name for name in needed if name not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")
    if "volume" not in frame.columns:
        frame["volume"] = 0.0
    frame = frame[needed + ["volume"]].astype(float)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index().dropna(subset=["close"])
    return frame


# ------------------------------------------------------------------------ signals


def score_series(frame: pd.DataFrame, weights: dict | None = None, warmup: int = WARMUP, score_fn=None) -> pd.Series:
    """Technical score for each day from warmup on, using only bars up to that day.

    score_fn(window) -> number or None lets tests supply their own signal.
    """
    if score_fn is None:
        from scoring import calculate_indicators, compute_score

        indicated = calculate_indicators(frame)

        def score_fn(window):
            result = compute_score(window, weights)
            if not isinstance(result, dict) or result.get("label") == "Insufficient data":
                return None
            return result.get("score")

        source = indicated
    else:
        source = frame

    values = {}
    for end in range(warmup, len(source)):
        try:
            value = score_fn(source.iloc[: end + 1])
        except Exception:
            value = None
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = float("nan")
        values[source.index[end]] = number if math.isfinite(number) else float("nan")
    return pd.Series(values, dtype=float, name="score")


def forward_returns(closes: pd.Series, horizon: int, lag: int = LAG) -> pd.Series:
    """Percent change from the trade close (t + lag) to the exit close (t + lag + horizon)."""
    entry = closes.shift(-lag)
    exit_ = closes.shift(-(lag + horizon))
    return (exit_ / entry - 1.0) * 100.0


# ------------------------------------------------------------------------- stats


def effective_n(n: int, horizon: int) -> float:
    """Overlapping h-bar returns carry about n / h independent observations."""
    return n / max(1, int(horizon))


def noise_floor(n_eff: float) -> float | None:
    """Correlation size that stands out from chance at about 95 percent."""
    return 1.96 / math.sqrt(n_eff) if n_eff > 0 else None


def rank_correlation(left, right) -> float | None:
    """Spearman correlation without scipy. None when there is no spread."""
    a = pd.Series(list(left), dtype=float)
    b = pd.Series(list(right), dtype=float)
    keep = a.notna() & b.notna()
    a, b = a[keep], b[keep]
    if len(a) < 3 or a.nunique() < 2 or b.nunique() < 2:
        return None
    value = a.rank().corr(b.rank())
    return None if value is None or not math.isfinite(value) else float(value)


def bucket_stats(scores: pd.Series, fwd: pd.Series, bull: float, bear: float, horizon: int) -> dict:
    """What happened next, by score bucket, against the average day."""
    frame = pd.DataFrame({"score": scores, "fwd": fwd}).dropna()
    base_mean = float(frame["fwd"].mean()) if len(frame) else None
    base_up = float((frame["fwd"] > 0).mean()) if len(frame) else None
    out = {
        "n": int(len(frame)),
        "base_mean_pct": base_mean,
        "base_up_rate": base_up,
    }
    buckets = {
        "high": frame[frame["score"] >= bull],
        "middle": frame[(frame["score"] < bull) & (frame["score"] > bear)],
        "low": frame[frame["score"] <= bear],
    }
    for name, part in buckets.items():
        n = int(len(part))
        info = {"n": n, "effective_n": effective_n(n, horizon)}
        if n:
            mean = float(part["fwd"].mean())
            info.update(
                mean_pct=mean,
                excess_pct=None if base_mean is None else mean - base_mean,
                up_rate=float((part["fwd"] > 0).mean()),
            )
            n_eff = info["effective_n"]
            if n >= 2 and n_eff >= 2:
                spread = float(part["fwd"].std(ddof=1))
                # standard error shrunk to effective n: overlapping returns count once
                info["t_stat"] = None if spread == 0 else (mean - (base_mean or 0.0)) / (spread / math.sqrt(n_eff))
        out[name] = info
    return out


def information_coefficient(scores: pd.Series, fwd: pd.Series, horizon: int) -> dict:
    """Rank correlation of score with later return, whole run and each half."""
    frame = pd.DataFrame({"score": scores, "fwd": fwd}).dropna()
    result = {"n": int(len(frame))}
    whole = rank_correlation(frame["score"], frame["fwd"])
    result["ic"] = whole
    result["noise_floor"] = noise_floor(effective_n(len(frame), horizon))
    middle = len(frame) // 2
    for label, part in (("first_half", frame.iloc[:middle]), ("second_half", frame.iloc[middle:])):
        result[label] = rank_correlation(part["score"], part["fwd"])
        result[label + "_noise_floor"] = noise_floor(effective_n(len(part), horizon))
    return result


# ---------------------------------------------------------------------- strategy


def run_strategy(
    closes: pd.Series,
    scores: pd.Series,
    enter: float = 70.0,
    exit_below: float = 50.0,
    cost_bps: float = 10.0,
    lag: int = LAG,
) -> dict:
    """Long when the score reaches enter, flat once it falls below exit_below.

    A position decided at the close of day t is entered at the close of day
    t + lag, so it first earns the return from t + lag to t + lag + 1. This
    matches forward_returns. cost_bps is charged on each side whenever the
    position changes.
    """
    aligned = pd.DataFrame({"close": closes, "score": scores}).dropna(subset=["close"])
    state = 0
    wanted = []
    for value in aligned["score"]:
        if value == value:
            if state == 0 and value >= enter:
                state = 1
            elif state == 1 and value < exit_below:
                state = 0
        wanted.append(state)
    position = pd.Series(wanted, index=aligned.index, dtype=float).shift(lag + 1).fillna(0.0)
    daily = aligned["close"].pct_change().fillna(0.0)
    trades = position.diff().abs().fillna(position.abs())
    net = position * daily - trades * (cost_bps / 10000.0)

    start = scores.first_valid_index()
    if start is not None:
        net = net.loc[start:]
        daily = daily.loc[start:]
        position = position.loc[start:]
        trades = trades.loc[start:]
    equity = (1.0 + net).cumprod()
    hold = (1.0 + daily).cumprod()
    return {
        "days": int(len(net)),
        "strategy_return_pct": float((equity.iloc[-1] - 1.0) * 100.0) if len(equity) else None,
        "buy_hold_return_pct": float((hold.iloc[-1] - 1.0) * 100.0) if len(hold) else None,
        "strategy_max_drawdown_pct": _max_drawdown(equity),
        "buy_hold_max_drawdown_pct": _max_drawdown(hold),
        "exposure_pct": float(position.mean() * 100.0) if len(position) else None,
        "position_changes": int(trades.sum()) if len(trades) else 0,
        "cost_bps_per_side": cost_bps,
    }


def _max_drawdown(equity: pd.Series) -> float | None:
    if equity is None or len(equity) == 0:
        return None
    peak = equity.cummax()
    return float(((equity / peak) - 1.0).min() * 100.0)


# ------------------------------------------------------------------------ driver


def run_backtest(
    frame: pd.DataFrame,
    weights: dict | None = None,
    bull: float = 70.0,
    bear: float = 30.0,
    horizons=DEFAULT_HORIZONS,
    exit_below: float = 50.0,
    cost_bps: float = 10.0,
    warmup: int = WARMUP,
    score_fn=None,
) -> dict:
    scores = score_series(frame, weights, warmup=warmup, score_fn=score_fn)
    closes = frame["close"]
    report = {
        "bars": int(len(frame)),
        "scored_days": int(scores.notna().sum()),
        "first_scored": None if scores.first_valid_index() is None else str(scores.first_valid_index())[:10],
        "last_scored": None if scores.last_valid_index() is None else str(scores.last_valid_index())[:10],
        "bull": bull,
        "bear": bear,
        "lag_bars": LAG,
        "horizons": {},
    }
    for horizon in horizons:
        fwd = forward_returns(closes, int(horizon)).reindex(scores.index)
        report["horizons"][int(horizon)] = {
            "buckets": bucket_stats(scores, fwd, bull, bear, int(horizon)),
            "rank_correlation": information_coefficient(scores, fwd, int(horizon)),
        }
    report["strategy"] = run_strategy(closes, scores, enter=bull, exit_below=exit_below, cost_bps=cost_bps)
    return report


def _pct(value, digits=2, sign=False) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "-"
    return f"{value:+.{digits}f}%" if sign else f"{value:.{digits}f}%"


def _num(value, digits=2) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "-"
    return f"{value:+.{digits}f}"


def format_report(report: dict, label: str = "") -> str:
    lines = []
    head = f"Backtest {label}".strip()
    lines.append(head)
    lines.append(
        f"{report['scored_days']} scored days ({report['first_scored']} to {report['last_scored']}), "
        f"trades {report['lag_bars']} bar after the signal."
    )
    for horizon, block in report["horizons"].items():
        buckets = block["buckets"]
        ic = block["rank_correlation"]
        lines.append("")
        lines.append(f"Next {horizon} day{'s' if horizon != 1 else ''}  (average day: {_pct(buckets['base_mean_pct'], sign=True)}, up {_pct((buckets['base_up_rate'] or 0) * 100 if buckets['base_up_rate'] is not None else None, 0)})")
        lines.append(f"  {'bucket':<8}{'cases':>7}{'eff.n':>7}{'mean':>9}{'vs avg':>9}{'up':>6}{'t':>7}")
        for name, title in (("high", f">= {report['bull']:g}"), ("middle", "middle"), ("low", f"<= {report['bear']:g}")):
            info = buckets.get(name, {})
            if not info.get("n"):
                lines.append(f"  {title:<8}{0:>7}")
                continue
            up = None if info.get("up_rate") is None else info["up_rate"] * 100
            lines.append(
                f"  {title:<8}{info['n']:>7}{info['effective_n']:>7.0f}"
                f"{_pct(info.get('mean_pct'), sign=True):>9}{_pct(info.get('excess_pct'), sign=True):>9}"
                f"{_pct(up, 0):>6}{_num(info.get('t_stat'), 1):>7}"
            )
        lines.append(
            f"  rank correlation {_num(ic['ic'])} (noise ±{_num(ic['noise_floor']).lstrip('+')}); "
            f"first half {_num(ic['first_half'])}, second half {_num(ic['second_half'])}"
        )
    strat = report["strategy"]
    lines.append("")
    lines.append("Hold while the score says so (long only)")
    lines.append(
        f"  strategy {_pct(strat['strategy_return_pct'], 1, True)} (max drawdown {_pct(strat['strategy_max_drawdown_pct'], 1)}), "
        f"buy and hold {_pct(strat['buy_hold_return_pct'], 1, True)} (max drawdown {_pct(strat['buy_hold_max_drawdown_pct'], 1)})"
    )
    lines.append(
        f"  in the market {_pct(strat['exposure_pct'], 0)} of days, {strat['position_changes']} position changes, "
        f"{strat['cost_bps_per_side']:g} bps per side"
    )
    lines.append("")
    lines.append(
        "Read it with care: eff.n is cases divided by the horizon because overlapping returns are not independent. "
        "A t-stat under about 2 or a rank correlation inside the noise band is not evidence. "
        "One asset and one period can look good by luck; run several assets and compare the two halves."
    )
    return "\n".join(lines)


def _parse_horizons(text: str) -> tuple[int, ...]:
    values = tuple(sorted({int(part) for part in text.split(",") if part.strip()}))
    if not values or any(v < 1 for v in values):
        raise argparse.ArgumentTypeError("horizons must be positive whole numbers, like 1,3,7")
    return values


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Walk-forward backtest of the technical score.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--ticker", help="yfinance symbol, e.g. BTC-USD or AAPL")
    source.add_argument("--csv", help="CSV with date, open, high, low, close[, volume]")
    parser.add_argument("--period", default="5y", help="yfinance period (default 5y)")
    parser.add_argument("--bull", type=float, default=70.0, help="high-score boundary (default 70)")
    parser.add_argument("--bear", type=float, default=30.0, help="low-score boundary (default 30)")
    parser.add_argument("--exit-below", type=float, default=50.0, help="strategy goes flat below this score")
    parser.add_argument("--horizons", type=_parse_horizons, default=DEFAULT_HORIZONS)
    parser.add_argument("--cost-bps", type=float, default=10.0, help="cost per side in basis points")
    parser.add_argument("--json", dest="json_path", help="also write the full report here")
    args = parser.parse_args(argv)

    try:
        frame = load_prices(args.ticker, args.period, args.csv)
    except Exception as exc:
        print(f"Could not load prices: {exc}", file=sys.stderr)
        return 2
    if len(frame) < WARMUP + 30:
        print(f"Only {len(frame)} bars; need at least {WARMUP + 30}.", file=sys.stderr)
        return 2
    report = run_backtest(
        frame,
        bull=args.bull,
        bear=args.bear,
        horizons=args.horizons,
        exit_below=args.exit_below,
        cost_bps=args.cost_bps,
    )
    print(format_report(report, args.ticker or args.csv))
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
