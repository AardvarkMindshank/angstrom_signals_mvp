// Browser check: 🔍 Why these readings shows one block per column, the clicked one open, parts in plain words, a
// Lattice button in each, and no sideways scrolling on a phone. Usage: node why_check.js <url> <out>
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
    await page.goto(url); await page.waitForSelector("[data-testid='stExpander']", { timeout: 120000 }); await page.waitForTimeout(2500);
    const titles = await page.locator("[data-testid='stExpander'] summary").allInnerTexts();
    check(`${label}: a block per column`, titles.length === 6, titles.join(" / "));
    check(`${label}: Trend shows its number and label`, titles.some((t) => /📈 Trend · [+-]?\d+ · /.test(t)));
    check(`${label}: the waiting hourly column says so`, titles.some((t) => t.includes("Hourly dip · no answer yet")));
    // Streamlit keeps [open] on every expander; the arrow icon says which are expanded.
    const expanded = (ts) => ts.filter((t) => t.includes("keyboard_arrow_down"));
    const open = expanded(titles);
    check(`${label}: the clicked column is open`, open.some((t) => t.includes("Pullback")) && !open.some((t) => t.includes("Trend ·")), open.join(" / "));
    const body = await page.locator("[data-testid='stExpander']", { hasText: "Pullback" }).last().innerText();
    check(`${label}: Set lines with their readings`, body.includes("reading:"), body.slice(0, 120));
    check(`${label}: the Set says how long it has been Yes or No`, /(Yes|No|Unknown) for (\d+ days?|all of the last)/.test(body), body.slice(0, 200));
    const boxes = await page.locator("[data-testid='stExpander']", { hasText: "Pullback" }).last().locator("span[aria-label^='Last ']").count();
    check(`${label}: the Set's last 30 days as a strip`, boxes === 1);
    check(`${label}: a Lattice button`, await page.getByRole("button", { name: /Open in Lattice/ }).filter({ visible: true }).count() >= 1);
    await page.locator("summary", { hasText: "Trend ·" }).first().click(); await page.waitForTimeout(600);
    const trend = await page.locator("[data-testid='stExpander']", { hasText: "Trend ·" }).allInnerTexts();
    check(`${label}: Trend parts in plain words`, trend.join(" ").includes("Moving averages") && trend.join(" ").includes("vs 200-day"));
    check(`${label}: no named views`, !trend.join(" ").includes("Named views"));
    const svg = await page.locator("[data-testid='stExpander']", { hasText: "Trend ·" }).first().locator("img[alt^='Score over']").count();
    check(`${label}: Trend has its 30-day line`, svg === 1);
    check(`${label}: Trend says what changed this week`, /Trend reads \w+ \([+-]?\d+\)/.test(trend.join(" ")) && trend.join(" ").includes("this week"), trend.join(" ").slice(0, 200));
    await page.locator("[data-testid='stExpander']", { hasText: "Trend ·" }).first().screenshot({ path: `${out}/${label}_trend_card.png` });
    check(`${label}: no sideways scrolling`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
    check(`${label}: no browser errors`, errors.length === 0, errors.join("; "));
    await page.screenshot({ path: `${out}/${label}.png`, fullPage: true });
    await ctx.close();
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
