import React, { useEffect, useState } from "react";
import { T } from "../../lib/i18n.js";
import { funnelStatus } from "../../lib/assets.js";
import { dayMonthYear } from "../../lib/format.js";
import { assetSets } from "../../lib/service.js";

// Where this asset stands in the member's funnels, stage by stage, as the funnel job last checked it, and each of the
// member's own Sets checked on it right now by MarketNavi's engine (the data service), the same answer as Prism gives.
export default function Sets({ who, assetKey }) {
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
      <LiveSets assetKey={assetKey} />
    </div>
  );
}

function LiveSets({ assetKey }) {
  const [got, setGot] = useState(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState(null);
  const [round, setRound] = useState(0);
  useEffect(() => {
    // The first check after the service wakes can stall, so one quiet retry before saying so; then a Try again button.
    let live = true; setGot(null); setErr("");
    const go = (n) => assetSets(assetKey).then((g) => live && setGot(g)).catch((e) => {
      if (!live) return;
      if (n < 1 && e.status !== 401 && e.status !== 403) go(n + 1); else setErr(e.status === 0 ? "down" : "fail");
    });
    go(0);
    return () => { live = false; };
  }, [assetKey, round]);
  const ANSWER = { yes: T("Yes"), no: T("No"), unknown: T("Not known yet") };
  return (
    <section className="card">
      <h2>{T("Your Sets on this asset")}</h2>
      <p className="sub">{T("Each of your own Sets checked on this asset right now, the same answer Prism would give.")}</p>
      {err ? <p className="sub">{err === "down" ? T("The service that checks Sets isn't reachable just now.") : T("Your Sets couldn't be checked just now. Please try again in a minute.")} <button type="button" className="linkish" onClick={() => setRound(round + 1)}>{T("Try again")}</button></p>
        : !got ? <p className="sub">{T("Checking your Sets… this can take up to a minute the first time.")}</p>
        : !got.sets.length ? <p className="sub">{<a className="linkish" href="#lattice/sets">{T("You haven't made any Sets yet. Build one in Lattice › Signal Sets.")}</a>}</p> : (
          <ol className="fsteps">
            {got.sets.map((x) => (
              <li key={x.id} className={x.answer}>
                <span className="fdot" aria-hidden="true" />
                <a className="b linkish" href={`#lattice/sets/saved:${encodeURIComponent(x.id)}`} title={T("Open in Signal Sets")}>{x.name}</a>
                <span className="m">{({ Definite: T("Definite"), Undecided: T("Undecided") })[x.how_sure] || x.how_sure}</span>
                <span className="fans">{ANSWER[x.answer] || "—"}</span>
                {x.why && (open === x.id || x.why.length < 120 ? <span className="m fline">{x.why}</span>
                  : <button type="button" className="linkish fline" style={{ textAlign: "left" }} onClick={() => setOpen(x.id)}>{x.why.slice(0, 110)}… {T("more")}</button>)}
              </li>
            ))}
          </ol>
        )}
      {got && got.more > 0 && <p className="sub">{T("Showing your first {n} Sets.", { n: got.sets.length })}</p>}
    </section>
  );
}
