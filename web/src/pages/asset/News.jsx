import React, { useEffect, useRef, useState } from "react";
import { T, lang } from "../../lib/i18n.js";
import { signed, tone, stamp } from "../../lib/format.js";
import { COVERAGE } from "./words.js";

const sc = (s) => (s == null ? null : Math.round((Number(s) - 50) * 2));
const tr = (obj, field) => (obj && obj.tr && obj.tr[lang] && obj.tr[lang][field]) || null;

// The asset's news, as scored by MarketNavi: the mood, the spread of the articles, what drove it, and each story.
// The strip and the stories are linked: hover a dot for its story, click it to open "Why this score" and bring the
// story into view, highlighted; hover or click a story (its score badge) to light up its dot on the strip.
const keyOf = (h) => h.id || h.link;

export default function News({ rep, score, at }) {
  const [open, setOpen] = useState(null);
  const [sel, setSel] = useState(null);      // the story chosen on the strip or in the list
  const [hot, setHot] = useState(null);      // the story under the pointer, in either place
  const rows = useRef({});
  const strip = useRef(null);
  if (!rep || !rep.ok) return <div className="empty">{T("No news has been scored for this asset in the last 12 hours.")}</div>;
  const heads = (rep.headlines || []).slice().sort((a, b) => String(b.published_at || "").localeCompare(String(a.published_at || "")));
  const local = (rep.tr && rep.tr[lang]) || {};
  const ago = (iso) => {
    if (!iso) return "";
    const h = (Date.now() - new Date(iso).getTime()) / 36e5;
    return h < 1 ? T("within the hour") : h < 48 ? T("{n} hours ago", { n: Math.round(h) }) : T("{n} days ago", { n: Math.round(h / 24) });
  };
  const fromStrip = (k) => {
    setSel(k); setOpen(k);
    const el = rows.current[k];
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  const fromList = (k) => {
    setSel(sel === k ? null : k);
    const el = strip.current;
    if (el && sel !== k) { const r = el.getBoundingClientRect(); if (r.bottom < 70 || r.top > window.innerHeight) el.scrollIntoView({ behavior: "smooth", block: "center" }); }
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
      <section className="card">
        <div className="bar" style={{ alignItems: "baseline" }}>
          <div className={"big-num " + tone(score)}>{signed(score)}</div>
          <div><b>{COVERAGE(score)}</b><div className="m">{T("{n} articles, scored {when}", { n: rep.scored || heads.length, when: stamp(at) })}</div></div>
        </div>
        <div ref={strip}><Spread heads={heads} score={score} sel={sel} hot={hot} setHot={setHot} pick={fromStrip} ago={ago} /></div>
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
            const s = sc(h.score), k = keyOf(h);
            return (
              <li key={k} ref={(el) => { rows.current[k] = el; }} className={(sel === k ? "sel" : "") + (hot === k ? " hot" : "")}
                onMouseEnter={() => setHot(k)} onMouseLeave={() => setHot(null)}>
                <button type="button" className={"sbadge " + tone(s)} onClick={() => fromList(k)} aria-pressed={sel === k}
                  title={T("Show this story on the strip above")}>{signed(s)}</button>
                <div>
                  <a href={h.link} target="_blank" rel="noopener noreferrer" className="b">{(h.tr && h.tr[lang]) || h.title}</a>
                  <div className="m">{h.source}{(h.also_sources || []).length ? " " + T("and {n} more", { n: h.also_sources.length }) : ""} · {ago(h.published_at)}</div>
                  {h.note && (open === k ? <p className="sub" style={{ margin: "4px 0 0" }}>{h.note}</p>
                    : <button type="button" className="linkish" onClick={() => { setOpen(k); setSel(k); }}>{T("Why this score")}</button>)}
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

function Spread({ heads, score, sel, hot, setHot, pick, ago }) {
  const dots = heads.map((h) => ({ h, k: keyOf(h), v: sc(h.score) })).filter((d) => d.v != null);
  if (!dots.length) return null;
  const seen = {};
  const tipFor = hot;
  let tip = null;
  return (
    <div className="spread" aria-label={T("The articles' scores from −100 to +100")}>
      <span className="strack" /><span className="smid" />
      {dots.map(({ h, k, v }) => {
        const b = Math.round(v / 8); const row = (seen[b] = (seen[b] || 0) + 1) - 1;
        const left = 50 + v / 2, top = 16 - row * 11;
        if (k === tipFor) tip = { h, v, left, top };
        return <button key={k} type="button" className={"sdot " + (v > 10 ? "good" : v < -10 ? "bad" : "mid") + (sel === k ? " sel" : "") + (hot === k ? " hot" : "")}
          style={{ left: `${left}%`, top }} aria-label={`${signed(v)} · ${(h.tr && h.tr[lang]) || h.title}`}
          onMouseEnter={() => setHot(k)} onMouseLeave={() => setHot(null)} onFocus={() => setHot(k)} onBlur={() => setHot(null)} onClick={() => pick(k)} />;
      })}
      {score != null && <span className="smark" style={{ left: `${50 + score / 2}%` }} />}
      <span className="sl">−100</span><span className="sr2">+100</span>
      {tip && (
        <div className={"stip" + (tip.left > 70 ? " r" : tip.left < 30 ? " l" : "")} style={{ left: `${tip.left}%`, top: tip.top }} role="tooltip">
          <b className={tone(tip.v)}>{signed(tip.v)}</b> {(tip.h.tr && tip.h.tr[lang]) || tip.h.title}
          <div className="m">{tip.h.source} · {ago(tip.h.published_at)}</div>
          {tip.h.note && <div className="m">{T("Click for why this score")}</div>}
        </div>
      )}
    </div>
  );
}
