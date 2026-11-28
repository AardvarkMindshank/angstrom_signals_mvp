import React, { useEffect, useState } from "react";
import Icon, { Tile } from "../../components/Icon.jsx";
import { T } from "../../lib/i18n.js";
import { supabase } from "../../lib/supabase.js";
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
        <h1 className="ptitle" style={{ marginRight: "auto" }}><Tile n="notebook" size={22} /> {T("Logbook")}</h1>
        <div className="daybar">
          <button type="button" className="ghost icon" disabled={day <= oldest} onClick={() => setDay(shift(day, -1))} aria-label={T("The day before")} title={T("The day before")}><Icon n="chevron-left" /></button>
          <button type="button" className={"ghost" + (isToday ? " on" : "")} onClick={() => setDay(today())}>{T("Today")}</button>
          <button type="button" className="ghost icon" disabled={isToday} onClick={() => setDay(shift(day, 1))} aria-label={T("The day after")} title={T("The day after")}><Icon n="chevron-right" /></button>
          <input type="date" value={day} min={oldest} max={today()} onChange={(e) => e.target.value && setDay(e.target.value)} aria-label={T("Date")} />
        </div>
      </div>
      <p className="sub">{T("Each day's video, Morning Outlook and your Passage Plan, kept for two weeks. Showing {day}.", { day: dayMonthYear(day) })}</p>
      <div className="snaptop logtop">
        <Video account={account} day={day} key={"v" + day} />
        <Outlook day={day} />
        <Passage account={account} day={day} written={plans[day] ? <Rich text={plans[day]} /> : null} key={"p" + day} />
      </div>
      {pro && <p className="sub"><Icon n="mic" size={16} /> {T("Listen in a podcast app:")} <a className="linkish" href="#settings/logbook">{T("get the feed links in ⚙️ Settings")} ›</a></p>}
    </div>
  );
}
