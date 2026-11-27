import React, { useState } from "react";
import { T, lang } from "../../lib/i18n.js";
import { signed, tone, stamp } from "../../lib/format.js";
import { COVERAGE } from "./words.js";

const sc = (s) => (s == null ? null : Math.round((Number(s) - 50) * 2));
const tr = (obj, field) => (obj && obj.tr && obj.tr[lang] && obj.tr[lang][field]) || null;

// The asset's news, as scored by MarketNavi: the mood, the spread of the articles, what drove it, and each story.
export default function News({ rep, score, at }) {
  const [open, setOpen] = useState(null);
  if (!rep || !rep.ok) return <div className="empty">{T("No news has been scored for this asset in the last 12 hours.")}</div>;
  const heads = (rep.headlines || []).slice().sort((a, b) => String(b.published_at || "").localeCompare(String(a.published_at || "")));
  const local = (rep.tr && rep.tr[lang]) || {};
  const ago = (iso) => {
    if (!iso) return "";
    const h = (Date.now() - new Date(iso).getTime()) / 36e5;
    return h < 1 ? T("within the hour") : h < 48 ? T("{n} hours ago", { n: Math.round(h) }) : T("{n} days ago", { n: Math.round(h / 24) });
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
      <section className="card">
        <div className="bar" style={{ alignItems: "baseline" }}>
          <div className={"big-num " + tone(score)}>{signed(score)}</div>
          <div><b>{COVERAGE(score)}</b><div className="m">{T("{n} articles, scored {when}", { n: rep.scored || heads.length, when: stamp(at) })}</div></div>
        </div>
        <Spread heads={heads} score={score} />
        <p style={{ marginTop: 14 }}>{local.summary || rep.summary}</p>
        <div className="notes">
          {(local.positive || rep.positive) && <span className="note good">{local.positive || rep.positive}</span>}
          {(local.negative || rep.negative) && <span className="note bad">{local.negative || rep.negative}</span>}
        </div>
        {(rep.drivers || []).length > 0 && <p className="sub" style={{ marginTop: 12 }}>{T("What drove it")}: {(local.drivers || rep.drivers).join(" · ")}</p>}
      </section>
      <section className="card">
        <h2>{T("The stories")}</h2>
        <p className="sub">{T("Newest first. Each score is the AI's reading of that article, from −100 to +100.")}</p>
        <ol className="stories">
          {heads.map((h) => {
            const s = sc(h.score);
            return (
              <li key={h.id || h.link}>
                <span className={"sbadge " + tone(s)}>{signed(s)}</span>
                <div>
                  <a href={h.link} target="_blank" rel="noopener noreferrer" className="b">{(h.tr && h.tr[lang]) || h.title}</a>
                  <div className="m">{h.source}{(h.also_sources || []).length ? " " + T("and {n} more", { n: h.also_sources.length }) : ""} · {ago(h.published_at)}</div>
                  {h.note && (open === h.id ? <p className="sub" style={{ margin: "4px 0 0" }}>{h.note}</p>
                    : <button type="button" className="linkish" onClick={() => setOpen(h.id)}>{T("Why this score")}</button>)}
                </div>
              </li>
            );
          })}
        </ol>
        {rep.model && <p className="sub">{T("Scored by {model}.", { model: rep.model })}</p>}
      </section>
    </div>
  );
}

function Spread({ heads, score }) {
  const pts = heads.map((h) => sc(h.score)).filter((v) => v != null);
  if (!pts.length) return null;
  const seen = {};
  return (
    <div className="spread" aria-label={T("The articles' scores from −100 to +100")}>
      <span className="strack" /><span className="smid" />
      {pts.map((v, i) => { const b = Math.round(v / 8); const row = (seen[b] = (seen[b] || 0) + 1) - 1;
        return <span key={i} className={"sdot " + (v > 10 ? "good" : v < -10 ? "bad" : "mid")} style={{ left: `${50 + v / 2}%`, top: 16 - row * 11 }} />; })}
      {score != null && <span className="smark" style={{ left: `${50 + score / 2}%` }} />}
      <span className="sl">−100</span><span className="sr2">+100</span>
    </div>
  );
}
