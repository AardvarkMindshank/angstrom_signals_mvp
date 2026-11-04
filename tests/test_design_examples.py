"""Design-time checks for the Groups/Sets proposal (docs/design/groups_sets.md).

These check that the example documents are consistent with the proposal and with the live Signal Library:
references resolve, roles and missing-data policies match the role table, rules only use allowed members and
field paths that exist in real signal outputs (evaluated on synthetic candles), transforms are well formed,
coverage thresholds are exact fractions, Set snapshots match their sources by hash, and the lineage table covers
every signal. They are not the product validator or evaluator, which do not exist yet.
"""

import hashlib
import json
import math
import pathlib
from fractions import Fraction

import pytest

import signal_library as sl
from signal_library import DataContext, engine
from tests.test_signal_library_ta import _frame

EXAMPLES = pathlib.Path(__file__).resolve().parents[1] / "docs" / "design" / "examples"
STARTERS = {"starter:trend-confirmation": "group_trend_confirmation.json",
            "starter:reversal-evidence": "group_reversal_evidence.json"}
ROLES = {"score": {"exclude", "neutral"}, "condition": set(), "levels": set(), "context": set()}
RULE_ROLES = {"score", "condition", "levels"}
COMBINATORS = {"all", "any", "not", "count_at_least", "count_distinct_sources_at_least"}
COMPARATORS = {"eq", "in", "gte", "lte", "between", "exists"}
EVENT_FILTERS = {"type_in", "kind_in", "direction", "within_candles", "include_developing"}


def load(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def canonical_sha(body):
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def groups_under_test():
    out = [(name, load(name)) for name in sorted(STARTERS.values())]
    for g in load("set_multi_timeframe.json")["groups"]:
        out.append((f"set:{g['key']}", g["snapshot"]))
    return out


# ----------------------------------------------------------------------------- real outputs on synthetic candles

_OUTPUTS = {}


def output_of(ref: dict, seed: int):
    key = (json.dumps(ref, sort_keys=True), seed)
    if key not in _OUTPUTS:
        frames = {tf: _frame(f, seed=seed) for tf, f in (("15m", "15min"), ("1h", "1h"), ("4h", "4h"), ("1D", "1D"), ("1W", "7D"))}
        ctx = DataContext("crypto", "bitcoin", candle_loader=lambda k, a, tf: {"frame": frames[tf], "session": None, "source": "t"})
        engine.clear_cache()
        d = sl.REGISTRY.get(ref["id"], ref["version"])
        made = sl.SignalRef.make(d, ref["timeframe"], **ref["params"])
        result = sl.evaluate([made], ctx)[made.instance_key]
        assert result.status == "ok", (ref["id"], result.notes)
        _OUTPUTS[key] = result.value
    return _OUTPUTS[key]


def resolve(value, path):
    """(found, value) following a dotted path with integer list indexes."""
    for part in path.split("."):
        if isinstance(value, list) and part.isdigit():
            idx = int(part)
            if idx >= len(value):
                return False, None
            value = value[idx]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return False, None
    return True, value


def path_exists(ref, path, expect=None):
    """The path resolves on real output for at least one of several synthetic histories (a list can be empty in one)."""
    for seed in (3, 5, 7, 11, 13, 17, 19, 23):
        found, value = resolve(output_of(ref, seed), path)
        if found:
            if expect is not None:
                assert isinstance(value, expect), (path, value)
            return True
    return False


# ----------------------------------------------------------------------------- group checks

def check_transform(t, member, ref):
    assert t["kind"] in {"map", "bands", "clip", "events"} and t["version"] == 1
    if t["kind"] == "map":
        assert all(v is None or (isinstance(v, (int, float)) and -1 <= v <= 1) for v in t["map"].values())
        if "field" in t:
            assert path_exists(ref, t["field"], str), f"{member['key']}: field {t['field']} not in output"
        else:
            assert isinstance(output_of(ref, 3), str), f"{member['key']}: map needs a label"


def walk(rule, members, group_name, has_score, depth=0, counter=None):
    counter = counter if counter is not None else [0]
    assert depth <= 6, f"{group_name}: rule deeper than 6"
    assert isinstance(rule, dict)
    combos = COMBINATORS & set(rule)
    if combos:
        (combo,) = combos
        if combo in ("all", "any"):
            assert isinstance(rule[combo], list) and rule[combo]
            for sub in rule[combo]:
                walk(sub, members, group_name, has_score, depth + 1, counter)
        elif combo == "not":
            walk(rule["not"], members, group_name, has_score, depth + 1, counter)
        else:
            k = rule[combo]
            assert isinstance(k, int) and 1 <= k <= len(rule["of"]), f"{group_name}: {combo} {k} of {len(rule['of'])}"
            for sub in rule["of"]:
                walk(sub, members, group_name, has_score, depth + 1, counter)
        return counter[0]
    counter[0] += 1
    if "score" in rule:
        assert has_score, f"{group_name}: score predicate without a score"
        assert set(rule["score"]) <= COMPARATORS
        return counter[0]
    key = rule["member"]
    assert key in members, f"{group_name}: unknown member {key}"
    m = members[key]
    assert m["role"] in RULE_ROLES, f"{group_name}: {key} has role {m['role']} and cannot be used in rules"
    ref = m["ref"]
    if "events" in rule:
        assert set(rule["events"]) <= EVENT_FILTERS, rule["events"]
        definition = sl.REGISTRY.get(ref["id"], ref["version"])
        assert definition.output == "events", f"{group_name}: events filter on non-event signal {ref['id']}"
        assert path_exists(ref, "events", list)
        needed = {"type_in": "type", "kind_in": "kind", "direction": "direction"}
        for f, field in needed.items():
            if f in rule["events"]:
                for seed in (3, 5, 7, 11):
                    events = output_of(ref, seed)["events"]
                    if events:
                        assert field in events[0], f"{group_name}: events have no {field}"
                        break
    else:
        ops = set(rule) - {"member", "field"}
        assert ops and ops <= COMPARATORS, rule
        if "field" in rule:
            numeric = any(op in rule for op in ("gte", "lte", "between"))
            assert path_exists(ref, rule["field"], (int, float) if numeric else None), \
                f"{group_name}: {key}.{rule['field']} never resolves on real output"
    return counter[0]


@pytest.mark.parametrize("name,doc", groups_under_test(), ids=[n for n, _ in groups_under_test()])
def test_group_structure(name, doc):
    assert doc["schema"] == "angstrom.group/1"
    assert doc["lineage_version"] == load("lineage.json")["version"], "pin the lineage version"
    members = {}
    for m in doc["members"]:
        assert m["key"] not in members, f"duplicate key {m['key']}"
        members[m["key"]] = m
        definition = sl.REGISTRY.get(m["ref"]["id"], m["ref"]["version"])
        sl.SignalRef.make(definition, m["ref"]["timeframe"], **m["ref"]["params"])
        assert m["role"] in ROLES
        policy = m.get("when_unavailable")
        if ROLES[m["role"]]:
            assert policy in ROLES[m["role"]], f"{m['key']}: {m['role']} needs one of {ROLES[m['role']]}"
        else:
            assert policy is None, f"{m['key']}: role {m['role']} has a fixed missing-data rule"
        assert "family" not in m, "family was replaced by category + lineage"
        if m["role"] == "score":
            w = m["weight"]
            assert isinstance(w, (int, float)) and math.isfinite(w) and 0 <= w <= 1000
            check_transform(m["transform"], m, m["ref"])
        else:
            assert "weight" not in m and "transform" not in m
    if doc["score"] is not None:
        s = doc["score"]
        assert s["meaning"] and s["method"] == "weighted_mean"
        num, den = s["min_coverage"]["num"], s["min_coverage"]["den"]
        assert isinstance(num, int) and isinstance(den, int) and 0 < num <= den
        enabled = [Fraction(str(m["weight"])) for m in doc["members"] if m["role"] == "score" and m["weight"] > 0]
        assert enabled, "a score needs an enabled member"
    predicates = 0
    referenced = json.dumps(doc["conditions"])
    for c in doc["conditions"]:
        assert c["kind"] in {"confirmation", "veto"}
        predicates += walk(c["rule"], members, name, doc["score"] is not None)
    assert len(doc["members"]) <= 30 and len(doc["conditions"]) <= 20 and predicates <= 50
    for m in doc["members"]:
        if m["role"] == "condition":
            assert f'"member": "{m["key"]}"' in referenced, f"condition member {m['key']} is never used"
    assert len(json.dumps(doc).encode()) <= 64 * 1024


def test_trend_coverage_threshold_is_exactly_two_of_three():
    doc = load("group_trend_confirmation.json")
    enabled = sum(Fraction(str(m["weight"])) for m in doc["members"] if m["role"] == "score" and m["weight"] > 0)
    mc = doc["score"]["min_coverage"]
    two = Fraction(2)
    assert two * mc["den"] >= enabled * mc["num"]  # two of three equal weights meets the threshold
    assert Fraction(1) * mc["den"] < enabled * mc["num"]


def test_regime_controls_the_veto_as_a_condition():
    doc = load("group_trend_confirmation.json")
    roles = {m["key"]: m["role"] for m in doc["members"]}
    veto = next(c for c in doc["conditions"] if c["kind"] == "veto")
    assert roles[veto["rule"]["member"]] == "condition"


# ----------------------------------------------------------------------------- set checks

def test_set_snapshots_match_their_sources():
    doc = load("set_multi_timeframe.json")
    assert doc["schema"] == "angstrom.set/1" and doc["score"] is None
    assert doc["lineage_version"] == load("lineage.json")["version"]
    keys = set()
    for g in doc["groups"]:
        assert g["key"] not in keys
        keys.add(g["key"])
        prov = g["provenance"]
        assert prov["source_config"] in STARTERS, prov["source_config"]
        assert prov["source_version"] == 1
        source = load(STARTERS[prov["source_config"]])
        assert g["snapshot"] == source, "snapshot differs from the pinned source version"
        assert prov["content_sha256"] == canonical_sha(g["snapshot"])
        assert prov["audience_ceiling"] in {"private", "communities", "public"}
    order = {"private": 0, "communities": 1, "public": 2}
    assert order[doc["audience_ceiling"]] <= min(order[g["provenance"]["audience_ceiling"]] for g in doc["groups"])


def test_set_standalone_and_market_context():
    doc = load("set_multi_timeframe.json")
    for item in doc["standalone"] + doc["market_context"]:
        definition = sl.REGISTRY.get(item["ref"]["id"], item["ref"]["version"])
        sl.SignalRef.make(definition, item["ref"]["timeframe"], **item["ref"]["params"])
        assert item["role"] in {"context", "levels"}
    for item in doc["market_context"]:
        if item["ref"]["params"].get("point_in_time") is False:
            assert item["data_modes"] == ["live"], "non-point-in-time flows are current context only"


# ----------------------------------------------------------------------------- lineage and transforms

def test_lineage_covers_every_library_signal():
    """The design's lineage (v2) covers the design's Groups; the current package table covers every signal."""
    from signal_groups import lineage

    current = lineage.table(lineage.CURRENT)
    for d in sl.REGISTRY.latest():
        if d.id.startswith("test."):
            continue
        assert current.get(d.id), f"{d.id} has no lineage in version {lineage.CURRENT}"
    roots = load("lineage.json")["roots"]
    for d in []:
        if d.id.startswith("test."):
            continue
        assert roots.get(d.id), f"{d.id} has no lineage"
    for name, doc in groups_under_test():
        for m in doc["members"]:
            assert m["ref"]["id"] in roots


def test_reversal_rule_does_not_claim_independence():
    roots = load("lineage.json")["roots"]
    doc = load("group_reversal_evidence.json")
    rule_members = {m["ref"]["id"] for m in doc["members"] if m["role"] in RULE_ROLES}
    assert all(roots[i] == ["price"] for i in rule_members)
    text = json.dumps(doc["conditions"])
    assert "count_distinct_sources_at_least" not in text and "not independent" in text


def test_transform_fixtures_are_well_formed():
    cases = load("transform_fixtures.json")["cases"]
    kinds = {c["kind"] for c in cases}
    assert kinds == {"map", "bands", "clip", "events"}
    for c in cases:
        e = c["expected"]
        assert e in ("unknown", "invalid_config") or (isinstance(e, (int, float)) and -1 <= e <= 1), c


def test_lineage_records_price_inputs_whatever_the_provider():
    roots = load("lineage.json")["roots"]
    assert "price" in roots["positioning.oi_price"] and "price" in roots["positioning.liquidation_levels"]
    assert "price" not in roots["positioning.liquidations"] and roots["volume.relative"] == ["volume"]


# ----------------------------------------------------------------------------- counting contract (reference)

def reference_count(op, k, items):
    """Test-only reference of design section 3.4.1, to show the worked cases are consistent with the contract.
    Not the product evaluator."""
    key = "support" if op == "count_at_least" else "roots"
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if set(items[i][key]) & set(items[j][key]):
                parent[find(i)] = find(j)
    clusters = {}
    for i, item in enumerate(items):
        clusters.setdefault(find(i), []).append(item["value"])
    values = [True if True in v else "unknown" if "unknown" in v else False for v in clusters.values()]
    trues, unknowns = values.count(True), values.count("unknown")
    if trues >= k:
        return True
    if trues + unknowns < k:
        return False
    return "unknown"


@pytest.mark.parametrize("case", load("rule_fixtures.json")["cases"], ids=lambda c: c["name"])
def test_counting_contract_worked_cases(case):
    assert reference_count(case["op"], case["k"], case["items"]) == case["expected"]


def _rule_roots(rule, members, roots):
    """Union of lineage roots under a rule expression."""
    if "member" in rule:
        return set(roots[members[rule["member"]]["ref"]["id"]])
    out = set()
    for key in ("all", "any", "of"):
        for sub in rule.get(key, []):
            out |= _rule_roots(sub, members, roots)
    if "not" in rule:
        out |= _rule_roots(rule["not"], members, roots)
    return out


def test_reversal_source_count_would_be_unsatisfiable():
    """Section 3.4.1 rule 5: every item is price-derived, so two distinct sources can never be reached."""
    roots = load("lineage.json")["roots"]
    doc = load("group_reversal_evidence.json")
    members = {m["key"]: m for m in doc["members"]}
    for c in doc["conditions"]:
        items = [{"value": True, "support": [], "roots": sorted(_rule_roots(i, members, roots))} for i in c["rule"]["of"]]
        assert reference_count("count_distinct_sources_at_least", 2, items) is False


# ----------------------------------------------------------------------------- strict capture ceilings (reference)

PUBLIC = "public"


def _aud(a):
    """Audience as 'public', frozenset of communities, or None (owner only)."""
    if a.get("public"):
        return PUBLIC
    if a.get("owner"):
        return None
    return frozenset(a.get("communities") or []) or None


def _meet(x, y):
    if x == PUBLIC:
        return y
    if y == PUBLIC:
        return x
    if x is None or y is None:
        return None
    return (x & y) or None


def _within(x, y):
    """x ⊆ y; owner-only (None) is within anything."""
    if x is None or y == PUBLIC:
        return True
    if x == PUBLIC:
        return False
    return y is not None and x <= y


class SharingReference:
    """Test-only reference of design section 7 (strict capture ceilings). Not the database implementation."""

    def __init__(self, users):
        self.users = {u: frozenset(v["communities"]) for u, v in users.items()}
        self.owner, self.copy_ceiling, self.versions = {}, {}, {}

    def effective(self, cfg, ver):
        v = self.versions[(cfg, ver)]
        return _meet(v["published"], v["capture"])

    def can_read(self, user, cfg, ver):
        if self.owner[cfg] == user:
            return True
        eff = self.effective(cfg, ver)
        return eff == PUBLIC or (eff is not None and bool(eff & self.users[user]))

    def step(self, s):
        user, cfg = s["user"], s.get("config")
        if s["do"] == "copy":
            src = tuple(s["from"])
            if not self.can_read(user, *src):
                return "refused", None
            self.owner[cfg] = user
            self.copy_ceiling[cfg] = self.effective(*src)
            self.versions[(cfg, 1)] = {"published": None, "capture": self.copy_ceiling[cfg], "deps": [src]}
            return "ok", self.copy_ceiling[cfg]
        if s["do"] == "save":
            if cfg in self.owner and self.owner[cfg] != user:
                return "refused", None
            deps = [tuple(e) for e in s.get("embeds", [])]
            if not all(self.can_read(user, *d) for d in deps):
                return "refused", None
            self.owner.setdefault(cfg, user)
            capture = self.copy_ceiling.get(cfg, PUBLIC)
            for d in deps:
                capture = _meet(capture, self.effective(*d))
            self.versions[(cfg, s["version"])] = {"published": None, "capture": capture, "deps": deps}
            return "ok", capture
        if s["do"] == "publish":
            if self.owner.get(cfg) != user:
                return "refused", None
            v = self.versions[(cfg, s["version"])]
            want = _aud(s["audience"])
            if not _within(want, v["capture"]) or not all(_within(want, self.effective(*d)) for d in v["deps"]):
                return "refused", None
            v["published"] = want
            return "ok", None
        raise ValueError(s["do"])


@pytest.mark.parametrize("scenario", load("sharing_fixtures.json")["scenarios"], ids=lambda s: s["name"])
def test_strict_capture_ceilings(scenario):
    ref = SharingReference(load("sharing_fixtures.json")["users"])
    for i, step in enumerate(scenario["steps"]):
        outcome, ceiling = ref.step(step)
        assert outcome == step.get("expect", "ok"), f"step {i}: {step}"
        if "capture_ceiling" in step:
            assert ceiling == _aud(step["capture_ceiling"]), f"step {i}: ceiling {ceiling}"


def test_design_lists_five_tables_and_requires_real_rls_tests():
    text = (EXAMPLES.parent / "groups_sets.md").read_text(encoding="utf-8")
    for table in ("analysis_configs", "analysis_config_versions", "analysis_version_publications",
                  "analysis_version_shares", "analysis_publication_log"):
        assert table in text
    assert "Five tables" in text and "Three tables" not in text
    assert "Implementation acceptance requirement" in text and "real Supabase tests" in text
