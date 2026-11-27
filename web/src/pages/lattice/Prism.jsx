import React, { useCallback, useEffect, useRef, useState } from "react";
import { T, lang } from "../../lib/i18n.js";
import { call } from "../../lib/service.js";
import ClassicComponent from "../../components/ClassicComponent.jsx";
import Icon from "../../components/Icon.jsx";
import prismBoard, { css as prismCss } from "../../generated/prism_board.js";

// 🔎 Prism Scan: your saved scans on a board (the classic board, hosted), each a Set plus its assets, schedule and
// alerts. Every press goes to the data service (service/prism_page.py), which does what the classic page does; a
// ▶ Run now or ⏪ past-moment answer is kept here for the board while you stay in the app.
const kept = { results: {} };          // survives switching tabs, like the classic page's session

export default function Prism() {
  const [got, setGot] = useState(null);
  const [flash, setFlash] = useState(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const next = useRef({});

  const load = useCallback(async () => {
    try {
      const d = await call("/prism/board", { method: "POST", body: { results: kept.results, ...next.current, lang } });
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
