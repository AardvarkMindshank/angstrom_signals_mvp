import { lang } from "./i18n.js";

// Formatters follow the member's language (Thai with the Gregorian calendar, as elsewhere in MarketNavi).
const loc = () => ({ "zh-CN": "zh-CN", "pt-BR": "pt-BR", th: "th-TH-u-ca-gregory" }[lang] || lang || "en");
const memo = {};
const fmt = (kind, opts, Ctor = Intl.NumberFormat) => {
  const k = `${loc()}|${kind}`;
  if (!memo[k]) memo[k] = new Ctor(loc(), opts);
  return memo[k];
};
const nf0 = () => fmt("n0", { maximumFractionDigits: 0 });
const nf1 = () => fmt("n1", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const nf2 = () => fmt("n2", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const num = (v) => (v == null ? "—" : nf0().format(v));
// Small amounts keep their cents, so an average of a few cents isn't shown as "$0".
export function money(v, signed = true) {
  if (v == null) return "—";
  const s = "$" + (Math.abs(v) < 10 && v !== 0 ? nf2().format(Math.abs(v)) : nf0().format(Math.abs(Math.round(v))));
  if (!signed) return (v < 0 ? "−" : "") + s;
  return (v > 0 ? "+" : v < 0 ? "−" : "") + s;
}
export function pct(v, digits = 0, signed = true) {
  if (v == null) return "—";
  const body = (digits ? nf1() : nf0()).format(Math.abs(v)) + "%";
  if (!signed) return (v < 0 ? "−" : "") + body;
  return (v > 0 ? "+" : v < 0 ? "−" : "") + body;
}
export const price = (v) => (v == null ? "—" : fmt("p", { maximumSignificantDigits: 5 }).format(v));
export const tone = (v) => (v == null ? "" : v >= 0 ? "good" : "bad");
const parse = (d) => new Date(String(d).slice(0, 10) + "T12:00:00Z");
const dt = (kind, opts) => fmt(kind, opts, Intl.DateTimeFormat);
export const monthYear = (d) => (d ? dt("my", { month: "short", year: "numeric" }).format(parse(d)) : "—");
export const dayMonthYear = (d) => (d ? dt("dmy", { day: "numeric", month: "short", year: "numeric" }).format(parse(d)) : "—");
export const dayMonth = (d) => (d ? dt("dm", { day: "numeric", month: "short" }).format(parse(d)) : "—");
export const stamp = (iso) => (iso ? dt("st", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(iso)) : "—");
export const when = (iso) => (iso ? dt("wh", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(iso)) : "—");
export const monthNames = () => Array.from({ length: 12 }, (_, i) => dt("mn", { month: "short" }).format(new Date(Date.UTC(2026, i, 15))));
