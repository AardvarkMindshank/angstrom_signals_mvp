"""How much has the technical score actually told us about this asset?

build_evidence replays the score over years of daily bars (no look-ahead, trade
one bar after the signal) and boils the result down to a small record. The
verdict comes from fixed rules, not from a model, and defaults to "no evidence".
An AI paragraph may reword the numbers, but only if every number in it already
appears in the facts it was given and it uses none of the banned phrases.

The alert worker builds one record per asset a few times a day and stores it in
asset_evidence. The dashboard only reads it.
"""

from __future__ import annotations

import math
import re
import time
from datetime import datetime, timezone

import pandas as pd

import backtest as bt

VERSION = 1
HORIZONS = (1, 3, 7, 14)
# Warm-up bars plus enough scored days that a 14-day horizon is not empty.
MIN_BARS = bt.WARMUP + 300
FETCH_DAYS = 1825  # about five years
FUNDING_PRICE_DAYS = 3650  # as much history as Yahoo has, to overlap funding from 2019
REFRESH_SECONDS = 24 * 60 * 60
# How many assets one worker run will evaluate. Each takes a little while to score.
EVIDENCE_BATCH = 2

_BANNED = (
    "guarantee", "will rise", "will fall", "will go up", "will go down", "buy now",
    "sell now", "you should buy", "you should sell", "risk-free", "can't lose", "profit from",
)
_BANNED_WHEN_NONE = ("strong signal", "reliable signal", "proves", "proven", "predictive power")


# ------------------------------------------------------------------- the numbers


def _clean(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 4) if math.isfinite(number) else None


def build_evidence(
    frame: pd.DataFrame,
    bull: float = 70.0,
    bear: float = 30.0,
    horizons=HORIZONS,
    detail_fn=None,
    warmup: int = bt.WARMUP,
) -> dict | None:
    """The record for one asset, or None when there is too little history."""
    if frame is None or len(frame) < warmup + 300:
        return None
    details = bt.score_details(frame, detail_fn=detail_fn, warmup=warmup)
    if details.empty or details["score"].notna().sum() < 250:
        return None
    closes = frame["close"]
    total = details["score"]

    record = {
        "version": VERSION,
        "asof": str(details.index[-1])[:10],
        "first_scored": str(details.index[0])[:10],
        "scored_days": int(total.notna().sum()),
        "bull": bull,
        "bear": bear,
        "horizons": {},
        "factors": {},
    }
    factor_columns = {name: details[name] for name in bt.FACTOR_NAMES if name in details.columns}
    for title, members in bt.FACTOR_GROUPS.items():
        present = [member for member in members if member in details.columns]
        if present:
            factor_columns[title.replace("GROUP ", "").split(" (")[0] + " group"] = details[present].sum(axis=1, min_count=1)

    for horizon in horizons:
        fwd = bt.forward_returns(closes, int(horizon)).reindex(details.index)
        ic = bt.information_coefficient(total, fwd, int(horizon))
        buckets = bt.bucket_stats(total, fwd, bull, bear, int(horizon))
        record["horizons"][str(horizon)] = {
            "n": ic["n"],
            "ic": _clean(ic["ic"]),
            "noise": _clean(ic["noise_floor"]),
            "first_half": _clean(ic["first_half"]),
            "second_half": _clean(ic["second_half"]),
            "base_mean": _clean(buckets["base_mean_pct"]),
            "base_up": _clean(buckets["base_up_rate"]),
            "high": _bucket(buckets.get("high")),
            "low": _bucket(buckets.get("low")),
        }
        for name, values in factor_columns.items():
            pair = pd.DataFrame({"x": values, "fwd": fwd}).dropna()
            record["factors"].setdefault(name, {})[str(horizon)] = {
                "ic": _clean(bt.rank_correlation(pair["x"], pair["fwd"])),
                "noise": _clean(bt.noise_floor(bt.effective_n(len(pair), int(horizon)))),
            }

    block = _volatility_block(details, closes, horizons)
    if block:
        record["volatility"] = block

    strategy = bt.run_strategy(closes, total, enter=bull)
    record["strategy"] = {key: _clean(strategy.get(key)) for key in (
        "strategy_return_pct", "buy_hold_return_pct", "exposure_pct",
        "strategy_max_drawdown_pct", "buy_hold_max_drawdown_pct",
    )}
    record["verdict"] = verdict_for(record)
    record["text"] = plain_text(record)
    return record


def _volatility_block(details: pd.DataFrame, closes: pd.Series, horizons) -> dict | None:
    """Recent typical daily range, where it sits in this asset's own history, and
    whether wide ranges were followed by bigger moves here (beyond recent volatility)."""
    if "x_atr_pct" not in details.columns:
        return None
    series = details["x_atr_pct"].dropna()
    if len(series) < 250:
        return None
    now = float(series.iloc[-1])
    control = bt.trailing_activity(closes).reindex(details.index)
    checks = {}
    for horizon in horizons:
        future = bt.forward_activity(closes, int(horizon)).reindex(details.index)
        pair = pd.DataFrame({"y": future, "z": control}).dropna()
        checks[str(horizon)] = {
            "partial": _clean(bt.partial_rank_correlation(details["x_atr_pct"], future, control)),
            "noise": _clean(bt.noise_floor(bt.effective_n(len(pair), int(horizon)))),
        }
    return {
        "atr_now": _clean(now),
        "atr_median": _clean(series.median()),
        "atr_percentile": _clean(float((series < now).mean() * 100.0)),
        "checks": checks,
    }


def _funding_block(kind: str, asset_id: str, frame: pd.DataFrame) -> dict | None:
    """Funding summary for a crypto asset, or None when it cannot be fetched (blocked, no contract...)."""
    if kind != "Crypto":
        return None
    try:
        import funding as fd
        from data_fetchers import crypto_ticker, fetch_crypto_data

        base = crypto_ticker(asset_id)
        if not base:
            return None
        # Funding exists since about 2019, and the effect was strongest in 2020-21, so use
        # the longest price history there is, not only the five years the score test uses.
        prices = frame
        try:
            longer, err = fetch_crypto_data(asset_id, FUNDING_PRICE_DAYS)
            if not err and longer is not None and len(longer) > len(frame):
                prices = longer
        except Exception:
            pass
        series = fd.fetch_binance_funding(f"{base}USDT", prices.index[0])
        daily = fd.daily_funding(series)
        return fd.funding_summary(daily, prices["close"])
    except Exception as exc:
        print(f"Funding skipped for {asset_id}: {str(exc)[:100]}")
        return None


def volatility_text(record: dict) -> str | None:
    """One honest sentence about recent range and whether it has been informative here."""
    block = record.get("volatility") or {}
    now, median, pct = block.get("atr_now"), block.get("atr_median"), block.get("atr_percentile")
    if now is None or median is None or pct is None:
        return None
    if pct >= 75:
        where = "higher than usual"
    elif pct <= 25:
        where = "lower than usual"
    else:
        where = "about usual"
    text = (
        f"Recent typical daily range: {now:.1f}% of price ({where} for this asset; its median is {median:.1f}%)."
    )
    held = [
        h for h, info in (block.get("checks") or {}).items()
        if info.get("partial") is not None and info.get("noise") is not None and info["partial"] >= info["noise"]
    ]
    if len(held) >= 2:
        text += (
            " On this asset, wide recent ranges have tended to be followed by bigger moves over the next days, "
            "beyond what closing prices alone showed. That is about size, not direction."
        )
    else:
        text += " On this asset the link between recent range and later move size was not clear in this test."
    return text


def _bucket(info: dict | None) -> dict:
    info = info or {}
    return {
        "n": int(info.get("n") or 0),
        "effective_n": _clean(info.get("effective_n")),
        "mean": _clean(info.get("mean_pct")),
        "excess": _clean(info.get("excess_pct")),
        "up": _clean(info.get("up_rate")),
    }


# ------------------------------------------------------------------- the verdict


def _sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def _horizon_passes(info: dict) -> int:
    """+1 or -1 when the score's link to later return clears the noise band and
    points the same way in both halves of the history. 0 otherwise."""
    ic, noise = info.get("ic"), info.get("noise")
    first, second = info.get("first_half"), info.get("second_half")
    if ic is None or noise is None or first is None or second is None:
        return 0
    if abs(ic) < noise:
        return 0
    direction = _sign(ic)
    if _sign(first) != direction or _sign(second) != direction:
        return 0
    return direction


def verdict_for(record: dict) -> dict:
    """Fixed rules. 'holds' needs the same result at two or more horizons."""
    passes = {h: _horizon_passes(info) for h, info in record["horizons"].items()}
    hits = {h: d for h, d in passes.items() if d}
    directions = set(hits.values())
    level = "none"
    reverse = False
    if len(directions) == 1:
        reverse = directions == {-1}
        level = "holds" if len(hits) >= 2 else "hint"
    elif len(directions) > 1:
        level = "none"  # pointed both ways: that is noise

    factors = []
    for name, per_horizon in record.get("factors", {}).items():
        seen = []
        for info in per_horizon.values():
            ic, noise = info.get("ic"), info.get("noise")
            if ic is not None and noise is not None and abs(ic) >= noise:
                seen.append(_sign(ic))
        if len(seen) >= 2 and len(set(seen)) == 1:
            factors.append(name)
    return {
        "level": level,
        "reverse": reverse,
        "horizons": sorted(int(h) for h in hits),
        "factors": factors,
    }


# ---------------------------------------------------------------------- the words


def _signed(value, digits=2) -> str:
    return "n/a" if value is None else f"{value:+.{digits}f}"


def _range_text(record: dict) -> tuple[str, str]:
    ics = [info["ic"] for info in record["horizons"].values() if info.get("ic") is not None]
    noises = [info["noise"] for info in record["horizons"].values() if info.get("noise") is not None]
    if not ics:
        return "n/a", "n/a"
    return f"{min(ics):+.2f} to {max(ics):+.2f}", f"{max(noises):.2f}"


def plain_text(record: dict) -> str:
    """The fixed, rule-based paragraph. It is always shown if the AI one is rejected."""
    verdict = record["verdict"]
    years = record["scored_days"] / 365.0
    span = f"{years:.1f} years ({record['scored_days']} days)"
    ics, noise = _range_text(record)
    if verdict["level"] == "none":
        text = (
            f"Over {span} of this asset's history, the technical score showed no evidence of lining up "
            f"with what price did next. Its rank correlation with later returns ran from {ics}, against a "
            f"noise band of up to ±{noise}, so the pattern "
            f"cannot be told apart from chance. Treat the score as a description of current conditions, "
            f"not a forecast."
        )
    else:
        way = "in the opposite direction to the label (high scores were followed by weaker prices)" if verdict["reverse"] else "in the direction the label suggests"
        horizons = ", ".join(str(h) for h in verdict["horizons"])
        strength = "held up" if verdict["level"] == "holds" else "showed a hint"
        text = (
            f"Over {span}, the score {strength} {way} at the {horizons}-day horizon"
            f"{'s' if len(verdict['horizons']) > 1 else ''}, in both halves of the history and beyond the noise band. "
            f"Even so, one asset over one period can look good by luck, and the link was weak "
            f"(rank correlation {ics}). Check that it also holds on similar assets before relying on it."
        )
    if verdict["factors"]:
        text += (
            " Among the individual factors, " + ", ".join(verdict["factors"])
            + " cleared the noise band at two or more horizons. With this many comparisons that is worth a closer look, not proof."
        )
    return text


def facts_for_model(record: dict, label: str) -> str:
    verdict = record["verdict"]
    lines = [
        f"Asset: {label}",
        f"Verdict (fixed rules, do not change it): {verdict['level']}"
        + (" (reverse direction)" if verdict["reverse"] else ""),
        f"Years tested: {record['scored_days'] / 365.0:.1f}",
    ]
    for horizon, info in record["horizons"].items():
        lines.append(
            f"{horizon}-day horizon: rank correlation {_signed(info['ic'])}, noise band ±{info['noise']:.2f}"
            if info.get("noise") is not None else f"{horizon}-day horizon: no data"
        )
    strategy = record.get("strategy") or {}
    if strategy.get("strategy_return_pct") is not None and strategy.get("buy_hold_return_pct") is not None:
        lines.append(
            f"Holding only while the score was high returned {strategy['strategy_return_pct']:.0f}% "
            f"against {strategy['buy_hold_return_pct']:.0f}% for buy and hold."
        )
    if verdict["factors"]:
        lines.append("Factors that cleared the noise band at two or more horizons: " + ", ".join(verdict["factors"]))
    return "\n".join(lines)


_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    found = set()
    for token in _NUMBER.findall(text):
        found.add(token)
        found.add(token.lstrip("0") or "0")
        if "." in token:
            found.add(token.rstrip("0").rstrip("."))
    return found


def ai_text_ok(text: str, facts: str, level: str) -> bool:
    """Accept the model's paragraph only if it adds no number or promise of its own."""
    clean = " ".join((text or "").split())
    if not 40 <= len(clean) <= 900:
        return False
    lowered = clean.lower()
    if any(phrase in lowered for phrase in _BANNED):
        return False
    if level == "none" and any(phrase in lowered for phrase in _BANNED_WHEN_NONE):
        return False
    if level == "none" and not any(word in lowered for word in ("no evidence", "not evidence", "no reliable", "cannot be told apart", "no clear")):
        return False
    return _numbers(clean) <= _numbers(facts)


def ai_summary(record: dict, label: str) -> str | None:
    """A short plain-English paragraph from the facts, or None when it cannot be trusted."""
    try:
        import requests
        from sentiment import _CHAT_URL, _MODELS, _api_key
    except Exception:
        return None
    key = _api_key()
    if not key:
        return None
    facts = facts_for_model(record, label)
    prompt = (
        "Write 3 or 4 plain sentences for a retail trader reading a dashboard. Explain what these backtest "
        "results say about how useful the technical score has been for this asset. Rules: use only the facts "
        "below; any number you write must appear in them; do not invent figures; do not give trading advice; "
        "do not predict prices; if the verdict is 'none', say plainly there is no evidence the score helped. "
        "Reply with the paragraph only.\n\n" + facts
    )
    for attempt in _MODELS[:2]:
        body = {
            "model": attempt["model"],
            "messages": [
                {"role": "system", "content": "You explain statistics honestly and never overstate evidence."},
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": 600,
            "temperature": 0.2,
        }
        if attempt.get("reasoning_effort"):
            body["reasoning_effort"] = attempt["reasoning_effort"]
        try:
            response = requests.post(
                _CHAT_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
                timeout=40,
            )
            if response.status_code != 200:
                continue
            text = response.json()["choices"][0]["message"]["content"]
        except Exception:
            continue
        if ai_text_ok(text, facts, record["verdict"]["level"]):
            return " ".join(text.split())
    return None


# ------------------------------------------------------------------ store + worker


def evidence_due(computed_at: float | None, now: float | None = None) -> bool:
    if computed_at is None:
        return True
    return (now if now is not None else time.time()) - float(computed_at) >= REFRESH_SECONDS


def _stamp(value) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def load_evidence(supabase, asset_key: str) -> dict | None:
    """The stored record for one asset, or None when it is not there (or the table is not)."""
    try:
        rows = (
            supabase.table("asset_evidence")
            .select("payload, computed_at")
            .eq("asset_key", asset_key)
            .execute()
            .data
            or []
        )
    except Exception:
        return None
    if not rows or not isinstance(rows[0].get("payload"), dict):
        return None
    payload = dict(rows[0]["payload"])
    payload["computed_at"] = rows[0].get("computed_at")
    return payload


def save_evidence(supabase, asset_key: str, payload: dict) -> bool:
    try:
        supabase.table("asset_evidence").upsert(
            {
                "asset_key": asset_key,
                "computed_at": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            },
            on_conflict="asset_key",
        ).execute()
        return True
    except Exception as exc:
        print(f"Evidence was not saved for {asset_key}: {str(exc)[:160]}")
        return False


def fetch_long_history(kind: str, asset_id: str):
    """About five years of daily bars for the evidence run."""
    from data_fetchers import fetch_crypto_data, fetch_stock_data

    if kind == "Crypto":
        return fetch_crypto_data(asset_id, FETCH_DAYS)
    return fetch_stock_data(asset_id, period="5y")


def refresh_due_evidence(supabase, catalog: dict, batch: int = EVIDENCE_BATCH) -> None:
    """Evaluate the assets whose record is missing or a day old. Oldest first, a few per run."""
    from market_store import asset_market_key

    if not catalog:
        return
    keys = {asset_market_key(kind, asset_id): (kind, asset_id, label) for (kind, asset_id), label in catalog.items()}
    try:
        stored = {
            row["asset_key"]: _stamp(row.get("computed_at"))
            for row in (
                supabase.table("asset_evidence").select("asset_key, computed_at").in_("asset_key", list(keys)).execute().data or []
            )
        }
    except Exception as exc:
        print(f"Evidence skipped (run the latest supabase_rls.sql): {str(exc)[:120]}")
        return
    due = []
    for key, (kind, asset_id, label) in keys.items():
        stamp = stored.get(key)
        if evidence_due(stamp):
            due.append((stamp or 0.0, key, kind, asset_id, str(label or asset_id)))
    due.sort()
    done = 0
    for _stamp_value, key, kind, asset_id, label in due[: max(1, int(batch))]:
        try:
            frame, err = fetch_long_history(kind, asset_id)
            if err or frame is None or len(frame) < MIN_BARS:
                print(f"Evidence skipped for {label}: not enough history.")
                record = {"version": VERSION, "too_short": True, "bars": 0 if frame is None else int(len(frame))}
            else:
                record = build_evidence(frame)
                if record is None:
                    record = {"version": VERSION, "too_short": True, "bars": int(len(frame))}
                else:
                    record["ai_text"] = ai_summary(record, label)
                    block = _funding_block(kind, asset_id, frame)
                    if block:
                        record["funding"] = block
            if save_evidence(supabase, key, record):
                done += 1
        except Exception as exc:
            print(f"Evidence failed for {label}: {str(exc)[:160]}")
    print(f"Evidence: {done} updated, {max(0, len(due) - done)} still waiting.")
