import React from "react";
import { T } from "../../lib/i18n.js";
import { money, pct, tone, dayMonthYear } from "../../lib/format.js";

export default function OpenNow({ d }) {
  const o = d.open;
  if (!o) return <section className="card"><div className="empty">{T("Open positions show after the next sync (press Refresh).")}</div></section>;
  const now = { up: T("Up-trend"), down: T("Down-trend"), side: T("Sideways") };
  return (
    <section className="card">
      <div className="tiles" style={{ marginBottom: 16 }}>
        <div><div className="ml" style={{ fontSize: 12, color: "var(--ang-muted)" }}>{T("Account value")}</div><div style={{ fontSize: 24, fontWeight: 600 }}>{money(o.account, false)}</div><div style={{ fontSize: 12, color: "var(--ang-muted)" }}>{T("Open trades plus spare cash.")}</div></div>
        <div><div style={{ fontSize: 12, color: "var(--ang-muted)" }}>{T("In open trades")}</div><div style={{ fontSize: 24, fontWeight: 600 }}>{money(o.invested, false)}</div><div style={{ fontSize: 12, color: "var(--ang-muted)" }}>{T("{n} positions in {a} assets", { n: o.positions, a: o.assets })}</div></div>
        <div><div style={{ fontSize: 12, color: "var(--ang-muted)" }}>{T("Open profit or loss")}</div><div className={tone(o.pnl)} style={{ fontSize: 24, fontWeight: 600 }}>{money(o.pnl)}</div><div style={{ fontSize: 12, color: "var(--ang-muted)" }}>{pct(o.pnl_pct, 1)}</div></div>
        <div><div style={{ fontSize: 12, color: "var(--ang-muted)" }}>{T("Spare cash")}</div><div style={{ fontSize: 24, fontWeight: 600 }}>{money(o.cash, false)}</div></div>
        {o.largest && <div><div style={{ fontSize: 12, color: "var(--ang-muted)" }}>{T("Largest holding")}</div><div style={{ fontSize: 24, fontWeight: 600 }}>{pct(o.largest.pct, 0, false)}</div><div style={{ fontSize: 12, color: "var(--ang-muted)" }}>{o.largest.name}</div></div>}
      </div>
      <div className="scroll">
        <table className="t">
          <thead><tr>
            <th>{T("Asset")}</th><th>{T("Positions")}</th><th className="r">{T("Invested")}</th><th className="r">{T("Value")}</th>
            <th className="r">{T("Profit or loss")}</th><th className="r">{T("To stop loss")}</th><th className="r">{T("Overnight fees")}</th><th>{T("Now")}</th>
          </tr></thead>
          <tbody>
            {o.rows.map((r) => (
              <tr key={r.name}>
                <td className="b">{r.name}</td>
                <td className="m">{r.positions}</td>
                <td className="r">{money(r.invested, false)}</td>
                <td className="r">{money(r.value, false)}</td>
                <td className={"r b " + tone(r.pnl)}>{money(r.pnl)}</td>
                <td className="r m">{r.stop_pct != null ? pct(r.stop_pct, 0) : r.stops_set ? T("{n} of {all} set", { n: r.stops_set, all: r.positions }) : T("none set")}</td>
                <td className="r m">{r.fees ? money(r.fees, false) : "—"}</td>
                <td>{r.now ? <span className={"pill " + r.now}>{now[r.now]}</span> : <span className="m">—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="sub" style={{ margin: "10px 0 0" }}>{T("The Now column is MarketNavi's reading for the asset today (trend and regime), for the assets MarketNavi follows. As at the last sync, {when}.", { when: dayMonthYear(o.as_at) })}</p>
    </section>
  );
}
