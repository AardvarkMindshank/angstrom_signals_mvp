import React, { useEffect, useMemo, useRef, useState } from "react";
import { createChart, CrosshairMode } from "lightweight-charts";
import { T } from "../../lib/i18n.js";
import { candles, drawings } from "../../lib/assets.js";
import { usd, pct, dayMonthYear, tone } from "../../lib/format.js";

const RANGES = [["1M", 22, 31], ["3M", 66, 92], ["6M", 130, 183], ["1Y", 252, 365], ["2Y", 504, 730]];

// Simple: the closing price as one clean line. Technical: candles with volume and the 50- and 200-candle averages, and
// for crypto the 1-hour, 4-hour and weekly candles from Binance.
export default function Chart({ row, meta, crypto, who }) {
  const [drawn, setDrawn] = useState(null);
  useEffect(() => { let live = true; if (who) drawings(who.kind, who.id).then((d) => live && setDrawn(d)); return () => { live = false; }; }, [who && who.id]);
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
        <span className="m">{mode === "simple" ? T("The closing price each day.") : T("Candles with volume; add indicators on the right.")}</span>
      </div>
      {bars.length < 3 ? <div className="empty">{T("No price history yet.")}</div>
        : mode === "simple" ? <Simple bars={bars} /> : <Technical bars={bars} pair={crypto && meta ? meta.pair : null} drawn={drawn} />}
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

// Indicators worked out in the browser from the candles shown (the classic definitions: RSI 14, MACD 12/26/9,
// Bollinger 20 with 2 standard deviations).
function rsi(rows, n = 14) {
  const out = []; let g = 0, l = 0;
  for (let i = 1; i < rows.length; i++) {
    const d = rows[i].close - rows[i - 1].close, up = Math.max(d, 0), dn = Math.max(-d, 0);
    if (i <= n) { g += up / n; l += dn / n; if (i < n) continue; }
    else { g = (g * (n - 1) + up) / n; l = (l * (n - 1) + dn) / n; }
    out.push({ time: rows[i].time, value: l === 0 ? 100 : 100 - 100 / (1 + g / l) });
  }
  return out;
}
const ema = (vals, n) => { const k = 2 / (n + 1); let e = null; return vals.map((v) => (e = e == null ? v : v * k + e * (1 - k))); };
function macd(rows) {
  const c = rows.map((r) => r.close), a = ema(c, 12), b = ema(c, 26), line = a.map((x, i) => x - b[i]), sig = ema(line, 9);
  return rows.map((r, i) => ({ time: r.time, line: line[i], signal: sig[i], hist: line[i] - sig[i] })).slice(26);
}
function bollinger(rows, n = 20, k = 2) {
  const out = [];
  for (let i = n - 1; i < rows.length; i++) {
    const w = rows.slice(i - n + 1, i + 1).map((r) => r.close), m = w.reduce((a, b) => a + b, 0) / n;
    const sd = Math.sqrt(w.reduce((a, b) => a + (b - m) ** 2, 0) / n);
    out.push({ time: rows[i].time, mid: m, up: m + k * sd, lo: m - k * sd });
  }
  return out;
}

const IND = () => [["ma", T("Moving averages")], ["bb", T("Bollinger bands")], ["rsi", "RSI"], ["macd", "MACD"], ["draw", T("Your drawings")]];

function Technical({ bars, pair, drawn }) {
  const frames = pair ? [["1h", T("1 hour")], ["4h", T("4 hours")], ["1d", T("Daily")], ["1w", T("Weekly")]] : [["1d", T("Daily")], ["1w", T("Weekly")]];
  const [tf, setTf] = useState("1d");
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const [on, setOn] = useState(() => { try { return JSON.parse(localStorage.getItem("mn_chart_ind")) || { ma: true, draw: true }; } catch (e) { return { ma: true, draw: true }; } });
  const flip = (k) => setOn((o) => { const n = { ...o, [k]: !o[k] }; try { localStorage.setItem("mn_chart_ind", JSON.stringify(n)); } catch (e) { /* private window */ } return n; });
  const box = useRef(null), rbox = useRef(null), mbox = useRef(null), canvas = useRef(null);
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
    const text = css("--ang-muted"), grid = css("--ang-border"), good = css("--good"), bad = css("--bad"), gold = css("--gold") || "#c69420", grey = css("--grey") || "#8a94a3";
    const base = (h, extra) => ({ height: h, layout: { background: { color: "transparent" }, textColor: text, fontFamily: "Inter, system-ui, sans-serif" },
      grid: { vertLines: { color: grid }, horzLines: { color: grid } }, rightPriceScale: { borderColor: grid, minimumWidth: 64 },
      timeScale: { borderColor: grid, timeVisible: tf === "1h" || tf === "4h" }, crosshair: { mode: CrosshairMode.Normal }, autoSize: true, ...(extra || {}) });
    const charts = [];
    const chart = createChart(box.current, base(420)); charts.push(chart);
    const c = chart.addCandlestickSeries({ upColor: good, downColor: bad, borderVisible: false, wickUpColor: good, wickDownColor: bad });
    c.setData(rows);
    const v = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol", color: grid });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    v.setData(rows.map((r) => ({ time: r.time, value: r.volume || 0, color: r.close >= r.open ? "rgba(0,127,115,.28)" : "rgba(194,51,63,.28)" })));
    const line = (ch, color, data, w = 2, style = 0) => { const sr = ch.addLineSeries({ color, lineWidth: w, lineStyle: style, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }); sr.setData(data); return sr; };
    if (on.ma) { line(chart, gold, sma(rows, 50)); line(chart, grey, sma(rows, 200)); }
    if (on.bb) { const b = bollinger(rows); const col = "rgba(41,98,255,.65)"; line(chart, col, b.map((x) => ({ time: x.time, value: x.up })), 1); line(chart, col, b.map((x) => ({ time: x.time, value: x.lo })), 1); line(chart, col, b.map((x) => ({ time: x.time, value: x.mid })), 1, 2); }
    if (on.rsi && rbox.current) {
      const rc = createChart(rbox.current, base(130, { timeScale: { visible: false } })); charts.push(rc);
      const rs = line(rc, "#7e57c2", rsi(rows), 2);
      rs.createPriceLine({ price: 70, color: bad, lineWidth: 1, lineStyle: 2, axisLabelVisible: true });
      rs.createPriceLine({ price: 30, color: good, lineWidth: 1, lineStyle: 2, axisLabelVisible: true });
    }
    if (on.macd && mbox.current) {
      const mc = createChart(mbox.current, base(130, { timeScale: { visible: false } })); charts.push(mc);
      const m = macd(rows);
      const h = mc.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
      h.setData(m.map((x) => ({ time: x.time, value: x.hist, color: x.hist >= 0 ? "rgba(0,127,115,.5)" : "rgba(194,51,63,.5)" })));
      line(mc, "#2962ff", m.map((x) => ({ time: x.time, value: x.line })), 2); line(mc, "#ff9800", m.map((x) => ({ time: x.time, value: x.signal })), 2);
    }
    // The lower charts follow the main chart's scrolling and zooming.
    const sync = (r) => { if (r) charts.slice(1).forEach((ch) => ch.timeScale().setVisibleLogicalRange(r)); paint(); };
    chart.timeScale().subscribeVisibleLogicalRangeChange(sync);
    const shown = tf === "1w" ? 104 : 160;
    if (rows.length > shown) chart.timeScale().setVisibleLogicalRange({ from: rows.length - shown, to: rows.length + 2 });

    // The member's own drawings, made in the classic app's chart, painted over the candles.
    const times = rows.map((r) => r.time);
    const X = (t) => {
      let lo = 0, hi = times.length - 1;
      const step = (times[1] - times[0]) || 86400;
      if (t <= times[0]) lo = (t - times[0]) / step; else if (t >= times[hi]) lo = hi + (t - times[hi]) / ((times[hi] - times[hi - 1]) || step); else {
        while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (times[mid] <= t) lo = mid; else hi = mid; }
        lo = lo + (t - times[lo]) / ((times[lo + 1] - times[lo]) || 1);
      }
      return chart.timeScale().logicalToCoordinate(lo);
    };
    const Y = (p) => c.priceToCoordinate(p);
    function paint() {
      const cv = canvas.current; if (!cv || !box.current) return;
      const w = box.current.clientWidth, hgt = 420, dpr = window.devicePixelRatio || 1;
      cv.width = w * dpr; cv.height = hgt * dpr; cv.style.width = w + "px"; cv.style.height = hgt + "px";
      const ctx = cv.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, hgt);
      if (!on.draw) return;
      const plotW = w - 64;
      ctx.save(); ctx.beginPath(); ctx.rect(0, 0, plotW, hgt); ctx.clip();
      (drawn || []).forEach((it) => drawOne(ctx, it, X, Y, plotW, hgt));
      ctx.restore();
    }
    const ro = new ResizeObserver(() => paint()); ro.observe(box.current);
    setTimeout(paint, 50);
    return () => { ro.disconnect(); chart.timeScale().unsubscribeVisibleLogicalRangeChange(sync); charts.forEach((ch) => ch.remove()); };
  }, [rows, on, drawn]);

  return (
    <>
      <div className="bar" style={{ marginBottom: 8 }}>
        <div className="chips" role="group" aria-label={T("Candle size")}>
          {frames.map(([k, l]) => <button key={k} type="button" className={tf === k ? "on" : ""} aria-pressed={tf === k} onClick={() => setTf(k)}>{l}</button>)}
        </div>
        <div className="chips right ind" role="group" aria-label={T("Indicators")}>
          {IND().filter(([k]) => k !== "draw" || (drawn && drawn.length)).map(([k, l]) => <button key={k} type="button" className={on[k] ? "on" : ""} aria-pressed={!!on[k]} onClick={() => flip(k)}>{l}</button>)}
        </div>
      </div>
      {err && <p className="sub">{err}</p>}
      {!rows ? <div className="empty" style={{ height: 420 }}>{T("Loading…")}</div> : (
        <>
          <div style={{ position: "relative", height: 420 }}>
            <div ref={box} style={{ height: 420 }} />
            <canvas ref={canvas} style={{ position: "absolute", left: 0, top: 0, pointerEvents: "none" }} />
          </div>
          {on.rsi && <><div className="sublabel">RSI (14)</div><div ref={rbox} style={{ height: 130 }} /></>}
          {on.macd && <><div className="sublabel">MACD (12, 26, 9)</div><div ref={mbox} style={{ height: 130 }} /></>}
        </>
      )}
      <div className="legend" style={{ marginTop: 8 }}>
        {on.ma && <><span><i style={{ background: "var(--gold)" }} />{T("Average of 50 candles")}</span><span><i style={{ background: "var(--grey)" }} />{T("Average of 200 candles")}</span></>}
        {on.bb && <span><i style={{ background: "rgba(41,98,255,.65)" }} />{T("Bollinger bands (20, 2)")}</span>}
        {on.draw && drawn && drawn.length > 0 && <span className="m">{T("Drawings are made and edited in the classic app's chart.")}</span>}
      </div>
    </>
  );
}

// Paint one saved drawing (the classic chart's format: {tool, pts: [{t, p}], color, width, text, mark}).
function drawOne(ctx, it, X, Y, W, H) {
  const P = (it.pts || []).map((q) => [X(q.t), Y(q.p)]);
  if (!P.length || P.some(([x, y]) => x == null || y == null || !isFinite(x) || !isFinite(y))) return;
  const colour = it.color || "#2962ff", width = it.width || 2;
  ctx.strokeStyle = colour; ctx.fillStyle = colour; ctx.lineWidth = width; ctx.globalAlpha = 1;
  const ln = (pts) => { ctx.beginPath(); pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.stroke(); };
  const two = P.length > 1;
  switch (it.tool) {
    case "pen": ln(P); break;
    case "hl": ctx.globalAlpha = 0.35; ctx.lineWidth = Math.max(12, width * 5); ln(P); break;
    case "trend": case "measure": if (two) ln(P.slice(0, 2)); break;
    case "arrow": if (two) { ln(P.slice(0, 2)); const [[ax, ay], [bx, by]] = P, a = Math.atan2(by - ay, bx - ax), s = 8 + width * 2;
      ctx.beginPath(); ctx.moveTo(bx, by); ctx.lineTo(bx - s * Math.cos(a - 0.4), by - s * Math.sin(a - 0.4)); ctx.lineTo(bx - s * Math.cos(a + 0.4), by - s * Math.sin(a + 0.4)); ctx.closePath(); ctx.fill(); } break;
    case "ray": if (two) { const [[ax, ay], [bx, by]] = P, dx = bx - ax, dy = by - ay, k = dx || dy ? 4 * (W + H) / Math.hypot(dx, dy) : 0; ln([[ax, ay], [ax + dx * k, ay + dy * k]]); } break;
    case "hline": ln([[0, P[0][1]], [W, P[0][1]]]); break;
    case "vline": ln([[P[0][0], 0], [P[0][0], H]]); break;
    case "channel": if (two) ln(P.slice(0, 2)); break;
    case "box": case "position": if (two) { const [[ax, ay], [bx, by]] = P; ctx.globalAlpha = 0.14; ctx.fillRect(Math.min(ax, bx), Math.min(ay, by), Math.abs(bx - ax), Math.abs(by - ay)); ctx.globalAlpha = 1; ctx.strokeRect(Math.min(ax, bx), Math.min(ay, by), Math.abs(bx - ax), Math.abs(by - ay)); } break;
    case "circle": if (two) { const [[ax, ay], [bx, by]] = P; ctx.beginPath(); ctx.ellipse((ax + bx) / 2, (ay + by) / 2, Math.max(2, Math.abs(bx - ax) / 2), Math.max(2, Math.abs(by - ay) / 2), 0, 0, Math.PI * 2); ctx.stroke(); } break;
    case "marker": ctx.font = `bold ${12 + width * 4}px system-ui,sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(it.mark || "✖", P[0][0], P[0][1]); ctx.textAlign = "start"; break;
    case "text": { const px = 11 + width * 2; ctx.font = `${px}px system-ui,sans-serif`; ctx.textBaseline = "top"; String(it.text || "").split("\n").forEach((r, i) => ctx.fillText(r, P[0][0], P[0][1] + i * (px + 3))); break; }
    case "fib": if (two) { const a = it.pts[0].p, b = it.pts[1].p, x0 = Math.min(P[0][0], P[1][0]);
      [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1].forEach((r) => { const y = Y(b - (b - a) * r); if (y == null) return; ctx.lineWidth = r === 0.5 || r === 0.618 ? width + 0.5 : 1; ln([[x0, y], [W, y]]); ctx.font = "11px system-ui,sans-serif"; ctx.fillText(String(r), x0 + 3, y - 3); }); } break;
    default: break;
  }
  ctx.globalAlpha = 1;
}
