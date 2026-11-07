// Browser check: the table's Groups and Sets sections fold sideways and remember it; Set and Group cells explain on
// hover and open Lattice on click; sorting by a Set column puts Yes first. Usage: node table_columns_check.js <url> <out>
const fs = require("fs");
const { chromium, devices } = require("playwright");

(async () => {
  const [url, out] = [process.argv[2], process.argv[3] || "out/ui"];
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const results = [];
  const check = (name, ok, note = "") => { results.push([name, ok]); console.log(`| ${name} | ${ok ? "pass" : "FAIL"} | ${note} |`); };
  for (const [label, opts] of [["desktop", { viewport: { width: 1280, height: 700 } }], ["iphone", devices["iPhone 13"]]]) {
    const ctx = await browser.newContext(opts);
    const page = await ctx.newPage();
    await page.goto(url); await page.waitForSelector("table.ang-table", { timeout: 120000 }); await page.waitForTimeout(1500);
    const visible = async (sel) => page.locator(sel).first().isVisible();
    check(`${label}: both sections open at first`, await visible("td[data-sec='s']") && !(await visible("td[data-sec-folded='s']")));
    await page.screenshot({ path: `${out}/${label}_open.png` });
    await page.locator("th[data-sec='s'] button[data-fold='s']").first().click(); await page.waitForTimeout(300);
    check(`${label}: Sets fold to one column`, !(await visible("td[data-sec='s']")) && await visible("td[data-sec-folded='s']"));
    const summary = await page.locator("td[data-sec-folded='s']").first().innerText();
    check(`${label}: the folded column counts Yes`, summary.includes("1✓"), summary);
    await page.screenshot({ path: `${out}/${label}_folded.png` });
    await page.reload(); await page.waitForSelector("table.ang-table"); await page.waitForTimeout(1500);
    check(`${label}: folding is remembered`, !(await visible("td[data-sec='s']")));
    await page.locator("th[data-sec-folded='s'] button[data-fold='s']").first().click(); await page.waitForTimeout(300);
    check(`${label}: and opens again`, await visible("td[data-sec='s']"));
    const tip = await page.locator("td[data-sec='s'] button").first().getAttribute("title");
    check(`${label}: a Set cell explains itself`, tip && tip.startsWith("Pullback in an uptrend: Yes"), tip);
    await page.locator("th[data-sec='s'] button[data-sort-col='4']").first().click(); await page.waitForTimeout(300);
    const first = await page.locator("tbody tr").first().innerText();
    check(`${label}: sorting a Set column puts Yes first`, first.startsWith("Bitcoin"), first.slice(0, 20));
    await page.locator("td[data-sec='s'] button").nth(1).click(); await page.waitForTimeout(2500);
    const picked = await page.locator("#picked").innerText();
    check(`${label}: clicking a Set opens it in Lattice`, /lattice\|sets\|s[12]/.test(picked), picked);
    const wide = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(`${label}: no sideways page scrolling`, wide <= 1, `${wide} px`);
    await ctx.close();
  }
  await browser.close();
  if (results.some((r) => !r[1])) process.exit(1);
})();
