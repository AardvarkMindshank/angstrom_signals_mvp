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
async function saveAndScan(h, name, group) {
  await h.type('.lat input[aria-label="Set name"]', name);
  await h.press('button:has-text("Save as a new Set")');
  await h.wait(900);
  await h.section("Prism Scan");
  await h.press(`.lat.prism button[aria-label="Start a scan with ${name}"]`);
  await h.page.waitForSelector(".lat.prism .scan", { timeout: 60000 });
  await addAssets(h, group);
  await play(h);
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

async function showResults(h) {
  await h.show(TABLE);
  await h.ring(TABLE);
}

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
      await h.press('button:has-text("Save as a new Group")');
      await h.glide(h.page.getByText("Saved as a new Group").first());
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
      await h.tip('.lat .lib .chip:has-text("RSI (14)")', null, "right");
      await h.wait(1800);
      await h.clear("demo-tip");
      await h.press(SET_ADD("RSI (14)"));
    },
    lines: async (h) => {
      await newLine(h);
      await setLine(h, 0, "outcome:my_trend", null, "bullish");
      await h.wait(800);
      await newLine(h);
      await setLine(h, 1, "member:level_1d:rsi", "lte", "40");
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
        lines: ["✓ My Trend is Bullish", "✓ RSI (14) is at most 40", "Yes, No or Unknown for every asset, with its reason"] });
    },
  },

  // ------------------------------------------------------------------------------------------ 5 · Prism Scan
  "05-prism-scan": {
    query: "?section=prism&seed=pullback",
    board: async (h) => { await h.ring(".lat.prism .lib"); },
    create: async (h) => {
      await h.clear();
      await h.press('.lat.prism button[aria-label="Start a scan with Pullback in an uptrend"]');
      await h.page.waitForSelector(".lat.prism .scan", { timeout: 60000 });
    },
    card: async (h) => { await h.glide(".lat.prism .scan .head"); await h.ring(".lat.prism .scan .head"); },
    assets: async (h) => { await h.clear(); await addAssets(h, "All crypto"); },
    play: async (h) => { await play(h); },
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
    rerun: async (h) => { await play(h); await showResults(h); },
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
    save: async (h) => { await h.clear(); await saveAndScan(h, "Trend with volume behind it", "All crypto"); },
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
    save: async (h) => { await saveAndScan(h, "Overextended rally", "All crypto"); },
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
    save: async (h) => { await saveAndScan(h, "Breakout with volume", "All equities"); },
    results: async (h) => { await showResults(h); },
  },
};
