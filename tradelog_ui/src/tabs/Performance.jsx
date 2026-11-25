import React, { useMemo, useState } from "react";
import { T } from "../env.js";
import { money, pct, tone, monthYear, dayMonthYear, monthNames } from "../format.js";

const W = 1000, H = 300, DH = 90;

function GrowthChart({ a }) {
  const [hover, setHover] = useState(null);
  const pts = a.curve;
  const vals = pts.flatMap((p) => [p.acc, p.btc, p.spx]).filter((v) => v != null && v > 0);
  const lo = Math.log(Math.min(...vals) * 0.9), hi = Math.log(Math.max(...vals) * 1.1);
  const X = (i) => (i / Math.max(pts.length - 1, 1)) * W;
  const Y = (v) => H - ((Math.log(v) - lo) / (hi - lo)) * H;
  const path = (key) => pts.map((p, i) => (p[key] > 0 ? `${i && pts[i - 1][key] > 0 ? "L" : "M"}${X(i).toFixed(1)} ${Y(p[key]).toFixed(1)}` : "")).join(" ");
  const ticks = [6400, 3200, 1600, 800, 400, 200, 100, 50, 25, 12].filter((t) => Math.log(t) <= hi && Math.log(t) >= lo);
  const deepest = Math.min(...a.drawdown.map((x) => x.dd), -1);
  const dd = "M0 0 " + a.drawdown.map((x, i) => `L${X(i).toFixed(1)} ${((x.dd / deepest) * (DH - 2)).toFixed(1)}`).join(" ") + ` L${W} 0 Z`;
  const years = [];
  pts.forEach((p, i) => { const y = p.d.slice(0, 4); if (!years.length || years[years.length - 1].y !== y) years.push({ y, i }); });
  const step = Math.ceil(years.length / 9);
  const onMove = (e) => {
    const box = e.currentTarget.getBoundingClientRect();
    const i = Math.max(0, Math.min(pts.length - 1, Math.round(((e.clientX - box.left) / box.width) * (pts.length - 1))));
    setHover({ i, x: e.clientX - box.left, w: box.width });
  };
  const h = hover && pts[hover.i];
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <div className="yaxis" style={{ position: "relative" }}>
        {ticks.map((t) => <span key={t} style={{ position: "absolute", right: 0, top: Y(t) - 8 }}>${t.toLocaleString()}</span>)}
      </div>
      <div style={{ flex: 1, minWidth: 0 }} className="chartbox">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={T("Growth of $100: your account against Bitcoin and the S&P 500")}
          style={{ width: "100%", height: H, display: "block", cursor: "crosshair" }} onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          {ticks.map((t) => <line key={t} x1="0" x2={W} y1={Y(t)} y2={Y(t)} stroke="var(--ang-border)" strokeWidth="1" vectorEffect="non-scaling-stroke" />)}
          <line x1="0" x2={W} y1={Y(100)} y2={Y(100)} stroke="var(--grey)" strokeDasharray="4 4" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          <path d={path("spx")} fill="none" stroke="var(--grey)" strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
          <path d={path("btc")} fill="none" stroke="var(--gold)" strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
          <path d={path("acc")} fill="none" stroke="var(--acc)" strokeWidth="2.6" vectorEffect="non-scaling-stroke" />
          {h && <line x1={X(hover.i)} x2={X(hover.i)} y1="0" y2={H} stroke="var(--grey)" strokeWidth="1" vectorEffect="non-scaling-stroke" />}
        </svg>
        {h && (
          <div className="tip" style={{ left: Math.min(hover.x + 12, hover.w - 190), top: 8 }}>
            <div style={{ fontWeight: 600 }}>{dayMonthYear(h.d)}</div>
            <div>{T("Your account")}: ${h.acc?.toFixed(0)}</div>
            {h.btc != null && <div style={{ color: "var(--gold)" }}>{T("Bitcoin")}: ${h.btc.toFixed(0)}</div>}
            {h.spx != null && <div style={{ color: "var(--grey)" }}>{T("S&P 500")}: ${h.spx.toFixed(0)}</div>}
            <div className="bad">{T("Below the last high")}: {pct(a.drawdown[hover.i]?.dd)}</div>
          </div>
        )}
        <div style={{ fontSize: 11.5, color: "var(--ang-muted)", margin: "6px 0 2px" }}>{T("Below the last high (drawdown)")}</div>
        <svg viewBox={`0 0 ${W} ${DH}`} preserveAspectRatio="none" role="img" aria-label={T("Drawdown below the last high")}
          style={{ width: "100%", height: DH, display: "block", borderTop: "1px solid var(--ang-border)" }}>
          <path d={dd} fill="var(--bad)" fillOpacity="0.22" stroke="var(--bad)" strokeWidth="1.2" vectorEffect="non-scaling-stroke" />
        </svg>
        <div className="axis">{years.filter((_, k) => k % step === 0).map((y) => <span key={y.y}>{y.y}</span>)}</div>
      </div>
    </div>
  );
}

function MonthGrid({ a }) {
  const years = Object.keys(a.years);
  return (
    <div className="scroll">
      <div className="grid-months">
        <span />
        {monthNames.map((m) => <span key={m} className="h">{m}</span>)}
        <span className="h" style={{ textAlign: "right" }}>{T("Year")}</span>
        {years.map((y) => (
          <React.Fragment key={y}>
            <span className="y">{y}</span>
            {monthNames.map((m, i) => {
              const v = a.months[`${y}-${String(i + 1).padStart(2, "0")}`];
              if (v == null) return <span key={i} className="c" style={{ background: "var(--ang-hover)" }} />;
              const s = Math.min(Math.abs(v) / 25, 1);
              const bg = v >= 0 ? `rgba(0,127,115,${(0.12 + s * 0.75).toFixed(2)})` : `rgba(194,51,63,${(0.12 + s * 0.75).toFixed(2)})`;
              return <span key={i} className="c" title={`${m} ${y}: ${pct(v, 1)}`} style={{ background: bg, color: s > 0.55 ? "#fff" : "var(--ang-text)" }}>{Math.round(v)}</span>;
            })}
            <span className={"t " + tone(a.years[y])}>{pct(a.years[y])}</span>
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

function Compare({ c }) {
  const rows = [
    [T("Trades"), c.own.trades.toLocaleString(), c.copied.trades.toLocaleString()],
    [T("Win rate"), pct(c.own.win_rate, 0, false), pct(c.copied.win_rate, 0, false)],
    [T("Net result"), money(c.own.net), money(c.copied.net), true],
    [T("Average trade"), money(c.own.average), money(c.copied.average)],
    [T("Profit factor"), c.own.profit_factor?.toFixed(2) ?? "—", c.copied.profit_factor?.toFixed(2) ?? "—"],
  ];
  return (
    <div className="pairs">
      <span /><span className="hd">{T("Yours")}</span><span className="hd">{T("Copied")}</span>
      {rows.map(([l, a, b, col]) => (
        <React.Fragment key={l}>
          <span style={{ color: "var(--ang-soft)" }}>{l}</span>
          <span className={col ? "b " + tone(c.own.net) : ""} style={col ? { fontWeight: 600 } : null}>{a}</span>
          <span className={col ? tone(c.copied.net) : ""} style={col ? { fontWeight: 600 } : null}>{b}</span>
        </React.Fragment>
      ))}
    </div>
  );
}

export default function Performance({ d, whose }) {
  const a = d.account;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {a ? (
        <section className="card">
          <div className="bar">
            <h2>{T("Your account {a} since {when}: Bitcoin {b}, S&P 500 {s}", { a: pct(a.total_pct), when: monthYear(a.from), b: a.bench.btc ? pct(a.bench.btc.total) : "—", s: a.bench.spx ? pct(a.bench.spx.total) : "—" })}</h2>
            <div className="legend">
              <span><i style={{ background: "var(--acc)" }} />{T("Your account")}</span>
              <span><i style={{ background: "var(--gold)", height: 2 }} />{T("Bitcoin")}</span>
              <span><i style={{ background: "var(--grey)", height: 2 }} />{T("S&P 500")}</span>
            </div>
          </div>
          <p className="sub">{T("Growth of $100 from eToro's daily return, so money paid in or taken out doesn't move it. Log scale: equal steps are equal % changes. Your whole account, whichever trades are chosen above.")}</p>
          <GrowthChart a={a} />
          <div className="notes">
            <div className="note bad">{T("Deepest fall {p}: {a} to {b}", { p: pct(a.deepest.pct), a: monthYear(a.deepest.from), b: monthYear(a.deepest.to) })}</div>
            <div className="note bad">{T("Longest time below a high: {n} months", { n: Math.round(a.longest_under_days / 30.4) })}</div>
            <div className={"note " + (a.now_below_high_pct < -1 ? "bad" : "good")}>{T("Now {p} below the last high", { p: pct(a.now_below_high_pct) })}</div>
          </div>
        </section>
      ) : (
        <section className="card"><div className="empty">{T("eToro's daily return for the account isn't available yet: it arrives with the next full sync (press Refresh).")}</div></section>
      )}
      <div className="row">
        {a && (
          <section className="card wide">
            <h2>{T("Monthly returns")}</h2>
            <p className="sub">{T("Green months gained, red months lost; the darker, the bigger. Year total on the right.")}</p>
            <MonthGrid a={a} />
          </section>
        )}
        <section className="card narrow">
          <h2>{T("Your trades and copy trading")}</h2>
          <p className="sub">{T("Closed trades in this period, side by side.")}</p>
          <Compare c={d.compare} />
        </section>
      </div>
    </div>
  );
}
