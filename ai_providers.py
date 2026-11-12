"""
Which AI does which job (decision of 12 Nov 2026: "Claude by default, with an option in Settings to select the AI for
each or all of our use cases").

Four providers, each switched on by its own API key in the app's environment (a secret on Render, and on GitHub for
the background worker). A provider without a key is shown but can't be picked. Keys never pass through the page.

    provider   key (secret name)    model (override with the *_MODEL secret)
    claude     ANTHROPIC_API_KEY    claude-sonnet-5-5         (ANTHROPIC_MODEL)
    grok       XAI_API_KEY          grok-4.3                  (XAI_CHAT_MODEL)
    chatgpt    OPENAI_API_KEY       gpt-6-astra               (OPENAI_MODEL)
    gemini     GEMINI_API_KEY       gemini-4-argon            (GEMINI_MODEL)

Uses:
- navigator: the ✨ AI Navigator and Today's AI Passage Plan. Each person picks theirs (account setting ai_navigator);
  default Claude.
- sentiment: the 📰 news sentiment scores. They are shared by everyone, so one choice for the whole app, made by an
  admin (app_settings row "ai", sql/2026-11-25_app_settings.sql); default Grok, as before.

chat() takes the conversation in one shape (Anthropic's: role + text, or text and image blocks) and returns
(text, finished), where finished is False when the answer ran out of room.
"""

from __future__ import annotations

import json
import os

import requests

PROVIDERS = {
    "claude": {"name": "Claude", "maker": "Anthropic", "env": "ANTHROPIC_API_KEY", "model_env": "ANTHROPIC_MODEL",
               "model": "claude-sonnet-5-5", "images": True,
               "keys_at": "https://console.anthropic.com/settings/keys"},
    "grok": {"name": "Grok", "maker": "xAI", "env": "XAI_API_KEY", "model_env": "XAI_CHAT_MODEL",
             "model": "grok-4.3", "images": False, "keys_at": "https://console.x.ai"},
    "chatgpt": {"name": "ChatGPT", "maker": "OpenAI", "env": "OPENAI_API_KEY", "model_env": "OPENAI_MODEL",
                "model": "gpt-6-astra", "images": True, "keys_at": "https://platform.openai.com/api-keys"},
    "gemini": {"name": "Gemini", "maker": "Google", "env": "GEMINI_API_KEY", "model_env": "GEMINI_MODEL",
               "model": "gemini-4-argon", "images": True, "keys_at": "https://aistudio.google.com/apikey"},
}

USES = {   # key: (label, default provider, who chooses, help)
    "navigator": ("✨ AI Navigator and Passage Plan", "claude", "you",
                  "Answers your questions about the app, your ideas and the Tides readings, and writes Today's AI "
                  "Passage Plan."),
    "sentiment": ("📰 News sentiment scores", "grok", "admin",
                  "Scores the headlines for every asset and both markets. Shared by everyone, so an admin picks it "
                  "for the whole app; new scores use it from their next refresh (every 12 hours)."),
}

URLS = {"claude": "https://api.anthropic.com/v1/messages",
        "grok": "https://api.x.ai/v1/chat/completions",
        "chatgpt": "https://api.openai.com/v1/responses",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"}


def key(provider: str) -> str:
    raw = (os.getenv(PROVIDERS[provider]["env"]) or "").strip().strip('"').strip("'")
    return raw[7:].strip() if raw.lower().startswith("bearer ") else raw


def available(provider: str) -> bool:
    return provider in PROVIDERS and bool(key(provider))


def model(provider: str) -> str:
    spec = PROVIDERS[provider]
    return (os.getenv(spec["model_env"]) or "").strip() or spec["model"]


def label(provider: str) -> str:
    spec = PROVIDERS.get(provider) or {}
    return f"{spec.get('name', provider)} ({spec.get('maker', '')})"


def pick(use: str, chosen: str | None) -> str:
    """The provider to use: the chosen one when its key is there, else the default, else any with a key."""
    default = USES[use][1]
    for p in (chosen, default, *PROVIDERS):
        if p in PROVIDERS and available(p):
            return p
    return chosen if chosen in PROVIDERS else default


# ------------------------------------------------------------------------------------------- one conversation

def _blocks(content) -> tuple[str, list[dict]]:
    """(text, [image {media_type, data}]) from a message's content (text, or Anthropic-style blocks)."""
    if isinstance(content, str):
        return content, []
    text, images = [], []
    for b in content or []:
        if b.get("type") == "text":
            text.append(b.get("text", ""))
        elif b.get("type") == "image" and (b.get("source") or {}).get("type") == "base64":
            images.append({"media_type": b["source"]["media_type"], "data": b["source"]["data"]})
    return "\n".join(text), images


def _system_text(system) -> str:
    if isinstance(system, (list, tuple)):
        return "\n\n".join(s["text"] if isinstance(s, dict) else str(s) for s in system)
    return str(system or "")


def _check(response, provider: str) -> dict:
    if response.status_code != 200:
        try:
            body = response.json()
            err = body.get("error") if isinstance(body, dict) else None
            detail = (err.get("message") if isinstance(err, dict) else err) or str(body)[:200]
        except ValueError:
            detail = response.text[:200]
        raise RuntimeError(f"{PROVIDERS[provider]['name']} answered {response.status_code}: {str(detail)[:200]}")
    return response.json()


def chat(provider: str, system, messages: list[dict], max_tokens: int = 2500, post=requests.post,
         json_only: bool = False, timeout: int = 120) -> tuple[str, bool]:
    """One answer from `provider`. messages: [{role: user|assistant, content}]; an assistant message last means
    "carry on from here" (Claude continues it; the others are asked to)."""
    k = key(provider)
    if not k:
        raise RuntimeError(f"{label(provider)} isn't switched on: it needs {PROVIDERS[provider]['env']}.")
    m = model(provider)
    if provider == "claude":
        if isinstance(system, (tuple, list)) and len(system) == 2 and all(isinstance(s, str) for s in system):
            system = [{"type": "text", "text": system[0], "cache_control": {"type": "ephemeral"}},
                      {"type": "text", "text": system[1]}]
        data = _check(post(URLS["claude"], timeout=timeout, headers={
            "x-api-key": k, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            data=json.dumps({"model": m, "max_tokens": max_tokens, "system": system, "messages": messages})),
            provider)
        text = "".join(p.get("text", "") for p in data.get("content") or [] if p.get("type") == "text")
        return text, data.get("stop_reason") != "max_tokens"

    sys_text = _system_text(system)
    msgs = list(messages)
    if msgs and msgs[-1]["role"] == "assistant":      # carry on: say so in words
        msgs.append({"role": "user", "content": "Continue exactly where you stopped, without repeating anything."})

    if provider == "grok":
        out = [{"role": "system", "content": sys_text}]
        for msg in msgs:
            text, images = _blocks(msg["content"])
            out.append({"role": msg["role"], "content": text + (" [screenshot attached; this AI can't see "
                                                                 "pictures]" if images else "")})
        body = {"model": m, "messages": out, "max_completion_tokens": max_tokens}
        if json_only:
            body["response_format"] = {"type": "json_object"}
        data = _check(post(URLS["grok"], timeout=timeout, headers={"Authorization": f"Bearer {k}",
                                                                   "Content-Type": "application/json"},
                           data=json.dumps(body)), provider)
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        if isinstance(content, list):
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        return str(content), choice.get("finish_reason") != "length"

    if provider == "chatgpt":
        items = []
        for msg in msgs:
            text, images = _blocks(msg["content"])
            kind = "output_text" if msg["role"] == "assistant" else "input_text"
            parts = [{"type": kind, "text": text}]
            if msg["role"] == "user":
                parts += [{"type": "input_image", "image_url": f"data:{i['media_type']};base64,{i['data']}"}
                          for i in images]
            items.append({"role": msg["role"], "content": parts})
        body = {"model": m, "instructions": sys_text, "input": items, "max_output_tokens": max_tokens}
        if json_only:
            body["text"] = {"format": {"type": "json_object"}}
        data = _check(post(URLS["chatgpt"], timeout=timeout, headers={"Authorization": f"Bearer {k}",
                                                                      "Content-Type": "application/json"},
                           data=json.dumps(body)), provider)
        text = "".join(c.get("text", "") for o in data.get("output") or [] if o.get("type") == "message"
                       for c in o.get("content") or [] if c.get("type") == "output_text")
        cut = data.get("status") == "incomplete" and (data.get("incomplete_details") or {}).get(
            "reason") == "max_output_tokens"
        return text, not cut

    if provider == "gemini":
        contents = []
        for msg in msgs:
            text, images = _blocks(msg["content"])
            parts = [{"text": text}] + [{"inline_data": {"mime_type": i["media_type"], "data": i["data"]}}
                                        for i in images]
            contents.append({"role": "model" if msg["role"] == "assistant" else "user", "parts": parts})
        cfg = {"maxOutputTokens": max_tokens}
        if json_only:
            cfg["responseMimeType"] = "application/json"
        body = {"systemInstruction": {"parts": [{"text": sys_text}]}, "contents": contents, "generationConfig": cfg}
        data = _check(post(URLS["gemini"].format(model=m), timeout=timeout,
                           headers={"x-goog-api-key": k, "Content-Type": "application/json"},
                           data=json.dumps(body)), provider)
        cand = (data.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts") or []
                       if not p.get("thought"))
        return text, cand.get("finishReason") != "MAX_TOKENS"

    raise RuntimeError(f"Unknown AI: {provider}")


# ---------------------------------------------------------------------------------------- the app-wide choice

def app_choice(supabase, use: str) -> str | None:
    """The admin's choice for a shared use (app_settings row "ai"), or None (not set, or the table isn't there)."""
    try:
        rows = supabase.table("app_settings").select("value").eq("key", "ai").limit(1).execute().data or []
    except Exception:
        return None
    value = (rows[0].get("value") if rows else None) or {}
    return value.get(use) if isinstance(value, dict) else None


def save_app_choice(supabase, use: str, provider: str) -> str:
    """Save an admin's choice. Empty when it worked, else the reason."""
    try:
        supabase.rpc("app_setting_set", {"p_key": "ai", "p_patch": {use: provider}}).execute()
        return ""
    except Exception as exc:
        text = str(exc)
        if "app_setting_set" in text and ("does not exist" in text or "PGRST" in text):
            return "The database update for app settings hasn't been run yet (sql/2026-11-25_app_settings.sql)."
        if "not allowed" in text:
            return "Only an admin can change this."
        return f"Could not save it: {text[:160]}"
