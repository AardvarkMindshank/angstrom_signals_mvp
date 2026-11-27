import React, { useEffect, useState } from "react";
import { T } from "../../lib/i18n.js";
import { supabase, SUPABASE_URL } from "../../lib/supabase.js";
import { saveSettings } from "../../lib/account.js";
import { dayMonthYear } from "../../lib/format.js";
import { Video, Outlook, Passage } from "../snapshot/Snapshot.jsx";
import { Rich } from "../../components/Navigator.jsx";

// 📓 The Logbook: one day at a time (Today, the arrows, or a date), with that day's video, Morning Outlook and your
// Passage Plan (spoken, and the written plan kept in navigator_logbook), and the podcast feeds for Pro and Elite.
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const today = () => iso(new Date());
const shift = (day, n) => { const d = new Date(day + "T12:00:00"); d.setDate(d.getDate() + n); return iso(d); };
const OLDEST_DAYS = 14;

export default function Logbook({ account }) {
  const [day, setDay] = useState(today());
  const [plans, setPlans] = useState({});
  const pro = ["pro", "elite"].includes(account && account.plan);
  const oldest = shift(today(), -OLDEST_DAYS);
  useEffect(() => {
    (async () => {
      try {
        const { data: u } = await supabase.auth.getUser();
        const { data } = await supabase.from("navigator_logbook").select("day, body, created_at").eq("owner_id", u.user.id).eq("kind", "passage_plan")
          .gte("day", oldest).order("created_at", { ascending: false }).limit(40);
        const by = {}; (data || []).forEach((r) => { const d = String(r.day || r.created_at || "").slice(0, 10); if (!by[d]) by[d] = r.body || ""; });
        setPlans(by);
      } catch (e) { setPlans({}); }
    })();
  }, []);
  const isToday = day === today();
  return (
    <div className="page">
      <div className="bar">
        <h1 className="ptitle" style={{ marginRight: "auto" }}>📓 {T("Logbook")}</h1>
        <div className="daybar">
          <button type="button" className="ghost icon" disabled={day <= oldest} onClick={() => setDay(shift(day, -1))} aria-label={T("The day before")} title={T("The day before")}>◀</button>
          <button type="button" className={"ghost" + (isToday ? " on" : "")} onClick={() => setDay(today())}>{T("Today")}</button>
          <button type="button" className="ghost icon" disabled={isToday} onClick={() => setDay(shift(day, 1))} aria-label={T("The day after")} title={T("The day after")}>▶</button>
          <input type="date" value={day} min={oldest} max={today()} onChange={(e) => e.target.value && setDay(e.target.value)} aria-label={T("Date")} />
        </div>
      </div>
      <p className="sub">{T("Each day's video, Morning Outlook and your Passage Plan, kept for two weeks. Showing {day}.", { day: dayMonthYear(day) })}</p>
      <div className="snaptop">
        <Video account={account} day={day} key={"v" + day} />
        <Outlook day={day} />
        <Passage account={account} day={day} written={plans[day] ? <Rich text={plans[day]} /> : null} key={"p" + day} />
      </div>
      {pro && <Feeds account={account} />}
    </div>
  );
}

function Feeds({ account }) {
  const [token, setToken] = useState((((account && account.settings) || {}).briefing || {}).token || "");
  const [copied, setCopied] = useState("");
  const url = (path) => `${SUPABASE_URL.replace(/\/$/, "")}/storage/v1/object/public/briefings/${path}`;
  const copy = (u) => { navigator.clipboard.writeText(u).then(() => { setCopied(u); setTimeout(() => setCopied(""), 1800); }).catch(() => {}); };
  const renew = async () => {
    const bytes = crypto.getRandomValues(new Uint8Array(18));
    const fresh = btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    const b = { ...((((account && account.settings) || {}).briefing) || {}), token: fresh };
    try { await saveSettings({ briefing: b }); setToken(fresh); } catch (e) { /* stays as it was */ }
  };
  const rows = [["🧭 " + T("Your Passage Plan"), token ? url(`${token}/feed.xml`) : ""], ["🌍 " + T("Morning Outlook"), url("general/feed.xml")]];
  return (
    <section className="card">
      <h2>🎙️ {T("Listen in a podcast app")}</h2>
      <p className="sub">{T("Add these feeds to Apple Podcasts (Library, then Follow a Show by URL), Pocket Casts or Overcast, and each one downloads by itself. Your own feed is private: anyone with the link can listen, so keep it to yourself. Spotify can't take private feeds.")}</p>
      {rows.map(([name, u]) => u && (
        <div key={name} className="srow2">
          <div className="stext"><div className="stitle">{name}</div><div className="shelp feedurl">{u}</div></div>
          <div className="sctl"><button type="button" className="ghost" onClick={() => copy(u)}>{copied === u ? "✓ " + T("Copied") : T("Copy link")}</button></div>
        </div>
      ))}
      <button type="button" className="linkish" onClick={renew} title={T("The old link stops getting new plans.")}>🔄 {T("Make a new private link")}</button>
    </section>
  );
}
