// The Lattice Group editor inside a real Streamlit server (CI, chart job).
// Usage: node lattice_streamlit_check.js http://127.0.0.1:8597/ out/lattice_streamlit
// Checks the full round trip: an edit in the browser goes to Python, Python checks it, and the page shows the result.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

(async () => {
  const url = process.argv[2] || "http://127.0.0.1:8597/";
  const dir = process.argv[3] || "out/lattice_streamlit";
  fs.mkdirSync(dir, { recursive: true });
  const results = [];
  const check = (name, ok, detail) => results.push({ name, ok: !!ok, detail: detail || "" });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 1100 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const settle = async () => {
    await page.waitForTimeout(600);
    await page.waitForFunction(() => !document.querySelector("[data-testid='stStatusWidgetRunningIcon']"),
      null, { timeout: 60000 }).catch(() => {});
    await page.waitForTimeout(600);
  };
  const text = () => page.evaluate(() => document.body.innerText);
  try {
    await page.goto(url);
    await page.waitForSelector(".lat", { timeout: 90000 });
    await settle();
    check("the editor appears", await page.$(".lat"));
    check("an empty Group cannot be saved", (await text()).includes("Add at least one signal"));

    await page.click('button[aria-label="Add RSI (14) to the Group"]');
    await settle();
    let body = await text();
    check("tap + reaches Python and comes back", (await page.$$(".lat .card")).length === 1);
    check("the description is rewritten", body.includes("averages 1 reading (RSI (14) (1D))"), body.slice(0, 200));
    check("saving is allowed once valid", !body.includes("Add at least one signal"));

    await page.click('.lat button[title="Add a rule that gives this label"]');
    await settle();
    check("a rule can be added", (await page.$$(".lat .rule")).length === 1);

    await page.fill('.lat .rule input[aria-label="Value"]', "130");
    await page.keyboard.press("Tab");
    await settle();
    body = await text();
    check("an out-of-scale threshold blocks saving", body.includes("Can't save") && body.includes("outside"),
          (body.match(/Can't save[^\n]*/) || [""])[0]);
    await page.screenshot({ path: path.join(dir, "lattice_in_streamlit.png"), fullPage: true });
    check("no browser errors", errors.length === 0, errors.join("; "));
  } catch (e) {
    check("ran to the end", false, String(e).slice(0, 300));
  } finally {
    await browser.close();
  }
  const lines = ["# Lattice editor inside Streamlit", "", "| Check | Result | Detail |", "|---|---|---|"];
  results.forEach((r) => lines.push(`| ${r.name} | ${r.ok ? "pass" : "FAIL"} | ${String(r.detail).replace(/\|/g, "/")} |`));
  fs.writeFileSync(path.join(dir, "lattice_streamlit.md"), lines.join("\n") + "\n");
  console.log(lines.join("\n"));
  process.exit(results.every((r) => r.ok) ? 0 : 1);
})();
