// A first test of recording the live site as the demo account (18 Nov 2026): sign in, tour the main page and the
// four parts of Lattice, and save a raw video (no voice yet) and a screenshot at each stop.
//
//   DEMO_EMAIL=... DEMO_PASSWORD=... node video/live_tour.js out/live_tour
//
// The login comes from GitHub secrets and is never printed. Nothing is saved or changed in the account: the tour
// only opens sections and tabs.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const URL = process.env.APP_URL || "https://app.marketnavi.ai/";
const OUT = process.argv[2] || "out/live_tour";
const W = 1280, H = 720;

(async () => {
  const email = process.env.DEMO_EMAIL, password = process.env.DEMO_PASSWORD;
  if (!email || !password) { console.log("DEMO_EMAIL or DEMO_PASSWORD is not set as a GitHub secret."); process.exit(1); }
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, colorScheme: "dark",
    recordVideo: { dir: OUT, size: { width: W, height: H } } });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  const log = [];
  const note = (line) => { console.log(line); log.push(line); };
  let n = 0;
  const shot = async (name) => {
    n += 1;
    await page.screenshot({ path: path.join(OUT, `${String(n).padStart(2, "0")}_${name}.png`) });
    note(`saved ${name}`);
  };
  const settle = async (ms = 600) => {
    await page.waitForTimeout(ms);
    await page.waitForFunction(() => !document.querySelector("[data-testid='stStatusWidgetRunningIcon']"),
      null, { timeout: 180000 }).catch(() => {});
    await page.waitForTimeout(500);
  };
  const glideTo = async (loc) => {
    await loc.scrollIntoViewIfNeeded().catch(() => {});
    const box = await loc.boundingBox();
    if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 20 });
    await page.waitForTimeout(300);
  };

  try {
    // ---------------------------------------------------------------- sign in
    await page.goto(URL, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('input[autocomplete="username"]', { timeout: 180000 });
    await settle(1500);
    await shot("sign_in");
    await page.fill('input[autocomplete="username"]', email);
    await page.fill('input[autocomplete="current-password"]', password);
    await page.locator("button").filter({ hasText: "Log In" }).first().click();
    // What the page shows in the seconds after Log In, every 120 ms (to see any flicker of the sign-in form).
    for (let i = 0; i < 70; i += 1) {
      await page.screenshot({ path: path.join(OUT, `burst_${String(i).padStart(2, "0")}.png`), scale: "css" }).catch(() => {});
      await page.waitForTimeout(120);
    }
    await page.waitForFunction(() => !document.querySelector('input[autocomplete="current-password"]'), null, { timeout: 120000 })
      .catch(() => {});
    await settle(3000);
    if (await page.locator('input[autocomplete="current-password"]').count()) {
      await shot("sign_in_failed");
      throw new Error("Sign-in did not go through: check the demo email and password secrets.");
    }
    if (await page.getByText(/non-disclosure|NDA/i).first().isVisible().catch(() => false)) {
      await shot("nda_waiting");
      throw new Error("The demo account still has the NDA to accept: sign in once by hand and accept it.");
    }
    note("signed in");
    await shot("home");

    // ---------------------------------------------------------------- the main page, top to bottom
    for (let i = 1; i <= 4; i += 1) {
      await page.mouse.wheel(0, H * 0.8);
      await settle(900);
      await shot(`home_scroll_${i}`);
    }
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
    await settle(800);

    // ---------------------------------------------------------------- Lattice and its four parts
    const lattice = page.locator("summary").filter({ hasText: "Lattice" }).first();
    if (await lattice.count()) {
      await glideTo(lattice);
      const open = await lattice.evaluate((s) => s.parentElement && s.parentElement.open).catch(() => false);
      if (!open) await lattice.click();
      await page.waitForSelector(".lat, [data-testid='stBidiComponentIsolated']", { timeout: 90000 }).catch(() => {});
      await settle(2500);
      await shot("lattice");
      for (const part of ["Signal Groups", "Signal Sets", "Prism Scan", "Funnels"]) {
        const tab = page.locator("button").filter({ hasText: part, visible: true }).first();
        if (!(await tab.count())) { note(`no ${part} tab found`); continue; }
        await glideTo(tab);
        await tab.click();
        await settle(3000);
        await shot(part.toLowerCase().replace(/\s+/g, "_"));
        await page.mouse.wheel(0, H * 0.7);
        await settle(900);
        await shot(part.toLowerCase().replace(/\s+/g, "_") + "_lower");
        await lattice.scrollIntoViewIfNeeded().catch(() => {});
        await settle(500);
      }
    } else {
      note("no Lattice section found on the page");
    }
    note("tour finished");
  } catch (err) {
    note("stopped: " + String(err && err.message || err).replace(password, "***"));
    process.exitCode = 1;
  } finally {
    const video = page.video();
    await context.close();
    if (video) {
      const raw = await video.path();
      fs.renameSync(raw, path.join(OUT, "tour.webm"));
    }
    fs.writeFileSync(path.join(OUT, "log.txt"), log.join("\n") + "\n");
    await browser.close();
  }
})();
