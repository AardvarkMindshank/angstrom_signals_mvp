// Words for values that arrive as data (reading labels, Tide states), each a literal T() so it is translated.
import { T } from "../../lib/i18n.js";

export const READING_LABEL = () => ({
  "Strong uptrend": T("Strong uptrend"), Uptrend: T("Uptrend"), "No clear trend": T("No clear trend"), Downtrend: T("Downtrend"),
  "Strong downtrend": T("Strong downtrend"), "Very stretched up": T("Very stretched up"), "Stretched up": T("Stretched up"),
  "Not stretched": T("Not stretched"), "Stretched down": T("Stretched down"), "Very stretched down": T("Very stretched down"),
  "Volume strongly backing rises": T("Volume strongly backing rises"), "Volume backing rises": T("Volume backing rises"),
  "Volume neutral": T("Volume neutral"), "Volume backing falls": T("Volume backing falls"),
  "Volume strongly backing falls": T("Volume strongly backing falls"),
  "Strong buying volume": T("Strong buying volume"), "Buying volume": T("Buying volume"), "Selling volume": T("Selling volume"),
  "Strong selling volume": T("Strong selling volume"), "Not enough data": T("Not enough data"),
});
export const label = (l) => (l ? READING_LABEL()[l] || l : "");

export const REGIME = () => ({ trending_up: T("Trending up"), trending_down: T("Trending down"), trending_mixed: T("Trending, mixed"),
  ranging: T("Ranging"), transitional: T("Transitional"), trending: T("Trending") });

export const HORIZON = () => ({ "weeks to months": T("weeks to months"), "1 to 4 weeks": T("1 to 4 weeks"), "days to weeks": T("days to weeks") });

export const TIDE = () => ({ in: T("Tide coming in"), slack: T("Slack tide"), out: T("Tide going out") });
export const TIDE_PLAIN = () => ({ in: T("risk-supportive"), slack: T("mixed"), out: T("risk-defensive") });
export const SEA = () => ({ calm: T("calm"), moderate: T("moderate"), rough: T("rough"), storm: T("storm") });
export const SEA_PLAIN = () => ({ calm: T("low volatility"), moderate: T("normal volatility"), rough: T("high volatility"), storm: T("extreme volatility") });
export const WIND = () => ({ headwind: T("Headwind"), tailwind: T("Tailwind"), neither: T("Neither") });

export const CURRENT = () => ({
  short_rates: T("Short rates"), long_rates: T("Long rates"), curve: T("Yield curve"), dollar: T("US dollar"), inflation: T("Inflation"),
  gold: T("Gold"), fear: T("Fear (VIX)"), copper_gold: T("Copper vs gold"), oil: T("Oil"), credit: T("Credit"),
  equity_rotation: T("Equities vs bonds"), crypto_rotation: T("Crypto rotation"),
});
export const EFFECT = () => ({ helping: T("helping"), hurting: T("hurting"), neutral: T("neutral") });

export const EVENT = () => ({ fomc: T("Fed rate decision"), cpi: T("CPI inflation"), jobs: T("Jobs report"), ppi: T("Producer prices"), deadline: T("Deadline") });

export const ALERT = () => ({
  TREND_UP: T("Trend"), TREND_DOWN: T("Trend"), STRETCH_UP: T("Stretch"), STRETCH_DOWN: T("Stretch"), FLOW_UP: T("Flow"), FLOW_DOWN: T("Flow"),
});

export const COVERAGE = (score) => (score == null ? "" : score >= 35 ? T("bullish coverage") : score >= 10 ? T("mildly bullish coverage")
  : score > -10 ? T("mixed coverage") : score > -35 ? T("mildly bearish coverage") : T("bearish coverage"));

// Alert texts are stored in English by the background job; the usual "Trend gets strongly bearish: −52 (Strong
// downtrend), was Downtrend." shape is put back together in the member's language. Anything else shows as stored.
const CROSS = () => ({
  "gets strongly bullish": T("gets strongly bullish"), "fades back from strongly bullish": T("fades back from strongly bullish"),
  "turns bullish (leaves neutral)": T("turns bullish (leaves neutral)"), "falls back into neutral": T("falls back into neutral"),
  "rises back into neutral": T("rises back into neutral"), "turns bearish (leaves neutral)": T("turns bearish (leaves neutral)"),
  "fades back from strongly bearish": T("fades back from strongly bearish"), "gets strongly bearish": T("gets strongly bearish"),
  "flips from bearish to bullish": T("flips from bearish to bullish"), "flips from bullish to bearish": T("flips from bullish to bearish"),
});
const NAMES = () => ({ Trend: T("Trend"), Stretch: T("Stretch"), Flow: T("Flow") });
export function alertText(msg) {
  const m = /^(Trend|Stretch|Flow) (.+?): ([+\-−]?\d+) \((.+?)\), was (.+?)\.(\s+Readings describe conditions, not forecasts\.)?$/.exec(String(msg || "").trim());
  if (!m || !CROSS()[m[2]]) return msg;
  const words = READING_LABEL();
  const find = (w) => words[w] || words[Object.keys(words).find((k) => k.toLowerCase() === w.toLowerCase())] || w;
  return T("{name} {what}: {value} ({now}), was {before}.", { name: NAMES()[m[1]], what: CROSS()[m[2]], value: m[3], now: find(m[4]), before: find(m[5]).toLowerCase() })
    + (m[6] ? " " + T("Readings describe conditions, not forecasts.") : "");
}
