import React from "react";
import { T } from "../../lib/i18n.js";
import { money, pct, monthYear } from "../../lib/format.js";
import { LABEL } from "./Edge.jsx";

function text(h) {
  const L = LABEL();
  switch (h.key) {
    case "after_loss":
      return [T("After a loss"), h.avg_after < h.avg_other ? T("Trades opened soon after a loss do worse") : T("Trades opened soon after a loss do no worse"),
        T("{n} trades opened within 6 hours of a losing trade closing: {total} in total, {a} each against {b} for your other trades.", { n: h.trades, total: money(h.total), a: money(h.avg_after), b: money(h.avg_other) })];
    case "hold_losers":
      return [T("Holding losers"), T("Losers are held {x} times longer than winners", { x: h.ratio }),
        T("An average of {l} days for a losing trade against {w} days for a winner.", { l: Math.round(h.loss_days), w: Math.round(h.win_days) })];
    case "cut_losers":
      return [T("Cutting losers"), T("Losers are closed {x} times sooner than winners", { x: h.ratio }),
        T("An average of {l} days for a losing trade against {w} days for a winner.", { l: Math.round(h.loss_days), w: Math.round(h.win_days) })];
    case "busy_days":
      return [T("Busy days"), h.total < 0 ? T("Days with 10 or more trades lost money") : T("Days with 10 or more trades made money"),
        T("{n} busy days: {total} in total. Quiet days (1 to 3 trades): {q}.", { n: h.days, total: money(h.total), q: money(h.quiet_total) })];
    case "streak_size":
      return [T("After a winning streak"), T("Sizes change by {p} after 3 wins in a row", { p: pct(h.grow_pct) }),
        T("The next trade after a streak won {a} of the time, against your usual {b} ({n} trades).", { a: pct(h.win_rate, 0, false), b: pct(h.usual_win_rate, 0, false), n: h.trades })];
    case "size_after_loss":
      return [T("Size after a loss"), h.times >= 1 ? T("Trades after a loss are {x} times the size", { x: h.times }) : T("Trades after a loss are smaller"),
        T("After a loss, your next trade was on average {x} times the size of one after a win ({n} trades).", { x: h.times, n: h.trades })];
    case "leverage":
      return [T("Leverage"), T("Trades with leverage above 2x lost money"),
        T("{n} trades, {total} in total. Everything else together: {rest}.", { n: h.trades, total: money(h.total), rest: money(h.rest_total) })];
    case "loss_concentration":
      return [T("One asset"), T("{name} made up {p} of all your losses", { name: h.name, p: pct(h.share, 0, false) }),
        T("{total} lost on {name} alone.", { total: money(h.total), name: h.name })];
    case "best_hold":
      return [T("Patience"), T("Trades held {band} are your best", { band: (L[h.band] || h.band).toLowerCase() }),
        T("{w} win rate and {total}, from {n} trades.", { w: pct(h.win_rate, 0, false), total: money(h.total), n: h.trades })];
    default:
      return null;
  }
}

const PALETTE = ["var(--acc)", "var(--gold)", "var(--good)", "#7a8ca8"];

export default function Behaviour({ d }) {
  const habits = d.habits.map((h) => [h, text(h)]).filter((x) => x[1]);
  const al = d.allocation;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <p className="sub" style={{ margin: 0, fontSize: 13, color: "var(--ang-muted)" }}>{T("Checks on your own trades only: copied trades were someone else's decisions.")}</p>
      {habits.length ? (
        <section className="habits">
          {habits.map(([h, [tag, head, body]]) => (
            <div key={h.key} className={"habit " + h.kind}>
              <div className="ht">{tag}</div>
              <div className="hh">{head}</div>
              <div className="hx">{body}</div>
            </div>
          ))}
        </section>
      ) : <div className="empty">{T("Not enough of your own trades in this period for these checks (20 or more needed).")}</div>}
      {al && (
        <section className="card">
          <h2>{T("What your account held")}</h2>
          <p className="sub">{T("Share of the account by asset at the end of each month, from eToro's allocation history (it keeps about three years). Grey is everything else; the lightest is cash.")}</p>
          <div className="alloc">
            {al.months.map((m) => (
              <div key={m.month} title={`${monthYear(m.month + "-01")}: ` + m.parts.map((p) => `${p.name} ${pct(p.pct, 0, false)}`).join(", ") + `, ${T("cash")} ${pct(m.cash, 0, false)}`}>
                <div style={{ height: m.cash + "%", background: "var(--ang-track)" }} />
                <div style={{ height: m.other + "%", background: "#c9cfd8" }} />
                {[...m.parts].reverse().map((p, i) => <div key={p.name} style={{ height: p.pct + "%", background: PALETTE[m.parts.length - 1 - i] }} />)}
              </div>
            ))}
          </div>
          <div className="axis"><span>{monthYear(al.months[0].month + "-01")}</span><span>{monthYear(al.months[al.months.length - 1].month + "-01")}</span></div>
          <div className="keys">
            {al.names.map((n, i) => <span key={n}><i style={{ background: PALETTE[i] }} />{n}</span>)}
            <span><i style={{ background: "#c9cfd8" }} />{T("Other assets")}</span>
            <span><i style={{ background: "var(--ang-track)", border: "1px solid var(--ang-border)" }} />{T("Cash")}</span>
          </div>
        </section>
      )}
    </div>
  );
}
