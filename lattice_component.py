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
.lat button.sq{width:36px;padding:0}
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
.lat .tag{font-size:11px;padding:2px 8px;border-radius:999px;border:1px solid rgba(127,127,127,.4);
  font-family:ui-monospace,monospace;opacity:.85}
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

  Array.from(parentElement.children).forEach((c) => c.remove());
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
    card.appendChild(button("✕", "Remove " + s.name, () => { model.members.splice(i, 1); send(); }, "sq"));
    drop.appendChild(card);
  });

  // ---------------------------------------------------------------- rules
  const rules = el("div", "col");
  mid.appendChild(rules);
  const rh = el("div", "hd");
  rh.appendChild(el("h3", "", "Rules: what the Group says"));
  rh.appendChild(el("span", "muted", "Checked top to bottom · first match wins · ↑↓ to reorder"));
  rules.appendChild(rh);
  const operands = state.operands || [];
  const opByKey = {};
  operands.forEach((o) => { opByKey[o.key] = o; });
  const OPS = {number: [["gte", "is at least"], ["lte", "is at most"]], "yes/no": [["yes", "is yes"], ["no", "is no"]],
               label: [["is", "is"], ["is_not", "is not"]]};
  (model.rules || []).forEach((r, ri) => {
    const row = el("div", "rule");
    const up = button("↑", "Check this rule earlier", () => { const t = model.rules[ri - 1]; model.rules[ri - 1] = r; model.rules[ri] = t; send(); }, "sq");
    up.disabled = ri === 0;
    const down = button("↓", "Check this rule later", () => { const t = model.rules[ri + 1]; model.rules[ri + 1] = r; model.rules[ri] = t; send(); }, "sq");
    down.disabled = ri === model.rules.length - 1;
    row.appendChild(up); row.appendChild(down);
    row.appendChild(el("span", "num", ri + 1));
    const lab = el("input");
    lab.value = r.label; lab.size = 12; lab.title = "The label this rule gives (for example Bullish)";
    lab.setAttribute("aria-label", "Label of rule " + (ri + 1));
    lab.addEventListener("change", () => { r.label = lab.value; r.id = slug(lab.value); send(); });
    row.appendChild(lab);
    row.appendChild(el("span", "muted", "when"));
    (r.clauses || []).forEach((c, ci) => {
      if (ci > 0) {
        const j = button(r.joiner === "any" ? "OR" : "AND", "Switch between AND (all must hold) and OR (any may hold)",
                         () => { r.joiner = r.joiner === "any" ? "all" : "any"; send(); });
        row.appendChild(j);
      }
      const o = opByKey[c.operand] || {type: "number", scale: "", labels: []};
      const type = el("span", "tag", o.type === "number" ? "#" : o.type === "yes/no" ? "Y/N" : "Aa");
      type.title = o.type === "number" ? "A number: compare it with a value." : o.type === "yes/no" ? "A yes/no reading." : "A label.";
      row.appendChild(type);
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
      row.appendChild(pick);
      const ops = el("select");
      ops.setAttribute("aria-label", "Comparison");
      (OPS[o.type] || OPS.number).forEach(([k, t]) => { const op = el("option", "", t); op.value = k; if (k === c.op) op.selected = true; ops.appendChild(op); });
      ops.addEventListener("change", () => { c.op = ops.value; send(); });
      row.appendChild(ops);
      if (o.type === "number") {
        const v = el("input"); v.value = c.value || ""; v.size = 6; v.setAttribute("aria-label", "Value");
        v.addEventListener("change", () => { c.value = v.value; send(); });
        row.appendChild(v);
        row.appendChild(el("span", "muted", o.scale || ""));
      } else if (o.type === "label") {
        const v = el("select"); v.setAttribute("aria-label", "Label");
        (o.labels || []).forEach((l) => { const op = el("option", "", l); op.value = l; if (l === c.value) op.selected = true; v.appendChild(op); });
        v.addEventListener("change", () => { c.value = v.value; send(); });
        row.appendChild(v);
      }
      row.appendChild(button("✕", "Remove this condition", () => { r.clauses.splice(ci, 1); send(); }, "sq"));
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
