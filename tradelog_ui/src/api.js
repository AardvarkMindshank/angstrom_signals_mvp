// Reads from the database with the member's own pass: the database lets each member read only their own rows.
import { settings, token, dropToken } from "./env.js";

async function rest(path) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const access = await token();
    const r = await fetch(`${settings.url}/rest/v1/${path}`, {
      headers: { apikey: settings.key, Authorization: `Bearer ${access}`, Accept: "application/json" },
    });
    if (r.status === 401) { dropToken(); continue; }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }
  throw new Error("signed out");
}

const cache = new Map();

// One ready-made summary: scope "all", whose own / copied / all, period 1y / 3y / 5y / all.
export async function insights(whose, period) {
  const key = `${whose}|${period}`;
  if (!cache.has(key)) {
    cache.set(key, rest(`trade_insights?select=data,computed_at&scope=eq.all&whose=eq.${whose}&period=eq.${period}`)
      .then((rows) => (rows && rows[0]) || null)
      .catch((e) => { cache.delete(key); throw e; }));
  }
  return cache.get(key);
}

const TRADE_COLS = "id,closed_at,opened_at,name,symbol,direction,net_result_usd,result_pct,risk_r,exit_kind,kept_pct,copied,leverage";

// A page of closed trades, newest first, for the Trades tab.
export async function trades(whose, since, offset, limit = 50, hideRewards = false) {
  let q = `trade_round_trips?select=${TRADE_COLS}&order=closed_at.desc&offset=${offset}&limit=${limit}`;
  if (whose === "own") q += "&copied=eq.false";
  if (whose === "copied") q += "&copied=eq.true";
  if (since) q += `&closed_at=gte.${since}`;
  if (hideRewards) q += "&reward=eq.false";          // staking rewards and airdrops aren't trades
  const rows = await rest(q);
  const ids = rows.map((r) => r.id);
  let snaps = [];
  if (ids.length) {
    snaps = await rest(`trade_snapshots?select=round_trip_id,readings&moment=eq.entry&round_trip_id=in.(${ids.join(",")})`).catch(() => []);
  }
  const by = Object.fromEntries(snaps.map((s) => [s.round_trip_id, s.readings || {}]));
  return rows.map((r) => ({ ...r, entry: by[r.id] || null }));
}
