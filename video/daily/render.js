// 🎬 Renders video/daily/forecast.html frame by frame into an MP4 (daily_video.py):
//   node render.js <page> <spec.json> <out.mp4> <width> <height> <seconds> <fps>
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const fs = require("fs");
(async () => {
  const [page, specPath, out, w, h, total, fps] = process.argv.slice(2);
  const W = Number(w), H = Number(h), F = Number(fps), n = Math.round(Number(total) * F);
  const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
  const ff = spawn("ffmpeg", ["-y", "-v", "error", "-f", "image2pipe", "-framerate", String(F), "-c:v", "mjpeg", "-i", "-",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out], { stdio: ["pipe", "inherit", "inherit"] });
  // The runner's own Google Chrome when Playwright's browser didn't download (24 Nov 2026: three timed-out installs).
  const b = await chromium.launch().catch(() => chromium.launch({ channel: "chrome" }));
  const p = await b.newPage({ viewport: { width: W, height: H } });
  await p.goto("file://" + require("path").resolve(page));
  await p.evaluate((s) => window.setup(s), spec);
  await p.evaluate(() => Promise.all(Array.from(document.images).map((i) => i.decode().catch(() => null))));
  await p.waitForTimeout(400);
  for (let i = 0; i < n; i++) {
    await p.evaluate((t) => window.render(t), i / F);
    const buf = await p.screenshot({ type: "jpeg", quality: 90 });
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
  }
  ff.stdin.end();
  await new Promise((r) => ff.on("close", r));
  await b.close();
})();
