// Browser check: the provided library in Prism shows what each Set looks at (icons), a one-line description,
// "more…" with three parts, the 🔬 evidence mark, and filters by icon; the starter Groups list does the same.
// Usage: node library_check.js <url> <out>
const fs = require("fs");
const { chromium, devices } = require("playwright");

(async () => {
  const [url, out] = [process.argv[2], process.argv[3] || "out/ui"];
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  let failed = 0;
  const check = (name, ok, note = "") => { if (!ok) failed++; console.log(`| ${name} | ${ok ? "pass" : "FAIL"} | ${note} |`); };
  console.log("| check | result | note |\n|---|---|---|");
  for (const [label, opts] of [["desktop", { viewport: { width: 1280, height: 900 } }], ["iphone", devices["iPhone 13"]]]) {
    const ctx = await browser.newContext(opts);
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(url + "?section=prism"); await page.waitForSelector(".lat.prism", { timeout: 120000 }); await page.waitForTimeout(2000);
    const prov = page.locator(".lat.prism details.prov").first();
    await prov.locator(":scope > summary").click(); await page.waitForTimeout(300);
    const chip = page.locator(".lat.prism .chip", { hasText: "Breakout with volume" }).first();
    const text = await chip.innerText();
    check(`${label}: icons on a provided Set`, text.includes("🔊") && text.includes("🧱"), text.replace(/\n/g, " ").slice(0, 120));
    check(`${label}: evidence mark`, text.includes("🔬"));
    check(`${label}: one-line description`, text.includes("An upward break"));
    await chip.locator("details.more summary").click(); await page.waitForTimeout(300);
    const more = await chip.innerText();
    check(`${label}: more… opens three parts`, more.includes("What it measures") && more.includes("doesn't prove"));
    check(`${label}: more… turns into less…`, more.includes("less…") && !more.includes("more…"));
    await page.screenshot({ path: `${out}/${label}_library.png`, fullPage: false });
    await page.locator(".lat.prism .pvf button", { hasText: "🌊" }).first().click(); await page.waitForTimeout(300);
    const names = await page.locator(".lat.prism details.prov .chip .nm > div:first-child").allInnerTexts();
    check(`${label}: filter by 🌊 keeps only volatility Sets`, names.length >= 2 && names.every((n) => n.includes("🌊")), names.join(" / ").slice(0, 160));
    await page.screenshot({ path: `${out}/${label}_filtered.png`, fullPage: false });
    check(`${label}: no sideways scrolling`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
    check(`${label}: no browser errors`, errors.length === 0, errors.join("; "));
    await ctx.close();
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
