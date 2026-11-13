// TradingView Lightweight Charts price chart for the dashboard (Streamlit component v2).
// Python sends finished numbers (lw_chart.build_payload); this file only draws them.
// The library (Apache 2.0) is served from /app/static/lwc/ and shows TradingView's attribution logo.

const STORE = window.__angLwc || (window.__angLwc = { loading: null, views: new Map() });

function loadLibrary(url) {
  if (window.LightweightCharts) return Promise.resolve(window.LightweightCharts);
  if (!STORE.loading) {
    STORE.loading = new Promise((resolve, reject) => {
      const tag = document.createElement("script");
      tag.src = url;
      tag.async = true;
      tag.onload = () => (window.LightweightCharts ? resolve(window.LightweightCharts) : reject(new Error("empty")));
      tag.onerror = () => { STORE.loading = null; tag.remove(); reject(new Error("load")); };
      document.head.appendChild(tag);
    });
  }
  return STORE.loading;
}

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
    data.panes.map((p) => p.height), data.vlines.length, data.price_lines.length, data.theme.dark, data.right_offset,
    (data.zones || []).map((z) => z || "").join("|").length, data.series.map((s) => (s.zones || []).filter((z) => z).length),
    data.zones_name || "",
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
    note.textContent = "No candles to draw.";
    return;
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
    host.title = "Tap a small chart to put that asset on top";
  }
  if (data.zones && data.zones.some((c) => c)) candles.attachPrimitive(new ZoneBlocks(data.zones));

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
    candles.createPriceLine({ price: p.price, color: p.color, lineWidth: p.width, lineStyle: 0, axisLabelVisible: false, title: "" });
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
      ? `<span style="color:#f59e0b;font-weight:600" title="This candle has not closed yet, so its values will still change.">● forming</span>`
      : (!hovering ? `<span style="color:${theme.muted}">last closed</span>` : "");
    let html =
      `<div style="color:${theme.ink}"><b>${data.panes[0].title}</b> &nbsp;${timeText(data.times[i], data.intraday)} ${state}</div>` +
      `<div style="color:${theme.muted}">O <b style="color:${tone}">${fmt(O[i], C[i])}</b> H <b style="color:${tone}">${fmt(H[i], C[i])}</b> ` +
      `L <b style="color:${tone}">${fmt(Lo[i], C[i])}</b> C <b style="color:${tone}">${fmt(C[i], C[i])}</b>` +
      (change === null ? "" : ` <b style="color:${tone}">${change >= 0 ? "+" : ""}${change.toFixed(2)}%</b>`) +
      ` V <b style="color:${theme.ink}">${fmtBig(data.volume[i])}</b></div>`;
    const bits = legendSeries.map((s) => `${swatch(s.color)}<span style="color:${theme.muted}">${s.name}</span> <span style="color:${theme.ink}">${fmt(s.values[i], C[i])}</span>`);
    if (bits.length) html += `<div>${bits.join(" &nbsp;")}</div>`;
    if (data.zones_answers) {
      const a = data.zones_answers[i];
      const word = a === "yes" ? "Yes" : a === "no" ? "No" : a === "unknown" ? "Unknown" : "not worked out";
      const tint = a === "yes" ? "#16a34a" : a === "unknown" ? "#d97706" : theme.muted;
      html += `<div><span style="color:${theme.muted}">${data.zones_name}</span> <b style="color:${tint}">${word}</b></div>`;
    }
    legend.innerHTML = html;
    legend.style.background = theme.dark ? "rgba(38,39,48,0.75)" : "rgba(255,255,255,0.75)";
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
        `color:${theme.ink};background:${theme.dark ? "rgba(38,39,48,0.7)" : "rgba(255,255,255,0.7)"};padding:1px 5px;border-radius:4px;`;
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
  const reset = toolButton("⟲", "Back to the chosen range", theme);
  reset.onclick = () => {
    STORE.views.delete(data.key);
    try { sessionStorage.removeItem("ang-lwc:" + data.key); } catch (e) { /* private mode */ }
    defaultView();
  };
  const latest = toolButton("⇥", "Scroll to the newest candle", theme);
  latest.onclick = () => chart.timeScale().scrollToRealTime();
  tools.appendChild(reset);
  tools.appendChild(latest);

  // ---------------------------------------------------------------- the line under the chart
  const formingText = data.forming
    ? "The newest candle is still forming (drawn faded); the legend shows the last closed candle until you point at it. "
    : "";
  note.style.color = theme.muted;
  note.textContent =
    (data.zones_legend ? data.zones_legend + ". " : "") +
    `${data.source}. ${data.clock ? "Times in " + data.clock + ". " : ""}${formingText}` +
    "Scroll or pinch to zoom, drag to move back in time, double-click the price scale to reset it.";

  try { setupDrawing(L, root, host, chart, candles, data, theme, hasOsc); } catch (e) { /* drawings are extra: never break the chart */ }

  root.__chart = chart;
  root.__times = data.times;
  root.__key = data.key;
  root.__extra = extra;
  root.__sig = signature(data);
}

export default function (component) {
  const { data, parentElement } = component;
  if (!data || !data.times) return;
  let root = parentElement.querySelector(".ang-lwc");
  if (!root) root = buildShell(parentElement);
  root.__trigger = component.setTriggerValue;
  const sig = signature(data);
  if (root.__chart && root.__sig === sig) {        // nothing changed: keep the chart exactly as it is
    try { refreshDrawing(root, data); } catch (e) { /* drawings are extra */ }
    return;
  }
  loadLibrary(data.lib)
    .then((L) => draw(L, root, data))
    .catch(() => {
      const note = root.querySelector(".ang-lwc-note");
      if (note) note.textContent = "The TradingView chart could not load. You can switch to the Plotly chart in Settings.";
    });
}
