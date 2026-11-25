import React, { useEffect, useState } from "react";
import { T } from "../env.js";
import { trades } from "../api.js";
import { money, dayMonthYear } from "../format.js";

function state(readings) {
  if (!readings || !readings.regime) return null;
  const r = String(readings.regime), t = Number(readings.trend);
  if (r === "trending_up" || (r === "trending" && t > 0)) return "up";
  if (r === "trending_down" || (r === "trending" && t <= 0)) return "down";
  return "side";
}

export default function Trades({ whose, since }) {
  const [rows, setRows] = useState([]);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const load = (offset) => {
    setBusy(true);
    trades(whose, since, offset).then((got) => {
      setRows((r) => (offset ? r.concat(got) : got));
      setDone(got.length < 50);
    }).catch(() => setDone(true)).finally(() => setBusy(false));
  };
  useEffect(() => { load(0); }, [whose, since]);
  const end = { stop_loss: T("Stop loss"), take_profit: T("Take profit"), trailing_stop: T("Trailing stop"), by_hand: T("By hand") };
  const st = { up: T("Up-trend"), down: T("Down-trend"), side: T("Sideways") };
  return (
    <section className="card">
      <p className="sub" style={{ marginTop: 0 }}>{T("Your closed trades, newest first: the result in R (when you set a stop loss), how the trade ended, and how much of the best move a winning trade kept. Open the classic Trade Log for each trade's chart and notes.")}</p>
      <div className="scroll">
        <table className="t">
          <thead><tr>
            <th>{T("Closed")}</th><th>{T("Asset")}</th><th>{T("Direction")}</th><th className="r">{T("Result")}</th><th className="r">R</th>
            <th>{T("Ended by")}</th><th className="r">{T("Kept of best move")}</th><th>{T("Market at entry")}</th>
          </tr></thead>
          <tbody>
            {rows.map((r) => {
              const s = state(r.entry);
              return (
                <tr key={r.id}>
                  <td className="m">{dayMonthYear(r.closed_at)}</td>
                  <td className="b">{r.name || r.symbol}{r.copied ? <span className="m" style={{ fontWeight: 400 }}> · {T("Copied")}</span> : null}</td>
                  <td>{r.direction === "short" ? T("Sell") : T("Buy")}</td>
                  <td className={"r b " + (r.net_result_usd >= 0 ? "good" : "bad")}>{money(r.net_result_usd)}</td>
                  <td className={"r " + (r.risk_r == null ? "m" : r.risk_r >= 0 ? "good" : "bad")}>{r.risk_r == null ? "—" : (r.risk_r >= 0 ? "+" : "−") + Math.abs(r.risk_r).toFixed(1) + "R"}</td>
                  <td>{end[r.exit_kind] || "—"}</td>
                  <td className="r">{r.kept_pct == null ? "—" : Math.round(r.kept_pct) + "%"}</td>
                  <td>{s ? <span className={"pill " + s}>{st[s]}</span> : <span className="m">—</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!rows.length && !busy && <div className="empty">{T("No closed trades in this period.")}</div>}
      {!done && <button type="button" className="more" disabled={busy} onClick={() => load(rows.length)}>{busy ? T("Loading…") : T("Show 50 more")}</button>}
    </section>
  );
}
