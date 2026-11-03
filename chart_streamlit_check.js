// Checks the TradingView chart inside real Streamlit (chart_streamlit_app.py), in CI.
// Usage: node chart_streamlit_check.js <url> <output folder>

const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const URL = process.argv[2] || "http://127.0.0.1:8599/";
const OUT = path.resolve(process.argv[3] || "out");
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const check = (name, ok, detail) => {
  results.push({ name, ok: !!ok, detail: detail === undefined ? "" : String(detail) });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail === undefined ? "" : "  (" + detail + ")"}`);
};

const state = (page) => page.evaluate(() => {
  const root = document.querySelector(".ang-lwc");
  const c = root && root.__chart;
  if (!c) return null;
  const r = c.timeScale().getVisibleLogicalRange();
  if (!root.__testId) root.__testId = Math.random();
  return { from: r.from, to: r.to, panes: c.panes().length, id: root.__testId, roots: document.querySelectorAll(".ang-lwc").length };
});

async function settle(page) {
  await page.waitForTimeout(400);
  await page.waitForFunction(() => !document.querySelector("[data-testid='stStatusWidget'] [data-testid='stStatusWidgetRunningIcon']"), null, { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(600);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1200, height: 1000 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  try {
    await page.goto(URL);
    await page.waitForSelector(".ang-lwc canvas", { timeout: 60000 });
    await settle(page);
    const first = await state(page);
    check("chart mounts inside Streamlit", first && first.panes === 7, first && first.panes);
    check("library served from /app/static", await page.evaluate(() => !!window.LightweightCharts));

    const host = await page.locator(".ang-lwc-host").boundingBox();
    await page.mouse.move(host.x + host.width / 2, host.y + 150);
    await page.mouse.wheel(0, -500);
    await page.waitForTimeout(400);
    const zoomed = await state(page);
    check("wheel zoom works inside Streamlit", (zoomed.to - zoomed.from) < (first.to - first.from) * 0.95);

    await page.getByRole("button", { name: "Rerun" }).click();
    await settle(page);
    const rerun = await state(page);
    check("a rerun keeps the same chart and view", rerun.id === zoomed.id && Math.abs(rerun.from - zoomed.from) < 0.01,
          `${zoomed.from.toFixed(1)} vs ${rerun.from.toFixed(1)}`);
    check("only one chart on the page after reruns", rerun.roots === 1, rerun.roots);

    await page.getByText("Unrelated toggle").click();
    await settle(page);
    const toggled = await state(page);
    check("an unrelated widget change keeps the view", Math.abs(toggled.from - zoomed.from) < 0.01);

    await page.getByText("crypto_4h_overlay").click();
    await settle(page);
    const changed = await state(page);
    check("changing indicators keeps the view (same asset and interval)", changed && Math.abs(changed.from - zoomed.from) < 1 && changed.panes === 2,
          changed && `${changed.from.toFixed(1)}, ${changed.panes} panes`);

    await page.getByText("equity_daily_earnings").click();
    await settle(page);
    const other = await state(page);
    check("another asset opens on its own range", other && other.panes === 3, other && other.panes);

    await page.getByText("crypto_4h_all").click();
    await settle(page);
    const back = await state(page);
    check("coming back to the first chart restores its view", back && Math.abs(back.from - zoomed.from) < 1,
          back && `${zoomed.from.toFixed(1)} vs ${back.from.toFixed(1)}`);

    await page.reload();
    await page.waitForSelector(".ang-lwc canvas", { timeout: 60000 });
    await settle(page);
    const reloaded = await state(page);
    check("view survives a page reload in the same tab", reloaded && Math.abs(reloaded.from - zoomed.from) < 1,
          reloaded && reloaded.from.toFixed(1));
    await page.screenshot({ path: path.join(OUT, "streamlit_chart.png"), fullPage: true });
  } catch (e) {
    check("streamlit run finished", false, e.stack || e.message);
  }
  check("no browser errors", errors.length === 0, errors.join(" | "));
  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  fs.writeFileSync(path.join(OUT, "chart_streamlit.md"),
    ["# Chart inside Streamlit", "", `${results.length - failed}/${results.length} passed.`, "",
     ...results.map((r) => `- ${r.ok ? "PASS" : "FAIL"} ${r.name}${r.detail ? ` (${r.detail})` : ""}`)].join("\n") + "\n");
  process.exit(failed ? 1 : 0);
})();
