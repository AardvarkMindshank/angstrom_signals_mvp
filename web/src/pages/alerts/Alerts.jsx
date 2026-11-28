import React, { useEffect, useState } from "react";
import { useDelayed, UndoButton } from "../../components/Confirm.jsx";
import Icon, { Tile } from "../../components/Icon.jsx";
import { T } from "../../lib/i18n.js";
import { supabase } from "../../lib/supabase.js";
import { watchlists } from "../../lib/assets.js";
import { stamp } from "../../lib/format.js";
import { assetHref } from "../../components/Search.jsx";
import { alertText } from "../asset/words.js";

// 🔔 Your alerts: unread first, then newest. A click opens what it is about (an asset on its chart, a market's
// sentiment, a funnel's Candidates). Read alerts can be cleared; a reading still past its line stays latched, so it
// does not alert again until it comes back (alerts.dismiss_read_alerts), exactly as in the classic app.
const OPEN = ["BULLISH_THRESHOLD", "BEARISH_THRESHOLD", "TREND_UP", "TREND_DOWN", "STRETCH_UP", "STRETCH_DOWN", "FLOW_UP", "FLOW_DOWN"];
const HELD = OPEN.map((k) => k + "_HELD");
const QUIET = ["invite_joined", "group_invite", "group_joined", "moderation_warning", "report_update"];
const ICON = { TREND_UP: "trending-up", TREND_DOWN: "trending-down", STRETCH_UP: "target", STRETCH_DOWN: "target", FLOW_UP: "audio-lines", FLOW_DOWN: "audio-lines", BULLISH_THRESHOLD: "globe", BEARISH_THRESHOLD: "globe",
  funnel: "funnel", study: "microscope", chart_share: "share", prism: "search", group_invite: "users", invite_joined: "users", group_joined: "users", moderation_warning: "triangle-exclamation-point", report_update: "shield" };

export default function Alerts() {
  const [rows, setRows] = useState(null);
  const [wl, setWl] = useState({ crypto: {}, equity: {} });
  const [busy, setBusy] = useState(false);
  const load = async () => {
    try {
      const { data: u } = await supabase.auth.getUser();
      try { await supabase.rpc("expire_my_group_invites"); } catch (e) { /* not installed */ }
      const { data } = await supabase.from("user_notifications").select("*").eq("user_id", u.user.id)
        .not("alert_type", "in", `(${HELD.join(",")})`).order("created_at", { ascending: false }).limit(60);
      setRows(data || []);
    } catch (e) { setRows([]); }
  };
  useEffect(() => { load(); watchlists().then(setWl).catch(() => {}); }, []);
  const isAlert = (n) => n.alert_type !== "group_invite";
  const act = async (what) => {
    setBusy(true);
    try {
      const { data: u } = await supabase.auth.getUser(), me = u.user.id;
      if (what === "read" || what === "all") await supabase.from("user_notifications").update({ is_read: true }).eq("user_id", me).neq("alert_type", "group_invite");
      if (what === "clear" || what === "all") {
        for (const k of OPEN) await supabase.from("user_notifications").update({ alert_type: k + "_HELD", is_read: true }).eq("user_id", me).eq("is_read", true).eq("alert_type", k);
        await supabase.from("user_notifications").delete().eq("user_id", me).eq("is_read", true).neq("alert_type", "group_invite")
          .not("alert_type", "in", `(${[...HELD, "moderation_warning", "report_update"].join(",")})`);
      }
    } catch (e) { /* the list reloads as it is */ }
    await load(); setBusy(false);
  };
  const open = async (n) => {
    if (!n.is_read && isAlert(n)) { supabase.from("user_notifications").update({ is_read: true }).eq("id", n.id).then(() => {}, () => {}); }
  };
  const target = (n) => {
    const s = String(n.asset_symbol || "").trim();
    if (s.toLowerCase().startsWith("market:")) return `#mood/${s.slice(7).toLowerCase() === "stock" ? "stock" : "crypto"}`;
    if (n.alert_type === "funnel") return "#signals/" + (String(n.message || "").toLowerCase().includes("equit") ? "equity" : "crypto");
    if (!s) return null;
    const c = Object.keys(wl.crypto || {}).find((k) => k.toLowerCase() === s.toLowerCase());
    if (c) return assetHref(`Crypto|${c}`, "chart");
    const e = Object.keys(wl.equity || {}).find((k) => k.toUpperCase() === s.toUpperCase());
    if (e) return assetHref(`Stock|${e}`, "chart");
    return null;
  };
  const list = (rows || []).slice().sort((a, b) => (Number(!!a.is_read && isAlert(a)) - Number(!!b.is_read && isAlert(b))) || String(b.created_at).localeCompare(String(a.created_at)));
  // Clearing hides those alerts at once and shows Undo where you pressed; they are cleared a few seconds later.
  const later = useDelayed();
  const [hold, setHold] = useState(null);
  const clear = (what) => { setHold(what); later.run("clear", async () => { await act(what); setHold(null); }); };
  const shown = hold ? list.filter((n) => !isAlert(n) || (hold === "clear" && !n.is_read)) : list;
  const unread = list.filter((n) => isAlert(n) && !n.is_read).length;
  return (
    <div className="page">
      <div className="bar">
        <h1 className="ptitle" style={{ marginRight: "auto" }}><Tile n="bell" size={22} /> {T("Alerts")}{unread ? <span className="pcount">{unread}</span> : null}</h1>
        <div className="right">
          <button type="button" className="ghost" disabled={busy || !unread} onClick={() => act("read")} title={T("Mark all as read")} aria-label={T("Mark all as read")}><Icon n="check-check" /></button>
          {hold ? <UndoButton onUndo={() => { later.undo("clear"); setHold(null); }} /> : <>
          <button type="button" className="ghost" disabled={busy || !list.some((n) => isAlert(n) && n.is_read)} onClick={() => clear("clear")} title={T("Clear read alerts")} aria-label={T("Clear read alerts")}><Icon n="brush-cleaning" /></button>
          <button type="button" className="ghost" disabled={busy || !list.some(isAlert)} onClick={() => clear("all")} title={T("Clear all alerts. Each one was already sent by email or in your digest.")} aria-label={T("Clear all")}><Icon n="trash" /></button>
          </>}
        </div>
      </div>
      <p className="sub">{T("Alerts arrive here when a watchlist asset crosses one of your alert lines, a market's sentiment crosses its line, a Prism scan finds a match, a funnel has new Candidates, or a study you started finishes. Choose them in")} <a className="linkish" href="#settings/alerts"><Icon n="settings" size={15} /> {T("Settings")}</a>.</p>
      {rows === null ? <div className="empty" style={{ height: 200 }}>{T("Loading…")}</div> : !shown.length ? <p className="sub">{T("No alerts yet.")}</p> : (
        <ol className="alist">
          {shown.map((n) => {
            const href = target(n);
            const quiet = QUIET.includes(n.alert_type);
            const body = (
              <>
                <span className="aicon" aria-hidden="true"><Icon n={ICON[n.alert_type] || "bell"} /></span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="ahead"><b>{n.asset_name || T("Alert")}</b><span className="m">{stamp(n.created_at)}</span></div>
                  <div className="abody">{alertText(n.message)}</div>
                  {quiet && n.alert_type === "group_invite" && <Invite n={n} onDone={load} />}
                </div>
              </>
            );
            return (
              <li key={n.id} className={n.is_read && isAlert(n) ? "read" : ""}>
                {href ? <a className="arow" href={href} onClick={() => open(n)}>{body}</a> : <div className="arow" onClick={() => open(n)}>{body}</div>}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

// 👥 A community invitation: Accept or Dismiss (respond_group_invite, as the classic app).
function Invite({ n, onDone }) {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const raw = String(n.asset_symbol || "");
  const id = raw.startsWith("group:") ? parseInt(raw.slice(6), 10) : NaN;
  if (!id) return null;
  const answer = async (accept) => {
    setBusy(true); setMsg("");
    try {
      const { data, error } = await supabase.rpc("respond_group_invite", { invite_id: id, accept });
      const code = String(data || "").replace(/"/g, "").trim();
      if (error || !["ok", "dismissed", "gone", "expired", "full"].includes(code)) setMsg(T("That invite could not be updated. Please try again."));
      else if (code === "expired") setMsg(T("That invite has expired."));
      else if (code === "full") setMsg(T("That community already has 50 members."));
      else { onDone(); return; }
    } catch (e) { setMsg(T("That invite could not be updated. Please try again.")); }
    setBusy(false);
  };
  return (
    <div className="bar" style={{ marginTop: 8 }} onClick={(e) => e.stopPropagation()}>
      <button type="button" className="primary" disabled={busy} onClick={() => answer(true)}><Icon n="check" size={16} /> {T("Accept")}</button>
      <button type="button" className="ghost bordered" disabled={busy} onClick={() => answer(false)}>{T("Dismiss")}</button>
      {msg && <span className="m">{msg}</span>}
    </div>
  );
}
