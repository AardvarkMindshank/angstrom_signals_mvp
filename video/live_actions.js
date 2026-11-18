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
};
