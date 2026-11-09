"""AI Advisor, phase 0: explains only; its prompt carries the building blocks and the house rules."""

import json

import advisor


def test_the_prompt_knows_the_building_blocks_and_the_rules():
    saved = [{"id": "s1", "kind": "set", "name": "Breakout fading", "owner_id": "me",
              "versions": [{"version": 2, "body": __import__("prism").demo_sets()["demo:breakout"]}]}]
    text = advisor.system_prompt(saved, "me")
    for must in ("Relative volume", "Recent structure break", "Breakout with volume", "+ ⏭ THEN box",
                 "Study this Set", "never claim to have built", "Never tell the person to buy",
                 "30 Oct 2024", "Set “Breakout fading” (v2)"):
        assert must in text, must
    assert "None ()" not in text


def test_ask_sends_the_conversation_and_returns_the_text(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    sent = []

    class Answer:
        status_code = 200

        def json(self):
            return {"content": [{"type": "text", "text": "1. Open Signal Sets."}]}

    out = advisor.ask([{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}], "how?", "SYS",
                      post=lambda url, **k: sent.append((url, k)) or Answer())
    assert out == "1. Open Signal Sets."
    body = json.loads(sent[0][1]["data"])
    assert body["system"] == "SYS" and body["messages"][-1] == {"role": "user", "content": "how?"}
    assert sent[0][1]["headers"]["x-api-key"] == "k"


def test_no_key_means_no_advisor(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert not advisor.available()
