import React, { useEffect, useState } from "react";
import { T, lang } from "../../lib/i18n.js";
import { review as loadReview, requestReview } from "../../lib/api.js";
import { dayMonth, dayMonthYear } from "../../lib/format.js";
import { LABEL } from "./Edge.jsx";

// The last finished Monday-to-Sunday week, as the classic app counts it (tradelog_coach.week_of).
function lastWeek() {
  const now = new Date();
  const day = (now.getDay() + 6) % 7;                       // Monday 0
  const monday = new Date(now); monday.setDate(now.getDate() - day - 7);
  const sunday = new Date(monday); sunday.setDate(monday.getDate() + 6);
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return [iso(monday), iso(sunday)];
}

const PRO = ["pro", "elite"];

// 🧭 The weekly review: last week's own trades, written by the AI from checked facts (Pro and Elite).
export default function Review({ account, classes }) {
  const [start, end] = lastWeek();
  const [scope, setScope] = useState("all");
  const [row, setRow] = useState(undefined);
  const [asked, setAsked] = useState(false);
  const L = LABEL();
  useEffect(() => {
    let live = true, timer;
    const look = () => loadReview(start, scope).then((r) => {
      if (!live) return;
      setRow(r);
      if (r && r.review && r.review.pending) timer = window.setTimeout(look, 30000);   // the job writes it within minutes
    }).catch(() => live && setRow(null));
    look();
    return () => { live = false; window.clearTimeout(timer); };
  }, [start, scope, asked]);
  if (!PRO.includes(account.plan)) {
    return <section className="card"><h2>{T("Weekly review")}</h2><p className="sub">{T("A short review of your week, written for you each week. Comes with Pro.")}</p></section>;
  }
  const rv = row && row.review;
  const ask = async () => { await requestReview(account.user.id, start, scope, lang, account.zone); setAsked((x) => !x); };
  return (
    <section className="card">
      <div className="bar">
        <h2>{T("Weekly review")} · <span style={{ fontWeight: 400 }}>{T("{a} to {b}", { a: dayMonth(start), b: dayMonthYear(end) })}</span></h2>
        <div className="chips" style={{ marginLeft: "auto" }}>
          {["all", ...classes.map((c) => `class:${c}`)].map((sc) => (
            <button key={sc} type="button" className={scope === sc ? "on" : ""} onClick={() => setScope(sc)}>{sc === "all" ? T("All") : L[sc.slice(6)] || sc.slice(6)}</button>
          ))}
        </div>
      </div>
      {row === undefined && <div className="empty">{T("Loading…")}</div>}
      {row !== undefined && !rv && (
        <div style={{ marginTop: 10 }}>
          <button type="button" className="primary" onClick={ask}>{T("Write my review")}</button>
          <p className="sub">{T("Written once from your own trades, then kept. Describes, never advises.")}</p>
        </div>
      )}
      {rv && rv.pending && <div className="note plain" style={{ marginTop: 10 }}>{T("Writing your review… It appears here within about 5 minutes.")}</div>}
      {rv && !rv.pending && (
        <div style={{ marginTop: 8 }}>
          {!rv.empty && [[T("What happened"), rv.happened], [T("One pattern worth noticing"), rv.pattern], [T("One question for you"), rv.question]].map(([h, b]) => (
            <div key={h} style={{ margin: "6px 0 12px" }}>
              <div className="ml" style={{ textTransform: "uppercase", letterSpacing: ".04em", fontSize: 12, color: "var(--ang-muted)" }}>{h}</div>
              <div>{b}</div>
            </div>
          ))}
          {rv.plain && <p className="sub">{T("A plain summary of the facts: the written review didn't pass our checks this time.")}</p>}
          {rv.empty && <p className="sub">{T("No trades closed that week.")}</p>}
        </div>
      )}
      <p className="sub">{T("Describes your past trades. Not advice.")}</p>
    </section>
  );
}
