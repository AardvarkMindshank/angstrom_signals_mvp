// What the page takes from the main MarketNavi page it sits in (same origin): settings, words in the member's
// language, colours from UI Colours, its height, and the signed-in pass (the same hand-over the side panels use).

const host = (() => { try { return window.parent && window.parent !== window ? window.parent : null; } catch (e) { return null; } })();
const config = (() => { try { return (host && host.__tl2Config) || {}; } catch (e) { return {}; } })();
const params = new URLSearchParams(window.location.search);

export const settings = {
  url: config.url || params.get("u") || "",
  key: config.key || params.get("k") || "",
  lang: config.lang || params.get("lang") || "en",
  plan: config.plan || params.get("plan") || "pro",
  periods: config.periods || ["1y", "3y", "5y", "all"],
  sample: params.get("sample") === "1",
};

const words = config.words || {};

// T(text, values): the member's language when there is a translation (texts listed in the app's language
// files), English otherwise.
export function T(text, values) {
  let w = words[text] || text;
  if (values) w = w.replace(/\{(\w+)\}/g, (m, k) => (k in values ? values[k] : m));
  return w;
}

// Colours: copy the main page's UI Colours (CSS variables) and follow day/night as it changes.
const VARS = ["--ang-surface", "--ang-text", "--ang-muted", "--ang-soft", "--ang-border", "--ang-page", "--ang-track",
  "--ang-field", "--ang-hover"];
export function followColours(onNight) {
  const apply = () => {
    try {
      const root = host.document.documentElement;
      const cs = host.getComputedStyle(root);
      VARS.forEach((v) => {
        const val = cs.getPropertyValue(v).trim();
        if (val) document.documentElement.style.setProperty(v, val);
      });
      const night = root.classList.contains("angstrom-night");
      document.documentElement.classList.toggle("night", night);
      onNight && onNight(night);
    } catch (e) { /* not inside the app: the page's own defaults */ }
  };
  apply();
  try {
    new MutationObserver(apply).observe(host.document.documentElement, { attributes: true, attributeFilter: ["class", "style"] });
  } catch (e) { /* standalone */ }
}

// Height: the frame grows and shrinks with the page, so the main page scrolls as one.
export function followHeight() {
  const set = () => {
    try {
      // The page's own content height (not the document's, which never drops below the frame's current height).
      const root = document.getElementById("root");
      if (window.frameElement && root) window.frameElement.style.height = Math.ceil(root.getBoundingClientRect().height) + 8 + "px";
    } catch (e) { /* standalone */ }
  };
  new ResizeObserver(set).observe(document.getElementById("root") || document.body);
  set();
}

// The signed-in pass: ask the main page (BroadcastChannel "angstrom-handoff"), keep the renewed one it sends later.
let current = "";
const waiting = [];
export function token() {
  if (current) return Promise.resolve(current);
  return new Promise((resolve) => waiting.push(resolve));
}
export function dropToken() { current = ""; ask(); }
const channel = ("BroadcastChannel" in window) ? new BroadcastChannel("angstrom-handoff") : null;
const myId = Math.random().toString(36).slice(2);
if (channel) {
  channel.onmessage = (event) => {
    const msg = event.data || {};
    if (msg.type !== "token" || !msg.access) return;
    if (msg.to !== myId && msg.to !== "*") return;
    current = msg.access;
    while (waiting.length) waiting.shift()(current);
  };
}
let tries = 0;
function ask() {
  if (current || !channel || tries > 60) return;
  tries += 1;
  channel.postMessage({ type: "ask", id: myId });
  window.setTimeout(ask, 700);
}
ask();
export function signedOut() { return !channel || (tries > 60 && !current); }
