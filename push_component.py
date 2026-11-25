"""
📱 Turn phone or desktop notifications on or off for THIS device (Settings → Notifications).

The browser does the asking (the permission prompt needs a tap) and makes the push address; the app saves it
(push_subscribe in sql/2026-11-28_push_notifications.sql). On an iPhone, notifications only work in the home-screen
app (added from Safari's Share menu), so there the box explains that instead.

The box sends {action: "on" | "off" | "test", sub?, endpoint?, device?, nonce} through the "push" trigger.
"""

from __future__ import annotations

import json

import i18n

CSS = """
.angpush{font:13px/1.45 inherit;color:inherit;display:flex;flex-direction:column;gap:8px;margin:2px 0 4px}
.angpush .row{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.angpush button{font:inherit;padding:5px 12px;border-radius:8px;cursor:pointer;border:1px solid rgba(127,127,127,.45);
  background:rgba(127,127,127,.08);color:inherit}
.angpush button.main{border-color:#0f766e;background:rgba(15,118,110,.16)}
.angpush button:disabled{opacity:.5;cursor:default}
.angpush .state{opacity:.9}
.angpush .quiet{opacity:.7;font-size:12px}
.angpush ol{margin:0;padding-left:20px}
"""

JS = r"""
export default function anglePush(component) {
  const { data, setTriggerValue, parentElement } = component;
  const d = data || {};
  Array.from(parentElement.children).forEach((c) => { if (c.classList && c.classList.contains("angpush")) c.remove(); });
  const root = document.createElement("div");
  root.className = "angpush";
  parentElement.appendChild(root);
  const send = (body) => setTriggerValue("push", JSON.stringify({ ...body, nonce: Date.now() + Math.random() }));
  const line = (html, cls) => { const p = document.createElement("div"); p.className = cls || "state"; p.innerHTML = html; root.appendChild(p); return p; };
  const button = (row, text, tip, main, onClick) => {
    const b = document.createElement("button"); b.type = "button"; b.textContent = text; b.title = tip;
    if (main) b.className = "main"; b.onclick = onClick; row.appendChild(b); return b;
  };
  const ua = navigator.userAgent || "";
  const apple = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const device = apple ? (/iPad/.test(ua) || navigator.maxTouchPoints > 1 && !/iPhone/.test(ua) ? "iPad" : "iPhone")
    : /Android/.test(ua) ? "Android device" : /Windows/.test(ua) ? "Windows computer" : /Mac/.test(ua) ? "Mac" : "computer";
  const shown = T(device);
  const supported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

  if (apple && !standalone) {
    line(T("On an {device}, notifications work in the <b>MarketNavi app on your Home Screen</b>:", {device: shown}));
    const ol = document.createElement("ol");
    ol.innerHTML = "<li>" + T("Open this site in <b>Safari</b>.") + "</li><li>" +
      T("Tap <b>Share</b> (the square with an arrow), then <b>Add to Home Screen</b>.") + "</li><li>" +
      T("Open MarketNavi from its new icon, sign in, and turn notifications on here.") + "</li>";
    root.appendChild(ol);
    line(T("Needs iOS 16.4 or later."), "quiet");
    return;
  }
  if (!supported) { line(T("This browser can't show notifications from websites. Try Chrome, Edge, Firefox or Safari.")); return; }
  if (!d.key) { line(T("Notifications aren't set up on the server yet.")); return; }
  if (Notification.permission === "denied") {
    line(T("Notifications are <b>blocked</b> for this site in your browser's settings. Allow them there, then reload."));
    return;
  }

  const keyBytes = (b64) => {
    const pad = "=".repeat((4 - (b64.length % 4)) % 4);
    const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from(raw, (c) => c.charCodeAt(0));
  };
  const activeWorker = async () => {
    const reg = await navigator.serviceWorker.register("/app/static/sw.js", { scope: "/app/static/" });
    if (reg.active) return reg;
    const w = reg.installing || reg.waiting;
    if (w) await new Promise((ok) => { w.addEventListener("statechange", () => { if (w.state === "activated") ok(); }); setTimeout(ok, 4000); });
    return reg;
  };
  const status = line(T("Checking this device…"));
  const row = document.createElement("div"); row.className = "row"; root.appendChild(row);
  const note = line("", "quiet");
  const saved = new Set(d.endpoints || []);

  (async () => {
    let reg;
    try { reg = await activeWorker(); } catch (e) { status.textContent = T("Notifications couldn't start on this device."); return; }
    let sub = await reg.pushManager.getSubscription();
    if (sub && !saved.has(sub.endpoint)) {          // signed up before, but the app doesn't know it (or another account)
      send({ action: "on", sub: sub.toJSON(), device });
      status.innerHTML = T("Turning notifications on for this {device}…", {device: shown});
      return;
    }
    if (sub) {
      status.innerHTML = T("✅ Notifications are <b>on</b> for this {device}.", {device: shown});
      button(row, T("📨 Send a test"), T("Send a test notification to your devices"), false, () => { send({ action: "test" }); note.textContent = T("Test sent. It should arrive in a few seconds."); });
      button(row, T("Turn off"), T("Stop notifications on this device"), false, async () => {
        try { await sub.unsubscribe(); } catch (e) { /* already gone */ }
        send({ action: "off", endpoint: sub.endpoint });
      });
      return;
    }
    status.innerHTML = T("Get your alerts, funnel Candidates and shared charts as notifications on this {device}.", {device: shown});
    const on = button(row, T("🔔 Turn on for this device"), T("Your browser will ask to allow notifications"), true, async () => {
      on.disabled = true;
      try {
        const ok = await Notification.requestPermission();
        if (ok !== "granted") { note.textContent = T("Notifications weren't allowed, so nothing changed."); on.disabled = false; return; }
        sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(d.key) });
        send({ action: "on", sub: sub.toJSON(), device });
        note.textContent = T("Turning on…");
      } catch (e) {
        note.textContent = T("Couldn't turn them on: {why}", {why: e && e.message ? e.message : e});
        on.disabled = false;
      }
    });
  })();
  return () => root.remove();
}
"""

JS = i18n.js_ready(JS)
_DEVICES = 'T("iPad") T("iPhone") T("Android device") T("Windows computer") T("Mac") T("computer")'
_COMPONENT = None


def component():
    global _COMPONENT
    if _COMPONENT is None:
        import streamlit as st

        _COMPONENT = i18n.with_words(st.components.v2.component("angstrom_push", js=i18n.js_ready(JS), css=CSS), JS + _DEVICES)
    return _COMPONENT


def read_event(result, seen_key: str, state) -> dict | None:
    """The box's latest press, once (None when nothing new)."""
    raw = getattr(result, "push", None)
    if not raw or raw == state.get(seen_key):
        return None
    state[seen_key] = raw
    try:
        event = json.loads(raw)
    except ValueError:
        return None
    return event if event.get("action") in ("on", "off", "test") else None
