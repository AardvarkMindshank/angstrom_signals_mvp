// The Angstrom Lattice diagram for the training videos, drawn over the page at 1280 x 610 real pixels.
// draw({stage, lit}): every part shows in outline from the start; stage 0 = outlines only; 1..5 fill in Signals, Signal Groups, Signal Sets, Prism Scan and Alerts in
// turn; 6 adds Strategies (coming next); 7 adds the closing line. lit = "signals" | "groups" | "sets" | "prism" |
// "alerts" highlights one part and dims the rest. Calling it again animates from the current picture.
// Everything is example content, drawn here; nothing is read from the app.

function draw({ stage, lit }) {
  const NAVY = "#0b2d6b", TEAL = "#0f766e", GREEN = "#16a34a", GREY = "#64748b", RED = "#dc2626", AMBER = "#b45309";
  const FONT = "'DejaVu Sans',system-ui,sans-serif";
  const ICONS = {
    signals: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    groups: '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    sets: '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>',
    prism: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    alerts: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    strategies: '<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>',
  };
  const svg = (name, size, colour) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${colour}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
  const pill = (text, bg, fg) => `<span style="display:inline-block;padding:2px 10px;border-radius:999px;background:${bg};color:${fg};font:bold 13px ${FONT}">${text}</span>`;

  let root = document.getElementById("demo-diagram");
  if (!root) {
    root = document.createElement("div");
    root.id = "demo-diagram";
    Object.assign(root.style, { position: "fixed", inset: "0", zIndex: 2147483590, pointerEvents: "none", background: "#fff",
      font: `16px/1.35 ${FONT}`, color: NAVY, opacity: "0", transition: "opacity .45s" });
    const W = 214, GAP = 34, X0 = (1280 - (5 * W + 4 * GAP)) / 2, Y = 118, H = 250;
    const parts = [
      ["signals", "Signals", `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:6px">
          ${[["Trend", "#2563eb"], ["Momentum", "#9333ea"], ["Regime", "#0891b2"], ["Structure", "#b45309"], ["Volume", "#16a34a"], ["Sentiment", "#db2777"]]
            .map(([t, c], i) => `<div class="dg-bit" style="transition-delay:${0.15 + i * 0.12}s;font-size:13px;padding:5px 6px;border-radius:8px;background:${c}14;color:${c};font-weight:bold;text-align:center">${t}</div>`).join("")}
        </div>
        <div style="margin-top:12px;font-size:13px;color:${GREY}">21 signals, each one measurement</div>`],
      ["groups", "Signal Groups", `
        <svg width="186" height="114" viewBox="0 0 186 114" style="margin-top:2px">
          <defs><linearGradient id="dg-g" x1="0" x2="1"><stop offset="0" stop-color="${RED}"/><stop offset=".5" stop-color="#cbd5e1"/><stop offset="1" stop-color="${GREEN}"/></linearGradient></defs>
          <path d="M18 92 A75 75 0 0 1 168 92" fill="none" stroke="url(#dg-g)" stroke-width="14" stroke-linecap="round"/>
          <g class="dg-needle" style="transform-origin:93px 92px;transform:rotate(-90deg);transition:transform 1.4s cubic-bezier(.3,1.4,.6,1) .4s">
            <line x1="93" y1="92" x2="93" y2="30" stroke="${NAVY}" stroke-width="4" stroke-linecap="round"/></g>
          <circle cx="93" cy="92" r="7" fill="${NAVY}"/>
          <text x="4" y="112" font-size="11" fill="${GREY}" font-family="DejaVu Sans">−100</text>
          <text x="150" y="112" font-size="11" fill="${GREY}" font-family="DejaVu Sans">+100</text>
        </svg>
        <div class="dg-bit" style="transition-delay:1.5s;text-align:center;margin-top:4px">
          <span style="font:bold 24px ${FONT}">+42</span> ${pill("Bullish", "#dcfce7", GREEN)}</div>
        <div style="margin-top:8px;font-size:13px;color:${GREY}">one score, your labels</div>`],
      ["sets", "Signal Sets", `
        <div style="margin-top:8px;display:flex;flex-direction:column;gap:8px;font-size:14px">
          ${["Trend is Bullish", "Stochastic is at most 30"].map((t, i) => `<div class="dg-bit" style="transition-delay:${0.3 + i * 0.5}s;display:flex;gap:8px;align-items:center">
            <span style="width:22px;height:22px;border-radius:50%;background:${GREEN};color:#fff;font:bold 13px/22px ${FONT};text-align:center">✓</span>${t}</div>`).join("")}
          <div class="dg-bit" style="transition-delay:1.4s;margin-top:6px;text-align:center">${pill("Yes", "#dcfce7", GREEN)}</div>
        </div>
        <div style="margin-top:12px;font-size:13px;color:${GREY}">Yes, No or Unknown, with the reason</div>`],
      ["prism", "Prism Scan", `
        <div style="margin-top:6px;display:flex;flex-direction:column;gap:6px;font-size:14px">
          ${[["Bitcoin", "Yes"], ["Ethereum", "No"], ["Solana", "Yes"], ["Apple", "No"], ["XRP", "Unknown"]].map(([a, v], i) => `<div class="dg-bit" style="transition-delay:${0.2 + i * 0.25}s;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #e2e8f0;padding-bottom:3px">
            <span>${a}</span>${v === "Yes" ? pill("Yes", "#dcfce7", GREEN) : v === "No" ? pill("No", "#f1f5f9", GREY) : pill("Unknown", "#fef3c7", AMBER)}</div>`).join("")}
        </div>
        <div style="margin-top:8px;font-size:13px;color:${GREY}">your watchlist: now, then, or on a schedule</div>`],
      ["alerts", "Alerts", `
        <div style="margin-top:8px;display:flex;flex-direction:column;gap:9px;font-size:14px">
          ${["In the app", "By email, instantly", "In the daily summary"].map((t, i) => `<div class="dg-bit" style="transition-delay:${0.25 + i * 0.3}s;padding:6px 10px;border-radius:8px;background:#f1f5f9">${t}</div>`).join("")}
        </div>
        <div style="margin-top:12px;font-size:13px;color:${GREY}">when an asset turns Yes</div>`],
    ];
    let html = `<div class="dg-title" style="position:absolute;top:34px;width:100%;text-align:center;font:bold 32px ${FONT}">From signals to a scan</div>`;
    parts.forEach(([key, name, body], i) => {
      const x = X0 + i * (W + GAP);
      html += `<div class="dg-box" data-k="${key}" data-i="${i + 1}" style="position:absolute;left:${x}px;top:${Y}px;width:${W}px;height:${H}px;box-sizing:border-box;padding:14px 14px;border:2px solid #cbd5e1;border-radius:16px;background:#fff">
        <div class="dg-head" style="display:flex;align-items:center;gap:8px;font:bold 17px ${FONT}">${svg(key, 22, TEAL)}${name}</div><div class="dg-body">${body}</div></div>`;
      if (i < 4) html += `<div class="dg-arrow" data-i="${i + 2}" style="position:absolute;left:${x + W + 4}px;top:${Y + H / 2 - 14}px;width:${GAP - 8}px;height:28px">
        <svg width="${GAP - 8}" height="28" viewBox="0 0 26 28"><path d="M2 14h18M14 7l7 7-7 7" fill="none" stroke="${TEAL}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></div>`;
    });
    const sx = X0 + 2 * (W + GAP) + W / 2 - 210;
    html += `<div class="dg-box" data-k="strategies" data-i="6" style="position:absolute;left:${sx}px;top:${Y + H + 34}px;width:420px;height:76px;box-sizing:border-box;padding:12px 16px;border:2px dashed #94a3b8;border-radius:16px;background:#fff;color:${GREY}">
      <div class="dg-head" style="display:flex;align-items:center;gap:8px;font:bold 17px ${FONT}">${svg("strategies", 22, GREY)}Strategies <span class="dg-body" style="font:13px ${FONT}">· coming next</span></div>
      <div class="dg-body" style="font-size:14px;margin-top:4px">Entries, exits and risk, built on the same Sets</div></div>`;
    html += `<div class="dg-arrow" data-i="6" style="position:absolute;left:${X0 + 2 * (W + GAP) + W / 2 - 1}px;top:${Y + H + 4}px;height:28px;border-left:3px dashed #94a3b8"></div>`;
    html += `<div class="dg-foot" data-i="7" style="position:absolute;bottom:26px;width:100%;text-align:center;font:17px ${FONT};color:${GREY}">Descriptive readings of the market as it is: not a forecast, and not advice.</div>`;
    root.innerHTML = html;
    root.querySelectorAll(".dg-box,.dg-arrow,.dg-foot").forEach((n) => {
      Object.assign(n.style, { opacity: "0", transform: "translateY(14px)", transition: "opacity .55s, transform .55s, border-color .4s, box-shadow .4s, filter .4s" });
    });
    root.querySelectorAll(".dg-body,.dg-head").forEach((n) => { n.style.opacity = "0"; n.style.transition = "opacity .5s"; });
    root.querySelectorAll(".dg-bit").forEach((n) => { n.style.opacity = "0"; n.style.transition = (n.style.transition ? n.style.transition + "," : "") + "opacity .45s"; });
    document.documentElement.appendChild(root);
  }
  requestAnimationFrame(() => requestAnimationFrame(() => {
    root.style.opacity = "1";
    // Every part is drawn in outline from the start; a part fills in when the narration reaches it.
    root.querySelectorAll("[data-i]").forEach((n) => {
      const on = Number(n.dataset.i) <= stage;
      const box = n.classList.contains("dg-box"), arrow = n.classList.contains("dg-arrow");
      n.style.opacity = on || box ? "1" : arrow ? "0.3" : "0";
      n.style.transform = on || box || arrow ? "none" : "translateY(14px)";
      if (!box) return;
      n.querySelectorAll(".dg-body").forEach((b) => { b.style.opacity = on ? "1" : "0"; });
      n.querySelectorAll(".dg-head").forEach((b) => { b.style.opacity = on ? "1" : "0.45"; });
      if (on) n.querySelectorAll(".dg-bit").forEach((b) => { b.style.opacity = "1"; });
      const needle = n.querySelector(".dg-needle");
      if (needle && on) needle.style.transform = "rotate(38deg)";
      const me = on && lit && n.dataset.k === lit;
      n.style.borderStyle = on && n.dataset.k !== "strategies" ? "solid" : "dashed";
      n.style.borderColor = me ? "#0f766e" : on && n.dataset.k !== "strategies" ? "#cbd5e1" : "#cbd5e1";
      n.style.boxShadow = me ? "0 0 0 6px rgba(15,118,110,.15), 0 10px 30px rgba(15,118,110,.18)" : "none";
      n.style.filter = on && lit && !me ? "grayscale(.6) opacity(.45)" : "none";
    });
  }));
}

module.exports = { draw };
