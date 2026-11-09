// What happens on screen in each training video, step by step. The step ids match video/series/<slug>.json; each
// action gets the helpers (helpers.js) and how long the narration for that step lasts (seconds). The recorder waits
// for whichever is longer, the voice or the action.
//
// Editor parts are found by their labels (aria-label), the same ones screen readers use, so a wording change in the
// app shows up here as a missed step in the log, never as a wrong click.

const GROUP_ADD = (name) => `.lat button[aria-label="Add ${name} to the Group"]`;
const SET_ADD = (name) => `.lat button[aria-label="Add ${name} to the Set"]`;
const ADD_LINE = '.lat button[aria-label="Add a line that must hold"]';
const PLAY = ".lat.prism .scan button.play";
const TABLE = ".lat.prism .scan table";

const line = (h, i) => h.page.locator(".lat .rule").nth(i);

// A line in the Set editor: reading (its key), comparison and value.
async function setLine(h, i, reading, op, value) {
  const row = () => line(h, i);
  await h.choose(row().locator('select[aria-label="Reading"]'), reading);
  if (op) await h.choose(row().locator('select[aria-label="Comparison"]'), op);
  if (value !== undefined) {
    const box = row().locator('input[aria-label="Value"]');
    if (await box.count()) await h.type(box, value);
    else await h.choose(row().locator('select[aria-label="Value"]'), value);
  }
}

async function newLine(h) {
  await h.press(ADD_LINE);
}

// A category of the signal list: ring its heading and its signals.
async function category(h, name) {
  await h.clear("demo-tip", "demo-ring");
  const mark = `cat-${name.toLowerCase()}`;
  await h.page.locator(".lat .lib .cat", { hasText: name }).first().evaluate((head, mark) => {
    head.setAttribute("data-demo", mark);
    for (let n = head.nextElementSibling; n && !n.classList.contains("cat"); n = n.nextElementSibling) n.setAttribute("data-demo", mark);
  }, mark);
  await h.ring(h.page.locator(`.lat .lib [data-demo="${mark}"]`));
}

// Save the Set being edited, then scan it on a Watchlist group in Prism Scan.
async function saveAndScan(h, name, group, date) {
  await h.type('.lat input[aria-label="Set name"]', name);
  await h.press('button:has-text("Save as a new Set")');
  await h.wait(900);
  await h.section("Prism Scan");
  await h.press(`.lat.prism button[aria-label="Start a scan with ${name}"] >> visible=true`);   // your Set, not the provided one of the same name
  await h.page.waitForSelector(".lat.prism .scan", { timeout: 60000 });
  await addAssets(h, group);
  await past(h, date);
}

async function addAssets(h, group) {
  await h.press(`.lat.prism button[aria-label="Add ${group} to the selected scan"]`);
  const whole = '.lat.prism .scan button[aria-label="Remove Whole Watchlist"]';
  if (await h.page.locator(whole).count()) await h.press(whole);
}

async function play(h) {
  await h.press(PLAY);
  await h.page.waitForSelector(TABLE, { timeout: 240000 }).catch(() => {});
  await h.settle();
}

// Rewind to a past moment (before the hold-out) and run there: Prism rebuilds what was known at that time.
async function past(h, date) {
  const open = h.page.locator('.lat.prism .scan input[aria-label="Date (UTC)"]');
  if (!(await open.count())) await h.press('.lat.prism .scan button[aria-label="Run at a past moment"]', false);
  await h.glide(open.first());
  await open.first().fill(date);
  await open.first().dispatchEvent("change");
  await h.wait(500);
  await h.press('.lat.prism .scan button[aria-label="Rebuild what was known then, using only data available at that time"]');
  await h.page.waitForSelector(TABLE, { timeout: 240000 }).catch(() => {});
  await h.settle();
}

async function showResults(h) {
  await h.show(TABLE);
  await h.ring(TABLE);
}

// A provided item in Prism's library, by name.
const provided = (h, name) => h.page.locator(".lat.prism .chip", { hasText: name }).first();

module.exports = {
  // ------------------------------------------------------------------------------------------ 1 · at a glance
  "01-angstrom-lattice-at-a-glance": {
    query: "?section=groups&seed=pullback&preset=1",
    setup: async (h) => { await h.diagram(0); await h.wait(600); },
    intro: async (h) => {},
    signals: async (h) => { await h.diagram(1, "signals"); },
    groups: async (h) => { await h.diagram(2, "groups"); },
    sets: async (h) => { await h.diagram(3, "sets"); },
    prism: async (h) => { await h.diagram(4, "prism"); },
    alerts: async (h) => { await h.diagram(5, "alerts"); },
    strategies: async (h) => { await h.diagram(6, "strategies"); },
    cuts: async (h, dur) => {
      const each = Math.max(2500, (dur * 1000 - 1500) / 3);
      await h.clear();
      await h.page.mouse.move(700, 330, { steps: 10 });
      await h.wait(each - 800);
      await h.section("Signal Sets");
      await h.wait(each - 1500);
      await h.section("Prism Scan");
    },
    whole: async (h) => { await h.diagram(7); },
  },

  // ------------------------------------------------------------------------------------------ 2 · signals
  "02-signals": {
    query: "?section=groups",
    setup: async (h) => { await h.diagram(1, "signals"); await h.wait(600); },
    what: async (h, dur) => {
      await h.wait(Math.min(3500, dur * 400));
      await h.clear();
      await h.ring(".lat .lib");
    },
    hover: async (h) => {
      await h.clear("demo-ring");
      await h.tip('.lat .lib .chip:has-text("RSI (14)")', null, "right");
      await h.wait(2600);
      await h.clear("demo-tip");
      await h.press(GROUP_ADD("RSI (14)"));
      const tf = '.lat .card select[aria-label="Timeframe of RSI (14)"]';
      const options = await h.page.locator(tf).first().evaluate((s) => Array.from(s.options).map((o) => o.textContent).join(" · "));
      await h.tip(tf, `Timeframes: ${options}\nAlways the last finished candle.`);
    },
    trend: async (h) => { await category(h, "Trend"); },
    momentum: async (h) => { await category(h, "Momentum"); },
    regime: async (h) => { await category(h, "Regime"); },
    structure: async (h) => { await category(h, "Structure"); },
    volume: async (h) => { await category(h, "Volume"); },
    sentiment: async (h) => { await category(h, "Sentiment"); },
    together: async (h) => { await h.clear(); await h.diagram(3); },
    reason: async (h) => {
      await h.card({ kicker: "Example reading", title: "Trend · Bullish (+42)",
        lines: ["✓ Moving averages: price above the 50- and 200-day averages", "✓ Ichimoku: price above the cloud",
                "✓ MACD line above zero"],
        foot: "An illustration: every reading in Lattice comes with its reasons." });
    },
  },

  // ------------------------------------------------------------------------------------------ 3 · Signal Groups
  "03-signal-groups": {
    query: "?section=groups",
    setup: async (h) => { await h.diagram(2, "groups"); await h.wait(600); },
    what: async (h, dur) => { await h.wait(Math.min(3500, dur * 450)); await h.clear(); },
    start: async (h) => {
      await h.pick("Start from", null);
      await h.wait(400);
      await h.glide('.lat input[aria-label="Group name"]');
    },
    add: async (h) => {
      for (const name of ["Moving averages (50, 200)", "Ichimoku cloud position", "MACD line"]) {
        await h.press(GROUP_ADD(name));
        await h.wait(500);
      }
    },
    roles: async (h) => {
      const first = h.page.locator(".lat .card").first();
      await h.tip(first.locator("button", { hasText: /^Score$/ }));
      await h.wait(2600);
      await h.tip(first.locator("button", { hasText: /^Condition$/ }));
      await h.wait(2200);
      await h.tip(first.locator("button", { hasText: /^Context$/ }));
    },
    rules: async (h) => {
      await h.clear("demo-tip");
      for (const label of ["Bullish", "Bearish"]) {
        await h.choose('.lat select[aria-label="Label for a new rule"]', label);
        await h.press('.lat button[aria-label="Add a rule that gives this label"]');
        await h.wait(700);
      }
      await h.ring('.lat input[aria-label="Label when no rule matches"]');
    },
    unknown: async (h) => {
      await h.clear("demo-ring");
      await h.ring('.lat .fixed:has-text("if a rule cannot be checked")');
    },
    veto: async (h) => {
      await h.clear("demo-ring");
      await h.press(GROUP_ADD("Regime evidence"));
      await h.press(h.page.locator(".lat .card", { hasText: "Regime evidence" }).locator("button", { hasText: /^Condition$/ }));
      await h.press('.lat button[aria-label="Add a veto (when true, every label becomes Vetoed)"]');
      const row = () => h.page.locator('.lat .rule:has(input[aria-label="Name of this veto"])').first();
      await h.type(row().locator('input[aria-label="Name of this veto"]'), "Daily regime is ranging");
      await h.choose(row().locator('select[aria-label="Reading"]'), "regime_observation_1d:state");
      await h.choose(row().locator('select[aria-label="Label"]'), "ranging");
    },
    checks: async (h, dur) => {
      await h.ring(h.page.getByText("Checks", { exact: true }).locator("xpath=ancestor::div[@data-testid='stColumn'][1]"));
      await h.wait(Math.max(1500, dur * 450));
      await h.ring(h.page.getByText("Description", { exact: false }).last().locator("xpath=ancestor::div[@data-testid='stColumn'][1]"));
    },
    save: async (h) => {
      await h.clear("demo-ring");
      await h.top();
      await h.type('.lat input[aria-label="Group name"]', "My Trend");
      await h.wait(1200);                         // let the name reach the page before saving
      await h.press('button:has-text("Save as a new Group")');
      const saved = h.page.getByText("Saved as a new Group").first();
      await h.wait(1200);
      if (!(await saved.isVisible().catch(() => false))) {       // the click landed during a redraw: press again
        console.log("save: no message after the first press; pressing again");
        await h.press('button:has-text("Save as a new Group")');
        await h.wait(1200);
        if (!(await saved.isVisible().catch(() => false))) {
          console.log("save: still no message. Alerts: " + JSON.stringify(await h.page.locator('[data-testid="stAlert"], [data-testid="stException"]').allInnerTexts()));
          console.log("save: buttons: " + JSON.stringify(await h.page.locator('button:has-text("Save")').evaluateAll((b) => b.map((x) => [x.innerText, x.disabled]))));
        }
      }
      await h.pick("Start from", null);          // My Trend is now in the list, as one of yours
    },
    summary: async (h) => {
      await h.card({ kicker: "Saved", title: "My Trend",
        lines: ["✓ One score, from −100 to +100", "✓ Your labels: Bullish, Bearish, otherwise Neutral",
                "✓ Your veto: the daily market is ranging"] });
    },
  },

  // ------------------------------------------------------------------------------------------ 4 · Signal Sets
  "04-signal-sets": {
    query: "?section=sets&seed=trend",
    setup: async (h) => { await h.diagram(3, "sets"); await h.wait(600); },
    what: async (h, dur) => { await h.wait(Math.min(3500, dur * 450)); await h.clear(); },
    idea: async (h) => {
      await h.card({ kicker: "The idea", title: "Pullback in an uptrend",
        lines: ["✓ The main trend is up", "✓ Price has dipped in the short term"] });
    },
    group: async (h) => { await h.clear(); await h.press(SET_ADD("My Trend v1")); },
    signal: async (h) => {
      await h.tip('.lat .lib .chip:has-text("Stochastic %K")', null, "right");
      await h.wait(2600);
      await h.clear("demo-tip");
      await h.press(SET_ADD("Stochastic %K (14, 3)"));
    },
    lines: async (h) => {
      await newLine(h);
      await setLine(h, 0, "outcome:my_trend", null, "bullish");
      await h.wait(800);
      await newLine(h);
      await setLine(h, 1, "member:level_1d:stoch_k", "lte", "30");
    },
    all: async (h) => {
      await h.ring(h.page.locator(".lat .col").filter({ has: h.page.locator(".lbl", { hasText: "ALL · AND" }) }).last());
      await h.wait(2200);
      await h.clear("demo-ring");
      await h.tip('.lat button[aria-label="Add a box where any one of its lines is enough"]');
    },
    returns: async (h) => {
      await h.clear("demo-tip");
      await h.ring('.lat .fixed:has-text("How the answer is decided")');
    },
    save: async (h) => {
      await h.clear("demo-ring");
      await h.top();
      await h.type('.lat input[aria-label="Set name"]', "Pullback in an uptrend");
      await h.ring(h.page.getByText("Description", { exact: false }).last().locator("xpath=ancestor::div[@data-testid='stColumn'][1]"));
      await h.wait(1200);
      await h.clear("demo-ring");
      await h.press('button:has-text("Save as a new Set")');
      await h.glide(h.page.getByText("It now appears in").first());
    },
    summary: async (h) => {
      await h.card({ kicker: "Saved", title: "Pullback in an uptrend",
        lines: ["✓ My Trend is Bullish", "✓ Stochastic %K is at most 30", "Yes, No or Unknown for every asset, with its reason"] });
    },
  },

  // ------------------------------------------------------------------------------------------ 5 · Prism Scan
  "05-prism-scan": {
    query: "?section=prism&seed=pullback",
    board: async (h) => { await h.ring(".lat.prism .lib"); },
    create: async (h) => {
      await h.clear();
      await h.press('.lat.prism button[aria-label="Start a scan with Pullback in an uptrend"] >> visible=true');
      await h.page.waitForSelector(".lat.prism .scan", { timeout: 60000 });
    },
    card: async (h) => { await h.glide(".lat.prism .scan .head"); await h.ring(".lat.prism .scan .head"); },
    assets: async (h) => { await h.clear(); await addAssets(h, "All crypto"); },
    play: async (h) => {
      await h.tip(PLAY, "Run now: the latest finished daily candles");
      await h.wait(2200);
      await h.clear("demo-tip");
      await past(h, "2024-01-15");
    },
    results: async (h) => { await showResults(h); },
    pause: async (h) => {
      await h.clear();
      const yes = h.page.locator(`${TABLE} tr`, { hasText: "Yes" });
      await h.ring((await yes.count()) ? yes.first() : h.page.locator(`${TABLE} tr`).nth(1));
    },
    bitcoin: async (h) => {
      await h.clear();
      await h.section("Signal Sets");
      await h.pick("Start from", "Pullback in an uptrend");
      await h.press(SET_ADD("My Trend v1"));
      await h.choose(h.page.locator('.lat select[aria-label="Which asset My Trend v1 is read on"]').nth(1), "crypto");
      await h.type(h.page.locator('.lat input[aria-label="Fixed asset for My Trend v1"]').nth(1), "bitcoin");
      await newLine(h);
      await setLine(h, 2, "outcome:my_trend_2", null, "bullish");
    },
    version: async (h) => {
      await h.press('button:has-text("Save as version 2")');
      await h.glide(h.page.getByText("Saved version 2").first());
    },
    switch: async (h) => {
      await h.section("Prism Scan");
      await h.press('.lat.prism button[aria-label="Switch this scan to version 2 of its Set"]');
    },
    rerun: async (h) => { await past(h, "2024-01-15"); await showResults(h); },
    schedule: async (h) => {
      await h.clear();
      await h.choose('.lat.prism .scan select[aria-label="When the scan runs"]', "1D");
      await h.press('.lat.prism .scan button[aria-label="Save when the scan runs"]');
    },
    alerts: async (h) => {
      const a = '.lat.prism .scan select[aria-label="Where alerts go"]';
      await h.glide(a);
      await h.ring(a);
    },
    tidy: async (h) => {
      await h.clear();
      await h.top();
      await h.press('.lat.prism button:has-text("Collapse all")');
    },
  },

  // ------------------------------------------------------------------------------------------ worked examples
  "w1-trend-with-volume": {
    query: "?section=sets&seed=trend",
    idea: async (h) => {
      await h.card({ kicker: "Worked example", title: "Trend with volume behind it",
        lines: ["✓ The trend is up", "✓ Volume is buying, not selling"] });
    },
    add: async (h) => {
      await h.clear();
      await h.press(SET_ADD("My Trend v1"));
      const provided = h.page.locator(".lat details.prov > summary").first();   // the starters' folded section
      if (await provided.count()) await h.press(provided, false);
      await h.tip('.lat .lib .chip:has-text("Flow v1")', null, "right");
      await h.wait(1200);
      await h.clear("demo-tip");
      await h.press(SET_ADD("Flow v1"));
    },
    lines: async (h) => {
      await newLine(h);
      await setLine(h, 0, "outcome:my_trend", null, "bullish");
      await newLine(h);
      await setLine(h, 1, "score:flow", "gte", "+30");
    },
    veto: async (h) => {
      await h.tip(h.page.locator(".lat .card", { hasText: "My Trend v1" }).first(),
        "Inside My Trend: a veto when the daily market is ranging.\nA vetoed trend is never Bullish.");
    },
    save: async (h) => { await h.clear(); await saveAndScan(h, "Trend with volume behind it", "All crypto", "2024-03-13"); },
    results: async (h) => { await showResults(h); },
  },

  "w2-overextended-rally": {
    query: "?section=sets&seed=trend",
    idea: async (h) => {
      await h.card({ kicker: "Worked example · a caution flag", title: "Overextended rally",
        lines: ["✓ A strong uptrend", "✓ RSI has run very hot"] });
    },
    add: async (h) => { await h.clear(); await h.press(SET_ADD("My Trend v1")); await h.press(SET_ADD("RSI (14)")); },
    lines: async (h) => {
      await newLine(h);
      await setLine(h, 0, "outcome:my_trend", null, "bullish");
      await newLine(h);
      await setLine(h, 1, "member:level_1d:rsi", "gte", "75");
    },
    save: async (h) => { await saveAndScan(h, "Overextended rally", "All crypto", "2024-03-13"); },
    results: async (h) => { await showResults(h); },
    alerts: async (h) => {
      await h.clear();
      await h.choose('.lat.prism .scan select[aria-label="Where alerts go"]', "instant");
      const yes = h.page.locator(".lat.prism .scan label", { hasText: "Turns Yes" }).first();
      if (!(await yes.locator("input").isChecked().catch(() => true))) await h.press(yes.locator("input"));
      await h.ring(yes);
    },
  },

  "w3-breakout-with-volume": {
    query: "?section=sets",
    idea: async (h) => {
      await h.card({ kicker: "Worked example", title: "Breakout with volume",
        lines: ["✓ The swing highs and lows are rising", "✓ The close is at the upper Bollinger band",
                "✓ Volume at least twice the usual"] });
    },
    add: async (h) => {
      await h.clear();
      for (const name of ["Market structure", "Bollinger position (20, 2)", "Heavy-volume candle"]) await h.press(SET_ADD(name));
    },
    lines: async (h) => {
      await newLine(h);
      await setLine(h, 0, "member:swings_1d:structure", null, "up");
      await newLine(h);
      await setLine(h, 1, "member:position_1d:position", "gte", "1");
      await newLine(h);
      await setLine(h, 2, "member:heavy_candle_1d:volume_ratio", "gte", "2");
    },
    save: async (h) => { await saveAndScan(h, "Breakout with volume", "All equities", "2023-04-28"); },
    results: async (h) => { await showResults(h); },
  },

  // ------------------------------------------------------------------------------------------ 6 · the provided library
  "06-provided-library": {
    query: "?section=prism",
    open: async (h) => {
      await h.ring(".lat.prism details.prov");
      await h.press(h.page.locator(".lat.prism details.prov > summary").first(), false);
      await h.wait(500);
    },
    icons: async (h) => {
      await h.clear();
      const chip = provided(h, "Breakout with volume");
      await h.tip(chip.locator(".pv, .ic, span[title]").first(), "🔊 Looks at volume\n🧱 Looks at support, resistance or structure", "right");
    },
    line: async (h) => {
      await h.clear();
      await h.ring(provided(h, "Breakout with volume"));
    },
    more: async (h) => {
      await h.clear();
      const chip = provided(h, "Breakout with volume");
      await h.press(chip.locator("details.more > summary").first(), false);
      await h.wait(400);
      await h.show(chip.locator("details.more").first());
    },
    evidence: async (h) => {
      const chip = provided(h, "Breakout with volume");
      await h.tip(chip.locator("details.wf > summary").first(),
        "🔬 Not yet studied\n⚖️ Studied: no clear difference from comparable days", "right");
      await h.wait(2500);
      await h.clear();
      await h.press(chip.locator("details.more > summary").first(), false);
    },
    filter: async (h) => {
      await h.press(h.page.locator(".lat.prism .pvf button", { hasText: "🌊" }).first(), false);
      await h.wait(600);
      await h.ring(h.page.locator(".lat.prism details.prov").first());
    },
    use: async (h) => {
      await h.clear();
      await h.press(h.page.locator(".lat.prism .pvf button.on").first(), false);
      await h.press(provided(h, "Volatility squeeze").locator("button.sq").first());
      await h.wait(800);
      await h.ring(h.page.locator(".lat.prism .scan, .lat.prism .card").first());
    },
    groups: async (h) => {
      await h.clear();
      await h.section("Signal Groups");
      await h.ring(h.page.locator(".lat details.prov, [data-testid='stExpander']").first());
      await h.wait(1500);
      await h.clear();
      await h.pick("Start from", null);
    },
    hide: async (h) => {
      await h.card({ kicker: "Settings", title: "Show provided items",
        lines: ["One switch hides every provided Group, Set and built-in alert", "Your own items stay as they are"] });
    },
  },

  // ------------------------------------------------------------------------------------------ 7 · Visualize History
  "07-visualize-history": {
    query: "?section=prism",
    setup: async (h) => {
      // Make the scan and load its history once, off camera, so the recording does not wait for the downloads.
      await h.page.locator(".lat.prism details.prov > summary").first().click();
      await h.wait(400);
      await provided(h, "Volatility squeeze").locator("button.sq").first().click();
      await h.page.waitForSelector(".lat.prism button.hist", { timeout: 60000 }); await h.wait(1500);
      await h.page.locator(".lat.prism button.hist").first().click();
      await h.page.waitForFunction(() => { const r = document.querySelector(".ang-lwc"); return r && r.__chart; }, null, { timeout: 420000 });
      await h.page.waitForFunction(() => !document.body.innerText.includes("⏳"), null, { timeout: 900000 }).catch(() => {});
      await h.page.locator(".lat.prism button.hist").first().click();
      await h.settle();
      await h.page.locator(".lat.prism details.prov > summary").first().click();
      await h.top();
    },
    what: async (h) => {
      await h.press(h.page.locator(".lat.prism button.hist").first());
      await h.page.waitForFunction(() => { const r = document.querySelector(".ang-lwc"); return r && r.__chart; }, null, { timeout: 120000 }).catch(() => {});
      await h.wait(800);
      await h.show(".ang-lwc");
    },
    bands: async (h) => {
      await h.tip(".ang-lwc-legend", "Green: Yes · Amber: Unknown · No: clear\n(a switch shows No as faint red)", "below");
    },
    panes: async (h) => {
      await h.clear();
      await h.page.evaluate(() => { const r = document.querySelector(".ang-lwc"); if (r) window.scrollBy({ top: r.getBoundingClientRect().top + 260, behavior: "smooth" }); });
      await h.wait(1800);
    },
    tap: async (h) => {
      const pt = await h.page.evaluate(() => {
        const r = document.querySelector(".ang-lwc"), c = r.__chart, host = r.querySelector(".ang-lwc-host").getBoundingClientRect();
        let top = 0; const hs = c.panes().map((p) => p.getHeight());
        for (let i = 0; i < 2; i++) top += hs[i] + 1;
        return { x: host.left + host.width / 2, y: host.top + top + hs[2] / 2 };
      });
      await h.page.mouse.move(pt.x, pt.y, { steps: 20 }); await h.wait(300);
      await h.page.mouse.click(pt.x, pt.y);
      await h.settle();
      await h.show(".ang-lwc");
    },
    years: async (h, dur) => {
      const seg = h.page.getByRole("button", { name: "3Y", exact: true }).first();
      await h.ring(seg.locator("xpath=.."));
      await h.wait(1200); await h.clear();
      await h.press(seg); await h.wait(Math.max(800, dur * 250));
      await h.press(h.page.getByRole("button", { name: "10Y", exact: true }).first());
      await h.show(".ang-lwc");
    },
    main: async (h) => {
      await h.ring(h.page.getByRole("button", { name: /Open on the main price chart/ }).first());
    },
    note: async (h) => {
      await h.clear();
      await h.card({ kicker: "Remember", title: "Bands show when, not what next",
        lines: ["✓ When the Set's conditions were met", "✓ On every asset in the scan, side by side",
                "What happened afterwards is the job of What followed"] });
    },
  },

  // ------------------------------------------------------------------------------------------ 8 · What followed
  "08-what-followed": {
    query: "?section=prism",
    question: async (h) => {
      await h.card({ kicker: "What followed", title: "After a Yes, what happened next?",
        lines: ["Compared with ordinary days", "Measured on the past, before October 2024"] });
    },
    how: async (h) => {
      await h.card({ kicker: "How it is measured", title: "The next 10 daily candles",
        lines: ["✓ Each time a Set first turns Yes", "✓ Against comparable days: same asset, same year, same side of the 200-day average",
                "✓ 25 coins and 61 large US equities, Sep 2014 to Oct 2024"],
        foot: "Moves are measured in each asset's typical daily move, so Bitcoin and Apple can be compared." });
    },
    find: async (h) => {
      await h.clear();
      await h.press(h.page.locator(".lat.prism details.prov > summary").first(), false);
      await h.wait(400);
      const chip = provided(h, "Breakout with volume");
      await h.press(chip.locator("details.more > summary").first(), false);
      await h.wait(400);
      await h.ring(chip.locator("details.wf").first());
    },
    card: async (h) => {
      await h.clear();
      const chip = provided(h, "Breakout with volume");
      await h.press(chip.locator("details.wf > summary").first(), false);
      await h.wait(400);
      await h.show(chip.locator("details.wf").first());
      await h.ring(chip.locator("details.wf").first());
    },
    verdicts: async (h) => {
      await h.clear();
      await h.card({ kicker: "Four verdicts", title: "What the study can say",
        lines: ["🔬 Too few to judge", "⚖️ No clear difference", "〰️ Some difference, not established", "🧭 Consistent difference"],
        foot: "Corrected for the number of tests, and checked across periods and between coins and equities." });
    },
    honest: async (h) => {
      await h.clear();
      const chip = provided(h, "Breakout with volume");
      await h.ring(chip.locator("details.wf > summary").first());
    },
    alignment: async (h) => {
      await h.clear();
      const chip = provided(h, "Trend alignment");
      await h.show(chip);
      await h.press(chip.locator("details.more > summary").first(), false);
      await h.wait(300);
      await h.press(chip.locator("details.wf > summary").first(), false);
      await h.wait(400);
      await h.show(chip.locator("details.wf").first());
      await h.ring(chip.locator("details.wf").first());
    },
    own: async (h) => {
      await h.clear();
      await h.open("?section=sets&seed=trend,pullback&preset=1");
      const study = h.page.getByRole("button", { name: /Study this Set/ });
      if (await study.count()) { await h.press(study.first()); }
      else await h.ring(h.page.getByText("What followed · what happened after").first());
    },
  },
};
