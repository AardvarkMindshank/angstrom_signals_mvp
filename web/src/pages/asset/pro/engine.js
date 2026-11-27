// ⭐ The Pro chart: the classic app's TradingView chart (lw_chart.js) and its drawing tools (lw_draw.js), ported
// to this app as one module on the bundled library. The data service builds the same data the classic app sends
// (service/pro_chart.py, lw_chart.build_payload), so every indicator, marker and line matches the classic chart.
// Kept close to the originals on purpose: a fix in one should be easy to carry to the other.
/* eslint-disable */
import * as L from "lightweight-charts";
import { T } from "../../../lib/i18n.js";

const TM = (s) => s;      // marks text kept in a constant; translated with T(…) where it is shown

// ✏️ Drawing on the price chart (13 Nov 2026): pen, highlighter, eraser, lines, shapes, markers, notes, Fibonacci,
// measure and long/short position, anchored VWAP and a volume profile over a range (19 Nov 2026), in a toolbar above
// the chart. Loaded in front of lw_chart.js (one module).
//
// Points are (time in seconds, price), so drawings stay put when the chart zooms or scrolls, and show on every
// candle size of the same asset. They save to the account (chart_drawings, sql/2026-11-27_chart_drawings.sql)
// straight from the browser with the person's own session, so drawing never reloads the page. If that fails, the
// chart hands them to the app instead ("drawings" trigger) and the app saves them.

const DRAW_TOOLS = [
  // [id, icon, tip, kind]   kind: free | erase | one | two | three | text
  ["pan", "✋", TM("Move the chart (no drawing tool)"), "none"],
  ["pen", "✏️", TM("Pen: draw freely with a finger, Pencil or mouse"), "free"],
  ["hl", "🖍️", TM("Highlighter: a wide, see-through pen"), "free"],
  ["erase", "🧽", TM("Eraser: tap or drag across a drawing to remove it"), "erase"],
  ["trend", "╱", TM("Trend line: drag from one point to another"), "two"],
  ["ray", "↗", TM("Ray: a line from a point that runs on into the future"), "two"],
  ["hline", "━", TM("Horizontal line: a price level across the chart"), "one"],
  ["vline", "┃", TM("Vertical line: marks a date or time"), "one"],
  ["channel", "⫽", TM("Parallel channel: drag the first line, then tap where the parallel line goes"), "three"],
  ["arrow", "➚", TM("Arrow: drag from the tail to the point"), "two"],
  ["box", "▭", TM("Box / zone: drag from one corner to the other"), "two"],
  ["circle", "◯", TM("Circle: drag across what to circle"), "two"],
  ["marker", "✖", TM("Marker: tap to stamp the mark chosen beside it"), "one"],
  ["text", "🔤", TM("Text note: tap where the note goes, then type"), "text"],
  ["fib", "📐", TM("Fibonacci retracement: drag from the swing low to the swing high (or high to low)"), "two"],
  ["avwap", "⚓", TM("Anchored VWAP: tap a candle to draw the volume-weighted average price from there on"), "one"],
  ["vprofile", "📊", TM("Volume profile: drag across a stretch of the chart to see at which prices most trading happened"), "two"],
  ["measure", "📏", TM("Measure: drag between two points to see the % change and the number of candles"), "two"],
  ["position", "🎯", TM("Long / short position: drag from the entry to the stop, then tap the target"), "three"],
];
const DRAW_COLOURS = ["#2962ff", "#f23645", "#089981", "#ff9800", "#9c27b0", "#00bcd4", "#e91e63", "#ffffff", "#131722"];
const DRAW_WIDTHS = [[1, TM("Thin lines")], [2, TM("Medium lines")], [4, TM("Thick lines")]];
const DRAW_MARKS = ["✖", "✔", "★", "▲", "▼", "●", "?", "!"];
const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.65, 0.786, 1];
const DRAW_MAX_ITEMS = 400;
const PROFILE_ROWS = 24;            // price rows in a volume profile
const VALUE_AREA = 0.7;             // the rows around the busiest price that hold 70% of the volume

// Candles of the chart's own candle size from `from` (seconds) on: [index, high, low, close, volume].
function candleIndex(data, t) {
  const T = data.times;
  let lo = 0, hi = T.length - 1;
  if (!T.length || t > T[hi]) return T.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (T[mid] < t) lo = mid + 1; else hi = mid; }
  return lo;
}

// Anchored VWAP: from the anchor candle on, the running sum of typical price x volume over the running volume.
function vwapLine(data, anchor) {
  const [, H, Lo, C] = data.ohlc, V = data.volume, T = data.times;
  const out = [];
  let pv = 0, vol = 0;
  for (let i = Math.max(0, candleIndex(data, anchor)); i < T.length; i++) {
    const v = Number(V[i]) || 0, typical = (H[i] + Lo[i] + C[i]) / 3;
    if (!isFinite(typical)) continue;
    pv += typical * v; vol += v;
    out.push([T[i], vol > 0 ? pv / vol : typical]);
  }
  return out;
}

// Volume profile between two times: the range's volume shared out over PROFILE_ROWS price rows (each candle's
// volume spread evenly over the rows its high-low covers), the busiest row and the 70% value area around it.
function volumeProfile(data, t0, t1) {
  const [, H, Lo] = data.ohlc, V = data.volume, T = data.times;
  const a = candleIndex(data, Math.min(t0, t1)), b = Math.min(T.length, candleIndex(data, Math.max(t0, t1) + 1));
  let top = -Infinity, bottom = Infinity;
  for (let i = a; i < b; i++) { if (isFinite(H[i])) top = Math.max(top, H[i]); if (isFinite(Lo[i])) bottom = Math.min(bottom, Lo[i]); }
  if (!(top > bottom)) return null;
  const step = (top - bottom) / PROFILE_ROWS, rows = new Array(PROFILE_ROWS).fill(0);
  for (let i = a; i < b; i++) {
    const v = Number(V[i]) || 0;
    if (!v || !isFinite(H[i]) || !isFinite(Lo[i])) continue;
    const r0 = Math.max(0, Math.min(PROFILE_ROWS - 1, Math.floor((Lo[i] - bottom) / step)));
    const r1 = Math.max(0, Math.min(PROFILE_ROWS - 1, Math.floor((H[i] - bottom) / step)));
    for (let r = r0; r <= r1; r++) rows[r] += v / (r1 - r0 + 1);
  }
  const total = rows.reduce((x, y) => x + y, 0);
  if (!total) return null;
  const poc = rows.indexOf(Math.max(...rows));
  let lo = poc, hi = poc, held = rows[poc];
  while (held < total * VALUE_AREA && (lo > 0 || hi < PROFILE_ROWS - 1)) {
    const below = lo > 0 ? rows[lo - 1] : -1, above = hi < PROFILE_ROWS - 1 ? rows[hi + 1] : -1;
    if (above >= below) { hi += 1; held += above; } else { lo -= 1; held += below; }
  }
  return { bottom, step, rows, poc, lo, hi, candles: b - a };
}
const DRAW_STORE = window.__angDraw || (window.__angDraw = { assets: new Map() });

function drawPref(name, fallback) {
  try { const v = localStorage.getItem("ang-draw:" + name); return v === null ? fallback : JSON.parse(v); } catch (e) { return fallback; }
}
function setDrawPref(name, value) {
  try { localStorage.setItem("ang-draw:" + name, JSON.stringify(value)); } catch (e) { /* private mode */ }
}

function segDistance(px, py, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay;
  const len = dx * dx + dy * dy;
  let t = len ? ((px - ax) * dx + (py - ay) * dy) / len : 0;
  t = Math.max(0, Math.min(1, t));
  const x = ax + t * dx, y = ay + t * dy;
  return Math.hypot(px - x, py - y);
}

function niceNumber(v) {
  if (v === null || v === undefined || !isFinite(v)) return "–";
  const a = Math.abs(v);
  const digits = a >= 1000 ? 2 : a >= 1 ? 2 : a >= 0.01 ? 4 : 6;
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

// ------------------------------------------------------------------ the layer that paints the drawings

class DrawLayer {
  constructor(state) { this.state = state; this._update = null; }
  attached(params) { this._update = params.requestUpdate; }
  detached() { this._update = null; }
  update() { if (this._update) this._update(); }
  updateAllViews() {}
  paneViews() {
    const self = this;
    return [{
      zOrder: () => "top",
      renderer: () => ({
        draw: (target) => {
          const s = self.state;
          if (s.hidden && !s.tool) return;
          target.useMediaCoordinateSpace(({ context, mediaSize }) => {
            const ctx = context;
            ctx.save();
            ctx.lineCap = "round";
            ctx.lineJoin = "round";
            if (!s.hidden) {
              ctx.globalAlpha = 1;
              for (const it of s.shared || []) paintItem(ctx, s, it, mediaSize);    // someone's shared drawings
              for (const it of s.items) paintItem(ctx, s, it, mediaSize);
            }
            if (s.draft) paintItem(ctx, s, s.draft, mediaSize);
            ctx.restore();
          });
        },
      }),
    }];
  }
}

function screenPts(s, it) {
  return it.pts.map((p) => [s.X(p.t), s.Y(p.p)]);
}

function label(ctx, text, x, y, colour, align, ink) {
  ctx.font = "11px system-ui,-apple-system,Segoe UI,sans-serif";
  const w = ctx.measureText(text).width + 8;
  const left = align === "right" ? x - w : align === "center" ? x - w / 2 : x;
  ctx.fillStyle = colour;
  ctx.globalAlpha = 0.9;
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(left, y - 8, w, 16, 3); else ctx.rect(left, y - 8, w, 16);
  ctx.fill();
  ctx.globalAlpha = 1;
  ctx.fillStyle = ink || "#ffffff";
  ctx.textBaseline = "middle";
  ctx.fillText(text, left + 4, y + 0.5);
}

function arrowHead(ctx, ax, ay, bx, by, size) {
  const a = Math.atan2(by - ay, bx - ax);
  ctx.beginPath();
  ctx.moveTo(bx, by);
  ctx.lineTo(bx - size * Math.cos(a - 0.45), by - size * Math.sin(a - 0.45));
  ctx.lineTo(bx - size * Math.cos(a + 0.45), by - size * Math.sin(a + 0.45));
  ctx.closePath();
  ctx.fill();
}

function paintItem(ctx, s, it, size) {
  const P = screenPts(s, it);
  if (P.some(([x, y]) => x === null || y === null || !isFinite(x) || !isFinite(y))) return;
  const W = size.width, H = size.height;
  const colour = it.color || "#2962ff";
  const width = it.width || 2;
  ctx.strokeStyle = colour;
  ctx.fillStyle = colour;
  ctx.lineWidth = width;
  ctx.globalAlpha = 1;
  const line = (pts) => { ctx.beginPath(); pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.stroke(); };
  switch (it.tool) {
    case "pen": line(P); break;
    case "hl":
      ctx.globalAlpha = 0.35; ctx.lineWidth = Math.max(12, width * 5); line(P); ctx.globalAlpha = 1; break;
    case "trend": line(P); break;
    case "arrow":
      line(P); if (P.length > 1) arrowHead(ctx, P[0][0], P[0][1], P[1][0], P[1][1], 8 + width * 2); break;
    case "ray": {
      if (P.length < 2) break;
      const [[ax, ay], [bx, by]] = P;
      const dx = bx - ax, dy = by - ay;
      const k = dx === 0 && dy === 0 ? 0 : 4 * (W + H) / Math.hypot(dx, dy);
      line([[ax, ay], [ax + dx * k, ay + dy * k]]);
      break;
    }
    case "hline": {
      const y = P[0][1];
      line([[0, y], [W, y]]);
      label(ctx, niceNumber(it.pts[0].p), W - 2, y, colour, "right");
      break;
    }
    case "vline": line([[P[0][0], 0], [P[0][0], H]]); break;
    case "channel": {
      line(P.slice(0, 2));
      if (P.length > 2) {
        const off = it.pts[2].p - (it.pts[0].p + (it.pts[1].p - it.pts[0].p) * ((P[2][0] - P[0][0]) / ((P[1][0] - P[0][0]) || 1)));
        const a2 = [P[0][0], s.Y(it.pts[0].p + off)], b2 = [P[1][0], s.Y(it.pts[1].p + off)];
        line([a2, b2]);
        ctx.globalAlpha = 0.08;
        ctx.beginPath(); ctx.moveTo(P[0][0], P[0][1]); ctx.lineTo(P[1][0], P[1][1]); ctx.lineTo(b2[0], b2[1]); ctx.lineTo(a2[0], a2[1]); ctx.closePath(); ctx.fill();
        ctx.globalAlpha = 1;
      }
      break;
    }
    case "box": {
      if (P.length < 2) break;
      const [[ax, ay], [bx, by]] = P;
      ctx.globalAlpha = 0.14; ctx.fillRect(Math.min(ax, bx), Math.min(ay, by), Math.abs(bx - ax), Math.abs(by - ay));
      ctx.globalAlpha = 1; ctx.strokeRect(Math.min(ax, bx), Math.min(ay, by), Math.abs(bx - ax), Math.abs(by - ay));
      break;
    }
    case "circle": {
      if (P.length < 2) break;
      const [[ax, ay], [bx, by]] = P;
      ctx.beginPath();
      ctx.ellipse((ax + bx) / 2, (ay + by) / 2, Math.max(2, Math.abs(bx - ax) / 2), Math.max(2, Math.abs(by - ay) / 2), 0, 0, Math.PI * 2);
      ctx.stroke();
      break;
    }
    case "marker": {
      const sizePx = 12 + width * 4;
      ctx.font = `bold ${sizePx}px system-ui,-apple-system,Segoe UI,sans-serif`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(it.mark || "✖", P[0][0], P[0][1]);
      ctx.textAlign = "start";
      break;
    }
    case "text": {
      const sizePx = 11 + width * 2;
      ctx.font = `${sizePx}px system-ui,-apple-system,Segoe UI,sans-serif`;
      ctx.textBaseline = "top";
      String(it.text || "").split("\n").forEach((row, i) => ctx.fillText(row, P[0][0], P[0][1] + i * (sizePx + 3)));
      break;
    }
    case "fib": {
      if (P.length < 2) break;
      const a = it.pts[0].p, b = it.pts[1].p;
      const x0 = Math.min(P[0][0], P[1][0]);
      const levelY = (r) => s.Y(b - (b - a) * r);
      const gp = [levelY(0.618), levelY(0.65)];
      ctx.globalAlpha = 0.16; ctx.fillStyle = "#f5a524";
      ctx.fillRect(x0, Math.min(...gp), W - x0, Math.abs(gp[1] - gp[0]));
      ctx.globalAlpha = 1; ctx.fillStyle = colour;
      for (const r of FIB_LEVELS) {
        const y = levelY(r);
        if (y === null) continue;
        ctx.lineWidth = r === 0.5 || r === 0.618 ? width + 0.5 : 1;
        line([[x0, y], [W, y]]);
        label(ctx, `${r} · ${niceNumber(b - (b - a) * r)}`, x0 + 2, y - 9, colour, "left");
      }
      ctx.setLineDash([4, 4]); ctx.lineWidth = 1; line(P); ctx.setLineDash([]);
      break;
    }
    case "avwap": {
      if (!s.data) break;
      const pts = vwapLine(s.data, it.pts[0].t).map(([t, p]) => [s.X(t), s.Y(p)]).filter(([x, y]) => x !== null && y !== null);
      if (pts.length < 1) break;
      ctx.beginPath(); ctx.arc(pts[0][0], pts[0][1], 3 + width, 0, Math.PI * 2); ctx.fill();
      line(pts);
      const last = vwapLine(s.data, it.pts[0].t).pop();
      if (last) label(ctx, `AVWAP ${niceNumber(last[1])}`, W - 2, pts[pts.length - 1][1], colour, "right");
      break;
    }
    case "vprofile": {
      if (P.length < 2 || !s.data) break;
      const vp = volumeProfile(s.data, it.pts[0].t, it.pts[1].t);
      const x0 = Math.min(P[0][0], P[1][0]), x1 = Math.max(P[0][0], P[1][0]);
      ctx.globalAlpha = 0.06; ctx.fillRect(x0, 0, x1 - x0, H); ctx.globalAlpha = 1;
      if (!vp) break;
      const most = vp.rows[vp.poc], room = Math.max(40, (x1 - x0) * 0.6);
      vp.rows.forEach((v, r) => {
        const yTop = s.Y(vp.bottom + vp.step * (r + 1)), yBottom = s.Y(vp.bottom + vp.step * r);
        if (yTop === null || yBottom === null) return;
        ctx.globalAlpha = r === vp.poc ? 0.75 : r >= vp.lo && r <= vp.hi ? 0.4 : 0.18;
        ctx.fillRect(x0, Math.min(yTop, yBottom) + 0.5, room * v / most, Math.max(1, Math.abs(yBottom - yTop) - 1));
      });
      ctx.globalAlpha = 1;
      const pocPrice = vp.bottom + vp.step * (vp.poc + 0.5), yp = s.Y(pocPrice);
      if (yp !== null) {
        ctx.lineWidth = 1; ctx.setLineDash([4, 3]); line([[x0, yp], [x1, yp]]); ctx.setLineDash([]);
        label(ctx, `${T("Busiest price")} ${niceNumber(pocPrice)}`, x1 - 2, yp - 10, colour, "right");
      }
      const vah = s.Y(vp.bottom + vp.step * (vp.hi + 1)), val = s.Y(vp.bottom + vp.step * vp.lo);
      if (vah !== null) label(ctx, `${T("70% of volume")} ↑ ${niceNumber(vp.bottom + vp.step * (vp.hi + 1))}`, x1 - 2, vah - 10, colour, "right");
      if (val !== null) label(ctx, `↓ ${niceNumber(vp.bottom + vp.step * vp.lo)}`, x1 - 2, val + 10, colour, "right");
      break;
    }
    case "measure": {
      if (P.length < 2) break;
      const [[ax, ay], [bx, by]] = P;
      const up = it.pts[1].p >= it.pts[0].p;
      const tone = up ? "#089981" : "#f23645";
      ctx.fillStyle = tone; ctx.globalAlpha = 0.14;
      ctx.fillRect(Math.min(ax, bx), Math.min(ay, by), Math.abs(bx - ax), Math.abs(by - ay));
      ctx.globalAlpha = 1; ctx.strokeStyle = tone; ctx.lineWidth = 1;
      ctx.setLineDash([4, 3]); line(P); ctx.setLineDash([]);
      const pct = it.pts[0].p ? ((it.pts[1].p - it.pts[0].p) / it.pts[0].p) * 100 : 0;
      const bars = Math.round(Math.abs(s.tToL(it.pts[1].t) - s.tToL(it.pts[0].t)));
      label(ctx, `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}% · ${bars} candle${bars === 1 ? "" : "s"}`,
        (ax + bx) / 2, Math.min(ay, by) - 12, tone, "center");
      break;
    }
    case "position": {
      if (P.length < 2) break;
      const entry = it.pts[0].p, stop = it.pts[1].p;
      const long = stop < entry;
      const target = it.pts[2] ? it.pts[2].p : entry + (entry - stop) * 2;
      const x0 = P[0][0];
      const x1 = Math.max(P[1][0], it.pts[2] ? P[2][0] : P[1][0], x0 + 60);
      const ye = s.Y(entry), ys = s.Y(stop), yt = s.Y(target);
      ctx.globalAlpha = 0.18;
      ctx.fillStyle = "#f23645"; ctx.fillRect(x0, Math.min(ye, ys), x1 - x0, Math.abs(ys - ye));
      ctx.fillStyle = "#089981"; ctx.fillRect(x0, Math.min(ye, yt), x1 - x0, Math.abs(yt - ye));
      ctx.globalAlpha = 1; ctx.lineWidth = 1; ctx.strokeStyle = colour;
      line([[x0, ye], [x1, ye]]);
      const risk = Math.abs(entry - stop), reward = Math.abs(target - entry);
      const rr = risk ? reward / risk : 0;
      label(ctx, `${long ? "Long" : "Short"} · R:R ${rr.toFixed(2)}`, x0 + 2, ye, colour, "left");
      label(ctx, `Target ${niceNumber(target)} (${(((target - entry) / entry) * 100).toFixed(2)}%)`, x0 + 2, yt + (yt < ye ? -10 : 10), "#089981", "left");
      label(ctx, `Stop ${niceNumber(stop)} (${(((stop - entry) / entry) * 100).toFixed(2)}%)`, x0 + 2, ys + (ys < ye ? -10 : 10), "#f23645", "left");
      break;
    }
    default: break;
  }
  ctx.globalAlpha = 1;
}

// Is the point (x, y) on this drawing? (for the eraser)
function hitItem(s, it, x, y, size) {
  const P = screenPts(s, it);
  if (P.some(([a, b]) => a === null || b === null)) return false;
  const near = 8 + (it.width || 2);
  const onLine = (pts) => pts.some((p, i) => i > 0 && segDistance(x, y, pts[i - 1][0], pts[i - 1][1], p[0], p[1]) <= near);
  const inBox = (a, b) => x >= Math.min(a[0], b[0]) - near && x <= Math.max(a[0], b[0]) + near
    && y >= Math.min(a[1], b[1]) - near && y <= Math.max(a[1], b[1]) + near;
  switch (it.tool) {
    case "pen": case "hl": return P.length === 1 ? Math.hypot(x - P[0][0], y - P[0][1]) <= near : onLine(P);
    case "trend": case "arrow": case "channel": return onLine(P.slice(0, 2)) || (P.length > 2 && Math.abs(y - P[2][1]) <= near * 2 && inBox(P[0], P[1]));
    case "ray": return onLine([P[0], [P[0][0] + (P[1][0] - P[0][0]) * 50, P[0][1] + (P[1][1] - P[0][1]) * 50]]);
    case "hline": return Math.abs(y - P[0][1]) <= near;
    case "vline": return Math.abs(x - P[0][0]) <= near;
    case "box": case "circle": case "measure": case "fib": return inBox(P[0], P[1]);
    case "avwap": {
      if (!s.data) return false;
      const pts = vwapLine(s.data, it.pts[0].t).map(([t, p]) => [s.X(t), s.Y(p)]).filter(([a, b]) => a !== null && b !== null);
      return pts.length === 1 ? Math.hypot(x - pts[0][0], y - pts[0][1]) <= near : onLine(pts);
    }
    case "vprofile": return x >= Math.min(P[0][0], P[1][0]) - near && x <= Math.max(P[0][0], P[1][0]) + near;
    case "position": return inBox(P[0], [Math.max(P[1][0], P[0][0] + 60), P[1][1]]) || (P[2] && inBox(P[0], [P[0][0] + 60, P[2][1]]));
    case "marker": return Math.hypot(x - P[0][0], y - P[0][1]) <= 14;
    case "text": return x >= P[0][0] - 4 && x <= P[0][0] + 8 * String(it.text || "").length + 8 && y >= P[0][1] - 4 && y <= P[0][1] + 22;
    default: return false;
  }
}

// ------------------------------------------------------------------ saving

function saveDrawings(s) {
  clearTimeout(s.saveTimer);
  s.status(T("Saving…"));
  s.saveTimer = setTimeout(async () => {
    const record = DRAW_STORE.assets.get(s.asset);
    if (record) record.savedAt = Date.now();
    let ok = false;
    try { ok = s.save ? await s.save(s.items) : false; } catch (e) { ok = false; }
    s.status(ok ? T("Saved") : T("Not saved: sign in again to keep these drawings."));
  }, 700);
}

// ------------------------------------------------------------------ the toolbar and the pointer

function setupDrawing(L, root, host, chart, candles, data, theme, hasOsc) {
  const conf = data.draw;
  const bar = root.querySelector(".ang-lwc-drawbar");
  const tools = root.querySelector(".ang-lwc-tools");
  if (!bar) return;
  bar.innerHTML = "";
  if (!conf || !conf.asset) { bar.style.display = "none"; return; }

  // The drawings of this asset: kept while the page is open (so a candle-size change keeps unsaved work), and
  // replaced by the saved ones only when those are newer (drawn on another device).
  let record = DRAW_STORE.assets.get(conf.asset);
  const savedAt = conf.updated ? Date.parse(conf.updated) : 0;
  if (!record || (savedAt && savedAt > (record.savedAt || 0) + 2000)) {
    record = { items: Array.isArray(conf.items) ? conf.items.slice() : [], savedAt: savedAt || Date.now() };
    DRAW_STORE.assets.set(conf.asset, record);
  }

  const TS = data.times, n = TS.length;   // not T: that is the translation helper
  const ts = chart.timeScale();
  const tToL = (t) => {
    if (n < 2) return 0;
    if (t <= TS[0]) return (t - TS[0]) / (TS[1] - TS[0]);
    if (t >= TS[n - 1]) return n - 1 + (t - TS[n - 1]) / (TS[n - 1] - TS[n - 2]);
    const i = indexOfTime(TS, t);
    if (TS[i] === t) return i;
    return i - 1 + (t - TS[i - 1]) / (TS[i] - TS[i - 1]);
  };
  const lToT = (l) => {
    if (n < 2) return TS[0] || 0;
    if (l <= 0) return TS[0] + l * (TS[1] - TS[0]);
    if (l >= n - 1) return TS[n - 1] + (l - (n - 1)) * (TS[n - 1] - TS[n - 2]);
    const i = Math.floor(l);
    return TS[i] + (l - i) * (TS[i + 1] - TS[i]);
  };

  const s = {
    asset: conf.asset, save: conf.save,
    items: record.items, draft: null, stage: null, shared: Array.isArray(conf.shared) ? conf.shared : [],
    tool: null, colour: drawPref("colour", DRAW_COLOURS[0]), width: drawPref("width", 2),
    mark: drawPref("mark", "✖"), hidden: drawPref("hidden", false), history: [],
    tToL, data,
    X: (t) => { const x = ts.logicalToCoordinate(tToL(t)); return x === null ? null : x; },
    Y: (p) => { const y = candles.priceToCoordinate(p); return y === null ? null : y; },
    status: () => {},
  };
  root.__draw = s;
  const layer = new DrawLayer(s);
  candles.attachPrimitive(layer);
  const repaint = () => layer.update();
  s.repaint = repaint;

  const setItems = (items, remember = true) => {
    if (remember) { s.history.push(s.items.slice()); if (s.history.length > 40) s.history.shift(); }
    s.items = items.slice(-DRAW_MAX_ITEMS);
    record.items = s.items;
    repaint();
    saveDrawings(s);
    paintBar();
  };

  // ---- the pointer layer over the price pane (only while a drawing tool is on, so the chart still pans)
  const overlay = document.createElement("div");
  overlay.style.cssText = "position:absolute;z-index:3;display:none;touch-action:none;cursor:crosshair;";
  host.appendChild(overlay);
  const placeOverlay = () => {
    let w = host.clientWidth - 70, h = data.panes[0].height, left = 0;
    try { const size = chart.paneSize(0); if (size) { w = size.width; h = size.height; } } catch (e) { /* older library */ }
    try { if (hasOsc) left = chart.priceScale("left").width(); } catch (e) { left = 0; }
    overlay.style.left = left + "px"; overlay.style.top = "0px"; overlay.style.width = w + "px"; overlay.style.height = h + "px";
  };
  requestAnimationFrame(placeOverlay);
  if (root.__drawRo) root.__drawRo.disconnect();
  root.__drawRo = new ResizeObserver(() => requestAnimationFrame(placeOverlay));
  root.__drawRo.observe(host);

  const where = (e) => {
    const r = overlay.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };
  const toPoint = (x, y) => {
    const l = ts.coordinateToLogical(x), p = candles.coordinateToPrice(y);
    if (l === null || p === null || !isFinite(p)) return null;
    return { t: Math.round(lToT(l)), p: Number(p.toPrecision(10)) };
  };
  const kindOf = (id) => (DRAW_TOOLS.find((t) => t[0] === id) || [])[3];
  const newItem = (pt) => ({ id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), tool: s.tool,
    color: s.colour, width: s.width, pts: [pt] });

  let pressed = false, downAt = null, lastXY = null, erased = false;
  const commit = (it) => { s.draft = null; s.stage = null; setItems([...s.items, it]); };
  // A tap removes the drawing on top; dragging the eraser removes everything it crosses (one undo step).
  const eraseAt = (x, y, size, all) => {
    let keep;
    if (all) keep = s.items.filter((it) => !hitItem(s, it, x, y, size));
    else {
      const top = [...s.items].reverse().find((it) => hitItem(s, it, x, y, size));
      keep = top ? s.items.filter((it) => it !== top) : s.items;
    }
    if (keep.length !== s.items.length) { setItems(keep, !erased); erased = true; }
  };

  overlay.addEventListener("pointerdown", (e) => {
    if (!s.tool) return;
    e.preventDefault();
    try { overlay.setPointerCapture(e.pointerId); } catch (err) { /* old browser */ }
    const [x, y] = where(e);
    const pt = toPoint(x, y);
    if (!pt) return;
    pressed = true; downAt = [x, y]; lastXY = [x, y]; erased = false;
    const kind = kindOf(s.tool);
    const size = { width: overlay.clientWidth, height: overlay.clientHeight };
    if (kind === "erase") { eraseAt(x, y, size, false); return; }
    if (s.stage === "third" && s.draft) {        // channel / position: this tap places the last point
      s.draft.pts[2] = pt; commit(s.draft); pressed = false; return;
    }
    if (s.stage === "second" && s.draft) {       // tap, tap: the second tap ends a two-point drawing
      s.draft.pts[1] = pt;
      if (kind === "three") { s.stage = "third"; s.draft.pts[2] = pt; repaint(); } else commit(s.draft);
      pressed = false; return;
    }
    s.draft = newItem(pt);
    if (s.tool === "marker") s.draft.mark = s.mark;
    if (kind === "two" || kind === "three") s.draft.pts.push(pt);
    repaint();
  });
  overlay.addEventListener("pointermove", (e) => {
    if (!s.tool) return;
    const [x, y] = where(e);
    const kind = kindOf(s.tool);
    if (kind === "erase") {
      if (pressed && downAt && Math.hypot(x - downAt[0], y - downAt[1]) > 4) eraseAt(x, y, { width: overlay.clientWidth, height: overlay.clientHeight }, true);
      return;
    }
    if (!s.draft) return;
    const pt = toPoint(x, y);
    if (!pt) return;
    if (s.stage === "third") { s.draft.pts[2] = pt; repaint(); return; }
    if (s.stage === "second") { s.draft.pts[1] = pt; repaint(); return; }
    if (!pressed) return;
    if (kind === "free") {
      if (lastXY && Math.hypot(x - lastXY[0], y - lastXY[1]) < 2) return;
      s.draft.pts.push(pt); lastXY = [x, y];
    } else if (kind === "one") {
      s.draft.pts[0] = pt;
    } else if (kind === "two" || kind === "three") {
      s.draft.pts[1] = pt;
    }
    repaint();
  });
  const finish = (e) => {
    if (!pressed) return;
    pressed = false;
    const kind = kindOf(s.tool);
    if (kind === "erase" || !s.draft) return;
    const [x, y] = where(e);
    const moved = downAt ? Math.hypot(x - downAt[0], y - downAt[1]) : 0;
    if (kind === "free") { if (s.draft.pts.length === 1) s.draft.pts.push({ ...s.draft.pts[0] }); commit(s.draft); return; }
    if (kind === "one") { commit(s.draft); return; }
    if (kind === "text") { askText(s.draft, x, y); return; }
    if (kind === "two" || kind === "three") {
      if (moved < 4) { s.stage = "second"; repaint(); return; }       // a tap: wait for the second tap
      if (kind === "three") { s.stage = "third"; s.draft.pts[2] = s.draft.pts[1]; repaint(); return; }
      commit(s.draft);
    }
  };
  overlay.addEventListener("pointerup", finish);
  overlay.addEventListener("pointercancel", () => { pressed = false; });
  overlay.addEventListener("wheel", (e) => e.preventDefault(), { passive: false });

  // ---- text notes: a small box where the note goes
  const askText = (draft, x, y) => {
    const box = document.createElement("textarea");
    box.rows = 2;
    box.maxLength = 200;
    box.placeholder = T("Type a note, then Enter");
    box.style.cssText = `position:absolute;z-index:6;left:${Math.min(x, overlay.clientWidth - 200) + parseFloat(overlay.style.left || 0)}px;` +
      `top:${y}px;width:190px;font:13px system-ui,sans-serif;padding:4px 6px;border-radius:6px;` +
      `border:1px solid ${theme.grid};background:${theme.bg};color:${theme.ink};`;
    host.appendChild(box);
    box.focus();
    setTimeout(() => box.focus(), 30);
    let done = false;
    const end = (keep) => {
      if (done) return;
      done = true;
      const text = box.value.trim();
      box.remove();
      if (keep && text) { draft.text = text; commit(draft); } else { s.draft = null; repaint(); }
    };
    box.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); end(true); }
      if (e.key === "Escape") end(false);
    });
    box.addEventListener("blur", () => setTimeout(() => { if (document.activeElement !== box) end(true); }, 120));
  };

  // ---- the toolbar
  const btn = (label, tip, on, onClick, extra = "") => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.title = tip;
    b.setAttribute("aria-label", tip);
    b.style.cssText = `min-width:30px;height:30px;padding:0 6px;border-radius:6px;font-size:15px;line-height:1;cursor:pointer;` +
      `touch-action:manipulation;border:1px solid ${on ? "#2962ff" : theme.grid};` +
      `background:${on ? (theme.dark ? "rgba(41,98,255,.28)" : "rgba(41,98,255,.12)") : theme.bg};color:${theme.ink};${extra}`;
    b.onclick = onClick;
    return b;
  };
  const gap = () => { const g = document.createElement("span"); g.style.cssText = `width:1px;align-self:stretch;margin:2px 3px;background:${theme.grid};`; return g; };
  const statusEl = document.createElement("span");
  statusEl.style.cssText = `font:11px system-ui,sans-serif;color:${theme.muted};margin-left:4px;align-self:center;`;
  s.status = (text) => { statusEl.textContent = text; };
  let confirmClear = false;

  const setTool = (id) => {
    s.tool = id === "pan" ? null : id;
    s.draft = null; s.stage = null;
    overlay.style.display = s.tool ? "block" : "none";
    overlay.style.cursor = s.tool === "erase" ? "cell" : "crosshair";
    if (s.tool && s.hidden) { s.hidden = false; setDrawPref("hidden", false); paintEye(); }
    placeOverlay();
    repaint();
    paintBar();
  };

  const paintBar = () => {
    bar.innerHTML = "";
    const open = drawPref("open", false);
    bar.style.display = open ? "flex" : "none";
    if (!open) return;
    for (const [id, icon, tip] of DRAW_TOOLS) {
      bar.appendChild(btn(icon, T(tip), (s.tool || "pan") === id, () => setTool(id)));
      if (id === "erase" || id === "circle") bar.appendChild(gap());
    }
    if (s.tool === "marker") {
      bar.appendChild(gap());
      for (const m of DRAW_MARKS) bar.appendChild(btn(m, T("Stamp {mark}", {mark: m}), s.mark === m, () => { s.mark = m; setDrawPref("mark", m); paintBar(); }));
    }
    bar.appendChild(gap());
    for (const c of DRAW_COLOURS) {
      const b = btn("", T("Colour {c}", {c: c}), s.colour === c, () => { s.colour = c; setDrawPref("colour", c); paintBar(); },
        `min-width:22px;width:22px;height:22px;padding:0;align-self:center;border-radius:50%;background:${c};` +
        (s.colour === c ? "outline:2px solid #2962ff;outline-offset:2px;" : ""));
      bar.appendChild(b);
    }
    bar.appendChild(gap());
    for (const [w, words] of DRAW_WIDTHS) {
      bar.appendChild(btn(["─", "━", "▬"][DRAW_WIDTHS.findIndex((x) => x[0] === w)], T(words), s.width === w,
        () => { s.width = w; setDrawPref("width", w); paintBar(); }));
    }
    bar.appendChild(gap());
    bar.appendChild(btn("↶", T("Undo"), false, () => {
      if (!s.history.length) return;
      s.items = s.history.pop(); record.items = s.items; repaint(); saveDrawings(s); paintBar();
    }, s.history.length ? "" : "opacity:.45;"));
    bar.appendChild(btn(confirmClear ? T("Clear all?") : "🗑", confirmClear ? T("Press again to remove every drawing on this asset") :
      T("Remove every drawing on this asset"), confirmClear, () => {
      if (!confirmClear) { confirmClear = true; paintBar(); setTimeout(() => { confirmClear = false; paintBar(); }, 3000); return; }
      confirmClear = false; setItems([]);
    }));
    if (conf.share) {
      bar.appendChild(btn("📤", T("Share this chart and its drawings with your communities"), false, () => {
        if (!s.items.length) { s.status(T("Draw something first.")); return; }
        if (s.trigger) s.trigger("share", JSON.stringify({ asset: s.asset, items: s.items, nonce: Date.now() + Math.random() }));
      }));
    }
    bar.appendChild(statusEl);
  };

  // ---- ✏️ and 👁 beside ⟲ and ⇥
  // A line pencil like its neighbours (not the coloured emoji): grey while the drawing tools are closed, orange when open.
  const pen = toolButton("", T("Drawing tools: lines, shapes, pen, notes, Fibonacci and more"), theme);
  pen.innerHTML = "<svg viewBox='0 0 24 24' width='16' height='16' aria-hidden='true' fill='none' stroke='currentColor' "
    + "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' style='vertical-align:middle'>"
    + "<path d='M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4z'/><path d='M14.5 5.5l3 3'/></svg>";
  const paintPen = () => {
    const open = drawPref("open", false);
    pen.style.color = open ? "#f59e0b" : theme.ink;
    pen.style.borderColor = open ? "#f59e0b" : theme.grid;
    pen.setAttribute("aria-pressed", open ? "true" : "false");
  };
  pen.onclick = () => { const open = !drawPref("open", false); setDrawPref("open", open); if (!open) setTool("pan"); paintPen(); paintBar(); };
  paintPen();
  const eye = toolButton("👁", "", theme);
  const paintEye = () => {
    eye.textContent = s.hidden ? "🙈" : "👁";
    eye.title = s.hidden ? T("Drawings are hidden: press to show them") : T("Hide the drawings");
    eye.setAttribute("aria-label", eye.title);
  };
  eye.onclick = () => { s.hidden = !s.hidden; setDrawPref("hidden", s.hidden); paintEye(); repaint(); };
  paintEye();
  tools.insertBefore(eye, tools.firstChild);
  tools.insertBefore(pen, tools.firstChild);
  if (root.__drawKeys) document.removeEventListener("keydown", root.__drawKeys);
  root.__drawKeys = (e) => {
    if (e.key === "Escape" && s.tool && !(e.target.closest && e.target.closest("textarea,input"))) {
      s.draft = null; s.stage = null; repaint();
    }
  };
  document.addEventListener("keydown", root.__drawKeys);
  paintBar();
}

// TradingView Lightweight Charts price chart for the dashboard (Streamlit component v2).
// Python sends finished numbers (lw_chart.build_payload); this file only draws them.
// The library (Apache 2.0) is served from /app/static/lwc/ and shows TradingView's attribution logo.

const STORE = window.__angLwc || (window.__angLwc = { views: new Map() });

// ------------------------------------------------------------------ small helpers

const STYLE = { solid: 0, dotted: 1, dashed: 2 };

function withAlpha(colour, alpha) {
  if (alpha >= 1 || !colour) return colour;
  if (colour[0] === "#" && colour.length === 7) {
    const n = parseInt(colour.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
  }
  return colour;
}

function fmt(value, ref) {
  if (value === null || value === undefined || !isFinite(value)) return "–";
  const size = Math.abs(ref === undefined ? value : ref);
  let digits = 2;
  if (size >= 1000) digits = 2;
  else if (size >= 1) digits = 2;
  else if (size >= 0.01) digits = 4;
  else digits = 6;
  return Number(value).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtBig(value) {
  if (value === null || value === undefined || !isFinite(value)) return "–";
  const a = Math.abs(value);
  if (a >= 1e9) return (value / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return (value / 1e6).toFixed(2) + "M";
  if (a >= 1e3) return (value / 1e3).toFixed(1) + "K";
  return Number(value).toFixed(0);
}

function timeText(seconds, intraday) {
  const d = new Date(seconds * 1000);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const day = `${String(d.getUTCDate()).padStart(2, "0")} ${months[d.getUTCMonth()]} '${String(d.getUTCFullYear()).slice(2)}`;
  if (!intraday) return day;
  return `${day} ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}

function signature(data) {
  // Same signature = nothing to redraw (a rerun that changed nothing).
  const n = data.times.length;
  const c = data.ohlc[3];
  return JSON.stringify([
    data.key, n, data.times[0], data.times[n - 1], c[n - 1], data.ohlc[1][n - 1], data.ohlc[2][n - 1],
    data.volume[n - 1], data.forming, data.series.map((s) => s.id + ":" + s.pane + ":" + (s.scale || "")),
    data.panes.map((p) => p.height), data.vlines.length, data.price_lines.map((p) => p.price + (p.label || "")).join(","), data.theme.dark, data.theme.bg, data.right_offset,
    (data.zones || []).map((z) => z || "").join("|").length, data.series.map((s) => (s.zones || []).filter((z) => z).length),
    data.zones_name || "", !!data.fvg, (data.single_prints || []).map((z) => z.from + ":" + z.top + ":" + z.bottom).join(","), (data.symbols || []).length, (data.shapes || []).length,
  ]);
}

// ------------------------------------------------------------------ the band (cloud / Bollinger fill)

class BandRenderer {
  constructor() { this.data = null; this.options = null; }
  update(data, options) { this.data = data; this.options = options; }
  draw(target, priceToY) {
    const data = this.data;
    if (!data || !data.visibleRange || !data.bars.length) return;
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const hr = scope.horizontalPixelRatio, vr = scope.verticalPixelRatio;
      ctx.fillStyle = this.options.fill;
      const from = Math.max(0, data.visibleRange.from - 1), to = Math.min(data.bars.length, data.visibleRange.to + 1);
      let run = [];
      const flush = () => {
        if (run.length > 1) {
          ctx.beginPath();
          run.forEach((p, i) => (i ? ctx.lineTo(p.x * hr, priceToY(p.a) * vr) : ctx.moveTo(p.x * hr, priceToY(p.a) * vr)));
          for (let i = run.length - 1; i >= 0; i--) ctx.lineTo(run[i].x * hr, priceToY(run[i].b) * vr);
          ctx.closePath();
          ctx.fill();
        }
        run = [];
      };
      for (let i = from; i < to; i++) {
        const bar = data.bars[i];
        const row = bar.originalData;
        if (row && row.a !== undefined && row.b !== undefined) run.push({ x: bar.x, a: row.a, b: row.b });
        else flush();
      }
      flush();
    });
  }
}

class BandSeries {
  constructor(L) { this.L = L; this._renderer = new BandRenderer(); }
  renderer() { return this._renderer; }
  update(data, options) { this._renderer.update(data, options); }
  priceValueBuilder(row) { return [Math.min(row.a, row.b), Math.max(row.a, row.b), row.b]; }
  isWhitespace(row) { return row.a === undefined || row.b === undefined; }
  defaultOptions() { return Object.assign({}, this.L.customSeriesDefaultOptions, { fill: "rgba(128,128,128,0.1)" }); }
  destroy() {}
}

// ------------------------------------------------------------------ vertical lines (earnings)

class VerticalLines {
  constructor(lines, showLabels, ink) { this.lines = lines; this.showLabels = showLabels; this.ink = ink; this.chart = null; }
  attached(params) { this.chart = params.chart; }
  detached() { this.chart = null; }
  updateAllViews() {}
  paneViews() {
    const self = this;
    return [{
      zOrder: () => "bottom",
      renderer: () => ({
        draw: (target) => {
          if (!self.chart) return;
          const scale = self.chart.timeScale();
          target.useBitmapCoordinateSpace((scope) => {
            const ctx = scope.context;
            for (const line of self.lines) {
              const x = scale.logicalToCoordinate(line.index);
              if (x === null || x < 0 || x > scope.mediaSize.width) continue;
              const px = Math.round(x * scope.horizontalPixelRatio) + 0.5;
              ctx.save();
              ctx.strokeStyle = line.color;
              ctx.globalAlpha = line.style === "dashed" ? 0.9 : 0.6;
              ctx.lineWidth = Math.max(1, line.width * scope.horizontalPixelRatio);
              const dash = line.style === "dotted" ? [2, 4] : line.style === "dashed" ? [7, 5] : [];
              ctx.setLineDash(dash.map((v) => v * scope.horizontalPixelRatio));
              ctx.beginPath();
              ctx.moveTo(px, 0);
              ctx.lineTo(px, scope.bitmapSize.height);
              ctx.stroke();
              if (self.showLabels && line.label) {
                ctx.setLineDash([]);
                ctx.globalAlpha = 1;
                ctx.fillStyle = line.color;
                ctx.font = `${12 * scope.verticalPixelRatio}px sans-serif`;
                ctx.textAlign = "right";
                ctx.font = `${(line.event ? 10 : 12) * scope.verticalPixelRatio}px sans-serif`;
                const y = line.label_y < 0 ? scope.mediaSize.height + line.label_y : (line.label_y || 78);   // below 0: from the bottom
                ctx.fillText(line.label, px - 4 * scope.horizontalPixelRatio, y * scope.verticalPixelRatio);
              }
              ctx.restore();
            }
          });
        },
      }),
    }];
  }
}

// ------------------------------------------------------------------ Set bands (solid blocks behind the candles)

class ZoneBlocks {
  constructor(colors) {
    // Runs of the same colour: [first bar, last bar, colour].
    this.runs = [];
    colors.forEach((c, i) => {
      const last = this.runs[this.runs.length - 1];
      if (c && last && last[2] === c && last[1] === i - 1) last[1] = i;
      else if (c) this.runs.push([i, i, c]);
    });
    this.chart = null;
  }
  attached(params) { this.chart = params.chart; }
  detached() { this.chart = null; }
  updateAllViews() {}
  paneViews() {
    const self = this;
    return [{
      zOrder: () => "bottom",
      renderer: () => ({
        draw: (target) => {
          if (!self.chart) return;
          const scale = self.chart.timeScale();
          target.useBitmapCoordinateSpace((scope) => {
            const ctx = scope.context;
            for (const [a, b, colour] of self.runs) {
              const ca = scale.logicalToCoordinate(a), cb = scale.logicalToCoordinate(b);
              if (ca === null || cb === null) continue;
              const half = (self.chart.timeScale().options().barSpacing || 6) / 2;
              const x0 = ca - half, x1 = cb + half;
              if (x1 < 0 || x0 > scope.mediaSize.width) continue;
              ctx.fillStyle = colour;
              const left = Math.round(x0 * scope.horizontalPixelRatio);
              ctx.fillRect(left, 0, Math.max(1, Math.round(x1 * scope.horizontalPixelRatio) - left), scope.bitmapSize.height);
            }
          });
        },
      }),
    }];
  }
}

// ------------------------------------------------------------------ 🛰️ Sonar markers (drawn over the candles)

class SonarSymbols {
  // symbols: [candle index, shape, colour, above, size, words]; highs and lows place them clear of the wicks.
  constructor(symbols, highs, lows) {
    this.symbols = symbols; this.highs = highs; this.lows = lows;
    this.chart = null; this.series = null;
  }
  attached(params) { this.chart = params.chart; this.series = params.series; }
  detached() { this.chart = null; this.series = null; }
  updateAllViews() {}
  paneViews() {
    const self = this;
    return [{
      zOrder: () => "top",
      renderer: () => ({
        draw: (target) => {
          if (!self.chart || !self.series) return;
          const scale = self.chart.timeScale();
          const spacing = scale.options().barSpacing || 6;
          const base = Math.max(4.5, Math.min(8, spacing * 0.5));
          const stack = {};
          target.useBitmapCoordinateSpace((scope) => {
            const ctx = scope.context, hr = scope.horizontalPixelRatio, vr = scope.verticalPixelRatio;
            for (const [i, shape, colour, above, size] of self.symbols) {
              const x = scale.logicalToCoordinate(i);
              if (x === null || x < -10 || x > scope.mediaSize.width + 10) continue;
              const price = above ? self.highs[i] : self.lows[i];
              if (price === null || price === undefined) continue;
              const yEdge = self.series.priceToCoordinate(price);
              if (yEdge === null) continue;
              const r = base * size;
              const slot = `${i}:${above ? 1 : 0}`;
              const k = stack[slot] || 0;
              stack[slot] = k + 1;
              const gap = 4 + r + k * (2 * base + 3);
              const y = above ? yEdge - gap : yEdge + gap;
              const X = x * hr, Y = y * vr, R = r * hr;
              ctx.fillStyle = colour; ctx.strokeStyle = colour;
              ctx.beginPath();
              if (shape === "triangle_up") { ctx.moveTo(X, Y - R); ctx.lineTo(X + R, Y + R * 0.8); ctx.lineTo(X - R, Y + R * 0.8); ctx.closePath(); ctx.fill(); }
              else if (shape === "triangle_down") { ctx.moveTo(X, Y + R); ctx.lineTo(X + R, Y - R * 0.8); ctx.lineTo(X - R, Y - R * 0.8); ctx.closePath(); ctx.fill(); }
              else if (shape === "diamond") { ctx.moveTo(X, Y - R); ctx.lineTo(X + R * 0.8, Y); ctx.lineTo(X, Y + R); ctx.lineTo(X - R * 0.8, Y); ctx.closePath(); ctx.fill(); }
              else if (shape === "circle") { ctx.arc(X, Y, R * 0.75, 0, Math.PI * 2); ctx.fill(); }
              else if (shape === "star") {
                for (let k = 0; k < 10; k++) {
                  const a = -Math.PI / 2 + k * Math.PI / 5, rr = k % 2 ? R * 0.42 : R;
                  if (k) ctx.lineTo(X + rr * Math.cos(a), Y + rr * Math.sin(a)); else ctx.moveTo(X + rr * Math.cos(a), Y + rr * Math.sin(a));
                }
                ctx.closePath(); ctx.fill();
              }
              else if (shape === "x") {
                ctx.lineWidth = Math.max(2, R * 0.38); ctx.lineCap = "round";
                ctx.moveTo(X - R * 0.8, Y - R * 0.8); ctx.lineTo(X + R * 0.8, Y + R * 0.8);
                ctx.moveTo(X + R * 0.8, Y - R * 0.8); ctx.lineTo(X - R * 0.8, Y + R * 0.8); ctx.stroke();
              }
            }
          });
        },
      }),
    }];
  }
}

// ------------------------------------------------------------------ 📐 chart shapes (outline, neckline, target)

// 🕳️ Fair value gaps (19 Nov 2026): a three-candle gap a fast move leaves behind. Up: the third candle's low is above
// the first candle's high; down: the third candle's high is below the first's low. Shaded from the middle candle to
// the right until price trades back through it (a part filled shrinks it). Only gaps still open, at least 0.15% of
// the price, the newest 40.
const FVG_MIN = 0.0015, FVG_MAX = 40;
function fairValueGaps(data) {
  const [, H, Lo] = data.ohlc, n = data.times.length, gaps = [];
  for (let i = 2; i < n; i++) {
    if (Lo[i] > H[i - 2] && (Lo[i] - H[i - 2]) / H[i - 2] >= FVG_MIN) gaps.push({ up: true, from: i - 1, top: Lo[i], bottom: H[i - 2] });
    else if (H[i] < Lo[i - 2] && (Lo[i - 2] - H[i]) / Lo[i - 2] >= FVG_MIN) gaps.push({ up: false, from: i - 1, top: Lo[i - 2], bottom: H[i] });
  }
  const open = [];
  for (const g of gaps) {
    let filled = false;
    for (let k = g.from + 2; k < n && !filled; k++) {
      if (g.up) { if (Lo[k] <= g.bottom) filled = true; else if (Lo[k] < g.top) g.top = Lo[k]; }
      else { if (H[k] >= g.top) filled = true; else if (H[k] > g.bottom) g.bottom = H[k]; }
    }
    if (!filled && g.top > g.bottom) open.push(g);
  }
  return open.slice(-FVG_MAX);
}

class FairValueGaps {
  constructor(gaps, fill, edge) { this.gaps = gaps; this.fill = fill; this.edge = edge; this.chart = null; this.series = null; }
  attached(params) { this.chart = params.chart; this.series = params.series; }
  detached() { this.chart = null; this.series = null; }
  updateAllViews() {}
  paneViews() {
    const self = this;
    return [{
      zOrder: () => "bottom",
      renderer: () => ({
        draw: (target) => {
          if (!self.chart || !self.series) return;
          const scale = self.chart.timeScale();
          target.useBitmapCoordinateSpace((scope) => {
            const ctx = scope.context, hr = scope.horizontalPixelRatio, vr = scope.verticalPixelRatio;
            const right = scope.bitmapSize.width;
            for (const g of self.gaps) {
              const x = scale.logicalToCoordinate(g.from), y1 = self.series.priceToCoordinate(g.top), y2 = self.series.priceToCoordinate(g.bottom);
              if (x === null || y1 === null || y2 === null) continue;
              const yTop = Math.min(y1, y2) * vr, h = Math.max(1, Math.abs(y2 - y1) * vr);
              ctx.fillStyle = self.fill ? self.fill(g) : g.up ? "rgba(8,153,129,0.16)" : "rgba(242,54,69,0.16)";
              ctx.fillRect(x * hr, yTop, right - x * hr, h);
              if (self.edge) {                       // single prints: a dotted outline so they read apart from gaps
                ctx.strokeStyle = self.edge; ctx.lineWidth = hr; ctx.setLineDash([3 * hr, 3 * hr]);
                ctx.strokeRect(x * hr, yTop, right - x * hr, h); ctx.setLineDash([]);
              }
            }
          });
        },
      }),
    }];
  }
}

class ShapeLines {
  constructor(shapes, dark) { this.shapes = shapes; this.dark = dark; this.chart = null; this.series = null; }
  attached(params) { this.chart = params.chart; this.series = params.series; }
  detached() { this.chart = null; this.series = null; }
  updateAllViews() {}
  paneViews() {
    const self = this;
    return [{
      zOrder: () => "top",
      renderer: () => ({
        draw: (target) => {
          if (!self.chart || !self.series) return;
          const scale = self.chart.timeScale();
          const xy = ([i, p]) => [scale.logicalToCoordinate(i), self.series.priceToCoordinate(p)];
          target.useBitmapCoordinateSpace((scope) => {
            const ctx = scope.context, hr = scope.horizontalPixelRatio, vr = scope.verticalPixelRatio;
            for (const s of self.shapes) {
              const failed = s.stage === "failed";
              const colour = failed ? "rgba(148,163,184,0.85)" : s.bear ? "#e11d48" : "#059669";
              const pts = s.points.map(xy);
              if (pts.some(([x, y]) => x === null || y === null)) continue;
              ctx.save();
              ctx.globalAlpha = failed ? 0.6 : 0.95;
              ctx.strokeStyle = colour; ctx.lineWidth = 2 * hr; ctx.lineJoin = "round";
              ctx.setLineDash(s.stage === "forming" ? [6 * hr, 4 * hr] : []);
              ctx.beginPath();
              pts.forEach(([x, y], k) => { if (k) ctx.lineTo(x * hr, y * vr); else ctx.moveTo(x * hr, y * vr); });
              ctx.stroke();
              const [n0, n1] = s.neck.map(xy);
              if (n0[0] !== null && n1[0] !== null && n0[1] !== null && n1[1] !== null) {
                ctx.setLineDash([3 * hr, 3 * hr]); ctx.lineWidth = 1.5 * hr;
                ctx.beginPath(); ctx.moveTo(n0[0] * hr, n0[1] * vr); ctx.lineTo(n1[0] * hr, n1[1] * vr); ctx.stroke();
              }
              if (s.at !== null && s.at !== undefined && !failed) {
                const [tx0, ty] = xy([s.at, s.target]), [tx1] = xy([s.at + 12, s.target]);
                if (tx0 !== null && ty !== null && tx1 !== null) {
                  ctx.setLineDash([2 * hr, 4 * hr]); ctx.lineWidth = 1.25 * hr;
                  ctx.beginPath(); ctx.moveTo(tx0 * hr, ty * vr); ctx.lineTo(tx1 * hr, ty * vr); ctx.stroke();
                }
              }
              const top = s.points.reduce((a, b) => (s.bear ? (b[1] > a[1] ? b : a) : (b[1] < a[1] ? b : a)));
              const [lx, ly] = xy(top);
              if (lx !== null && ly !== null) {
                const tag = { head_shoulders: "H&S", inverse_head_shoulders: "Inv H&S", double_top: T("Double top"), double_bottom: T("Double bottom") }[s.kind];
                ctx.setLineDash([]); ctx.globalAlpha = 1;
                ctx.font = `600 ${11 * vr}px sans-serif`; ctx.textAlign = "center";
                ctx.fillStyle = colour;
                ctx.fillText(tag + (s.stage === "forming" ? " ?" : ""), lx * hr, (ly + (s.bear ? -12 : 20)) * vr);
              }
              ctx.restore();
            }
          });
        },
      }),
    }];
  }
}

// ------------------------------------------------------------------ view memory

function saveView(key, chart, times, extra) {
  const range = chart.timeScale().getVisibleLogicalRange();
  if (!range) return;
  const last = times.length - 1 + extra;
  const view = {
    atEnd: range.to >= last - 0.5,
    fromEnd: last - range.from,
    toEnd: last - range.to,
    fromTime: times[Math.max(0, Math.min(times.length - 1, Math.round(range.from)))],
    toTime: times[Math.max(0, Math.min(times.length - 1, Math.round(range.to)))],
  };
  STORE.views.set(key, view);
  try { sessionStorage.setItem("ang-lwc:" + key, JSON.stringify(view)); } catch (e) { /* private mode */ }
}

function loadView(key) {
  if (STORE.views.has(key)) return STORE.views.get(key);
  try {
    const raw = sessionStorage.getItem("ang-lwc:" + key);
    if (raw) return JSON.parse(raw);
  } catch (e) { /* private mode */ }
  return null;
}

// ⏱ Under the latest price on the right: the time left until the forming candle closes, counting down each second
// (as TradingView shows it). data.closes_at is that moment in milliseconds (lw_chart.candle_closes_at).
const LABEL_HALF = 8;

function candleCountdown(root, host, chart, candles, data, theme) {
  if (root.__countdown) { clearInterval(root.__countdown); root.__countdown = null; }
  const old = host.querySelector(".ang-lwc-countdown");
  if (old) old.remove();
  if (!data.forming || !data.closes_at) return;
  const n = data.times.length;
  if (data.ohlc[3][n - 1] === null || data.ohlc[3][n - 1] === undefined) return;
  const tag = document.createElement("div");
  tag.className = "ang-lwc-countdown";
  tag.title = T("Time left until this candle closes");
  tag.style.cssText = "position:absolute;right:0;z-index:4;pointer-events:none;text-align:center;" +
    "font:11px/16px system-ui,-apple-system,Segoe UI,sans-serif;font-variant-numeric:tabular-nums;color:#fff;" +
    "border-radius:0 0 2px 2px;";
  host.appendChild(tag);
  const two = (v) => String(v).padStart(2, "0");
  const words = (ms) => {
    if (ms <= 0) return "closing…";
    const t = Math.floor(ms / 1000);
    const d = Math.floor(t / 86400), h = Math.floor((t % 86400) / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
    if (d > 0) return `${d}d ${two(h)}h`;
    if (h > 0) return `${h}:${two(m)}:${two(sec)}`;
    return `${two(m)}:${two(sec)}`;
  };
  const tick = () => {
    if (!tag.isConnected) { clearInterval(root.__countdown); root.__countdown = null; return; }
    // The price label on the right shows the last candle in view (the newest one, or an older one when the chart is
    // scrolled back). Ask the chart for exactly that label's price and colour, so the countdown always matches it.
    let price = data.ohlc[3][n - 1], colour = data.ohlc[3][n - 1] >= data.ohlc[0][n - 1] ? theme.up : theme.down;
    try {
      const shown = candles.lastValueData(false);
      if (shown && !shown.noData) {
        price = shown.price;
        // The forming candle is drawn faded; its price label is solid, so drop the fade here too.
        if (shown.color) colour = String(shown.color).replace(/rgba\(([^,]+),([^,]+),([^,]+),[^)]+\)/, "rgb($1,$2,$3)");
      }
    } catch (e) { /* older library: the newest candle */ }
    tag.style.background = colour;
    const y = candles.priceToCoordinate(price);
    let width = 56;
    try { width = chart.priceScale("right").width() || width; } catch (e) { /* older library */ }
    const paneH = (data.panes[0] || {}).height || 0;
    tag.style.width = width + "px";
    tag.style.display = y === null || y < 0 || y > paneH - 10 ? "none" : "block";
    // Just under the price label: it is centred on the price and about 1.4 × the 11 px font tall.
    tag.style.top = (Math.round(y || 0) + LABEL_HALF) + "px";
    tag.textContent = words(data.closes_at - Date.now());
  };
  tick();
  root.__countdown = setInterval(tick, 1000);
  // After a scroll or zoom the price scale re-fits on the next frame: place the countdown once it has.
  chart.timeScale().subscribeVisibleLogicalRangeChange(() => requestAnimationFrame(() => requestAnimationFrame(tick)));
}

function indexOfTime(times, t) {
  let lo = 0, hi = times.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (times[mid] < t) lo = mid + 1; else hi = mid;
  }
  return lo;
}

// ------------------------------------------------------------------ page parts

function buildShell(parent) {
  const root = document.createElement("div");
  root.className = "ang-lwc";
  root.style.cssText = "position:relative;width:100%;touch-action:pan-y;";
  root.innerHTML =
    "<div class='ang-lwc-drawbar' style='display:none;flex-wrap:wrap;gap:4px;align-items:center;margin:0 0 6px;'></div>" +
    // The chart and what floats on it (legend, pane titles, buttons) share one box, so the drawing toolbar above
    // can grow to any number of rows without covering them.
    "<div class='ang-lwc-stage' style='position:relative;width:100%;'>" +
    "<div class='ang-lwc-host' style='position:relative;width:100%;'></div>" +
    "<div class='ang-lwc-legend' style='position:absolute;left:8px;top:6px;z-index:3;pointer-events:none;" +
    "font:12px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;max-width:calc(100% - 160px);'></div>" +
    "<div class='ang-lwc-panes'></div>" +
    "<div class='ang-lwc-tools' style='position:absolute;right:82px;top:6px;z-index:4;display:flex;gap:4px;'></div>" +
    "</div>" +
    "<div class='ang-lwc-note' style='font:12px/1.4 system-ui,sans-serif;margin:4px 2px 0;'></div>";
  parent.appendChild(root);
  return root;
}

function toolButton(label, tip, theme) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = label;
  b.title = tip;
  b.setAttribute("aria-label", tip);
  b.style.cssText =
    `min-width:34px;height:30px;border-radius:6px;border:1px solid ${theme.grid};background:${theme.bg};` +
    `color:${theme.ink};font-size:15px;cursor:pointer;opacity:.85;touch-action:manipulation;`;
  return b;
}

// ------------------------------------------------------------------ draw

function draw(L, root, data) {
  const host = root.querySelector(".ang-lwc-host");
  const legend = root.querySelector(".ang-lwc-legend");
  const paneLabels = root.querySelector(".ang-lwc-panes");
  const tools = root.querySelector(".ang-lwc-tools");
  const note = root.querySelector(".ang-lwc-note");
  const theme = data.theme;
  const n = data.times.length;

  if (root.__chart) {
    // Keep where the reader was looking before the redraw.
    saveView(root.__key, root.__chart, root.__times, root.__extra || 0);
    try { root.__chart.remove(); } catch (e) { /* already gone */ }
    root.__chart = null;
  }
  if (root.__ro) { root.__ro.disconnect(); root.__ro = null; }
  host.innerHTML = "";
  paneLabels.innerHTML = "";
  tools.innerHTML = "";

  if (!n) {
    note.textContent = T("No candles to draw.");
    return;
  }

  // 📱 On a phone the whole chart (price and every indicator pane) fits in about two-thirds of the screen, so there is
  // always page above or below it to scroll with: taller than the screen, a dark chart left nothing to grab and
  // looked like a black screen with no way back.
  if (window.matchMedia && window.matchMedia("(max-width: 760px)").matches) {
    const budget = Math.max(300, Math.round(window.innerHeight * 0.66) - 30);
    const sum = data.panes.reduce((a, p) => a + p.height, 0);
    if (sum > budget) {
      const f = budget / sum;
      data.panes = data.panes.map((p, i) => ({ ...p, height: Math.max(i === 0 ? 170 : 56, Math.round(p.height * f)) }));
    }
  }
  const totalHeight = data.panes.reduce((sum, p) => sum + p.height, 0) + 30;
  host.style.height = totalHeight + "px";
  const hasOsc = data.series.some((s) => s.scale === "osc");

  const chart = L.createChart(host, {
    autoSize: true,
    layout: {
      background: { type: "solid", color: theme.bg },
      textColor: theme.ink,
      fontSize: 11,
      attributionLogo: true,
      panes: { separatorColor: theme.grid, separatorHoverColor: theme.muted, enableResize: true },
    },
    grid: { vertLines: { color: theme.grid }, horzLines: { color: theme.grid } },
    rightPriceScale: { borderColor: theme.grid, scaleMargins: { top: 0.16, bottom: 0.08 }, mode: data.log_scale ? 1 : 0 },
    leftPriceScale: { visible: hasOsc, borderColor: theme.grid },
    timeScale: {
      borderColor: theme.grid, timeVisible: data.intraday, secondsVisible: false,
      rightOffset: 3, minBarSpacing: 0.5, shiftVisibleRangeOnNewBar: true,
    },
    crosshair: { mode: 0 },
    handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
    handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true, axisDoubleClickReset: true },
    kineticScroll: { touch: true, mouse: false },
    localization: { dateFormat: "dd MMM 'yy" },
  });

  // Candles. The unfinished last candle is drawn hollow-ish and named in the legend.
  const [O, H, Lo, C] = data.ohlc;
  const candleRows = [];
  for (let i = 0; i < n; i++) {
    if (O[i] === null || H[i] === null || Lo[i] === null || C[i] === null) { candleRows.push({ time: data.times[i] }); continue; }
    const row = { time: data.times[i], open: O[i], high: H[i], low: Lo[i], close: C[i] };
    if (data.forming && i === n - 1) {
      const up = C[i] >= O[i];
      row.color = up ? theme.up_faded : theme.down_faded;
      row.borderColor = up ? theme.up : theme.down;
      row.wickColor = up ? theme.up : theme.down;
    }
    candleRows.push(row);
  }
  const candles = chart.addSeries(L.CandlestickSeries, {
    upColor: theme.up, downColor: theme.down, borderUpColor: theme.up, borderDownColor: theme.down,
    wickUpColor: theme.up, wickDownColor: theme.down, priceLineVisible: true, lastValueVisible: true,
  }, 0);
  candles.setData(candleRows);
  if (data.pane_keys) {
    // Visualize History: tapping a small pane puts that asset on top.
    chart.subscribeClick((p) => {
      if (!p || !p.point) return;
      let pane = typeof p.paneIndex === "number" ? p.paneIndex : -1;
      if (pane < 0) {            // older library: work it out from the height
        let y = p.point.y, top = 0;
        chart.panes().forEach((x, i) => { const h = x.getHeight(); if (pane < 0 && y >= top && y < top + h) pane = i; top += h + 1; });
      }
      const key = data.pane_keys[pane];
      if (pane > 0 && key && root.__trigger) root.__trigger("pane", key);
    });
    host.title = T("Tap a small chart to put that asset on top");
  }
  if (data.zones && data.zones.some((c) => c)) candles.attachPrimitive(new ZoneBlocks(data.zones));
  if (data.symbols && data.symbols.length) candles.attachPrimitive(new SonarSymbols(data.symbols, H, Lo));
  if (data.shapes && data.shapes.length) candles.attachPrimitive(new ShapeLines(data.shapes, theme.dark));
  if (data.fvg) candles.attachPrimitive(new FairValueGaps(fairValueGaps(data)));
  // 📍 single prints (single_prints.py): violet, dotted edge
  if (data.single_prints && data.single_prints.length) {
    candles.attachPrimitive(new FairValueGaps(data.single_prints, () => "rgba(124,58,237,0.13)", "rgba(124,58,237,0.6)"));
  }
  const symbolWords = {};
  (data.symbols || []).forEach(([i, shape, colour, above, size, words]) => { (symbolWords[i] = symbolWords[i] || []).push([colour, words]); });

  const made = { candles };
  const paneFirst = { 0: candles };
  for (const s of data.series) {
    const rows = [];
    let options;
    let api;
    if (s.type === "band") {
      for (let i = 0; i < n; i++) {
        const a = s.a[i], b = s.b[i];
        rows.push(a === null || b === null ? { time: data.times[i] } : { time: data.times[i], a, b });
      }
      const bandOptions = { fill: s.fill, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false };
      const bandPane = data.panes[s.pane];
      if (s.pane > 0 && bandPane && bandPane.fixed) bandOptions.autoscaleInfoProvider = () => ({ priceRange: { minValue: bandPane.fixed[0], maxValue: bandPane.fixed[1] } });
      api = chart.addCustomSeries(new BandSeries(L), bandOptions, s.pane);
    } else if (s.type === "hist") {
      for (let i = 0; i < n; i++) {
        const v = s.values[i];
        rows.push(v === null ? { time: data.times[i] } : { time: data.times[i], value: v, color: s.colors ? s.colors[i] : undefined });
      }
      options = { priceLineVisible: false, lastValueVisible: false, base: s.base ?? 0 };
      if (s.id === "volume") options.priceFormat = { type: "volume" };
      const histPane = data.panes[s.pane];
      if (histPane && histPane.fixed) options.autoscaleInfoProvider = () => ({ priceRange: { minValue: histPane.fixed[0], maxValue: histPane.fixed[1] } });
      api = chart.addSeries(L.HistogramSeries, options, s.pane);
    } else {
      for (let i = 0; i < n; i++) {
        const v = s.values[i];
        if (v === null) rows.push({ time: data.times[i] });
        else rows.push(s.colors ? { time: data.times[i], value: v, color: s.colors[i] } : { time: data.times[i], value: v });
      }
      options = {
        color: withAlpha(s.color, s.alpha || 1), lineWidth: s.width >= 1.5 ? 2 : 1, lineStyle: STYLE[s.style] || 0,
        priceLineVisible: false, lastValueVisible: s.pane > 0, crosshairMarkerVisible: s.pane > 0,
      };
      if (s.type === "dots") {     // points only (Sonar pings): no line between them
        Object.assign(options, { lineVisible: false, pointMarkersVisible: true, pointMarkersRadius: s.radius || 3,
                                 lastValueVisible: false, crosshairMarkerVisible: false, color: s.colors ? s.colors[0] : "#888" });
      }
      if (s.scale === "osc") {
        options.priceScaleId = "left";
        options.autoscaleInfoProvider = () => ({ priceRange: { minValue: 0, maxValue: 100 } });
      }
      const pane = data.panes[s.pane];
      if (pane && pane.fixed) options.autoscaleInfoProvider = () => ({ priceRange: { minValue: pane.fixed[0], maxValue: pane.fixed[1] } });
      api = chart.addSeries(L.LineSeries, options, s.pane);
    }
    api.setData(rows);
    if (data.log_scale && s.type === "line" && s.pane > 0 && !String(s.id).startsWith("mc_")) { try { api.priceScale().applyOptions({ mode: 1 }); } catch (e) { /* older library */ } }
    if (s.zones && s.zones.some((c) => c)) api.attachPrimitive(new ZoneBlocks(s.zones));
    made[s.id] = api;
    if (paneFirst[s.pane] === undefined) paneFirst[s.pane] = api;
  }

  for (const g of data.guides) {
    const api = made[g.series];
    if (api) api.createPriceLine({ price: g.value, color: g.color, lineWidth: 1, lineStyle: STYLE[g.style] ?? 2, axisLabelVisible: false, title: "" });
  }
  for (const p of data.price_lines) {
    candles.createPriceLine({ price: p.price, color: p.color, lineWidth: p.width, lineStyle: STYLE[p.style] ?? 0,
                              axisLabelVisible: !!p.label, title: p.label || "" });
  }
  if (data.vlines.length) {
    Object.keys(paneFirst).forEach((pane) => {
      paneFirst[pane].attachPrimitive(new VerticalLines(data.vlines, Number(pane) === 0, theme.ink));
    });
  }

  // Pane heights: the price pane follows the account's chosen size.
  // Stretch factors are proportions, so they hold when the chart is first sized or resized.
  const sizePanes = () => {
    try {
      const panes = chart.panes();
      data.panes.forEach((p, i) => {
        if (!panes[i]) return;
        if (panes[i].setStretchFactor) panes[i].setStretchFactor(p.height);
        else panes[i].setHeight(p.height);
      });
    } catch (e) { /* older library: equal panes */ }
  };
  sizePanes();

  // ---------------------------------------------------------------- what the chart opens on
  const extra = data.right_offset || 0;
  const defaultView = () => {
    chart.timeScale().setVisibleLogicalRange({ from: data.start_index - 0.5, to: n - 1 + extra + 3 });
  };
  const view = loadView(data.key);
  if (view) {
    let from, to;
    if (view.atEnd) {
      from = n - 1 + extra - view.fromEnd;
      to = n - 1 + extra - view.toEnd;
    } else {
      from = indexOfTime(data.times, view.fromTime);
      to = indexOfTime(data.times, view.toTime);
    }
    if (isFinite(from) && isFinite(to) && to > from) chart.timeScale().setVisibleLogicalRange({ from, to });
    else defaultView();
  } else {
    defaultView();
  }
  let saveTimer = null;
  chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => saveView(data.key, chart, data.times, extra), 150);
  });

  // ---------------------------------------------------------------- legend
  const lastClosed = data.forming ? n - 2 : n - 1;
  const legendSeries = data.series.filter((s) => s.type === "line" && s.legend !== false && s.pane === 0);
  const paneSeries = {};
  data.series.filter((s) => s.pane > 0 && s.type !== "band" && s.legend !== false).forEach((s) => { (paneSeries[s.pane] = paneSeries[s.pane] || []).push(s); });

  const swatch = (colour) => `<span style="display:inline-block;width:9px;height:2px;background:${colour};vertical-align:middle;margin-right:3px"></span>`;
  const paintLegend = (index, hovering) => {
    const i = Math.max(0, Math.min(n - 1, index));
    const up = C[i] >= O[i];
    const tone = up ? theme.up : theme.down;
    const prev = i > 0 ? C[i - 1] : null;
    const change = prev ? ((C[i] - prev) / prev) * 100 : null;
    const forming = data.forming && i === n - 1;
    const state = forming
      ? `<span style="color:#f59e0b;font-weight:600" title="${T("This candle has not closed yet, so its values will still change.")}">● ${T("forming")}</span>`
      : (!hovering ? `<span style="color:${theme.muted}">${T("last closed")}</span>` : "");
    let html =
      `<div style="color:${theme.ink}"><b>${data.panes[0].title}</b> &nbsp;${timeText(data.times[i], data.intraday)} ${state}</div>` +
      `<div style="color:${theme.muted}">O <b style="color:${tone}">${fmt(O[i], C[i])}</b> H <b style="color:${tone}">${fmt(H[i], C[i])}</b> ` +
      `L <b style="color:${tone}">${fmt(Lo[i], C[i])}</b> C <b style="color:${tone}">${fmt(C[i], C[i])}</b>` +
      (change === null ? "" : ` <b style="color:${tone}">${change >= 0 ? "+" : ""}${change.toFixed(2)}%</b>`) +
      ` V <b style="color:${theme.ink}">${fmtBig(data.volume[i])}</b></div>`;
    const bits = legendSeries.map((s) => `${swatch(s.color)}<span style="color:${theme.muted}">${s.name}</span> <span style="color:${theme.ink}">${fmt(s.values[i], C[i])}</span>`);
    if (bits.length) html += `<div>${bits.join(" &nbsp;")}</div>`;
    (data.shapes || []).forEach((s) => {
      const from = s.points[0][0], to = Math.max(s.points[s.points.length - 1][0], s.at ?? 0) + 3;
      if (i >= from && i <= to) html += `<div style="color:${theme.ink}"><span style="color:${s.stage === "failed" ? "#94a3b8" : s.bear ? "#e11d48" : "#059669"}">📐</span> ${s.words}</div>`;
    });
    (symbolWords[i] || []).forEach(([colour, words]) => {
      html += `<div style="color:${theme.ink}"><span style="color:${colour}">●</span> ${words}</div>`;
    });
    if (data.zones_answers) {
      const a = data.zones_answers[i];
      const word = a === "yes" ? T("Yes") : a === "no" ? T("No") : a === "unknown" ? T("Unknown") : T("not worked out");
      const tint = a === "yes" ? "#16a34a" : a === "unknown" ? "#d97706" : theme.muted;
      html += `<div><span style="color:${theme.muted}">${data.zones_name}</span> <b style="color:${tint}">${word}</b></div>`;
    }
    legend.innerHTML = html;
    legend.style.background = theme.bg + "c0";      // the chart colour, slightly see-through
    legend.style.borderRadius = "6px";
    legend.style.padding = "2px 6px";
    paneLabels.querySelectorAll("[data-pane]").forEach((label) => {
      const pane = Number(label.dataset.pane);
      const parts = (paneSeries[pane] || []).map((s) => {
        const v = s.values[i];
        const shown = s.id === "volume" || s.id === "obv" || s.id === "obv_avg" ? fmtBig(v)
          : fmt(v, ["rsi", "stoch", "stochrsi_k", "stochrsi_d", "adx", "mc_rsi", "mc_sk"].includes(s.id) ? 100 : v);   // 0-100: 2 decimals
        const single = (paneSeries[pane] || []).length === 1;
        const name = single ? "" : s.name.replace("MACD histogram", "Hist");
        return name ? `<span style="color:${s.colors ? theme.muted : s.color}">${name}</span> ${shown}` : shown;
      });
      label.innerHTML = `<b>${data.panes[pane].title}</b> ${parts.join(" · ")}`;
    });
  };

  // Pane titles sit inside the top-left corner of each lower pane.
  const placePaneLabels = () => {
    paneLabels.innerHTML = "";
    let panes = [];
    try { panes = chart.panes(); } catch (e) { return; }
    const top0 = host.getBoundingClientRect().top;
    panes.forEach((pane, index) => {
      if (index === 0) return;
      let top = null;
      try {
        const el = pane.getHTMLElement();
        if (el) top = el.getBoundingClientRect().top - top0;
      } catch (e) { top = null; }
      if (top === null) return;
      const label = document.createElement("div");
      label.dataset.pane = String(index);
      label.style.cssText =
        `position:absolute;left:8px;top:${top + 3}px;z-index:3;pointer-events:none;font:11px/1.3 system-ui,sans-serif;` +
        `color:${theme.ink};background:${theme.bg}b3;padding:1px 5px;border-radius:4px;`;
      paneLabels.appendChild(label);
    });
  };
  requestAnimationFrame(() => { placePaneLabels(); paintLegend(lastClosed, false); });
  chart.subscribeCrosshairMove((param) => {
    if (param && param.logical !== undefined && param.logical !== null && param.point) {
      paintLegend(Math.round(param.logical), true);
    } else {
      paintLegend(lastClosed, false);
    }
  });
  const ro = new ResizeObserver(() => requestAnimationFrame(() => { placePaneLabels(); paintLegend(lastClosed, false); }));
  ro.observe(host);
  root.__ro = ro;

  // ---------------------------------------------------------------- buttons
  const reset = toolButton("⟲", T("Back to the chosen range"), theme);
  reset.onclick = () => {
    STORE.views.delete(data.key);
    try { sessionStorage.removeItem("ang-lwc:" + data.key); } catch (e) { /* private mode */ }
    defaultView();
  };
  const latest = toolButton("⇥", T("Scroll to the newest candle"), theme);
  latest.onclick = () => chart.timeScale().scrollToRealTime();
  tools.appendChild(reset);
  tools.appendChild(latest);

  // ---------------------------------------------------------------- the line under the chart
  const formingText = data.forming
    ? T("The newest candle is still forming (drawn faded); the legend shows the last closed candle until you point at it.") + " "
    : "";
  note.style.color = theme.muted;
  note.textContent =
    (data.zones_legend ? data.zones_legend + ". " : "") +
    `${data.source}. ${data.clock ? T("Times in {clock}.", {clock: data.clock}) + " " : ""}${formingText}` +
    T("Scroll or pinch to zoom, drag to move back in time, double-click the price scale to reset it.");

  try { setupDrawing(L, root, host, chart, candles, data, theme, hasOsc); } catch (e) { console.warn("drawings", e); }
  try { candleCountdown(root, host, chart, candles, data, theme); } catch (e) { /* the countdown is extra too */ }

  root.__chart = chart;
  root.__times = data.times;
  root.__key = data.key;
  root.__extra = extra;
  root.__sig = signature(data);
}



// Draw `data` into `parent` (building the chart's frame the first time). Returns a function that removes it all.
export function mount(parent, data) {
  let root = parent.querySelector(".ang-lwc");
  if (!root) root = buildShell(parent);
  draw(L, root, data);
  return () => {
    try { if (root.__chart) saveView(root.__key, root.__chart, root.__times, root.__extra || 0); } catch (e) { /* gone */ }
    if (root.__countdown) { clearInterval(root.__countdown); root.__countdown = null; }
    if (root.__ro) { root.__ro.disconnect(); root.__ro = null; }
    if (root.__drawRo) { root.__drawRo.disconnect(); root.__drawRo = null; }
    if (root.__drawKeys) { document.removeEventListener("keydown", root.__drawKeys); root.__drawKeys = null; }
    try { if (root.__chart) root.__chart.remove(); } catch (e) { /* already gone */ }
    root.__chart = null;
  };
}

// Drawings kept while the page is open, per asset (so a candle-size change keeps unsaved work).
export function forgetDrawings(asset) { DRAW_STORE.assets.delete(asset); }
