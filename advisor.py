"""
✨ AI Navigator (it started as the Lattice AI Advisor, then the Angstrom Assistant), phase 0: one assistant for the whole app. It answers
questions about where things are and how to use them, and explains in plain words how to build and test an idea in
Lattice. Opened from the top bar it starts as the app guide; opened from Lattice, as the research coach; it answers
either kind of question in the same conversation. Both buttons open the same window (?view=advisor&from=...).

What it knows is rebuilt from the app on every question, so it cannot drift: the Help and guides text (read from
app.py), the training videos, every signal, the provided Groups and Sets, and the person's own. The hand-written part
(RULES) is guarded by tests/test_advisor_guide.py.

It never builds, saves or runs anything: the person does every click. It knows the building blocks (every signal and
its readings, the provided Groups and Sets as Look inside shows them, the person's own Groups and Sets, the What
followed results) and how the editor works, and keeps the house rules (descriptions, not advice; studies only on
data before the protected hold-out; caution about testing many variations).

The model is Claude through the Anthropic API (ANTHROPIC_API_KEY in the app's environment). No key, no Advisor:
the tab says so and the rest of Lattice is unaffected.
"""

from __future__ import annotations

import json
import os

import requests

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5-5"            # Claude, the default; other AIs via ai_providers.py (Settings)
MAX_TOKENS = 2500                      # an answer that reaches this is continued once (never cut off silently)
MAX_TURNS = 12                         # earlier turns are dropped from what is sent, oldest first
DAILY_LIMIT = 60                       # questions per person per day (this browser session's count)

RULES = """You are the ✨ AI Navigator inside Angstrom Signals, a market research app for crypto and stocks. You
have two jobs, and the person can ask about either at any time:
1. App guide: where things are and how to use them (sections, buttons, settings, alerts, watchlists, the chart,
   what a reading or score means). Answer from the Help and guides text below, which is the app's own help; when
   a 🎬 training video covers the question, give its link exactly as listed under 🎬 Training videos (a markdown
   link such as [🎬 3 · Signal Groups](?view=video&v=03-signal-groups)); the person clicks it to watch. If the help does not cover something, say you are not sure rather than guess where it is.
2. Research coach in the research workspace, Angstrom Lattice: help the person turn a trading idea into the app's
   building blocks and understand the results.
You only explain: you never claim to have built, saved, run or changed anything, because you cannot. The person
does every click, following your steps.
The person may attach screenshots of the app. Read them to see what they are looking at, and answer about what is
actually on the screen; say so if a screenshot is unclear or is not of this app.

How you answer:
- Plain words for a beginner. Short paragraphs or numbered steps. Name the real buttons and fields exactly as the
  app shows them (they are listed below). Use the exact names of signals, Groups and Sets from the lists below;
  never invent a signal, field, Group, Set or feature. If something cannot be expressed today, say so plainly
  and give the closest honest way, saying what it leaves out.
- Readings describe the market; they are not forecasts. Never tell the person to buy, sell, hold, size a
  position or use leverage, and never call anything a good trade. You may explain what a past study found, with
  its limits ("past patterns, before costs; not a forecast").
- Encourage testing with "Study this Set" (What followed) instead of trusting a chart by eye, and explain why a
  chart of one asset over one year can mislead (a falling year makes almost any moment look followed by a drop;
  studies compare with comparable days). Warn that testing many variations makes a lucky result likely: decide the
  idea first, then test it once or twice.
- The protected hold-out (30 Oct 2024 onwards) is never used for studies; never suggest using it.
- If the person asks about something outside Lattice (prices now, news, which coin to buy), say briefly what the
  app can and cannot do and steer back to building and testing their idea.
- Be honest when unsure. Ask one short question when the idea is too vague to build.

How Lattice works (the screens):
- Tabs: Signal Groups, Signal Sets, Prism Scan, Strategies (coming later; nothing to build there yet). You, the
  AI Navigator, open in your own window from the ✨ AI button beside those tabs, so the person can follow your steps
  in the app beside you.
- A Signal is one measurement from finished candles (each has readings, listed below with their ranges).
- Signal Groups tab: "Start from" (➕ New Group, provided starters, your own). Left panel "Signals": tap + or drag a
  signal in. Each member has a role: Score (counts toward the -100..+100 score), Condition (used only in rules),
  Levels, Context. "Rules: what the Group says" give labels such as Bullish, checked top to bottom, first match
  wins; Unknown if a needed reading is missing; an "otherwise" label. Buttons: 💾 Save as a new Group, 💾 Save as
  version N of <name>, ✏️ Rename, 🗑 Delete.
- Signal Sets tab: "Start from" (➕ New Set, provided Sets as "(my copy)", your own). Left panel "Groups and
  signals": tap + to add a Group (goes in exactly as saved) or a single signal (a Condition). Each item can be read
  on "📌 the scanned asset" or a fixed crypto or equity (type a name and press Enter to search the market, then
  pick a match). "Decision: when does this Set say Yes?" is an ALL · AND box: every line must hold. Buttons under
  it: "+ Line", "+ ANY (OR) box" (any one of its lines is enough), "+ ⏭ THEN box" (a sequence: "1 · First" lines
  held on an earlier daily close, then "2 · Then, within N daily closes" (1 to 20) the Then lines hold; optional
  "3 · Cancel if"; at most 2 THEN boxes; lines inside a part all must hold, there is no OR inside a THEN box).
  A line picks a reading, a comparison (is at least, is at most, has a value, is, is not, is yes, is no) and a
  value. Group lines can test its label, its score (shown -100..+100), a named condition (met / not met) or its
  status. Saving: 💾 Save as a new Set, 💾 Save as version N, ✏️ Rename, 🗑 Delete. Under the editor: "What
  followed" with "🔬 Study this Set (version N)": a background study (usually within an hour; a 🔬 note arrives in
  the notifications) of what happened in the 10 daily candles after each fresh Yes, compared with comparable days
  (same asset, same year, same side of the 200-day average), on 25 major coins and 61 large US equities from Sep
  2014 to Oct 2024. Verdicts: 🔬 Too few to judge, ⚖️ No clear difference, 〰️ Some difference, not established,
  🧭 Consistent difference. Measures: rose a typical move before falling one (and the reverse), average move after
  10 candles in typical moves, finished higher.
- Prism Scan tab: left panel lists Saved Sets (provided ones under "Provided by Angstrom Signals", each with
  "more…" and "🔍 Look inside" → "Make my own copy") and the Watchlist (groups Whole Watchlist, All crypto, All
  equities; single assets). Drop a Set or tap + to start a scan. A scan has Assets (adding something replaces Whole
  Watchlist; All crypto takes in single coins), Runs (Only when I press Play, each 4-hour/daily/weekly close, at
  set times), Alerts (Instant, Daily digest, App only, Off; Turns Yes, Turns No, Can't run). Buttons: ▶ run now,
  ⏪ past moment, 🕰️ Visualize History (the Set's answer on every past day as green bands, small charts for every
  asset, 1Y/3Y/10Y/All), pause, 🔍 look inside, ⧉ Duplicate this scan, ✕ delete. A row that is No but part-way
  through a THEN box shows ⏭ N (Armed: N closes left).
- The asset tables on the dashboard can show chosen Groups and Sets as columns (column icon in the table header).
"""


def api_key() -> str:
    return (os.getenv("ANTHROPIC_API_KEY") or "").strip().strip('"').strip("'")


def available() -> bool:
    return bool(api_key())


def _signals() -> list[str]:
    import lattice_editor as le

    out = []
    for s in le.catalogue():
        reads = []
        for o in s.get("operands") or []:
            if o["type"] == "label" and o.get("labels"):
                reads.append(f"{o['label']} (one of {', '.join(o['labels'])})")
            else:
                reads.append(f"{o['label']} ({o.get('scale') or o['type']})")
        out.append(f"- {s['name']} [{s['category_label']}; timeframes {', '.join(s['timeframes'])}]: "
                   f"{(s.get('hint') or '')[:180]} Readings: {'; '.join(reads)}")
    return out


def _provided() -> list[str]:
    import perspectives
    import prism
    import set_inside

    out = ["Provided Groups (Signal Sets → Groups and signals → Provided by Angstrom Signals):"]
    for _, (name, body) in prism.provided_groups().items():
        members = ", ".join(m.get("label") or m["ref"]["id"] for m in body.get("members") or [])
        labels = [r["label"] for r in ((body.get("outcomes") or {}).get("rules") or [])]
        conds = [c.get("label") or c["key"] for c in body.get("conditions") or []]
        out.append(f"- {name}: signals {members}" + (f"; labels {', '.join(labels)}" if labels else "")
                   + (f"; conditions: {'; '.join(conds)}" if conds else ""))
    out.append("Provided Sets (Prism → Provided by Angstrom Signals; open with 🔍 Look inside → Make my own copy):")
    for key, doc in prism.demo_sets().items():
        inside = set_inside.parts(doc)
        card = perspectives.followed_card(doc, key)
        more = perspectives.explain(key) or {}
        out.append(f"- {doc['name']}: {more.get('measures') or doc.get('purpose') or ''} {inside['decision']}"
                   + (f" What followed: {card['verdict']} ({' '.join(card['lines'][:3])})"
                      if card and card.get("verdict") else " (a filter for other Sets; not studied on its own)"
                      if card else ""))
    return out


def _mine(saved: list[dict], user_id: str) -> list[str]:
    import perspectives
    import set_inside

    out = []
    for c in saved or []:
        if c.get("owner_id") != user_id or not c.get("versions"):
            continue
        body = c["versions"][-1].get("body") or {}
        v = c["versions"][-1].get("version")
        if c.get("kind") == "set":
            inside = set_inside.parts(body)
            card = perspectives.followed_card(body)
            extra = ""
            if card:
                bits = [p["line"] for p in card.get("parts") or []] + [card.get("compare") or "",
                                                                    (card.get("assets") or {}).get("line") or ""]
                extra = f" What followed: {card['verdict']}. " + " ".join(b for b in bits if b)
            out.append(f"- Set “{c['name']}” (v{v}): {inside['decision'] or 'no decision yet'}" + extra)
        else:
            members = ", ".join(m.get("label") or m["ref"]["id"] for m in body.get("members") or [])
            out.append(f"- Group “{c['name']}” (v{v}): signals {members}")
    return out or ["(none saved yet)"]


_HELP: list[str] = []


def _help_text() -> str:
    """The text of 📖 Help and guides, read from app.py (every markdown, caption and tab name in that section)."""
    if not _HELP:
        import ast
        from pathlib import Path

        src = (Path(__file__).resolve().parent / "app.py").read_text(encoding="utf-8")
        texts = []
        for node in ast.walk(ast.parse(src)):
            # The guide is the function _render_help_guides (drawn in the sidebar and in its own window).
            if not (isinstance(node, ast.FunctionDef) and node.name == "_render_help_guides"):
                continue
            for call in ast.walk(node):
                if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.args
                        and call.func.attr in ("markdown", "caption", "tabs", "info", "write", "expander")):
                    continue
                arg = call.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    texts.append(arg.value)
                elif isinstance(arg, ast.JoinedStr):
                    texts.append("".join(v.value if isinstance(v, ast.Constant) else "…" for v in arg.values))
                elif isinstance(arg, ast.List):
                    texts.append("Help tabs: " + " | ".join(e.value for e in arg.elts if isinstance(e, ast.Constant)))
            break
        _HELP.append("\n\n".join(t.strip() for t in texts if t.strip()))
    return _HELP[0]


def _videos() -> list[str]:
    import training_videos as tv

    out = []
    for _, (series, videos) in tv.SERIES.items():
        out.append(f"{series}: " + "; ".join(f"[🎬 {tv.info(slug)['label']}]({tv.address(slug)}) ({length})"
                                             for slug, _, length in videos))
    return out


START = {
    "app": "The person opened you from the top bar of the app: expect questions about the app itself first.",
    "lattice": "The person opened you from Angstrom Lattice: expect questions about building and testing ideas first.",
    "tides": "The person opened you from 🌊 Tides, the macro layer: expect questions about the currents, the tide, the "
             "sea state and the macro calendar first, and how they bear on their own assets, Sets and funnels.",
}


def system_parts(saved: list[dict], user_id: str, start: str = "lattice", extra: str = "") -> tuple[str, str]:
    """(the part that is the same for everyone, so it can be cached; the part about this person). `extra`: more about
    this person's view, such as the day's Tides readings with their watchlist and funnels (navigator.py)."""
    shared = "\n".join([RULES, "Help and guides (the app's own help text):", _help_text(), "",
                        "🎬 Training videos:", *_videos(), "",
                        "Signals (name, readings and their ranges):", *_signals(), "", *_provided()])
    mine = "\n".join([START.get(start, START["lattice"]), "", "The person's own Groups and Sets:",
                      *_mine(saved, user_id)] + (["", extra] if extra else []))
    return shared, mine


def system_prompt(saved: list[dict], user_id: str, start: str = "lattice") -> str:
    return "\n\n".join(system_parts(saved, user_id, start))


MAX_IMAGES = 3                          # screenshots per question


def image_blocks(images: list[str] | None) -> list[dict]:
    """Pasted screenshots (data: URLs from the paste box) as API image blocks; anything else is left out."""
    out = []
    for url in (images or [])[:MAX_IMAGES]:
        head, _, body = str(url).partition(",")
        kind = head[5:].split(";")[0] if head.startswith("data:") and ";base64" in head else ""
        if kind in ("image/jpeg", "image/png", "image/webp", "image/gif") and body:
            out.append({"type": "image", "source": {"type": "base64", "media_type": kind, "data": body}})
    return out


def ask(history: list[dict], question: str, system, post=requests.post, images: list[str] | None = None,
        max_tokens: int = MAX_TOKENS, provider: str = "claude") -> str:
    """The answer from the chosen AI; when another AI than Claude can't answer (no credit left, a key problem, busy),
    Claude answers instead, with a note saying so."""
    if provider == "claude":
        return _ask(history, question, system, post, images, max_tokens, "claude")
    try:
        return _ask(history, question, system, post, images, max_tokens, provider)
    except Exception as exc:
        import ai_providers

        if not ai_providers.available("claude"):
            raise
        print(f"AI Navigator: {provider} failed, Claude answered instead: {str(exc)[:200]}", flush=True)
        text = _ask(history, question, system, post, images, max_tokens, "claude")
        return text + (f"\n\n*({ai_providers.label(provider)} couldn't answer just now, so Claude answered "
                       "instead.)*")


def _ask(history: list[dict], question: str, system, post=requests.post, images: list[str] | None = None,
         max_tokens: int = MAX_TOKENS, provider: str = "claude") -> str:
    """The Advisor's answer to `question` (with any pasted screenshots), given the conversation so far
    ([{role, content}]; earlier screenshots are not sent again). provider: which AI (ai_providers.py; the
    person's choice in Settings), Claude by default."""
    import ai_providers

    key = api_key() if provider == "claude" else ai_providers.key(provider)
    if not key:
        raise RuntimeError(f"The AI Navigator needs {ai_providers.PROVIDERS[provider]['env']} in the app's "
                           "environment.")
    messages = [{"role": m["role"], "content": m["content"] + (" [screenshot attached]" if m.get("images") else "")}
                for m in history if m.get("role") in ("user", "assistant")][-2 * MAX_TURNS:]
    pictures = image_blocks(images)
    messages = messages + [{"role": "user", "content": pictures + [{"type": "text", "text": question}]
                            if pictures else question}]
    if isinstance(system, (tuple, list)):         # the shared part is cached by the API, so each question costs less
        system = [{"type": "text", "text": system[0], "cache_control": {"type": "ephemeral"}},
                  {"type": "text", "text": system[1]}]
    def call(msgs):
        if provider != "claude":
            text, done = ai_providers.chat(provider, system, msgs, max_tokens, post=post)
            return text, None if done else "max_tokens"
        response = post(API_URL, timeout=120, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            data=json.dumps({"model": MODEL, "max_tokens": max_tokens, "system": system, "messages": msgs}))
        if response.status_code != 200:
            try:
                detail = response.json().get("error", {}).get("message", "")
            except ValueError:
                detail = response.text[:200]
            raise RuntimeError(f"The AI service answered {response.status_code}: {detail[:200]}")
        data = response.json()
        text = "".join(part.get("text", "") for part in data.get("content") or [] if part.get("type") == "text")
        return text, data.get("stop_reason")

    text, stop = call(messages)
    if stop == "max_tokens" and text.strip():
        # It ran out of room mid-answer: ask it to carry on from exactly where it stopped, once.
        more, stop = call(messages + [{"role": "assistant", "content": text.rstrip()}])
        text = text.rstrip() + more if more[:1] in (" ", "\n", ",", ".", ";", ":", ")") else text.rstrip() + " " + more
    text = text.strip()
    if stop == "max_tokens":
        text += "\n\n*(This answer was long and was cut short. Ask the Navigator to finish it.)*"
    return text


# ----------------------------------------------------------------------------------------------- the window

_PASTE_JS = """
export default function(component) {
  const { data, setStateValue, parentElement } = component;
  const box = parentElement.querySelector(".ang-paste");
  if (!box) return;
  const strip = box.querySelector(".ang-shots");
  const pick = box.querySelector("input[type=file]");
  const max = (data && data.max) || 3;
  // Cleared after each question: the window remembers the token it last cleared for.
  if (data && data.clear !== window.__angPasteCleared) { window.__angPasteCleared = data.clear; window.__angShots = []; }
  let shots = window.__angShots || [];
  const draw = () => {
    strip.innerHTML = "";
    shots.forEach((url, i) => {
      const cell = document.createElement("span");
      cell.className = "ang-shot";
      const img = document.createElement("img"); img.src = url; img.alt = "Screenshot " + (i + 1);
      const x = document.createElement("button"); x.type = "button"; x.textContent = "✕"; x.title = "Remove this screenshot";
      x.addEventListener("click", () => { shots.splice(i, 1); save(); });
      cell.append(img, x); strip.appendChild(cell);
    });
    box.classList.toggle("has", shots.length > 0);
  };
  const save = () => { window.__angShots = shots; draw(); setStateValue("images", shots.slice()); };
  // Screenshots are shrunk to at most 1568 px on the long side (what the AI reads anyway) and sent as JPEG.
  const add = (file) => {
    if (!file || !file.type.startsWith("image/") || shots.length >= max) return;
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const scale = Math.min(1, 1568 / Math.max(img.width, img.height));
        const c = document.createElement("canvas");
        c.width = Math.round(img.width * scale); c.height = Math.round(img.height * scale);
        const g = c.getContext("2d"); g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height);
        g.drawImage(img, 0, 0, c.width, c.height);
        if (shots.length < max) { shots.push(c.toDataURL("image/jpeg", 0.85)); save(); }
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  };
  draw();
  if (!box.dataset.ready) {
    box.dataset.ready = "1";
    pick.addEventListener("change", () => { Array.from(pick.files || []).forEach(add); pick.value = ""; });
    box.querySelector(".ang-add").addEventListener("click", () => pick.click());
  }
  if (!window.__angPasteReady) {
    window.__angPasteReady = true;
    // Paste anywhere in the window (Ctrl+V / ⌘V), or drop a picture on it.
    document.addEventListener("paste", (e) => {
      const items = Array.from((e.clipboardData && e.clipboardData.items) || []).filter((it) => it.type.startsWith("image/"));
      if (!items.length) return;
      e.preventDefault();
      items.forEach((it) => add(it.getAsFile()));
    });
    document.addEventListener("dragover", (e) => e.preventDefault());
    document.addEventListener("drop", (e) => {
      const files = Array.from((e.dataTransfer && e.dataTransfer.files) || []).filter((f) => f.type.startsWith("image/"));
      if (!files.length) return;
      e.preventDefault();
      files.forEach(add);
    });
  }
}
"""

_PASTE_HTML = (
    "<div class='ang-paste'><div class='ang-shots'></div>"
    "<button type='button' class='ang-add' title='Add a screenshot of the app: paste it anywhere in this window "
    "(Ctrl+V, or ⌘V on a Mac), drop it here, or tap to choose one. Up to 3 per question.'>"
    "<svg viewBox='0 0 24 24' width='16' height='16' fill='currentColor' aria-hidden='true'><path d='M21 19V5c0-1.1"
    "-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z'/>"
    "</svg><span>Paste or add a screenshot</span></button>"
    "<input type='file' accept='image/*' multiple hidden></div>")

_PASTE_CSS = """
.ang-paste{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:2px 0 6px}
.ang-shots{display:flex;flex-wrap:wrap;gap:8px}
.ang-shot{position:relative;display:inline-block}
.ang-shot img{height:64px;max-width:140px;object-fit:cover;border-radius:6px;border:1px solid rgba(128,128,128,.35)}
.ang-shot button{position:absolute;top:-7px;right:-7px;width:20px;height:20px;border-radius:50%;border:none;
  background:#334155;color:#fff;font-size:11px;line-height:20px;padding:0;cursor:pointer}
.ang-add{display:inline-flex;align-items:center;gap:6px;background:transparent;color:inherit;opacity:.75;
  border:1px dashed rgba(128,128,128,.5);border-radius:8px;padding:6px 10px;font:inherit;font-size:.85rem;cursor:pointer}
.ang-add:hover{opacity:1}
"""
_PASTE = []


def _paste_box(st) -> list[str]:
    """The screenshot box under the question; returns the pasted screenshots (data: URLs)."""
    if not _PASTE:
        _PASTE.append(st.components.v2.component("advisor_paste", html=_PASTE_HTML, css=_PASTE_CSS, js=_PASTE_JS,
                                                 isolate_styles=False))
    got = _PASTE[0](key="advisor_paste", data={"max": MAX_IMAGES, "clear": st.session_state.get("advisor_cleared", 0)},
                    default={"images": []}, on_images_change=lambda: None)
    try:
        return list(getattr(got, "images", None) or [])
    except Exception:
        return []


def _show_images(st, images: list[str]) -> None:
    import base64

    for url in images or []:
        try:
            st.image(base64.b64decode(url.partition(",")[2]), width=220)
        except Exception:
            pass


def render(st, supabase, user_id: str = "", start: str = "lattice", watchlist: dict | None = None,
           auto: str = "", provider: str = "claude") -> None:
    import time

    import ai_providers

    import signal_groups_inspector as gi

    st.caption("Ask anything about the app: where things are, how to use them, what a reading means. Or describe a "
               "trading idea in plain words and get step-by-step help building and testing it in Angstrom Lattice. "
               "It explains; you do the clicks. No buy or sell calls.")
    provider = ai_providers.pick("navigator", provider)
    if not ai_providers.available(provider):
        st.info("The AI Navigator isn't switched on yet: it needs an AI key in the app's settings "
                "(ANTHROPIC_API_KEY on Render for Claude).")
        return
    if provider != "claude":
        st.caption(f"Answering with {ai_providers.label(provider)}, your choice in Settings.")
    chat = st.session_state.setdefault("advisor_chat", [])
    day = time.strftime("%Y-%m-%d")
    extra = ""
    snap = None
    if start == "tides":
        import navigator
        import tides

        snap = tides.latest(supabase)
        extra = (navigator.TIDES_RULES + "\n\n" + navigator.tides_context(snap) + "\n\n"
                 + navigator.portfolio_context(supabase, user_id, watchlist))
        if auto == "passage" and not st.session_state.get("_passage_shown"):
            st.session_state["_passage_shown"] = True
            with st.spinner("Charting today's passage…"):
                try:
                    plan = navigator.passage_plan(st, supabase, user_id, watchlist, snap, provider=provider)
                    chat.extend([{"role": "user", "content": "📜 Today's AI Passage Plan"},
                                 {"role": "assistant", "content": plan}])
                except Exception as exc:
                    st.error(f"The AI Navigator couldn't write the passage plan just now ({str(exc)[:200]}).")
    used = st.session_state.setdefault("advisor_used", {}).get(day, 0)
    for m in chat:
        with st.chat_message(m["role"], avatar="🧑" if m["role"] == "user" else ":material/auto_awesome:"):
            _show_images(st, m.get("images"))
            st.markdown(m["content"])
    if not chat:
        if start == "app":
            st.markdown("Try: *“Where do I change which emails I get?”* or *“What does a Stretch of +60 mean?”*")
        elif start == "tides":
            st.markdown("Try: *“Why is the tide going out?”* or *“What is pulling against crypto longs right now?”* "
                        "or *“Which of my funnel Candidates face a headwind?”*")
        else:
            st.markdown("Try: *“I think price often drops a few days after a breakout on heavy volume fizzles out. "
                        "How do I check that?”*")
    images = _paste_box(st)              # outside the form: adding a picture must not count as pressing Ask
    with st.form("advisor_form", clear_on_submit=True, border=False):
        question = st.text_area("Your question", key="advisor_q", height=90, label_visibility="collapsed",
                                placeholder="Ask about the app, an idea, a Set, or a result…")
        cols = st.columns([1, 1, 3])
        sent = cols[0].form_submit_button("Ask", type="primary", icon=":material/send:", width="stretch")
        fresh = cols[1].form_submit_button("New chat", icon=":material/refresh:", width="stretch")
    if fresh:
        st.session_state["advisor_chat"] = []
        import lattice_panel

        lattice_panel.rerun(st)
    if sent and not question.strip() and images:
        st.warning("Add a question to go with the screenshot, such as “what am I looking at here?”")
    if sent and question.strip():
        if used >= DAILY_LIMIT:
            st.warning(f"That's {DAILY_LIMIT} questions today: the Navigator is resting until tomorrow.")
            return
        cached = st.session_state.get("siggroups_saved")
        if not cached or time.time() - cached[0] > 60:
            cached = (time.time(), *gi.saved_configs(supabase))
            st.session_state["siggroups_saved"] = cached
        with st.spinner("Thinking…"):
            try:
                answer = ask(chat, question.strip()[:4000], system_parts(cached[1] or [], user_id, start, extra),
                             images=images, provider=provider)
            except Exception as exc:
                st.error(f"The Navigator couldn't answer just now ({str(exc)[:200]}).")
                return
        chat.extend([{"role": "user", "content": question.strip(), "images": images[:MAX_IMAGES]},
                     {"role": "assistant", "content": answer}])
        st.session_state["advisor_cleared"] = st.session_state.get("advisor_cleared", 0) + 1   # empty the box
        st.session_state["advisor_used"][day] = used + 1
        import lattice_panel

        lattice_panel.rerun(st)
