// Browser check: what Angstrom Signals provides sits in folded "Provided by Angstrom Signals" sections at the top of
// Signal Groups, Signal Sets and Prism Scan, and the setting hides them. Usage: node provided_check.js <url> <out>
const fs = require("fs");
const { chromium } = require("playwright");

(async () => {
  const [url, out] = [process.argv[2], process.argv[3] || "out/ui"];
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const results = [];
  const check = (name, ok, note = "") => { results.push([name, ok]); console.log(`| ${name} | ${ok ? "pass" : "FAIL"} | ${note} |`); };
  for (const [label, q] of [["shown", "1"], ["hidden", "0"]]) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const settle = () => page.waitForTimeout(2500);
    await page.goto(`${url}?section=groups&seed=pullback&provided=${q}`);
    await page.waitForSelector(".lat", { timeout: 120000 }); await settle();
    const box = page.locator('[data-testid="stSelectbox"]').filter({ hasText: "Start from" }).first();
    await box.locator("input").first().click({ force: true }); await page.waitForTimeout(800);
    const opts = (await page.locator('[role="option"]').allInnerTexts()).join(" | ");
    await page.keyboard.press("Escape");
    check(`${label}: Start from lists only new and your own`, opts.includes("My Trend") && !opts.includes("starter"), opts);
    const starterSection = await page.locator('[data-testid="stExpander"]').filter({ hasText: "Provided by Angstrom Signals" }).count();
    check(`${label}: Groups' provided section ${q === "1" ? "is there" : "is gone"}`, (starterSection > 0) === (q === "1"));
    if (q === "1") {
      await page.locator('[data-testid="stExpander"] summary').filter({ hasText: "Provided by Angstrom Signals" }).first().click();
      await page.waitForTimeout(600);
      await page.getByRole("button", { name: /Copy/ }).first().click(); await settle();
      const name = await page.locator('.lat input[aria-label="Group name"]').first().inputValue();
      check("shown: Copy starts from the starter", /copy/i.test(name), name);
    }
    await page.screenshot({ path: `${out}/${label}_groups.png` });

    await page.locator("button").filter({ hasText: "Signal Sets" }).first().click(); await settle();
    const fold = await page.locator(".lat .lib details.prov").count();
    const lib = await page.locator(".lat .lib").first().innerText();
    check(`${label}: Set library ${q === "1" ? "folds the starters at the top" : "has no starters"}`,
      q === "1" ? fold === 1 && lib.toLowerCase().indexOf("provided by angstrom signals") < lib.toLowerCase().indexOf("your groups") : fold === 0);
    check(`${label}: your Groups listed`, lib.includes("My Trend"));
    await page.screenshot({ path: `${out}/${label}_sets.png` });

    await page.locator("button").filter({ hasText: "Prism Scan" }).first().click(); await settle();
    const pfold = await page.locator(".lat.prism .lib details.prov").count();
    const plib = await page.locator(".lat.prism .lib").first().innerText();
    check(`${label}: Prism library ${q === "1" ? "folds the examples" : "has no examples"}`,
      (q === "1" ? pfold === 1 : pfold === 0 && !plib.includes("demo")) && plib.includes("Pullback"));
    await page.screenshot({ path: `${out}/${label}_prism.png` });
    await page.close();
  }
  await browser.close();
  if (results.some((r) => !r[1])) process.exit(1);
})();
