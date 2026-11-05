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
    return {"demo:agree": agree, "demo:entry": entry}


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
    return {"asset": asset_name, "answer": decision["answer"], "how_sure": how_sure, "reason": text,
            "available": available, "available_detail": detail, "lines": lines, "path": path}


def columns(doc: dict) -> list[tuple[str, str]]:
    """(line path, header) for each decision line, in the rule's order, worded as the decision words them."""
    return list(_walk(doc["decision"]["rule"], "decision.rule"))


def _walk(rule: dict, path: str):
    from signal_groups.decision import _choice_text, _num_text

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

def run_now(doc: dict, assets: list[tuple[str, str, str]], *, live_context, market_context=None,
            replay=None, progress=None) -> list[dict]:
    """Evaluate `doc` on each (kind, id, name). Live when `replay` is None; otherwise `replay` is
    (ReplayRun, as_of) and each asset is reconstructed at that moment (one replay step for all assets)."""
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
            result = sg.evaluate_set(doc, live_context(kind, asset_id), market_context=market_context)
            path = "Live"
        else:
            run, as_of = replay
            try:
                ctx = run.context(kind, asset_id, as_of)
                result = sg.evaluate_set(doc, ctx, data_mode="point_in_time",
                                         market_context=lambda scope: run.context("market", scope.split(":", 1)[1], as_of))
            except Exception as exc:   # a refused reconstruction is reported for that asset only
                result = {"status": "unsupported", "reason": str(exc)[:200]}
            path = f"Reconstruction as of {pd.Timestamp(as_of).strftime('%d %b %Y %H:%M')} UTC"
        rows.append(row(name, result, path))
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
