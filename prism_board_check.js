// Prism Scans board in a real browser (CI, chart job). Usage: node prism_board_check.js out/prism_board
// Opens the harness written by prism_board_check.py, clicks, taps and drags through the board, checks each action it
// sends back, and saves screenshots (desktop and iPhone width). Exits 1 on any failure.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

(async () => {
  const dir = process.argv[2] || "out/prism_board";
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
    const bodies = () => page.$$eval(".scan .body", (b) => b.length);

    check("three scans, all collapsed at first", (await page.$$(".scan")).length === 3 && (await bodies()) === 0);
    const summary = await page.$eval(".scan", (c) => c.querySelector(".head").innerText);
    check("a collapsed scan shows its summary", /Yes \d+\s+No \d+/.test(summary) && /next in/.test(summary) && /v2 available/.test(summary), summary.replace(/\n/g, " "));
    check("the last runs show as dots", (await page.$$('.scan[data-scan="s1"] .dot')).length === 6);
    await page.click('text=Expand all');
    check("Expand all opens every scan", (await bodies()) === 3);
    await page.screenshot({ path: path.join(dir, "board_desktop_open.png"), fullPage: true });
    await page.click('text=Collapse all');
    check("Collapse all closes every scan", (await bodies()) === 0);
    await page.click('.scan[data-scan="s1"] button.chev');
    check("the arrow opens one scan", (await bodies()) === 1 && await page.$('.scan[data-scan="s1"] .body'));

    await page.click('button[aria-label="Start a scan with COIN leads BTC"]');
    let a = await last();
    check("tap + on a Set starts a scan", a && a.op === "create" && a.set === "saved:cfg1:2");

    await page.evaluate(() => {
      const chip = document.querySelector(".lib .chip");
      const drop = document.querySelector(".newdrop");
      const dt = new DataTransfer();
      chip.dispatchEvent(new DragEvent("dragstart", { dataTransfer: dt, bubbles: true }));
      drop.dispatchEvent(new DragEvent("dragover", { dataTransfer: dt, bubbles: true, cancelable: true }));
      drop.dispatchEvent(new DragEvent("drop", { dataTransfer: dt, bubbles: true, cancelable: true }));
    });
    a = await last();
    check("dragging a Set onto the board starts a scan", a && a.op === "create");

    await page.click('button[aria-label="Add Coinbase (COIN) to the selected scan"]');
    a = await last();
    check("tap + on an asset adds it to the open scan", a && a.op === "add_asset" && a.scan === "s1" && a.item.id === "COIN");

    await page.evaluate(() => {
      const chip = document.querySelector(".grpchip");
      const card = document.querySelector('.scan[data-scan="s2"]');
      const dt = new DataTransfer();
      chip.dispatchEvent(new DragEvent("dragstart", { dataTransfer: dt, bubbles: true }));
      card.dispatchEvent(new DragEvent("dragover", { dataTransfer: dt, bubbles: true, cancelable: true }));
      card.dispatchEvent(new DragEvent("drop", { dataTransfer: dt, bubbles: true, cancelable: true }));
    });
    a = await last();
    check("dragging a Watchlist group onto a scan adds it", a && a.op === "add_asset" && a.scan === "s2" && a.item.group === "watchlist");

    await page.click('.scan[data-scan="s1"] button.play');
    a = await last();
    check("▶ runs the scan now", a && a.op === "run" && a.scan === "s1");
    await page.click('.scan[data-scan="s1"] button[aria-label="Run at a past moment"]');
    check("⏪ shows the date and time", await page.$('.scan[data-scan="s1"] input[type="date"]'));
    await page.fill('.scan[data-scan="s1"] input[type="date"]', "2026-10-01");
    await page.click('.scan[data-scan="s1"] >> text=⏪ Run at this moment');
    a = await last();
    check("⏪ runs at the chosen moment", a && a.op === "run_past" && a.date === "2026-10-01" && a.time === "00:05");

    await page.click('.scan[data-scan="s1"] button[aria-label^="Pause"]');
    a = await last();
    check("⏸ pauses", a && a.op === "pause" && a.scan === "s1");
    await page.click('.scan[data-scan="s3"] button[aria-label^="Resume"]');
    a = await last();
    check("a paused scan offers resume", a && a.op === "resume" && a.scan === "s3");
    const before = await page.evaluate(() => window.sent.length);
    await page.click('.scan[data-scan="s2"] button.del');
    check("✕ asks once before deleting", (await page.evaluate(() => window.sent.length)) === before);
    await page.click('.scan[data-scan="s2"] button.del');
    a = await last();
    check("✕ pressed twice deletes", a && a.op === "delete" && a.scan === "s2");

    await page.selectOption('.scan[data-scan="s1"] select[aria-label="Where alerts go"]', "digest");
    a = await last();
    check("the alert channel saves", a && a.op === "alerts" && a.channel === "digest" && a.on_yes === true);
    await page.check('.scan[data-scan="s1"] label:has-text("Turns No") input');
    a = await last();
    check("Turns No can be ticked", a && a.op === "alerts" && a.on_no === true);
    await page.selectOption('.scan[data-scan="s1"] select[aria-label="When the scan runs"]', "times");
    check("set times show their fields", await page.isVisible('.scan[data-scan="s1"] input[aria-label="Times of day"]'));
    await page.fill('.scan[data-scan="s1"] input[aria-label="Times of day"]', "08:00, 20:00");
    await page.press('.scan[data-scan="s1"] input[aria-label="Times of day"]', "Tab");   // saved on change, no button
    a = await last();
    check("the schedule saves", a && a.op === "schedule" && a.runs === "times" && a.times === "08:00, 20:00");
    await page.selectOption('.scan[data-scan="s1"] select[aria-label="Snooze Solana"]', "3");
    a = await last();
    check("a Yes asset can be snoozed", a && a.op === "snooze" && a.key === "crypto:solana" && a.days === 3);
    await page.click('.scan[data-scan="s1"] button[aria-label^="Update"], .scan[data-scan="s1"] .pill.upd');
    a = await last();
    check("the update badge switches to the newer version", a && a.op === "update_set" && a.key === "saved:cfg1:2");

    await page.fill('input[aria-label="Filter Sets"]', "zzz");
    check("the Set filter narrows the list", (await page.$$(".lib .chip button[aria-label^='Start a scan']")).length === 0);
    await page.fill('input[aria-label="Filter Sets"]', "");
    await page.fill('input[aria-label="Filter assets"]', "sol");
    check("the asset filter narrows the list", (await page.$$("button[aria-label$='to the selected scan'].sq")).length === 1);
    await page.fill('input[aria-label="Filter assets"]', "");

    await page.click('text=Expand all');
    await page.screenshot({ path: path.join(dir, "board_desktop.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(100);
    const wide = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check("iPhone width: no sideways scrolling", wide <= 1, `${wide} px too wide`);
    const tap = await page.$eval('.scan[data-scan="s1"] button.play', (b) => b.getBoundingClientRect().height);
    check("iPhone width: buttons are thumb-sized", tap >= 44, `${tap}px`);
    await page.screenshot({ path: path.join(dir, "board_phone.png"), fullPage: true });
    check("no browser errors", errors.length === 0, errors.join("; "));
  } catch (e) {
    check("ran to the end", false, String(e).slice(0, 300));
  } finally {
    await browser.close();
  }
  const lines = ["# Prism Scans board in a browser", "", "| Check | Result | Detail |", "|---|---|---|"];
  results.forEach((r) => lines.push(`| ${r.name} | ${r.ok ? "pass" : "FAIL"} | ${String(r.detail).replace(/\|/g, "/")} |`));
  fs.writeFileSync(path.join(dir, "prism_board.md"), lines.join("\n") + "\n");
  console.log(lines.join("\n"));
  process.exit(results.every((r) => r.ok) ? 0 : 1);
})();
