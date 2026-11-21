"""
✨ The AI Navigator as a pull-out on the right edge (16 Nov 2026), in the same place on every page: a "✨" handle just
under the social/chat arrow slides out a panel with the Navigator in it. It replaced the three ✨ AI buttons (top
bar, beside the Lattice tabs, beside the Tides daily note).

The panel holds the Navigator page itself (?view=advisor&from=panel&inpanel=1; not "embed", which Streamlit keeps for
itself) in a frame, made the first time it is opened and kept afterwards, so the conversation carries on when the
panel is closed and opened again, and the page under it stays free to use. The frame signs in the way the pop-out
windows do (it asks this signed-in page).
The ⧉ button opens the Navigator in its own window instead (20 Nov 2026).
One right-edge panel at a time: opening the AI closes social and chat, and opening social and chat closes the AI.
On a phone the panel covers the whole screen.

Elsewhere, window.angstromOpenAI({from, ask}) opens it with a request, such as Tides' Today's AI Passage Plan.
"""

from __future__ import annotations

import i18n
from i18n import t

_COMPONENT: list = []

# The page makes room for a pinned right-hand panel (this one or social and chat): see app.py's --ang-dock-* rule.
TIP = i18n.mark("✨ AI Navigator: ask anything about the app, the asset you have selected, your ideas, Groups, Sets "
                "and funnels, or today's Tides. It explains; you do the clicks. No buy or sell calls.")

_SPARKLE = ("<svg viewBox='0 0 24 24' width='18' height='18' fill='currentColor' aria-hidden='true'><path d='M19 9l1.25-"
            "2.75L23 5.5l-2.75-1.25L19 1.5l-1.25 2.75L15 5.5l2.75 1.25L19 9zm-7.5.5L9 4 6.5 9.5 1 12l5.5 2.5L9 20l2.5"
            "-5.5L17 12l-5.5-2.5zM19 15l-1.25 2.75L15 19l2.75 1.25L19 23l1.25-2.75L23 19l-2.75-1.25L19 15z'/></svg>")

CSS = """
.st-key-ang_ai_panel{display:none !important;}
#ang-ai-root{position:fixed;inset:0;z-index:10000001;pointer-events:none;}
#ang-ai-root .ai-edge{position:fixed;top:calc(3rem + env(safe-area-inset-top, 0px));right:var(--ai-right,0px);pointer-events:auto;
  display:flex;align-items:center;justify-content:center;width:2rem;height:2rem;padding:0;
  border:1px solid rgba(49,51,63,.2);border-right:0;border-radius:.5rem 0 0 .5rem;background:#fff;color:#f5a524;
  cursor:pointer;box-shadow:-1px 1px 4px rgba(0,0,0,.08);transition:right .22s ease,background .15s ease;}
#ang-ai-root .ai-edge svg{filter:drop-shadow(0 0 2px rgba(245,165,36,.35));}
#ang-ai-root .ai-edge:hover{background:#f0f2f6;}
#ang-ai-root .ai-panel{position:absolute;top:0;right:var(--ai-right,0px);height:100%;width:min(var(--ai-width,460px),100vw);display:flex;
  flex-direction:column;background:var(--ang-section,#fff);color:inherit;box-shadow:-12px 0 40px rgba(17,24,39,.18);
  transform:translateX(calc(100% + var(--ai-right,0px)));transition:transform .22s ease,right .22s ease;pointer-events:auto;visibility:hidden;}
#ang-ai-root.is-open .ai-panel{transform:none;visibility:visible;}
#ang-ai-root.is-open .ai-edge{right:calc(var(--ai-right,0px) + min(var(--ai-width,460px),calc(100vw - 2.25rem)));}
#ang-ai-root .ai-grip{position:absolute;top:0;bottom:0;left:0;width:12px;z-index:3;cursor:col-resize;touch-action:none;
  user-select:none;}
#ang-ai-root .ai-grip::before{content:'';position:absolute;top:50%;left:3px;width:4px;height:48px;margin-top:-24px;
  border-radius:999px;background:#9ca3af;}
#ang-ai-root .ai-grip:hover::before,#ang-ai-root .ai-grip.is-dragging::before{background:#111827;}
html.angstrom-night #ang-ai-root .ai-grip::before{background:#6b7280;}
html.angstrom-night #ang-ai-root .ai-grip:hover::before,html.angstrom-night #ang-ai-root .ai-grip.is-dragging::before{background:#e5e7eb;}
#ang-ai-root.is-width-dragging .ai-body iframe{pointer-events:none;}
#ang-ai-root.is-width-dragging,#ang-ai-root.is-width-dragging *{cursor:col-resize !important;user-select:none !important;}
#ang-ai-root .ai-head .ai-actions{margin-left:auto;display:flex;gap:6px;}
#ang-ai-root .ai-head .ai-pin,#ang-ai-root .ai-head .ai-close,#ang-ai-root .ai-head .ai-pop{width:28px;height:28px;padding:0;display:inline-flex;
  align-items:center;justify-content:center;background:rgba(127,127,127,.15);border:0;border-radius:999px;cursor:pointer;
  color:inherit;}
#ang-ai-root .ai-head .ai-pin.is-on{background:#111827;color:#fff;}
html.angstrom-night #ang-ai-root .ai-head .ai-pin.is-on{background:#f3f4f6;color:#111827;}
#ang-ai-root .ai-head{flex:none;display:flex;align-items:center;gap:8px;padding:10px 12px 8px 16px;
  border-bottom:1px solid rgba(127,127,127,.25);}
#ang-ai-root .ai-head .ai-title{font-weight:650;font-size:1.05rem;display:flex;align-items:center;gap:6px;}
#ang-ai-root .ai-head .ai-title svg{color:#f5a524;}
#ang-ai-root .ai-body{flex:1;min-height:0;position:relative;}
#ang-ai-root .ai-body iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:transparent;}
html.angstrom-night #ang-ai-root .ai-edge{background:#262730;border-color:rgba(250,250,250,.2);}
html.angstrom-night #ang-ai-root .ai-edge:hover{background:#31333f;}
@media (max-width: 640px){
  #ang-ai-root .ai-panel{width:100vw;}
  #ang-ai-root .ai-grip,#ang-ai-root .ai-pin{display:none !important;}
  #ang-ai-root.is-open .ai-edge{display:none;}
}
"""

JS = """
export default function(component) {
  const { data } = component;
  const d = data || {};
  const words = { tip: d.tip || "AI Navigator", title: T("✨ AI Navigator").replace(/^✨\\s*/, ""), close: T("Close"),
                  pin: T("Pin the panel beside the page: the page makes room for it and it stays open"),
                  resize: T("Drag to resize the panel"), pop: T("Open this panel in its own window") };
  const POP_SVG = "<svg viewBox='0 0 24 24' width='15' height='15' aria-hidden='true' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 4h6v6'/><path d='M20 4 10 14'/><path d='M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5'/></svg>";
  const PIN_SVG = "<svg viewBox='0 0 24 24' width='15' height='15' aria-hidden='true' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M9 4h6l-1 6 3 3H7l3-3z'/><path d='M12 13v7'/></svg>";
  const CLOSE_SVG = "<svg viewBox='0 0 24 24' width='15' height='15' aria-hidden='true' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M6 6l12 12'/><path d='M18 6 6 18'/></svg>";
  let root = document.getElementById("ang-ai-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "ang-ai-root";
    const edge = document.createElement("button");
    edge.type = "button";
    edge.className = "ai-edge";
    edge.innerHTML = d.sparkle || "✨";
    const panel = document.createElement("div");
    panel.className = "ai-panel";
    panel.setAttribute("role", "dialog");
    const head = document.createElement("div");
    head.className = "ai-head";
    const title = document.createElement("div");
    title.className = "ai-title";
    const actions = document.createElement("div");
    actions.className = "ai-actions";
    const pin = document.createElement("button");
    pin.type = "button";
    pin.className = "ai-pin";
    pin.innerHTML = PIN_SVG;
    const close = document.createElement("button");
    close.type = "button";
    close.className = "ai-close";
    close.innerHTML = CLOSE_SVG;
    // ⧉ The Navigator in its own window (the ?view=advisor pop-out), and the panel put away.
    const pop = document.createElement("button");
    pop.type = "button";
    pop.className = "ai-pop";
    pop.innerHTML = POP_SVG;
    pop.addEventListener("click", () => {
      const address = window.location.origin + window.location.pathname + "?view=advisor&from=panel";
      const opened = window.open(address, "ang_popout_advisor", "popup=yes,width=620,height=880");
      if (!opened) window.open(address, "_blank");
      window.angstromCloseAI();
    });
    actions.append(pop, pin, close);
    head.append(title, actions);
    const grip = document.createElement("div");
    grip.className = "ai-grip";
    grip.setAttribute("role", "separator");
    grip.setAttribute("aria-orientation", "vertical");
    const body = document.createElement("div");
    body.className = "ai-body";
    panel.append(grip, head, body);
    root.append(panel, edge);
    document.body.appendChild(root);
    edge.addEventListener("click", () => (root.classList.contains("is-open") ? window.angstromCloseAI() : window.angstromOpenAI()));
    close.addEventListener("click", () => window.angstromCloseAI());
    // Pinned (the default, as before): it stays open while you use the page. Unpinned: a click on the page
    // outside it closes it, as the social panel does.
    const store = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } };
    root.__pinned = store("angAiPinned") !== "0";
    const paintPin = () => {
      pin.classList.toggle("is-on", root.__pinned);
      pin.setAttribute("aria-pressed", root.__pinned ? "true" : "false");
    };
    // Pinned and open on a wide screen: the page makes room for it (docked) instead of sitting under it.
    root.__dock = () => {
      const on = root.__pinned && root.classList.contains("is-open") && window.innerWidth >= 900;
      const w = getComputedStyle(root).getPropertyValue("--ai-width").trim() || "460px";
      document.documentElement.style.setProperty("--ang-dock-ai", on ? w : "0px");
    };
    paintPin();
    pin.addEventListener("click", () => {
      root.__pinned = !root.__pinned; store("angAiPinned", root.__pinned ? "1" : "0"); paintPin(); root.__dock();
    });
    window.addEventListener("resize", () => root.__dock());
    document.addEventListener("pointerdown", (e) => {
      if (root.__pinned || !root.classList.contains("is-open")) return;
      if (panel.contains(e.target) || edge.contains(e.target)) return;
      window.angstromCloseAI();
    });
    // Width: drag the grip on its left edge (320 to 900 px), remembered in this browser.
    const applyWidth = (px) => {
      const max = Math.max(320, Math.min(900, window.innerWidth - 36));
      const next = Math.min(max, Math.max(320, Math.round(px)));
      root.style.setProperty("--ai-width", next + "px");
      if (root.__dock) root.__dock();
      return next;
    };
    const saved = Number(store("angAiWidth"));
    applyWidth(saved >= 320 ? saved : 460);
    grip.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      root.classList.add("is-width-dragging");
      grip.classList.add("is-dragging");
      try { grip.setPointerCapture(event.pointerId); } catch (error) {}
      let last = saved >= 320 ? saved : 460;
      const move = (m) => { last = applyWidth(window.innerWidth - m.clientX); };
      const stop = (end) => {
        root.classList.remove("is-width-dragging");
        grip.classList.remove("is-dragging");
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", stop);
        window.removeEventListener("pointercancel", stop);
        try { grip.releasePointerCapture(end.pointerId); } catch (error) {}
        store("angAiWidth", String(last));
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", stop);
      window.addEventListener("pointercancel", stop);
    });
  }
  // Words every run: the panel outlives a language switch.
  const edge = root.querySelector(".ai-edge");
  edge.title = words.tip;
  edge.setAttribute("aria-label", words.tip);
  root.querySelector(".ai-title").innerHTML = (d.sparkle || "✨") + "<span></span>";
  root.querySelector(".ai-title span").textContent = words.title;
  root.querySelector(".ai-close").title = words.close;
  root.querySelector(".ai-close").setAttribute("aria-label", words.close);
  root.querySelector(".ai-pin").title = words.pin;
  root.querySelector(".ai-pin").setAttribute("aria-label", words.pin);
  root.querySelector(".ai-grip").title = words.resize;
  root.querySelector(".ai-pop").title = words.pop;
  root.querySelector(".ai-pop").setAttribute("aria-label", words.pop);
  root.querySelector(".ai-panel").setAttribute("aria-label", words.title);

  const address = (from, ask) => window.location.origin + window.location.pathname + "?view=advisor&inpanel=1&from="
    + encodeURIComponent(from || "panel") + (ask ? "&ask=" + encodeURIComponent(ask) : "");

  window.angstromOpenAI = (opts) => {
    const o = opts || {};
    const body = root.querySelector(".ai-body");
    let frame = body.querySelector("iframe");
    if (!frame) {
      frame = document.createElement("iframe");
      frame.title = words.title;
      frame.setAttribute("allow", "clipboard-read; clipboard-write");
      frame.src = address(o.from, o.ask);
      body.appendChild(frame);
    } else if (o.ask) {
      frame.src = address(o.from, o.ask);           // a set request (the Passage Plan) always loads
    }
    const social = window.socialStreamState;        // a phone or narrow screen: one right-edge panel at a time
    if (social && social.open && window.innerWidth < 900) {
      social.open = false;
      if (window.renderSocialStream) window.renderSocialStream();
    }
    root.classList.add("is-open");
    if (root.__dock) root.__dock();
  };
  window.angstromCloseAI = () => { root.classList.remove("is-open"); if (root.__dock) root.__dock(); };

  // Stacked like the left side (21 Nov 2026): on a wide screen, with social and chat open, the ✨ handle and panel sit
  // at the social panel's left edge, so both can be open side by side. On a narrow screen opening one closes the other.
  const stackRight = () => {
    const s = document.getElementById("social-stream-root");
    const panelEl = s && s.querySelector(".panel");
    const open = s && s.classList.contains("is-open") && window.innerWidth >= 900;
    root.style.setProperty("--ai-right", (open && panelEl ? Math.round(panelEl.getBoundingClientRect().width) : 0) + "px");
  };
  if (!root.__stackTimer) { root.__stackTimer = window.setInterval(stackRight, 400); window.addEventListener("resize", stackRight); }
  stackRight();
  // The social panel can be rebuilt, so watch whichever is there now.
  const stream = document.getElementById("social-stream-root");
  if (stream && !stream.__angAiWatch) {
    stream.__angAiWatch = true;
    new MutationObserver(() => {
      const socialOpen = stream.classList.contains("is-open");
      root.classList.toggle("social-open", socialOpen);
      stackRight();
      if (socialOpen && root.classList.contains("is-open") && window.innerWidth < 900) window.angstromCloseAI();
    }).observe(stream, { attributes: true, attributeFilter: ["class"] });
  }
  root.classList.toggle("social-open", !!(stream && stream.classList.contains("is-open")));
}
"""


def mount(st) -> None:
    """Draw the ✨ handle and its panel (once per page; later runs only refresh the words)."""
    if not _COMPONENT:
        _COMPONENT.append(i18n.with_words(
            st.components.v2.component("ang_ai_panel", js=i18n.js_ready(JS), css=CSS, isolate_styles=False), JS))
    _COMPONENT[0](key="ang_ai_panel", data={"tip": t(TIP), "sparkle": _SPARKLE})
