// What happens on screen in the live-site videos (app.angstromsignals.com, signed in as the demo account), step by
// step. Same shape as actions.js: the step ids match video/series/<slug>.json. Recorded by record.js with
// ACTIONS=live_actions.js; video/live_reset.py puts the demo account back to a new account first.
//
// The app's sections are found by their headings (the <summary> of each folding section), so a renamed section
// shows up as a missed step in the log, never as a wrong click.

const SIDEBAR = '[data-testid="stSidebar"]';

// ------------------------------------------------------------------------------------------------ live helpers
function live(h) {
  const page = h.page;
  // A folding section by its heading text (sidebar or main page).
  h.sum = (text, where) => page.locator(`${where || ""} summary`.trim()).filter({ hasText: text }).first();
  h.head = async (text, where) => {
    const s = h.sum(text, where);
    await s.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
    await page.waitForTimeout(700);
    return s;
  };
  h.expand = async (text, where) => {
    const s = await h.head(text, where);
    await h.glide(s, 250);
    const open = await s.evaluate((n) => !!(n.parentElement && n.parentElement.open)).catch(() => false);
    if (!open) { await s.click(); await h.settle(); }
    return s;
  };
  h.fold = async (text, where) => {
    const s = h.sum(text, where);
    const open = await s.evaluate((n) => !!(n.parentElement && n.parentElement.open)).catch(() => false);
    if (open) { await s.click(); await h.settle(); }
  };
  // The whole section (heading and contents), up to a height that fits the screen.
  h.section_ = (text, where) => h.sum(text, where).locator("xpath=..");
  return h;
}

async function sidebarOpen(h) {
  const tab = h.page.locator("#angstrom-sidebar-tab.is-closed");
  if (await tab.count()) { await h.press(tab); await h.wait(600); }
}

async function signIn(h) {
  const page = h.page;
  live(h);
  await page.goto(h.url, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('input[autocomplete="username"]', { timeout: 180000 });
  await h.settle();
  await page.fill('input[autocomplete="username"]', process.env.DEMO_EMAIL || "");
  await page.fill('input[autocomplete="current-password"]', process.env.DEMO_PASSWORD || "");
  await page.locator("button").filter({ hasText: "Log In" }).first().click();
  await page.waitForFunction(() => !document.querySelector('input[autocomplete="current-password"]'), null, { timeout: 120000 });
  await page.waitForSelector("summary", { timeout: 180000 });
  await h.settle();
  await page.waitForTimeout(4000);           // first readings and prices
  await h.settle();
  // Start every video from the same place: the top, with the big sections folded.
  for (const name of ["Angstrom Lattice", "Crypto Signals", "Equity Signals", "Interactive Chart", "Why these readings"]) {
    await h.fold(name).catch(() => {});
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.locator('[data-testid="stMain"]').evaluate((n) => n.scrollTo(0, 0)).catch(() => {});
  await page.mouse.move(1150, 560);       // away from anything with a hover note
  await h.settle();
}


// Open Angstrom Lattice on one of its tabs, with the tab row at the top of the screen.
async function lattice(h, tab) {
  await h.expand("Angstrom Lattice");
  const button = h.page.locator("button").filter({ hasText: tab, visible: true }).first();
  await h.glide(button, 250);
  await button.click();
  await h.settle();
  await h.page.waitForSelector(".lat", { timeout: 90000 }).catch(() => {});
  await h.settle();
  await button.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
  await h.wait(600);
}

// The + on a signal in the family list (the variant shown on its card).
const ADD = (name) => `.lat button[aria-label="Add ${name}"] >> visible=true`;
const RULE = (h, i) => h.page.locator(".lat .rule").nth(i);

// A line in the Set editor: the reading whose label contains `text`, then its comparison and value.
async function setLine(h, i, text, op, value) {
  const row = () => RULE(h, i);
  const key = await row().locator('select[aria-label="Reading"] option').evaluateAll(
    (opts, text) => (opts.find((o) => o.textContent.includes(text)) || {}).value, text);
  if (key) await h.choose(row().locator('select[aria-label="Reading"]'), key);
  else console.log(`no reading matching ${text}`);
  if (op) await h.choose(row().locator('select[aria-label="Comparison"]'), op);
  if (value !== undefined) {
    const box = row().locator('input[aria-label="Value"]');
    if (await box.count()) await h.type(box, value);
    else {
      const sel = row().locator('select[aria-label="Value"]');
      const v = await sel.locator("option").evaluateAll((opts, want) => (opts.find((o) => o.value === want || o.textContent.trim() === want) || {}).value, value);
      await h.choose(sel, v || value);
    }
  }
}

// Press a Streamlit save button, and press again if the click landed during a redraw.
async function save(h, label, done) {
  const btn = () => h.page.locator("button").filter({ hasText: label, visible: true }).first();
  await h.press(btn());
  await h.wait(1500);
  if (done && !(await h.page.getByText(done).first().isVisible().catch(() => false))) {
    console.log(`${label}: no "${done}" message; pressing again`);
    if (await btn().isEnabled().catch(() => false)) { await h.press(btn()); await h.wait(1500); }
  }
}

async function signInWide(h) {
  await signIn(h);
  const tab = h.page.locator("#angstrom-sidebar-tab:not(.is-closed)");
  if (await tab.count()) { await tab.click(); await h.wait(800); await h.settle(); }
}

// ------------------------------------------------------------------------------------------------ Soundings
const SOUNDINGS_DIAGRAM = require("./soundings_diagram.js");

// One of the in-depth video's explainer pictures (soundings_diagram.js), over the page; h.clear() removes it.
async function scene(h, name) {
  await h.page.mouse.move(1276, 606, { steps: 6 });        // the pointer out of the way of the picture
  await h.page.evaluate(SOUNDINGS_DIAGRAM.draw, { scene: name });
  await h.wait(300);
}

// Open Angstrom Lattice on Soundings, with the Soundings heading near the top of the screen.
async function soundings(h) {
  await h.expand("Angstrom Lattice");
  const button = h.page.locator(".st-key-lattice_section button").filter({ hasText: "Soundings" }).first();
  await h.glide(button, 250);
  await button.click();
  await h.settle();
  await h.page.waitForSelector(".st-key-snd_market", { timeout: 90000 }).catch(() => {});
  await h.settle();
  await button.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
  await h.wait(700);
}

// A Soundings tab (Chart, Before rises, Before falls) by its name.
async function sndTab(h, name) {
  // Only the Soundings tabs on show: other tab rows on the page (hidden ones too) can also say "Chart".
  const label = { "Chart": "🗺️ Chart", "Before rises": "📈 Before rises", "Before falls": "📉 Before falls" }[name] || name;
  const tab = h.page.locator('[role="tab"]').filter({ hasText: label, visible: true }).first();
  await tab.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
  await h.wait(500);
  await h.press(tab);
  await h.wait(900);
  return tab;
}

// The Soundings chart, waited for until it has drawn, brought into view.
async function sndChart(h) {
  const chart = h.page.locator(".st-key-snd_tv_chart").first();
  await h.page.waitForSelector(".st-key-snd_tv_chart canvas", { timeout: 60000 }).catch(() => {});
  await h.wait(1200);
  await chart.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
  await h.wait(800);
  return chart;
}

// The first result card in the tab on show.
function firstCard(h) {
  return h.page.locator(".snd-card").filter({ visible: true }).first();
}


// ------------------------------------------------------------------------------------------------ the price chart
// The chart videos (c1 to c5) are recorded without page zoom ("zoom": "none"): the fast chart draws on a canvas and
// measures itself wrongly under CSS zoom. The chart is brought to the top of the screen so the whole of it shows.

const LWC = ".ang-lwc";

// Open an asset from the Crypto Signals table on the Interactive Chart, with the candle size and range given.
async function openChart(h, name = "Bitcoin", interval = "4h", range = "3M") {
  await h.expand("Crypto Signals");
  await h.wait(2000);
  // The table may be showing a dynamic funnel: switch it to the watchlist, where the asset is.
  const wl = h.section_("Crypto Signals").locator("label").filter({ hasText: "My Watchlist" }).first();
  if (await wl.count()) { await wl.click().catch(() => {}); await h.settle(); await h.wait(2000); }
  let link = h.section_("Crypto Signals").locator("table").getByText(name, { exact: true }).first();
  if (!(await link.count())) link = h.section_("Crypto Signals").getByText(name, { exact: false }).first();
  await h.glide(link, 300);
  await link.click();
  await h.settle();
  await h.fold("Crypto Signals");
  for (let i = 0; i < 3; i++) {             // the section can fold again in the redraw after picking the asset
    await h.expand("Interactive Chart");
    const drawn = await h.page.waitForSelector(LWC + " canvas", { timeout: 30000 }).then(() => true).catch(() => false);
    if (drawn) break;
    await h.settle();
  }
  await h.settle();
  await timeframe(h, interval, range, false);
  await chartTop(h);
}

// The candle size and range buttons above the chart.
async function timeframe(h, interval, range, show = true) {
  for (const [key, label] of [["chart_interval", interval], ["chart_range", range]]) {
    if (!label) continue;
    const b = h.page.locator(`.st-key-${key} button`).filter({ hasText: new RegExp(`^${label}( ⊘)?$`) }).first();
    if (!(await b.count())) { console.log(`no ${key} button ${label}`); continue; }
    if (show) await h.glide(b, 250);
    await b.click().catch(() => {});
    await h.settle();
  }
  await h.page.waitForSelector(LWC + " canvas", { timeout: 60000 }).catch(() => {});
  await h.wait(1200);
}

// Scroll so the chart's top edge sits near the top of the screen (the whole price pane in view).
async function chartTop(h, offset = 8) {
  await h.page.locator(LWC).first().evaluate((n, off) => {
    const main = document.querySelector('[data-testid="stMain"]') || document.scrollingElement;
    const top = n.getBoundingClientRect().top;
    (main.scrollBy ? main : window).scrollBy({ top: top - off, behavior: "smooth" });
  }, offset).catch(() => {});
  await h.wait(900);
}

// Bring the controls above the chart into view (the pills and the timeframe row), then the chart below them.
async function chartControls(h, key = "chart_timeframe") {
  const row = h.page.locator(`.st-key-${key}`).first();
  await row.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
  await h.wait(800);
  return row;
}

// An indicator pill (or the Sonar marker pills) by its words; on = true switches it on, false off.
async function pill(h, words, on = true, key = "chart_indicators") {
  const b = h.page.locator(`.st-key-${key} button`).filter({ hasText: words }).first();
  if (!(await b.count())) { console.log(`no pill ${words}`); return null; }
  await b.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
  await h.wait(400);
  const active = await b.evaluate((n) => n.getAttribute("aria-pressed") === "true" || n.getAttribute("aria-checked") === "true"
    || /active|selected/i.test(n.getAttribute("kind") || "") || n.dataset.testid === "stBaseButton-pillsActive").catch(() => false);
  if (active !== on) { await h.glide(b, 250); await b.click(); await h.settle(); await h.wait(1200); }
  return b;
}

// Where things are on the price pane, in screen pixels, worked out from the chart's own candles: the lowest low and
// highest high in the visible window, the two lowest lows of its two halves, the last close, and the pane's box.
async function chartPoints(h) {
  return h.page.evaluate((sel) => {
    const root = document.querySelector(sel);
    const s = root && root.__draw;
    const chart = root && root.__chart;
    if (!s || !chart || !s.data) return null;
    const overlay = [...root.querySelectorAll("div")].find((d) => d.style.zIndex === "3");
    const host = overlay ? overlay.parentElement.getBoundingClientRect() : root.getBoundingClientRect();
    let left = 0, size = null;
    try { left = chart.priceScale("left").width() || 0; } catch (e) { left = 0; }
    try { size = chart.paneSize(0); } catch (e) { size = null; }
    const ox = host.left + left, oy = host.top;
    const [, H, L, C] = s.data.ohlc, T = s.data.times;
    const r = chart.timeScale().getVisibleLogicalRange();
    const a = Math.max(0, Math.ceil(r.from) + 2), b = Math.min(T.length - 1, Math.floor(r.to) - 1);
    const pt = (i, p) => ({ x: ox + s.X(T[i]), y: oy + s.Y(p) });
    const argmin = (from, to) => { let k = from; for (let i = from; i <= to; i++) if (L[i] < L[k]) k = i; return k; };
    const argmax = (from, to) => { let k = from; for (let i = from; i <= to; i++) if (H[i] > H[k]) k = i; return k; };
    const lo = argmin(a, b), hi = argmax(a, b);
    const mid = Math.floor((a + b) / 2);
    const lo1 = argmin(a, mid), lo2 = argmin(mid + 1, b);
    const swingLo = argmin(Math.floor(a + (b - a) * 0.35), Math.floor(a + (b - a) * 0.7));
    const recentHi = argmax(Math.floor(a + (b - a) * 0.6), b);
    const fibLo = lo < hi ? lo : argmin(a, hi), fibHi = hi;
    const hi1 = argmax(a, mid), hi2 = argmax(mid + 1, b);
    // A trend line along two swing points: under two rising lows, or else over two falling highs.
    const rising = L[lo2] > L[lo1];
    const t1 = rising ? pt(lo1, L[lo1]) : pt(hi1, H[hi1]), t2 = rising ? pt(lo2, L[lo2]) : pt(hi2, H[hi2]);
    return {
      pane: { x: ox, y: oy, w: size ? size.width : host.width - 70, h: size ? size.height : host.height * 0.6 },
      low: pt(lo, L[lo]), high: pt(hi, H[hi]), low1: pt(lo1, L[lo1]), low2: pt(lo2, L[lo2]), trendA: t1, trendB: t2,
      priceY: null,
      swingLow: pt(swingLo, L[swingLo]), recentHigh: pt(recentHi, H[recentHi]),
      fibLow: pt(fibLo, L[fibLo]), fibHigh: pt(fibHi, H[fibHi]),
      last: pt(b, C[b]), at: (f, p) => null, from: a, to: b,
      xs: [pt(a + Math.floor((b - a) * 0.2), C[a]).x, pt(a + Math.floor((b - a) * 0.55), C[a]).x],
    };
  }, LWC);
}

// Screen point of a price at a fraction across the price pane.
async function pricePoint(h, price, f) {
  return h.page.evaluate(([sel, price, f]) => {
    const root = document.querySelector(sel);
    const s = root && root.__draw, chart = root && root.__chart;
    if (!s || !chart) return null;
    const overlay = [...root.querySelectorAll("div")].find((d) => d.style.zIndex === "3");
    const host = overlay ? overlay.parentElement.getBoundingClientRect() : root.getBoundingClientRect();
    let left = 0, size = null;
    try { left = chart.priceScale("left").width() || 0; } catch (e) { left = 0; }
    try { size = chart.paneSize(0); } catch (e) { size = null; }
    const y = s.Y(price);
    return y === null ? null : { x: host.left + left + (size ? size.width : host.width - 70) * f, y: host.top + y };
  }, [LWC, price, f]);
}

// Sonar off for a cleaner price chart (videos 2, 3 and 5), keeping what each video turns on itself.
async function quietChart(h) {
  await pill(h, /Sonar\s*$/, false);
  await pill(h, "Sonar markers", false);
  await pill(h, "Liquidation levels", false);
}

// Open the drawing toolbar (the pencil) and pick a tool by the start of its hover text.
async function drawTool(h, tip) {
  const bar = h.page.locator(LWC + " .ang-lwc-drawbar").first();
  if (!(await bar.isVisible().catch(() => false))) {
    await h.press(h.page.locator(LWC + ' .ang-lwc-tools button[aria-label^="Drawing tools"]').first(), false);
    await h.wait(500);
  }
  if (!tip) return bar;
  const b = h.page.locator(LWC + ` .ang-lwc-drawbar button[aria-label^="${tip}"]`).first();
  await h.glide(b, 200);
  await b.click();
  await h.wait(300);
  return b;
}

// Drag on the chart from one screen point to another, at a person's pace.
async function drag(h, a, b, steps = 28) {
  await h.page.mouse.move(a.x, a.y, { steps: 14 });
  await h.wait(250);
  await h.page.mouse.down();
  await h.page.mouse.move(b.x, b.y, { steps });
  await h.wait(200);
  await h.page.mouse.up();
  await h.wait(600);
}

async function tap(h, p) {
  await h.page.mouse.move(p.x, p.y, { steps: 16 });
  await h.wait(250);
  await h.page.mouse.down();
  await h.page.mouse.up();
  await h.wait(600);
}

// Back to moving the chart (no drawing tool), and the drawing toolbar closed.
async function stopDrawing(h) {
  const pan = h.page.locator(LWC + ' .ang-lwc-drawbar button[aria-label^="Move the chart"]').first();
  if (await pan.isVisible().catch(() => false)) await pan.click().catch(() => {});
  await h.wait(200);
}

// Remove every drawing on this asset (the bin, pressed twice).
async function clearDrawings(h, show = true) {
  await drawTool(h);
  const bin = () => h.page.locator(LWC + ' .ang-lwc-drawbar button[aria-label^="Remove every drawing"], ' +
    LWC + ' .ang-lwc-drawbar button[aria-label^="Press again"]').first();
  if (show) await h.glide(bin(), 300);
  await bin().click().catch(() => {});
  await h.wait(500);
  await bin().click().catch(() => {});
  await h.wait(700);
}

// A Streamlit drop-down inside `box`: open it and choose the option at `n` (0 = the first).
async function pickNth(h, box, n, show = true) {
  let opener = box.locator('[role="combobox"], [data-baseweb="select"], input').first();
  if (!(await opener.count())) opener = box;
  if (show) await h.glide(opener, 300);
  await opener.click({ force: true }).catch(() => {});
  if (!(await h.page.locator('[role="option"]').count())) await h.page.keyboard.press("ArrowDown");
  await h.page.waitForSelector('[role="option"]', { timeout: 5000 }).catch(() => {});
  await h.wait(800);
  const option = h.page.locator('[role="option"]').nth(n);
  if (show) await h.glide(option, 300);
  await option.click().catch(() => {});
  await h.settle();
}

// Point the mouse across the price pane, candle by candle, so the legend changes.
async function hoverAcross(h, from = 0.45, to = 0.8, stops = 4) {
  const p = await chartPoints(h);
  if (!p) return;
  for (let i = 0; i < stops; i++) {
    const f = from + (to - from) * (i / Math.max(1, stops - 1));
    await h.page.mouse.move(p.pane.x + p.pane.w * f, p.pane.y + p.pane.h * 0.45, { steps: 20 });
    await h.wait(900);
  }
}

module.exports = {
  // ------------------------------------------------------------------------------------------ 0 · at a glance
  "d0-overview": {
    login: signIn,
    welcome: async (h) => {
      await h.card({ kicker: "Welcome", title: "Angstrom Signals",
        lines: ["✓ Readings for crypto and stocks, in plain words", "✓ AI guidance and alerts",
                "✓ A community alongside"],
        foot: "Descriptive readings, not forecasts or advice." });
    },
    sidebar: async (h) => {
      await h.clear();
      const tab = h.page.locator("#angstrom-sidebar-tab.is-closed");
      if (await tab.count()) { await h.press(tab); await h.wait(600); }
      await h.ring(SIDEBAR + ' [data-testid="stSidebarContent"]', 2);
    },
    start: async (h) => {
      await h.clear();
      const card = h.page.locator('[class*="st-key-onboarding_card"]').first();
      if (await card.count()) await h.ring(card);
    },
    snapshot: async (h) => {
      await h.clear();
      const s = await h.expand("Quick Snapshot");
      await h.ring(h.section_("Quick Snapshot"));
    },
    tides: async (h) => {
      await h.clear();
      await h.fold("Quick Snapshot");
      const s = await h.head("Tides");
      await h.ring(s);
    },
    sentiment: async (h) => {
      await h.clear();
      await h.ring([h.sum("Market sentiment - Crypto market"), h.sum("Market sentiment - Stock market")]);
    },
    table: async (h) => {
      await h.clear();
      await h.expand("Crypto Signals");
      await h.wait(2500);
      const table = h.section_("Crypto Signals").locator("table").first();
      await table.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(700);
      await h.ring(table);
    },
    asset: async (h) => {
      await h.clear();
      const name = h.section_("Crypto Signals").getByText("Bitcoin", { exact: false }).first();
      await h.glide(name, 400);
      await name.click();
      await h.settle();
      await h.wait(1500);
    },
    chart: async (h) => {
      await h.clear();
      await h.fold("Crypto Signals");
      await h.expand("Interactive Chart");
      await h.wait(3000);
      await h.ring(h.section_("Interactive Chart"));
    },
    why: async (h) => {
      await h.clear();
      await h.fold("Interactive Chart");
      await h.expand("Why these readings");
      await h.wait(1500);
      await h.ring(h.section_("Why these readings"));
    },
    lattice: async (h, dur) => {
      await h.clear();
      await h.fold("Why these readings");
      await h.expand("Angstrom Lattice");
      await h.page.waitForSelector(".lat", { timeout: 90000 }).catch(() => {});
      await h.settle();
      const each = Math.max(2200, (dur * 1000 - 3000) / 4);
      for (const part of ["Signal Groups", "Signal Sets", "Prism Scan", "Funnels"]) {
        const tab = h.page.locator("button").filter({ hasText: part, visible: true }).first();
        await h.glide(tab, 200);
        await tab.click();
        await h.settle();
        await h.wait(each - 1200);
      }
    },
    ai: async (h) => {
      await h.clear();
      await h.ring("button.ai-edge", 4);
      await h.tip("button.ai-edge", "✨ AI Navigator", "below");
    },
    social: async (h) => {
      await h.clear();
      await h.ring("button.edge", 4);
      await h.tip("button.edge", "Social signals and chat", "below");
    },
    next: async (h) => {
      await h.clear();
      await h.card({ kicker: "Day one", title: "Your first steps",
        lines: ["✓ Add the assets you follow", "✓ Build a Signal Group and a Signal Set",
                "✓ Scan your assets with Prism", "✓ Make your own funnel"] });
    },
  },
  // ------------------------------------------------------------------------------------------ 1 · watchlist
  "d1-watchlist": {
    login: signIn,
    idea: async (h) => {
      await h.card({ kicker: "Day one", title: "Your watchlists",
        lines: ["✓ The signal tables and the chart", "✓ Your Prism scans", "✓ Your alerts"],
        foot: "Everything follows the assets you choose." });
    },
    markets: async (h) => {
      await h.clear();
      await sidebarOpen(h);
      await h.expand("Settings", SIDEBAR);
      const radio = h.page.locator(SIDEBAR + ' [data-testid="stRadio"]').filter({ hasText: "I trade both" }).first();
      await h.ring(radio);
      const both = radio.locator("label").filter({ hasText: "I trade both" }).first();
      await h.glide(both, 300);
      await both.click();
      await h.settle();
    },
    tick: async (h) => {
      await h.clear();
      await h.fold("Settings", SIDEBAR);
      const box = h.page.locator('[class*="st-key-onboarding_card"] label').filter({ hasText: "Choose the markets you trade" }).first();
      await h.show(box);
      await h.ring(h.page.locator('[class*="st-key-onboarding_card"]').first());
      await h.press(box);
    },
    crypto: async (h) => {
      await h.clear();
      await h.expand("Watchlists", SIDEBAR);
      await h.expand("Edit Crypto", SIDEBAR);
      const box = h.page.locator(SIDEBAR + ' input[aria-label="Add crypto"]').first();
      await h.glide(box);
      await box.click();
      await box.pressSequentially("Chainlink", { delay: 70 });
      await box.press("Enter");
      await h.settle();
      await h.wait(1200);
      await h.press(h.page.locator(SIDEBAR + " button").filter({ hasText: "Add Crypto" }).first());
      await h.wait(800);
    },
    stock: async (h) => {
      await h.fold("Edit Crypto", SIDEBAR);
      await h.expand("Edit Stocks", SIDEBAR);
      const box = h.page.locator(SIDEBAR + ' input[aria-label="Add stock or ETF"]').first();
      await h.glide(box);
      await box.click();
      await box.pressSequentially("AMD", { delay: 90 });
      await box.press("Enter");
      await h.settle();
      await h.wait(1200);
      await h.press(h.page.locator(SIDEBAR + " button").filter({ hasText: "Add Stock" }).first());
      await h.wait(800);
    },
    table: async (h) => {
      await h.expand("Crypto Signals");
      await h.wait(2500);
      const row = h.section_("Crypto Signals").getByText("Chainlink", { exact: false }).first();
      await h.show(row);
      await h.ring(row, 10);
    },
    remove: async (h) => {
      await h.clear();
      const pick = h.page.locator(SIDEBAR + ' [data-testid="stSelectbox"]').filter({ hasText: "Remove stock" }).first();
      await h.show(pick);
      await h.ring(pick);
    },
    summary: async (h) => {
      await h.clear();
      await h.card({ kicker: "Done", title: "Your watchlists",
        lines: ["✓ Markets: cryptos and equities", "✓ Added Chainlink and AMD", "✓ Saved on your account"] });
    },
  },
  // ------------------------------------------------------------------------------------------ 2 · first Group
  "d2-first-group": {
    login: signInWide,
    idea: async (h) => {
      await h.card({ kicker: "Signal Groups", title: "Several signals, one reading",
        lines: ["✓ A score from −100 to +100", "✓ Labels you choose: Bullish, Bearish, Neutral", "✓ The reasons behind every reading"] });
    },
    open: async (h) => {
      await h.clear();
      await lattice(h, "Signal Groups");
      await h.ring(".lat .lib");
    },
    families: async (h, dur) => {
      await h.clear();
      await h.ring(".lat .lib .fam >> nth=0");
      await h.wait(Math.max(1500, dur * 450));
      await h.clear();
      await h.ring(".lat .lib .pvf");
    },
    add: async (h) => {
      await h.clear();
      await h.press(ADD("Trend direction"));
      await h.wait(600);
      const ma = h.page.locator(".lat .lib .chip.card").filter({ hasText: "Moving averages" }).first();
      await h.press(ma.locator(".vars button").filter({ hasText: "Moving averages (50, 200)" }).first());
      await h.press(ADD("Moving averages (50, 200)"));
      await h.wait(600);
      await h.press(ADD("MACD line"));
      await h.wait(600);
      const members = h.page.locator(".lat .mid").first();
      await members.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(500);
    },
    score: async (h, dur) => {
      const roles = h.page.locator(".lat .mid .card").first();
      await h.show(roles);
      await h.ring(roles);
      await h.wait(Math.max(1500, dur * 450));
      await h.clear("demo-ring");
      await h.ring(h.page.locator(".lat .mid .card"));
    },
    rules: async (h) => {
      await h.clear();
      for (const label of ["Bullish", "Bearish"]) {
        await h.choose('.lat select[aria-label="Label for a new rule"]', label);
        await h.press('.lat button[aria-label="Add a rule that gives this label"]');
        await h.wait(700);
      }
      await h.ring(".lat .rule >> nth=0");
    },
    save: async (h) => {
      await h.clear();
      await h.type('.lat input[aria-label="Group name"]', "My Trend");
      await h.wait(1200);
      await save(h, "Save as a new Group", "Saved as a new Group");
    },
    summary: async (h) => {
      await h.card({ kicker: "Saved", title: "My Trend",
        lines: ["✓ Trend direction, moving averages and MACD", "✓ One score, from −100 to +100",
                "✓ Bullish at +30 or more, Bearish at −30 or less"] });
    },
  },

  // ------------------------------------------------------------------------------------------ 3 · first Set
  "d3-first-set": {
    login: signInWide,
    idea: async (h) => {
      await h.card({ kicker: "Signal Sets", title: "Dip in my uptrend",
        lines: ["✓ My Trend is Bullish", "✓ RSI is 40 or less: price has dipped"],
        foot: "Yes, No or Unknown for every asset, with the reason." });
    },
    open: async (h) => {
      await h.clear();
      await lattice(h, "Signal Sets");
      await h.ring(".lat .lib");
    },
    group: async (h) => {
      await h.clear();
      await h.press('.lat button[aria-label="Add My Trend v1 to the Set"] >> visible=true');
      await h.wait(700);
    },
    signal: async (h) => {
      const fam = h.page.locator(".lat .lib .chip.card").filter({ hasText: "Overbought / oversold" }).first();
      await h.show(fam);
      await h.ring(fam);
      await h.wait(1200);
      await h.clear("demo-ring");
      await h.press(ADD("RSI (14)"));
      await h.wait(700);
    },
    lines: async (h) => {
      await h.press('.lat button[aria-label="Add a line that must hold"] >> visible=true');
      await setLine(h, 0, "My Trend", null, "bullish");
      await h.wait(700);
      await h.press('.lat button[aria-label="Add a line that must hold"] >> visible=true');
      await setLine(h, 1, "RSI", "lte", "40");
    },
    answer: async (h) => {
      const box = h.page.locator(".lat .fixed").filter({ hasText: "How the answer is decided" }).first();
      if (await box.count()) await h.ring(box);
      else await h.ring(".lat .rule >> nth=0");
    },
    save: async (h) => {
      await h.clear();
      await h.type('.lat input[aria-label="Set name"]', "Dip in my uptrend");
      await h.wait(1200);
      await save(h, "Save as a new Set", "It now appears in");
    },
    summary: async (h) => {
      await h.card({ kicker: "Saved", title: "Dip in my uptrend",
        lines: ["✓ My Trend is Bullish", "✓ RSI (14) is 40 or less", "Ready to scan your assets"] });
    },
  },

  // ------------------------------------------------------------------------------------------ 4 · first scan
  "d4-first-scan": {
    login: signInWide,
    idea: async (h) => {
      await h.card({ kicker: "Prism Scan", title: "Ask your Set about every asset",
        lines: ["✓ Run it now, on the latest finished candles", "✓ Or on a schedule, by itself", "✓ Alerts when an answer turns Yes"] });
    },
    open: async (h) => {
      await h.clear();
      await lattice(h, "Prism Scan");
      await h.ring(".lat.prism .lib");
    },
    create: async (h) => {
      await h.clear();
      await h.press('.lat.prism button[aria-label="Start a scan with Dip in my uptrend"] >> visible=true');
      await h.page.waitForSelector(".lat.prism .scan", { timeout: 60000 }).catch(() => {});
      await h.settle();
      await h.ring(".lat.prism .scan >> nth=0");
    },
    play: async (h) => {
      await h.clear();
      await h.press(".lat.prism .scan button.play >> nth=0");
      await h.page.waitForSelector(".lat.prism .scan table", { timeout: 240000 }).catch(() => {});
      await h.settle();
    },
    results: async (h) => {
      const table = h.page.locator(".lat.prism .scan table").first();
      await h.show(table);
      await h.ring(table);
    },
    schedule: async (h) => {
      await h.clear();
      await h.choose('.lat.prism .scan select[aria-label="When the scan runs"] >> nth=0', "1D");
      await h.ring('.lat.prism .scan select[aria-label="When the scan runs"] >> nth=0');
    },
    alerts: async (h) => {
      await h.clear();
      const a = '.lat.prism .scan select[aria-label="Where alerts go"] >> nth=0';
      await h.glide(a);
      await h.ring(a);
    },
    summary: async (h) => {
      await h.clear();
      await h.card({ kicker: "Running", title: "Dip in my uptrend",
        lines: ["✓ Checks your watchlist at every daily close", "✓ Alerts when an answer turns Yes",
                "✓ Ticks the Prism step of your checklist"] });
    },
  },

  // ------------------------------------------------------------------------------------------ 5 · own funnel
  "d5-first-funnel": {
    login: signInWide,
    idea: async (h) => {
      await h.card({ kicker: "🔻 Funnels", title: "From a whole market to a short list",
        lines: ["Pool: the top coins, or the S&P 500", "Each stage narrows it down, on its own chart",
                "✓ Candidates: the assets that hold every stage"],
        foot: "Checked every hour, by itself." });
    },
    open: async (h) => {
      await h.clear();
      await lattice(h, "Funnels");
      await h.page.waitForSelector(".lat.fun", { timeout: 60000 }).catch(() => {});
      await h.settle();
      const board = h.page.locator(".lat.fun").first();
      await board.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(700);
      await h.ring(".lat.fun .pool");
    },
    copy: async (h) => {
      await h.clear();
      const copy = h.page.getByRole("button", { name: "Make my own copy" }).first();
      await h.show(copy);
      await h.press(copy);
      await h.page.waitForSelector('input[aria-label="Name"]', { timeout: 60000 }).catch(() => {});
      await h.settle();
      const name = h.page.locator('input[aria-label="Name"]').first();
      await name.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
    },
    name: async (h) => {
      const name = h.page.locator('input[aria-label="Name"]').first();
      await name.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.type(name, "My trend funnel");
    },
    pool: async (h) => {
      const pool = h.page.locator(".lat.fun .pool").first();
      await pool.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(pool);
      await h.choose(".lat.fun .pool select >> nth=0", "100");
    },
    stages: async (h) => {
      await h.clear();
      const stages = h.page.locator(".lat.fun .stages").first();
      await stages.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(".lat.fun .stage >> nth=0");
    },
    save: async (h) => {
      await h.clear();
      const btn = h.page.locator("button").filter({ hasText: "Save and activate", visible: true }).first();
      await h.show(btn);
      await h.press(btn);
      await h.wait(1500);
    },
    summary: async (h) => {
      await h.card({ kicker: "Active", title: "My trend funnel",
        lines: ["✓ The top 100 coins, narrowed stage by stage", "✓ Shown as Dynamic funnel above the tables",
                "✓ Alerts on new Candidates"],
        foot: "A Candidate matches your conditions. It is not a recommendation to trade." });
    },
  },
  // ------------------------------------------------------------------------------------------ around the app
  "u1-tides": {
    login: signIn,
    idea: async (h) => {
      await h.card({ kicker: "🌊 Tides", title: "The money behind every chart",
        lines: ["Rates, the dollar, inflation and fear", "Credit, and where money is rotating",
                "✓ The conditions every asset trades in"] });
    },
    open: async (h) => {
      await h.clear();
      await h.expand("Tides");
      await h.wait(2500);
      const hero = h.page.locator(".tides .hero").first();
      await hero.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(hero);
    },
    winds: async (h) => {
      await h.clear();
      const pills = h.page.locator(".tides .hero").first().getByText(/headwind|tailwind/i);
      if (await pills.count()) await h.ring(pills); else await h.ring(".tides .hero >> nth=0");
    },
    note: async (h) => {
      await h.clear();
      const note = h.page.locator('[class*="st-key-tides_note_row"]').first();
      await note.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(note);
    },
    storm: async (h) => {
      await h.clear();
      // The page holds two storm cards (one hidden, depending on the screen width): use the one on show.
      const storm = h.page.locator(".tides .card.storm").filter({ visible: true }).first();
      await storm.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(storm);
    },
    waves: async (h) => {
      await h.clear();
      const head = h.page.locator(".tides h4").filter({ hasText: "The waves" }).first();
      await head.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(1500);
      await h.ring(head);
    },
    currents: async (h) => {
      await h.clear();
      const head = h.page.locator(".tides h4").filter({ hasText: "The currents" }).first();
      await head.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(800);
      await h.ring(head.locator("xpath=.."));
    },
    plan: async (h) => {
      await h.clear();
      const b = h.page.locator("button").filter({ hasText: "Passage Plan", visible: true }).first();
      await b.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(b);
    },
    take: async (h) => {
      await h.clear();
      const take = h.page.locator('[class*="st-key-tides_take_col"]').first();
      await take.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(take);
    },
  },

  "u2-ai-navigator": {
    login: signIn,
    idea: async (h) => {
      await h.card({ kicker: "✨ AI Navigator", title: "Ask anything about the app",
        lines: ["✓ Where things are, and what a reading means", "✓ How to turn an idea into a Group, Set or scan",
                "✓ Today's Tides, and your own assets and funnels"],
        foot: "It explains; you do the clicks. No buy or sell calls." });
    },
    open: async (h) => {
      await h.clear();
      await h.press("button.ai-edge");
      await h.page.waitForSelector("#ang-ai-root iframe", { timeout: 30000 }).catch(() => {});
      const f = h.page.frameLocator("#ang-ai-root iframe");
      await f.locator('textarea[aria-label="Your question"]').waitFor({ timeout: 90000 }).catch(() => {});
      await h.wait(800);
    },
    ask: async (h) => {
      const f = h.page.frameLocator("#ang-ai-root iframe");
      const box = f.locator('textarea[aria-label="Your question"]').first();
      const b = await box.boundingBox().catch(() => null);
      if (b) await h.page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 20 });
      await box.click();
      await box.pressSequentially("How do I find coins that are dipping inside an uptrend?", { delay: 35 });
      await h.wait(400);
      // The Ask button (its label also holds the icon's name), pressed like a person would; Ctrl+Enter if that misses.
      const ask = f.locator('[data-testid="stFormSubmitButton"] button').first();
      const a = await ask.boundingBox().catch(() => null);
      if (a) await h.page.mouse.move(a.x + a.width / 2, a.y + a.height / 2, { steps: 15 });
      try { await ask.click({ timeout: 5000 }); } catch (e) { await box.press("Control+Enter"); }
    },
    wait: async (h) => {
      const f = h.page.frameLocator("#ang-ai-root iframe");
      await f.locator('[data-testid="stChatMessage"]').nth(1).waitFor({ timeout: 120000 }).catch(() => {});
      await h.wait(1000);
    },
    answer: async (h, dur) => {
      const f = h.page.frameLocator("#ang-ai-root iframe");
      const msg = f.locator('[data-testid="stChatMessage"]').nth(1);
      await msg.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      const steps = Math.max(3, Math.round(dur / 1.6));
      for (let i = 0; i < steps; i += 1) {          // read down the answer, slowly
        await h.wait(1300);
        await msg.evaluate((n) => { const s = n.closest('[data-testid="stMain"]') || document.scrollingElement; s.scrollBy({ top: 70, behavior: "smooth" }); }).catch(() => {});
      }
    },
    paste: async (h) => {
      const f = h.page.frameLocator("#ang-ai-root iframe");
      const box = f.locator('textarea[aria-label="Your question"]').first();
      await box.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      const b = await box.boundingBox().catch(() => null);
      if (b) await h.page.mouse.move(b.x + b.width / 2, b.y - 40, { steps: 15 });
    },
    close: async (h) => {
      await h.press("button.ai-edge");
      await h.wait(800);
    },
  },

  "u3-social": {
    login: async (h) => {
      await signIn(h);
      // Other members' posts, names and pictures are blurred: this video shows how the panel works, not who said what.
      await h.page.addStyleTag({ content: "#social-stream-root .list > *, #social-stream-root .chat-list > *, " +
        "#social-stream-root #stream-person, #social-stream-root #chat-person, #social-stream-root .found " +
        "{ filter: blur(7px) !important; }" });
    },
    idea: async (h) => {
      await h.card({ kicker: "💬 Community", title: "Traders alongside you",
        lines: ["✓ A live stream of social signals", "✓ Chat: everyone, your communities, or one person",
                "✓ Votes beside every AI sentiment score"] });
    },
    open: async (h) => {
      await h.clear();
      await h.press("button.edge");
      await h.page.waitForSelector("#social-stream-root .panel", { timeout: 30000 }).catch(() => {});
      await h.wait(1500);
    },
    stream: async (h) => { await h.ring("#social-stream-root .stream-pane"); },
    filters: async (h) => {
      await h.clear();
      await h.ring("#social-stream-root .filters");
      await h.press(h.page.locator("#social-stream-root .chips button").filter({ hasText: "Positive" }).first());
      await h.wait(1200);
      await h.press(h.page.locator("#social-stream-root .chips button").filter({ hasText: "All" }).first());
    },
    chat: async (h) => { await h.clear(); await h.ring("#social-stream-root .chat-pane"); },
    write: async (h) => {
      await h.clear();
      const box = h.page.locator("#social-stream-root .chat-box").first();
      await h.glide(box);
      await box.click();
      await box.pressSequentially("Hello from the demo account!", { delay: 60 });   // typed, never posted
      await h.ring("#social-stream-root .composer");
      await h.wait(1500);
      await box.fill("");
    },
    pin: async (h) => {
      await h.clear();
      const pin = h.page.locator("#social-stream-root .pin").first();
      if (await pin.count()) await h.tip(pin, "Pin the panel open", "below");
      await h.wait(1800);
      await h.clear();
      await h.press("#social-stream-root .close");
    },
  },

  "u5-alerts": {
    login: signIn,
    idea: async (h) => {
      await h.card({ kicker: "🔔 Alerts", title: "Know when something changes",
        lines: ["✓ A reading crosses a line you chose", "✓ A scan's answer turns Yes", "✓ A funnel finds a new Candidate"] });
    },
    open: async (h) => {
      await h.clear();
      await sidebarOpen(h);
      await h.expand("Notifications", SIDEBAR);
      await h.expand("Alert Feed", SIDEBAR);
      await h.ring(h.section_("Alert Feed", SIDEBAR));
    },
    rules: async (h) => {
      await h.clear();
      await h.fold("Alert Feed", SIDEBAR);
      await h.expand("Configure Alert Rules", SIDEBAR);
      await h.wait(800);
      await h.ring(h.section_("Configure Alert Rules", SIDEBAR));
    },
    emails: async (h) => {
      await h.clear();
      const mail = h.page.locator(SIDEBAR).getByText(/Instant|Daily alerts summary/).first();
      await mail.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(mail.locator("xpath=ancestor::div[@data-testid='stVerticalBlock'][1]"));
    },
    push: async (h) => {
      await h.clear();
      await h.fold("Configure Alert Rules", SIDEBAR);
      const s = await h.head("Phone and desktop notifications", SIDEBAR);
      await h.ring(s);
    },
    tick: async (h) => {
      await h.clear();
      await h.fold("Notifications", SIDEBAR);
      const box = h.page.locator('[class*="st-key-onboarding_card"] label').filter({ hasText: "Choose how alerts reach you" }).first();
      if (await box.count()) {
        await h.show(box);
        await h.ring(h.page.locator('[class*="st-key-onboarding_card"]').first());
        await h.press(box);
      }
    },
    others: async (h) => {
      await h.clear();
      await h.card({ kicker: "Also", title: "Scans and funnels alert too",
        lines: ["✓ Prism Scan: Where alerts go, on each scan", "✓ Funnels: Alert me on new Candidates",
                "✓ Everything lands in your Alert Feed"] });
    },
  },

  "u4-dynamic-funnel": {
    login: signIn,
    idea: async (h) => {
      await h.card({ kicker: "🔻 Dynamic funnel", title: "What your funnel found",
        lines: ["✓ Checked every hour, by itself", "✓ Stages, Flagged and Candidates at a glance",
                "✓ Alerts on new Candidates"] });
    },
    open: async (h) => {
      await h.clear();
      await h.expand("Crypto Signals");
      await h.wait(1500);
      const radio = h.section_("Crypto Signals").locator("label").filter({ hasText: "Dynamic funnel" }).first();
      await h.press(radio);
      await h.page.waitForSelector(".angfr .frow", { timeout: 60000 }).catch(() => {});
      await h.settle();
      const rows = h.page.locator(".angfr").first();
      await rows.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(rows);
    },
    chips: async (h) => {
      await h.clear();
      await h.ring(".angfr .frow .chips >> nth=0");
      const chip = h.page.locator(".angfr .frow .chip:not(.empty)").first();     // the first stage: it always holds some
      if (await chip.count()) await h.press(chip);
    },
    table: async (h) => {
      await h.clear();
      const table = h.section_("Crypto Signals").locator("table").first();
      await table.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(700);
      await h.ring(table);
    },
    actions: async (h) => {
      await h.clear();
      const acts = h.page.locator(".angfr .frow .acts").first();
      await acts.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(acts);
    },
    snapshot: async (h) => {
      await h.clear();
      await h.fold("Crypto Signals");
      await h.expand("Quick Snapshot");
      await h.wait(1500);
      const tile = h.page.getByText("My trend funnel").first();
      if (await tile.count()) {
        await tile.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
        await h.wait(600);
        await h.ring(tile.locator("xpath=ancestor::div[2]"));
      } else await h.ring(h.section_("Quick Snapshot"));
    },
    back: async (h) => {
      await h.clear();
      await h.fold("Quick Snapshot");
      await h.expand("Crypto Signals");
      const radio = h.section_("Crypto Signals").locator("label").filter({ hasText: "My Watchlist" }).first();
      await h.press(radio);
    },
  },
  // ------------------------------------------------------------------------------------------ Soundings
  "s1-soundings": {
    login: signInWide,
    idea: async (h) => {
      await h.card({ kicker: "🧭 Soundings", title: "Start from the moves, and look back",
        lines: ["Every past rise and fall, marked first", "Then: what were the readings just before?",
                "✓ Checked on later years the search never saw"] });
    },
    open: async (h) => {
      await h.clear();
      await soundings(h);
      await h.ring(h.page.locator(".st-key-snd_market").first());
    },
    chart: async (h) => {
      await h.clear();
      await sndTab(h, "Chart");
      const chart = await sndChart(h);
      await h.ring(chart);
    },
    hover: async (h) => {
      await h.clear();
      const chart = h.page.locator(".st-key-snd_tv_chart").first();
      // The day's note shows at the top of the chart: bring the top of the chart into view first.
      await chart.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(700);
      const b = await chart.boundingBox().catch(() => null);
      if (b) {
        for (const f of [0.45, 0.55, 0.62, 0.7]) {
          await h.page.mouse.move(b.x + b.width * f, b.y + b.height * 0.3, { steps: 18 });
          await h.wait(900);
        }
      }
    },
    rises: async (h) => {
      await h.page.mouse.move(1150, 560);
      await h.clear();
      const tab = await sndTab(h, "Before rises");
      await h.ring(tab);
    },
    card: async (h) => {
      await h.clear();
      const card = firstCard(h);
      await card.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(700);
      await h.ring(card);
    },
    verdicts: async (h) => {
      await h.clear();
      const heads = h.page.locator("p").filter({ visible: true }).filter({ hasText: /^(✅|↕️|⚠️|➖|✖️)/ });
      const first = heads.first();
      await first.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(700);
      await h.ring(first);
      await h.wait(1800);
      const second = heads.nth(1);
      if (await second.count()) {
        await second.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
        await h.wait(700);
        await h.ring(second);
      }
    },
    set: async (h) => {
      await h.clear();
      const button = h.page.locator('[class*="st-key-snd_set_rise_"] button').filter({ visible: true }).first();
      await button.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(700);
      await h.glide(button, 300);
      await h.ring(button);
    },
    how: async (h) => {
      await h.clear();
      const s = h.page.locator("summary").filter({ hasText: "How this run was done" }).first();
      await s.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.press(s);
      await h.wait(900);
      await h.ring(s.locator("xpath=.."));
    },
  },
  "s2-soundings-in-depth": {
    login: signInWide,
    plan: async (h) => {
      await soundings(h);                      // the page behind the pictures
      await h.card({ kicker: "🧭 Soundings, in depth", title: "How it works, and why to trust it",
        lines: ["The objective, and what counts as a move", "The process, and the statistics behind it",
                "✓ The integrity checks", "✓ The limits"] });
    },
    question: async (h) => { await h.clear(); await scene(h, "question"); },
    move: async (h) => { await scene(h, "move"); },
    typical: async (h) => { await scene(h, "typical"); },
    readings: async (h) => { await scene(h, "readings"); },
    usual: async (h) => { await scene(h, "usual"); },
    split: async (h) => { await scene(h, "split"); },
    many: async (h) => { await scene(h, "many"); },
    together: async (h) => { await scene(h, "together"); },
    themes: async (h) => { await scene(h, "themes"); },
    verdicts: async (h) => { await scene(h, "verdicts"); },
    live: async (h) => {
      await h.clear();
      await sndTab(h, "Before rises");
      const head = h.page.locator("p").filter({ visible: true }).filter({ hasText: /^✅/ }).first();
      await head.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(800);
      await h.ring([head, firstCard(h)]);
    },
    example: async (h) => { await h.clear(); await scene(h, "example"); },
    integrity: async (h) => { await scene(h, "integrity"); },
    limits: async (h) => { await scene(h, "limits"); },
    chart: async (h) => {
      await h.clear();
      await sndTab(h, "Chart");
      const chart = await sndChart(h);
      await h.ring(chart);
      const b = await chart.boundingBox().catch(() => null);
      if (b) {
        await h.wait(1500);
        await h.clear("demo-ring");
        for (const f of [0.5, 0.6, 0.68]) {
          await h.page.mouse.move(b.x + b.width * f, b.y + b.height * 0.3, { steps: 18 });
          await h.wait(1000);
        }
      }
    },
    use: async (h) => {
      await h.page.mouse.move(1150, 560);
      await h.clear();
      await scene(h, "use");
    },
  },
  // ------------------------------------------------------------------------------------------ Charts series
  "c1-charts-overview": {
    login: signInWide,
    setup: async (h) => { await openChart(h, "Bitcoin", "1D", "1Y"); await h.page.evaluate(() => window.scrollTo(0, 0));
      await h.page.locator('[data-testid="stMain"]').evaluate((n) => n.scrollTo(0, 0)).catch(() => {}); },
    idea: async (h) => {
      await h.card({ kicker: "📊 Charts", title: "Two charts, one set of readings",
        lines: ["✓ The fast chart: zoom, scroll, draw, 5-minute to monthly candles",
                "✓ The classic chart: the original, simple and steady", "✓ The same indicators on both"] });
    },
    engine: async (h) => {
      await h.clear();
      await sidebarOpen(h);
      await h.expand("Settings", SIDEBAR);
      const radio = h.page.locator(SIDEBAR + ' [data-testid="stRadio"]').filter({ hasText: "TradingView" }).first();
      await radio.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(radio);
      await h.glide(radio.locator("label").filter({ hasText: "TradingView" }).first(), 300);
    },
    open: async (h) => {
      await h.clear();
      await h.fold("Settings", SIDEBAR);
      const tab = h.page.locator("#angstrom-sidebar-tab:not(.is-closed)");
      if (await tab.count()) { await tab.click().catch(() => {}); await h.wait(700); }
      await chartTop(h);
      await h.ring(h.page.locator(LWC).first(), 4);
    },
    candles: async (h) => {
      await h.clear();
      const row = await chartControls(h);
      await h.ring(row);
      await timeframe(h, "4h", "3M");
      await h.wait(600);
      await chartTop(h);
    },
    zoom: async (h) => {
      await h.clear();
      const p = await chartPoints(h);
      if (!p) return;
      const c = { x: p.pane.x + p.pane.w * 0.7, y: p.pane.y + p.pane.h * 0.5 };
      await h.page.mouse.move(c.x, c.y, { steps: 16 });
      for (let i = 0; i < 6; i++) { await h.page.mouse.wheel(0, -120); await h.wait(220); }
      await h.wait(500);
      await drag(h, c, { x: c.x + 260, y: c.y }, 30);
      await h.wait(400);
      const back = h.page.locator(LWC + ' .ang-lwc-tools button[title="Back to the chosen range"], ' + LWC + " .ang-lwc-tools button").filter({ hasText: "⟲" }).first();
      await h.tip(back, "⟲ Back to the chosen range", "below");
      await back.click().catch(() => {});
      await h.wait(800);
    },
    legend: async (h) => {
      await h.clear();
      await hoverAcross(h, 0.35, 0.85, 5);
      await h.ring(h.page.locator(LWC + " .ang-lwc-legend").first(), 4);
    },
    indicators: async (h) => {
      await h.clear();
      await h.page.mouse.move(1150, 560);
      const row = await chartControls(h, "chart_indicators");
      await h.ring(row);
      await pill(h, "Stoch RSI", true);
      await h.clear();
      await chartTop(h, -120);
      await h.wait(1800);
      await chartControls(h, "chart_indicators");
      await pill(h, "Stoch RSI", false);
      const all = h.page.locator(".st-key-chart_indicators button").filter({ hasText: /^(All|Clear)$/ });
      await h.ring(all);
    },
    resize: async (h) => {
      await h.clear();
      const bar = h.page.locator(".st-key-chart_resize").first();
      await bar.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(700);
      await h.ring(bar, 4);
      await h.glide(bar, 400);
    },
    series: async (h) => {
      await h.clear();
      await h.card({ kicker: "📊 Charts", title: "Coming up in this series",
        lines: ["✓ Drawing tools", "✓ Where the money sits: the levels traders watch",
                "✓ Signals on the chart", "✓ Planning an entry"] });
    },
  },

  "c2-drawing-tools": {
    login: signInWide,
    setup: async (h) => {
      await openChart(h, "Bitcoin", "4h", "3M");
      await quietChart(h);
      await chartTop(h);
      await clearDrawings(h, false);
      await stopDrawing(h);
      await h.page.locator(LWC + ' .ang-lwc-tools button[aria-label^="Drawing tools"]').first().click().catch(() => {});
      await h.wait(500);
    },
    idea: async (h) => {
      await h.card({ kicker: "📊 Charts", title: "Draw your own analysis",
        lines: ["✓ Lines, levels, Fibonacci, measurements, notes", "✓ Saved to your account, on that asset",
                "✓ Shown on every candle size"] });
    },
    open: async (h) => {
      await h.clear();
      await chartTop(h);
      const bar = await drawTool(h);
      await h.ring(bar, 4);
    },
    trend: async (h) => {
      await h.clear();
      await drawTool(h, "Trend line");
      const p = await chartPoints(h);
      if (p) await drag(h, p.trendA, p.trendB);
    },
    hline: async (h) => {
      await drawTool(h, "Horizontal line");
      const p = await chartPoints(h);
      if (p) await tap(h, { x: p.recentHigh.x, y: p.recentHigh.y });
    },
    fib: async (h) => {
      await drawTool(h, "Fibonacci");
      const p = await chartPoints(h);
      if (p) await drag(h, p.fibLow, p.fibHigh, 36);
    },
    measure: async (h) => {
      await drawTool(h, "Measure");
      const p = await chartPoints(h);
      if (p) await drag(h, p.swingLow, p.recentHigh, 30);
      await h.wait(1500);
      await drawTool(h, "Undo");
    },
    position: async (h) => {
      await drawTool(h, "Long / short position");
      const p = await chartPoints(h);
      if (!p) return;
      const entry = { x: p.pane.x + p.pane.w * 0.62, y: p.last.y };
      const stop = { x: p.pane.x + p.pane.w * 0.8, y: p.last.y + p.pane.h * 0.08 };
      await drag(h, entry, stop);
      await tap(h, { x: stop.x, y: p.last.y - p.pane.h * 0.16 });
    },
    note: async (h) => {
      await drawTool(h, "Text note");
      const p = await chartPoints(h);
      if (!p) return;
      await tap(h, { x: p.recentHigh.x - 160, y: Math.max(p.recentHigh.y + 30, p.pane.y + 70) });
      await h.page.keyboard.type("Watch this level", { delay: 70 });
      await h.page.keyboard.press("Enter");
      await h.wait(500);
    },
    style: async (h) => {
      await stopDrawing(h);
      const colours = h.page.locator(LWC + ' .ang-lwc-drawbar button[aria-label^="Colour"]');
      await h.ring(colours);
      await h.wait(1500);
      await h.clear();
      await h.press(h.page.locator(LWC + ' .ang-lwc-drawbar button[aria-label="Undo"]').first(), false);
      await h.wait(900);
      const eye = h.page.locator(LWC + ' .ang-lwc-tools button[aria-label^="Hide the drawings"]').first();
      await h.press(eye, false);
      await h.wait(1300);
      await h.press(h.page.locator(LWC + ' .ang-lwc-tools button[aria-label^="Drawings are hidden"]').first(), false);
    },
    share: async (h) => {
      const share = h.page.locator(LWC + ' .ang-lwc-drawbar button[aria-label^="Share this chart"]').first();
      await h.ring(share, 4);
      await h.tip(share, "📤 Share this chart and its drawings with your communities", "below");
    },
    clear: async (h) => {
      await h.clear();
      await clearDrawings(h, true);
      await drawTool(h);
      await h.press(h.page.locator(LWC + ' .ang-lwc-tools button[aria-label^="Drawing tools"]').first(), false);
    },
  },

  "c3-levels": {
    login: signInWide,
    setup: async (h) => {
      await openChart(h, "Bitcoin", "4h", "1M");
      await quietChart(h);
      for (const name of ["Fair value gaps", "Single prints"]) await pill(h, name, false);
      await chartTop(h);
      await clearDrawings(h, false);
      await stopDrawing(h);
    },
    idea: async (h) => {
      await h.card({ kicker: "📊 Charts", title: "Where the money sits",
        lines: ["✓ Liquidation levels", "✓ Fair value gaps and single prints", "✓ Anchored VWAP and the volume profile"] });
    },
    open: async (h) => {
      await h.clear();
      await chartTop(h);
      await h.ring(h.page.locator(LWC).first(), 4);
    },
    liq: async (h) => {
      await h.clear();
      await pill(h, "Liquidation levels", true);
      await chartTop(h);
      await h.wait(2500);
    },
    fvg: async (h) => {
      await pill(h, "Liquidation levels", false);
      await pill(h, "Fair value gaps", true);
      await chartTop(h);
      await hoverAcross(h, 0.55, 0.9, 3);
    },
    sp: async (h) => {
      await pill(h, "Fair value gaps", false);
      await pill(h, "Single prints", true);
      await chartTop(h);
      await h.wait(2500);
    },
    avwap: async (h) => {
      await pill(h, "Single prints", false);
      await chartTop(h);
      await drawTool(h, "Anchored VWAP");
      const p = await chartPoints(h);
      if (p) await tap(h, p.swingLow);
      await stopDrawing(h);
      await h.wait(1500);
    },
    vprofile: async (h) => {
      await drawTool(h, "Volume profile");
      const p = await chartPoints(h);
      if (p) await drag(h, { x: p.xs[0], y: p.pane.y + p.pane.h * 0.5 }, { x: p.xs[1], y: p.pane.y + p.pane.h * 0.5 }, 40);
      await stopDrawing(h);
      await h.page.mouse.move(1150, 560);
      await h.wait(1500);
    },
    tidy: async (h) => {
      await h.card({ kicker: "📊 Charts", title: "What they tell you",
        lines: ["✓ Where price has reason to pause or turn", "✓ Somewhere to plan entries, stops and targets",
                "Not forecasts: levels, not promises"] });
      await clearDrawings(h, false);
      await drawTool(h);
      await h.page.locator(LWC + ' .ang-lwc-tools button[aria-label^="Drawing tools"]').first().click().catch(() => {});
    },
  },

  "c4-signals-on-chart": {
    login: signInWide,
    setup: async (h) => {
      await openChart(h, "Bitcoin", "1D", "1Y");
      for (const name of [/Sonar\s*$/, "Sonar markers", "Chart shapes", "Liquidation levels"]) await pill(h, name, false);
      await chartTop(h);
    },
    idea: async (h) => {
      await h.card({ kicker: "📊 Charts", title: "See the readings where they happened",
        lines: ["✓ Sonar strip and markers", "✓ Chart shapes and crosses", "✓ A Signal Set as colour bands",
                "✓ Fed, CPI and jobs days"] });
    },
    open: async (h) => {
      await h.clear();
      await chartTop(h);
      await h.ring(h.page.locator(LWC).first(), 4);
    },
    sonar: async (h) => {
      await h.clear();
      await pill(h, /Sonar\s*$/, true);
      await chartTop(h, -140);
      await hoverAcross(h, 0.5, 0.9, 3);
    },
    marks: async (h) => {
      await pill(h, "Sonar markers", true);
      const row = h.page.locator(".st-key-chart_sonar_marks").first();
      if (await row.count()) {
        await row.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
        await h.wait(600);
        await h.ring(row);
        await h.wait(1500);
        await h.clear();
      }
      await chartTop(h);
      await hoverAcross(h, 0.55, 0.92, 4);
    },
    shapes: async (h) => {
      await pill(h, "Sonar markers", false);
      await pill(h, /Sonar\s*$/, false);
      await pill(h, "Chart shapes", true);
      await chartTop(h);
      await h.wait(2500);
    },
    bands: async (h) => {
      await pill(h, "Chart shapes", false);
      const box = h.page.locator(".st-key-chart_band_set").first();
      await box.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(box);
      await pickNth(h, box, 1);
      await h.clear();
      await chartTop(h);
      await h.wait(2000);
    },
    events: async (h) => {
      const box = h.page.locator(".st-key-chart_band_set").first();
      await box.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await pickNth(h, box, 0, false);
      const ev = h.page.locator(".st-key-chart_events").first();
      await ev.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(500);
      await h.ring(ev);
      const ticked = await ev.locator('input[type="checkbox"]').first().isChecked().catch(() => true);
      if (!ticked) await h.press(ev.locator("label").first());
      await h.wait(1500);
      await h.clear();
      await chartTop(h);
      await hoverAcross(h, 0.7, 0.97, 3);
    },
    tidy: async (h) => {
      await h.clear();
      const row = await chartControls(h, "chart_indicators");
      await h.ring(row);
    },
  },

  "c5-plan-entry": {
    login: signInWide,
    setup: async (h) => {
      await openChart(h, "Bitcoin", "1h", "7D");
      await quietChart(h);
      await clearDrawings(h, false);
      await stopDrawing(h);
      const head = h.sum("Ladder helper");
      const open = await head.evaluate((n) => !!(n.parentElement && n.parentElement.open)).catch(() => false);
      if (open) { await head.click().catch(() => {}); await h.settle(); }
      await chartTop(h);
    },
    idea: async (h) => {
      await h.card({ kicker: "📊 Charts", title: "Don't buy all at once",
        lines: ["✓ A ladder of orders below the price", "✓ Spaced by the coin's own daily move", "✓ Drawn on the chart"] });
    },
    open: async (h) => {
      await h.clear();
      const head = h.sum("Ladder helper");
      await head.evaluate((n) => n.scrollIntoView({ block: "start", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      const open = await head.evaluate((n) => !!(n.parentElement && n.parentElement.open)).catch(() => false);
      if (!open) await h.press(head);
      await h.ring(h.section_("Ladder helper"));
    },
    style: async (h) => {
      await h.clear();
      const market = h.page.locator('[class*="st-key-ladder_style_"]').first();
      await h.ring(market);
      await h.press(market.locator("button").filter({ hasText: "Trending" }).first());
      await h.wait(1500);
      await h.press(market.locator("button").filter({ hasText: "Consolidating" }).first());
    },
    spacing: async (h) => {
      await h.clear();
      const table = h.section_("Ladder helper").locator("table.lad").first();
      await table.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(table);
    },
    lines: async (h) => {
      await h.clear();
      const toggle = h.page.locator('[class*="st-key-ladder_show_"]').first();
      await toggle.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(500);
      await h.press(toggle.locator("label").first());
      await h.wait(1500);
      await chartTop(h);
      await h.wait(2500);
    },
    fib: async (h) => {
      await h.clear();
      const place = h.page.locator('[class*="st-key-ladder_place_"]').first();
      await place.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(500);
      await h.press(place.locator("button").filter({ hasText: "On Fibonacci levels" }).first());
      await h.wait(1000);
      // No level left below the price (a falling market): the mirror, a short, measured from the last swing high.
      const table = () => h.section_("Ladder helper").locator("table.lad").first();
      let side = "long";
      if (!(await table().count())) {
        side = "short";
        await h.press(h.page.locator('[class*="st-key-ladder_side_"] button').filter({ hasText: "Short" }).first());
        await h.wait(1000);
      }
      const words = await h.section_("Ladder helper").getByText(/low [\d.,]+, high [\d.,]+/).first().textContent().catch(() => "");
      const m = (words || "").match(/low ([\d.,]+), high ([\d.,]+)/);
      if (await table().count()) await h.ring(table());
      await h.wait(1500);
      await h.clear();
      await chartTop(h);
      if (m) {                                   // the same move drawn with the Fibonacci tool: its lines meet the orders
        const lo = parseFloat(m[1].replace(/,/g, "")), hi = parseFloat(m[2].replace(/,/g, ""));
        const a = await pricePoint(h, side === "long" ? lo : hi, 0.35), b = await pricePoint(h, side === "long" ? hi : lo, 0.6);
        if (a && b) { await drawTool(h, "Fibonacci"); await drag(h, a, b, 36); await stopDrawing(h); }
      }
      await h.page.mouse.move(1150, 560);
      await h.wait(2000);
    },
    five: async (h) => {
      await chartControls(h);
      await timeframe(h, "5m", "7D");
      await chartTop(h);
      await h.wait(2500);
    },
    tidy: async (h) => {
      await chartControls(h);
      await timeframe(h, "4h", "1M");
      await clearDrawings(h, false);
      await h.page.locator('[class*="st-key-ladder_side_"] button').filter({ hasText: "Long" }).first().click().catch(() => {});
      const place = h.page.locator('[class*="st-key-ladder_place_"]').first();
      await place.locator("button").filter({ hasText: "By daily move" }).first().click().catch(() => {});
      await h.settle();
      const toggle = h.page.locator('[class*="st-key-ladder_show_"]').first();
      await toggle.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(400);
      await h.press(toggle.locator("label").first());
    },
  },
  "c6-chart-to-signals": {
    login: signInWide,
    idea: async (h) => {
      await h.card({ kicker: "📊 Charts", title: "From the chart to your signals",
        lines: ["✓ Chart shapes and Sonar markers", "✓ Fair value gaps, anchored VWAP, volume profile",
                "✓ In Sets, Prism scans, funnels and Soundings"] });
    },
    open: async (h) => {
      await h.clear();
      await lattice(h, "Signal Sets");
      const card = h.page.locator(".lat .lib .chip.card").filter({ hasText: "Levels made by trading" }).first();
      await h.show(card);
      await card.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(card);
    },
    variants: async (h) => {
      const card = h.page.locator(".lat .lib .chip.card").filter({ hasText: "Levels made by trading" }).first();
      for (const v of ["Anchored VWAP", "Volume profile", "Fair value gaps"]) {
        await h.press(card.locator(".vars button").filter({ hasText: v }).first());
        await h.wait(700);
      }
      await h.press(card.locator(".seg button").filter({ hasText: /^4h$/ }).first());
    },
    add: async (h) => {
      await h.clear();
      const card = () => h.page.locator(".lat .lib .chip.card").filter({ hasText: "Levels made by trading" }).first();
      await h.press(ADD("Fair value gaps"));
      await h.wait(600);
      await h.press(card().locator(".vars button").filter({ hasText: "Anchored VWAP" }).first());
      await h.press(card().locator("button.sq").first());
      await h.wait(600);
    },
    lines: async (h) => {
      await h.press('.lat button[aria-label="Add a line that must hold"] >> visible=true');
      await setLine(h, 0, "Fair value gaps (4h) · test up", "within", "3");
      await h.wait(600);
      await h.press('.lat button[aria-label="Add a line that must hold"] >> visible=true');
      await setLine(h, 1, "(swing low) (4h) · position", "is", "above");
    },
    shapes: async (h) => {
      const card = h.page.locator(".lat .lib .chip.card").filter({ hasText: "Chart shapes" }).first();
      await card.evaluate((n) => n.scrollIntoView({ block: "center", behavior: "smooth" })).catch(() => {});
      await h.wait(600);
      await h.ring(card);
    },
    save: async (h) => {
      await h.clear();
      await h.type('.lat input[aria-label="Set name"]', "Gap held above VWAP");
      await h.wait(1000);
      await save(h, "Save as a new Set", "It now appears in");
    },
    use: async (h) => {
      await h.card({ kicker: "Saved", title: "Gap held above VWAP",
        lines: ["✓ Scan your assets with it in Prism", "✓ A stage in a funnel", "✓ Colour bands on the chart",
                "✓ Readings Soundings checks too"] });
    },
  },
};
