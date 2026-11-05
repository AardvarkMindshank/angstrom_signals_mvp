// Lattice Group editor in a real browser (CI, chart job). Usage: node lattice_component_check.js out/lattice
// Opens the harness written by lattice_component_check.py, taps, clicks and drags through the editor, checks what
// the component sends back, and saves screenshots (desktop and iPad width). Exits 1 on any failure.
const fs = require("fs");
const path = require("path");
const { chromium, devices } = require("playwright");

(async () => {
  const dir = process.argv[2] || "out/lattice";
  const url = "file://" + path.resolve(dir, "editor.html");
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
    await page.screenshot({ path: path.join(dir, "editor_desktop.png"), fullPage: true });
    const last = () => page.evaluate(() => (window.sent.length ? window.sent[window.sent.length - 1][1] : null));

    await page.click('button[aria-label="Add Stochastic %K (14, 3) to the Group"]');
    let m = await last();
    check("tap + adds a signal", m && m.members.some((x) => x.id === "stochastic.level"));

    const roleButtons = await page.$$(".card button[aria-pressed]");
    await roleButtons[1].click();
    m = await last();
    check("a role button changes the role", m && m.members[0].role === "condition");

    const disabled = await page.$eval('button[aria-label="Add RSI divergence to the Group"]', (b) => !!b);
    check("signals without a standard score are listed", disabled);

    await page.click('button[title="Check this rule earlier"]:not([disabled])');
    m = await last();
    check("rules reorder with the arrows", m && m.rules[0].label === "Bearish" && m.rules[1].label === "Bullish");

    await page.evaluate(() => {
      const chip = document.querySelector(".chip");
      const drop = document.querySelector(".drop");
      const dt = new DataTransfer();
      chip.dispatchEvent(new DragEvent("dragstart", { dataTransfer: dt, bubbles: true }));
      drop.dispatchEvent(new DragEvent("dragover", { dataTransfer: dt, bubbles: true, cancelable: true }));
      drop.dispatchEvent(new DragEvent("drop", { dataTransfer: dt, bubbles: true, cancelable: true }));
    });
    m = await last();
    check("dragging a signal onto the Group adds it", m && m.members.length >= 5);

    await page.fill('input[aria-label="Search signals"]', "volume");
    const chips = await page.$$eval(".chip", (cs) => cs.length);
    check("search filters the list", chips >= 1 && chips <= 4, `${chips} chips`);

    const injected = await page.evaluate(() => document.querySelectorAll("#host script, #host img").length);
    check("page text is never inserted as HTML", injected === 0);
    check("no browser errors", errors.length === 0, errors.join("; "));

    const ipad = await browser.newPage({ ...devices["iPad (gen 7)"] });
    await ipad.goto(url);
    await ipad.waitForFunction(() => window.ready);
    await ipad.screenshot({ path: path.join(dir, "editor_ipad.png"), fullPage: true });
    const wide = await ipad.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
    check("iPad width: no sideways scrolling", wide);
  } finally {
    await browser.close();
  }
  const lines = ["# Lattice editor in a browser", "", "| Check | Result | Detail |", "|---|---|---|"];
  results.forEach((r) => lines.push(`| ${r.name} | ${r.ok ? "pass" : "FAIL"} | ${r.detail} |`));
  fs.writeFileSync(path.join(dir, "lattice_browser.md"), lines.join("\n") + "\n");
  console.log(lines.join("\n"));
  process.exit(results.every((r) => r.ok) ? 0 : 1);
})();
