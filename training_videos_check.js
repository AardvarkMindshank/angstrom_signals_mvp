// Browser check for the training-video player (training_videos_check_app.py): open a video from its link, move with
// Next, Back and Start, pick from the list, on a desktop and on an iPhone. Saves pictures to <out>/.
// Usage: node training_videos_check.js http://127.0.0.1:8611/ out/training_check
const fs = require("fs");
const { chromium, devices } = require("playwright");

(async () => {
  const [url, out] = [process.argv[2], process.argv[3] || "out/training_check"];
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const results = [];
  const check = (name, ok, note = "") => { results.push([name, ok, note]); console.log(`| ${name} | ${ok ? "pass" : "FAIL"} | ${note} |`); };
  for (const [label, opts] of [["desktop", { viewport: { width: 1280, height: 800 } }], ["iphone", devices["iPhone 13"]]]) {
    const page = await browser.newPage(opts);
    await page.goto(url);
    await page.waitForTimeout(8000);
    await page.screenshot({ path: `${out}/${label}_loaded.png`, fullPage: true });
    console.log(`${label}: ${await page.locator("button", { hasText: "Watch: 3" }).count()} matching buttons`);
    const open3 = page.locator("button", { hasText: "Watch: 3 · Signal Groups" }).filter({ visible: true }).first();
    await open3.waitFor({ timeout: 60000 });
    await page.screenshot({ path: `${out}/${label}_links.png`, fullPage: true });
    await open3.click();
    const dialog = page.locator('[role="dialog"]');
    await dialog.waitFor({ timeout: 30000 });
    await page.waitForTimeout(1500);
    const src = await dialog.locator("video").first().getAttribute("src").catch(() => null);
    check(`${label}: opens at video 3`, !!src && src.includes("03-signal-groups"), src || "no video");
    check(`${label}: says 3 of 5`, (await dialog.innerText()).includes("3 of 5"));
    await page.screenshot({ path: `${out}/${label}_player.png` });
    const srcNow = async () => (await dialog.locator("video").first().getAttribute("src")) || "";
    await dialog.getByRole("button", { name: "Next", exact: true }).first().click(); await page.waitForTimeout(1500);
    check(`${label}: Next goes to 4`, (await srcNow()).includes("04-signal-sets"));
    await dialog.getByRole("button", { name: "Back", exact: true }).first().click(); await page.waitForTimeout(1500);
    await dialog.getByRole("button", { name: "Back", exact: true }).first().click(); await page.waitForTimeout(1500);
    check(`${label}: Back twice goes to 2`, (await srcNow()).includes("02-signals"));
    await dialog.getByRole("button", { name: "Start", exact: true }).first().click(); await page.waitForTimeout(1500);
    check(`${label}: Start goes to 1`, (await srcNow()).includes("01-angstrom-lattice-at-a-glance"));
    check(`${label}: Back and Start are off on the first video`,
      await dialog.getByRole("button", { name: "Back", exact: true }).first().isDisabled() && await dialog.getByRole("button", { name: "Start", exact: true }).first().isDisabled());
    await dialog.locator("summary", { hasText: "All videos" }).first().click(); await page.waitForTimeout(800);
    await dialog.locator("button", { hasText: "Overextended rally" }).first().click(); await page.waitForTimeout(1500);
    check(`${label}: the list jumps to a worked example`, (await srcNow()).includes("w2-overextended-rally"));
    check(`${label}: worked examples count on their own`, (await dialog.innerText()).includes("2 of 3"));
    await page.screenshot({ path: `${out}/${label}_example.png` });
    const wide = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(`${label}: no sideways scrolling`, wide <= 1, `${wide} px`);
    await page.close();
  }
  await browser.close();
  fs.writeFileSync(`${out}/results.json`, JSON.stringify(results, null, 1));
  if (results.some((r) => !r[1])) process.exit(1);
})();
