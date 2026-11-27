import React, { useCallback, useEffect, useRef, useState } from "react";
import { T, lang } from "../../lib/i18n.js";
import { call } from "../../lib/service.js";
import ClassicComponent from "../../components/ClassicComponent.jsx";
import Icon from "../../components/Icon.jsx";
import prismBoard, { css as prismCss } from "../../generated/prism_board.js";
import { assetHref } from "../../components/Search.jsx";

// 🔎 Prism Scan: your saved scans on a board (the classic board, hosted), each a Set plus its assets, schedule and
// alerts. Every press goes to the data service (service/prism_page.py), which does what the classic page does; a
// ▶ Run now or ⏪ past-moment answer is kept here for the board while you stay in the app.
const kept = { results: {}, history: null };          // survives switching tabs, like the classic page's session

export default function Prism() {
  const [got, setGot] = useState(null);
  const [flash, setFlash] = useState(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const next = useRef({});
  const [hist, setHist] = useState(kept.history);

  const load = useCallback(async () => {
    try {
      const d = await call("/prism/board", { method: "POST", body: { results: kept.results, history: kept.history, ...next.current, lang } });
      next.current = {};
      setGot(d); setErr("");
    } catch (e) { setErr(T("Prism isn't reachable just now. Please try again in a minute.")); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const onTrigger = async (name, value) => {
    if (name !== "action") return;
    let act;
    try { act = JSON.parse(value); } catch (e) { return; }
    const long = act.op === "run" || act.op === "run_past";
    setBusy(long ? T("Checking the scan's assets… this can take up to a minute.") : T("Saving…"));
    setFlash(null);
    try {
      const r = await call("/prism/action", { method: "POST", body: { action: act, lang }, timeout: 180000 });
      if (r.result) kept.results[r.result.scan] = r.result.value;
      if (r.drop) delete kept.results[r.drop];
      if (r.open_new) next.current.open_new = r.open_new;
      if (r.goto) { window.location.hash = r.goto.slice(1); return; }
      if (r.history !== undefined) setHist(kept.history = r.history);
      if (r.message) setFlash([r.status, r.message]);
      await load();
    } catch (e) { setFlash(["error", T("That didn't work just now. Please try again.")]); }
    finally { setBusy(""); }
  };

  if (err) return <p className="note bad" style={{ marginTop: 16 }}>{err}</p>;
  if (!got) return <div className="empty" style={{ height: 360, marginTop: 16 }}>{T("Loading…")}</div>;
  if (!got.ready) return <p className="note bad" style={{ marginTop: 16 }}>{got.message}</p>;
  if (!got.has_assets) return <p className="sub" style={{ marginTop: 16 }}>{T("No assets in the watchlists.")} <a className="linkish" href="#settings/markets">{T("Add some in Settings ›")}</a></p>;
  return (
    <div className="prismp">
      <p className="sub">{T("Scan your Watchlist with a Set: now, at a past moment, or on a schedule with alerts.")}</p>
      {got.builtins.length > 0 && <Builtins rows={got.builtins} max={got.max_scans} />}
      {(busy || flash) && (
        <p className={"note " + (busy ? "" : flash[0] === "ok" ? "good" : "bad")} role="status">
          {busy ? <><Icon n="hourglass" size={15} /> {busy}</> : flash[1]}
        </p>
      )}
      <div className={busy ? "prismbusy" : ""}>
        <ClassicComponent fn={prismBoard} css={prismCss} data={got.board} onTrigger={onTrigger} className="prismboard" />
      </div>
      {hist && <History key={hist} scan={hist} onClose={() => { setHist(kept.history = null); load(); }} />}
      <p className="sub">{T("Answers are descriptive readings, not forecasts or advice. ▶ uses the latest finished candles; ⏪ rebuilds a past moment from today's data providers (a reconstruction, not a record).")}</p>
    </div>
  );
}

// The six built-in alerts (Trend, Stretch and Flow, up and down), folded at the top as in the classic app.
function Builtins({ rows, max }) {
  const on = rows.filter((r) => r.on).length;
  return (
    <details className="card latdet prismbuilt">
      <summary><Icon n="bell" size={16} /> {T("Provided by MarketNavi · built-in alerts, {on} of {len_builtins} on", { on, len_builtins: rows.length })}</summary>
      <p className="sub">{T("Trend, Stretch and Flow alerts, checked at each daily close (crypto 00:10 UTC, shares 10 minutes after the New York close) on the same readings as the dashboard. Change the lines and switch them on or off in Notifications → Configure Alert Rules. They don't count towards your {MAX_SCANS_TEXT} scheduled scans.", { MAX_SCANS_TEXT: max })}</p>
      <div className="latscroll">
        <table className="lattbl">
          <thead><tr><th>{T("Alert")}</th><th>{T("Says Yes at")}</th><th>{T("Alerts again after")}</th><th>{T("Alerts go")}</th><th>{T("Past the line now")}</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.name}>
              <td><Icon n={r.on ? "bell" : "bell-off"} size={14} /> {r.name}</td><td>{r.yes_at}</td><td>{r.again_after}</td><td>{r.goes}</td><td>{r.past == null ? "—" : r.past}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <a className="linkish" href="#settings/alerts"><Icon n="settings" size={14} /> {T("Alerts & email")} ›</a>
    </details>
  );
}

// 🕰️ Visualize History: the chosen asset's candles with the Set's answers as bands, and a thin pane per asset under it,
// all on one time axis (the Pro chart's engine draws it). Each asset's last year comes first; older years are worked
// out one step at a time while you look, and 3Y, 10Y and All open as every asset reaches them.
function History({ scan, onClose }) {
  const [sum, setSum] = useState(null);
  const [top, setTop] = useState("");
  const [years, setYears] = useState("1Y");
  const [showNo, setShowNo] = useState(false);
  const [view, setView] = useState(null);
  const [msg, setMsg] = useState("");
  const host = useRef(null);
  const live = useRef(true);
  useEffect(() => () => { live.current = false; }, []);
  useEffect(() => {                                       // start, then fill in older years one step at a time
    (async () => {
      try {
        let s = await call("/prism/history/start", { method: "POST", body: { scan, lang }, timeout: 300000 });
        if (!live.current) return;
        if (s.status !== "ok") { setMsg(s.message); return; }
        setSum(s);
        while (live.current && s.pending > 0) {
          s = await call("/prism/history/more", { method: "POST", body: { scan, lang }, timeout: 300000 });
          if (!live.current || s.status !== "ok") break;
          setSum(s);
        }
      } catch (e) { if (live.current) setMsg(T("That didn't work just now. Please try again.")); }
    })();
  }, [scan]);
  const ready = sum ? sum.ready : {};
  const readyKey = sum ? Object.entries(ready).filter(([, v]) => v).map(([k]) => k).join(",") : "";
  useEffect(() => {
    if (!sum) return;
    let gone = false;
    call("/prism/history/chart", { method: "POST", timeout: 120000,
      body: { scan, top, years, show_no: showNo, dark: document.documentElement.classList.contains("night"), lang } })
      .then((d) => { if (!gone) { setView(d); if (d.top && d.top !== top) setTop(d.top); } })
      .catch(() => !gone && setMsg(T("That didn't work just now. Please try again.")));
    return () => { gone = true; };
  }, [sum && sum.scan, top, years, showNo, readyKey]);
  useEffect(() => {                                       // draw with the Pro chart's engine; a tapped pane goes on top
    if (!view || !view.chart || !host.current) return;
    let stop = null, gone = false;
    import("../asset/pro/engine.js").then(({ mount }) => {
      if (gone || !host.current) return;
      stop = mount(host.current, view.chart);
      const root = host.current.querySelector(".ang-lwc");
      if (root) root.__trigger = (name, key) => { if (name === "pane" && key) setTop(key); };
    });
    return () => { gone = true; if (stop) stop(); };
  }, [view]);
  const asset = sum && view && sum.assets.find((a) => a.key === view.top);
  return (
    <section className="card vhist">
      <div className="bar">
        <h2 style={{ margin: 0 }}><Icon n="clock-arrow-up" /> {T("Visualize History")} <span className="m">· {sum ? sum.name : ""}</span></h2>
        <button type="button" className="ghost icon" onClick={onClose} aria-label={T("Close Visualize History")} title={T("Close Visualize History")}><Icon n="x" /></button>
      </div>
      {msg && <p className="note bad">{msg}</p>}
      {!sum && !msg && <p className="note"><Icon n="hourglass" size={15} /> {T("Working out the last year…")}</p>}
      {sum && (
        <>
          <div className="histbar">
            <label className="m">{T("On top")}
              <select value={view ? view.top : top} onChange={(e) => setTop(e.target.value)} title={T("The asset drawn large with candles. Tap any small chart to put it on top.")}>
                {sum.assets.map((a) => <option key={a.key} value={a.key}>{a.name}</option>)}
              </select>
            </label>
            <div className="chips" role="group" aria-label={T("Years")} title={T("How far back the chart opens; you can also zoom and drag along the time axis. ⏳ = still being worked out: 3Y opens when every asset has 3 years, then 10Y, then All.")}>
              {["1Y", "3Y", "10Y", "All"].map((o) => <button key={o} type="button" className={years === o ? "on" : ""} aria-pressed={years === o} onClick={() => setYears(o)}>{ready[o] ? o : <><Icon n="hourglass" size={13} /> {o}</>}</button>)}
            </div>
            <label className="ptog" title={T("Tint the No days too. Off keeps the chart clear, since most days are No.")}><input type="checkbox" checked={showNo} onChange={(e) => setShowNo(e.target.checked)} /> <span>{T("No as faint red")}</span></label>
          </div>
          {sum.pending > 0 && <p className="m"><Icon n="hourglass" size={14} /> {T("Older years are being filled in.")} ({sum.total - sum.pending}/{sum.total})</p>}
          {view && view.note && <p className="m">{view.note}</p>}
          {view && !view.chart && <p className="sub">{view.message}</p>}
          <div ref={host} className="histchart" />
          {view && view.caption && <p className="sub">{view.caption}</p>}
          {asset && <a className="ghost bordered" href={assetHref(`${asset.kind === "crypto" ? "Crypto" : "Stock"}|${asset.id}`, "chart")}
            title={T("Select this asset everywhere (tables, chart, analysis sections) with this Set's bands on.")}><Icon n="chart-candlestick" size={16} /> {T("Open on the main price chart")}</a>}
        </>
      )}
    </section>
  );
}
