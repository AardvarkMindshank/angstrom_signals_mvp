"""📒 Trade Log (new): the React page (tradelog_ui/, built into static/tl2/) set into the main page (26 Nov 2026).

The page is served by the app itself (/app/static/tl2/), so it shares the app's address: it takes the signed-in pass
from the main page the way the side panels do, and its colours from the UI Colours settings. It reads one ready-made
summary (tradelog_insights.py, worked out by the background job) and pages through trades, all with the member's own
pass, so the database's row rules apply.

This file hands the page what it needs (the database address and public key, the language and its words, the plan's
periods) and holds the frame. The page's texts are its T(text) calls, translated in locales/ like everywhere else.
"""
from __future__ import annotations

import glob
import os

from i18n import current, js_words

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = sorted(glob.glob(os.path.join(HERE, "tradelog_ui", "src", "**", "*.js*"), recursive=True))
HISTORY_DAYS = {"plus": 90}          # as the classic Trade Log: Plus keeps the last 90 days

_FRAME_JS = """
export default function(component) {
  const { data, parentElement } = component;
  window.__tl2Config = data || {};
  let frame = parentElement.querySelector("iframe.tl2");
  if (!frame) {
    frame = document.createElement("iframe");
    frame.className = "tl2";
    frame.title = (data && data.title) || "Trade Log";
    frame.style.cssText = "width:100%;border:0;height:640px;display:block;background:transparent";
    frame.setAttribute("loading", "lazy");
    parentElement.appendChild(frame);
  }
  const src = "/app/static/tl2/index.html?v=" + encodeURIComponent((data && data.version) || "");
  if (frame.dataset.src !== src || frame.dataset.lang !== String(data.lang)) {
    frame.dataset.src = src;
    frame.dataset.lang = String(data.lang);
    frame.src = src;
  }
}
"""


def _sources_text() -> list[str]:
    out = []
    for path in SOURCES:
        try:
            with open(path, encoding="utf-8") as fh:
                out.append(fh.read())
        except OSError:
            continue
    return out


def _version() -> str:
    """Changes when a new build is shipped, so browsers fetch it rather than a cached copy."""
    try:
        names = sorted(os.listdir(os.path.join(HERE, "static", "tl2", "assets")))
        return ",".join(n for n in names if n.endswith(".js"))[:120]
    except OSError:
        return ""


def config(url: str, key: str, plan: str) -> dict:
    periods = ["1y"] if HISTORY_DAYS.get(plan) else ["1y", "3y", "5y", "all"]
    return {"url": url, "key": key, "lang": current(), "plan": plan, "periods": periods,
            "words": js_words(*_sources_text()), "version": _version(), "title": "Trade Log"}


_frame = None


def render(st, url: str, key: str, plan: str) -> None:
    global _frame
    if _frame is None:
        _frame = st.components.v2.component("tradelog_v2_frame", js=_FRAME_JS, isolate_styles=False)
    _frame(key="tradelog_v2_frame", data=config(url, key, plan))
