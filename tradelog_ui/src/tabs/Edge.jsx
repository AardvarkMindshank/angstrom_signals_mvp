import React from "react";
import { T } from "../env.js";
import { money, pct } from "../format.js";

export const DIM = () => ({ asset_class: T("Asset class"), direction: T("Direction"), leverage: T("Leverage"), held: T("Held for"),
  regime: T("Market at entry"), day: T("Day opened") });
export const LABEL = () => ({ crypto: T("Crypto"), stocks: T("Equities"), etfs: T("ETFs"), indices: T("Indices"), commodities: T("Commodities"),
  currencies: T("Currencies"), other: T("Other"), long: T("Long"), short: T("Short"), none: T("None"), x2: T("2x"),
  above_2: T("Above 2x"), under_day: T("Under a day"), week: T("1 to 7 days"), month: T("1 to 4 weeks"), longer: T("Longer"),
  up: T("Up-trend"), side: T("Sideways"), down: T("Down-trend"), mon_thu: T("Mon to Thu"), fri: T("Friday"), weekend: T("Weekend") });

function boxStyle(v, top) {
  const s = Math.min(Math.abs(v) / (top || 1), 1);
  const strong = s > 0.6;
  return { background: v >= 0 ? `rgba(0,127,115,${(0.08 + s * 0.55).toFixed(2)})` : `rgba(194,51,63,${(0.08 + s * 0.55).toFixed(2)})`,
    color: strong ? "#fff" : v >= 0 ? "var(--good-ink)" : "var(--bad-ink)" };
}

export default function Edge({ d }) {
  const e = d.edge;
  const dims = DIM(), labels = LABEL();
  const top = Math.max(1, ...e.rows.flatMap((r) => r.cells.map((c) => Math.abs(c.net))));
  const best = d.assets.best, worst = d.assets.worst;
  const amax = Math.max(1, ...best.map((x) => Math.abs(x.net)), ...worst.map((x) => Math.abs(x.net)));
  const bars = [...best, ...worst];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <section className="card">
        <h2>{T("Where you make and lose money")}</h2>
        <p className="sub">{T("Each box: net result, win rate and number of closed trades. Strong green and red boxes are your edge and your leak.")}</p>
        {!e.rows.length && <div className="empty">{T("No closed trades in this period.")}</div>}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {e.rows.map((r) => (
            <div key={r.dim} className="edge-row">
              <div className="dim">{dims[r.dim]}</div>
              {r.cells.map((c) => (
                <div key={c.label} className="box" style={boxStyle(c.net, top)}>
                  <div className="bl">{labels[c.label] || c.label}</div>
                  <div className="bn">{money(c.net)}</div>
                  <div className="bm">{T("{w} wins · {n} trades", { w: pct(c.win_rate, 0, false), n: c.trades.toLocaleString() })}</div>
                </div>
              ))}
            </div>
          ))}
        </div>
        {(e.edge || e.leak) && (
          <div className="notes" style={{ marginTop: 16 }}>
            {e.edge && <div className="note good"><b>{T("Edge")}:</b> {T("{label} ({dim}) made {net} over {n} trades.", { dim: dims[e.edge.dim].toLowerCase(), label: labels[e.edge.label] || e.edge.label, net: money(e.edge.net), n: e.edge.trades.toLocaleString() })}</div>}
            {e.leak && <div className="note bad"><b>{T("Leak")}:</b> {T("{label} ({dim}) lost {net} over {n} trades.", { dim: dims[e.leak.dim].toLowerCase(), label: labels[e.leak.label] || e.leak.label, net: money(e.leak.net), n: e.leak.trades.toLocaleString() })}</div>}
          </div>
        )}
      </section>
      <section className="card">
        <h2>{T("Best and worst assets")}</h2>
        <p className="sub">{T("Net result of closed trades per asset in this period, with the number of trades.")}</p>
        <div className="abars">
          {bars.map((x) => {
            const w = (Math.abs(x.net) / amax) * 100 + "%";
            return (
              <div key={x.name + x.net} className="abar" title={T("{n} trades", { n: x.trades })}>
                <span className="n">{x.name} <span style={{ fontWeight: 400, color: "var(--ang-muted)" }}>({x.trades})</span></span>
                <div className="neg"><div style={{ width: x.net < 0 ? w : 0 }} /></div>
                <div className="pos"><div style={{ width: x.net > 0 ? w : 0 }} /></div>
                <span className={"val " + (x.net >= 0 ? "good" : "bad")}>{money(x.net)}</span>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
