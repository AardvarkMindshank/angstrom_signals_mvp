import React, { useEffect, useState } from "react";
import { T } from "../../lib/i18n.js";
import { alerts, trades } from "../../lib/assets.js";
import { alertText } from "./words.js";
import { money, pct, tone, dayMonthYear, stamp } from "../../lib/format.js";

// What the member has to do with this asset: trades and alerts.
export default function Activity({ assetKey, who }) {
  const [al, setAl] = useState(null), [tr, setTr] = useState(null);
  useEffect(() => {
    let live = true;
    alerts(who.id).then((x) => live && setAl(x));
    trades(assetKey).then((x) => live && setTr((x || []).filter((t) => !t.reward)));
    return () => { live = false; };
  }, [assetKey]);
  const own = (tr || []).filter((t) => !t.copied);
  const net = own.reduce((a, t) => a + (t.net_result_usd || 0), 0);
  const wins = own.filter((t) => (t.net_result_usd || 0) > 0).length;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
      <section className="card">
        <h2>{T("Your trades")}</h2>
        {tr === null ? <p className="sub">{T("Loading…")}</p> : !tr.length ? <p className="sub">{T("No closed trades in this asset in your Trade Log.")} <a className="linkish" href="#tradelog">{T("Open the Trade Log")} ›</a></p> : (
          <>
            <div className="facts" style={{ margin: "10px 0 14px" }}>
              <span>{T("Your own trades")} <b>{own.length}</b> <span className="m">{T("{w} wins, {l} losses", { w: wins, l: own.length - wins })}</span></span>
              <span>{T("Result")} <b className={tone(net)}>{money(net)}</b></span>
              {tr.length > own.length && <span>{T("Copied")} <b>{tr.length - own.length}</b></span>}
            </div>
            <div className="scroll"><table className="t" style={{ minWidth: 520 }}>
              <thead><tr><th>{T("Closed")}</th><th>{T("Direction")}</th><th className="r">{T("Result")}</th><th className="r">%</th><th /></tr></thead>
              <tbody>{tr.slice(0, 12).map((t) => (
                <tr key={t.id}><td className="m">{dayMonthYear(t.closed_at)}</td><td>{t.direction === "short" ? T("Sell") : T("Buy")}</td>
                  <td className={"r b " + tone(t.net_result_usd)}>{money(t.net_result_usd)}</td><td className={"r " + tone(t.result_pct)}>{pct(t.result_pct, 1)}</td>
                  <td className="m">{t.copied ? T("Copied") : ""}</td></tr>
              ))}</tbody>
            </table></div>
            <p className="sub"><a className="linkish" href="#tradelog">{T("Open the Trade Log")} ›</a></p>
          </>
        )}
      </section>
      <section className="card">
        <h2>{T("Your alerts")}</h2>
        {al === null ? <p className="sub">{T("Loading…")}</p> : !al.length ? <p className="sub">{T("No alerts for this asset yet.")}</p> : (
          <ol className="events">
            {al.map((a) => <li key={a.id}><span className={"tier " + (/DOWN/.test(a.alert_type) ? "bad" : "good")} aria-hidden="true" /><b>{alertText(a.message)}</b><span className="when">{stamp(a.created_at)}</span></li>)}
          </ol>
        )}
      </section>
    </div>
  );
}
