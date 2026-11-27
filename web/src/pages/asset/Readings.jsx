import React from "react";
import { T } from "../../lib/i18n.js";
import { signed, tone, dayMonth } from "../../lib/format.js";
import { label, REGIME, HORIZON } from "./words.js";

const PART = () => ({ "Moving averages (50, 200 days)": T("Moving averages (50, 200 days)"), "MACD line": T("MACD line"), "Ichimoku cloud": T("Ichimoku cloud") });

// Trend, Stretch and Flow: where each stands, how it got there over the last months, and what is behind it.
export default function Readings({ f, hist }) {
  const sig = f.signals || {};
  const cl = sig.clusters || {};
  const r = sig.readings || {};
  const ctx = sig.context || {};
  if (sig.status !== "ok") return <div className="empty">{T("The readings for this asset are being worked out.")}</div>;
  const rows = [["trend", T("Trend")], ["stretch", T("Stretch")], ["flow", T("Flow")]];
  const reg = (ctx.regime || {}).label;
  const n = (v, d = 0) => (v == null ? "—" : Number(v).toFixed(d));
  const facts = [
    [T("Market state"), reg ? REGIME()[reg] || reg : "—"],
    [T("RSI (14)"), n(r.rsi), r.rsi_percentile != null ? T("lower than {p}% of the last year", { p: Math.round(100 - r.rsi_percentile) }) : ""],
    [T("ADX, trend strength"), n(r.adx), ({ Strong: T("Strong"), Weak: T("Weak"), Moderate: T("Moderate") })[(ctx.trend_strength || {}).label] || ""],
    [T("Price vs 50-day average"), r.vs_sma_50_pct == null ? "—" : signed(r.vs_sma_50_pct) + "%"],
    [T("Price vs 200-day average"), r.vs_sma_200_pct == null ? "—" : signed(r.vs_sma_200_pct) + "%"],
    [T("Volatility (ATR)"), r.atr_pct == null ? "—" : n(r.atr_pct, 1) + "%", r.atr_pct_percentile != null ? T("higher than {p}% of the last year", { p: Math.round(r.atr_pct_percentile) }) : ""],
    [T("Volume vs usual"), r.volume_ratio == null ? "—" : "×" + n(r.volume_ratio, 2)],
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
      <section className="card">
        <h2>{T("Where the readings stand")}</h2>
        <p className="sub">{T("From the last finished daily candle ({day}). Each runs from −100 to +100; the line shows the last four months.", { day: dayMonth(sig.as_of) })}</p>
        <div className="rgrid">
          {rows.map(([k, name]) => {
            const c = cl[k] || {};
            return (
              <div key={k} className="rcol">
                <div className="rhead"><span>{name}</span><span className="m">{HORIZON()[c.horizon] || c.horizon || ""}</span></div>
                <div className={"rbig " + tone(c.percent)}>{signed(c.percent)}</div>
                <div className="rlab">{label(c.label)}</div>
                <Spark hist={hist} k={k} />
              </div>
            );
          })}
        </div>
      </section>
      {f.trend_parts && (
        <section className="card">
          <h2>{T("What's behind the Trend")}</h2>
          <p className="sub">{T("Each part from −100 to +100; the Trend is their average.")}</p>
          <div className="parts">
            {Object.entries(f.trend_parts).map(([k, v]) => (
              <div key={k} className="part">
                <span>{PART()[k] || k}</span>
                <span className="ptrack"><span className="pzero" /><span className={"pfill " + tone(v)} style={{ left: v >= 0 ? "50%" : `${50 + v / 2}%`, width: `${Math.abs(v) / 2}%` }} /></span>
                <b className={tone(v)}>{signed(v)}</b>
              </div>
            ))}
          </div>
        </section>
      )}
      <section className="card">
        <h2>{T("The indicators")}</h2>
        <p className="sub">{T("The raw figures the readings are built from.")}</p>
        <div className="facts-table">
          {facts.map(([k, v, s]) => <div key={k}><span className="m">{k}</span><b>{v}</b><span className="m">{s || ""}</span></div>)}
        </div>
      </section>
    </div>
  );
}

function Spark({ hist, k }) {
  const pts = (hist || []).filter((h) => h[k] != null);
  if (pts.length < 3) return <div className="m" style={{ fontSize: 12.5, height: 64 }}>{T("History builds up day by day.")}</div>;
  const W = 300, H = 64, Y = (v) => H / 2 - (v / 100) * (H / 2 - 3);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${((i / (pts.length - 1)) * W).toFixed(1)} ${Y(p[k]).toFixed(1)}`).join(" ");
  const last = pts[pts.length - 1][k];
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: H, display: "block" }} aria-hidden="true">
        <line x1="0" x2={W} y1={H / 2} y2={H / 2} stroke="var(--ang-border)" />
        <path d={d} fill="none" stroke={last >= 0 ? "var(--good)" : "var(--bad)"} strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="axis"><span>{dayMonth(pts[0].day)}</span><span>{dayMonth(pts[pts.length - 1].day)}</span></div>
    </div>
  );
}
