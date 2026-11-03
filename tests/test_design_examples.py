"""The Groups/Sets design examples must reference real Signal Library signals with valid parameters,
so the proposal under review matches the code."""

import json
import pathlib

import pytest

import signal_library as sl

EXAMPLES = pathlib.Path(__file__).resolve().parents[1] / "docs" / "design" / "examples"


def _refs(doc):
    for section in ("members", "standalone", "market_context"):
        for item in doc.get(section) or []:
            yield item["key"], item["ref"]


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.json")), ids=lambda p: p.name)
def test_example_refs_resolve(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    keys = set()
    for key, ref in _refs(doc):
        assert key not in keys, f"duplicate key {key}"
        keys.add(key)
        definition = sl.REGISTRY.get(ref["id"], ref["version"])
        made = sl.SignalRef.make(definition, ref["timeframe"], **ref["params"])  # raises on bad params/timeframe
        assert made.version == ref["version"]
    if doc["schema"].startswith("angstrom.group/"):
        roles = {m["role"] for m in doc["members"]}
        assert roles <= {"score", "condition", "levels", "context"}
        for m in doc["members"]:
            if m["role"] == "score":
                assert m["weight"] >= 0 and m.get("transform")
        if doc["score"] is not None:
            assert any(m["role"] == "score" for m in doc["members"]) and doc["score"]["meaning"]
        text = json.dumps(doc["conditions"])
        for m in doc["members"]:
            if m["role"] == "condition":
                assert f'"{m["key"]}"' in text, f"condition member {m['key']} unused"
