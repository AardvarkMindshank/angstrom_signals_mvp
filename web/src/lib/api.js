// Everything the new app reads and writes, straight to the database with the member's own sign-in. The database's
// row rules decide what each member can see and change, exactly as in the classic app.
import { supabase } from "./supabase.js";

const must = ({ data, error }) => { if (error) throw error; return data; };

export async function settings(userId) {
  try {
    const rows = must(await supabase.from("user_preferences").select("settings").eq("user_id", userId).limit(1));
    return (rows[0] && rows[0].settings) || {};
  } catch (e) { return {}; }
}

export async function plan(userId) {
  try {
    const rows = must(await supabase.from("user_plans").select("plan").eq("user_id", userId).limit(1));
    return (rows[0] && rows[0].plan) || "pro";
  } catch (e) { return "pro"; }          // no row (or no table yet): the beta plan, as in the classic app
}

// ---- Trade Log ---------------------------------------------------------------------------------------------------

const CONN_COLS = "id,platform,label,status,last_sync_at,last_error,created_at,cash_usd,portfolio_at,insights_at";
export async function connections() {
  let r = await supabase.from("trade_connections").select(CONN_COLS).order("created_at");
  if (r.error) r = await supabase.from("trade_connections").select("id,platform,label,status,last_sync_at,last_error,created_at").order("created_at");
  return must(r) || [];
}

const cache = new Map();
export function forgetInsights() { cache.clear(); }

// One ready-made summary: scope "all" or a connection id, whose own / copied / all, period 1y / 3y / 5y / all.
export function insights(scope, whose, period) {
  const key = `${scope}|${whose}|${period}`;
  if (!cache.has(key)) {
    cache.set(key, supabase.from("trade_insights").select("data,computed_at")
      .eq("scope", scope).eq("whose", whose).eq("period", period).limit(1)
      .then((r) => { const rows = must(r); return (rows && rows[0]) || null; })
      .catch((e) => { cache.delete(key); throw e; }));
  }
  return cache.get(key);
}

const TRADE_COLS = "id,user_id,connection_id,asset_key,asset_class,closed_at,opened_at,name,symbol,direction,net_result_usd,"
  + "result_pct,risk_r,exit_kind,kept_pct,after20_pct,copied,leverage,entry_price,exit_price,invested_usd,fees_usd,"
  + "stop_loss,take_profit,parts";

// A page of closed trades, newest first, with MarketNavi's readings at entry and exit.
export async function trades({ scope, whose, since, cls, offset, limit = 50, hideRewards }) {
  let q = supabase.from("trade_round_trips").select(TRADE_COLS).order("closed_at", { ascending: false })
    .range(offset, offset + limit - 1);
  if (scope && scope !== "all") q = q.eq("connection_id", scope);
  if (whose === "own") q = q.eq("copied", false);
  if (whose === "copied") q = q.eq("copied", true);
  if (since) q = q.gte("closed_at", since);
  if (cls) q = q.eq("asset_class", cls);
  if (hideRewards) q = q.eq("reward", false);
  const rows = must(await q) || [];
  const ids = rows.map((r) => r.id);
  const snaps = ids.length ? (must(await supabase.from("trade_snapshots").select("round_trip_id,moment,readings,source")
    .in("round_trip_id", ids)) || []) : [];
  const by = {};
  snaps.forEach((s) => { (by[s.round_trip_id] = by[s.round_trip_id] || {})[s.moment] = { ...(s.readings || {}), _source: s.source }; });
  return rows.map((r) => ({ ...r, entry: (by[r.id] || {}).entry || null, exit: (by[r.id] || {}).exit || null }));
}

export async function note(tripId) {
  const rows = must(await supabase.from("trade_notes").select("note,tags").eq("round_trip_id", tripId).limit(1));
  return (rows && rows[0]) || { note: "", tags: [] };
}

export async function saveNote(trip, text, tags) {
  must(await supabase.from("trade_notes").upsert({ round_trip_id: trip.id, user_id: trip.user_id, note: text.slice(0, 2000),
    tags: tags.slice(0, 12), updated_at: new Date().toISOString() }, { onConflict: "round_trip_id" }));
}

// Daily closes for one asset MarketNavi follows (the shared price store), for the price around a trade.
const closesCache = new Map();
export function closes(assetKey) {
  if (!closesCache.has(assetKey)) {
    closesCache.set(assetKey, supabase.from("asset_market").select("prices").eq("asset_key", assetKey).limit(1)
      .then((r) => {
        let p = ((must(r) || [])[0] || {}).prices || [];
        if (typeof p === "string") { try { p = JSON.parse(p); } catch (e) { p = []; } }
        return (p || []).filter((x) => x && x.t && x.c != null).map((x) => [String(x.t).slice(0, 10), Number(x.c)]);
      }).catch(() => []));
  }
  return closesCache.get(assetKey);
}

export async function review(weekStart, scope) {
  const rows = must(await supabase.from("trade_reviews").select("review,created_at").eq("week_start", weekStart).eq("scope", scope).limit(1));
  return (rows && rows[0]) || null;
}

// Ask for this week's review: the background job writes it within about 5 minutes (it holds the AI keys).
export async function requestReview(userId, weekStart, scope, language, zone) {
  must(await supabase.from("trade_reviews").upsert({ user_id: userId, week_start: weekStart, scope, language,
    provider: "", review: { pending: true, zone } }, { onConflict: "user_id,week_start,scope" }));
}

export const rpc = async (name, args) => must(await supabase.rpc(name, args || {}));
