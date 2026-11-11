"""
🔻 Funnel stages board (Lattice → Funnels → Stages (advanced)): the saved-Set list on the left, exactly as in Prism
(filter, perspective icons, "Provided by Angstrom Signals" folded, Your Sets), the funnel's stages on the right, with
the same vertical divider between them.

Each stage holds one Set. Drag a Set onto a stage to put it there (it replaces the one before), or onto "Add a stage"
to add one. On a phone, tap a stage to select it, then + on a Set; with no stage selected, + adds a new stage.
Each stage card keeps its name, the close it is checked at, ⬆ when its Set has a newer version, and move / remove.

Like the Prism board, the board only draws and reports: every press goes to Python as one action
({op, stage, ...} with a fresh nonce); funnel_editor applies it to the working copy and redraws.
"""

from __future__ import annotations

import lattice_component
import prism_component

CSS = prism_component.CSS + """
.lat.fun .stages{display:flex;flex-direction:column;gap:8px;position:relative;padding:4px 0 8px}
.lat.fun .stages::before{content:"";position:absolute;inset:0;pointer-events:none;z-index:0;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' preserveAspectRatio='none'><polygon points='0,0 100,0 60,88 60,100 40,100 40,88' fill='%23818cf8' fill-opacity='0.09'/></svg>") center/100% 100% no-repeat}
.lat.fun .stage{position:relative;z-index:1;border:1px solid rgba(127,127,127,.35);border-radius:12px;
  background:rgba(127,127,127,.07);padding:8px 10px;display:flex;flex-direction:column;gap:6px;cursor:pointer}
.lat.fun .stage.sel{border-color:#0f766e;box-shadow:0 0 0 1px #0f766e inset}
.lat.fun .stage.over,.lat.fun .addstage.over{background:rgba(15,118,110,.12);border-color:#0f766e}
.lat.fun .stage .top{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.lat.fun .stage .num{font-size:16px;min-width:26px;text-align:center;cursor:help}
.lat.fun .stage input.lab{flex:1 1 140px;min-width:0;font-weight:600}
.lat.fun .stage select{min-height:32px}
.lat.fun .stage .setrow{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding-left:34px}
.lat.fun .stage .setnm{font-weight:600}
.lat.fun .stage .ctl{display:flex;gap:6px;margin-left:auto}
.lat.fun .stage .ctl button{width:36px;min-height:32px;padding:0}
.lat.fun .stage .ctl button.del{border-color:rgba(220,38,38,.6);color:#dc2626}
.lat.fun .addstage{position:relative;z-index:1;border:1px dashed rgba(127,127,127,.55);border-radius:12px;padding:12px;
  text-align:center;font-size:13px;opacity:.85;background:transparent}
.lat.fun .spout{position:relative;z-index:1;align-self:center;font-size:13px;padding:4px 12px;border-radius:999px;
  border:1px solid rgba(127,127,127,.4);background:rgba(16,185,129,.12);cursor:help}
@media (max-width:640px){.lat.fun .stage{margin-left:0 !important;margin-right:0 !important}
  .lat.fun .stage .setrow{padding-left:0}.lat.fun .stage .ctl button{min-height:44px;width:44px}}
"""

JS = r"""
export default function funnelStages(component) {
  component.__redraw = () => funnelStages(component);
  const { data, setTriggerValue, parentElement } = component;
  const state = data || {};
  const lib = state.library || {sets: [], perspectives: []};
  const stages = state.stages || [];
  const scope = state.scope || "f";
  window.__funSel = window.__funSel || {};
  let sel = window.__funSel[scope];
  if (sel === undefined || sel === null || sel >= stages.length) sel = null;

  Array.from(parentElement.children).filter((c) => c.classList && c.classList.contains("lat")).forEach((c) => c.remove());
  const root = el("div", "lat prism fun");
  parentElement.appendChild(root);
""" + lattice_component.SPLITTER_JS + prism_component.SET_LIBRARY_JS + r"""

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
    b.addEventListener("click", (e) => { e.stopPropagation(); onClick(e); });
    return b;
  }
  function act(op, extra) {
    setTriggerValue("action", JSON.stringify(Object.assign({op: op, nonce: Date.now() + Math.random()}, extra || {})));
  }
  function redraw() { if (component.__redraw) component.__redraw(); }
  function select(i) { window.__funSel[scope] = (sel === i ? null : i); redraw(); }
  function dropped(e) {
    try { const d = JSON.parse(e.dataTransfer.getData("text/plain") || "{}"); return d.type === "set" ? d.key : null; }
    catch (err) { return null; }
  }
  function dropZone(node, onSet) {
    node.addEventListener("dragover", (e) => { e.preventDefault(); node.classList.add("over"); });
    node.addEventListener("dragleave", () => node.classList.remove("over"));
    node.addEventListener("drop", (e) => {
      e.preventDefault(); node.classList.remove("over");
      const key = dropped(e);
      if (key) onSet(key);
    });
  }
  const full = stages.length >= (state.max_stages || 5);

  // ------------------------------------------------------------------ the Set list (shared with Prism)
  const libCol = el("div", "col lib");
  root.appendChild(libCol);
  window.__funLib = window.__funLib || {};
  setLibrary(libCol, {sets: lib.sets, perspectives: lib.perspectives, showProvided: state.show_provided,
    mem: window.__funLib, title: "Sets",
    hint: "Drag a Set onto a stage, or select a stage and tap +. With no stage selected, + adds a new stage.",
    addTitle: (s) => sel !== null ? "Use " + s.name + " in stage " + (sel + 1)
                    : (full ? "Select a stage first (a funnel has at most " + (state.max_stages || 5) + " stages)"
                            : "Add a stage that checks " + s.name),
    addDisabled: () => sel === null && full,
    onAdd: (s) => sel !== null ? act("set", {stage: sel, set: s.key}) : act("add", {set: s.key}),
    onOpen: (s) => act("open_set", {set: s.key})});

  // ------------------------------------------------------------------ the funnel
  const mid = el("div", "mid");
  root.appendChild(mid);
  addSplitter(root, libCol, mid);
  const hd = el("div", "hd");
  hd.appendChild(el("h3", "", "Stages"));
  hd.appendChild(el("span", "muted", state.intro || ""));
  mid.appendChild(hd);
  const box = el("div", "stages");
  mid.appendChild(box);
  const tfs = state.timeframes || [];
  const n = stages.length;
  stages.forEach((st, i) => {
    const card = el("div", "stage" + (sel === i ? " sel" : ""));
    const inset = Math.round(i * 4 * (5 / Math.max(n, 3)));            // narrower down the funnel
    card.style.marginLeft = inset + "%"; card.style.marginRight = inset + "%";
    card.title = sel === i ? "Selected: tap + on a Set to use it here (tap again to unselect)"
                           : "Tap to select this stage, then + on a Set to use it here";
    card.addEventListener("click", (e) => { if (!e.target.closest("input,select,button,details")) select(i); });
    dropZone(card, (key) => act("set", {stage: i, set: key}));
    const top = el("div", "top");
    const num = el("span", "num", st.icon || String(i + 1));
    num.title = "Stage " + (i + 1) + " of " + n; num.setAttribute("aria-label", num.title);
    top.appendChild(num);
    const lab = el("input", "lab"); lab.value = st.label || ""; lab.maxLength = 40;
    lab.setAttribute("aria-label", "Name of stage " + (i + 1)); lab.placeholder = "Stage " + (i + 1);
    lab.addEventListener("change", () => act("label", {stage: i, label: lab.value}));
    top.appendChild(lab);
    const tf = el("select", "");
    tf.title = "When this stage is checked: at each close of this candle (the Set's readings keep their own timeframes)";
    tf.setAttribute("aria-label", tf.title);
    tfs.forEach(([k, words]) => { const o = el("option", "", "⏱ " + words); o.value = k; if (k === st.timeframe) o.selected = true; tf.appendChild(o); });
    tf.addEventListener("change", () => act("tf", {stage: i, tf: tf.value}));
    top.appendChild(tf);
    const ctl = el("div", "ctl");
    if (i > 0) ctl.appendChild(button("↑", "Move this stage up", () => { window.__funSel[scope] = null; act("move", {stage: i, dir: -1}); }));
    if (i < n - 1) ctl.appendChild(button("↓", "Move this stage down", () => { window.__funSel[scope] = null; act("move", {stage: i, dir: 1}); }));
    if (n > (state.min_stages || 3)) ctl.appendChild(button("✖", "Remove this stage", () => { window.__funSel[scope] = null; act("remove", {stage: i}); }, "del"));
    top.appendChild(ctl);
    card.appendChild(top);
    const row = el("div", "setrow");
    const nm = el("span", "setnm", st.set_name || "No Set");
    if (st.set_line) nm.title = st.set_line;
    row.appendChild(nm);
    const pv = el("span", "pv");
    (st.icons || []).forEach((p) => { const x = el("span", "", p.icon); x.title = p.hover; x.setAttribute("aria-label", p.hover); pv.appendChild(x); });
    row.appendChild(pv);
    if (st.upgrade) {
      const up = button(st.upgrade, "Use the newer version of this Set. Saving then starts every asset again.",
                        () => act("upgrade", {stage: i}), "pill upd");
      row.appendChild(up);
    }
    card.appendChild(row);
    box.appendChild(card);
  });
  if (!full) {
    const add = el("div", "addstage", "➕ Drop a Set here to add a stage");
    add.title = "Or tap + on a Set with no stage selected";
    dropZone(add, (key) => act("add", {set: key}));
    box.appendChild(add);
  }
  const spout = el("div", "spout", "✅ Candidates");
  spout.title = "Assets that hold every stage";
  box.appendChild(spout);
}
"""

_COMPONENT = None


def component():
    global _COMPONENT
    if _COMPONENT is None:
        import streamlit as st

        _COMPONENT = st.components.v2.component("funnel_stages", js=JS, css=CSS)
    return _COMPONENT
