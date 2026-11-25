"""
📓 The Logbook as a pull-out on the left edge (20 Nov 2026), the mirror of the ✨ AI pull-out on the right: a 📓 handle
just under the sidebar's handle slides out a panel with the Logbook in it (today's Passage Plan, written and spoken,
the plans before it, the Morning Outlook, and the spoken plan's settings). Your trades will join it.

Like the AI panel, the panel holds the Logbook page itself (?view=logbook&inpanel=1) in a frame, made the first time
it is opened and kept afterwards, so a playing briefing carries on when the panel is closed. The ⧉ button opens the
same page in its own window (as the social panel and the sections do) and puts the panel away. Pinned (the default),
it stays open and the page makes room for it on a wide screen; unpinned, a click on the page closes it. On a phone it
covers the whole screen.
"""

from __future__ import annotations

import i18n
from i18n import t

_COMPONENT: list = []

TIP = i18n.mark("📓 Logbook: today's Passage Plan to read or hear, the plans before it, and the Morning Outlook.")

POP_SVG = ("<svg viewBox='0 0 24 24' width='15' height='15' aria-hidden='true' fill='none' stroke='currentColor' "
           "stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 4h6v6'/><path d='M20 4 10 14'/>"
           "<path d='M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5'/></svg>")

CSS = """
.st-key-ang_log_panel{display:none !important;}
#ang-log-root{position:fixed;inset:0;z-index:10000001;pointer-events:none;}  /* above the social panel's dimmed cover, like ✨ AI (25 Nov 2026) */
#ang-log-root .log-edge{position:fixed;top:calc(3rem + env(safe-area-inset-top, 0px));left:var(--log-tab-left,0px);
  pointer-events:auto;display:flex;align-items:center;justify-content:center;width:2rem;height:2rem;padding:0;
  font-size:1rem;line-height:1;border:1px solid rgba(49,51,63,.2);border-left:0;border-radius:0 .5rem .5rem 0;
  background:#fff;cursor:pointer;box-shadow:1px 1px 4px rgba(0,0,0,.08);transition:left .22s ease,background .15s ease;}
#ang-log-root .log-edge:hover{background:#f0f2f6;}
#ang-log-root .log-panel{position:absolute;top:0;left:var(--log-tab-left,0px);height:100%;
  width:min(var(--log-width,440px),100vw);display:flex;flex-direction:column;background:var(--ang-section,#fff);
  color:inherit;box-shadow:12px 0 40px rgba(17,24,39,.18);transform:translateX(-110%);transition:transform .22s ease;
  pointer-events:auto;visibility:hidden;}
#ang-log-root.is-open .log-panel{transform:none;visibility:visible;}
#ang-log-root.is-open .log-edge{left:calc(var(--log-tab-left,0px) + min(var(--log-width,440px),calc(100vw - 2.25rem)));}
#ang-log-root .log-grip{position:absolute;top:0;bottom:0;right:0;width:12px;z-index:3;cursor:col-resize;
  touch-action:none;user-select:none;}
#ang-log-root .log-grip::before{content:'';position:absolute;top:50%;right:3px;width:4px;height:48px;margin-top:-24px;
  border-radius:999px;background:#9ca3af;}
#ang-log-root .log-grip:hover::before,#ang-log-root .log-grip.is-dragging::before{background:#111827;}
html.angstrom-night #ang-log-root .log-grip::before{background:#6b7280;}
html.angstrom-night #ang-log-root .log-grip:hover::before{background:#e5e7eb;}
#ang-log-root.is-width-dragging .log-body iframe{pointer-events:none;}
#ang-log-root.is-width-dragging,#ang-log-root.is-width-dragging *{cursor:col-resize !important;user-select:none !important;}
#ang-log-root .log-head{flex:none;display:flex;align-items:center;gap:8px;padding:10px 16px 8px 2.75rem;
  border-bottom:1px solid rgba(127,127,127,.25);}
#ang-log-root .log-title{font-weight:650;font-size:1.05rem;}
#ang-log-root .log-actions{margin-left:auto;display:flex;gap:6px;}
#ang-log-root .log-actions button{width:28px;height:28px;padding:0;display:inline-flex;align-items:center;
  justify-content:center;background:rgba(127,127,127,.15);border:0;border-radius:999px;cursor:pointer;color:inherit;}
#ang-log-root .log-pin.is-on{background:#111827;color:#fff;}
html.angstrom-night #ang-log-root .log-pin.is-on{background:#f3f4f6;color:#111827;}
#ang-log-root .log-body{flex:1;min-height:0;position:relative;}
#ang-log-root .log-body iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:transparent;}
html.angstrom-night #ang-log-root .log-edge{background:#262730;border-color:rgba(250,250,250,.2);}
html.angstrom-night #ang-log-root .log-edge:hover{background:#31333f;}
@media print{#ang-log-root{display:none !important;}}
/* One row down on a wider screen (25 Nov 2026): the sidebar and social handles keep the top row to themselves, and this panel's header lines up with its own handle. */
@media (min-width: 641px){#ang-log-root .log-panel{top:calc(2.75rem + env(safe-area-inset-top, 0px));height:calc(100% - 2.75rem - env(safe-area-inset-top, 0px));border-top-right-radius:10px;}}
@media (max-width: 640px){
  #ang-log-root .log-panel{width:100vw;left:0;}
  #ang-log-root .log-grip,#ang-log-root .log-pin{display:none !important;}
  #ang-log-root.is-open .log-edge{display:none;}
  /* the right-hand handles (AI, social) sit over the panel's right edge on a phone: keep the buttons clear of them */
  #ang-log-root .log-head{padding-right:calc(2.75rem + env(safe-area-inset-right, 0px));}
}
"""

JS = """
export default function(component) {
  const { data } = component;
  const d = data || {};
  const words = { tip: d.tip || "Logbook", title: T("Logbook"), close: T("Close"),
                  pin: T("Pin the panel beside the page: the page makes room for it and it stays open"),
                  pop: T("Open this panel in its own window"), resize: T("Drag to resize the panel") };
  const PIN_SVG = "<svg viewBox='0 0 24 24' width='15' height='15' aria-hidden='true' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M9 4h6l-1 6 3 3H7l3-3z'/><path d='M12 13v7'/></svg>";
  const CLOSE_SVG = "<svg viewBox='0 0 24 24' width='15' height='15' aria-hidden='true' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M6 6l12 12'/><path d='M18 6 6 18'/></svg>";
  const store = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } };
  let root = document.getElementById("ang-log-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "ang-log-root";
    root.innerHTML = "<div class='log-panel' role='dialog'><div class='log-grip' role='separator' aria-orientation='vertical'></div>"
      + "<div class='log-head'><div class='log-title'>📓 <span></span></div><div class='log-actions'>"
      + "<button type='button' class='log-pop'>" + (d.pop || "⧉") + "</button>"
      + "<button type='button' class='log-pin'>" + PIN_SVG + "</button>"
      + "<button type='button' class='log-close'>" + CLOSE_SVG + "</button></div></div>"
      + "<div class='log-body'></div></div><button type='button' class='log-edge'>📓</button>";
    document.body.appendChild(root);
    const panel = root.querySelector(".log-panel");
    const edge = root.querySelector(".log-edge");
    const pin = root.querySelector(".log-pin");
    const grip = root.querySelector(".log-grip");
    const address = (inpanel) => window.location.origin + window.location.pathname + "?view=logbook" + (inpanel ? "&inpanel=1" : "");
    window.angstromOpenLogbook = () => {
      const body = root.querySelector(".log-body");
      if (!body.querySelector("iframe")) {
        const frame = document.createElement("iframe");
        frame.title = words.title;
        frame.setAttribute("allow", "autoplay; clipboard-read; clipboard-write");
        frame.src = address(true);
        body.appendChild(frame);
      }
      root.classList.add("is-open");
      root.__dock();
      document.dispatchEvent(new CustomEvent("ang-panel-open", { detail: "log" }));
    };
    window.angstromCloseLogbook = () => { root.classList.remove("is-open"); root.__dock(); };
    edge.addEventListener("click", () => (root.classList.contains("is-open") ? window.angstromCloseLogbook() : window.angstromOpenLogbook()));
    root.querySelector(".log-close").addEventListener("click", () => window.angstromCloseLogbook());
    root.querySelector(".log-pop").addEventListener("click", () => {
      const opened = window.open(address(false), "ang_popout_logbook", "popup=yes,width=560,height=860");
      if (!opened) window.open(address(false), "_blank");
      const frame = root.querySelector(".log-body iframe");     // no second copy playing in the panel
      if (frame) frame.remove();
      window.angstromCloseLogbook();
    });
    root.__pinned = store("angLogPinned") !== "0";
    const paintPin = () => { pin.classList.toggle("is-on", root.__pinned); pin.setAttribute("aria-pressed", root.__pinned ? "true" : "false"); };
    root.__dock = () => {
      const on = root.__pinned && root.classList.contains("is-open") && window.innerWidth >= 900;
      const w = getComputedStyle(root).getPropertyValue("--log-width").trim() || "440px";
      document.documentElement.style.setProperty("--ang-dock-log", on ? w : "0px");
    };
    paintPin();
    pin.addEventListener("click", () => { root.__pinned = !root.__pinned; store("angLogPinned", root.__pinned ? "1" : "0"); paintPin(); root.__dock(); });
    window.addEventListener("resize", () => root.__dock());
    document.addEventListener("pointerdown", (e) => {
      if (root.__pinned || !root.classList.contains("is-open")) return;
      if (panel.contains(e.target) || edge.contains(e.target)) return;
      // Opening or using another panel (📓 Logbook, ✨ AI, social) never closes this one (25 Nov 2026).
      if (e.target.closest && e.target.closest("#ang-log-root, #ang-ai-root, #social-stream-root")) return;
      window.angstromCloseLogbook();
    });
    // A phone or narrow screen shows one panel at a time; Escape closes this panel when it isn't pinned (25 Nov 2026).
    document.addEventListener("ang-panel-open", (e) => {
      if (e.detail !== "log" && window.innerWidth < 900 && root.classList.contains("is-open")) window.angstromCloseLogbook();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !root.__pinned && root.classList.contains("is-open")) window.angstromCloseLogbook();
    });
    // The handle sits under the sidebar's own handle, and moves with it when the sidebar opens or closes.
    const follow = () => {
      const tab = document.querySelector(".angstrom-sidebar-tab");
      const sidebar = document.querySelector("[data-testid='stSidebar']");
      let left = 0;
      if (tab && !tab.hidden) left = parseFloat(tab.style.left) || 0;
      else if (sidebar && sidebar.getAttribute("data-collapsed") !== "true") left = Math.max(0, Math.round(sidebar.getBoundingClientRect().right));
      root.style.setProperty("--log-tab-left", left + "px");
    };
    follow();
    window.setInterval(follow, 400);
    const pageRoomWithout = (mine) => {     // the page's width if this panel made no room (25 Nov 2026 audit)
      const d = document.documentElement.style;
      const others = ["--ang-dock-ai", "--ang-dock-log", "--ang-dock-social"].filter((v) => v !== mine)
        .reduce((a, v) => a + (parseFloat(d.getPropertyValue(v)) || 0), 0);
      const sb = document.querySelector("[data-testid='stSidebar']");
      const side = sb && sb.getAttribute("data-collapsed") !== "true" ? sb.getBoundingClientRect().width : 0;
      return window.innerWidth - side - others;
    };
    const PAGE_MIN = 420;                    // a docked panel never leaves the page narrower than this
    const applyWidth = (px) => {
      const docked = root.__pinned && root.classList.contains("is-open") && window.innerWidth >= 900;
      const tabLeft = parseFloat(root.style.getPropertyValue("--log-tab-left")) || 0;
      const room = docked ? pageRoomWithout("--ang-dock-log") - PAGE_MIN : 900;
      const max = Math.max(320, Math.min(900, window.innerWidth - 36 - tabLeft, room));
      const next = Math.min(max, Math.max(320, Math.round(px)));
      root.style.setProperty("--log-width", next + "px");
      root.__dock();
      return next;
    };
    const saved = Number(store("angLogWidth"));
    applyWidth(saved >= 320 ? saved : 440);
    grip.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      root.classList.add("is-width-dragging");
      document.documentElement.classList.add("ang-panel-drag");
      grip.classList.add("is-dragging");
      try { grip.setPointerCapture(event.pointerId); } catch (error) {}
      let last = saved >= 320 ? saved : 440;
      const start = panel.getBoundingClientRect().left;
      const move = (m) => { last = applyWidth(m.clientX - start); };
      const stop = (end) => {
        root.classList.remove("is-width-dragging");
        document.documentElement.classList.remove("ang-panel-drag");
        grip.classList.remove("is-dragging");
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", stop);
        window.removeEventListener("pointercancel", stop);
        try { grip.releasePointerCapture(end.pointerId); } catch (error) {}
        store("angLogWidth", String(last));
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", stop);
      window.addEventListener("pointercancel", stop);
    });
  }
  // Words every run: the panel outlives a language switch.
  const edge = root.querySelector(".log-edge");
  edge.title = words.tip;
  edge.setAttribute("aria-label", words.tip);
  root.querySelector(".log-title span").textContent = words.title;
  root.querySelector(".log-panel").setAttribute("aria-label", words.title);
  for (const [cls, w] of [[".log-close", words.close], [".log-pin", words.pin], [".log-pop", words.pop]]) {
    const b = root.querySelector(cls);
    b.title = w;
    b.setAttribute("aria-label", w);
  }
  root.querySelector(".log-grip").title = words.resize;
}
"""


def mount(st) -> None:
    """Draw the 📓 handle and its panel (once per page; later runs only refresh the words)."""
    if not _COMPONENT:
        _COMPONENT.append(i18n.with_words(
            st.components.v2.component("ang_log_panel", js=i18n.js_ready(JS), css=CSS, isolate_styles=False), JS))
    _COMPONENT[0](key="ang_log_panel", data={"tip": t(TIP), "pop": POP_SVG})
