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
  await page.mouse.move(700, 300);
  await h.settle();
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
      await h.ring(h.section_("Crypto Signals"));
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
};
