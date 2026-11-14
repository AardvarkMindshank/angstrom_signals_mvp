"""
🔎 Prism Scan board (build stage 7): saved Sets and Watchlist on the left, the account's Prism Scans on the right,
each a collapsible card with Play, past moment, pause, duplicate and delete.

The board only draws and reports what was pressed: every press is sent to Python as one action
({op, scan, ...}, with a fresh nonce), Python checks it, writes through `prism_put_scan` and redraws. Which cards are
open is remembered in the browser for the session. Data comes from prism_board.py.
"""

from __future__ import annotations

import lattice_component

CSS = lattice_component.CSS + """
.lat.prism .pv{display:inline-flex;gap:2px;margin-left:6px;font-size:13px;vertical-align:middle}
.lat.prism .pv span{cursor:help}
.lat.prism .ev{margin-left:6px;font-size:13px;opacity:.75;cursor:help}
.lat.prism .chip.focus{outline:2px solid #2563eb;outline-offset:1px}
.lat.prism details.inside{margin-top:4px;font-size:12px}
.lat.prism details.inside>summary{cursor:pointer;opacity:.8}
.lat.prism details.inside .part{margin:6px 0 0;padding-left:8px;border-left:2px solid rgba(127,127,127,.3)}
.lat.prism details.inside .sig{opacity:.85}
.lat.prism details.inside .dec{border-left-color:#2563eb}
.lat.prism details.inside button{margin-top:8px}
.lat.prism details.inside.scan{font-size:13px;margin:0 0 10px;padding:8px 10px;border:1px solid rgba(127,127,127,.3);border-radius:8px}
.lat.prism .armed{margin-left:6px;font-size:12px;padding:0 5px;border-radius:8px;background:#ede9fe;color:#5b21b6;cursor:help;white-space:nowrap}
.lat.prism .line{font-size:12px;opacity:.8;margin-top:2px}
.lat.prism .more{font-size:12px;margin-top:2px}
.lat.prism .more summary{cursor:pointer;opacity:.75;min-height:24px;list-style:none}
.lat.prism .more summary::-webkit-details-marker{display:none}
.lat.prism .more p{margin:4px 0}
.lat.prism .wf{margin:8px 0 2px;padding:4px 8px;border-left:3px solid rgba(127,127,127,.35)}
.lat.prism .wf summary{cursor:pointer;min-height:24px;list-style:none}
.lat.prism .wf summary::-webkit-details-marker{display:none}
.lat.prism .wf[open]{display:grid;gap:3px}
.lat.prism .more[open] .m,.lat.prism .more:not([open]) .l{display:none}
.lat.prism .hstrip{margin:6px 0 10px}
.lat.prism .hstrip .hrow{display:flex;align-items:center;gap:8px;padding:3px 0;cursor:pointer;border-radius:6px}
.lat.prism .hstrip .hrow:hover{background:rgba(127,127,127,.1)}
.lat.prism .hstrip .hname{flex:0 0 7.5em;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lat.prism .hstrip svg{flex:1 1 auto;height:16px;min-width:0;border-radius:3px;background:rgba(127,127,127,.12)}
.lat.prism .hstrip .hax{display:flex;justify-content:space-between;font-size:11px;opacity:.7;margin-left:calc(7.5em + 8px)}
.lat.prism .hseg{display:inline-flex;gap:4px;margin-left:auto}
.lat.prism .hseg button{min-height:28px;padding:2px 8px;font-size:12px}
.lat.prism .hseg button.on{border-color:#0f766e;background:rgba(15,118,110,.12);color:inherit;font-weight:600}
.lat.prism button.hist.on{border-color:#0f766e;background:rgba(15,118,110,.12)}
.lat.prism .pvf{display:flex;flex-wrap:wrap;gap:4px;margin:4px 0 6px}
.lat.prism .pvf button{min-width:36px;min-height:32px;padding:2px 6px;font-size:15px;border-radius:8px;
  border:1px solid rgba(127,127,127,.35);background:transparent;cursor:pointer}
.lat.prism .pvf button.on{border-color:#0f766e;background:rgba(15,118,110,.12)}
.lat.prism .scans{display:flex;flex-direction:column;gap:10px}
.lat.prism .scan{border:1px solid rgba(127,127,127,.3);border-radius:12px;background:rgba(127,127,127,.05);
  padding:8px 12px;display:flex;flex-direction:column;gap:8px}
.lat.prism .scan.sel{border-color:#0f766e;box-shadow:0 0 0 1px #0f766e inset}
.lat.prism .scan.paused{opacity:.75}
.lat.prism .scan.over{background:rgba(15,118,110,.08);border-color:#0f766e}
.lat.prism .head{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.lat.prism .head .nm{font-weight:700;font-size:15px}
.lat.prism .chev{width:36px;padding:0;border:0}
.lat.prism .chev svg{transition:transform .15s}
.lat.prism .chev.open svg{transform:rotate(90deg)}
.lat.prism .sum{display:flex;flex-wrap:wrap;align-items:center;gap:10px;flex:1 1 280px;min-width:0}
.lat.prism .y{color:#059669;font-weight:600}.lat.prism .n{color:#ea580c;font-weight:600}
.lat.prism .u{opacity:.8;font-weight:600}
.lat.prism .dots{display:inline-flex;gap:3px;align-items:center}
.lat.prism .dot{width:8px;height:8px;border-radius:999px;background:#9ca3af}
.lat.prism .dot.yes{background:#10b981}.lat.prism .dot.no{background:#f97316}
.lat.prism .dot.failed{background:transparent;border:2px solid #dc2626;width:8px;height:8px}
.lat.prism .ctl{display:flex;gap:6px;margin-left:auto}
.lat.prism .ctl button{width:40px;padding:0;display:inline-flex;align-items:center;justify-content:center;color:#fff;
  border:1px solid #4a6a95;border-radius:8px;background:linear-gradient(180deg,#86a5cc,#557aa6);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 1px 2px rgba(0,0,0,.18)}
.lat.prism .ctl button:hover{background:linear-gradient(180deg,#7898c2,#486d9b);color:#fff}
.lat.prism .ctl button.del{border-color:#b91c1c;background:linear-gradient(180deg,#ef6b6b,#c62828)}
.lat.prism .ctl button.del:hover{background:linear-gradient(180deg,#e35d5d,#b42020)}
.lat.prism .ctl button.del.arm{width:auto;padding:0 10px}
.lat.prism .pill{font-size:12px;padding:2px 8px;border-radius:999px;border:1px solid rgba(127,127,127,.45)}
.lat.prism .pill.upd{border-color:#d97706;color:#b45309;cursor:pointer;background:transparent;min-height:0}
.lat.prism .body{border-top:1px solid rgba(127,127,127,.25);padding:8px 0 4px 44px;display:flex;flex-direction:column;gap:10px}
.lat.prism .row{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.lat.prism .row > b{min-width:70px}
.lat.prism .achip{display:inline-flex;align-items:center;gap:4px;padding:2px 4px 2px 10px;border-radius:999px;
  border:1px solid rgba(127,127,127,.4)}
.lat.prism .achip.grp{border-color:#0f766e}
.lat.prism .achip button{min-height:26px;width:26px;padding:0;border:0}
.lat.prism table{border-collapse:collapse;width:100%}
.lat.prism td,.lat.prism th{text-align:left;padding:4px 8px 4px 0;vertical-align:top;border-bottom:1px solid rgba(127,127,127,.15)}
.lat.prism th{font-weight:600;font-size:12px;opacity:.75}
.lat.prism .grpchip{display:inline-flex;align-items:center;gap:6px;padding:4px 4px 4px 10px;border-radius:999px;
  border:1px solid #0f766e;margin:0 4px 4px 0;cursor:grab}
.lat.prism .grpchip button{min-height:28px;width:28px;padding:0}
.lat.prism .newdrop{min-height:0;padding:12px}
@media (max-width:640px){.lat.prism .body{padding-left:0}.lat.prism .ctl{margin-left:0;width:100%}
  .lat.prism .ctl button{flex:1 1 0;width:auto;min-height:44px}}
"""

SET_LIBRARY_JS = r"""
  // The saved-Set list shared by Prism and the funnel stages: filter, perspective icons, "Provided by Angstrom
  // Signals" folded, then Your Sets. Each chip drags as {type: "set", key} and has a + button.
  // opts: sets, perspectives, showProvided, focus, title, hint, empty, addTitle(s), onAdd(s), addDisabled(s),
  // onOpen(s), mem (an object kept on window for the session: filter text, icon filter, folded state).
  function setLibrary(libCol, opts) {
    const M = opts.mem;
    libCol.appendChild(el("h3", "", opts.title || "Saved Sets"));
    libCol.appendChild(el("div", "muted", opts.hint || ""));
  const fs = el("input", "wide"); fs.placeholder = "Filter Sets"; fs.setAttribute("aria-label", "Filter Sets"); fs.value = M.q || "";
  libCol.appendChild(fs);
  // Filter by what a Set looks at: tap an icon, tap it again to show all.
  const pvf = el("div", "pvf");
  (opts.perspectives || []).forEach((p) => {
    const b = button(p.icon, p.hover + " (tap to filter)", () => {
      M.pv = M.pv === p.key ? "" : p.key;
      pvf.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x.dataset.k === M.pv));
      drawSets();
    });
    b.dataset.k = p.key; b.setAttribute("aria-label", p.hover);
    if (M.pv === p.key) b.classList.add("on");
    pvf.appendChild(b);
  });
  libCol.appendChild(pvf);
  const setList = el("div", "");
  libCol.appendChild(setList);
  function setChip(s) {
      const c = el("div", "chip");
      c.draggable = true;
      c.addEventListener("dragstart", (e) => e.dataTransfer.setData("text/plain", JSON.stringify({type: "set", key: s.key})));
      const nm = el("div", "nm");
      const title = el("div", "", s.name);
      const pv = el("span", "pv");
      (s.icons || []).forEach((p) => { const i = el("span", "", p.icon); i.title = p.hover; i.setAttribute("aria-label", p.hover); pv.appendChild(i); });
      title.appendChild(pv);
      if (s.evidence) { const ev = el("span", "ev", s.evidence.icon); ev.title = s.evidence.hover; ev.setAttribute("aria-label", s.evidence.hover); title.appendChild(ev); }
      nm.appendChild(title);
      if (s.line) nm.appendChild(el("div", "line", s.line));
      if (s.more) {
        const d = el("details", "more");
        const sm = el("summary", "");
        sm.appendChild(el("span", "m", "more…")); sm.appendChild(el("span", "l", "less…"));
        d.appendChild(sm);
        [["What it measures", s.more.measures], ["Why traders watch it", s.more.why], ["What it doesn't prove", s.more.not_proven]]
          .forEach(([h, t]) => { const p = el("p", ""); const b = el("b", "", h + ": "); p.appendChild(b); p.appendChild(document.createTextNode(t)); d.appendChild(p); });
        if (s.followed) d.appendChild(followedBlock(s.followed, s.evidence && s.evidence.icon));
        d.addEventListener("click", (e) => e.stopPropagation());
        nm.appendChild(d);
      }
      if (s.followed && !s.more) nm.appendChild(followedBlock(s.followed, s.evidence && s.evidence.icon));
      if (s.key && s.key === (opts.focus || {}).key) {
        c.classList.add("focus");
        const more = nm.querySelector("details.more");
        if (more) more.open = true;
        const token = opts.focus.token;
        if (M.focusToken !== token) {          // scroll to it once per Open in Lattice
          M.focusToken = token;
          window.setTimeout(() => c.scrollIntoView({behavior: "smooth", block: "center"}), 700);
        }
      }
      if (s.inside) nm.appendChild(insideBlock(s));
      if (!s.provided) nm.appendChild(el("div", "muted", s.meta));
      c.appendChild(nm);
      const plus = button("+", opts.addTitle(s), () => opts.onAdd(s), "sq");
      if (opts.addDisabled && opts.addDisabled(s)) plus.disabled = true;
      c.appendChild(plus);
      return c;
  }
  function insideBlock(s) {   // 🔍 the building blocks: Groups (signals, labels), single signals, the decision
    const b = el("details", "inside");
    const sm = el("summary", "", "🔍 Look inside");
    sm.title = "The Groups and signals this Set is made of, and when it says Yes";
    b.appendChild(sm);
    const x = s.inside;
    (x.groups || []).forEach((g) => {
      const p = el("div", "part");
      p.appendChild(el("b", "", "Group · " + g.name));
      if (g.labels && g.labels.length) p.appendChild(el("div", "muted", "Labels: " + g.labels.join(", ")));
      (g.signals || []).forEach((t) => p.appendChild(el("div", "sig", "• " + t)));
      b.appendChild(p);
    });
    (x.signals || []).forEach((t) => {
      const p = el("div", "part");
      p.appendChild(el("b", "", "Signal · " + t.name));
      if (t.settings) p.appendChild(el("div", "muted", "Settings: " + t.settings));
      b.appendChild(p);
    });
    if (x.decision) b.appendChild(el("div", "part dec", x.decision));
    if (s.open) {
      const go = button(s.open === "copy" ? "Make my own copy" : "Open in Signal Sets",
        s.open === "copy" ? "Opens a copy in Signal Sets that you can change and save as your own"
                          : "Opens this Set in Signal Sets", () => opts.onOpen(s));
      b.appendChild(go);
    }
    b.addEventListener("click", (e) => e.stopPropagation());
    return b;
  }
  function followedBlock(f, mark) {   // "What followed", folded to one line: the verdict; tap for the plain numbers (muted, no colours)
    const b = el("details", "wf");
    const sm = el("summary", "");
    sm.appendChild(el("b", "", (mark ? mark + " " : "") + "What followed: "));
    sm.appendChild(document.createTextNode(f.verdict || "not studied on its own"));
    b.appendChild(sm);
    b.appendChild(el("div", "muted", f.title.replace(/^What followed · /, "")));
    (f.lines || []).forEach((t) => b.appendChild(el("div", "", t)));
    (f.parts || []).forEach((p) => b.appendChild(el("div", "", p.line)));
    if (f.compare) b.appendChild(el("div", "", f.compare));
    if (f.parts_note) b.appendChild(el("div", "muted", f.parts_note));
    if (f.assets) b.appendChild(el("div", "", f.assets.line + " Asset by asset: open the Set in Signal Sets."));
    if (f.note) b.appendChild(el("div", "muted", f.note));
    b.addEventListener("click", (e) => e.stopPropagation());
    return b;
  }
  function drawSets() {
    setList.innerHTML = "";
    const q = (M.q || "").toLowerCase();
    const showProvided = opts.showProvided !== false;
    const focus = (opts.focus || {}).key || "";          // Open in Lattice on a provided Set
    const usable = (opts.sets || []).filter((s) => showProvided || !s.provided || s.key === focus);
    const pick = M.pv || "";
    const shown = usable.filter((s) => (!q || (s.name + " " + s.meta + " " + (s.line || "")).toLowerCase().includes(q))
      && (!pick || (s.icons || []).some((p) => p.key === pick)));
    const given = shown.filter((s) => s.provided), mine = shown.filter((s) => !s.provided);
    if (given.length) {
      // What Angstrom Signals provides sits in its own folded section at the top (hidden with the setting).
      const box = el("details", "prov");
      box.open = !!M.provOpen || !!q || !!pick || given.some((s) => s.key === focus);
      box.addEventListener("toggle", () => { if (!q) M.provOpen = box.open; });
      const sum = el("summary", "", "Provided by Angstrom Signals · " + given.length);
      sum.title = "Example Sets made by Angstrom Signals. Hide them in ⚙️ Settings → Show provided starters and examples.";
      box.appendChild(sum);
      given.forEach((s) => box.appendChild(setChip(s)));
      setList.appendChild(box);
    }
    if (given.length && mine.length) setList.appendChild(el("div", "cat", "Your Sets"));
    mine.forEach((s) => setList.appendChild(setChip(s)));
    if (!shown.length) setList.appendChild(el("div", "muted", usable.length ? "No Set matches." : (opts.empty || "No Sets with a decision yet: make one in Signal Sets.")));
  }
  fs.addEventListener("input", () => { M.q = fs.value; drawSets(); });
  drawSets();

    return drawSets;
  }
"""

JS = r"""
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const state = data || {};
  const lib = state.library || {sets: [], groups: [], assets: []};
  const scans = state.scans || [];
  window.__prismOpen = window.__prismOpen || {};
  window.__prismInside = window.__prismInside || {};
  window.__prismPast = window.__prismPast || {};
  if (state.open_new && window.__prismOpen[state.open_new] === undefined) window.__prismOpen[state.open_new] = true;
  if (state.open_new) window.__prismSel = state.open_new;
  let sel = window.__prismSel || null;
  if (sel && !scans.some((s) => s.id === sel)) sel = null;
  let qAssets = window.__prismQA || "";

  Array.from(parentElement.children).filter((c) => c.classList && c.classList.contains("lat")).forEach((c) => c.remove());
  const root = el("div", "lat prism");
  parentElement.appendChild(root);
""" + lattice_component.SPLITTER_JS + SET_LIBRARY_JS + r"""

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
  function icon(name) {
    const paths = {
      play: '<path d="M7 4.5v15l12-7.5z" fill="currentColor" stroke="none"/>',
      past: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 8v4l3 2"/>',
      pause: '<rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none"/><rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none"/>',
      resume: '<path d="M7 4.5v15l12-7.5z" fill="currentColor" stroke="none"/>',
      inside: '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
      copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
      del: '<path d="M6 6l12 12M18 6L6 18"/>',
      chev: '<path d="M9 6l6 6-6 6"/>',
      timer: '<path d="M6 3h12M6 21h12M7 3c0 5 10 5 10 9s-10 4-10 9M17 3c0 5-10 5-10 9"/>',
    };
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("width", "18"); s.setAttribute("height", "18");
    s.setAttribute("fill", "none"); s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "2");
    s.setAttribute("stroke-linecap", "round"); s.setAttribute("stroke-linejoin", "round"); s.setAttribute("aria-hidden", "true");
    s.innerHTML = paths[name];
    return s;
  }
  function iconButton(name, title, onClick, cls) {
    const b = button("", title, onClick, cls);
    b.appendChild(icon(name));
    return b;
  }
  function act(op, extra) {
    setTriggerValue("action", JSON.stringify(Object.assign({op: op, nonce: Date.now() + Math.random()}, extra || {})));
  }
  function redraw() { if (window.__prismDraw) window.__prismDraw(); }

  // ------------------------------------------------------------------ library
  const libCol = el("div", "col lib");
  root.appendChild(libCol);
  window.__prismLib = window.__prismLib || {q: window.__prismQS || ""};
  setLibrary(libCol, {sets: lib.sets, perspectives: lib.perspectives, showProvided: state.show_provided,
    focus: state.focus_set, mem: window.__prismLib, title: "Saved Sets",
    hint: "Drag a Set onto the scans, or tap + to start a scan.",
    addTitle: (s) => "Start a scan with " + s.name, onAdd: (s) => act("create", {set: s.key}),
    onOpen: (s) => act("open_set", {set: s.key})});

  libCol.appendChild(el("h3", "", "Watchlist"));
  const fa = el("input", "wide"); fa.placeholder = "Filter assets"; fa.setAttribute("aria-label", "Filter assets"); fa.value = qAssets;
  libCol.appendChild(fa);
  libCol.appendChild(el("div", "cat", "Groups · follow the Watchlist"));
  const grpRow = el("div", "");
  libCol.appendChild(grpRow);
  lib.groups.forEach((g) => {
    const c = el("span", "grpchip");
    c.draggable = true;
    c.addEventListener("dragstart", (e) => e.dataTransfer.setData("text/plain", JSON.stringify({type: "asset", item: {group: g.group}})));
    c.appendChild(el("span", "", g.name + " · " + g.count));
    const b = button("+", sel ? "Add " + g.name + " to the selected scan" : "Open a scan first", () => sel && act("add_asset", {scan: sel, item: {group: g.group}}));
    b.disabled = !sel;
    c.appendChild(b);
    grpRow.appendChild(c);
  });
  libCol.appendChild(el("div", "cat", "Single assets"));
  const assetList = el("div", "");
  libCol.appendChild(assetList);
  function drawAssets() {
    assetList.innerHTML = "";
    const q = qAssets.toLowerCase();
    lib.assets.filter((a) => !q || (a.name + " " + a.id).toLowerCase().includes(q)).forEach((a) => {
      const c = el("div", "chip");
      c.draggable = true;
      c.addEventListener("dragstart", (e) => e.dataTransfer.setData("text/plain", JSON.stringify({type: "asset", item: {kind: a.kind, id: a.id}})));
      c.appendChild(el("span", "nm", a.name));
      c.appendChild(el("span", "muted", a.market));
      const b = button("+", sel ? "Add " + a.name + " to the selected scan" : "Open a scan first", () => sel && act("add_asset", {scan: sel, item: {kind: a.kind, id: a.id}}), "sq");
      b.disabled = !sel;
      c.appendChild(b);
      assetList.appendChild(c);
    });
  }
  fa.addEventListener("input", () => { qAssets = fa.value; window.__prismQA = qAssets; drawAssets(); });
  drawAssets();

  // ------------------------------------------------------------------ scans
  const mid = el("div", "mid");
  root.appendChild(mid);
  addSplitter(root, libCol, mid);
  const hd = el("div", "hd");
  hd.appendChild(el("h3", "", "Prism Scans"));
  hd.appendChild(el("span", "muted", (state.scheduled || 0) + " of " + (state.max_scheduled || 5) + " scheduled · paused and Play-only scans don't count"));
  const all = el("div", "row"); all.style.marginLeft = "auto";
  all.appendChild(button("Expand all", "Open every scan", () => { scans.forEach((s) => { window.__prismOpen[s.id] = true; }); redraw(); }));
  all.appendChild(button("Collapse all", "Close every scan", () => { scans.forEach((s) => { window.__prismOpen[s.id] = false; }); redraw(); }));
  hd.appendChild(all);
  mid.appendChild(hd);

  const drop = el("div", "drop newdrop", "Drop a Set here to start a new scan. It scans your whole Watchlist until you change its assets, and runs when you press Play until you give it a schedule.");
  drop.classList.add("muted");
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault(); drop.classList.remove("over");
    try { const d = JSON.parse(e.dataTransfer.getData("text/plain")); if (d.type === "set") act("create", {set: d.key}); } catch (err) {}
  });
  mid.appendChild(drop);

  const list = el("div", "scans");
  mid.appendChild(list);
  if (!scans.length) list.appendChild(el("div", "muted", "No scans yet."));
  scans.forEach((s) => list.appendChild(card(s)));

  function card(s) {
    const open = !!window.__prismOpen[s.id];
    const c = el("article", "scan" + (s.paused ? " paused" : "") + (sel === s.id ? " sel" : ""));
    c.dataset.scan = s.id;
    c.addEventListener("click", () => { if (window.__prismSel !== s.id) { window.__prismSel = s.id; redraw(); } });
    c.addEventListener("dragover", (e) => { e.preventDefault(); c.classList.add("over"); });
    c.addEventListener("dragleave", () => c.classList.remove("over"));
    c.addEventListener("drop", (e) => {
      e.preventDefault(); c.classList.remove("over");
      try { const d = JSON.parse(e.dataTransfer.getData("text/plain")); if (d.type === "asset") act("add_asset", {scan: s.id, item: d.item}); } catch (err) {}
    });

    const head = el("div", "head");
    const chev = iconButton("chev", open ? "Hide details" : "Show details", (e) => { e.stopPropagation(); window.__prismOpen[s.id] = !open; window.__prismSel = s.id; redraw(); }, "chev" + (open ? " open" : ""));
    chev.setAttribute("aria-expanded", open ? "true" : "false");
    head.appendChild(chev);
    const sum = el("div", "sum");
    sum.appendChild(el("span", "nm", s.name));
    sum.appendChild(el("span", "tag", s.version));
    if (s.update) {
      const u = button("v" + s.update.version + " available", "Switch this scan to version " + s.update.version + " of its Set", (e) => { e.stopPropagation(); act("update_set", {scan: s.id, key: s.update.key}); }, "pill upd");
      sum.appendChild(u);
    }
    if (s.paused) sum.appendChild(el("span", "pill", "Paused"));
    const counts = el("span", "row");
    counts.appendChild(el("span", "y", "Yes " + s.counts.yes));
    counts.appendChild(el("span", "n", "No " + s.counts.no));
    counts.appendChild(el("span", "u", "? " + s.counts.unknown));
    sum.appendChild(counts);
    if (s.dots.length) {
      const d = el("span", "dots"); d.setAttribute("role", "img"); d.setAttribute("aria-label", "Last " + s.dots.length + " scheduled runs");
      d.title = "Last " + s.dots.length + " scheduled runs: green had a Yes, orange all No, grey mostly Unknown, red ring failed";
      s.dots.forEach((x) => d.appendChild(el("span", "dot " + x)));
      sum.appendChild(d);
    }
    const nx = el("span", "muted row"); nx.appendChild(icon("timer")); nx.appendChild(el("span", "", s.next_text));
    sum.appendChild(nx);
    head.appendChild(sum);

    const ctl = el("div", "ctl");
    ctl.addEventListener("click", (e) => e.stopPropagation());
    ctl.appendChild(iconButton("play", "Run now on " + s.asset_count + " assets", () => { window.__prismOpen[s.id] = true; act("run", {scan: s.id}); }, "play"));
    ctl.appendChild(iconButton("past", "Run at a past moment", () => { window.__prismPast[s.id] = !window.__prismPast[s.id]; window.__prismOpen[s.id] = true; redraw(); }));
    const hb = button("🕰️", s.history ? "Close Visualize History" : "Visualize History: this Set on every past day, for each asset, on a chart under the scans", () => {
      window.__prismOpen[s.id] = true; act(s.history ? "history_close" : "history", {scan: s.id}); }, "sq hist");
    if (s.history) hb.classList.add("on");
    ctl.appendChild(hb);
    ctl.appendChild(iconButton(s.paused ? "resume" : "pause", s.paused ? "Resume: the first run after resuming records answers without alerting" : "Pause: keeps the scan, stops runs and alerts", () => act(s.paused ? "resume" : "pause", {scan: s.id})));
    if (s.inside) {
      const ib = iconButton("inside", "Look inside: the Groups and signals this scan's Set is made of, and when it says Yes",
        () => { window.__prismInside[s.id] = !window.__prismInside[s.id]; window.__prismOpen[s.id] = true; redraw(); });
      if (window.__prismInside[s.id]) ib.classList.add("on");
      ctl.appendChild(ib);
    }
    ctl.appendChild(iconButton("copy", "Duplicate this scan: same Set, to run on other assets or with another schedule or alerts (the copy runs only when you press Play until you schedule it). To change what the Set checks, use 🔍 Look inside → Make my own copy", () => act("duplicate", {scan: s.id})));
    const del = iconButton("del", "Delete this scan", () => {
      if (del.classList.contains("arm")) { act("delete", {scan: s.id}); return; }
      del.classList.add("arm"); del.textContent = "Delete?"; del.title = "Press again to delete";
      setTimeout(() => { if (del.isConnected) redraw(); }, 4000);
    }, "del");
    ctl.appendChild(del);
    head.appendChild(ctl);
    c.appendChild(head);

    if (!open) return c;
    const body = el("div", "body");
    if (s.inside && window.__prismInside[s.id]) {
      const box = insideBlock({key: s.set_key, inside: s.inside, open: s.set_key ? s.set_open : null});
      box.open = true;
      box.querySelector("summary").textContent = "🔍 Inside this scan's Set";
      box.classList.add("scan");
      body.appendChild(box);
    }
    c.appendChild(body);

    if (window.__prismPast[s.id]) {
      const r = el("div", "row");
      r.appendChild(el("b", "", "Past moment"));
      const d = el("input"); d.type = "date"; d.setAttribute("aria-label", "Date (UTC)");
      const t = el("input"); t.type = "time"; t.value = "00:05"; t.setAttribute("aria-label", "Time (UTC)");
      const day = new Date(Date.now() - 7 * 864e5).toISOString().slice(0, 10);
      const kept = (window.__prismPastAt || {})[s.id] || {};          // keep the chosen moment when the board redraws
      d.value = kept.date || day; d.max = new Date().toISOString().slice(0, 10);
      if (kept.time) t.value = kept.time;
      const keep = () => { window.__prismPastAt = window.__prismPastAt || {}; window.__prismPastAt[s.id] = {date: d.value, time: t.value}; };
      d.addEventListener("change", keep); t.addEventListener("change", keep);
      r.appendChild(d); r.appendChild(t); r.appendChild(el("span", "muted", "UTC"));
      r.appendChild(button("⏪ Run at this moment", "Rebuild what was known then, using only data available at that time", () => { keep(); act("run_past", {scan: s.id, date: d.value, time: t.value}); }, "on"));
      body.appendChild(r);
    }

    const ar = el("div", "row");
    ar.appendChild(el("b", "", "Assets"));
    s.assets.forEach((a, i) => {
      const ch = el("span", "achip" + (a.group ? " grp" : ""));
      ch.appendChild(el("span", "", a.label));
      // The only entry has no ×: a scan always scans something. Adding another replaces it.
      if (s.assets.length > 1) ch.appendChild(button("×", "Remove " + a.label, () => act("remove_asset", {scan: s.id, index: i})));
      ar.appendChild(ch);
    });
    const only = s.assets.length === 1;
    ar.appendChild(el("span", "muted", s.asset_count + " assets now · " + (only
      ? (s.assets[0].watchlist
        ? "to scan less, drop assets or a group here (or tap + in the list): they take the Watchlist's place"
        : "drop more assets or a group here, or tap + in the list (a scan keeps at least one)")
      : "drop assets or a group here, or tap + in the list")));
    body.appendChild(ar);

    const rr = el("div", "row");
    rr.appendChild(el("b", "", "Runs"));
    const runs = el("select"); runs.setAttribute("aria-label", "When the scan runs");
    const choices = [["manual", "Only when I press Play"], ["4H", "Each 4-hour close"], ["1D", "Each daily close"], ["1W", "Each weekly close"], ["times", "At set times"]];
    const cur = s.schedule.kind === "manual" ? "manual" : s.schedule.kind === "close" ? s.schedule.timeframe : "times";
    choices.forEach(([v, l]) => { const o = el("option", "", l); o.value = v; if (v === cur) o.selected = true; runs.appendChild(o); });
    rr.appendChild(runs);
    const times = el("input"); times.placeholder = "08:00, 20:00"; times.setAttribute("aria-label", "Times of day");
    times.value = (s.schedule.times || ["08:00"]).join(", "); times.style.width = "130px";
    const days = el("select"); days.setAttribute("aria-label", "Days");
    [["all", "Every day"], ["weekdays", "Weekdays"]].forEach(([v, l]) => { const o = el("option", "", l); o.value = v; if ((s.schedule.days || "all") === v) o.selected = true; days.appendChild(o); });
    const tz = el("select"); tz.setAttribute("aria-label", "Time zone");
    (state.zones || []).forEach((z) => { const o = el("option", "", z); o.value = z; if ((s.schedule.tz || state.zones[0]) === z) o.selected = true; tz.appendChild(o); });
    const timeBits = [times, days, tz];
    function showTimes() { timeBits.forEach((x) => { x.style.display = runs.value === "times" ? "" : "none"; }); }
    timeBits.forEach((x) => rr.appendChild(x));
    // Saved as soon as it changes, like the alert settings. Only "At set times" waits for its times to be typed.
    const saveSchedule = () => act("schedule", {scan: s.id, runs: runs.value, times: times.value, days: days.value, tz: tz.value});
    runs.addEventListener("change", () => { showTimes(); if (runs.value !== "times") saveSchedule(); });
    times.addEventListener("change", () => { if (runs.value === "times" && times.value.trim()) saveSchedule(); });
    days.addEventListener("change", () => { if (runs.value === "times") saveSchedule(); });
    tz.addEventListener("change", () => { if (runs.value === "times") saveSchedule(); });
    showTimes();
    body.appendChild(rr);
    if (s.warning) body.appendChild(el("div", "muted", "Note: " + s.warning));

    const al = el("div", "row");
    al.appendChild(el("b", "", "Alerts"));
    const ch = el("select"); ch.setAttribute("aria-label", "Where alerts go");
    const chans = [["instant", "Instant (app and email)"], ["digest", "Daily digest"], ["app", "App only"], ["off", "Off"]];
    if (s.notify.channel === "account") chans.unshift(["account", "As my alert settings"]);
    chans.forEach(([v, l]) => { const o = el("option", "", l); o.value = v; if (v === s.notify.channel) o.selected = true; ch.appendChild(o); });
    al.appendChild(ch);
    const boxes = {};
    [["on_yes", "Turns Yes"], ["on_no", "Turns No"], ["on_fail", "Can't run"]].forEach(([k, l]) => {
      const lab = el("label", "row"); lab.style.gap = "4px";
      const b = el("input"); b.type = "checkbox"; b.checked = !!s.notify[k]; boxes[k] = b;
      lab.appendChild(b); lab.appendChild(el("span", "", l));
      lab.title = {on_yes: "The first Yes for an asset; not again until it has said No", on_no: "When an asset that was Yes turns No", on_fail: "When a run fails, or at least half its answers are Unknown"}[k];
      al.appendChild(lab);
    });
    function sendAlerts() { act("alerts", {scan: s.id, channel: ch.value, on_yes: boxes.on_yes.checked, on_no: boxes.on_no.checked, on_fail: boxes.on_fail.checked}); }
    ch.addEventListener("change", sendAlerts);
    Object.values(boxes).forEach((b) => b.addEventListener("change", sendAlerts));
    body.appendChild(al);
    if (s.notify.channel === "digest") body.appendChild(el("div", "muted", "Daily digest alerts arrive with your daily summary email (switch it on in your alert settings)."));

    const yr = el("div", "row");
    yr.appendChild(el("b", "", "Yes now"));
    if (!s.yes_now.length) yr.appendChild(el("span", "muted", "none on the last scheduled runs"));
    s.yes_now.forEach((a) => {
      const chp = el("span", "achip");
      chp.appendChild(el("span", "", a.name));
      const sz = el("select"); sz.setAttribute("aria-label", "Snooze " + a.name); sz.style.minHeight = "28px"; sz.style.padding = "0 4px";
      [["", "Snooze…"], ["1", "1 day"], ["3", "3 days"], ["7", "7 days"]].forEach(([v, l]) => { const o = el("option", "", l); o.value = v; sz.appendChild(o); });
      sz.addEventListener("change", () => sz.value && act("snooze", {scan: s.id, key: a.key, days: Number(sz.value)}));
      chp.appendChild(sz);
      yr.appendChild(chp);
    });
    body.appendChild(yr);
    if (s.snoozes.length) {
      const sr = el("div", "row");
      sr.appendChild(el("b", "", "Snoozed"));
      s.snoozes.forEach((a) => {
        const chp = el("span", "achip");
        chp.appendChild(el("span", "", a.name + " until " + a.until));
        chp.appendChild(button("×", "Stop snoozing " + a.name, () => act("unsnooze", {scan: s.id, key: a.key})));
        sr.appendChild(chp);
      });
      body.appendChild(sr);
    }

    const res = el("div", "");
    const rt = el("div", "muted", s.results_title || (s.last_text + ". Press ▶ to run it now."));
    if (s.evidence) { const ev = el("span", "ev", s.evidence.icon); ev.title = s.evidence.hover; ev.setAttribute("aria-label", s.evidence.hover); rt.appendChild(ev); }
    res.appendChild(rt);
    if (s.results.length) {
      const tb = el("table");
      const tr = el("tr"); ["Asset", "Answer", "Deciding line"].forEach((h) => tr.appendChild(el("th", "", h)));
      tb.appendChild(tr);
      s.results.forEach((r) => {
        const row = el("tr");
        row.appendChild(el("td", "", r.asset));
        const ans = el("td", r.answer === "yes" ? "y" : r.answer === "no" ? "n" : "u", r.answer === "yes" ? "Yes" : r.answer === "no" ? "No" : "Unknown");
        ans.title = {yes: "Yes: conditions met", no: "No: a condition failed"}[r.answer] || "Unknown: nothing failed, but some data is missing";
        if (r.data) { const d = el("span", "ev", r.data.icon); d.title = r.data.hover; d.setAttribute("aria-label", r.data.hover); ans.appendChild(d); }
        if (r.armed) {
          const a = el("span", "armed", "⏭ " + r.armed.left);
          const hover = "Armed: the first step was seen; the next can still come in time (" + r.armed.left +
                        " close" + (r.armed.left === 1 ? "" : "s") + " left). Not a match yet. " + r.armed.text;
          a.title = hover; a.setAttribute("aria-label", hover);
          ans.appendChild(a);
        }
        row.appendChild(ans);
        row.appendChild(el("td", "", r.reason));
        tb.appendChild(row);
      });
      res.appendChild(tb);
    }
    body.appendChild(res);
    return c;
  }

  window.__prismDraw = () => component.__redraw && component.__redraw();
}
"""

# The board redraws itself on local changes (open/close, select) by re-running its own function with the same data.
JS = JS.replace("export default function(component) {", """export default function prismBoard(component) {
  component.__redraw = () => prismBoard(component);""", 1)

_COMPONENT = None


def component():
    global _COMPONENT
    if _COMPONENT is None:
        import streamlit as st

        _COMPONENT = st.components.v2.component("prism_board", js=JS, css=CSS)
    return _COMPONENT
