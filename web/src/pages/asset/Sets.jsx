import React, { useEffect, useState } from "react";
import { T } from "../../lib/i18n.js";
import { funnelStatus } from "../../lib/assets.js";
import { dayMonthYear } from "../../lib/format.js";
import { CLASSIC } from "../../lib/supabase.js";

// Where this asset stands in the member's funnels, stage by stage, as the funnel job last checked it. Checking the
// member's own Sets live needs MarketNavi's engine on a server, which comes next; until then they are in the classic app.
export default function Sets({ who }) {
  const [fu, setFu] = useState(null);
  useEffect(() => { let live = true; funnelStatus(who.id).then((x) => live && setFu(x)); return () => { live = false; }; }, [who.id]);
  const STATUS = { pool: T("In the pool"), stage: T("Passing stage {n} of {m}"), flagged: T("Flagged"), candidate: T("Candidate") };
  const ANSWER = { yes: T("Yes"), no: T("No"), unknown: T("Not known yet") };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
      <section className="card">
        <h2>{T("Your funnels")}</h2>
        <p className="sub">{T("Each stage is a Set the asset has to pass, from the first filter to the final check.")}</p>
        {fu === null ? <p className="sub">{T("Loading…")}</p> : !fu.length ? <p className="sub">{T("This asset isn't in any of your funnels.")}</p> : fu.map((f) => (
          <div key={f.funnel_id} className="funnel">
            <div className="bar" style={{ alignItems: "baseline" }}>
              <b style={{ fontSize: 16 }}>{f.name}</b>
              <span className="m">{f.direction === "short" ? T("Shorts") : T("Longs")}</span>
              <span className={"fstatus " + f.status}>{f.status === "stage" ? STATUS.stage.replace("{n}", f.depth).replace("{m}", f.stages || "?") : STATUS[f.status] || f.status}</span>
              <span className="m right">{T("checked {d}", { d: dayMonthYear(f.updated_at) })}</span>
            </div>
            <ol className="fsteps">
              {f.steps.map((s, i) => (
                <li key={i} className={s.answer || "none"}>
                  <span className="fdot" aria-hidden="true" />
                  <span className="b">{s.label || T("Stage {n}", { n: i + 1 })}</span>
                  {s.timeframe && <span className="m">{s.timeframe}</span>}
                  <span className="fans">{ANSWER[s.answer] || "—"}</span>
                  {s.line && <span className="m fline">{s.line}</span>}
                </li>
              ))}
            </ol>
          </div>
        ))}
      </section>
      <section className="card">
        <h2>{T("Your Sets on this asset")}</h2>
        <p className="sub">{T("Checking your own Sets on this asset right now, with their history behind the chart, is coming to the new app next. Until then they're in the classic app's Lattice.")} <a className="linkish" href={CLASSIC}>{T("Open the classic app")} ›</a></p>
      </section>
    </div>
  );
}
