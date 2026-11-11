"""
Lattice Group editor: the logic behind the drag-and-drop screen (docs/design/lattice_prism.md §7, build stage 4).

The browser component only draws and sends back a simple editor model. Everything that decides anything happens
here, with the engine's own validator: turning the model into an `angstrom.group/1` document, the blocks and
warnings, the auto-written description, and turning a saved Group back into a model.

Editor model:
    {"name": str, "question": str,
     "members": [{"key", "id", "version", "timeframe", "role"}],
     "rules": [{"id", "label", "joiner": "all" | "any",
                "clauses": [{"operand": "score" | "<member key>:<field>", "op": ..., "value": str}]}],
     "otherwise": {"id", "label"}}

Ops: "gte" (is at least), "lte" (is at most) for numbers; "yes", "no" for yes/no fields; "is", "is_not" for labels.
"""

from __future__ import annotations

import copy
import re

import signal_groups as sg
import signal_library as sl
from signal_groups.units import score_from_display, score_to_display
from signal_library import fields

LINEAGE = 3
ROLES = ("score", "condition", "levels", "context")
ROLE_HINT = {
    "score": "Counts towards the Group score (−100 to +100), using the signal's standard score.",
    "condition": "Used only in the rules, not in the score.",
    "levels": "Supplies price levels (support, resistance) for later strategies.",
    "context": "Shown alongside the result, but changes nothing.",
}
CATEGORY = {"trend": "Trend", "momentum": "Momentum", "regime": "Regime", "structure": "Structure",
            "volume": "Volume", "sentiment": "Sentiment"}
CATEGORY_ICON = {"trend": "trend", "momentum": "momentum", "regime": "regime", "structure": "structure",
                 "volume": "volume", "sentiment": "sentiment"}
DIRECTION_MAP = {"up": 1, "down": -1, "mixed": 0}
OPS = {"gte": "is at least", "lte": "is at most", "yes": "is yes", "no": "is no", "is": "is", "is_not": "is not",
       "exists": "has a value"}     # "exists": there is one (for example a support zone at all)
TF_WORDS = {"15m": "15-minute", "30m": "30-minute", "1h": "hourly", "4h": "4-hour", "12h": "12-hour", "1D": "daily", "1W": "weekly"}
SUGGESTED_LABELS = [("bullish", "Bullish"), ("bearish", "Bearish"), ("stretched_up", "Stretched up"),
                    ("stretched_down", "Stretched down"), ("buying", "Buying"), ("selling", "Selling")]


# ----------------------------------------------------------------------------------------------- catalogue

def _usable(definition) -> bool:
    return definition.scope == "asset" and fields.described(definition.key)


def catalogue() -> list[dict]:
    """Every signal the editor offers, with what the screen needs to show and check it."""
    out = []
    for d in sl.REGISTRY.latest():
        if not _usable(d):
            continue
        table = fields.FIELDS[d.key]
        operands = []
        for path, desc in table.items():
            if desc["type"] in (fields.EVENTS, fields.OTHER):
                continue
            label = path.replace("_", " ") if path else "value"
            if "*" in path:                       # a list: offer its first item ("support.0" = the nearest support)
                head, _, rest = path.partition(".*.")
                path, label = path.replace("*", "0"), f"nearest {head} · {rest.replace('_', ' ')}"
            operands.append({"field": path, "type": desc["type"], "label": label, "scale": fields.scale_text(desc),
                             "labels": desc.get("labels") or [], "range": desc.get("range")})
        badge = ("History from Nov 2026" if "sentiment" in d.requires else "")
        out.append({
            "id": d.id, "version": d.version, "name": d.name, "category": d.category,
            "category_label": CATEGORY.get(d.category, d.category.title()), "icon": CATEGORY_ICON.get(d.category, "trend"),
            "timeframes": list(d.timeframes), "hint": (d.interpretation or d.calculation or "")[:220],
            "badge": badge, "can_score": _score_transform(d.key) is not None, "operands": operands,
            # Settings a person may change (such as an EMA's length): shown on the signal's card in the editors.
            "params": {name: {"default": p.default, "kind": p.kind, "min": p.minimum, "max": p.maximum,
                              "choices": list(p.choices), "doc": p.doc} for name, p in d.params.items()},
        })
    order = list(CATEGORY)
    return sorted(out, key=lambda s: (order.index(s["category"]) if s["category"] in order else 99, s["name"]))


def _score_transform(signal_key: str) -> dict | None:
    if fields.field(signal_key, "standard_score"):
        return {"kind": "clip", "version": 1, "field": "standard_score", "low": -1, "high": 1}
    table = fields.FIELDS.get(signal_key) or {}
    for path in [""] + [p for p in table if p and "*" not in p]:
        desc = table.get(path)
        if desc and desc["type"] == fields.LABEL and set(desc.get("labels") or []) == set(DIRECTION_MAP):
            transform = {"kind": "map", "version": 1, "map": dict(DIRECTION_MAP)}
            if path:
                transform = {"kind": "map", "version": 1, "field": path, "map": dict(DIRECTION_MAP)}
            return transform
    return None


def new_member_key(model: dict, signal_id: str, timeframe: str) -> str:
    base = re.sub(r"[^a-z0-9_]", "_", signal_id.split(".")[0] + "_" + signal_id.split(".")[-1])[:30]
    base = f"{base}_{timeframe.lower()}"
    taken = {m["key"] for m in model.get("members") or []}
    key, n = base, 2
    while key in taken:
        key, n = f"{base}_{n}", n + 1
    return key


def empty_model() -> dict:
    return {"name": "My Group", "question": "", "members": [], "rules": [], "conditions": [],
            "otherwise": {"id": "neutral", "label": "Neutral"}}


# ----------------------------------------------------------------------------------------------- model -> document

def _signal_key(member: dict) -> str:
    return f"{member['id']}@{member['version']}"


def _number(text):
    try:
        return float(str(text).strip().replace("−", "-").replace("+", ""))
    except (TypeError, ValueError):
        return None


def _predicate(clause: dict) -> dict:
    op, value = clause.get("op"), clause.get("value")
    if clause.get("operand") == "score":
        try:
            return {"score": {op: score_from_display(value)}}
        except ValueError:
            number = _number(value)                      # out of scale: let the validator's range check refuse it
            return {"score": {op: number / 100 if number is not None else value}}
    key, _, field = str(clause.get("operand") or "").partition(":")
    pred = {"member": key}
    if field:
        pred["field"] = field
    if op in ("gte", "lte"):
        number = _number(value)
        pred[op] = number if number is not None else value
    elif op in ("yes", "no"):
        pred["eq"] = op == "yes"
    elif op == "is":
        pred["eq"] = value
    elif op == "is_not":
        return {"not": {**pred, "eq": value}}
    elif op == "exists":
        pred["exists"] = True
    else:
        pred["eq"] = value
    return pred


def _when(rule: dict) -> dict:
    preds = [_predicate(c) for c in rule.get("clauses") or []]
    if len(preds) == 1:
        return preds[0]
    return {rule.get("joiner") or "all": preds}


def to_document(model: dict) -> dict:
    members = []
    score_keys = []
    for m in model.get("members") or []:
        member = {"key": m["key"], "label": m.get("label") or display_name(m),
                  "ref": {"id": m["id"], "version": m["version"], "timeframe": m["timeframe"],
                          "params": dict(m.get("params") or {})},
                  "role": m["role"], "category": _category_of(m["id"])}
        if m["role"] == "score":
            transform = m.get("transform") or _score_transform(_signal_key(m))   # a saved transform stays as saved
            member.update({"weight": 1, "when_unavailable": "exclude",
                           "transform": transform or {"kind": "clip", "version": 1, "field": "standard_score",
                                                      "low": -1, "high": 1}})
            score_keys.append(m["key"])
        members.append(member)
    doc = {"schema": "angstrom.group/1", "name": (model.get("name") or "").strip() or "Untitled Group",
           "question": (model.get("question") or "").strip() or "What do these readings say together?",
           "lineage_version": LINEAGE, "members": members,
           "conditions": [{"key": c["key"], "label": c["label"], "kind": c["kind"], "rule": _when(c)}
                          for c in model.get("conditions") or [] if c.get("clauses")],
           "notes": "Built in the Lattice editor."}
    doc["score"] = {"method": "weighted_mean", "range": [-1, 1],
                    "meaning": "The average of the score members' standard scores (−1 to +1), shown as −100 to +100. "
                               "Not a forecast.",
                    "min_coverage": {"num": 1, "den": max(1, len(score_keys))}} if score_keys else None
    rules = [r for r in model.get("rules") or [] if r.get("clauses")]
    if rules:
        doc["outcomes"] = {"version": 1, "rules": [{"id": r["id"], "label": r["label"], "when": _when(r)} for r in rules],
                           "otherwise": dict(model.get("otherwise") or {"id": "neutral", "label": "Neutral"})}
    return doc


def _name_of(signal_id: str) -> str:
    try:
        return sl.REGISTRY.get(signal_id).name
    except KeyError:
        return signal_id


# Short names for signals whose settings are the point (an EMA 20 is not an EMA 50), used in lines and descriptions.
SHORT = {
    "ma.line": lambda p: f"{p['kind']} {p['length']}",
    "ma.pair": lambda p: f"{p['kind']} {p['fast']} vs {p['slow']}",
    "osc.wavetrend": lambda p: f"WaveTrend {p['channel']}/{p['average']}",
    "flow.money": lambda p: f"Money flow {p['period']}",
    "osc.stoch_ohlc4": lambda p: f"Stochastic OHLC4 {p['length']}",
    "divergence.mtf": lambda p: f"Divergence ({p['set']}, {p['oscillator']})",
    "candle.shape": lambda p: "Candle",
    "volatility.atr_trend": lambda p: f"ATR {p['length']} vs its {p['average']}-candle average",
}


def display_name(member: dict) -> str:
    """A member's name with its settings where they matter: "EMA 20", "EMA 20 vs 50"."""
    sid = member.get("id")
    if sid in SHORT:
        try:
            d = sl.REGISTRY.get(sid, member.get("version") or 1)
            params = {k: p.default for k, p in d.params.items()} | dict(member.get("params") or {})
            return SHORT[sid](params)
        except (KeyError, TypeError):
            pass
    return _name_of(sid)


def _category_of(signal_id: str) -> str:
    try:
        return sl.REGISTRY.get(signal_id).category
    except KeyError:
        return ""


# ----------------------------------------------------------------------------------------------- document -> model

def from_document(doc: dict) -> tuple[dict | None, str | None]:
    """(model, None) or (None, reason) when the Group uses something the editor cannot show yet."""
    conditions = []
    for c in doc.get("conditions") or []:
        parsed = _clauses(c["rule"])
        if parsed is None:
            return None, f"The {c['kind']} {c.get('label') or c['key']!r} is more complex than the editor can show yet."
        joiner, clauses = parsed
        conditions.append({"key": c["key"], "label": c.get("label") or c["key"], "kind": c["kind"], "joiner": joiner,
                           "clauses": clauses})
    members = []
    for m in doc.get("members") or []:
        ref = m["ref"]
        if not fields.described(f"{ref['id']}@{ref['version']}"):
            return None, f"{m['key']} ({ref['id']}) is not in the editor's signal list yet."
        if m["role"] == "score" and m.get("weight") not in (1, 1.0):
            return None, f"{m['key']} has weight {m.get('weight')}; the editor uses equal weights."
        members.append({"key": m["key"], "id": ref["id"], "version": ref["version"], "timeframe": ref["timeframe"],
                        "role": m["role"], "label": m.get("label"),
                        **({"params": dict(ref["params"])} if ref.get("params") else {}),
                        **({"transform": dict(m["transform"])} if m["role"] == "score" and m.get("transform") else {})})
    model = {"name": doc.get("name") or "", "question": doc.get("question") or "", "members": members, "rules": [],
             "conditions": conditions, "otherwise": {"id": "neutral", "label": "Neutral"}}
    spec = doc.get("outcomes")
    if spec:
        model["otherwise"] = dict(spec["otherwise"])
        for r in spec["rules"]:
            parsed = _clauses(r["when"])
            if parsed is None:
                return None, f"Rule {r['label']!r} is more complex than the editor can show yet."
            joiner, clauses = parsed
            model["rules"].append({"id": r["id"], "label": r["label"], "joiner": joiner, "clauses": clauses})
    return model, None


def _clause(pred: dict) -> dict | None:
    if "not" in pred:
        inner = _clause(pred["not"])
        return {**inner, "op": "is_not"} if inner and inner["op"] == "is" else None
    if "score" in pred:
        (op, v), = pred["score"].items()
        return {"operand": "score", "op": op, "value": score_to_display(v)} if op in ("gte", "lte") else None
    if "member" not in pred or "events" in pred:
        return None
    operand = pred["member"] + (f":{pred['field']}" if pred.get("field") else ":")
    for op in ("gte", "lte"):
        if op in pred:
            return {"operand": operand, "op": op, "value": f"{pred[op]:g}"}
    if pred.get("exists") is True:
        return {"operand": operand, "op": "exists", "value": ""}
    if "eq" in pred:
        if isinstance(pred["eq"], bool):
            return {"operand": operand, "op": "yes" if pred["eq"] else "no", "value": ""}
        return {"operand": operand, "op": "is", "value": pred["eq"]}
    return None


def _clauses(when: dict):
    for joiner in ("all", "any"):
        if joiner in when:
            parts = [_clause(p) for p in when[joiner]]
            return None if None in parts else (joiner, parts)
    single = _clause(when)
    return None if single is None else ("all", [single])


# ----------------------------------------------------------------------------------------------- checks

def checks(model: dict) -> dict:
    """{"blocks": [...], "warnings": [...]} in plain words. Blocks stop saving; warnings do not."""
    blocks, warns = [], []
    members = model.get("members") or []
    if not members:
        blocks.append("Add at least one signal.")
    score = [m for m in members if m["role"] == "score"]
    for m in score:
        if not m.get("transform") and _score_transform(_signal_key(m)) is None:
            blocks.append(f"{_name_of(m['id'])} has no standard score, so it cannot be a Score member. "
                          "Use it as a Condition.")
    if members and not score and not model.get("rules"):
        blocks.append("Add a Score member, or a rule, so the Group says something.")
    rule_ids = [r["id"] for r in model.get("rules") or []]
    if len(set(rule_ids)) != len(rule_ids):
        blocks.append("Two rules use the same label; each label must be different.")
    kinds = {o["key"]: o["type"] for o in operands(model)}
    keys = [c["key"] for c in model.get("conditions") or []]
    if len(set(keys)) != len(keys):
        blocks.append("Two confirmations or vetoes have the same name; each must be different.")
    for c in model.get("conditions") or []:
        if not c.get("clauses"):
            blocks.append(f"The {c['kind']} {c['label']!r} has no condition yet.")
        for cl in c.get("clauses") or []:
            if cl.get("operand") not in kinds:
                blocks.append(f"The {c['kind']} {c['label']!r} uses a reading that is no longer in the Group.")
            elif kinds[cl["operand"]] == fields.NUMBER and cl.get("op") in ("gte", "lte") and _number(cl.get("value")) is None:
                blocks.append(f"The {c['kind']} {c['label']!r}: {cl.get('value')!r} is not a number.")
    for i, r in enumerate(model.get("rules") or []):
        if not r.get("clauses"):
            blocks.append(f"Rule {i + 1} ({r['label']}) has no condition yet.")
        for c in r.get("clauses") or []:
            if c.get("operand") not in kinds:
                blocks.append(f"Rule {i + 1} ({r['label']}) uses a reading that is no longer in the Group.")
            elif kinds[c["operand"]] == fields.NUMBER and c.get("op") in ("gte", "lte") and _number(c.get("value")) is None:
                blocks.append(f"Rule {i + 1} ({r['label']}): {c.get('value')!r} is not a number.")

    doc = to_document(model)
    if not blocks:
        names = {m["key"]: f"{display_name(m)} ({m['timeframe']})" for m in members}
        for e in sg.validate_group(doc):
            blocks.append(_plain(e, names))

    used: dict = {}
    for i, r in enumerate(model.get("rules") or []):
        for c in r.get("clauses") or []:
            key = str(c.get("operand") or "").partition(":")[0]
            if key != "score":
                used.setdefault(key, set()).add(i + 1)
    in_checks: set = set()
    for c in model.get("conditions") or []:
        for cl in c.get("clauses") or []:
            key = str(cl.get("operand") or "").partition(":")[0]
            if key != "score":
                in_checks.add(key)
    if any(c["kind"] == "veto" for c in model.get("conditions") or []) and model.get("rules"):
        warns.append("When a veto fires, every label becomes Vetoed; when a veto cannot be checked, labels are marked "
                     "qualified and a Set treats them as uncertain.")
    by_cat: dict = {}
    for m in score:
        by_cat.setdefault(_category_of(m["id"]), []).append(_name_of(m["id"]))
    for cat, names in by_cat.items():
        names = sorted(set(names))
        if len(names) > 1:
            listed = ", ".join(names[:-1]) + " and " + names[-1]
            verb = "both measure" if len(names) == 2 else "all measure"
            warns.append(f"{listed} {verb} {CATEGORY.get(cat, cat).lower()}. The score may count the same move "
                         f"{'twice' if len(names) == 2 else 'several times'}.")
    if len(score) >= 3 and all("candles" in sl.REGISTRY.get(m["id"]).requires for m in score):
        warns.append("Every score member comes from price and volume alone, so they will often agree.")
    tfs = sorted({m["timeframe"] for m in members if "candles" in sl.REGISTRY.get(m["id"]).requires})
    if len(tfs) > 1:
        warns.append(f"Members use different timeframes ({', '.join(tfs)}). Each uses its own last closed candle, so "
                     "they update at different times.")
    for m in members:
        name = display_name(m)
        if m["role"] == "condition" and m["key"] not in used and m["key"] not in in_checks:
            warns.append(f"{name} is a Condition member, but no rule uses it, so it changes nothing.")
        if m["role"] == "score" and m["key"] in used:
            warns.append(f"{name} already counts in the score and is tested again in rule "
                         f"{', '.join(map(str, sorted(used[m['key']])))}. That leans harder on the same evidence; it is "
                         "not independent confirmation.")
        if m["role"] == "context" and (m["key"] in used or m["key"] in in_checks):
            blocks.append(f"{name} is marked Context, so rules cannot use it. Make it a Condition.")
        if "sentiment" in sl.REGISTRY.get(m["id"]).requires:
            warns.append(f"{name}: sentiment history starts in November 2026, so earlier dates will show it as missing.")
    rules = model.get("rules") or []
    for i, r in enumerate(rules):
        if r.get("joiner") == "any" and len(r.get("clauses") or []) > 1 and len(rules) > 1:
            warns.append(f"Rule {i + 1} uses OR, so it can be true at the same time as another rule. The higher rule "
                         "wins; reorder with the arrows if that is wrong.")
    return {"blocks": list(dict.fromkeys(blocks)), "warnings": list(dict.fromkeys(warns))}


def _plain(error: str, names: dict | None = None) -> str:
    """Validator messages start with a path and use member keys; the editor shows the sentence with names."""
    text = re.sub(r"^outcomes\.rules\[(\d+)\]\.when[^:]*:\s*", lambda m: f"Rule {int(m.group(1)) + 1}: ", error)
    text = re.sub(r"^outcomes\.(rules\[(\d+)\]|otherwise)[^:]*:\s*", "Labels: ", text)
    text = text.replace("outside the Group score range -1 to 1 (stored scale; +30 on screen is 0.30)",
                        "outside the Group score scale, −100 to +100")
    for key, name in sorted((names or {}).items(), key=lambda kv: -len(kv[0])):
        text = re.sub(rf"\b{re.escape(key)}\.standard_score\b", f"{name} standard score", text)
        text = re.sub(rf"\b{re.escape(key)}\.(\w+)", lambda m, n=name: f"{n} {m.group(1).replace('_', ' ')}", text)
        text = re.sub(rf"\b{re.escape(key)}\b", name, text)
    return text[:1].upper() + text[1:]


# ----------------------------------------------------------------------------------------------- description

def _clause_text(c: dict, members: dict) -> str:
    if c.get("operand") == "score":
        return f"the Group score {OPS.get(c['op'], c['op'])} {c.get('value')}"
    key, _, field = str(c.get("operand") or "").partition(":")
    m = members.get(key)
    name = display_name(m) if m else key
    if m and m["timeframe"]:
        name += f" ({m['timeframe']})"
    if field and field != "standard_score":
        name += f" {field.replace('_', ' ')}"
    elif field == "standard_score":
        name += " standard score"
    if c["op"] in ("yes", "no", "exists"):
        return f"{name} {OPS[c['op']]}"
    return f"{name} {OPS.get(c['op'], c['op'])} {c.get('value')}"


def describe(model: dict) -> str:
    members = {m["key"]: m for m in model.get("members") or []}
    score = [m for m in members.values() if m["role"] == "score"]
    name = (model.get("name") or "").strip() or "This Group"
    parts = []
    if score:
        listed = ", ".join(f"{display_name(m)} ({m['timeframe']})" for m in score)
        parts.append(f"{name} averages {len(score)} reading{'s' if len(score) > 1 else ''} ({listed}) into a score "
                     "from −100 to +100.")
    else:
        parts.append(f"{name} has no score.")
    rules = [r for r in model.get("rules") or [] if r.get("clauses")]
    for i, r in enumerate(rules):
        joint = " and " if r.get("joiner") != "any" else " or "
        parts.append(f"Rule {i + 1}: {r['label']} when " + joint.join(_clause_text(c, members) for c in r["clauses"]) + ".")
    if rules:
        parts.append(f"If a rule cannot be checked, the label is Unknown. If none match, "
                     f"{(model.get('otherwise') or {}).get('label', 'Neutral')}.")
    for c in model.get("conditions") or []:
        if c.get("clauses"):
            joint = " and " if c.get("joiner") != "any" else " or "
            what = "Veto" if c["kind"] == "veto" else "Confirmation"
            parts.append(f"{what} “{c['label']}”: " + joint.join(_clause_text(x, members) for x in c["clauses"]) + ".")
    if score:
        parts.append(f"A score is given when at least 1 of its {len(score)} readings is available.")
    return " ".join(parts)


def operands(model: dict) -> list[dict]:
    """What a rule can test, with its type and scale, for the screen."""
    cat = {(s["id"], s["version"]): s for s in catalogue()}
    out = [{"key": "score", "label": "Group score", "type": fields.NUMBER, "scale": "−100 to +100", "labels": []}]
    for m in model.get("members") or []:
        if m["role"] == "context":
            continue
        s = cat.get((m["id"], m["version"]))
        if not s:
            continue
        for o in s["operands"]:
            kind = "standard score" if o["field"] == "standard_score" else o["label"]
            out.append({"key": f"{m['key']}:{o['field']}", "label": f"{s['name']} ({m['timeframe']}) · {kind}",
                        "type": o["type"], "scale": o["scale"], "labels": o["labels"]})
    return out


def member_tag(member: dict) -> str:
    """What a member is read from, generated from its timeframe and source."""
    requires = sl.REGISTRY.get(member["id"]).requires
    if "sentiment" in requires:
        return "Latest score at the time"
    return f"{member['timeframe']} · last closed candle" + (" · custom settings" if member.get("params") else "")


def state_for_screen(model: dict) -> dict:
    """Everything the component draws: the model, what rules can test, checks and description."""
    found = checks(model)
    return {"model": copy.deepcopy(model), "operands": operands(model), "checks": found,
            "member_tags": {m["key"]: member_tag(m) for m in model.get("members") or []},
            "description": describe(model), "can_save": not found["blocks"],
            "returns": {"score": any(m["role"] == "score" for m in model.get("members") or []),
                        "labels": [r["label"] for r in model.get("rules") or []]
                        + [(model.get("otherwise") or {}).get("label", "Neutral")]}}


# ----------------------------------------------------------------------------------------------- input from the screen

MAX_MEMBERS, MAX_RULES, MAX_CLAUSES = 30, 10, 10
_ID = re.compile(r"^[a-z][a-z0-9_]{0,23}$")


def clean_model(raw) -> dict:
    """The model sent by the browser, reduced to known keys, known signals, known roles and timeframes, and limits.
    Anything else is dropped, so the screen can never hand Python something the editor does not offer."""
    raw = raw if isinstance(raw, dict) else {}
    by_id = {s["id"]: s for s in catalogue()}
    model = {"name": str(raw.get("name") or "")[:80], "question": str(raw.get("question") or "")[:200],
             "members": [], "rules": [], "otherwise": {"id": "neutral", "label": "Neutral"}}
    seen = set()
    for m in (raw.get("members") or [])[:MAX_MEMBERS]:
        if not isinstance(m, dict) or m.get("id") not in by_id:
            continue
        s = by_id[m["id"]]
        tf = m.get("timeframe") if m.get("timeframe") in s["timeframes"] else ("1D" if "1D" in s["timeframes"]
                                                                              else s["timeframes"][0])
        key = str(m.get("key") or "")
        if not re.match(r"^[a-z0-9_]{1,40}$", key) or key in seen:
            key = new_member_key(model, m["id"], tf)
        seen.add(key)
        role = m.get("role") if m.get("role") in ROLES else ("score" if s["can_score"] else "condition")
        member = {"key": key, "id": s["id"], "version": s["version"], "timeframe": tf, "role": role}
        params = m.get("params")
        if isinstance(params, dict) and params:
            try:   # settings saved with the Group are kept as they are, if the signal accepts them
                sl.SignalRef.make(sl.REGISTRY.get(s["id"], s["version"]), tf, **params)
                member["params"] = dict(params)
            except (ValueError, TypeError, KeyError):
                pass
        if m.get("label"):
            member["label"] = str(m["label"])[:80]
        transform = m.get("transform")
        if role == "score" and isinstance(transform, dict) and not sg.transforms.config_errors(transform):
            member["transform"] = transform
        model["members"].append(member)
    for r in (raw.get("rules") or [])[:MAX_RULES]:
        if not isinstance(r, dict):
            continue
        label = str(r.get("label") or "").strip()[:24] or "Label"
        rid = str(r.get("id") or "")
        if not _ID.match(rid):
            rid = (re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "label")[:24]
            rid = rid if rid[0].isalpha() else f"l_{rid}"[:24]
        clauses = []
        for c in (r.get("clauses") or [])[:MAX_CLAUSES]:
            if isinstance(c, dict) and c.get("op") in OPS:
                clauses.append({"operand": str(c.get("operand") or "score")[:80], "op": c["op"],
                                "value": str(c.get("value") if c.get("value") is not None else "")[:40]})
        model["rules"].append({"id": rid, "label": label, "joiner": "any" if r.get("joiner") == "any" else "all",
                               "clauses": clauses})
    model["conditions"] = []
    ckeys: set = set()
    for c in (raw.get("conditions") or [])[:MAX_RULES]:
        if not isinstance(c, dict):
            continue
        label = str(c.get("label") or "").strip()[:200] or "Check"
        key = str(c.get("key") or "")
        if not re.match(r"^[a-z0-9_]{1,40}$", key) or key in ckeys:
            key = (re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "check")[:36]
            base, n = key, 2
            while key in ckeys:
                key, n = f"{base}_{n}", n + 1
        ckeys.add(key)
        clauses = [{"operand": str(x.get("operand") or "score")[:80], "op": x["op"],
                    "value": str(x.get("value") if x.get("value") is not None else "")[:40]}
                   for x in (c.get("clauses") or [])[:MAX_CLAUSES] if isinstance(x, dict) and x.get("op") in OPS]
        model["conditions"].append({"key": key, "label": label, "kind": "veto" if c.get("kind") == "veto" else "confirmation",
                                    "joiner": "any" if c.get("joiner") == "any" else "all", "clauses": clauses})
    other = raw.get("otherwise") if isinstance(raw.get("otherwise"), dict) else {}
    olabel = str(other.get("label") or "Neutral").strip()[:24] or "Neutral"
    oid = str(other.get("id") or "")
    if not _ID.match(oid):
        oid = (re.sub(r"[^a-z0-9]+", "_", olabel.lower()).strip("_") or "neutral")[:24]
        oid = oid if oid[0].isalpha() else f"l_{oid}"[:24]
    model["otherwise"] = {"id": oid, "label": olabel}
    return model
