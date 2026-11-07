"""
The Lattice Group editor's browser component (docs/design/lattice_prism.md §7, build stage 4).

It draws the editor and sends the edited model back as one JSON string ("model"). It decides nothing: Python
(lattice_editor.py) cleans the model, checks it with the engine's validator, writes the description and sends
everything back to be drawn. Drag and drop for mouse users, a + button for touch screens. All text from the page
is inserted with textContent, never as HTML.
"""

from __future__ import annotations

CSS = """
.lat{font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;color:inherit;display:flex;flex-wrap:wrap;gap:14px}
.lat *{box-sizing:border-box}
.lat .col{background:rgba(127,127,127,.06);border:1px solid rgba(127,127,127,.25);border-radius:12px;padding:12px}
.lat .lib{flex:1 1 240px;max-width:300px;max-height:760px;overflow:auto}
.lat .mid{flex:999 1 480px;min-width:0;display:flex;flex-direction:column;gap:14px}
.lat .cat{font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.7;margin:10px 0 4px}
.lat .chip{display:flex;align-items:center;gap:8px;padding:6px 6px 6px 10px;margin-bottom:4px;border-radius:8px;
  border:1px solid rgba(127,127,127,.3);background:rgba(127,127,127,.06);cursor:grab}
.lat .chip .nm{flex:1 1 auto;min-width:0}
.lat .badge{font-size:11px;color:#b7791f}
.lat button{font:inherit;cursor:pointer;border-radius:8px;border:1px solid rgba(127,127,127,.4);
  background:transparent;color:inherit;min-height:36px;padding:4px 10px}
.lat button:disabled{opacity:.4;cursor:not-allowed}
.lat button.on{background:#0f766e;border-color:#0f766e;color:#fff;font-weight:600}
.lat button.sq{width:36px;height:36px;min-height:36px;padding:0;flex:0 0 36px;align-self:center}
.lat .chip:has(details[open])>button.sq{align-self:flex-start;margin-top:4px}
.lat input,.lat select{font:inherit;color:inherit;background:rgba(127,127,127,.08);border:1px solid rgba(127,127,127,.4);
  border-radius:8px;padding:6px 8px;min-height:36px}
.lat input.wide{width:100%}
.lat .drop{border:2px dashed rgba(127,127,127,.45);border-radius:12px;padding:10px;min-height:120px;
  display:flex;flex-direction:column;gap:8px}
.lat .drop.over{border-color:#0f766e;background:rgba(15,118,110,.08)}
.lat .card{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:8px 10px;border-radius:10px;
  border:1px solid rgba(127,127,127,.3);background:rgba(127,127,127,.05)}
.lat .card .nm{flex:1 1 160px;min-width:0;font-weight:600}
.lat .muted{opacity:.72;font-size:12px}
.lat .pv{display:inline-flex;gap:2px;margin-left:6px;font-size:13px;vertical-align:middle}
.lat .pv span{cursor:help}
.lat .tag{font-size:11px;padding:2px 8px;border-radius:999px;border:1px solid rgba(127,127,127,.4);
  font-family:ui-monospace,monospace;opacity:.85}
.lat .grip{cursor:grab;touch-action:none;user-select:none;font-size:20px;line-height:1;padding:6px 4px;opacity:.6;
  min-width:24px;text-align:center}
.lat .grip:active{cursor:grabbing}
.lat .rule.dragging{position:relative;z-index:5;box-shadow:0 6px 18px rgba(0,0,0,.25);opacity:.95}
.lat .rule{transition:transform .12s}
.lat .rule.dragging{transition:none}
.lat .clause{display:flex;flex-wrap:wrap;align-items:center;gap:6px;flex-basis:100%;min-width:0;max-width:100%}
.lat .clause>select{min-width:0;max-width:100%;flex:0 1 auto}
.lat .clause>select:first-of-type{flex:1 1 8em;width:0}
.lat button.del{color:#dc2626;border-color:rgba(220,38,38,.45)}
.lat .rule{display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:8px;border-radius:10px;
  background:rgba(127,127,127,.07);margin-bottom:8px}
.lat .num{width:28px;height:28px;border-radius:999px;border:1px solid rgba(127,127,127,.4);display:inline-flex;
  align-items:center;justify-content:center;font-family:ui-monospace,monospace}
.lat .lbl{font-weight:600;padding:4px 8px;border-radius:6px;background:rgba(15,118,110,.12)}
.lat .fixed{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:8px;border-radius:10px;
  border:1px dashed rgba(127,127,127,.45);margin-bottom:8px}
.lat h3{font-size:14px;margin:0 0 8px}
.lat .hd{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:8px}
.lat .hd h3{margin:0}
.lat details.prov{border:1px solid rgba(127,127,127,.3);border-radius:10px;padding:4px 8px;margin:6px 0 8px;
  background:rgba(127,127,127,.04)}
.lat details.prov>summary{cursor:pointer;font-size:12px;letter-spacing:.04em;opacity:.8;padding:6px 0;min-height:28px}
@media (max-width:640px){.lat .lib{max-width:none;flex-basis:100%;max-height:380px}.lat .mid{flex-basis:100%}}
"""

JS = r"""
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const state = data || {};
  const catalogue = state.catalogue || [];
  const byId = {};
  catalogue.forEach((s) => { byId[s.id] = s; });
  let model = JSON.parse(JSON.stringify(state.model || {members: [], rules: [], otherwise: {id: "neutral", label: "Neutral"}}));
  let query = (window.__latQuery || "");

  Array.from(parentElement.children).filter((c) => c.classList && c.classList.contains("lat")).forEach((c) => c.remove());
  const root = el("div", "lat");
  parentElement.appendChild(root);

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }
  function button(text, title, onClick, cls) {
    const b = el("button", cls || "", text);
    b.type = "button";
    if (title) { b.title = title; b.setAttribute("aria-label", title); }
    b.addEventListener("click", onClick);
    return b;
  }
  function send() { setTriggerValue("model", JSON.stringify(model)); }
  function slug(text) {
    let s = String(text || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 24);
    if (!s) s = "label";
    if (!/^[a-z]/.test(s)) s = ("l_" + s).slice(0, 24);
    return s;
  }
  function memberKey(id, tf) {
    const base = (id.split(".")[0] + "_" + id.split(".").slice(-1)[0] + "_" + tf).toLowerCase().replace(/[^a-z0-9_]/g, "_").slice(0, 36);
    let key = base, n = 2;
    const taken = new Set((model.members || []).map((m) => m.key));
    while (taken.has(key)) { key = base + "_" + n; n += 1; }
    return key;
  }
  function addSignal(id) {
    const s = byId[id];
    if (!s) return;
    const tf = s.timeframes.indexOf("1D") >= 0 ? "1D" : s.timeframes[0];
    model.members = model.members || [];
    model.members.push({key: memberKey(id, tf), id: s.id, version: s.version, timeframe: tf,
                        role: s.can_score ? "score" : "condition"});
    send();
  }

  // ---------------------------------------------------------------- library
  const lib = el("div", "col lib");
  root.appendChild(lib);
  lib.appendChild(el("h3", "", "Signals"));
  lib.appendChild(el("div", "muted", "Drag a signal into the Group, or tap + (works on iPad). Hover for what it measures."));
  const search = el("input", "wide");
  search.placeholder = "Search: RSI, volume, sentiment…";
  search.value = query;
  search.setAttribute("aria-label", "Search signals");
  lib.appendChild(search);
  const list = el("div");
  lib.appendChild(list);
  function drawLibrary() {
    list.replaceChildren();
    const q = query.toLowerCase();
    let last = null;
    catalogue.filter((s) => !q || s.name.toLowerCase().indexOf(q) >= 0 || s.category_label.toLowerCase().indexOf(q) >= 0)
      .forEach((s) => {
        if (s.category_label !== last) { list.appendChild(el("div", "cat", s.category_label)); last = s.category_label; }
        const chip = el("div", "chip");
        chip.draggable = true;
        chip.title = s.hint;
        chip.addEventListener("dragstart", (e) => { e.dataTransfer.setData("text/plain", s.id); });
        const nm = el("div", "nm");
        nm.appendChild(el("div", "", s.name));
        if (s.badge) nm.appendChild(el("div", "badge", s.badge));
        if (!s.can_score) nm.appendChild(el("div", "muted", "condition only"));
        chip.appendChild(nm);
        chip.appendChild(button("+", "Add " + s.name + " to the Group", () => addSignal(s.id), "sq"));
        list.appendChild(chip);
      });
  }
  search.addEventListener("input", () => { query = search.value; window.__latQuery = query; drawLibrary(); });
  drawLibrary();

  // ---------------------------------------------------------------- group
  const mid = el("div", "mid");
  root.appendChild(mid);
  const group = el("div", "col");
  mid.appendChild(group);
  const head = el("div", "hd");
  const name = el("input", "wide");
  name.value = model.name || "";
  name.placeholder = "Group name";
  name.setAttribute("aria-label", "Group name");
  name.addEventListener("change", () => { model.name = name.value; send(); });
  head.appendChild(name);
  group.appendChild(head);
  const question = el("input", "wide");
  question.value = model.question || "";
  question.placeholder = "The question it answers (optional), e.g. Is the trend up and not overstretched?";
  question.setAttribute("aria-label", "Question");
  question.addEventListener("change", () => { model.question = question.value; send(); });
  group.appendChild(question);

  const drop = el("div", "drop");
  drop.style.marginTop = "10px";
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); addSignal(e.dataTransfer.getData("text/plain")); });
  group.appendChild(drop);
  const ROLE_TITLES = state.role_hints || {};
  if (!(model.members || []).length) drop.appendChild(el("div", "muted", "Drag signals here, or tap + in the list."));
  (model.members || []).forEach((m, i) => {
    const s = byId[m.id] || {name: m.id, timeframes: [m.timeframe], can_score: false};
    const card = el("div", "card");
    const nm = el("div", "nm", s.name);
    nm.title = s.hint || "";
    card.appendChild(nm);
    const tf = el("select");
    tf.setAttribute("aria-label", "Timeframe of " + s.name);
    tf.title = "Timeframe this member is read on (always its last closed candle)";
    s.timeframes.forEach((t) => { const o = el("option", "", t); o.value = t; if (t === m.timeframe) o.selected = true; tf.appendChild(o); });
    tf.addEventListener("change", () => { m.timeframe = tf.value; send(); });
    card.appendChild(tf);
    const tag = el("span", "tag", (state.member_tags || {})[m.key] || ((m.timeframe || "") + " · last closed candle"));
    tag.title = "What this member is read from. The candle still forming is never used.";
    card.appendChild(tag);
    ["score", "condition", "levels", "context"].forEach((r) => {
      const label = r.charAt(0).toUpperCase() + r.slice(1);
      const b = button(label, ROLE_TITLES[r] || label, () => { m.role = r; send(); }, m.role === r ? "on" : "");
      b.setAttribute("aria-pressed", m.role === r ? "true" : "false");
      if (r === "score" && !s.can_score) { b.disabled = true; b.title = s.name + " has no standard score: use it as a Condition."; }
      card.appendChild(b);
    });
    card.appendChild(button("✕", "Remove " + s.name, () => { model.members.splice(i, 1); send(); }, "sq del"));
    drop.appendChild(card);
  });

  // ---------------------------------------------------------------- rules
  const rules = el("div", "col");
  mid.appendChild(rules);
  const rh = el("div", "hd");
  rh.appendChild(el("h3", "", "Rules: what the Group says"));
  rh.appendChild(el("span", "muted", "Checked top to bottom · first match wins · drag ⠿ to reorder"));
  rules.appendChild(rh);
  const operands = state.operands || [];
  const opByKey = {};
  operands.forEach((o) => { opByKey[o.key] = o; });
  const OPS = {number: [["gte", "is at least"], ["lte", "is at most"]], "yes/no": [["yes", "is yes"], ["no", "is no"]],
               label: [["is", "is"], ["is_not", "is not"]]};
  // Reorder rules by dragging the ⠿ handle (mouse, pen or finger): the rows move apart to show where it will land.
  function dragHandle(row, from) {
    const h = el("span", "grip", "⠿");
    h.title = "Drag to check this rule earlier or later";
    h.setAttribute("aria-label", "Drag to reorder rule " + (from + 1));
    h.setAttribute("role", "button"); h.tabIndex = 0;
    h.addEventListener("keydown", (e) => {          // keyboard: arrow keys move it one place
      const to = e.key === "ArrowUp" ? from - 1 : e.key === "ArrowDown" ? from + 1 : -1;
      if (to < 0 || to >= model.rules.length) return;
      e.preventDefault(); const [m] = model.rules.splice(from, 1); model.rules.splice(to, 0, m); send();
    });
    h.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      h.setPointerCapture(e.pointerId);
      const rows = [...rules.querySelectorAll(":scope > .rule")];
      const mids = rows.map((x) => { const b = x.getBoundingClientRect(); return b.top + b.height / 2; });
      const startY = e.clientY;
      let to = from;
      row.classList.add("dragging");
      const move = (ev) => {
        const dy = ev.clientY - startY;
        row.style.transform = "translateY(" + dy + "px)";
        const y = mids[from] + dy;
        to = mids.filter((m, i) => i !== from && m < y).length;
        rows.forEach((x, i) => {
          if (i === from) return;
          const shift = from < to && i > from && i <= to ? -1 : from > to && i < from && i >= to ? 1 : 0;
          x.style.transform = shift ? "translateY(" + shift * (row.offsetHeight + 8) + "px)" : "";
        });
      };
      const up = () => {
        h.removeEventListener("pointermove", move); h.removeEventListener("pointerup", up); h.removeEventListener("pointercancel", up);
        rows.forEach((x) => { x.style.transform = ""; }); row.classList.remove("dragging");
        if (to !== from) { const [m] = model.rules.splice(from, 1); model.rules.splice(to, 0, m); send(); }
      };
      h.addEventListener("pointermove", move); h.addEventListener("pointerup", up); h.addEventListener("pointercancel", up);
    });
    return h;
  }
  (model.rules || []).forEach((r, ri) => {
    const row = el("div", "rule");
    row.dataset.ri = ri;
    if (model.rules.length > 1) row.appendChild(dragHandle(row, ri));
    row.appendChild(el("span", "num", ri + 1));
    const lab = el("input");
    lab.value = r.label; lab.size = 12; lab.title = "The label this rule gives (for example Bullish)";
    lab.setAttribute("aria-label", "Label of rule " + (ri + 1));
    lab.addEventListener("change", () => { r.label = lab.value; r.id = slug(lab.value); send(); });
    row.appendChild(lab);
    row.appendChild(el("span", "muted", "when"));
    (r.clauses || []).forEach((c, ci) => {
      const cl = el("div", "clause");
      row.appendChild(cl);
      if (ci > 0) {
        const j = button(r.joiner === "any" ? "OR" : "AND", "Switch between AND (all must hold) and OR (any may hold)",
                         () => { r.joiner = r.joiner === "any" ? "all" : "any"; send(); });
        cl.appendChild(j);
      }
      cl.appendChild(button("✕", "Remove this condition", () => { r.clauses.splice(ci, 1); send(); }, "sq del"));
      const o = opByKey[c.operand] || {type: "number", scale: "", labels: []};
      const pick = el("select");
      pick.setAttribute("aria-label", "Reading");
      operands.forEach((x) => { const op = el("option", "", x.label); op.value = x.key; if (x.key === c.operand) op.selected = true; pick.appendChild(op); });
      if (!opByKey[c.operand]) { const op = el("option", "", "(removed reading)"); op.value = c.operand; op.selected = true; pick.appendChild(op); }
      pick.addEventListener("change", () => {
        c.operand = pick.value;
        const n = opByKey[c.operand] || {type: "number", labels: []};
        c.op = OPS[n.type] ? OPS[n.type][0][0] : "gte";
        c.value = n.type === "label" ? (n.labels[0] || "") : n.type === "yes/no" ? "" : "";
        send();
      });
      cl.appendChild(pick);
      const ops = el("select");
      ops.setAttribute("aria-label", "Comparison");
      (OPS[o.type] || OPS.number).forEach(([k, t]) => { const op = el("option", "", t); op.value = k; if (k === c.op) op.selected = true; ops.appendChild(op); });
      ops.addEventListener("change", () => { c.op = ops.value; send(); });
      cl.appendChild(ops);
      if (o.type === "number") {
        const v = el("input"); v.value = c.value || ""; v.size = 6; v.setAttribute("aria-label", "Value");
        v.addEventListener("change", () => { c.value = v.value; send(); });
        cl.appendChild(v);
        cl.appendChild(el("span", "muted", o.scale || ""));
      } else if (o.type === "label") {
        const v = el("select"); v.setAttribute("aria-label", "Label");
        (o.labels || []).forEach((l) => { const op = el("option", "", l); op.value = l; if (l === c.value) op.selected = true; v.appendChild(op); });
        v.addEventListener("change", () => { c.value = v.value; send(); });
        cl.appendChild(v);
      }
    });
    row.appendChild(button("+ condition", "Add another condition to this rule",
      () => { r.clauses = r.clauses || []; r.clauses.push({operand: "score", op: "gte", value: "+30"}); send(); }));
    row.appendChild(button("🗑", "Remove this rule", () => { model.rules.splice(ri, 1); send(); }, "sq"));
    rules.appendChild(row);
  });
  const unknown = el("div", "fixed");
  unknown.appendChild(el("span", "lbl", "Unknown"));
  unknown.appendChild(el("span", "", "if a rule cannot be checked because a reading is missing. Later rules are not tried."));
  unknown.title = "Fixed: missing data never becomes a confident label.";
  rules.appendChild(unknown);
  const other = el("div", "fixed");
  const ol = el("input"); ol.value = (model.otherwise || {}).label || "Neutral"; ol.size = 12;
  ol.setAttribute("aria-label", "Label when no rule matches");
  ol.addEventListener("change", () => { model.otherwise = {id: slug(ol.value), label: ol.value}; send(); });
  other.appendChild(ol);
  other.appendChild(el("span", "", "otherwise: every rule was checked and none matched."));
  rules.appendChild(other);
  const add = el("div", "hd");
  const suggest = el("select");
  suggest.setAttribute("aria-label", "Label for a new rule");
  (state.suggested_labels || []).forEach(([id, label]) => { const o = el("option", "", label); o.value = label; suggest.appendChild(o); });
  add.appendChild(suggest);
  add.appendChild(button("+ Add rule", "Add a rule that gives this label",
    () => { model.rules = model.rules || []; model.rules.push({id: slug(suggest.value), label: suggest.value, joiner: "all",
             clauses: [{operand: "score", op: suggest.value.toLowerCase().indexOf("bear") >= 0 || suggest.value.toLowerCase().indexOf("down") >= 0 || suggest.value.toLowerCase().indexOf("sell") >= 0 ? "lte" : "gte",
                        value: suggest.value.toLowerCase().indexOf("bear") >= 0 || suggest.value.toLowerCase().indexOf("down") >= 0 || suggest.value.toLowerCase().indexOf("sell") >= 0 ? "−30" : "+30"}]}); send(); }));
  rules.appendChild(add);

  // ---------------------------------------------------------------- confirmations and vetoes
  const checksBox = el("div", "col");
  mid.appendChild(checksBox);
  const chh = el("div", "hd");
  chh.appendChild(el("h3", "", "Confirmations and vetoes"));
  chh.appendChild(el("span", "muted", "Optional. A confirmation is reported as met or not met; a veto that fires makes every label Vetoed."));
  checksBox.appendChild(chh);
  function slugKey(text) {
    let k = String(text || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 36) || "check";
    const taken = new Set((model.conditions || []).map((c) => c.key));
    let out = k, n = 2;
    while (taken.has(out)) { out = k + "_" + n; n += 1; }
    return out;
  }
  (model.conditions || []).forEach((c, ci) => {
    const row = el("div", "rule");
    ["confirmation", "veto"].forEach((k) => {
      const b = button(k === "veto" ? "⛔ Veto" : "✅ Confirmation", k === "veto" ? "When true, the Group is vetoed." : "Reported as met or not met.",
                       () => { c.kind = k; send(); }, c.kind === k ? "on" : "");
      b.setAttribute("aria-pressed", c.kind === k ? "true" : "false");
      row.appendChild(b);
    });
    const lab = el("input");
    lab.value = c.label || ""; lab.size = 24; lab.setAttribute("aria-label", "Name of this " + c.kind);
    lab.addEventListener("change", () => { c.label = lab.value; send(); });
    row.appendChild(lab);
    row.appendChild(el("span", "muted", "when"));
    (c.clauses || []).forEach((x, xi) => {
      const cl = el("div", "clause");
      row.appendChild(cl);
      if (xi > 0) cl.appendChild(button(c.joiner === "any" ? "OR" : "AND", "Switch between AND and OR",
                                         () => { c.joiner = c.joiner === "any" ? "all" : "any"; send(); }));
      cl.appendChild(button("✕", "Remove this condition", () => { c.clauses.splice(xi, 1); send(); }, "sq del"));
      const o = opByKey[x.operand] || {type: "number", scale: "", labels: []};
      const pick = el("select");
      pick.setAttribute("aria-label", "Reading");
      operands.forEach((y) => { const op = el("option", "", y.label); op.value = y.key; if (y.key === x.operand) op.selected = true; pick.appendChild(op); });
      if (!opByKey[x.operand]) { const op = el("option", "", "(removed reading)"); op.value = x.operand; op.selected = true; pick.appendChild(op); }
      pick.addEventListener("change", () => {
        x.operand = pick.value;
        const n = opByKey[x.operand] || {type: "number", labels: []};
        x.op = OPS[n.type] ? OPS[n.type][0][0] : "gte";
        x.value = n.type === "label" ? (n.labels[0] || "") : "";
        send();
      });
      cl.appendChild(pick);
      const ops = el("select");
      ops.setAttribute("aria-label", "Comparison");
      (OPS[o.type] || OPS.number).forEach(([k, t]) => { const op = el("option", "", t); op.value = k; if (k === x.op) op.selected = true; ops.appendChild(op); });
      ops.addEventListener("change", () => { x.op = ops.value; send(); });
      cl.appendChild(ops);
      if (o.type === "number") {
        const v = el("input"); v.value = x.value || ""; v.size = 6; v.setAttribute("aria-label", "Value");
        v.addEventListener("change", () => { x.value = v.value; send(); });
        cl.appendChild(v);
        cl.appendChild(el("span", "muted", o.scale || ""));
      } else if (o.type === "label") {
        const v = el("select"); v.setAttribute("aria-label", "Label");
        (o.labels || []).forEach((l) => { const op = el("option", "", l); op.value = l; if (l === x.value) op.selected = true; v.appendChild(op); });
        v.addEventListener("change", () => { x.value = v.value; send(); });
        cl.appendChild(v);
      }
    });
    row.appendChild(button("+ condition", "Add another condition",
      () => { c.clauses = c.clauses || []; c.clauses.push({operand: "score", op: "gte", value: "+30"}); send(); }));
    row.appendChild(button("🗑", "Remove this " + c.kind, () => { model.conditions.splice(ci, 1); send(); }, "sq"));
    checksBox.appendChild(row);
  });
  const addChecks = el("div", "hd");
  addChecks.appendChild(button("+ Confirmation", "Add a confirmation (reported as met or not met)", () => {
    model.conditions = model.conditions || [];
    model.conditions.push({key: slugKey("confirmation"), label: "Confirmation", kind: "confirmation", joiner: "all",
                           clauses: [{operand: "score", op: "gte", value: "+50"}]}); send(); }));
  addChecks.appendChild(button("+ Veto", "Add a veto (when true, every label becomes Vetoed)", () => {
    model.conditions = model.conditions || [];
    model.conditions.push({key: slugKey("veto"), label: "Veto", kind: "veto", joiner: "all",
                           clauses: [{operand: "score", op: "lte", value: "0"}]}); send(); }));
  checksBox.appendChild(addChecks);
}
"""

_COMPONENT = None


def component():
    """Registered once per process, like the app's other components."""
    global _COMPONENT
    if _COMPONENT is None:
        import streamlit as st

        _COMPONENT = st.components.v2.component("lattice_group_editor", js=JS, css=CSS)
    return _COMPONENT


SET_JS = r"""
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const state = data || {};
  const catalogue = state.catalogue || [];
  const groupsAvail = state.groups || [];
  const byId = {};
  catalogue.forEach((s) => { byId[s.id] = s; });
  const bySource = {};
  groupsAvail.forEach((g) => { bySource[g.source] = g; });
  let model = JSON.parse(JSON.stringify(state.model || {groups: [], standalone: [], lines: []}));
  let query = (window.__latSetQuery || "");

  Array.from(parentElement.children).filter((c) => c.classList && c.classList.contains("lat")).forEach((c) => c.remove());
  const root = el("div", "lat");
  parentElement.appendChild(root);

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }
  function button(text, title, onClick, cls) {
    const b = el("button", cls || "", text);
    b.type = "button";
    if (title) { b.title = title; b.setAttribute("aria-label", title); }
    b.addEventListener("click", onClick);
    return b;
  }
  function send() { setTriggerValue("model", JSON.stringify(model)); }
  function key(base) {
    base = String(base).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 30) || "item";
    if (!/^[a-z]/.test(base)) base = ("g_" + base).slice(0, 30);
    const taken = new Set([...(model.groups || []).map((g) => g.key), ...(model.standalone || []).map((m) => m.key)]);
    let k = base, n = 2;
    while (taken.has(k)) { k = base + "_" + n; n += 1; }
    return k;
  }
  function addGroup(source) {
    const g = bySource[source];
    if (!g) return;
    model.groups = model.groups || [];
    model.groups.push({key: key(g.name.split(" v")[0]), source: source});
    send();
  }
  function addSignal(id) {
    const s = byId[id];
    if (!s) return;
    const tf = s.timeframes.indexOf("1D") >= 0 ? "1D" : s.timeframes[0];
    model.standalone = model.standalone || [];
    model.standalone.push({key: key(id.split(".").slice(-1)[0] + "_" + tf), id: s.id, version: s.version, timeframe: tf, role: "condition"});
    send();
  }
  function subjectPicker(item, name) {
    // E4: read this item on the scanned asset (default) or on one fixed asset, at the same moment.
    const wrap = el("span", "hd");
    wrap.style.margin = "0";
    const kind = el("select");
    kind.setAttribute("aria-label", "Which asset " + name + " is read on");
    kind.title = "Read on the asset being scanned, or always on one fixed asset (for example COIN), at the same moment.";
    [["", "📌 the scanned asset"], ["crypto", "📌 fixed crypto"], ["equity", "📌 fixed equity"]].forEach(([v, t]) => {
      const o = el("option", "", t); o.value = v;
      if ((item.subject ? item.subject.kind : "") === v) o.selected = true;
      kind.appendChild(o);
    });
    const id = el("input");
    id.size = 9; id.placeholder = "COIN, bitcoin"; id.setAttribute("aria-label", "Fixed asset for " + name);
    id.value = item.subject ? item.subject.id : "";
    id.style.display = item.subject ? "" : "none";
    const apply = () => {
      if (!kind.value) { delete item.subject; send(); return; }
      id.style.display = "";
      if (id.value.trim()) { item.subject = {kind: kind.value, id: id.value.trim()}; send(); }
    };
    kind.addEventListener("change", apply);
    id.addEventListener("change", apply);
    wrap.appendChild(kind); wrap.appendChild(id);
    return wrap;
  }
  function onDrop(raw) {
    if (raw.indexOf("group|") === 0) addGroup(raw.slice(6));
    else if (raw.indexOf("signal|") === 0) addSignal(raw.slice(7));
  }

  // ---------------------------------------------------------------- library
  const lib = el("div", "col lib");
  root.appendChild(lib);
  lib.appendChild(el("h3", "", "Groups and signals"));
  lib.appendChild(el("div", "muted", "Drag into the Set, or tap +. A Group goes in exactly as saved."));
  const search = el("input", "wide");
  search.placeholder = "Search…";
  search.value = query;
  search.setAttribute("aria-label", "Search Groups and signals");
  lib.appendChild(search);
  const list = el("div");
  lib.appendChild(list);
  function chip(label, sub, hint, payload, onAdd, addTitle, icons) {
    const c = el("div", "chip");
    c.draggable = true;
    c.title = hint || "";
    c.addEventListener("dragstart", (e) => { e.dataTransfer.setData("text/plain", payload); });
    const nm = el("div", "nm");
    const top = el("div", "", label);
    if (icons && icons.length) {
      const pv = el("span", "pv");
      icons.forEach((p) => { const i = el("span", "", p.icon); i.title = p.hover; i.setAttribute("aria-label", p.hover); pv.appendChild(i); });
      top.appendChild(pv);
    }
    nm.appendChild(top);
    if (sub) nm.appendChild(el("div", "muted", sub));
    c.appendChild(nm);
    c.appendChild(button("+", addTitle, onAdd, "sq"));
    return c;
  }
  function drawLibrary() {
    list.replaceChildren();
    const q = query.toLowerCase();
    const gs = groupsAvail.filter((g) => !q || g.name.toLowerCase().indexOf(q) >= 0);
    const groupChip = (g) => {
      const sub = (g.owner === "starter" ? "starter" : g.owner) + " · " + (g.labels.length ? "labels: " + g.labels.join(", ") : (g.has_score ? "score only" : "no score"));
      return chip(g.name, sub, "Members: " + g.members.join(", "), "group|" + g.source, () => addGroup(g.source), "Add " + g.name + " to the Set", g.icons);
    };
    // What Angstrom Signals provides (the starter Groups) sits in its own folded section at the top; the setting
    // in ⚙️ Settings hides it. A starter already in this Set stays usable either way.
    const given = state.show_provided === false ? [] : gs.filter((g) => g.owner === "starter");
    const mine = gs.filter((g) => g.owner !== "starter");
    if (given.length) {
      const box = el("details", "prov");
      box.open = !!window.__latProvOpen || !!q;
      box.addEventListener("toggle", () => { if (!q) window.__latProvOpen = box.open; });
      const sum = el("summary", "", "Provided by Angstrom Signals · " + given.length);
      sum.title = "The starter Groups: the dashboard's own readings. Hide them in ⚙️ Settings → Show provided starters and examples.";
      box.appendChild(sum);
      given.forEach((g) => box.appendChild(groupChip(g)));
      list.appendChild(box);
    }
    list.appendChild(el("div", "cat", "Your Groups"));
    if (!mine.length) list.appendChild(el("div", "muted", "No saved Groups yet: save one in Signal Groups."));
    mine.forEach((g) => list.appendChild(groupChip(g)));
    list.appendChild(el("div", "cat", "Single signals"));
    catalogue.filter((s) => !q || s.name.toLowerCase().indexOf(q) >= 0).forEach((s) => {
      list.appendChild(chip(s.name, s.badge || s.category_label, s.hint, "signal|" + s.id, () => addSignal(s.id), "Add " + s.name + " to the Set"));
    });
  }
  search.addEventListener("input", () => { query = search.value; window.__latSetQuery = query; drawLibrary(); });
  drawLibrary();

  // ---------------------------------------------------------------- set
  const mid = el("div", "mid");
  root.appendChild(mid);
  const box = el("div", "col");
  mid.appendChild(box);
  const name = el("input", "wide");
  name.value = model.name || ""; name.placeholder = "Set name"; name.setAttribute("aria-label", "Set name");
  name.addEventListener("change", () => { model.name = name.value; send(); });
  box.appendChild(name);
  const purpose = el("input", "wide");
  purpose.value = model.purpose || ""; purpose.placeholder = "What it looks for (optional)";
  purpose.setAttribute("aria-label", "Purpose");
  purpose.addEventListener("change", () => { model.purpose = purpose.value; send(); });
  box.appendChild(purpose);
  const drop = el("div", "drop");
  drop.style.marginTop = "10px";
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); onDrop(e.dataTransfer.getData("text/plain")); });
  box.appendChild(drop);
  if (!(model.groups || []).length && !(model.standalone || []).length) drop.appendChild(el("div", "muted", "Drag Groups or signals here, or tap +."));
  (model.groups || []).forEach((g, i) => {
    const info = bySource[g.source] || {name: "(no longer readable)", labels: [], has_score: false};
    const card = el("div", "card");
    card.appendChild(el("span", "tag", "Group"));
    card.appendChild(el("div", "nm", info.name));
    card.appendChild(el("span", "muted", info.labels.length ? "gives label and score" : (info.has_score ? "gives score" : "")));
    card.appendChild(subjectPicker(g, info.name));
    card.appendChild(button("✕", "Remove " + info.name, () => {
      model.groups.splice(i, 1);
      model.lines = (model.lines || []).filter((l) => (l.any || [l]).every((x) => x.group !== g.key));
      send(); }, "sq del"));
    drop.appendChild(card);
  });
  (model.standalone || []).forEach((m, i) => {
    const s = byId[m.id] || {name: m.id, timeframes: [m.timeframe]};
    const card = el("div", "card");
    card.appendChild(el("span", "tag", "Signal"));
    card.appendChild(el("div", "nm", s.name));
    const tf = el("select");
    tf.setAttribute("aria-label", "Timeframe of " + s.name);
    s.timeframes.forEach((t) => { const o = el("option", "", t); o.value = t; if (t === m.timeframe) o.selected = true; tf.appendChild(o); });
    tf.addEventListener("change", () => { m.timeframe = tf.value; send(); });
    card.appendChild(tf);
    card.appendChild(el("span", "tag", (state.member_tags || {})[m.key] || ""));
    card.appendChild(subjectPicker(m, s.name));
    ["condition", "context"].forEach((r) => {
      const b = button(r.charAt(0).toUpperCase() + r.slice(1), r === "condition" ? "Used in the decision." : "Shown for context; changes nothing.",
                       () => { m.role = r; send(); }, m.role === r ? "on" : "");
      b.setAttribute("aria-pressed", m.role === r ? "true" : "false");
      card.appendChild(b);
    });
    card.appendChild(button("✕", "Remove " + s.name, () => {
      model.standalone.splice(i, 1);
      model.lines = (model.lines || []).filter((l) => (l.any || [l]).every((x) => x.member !== m.key));
      send(); }, "sq del"));
    drop.appendChild(card);
  });

  // ---------------------------------------------------------------- decision
  const dec = el("div", "col");
  mid.appendChild(dec);
  const dh = el("div", "hd");
  dh.appendChild(el("h3", "", "Decision: when does this Set say Yes?"));
  dec.appendChild(dh);
  const targets = state.targets || [];
  const tByKey = {};
  targets.forEach((t) => { tByKey[t.key] = t; });
  const tkey = (l) => l.target === "member" ? "member:" + l.member + ":" + (l.field || "")
    : l.target === "condition" ? "condition:" + l.group + ":" + l.condition : l.target + ":" + l.group;
  const OPS = {number: [["gte", "is at least"], ["lte", "is at most"]], "yes/no": [["yes", "is yes"], ["no", "is no"]],
               label: [["is", "is"], ["is_not", "is not"]]};
  function fresh() {
    const t = targets[0];
    if (!t) return null;
    return {target: t.target, group: t.group, member: t.member, field: t.field, condition: t.condition,
            op: (OPS[t.type] || OPS.number)[0][0], value: t.type === "number" ? "+30" : t.values.length ? t.values[0][0] : ""};
  }
  function lineRow(l, onRemove) {
    const row = el("div", "rule");
    const t = tByKey[tkey(l)] || {type: "number", values: [], scale: ""};
    const pick = el("select");
    pick.setAttribute("aria-label", "Reading");
    targets.forEach((x) => { const o = el("option", "", x.label); o.value = x.key; if (x.key === tkey(l)) o.selected = true; pick.appendChild(o); });
    pick.addEventListener("change", () => {
      const n = tByKey[pick.value];
      l.target = n.target; l.group = n.group; l.member = n.member; l.field = n.field; l.condition = n.condition;
      l.op = (OPS[n.type] || OPS.number)[0][0];
      l.value = n.type === "number" ? "" : n.values.length ? n.values[0][0] : "";
      send();
    });
    row.appendChild(pick);
    const ops = el("select");
    ops.setAttribute("aria-label", "Comparison");
    (OPS[t.type] || OPS.number).forEach(([k, txt]) => { const o = el("option", "", txt); o.value = k; if (k === l.op) o.selected = true; ops.appendChild(o); });
    ops.addEventListener("change", () => { l.op = ops.value; send(); });
    row.appendChild(ops);
    if (t.type === "number") {
      const v = el("input"); v.value = l.value || ""; v.size = 6; v.setAttribute("aria-label", "Value");
      v.addEventListener("change", () => { l.value = v.value; send(); });
      row.appendChild(v);
      row.appendChild(el("span", "muted", t.scale || ""));
    } else if (t.type === "label") {
      const v = el("select"); v.setAttribute("aria-label", "Value");
      t.values.forEach(([id, label]) => { const o = el("option", "", label); o.value = id; if (id === l.value) o.selected = true; v.appendChild(o); });
      v.addEventListener("change", () => { l.value = v.value; send(); });
      row.appendChild(v);
    }
    row.appendChild(button("✕", "Remove this line", onRemove, "sq del"));
    return row;
  }
  const all = el("div", "col");
  all.style.borderColor = "#0f766e";
  const ah = el("div", "hd");
  ah.appendChild(el("span", "lbl", "ALL · AND"));
  ah.appendChild(el("span", "muted", "Every line in this box must hold. An ANY box inside counts as one line."));
  all.appendChild(ah);
  if (!targets.length) all.appendChild(el("div", "muted", "Add a Group or a Condition signal first; then its readings can be tested here."));
  (model.lines || []).forEach((line, i) => {
    if (line.any) {
      const anyBox = el("div", "fixed");
      anyBox.style.flexDirection = "column"; anyBox.style.alignItems = "stretch";
      const head = el("div", "hd");
      head.appendChild(el("span", "lbl", "ANY · OR"));
      head.appendChild(el("span", "muted", "This box holds if any of its lines holds."));
      head.appendChild(button("🗑", "Remove this ANY box", () => { model.lines.splice(i, 1); send(); }, "sq"));
      anyBox.appendChild(head);
      line.any.forEach((l, j) => anyBox.appendChild(lineRow(l, () => { line.any.splice(j, 1); if (!line.any.length) model.lines.splice(i, 1); send(); })));
      anyBox.appendChild(button("+ line in this box", "Add a line to this ANY box", () => { const f = fresh(); if (f) { line.any.push(f); send(); } }));
      all.appendChild(anyBox);
    } else {
      all.appendChild(lineRow(line, () => { model.lines.splice(i, 1); send(); }));
    }
  });
  const adds = el("div", "hd");
  const addLine = button("+ Line", "Add a line that must hold", () => { const f = fresh(); if (f) { model.lines = model.lines || []; model.lines.push(f); send(); } });
  const addAny = button("+ ANY (OR) box", "Add a box where any one of its lines is enough", () => { const f = fresh(); if (f) { model.lines = model.lines || []; model.lines.push({any: [f]}); send(); } });
  addLine.disabled = addAny.disabled = !targets.length;
  adds.appendChild(addLine); adds.appendChild(addAny);
  all.appendChild(adds);
  dec.appendChild(all);
  const how = el("div", "fixed");
  how.style.flexDirection = "column"; how.style.alignItems = "flex-start";
  how.appendChild(el("div", "", "🔒 How the answer is decided (fixed)"));
  how.appendChild(el("div", "muted", "Yes: every line holds (an ANY box: at least one of its lines)."));
  how.appendChild(el("div", "muted", "No: at least one line fails, even if others are missing: missing data cannot rescue it."));
  how.appendChild(el("div", "muted", "Unknown: nothing fails, but something needed is missing; it names what."));
  dec.appendChild(how);
}
"""

_SET_COMPONENT = None


def set_component():
    global _SET_COMPONENT
    if _SET_COMPONENT is None:
        import streamlit as st

        _SET_COMPONENT = st.components.v2.component("lattice_set_editor", js=SET_JS, css=CSS)
    return _SET_COMPONENT


def _instant(js: str, name: str) -> str:
    """Draw an edit at once in the browser; Python's checked version (descriptions, checks) follows. Without this the
    editor waited for the round trip to Python before showing the change."""
    head = "export default function(component) {\n  const { data, setTriggerValue, parentElement } = component;\n  const state = data || {};"
    assert head in js
    js = js.replace(head, f"""export default function {name}(component) {{
  const {{ data, setTriggerValue, parentElement }} = component;
  const state = Object.assign({{}}, data || {{}}, component.__local ? {{model: component.__local}} : {{}});
  component.__local = null;""", 1)
    send = 'function send() { setTriggerValue("model", JSON.stringify(model)); }'
    assert send in js
    return js.replace(send, f"""function send() {{
    setTriggerValue("model", JSON.stringify(model));
    component.__local = JSON.parse(JSON.stringify(model));
    {name}(component);
  }}""", 1)


JS = _instant(JS, "latticeGroup")
SET_JS = _instant(SET_JS, "latticeSet")
