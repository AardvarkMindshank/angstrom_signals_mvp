import React from "react";
import { T, lang } from "../lib/i18n.js";
import Icon from "./Icon.jsx";

// ✦ A member's social score, as a small pill beside their name (as the classic app). Points come from posting (5 a
// comment, 1 a reply) and inviting friends who join (100 each). Big numbers are shortened in the member's language
// (1.2k, 12k, 1.2M; 1.2万 in Japanese) so the pill stays small; hover or a long press shows the exact number.
const exact = (n) => { try { return new Intl.NumberFormat(lang).format(n); } catch (e) { return String(n); } };
export const shortScore = (n) => {
  if (n < 1000) return String(n);
  try { return new Intl.NumberFormat(lang, { notation: "compact", maximumFractionDigits: 1 }).format(n); } catch (e) { return n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : `${Math.floor(n / 100) / 10}k`; }
};

export default function Score({ n }) {
  const v = Math.max(0, Math.floor(Number(n) || 0));
  const tip = T("Social score {n}", { n: exact(v) });
  return <span className="sscore" title={tip} aria-label={tip}><Icon n="sparkle" size={11} tone={false} />{shortScore(v)}</span>;
}
