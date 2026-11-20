const { chromium } = require("playwright");
const { spawn } = require("child_process");
(async () => {
  const [dir, out, total, timing] = process.argv.slice(2);
  const fps = 30, n = Math.round(Number(total) * fps);
  const ff = spawn("ffmpeg", ["-y", "-v", "error", "-f", "image2pipe", "-framerate", String(fps), "-c:v", "mjpeg", "-i", "-",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out], { stdio: ["pipe", "inherit", "inherit"] });
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto("file://" + dir + "/teaser.html");
  await p.evaluate((T) => { window.T = T; }, JSON.parse(timing));
  await p.waitForTimeout(500);
  for (let i = 0; i < n; i++) {
    await p.evaluate((t) => window.render(t), i / fps);
    const buf = await p.screenshot({ type: "jpeg", quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
  }
  ff.stdin.end();
  await new Promise((r) => ff.on("close", r));
  await b.close();
  console.log("frames " + n);
})();
