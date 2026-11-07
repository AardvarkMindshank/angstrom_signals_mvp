// Things the training-video actions do on the demo page: move the pointer and press, type, choose, switch section,
// and draw notes, rings, idea cards and the Angstrom Lattice diagram on top of the page. Notes, cards and the diagram
// are drawn outside the page's zoom, at real pixels (1280 x 610).
const DIAGRAM = require("./diagram.js");

module.exports = function makeHelpers(page, url) {
  const h = { page };
  h.wait = (ms) => page.waitForTimeout(ms);
  h.loc = (selector) => (typeof selector === "string" ? page.locator(selector).first() : selector);

  // Wait until Streamlit has finished redrawing.
  h.settle = async () => {
    await page.waitForTimeout(450);
    await page.waitForFunction(() => !document.querySelector("[data-testid='stStatusWidgetRunningIcon']"),
      null, { timeout: 180000 }).catch(() => {});
    await page.waitForTimeout(350);
  };
  h.open = async (query) => {
    await page.goto(url + (query || ""));
    await page.waitForSelector(".lat", { timeout: 180000 });
    await h.settle();
    await page.mouse.move(640, 300, { steps: 2 });
  };
  h.show = async (selector) => {
    await h.loc(selector).scrollIntoViewIfNeeded({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(250);
  };
  // Move the pointer visibly to an element (scrolling it into view first).
  h.glide = async (selector, pause = 350) => {
    const l = h.loc(selector);
    await h.show(l);
    const box = await l.boundingBox();
    if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 22 });
    await page.waitForTimeout(pause);
  };
  h.press = async (selector, settle = true) => {
    await h.glide(selector);
    await h.loc(selector).click({ timeout: 15000 });
    if (settle) await h.settle();
  };
  // Type into a field the way a person does, then leave it (which saves the change).
  h.type = async (selector, text) => {
    await h.glide(selector);
    const l = h.loc(selector);
    await l.click({ clickCount: 3 });
    await l.press("Control+A");
    await l.pressSequentially(text, { delay: 45 });
    await l.press("Tab");
    await h.settle();
  };
  // A drop-down in the editors (a plain <select>): point at it, then choose by value.
  h.choose = async (selector, value) => {
    await h.glide(selector, 250);
    await h.loc(selector).selectOption(value);
    await h.settle();
  };
  // A Streamlit drop-down ("Start from"): open it, so the list is seen, then pick the option.
  h.pick = async (label, option) => {
    const box = page.locator(`[data-testid="stSelectbox"]:has-text("${label}")`).first();
    await h.press(box.locator("[data-baseweb='select']"), false);
    await page.waitForTimeout(900);
    if (option === null) { await page.keyboard.press("Escape"); await page.waitForTimeout(300); return; }
    await h.press(page.locator(`[role="option"]:has-text("${option}")`).first());
  };
  // One of the four parts of Angstrom Lattice.
  h.section = async (name) => {
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
    await page.waitForTimeout(500);
    await h.press(page.locator("button").filter({ hasText: name }).first());
    await page.waitForSelector(".lat", { timeout: 60000 });
    await h.settle();
  };
  h.top = async () => { await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" })); await page.waitForTimeout(600); };

  // ---------------------------------------------------------------- drawn on top of the page
  h.clear = (...ids) => page.evaluate((ids) => {
    (ids.length ? ids : ["demo-tip", "demo-ring", "demo-card", "demo-diagram"]).forEach((id) => {
      const n = document.getElementById(id);
      if (n) { n.style.transition = "opacity .35s"; n.style.opacity = "0"; setTimeout(() => n.remove(), 380); }
    });
  }, ids).then(() => page.waitForTimeout(400));

  // A note beside an element, like the app's hover note (recordings never show the browser's own).
  h.tip = async (selector, text, where = "below") => {
    const l = h.loc(selector);
    await h.show(l);
    const box = await l.boundingBox();
    if (!box) return;
    if (!text) text = await l.evaluate((n) => n.getAttribute("title") || n.getAttribute("aria-label") || "");
    await h.glide(l, 150);
    await page.evaluate(([box, text, where]) => {
      document.getElementById("demo-tip")?.remove();
      const n = document.createElement("div");
      n.id = "demo-tip";
      n.textContent = text;
      Object.assign(n.style, { position: "fixed", zIndex: 2147483601, pointerEvents: "none", maxWidth: "420px",
        background: "#1f2937", color: "#fff", font: "17px/1.4 'DejaVu Sans',system-ui,sans-serif", padding: "10px 14px",
        borderRadius: "10px", boxShadow: "0 8px 24px rgba(0,0,0,.3)", whiteSpace: "pre-line", opacity: "0",
        transition: "opacity .3s" });
      document.documentElement.appendChild(n);
      const b = n.getBoundingClientRect();
      let top = where === "above" ? box.y - b.height - 10 : box.y + box.height + 10;
      if (top + b.height > 600) top = Math.max(8, box.y - b.height - 10);
      let left = where === "right" ? box.x + box.width + 14 : box.x + box.width / 2 - b.width / 2;
      if (where === "right") top = Math.max(8, Math.min(600 - b.height, box.y + box.height / 2 - b.height / 2));
      n.style.top = top + "px";
      n.style.left = Math.min(Math.max(8, left), 1272 - b.width) + "px";
      requestAnimationFrame(() => { n.style.opacity = "1"; });
    }, [box, text, where]);
    await page.waitForTimeout(350);
  };
  // An amber ring around one element, or around several (selector list), to point something out.
  h.ring = async (selectors, pad = 6) => {
    const boxes = [];
    for (const s of [].concat(selectors)) {
      const matches = typeof s === "string" ? [h.loc(s)] : await s.all();     // a locator: every element it finds
      for (const l of matches) {
        if (boxes.length === 0) await h.show(l);
        const b = await l.boundingBox().catch(() => null);
        if (b) boxes.push(b);
      }
    }
    if (!boxes.length) return;
    const x = Math.min(...boxes.map((b) => b.x)) - pad, y = Math.min(...boxes.map((b) => b.y)) - pad;
    const r = Math.max(...boxes.map((b) => b.x + b.width)) + pad, btm = Math.max(...boxes.map((b) => b.y + b.height)) + pad;
    await page.evaluate(([x, y, w, ht]) => {
      document.getElementById("demo-ring")?.remove();
      const n = document.createElement("div");
      n.id = "demo-ring";
      Object.assign(n.style, { position: "fixed", left: x + "px", top: y + "px", width: w + "px", height: ht + "px",
        border: "3px solid #f59e0b", borderRadius: "12px", boxShadow: "0 0 0 4000px rgba(15,23,42,.18)",
        zIndex: 2147483599, pointerEvents: "none", opacity: "0", transition: "opacity .35s" });
      document.documentElement.appendChild(n);
      requestAnimationFrame(() => { n.style.opacity = "1"; });
    }, [x, y, r - x, btm - y]);
    await page.waitForTimeout(400);
  };
  // A card in the middle of the screen: a short idea or summary. lines: plain strings; "✓ " starts a ticked line.
  h.card = async ({ kicker, title, lines = [], foot }) => {
    await page.evaluate(([kicker, title, lines, foot]) => {
      document.getElementById("demo-card")?.remove();
      const veil = document.createElement("div");
      veil.id = "demo-card";
      Object.assign(veil.style, { position: "fixed", inset: "0", zIndex: 2147483600, pointerEvents: "none",
        background: "rgba(15,23,42,.45)", display: "flex", alignItems: "center", justifyContent: "center",
        opacity: "0", transition: "opacity .45s" });
      const c = document.createElement("div");
      Object.assign(c.style, { background: "#fff", color: "#0b2d6b", borderRadius: "18px", padding: "30px 40px",
        minWidth: "560px", maxWidth: "820px", boxShadow: "0 20px 60px rgba(0,0,0,.35)",
        font: "20px/1.45 'DejaVu Sans',system-ui,sans-serif", transform: "translateY(12px)", transition: "transform .45s" });
      const add = (text, css) => { const n = document.createElement("div"); n.textContent = text; Object.assign(n.style, css); c.appendChild(n); return n; };
      if (kicker) add(kicker, { font: "bold 15px 'DejaVu Sans',sans-serif", letterSpacing: ".08em", textTransform: "uppercase", color: "#16a34a", marginBottom: "6px" });
      add(title, { font: "bold 32px/1.2 'DejaVu Sans',sans-serif", marginBottom: lines.length ? "18px" : "0" });
      lines.forEach((t, i) => {
        const tick = t.startsWith("✓ ");
        const n = add(tick ? t.slice(2) : t, { color: "#334155", padding: "6px 0 6px " + (tick ? "34px" : "0"), position: "relative",
          opacity: "0", transition: `opacity .4s ${0.35 + i * 0.35}s` });
        if (tick) {
          const m = document.createElement("span");
          m.textContent = "✓";
          Object.assign(m.style, { position: "absolute", left: "0", top: "5px", width: "24px", height: "24px", borderRadius: "50%",
            background: "#16a34a", color: "#fff", font: "bold 15px/24px 'DejaVu Sans',sans-serif", textAlign: "center" });
          n.appendChild(m);
        }
        requestAnimationFrame(() => requestAnimationFrame(() => { n.style.opacity = "1"; }));
      });
      if (foot) add(foot, { marginTop: "16px", font: "15px 'DejaVu Sans',sans-serif", color: "#64748b" });
      veil.appendChild(c);
      document.documentElement.appendChild(veil);
      requestAnimationFrame(() => { veil.style.opacity = "1"; c.style.transform = "none"; });
    }, [kicker, title, lines, foot]);
    await page.waitForTimeout(600);
  };
  // The Angstrom Lattice diagram (diagram.js): stage = how much is shown, lit = the part to highlight.
  h.diagram = async (stage, lit) => {
    await page.evaluate(DIAGRAM.draw, { stage, lit: lit || null });
    await page.waitForTimeout(300);
  };
  return h;
};
