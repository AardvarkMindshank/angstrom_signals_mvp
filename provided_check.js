// Browser check: the 🔰 switch hides and shows the provided starters, example Sets and built-in alerts.
// Usage: node provided_check.js http://127.0.0.1:8611/ out/ui
const fs = require("fs");
const { chromium } = require("playwright");

(async () => {
  const [url, out] = [process.argv[2], process.argv[3] || "out/ui"];
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const results = [];
  const check = (name, ok, note = "") => { results.push([name, ok]); console.log(`| ${name} | ${ok ? "pass" : "FAIL"} | ${note} |`); };
  const settle = async () => { await page.waitForTimeout(2500); };
  const options = async () => {
    const box = page.locator('[data-testid="stSelectbox"]').filter({ hasText: "Start from" }).first();
    await box.locator("input").first().click({ force: true });
    await page.waitForTimeout(800);
    const texts = await page.locator('[role="option"]').allInnerTexts();
    await page.keyboard.press("Escape");
    return texts.join(" | ");
  };

  await page.goto(url + "?section=groups&seed=pullback"); await page.waitForSelector(".lat", { timeout: 120000 }); await settle();
  let opts = await options();
  check("shown: starters listed with 🔰", opts.includes("🔰 Trend"), opts.slice(0, 120));
  await page.screenshot({ path: `${out}/groups_shown.png` });
  await page.getByRole("button", { name: /Hide provided/ }).first().click(); await settle();
  opts = await options();
  check("hidden: no starters in Start from", !opts.includes("🔰") && opts.includes("My Trend"), opts.slice(0, 120));
  check("hidden: the switch offers to show 5", await page.getByRole("button", { name: /Show 5 provided/ }).count() > 0);
  await page.screenshot({ path: `${out}/groups_hidden.png` });

  await page.locator("button").filter({ hasText: "Signal Sets" }).first().click(); await settle();
  const lib = await page.locator(".lat .lib").first().innerText();
  check("hidden: Set library has My Trend, not the starters", lib.includes("My Trend") && !lib.includes("provided starter"));
  await page.screenshot({ path: `${out}/sets_hidden.png` });

  await page.locator("button").filter({ hasText: "Prism Scan" }).first().click(); await settle();
  const prismLib = await page.locator(".lat.prism .lib").first().innerText();
  check("hidden: Prism lists your Set, not the examples", prismLib.includes("Pullback") && !prismLib.includes("provided example"));
  await page.getByRole("button", { name: /Show \d+ provided/ }).first().click(); await settle();
  const again = await page.locator(".lat.prism .lib").first().innerText();
  check("shown again: examples back with 🔰", again.includes("🔰 provided example"));
  await page.screenshot({ path: `${out}/prism_shown.png` });
  await browser.close();
  if (results.some((r) => !r[1])) process.exit(1);
})();
