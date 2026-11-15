"""
🌐 The language button (sidebar and sign-in page): the current language's flag and own name; a press opens the list,
each language as its flag and its own name (so anyone can find theirs whatever the page is in), beta ones marked.

Flags are small SVG images (i18n.flag_svg), not emojis: Windows shows flag emojis as two letters.
The choice is remembered by this browser (localStorage "ang_lang") so the sign-in page can use it too; on load, when
the page has no choice yet (`ask` true), the box sends the remembered one.

Sends {code, how: "pick" | "remembered", nonce} through the "lang" trigger.
"""

from __future__ import annotations

import json

import i18n

CSS = """
.anglang{position:relative;font:13px/1.3 inherit;color:inherit;display:inline-block;max-width:100%}
.anglang .cur{display:inline-flex;align-items:center;gap:8px;padding:5px 10px;border-radius:999px;cursor:pointer;
  border:1px solid rgba(127,127,127,.35);background:rgba(127,127,127,.06);color:inherit;font:inherit}
.anglang .cur:hover{border-color:rgba(127,127,127,.6)}
.anglang .fl{width:22px;height:16px;border-radius:3px;overflow:hidden;flex:0 0 auto;display:inline-flex;
  box-shadow:0 0 0 1px rgba(0,0,0,.12)}
.anglang .fl svg{width:100%;height:100%;display:block}
.anglang .list{position:absolute;z-index:1000;left:0;top:calc(100% + 6px);min-width:280px;max-width:calc(100vw - 32px);max-height:340px;overflow:auto;
  padding:6px;border-radius:12px;border:1px solid var(--ang-border,rgba(127,127,127,.35));
  background:var(--ang-surface,#fff);color:var(--ang-text,inherit);box-shadow:0 8px 24px rgba(0,0,0,.18)}
.anglang .list.up{top:auto;bottom:calc(100% + 6px)}
.anglang .opt{display:flex;align-items:center;gap:10px;width:100%;padding:7px 9px;border-radius:8px;border:0;
  background:transparent;color:inherit;font:inherit;cursor:pointer;text-align:left}
.anglang .opt:hover{background:rgba(127,127,127,.12)}
.anglang .opt.on{background:rgba(15,118,110,.16);font-weight:600}
.anglang .nm{white-space:nowrap}
.anglang .en{opacity:.6;font-size:12px;margin-left:auto;padding-left:10px;text-align:right}
.anglang .beta{font-size:10px;font-weight:700;padding:1px 6px;border-radius:999px;background:#b45309;color:#fff;margin-left:6px}
"""

JS = r"""
export default function angLang(component) {
  const { data, setTriggerValue, parentElement } = component;
  const d = data || {};
  Array.from(parentElement.children).forEach((c) => { if (c.classList && c.classList.contains("anglang")) c.remove(); });
  const root = document.createElement("div");
  root.className = "anglang";
  parentElement.appendChild(root);
  const send = (code, how) => setTriggerValue("lang", JSON.stringify({ code, how, nonce: Date.now() + Math.random() }));
  const KEY = "ang_lang";
  const read = () => { try { return localStorage.getItem(KEY) || ""; } catch (e) { return ""; } };
  const write = (v) => { try { localStorage.setItem(KEY, v); } catch (e) { /* private mode */ } };
  const options = d.options || [];
  const cur = options.find((o) => o.code === d.current) || options[0];
  if (!cur) return;
  if (d.ask) {                                // no choice for this page yet: offer the one this browser remembers
    const kept = read();
    if (kept && kept !== d.current && options.some((o) => o.code === kept)) { send(kept, "remembered"); }
  } else if (d.chosen) {
    write(d.current);
  }
  try { document.documentElement.lang = d.current || "en"; } catch (e) { /* not allowed */ }
  const flag = (o) => { const s = document.createElement("span"); s.className = "fl"; s.innerHTML = o.flag || ""; return s; };
  const button = document.createElement("button");
  button.type = "button"; button.className = "cur";
  button.title = (d.tip || "Language") + ": " + cur.english;
  button.setAttribute("aria-haspopup", "listbox");
  button.appendChild(flag(cur));
  const nm = document.createElement("span"); nm.textContent = cur.name; button.appendChild(nm);
  const caret = document.createElement("span"); caret.textContent = "▾"; caret.style.opacity = ".6"; button.appendChild(caret);
  root.appendChild(button);
  let list = null;
  const close = () => { if (list) { list.remove(); list = null; document.removeEventListener("mousedown", outside, true); } };
  // The box lives in a shadow root: a page-level event's target is the host, so test the event's path instead.
  const outside = (e) => { const path = e.composedPath ? e.composedPath() : [e.target]; if (!path.includes(root)) close(); };
  button.onclick = () => {
    if (list) { close(); return; }
    list = document.createElement("div"); list.className = "list" + (d.up ? " up" : ""); list.setAttribute("role", "listbox");
    options.forEach((o) => {
      const b = document.createElement("button"); b.type = "button";
      b.className = "opt" + (o.code === cur.code ? " on" : "");
      b.setAttribute("role", "option"); b.title = o.english;
      b.appendChild(flag(o));
      const n = document.createElement("span"); n.className = "nm"; n.textContent = o.name; b.appendChild(n);
      if (o.beta) { const t = document.createElement("span"); t.className = "beta"; t.textContent = "beta"; t.title = d.beta_tip || "Being checked"; b.appendChild(t); }
      if (o.english !== o.name) { const e = document.createElement("span"); e.className = "en"; e.textContent = o.english; b.appendChild(e); }
      b.onclick = () => { write(o.code); close(); if (o.code !== cur.code) send(o.code, "pick"); };
      list.appendChild(b);
    });
    root.appendChild(list);
    document.addEventListener("mousedown", outside, true);
  };
  return () => { close(); root.remove(); };
}
"""

_COMPONENT = None


def component():
    global _COMPONENT
    if _COMPONENT is None:
        import streamlit as st

        _COMPONENT = st.components.v2.component("angstrom_lang", js=JS, css=CSS)
    return _COMPONENT


def payload(current: str, options: list[dict], ask: bool, chosen: bool, up: bool = False) -> dict:
    """What the button draws: the current language and the ones offered, each with its flag image."""
    return {"current": current, "ask": bool(ask), "chosen": bool(chosen), "up": bool(up),
            "tip": i18n.t("Language"), "beta_tip": i18n.t("Being checked: some text may still be in English"),
            "options": [{"code": o["code"], "name": o["name"], "english": o["english"], "beta": o["status"] == "beta",
                         "flag": i18n.flag_svg(o["flag"])} for o in options]}


def read_event(result, seen_key: str, state) -> dict | None:
    """The latest choice, once (None when nothing new)."""
    raw = getattr(result, "lang", None)
    if not raw or raw == state.get(seen_key):
        return None
    state[seen_key] = raw
    try:
        event = json.loads(raw)
    except ValueError:
        return None
    code = i18n.normalise(event.get("code"))
    if not code or event.get("how") not in ("pick", "remembered"):
        return None
    return {"code": code, "how": event["how"]}
