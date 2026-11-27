import React, { useEffect, useMemo, useRef, useState } from "react";
import { createChart, CrosshairMode } from "lightweight-charts";
import { T } from "../../lib/i18n.js";
import { candles } from "../../lib/assets.js";
import { usd, pct, dayMonthYear, tone } from "../../lib/format.js";

const RANGES = [["1M", 22, 31], ["3M", 66, 92], ["6M", 130, 183], ["1Y", 252, 365], ["2Y", 504, 730]];

// Simple: the closing price as one clean line. Technical: candles with volume and the 50- and 200-candle averages, and
// for crypto the 1-hour, 4-hour and weekly candles from Binance.
export default function Chart({ row, meta, crypto }) {
  const [mode, setMode] = useState(() => { try { return localStorage.getItem("mn_chart_mode") || "simple"; } catch (e) { return "simple"; } });
  const pick = (m) => { setMode(m); try { localStorage.setItem("mn_chart_mode", m); } catch (e) { /* private window */ } };
  const bars = (row.prices || []).filter((b) => b && b.t && b.c != null);
  return (
    <section className="card">
      <div className="bar" style={{ marginBottom: 14 }}>
        <div className="seg" role="group" aria-label={T("Chart style")}>
          <button type="button" className={mode === "simple" ? "on" : ""} aria-pressed={mode === "simple"} onClick={() => pick("simple")}>{T("Simple")}</button>
          <button type="button" className={mode === "technical" ? "on" : ""} aria-pressed={mode === "technical"} onClick={() => pick("technical")}>{T("Technical")}</button>
        </div>
        <span className="m">{mode === "simple" ? T("The closing price each day.") : T("Candles with volume and two moving averages.")}</span>
      </div>
      {bars.length < 3 ? <div className="empty">{T("No price history yet.")}</div>
        : mode === "simple" ? <Simple bars={bars} /> : <Technical bars={bars} pair={crypto && meta ? meta.pair : null} />}
    </section>
  );
}

function Simple({ bars }) {
  const [range, setRange] = useState("3M");
  const [hover, setHover] = useState(null);
  const box = useRef(null);
  const days = RANGES.find((r) => r[0] === range)[2];
  const since = new Date(Date.now() - days * 864e5).toISOString().slice(0, 10);
  const pts = bars.filter((b) => b.t >= since);
  const data = pts.length > 2 ? pts : bars.slice(-30);
  const vals = data.map((b) => b.c);
  const min = Math.min(...vals), max = Math.max(...vals), pad = (max - min) * 0.08 || max * 0.01 || 1;
  const W = 1000, H = 320;
  const X = (i) => (i / (data.length - 1)) * W;
  const Y = (v) => H - ((v - (min - pad)) / (max - min + 2 * pad)) * H;
  const first = data[0].c, lastc = data[data.length - 1].c, chg = (lastc / first - 1) * 100;
  const up = chg >= 0;
  const line = data.map((b, i) => `${i ? "L" : "M"}${X(i).toFixed(1)} ${Y(b.c).toFixed(1)}`).join(" ");
  const area = `${line} L${W} ${H} L0 ${H} Z`;
  const hi = data.reduce((a, b) => (b.c > a.c ? b : a)), lo = data.reduce((a, b) => (b.c < a.c ? b : a));
  const all = bars.map((b) => b.c), sma50 = all.length >= 50 ? all.slice(-50).reduce((a, b) => a + b, 0) / 50 : null;
  const move = (e) => {
    const r = box.current.getBoundingClientRect();
    const i = Math.round(((e.clientX - r.left) / r.width) * (data.length - 1));
    setHover(Math.max(0, Math.min(data.length - 1, i)));
  };
  const h = hover != null ? data[hover] : null;
  return (
    <>
      <div className="bar" style={{ marginBottom: 6 }}>
        <div className="big-num">{usd(h ? h.c : lastc)} <span className={tone(chg)} style={{ fontSize: 15 }}>{h ? dayMonthYear(h.t) : `${pct(chg, 1)} · ${range}`}</span></div>
        <div className="chips right" role="group" aria-label={T("Period")}>
          {RANGES.map(([k]) => <button key={k} type="button" className={range === k ? "on" : ""} aria-pressed={range === k} onClick={() => setRange(k)}>{k}</button>)}
        </div>
      </div>
      <div className="chartbox" ref={box} onMouseMove={move} onMouseLeave={() => setHover(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={T("Price chart")} style={{ width: "100%", height: H, display: "block" }}>
          <defs><linearGradient id="sfill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor={up ? "var(--good)" : "var(--bad)"} stopOpacity="0.16" /><stop offset="1" stopColor={up ? "var(--good)" : "var(--bad)"} stopOpacity="0" />
          </linearGradient></defs>
          <path d={area} fill="url(#sfill)" />
          <path d={line} fill="none" stroke={up ? "var(--good)" : "var(--bad)"} strokeWidth="2.2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
          {h && <line x1={X(hover)} x2={X(hover)} y1="0" y2={H} stroke="var(--grey)" strokeDasharray="3 4" vectorEffect="non-scaling-stroke" />}
          {h && <circle cx={X(hover)} cy={Y(h.c)} r="5" fill={up ? "var(--good)" : "var(--bad)"} />}
        </svg>
      </div>
      <div className="axis"><span>{dayMonthYear(data[0].t)}</span><span>{dayMonthYear(data[data.length - 1].t)}</span></div>
      <div className="facts">
        <span>{T("High")} <b>{usd(hi.c)}</b> <span className="m">{dayMonthYear(hi.t)}</span></span>
        <span>{T("Low")} <b>{usd(lo.c)}</b> <span className="m">{dayMonthYear(lo.t)}</span></span>
        {sma50 && <span>{T("50-day average")} <b>{usd(sma50)}</b> <span className={tone(lastc - sma50)}>{T("price {p} from it", { p: pct((lastc / sma50 - 1) * 100, 0) })}</span></span>}
      </div>
    </>
  );
}

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || undefined;
const sma = (rows, n) => rows.map((r, i) => (i < n - 1 ? null : { time: r.time, value: rows.slice(i - n + 1, i + 1).reduce((a, b) => a + b.close, 0) / n })).filter(Boolean);
function weekly(rows) {
  const out = [];
  rows.forEach((r) => {
    const d = new Date(r.time * 1000); const monday = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - ((d.getUTCDay() + 6) % 7)));
    const t = Math.floor(monday.getTime() / 1000), w = out[out.length - 1];
    if (!w || w.time !== t) out.push({ ...r, time: t });
    else { w.high = Math.max(w.high, r.high); w.low = Math.min(w.low, r.low); w.close = r.close; w.volume += r.volume || 0; }
  });
  return out;
}

function Technical({ bars, pair }) {
  const frames = pair ? [["1h", T("1 hour")], ["4h", T("4 hours")], ["1d", T("Daily")], ["1w", T("Weekly")]] : [["1d", T("Daily")], ["1w", T("Weekly")]];
  const [tf, setTf] = useState("1d");
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const box = useRef(null);
  const daily = useMemo(() => bars.map((b) => ({ time: Math.floor(new Date(b.t + "T00:00:00Z").getTime() / 1000), open: b.o ?? b.c, high: b.h ?? b.c, low: b.l ?? b.c, close: b.c, volume: b.v || 0 })), [bars]);

  useEffect(() => {
    let live = true; setErr("");
    if (tf === "1d") { setRows(daily); return; }
    if (tf === "1w" && !pair) { setRows(weekly(daily)); return; }
    setRows(null);
    candles(pair, tf).then((r) => live && setRows(r)).catch(() => { if (live) { setErr(T("Binance's candles couldn't load just now; showing daily candles.")); setRows(daily); } });
    return () => { live = false; };
  }, [tf, pair, daily]);

  useEffect(() => {
    if (!rows || !box.current) return;
    const text = css("--ang-muted"), grid = css("--ang-border"), good = css("--good"), bad = css("--bad");
    const chart = createChart(box.current, { height: 420, layout: { background: { color: "transparent" }, textColor: text, fontFamily: "Inter, system-ui, sans-serif" },
      grid: { vertLines: { color: grid }, horzLines: { color: grid } }, rightPriceScale: { borderColor: grid }, timeScale: { borderColor: grid, timeVisible: tf === "1h" || tf === "4h" },
      crosshair: { mode: CrosshairMode.Normal }, autoSize: true });
    const c = chart.addCandlestickSeries({ upColor: good, downColor: bad, borderVisible: false, wickUpColor: good, wickDownColor: bad });
    c.setData(rows);
    const v = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol", color: grid });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    v.setData(rows.map((r) => ({ time: r.time, value: r.volume || 0, color: r.close >= r.open ? "rgba(0,127,115,.28)" : "rgba(194,51,63,.28)" })));
    const s50 = chart.addLineSeries({ color: css("--gold") || "#c69420", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    s50.setData(sma(rows, 50));
    const s200 = chart.addLineSeries({ color: css("--grey") || "#8a94a3", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    s200.setData(sma(rows, 200));
    const shown = tf === "1w" ? 104 : 160;
    if (rows.length > shown) chart.timeScale().setVisibleLogicalRange({ from: rows.length - shown, to: rows.length + 2 });
    return () => chart.remove();
  }, [rows]);

  return (
    <>
      <div className="bar" style={{ marginBottom: 8 }}>
        <div className="chips" role="group" aria-label={T("Candle size")}>
          {frames.map(([k, l]) => <button key={k} type="button" className={tf === k ? "on" : ""} aria-pressed={tf === k} onClick={() => setTf(k)}>{l}</button>)}
        </div>
        <span className="legend"><span><i style={{ background: "var(--gold)" }} />{T("Average of 50 candles")}</span><span><i style={{ background: "var(--grey)" }} />{T("Average of 200 candles")}</span></span>
      </div>
      {err && <p className="sub">{err}</p>}
      {!rows ? <div className="empty" style={{ height: 420 }}>{T("Loading…")}</div> : <div ref={box} style={{ height: 420 }} />}
    </>
  );
}
