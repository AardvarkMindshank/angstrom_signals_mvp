import { settings } from "./env.js";

const LOCALE = { "zh-CN": "zh-CN", "pt-BR": "pt-BR", th: "th-TH-u-ca-gregory" }[settings.lang] || settings.lang || "en";
const nf0 = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 1, minimumFractionDigits: 1 });

export const stamp = (iso) => new Date(iso).toLocaleString(LOCALE, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
export const num = (v) => (v == null ? "—" : nf0.format(v));
const nf2 = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// Small amounts keep their cents, so an average of a few cents isn't shown as "$0" (26 Nov 2026).
export function money(v, signed = true) {
  if (v == null) return "—";
  const s = "$" + (Math.abs(v) < 10 && v !== 0 ? nf2.format(Math.abs(v)) : nf0.format(Math.abs(Math.round(v))));
  if (!signed) return (v < 0 ? "−" : "") + s;
  return (v > 0 ? "+" : v < 0 ? "−" : "") + s;
}
export function pct(v, digits = 0, signed = true) {
  if (v == null) return "—";
  const body = (digits ? nf1 : nf0).format(Math.abs(v)) + "%";
  if (!signed) return (v < 0 ? "−" : "") + body;
  return (v > 0 ? "+" : v < 0 ? "−" : "") + body;
}
export const tone = (v) => (v == null ? "" : v >= 0 ? "good" : "bad");
const mf = new Intl.DateTimeFormat(LOCALE, { month: "short", year: "numeric" });
const df = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "short", year: "numeric" });
const sf = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "short" });
const parse = (d) => new Date(String(d).slice(0, 10) + "T12:00:00Z");
export const monthYear = (d) => (d ? mf.format(parse(d)) : "—");
export const dayMonthYear = (d) => (d ? df.format(parse(d)) : "—");
export const dayMonth = (d) => (d ? sf.format(parse(d)) : "—");
export const monthNames = Array.from({ length: 12 }, (_, i) => new Intl.DateTimeFormat(LOCALE, { month: "short" }).format(new Date(Date.UTC(2026, i, 15))));
