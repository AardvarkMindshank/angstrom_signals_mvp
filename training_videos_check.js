// Browser check for the training-video player (training_videos_check_app.py): open a video from its link (in its own
// window), move with Next, Back and Start, pick from the list, on a desktop and on an iPhone. Saves pictures to <out>/.
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
    console.log(`${label}: ${await page.locator("a.ang-tv-link", { hasText: "Watch: 3" }).count()} matching buttons`);
    const open3 = page.locator("a.ang-tv-link", { hasText: "Watch: 3 · Signal Groups" }).filter({ visible: true }).first();
    await open3.waitFor({ timeout: 60000 });
    await page.screenshot({ path: `${out}/${label}_links.png`, fullPage: true });
    const [win] = await Promise.all([page.waitForEvent("popup", { timeout: 30000 }), open3.click()]);
    check(`${label}: opens in its own window`, !!win && win.url().includes("view=video"), win ? win.url() : "none");
    check(`${label}: the page underneath stays put`, !(await page.locator('[role="dialog"]').count()));
    const dialog = win.locator("body");
    await win.locator("video").first().waitFor({ timeout: 60000 });
    await win.waitForTimeout(1500);
    const src = await dialog.locator("video").first().getAttribute("src").catch(() => null);
    check(`${label}: opens at video 3`, !!src && src.includes("03-signal-groups"), src || "no video");
    check(`${label}: says 3 of 5`, (await dialog.innerText()).includes("3 of 5"));
    await win.screenshot({ path: `${out}/${label}_player.png` });
    const srcNow = async () => (await dialog.locator("video").first().getAttribute("src")) || "";
    await dialog.getByRole("button", { name: "Next", exact: true }).filter({ visible: true }).first().click(); await win.waitForTimeout(1500);
    check(`${label}: Next goes to 4`, (await srcNow()).includes("04-signal-sets"));
    await dialog.getByRole("button", { name: "Back", exact: true }).filter({ visible: true }).first().click(); await win.waitForTimeout(1500);
    await dialog.getByRole("button", { name: "Back", exact: true }).filter({ visible: true }).first().click(); await win.waitForTimeout(1500);
    check(`${label}: Back twice goes to 2`, (await srcNow()).includes("02-signals"));
    await dialog.getByRole("button", { name: "Start", exact: true }).filter({ visible: true }).first().click(); await win.waitForTimeout(1500);
    check(`${label}: Start goes to 1`, (await srcNow()).includes("01-angstrom-lattice-at-a-glance"));
    check(`${label}: Back and Start are off on the first video`,
      await dialog.getByRole("button", { name: "Back", exact: true }).filter({ visible: true }).first().isDisabled() && await dialog.getByRole("button", { name: "Start", exact: true }).filter({ visible: true }).first().isDisabled());
    await dialog.locator("summary", { hasText: "All videos" }).filter({ visible: true }).first().click(); await win.waitForTimeout(800);
    await dialog.locator("button", { hasText: "Overextended rally" }).filter({ visible: true }).first().click(); await win.waitForTimeout(1500);
    check(`${label}: the list jumps to a worked example`, (await srcNow()).includes("w2-overextended-rally"));
    check(`${label}: worked examples count on their own`, (await dialog.innerText()).includes("2 of 4"));
    await win.screenshot({ path: `${out}/${label}_example.png` });
    const wide = await win.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(`${label}: no sideways scrolling`, wide <= 1, `${wide} px`);
    await win.close();
    if (label === "desktop") {
      const ai = page.locator(".ang-ai-btn").first();
      await ai.waitFor({ timeout: 30000 });
      const [adv] = await Promise.all([page.waitForEvent("popup", { timeout: 30000 }), ai.click()]);
      await adv.waitForTimeout(5000);
      check("desktop: ✨ AI opens the Assistant in its own window", adv.url().includes("view=advisor")
        && (await adv.locator("body").innerText()).includes("AI Navigator"), adv.url());
      // A pasted screenshot shows as a thumbnail ready to send (simulated paste of a small PNG).
      await adv.waitForSelector(".ang-add", { timeout: 30000 }).catch(() => null);
      await adv.evaluate(async () => {
        const c = document.createElement("canvas"); c.width = 40; c.height = 30;
        c.getContext("2d").fillRect(0, 0, 40, 30);
        const blob = await new Promise((r) => c.toBlob(r, "image/png"));
        const dt = new DataTransfer(); dt.items.add(new File([blob], "shot.png", { type: "image/png" }));
        document.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true }));
      });
      await adv.waitForTimeout(3000);
      check("desktop: a pasted screenshot is ready to send", (await adv.locator(".ang-shot img").count()) === 1);
      await adv.screenshot({ path: `${out}/advisor_window.png` });
      await adv.close();
    }
    await page.close();
  }
  await browser.close();
  fs.writeFileSync(`${out}/results.json`, JSON.stringify(results, null, 1));
  if (results.some((r) => !r[1])) process.exit(1);
})();
