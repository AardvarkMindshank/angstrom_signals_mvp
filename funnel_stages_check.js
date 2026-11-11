// Funnel stages board in a real browser (CI, chart job). Usage: node funnel_stages_check.js out/funnel_stages
// Opens the harness written by funnel_stages_check.py, taps and drags through the board, checks each action it sends
// back, and saves screenshots (desktop and iPhone width). Exits 1 on any failure.
const path = require("path");
const { chromium, devices } = require("playwright");

(async () => {
  const dir = process.argv[2] || "out/funnel_stages";
  const url = "file://" + path.resolve(dir, "board.html");
  const results = [];
  const check = (name, ok, detail) => results.push({ name, ok: !!ok, detail: detail || "" });
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await page.goto(url);
    await page.waitForFunction(() => window.ready);
    const last = async () => { await page.waitForTimeout(60); return page.evaluate(() => (window.sent.length ? window.sent[window.sent.length - 1][1] : null)); };
    const drag = (chipSel, dropSel) => page.evaluate(([c, d]) => {
      const chip = document.querySelector(c), drop = document.querySelector(d);
      const dt = new DataTransfer();
      chip.dispatchEvent(new DragEvent("dragstart", { dataTransfer: dt, bubbles: true }));
      drop.dispatchEvent(new DragEvent("dragover", { dataTransfer: dt, bubbles: true, cancelable: true }));
      drop.dispatchEvent(new DragEvent("drop", { dataTransfer: dt, bubbles: true, cancelable: true }));
    }, [chipSel, dropSel]);

    const n = (await page.$$(".stage")).length;
    check("the funnel's stages show, with the Set list beside them", n === 4 && await page.$(".lib") && await page.$(".split"), n + " stages");
    const prov = await page.$("details.prov");
    check("provided Sets are folded, Your Sets below", prov && !(await prov.evaluate((d) => d.open)) &&
      (await page.$$eval(".lib .cat", (c) => c.map((x) => x.textContent))).includes("Your Sets"));
    const widths = await page.$$eval(".stage", (s) => s.map((x) => x.getBoundingClientRect().width));
    check("the stages narrow down the funnel", widths.every((w, i) => i === 0 || w < widths[i - 1]), widths.map(Math.round).join(" > "));
    check("an older Set shows ⬆", (await page.$$(".stage .pill.upd")).length === 1);
    await page.screenshot({ path: path.join(dir, "stages_desktop.png"), fullPage: true });

    await drag(".lib > div > .chip", ".stage:nth-of-type(2)");
    let a = await last();
    check("dragging a Set onto a stage puts it there", a && a.op === "set" && a.stage === 1 && a.set === "saved:cfg1:1", JSON.stringify(a));
    await drag(".lib > div > .chip", ".addstage");
    a = await last();
    check("dragging a Set onto Add a stage adds one", a && a.op === "add" && a.set === "saved:cfg1:1");

    await page.click('button[aria-label="Add a stage that checks My daily trend"]');
    a = await last();
    check("+ with no stage selected adds a stage", a && a.op === "add");
    await page.click(".stage:nth-of-type(3) .setrow");
    check("tapping a stage selects it", await page.$(".stage:nth-of-type(3).sel"));
    await page.click('button[aria-label="Use My daily trend in stage 3"]');
    a = await last();
    check("+ with a stage selected puts the Set there", a && a.op === "set" && a.stage === 2);

    await page.selectOption(".stage:nth-of-type(1) select", "4h");
    a = await last();
    check("the check timeframe can be changed", a && a.op === "tf" && a.stage === 0 && a.tf === "4h");
    await page.fill(".stage:nth-of-type(1) input.lab", "Weekly trend");
    await page.press(".stage:nth-of-type(1) input.lab", "Tab");
    a = await last();
    check("a stage can be renamed", a && a.op === "label" && a.label === "Weekly trend");
    await page.click('.stage:nth-of-type(2) button[aria-label="Move this stage down"]');
    a = await last();
    check("a stage moves", a && a.op === "move" && a.stage === 1 && a.dir === 1);
    await page.click('.stage:nth-of-type(4) button[aria-label="Remove this stage"]');
    a = await last();
    check("a stage can be removed", a && a.op === "remove" && a.stage === 3);
    await page.click(".stage .pill.upd");
    a = await last();
    check("⬆ upgrades the stage's Set", a && a.op === "upgrade" && a.stage === 1);
    await page.fill('input[aria-label="Filter Sets"]', "My daily");
    check("the Set filter narrows the list", (await page.$$(".lib .chip")).length === 1);
    check("no browser errors", errors.length === 0, errors.join(" | "));

    const phone = await browser.newPage({ ...devices["iPhone 13"] });
    await phone.goto(url);
    await phone.waitForFunction(() => window.ready);
    const over = await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check("iPhone width: no sideways scrolling", over <= 0, over + " px too wide");
    const btn = await phone.$eval(".stage .ctl button", (b) => Math.round(b.getBoundingClientRect().height));
    check("iPhone width: buttons are thumb-sized", btn >= 44, btn + "px");
    await phone.screenshot({ path: path.join(dir, "stages_iphone.png"), fullPage: true });
  } finally {
    await browser.close();
  }
  console.log("| check | result | detail |\n|---|---|---|");
  results.forEach((r) => console.log(`| ${r.name} | ${r.ok ? "pass" : "FAIL"} | ${r.detail} |`));
  process.exit(results.every((r) => r.ok) ? 0 : 1);
})();
