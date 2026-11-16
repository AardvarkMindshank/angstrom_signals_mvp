"""
✨ The AI Navigator as a pull-out on the right edge (16 Nov 2026), in the same place on every page: a "✨" handle just
under the social/chat arrow slides out a panel with the Navigator in it. It replaced the three ✨ AI buttons (top
bar, beside the Lattice tabs, beside the Tides daily note).

The panel holds the Navigator page itself (?view=advisor&from=panel&inpanel=1; not "embed", which Streamlit keeps for
itself) in a frame, made the first time it is opened and kept afterwards, so the conversation carries on when the
panel is closed and opened again, and the page under it stays free to use. The frame signs in the way the pop-out
windows do (it asks this signed-in page).
One right-edge panel at a time: opening the AI closes social and chat, and opening social and chat closes the AI.
On a phone the panel covers the whole screen.

Elsewhere, window.angstromOpenAI({from, ask}) opens it with a request, such as Tides' Today's AI Passage Plan.
"""

from __future__ import annotations

import i18n
from i18n import t

_COMPONENT: list = []

TIP = i18n.mark("✨ AI Navigator: ask anything about the app, the asset you have selected, your ideas, Groups, Sets "
                "and funnels, or today's Tides. It explains; you do the clicks. No buy or sell calls.")

_SPARKLE = ("<svg viewBox='0 0 24 24' width='18' height='18' fill='currentColor' aria-hidden='true'><path d='M19 9l1.25-"
            "2.75L23 5.5l-2.75-1.25L19 1.5l-1.25 2.75L15 5.5l2.75 1.25L19 9zm-7.5.5L9 4 6.5 9.5 1 12l5.5 2.5L9 20l2.5"
            "-5.5L17 12l-5.5-2.5zM19 15l-1.25 2.75L15 19l2.75 1.25L19 23l1.25-2.75L23 19l-2.75-1.25L19 15z'/></svg>")

CSS = """
.st-key-ang_ai_panel{display:none !important;}
#ang-ai-root{position:fixed;inset:0;z-index:10000001;pointer-events:none;}
#ang-ai-root .ai-edge{position:fixed;top:calc(3rem + env(safe-area-inset-top, 0px));right:0;pointer-events:auto;
  display:flex;align-items:center;justify-content:center;width:2rem;height:2rem;padding:0;
  border:1px solid rgba(49,51,63,.2);border-right:0;border-radius:.5rem 0 0 .5rem;background:#fff;color:#f5a524;
  cursor:pointer;box-shadow:-1px 1px 4px rgba(0,0,0,.08);transition:right .22s ease,background .15s ease;}
#ang-ai-root .ai-edge svg{filter:drop-shadow(0 0 2px rgba(245,165,36,.35));}
#ang-ai-root .ai-edge:hover{background:#f0f2f6;}
#ang-ai-root .ai-panel{position:absolute;top:0;right:0;height:100%;width:min(460px,100vw);display:flex;
  flex-direction:column;background:var(--ang-section,#fff);color:inherit;box-shadow:-12px 0 40px rgba(17,24,39,.18);
  transform:translateX(100%);transition:transform .22s ease;pointer-events:auto;visibility:hidden;}
#ang-ai-root.is-open .ai-panel{transform:none;visibility:visible;}
#ang-ai-root.is-open .ai-edge{right:min(460px,calc(100vw - 2.25rem));}
#ang-ai-root .ai-head{flex:none;display:flex;align-items:center;gap:8px;padding:10px 12px 8px 16px;
  border-bottom:1px solid rgba(127,127,127,.25);}
#ang-ai-root .ai-head .ai-title{font-weight:650;font-size:1.05rem;display:flex;align-items:center;gap:6px;}
#ang-ai-root .ai-head .ai-title svg{color:#f5a524;}
#ang-ai-root .ai-head .ai-close{margin-left:auto;background:rgba(127,127,127,.15);border:0;border-radius:999px;
  padding:6px 12px;font:inherit;font-weight:600;cursor:pointer;color:inherit;}
#ang-ai-root .ai-body{flex:1;min-height:0;position:relative;}
#ang-ai-root .ai-body iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:transparent;}
#ang-ai-root.social-open:not(.is-open) .ai-edge{display:none;}
html.angstrom-night #ang-ai-root .ai-edge{background:#262730;border-color:rgba(250,250,250,.2);}
html.angstrom-night #ang-ai-root .ai-edge:hover{background:#31333f;}
@media (max-width: 640px){
  #ang-ai-root .ai-panel{width:100vw;}
  #ang-ai-root.is-open .ai-edge{display:none;}
}
"""

JS = """
export default function(component) {
  const { data } = component;
  const d = data || {};
  const words = { tip: d.tip || "AI Navigator", title: T("✨ AI Navigator").replace(/^✨\\s*/, ""), close: T("Close") };
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
    const close = document.createElement("button");
    close.type = "button";
    close.className = "ai-close";
    head.append(title, close);
    const body = document.createElement("div");
    body.className = "ai-body";
    panel.append(head, body);
    root.append(panel, edge);
    document.body.appendChild(root);
    edge.addEventListener("click", () => (root.classList.contains("is-open") ? window.angstromCloseAI() : window.angstromOpenAI()));
    close.addEventListener("click", () => window.angstromCloseAI());
  }
  // Words every run: the panel outlives a language switch.
  const edge = root.querySelector(".ai-edge");
  edge.title = words.tip;
  edge.setAttribute("aria-label", words.tip);
  root.querySelector(".ai-title").innerHTML = (d.sparkle || "✨") + "<span></span>";
  root.querySelector(".ai-title span").textContent = words.title;
  root.querySelector(".ai-close").textContent = "✕ " + words.close;
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
    const social = window.socialStreamState;        // one right-edge panel at a time
    if (social && social.open) {
      social.open = false;
      if (window.renderSocialStream) window.renderSocialStream();
    }
    root.classList.add("is-open");
  };
  window.angstromCloseAI = () => root.classList.remove("is-open");

  // Opening social and chat closes the AI panel. The social panel can be rebuilt, so watch whichever is there now.
  const stream = document.getElementById("social-stream-root");
  if (stream && !stream.__angAiWatch) {
    stream.__angAiWatch = true;
    new MutationObserver(() => {
      const socialOpen = stream.classList.contains("is-open");
      root.classList.toggle("social-open", socialOpen);          // its handle would sit on the social panel
      if (socialOpen && root.classList.contains("is-open")) window.angstromCloseAI();
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
