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
    const last = async () => { await page.waitForTimeout(80); return page.evaluate(() => (window.sent.length ? window.sent[window.sent.length - 1][1] : null)); };

    await page.click('button[aria-label="Add Stochastic %K (14, 3) to the Group"]');
    let m = await last();
    check("tap + adds a signal", m && m.members.some((x) => x.id === "stochastic.level"));

    await page.locator(".card").first().locator("button[aria-pressed]").nth(1).click();
    m = await last();
    check("a role button changes the role", m && m.members[0].role === "condition");

    const disabled = await page.$eval('button[aria-label="Add RSI divergence to the Group"]', (b) => !!b);
    check("signals without a standard score are listed", disabled);

    await page.click('button[title="Check this rule earlier"]:not([disabled])');
    m = await last();
    check("rules reorder with the arrows", m && m.rules[0].label === "Bearish" && m.rules[1].label === "Bullish");

    await page.waitForTimeout(80);
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

    await page.click('button[title="Add a veto (when true, every label becomes Vetoed)"]');
    m = await last();
    check("a veto can be added", m && m.conditions && m.conditions.length === 1 && m.conditions[0].kind === "veto");
    await page.click('button[title="Reported as met or not met."]');
    m = await last();
    check("a veto can be turned into a confirmation", m && m.conditions[0].kind === "confirmation");

    await page.waitForTimeout(80);
    await page.fill('input[aria-label="Search signals"]', "volume");
    const chips = await page.$$eval(".chip", (cs) => cs.length);
    check("search filters the list", chips >= 1 && chips <= 4, `${chips} chips`);

    const injected = await page.evaluate(() => document.querySelectorAll("#host script, #host img").length);
    check("page text is never inserted as HTML", injected === 0);
    await page.fill('input[aria-label="Search signals"]', "");
    await page.waitForTimeout(80);
    const instant = await page.evaluate(() => {
      // the harness, like Streamlit, only answers later; the editor must show the change in the same moment
      const before = document.querySelectorAll(".lat .card").length;
      const add = document.querySelector('button[aria-label="Add MACD line to the Group"]');
      if (!add) return "no button";
      add.click();
      return document.querySelectorAll(".lat .card").length - before;
    });
    check("an added signal shows at once, without waiting for Python", instant === 1, String(instant));
    check("no browser errors", errors.length === 0, errors.join("; "));

    const ipad = await browser.newPage({ ...devices["iPad (gen 7)"] });
    await ipad.goto(url);
    await ipad.waitForFunction(() => window.ready);
    await ipad.screenshot({ path: path.join(dir, "editor_ipad.png"), fullPage: true });
    const wide = await ipad.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
    check("iPad width: no sideways scrolling", wide);
    // ------------------------------------------------------------ the Set editor
    const sp = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
    const serrors = [];
    sp.on("pageerror", (e) => serrors.push(e.message));
    await sp.goto("file://" + path.resolve(dir, "set_editor.html"));
    await sp.waitForFunction(() => window.ready);
    await sp.screenshot({ path: path.join(dir, "set_editor_desktop.png"), fullPage: true });
    const slast = async () => { await sp.waitForTimeout(80); return sp.evaluate(() => (window.sent.length ? window.sent[window.sent.length - 1][1] : null)); };
    check("Set: the saved decision line is shown", (await sp.$$(".rule")).length === 1);
    for (const s of await sp.locator("details.prov:not([open]) > summary").all()) await s.click();   // provided starters are folded
    await sp.click('button[aria-label="Add Flow v1 to the Set"]');
    let s = await slast();
    check("Set: tap + adds a Group", s && s.groups.length === 2);
    await sp.click('button[aria-label="Add RSI (14) to the Set"]');
    s = await slast();
    check("Set: tap + adds a single signal as a Condition", s && s.standalone.length === 1 && s.standalone[0].role === "condition");
    await sp.waitForTimeout(80);
    await sp.selectOption('select[aria-label="Which asset Flow v1 is read on"]', "equity");
    await sp.waitForTimeout(80);
    await sp.fill('input[aria-label="Fixed asset for Flow v1"]', "coin");
    await sp.press('input[aria-label="Fixed asset for Flow v1"]', "Tab");
    s = await slast();
    check("Set: a Group can be read on a fixed asset (E4)", s && s.groups.some((g) => g.subject && g.subject.id === "coin" && g.subject.kind === "equity"));
    await sp.click('button[title="Add a box where any one of its lines is enough"]');
    s = await slast();
    check("Set: an ANY box can be added", s && s.lines.some((l) => Array.isArray(l.any)));
    await sp.click('button[title="Add a line that must hold"]');
    s = await slast();
    check("Set: a line can be added", s && s.lines.length >= 2);
    await sp.click('button[aria-label="Remove Trend (with labels) v1"]');
    s = await slast();
    check("Set: removing a Group removes the lines that tested it",
          s && s.groups.length === 1 && s.groups[0].key === "flow"
            && s.lines.every((l) => (l.any || [l]).every((x) => x.group !== "trend_with_labels")));
    check("Set: no browser errors", serrors.length === 0, serrors.join("; "));
    const sipad = await browser.newPage({ ...devices["iPad (gen 7)"] });
    await sipad.goto("file://" + path.resolve(dir, "set_editor.html"));
    await sipad.waitForFunction(() => window.ready);
    await sipad.screenshot({ path: path.join(dir, "set_editor_ipad.png"), fullPage: true });
    check("Set: iPad width without sideways scrolling",
          await sipad.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
  } finally {
    await browser.close();
  }
  const lines = ["# Lattice editor in a browser", "", "| Check | Result | Detail |", "|---|---|---|"];
  results.forEach((r) => lines.push(`| ${r.name} | ${r.ok ? "pass" : "FAIL"} | ${r.detail} |`));
  fs.writeFileSync(path.join(dir, "lattice_browser.md"), lines.join("\n") + "\n");
  console.log(lines.join("\n"));
  process.exit(results.every((r) => r.ok) ? 0 : 1);
})();
