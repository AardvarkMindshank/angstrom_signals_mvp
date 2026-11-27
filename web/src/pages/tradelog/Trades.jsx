import React, { useEffect, useState } from "react";
import { T } from "../../lib/i18n.js";
import { trades } from "../../lib/api.js";
import { money, pct, dayMonthYear } from "../../lib/format.js";
import { LABEL } from "./Edge.jsx";
import TradeCard from "./TradeCard.jsx";

const CLASSES = ["crypto", "stocks", "etfs", "commodities", "currencies", "indices"];

export function marketState(readings) {
  if (!readings || !readings.regime) return null;
  const r = String(readings.regime), t = Number(readings.trend);
  if (r === "trending_up" || (r === "trending" && t > 0)) return "up";
  if (r === "trending_down" || (r === "trending" && t <= 0)) return "down";
  return "side";
}

export default function Trades({ scope, whose, since, hideRewards }) {
  const [cls, setCls] = useState(null);
  const [rows, setRows] = useState([]);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(null);
  const load = (offset) => {
    setBusy(true);
    trades({ scope, whose, since, cls, offset, hideRewards }).then((got) => {
      setRows((r) => (offset ? r.concat(got) : got));
      setDone(got.length < 50);
    }).catch(() => setDone(true)).finally(() => setBusy(false));
  };
  useEffect(() => { setOpen(null); load(0); }, [scope, whose, since, cls, hideRewards]);
  const L = LABEL();
  const end = { stop_loss: T("Stop loss"), take_profit: T("Take profit"), trailing_stop: T("Trailing stop"), by_hand: T("By hand") };
  const st = { up: T("Up-trend"), down: T("Down-trend"), side: T("Sideways") };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <section className="card">
        <div className="bar" style={{ marginBottom: 10 }}>
          <p className="sub" style={{ margin: 0, flex: "1 1 320px" }}>{T("Your closed trades, newest first. Pick a trade to see its chart, what MarketNavi read at entry and exit, and your note.")}</p>
          <div className="chips" role="group" aria-label={T("Asset class")}>
            <button type="button" className={cls === null ? "on" : ""} onClick={() => setCls(null)}>{T("All")}</button>
            {CLASSES.map((c) => <button key={c} type="button" className={cls === c ? "on" : ""} onClick={() => setCls(c)}>{L[c]}</button>)}
          </div>
        </div>
        <div className="scroll">
          <table className="t pick">
            <thead><tr>
              <th>{T("Closed")}</th><th>{T("Asset")}</th>{cls === null && <th>{T("Class")}</th>}<th>{T("Direction")}</th><th className="r">{T("Held (days)")}</th><th className="r">{T("Result")}</th><th className="r">%</th><th className="r">R</th>
              <th>{T("Ended by")}</th><th className="r">{T("Kept of best move")}</th><th>{T("Market at entry")}</th>
            </tr></thead>
            <tbody>
              {rows.map((r) => {
                const s = marketState(r.entry);
                const held = (new Date(r.closed_at) - new Date(r.opened_at)) / 864e5;
                return (
                  <React.Fragment key={r.id}>
                  <tr className={open === r.id ? "sel" : ""} tabIndex={0} onClick={() => setOpen(open === r.id ? null : r.id)}
                    onKeyDown={(e) => { if (e.key === "Enter") setOpen(open === r.id ? null : r.id); }}>
                    <td className="m">{dayMonthYear(r.closed_at)}</td>
                    <td className="b">{r.name || r.symbol}{r.copied ? <span className="m" style={{ fontWeight: 400 }}> · {T("Copied")}</span> : null}</td>
                    {cls === null && <td className="m">{L[r.asset_class] || "—"}</td>}
                    <td>{r.direction === "short" ? T("Sell") : T("Buy")}</td>
                    <td className="r m">{held < 10 ? held.toFixed(1) : Math.round(held)}</td>
                    <td className={"r b " + (r.net_result_usd >= 0 ? "good" : "bad")}>{money(r.net_result_usd)}</td>
                    <td className={"r " + (r.result_pct >= 0 ? "good" : "bad")}>{pct(r.result_pct, 1)}</td>
                    <td className={"r " + (r.risk_r == null ? "m" : r.risk_r >= 0 ? "good" : "bad")}>{r.risk_r == null ? "—" : (r.risk_r >= 0 ? "+" : "−") + Math.abs(r.risk_r).toFixed(1) + "R"}</td>
                    <td>{end[r.exit_kind] || "—"}</td>
                    <td className="r">{r.kept_pct == null ? "—" : Math.round(r.kept_pct) + "%"}</td>
                    <td>{s ? <span className={"pill " + s}>{st[s]}</span> : <span className="m">—</span>}</td>
                  </tr>
                  {open === r.id && <tr className="detail"><td colSpan={cls === null ? 11 : 10}><TradeCard trip={r} onClose={() => setOpen(null)} /></td></tr>}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
        {!rows.length && !busy && <div className="empty">{T("No closed trades in this period.")}</div>}
        {!done && <button type="button" className="more" disabled={busy} onClick={() => load(rows.length)}>{busy ? T("Loading…") : T("Show 50 more")}</button>}
      </section>
    </div>
  );
}
