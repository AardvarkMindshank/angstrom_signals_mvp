// T(text, values): the member's language (their account setting, else the browser's), from words/<code>.json, built
// from the same translations as the classic app. English when there is no translation.
const CODES = ["en", "zh-CN", "fr", "de", "id", "ja", "ko", "pt-BR", "es", "th", "tr", "vi"];
let words = {};
export let lang = "en";

export function pickLanguage(saved) {
  const want = [saved, ...(navigator.languages || [navigator.language])].filter(Boolean);
  for (const w of want) {
    const exact = CODES.find((c) => c.toLowerCase() === String(w).toLowerCase());
    if (exact) return exact;
    const base = CODES.find((c) => c.split("-")[0] === String(w).split("-")[0].toLowerCase());
    if (base) return base;
  }
  return "en";
}

export async function loadWords(code) {
  lang = code;
  document.documentElement.lang = code;
  if (code === "en") { words = {}; return; }
  try {
    const r = await fetch(`${import.meta.env.BASE_URL}words/${code}.json`);
    words = r.ok ? await r.json() : {};
  } catch (e) { words = {}; }
}

// The new app draws no colour emoji (one line-icon set, components/Icon.jsx): T() takes out any emoji the shared
// texts carry ("🔻 Your funnels" → "Your funnels", "in ⚙️ Settings" → "in Settings"); the page adds its icon.
export const EMOJI_RE = /(?![\u00A9\u00AE\u2122\u2190-\u21FF])(?:\p{Extended_Pictographic}|\p{Regional_Indicator})(?:\uFE0F|\u200D\p{Extended_Pictographic}|[\u{1F3FB}-\u{1F3FF}])*[ \t]*/gu;
export const noEmoji = (s) => String(s).replace(EMOJI_RE, "").replace(/\([ \t]+/g, "(").replace(/[ \t]{2,}/g, " ").replace(/[ \t]+([.,:;)])/g, "$1").replace(/^[ \t]+|[ \t]+$/gm, "");

export function T(text, values) {
  let w = words[text] || text;
  if (values) w = w.replace(/\{(\w+)\}/g, (m, k) => (k in values ? values[k] : m));
  return noEmoji(w);
}

// The whole word list, for the classic components the new app hosts (they read their words from data.tr).
export const allWords = () => words;
