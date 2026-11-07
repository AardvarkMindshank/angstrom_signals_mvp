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
.lat.prism .ctl button{width:40px;padding:0;display:inline-flex;align-items:center;justify-content:center}
.lat.prism .ctl button.play{border-color:#0f766e;color:#0f766e;background:rgba(15,118,110,.12)}
.lat.prism .ctl button.del{border-color:rgba(220,38,38,.6);color:#dc2626}
.lat.prism .ctl button.del.arm{background:#dc2626;color:#fff;width:auto;padding:0 10px}
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

JS = r"""
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const state = data || {};
  const lib = state.library || {sets: [], groups: [], assets: []};
  const scans = state.scans || [];
  window.__prismOpen = window.__prismOpen || {};
  window.__prismPast = window.__prismPast || {};
  if (state.open_new && window.__prismOpen[state.open_new] === undefined) window.__prismOpen[state.open_new] = true;
  if (state.open_new) window.__prismSel = state.open_new;
  let sel = window.__prismSel || null;
  if (sel && !scans.some((s) => s.id === sel)) sel = null;
  let qSets = window.__prismQS || "", qAssets = window.__prismQA || "";

  Array.from(parentElement.children).filter((c) => c.classList && c.classList.contains("lat")).forEach((c) => c.remove());
  const root = el("div", "lat prism");
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
  function icon(name) {
    const paths = {
      play: '<path d="M7 4.5v15l12-7.5z" fill="currentColor" stroke="none"/>',
      past: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 8v4l3 2"/>',
      pause: '<rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none"/><rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none"/>',
      resume: '<path d="M7 4.5v15l12-7.5z"/>',
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
  libCol.appendChild(el("h3", "", "Saved Sets"));
  libCol.appendChild(el("div", "muted", "Drag a Set onto the scans, or tap + to start a scan."));
  const fs = el("input", "wide"); fs.placeholder = "Filter Sets"; fs.setAttribute("aria-label", "Filter Sets"); fs.value = qSets;
  libCol.appendChild(fs);
  const setList = el("div", "");
  libCol.appendChild(setList);
  function drawSets() {
    setList.innerHTML = "";
    const q = qSets.toLowerCase();
    const shown = lib.sets.filter((s) => !q || (s.name + " " + s.meta).toLowerCase().includes(q));
    if (!shown.length) setList.appendChild(el("div", "muted", lib.sets.length ? "No Set matches." : "No Sets with a decision yet: make one in Signal Sets."));
    shown.forEach((s) => {
      const c = el("div", "chip");
      c.draggable = true;
      c.addEventListener("dragstart", (e) => e.dataTransfer.setData("text/plain", JSON.stringify({type: "set", key: s.key})));
      const nm = el("div", "nm"); nm.appendChild(el("div", "", s.name)); nm.appendChild(el("div", "muted", s.meta));
      c.appendChild(nm);
      c.appendChild(button("+", "Start a scan with " + s.name, () => act("create", {set: s.key}), "sq"));
      setList.appendChild(c);
    });
  }
  fs.addEventListener("input", () => { qSets = fs.value; window.__prismQS = qSets; drawSets(); });
  drawSets();

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
    ctl.appendChild(iconButton(s.paused ? "resume" : "pause", s.paused ? "Resume: the first run after resuming records answers without alerting" : "Pause: keeps the scan, stops runs and alerts", () => act(s.paused ? "resume" : "pause", {scan: s.id})));
    ctl.appendChild(iconButton("copy", "Duplicate (the copy runs only when you press Play until you schedule it)", () => act("duplicate", {scan: s.id})));
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
      ch.appendChild(button("×", "Remove " + a.label, () => act("remove_asset", {scan: s.id, index: i})));
      ar.appendChild(ch);
    });
    ar.appendChild(el("span", "muted", s.asset_count + " assets now · drop assets or a group here, or tap + in the list"));
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
    const saveRuns = button("Save", "Save when the scan runs", () => act("schedule", {scan: s.id, runs: runs.value, times: times.value, days: days.value, tz: tz.value}), "on");
    rr.appendChild(saveRuns);
    runs.addEventListener("change", showTimes);
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
    res.appendChild(el("div", "muted", s.results_title || (s.last_text + ". Press ▶ to run it now.")));
    if (s.results.length) {
      const tb = el("table");
      const tr = el("tr"); ["Asset", "Answer", "Deciding line"].forEach((h) => tr.appendChild(el("th", "", h)));
      tb.appendChild(tr);
      s.results.forEach((r) => {
        const row = el("tr");
        row.appendChild(el("td", "", r.asset));
        row.appendChild(el("td", r.answer === "yes" ? "y" : r.answer === "no" ? "n" : "u", r.answer === "yes" ? "Yes" : r.answer === "no" ? "No" : "Unknown"));
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
