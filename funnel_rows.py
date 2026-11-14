"""
🔻 The funnel list above the crypto and equity tables (Dynamic funnel), 14 Nov 2026.

One row per funnel of that market: its direction and name, then a chip per stage with how many assets hold it
(👁 332 › 🔷 2 › 📋 0 › 🚩 0 › ✅ 0), when it was last checked, and icon actions (⏸/▶ pause or resume, ↻ restart,
✏️ edit in Lattice → Funnels). One chip is picked across all funnels; its assets fill the table below.
Deleting a funnel is only in the Lattice editor.

The box sends {kind: "pick", funnel, stage} or {kind: "act", action: "pause"|"resume"|"restart"|"edit", funnel}
through the "go" trigger.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import funnel as fn

CSS = """
.angfr{font:13px/1.35 inherit;color:inherit;container-type:inline-size;margin:2px 0 4px}
.angfr .list{display:flex;flex-direction:column;gap:6px;max-height:236px;overflow-y:auto;padding:1px 2px 1px 1px}
.angfr .frow{display:flex;align-items:center;gap:10px;padding:6px 10px;border-radius:10px;
  border:1px solid rgba(127,127,127,.25);background:rgba(127,127,127,.05);min-height:30px}
.angfr .frow.on{border-color:rgba(15,118,110,.6);background:rgba(15,118,110,.07)}
.angfr .frow.paused{opacity:.62}
.angfr .name{flex:0 1 210px;min-width:110px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.angfr .dir{font-weight:700;margin-right:5px}
.angfr .dir.long{color:#16a34a}.angfr .dir.short{color:#dc2626}
.angfr .chips{display:flex;flex-wrap:wrap;align-items:center;gap:3px;flex:1 1 auto}
.angfr .sep{opacity:.4;padding:0 1px}
.angfr .chip{font:inherit;color:inherit;border:1px solid rgba(127,127,127,.35);background:transparent;border-radius:999px;
  padding:2px 9px;cursor:pointer;white-space:nowrap;position:relative;font-variant-numeric:tabular-nums}
.angfr .chip:hover{border-color:#0f766e}
.angfr .chip.sel{border-color:#0f766e;background:rgba(15,118,110,.22);font-weight:700}
.angfr .chip.empty{opacity:.38;cursor:default}
.angfr .chip.empty:hover{border-color:rgba(127,127,127,.35)}
.angfr .new{position:absolute;top:-7px;right:-6px;font-size:10px;line-height:1;padding:2px 4px;border-radius:999px;
  background:#0f766e;color:#fff;font-weight:700}
.angfr .meta{opacity:.62;font-size:12px;white-space:nowrap}
.angfr .acts{display:flex;gap:2px;margin-left:auto}
.angfr .act{font:inherit;color:inherit;border:1px solid transparent;background:transparent;border-radius:8px;
  width:30px;height:28px;cursor:pointer;font-size:15px;line-height:1}
.angfr .act:hover{border-color:rgba(127,127,127,.45);background:rgba(127,127,127,.1)}
.angfr .act.arm{border-color:#dc2626;background:rgba(220,38,38,.14)}
@container (max-width: 620px){
  .angfr .list{max-height:330px}
  .angfr .frow{flex-wrap:wrap;row-gap:6px}
  .angfr .name{order:1;flex:1 1 auto}
  .angfr .acts{order:2}
  .angfr .chips{order:3;flex:1 1 100%}
  .angfr .meta{order:4;flex:1 1 100%}
}
"""

JS = r"""
export default function angFunnelRows(component) {
  const { data, setTriggerValue, parentElement } = component;
  const d = data || {};
  Array.from(parentElement.children).forEach((c) => { if (c.classList && c.classList.contains("angfr")) c.remove(); });
  const root = document.createElement("div");
  root.className = "angfr";
  parentElement.appendChild(root);
  const list = document.createElement("div");
  list.className = "list";
  root.appendChild(list);
  const send = (body) => setTriggerValue("go", JSON.stringify({ ...body, nonce: Date.now() + Math.random() }));
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const sel = d.selected || {};
  let selectedRow = null;

  (d.rows || []).forEach((r) => {
    const row = el("div", "frow" + (r.paused ? " paused" : "") + (String(r.id) === String(sel.funnel) ? " on" : ""));
    const name = el("div", "name");
    const dir = el("span", "dir " + (r.direction || ""), r.dir_icon || "");
    dir.title = r.direction === "short" ? "Short funnel" : "Long funnel";
    name.appendChild(dir);
    name.appendChild(document.createTextNode(r.name));
    name.title = r.name + (r.paused ? " (paused)" : "");
    row.appendChild(name);

    const chips = el("div", "chips");
    (r.chips || []).forEach((c, i) => {
      if (i) chips.appendChild(el("span", "sep", "›"));
      const picked = String(r.id) === String(sel.funnel) && c.key === sel.stage;
      const empty = !c.count && !picked;
      const b = el("button", "chip" + (picked ? " sel" : "") + (empty ? " empty" : ""), c.icon + " " + c.count);
      b.type = "button";
      b.title = c.label + ": " + c.count + (c.hover ? " · " + c.hover : "") + (c.new ? " · " + c.new + " new since your last visit" : "");
      if (c.new) b.appendChild(el("span", "new", "+" + c.new));
      if (!empty && !picked) b.onclick = () => send({ kind: "pick", funnel: r.id, stage: c.key });
      chips.appendChild(b);
    });
    row.appendChild(chips);
    if (r.checked) row.appendChild(el("div", "meta", r.checked));

    const acts = el("div", "acts");
    const act = (icon, tip, onClick) => { const b = el("button", "act", icon); b.type = "button"; b.title = tip; b.onclick = onClick; acts.appendChild(b); return b; };
    if (r.paused) act("▶", "Resume: check this funnel again every hour", () => send({ kind: "act", action: "resume", funnel: r.id }));
    else act("⏸", "Pause: stop checking this funnel; it keeps its places until resumed", () => send({ kind: "act", action: "pause", funnel: r.id }));
    const again = act("↻", "Start again: every asset goes back to the pool and is checked from the first stage", () => {
      if (again.classList.contains("arm")) { send({ kind: "act", action: "restart", funnel: r.id }); return; }
      again.classList.add("arm");
      again.title = "Press again to start this funnel again from the pool";
      setTimeout(() => { again.classList.remove("arm"); again.title = "Start again: every asset goes back to the pool and is checked from the first stage"; }, 4000);
    });
    act("✏️", "Edit in Lattice → Funnels (delete it there too)", () => send({ kind: "act", action: "edit", funnel: r.id }));
    row.appendChild(acts);
    list.appendChild(row);
    if (row.classList.contains("on")) selectedRow = row;
  });
  if (selectedRow && list.scrollHeight > list.clientHeight) {
    list.scrollTop = Math.max(0, selectedRow.offsetTop - list.offsetTop - 4);
  }
  return () => root.remove();
}
"""

_COMPONENT = None


def component():
    global _COMPONENT
    if _COMPONENT is None:
        import streamlit as st

        _COMPONENT = st.components.v2.component("angstrom_funnel_rows", js=JS, css=CSS)
    return _COMPONENT


def ago(ts, now: datetime | None = None) -> str:
    """'checked 12 min ago' from a run's finish time (ISO text); '' when there is none."""
    if not ts:
        return ""
    try:
        when = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    mins = max(0, int(((now or datetime.now(timezone.utc)) - when).total_seconds() // 60))
    if mins < 1:
        return "checked just now"
    if mins < 60:
        return f"checked {mins} min ago"
    if mins < 48 * 60:
        return f"checked {mins // 60} h ago"
    return f"checked {mins // 1440} days ago"


def last_checked(runs: list) -> str | None:
    """The latest finish time among a funnel's stage runs."""
    times = [r.get("finished_at") for r in runs or [] if r and r.get("finished_at")]
    return max(times) if times else None


def chips(f: dict, states: dict, new: int = 0, hover: dict | None = None) -> list[dict]:
    """The stage chips of one funnel, widest first: each stage reached, then Flagged and Candidates (and Pending)."""
    k = fn.counts(states, len(f["stages"]))
    hover = hover or {}
    out = []
    for i, stage in enumerate(f["stages"][:-1]):
        out.append({"key": f"stage:{i}", "icon": fn.STAGE_ICONS[min(i, len(fn.STAGE_ICONS) - 1)],
                    "label": stage["label"], "count": k["reached"][i]})
    out.append({"key": "flagged", "icon": "🚩", "label": "Flagged", "count": k["flagged"],
                "hover": hover.get("flagged", "")})
    out.append({"key": "candidate", "icon": "✅", "label": "Candidates", "count": k["candidate"],
                "hover": hover.get("candidate", ""), "new": int(new or 0)})
    if k["pending"]:
        out.append({"key": "pending", "icon": "❔", "label": "Pending (no answer yet)", "count": k["pending"]})
    return out


def order(rows: list[dict]) -> list[dict]:
    """Paused funnels last; otherwise as saved."""
    return sorted(rows, key=lambda r: bool(r.get("paused")))


def default_pick(rows: list[dict]) -> tuple[str, str] | None:
    """(funnel id, stage) to show first: the first running funnel with Candidates, else the first funnel's narrowest
    stage before Candidates."""
    if not rows:
        return None
    for r in rows:
        if not r.get("paused") and any(c["key"] == "candidate" and c["count"] for c in r["chips"]):
            return r["id"], "candidate"
    first = rows[0]
    stages = [c["key"] for c in first["chips"] if c["key"].startswith("stage:")]
    return first["id"], (stages[-1] if stages else "candidate")


def read_event(result, seen_key: str, state) -> dict | None:
    """The latest press in the list, once (None when nothing new)."""
    raw = getattr(result, "go", None)
    if not raw or raw == state.get(seen_key):
        return None
    state[seen_key] = raw
    try:
        event = json.loads(raw)
    except ValueError:
        return None
    if event.get("kind") == "pick" and event.get("funnel") is not None and event.get("stage"):
        return event
    if event.get("kind") == "act" and event.get("action") in ("pause", "resume", "restart", "edit"):
        return event
    return None
