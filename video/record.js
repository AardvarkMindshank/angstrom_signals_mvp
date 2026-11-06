// Records the demo page (desktop, 1280x720) step by step, paced by the narration. Usage:
// node video/record.js http://127.0.0.1:8601/ out/video
// Writes out/video/raw.webm and timeline.json (when each step starts, in seconds from the start of the video).
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

(async () => {
  const url = process.argv[2];
  const dir = process.argv[3] || "out/video";
  const script = JSON.parse(fs.readFileSync("video/script.json"));
  const durations = JSON.parse(fs.readFileSync(path.join(dir, "durations.json")));
  const browser = await chromium.launch();
  // Warm up first (fonts, first run), so the video starts on a ready page.
  const warm = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await warm.goto(url); await warm.waitForSelector(".lat.prism", { timeout: 120000 }); await warm.close();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1,
    recordVideo: { dir: path.join(dir, "raw"), size: { width: 1280, height: 720 } } });
  const page = await ctx.newPage();
  const t0 = Date.now();
  const now = () => (Date.now() - t0) / 1000;
  const settle = async () => {
    await page.waitForTimeout(500);
    await page.waitForFunction(() => !document.querySelector("[data-testid='stStatusWidgetRunningIcon']"),
      null, { timeout: 120000 }).catch(() => {});
    await page.waitForTimeout(400);
  };
  const glide = async (selector) => {           // move the pointer visibly before clicking
    const box = await page.locator(selector).first().boundingBox();
    if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 18 });
    await page.waitForTimeout(250);
  };
  const scrollTo = (selector) => page.locator(selector).first().scrollIntoViewIfNeeded().catch(() => {});
  const actions = {
    intro: async () => { await page.goto(url); await page.waitForSelector(".lat.prism", { timeout: 120000 }); await settle(); },
    create: async () => {
      const b = 'button[aria-label="Start a scan with Trend and Flow agree (demo)"]';
      await glide(b); await page.click(b); await page.waitForSelector(".lat.prism .scan", { timeout: 60000 }); await settle();
    },
    card: async () => { await glide(".lat.prism .scan .head"); await page.waitForTimeout(800); },
    assets: async () => {
      const g = 'button[aria-label="Add All crypto to the selected scan"]';
      await glide(g); await page.click(g); await settle();
      const x = '.lat.prism .scan button[aria-label="Remove Whole Watchlist"]';
      if (await page.$(x)) { await glide(x); await page.click(x); await settle(); }
    },
    play: async () => {
      const p = ".lat.prism .scan button.play";
      await glide(p); await page.click(p); await settle();
      await page.waitForSelector(".lat.prism .scan table", { timeout: 180000 }).catch(() => {});
    },
    results: async () => { await scrollTo(".lat.prism .scan table"); await glide(".lat.prism .scan table tr:nth-child(2)"); },
    schedule: async () => {
      await scrollTo('.lat.prism .scan select[aria-label="When the scan runs"]');
      const s = '.lat.prism .scan select[aria-label="When the scan runs"]';
      await glide(s); await page.selectOption(s, "1D"); await page.waitForTimeout(500);
      const save = '.lat.prism .scan button[aria-label="Save when the scan runs"]';
      await glide(save); await page.click(save); await settle();
    },
    alerts: async () => {
      const a = '.lat.prism .scan select[aria-label="Where alerts go"]';
      await scrollTo(a); await glide(a); await page.waitForTimeout(1200);
    },
    tidy: async () => {
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" })); await page.waitForTimeout(700);
      const c = "text=Collapse all"; await glide(c); await page.click(c); await page.waitForTimeout(800);
    },
  };
  const timeline = [];
  for (const step of script.steps) {
    const start = now();
    timeline.push({ id: step.id, start, say: step.say });
    try { await actions[step.id](); } catch (e) { console.log(`step ${step.id}: ${e}`); }
    const wanted = start + durations[step.id] + 0.7;
    if (now() < wanted) await page.waitForTimeout((wanted - now()) * 1000);
  }
  await page.waitForTimeout(1500);
  const end = now();
  await page.screenshot({ path: path.join(dir, "last_frame.png") });
  await ctx.close();
  const video = fs.readdirSync(path.join(dir, "raw")).find((f) => f.endsWith(".webm"));
  fs.renameSync(path.join(dir, "raw", video), path.join(dir, "raw.webm"));
  fs.writeFileSync(path.join(dir, "timeline.json"), JSON.stringify({ steps: timeline, end }, null, 1));
  await browser.close();
  console.log(JSON.stringify(timeline.map((t) => [t.id, t.start.toFixed(1)])));
})();
