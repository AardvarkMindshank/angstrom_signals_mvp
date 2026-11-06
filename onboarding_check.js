// Tap to explain in a real browser (CI, chart job). Usage: node onboarding_check.js out/onboarding
// On an emulated iPhone: a tap explains a note that does nothing else; a tap on a button presses it; a long press
// explains the button without pressing it; notes inside a component's shadow root work. On a desktop: a plain click
// shows nothing new (the hover note does that), and Explain mode explains instead of pressing. Exits 1 on failure.
const fs = require("fs");
const path = require("path");
const { chromium, devices } = require("playwright");

(async () => {
  const dir = process.argv[2] || "out/onboarding";
  const url = "file://" + path.resolve(dir, "tap.html");
  const results = [];
  const check = (name, ok, detail) => results.push({ name, ok: !!ok, detail: detail || "" });
  const browser = await chromium.launch();
  const bubble = (p) => p.evaluate(() => { const b = document.querySelector(".explain-bubble"); return b ? b.textContent : null; });
  const clicks = (p) => p.evaluate(() => Number(document.getElementById("clicks").textContent));
  try {
    const ctx = await browser.newContext({ ...devices["iPhone 13"] });
    const phone = await ctx.newPage();
    const errors = [];
    phone.on("pageerror", (e) => errors.push(e.message));
    await phone.goto(url);
    await phone.waitForFunction(() => window.ready);
    await phone.tap("#reading");
    check("iPhone: a tap on a reading shows its note", ((await bubble(phone)) || "").startsWith("Trend +42"), await bubble(phone));
    await phone.screenshot({ path: path.join(dir, "tap_phone.png") });
    await phone.tap("#plain");
    check("iPhone: a tap elsewhere closes it", (await bubble(phone)) === null);
    await phone.tap("#act");
    check("iPhone: a tap on a button presses it, no bubble", (await clicks(phone)) === 1 && (await bubble(phone)) === null);
    await phone.tap("#rowcell");
    check("iPhone: a tap on something clickable acts, no bubble", (await bubble(phone)) === null);
    await phone.evaluate(() => {
      const b = document.getElementById("act");
      const r = b.getBoundingClientRect();
      b.dispatchEvent(new PointerEvent("pointerdown", { pointerType: "touch", pointerId: 3, clientX: r.x + 4, clientY: r.y + 4, bubbles: true, composed: true }));
    });
    await phone.waitForTimeout(650);
    await phone.evaluate(() => {
      const b = document.getElementById("act");
      b.dispatchEvent(new PointerEvent("pointerup", { pointerType: "touch", pointerId: 3, bubbles: true, composed: true }));
      b.click();
    });
    check("iPhone: a long press explains a button without pressing it",
      (await bubble(phone)) === "Run now on 12 assets" && (await clicks(phone)) === 1, `${await bubble(phone)} / ${await clicks(phone)}`);
    await phone.tap("#plain");
    const inner = await phone.evaluateHandle(() => document.getElementById("host").shadowRoot.getElementById("inner"));
    const box = await inner.boundingBox();
    await phone.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
    check("iPhone: notes inside components work", ((await bubble(phone)) || "").includes("starter Trend Group"), await bubble(phone));
    check("iPhone: no browser errors", errors.length === 0, errors.join("; "));

    const desk = await browser.newPage({ viewport: { width: 1200, height: 800 } });
    await desk.goto(url);
    await desk.waitForFunction(() => window.ready);
    await desk.click("#reading");
    check("desktop: a click adds nothing (the hover note does that)", (await bubble(desk)) === null);
    await desk.evaluate(() => window.tapExplain({ data: { on: true } }));
    await desk.click("#act");
    check("Explain mode: a click explains instead of pressing", (await bubble(desk)) === "Run now on 12 assets" && (await clicks(desk)) === 0);
    check("Explain mode: the help cursor shows", (await desk.$eval("#act", (b) => getComputedStyle(b).cursor)) === "help");
    await desk.evaluate(() => window.tapExplain({ data: { on: false } }));
    await desk.click("#act");
    check("Explain mode off: buttons work again", (await clicks(desk)) === 1);
  } catch (e) {
    check("ran to the end", false, String(e).slice(0, 300));
  } finally {
    await browser.close();
  }
  const lines = ["# Tap to explain in a browser", "", "| Check | Result | Detail |", "|---|---|---|"];
  results.forEach((r) => lines.push(`| ${r.name} | ${r.ok ? "pass" : "FAIL"} | ${String(r.detail).replace(/\|/g, "/")} |`));
  fs.writeFileSync(path.join(dir, "onboarding.md"), lines.join("\n") + "\n");
  console.log(lines.join("\n"));
  process.exit(results.every((r) => r.ok) ? 0 : 1);
})();
