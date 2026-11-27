import React, { useEffect, useState } from "react";
import * as LightweightCharts from "lightweight-charts";
import { T, lang } from "../../lib/i18n.js";
import { call } from "../../lib/service.js";
import ClassicComponent from "../../components/ClassicComponent.jsx";
import Icon, { Glyphs } from "../../components/Icon.jsx";
import Markdown from "../../components/Markdown.jsx";
import soundingsChart from "../../generated/soundings_chart.js";

// 🧭 Soundings (preview): what came before past rises and falls, found in the search years and checked on later years
// the search never saw (service/soundings_page.py, from the last checked run). The chart is the classic one, drawn
// with the app's own copy of the chart library. 🧩 Open as Set takes a result to the Set editor as a new Set.
if (typeof window !== "undefined" && !window.LightweightCharts) window.LightweightCharts = LightweightCharts;

const bold = (s) => String(s || "").split(/<\/?b>/).map((x, i) => (i % 2 ? <b key={i}>{x}</b> : <Glyphs key={i} text={x} />));

export default function Soundings() {
  const [market, setMarket] = useState("crypto");
  const [tab, setTab] = useState("chart");
  const [rep, setRep] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    setRep(null);
    call(`/soundings/report?market=${market}&lang=${lang}`).then(setRep).catch(() => setErr(T("Soundings isn't reachable just now. Please try again in a minute.")));
  }, [market]);
  return (
    <div className="sndp">
      <p className="sub">{T("Start from past rises and falls, and look back at what came before them.")} {T("Readings at the close before each move, compared with the same coin's usual chance of a move that year. Anything found in the search years must also hold on later years the search never saw. This describes the past: it is not a forecast or advice.")}</p>
      <div className="funrow">
        <div className="seg" role="radiogroup" aria-label={T("Market")}>
          {[["crypto", "coins", T("Crypto")], ["equity", "landmark", T("Equities")]].map(([k, ic, l]) => <button key={k} type="button" role="radio" aria-checked={market === k} className={market === k ? "on" : ""} onClick={() => setMarket(k)}><Icon n={ic} size={15} /> {l}</button>)}
        </div>
        <div className="chips" role="tablist">
          {[["chart", "map", T("Chart")], ["rise", "trending-up", T("📈 Before rises")], ["fall", "trending-down", T("📉 Before falls")]].map(([k, ic, l]) => <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}><Icon n={ic} size={15} /> {l}</button>)}
        </div>
      </div>
      {err ? <p className="note bad">{err}</p> : !rep ? <div className="empty" style={{ height: 300 }}>{T("Loading…")}</div>
        : !rep.ready ? <p className="sub">{rep.message}</p> : (
          <>
            <details className="latdet"><summary>{T("How this run was done")}</summary><Markdown text={rep.how} /></details>
            {tab === "chart" ? <Chart key={market} rep={rep} /> : <Results part={rep.targets[tab]} target={tab} />}
          </>
        )}
    </div>
  );
}

function Results({ part, target }) {
  const [msg, setMsg] = useState("");
  const open = async (c) => {
    try {
      const r = await call("/soundings/set", { method: "POST", body: { condition: c.condition, target, lift: c.search_lift, later: c.lift, lang } });
      if (!r.ok) { setMsg(r.message); return; }
      try { window.sessionStorage.setItem("mn_new_set", JSON.stringify({ model: r.model, message: r.message })); } catch (e) { /* private window */ }
      window.location.hash = "lattice/sets/fromsoundings";
    } catch (e) { setMsg(T("That didn't work just now. Please try again.")); }
  };
  return (
    <>
      <p className="sub">{part.caption}</p>
      {part.empty && <p>{part.empty}</p>}
      {msg && <p className="note bad">{msg}</p>}
      {part.groups.map((g) => (
        <section key={g.key} className="sndgroup">
          <div className="rowtitle"><Glyphs text={g.icon} /> {g.word} ({g.count}) <span className="m">· {g.why}</span></div>
          {g.cards.map((c, i) => (
            <div key={i} className="sndcard">
              <div className="sndcond">{c.condition.join(" + ")}</div>
              <div className="m">{bold(c.search)}</div>
              <div className="m">{bold(c.later)}</div>
              {c.tides.length > 0 && <div className="m" title={c.tides_hint}>{c.tides_label}: {c.tides.map((x, j) => <span key={j}>{j ? " · " : ""}<Icon n={x.tide === "in" ? "arrow-up-right" : x.tide === "out" ? "arrow-down-right" : "arrow-left-right"} size={13} /> {x.word} <b>{x.lift == null ? "–" : `${x.lift.toFixed(1)}×`}</b> ({x.days})</span>)}</div>}
              {c.theme && <div className="m" title={c.theme_list.join("\n")}>{c.theme}</div>}
              {g.key !== "faded" && <button type="button" className="ghost bordered" onClick={() => open(c)}
                title={T("Opens this condition in Signal Sets as a new Set (daily candles), to save, scan in Prism, put in a funnel or get alerts from.")}><Icon n="puzzle" size={15} /> {T("🧩 Open as Set")}</button>}
            </div>
          ))}
        </section>
      ))}
    </>
  );
}

function Chart({ rep }) {
  const [coin, setCoin] = useState(rep.first_coin);
  const [period, setPeriod] = useState("12m");
  const [target, setTarget] = useState("rise");
  const [faded, setFaded] = useState(false);
  const [d, setD] = useState(null);
  useEffect(() => {
    if (!coin) return;
    let gone = false;
    const dark = document.documentElement.classList.contains("night");
    call(`/soundings/chart?market=${rep.market}&coin=${encodeURIComponent(coin)}&period=${period}&target=${target}&faded=${faded}&dark=${dark}&lang=${lang}`)
      .then((x) => !gone && setD(x)).catch(() => !gone && setD({ ready: false, message: T("That didn't work just now. Please try again.") }));
    return () => { gone = true; };
  }, [coin, period, target, faded]);
  if (!rep.coins.length) return <p className="sub">{T("The chart's data is not available yet.")}</p>;
  return (
    <>
      <div className="histbar">
        <label className="m">{T("Asset")}<select value={coin} onChange={(e) => setCoin(e.target.value)}>{rep.coins.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <label className="m">{T("Period")}<select value={period} onChange={(e) => setPeriod(e.target.value)}>
          <option value="12m">{T("Last 12 months")}</option>
          {(d && d.years ? d.years : []).map((y) => <option key={y} value={y}>{y}</option>)}
          <option value="all">{T("All years")}</option>
        </select></label>
        <div className="seg" role="radiogroup" aria-label={T("Move")}>
          {[["rise", "trending-up", T("📈 Rises")], ["fall", "trending-down", T("📉 Falls")]].map(([k, ic, l]) => <button key={k} type="button" role="radio" aria-checked={target === k} className={target === k ? "on" : ""} onClick={() => setTarget(k)}><Icon n={ic} size={15} /> {l}</button>)}
        </div>
        <label className="ptog"><input type="checkbox" checked={faded} onChange={(e) => setFaded(e.target.checked)} /> <span>{T("Show faded too")}</span></label>
      </div>
      {!d ? <div className="empty" style={{ height: 360 }}>{T("Loading…")}</div> : !d.ready || !d.payload ? <p className="sub">{d.message}</p> : (
        <>
          <p className="sub">{d.caption}</p>
          <ClassicComponent fn={soundingsChart} css="" data={d.payload} onTrigger={() => {}} className="sndchart" />
          <p className="m">{d.zoom}</p>
          <Markdown text={d.summary} />
        </>
      )}
    </>
  );
}
