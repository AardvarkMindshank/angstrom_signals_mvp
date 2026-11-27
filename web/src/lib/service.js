// The MarketNavi data service (service/app.py on Render): live Sets, Sonar, topic search and the AI Navigator, the
// parts that need MarketNavi's Python engine or the AI keys. Every call carries the member's own sign-in.
import { supabase } from "./supabase.js";

export const DATA_URL = (import.meta.env.VITE_DATA_URL || "https://marketnavi-data.onrender.com").replace(/\/$/, "");

export class ServiceError extends Error {
  constructor(status, detail) { super(detail || String(status)); this.status = status; this.detail = detail || ""; }
}

// A call that can't reach the service at all (it is restarting after an update, say) is tried again once, a few
// seconds later, before the page says it isn't reachable.
export async function call(path, opts = {}) {
  try { return await once(path, opts); } catch (e) {
    // only when the request surely did nothing: no connection at all, or the service answered 502/503 (not up yet);
    // never after a time-out, which may have saved something
    if (!(e instanceof ServiceError) || !(e.detail === "unreachable" || e.status === 502 || e.status === 503)) throw e;
    await new Promise((r) => setTimeout(r, 4000));
    return once(path, opts);
  }
}

async function once(path, { method = "GET", body, timeout = 90000 } = {}) {
  const { data } = await supabase.auth.getSession();
  const token = data && data.session ? data.session.access_token : "";
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(DATA_URL + path, { method, signal: ctl.signal,
      headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : undefined });
    if (!r.ok) { let d = ""; try { d = (await r.json()).detail; } catch (e) { /* not JSON */ } throw new ServiceError(r.status, d); }
    return await r.json();
  } catch (e) {
    if (e instanceof ServiceError) throw e;
    throw new ServiceError(0, ctl.signal.aborted ? "timeout" : "unreachable");
  } finally { clearTimeout(timer); }
}

export const assetSets = (key) => call(`/asset/sets?key=${encodeURIComponent(key)}`, { timeout: 45000 });
export const sonar = (rows) => call("/sonar", { method: "POST", body: { time: rows.map((r) => r.time), open: rows.map((r) => r.open),
  high: rows.map((r) => r.high), low: rows.map((r) => r.low), close: rows.map((r) => r.close), volume: rows.map((r) => r.volume || 0) } });
export const search = (q) => call(`/search?q=${encodeURIComponent(q)}`);
export const ask = (question, history, language, onScreen) => call("/navigator", { method: "POST", timeout: 180000,
  body: { question, history, language, start: "panel", on_screen: onScreen || "" } });
