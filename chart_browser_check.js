// Browser test of the TradingView chart component (lw_chart.js) in headless Chromium.
// Runs locally and in CI. Touch is emulated (an iPad-sized touch screen with real
// two-finger touch events), which is useful but is NOT the same as a real iPad.
//
// Usage: node chart_browser_check.js <fixtures folder> <output folder>

const http = require("http");
const fs = require("fs");
const path = require("path");
const { chromium, devices } = require("playwright");

const ROOT = __dirname;
const FIX = path.resolve(process.argv[2] || "out/fixtures");
const OUT = path.resolve(process.argv[3] || "out");
fs.mkdirSync(OUT, { recursive: true });

const HARNESS = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;padding:16px;font-family:sans-serif} #mount{width:min(1000px,100%)} .spacer{height:1400px}</style></head>
<body><div id="mount"></div><div class="spacer"></div>
<script type="module">
import draw from "/lw_chart.js";
window.mountChart = async (name, fresh) => {
  const parent = document.getElementById("mount");
  if (fresh) parent.innerHTML = "";
  const data = await (await fetch("/fx/" + name + ".json")).json();
  draw({ data, parentElement: parent, setTriggerValue() {} });
  for (let i = 0; i < 100; i++) {
    const root = parent.querySelector(".ang-lwc");
    if (root && root.__chart && root.__sig) break;
    await new Promise((r) => setTimeout(r, 50));
  }
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  return true;
};
window.chartState = () => {
  const root = document.querySelector(".ang-lwc");
  const c = root && root.__chart;
  if (!c) return null;
  const r = c.timeScale().getVisibleLogicalRange();
  return { from: r.from, to: r.to, panes: c.panes().length, legend: root.querySelector(".ang-lwc-legend").innerText,
           note: root.querySelector(".ang-lwc-note").innerText, labels: [...root.querySelectorAll("[data-pane]")].map((e) => e.innerText),
           id: root.__chartId || (root.__chartId = Math.random()), canvases: root.querySelectorAll("canvas").length,
           attribution: !!root.querySelector("a[href*='tradingview']"), scrollY: window.scrollY,
           height: root.querySelector(".ang-lwc-host").getBoundingClientRect().height };
};
window.ready = true;
</script></body></html>`;

function serve() {
  const types = { ".js": "text/javascript", ".json": "application/json", ".html": "text/html" };
  const server = http.createServer((req, res) => {
    const url = decodeURIComponent(req.url.split("?")[0]);
    let file = null;
    if (url === "/" || url === "/index.html") {
      res.writeHead(200, { "content-type": "text/html" });
      return res.end(HARNESS);
    }
    if (url === "/lw_chart.js") file = path.join(ROOT, "lw_chart.js");
    else if (url.startsWith("/app/static/")) file = path.join(ROOT, "static", url.slice("/app/static/".length));
    else if (url.startsWith("/fx/")) file = path.join(FIX, path.basename(url));
    if (!file || !fs.existsSync(file)) { res.writeHead(404); return res.end("missing"); }
    res.writeHead(200, { "content-type": types[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

const results = [];
const fixture = (name) => JSON.parse(fs.readFileSync(path.join(FIX, name + ".json"), "utf8"));
const openSpan = (p) => (p.times.length - 1 + (p.right_offset || 0) + 3) - (p.start_index - 0.5);
function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail === undefined ? "" : String(detail) });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail === undefined ? "" : "  (" + detail + ")"}`);
}

async function chartBox(page) {
  const box = await page.locator(".ang-lwc-host").boundingBox();
  return box;
}

async function desktop(browser, base) {
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto(base);
  await page.waitForFunction(() => window.ready);

  const all = fixture("crypto_4h_all");
  const span = openSpan(all);
  const wantPanes = 1 + new Set(all.series.filter((x) => x.pane > 0).map((x) => x.pane)).size;
  await page.evaluate(() => window.mountChart("crypto_4h_all", true));
  let s = await page.evaluate(() => window.chartState());
  check("draws price pane plus volume, RSI, MACD, Stochastic, ADX, OBV panes", s && s.panes === wantPanes && wantPanes === 7, s && s.panes);
  check("opens on the chosen range", s && Math.abs((s.to - s.from) - span) < 2, s && `${(s.to - s.from).toFixed(1)} of ${span.toFixed(1)} candles`);
  check("legend shows last closed candle with OHLCV", s && (all.forming ? /last closed/.test(s.legend) : true) && /O .*H .*L .*C .*V /.test(s.legend.replace(/\n/g, " ")), s && s.legend.split("\n")[0]);
  check("note explains the forming candle (when there is one)", s && (/still forming/.test(s.note) === !!all.forming), all.forming);
  check("pane titles are placed", s && s.labels.length === 6 && /RSI/.test(s.labels.join(" ")), s && s.labels.join(" | "));
  check("TradingView attribution logo present", s && s.attribution);
  await page.screenshot({ path: path.join(OUT, "desktop_crypto_4h_all.png") });

  const box = await chartBox(page);
  const cx = box.x + box.width * 0.5, cy = box.y + 150;
  await page.mouse.move(cx, cy);
  await page.waitForTimeout(100);
  const hovered = await page.evaluate(() => window.chartState().legend);
  check("crosshair hover updates the OHLCV legend", hovered !== s.legend && !/last closed/.test(hovered), hovered.split("\n")[0]);

  const before = await page.evaluate(() => window.chartState());
  await page.mouse.wheel(0, -400);
  await page.waitForTimeout(250);
  const zoomed = await page.evaluate(() => window.chartState());
  check("mouse wheel zooms in", (zoomed.to - zoomed.from) < (before.to - before.from) * 0.95,
        `${(before.to - before.from).toFixed(1)} -> ${(zoomed.to - zoomed.from).toFixed(1)} candles`);

  await page.mouse.move(cx, cy);
  await page.mouse.down();
  await page.mouse.move(cx + 250, cy, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(250);
  const panned = await page.evaluate(() => window.chartState());
  check("drag pans back in time", panned.from < zoomed.from - 3, `${zoomed.from.toFixed(1)} -> ${panned.from.toFixed(1)}`);

  await page.waitForTimeout(250);
  await page.evaluate(() => window.mountChart("crypto_4h_all", false));
  const rerun = await page.evaluate(() => window.chartState());
  check("rerun with unchanged data keeps the same chart and view", rerun.id === panned.id && Math.abs(rerun.from - panned.from) < 0.01);

  await page.evaluate(() => window.mountChart("crypto_4h_overlay", false));
  const changed = await page.evaluate(() => window.chartState());
  check("changing indicators keeps the visible position", Math.abs(changed.from - panned.from) < 1 && Math.abs(changed.to - panned.to) < 1,
        `${panned.from.toFixed(1)}..${panned.to.toFixed(1)} vs ${changed.from.toFixed(1)}..${changed.to.toFixed(1)}`);
  check("overlay mode draws oscillators on the price pane (fewer panes)", changed.panes === 2, changed.panes);
  await page.screenshot({ path: path.join(OUT, "desktop_crypto_4h_overlay_dark.png") });

  await page.evaluate(() => window.mountChart("crypto_4h_overlay", true));
  const remount = await page.evaluate(() => window.chartState());
  check("view survives the chart being rebuilt from scratch", Math.abs(remount.from - panned.from) < 1, remount.from.toFixed(1));

  await page.locator("button[title='Back to the chosen range']").click();
  await page.waitForTimeout(150);
  const reset = await page.evaluate(() => window.chartState());
  check("reset button returns to the chosen range", Math.abs((reset.to - reset.from) - openSpan(fixture("crypto_4h_overlay"))) < 2, (reset.to - reset.from).toFixed(1));

  await page.evaluate(() => window.mountChart("equity_daily_earnings", true));
  const eq = await page.evaluate(() => window.chartState());
  check("equity daily: price, volume and RSI panes", eq.panes === 3, eq.panes);
  const eqp = fixture("equity_daily_earnings");
  if (eqp.right_offset > 0) check("equity daily: room on the right for the next earnings date", eq.to > eqp.times.length - 1 + 3, eq.to.toFixed(1));
  check("equity daily: earnings lines sent", eqp.vlines.length > 0 || !eqp.has_earnings, eqp.vlines.length);
  await page.screenshot({ path: path.join(OUT, "desktop_equity_daily_earnings.png") });

  await page.evaluate(() => window.mountChart("equity_1h", true));
  const h1 = await page.evaluate(() => window.chartState());
  check("equity 1h: legend time is New York clock", /\d\d:30/.test(h1.legend.split("\n")[0]), h1.legend.split("\n")[0]);
  check("equity 1h: note names New York time", /New York time/.test(h1.note));
  await page.screenshot({ path: path.join(OUT, "desktop_equity_1h.png") });

  if (fs.existsSync(path.join(FIX, "crypto_15m_large.json"))) {
    const big = fixture("crypto_15m_large");
    const t0 = Date.now();
    await page.evaluate(() => window.mountChart("crypto_15m_large", true));
    const ms = Date.now() - t0;
    const kb = Math.round(fs.statSync(path.join(FIX, "crypto_15m_large.json")).size / 1024);
    check("largest chart (15m, 1 month, every indicator) draws in under 1.5 s", ms < 1500,
          `${big.times.length} candles, ${kb} KB, ${ms} ms including fetch`);
    const t1 = Date.now();
    await page.mouse.move(cx, cy);
    for (let i = 0; i < 10; i++) { await page.mouse.wheel(0, i % 2 ? 200 : -200); await page.waitForTimeout(16); }
    check("zooming the largest chart stays responsive", Date.now() - t1 < 1500, `${Date.now() - t1} ms for 10 wheel steps`);
  }
  check("no browser errors (desktop)", errors.length === 0, errors.join(" | "));
  await page.close();
}

async function touch(browser, base) {
  const context = await browser.newContext({ ...devices["iPad Pro 11"] });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(base);
  await page.waitForFunction(() => window.ready);
  await page.evaluate(() => window.mountChart("crypto_4h_all", true));
  const cdp = await context.newCDPSession(page);
  const box = await chartBox(page);
  const cx = box.x + box.width / 2, cy = box.y + 160;
  const before = await page.evaluate(() => window.chartState());

  const touchEvent = (type, points) => cdp.send("Input.dispatchTouchEvent", {
    type, touchPoints: points.map(([x, y], id) => ({ x, y, id, radiusX: 2, radiusY: 2, force: 1 })),
  });
  // Pinch out: two fingers move apart.
  let gap = 40;
  await touchEvent("touchStart", [[cx - gap, cy], [cx + gap, cy]]);
  for (let i = 0; i < 12; i++) {
    gap += 15;
    await touchEvent("touchMove", [[cx - gap, cy], [cx + gap, cy]]);
    await page.waitForTimeout(16);
  }
  await touchEvent("touchEnd", []);
  await page.waitForTimeout(300);
  const pinched = await page.evaluate(() => window.chartState());
  check("touch: pinch zooms in (emulated)", (pinched.to - pinched.from) < (before.to - before.from) * 0.9,
        `${(before.to - before.from).toFixed(1)} -> ${(pinched.to - pinched.from).toFixed(1)} candles`);

  // One finger, sideways: pans.
  await touchEvent("touchStart", [[cx, cy]]);
  for (let i = 1; i <= 10; i++) { await touchEvent("touchMove", [[cx + i * 25, cy]]); await page.waitForTimeout(16); }
  await touchEvent("touchEnd", []);
  await page.waitForTimeout(600);
  const swiped = await page.evaluate(() => window.chartState());
  check("touch: sideways drag pans (emulated)", swiped.from < pinched.from - 2, `${pinched.from.toFixed(1)} -> ${swiped.from.toFixed(1)}`);

  // One finger, up: the page should scroll, not the chart.
  const y0 = await page.evaluate(() => window.scrollY);
  await touchEvent("touchStart", [[cx, cy + 100]]);
  for (let i = 1; i <= 10; i++) { await touchEvent("touchMove", [[cx, cy + 100 - i * 25]]); await page.waitForTimeout(16); }
  await touchEvent("touchEnd", []);
  await page.waitForTimeout(400);
  const after = await page.evaluate(() => window.chartState());
  check("touch: vertical swipe scrolls the page (emulated)", after.scrollY > y0, `${y0} -> ${after.scrollY}`);

  await page.screenshot({ path: path.join(OUT, "touch_ipad_emulated.png") });
  check("no browser errors (touch)", errors.length === 0, errors.join(" | "));
  await context.close();
}

(async () => {
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}/`;
  const browser = await chromium.launch();
  try {
    await desktop(browser, base);
    await touch(browser, base);
  } catch (e) {
    check("test run finished", false, e.stack || e.message);
  } finally {
    await browser.close();
    server.close();
  }
  const failed = results.filter((r) => !r.ok).length;
  const md = ["# TradingView chart browser check", "", `${results.length - failed}/${results.length} passed.`,
    "Touch checks use Chromium's iPad emulation with real touch events; they are not a test on a physical iPad.", "",
    ...results.map((r) => `- ${r.ok ? "PASS" : "FAIL"} ${r.name}${r.detail ? ` (${r.detail})` : ""}`)];
  fs.writeFileSync(path.join(OUT, "chart_browser.md"), md.join("\n") + "\n");
  process.exit(failed ? 1 : 0);
})();
