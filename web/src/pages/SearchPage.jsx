import React, { useEffect, useState } from "react";
import { T, lang } from "../lib/i18n.js";
import { search } from "../lib/service.js";
import { universe } from "../lib/assets.js";
import { signed, tone, dayMonthYear } from "../lib/format.js";
import { assetHref } from "../components/Search.jsx";
import { openNavigator } from "../components/Navigator.jsx";

const sc = (s) => (s == null ? null : Math.round((Number(s) - 50) * 2));
const ago = (iso) => {
  if (!iso) return "";
  const h = (Date.now() - new Date(iso).getTime()) / 36e5;
  return h < 1 ? T("within the hour") : h < 48 ? T("{n} hours ago", { n: Math.round(h) }) : T("{n} days ago", { n: Math.round(h / 24) });
};

// Everything in MarketNavi that mentions a topic: the scored news across every asset and market, the assets most
// mentioned, and the member's own Logbook. The Navigator can sum it up.
export default function SearchPage({ q }) {
  const [got, setGot] = useState(null);
  const [err, setErr] = useState("");
  const [names, setNames] = useState({});
  useEffect(() => {
    let live = true; setGot(null); setErr("");
    search(q).then((g) => live && setGot(g)).catch((e) => live && setErr(e.status === 0 ? T("Search isn't reachable just now. Please try again in a minute.") : T("Search couldn't run just now.")));
    universe().then((u) => live && setNames(Object.fromEntries(u.map((a) => [a.key, a])))).catch(() => {});
    return () => { live = false; };
  }, [q]);
  const mood = got ? sc(got.mood) : null;
  const summarise = () => openNavigator({
    question: T("Summarise what the news says about “{q}” and what it means for the markets, citing the headlines.", { q }),
    onScreen: "Search results for " + q + ":\n" + (got.news || []).slice(0, 25).map((n) => `- ${n.title} (${n.source}, score ${sc(n.score)})`).join("\n"),
  });
  return (
    <div className="page">
      <div>
        <h1 className="ptitle">“{q}”</h1>
        <p className="sub">{!got ? (err || T("Searching…")) : T("{n} headlines mention it, across every asset and market MarketNavi follows.", { n: got.count })}</p>
      </div>
      {got && got.count > 0 && (
        <section className="tiles closed">
          <div className="tile"><div className="l">{T("Headlines")}</div><div className="v">{got.count}</div><div className="s">{T("in the last day or two")}</div></div>
          <div className="tile"><div className="l">{T("News mood")}</div><div className={"v " + (mood ? tone(mood) : "")}>{signed(mood)}</div><div className="s">{T("average of their scores")}</div></div>
          <div className="tile"><div className="l">{T("AI Navigator")}</div><div className="v" style={{ fontSize: 16, paddingTop: 6 }}><button type="button" className="primary" onClick={summarise}>{T("Summarise")}</button></div><div className="s">{T("a short summary, citing the headlines")}</div></div>
        </section>
      )}
      {got && got.assets.length > 0 && (
        <section className="card">
          <h2>{T("Assets in the news")}</h2>
          <p className="sub">{T("The assets whose news mentions it most.")}</p>
          <div className="chips" style={{ flexWrap: "wrap", gap: 8 }}>
            {got.assets.map((a) => { const m = names[a.key]; return (
              <a key={a.key} className="pillink" href={assetHref(a.key, "news")}><b>{m ? m.symbol : a.key.split("|")[1]}</b> <span className="m">{m ? m.name : ""} · {T("{n} articles", { n: a.articles })}</span></a>
            ); })}
          </div>
        </section>
      )}
      {got && (
        <section className="card">
          <h2>{T("The news")}</h2>
          {!got.news.length ? <p className="sub">{T("Nothing in the current news mentions it. Try a broader word.")}</p> : (
            <ol className="stories">
              {got.news.map((h) => { const s = sc(h.score); const subj = h.subject.startsWith("Market|") ? null : names[h.subject]; return (
                <li key={h.id + h.subject}>
                  <span className={"sbadge " + tone(s)}>{signed(s)}</span>
                  <div>
                    <a href={h.link} target="_blank" rel="noopener noreferrer" className="b">{(h.tr && h.tr[lang]) || h.title}</a>
                    <div className="m">{h.source} · {ago(h.published_at)}{subj ? <> · <a className="linkish" href={assetHref(h.subject, "news")}>{subj.symbol}</a></> : null}</div>
                  </div>
                </li>
              ); })}
            </ol>
          )}
        </section>
      )}
      {got && got.logbook.length > 0 && (
        <section className="card">
          <h2>{T("Your Logbook")}</h2>
          <ol className="stories">
            {got.logbook.map((l, i) => <li key={i}><div><b>{T("Passage Plan")} · {dayMonthYear(l.day)}</b><div className="m">“…{l.snippet}…”</div></div></li>)}
          </ol>
        </section>
      )}
    </div>
  );
}
