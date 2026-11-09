"""
✨ AI Advisor, phase 0: explains in plain words how to build an idea in Lattice, and answers follow-up questions.

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
MODEL = "claude-sonnet-5-5"            # fast and capable; a model choice in Settings comes later
MAX_TOKENS = 1600
MAX_TURNS = 12                         # earlier turns are dropped from what is sent, oldest first
DAILY_LIMIT = 60                       # questions per person per day (this browser session's count)

RULES = """You are the AI Advisor inside Angstrom Signals, a market research app for traders, in its research
workspace called Angstrom Lattice. You help one person turn a trading idea into the app's building blocks and
understand the results. You only explain: you never claim to have built, saved, run or changed anything, because
you cannot. The person does every click, following your steps.

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
  AI Advisor, open in your own window from the ✨ AI button beside those tabs, so the person can follow your steps
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
            out.append(f"- Set “{c['name']}” (v{v}): {inside['decision'] or 'no decision yet'}"
                       + (f" What followed: {card['verdict']}" if card else ""))
        else:
            members = ", ".join(m.get("label") or m["ref"]["id"] for m in body.get("members") or [])
            out.append(f"- Group “{c['name']}” (v{v}): signals {members}")
    return out or ["(none saved yet)"]


def system_prompt(saved: list[dict], user_id: str) -> str:
    return "\n".join([RULES, "Signals (name, readings and their ranges):", *_signals(), "", *_provided(), "",
                      "The person's own Groups and Sets:", *_mine(saved, user_id)])


def ask(history: list[dict], question: str, system: str, post=requests.post) -> str:
    """The Advisor's answer to `question`, given the conversation so far ([{role, content}])."""
    key = api_key()
    if not key:
        raise RuntimeError("The AI Advisor needs ANTHROPIC_API_KEY in the app's environment.")
    messages = [m for m in history if m.get("role") in ("user", "assistant")][-2 * MAX_TURNS:]
    messages = messages + [{"role": "user", "content": question}]
    response = post(API_URL, timeout=90, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        data=json.dumps({"model": MODEL, "max_tokens": MAX_TOKENS, "system": system, "messages": messages}))
    if response.status_code != 200:
        try:
            detail = response.json().get("error", {}).get("message", "")
        except ValueError:
            detail = response.text[:200]
        raise RuntimeError(f"The AI service answered {response.status_code}: {detail[:200]}")
    data = response.json()
    return "".join(part.get("text", "") for part in data.get("content") or [] if part.get("type") == "text").strip()


# ----------------------------------------------------------------------------------------------- the tab

def render(st, supabase, user_id: str = "") -> None:
    import time

    import signal_groups_inspector as gi

    st.caption("Describe a trading idea in plain words. The Advisor explains how to build it from Groups, signals "
               "and Sets, and how to test it; you do the clicks. It explains, it doesn't advise: no buy or sell "
               "calls.")
    if not available():
        st.info("The AI Advisor isn't switched on yet: it needs an Anthropic API key in the app's settings "
                "(ANTHROPIC_API_KEY on Render).")
        return
    chat = st.session_state.setdefault("advisor_chat", [])
    day = time.strftime("%Y-%m-%d")
    used = st.session_state.setdefault("advisor_used", {}).get(day, 0)
    for m in chat:
        with st.chat_message(m["role"], avatar="🧑" if m["role"] == "user" else ":material/auto_awesome:"):
            st.markdown(m["content"])
    if not chat:
        st.markdown("Try: *“I think price often drops a few days after a breakout on heavy volume fizzles out. How "
                    "do I check that?”*")
    with st.form("advisor_form", clear_on_submit=True, border=False):
        question = st.text_area("Your question", key="advisor_q", height=90, label_visibility="collapsed",
                                placeholder="Ask about an idea, a Set, a result, or how to build something…")
        cols = st.columns([1, 1, 3])
        sent = cols[0].form_submit_button("Ask", type="primary", icon=":material/send:", width="stretch")
        fresh = cols[1].form_submit_button("New chat", icon=":material/refresh:", width="stretch")
    if fresh:
        st.session_state["advisor_chat"] = []
        import lattice_panel

        lattice_panel.rerun(st)
    if sent and question.strip():
        if used >= DAILY_LIMIT:
            st.warning(f"That's {DAILY_LIMIT} questions today: the Advisor is resting until tomorrow.")
            return
        cached = st.session_state.get("siggroups_saved")
        if not cached or time.time() - cached[0] > 60:
            cached = (time.time(), *gi.saved_configs(supabase))
            st.session_state["siggroups_saved"] = cached
        with st.spinner("Thinking…"):
            try:
                answer = ask(chat, question.strip()[:4000], system_prompt(cached[1] or [], user_id))
            except Exception as exc:
                st.error(f"The Advisor couldn't answer just now ({str(exc)[:200]}).")
                return
        chat.extend([{"role": "user", "content": question.strip()}, {"role": "assistant", "content": answer}])
        st.session_state["advisor_used"][day] = used + 1
        import lattice_panel

        lattice_panel.rerun(st)
