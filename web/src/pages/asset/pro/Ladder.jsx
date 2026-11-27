import React, { useEffect, useMemo, useState } from "react";
import { T } from "../../../lib/i18n.js";
import { call } from "../../../lib/service.js";
import Icon from "../../../components/Icon.jsx";

// 🪜 Ladder helper: plan a ladder of limit orders below the price (or above it, for a short) instead of buying all at
// once, spaced by the asset's own typical daily move (ATR 14) or on Fibonacci levels, with a stop beyond the last
// order. A planning calculator: nothing is placed or sent. The same rules as the classic app (ladder_helper.py); the
// data service sends the price, ATR, regime and last swings (service/pro_chart.ladder), the plan is worked out here.
const fibWords = (r) => `${(r * 100).toFixed(1).replace(/\.0$/, "")}%`;
const priceText = (v) => { const a = Math.abs(v); const d = a >= 100 ? 2 : a >= 1 ? 3 : a >= 0.01 ? 5 : 8; return v.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d }); };

function shares(n, styleCfg) {
  const raw = styleCfg.weights === "equal" ? Array(n).fill(1) : Array.from({ length: n }, (_, i) => i + 1);
  const sum = raw.reduce((a, b) => a + b, 0);
  return raw.map((w) => w / sum);
}
function finish(price, atr, side, rows, stop, amount) {
  const avg = 1 / rows.reduce((a, r) => a + r.share / r.price, 0);
  const lossPct = (stop / avg - 1) * 100 * (side === "long" ? 1 : -1);
  return { ok: true, rows, stop, stopPct: (stop / price - 1) * 100, stopMoves: Math.abs(stop - price) / atr, avg,
    avgPct: (avg / price - 1) * 100, lossPct, lossAmount: amount ? amount * lossPct / 100 : null };
}
export function planByMoves(c, price, atr, side, style, orders, deepest, amount) {
  const cfg = c.styles[style] || c.styles.consolidating;
  const n = Math.max(2, Math.min(6, orders | 0));
  const deep = deepest != null ? deepest : cfg.deepest;
  const first = Math.min(cfg.first, deep / 2);
  const sign = side === "long" ? -1 : 1, sh = shares(n, cfg);
  const rows = Array.from({ length: n }, (_, i) => {
    const d = first + (deep - first) * i / (n - 1), p = price + sign * d * atr;
    return { n: i + 1, price: p, pct: (p / price - 1) * 100, moves: d, share: sh[i], fib: null, amount: amount ? amount * sh[i] : null };
  });
  return finish(price, atr, side, rows, price + sign * (deep + c.stop_beyond) * atr, amount);
}
export function planOnFib(c, price, atr, low, high, side, style, orders, amount) {
  if (!low || !high || high <= low) return { ok: false, reason: "no_swing" };
  const levels = c.fib_sets[String(Math.max(2, Math.min(6, orders | 0)))];
  const at = (r) => (side === "long" ? high - (high - low) * r : low + (high - low) * r);
  const picked = levels.map((r) => [r, at(r)]).filter(([, p]) => (side === "long" ? p < price : p > price));
  if (!picked.length) return { ok: false, reason: "past_levels" };
  const cfg = c.styles[style] || c.styles.consolidating, sh = shares(picked.length, cfg);
  const rows = picked.map(([r, p], i) => ({ n: i + 1, price: p, pct: (p / price - 1) * 100, moves: Math.abs(p - price) / atr, share: sh[i], fib: r, amount: amount ? amount * sh[i] : null }));
  const stop = side === "long" ? low - c.fib_stop_beyond * atr : high + c.fib_stop_beyond * atr;
  return { ...finish(price, atr, side, rows, stop, amount), low, high };
}
// The newest Fibonacci among the member's drawings on this asset: {low, high}.
function drawnFib(items) {
  for (const it of [...(items || [])].reverse()) {
    if (it && it.tool === "fib" && (it.pts || []).length >= 2) {
      const a = Number(it.pts[0].p), b = Number(it.pts[1].p);
      if (isFinite(a) && isFinite(b) && a !== b) return { low: Math.min(a, b), high: Math.max(a, b) };
    }
  }
  return null;
}

export default function Ladder({ assetKey, interval, range, drawings, onLines }) {
  const [c, setC] = useState(null);
  const [side, setSide] = useState(null);
  const [style, setStyle] = useState(null);
  const [orders, setOrders] = useState(3);
  const [place, setPlace] = useState("moves");
  const [start, setStart] = useState("");
  const [deep, setDeep] = useState({});
  const [amount, setAmount] = useState("");
  const [show, setShow] = useState(false);
  useEffect(() => {
    let gone = false;
    call(`/ladder?key=${encodeURIComponent(assetKey)}&interval=${interval}&range=${range}`).then((d) => !gone && setC(d)).catch(() => !gone && setC({ ok: false }));
    return () => { gone = true; };
  }, [assetKey, interval, range]);
  const ready = c && c.ok;
  const presetSide = ready && c.regime === "trending_down" ? "short" : "long";
  const presetStyle = ready && String(c.regime || "").startsWith("trending") ? "trending" : "consolidating";
  const s = side || presetSide, st = style || presetStyle;
  const from = Number(start) > 0 ? Number(start) : ready ? c.price : 0;
  const amt = Number(amount) > 0 ? Number(amount) : null;
  const drawn = drawnFib(drawings);
  const swing = drawn ? { ...drawn, origin: "drawing" } : ready && c.swings && c.swings[s] ? { ...c.swings[s], origin: "swing" } : null;
  const p = useMemo(() => {
    if (!ready) return null;
    if (place === "fib") return swing ? planOnFib(c, from, c.atr, swing.low, swing.high, s, st, orders, amt) : { ok: false, reason: "no_swing" };
    return planByMoves(c, from, c.atr, s, st, orders, deep[st] != null ? deep[st] : c.styles[st].deepest, amt);
  }, [c, place, from, s, st, orders, deep, amt, swing && swing.low, swing && swing.high]);
  useEffect(() => {                                   // its lines on the chart when "Show on chart" is on
    if (!show || !p || !p.ok) { onLines([]); return; }
    const lines = p.rows.map((r) => ({ price: r.price, color: "#2563eb", width: Math.max(1, Math.min(4, Math.round(r.share * p.rows.length * 2))), style: "dashed",
      label: `${T("Order")} ${r.n} · ${Math.round(r.share * 100)}%` + (r.fib != null ? ` · ${fibWords(r.fib)}` : "") }));
    lines.push({ price: p.stop, color: "#dc2626", width: 2, style: "solid", label: T("Stop") });
    lines.push({ price: p.avg, color: "#64748b", width: 1, style: "dotted", label: T("Average if all fill") });
    onLines(lines);
  }, [show, p]);
  useEffect(() => () => onLines([]), []);
  if (!c) return null;
  if (!ready) return <p className="sub">{T("The ladder helper needs at least 15 days of prices for this asset.")}</p>;
  const regimeWord = c.regime && c.regime_words[c.regime];
  const levels = c.fib_sets[String(Math.max(2, Math.min(6, orders)))];
  const seg = (value, set, opts, label, help) => (
    <div className="seg" role="radiogroup" aria-label={label} title={help}>
      {opts.map(([k, ic, l]) => <button key={k} type="button" role="radio" aria-checked={value === k} className={value === k ? "on" : ""} onClick={() => set(k)}><Icon n={ic} size={15} /> {l}</button>)}
    </div>
  );
  return (
    <details className="card latdet ladder">
      <summary><Icon n="layers" size={16} /> {T("Ladder helper")} <span className="m">· {T("plan limit orders spaced by the daily range")}</span></summary>
      <div className="ladgrid">
        <div className="funfield"><span className="m">{T("Side")}</span>
          {seg(s, setSide, [["long", "trending-up", T("Long")], ["short", "trending-down", T("Short")]], T("Side"), T("Long: orders below the price. Short: orders above it."))}
          {regimeWord && String(c.regime).startsWith("trending_") && <span className="m">{T("Starts on {side} by a simple rule: the regime reads {regime}. An illustration of a ladder, not a recommendation; pick either side.", { side: presetSide === "short" ? T("Short") : T("Long"), regime: regimeWord })}</span>}
        </div>
        <div className="funfield"><span className="m">{T("Market")}</span>
          {seg(st, setStyle, [["consolidating", "blocks", T("Consolidating")], ["trending", "rocket", T("Trending")]], T("Market"), T("Consolidating: equal orders, close to the price. Trending: the order nearest the price smallest, the furthest largest."))}
          {regimeWord && <span className="m">{st === presetStyle ? T("Preset from this asset's regime ({regime}). Change it if you see it differently.", { regime: regimeWord }) : T("The regime reads {regime}; you chose otherwise.", { regime: regimeWord })}</span>}
        </div>
        <label className="funfield"><span className="m">{T("Orders")}</span><input type="number" min={2} max={6} value={orders} onChange={(e) => setOrders(Math.max(2, Math.min(6, Number(e.target.value) || 3)))} /></label>
        <div className="funfield"><span className="m">{T("Place the orders")}</span>
          {seg(place, setPlace, [["moves", "ruler", T("By daily move")], ["fib", "shapes", T("On Fibonacci levels")]], T("Place the orders"),
            T("By daily move: spaced by this asset's typical daily range. On Fibonacci levels: at the retracement levels of the last move, from your own 📐 Fibonacci drawing on this asset, or else from the last swing low to the high since (a short: the last swing high to the low since), with the stop just past the swing."))}
          {place === "fib" && <span className="m">{swing ? T("Measured on {where}: low {low}, high {high}.", { where: swing.origin === "drawing" ? T("your Fibonacci drawing") : T("the last swing on these candles"), low: priceText(swing.low), high: priceText(swing.high) }) : T("No swing found on these candles. Draw a Fibonacci on the chart, or pick a longer range.")}</span>}
        </div>
        <label className="funfield" title={T("The latest close; change it to plan from another price.")}><span className="m">{T("From price")}</span>
          <input type="number" min={0} step="any" value={start === "" ? c.price : start} onChange={(e) => setStart(e.target.value)} /></label>
        {place === "fib" ? <div className="funfield"><span className="m">{T("Levels used: {levels}", { levels: levels.map(fibWords).join(", ") })}</span></div> : (
          <label className="funfield" title={T("One daily move = this asset's typical daily range (ATR 14), {pct:.1f}% now.").replace("{pct:.1f}", (c.atr / c.price * 100).toFixed(1))}>
            <span className="m">{T("Deepest order, in daily moves")} · <b>{(deep[st] != null ? deep[st] : c.styles[st].deepest).toFixed(2)}</b></span>
            <input type="range" min={0.2} max={2} step={0.05} value={deep[st] != null ? deep[st] : c.styles[st].deepest} onChange={(e) => setDeep({ ...deep, [st]: Number(e.target.value) })} />
          </label>
        )}
        <label className="funfield" title={T("The total to split across the orders, in your account's currency.")}><span className="m">{T("Amount (optional)")}</span>
          <input type="number" min={0} step={100} value={amount} placeholder="0" onChange={(e) => setAmount(e.target.value)} /></label>
        <label className="ptog" title={T("Draws the orders (blue, thicker for a bigger share), the stop (red) and the average price if every order fills (grey) as lines across the chart above. A plan from the price here, not live orders.")}>
          <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} /> <span><Icon n="ruler" size={15} /> {T("Show on chart")}</span></label>
      </div>
      {p && !p.ok && p.reason === "past_levels" && <p className="sub">{T("Price is already past every Fibonacci level of this move on that side. Pick fewer orders, the other side, or draw a new Fibonacci.")}</p>}
      {p && p.ok && (
        <>
          <div className="latscroll"><table className="lattbl lad">
            <thead><tr><th>#</th><th>{T("Price")}</th>{place === "fib" && <th>{T("Fibonacci")}</th>}<th>{T("From price")}</th><th>{T("Daily moves")}</th><th>{T("Share")}</th>{amt && <th>{T("Amount")}</th>}</tr></thead>
            <tbody>
              {p.rows.map((r) => <tr key={r.n}><td>{r.n}</td><td><b>{priceText(r.price)}</b></td>{place === "fib" && <td>{fibWords(r.fib)}</td>}<td>{r.pct >= 0 ? "+" : ""}{r.pct.toFixed(2)}%</td><td>{r.moves.toFixed(2)}</td><td>{Math.round(r.share * 100)}%</td>{amt && <td>{r.amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>}</tr>)}
              <tr className="ladstop"><td><Icon n="octagon-x" size={15} /></td><td><b>{priceText(p.stop)}</b></td>{place === "fib" && <td>{T("past 100%")}</td>}<td>{p.stopPct >= 0 ? "+" : ""}{p.stopPct.toFixed(2)}%</td><td>{p.stopMoves.toFixed(2)}</td><td colSpan={amt ? 2 : 1}>{T("Stop")}</td></tr>
            </tbody>
          </table></div>
          <p className="sub">{T("If every order fills, the average price is {avg} ({avg_pct:+.2f}%); a stop there loses {loss:.1f}% of the amount")
            .replace("{avg}", priceText(p.avg)).replace("{avg_pct:+.2f}", `${p.avgPct >= 0 ? "+" : ""}${p.avgPct.toFixed(2)}`).replace("{loss:.1f}", Math.abs(p.lossPct).toFixed(1))}
            {p.lossAmount ? ` (${Math.abs(p.lossAmount).toLocaleString(undefined, { maximumFractionDigits: 2 })})` : ""}. {T("In our test of 30 coins on hourly candles, price dipped a typical 0.4 daily moves further within a day after a bottom signal, 1 time in 4 about 0.75 and 1 time in 10 about 1.3. A planning calculator: nothing is placed, and it is not advice.")}</p>
        </>
      )}
    </details>
  );
}
