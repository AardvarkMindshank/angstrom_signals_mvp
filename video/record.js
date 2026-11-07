// Records one training video from the demo page (desktop, 1280 x 610, zoomed to 125%), step by step, paced by the
// narration. Usage:
//   SCRIPT=video/series/03-signal-groups.json node video/record.js http://127.0.0.1:8601/ out/video/03-signal-groups
// Reads <dir>/durations.json (from narrate.py). Writes <dir>/raw.webm, timeline.json (when each step starts, in
// seconds; "trim" is the loading time cut from the start) and a picture of the end of every step (step_<id>.png),
// for checking the recording without watching it.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");
const makeHelpers = require("./helpers.js");
const ACTIONS = require("./actions.js");

(async () => {
  const url = process.argv[2];
  const dir = process.argv[3] || "out/video";
  const script = JSON.parse(fs.readFileSync(process.env.SCRIPT || "video/series/05-prism-scan.json"));
  const durations = JSON.parse(fs.readFileSync(path.join(dir, "durations.json")));
  const actions = ACTIONS[script.slug];
  if (!actions) throw new Error(`No actions for ${script.slug} in video/actions.js`);
  const browser = await chromium.launch();
  // Warm up first (fonts, first run, price downloads), so the video starts on a ready page.
  const warm = await browser.newPage({ viewport: { width: 1280, height: 610 } });
  await warm.goto(url + (actions.query || "")); await warm.waitForSelector(".lat", { timeout: 180000 }); await warm.close();
  // The app is recorded at 1280 x 610, zoomed to 125% (text 25% larger, sharp); build.py adds a 110-pixel caption
  // band underneath for a 1280 x 720 video. Only the page body is zoomed: the pointer, diagrams, cards and notes are
  // drawn outside the zoom, at real pixels.
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 610 }, deviceScaleFactor: 1,
    recordVideo: { dir: path.join(dir, "raw"), size: { width: 1280, height: 610 } } });
  await ctx.addInitScript(() => {
    const zoom = () => { if (document.body) document.body.style.zoom = "1.25"; else requestAnimationFrame(zoom); };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", zoom); else zoom();
  });
  // A visible pointer, and a ripple on every click (recordings do not show the real pointer).
  await ctx.addInitScript(() => {
    const ready = () => {
      if (document.getElementById("demo-pointer")) return;
      const p = document.createElement("div");
      p.id = "demo-pointer";
      p.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M3 2l7 19 2.6-7.4L20 11z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
      Object.assign(p.style, { position: "fixed", left: "-40px", top: "-40px", zIndex: 2147483647, pointerEvents: "none",
        transition: "transform .08s", filter: "drop-shadow(0 2px 3px rgba(0,0,0,.35))" });
      document.documentElement.appendChild(p);
      document.addEventListener("mousemove", (e) => { p.style.left = e.clientX - 3 + "px"; p.style.top = e.clientY - 2 + "px"; }, true);
      document.addEventListener("mousedown", (e) => {
        p.style.transform = "scale(.85)";
        const r = document.createElement("div");
        Object.assign(r.style, { position: "fixed", left: e.clientX - 18 + "px", top: e.clientY - 18 + "px", width: "36px",
          height: "36px", borderRadius: "50%", border: "3px solid #f59e0b", background: "rgba(245,158,11,.25)",
          zIndex: 2147483646, pointerEvents: "none", transition: "transform .45s ease-out, opacity .45s ease-out" });
        document.documentElement.appendChild(r);
        requestAnimationFrame(() => { r.style.transform = "scale(1.9)"; r.style.opacity = "0"; });
        setTimeout(() => r.remove(), 500);
      }, true);
      document.addEventListener("mouseup", () => { p.style.transform = ""; }, true);
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ready); else ready();
  });
  const page = await ctx.newPage();
  page.on("console", (m) => { if (m.type() === "error" || process.env.VIDEO_DEBUG) console.log(`browser ${m.type()}: ${m.text().slice(0, 300)}`); });
  page.on("pageerror", (e) => console.log(`page error: ${String(e).slice(0, 300)}`));
  const t0 = Date.now();
  const now = () => (Date.now() - t0) / 1000;
  const h = makeHelpers(page, url);
  await h.open(actions.query || "");
  if (actions.setup) await actions.setup(h);
  const trim = now();
  const timeline = [];
  for (const step of script.steps) {
    const start = now();
    timeline.push({ id: step.id, start, say: step.say });
    const fn = actions[step.id];
    if (!fn) console.log(`step ${step.id}: no action (the screen stays as it is)`);
    try { if (fn) await fn(h, durations[step.id]); } catch (e) { console.log(`step ${step.id}: ${String(e).split("\n")[0]}`); }
    const wanted = start + durations[step.id] + 0.7;
    if (now() < wanted) await page.waitForTimeout((wanted - now()) * 1000);
    else console.log(`step ${step.id}: the actions took ${(now() - start - durations[step.id]).toFixed(1)} s longer than the voice`);
    await page.screenshot({ path: path.join(dir, `step_${step.id}.png`) }).catch(() => {});
  }
  await page.waitForTimeout(1500);
  const end = now();
  await ctx.close();
  const video = fs.readdirSync(path.join(dir, "raw")).find((f) => f.endsWith(".webm"));
  fs.renameSync(path.join(dir, "raw", video), path.join(dir, "raw.webm"));
  fs.writeFileSync(path.join(dir, "timeline.json"), JSON.stringify({ steps: timeline, end, trim }, null, 1));
  await browser.close();
  console.log(JSON.stringify(timeline.map((t) => [t.id, (t.start - trim).toFixed(1)])));
})();
