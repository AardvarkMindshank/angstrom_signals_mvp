// Assets: what the search finds and what an asset page reads. Everything comes from the same shared tables the classic
// app and the background worker fill (asset_market, the crypto and equity universes, readings_daily, tides_daily),
// so every number matches the rest of MarketNavi. Member rows (alerts, trades, watchlists) go through the row rules.
import { supabase } from "./supabase.js";

const must = ({ data, error }) => { if (error) throw error; return data; };
const once = (fn) => { let p = null; const get = () => (p = p || fn().catch((e) => { p = null; throw e; })); get.reset = () => { p = null; }; return get; };

export const keyFor = (kind, id) => `${kind === "crypto" ? "Crypto" : "Stock"}|${id}`;
export const parseKey = (key) => {
  const [k, id] = String(key || "").split("|");
  return k && id ? { kind: k === "Crypto" ? "crypto" : "equity", id } : null;
};

// ---- the search's list of assets ---------------------------------------------------------------------------------

export const universe = once(async () => {
  const [c, e] = await Promise.all([
    supabase.from("crypto_universe").select("coin_id,symbol,name,rank,pair").eq("included", true).order("rank").limit(1000),
    supabase.from("equity_universe").select("ticker,name,sector,rank").eq("included", true).order("rank").limit(1000),
  ]);
  const crypto = (c.data || []).map((r) => ({ key: keyFor("crypto", r.coin_id), kind: "crypto", id: r.coin_id, symbol: r.symbol,
    name: r.name, rank: r.rank, pair: r.pair }));
  const equity = (e.data || []).map((r) => ({ key: keyFor("equity", r.ticker), kind: "equity", id: r.ticker, symbol: r.ticker,
    name: r.name, rank: r.rank, sector: r.sector }));
  return [...crypto, ...equity];
});

export const watchlists = once(async () => {
  const { data: u } = await supabase.auth.getUser();
  if (!u || !u.user) return { crypto: {}, equity: {} };
  const rows = must(await supabase.from("user_preferences").select("crypto_watchlist,stock_watchlist").eq("user_id", u.user.id).limit(1)) || [];
  return { crypto: (rows[0] && rows[0].crypto_watchlist) || {}, equity: (rows[0] && rows[0].stock_watchlist) || {} };
});

const norm = (s) => String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

// Best matches first: exact symbol, then symbol or name starting with the words, then containing them; watched and
// larger assets break ties.
export function match(list, typed, watched, limit = 8) {
  const q = norm(typed).trim();
  if (!q) return [];
  const scored = [];
  for (const a of list) {
    const s = norm(a.symbol), n = norm(a.name);
    let score = 0;
    if (s === q) score = 100; else if (n === q) score = 95;
    else if (s.startsWith(q)) score = 80; else if (n.startsWith(q)) score = 70;
    else if (n.split(/[\s.-]+/).some((w) => w.startsWith(q))) score = 60;
    else if (q.length >= 3 && n.includes(q)) score = 40;
    if (!score) continue;
    if (watched.has(a.key)) score += 15;
    score -= Math.min(10, (a.rank || 999) / 100);
    scored.push([score, a]);
  }
  return scored.sort((x, y) => y[0] - x[0]).slice(0, limit).map((x) => x[1]);
}

// ---- one asset ---------------------------------------------------------------------------------------------------

const rows = new Map();
const ROW = "asset_key,kind,asset_id,closes,prices,prices_updated_at,readings,sentiment_score,sentiment_report,"
  + "sentiment_updated_at,logo_url,market_cap,market_rank,next_earnings,liq_levels,liq_updated_at";

export function asset(key) {
  if (!rows.has(key)) {
    rows.set(key, supabase.from("asset_market").select(ROW).eq("asset_key", key).limit(1)
      .then((r) => (must(r) || [])[0] || null).catch((e) => { rows.delete(key); throw e; }));
  }
  return rows.get(key);
}

// Light rows for the search's top hit and the watchlist list: price, change, logo, readings.
export async function brief(keys) {
  if (!keys.length) return {};
  const got = must(await supabase.from("asset_market").select("asset_key,closes,logo_url,readings").in("asset_key", keys)) || [];
  const out = {};
  got.forEach((r) => {
    const f = (r.readings && r.readings.fields) || {};
    const c = (r.closes || []).filter((x) => x != null);
    out[r.asset_key] = { logo: r.logo_url, price: f.latest_price ?? c[c.length - 1], change: f.change_1d,
      trend: f.trend, stretch: f.stretch, flow: f.flow };
  });
  return out;
}

export async function readingsHistory(key, days = 120) {
  const since = new Date(Date.now() - days * 864e5).toISOString().slice(0, 10);
  return must(await supabase.from("readings_daily").select("day,trend,stretch,flow,regime").eq("asset_key", key)
    .gte("day", since).order("day")) || [];
}

export const tide = once(async () => (((must(await supabase.from("tides_daily").select("day,body").order("day", { ascending: false }).limit(1)) || [])[0]) || {}).body || null);

export async function maxPain(key) {
  try {
    return ((must(await supabase.from("options_pain").select("recorded_at,expiry,spot,max_pain,call_oi,put_oi,strikes,source")
      .eq("asset_key", key).order("recorded_at", { ascending: false }).limit(1)) || [])[0]) || null;
  } catch (e) { return null; }
}

export async function earningsHistory(ticker) {
  try {
    return must(await supabase.from("earnings_history").select("report_date").eq("ticker", ticker)
      .order("report_date", { ascending: false }).limit(8)) || [];
  } catch (e) { return []; }
}

// ---- the member's own rows for one asset ---------------------------------------------------------------------------

export async function alerts(id) {
  try {
    return must(await supabase.from("user_notifications").select("id,alert_type,message,created_at,is_read")
      .eq("asset_symbol", id).order("created_at", { ascending: false }).limit(30)) || [];
  } catch (e) { return []; }
}

export async function trades(key) {
  try {
    return must(await supabase.from("trade_round_trips").select("id,opened_at,closed_at,direction,net_result_usd,result_pct,copied,reward,connection_id,invested_usd,leverage")
      .eq("asset_key", key).order("closed_at", { ascending: false }).limit(200)) || [];
  } catch (e) { return []; }
}

export async function openPositions(key) {
  try {
    return must(await supabase.from("trade_open_positions").select("*").eq("asset_key", key)) || [];
  } catch (e) { return []; }
}

export async function funnelStatus(id) {
  try {
    const got = must(await supabase.from("funnel_coins").select("funnel_id,status,depth,updated_at,state").eq("coin_id", id)) || [];
    if (!got.length) return [];
    const names = must(await supabase.from("funnels").select("id,name,stages,direction").in("id", got.map((g) => g.funnel_id))) || [];
    const by = Object.fromEntries(names.map((n) => [n.id, n]));
    return got.filter((g) => by[g.funnel_id]).map((g) => {
      const st = Array.isArray(by[g.funnel_id].stages) ? by[g.funnel_id].stages : [];
      return { ...g, name: by[g.funnel_id].name, direction: by[g.funnel_id].direction, stages: st.length,
        steps: st.map((x, i) => ({ label: x.label || "", timeframe: x.timeframe || "", ...((((g.state || {}).stages) || [])[i] || {}) })) };
    });
  } catch (e) { return []; }
}

// ---- intraday candles (crypto) ----------------------------------------------------------------------------------
// Binance's public market-data address, read straight from the browser: no key, nothing about the member is sent.
const BINANCE = "https://data-api.binance.vision/api/v3/klines";
export async function candles(pair, interval, limit = 500) {
  const r = await fetch(`${BINANCE}?symbol=${encodeURIComponent(pair)}&interval=${interval}&limit=${limit}`);
  if (!r.ok) throw new Error("candles " + r.status);
  return (await r.json()).map((k) => ({ time: Math.floor(k[0] / 1000), open: +k[1], high: +k[2], low: +k[3], close: +k[4], volume: +k[5] }));
}

// ---- the macro calendar (written at build time from macro_calendar.py) ------------------------------------------
export const calendar = once(async () => {
  try { const r = await fetch(import.meta.env.BASE_URL + "data/calendar.json"); return r.ok ? await r.json() : []; } catch (e) { return []; }
});

// ---- how a watchlist entry is named -------------------------------------------------------------------------------
// Every coin is stored as "Name (TICKER)", e.g. "Solana (SOL)", "Aave (AAVE)"; just "XRP" when the name is exactly the
// ticker. The same rule as crypto_universe.coin_label in Python (the classic app and the worker use that one).
export function coinLabel(name, symbol) {
  const n = String(name || "").replace(/\s*\([^()]*\)\s*$/, "").trim();
  const s = String(symbol || "").trim().toUpperCase();
  if (!s) return n;
  if (!n || n === s) return s;
  return `${n} (${s})`;
}

// The name to store for an asset being added: from the search list (name and ticker), else what the page had.
export async function watchName(kind, id, fallback) {
  if (kind !== "crypto") return String(fallback || id).replace(/\s*\([^()]*\)\s*$/, "").trim() || id;
  try {
    const row = (await universe()).find((a) => a.kind === "crypto" && a.id === id);
    if (row) return coinLabel(row.name, row.symbol);
  } catch (e) { /* the list isn't to hand: the page's own name */ }
  return String(fallback || id);
}

// ---- the watchlist button -----------------------------------------------------------------------------------------
// The classic app keeps each watchlist as {id: name} on the account's preferences row; this changes one entry.
export async function setWatched(kind, id, name, on) {
  const { data: u } = await supabase.auth.getUser();
  const col = kind === "crypto" ? "crypto_watchlist" : "stock_watchlist";
  const rows = must(await supabase.from("user_preferences").select(col).eq("user_id", u.user.id).limit(1)) || [];
  const list = { ...((rows[0] && rows[0][col]) || {}) };
  if (on) list[id] = await watchName(kind, id, name); else delete list[id];
  must(await supabase.from("user_preferences").update({ [col]: list }).eq("user_id", u.user.id));
  watchlists.reset();
  return list;
}

// ---- community: takes on the news mood, comments and replies (the same tables and functions as the classic app) --
const one = (r) => must(r);
export async function crowd(key) {
  try { const rows = one(await supabase.rpc("sentiment_crowd", { asset_keys: [key] })) || []; const r = rows[0] || {};
    return { up: +r.thumbs_up || 0, down: +r.thumbs_down || 0, mine: r.my_vote == null ? null : +r.my_vote };
  } catch (e) { return { up: 0, down: 0, mine: null }; }
}
export async function vote(key, at, v) {
  const { data: u } = await supabase.auth.getUser();
  if (v !== 1 && v !== -1) { one(await supabase.from("sentiment_votes").delete().eq("user_id", u.user.id).eq("asset_key", key)); return; }
  one(await supabase.from("sentiment_votes").upsert({ user_id: u.user.id, asset_key: key, sentiment_at: at, vote: v, alt_score: null }, { onConflict: "user_id,asset_key" }));
}
export async function comments(key) {
  try { return one(await supabase.rpc("sentiment_comments", { asset_keys: [key] })) || []; } catch (e) { return []; }
}
export async function replies() {
  try { return one(await supabase.rpc("sentiment_replies")) || []; } catch (e) { return []; }
}
export const COMMENT_LIMIT = 160;
const clean = (s) => String(s || "").split(/\s+/).filter(Boolean).join(" ").slice(0, COMMENT_LIMIT);
export async function postComment(key, at, body, score, summary) {
  const { data: u } = await supabase.auth.getUser();
  one(await supabase.from("sentiment_comments").upsert({ user_id: u.user.id, asset_key: key, sentiment_at: at, body: clean(body),
    created_at: new Date().toISOString(), responded_score: score, responded_summary: String(summary || "").slice(0, 220) || null }, { onConflict: "user_id,asset_key" }));
}
export async function deleteNote(id, kind) { one(await supabase.rpc("delete_own_signal_message", { target_id: id, target_kind: kind })); }
export async function voteNote(id, kind, v) {
  const { data: u } = await supabase.auth.getUser();
  const table = kind === "reply" ? "sentiment_reply_votes" : "sentiment_comment_votes", col = kind === "reply" ? "reply_id" : "comment_id";
  if (v !== 1 && v !== -1) { one(await supabase.from(table).delete().eq("user_id", u.user.id).eq(col, id)); return; }
  one(await supabase.from(table).upsert({ user_id: u.user.id, [col]: id, vote: v }, { onConflict: `user_id,${col}` }));
}
export async function postReply(commentId, body) {
  const { data: u } = await supabase.auth.getUser();
  one(await supabase.from("sentiment_replies").insert({ user_id: u.user.id, comment_id: commentId, body: clean(body) }));
}

// ---- the member's own chart drawings (drawn in the classic app's chart) -----------------------------------------
export const drawingKey = (kind, id) => (kind === "crypto" ? `crypto:${String(id).toLowerCase()}` : `equity:${String(id).toUpperCase()}`);
export async function drawings(kind, id) {
  try {
    const { data: u } = await supabase.auth.getUser();
    const rows = must(await supabase.from("chart_drawings").select("items").eq("user_id", u.user.id).eq("asset_key", drawingKey(kind, id)).limit(1)) || [];
    return (rows[0] && rows[0].items) || [];
  } catch (e) { return []; }
}
