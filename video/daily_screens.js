// 🖥️ Fresh app screens behind the Morning Outlook video (24 Nov 2026): signs in to the live app as the demo account
// (DEMO_EMAIL / DEMO_PASSWORD) and photographs the parts each section is about, so the numbers behind the video match
// the ones in front. Nothing is saved or changed: it only opens sections. The social panel is never opened.
//
//   DEMO_EMAIL=... DEMO_PASSWORD=... node video/daily_screens.js video/daily/screens
//
// Each screen is written only when it was taken; a screen that fails keeps the stored copy already in the folder.
// The whole run is capped (DEADLINE), so it never holds up the video.
const { chromium } = require("playwright");
const path = require("path");

const URL = process.env.APP_URL || "https://app.marketnavi.ai/";
const OUT = process.argv[2] || "video/daily/screens";
const DEADLINE = Date.now() + 6 * 60 * 1000;

(async () => {
  let browser;
  const done = [];
  try {
    browser = await chromium.launch().catch(() => chromium.launch({ channel: "chrome" }));
    const ctx = await browser.newContext({ viewport: { width: 1400, height: 1030 }, colorScheme: "dark" });
    const page = await ctx.newPage();
    page.setDefaultTimeout(20000);
    const settle = async (ms = 700) => {
      await page.waitForTimeout(ms);
      await page.waitForFunction(() => !document.querySelector("[data-testid='stStatusWidgetRunningIcon']"), null, { timeout: 120000 }).catch(() => {});
      await page.waitForTimeout(600);
    };
    const sum = (text) => page.locator("summary").filter({ hasText: text }).first();
    const isOpen = (s) => s.evaluate((n) => !!(n.parentElement && n.parentElement.open)).catch(() => false);
    const expand = async (text) => { const s = sum(text); if (!(await isOpen(s))) { await s.click(); await settle(); } return s; };
    const fold = async (text) => { const s = sum(text); if (await s.count() && await isOpen(s)) { await s.click(); await settle(); } };
    const toTop = async (loc) => { await loc.evaluate((n) => n.scrollIntoView({ block: "start" })).catch(() => {}); await page.waitForTimeout(900); };
    const shot = async (name) => {
      // Members' votes and comments ("Your take") are never photographed: blanked for every picture.
      await page.addStyleTag({ content: "[class*='_take_box']{visibility:hidden !important}" }).catch(() => {});
      await page.mouse.move(1390, 1020);
      await page.screenshot({ path: path.join(OUT, name + ".jpg"), type: "jpeg", quality: 82 });
      done.push(name);
    };
    const step = async (name, fn) => {
      if (Date.now() > DEADLINE) { console.log(`${name}: out of time, stored copy kept`); return; }
      try { await fn(); } catch (e) { console.log(`${name}: ${String(e).split("\n")[0]} (stored copy kept)`); }
    };

    await page.goto(URL, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('input[autocomplete="username"]', { timeout: 150000 });
    await settle(1500);
    await page.fill('input[autocomplete="username"]', process.env.DEMO_EMAIL || "");
    await page.fill('input[autocomplete="current-password"]', process.env.DEMO_PASSWORD || "");
    await page.locator("button").filter({ hasText: "Log In" }).first().click();
    await page.waitForFunction(() => !document.querySelector('input[autocomplete="current-password"]'), null, { timeout: 120000 });
    await settle(6000);
    for (const name of ["Lattice", "Crypto Signals", "Equity Signals", "Interactive Chart", "Why these readings", "Quick Snapshot", "Tides",
                        "Market sentiment - Stock market", "Market sentiment - Crypto market"]) await fold(name).catch(() => {});
    await page.evaluate(() => window.scrollTo(0, 0));
    await settle();

    await step("dashboard", async () => { await shot("dashboard"); });
    await step("snapshot", async () => { const s = await expand("Quick Snapshot"); await settle(1500); await toTop(s); await shot("snapshot"); await fold("Quick Snapshot"); });
    await step("tides", async () => {
      const s = await expand("Tides"); await settle(2500); await toTop(s); await shot("tides");
      const cal = page.getByText("Storm warnings", { exact: false }).first();            // the macro calendar, under the Tides
      await toTop(cal); await page.evaluate(() => window.scrollBy(0, -120)); await page.waitForTimeout(600); await shot("calendar");
      await fold("Tides");
    });
    for (const [name, label] of [["stock_card", "Market sentiment - Stock market"], ["crypto_card", "Market sentiment - Crypto market"]]) {
      await step(name, async () => { const s = await expand(label); await settle(2500); await toTop(s); await shot(name); await fold(label); });
    }
    await step("btc_chart", async () => {
      const s = await expand("Interactive Chart"); await settle(4000);
      await page.waitForSelector(".ang-lwc canvas", { timeout: 60000 }).catch(() => {});
      await settle(1500);
      await toTop(s); await shot("btc_chart"); await fold("Interactive Chart");
    });
  } catch (e) {
    console.log(`App screens: ${String(e).split("\n")[0]} (stored copies kept)`);
  } finally {
    console.log(`App screens taken fresh: ${done.length ? done.join(", ") : "none"}`);
    if (browser) await browser.close().catch(() => {});
  }
})();
