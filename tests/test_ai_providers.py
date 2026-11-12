"""Which AI does which job (ai_providers.py): one conversation shape in, each provider's API out."""

import json

import ai_providers as ap


class R:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


def _capture(reply):
    sent = []

    def post(url, timeout, headers, data):
        sent.append((url, headers, json.loads(data)))
        return R(reply)
    return sent, post


SHOT = [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"}},
        {"type": "text", "text": "what is this?"}]


def test_pick_falls_back_to_a_provider_with_a_key(monkeypatch):
    for spec in ap.PROVIDERS.values():
        monkeypatch.delenv(spec["env"], raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert ap.pick("navigator", "gemini") == "claude"          # Gemini has no key: the default
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    assert ap.pick("navigator", "gemini") == "gemini"
    monkeypatch.setenv("GEMINI_MODEL", "gemini-x")
    assert ap.model("gemini") == "gemini-x"


def test_chatgpt_uses_the_responses_api_with_pictures(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    sent, post = _capture({"status": "completed", "output": [
        {"type": "reasoning"}, {"type": "message", "content": [{"type": "output_text", "text": "A chart."}]}]})
    text, done = ap.chat("chatgpt", ("shared", "mine"), [{"role": "user", "content": SHOT}], 100, post=post)
    assert (text, done) == ("A chart.", True)
    url, headers, body = sent[0]
    assert url.endswith("/v1/responses") and headers["Authorization"] == "Bearer o"
    assert body["instructions"] == "shared\n\nmine" and body["max_output_tokens"] == 100
    kinds = [p["type"] for p in body["input"][0]["content"]]
    assert kinds == ["input_text", "input_image"]


def test_gemini_maps_roles_and_reports_a_cut_answer(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    sent, post = _capture({"candidates": [{"content": {"parts": [{"text": "half"}]}, "finishReason": "MAX_TOKENS"}]})
    text, done = ap.chat("gemini", "sys", [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}],
                         50, post=post)
    assert (text, done) == ("half", False)
    url, headers, body = sent[0]
    assert headers["x-goog-api-key"] == "g" and ":generateContent" in url
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]   # "carry on" is asked in words


def test_grok_drops_pictures_and_can_ask_for_json(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "x")
    sent, post = _capture({"choices": [{"message": {"content": "{\"score\": 60}"}, "finish_reason": "stop"}]})
    text, done = ap.chat("grok", "sys", [{"role": "user", "content": SHOT}], 50, post=post, json_only=True)
    assert done and text == "{\"score\": 60}"
    body = sent[0][2]
    assert body["response_format"] == {"type": "json_object"}
    assert "can't see pictures" in body["messages"][1]["content"]


def test_claude_caches_the_shared_part(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    sent, post = _capture({"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"})
    assert ap.chat("claude", ("shared", "mine"), [{"role": "user", "content": "hi"}], post=post) == ("ok", True)
    assert sent[0][2]["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_no_key_is_a_plain_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    try:
        ap.chat("chatgpt", "s", [{"role": "user", "content": "x"}])
    except RuntimeError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("expected an error")


def test_the_navigator_can_answer_with_another_ai(monkeypatch):
    import advisor

    monkeypatch.setenv("GEMINI_API_KEY", "g")
    replies = [{"candidates": [{"content": {"parts": [{"text": "first half"}]}, "finishReason": "MAX_TOKENS"}]},
               {"candidates": [{"content": {"parts": [{"text": " and the rest."}]}, "finishReason": "STOP"}]}]
    sent = []

    def post(url, timeout, headers, data):
        sent.append(json.loads(data))
        return R(replies[len(sent) - 1])

    out = advisor.ask([], "plan", ("a", "b"), post=post, max_tokens=50, provider="gemini")
    assert out == "first half and the rest."


def test_sentiment_uses_the_admins_choice_when_its_key_is_there(monkeypatch):
    import sentiment

    monkeypatch.setenv("OPENAI_API_KEY", "o")
    sentiment.set_provider("chatgpt")
    try:
        assert sentiment.scoring_provider() == "chatgpt" and sentiment.sentiment_ready()
        monkeypatch.delenv("OPENAI_API_KEY")
        assert sentiment.scoring_provider() == "grok"
    finally:
        sentiment.set_provider(None)
