// NDA signature pad in a real browser (CI, chart job). Usage: node nda_pad_check.js out/nda_pad
// Draws with a mouse and with a finger (iPhone), checks the PNG sent back, that a tap alone is not a signature,
// that Clear empties it, and that a redraw of the page keeps the drawing. Exits 1 on any failure.
const fs = require("fs");
const path = require("path");
const { chromium, devices } = require("playwright");

(async () => {
  const dir = process.argv[2] || "out/nda_pad";
  const url = "file://" + path.resolve(dir, "pad.html");
  const results = [];
  const check = (name, ok, detail) => results.push({ name, ok: !!ok, detail: detail || "" });
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 900, height: 600 } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(url);
    await page.waitForFunction(() => window.ready);
    const box = await page.locator("canvas").boundingBox();
    const sent = () => page.evaluate(() => window.sent.map(([k, v]) => [k, v ? v.length : 0]));
    await page.mouse.click(box.x + 20, box.y + 20);
    check("a single tap is not a signature", (await sent()).length === 0);
    await page.mouse.move(box.x + 20, box.y + 120);
    await page.mouse.down();
    for (const [dx, dy] of [[80, 40], [140, 130], [200, 50], [260, 140], [330, 60]]) await page.mouse.move(box.x + dx, box.y + dy, { steps: 6 });
    await page.mouse.up();
    let s = await sent();
    check("drawing sends a PNG", s.length === 1 && s[0][0] === "png" && s[0][1] > 400, JSON.stringify(s));
    const png = await page.evaluate(() => window.sent[0][1].slice(0, 12));
    check("it is a real PNG", png.startsWith("iVBORw0KGgo"), png);
    await page.evaluate(() => window.draw());
    await page.waitForTimeout(150);
    const kept = await page.evaluate(() => { const c = document.querySelector("canvas"); const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data; let ink = 0; for (let i = 0; i < d.length; i += 4) if (d[i] < 100) ink++; return ink; });
    check("a redraw keeps the drawing", kept > 50, `${kept} dark pixels`);
    await page.click("text=Clear");
    s = await sent();
    check("Clear empties the signature", s[s.length - 1][1] === 0);
    await page.screenshot({ path: path.join(dir, "pad_desktop.png") });
    check("no browser errors", errors.length === 0, errors.join("; "));

    const ctx = await browser.newContext({ ...devices["iPhone 13"] });
    const phone = await ctx.newPage();
    await phone.goto(url);
    await phone.waitForFunction(() => window.ready);
    const pb = await phone.locator("canvas").boundingBox();
    check("iPhone: the pad fits the screen", pb.width <= 390 && pb.width > 250, `${pb.width}px`);
    await phone.evaluate(([x, y]) => {
      const c = document.querySelector("canvas");
      const ev = (type, px, py) => c.dispatchEvent(new PointerEvent(type, { pointerId: 7, pointerType: "touch", clientX: px, clientY: py, bubbles: true, cancelable: true }));
      ev("pointerdown", x + 20, y + 100);
      for (let i = 1; i <= 20; i++) ev("pointermove", x + 20 + i * 12, y + 100 + (i % 2 ? -40 : 30));
      ev("pointerup", x + 260, y + 90);
    }, [pb.x, pb.y]);
    const ps = await phone.evaluate(() => window.sent.map(([k, v]) => [k, v ? v.length : 0]));
    check("iPhone: drawing with a finger sends a PNG", ps.length === 1 && ps[0][1] > 400, JSON.stringify(ps));
    await phone.screenshot({ path: path.join(dir, "pad_phone.png") });
  } catch (e) {
    check("ran to the end", false, String(e).slice(0, 300));
  } finally {
    await browser.close();
  }
  const lines = ["# NDA signature pad in a browser", "", "| Check | Result | Detail |", "|---|---|---|"];
  results.forEach((r) => lines.push(`| ${r.name} | ${r.ok ? "pass" : "FAIL"} | ${String(r.detail).replace(/\|/g, "/")} |`));
  fs.writeFileSync(path.join(dir, "nda_pad.md"), lines.join("\n") + "\n");
  console.log(lines.join("\n"));
  process.exit(results.every((r) => r.ok) ? 0 : 1);
})();
