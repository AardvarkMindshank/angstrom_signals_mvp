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
    // The Group editor: no # tags, each condition on its own line, red remove buttons.
    await page.goto(url + "?section=groups&seed=trend&preset=1"); await page.waitForSelector(".lat .rule", { timeout: 120000 }); await page.waitForTimeout(1500);
    const hashes = await page.locator(".lat .tag", { hasText: /^#$/ }).count();
    check(`${label}: no # tags in the editor`, hashes === 0, String(hashes));
    check(`${label}: conditions sit in their own lines`, await page.locator(".lat .rule .clause").count() > 0);
    const red = await page.locator(".lat button.del").first().evaluate((b) => getComputedStyle(b).color);
    check(`${label}: remove buttons are red`, red === "rgb(220, 38, 38)", red);
    check(`${label}: a drag handle, no arrow buttons`, await page.locator(".lat .rule .grip").count() >= 2
      && await page.locator('.lat button[title="Check this rule earlier"]').count() === 0);
    {   // drag rule 2 above rule 1 with a finger or mouse
      const before = await page.locator(".lat .rule input").first().inputValue();
      const g = await page.locator(".lat .rule .grip").nth(1).boundingBox(), f = await page.locator(".lat .rule .grip").nth(0).boundingBox();
      await page.mouse.move(g.x + g.width / 2, g.y + g.height / 2); await page.mouse.down();
      await page.mouse.move(g.x + g.width / 2, f.y - 20, { steps: 10 }); await page.mouse.up();
      await page.waitForTimeout(2500);
      const after = await page.locator(".lat .rule input").first().inputValue();
      check(`${label}: dragging reorders the rules`, before !== after, before + " → " + after);
    }
    await page.locator(".lat .rule").first().scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${out}/${label}_editor.png`, fullPage: false });
    await ctx.close();
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
