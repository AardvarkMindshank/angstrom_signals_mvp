// ✏️ Drawing on the price chart (13 Nov 2026): pen, highlighter, eraser, lines, shapes, markers, notes, Fibonacci,
// measure and long/short position, in a toolbar above the chart. Loaded in front of lw_chart.js (one module).
//
// Points are (time in seconds, price), so drawings stay put when the chart zooms or scrolls, and show on every
// candle size of the same asset. They save to the account (chart_drawings, sql/2026-11-27_chart_drawings.sql)
// straight from the browser with the person's own session, so drawing never reloads the page. If that fails, the
// chart hands them to the app instead ("drawings" trigger) and the app saves them.

const DRAW_TOOLS = [
  // [id, icon, tip, kind]   kind: free | erase | one | two | three | text
  ["pan", "✋", "Move the chart (no drawing tool)", "none"],
  ["pen", "✏️", "Pen: draw freely with a finger, Pencil or mouse", "free"],
  ["hl", "🖍️", "Highlighter: a wide, see-through pen", "free"],
  ["erase", "🧽", "Eraser: tap or drag across a drawing to remove it", "erase"],
  ["trend", "╱", "Trend line: drag from one point to another", "two"],
  ["ray", "↗", "Ray: a line from a point that runs on into the future", "two"],
  ["hline", "━", "Horizontal line: a price level across the chart", "one"],
  ["vline", "┃", "Vertical line: marks a date or time", "one"],
  ["channel", "⫽", "Parallel channel: drag the first line, then tap where the parallel line goes", "three"],
  ["arrow", "➚", "Arrow: drag from the tail to the point", "two"],
  ["box", "▭", "Box / zone: drag from one corner to the other", "two"],
  ["circle", "◯", "Circle: drag across what to circle", "two"],
  ["marker", "✖", "Marker: tap to stamp the mark chosen beside it", "one"],
  ["text", "🔤", "Text note: tap where the note goes, then type", "text"],
  ["fib", "📐", "Fibonacci retracement: drag from the swing low to the swing high (or high to low)", "two"],
  ["measure", "📏", "Measure: drag between two points to see the % change and the number of candles", "two"],
  ["position", "🎯", "Long / short position: drag from the entry to the stop, then tap the target", "three"],
];
const DRAW_COLOURS = ["#2962ff", "#f23645", "#089981", "#ff9800", "#9c27b0", "#00bcd4", "#e91e63", "#ffffff", "#131722"];
const DRAW_WIDTHS = [[1, "Thin"], [2, "Medium"], [4, "Thick"]];
const DRAW_MARKS = ["✖", "✔", "★", "▲", "▼", "●", "?", "!"];
const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.65, 0.786, 1];
const DRAW_MAX_ITEMS = 400;
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
    case "position": return inBox(P[0], [Math.max(P[1][0], P[0][0] + 60), P[1][1]]) || (P[2] && inBox(P[0], [P[0][0] + 60, P[2][1]]));
    case "marker": return Math.hypot(x - P[0][0], y - P[0][1]) <= 14;
    case "text": return x >= P[0][0] - 4 && x <= P[0][0] + 8 * String(it.text || "").length + 8 && y >= P[0][1] - 4 && y <= P[0][1] + 22;
    default: return false;
  }
}

// ------------------------------------------------------------------ saving

function saveDrawings(s) {
  clearTimeout(s.saveTimer);
  s.status("Saving…");
  s.saveTimer = setTimeout(async () => {
    const record = DRAW_STORE.assets.get(s.asset);
    if (record) record.savedAt = Date.now();
    const rest = s.rest || {};
    let ok = false;
    if (rest.url && rest.key && rest.token && rest.user) {
      try {
        const r = await fetch(`${rest.url}/rest/v1/chart_drawings?on_conflict=user_id,asset_key`, {
          method: "POST",
          headers: {
            apikey: rest.key, Authorization: `Bearer ${rest.token}`, "Content-Type": "application/json",
            Prefer: "resolution=merge-duplicates,return=minimal",
          },
          body: JSON.stringify({ user_id: rest.user, asset_key: s.asset, items: s.items, updated_at: new Date().toISOString() }),
        });
        ok = r.ok;
        if (!ok && r.status === 404) { s.status("Drawings can't be saved yet: the database update hasn't been run."); return; }
      } catch (e) { ok = false; }
    }
    if (!ok && s.trigger) {         // the app saves them instead (its session is refreshed on every run)
      s.trigger("drawings", JSON.stringify({ asset: s.asset, items: s.items, nonce: Date.now() + Math.random() }));
      s.status("Saved");
      return;
    }
    s.status(ok ? "Saved" : "Not saved: sign in again to keep these drawings.");
  }, 700);
}

// A rerun that changed only the drawings part (a shared chart opened or closed, drawings copied, a fresh session):
// update the layer in place instead of redrawing the chart.
function refreshDrawing(root, data) {
  const s = root.__draw;
  const conf = data.draw;
  if (!s || !conf || conf.asset !== s.asset) return;
  s.rest = conf.rest;
  s.trigger = root.__trigger;
  s.shared = Array.isArray(conf.shared) ? conf.shared : [];
  const record = DRAW_STORE.assets.get(s.asset);
  const savedAt = conf.updated ? Date.parse(conf.updated) : 0;
  if (record && savedAt && savedAt > (record.savedAt || 0) + 2000 && Array.isArray(conf.items)) {
    record.items = conf.items.slice(); record.savedAt = savedAt; s.items = record.items;
  }
  if (s.repaint) s.repaint();
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

  const T = data.times, n = T.length;
  const ts = chart.timeScale();
  const tToL = (t) => {
    if (n < 2) return 0;
    if (t <= T[0]) return (t - T[0]) / (T[1] - T[0]);
    if (t >= T[n - 1]) return n - 1 + (t - T[n - 1]) / (T[n - 1] - T[n - 2]);
    const i = indexOfTime(T, t);
    if (T[i] === t) return i;
    return i - 1 + (t - T[i - 1]) / (T[i] - T[i - 1]);
  };
  const lToT = (l) => {
    if (n < 2) return T[0] || 0;
    if (l <= 0) return T[0] + l * (T[1] - T[0]);
    if (l >= n - 1) return T[n - 1] + (l - (n - 1)) * (T[n - 1] - T[n - 2]);
    const i = Math.floor(l);
    return T[i] + (l - i) * (T[i + 1] - T[i]);
  };

  const s = {
    asset: conf.asset, rest: conf.rest, trigger: root.__trigger,
    items: record.items, draft: null, stage: null, shared: Array.isArray(conf.shared) ? conf.shared : [],
    tool: null, colour: drawPref("colour", DRAW_COLOURS[0]), width: drawPref("width", 2),
    mark: drawPref("mark", "✖"), hidden: drawPref("hidden", false), history: [],
    tToL,
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
    box.placeholder = "Type a note, then Enter";
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
      bar.appendChild(btn(icon, tip, (s.tool || "pan") === id, () => setTool(id)));
      if (id === "erase" || id === "circle") bar.appendChild(gap());
    }
    if (s.tool === "marker") {
      bar.appendChild(gap());
      for (const m of DRAW_MARKS) bar.appendChild(btn(m, `Stamp ${m}`, s.mark === m, () => { s.mark = m; setDrawPref("mark", m); paintBar(); }));
    }
    bar.appendChild(gap());
    for (const c of DRAW_COLOURS) {
      const b = btn("", `Colour ${c}`, s.colour === c, () => { s.colour = c; setDrawPref("colour", c); paintBar(); },
        `min-width:22px;width:22px;height:22px;padding:0;align-self:center;border-radius:50%;background:${c};` +
        (s.colour === c ? "outline:2px solid #2962ff;outline-offset:2px;" : ""));
      bar.appendChild(b);
    }
    bar.appendChild(gap());
    for (const [w, words] of DRAW_WIDTHS) {
      bar.appendChild(btn(["─", "━", "▬"][DRAW_WIDTHS.findIndex((x) => x[0] === w)], `${words} lines`, s.width === w,
        () => { s.width = w; setDrawPref("width", w); paintBar(); }));
    }
    bar.appendChild(gap());
    bar.appendChild(btn("↶", "Undo", false, () => {
      if (!s.history.length) return;
      s.items = s.history.pop(); record.items = s.items; repaint(); saveDrawings(s); paintBar();
    }, s.history.length ? "" : "opacity:.45;"));
    bar.appendChild(btn(confirmClear ? "Clear all?" : "🗑", confirmClear ? "Press again to remove every drawing on this asset" :
      "Remove every drawing on this asset", confirmClear, () => {
      if (!confirmClear) { confirmClear = true; paintBar(); setTimeout(() => { confirmClear = false; paintBar(); }, 3000); return; }
      confirmClear = false; setItems([]);
    }));
    if (conf.share) {
      bar.appendChild(btn("📤", "Share this chart and its drawings with your communities", false, () => {
        if (!s.items.length) { s.status("Draw something first."); return; }
        if (s.trigger) s.trigger("share", JSON.stringify({ asset: s.asset, items: s.items, nonce: Date.now() + Math.random() }));
      }));
    }
    bar.appendChild(statusEl);
  };

  // ---- ✏️ and 👁 beside ⟲ and ⇥
  const pen = toolButton("✏️", "Drawing tools: lines, shapes, pen, notes, Fibonacci and more", theme);
  pen.onclick = () => { const open = !drawPref("open", false); setDrawPref("open", open); if (!open) setTool("pan"); paintBar(); };
  const eye = toolButton("👁", "", theme);
  const paintEye = () => {
    eye.textContent = s.hidden ? "🙈" : "👁";
    eye.title = s.hidden ? "Drawings are hidden: press to show them" : "Hide the drawings";
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
