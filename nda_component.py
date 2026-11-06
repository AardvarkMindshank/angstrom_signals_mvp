"""A signature pad for the NDA page: draw with a finger or a mouse; sends the drawing to Python as a PNG (base64)."""

from __future__ import annotations

CSS = """
.sigpad{display:flex;flex-direction:column;gap:6px;max-width:520px}
.sigpad canvas{width:100%;height:170px;border:1px solid rgba(127,127,127,.5);border-radius:10px;background:#fff;
  touch-action:none;cursor:crosshair}
.sigpad .bar{display:flex;align-items:center;gap:8px;font:13px system-ui,sans-serif;opacity:.85}
.sigpad button{font:inherit;min-height:40px;padding:0 14px;border-radius:8px;border:1px solid rgba(127,127,127,.5);
  background:transparent;color:inherit;cursor:pointer}
"""

JS = r"""
export default function(component) {
  const { parentElement } = component;
  const send = (v) => (component.setStateValue || component.setTriggerValue)("png", v);
  Array.from(parentElement.children).filter((c) => c.classList && c.classList.contains("sigpad")).forEach((c) => c.remove());
  const box = document.createElement("div");
  box.className = "sigpad";
  const cv = document.createElement("canvas");
  cv.setAttribute("aria-label", "Signature pad: draw your signature");
  cv.setAttribute("role", "img");
  const bar = document.createElement("div");
  bar.className = "bar";
  const clear = document.createElement("button");
  clear.type = "button"; clear.textContent = "Clear";
  const note = document.createElement("span");
  note.textContent = "Sign inside the box.";
  bar.appendChild(clear); bar.appendChild(note);
  box.appendChild(cv); box.appendChild(bar);
  parentElement.appendChild(box);

  const ratio = window.devicePixelRatio || 1;
  function size() {
    const r = cv.getBoundingClientRect();
    cv.width = Math.max(300, Math.round(r.width * ratio));
    cv.height = Math.round(170 * ratio);
    const g = cv.getContext("2d");
    g.fillStyle = "#fff"; g.fillRect(0, 0, cv.width, cv.height);
    g.lineWidth = 2.4 * ratio; g.lineCap = "round"; g.lineJoin = "round"; g.strokeStyle = "#111";
  }
  size();
  const g = cv.getContext("2d");
  let drawing = false, last = null, inked = 0;
  function at(e) { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * ratio, (e.clientY - r.top) * ratio]; }
  cv.addEventListener("pointerdown", (e) => { e.preventDefault(); drawing = true; last = at(e); cv.setPointerCapture(e.pointerId); });
  cv.addEventListener("pointermove", (e) => {
    if (!drawing) return;
    e.preventDefault();
    const p = at(e);
    g.beginPath(); g.moveTo(last[0], last[1]); g.lineTo(p[0], p[1]); g.stroke();
    inked += Math.hypot(p[0] - last[0], p[1] - last[1]);
    last = p;
  });
  function finish() {
    if (!drawing) return;
    drawing = false;
    if (inked > 60 * ratio) {
      note.textContent = "Signature captured.";
      window.__sigPng = cv.toDataURL("image/png");
      send(window.__sigPng.split(",")[1]);
    }
  }
  cv.addEventListener("pointerup", finish);
  cv.addEventListener("pointercancel", finish);
  cv.addEventListener("pointerleave", finish);
  clear.addEventListener("click", () => { size(); inked = 0; window.__sigPng = null; note.textContent = "Sign inside the box."; send(""); });
  if (window.__sigPng) {            // the page redrew (for example while typing the name): keep the drawing
    const img = new Image();
    img.onload = () => { g.drawImage(img, 0, 0, cv.width, cv.height); inked = 1e9; note.textContent = "Signature captured."; };
    img.src = window.__sigPng;
  }
}
"""

_COMPONENT = None


def pad(key: str):
    global _COMPONENT
    if _COMPONENT is None:
        import streamlit as st

        _COMPONENT = st.components.v2.component("nda_signature_pad", js=JS, css=CSS)
    try:
        return _COMPONENT(key=key, on_png_change=lambda: None)
    except Exception:
        return None
