import React from "react";
import { T } from "../../lib/i18n.js";
import { money, pct, dayMonthYear } from "../../lib/format.js";

const KIND = () => ({ stop_loss: [T("Stop loss"), "var(--bad)"], take_profit: [T("Take profit"), "var(--good)"],
  trailing_stop: [T("Trailing stop"), "#4da89f"], by_hand: [T("By hand"), "var(--grey)"] });

export default function Risk({ d }) {
  const r = d.risk, x = d.exits, m = d.moves;
  const max = Math.max(1, ...r.hist.map((b) => b.count));
  const kinds = KIND();
  return (
    <div className="row">
      <section className="card" style={{ flex: "1 1 520px" }}>
        <h2>{T("Results in units of risk (R)")}</h2>
        <p className="sub">{T("1R = what you stood to lose at your stop loss. A good system keeps losses near −1R and lets a few winners run to +3R or more.")}</p>
        {r.with_stop < 20 ? (
          <div className="note plain">{T("Only {n} of {all} trades had a stop loss you set (the rest used eToro's far default), so there is too little to chart in R.", { n: r.with_stop, all: r.trades.toLocaleString() })}</div>
        ) : (
          <>
            <div className="hist">
              {r.hist.map((b) => (
                <div key={b.r} className="col" title={T("{n} trades", { n: b.count })}>
                  <span>{b.count}</span>
                  <div style={{ height: (b.count / max) * 150, background: b.r < 0 ? (b.r <= -2 ? "var(--bad)" : "rgba(194,51,63,.45)") : b.r === 0 ? "var(--ang-track)" : "var(--good)" }} />
                </div>
              ))}
            </div>
            <div className="hlabels">{r.hist.map((b) => <span key={b.r}>{(b.r > 0 ? "+" : b.r < 0 ? "−" : "") + Math.abs(b.r) + "R"}</span>)}</div>
          </>
        )}
        <div className="mini">
          <div><div className="ml">{T("Trades with a real stop")}</div><div className="mv">{pct(r.stop_share, 0, false)}</div><div className="ms">{T("the rest used eToro's far default")}</div></div>
          <div><div className="ml">{T("Typical risk per trade")}</div><div className="mv">{r.median_risk_usd == null ? "—" : money(r.median_risk_usd, false)}</div><div className="ms">{r.median_risk_pct == null ? "" : T("{p} of the trade's size", { p: pct(r.median_risk_pct, 0, false) })}</div></div>
          {r.worst && (
            <div className={r.worst.r < -1.5 ? "bad" : ""}><div className="ml">{T("Biggest loss in R")}</div><div className="mv">{(r.worst.r < 0 ? "−" : "") + Math.abs(r.worst.r).toFixed(1)}R</div><div className="ms">{r.worst.name} · {dayMonthYear(r.worst.closed)}</div></div>
          )}
        </div>
      </section>
      <section className="card" style={{ flex: "1 1 420px" }}>
        <h2>{T("How your trades ended")}</h2>
        <p className="sub">{T("Share of closed trades, and the average result of each kind.")}</p>
        {!x.kinds.length ? <div className="empty">{T("This shows after the next full sync (press Refresh).")}</div> : (
          <>
            <div className="stack">{x.kinds.map((k) => <div key={k.kind} title={kinds[k.kind][0]} style={{ width: k.share + "%", background: kinds[k.kind][1] }} />)}</div>
            <div className="klist">
              {x.kinds.map((k) => (
                <div key={k.kind}>
                  <i style={{ background: kinds[k.kind][1] }} />
                  <span>{kinds[k.kind][0]} <span style={{ color: "var(--ang-muted)" }}>({k.trades.toLocaleString()})</span></span>
                  <span style={{ color: "var(--ang-muted)" }}>{pct(k.share, k.share < 1 ? 1 : 0, false)}</span>
                  <span className={(k.avg_r ?? k.avg_usd) >= 0 ? "good" : "bad"} style={{ textAlign: "right", fontWeight: 600 }}>
                    {k.avg_r != null ? T("{r} average", { r: (k.avg_r >= 0 ? "+" : "−") + Math.abs(k.avg_r).toFixed(1) + "R" }) : T("{v} average", { v: money(k.avg_usd) })}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
        <h3>{T("Given back and left on the table")}</h3>
        <div className="mini" style={{ marginTop: 6 }}>
          <div><div className="ml">{T("You kept")}</div><div className="mv">{m.kept_median == null ? "—" : pct(m.kept_median, 0, false)}</div><div className="ms">{m.kept_median == null ? T("Worked out from daily prices after the next full sync.") : T("of the best price move, in a typical winning trade ({n} trades)", { n: m.kept_trades })}</div></div>
          <div><div className="ml">{T("20 trading days after you sold")}</div><div className="mv">{m.after20_winners == null ? "—" : pct(m.after20_winners, 1)}</div><div className="ms">{m.after20_winners == null ? "" : m.after20_winners > 2 ? T("average further move after winning trades: winners cut early") : T("average further move after winning trades")}</div></div>
        </div>
      </section>
    </div>
  );
}
