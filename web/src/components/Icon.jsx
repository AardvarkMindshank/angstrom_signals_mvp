import React from "react";
import PATHS from "../generated/icons.js";
import { EMOJI_RE, noEmoji } from "../lib/i18n.js";

// The app's one icon set: Lucide line icons (web/scripts/icons.py copies the ones used), drawn in the text colour at
// one stroke weight. No colour emoji in the interface: colour only where it means something (good, bad, selected).
// <Icon n="trash" /> · <Icon n="bell" size={16} title="Alerts" />
export default function Icon({ n, size = 18, title, className, style }) {
  const d = PATHS[n];
  if (!d) return null;
  return (
    <svg className={"ic" + (className ? " " + className : "")} width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" style={style}
      role={title ? "img" : undefined} aria-hidden={title ? undefined : true}
      dangerouslySetInnerHTML={{ __html: (title ? `<title>${title.replace(/</g, "&lt;")}</title>` : "") + d }} />
  );
}

// The emoji the data service and the shared readings still send (Tides currents, families, signal icons), as icons.
export const EMOJI = {
  "🌊": "waves-horizontal", "📈": "trending-up", "📉": "trending-down", "⚙️": "settings", "⚙": "settings", "🧭": "compass",
  "👍": "thumbs-up", "👎": "thumbs-down", "🔻": "funnel", "🎯": "target", "🔔": "bell", "👥": "users",
  "📓": "notebook", "⭐": "star", "🌍": "globe", "🌎": "globe", "🌏": "globe", "🔊": "audio-lines", "🌐": "globe",
  "💬": "message-circle", "🪙": "coins", "🧩": "puzzle", "🎬": "clapperboard", "✏️": "pencil", "🚫": "ban",
  "✅": "circle-check", "📐": "shapes", "👁": "eye", "👁️": "eye", "⚠️": "triangle-exclamation-point", "⚠": "triangle-exclamation-point",
  "⏳": "hourglass", "🔬": "microscope", "🗑️": "trash", "🗑": "trash", "🔒": "lock", "✨": "sparkles", "📸": "camera",
  "📰": "newspaper", "🏛️": "landmark", "🏛": "landmark", "⏸️": "pause", "📤": "share", "🛰️": "satellite",
  "🎙️": "mic", "🔄": "refresh-cw", "➕": "plus", "💾": "save", "📜": "scroll-text", "📅": "calendar", "🚩": "flag",
  "⚓": "anchor", "📊": "chart-column", "📏": "ruler", "🕳️": "circle-dashed", "📍": "map-pin", "🔆": "sun",
  "🌤️": "cloud-sun", "☀️": "sun", "🌙": "moon", "🌓": "sun-moon", "⚡": "zap", "📬": "mail", "📋": "clipboard-list",
  "🔍": "search", "🔎": "search", "🛡️": "shield", "🧹": "brush-cleaning", "🧱": "blocks", "🌳": "workflow",
  "🗂️": "folder", "📁": "folder", "🔭": "telescope", "⛔": "octagon-x", "💵": "dollar-sign", "💲": "dollar-sign",
  "🏦": "landmark", "🥇": "medal", "🛢️": "fuel", "🏭": "factory", "🧾": "receipt", "💳": "credit-card",
  "🔥": "flame", "💧": "droplet", "🌪️": "tornado", "⛈️": "cloud-lightning", "🌧️": "cloud-rain", "☁️": "cloud",
  "🌫️": "cloud-fog", "💨": "wind", "🌬️": "wind", "⛵": "sailboat", "🚤": "ship", "🏝️": "tree-palm", "🎙": "mic",
  "₿": "bitcoin", "🤖": "bot", "🧠": "brain", "💡": "lightbulb", "🔗": "link", "📌": "pin", "🕰️": "clock-arrow-up",
  "🔺": "triangle", "♦️": "diamond", "🔶": "diamond", "🩸": "droplet", "⏱": "timer", "⏱️": "timer", "🙈": "eye-off",
  "✋": "hand", "🖍️": "highlighter", "🧽": "eraser", "🔤": "type", "📝": "notebook-pen", "🗓️": "calendar-days",
  "💼": "briefcase", "🏠": "house", "🧪": "flask-conical", "📦": "package", "🎉": "party-popper", "❓": "circle-question-mark", "⏭": "skip-forward", "⏭️": "skip-forward",
  "✔": "check", "➖": "minus", "↕️": "arrow-up-down", "🗺️": "map", "🌦️": "cloud-sun-rain", "🌦": "cloud-sun-rain", "🪨": "mountain", "🧭️": "compass", "🎣": "fish", "📡": "radar", "🌡️": "thermometer", "🌡": "thermometer", "🎚️": "sliders-horizontal", "🎛️": "sliders-vertical", "⛵": "sailboat", "😨": "gauge", "😱": "gauge", "🛍️": "shopping-bag", "🛍": "shopping-bag", "🐟": "fish",
  "🔷": "diamond", "〰️": "activity", "〰": "activity", "🏗️": "construction", "🚢": "ship", "🧊": "snowflake", "✔️": "check", "✖": "x", "✖️": "x", "➚": "arrow-up-right", "📶": "signal", "💹": "chart-line",
};

// A word that may start with an emoji (from the data service or the shared readings): its icon, then the rest.
export function Lead({ text, size = 16 }) {
  const s = String(text == null ? "" : text);
  const m = s.match(new RegExp("^(?:" + EMOJI_RE.source + ")", "u"));
  if (!m) return <>{s}</>;
  const k = m[0].trim(), n = EMOJI[k] || EMOJI[k.replace(/\uFE0F/g, "")] || EMOJI[k.replace(/\uFE0F/g, "") + "\uFE0F"];
  return <>{n ? <><Icon n={n} size={size} /> </> : null}{s.slice(m[0].length)}</>;
}
// One emoji from the data (a Tides current's icon, a family's icon) as its icon; anything unknown is left out.
export function Emo({ e, size = 16 }) {
  const k = String(e || "").replace(/️/g, "");
  const n = EMOJI[e] || EMOJI[k] || EMOJI[k + "️"];
  return n ? <Icon n={n} size={size} /> : null;
}
// Text without a leading emoji (for titles and hover notes that are plain text).
export const plain = (text) => noEmoji(text == null ? "" : text);

// The classic editors the app hosts (ClassicComponent) and the Pro chart's tools draw their own DOM, with emoji in it.
// watchIcons(element) swaps each emoji there for its icon as the DOM is drawn and redrawn (unknown ones are dropped;
// inside a pull-down's choices, where a picture can't go, and in hover notes they are just taken out).
const ONE = new RegExp(EMOJI_RE.source, "u");
function svgFor(e) {
  const k = e.trim();
  const n = EMOJI[k] || EMOJI[k.replace(/️/g, "")] || EMOJI[k.replace(/️/g, "") + "️"];
  if (!n || !PATHS[n]) return null;
  const span = document.createElement("span");
  span.className = "icw";
  span.innerHTML = `<svg class="ic" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATHS[n]}</svg>${/\s$/.test(e) ? " " : ""}`;
  return span;
}
export function iconify(root) {
  if (!root) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const hits = [];
  while (walker.nextNode()) if (ONE.test(walker.currentNode.nodeValue)) hits.push(walker.currentNode);
  const walk2 = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walk2.nextNode()) {
    const v = walk2.currentNode.nodeValue;
    if (/[\u2190-\u21FF\u23E9-\u23EF\u23F8-\u23FA\u25B6\u25C0]\uFE0F/.test(v)) walk2.currentNode.nodeValue = v.replace(/([\u2190-\u21FF\u23E9-\u23EF\u23F8-\u23FA\u25B6\u25C0])\uFE0F/g, "$1\uFE0E");
  }
  for (const t of hits) {
    const parent = t.parentNode;
    if (!parent) continue;
    if (parent.closest && parent.closest("option, textarea, script, style, title")) { t.nodeValue = noEmoji(t.nodeValue); continue; }
    const frag = document.createDocumentFragment();
    const text = t.nodeValue;
    let last = 0;
    for (const m of text.matchAll(new RegExp(EMOJI_RE.source, "gu"))) {
      if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      const icon = svgFor(m[0]);
      if (icon) frag.appendChild(icon);
      last = m.index + m[0].length;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    parent.replaceChild(frag, t);
  }
  root.querySelectorAll("[title], [aria-label], [placeholder]").forEach((el) => {
    for (const a of ["title", "aria-label", "placeholder"]) {
      const v = el.getAttribute(a);
      if (v && ONE.test(v)) el.setAttribute(a, noEmoji(v));
    }
  });
}
export function watchIcons(root) {
  if (!root) return () => {};
  iconify(root);
  let queued = false;
  const run = () => { queued = false; obs.disconnect(); iconify(root); obs.observe(root, OPTS); };
  const obs = new MutationObserver(() => { if (!queued) { queued = true; requestAnimationFrame(run); } });
  const OPTS = { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["title"] };
  obs.observe(root, OPTS);
  return () => obs.disconnect();
}

// Text from the data that may hold emoji anywhere ("🔻✅", "Trend 📈 (provided)"): each known one as its icon.
export function Glyphs({ text, size = 15 }) {
  const s = String(text == null ? "" : text).replace(/([\u2190-\u21FF\u23E9-\u23EF\u23F8-\u23FA\u25B6\u25C0])\uFE0F?/g, "$1\uFE0E");
  const out = [];
  let last = 0, i = 0;
  for (const m of s.matchAll(new RegExp(EMOJI_RE.source, "gu"))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    const k = m[0].trim(), n = EMOJI[k] || EMOJI[k.replace(/️/g, "")] || EMOJI[k.replace(/️/g, "") + "️"];
    if (n) out.push(<Icon key={i++} n={n} size={size} />, /\s$/.test(m[0]) ? " " : "");
    last = m.index + m[0].length;
  }
  if (last < s.length) out.push(s.slice(last));
  return <>{out}</>;
}
// The direction arrows the readings send (▲ ▼ ▶) as icons.
const ARROWS = { "▲": "arrow-up-right", "▼": "arrow-down-right", "▶": "arrow-right", "▶️": "arrow-right", "↗": "arrow-up-right", "↘": "arrow-down-right", "↔": "arrow-left-right" };
export const Arrow = ({ a, size = 15 }) => (ARROWS[a] ? <Icon n={ARROWS[a]} size={size} /> : <>{a}</>);
