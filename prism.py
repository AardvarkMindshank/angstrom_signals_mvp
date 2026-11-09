"""
Prism, the market scanner (docs/design/lattice_prism.md §5.1): Run now.

Runs one Set that has a decision on a list of assets, now (live, confirmed candles) or at one past moment (display
reconstruction), and turns each Set result into one row: each decision line's reading, the answer, how sure, the
decisive reason, and how much data was available.

Display only. Nothing is saved, exported or turned into a statistic (point_in_time.md §6, §8). Scheduled scans,
alerts and history are later stages.
"""

from __future__ import annotations

import copy

import pandas as pd

import signal_groups as sg

MAX_ASSETS = 40
ANSWER_TEXT = {"yes": "Yes", "no": "No", "unknown": "Unknown"}
ANSWER_ICON = {"yes": "✅", "no": "⛔", "unknown": "❔"}
VALUE_ICON = {"true": "✓", "false": "✗", "unknown": "?"}


# ----------------------------------------------------------------------------------------------- demo Sets
# Admin demos for stage 2 (design §8): the starters have no outcome labels, so these copies add them. They are new
# documents built in code, not starters, and nothing else reads them.

LABELS = {
    "starter:trend": [("bullish", "Bullish", {"score": {"gte": 0.3}}), ("bearish", "Bearish", {"score": {"lte": -0.3}}),
                      ("neutral", "Neutral")],
    "starter:flow": [("bullish", "Buying", {"score": {"gte": 0.3}}), ("bearish", "Selling", {"score": {"lte": -0.3}}),
                     ("neutral", "Neutral")],
    "starter:stretch": [("stretched_up", "Stretched up", {"score": {"gte": 0.5}}),
                        ("stretched_down", "Stretched down", {"score": {"lte": -0.5}}), ("normal", "Normal")],
}


def labelled_starter(alias: str) -> dict:
    doc = copy.deepcopy(sg.starter(alias))
    *rules, (other_id, other_label) = LABELS[alias]
    doc["name"] = f"{doc['name']} (with labels)"
    doc["outcomes"] = {"version": 1, "rules": [{"id": i, "label": label, "when": when} for i, label, when in rules],
                       "otherwise": {"id": other_id, "label": other_label}}
    return doc


def _group(key: str, alias: str) -> dict:
    body = labelled_starter(alias)
    return {"key": key, "snapshot": body,
            "provenance": {"source_config": alias, "note": "demo: the starter with outcome labels, built in code",
                           "content_sha256": sg.content_sha256(body)}}


def demo_sets() -> dict[str, dict]:
    base = {"schema": "angstrom.set/1", "lineage_version": 3, "score": None, "market_context": []}
    agree = {**base, "name": "Trend and Flow agree (demo)",
             "purpose": "Both the daily Trend and Flow readings are bullish.",
             "groups": [_group("trend", "starter:trend"), _group("flow", "starter:flow")], "standalone": [],
             "decision": {"version": 1, "rule": {"all": [{"group": "trend", "outcome": {"eq": "bullish"}},
                                                         {"group": "flow", "outcome": {"eq": "bullish"}}]}}}
    entry = {**base, "name": "Trend up, not overstretched (demo)",
             "purpose": "A bullish daily Trend that is not stretched up, while news sentiment is not clearly negative.",
             "groups": [_group("trend", "starter:trend"), _group("stretch", "starter:stretch")],
             "standalone": [{"key": "mood", "label": "Asset sentiment", "role": "condition",
                             "ref": {"id": "sentiment.asset", "version": 1, "timeframe": "1D", "params": {}}}],
             "decision": {"version": 1, "rule": {"all": [
                 {"group": "trend", "outcome": {"eq": "bullish"}},
                 {"not": {"group": "stretch", "outcome": {"eq": "stretched_up"}}},
                 {"member": "mood", "field": "score", "gte": -20}]}}}
    return {"demo:agree": agree, "demo:entry": entry, **against_trend_sets(), **library_sets()}


AGAINST_LEVEL = 0.3     # the dashboard's level for a pullback or rally inside a trend (signals_v2 against_trend_level)


def against_trend_sets() -> dict[str, dict]:
    """Pullback in an uptrend / Rally in a downtrend: the Trend and the Stretch pointing opposite ways, each at least
    0.3 (30) from zero. The asset card's note reads these Sets (group_readings.score)."""
    base = {"schema": "angstrom.set/1", "lineage_version": 3, "score": None, "market_context": [], "standalone": []}
    groups = [_group("trend", "starter:trend"), _group("stretch", "starter:stretch")]
    pullback = {**base, "name": "Pullback in an uptrend",
                "purpose": "The daily Trend is up (at least +30) while the Stretch has pulled back (−30 or lower).",
                "groups": groups, "decision": {"version": 1, "rule": {"all": [
                    {"group": "trend", "score": {"gte": AGAINST_LEVEL}},
                    {"group": "stretch", "score": {"lte": -AGAINST_LEVEL}}]}}}
    rally = {**base, "name": "Rally in a downtrend",
             "purpose": "The daily Trend is down (−30 or lower) while the Stretch has bounced (at least +30).",
             "groups": copy.deepcopy(groups), "decision": {"version": 1, "rule": {"all": [
                 {"group": "trend", "score": {"lte": -AGAINST_LEVEL}},
                 {"group": "stretch", "score": {"gte": AGAINST_LEVEL}}]}}}
    return {"demo:pullback": pullback, "demo:rally": rally}


# ----------------------------------------------------------------------------------------------- one row per asset

def _missing(result: dict) -> list[str]:
    """What was unavailable, in plain words (live results have no completeness block)."""
    out = []
    for g in result.get("groups") or []:
        r = g["result"]
        if r.get("status") in ("invalid", "unsupported"):
            out.append(f"{g['key']} (could not be evaluated)")
            continue
        for m in r.get("members") or []:
            if m["signal"]["status"] != "ok" and m.get("role") != "context":
                out.append(f"{g['key']}: {m.get('label') or m['key']}")
    for s in result.get("standalone") or []:
        if s["signal"]["status"] != "ok" and s.get("role") != "context":
            out.append(s.get("label") or s["key"])
    return out


def _availability(result: dict) -> tuple[str, str]:
    """(label, detail)."""
    completeness = result.get("completeness")
    if completeness:
        label = str(completeness.get("label") or "?")
        parts = [f"{m['item']}: {m['reason']}" for m in completeness.get("missing_items") or []]
        parts += [f"{k}: {v}" for k, v in (completeness.get("groups") or {}).items() if v and v != "complete"]
        parts += list(completeness.get("limitations") or [])
        return label.capitalize(), "; ".join(parts)
    missing = _missing(result)
    return ("Partial", "Missing: " + ", ".join(missing)) if missing else ("Complete", "All readings available")


def _line_text(line: dict) -> str:
    reading = line.get("reading")
    return line["text"] + (f" (reading: {reading})" if reading not in (None, "") else "")


def reason(decision: dict, missing: list[str]) -> tuple[str, str]:
    """(how sure, the decisive reason in plain words)."""
    answer = decision["answer"]
    decisive = [_line_text(d) for d in decision["decisive"]]
    if answer == "yes":
        return "Definite", "Every line holds."
    if answer == "no":
        text = "Fails on " + "; ".join(decisive) + "."
        if missing:
            text += " Missing " + ", ".join(missing) + " could not change this."
        return "Definite", text
    return "Undecided", "Depends on " + "; ".join(decisive) + ", which could not be decided."


def row(asset_name: str, result: dict, path: str) -> dict:
    """One results-table row from a Set result."""
    if result.get("status") != "ok" or "decision" not in result:
        problem = result.get("reason") or "; ".join(result.get("errors") or []) or result.get("status") or "error"
        return {"asset": asset_name, "answer": "unknown", "how_sure": "Undecided", "reason": f"Not evaluated: {problem}",
                "available": "—", "available_detail": "", "lines": {}, "path": path}
    decision = result["decision"]
    available, detail = _availability(result)
    how_sure, text = reason(decision, _missing(result))
    lines = {l["path"]: f"{VALUE_ICON[l['value']]} {l['reading'] if l['reading'] is not None else 'missing'}"
             for l in decision["lines"]}
    out = {"asset": asset_name, "answer": decision["answer"], "how_sure": how_sure, "reason": text,
           "available": available, "available_detail": detail, "lines": lines, "path": path}
    armed = [q for q in decision.get("sequences") or [] if q["state"] == "armed"]
    if armed and decision["answer"] != "yes":     # A seen, B can still come in time: not a match, shown beside it
        out["armed"] = {"left": min(q["left"] for q in armed), "text": "; ".join(q["text"] for q in armed)}
    return out


def columns(doc: dict) -> list[tuple[str, str]]:
    """(line path, header) for each decision line, in the rule's order, worded as the decision words them."""
    return list(_walk(doc["decision"]["rule"], "decision.rule"))


def _walk(rule: dict, path: str):
    from signal_groups.decision import _choice_text, _num_text, rule_text

    if "sequence" in rule:
        yield path, rule_text(rule)
        return
    for combo in ("all", "any"):
        if combo in rule:
            for i, sub in enumerate(rule[combo]):
                yield from _walk(sub, f"{path}.{combo}[{i}]")
            return
    if "not" in rule:
        for p, text in _walk(rule["not"], f"{path}.not"):
            yield p, "NOT " + text
        return
    if "group" in rule:
        g = rule["group"]
        if "outcome" in rule:
            yield path, f"{g} outcome {_choice_text(rule['outcome'])}"
        elif "score" in rule:
            yield path, f"{g} score {_num_text(rule['score'])}"
        elif "condition" in rule:
            yield path, f"{g} condition {rule['condition']} {_choice_text(rule['state'])}"
        else:
            yield path, f"{g} status {_choice_text(rule['status'])}"
    else:
        field = f".{rule['field']}" if rule.get("field") else ""
        yield path, f"{rule['member']}{field} " + ("has a matching event" if "events" in rule else _num_text(rule))


# ----------------------------------------------------------------------------------------------- running

def steps_needed(doc: dict) -> int:
    """Replay time steps one run of `doc` may need: 1, or for a sequence its earlier closes too (coins and shares
    close at different times, so up to two sets of them)."""
    from signal_groups import sequence

    n = sequence.longest(doc.get("decision") if isinstance(doc, dict) else None)
    return 1 + 2 * (n + 1) if n else 1


def _cutoff(run, kind: str, asset_id: str, day) -> pd.Timestamp:
    """When the daily candle of `asset_id` starting `day` closed, from the run's own candles."""
    history = run.history(kind, asset_id, "1D")
    pos = history.raw.index.get_indexer([pd.Timestamp(day).tz_convert("UTC") if pd.Timestamp(day).tzinfo
                                         else pd.Timestamp(day).tz_localize("UTC")])[0]
    if pos < 0:
        raise ValueError(f"No daily candle starting {day} in this data.")
    return pd.Timestamp(int(history.ends[pos]), tz="UTC")


def earlier_from(run, kind: str, asset_id: str):
    """earlier(day) for evaluate_set: the asset (and its pinned lines) reconstructed at an earlier daily close."""
    def earlier(day):
        t = _cutoff(run, kind, asset_id, day)
        return run.context(kind, asset_id, t), (lambda k, i: run.context(k, i, t))
    return earlier


def run_now(doc: dict, assets: list[tuple[str, str, str]], *, live_context, market_context=None,
            replay=None, progress=None, earlier_run=None) -> list[dict]:
    """Evaluate `doc` on each (kind, id, name). Live when `replay` is None; otherwise `replay` is
    (ReplayRun, as_of) and each asset is reconstructed at that moment (one replay step for all assets).
    Sequences read earlier closes as reconstructions: from the replay's run, or in live mode from `earlier_run`
    (without one, a live sequence is undecided)."""
    if not sg.scannable(doc):
        raise ValueError("This Set has no decision, so Prism cannot scan it. Add a decision first.")
    errors = sg.validate_set(doc)
    if errors:
        raise ValueError("This Set is not valid: " + "; ".join(errors[:3]))
    if len(assets) > MAX_ASSETS:
        raise ValueError(f"At most {MAX_ASSETS} assets per run.")
    rows = []
    for n, (kind, asset_id, name) in enumerate(assets):
        if replay is None:
            result = sg.evaluate_set(doc, live_context(kind, asset_id), market_context=market_context,
                                     subject_context=live_context,        # E4: a fixed asset, read live too
                                     earlier=earlier_from(earlier_run, kind, asset_id) if earlier_run else None)
            path = "Live"
        else:
            run, as_of = replay
            try:
                ctx = run.context(kind, asset_id, as_of)
                result = sg.evaluate_set(doc, ctx, data_mode="point_in_time",
                                         market_context=lambda scope: run.context("market", scope.split(":", 1)[1], as_of),
                                         subject_context=lambda k, i: run.context(k, i, as_of),   # same moment T
                                         earlier=earlier_from(run, kind, asset_id))
            except Exception as exc:   # a refused reconstruction is reported for that asset only
                result = {"status": "unsupported", "reason": str(exc)[:200]}
            path = f"Reconstruction as of {pd.Timestamp(as_of).strftime('%d %b %Y %H:%M')} UTC"
        rows.append({**row(name, result, path), "kind": kind, "id": asset_id})
        if progress:
            progress(n + 1, len(assets))
    return rows


def table(doc: dict, rows: list[dict]) -> pd.DataFrame:
    heads = columns(doc)
    records = []
    for r in rows:
        rec = {"Asset": r["asset"]}
        for path, head in heads:
            rec[head] = r["lines"].get(path, "—")
        rec["Answer"] = f"{ANSWER_ICON[r['answer']]} {ANSWER_TEXT[r['answer']]}"
        rec["How sure"] = r["how_sure"]
        rec["Why"] = r["reason"]
        rec["Data available"] = r["available"] + (f" ({r['available_detail']})"
                                                  if r["available"] not in ("Complete", "—") and r["available_detail"] else "")
        records.append(rec)
    return pd.DataFrame(records)


# ----------------------------------------------------------------------------------------------- the provided library
# Stage A of the agreed plan (docs/design/provided_library.md): Sets built only from existing signals and Groups.
# Descriptions, not forecasts: none has been tested for what follows a Yes.

def _item(key: str, label: str, signal: str, timeframe: str = "1D", **params) -> dict:
    return {"key": key, "label": label, "role": "condition",
            "ref": {"id": signal, "version": 1, "timeframe": timeframe, "params": params}}


def _weekly(alias: str) -> dict:
    """A labelled starter read on weekly candles."""
    doc = labelled_starter(alias)
    doc["name"] = doc["name"].replace("(with labels)", "(weekly, with labels)")
    for m in doc["members"]:
        m["ref"]["timeframe"] = "1W"
        m["key"] = m["key"] + "_w"
    return doc


def _pinned(key: str, alias: str, kind: str, asset_id: str) -> dict:
    g = _group(key, alias)
    g["subject"] = {"kind": kind, "id": asset_id}
    return g


def _breakout_group() -> dict:
    """Recent structure breaks: +1 when the only breaks in the last 3 daily candles were upward, -1 downward.
    Set rules can't say "within N candles" yet, so the recency lives in this Group's confirmation."""
    return {
        "schema": "angstrom.group/1", "name": "Recent structure break", "lineage_version": 3,
        "question": "Did price close through recent structure in the last 3 daily candles, and which way?",
        "score": {"method": "weighted_mean", "range": [-1, 1], "min_coverage": {"num": 1, "den": 1},
                  "meaning": "+1: only upward breaks recently; -1: only downward; 0: none or both."},
        "members": [{"key": "breaks", "label": "Daily structure breaks", "role": "score", "category": "structure",
                     "ref": {"id": "structure.breaks", "version": 1, "timeframe": "1D", "params": {}},
                     "weight": 1, "when_unavailable": "exclude",
                     "transform": {"kind": "events", "version": 1, "up_kinds": ["BOS", "CHoCH", "break"],
                                   "down_kinds": ["BOS", "CHoCH", "break"], "within_candles": 3}}],
        "conditions": [{"key": "recent_up", "label": "An upward break in the last 3 daily candles",
                        "kind": "confirmation",
                        "rule": {"member": "breaks", "events": {"direction": "bullish", "within_candles": 3}}}],
    }


def provided_groups() -> dict[str, tuple[str, dict]]:
    """Every Group a provided Set uses, as a provided Group in the database (starter alias -> (name shown, body)),
    so each provided Set is built only from parts a user can find, look at and copy (sql/2026-11-15_provided_groups.sql,
    written by provided_groups_sql.py). The bodies are exactly what the provided Sets embed."""
    return {
        "starter:trend": ("Trend", labelled_starter("starter:trend")),
        "starter:stretch": ("Stretch", labelled_starter("starter:stretch")),
        "starter:flow": ("Flow", labelled_starter("starter:flow")),
        "starter:trend-weekly": ("Trend (weekly)", _weekly("starter:trend")),
        "starter:breakout": ("Recent structure break", _breakout_group()),
    }


def library_sets() -> dict[str, dict]:
    base = {"schema": "angstrom.set/1", "lineage_version": 3, "score": None, "market_context": []}
    weekly = _weekly("starter:trend")
    out = {
        "demo:alignment": {
            **base, "name": "Trend alignment",
            "purpose": "The daily and the weekly Trend are both Bullish: the shorter and the longer view agree.",
            "groups": [_group("trend", "starter:trend"),
                       {"key": "trend_w", "snapshot": weekly,
                        "provenance": {"source_config": "starter:trend", "note": "the Trend starter on weekly candles",
                                       "content_sha256": sg.content_sha256(weekly)}}],
            "standalone": [],
            "decision": {"version": 1, "rule": {"all": [{"group": "trend", "outcome": {"eq": "bullish"}},
                                                        {"group": "trend_w", "outcome": {"eq": "bullish"}}]}}},
        "demo:breakout": {
            **base, "name": "Breakout with volume",
            "purpose": "Price closed through recent structure upwards in the last 3 daily candles, and the latest "
                       "candle traded at least 1.5 times its usual volume.",
            "groups": [{"key": "breakout", "snapshot": _breakout_group(),
                        "provenance": {"source_config": "provided", "note": "a recent upward structure break",
                                       "content_sha256": sg.content_sha256(_breakout_group())}}],
            "standalone": [_item("volume", "Relative volume", "volume.relative")],
            "decision": {"version": 1, "rule": {"all": [
                {"group": "breakout", "condition": "recent_up", "state": {"eq": "met"}},
                {"member": "volume", "gte": 1.5}]}}},
        "demo:squeeze": {
            **base, "name": "Volatility squeeze",
            "purpose": "The Bollinger bands are narrower than on 80% of days in the past year: unusually quiet "
                       "trading. It says nothing about which way a later move would go.",
            "groups": [],
            "standalone": [_item("regime", "Regime evidence", "regime.observation", window=252)],
            "decision": {"version": 1, "rule": {"member": "regime", "field": "band_width_percentile", "lte": 20}}},
        "demo:range_low": {
            **base, "name": "Oversold in a range",
            "purpose": "The market is ranging (no clear trend), and RSI is 30 or lower or Stochastic %K is 20 or "
                       "lower: price is near the bottom of its recent swings.",
            "groups": [],
            "standalone": [_item("regime", "Market regime", "regime.state"),
                           _item("rsi", "RSI (14)", "rsi.level"), _item("stoch", "Stochastic %K", "stochastic.level")],
            "decision": {"version": 1, "rule": {"all": [
                {"member": "regime", "eq": "ranging"},
                {"any": [{"member": "rsi", "field": "rsi", "lte": 30},
                         {"member": "stoch", "field": "stoch_k", "lte": 20}]}]}}},
        "demo:near_support": {
            **base, "name": "Near support in a range",
            "purpose": "The market is ranging, and the nearest support zone is within half a typical daily range "
                       "of price.",
            "groups": [],
            "standalone": [_item("regime", "Market regime", "regime.state"),
                           _item("zones", "Support and resistance", "levels.zones")],
            "decision": {"version": 1, "rule": {"all": [
                {"member": "regime", "eq": "ranging"},
                {"member": "zones", "field": "support.0.touches", "exists": True},   # no support zone below: No
                {"member": "zones", "field": "support.0.distance_atr", "lte": 0.5}]}}},
        "demo:btc_filter": {
            **base, "name": "Bitcoin trend filter",
            "purpose": "Bitcoin's own daily Trend is Bullish, whatever asset is scanned. Copy it into your own Sets "
                       "as a market filter.",
            "groups": [_pinned("btc_trend", "starter:trend", "crypto", "bitcoin")], "standalone": [],
            "decision": {"version": 1, "rule": {"group": "btc_trend", "outcome": {"eq": "bullish"}}}},
        "demo:overextended": {
            **base, "name": "Overextended",
            "purpose": "The Stretch is +50 or more: price has run far up within its recent range. A caution "
                       "against chasing, not a signal to sell.",
            "groups": [_group("stretch", "starter:stretch")], "standalone": [],
            "decision": {"version": 1, "rule": {"group": "stretch", "outcome": {"eq": "stretched_up"}}}},
    }
    return out
