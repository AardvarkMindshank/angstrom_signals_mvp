// Screenshots of the live app for the website (18 Nov 2026), signed in as the demo account after the day-one videos
// have filled it in. Sharp (2x) pictures at 1440 x 900, in the dark theme.
//
//   DEMO_EMAIL=... DEMO_PASSWORD=... node video/live_shots.js out/shots
//
// Nothing is saved or changed: it only opens sections and tabs. The social panel is never opened, so no other
// person's messages appear.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const URL = process.env.APP_URL || "https://app.angstromsignals.com/";
const OUT = process.argv[2] || "out/shots";

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, colorScheme: "dark" });
  const page = await ctx.newPage();
  page.setDefaultTimeout(20000);
  const settle = async (ms = 700) => {
    await page.waitForTimeout(ms);
    await page.waitForFunction(() => !document.querySelector("[data-testid='stStatusWidgetRunningIcon']"), null, { timeout: 180000 }).catch(() => {});
    await page.waitForTimeout(600);
  };
  const sum = (text) => page.locator("summary").filter({ hasText: text }).first();
  const isOpen = (s) => s.evaluate((n) => !!(n.parentElement && n.parentElement.open)).catch(() => false);
  const expand = async (text) => { const s = sum(text); if (!(await isOpen(s))) { await s.click(); await settle(); } return s; };
  const fold = async (text) => { const s = sum(text); if (await isOpen(s)) { await s.click(); await settle(); } };
  const toTop = async (loc) => { await loc.evaluate((n) => n.scrollIntoView({ block: "start" })).catch(() => {}); await page.waitForTimeout(800); };
  const shot = async (name) => { await page.mouse.move(1430, 890); await page.screenshot({ path: path.join(OUT, name + ".png") }); console.log("saved " + name); };
  const tab = async (name) => {
    const b = page.locator("button").filter({ hasText: name, visible: true }).first();
    await b.click(); await settle(1500);
    await page.waitForSelector(".lat", { timeout: 90000 }).catch(() => {});
    await settle(1200);
    await toTop(b);
  };
  const ONLY = (process.env.ONLY || "").split(",").map((x) => x.trim()).filter(Boolean);
  const step = async (name, fn) => {
    if (ONLY.length && !ONLY.includes(name)) return;
    try { await fn(); } catch (e) { console.log(`${name}: ${String(e).split("\n")[0]}`); }
  };
  const side = (text) => page.locator("[data-testid='stSidebar'] summary").filter({ hasText: text }).first();

  await page.goto(URL, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('input[autocomplete="username"]', { timeout: 180000 });
  await settle(1500);
  await page.fill('input[autocomplete="username"]', process.env.DEMO_EMAIL || "");
  await page.fill('input[autocomplete="current-password"]', process.env.DEMO_PASSWORD || "");
  await page.locator("button").filter({ hasText: "Log In" }).first().click();
  await page.waitForFunction(() => !document.querySelector('input[autocomplete="current-password"]'), null, { timeout: 120000 });
  await settle(6000);
  for (const name of ["Angstrom Lattice", "Crypto Signals", "Equity Signals", "Interactive Chart", "Why these readings", "Quick Snapshot", "Tides"]) await fold(name);
  await page.evaluate(() => window.scrollTo(0, 0));
  await settle();

  await step("dashboard", async () => { await shot("dashboard"); });
  await step("snapshot", async () => { const s = await expand("Quick Snapshot"); await toTop(s); await shot("quick_snapshot"); await fold("Quick Snapshot"); });
  await step("tides", async () => { const s = await expand("Tides"); await settle(2500); await toTop(s); await shot("tides"); await fold("Tides"); });
  await step("table", async () => { const s = await expand("Crypto Signals"); await settle(3000); await toTop(s); await shot("signal_table"); });
  await step("chart", async () => {
    const table = page.locator("summary").filter({ hasText: "Crypto Signals" }).first().locator("xpath=..");
    const wl = table.locator("label").filter({ hasText: "My Watchlist" }).first();
    if (await wl.count()) { await wl.click().catch(() => {}); await settle(2500); }
    let coin = table.locator("table").getByText("Bitcoin", { exact: true }).first();
    if (!(await coin.count())) coin = table.getByText("Bitcoin", { exact: false }).first();
    await coin.click().catch(() => {});
    await settle(2500);
    await settle(1500);
    await fold("Crypto Signals");
    const s = await expand("Interactive Chart"); await settle(4000);
    await page.waitForSelector(".ang-lwc canvas", { timeout: 90000 }).catch(() => {});
    // Daily candles over a year, with the Sonar strip and markers and chart shapes, so the picture shows the chart
    // at work; the whole chart is photographed (not the top of the section), then the pills are put back.
    const press = async (key, words) => {
      const b = page.locator(`.st-key-${key} button`).filter({ hasText: words }).first();
      if (await b.count()) { await b.click().catch(() => {}); await settle(1500); }
    };
    const pillOn = async (words) => {
      const b = page.locator(".st-key-chart_indicators button").filter({ hasText: words }).first();
      if (!(await b.count())) return false;
      const on = await b.evaluate((n) => n.dataset.testid === "stBaseButton-pillsActive" || n.getAttribute("aria-pressed") === "true").catch(() => false);
      if (!on) { await b.click().catch(() => {}); await settle(1500); return true; }
      return false;
    };
    await press("chart_interval", /^1D$/);
    await press("chart_range", /^1Y$/);
    const ev = page.locator(".st-key-chart_events").first();           // no Fed, CPI and jobs lines in the picture
    if (await ev.locator('input[type="checkbox"]').first().isChecked().catch(() => false)) {
      await ev.locator("label").first().click().catch(() => {}); await settle(1500);
    }
    const turned = [];
    for (const words of [/Sonar\s*$/, "Sonar markers", "Chart shapes", "Stoch RSI"]) if (await pillOn(words)) turned.push(words);
    const marks = page.locator(".st-key-chart_sonar_marks button").filter({ hasText: /^All$/ }).first();
    if (await marks.count()) { await marks.click().catch(() => {}); await settle(1500); }
    await page.locator(".ang-lwc .ang-lwc-tools button").filter({ hasText: "⟲" }).first().click().catch(() => {});
    await settle(3000);
    const chart = page.locator(".ang-lwc").first();
    await toTop(s); await shot("chart");
    await chart.evaluate((n) => n.scrollIntoView({ block: "start" })).catch(() => {});
    await page.waitForTimeout(1200);
    await page.mouse.move(1430, 890);
    await chart.screenshot({ path: path.join(OUT, "chart_full.png") }).then(() => console.log("saved chart_full")).catch((e) => console.log("chart_full: " + e));
    for (const words of turned) await press("chart_indicators", words);
    await fold("Interactive Chart");
  });
  await step("why", async () => { const s = await expand("Why these readings"); await settle(2000); await toTop(s); await shot("why_these_readings"); await fold("Why these readings"); });
  await step("lattice", async () => {
    await expand("Angstrom Lattice");
    await tab("Signal Groups"); await shot("signal_groups");
    await tab("Signal Sets"); await shot("signal_sets");
    await tab("Prism Scan"); await shot("prism_scan");
    await tab("Funnels"); await page.waitForSelector(".lat.fun", { timeout: 60000 }).catch(() => {});
    await settle(1500);
    const board = page.locator(".lat.fun").first();
    await toTop(board); await shot("funnel");
    await fold("Angstrom Lattice");
  });
  // 📓 Logbook and ☀️/🌙 Day or night (sidebar), checked after the 20 Nov changes; not website pictures.
  await step("logbook", async () => {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.locator("button.log-edge").first().click();
    await page.waitForTimeout(15000);                       // the panel's page signs in and draws
    await shot("logbook");
    await page.locator("#ang-log-root .log-close").first().click().catch(() => {});
    await settle();
  });
  await step("ui_mode", async () => {
    const s = side("Settings"); await s.click(); await settle(2500);
    const c = side("UI Colours"); await c.click(); await settle(2500);
    await c.evaluate((n) => n.scrollIntoView({ block: "start" })).catch(() => {});
    await page.waitForTimeout(800); await shot("ui_mode");
  });
  // The chart keeps its asset across visits (fixed 20 Nov 2026): pick another asset with the chart's pulldown, reload
  // (a new visit, still signed in) and read the pulldown again. Demo-account asset names only.
  await step("chart_keep", async () => {
    const box = () => page.locator("[data-testid='stSelectbox']").filter({ hasText: "Asset" }).first();
    const read = async () => (await box().innerText().catch(() => "")).replace(/^Asset\s*/, "").split("\n")[0].trim();
    const s = await expand("Interactive Chart"); await settle(4000);
    console.log("chart_keep: at login " + await read());
    await box().locator("[data-baseweb='select']").click(); await page.waitForTimeout(800);
    const opts = page.locator("[role='option']");
    const n = await opts.count();
    const before = await read();
    let chose = "";
    for (let i = 0; i < n; i++) { const txt = (await opts.nth(i).innerText()).trim(); if (txt && txt !== before) { chose = txt; await opts.nth(i).click(); break; } }
    await settle(5000);
    console.log("chart_keep: chose " + chose + ", now " + await read());
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(8000); await settle(6000);
    await expand("Interactive Chart"); await settle(4000);
    const after = await read();
    console.log("chart_keep: after reload " + after + (after === chose ? " (kept)" : " (NOT KEPT)"));
    await toTop(s); await shot("chart_keep");
  });
  await step("navigator", async () => {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.locator("button.ai-edge").first().click();
    await settle(3000);
    await shot("ai_navigator");
  });
  await browser.close();
})();
