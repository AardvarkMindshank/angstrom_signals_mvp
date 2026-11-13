"""
🔔 The alert settings for one reading (Trend, Stretch or Flow): the five colour boxes the tables use, from strongly
bearish to strongly bullish, with tick boxes on each border between them, ▲ for a rise across it and ▼ for a fall,
plus the two flips (one side straight to the other between two closes). alerts.CROSSINGS names each tick.

The board only draws and reports: a tick sends the whole list of ticks to Python ({ticks, nonce}), which saves it in
the account settings ("<reading>_crossings"). On a narrow screen the boxes stack, strongly bullish on top.
"""

from __future__ import annotations

import json

CSS = """
.ab{font:13px/1.35 inherit;color:inherit;margin:2px 0 6px}
.ab .line{display:flex;align-items:stretch;gap:0}
.ab .zone{flex:1 1 0;min-width:0;border-radius:8px;padding:8px 6px;text-align:center;display:flex;flex-direction:column;
  justify-content:center;gap:2px}
.ab .zone b{font-size:12.5px;line-height:1.2}
.ab .zone span{font-size:11px;opacity:.8}
.ab .border{flex:0 0 54px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;
  padding:0 2px}
.ab .border .num{font-size:11px;font-weight:600;opacity:.75}
.ab label.tick{display:flex;align-items:center;gap:3px;font-size:12.5px;border:1px solid rgba(127,127,127,.45);border-radius:999px;
  padding:2px 7px;cursor:pointer;user-select:none;background:rgba(127,127,127,.06);white-space:nowrap}
.ab label.tick.on{border-color:#0f766e;background:rgba(15,118,110,.14)}
.ab label.tick input{margin:0;width:14px;height:14px;accent-color:#0f766e;cursor:pointer}
.ab .flips{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:8px}
.ab .flips .what{font-size:12px;opacity:.8}
@media (max-width:560px){
  .ab .line{flex-direction:column-reverse}
  .ab .border{flex:0 0 auto;flex-direction:row;padding:4px 0;gap:8px}
  .ab .zone{flex:0 0 auto;padding:6px 8px}
  .ab label.tick{padding:6px 12px}
}
"""

JS = r"""
export default function alertBands(component) {
  const { data, setTriggerValue, parentElement } = component;
  const d = data || {};
  Array.from(parentElement.children).forEach((c) => { if (c.classList && c.classList.contains("ab")) c.remove(); });
  const root = document.createElement("div");
  root.className = "ab";
  parentElement.appendChild(root);
  const ticks = new Set(d.ticks || []);
  const send = () => setTriggerValue("change", JSON.stringify({ticks: Array.from(ticks), nonce: Date.now() + Math.random()}));
  const tick = (key, icon, tip) => {
    const lab = document.createElement("label");
    lab.className = "tick" + (ticks.has(key) ? " on" : "");
    lab.title = tip;
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = ticks.has(key);
    box.setAttribute("aria-label", tip);
    box.addEventListener("change", () => {
      if (box.checked) ticks.add(key); else ticks.delete(key);
      lab.classList.toggle("on", box.checked);
      send();
    });
    lab.appendChild(box);
    lab.appendChild(document.createTextNode(icon));
    return lab;
  };
  const line = document.createElement("div");
  line.className = "line";
  (d.zones || []).forEach((z, i) => {
    const box = document.createElement("div");
    box.className = "zone";
    box.style.background = z.bg;
    box.style.color = z.fg;
    box.title = z.tip;
    const name = document.createElement("b");
    name.textContent = z.name;
    const range = document.createElement("span");
    range.textContent = z.range;
    box.appendChild(name);
    box.appendChild(range);
    line.appendChild(box);
    const b = (d.borders || [])[i];
    if (!b) return;
    const cell = document.createElement("div");
    cell.className = "border";
    const num = document.createElement("div");
    num.className = "num";
    num.textContent = b.label;
    cell.appendChild(tick(b.up.key, "▲", b.up.tip));
    cell.appendChild(num);
    cell.appendChild(tick(b.down.key, "▼", b.down.tip));
    line.appendChild(cell);
  });
  root.appendChild(line);
  const flips = document.createElement("div");
  flips.className = "flips";
  const what = document.createElement("span");
  what.className = "what";
  what.textContent = d.flips_label || "";
  flips.appendChild(what);
  (d.flips || []).forEach((f) => flips.appendChild(tick(f.key, f.icon, f.tip)));
  root.appendChild(flips);
  return () => root.remove();
}
"""

_COMPONENT = None


def component():
    global _COMPONENT
    if _COMPONENT is None:
        import streamlit as st

        _COMPONENT = st.components.v2.component("alert_bands", js=JS, css=CSS)
    return _COMPONENT


def board_data(reading: str, ticks) -> dict:
    """What the board draws for one reading: its five zones (weakest first, left to right), the four borders with
    their rise and fall ticks, the flips, and which are ticked."""
    import alerts as al
    import signals_v2
    from score_colours import STEPS

    name = al.READING_ALERTS[reading]["name"]
    words = signals_v2.CLUSTER_WORDS[reading]                      # strongest up first
    steps = ("strong_down", "down", "mixed", "up", "strong_up")
    ranges = ("−50 or below", "−50 to −20", "−20 to +20", "+20 to +50", "+50 or above")
    zones = [{"name": words[4 - i], "range": ranges[i], "fg": STEPS[s][0], "bg": STEPS[s][1],
              "tip": f"{name} {ranges[i]}: {words[4 - i].lower()}."} for i, s in enumerate(steps)]
    borders = []
    for i, (code, value) in enumerate(al.BORDERS):
        below, above = words[4 - i].lower(), words[3 - i].lower()
        borders.append({
            "label": f"{value:+d}".replace("-", "−"),
            "up": {"key": f"up_{code}",
                   "tip": f"▲ Alert when {name} rises past {value:+d}: from {below} into {above}."},
            "down": {"key": f"dn_{code}",
                     "tip": f"▼ Alert when {name} falls past {value:+d}: from {above} into {below}."},
        })
    flips = [{"key": "flip_up", "icon": "⇧ to the up side",
              "tip": f"Alert when {name} jumps from the down side straight to the up side between two daily "
                     "closes (one alert, not one per border)."},
             {"key": "flip_dn", "icon": "⇩ to the down side",
              "tip": f"Alert when {name} jumps from the up side straight to the down side between two daily "
                     "closes (one alert, not one per border)."}]
    return {"zones": zones, "borders": borders, "flips": flips, "flips_label": "Flips:",
            "ticks": [k for k in ticks if k in al.CROSSINGS]}


def read_change(result, seen_key: str, state) -> list[str] | None:
    """The new tick list from a press, once (None when nothing new was pressed)."""
    raw = getattr(result, "change", None)
    if not raw or raw == state.get(seen_key):
        return None
    state[seen_key] = raw
    try:
        import alerts as al

        return [k for k in json.loads(raw).get("ticks") or [] if k in al.CROSSINGS]
    except (ValueError, AttributeError):
        return None
