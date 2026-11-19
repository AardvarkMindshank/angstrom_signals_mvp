// Explainer pictures for the Soundings in-depth video, drawn over the page at 1280 x 610 real pixels.
// draw({scene}) shows one picture (fading in, parts appearing in turn); h.clear() removes it (id "demo-diagram").
// The numbers are the checked run's own (data/soundings.json, crypto, daily candles, as of 19 Nov 2026), written in
// here so the picture can be drawn without reading the app.

function draw({ scene }) {
  const NAVY = "#0b2d6b", GREEN = "#16a34a", RED = "#dc2626", GREY = "#64748b", AMBER = "#b45309", BLUE = "#2563eb";
  const LIGHT = "#f1f5f9", FONT = "'DejaVu Sans',system-ui,sans-serif";
  let n = 0;
  const step = (css = "") => `class="sd-in" style="--d:${(n++) * 0.45}s;${css}"`;
  const box = (inner, css = "") =>
    `<div ${step()} ><div style="background:${LIGHT};border-radius:14px;padding:16px 20px;${css}">${inner}</div></div>`;
  const big = (text, colour = NAVY) => `<div style="font:bold 30px/1.2 ${FONT};color:${colour}">${text}</div>`;
  const small = (text, colour = GREY) => `<div style="font:16px/1.4 ${FONT};color:${colour};margin-top:6px">${text}</div>`;
  const pill = (text, bg, fg = "#fff") =>
    `<span style="display:inline-block;padding:3px 12px;border-radius:999px;background:${bg};color:${fg};font:bold 15px ${FONT}">${text}</span>`;
  const bar = (label, pct, colour, note) =>
    `<div ${step(`display:flex;align-items:center;gap:14px;margin:12px 0`)}>
       <div style="width:230px;text-align:right;font:17px ${FONT};color:${NAVY}">${label}</div>
       <div style="flex:1;background:#e2e8f0;border-radius:8px;height:34px;position:relative;overflow:hidden">
         <div class="sd-grow" style="--w:${pct * 2}%;height:100%;background:${colour};border-radius:8px"></div></div>
       <div style="width:170px;font:bold 20px ${FONT};color:${colour}">${note}</div></div>`;

  const scenes = {
    question: () => `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-top:20px">
        ${box(`${pill("The usual way", GREY)}<div style="margin-top:14px">${big("Signal → what followed?")}</div>
          ${small("Pick a signal first, then check what price did after it. You only ever test the ideas you already had.")}`)}
        ${box(`${pill("Soundings", GREEN)}<div style="margin-top:14px">${big("Move → what came before?", GREEN)}</div>
          ${small("Mark every past rise and fall first, then look back at every reading at the close before each one. The data suggests the ideas.")}`)}
      </div>
      <div ${step(`margin-top:34px;text-align:center;font:20px ${FONT};color:${NAVY}`)}>
        Like a ship's sounding line: measure the bottom you sailed over, so you know the water.</div>`,

    move: () => {
      // A price path from the close (left), with the +2 and -1 lines and the 6-candle window.
      const W = 860, H = 330, X0 = 70, Y0 = 200, U = 46;            // one typical move = 46 px
      const xs = [0, 1, 2, 3, 4, 5, 6].map((i) => X0 + i * 100);
      const path = [0, -0.4, 0.3, 0.9, 1.6, 2.2, 2.0];
      const pts = path.map((v, i) => `${xs[i]},${Y0 - v * U}`).join(" ");
      return `
      <div style="display:flex;gap:34px;align-items:center">
        <div ${step()}><svg width="${W}" height="${H}" style="font:15px ${FONT}">
          <rect x="${X0}" y="20" width="600" height="${H - 50}" fill="#f8fafc" stroke="#e2e8f0"/>
          <text x="${X0 + 300}" y="${H - 8}" text-anchor="middle" fill="${GREY}">the next 6 daily candles</text>
          <line x1="${X0}" x2="${X0 + 600}" y1="${Y0 - 2 * U}" y2="${Y0 - 2 * U}" stroke="${GREEN}" stroke-width="3" stroke-dasharray="8 6"/>
          <text x="${X0 + 610}" y="${Y0 - 2 * U + 5}" fill="${GREEN}" font-weight="bold">+2 typical moves</text>
          <line x1="${X0}" x2="${X0 + 600}" y1="${Y0}" y2="${Y0}" stroke="${GREY}" stroke-width="1.5"/>
          <text x="${X0 - 8}" y="${Y0 + 5}" text-anchor="end" fill="${NAVY}" font-weight="bold">close</text>
          <line x1="${X0}" x2="${X0 + 600}" y1="${Y0 + U}" y2="${Y0 + U}" stroke="${RED}" stroke-width="3" stroke-dasharray="8 6"/>
          <text x="${X0 + 610}" y="${Y0 + U + 5}" fill="${RED}" font-weight="bold">−1 first?</text>
          <polyline class="sd-draw" points="${pts}" fill="none" stroke="${NAVY}" stroke-width="4" stroke-linejoin="round"/>
          <circle cx="${xs[5]}" cy="${Y0 - 2.2 * U}" r="9" fill="${GREEN}" class="sd-in" style="--d:2.2s"/>
        </svg></div>
        <div style="flex:1">
          ${box(`${big("A rise", GREEN)}${small("Price reaches 2 typical moves above the close within 6 daily candles, without first falling 1 typical move below it.")}`)}
          <div style="height:14px"></div>
          ${box(`${big("A fall", RED)}${small("The mirror image. A candle that touches both lines counts as neither.")}`)}
        </div>
      </div>`;
    },

    typical: () => `
      <div style="text-align:center">${box(`${big("A typical move = that coin's average daily range")}
        ${small("The average true range of the last 20 candles. So a 'rise' means the same thing for a calm coin and a wild one.")}`)}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-top:30px">
        ${box(`${pill("Calm coin", BLUE)}<div style="margin-top:10px">${big("typical move 2%")}</div>${small("a rise = +4% before −2%")}`)}
        ${box(`${pill("Wild coin", AMBER)}<div style="margin-top:10px">${big("typical move 8%")}</div>${small("a rise = +16% before −8%")}`)}
      </div>`,

    readings: () => `
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:18px">
        ${[["Trend", "direction, averages, Ichimoku"], ["Stretch", "RSI, Bollinger, Stochastic"], ["Flow", "volume, OBV, money flow"],
           ["Patterns", "double tops and bottoms"], ["Sonar", "WaveTrend, Stoch RSI, dots"], ["Structure", "regime, swings, support"],
           ["Tides", "Tide, sea state, wind"], ["Macro", "dollar, rates, credit, fear"]]
          .map(([a, b]) => box(`<div style="font:bold 21px ${FONT};color:${NAVY}">${a}</div>${small(b)}`)).join("")}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:22px;margin-top:26px">
        ${box(`${big("127")}${small("single conditions, cut at fixed points, never tuned to the data")}`)}
        ${box(`${big("+ pairs")}${small("two conditions together: 7,319 looked at in all")}`)}
        ${box(`${big("as at each close", GREEN)}${small("the app's own signal library, replayed with nothing later visible")}`)}
      </div>`,

    usual: () => `
      <div ${step(`font:bold 26px ${FONT};color:${NAVY};margin-bottom:6px`)}>Lift: how much more often than usual?</div>
      ${bar("Usual (comparable days)", 20.7, "#94a3b8", "20.7%")}
      ${bar("After the condition", 30.7, GREEN, "30.7%")}
      <div ${step(`margin:18px 0 0 244px;font:bold 26px ${FONT};color:${GREEN}`)}>30.7 ÷ 20.7 = 1.48× usual</div>
      <div ${step(`margin:22px 0 0 0`)}>${box(`${small("<b style='color:" + NAVY + "'>Comparable days:</b> the same coin, in the same year, on the same side of its 200-day average. So a bull year, or a coin that only went up, can't make a condition look good.", "#334155")}`)}</div>`,

    split: () => {
      const seg = (w, bg, fg, a, b) =>
        `<div style="width:${w}%;background:${bg};color:${fg};padding:18px 16px;box-sizing:border-box">
           <div style="font:bold 21px ${FONT}">${a}</div><div style="font:15px ${FONT};margin-top:4px;opacity:.9">${b}</div></div>`;
      return `
      <div ${step(`display:flex;border-radius:14px;overflow:hidden;margin-top:30px`)}>
        ${seg(55, BLUE, "#fff", "Search years", "2018 to 2022: ideas are found here")}
        ${seg(28, GREEN, "#fff", "Later years", "2023 to Oct 2024: checked once")}
        ${seg(17, "#1f2937", "#fff", "🔒 Hold-out", "30 Oct 2024 on: never read")}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:22px;margin-top:30px">
        ${box(`${small("<b style='color:" + NAVY + "'>The search</b> may try thousands of ideas. It's allowed to be greedy.", "#334155")}`)}
        ${box(`${small("<b style='color:" + NAVY + "'>The later years</b> are a fresh exam the search never saw. Only the best of each idea sits it, once.", "#334155")}`)}
        ${box(`${small("<b style='color:" + NAVY + "'>The hold-out</b> is kept sealed for the final test of a finished strategy. No tuning, no peeking.", "#334155")}`)}
      </div>`;
    },

    many: () => {
      const dots = Array.from({ length: 300 }, (_, i) => {
        const lucky = [7, 31, 58, 77, 102, 140, 166, 199, 231, 260, 288, 295, 19, 121, 213].includes(i);
        return `<span style="display:inline-block;width:14px;height:14px;margin:3px;border-radius:50%;background:${lucky ? AMBER : "#cbd5e1"}"></span>`;
      }).join("");
      return `
      <div style="display:flex;gap:34px;align-items:center">
        <div ${step(`width:560px;line-height:0`)}>${dots}</div>
        <div style="flex:1">
          ${box(`${big("Try enough ideas, and some look great by luck")}
            ${small("Test 300 useless ideas at the usual 1-in-20 standard, and about 15 will pass anyway (the orange ones).")}`)}
          <div style="height:14px"></div>
          ${box(`${big("So the bar rises with the tries", GREEN)}
            ${small("Benjamini–Hochberg: at most 10% of what's kept may be luck. Plus at least 1.25× usual, 150 days and 8 coins.")}`)}
        </div>
      </div>`;
    },

    together: () => `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-top:20px">
        ${box(`${pill("The trap", RED)}<div style="margin-top:12px">${big("Coins move together")}</div>
          ${small("When Bitcoin rises, most coins rise the same week. 100 coins on one day are not 100 separate pieces of evidence, and neighbouring days overlap too.")}`)}
        ${box(`${pill("What Soundings does", GREEN)}<div style="margin-top:12px">${big("Resample whole stretches of days", GREEN)}</div>
          ${small("The test reshuffles blocks of calendar days across all coins together, thousands of times. That keeps the crowding in, so the evidence isn't counted twice.")}`)}
      </div>`,

    themes: () => `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-top:40px">
        ${box(`${big("7,319")}${small("conditions and pairs looked at")}`, "width:250px;text-align:center")}
        <div ${step(`font:bold 40px ${FONT};color:${GREY}`)}>→</div>
        ${box(`${big("1,004")}${small("passed the search, for rises")}`, "width:250px;text-align:center")}
        <div ${step(`font:bold 40px ${FONT};color:${GREY}`)}>→</div>
        ${box(`${big("20 themes", GREEN)}${small("one idea in many forms: only the strongest of each is checked")}`, "width:300px;text-align:center")}
      </div>
      <div ${step(`margin-top:34px;text-align:center;font:19px ${FONT};color:#334155`)}>
        "Near the top of the Bollinger band" turns up in dozens of pairs. Counting it dozens of times would be cheating.</div>`,

    verdicts: () => {
      const row = (icon, word, why, count, colour) =>
        `<div ${step(`display:grid;grid-template-columns:60px 310px 1fr 70px;align-items:center;gap:12px;padding:10px 16px;margin:8px 0;background:${LIGHT};border-radius:12px`)}>
          <div style="font:28px ${FONT}">${icon}</div><div style="font:bold 20px ${FONT};color:${colour}">${word}</div>
          <div style="font:16px ${FONT};color:#334155">${why}</div><div style="font:bold 26px ${FONT};color:${colour};text-align:right">${count}</div></div>`;
      return `
      <div ${step(`font:bold 22px ${FONT};color:${NAVY};margin-bottom:6px`)}>Crypto rises: the 20 theme leaders, on the later years</div>
      ${row("✅", "Held up", "still more rises than usual, on most coins", 3, GREEN)}
      ${row("↕️", "A bigger move, either way", "more rises AND more falls: a move coming, direction unknown", 10, BLUE)}
      ${row("⚠️", "Held up, on a few coins", "worked later, but only on some coins", 0, AMBER)}
      ${row("➖", "Weaker later", "pointed the same way, but not clearly enough", 5, GREY)}
      ${row("✖️", "Faded", "no more rises than usual once the search was over", 2, RED)}`;
    },

    example: () => `
      <div ${step(`font:bold 24px ${FONT};color:${NAVY}`)}>Bollinger position 0.8 to 1 + Stoch RSI: apart</div>
      ${small("Price near the top of its Bollinger band, while the two Stoch RSI lines are far apart.")}
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:22px;margin-top:22px">
        ${box(`${pill("Search years", BLUE)}<div style="margin-top:10px">${big("1.48×")}</div>${small("30.7% vs 20.7% usual · 4,215 days · 94 coins")}`)}
        ${box(`${pill("Later years", GREEN)}<div style="margin-top:10px">${big("1.36×", GREEN)}</div>${small("27.4% vs 20.1% usual · 3,632 days · 71 of 97 coins higher")}`)}
        ${box(`${pill("Falls after it", GREY)}<div style="margin-top:10px">${big("1.17×", GREY)}</div>${small("a little raised too, but under the 1.25× that would make it 'either way'")}`)}
      </div>
      <div ${step(`margin-top:26px;text-align:center;font:19px ${FONT};color:#334155`)}>
        Smaller on the exam than in the search: normal. A real edge shrinks; a lucky one vanishes.</div>`,

    integrity: () => {
      const tick = (a, b) => `<div ${step(`display:flex;gap:14px;align-items:flex-start;margin:9px 0`)}>
        <span style="flex:none;width:28px;height:28px;border-radius:50%;background:${GREEN};color:#fff;font:bold 17px/28px ${FONT};text-align:center">✓</span>
        <div><b style="font:bold 18px ${FONT};color:${NAVY}">${a}</b> <span style="font:16px ${FONT};color:#334155">${b}</span></div></div>`;
      return `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px 40px">
        <div>
          ${tick("No survivors only.", "The 101 most traded coins of 2018–2023, including ones that collapsed or stopped trading.")}
          ${tick("No hindsight.", "Every reading is replayed as it stood at that close; macro data as first published.")}
          ${tick("Fixed cut points.", "Thresholds set in advance, never tuned to make results look better.")}
          ${tick("Fair comparison.", "Same coin, same year, same side of the 200-day average.")}
        </div>
        <div>
          ${tick("Corrected for tries.", "False finds kept to 10%, in the search and again on the later years.")}
          ${tick("Breadth.", "It must hold on many coins, not one lucky chart.")}
          ${tick("A sealed hold-out.", "Nothing from 30 Oct 2024 on is ever read.")}
          ${tick("Failures shown.", "Faded results stay on the page: what didn't work is evidence too.")}
        </div>
      </div>`;
    },

    limits: () => `
      <div style="display:flex;gap:34px;align-items:center">
        <div ${step(`width:420px`)}>
          <div style="display:flex;flex-wrap:wrap;width:400px">${Array.from({ length: 100 }, (_, i) =>
            `<span style="width:30px;height:30px;margin:5px;border-radius:6px;background:${i < 27 ? GREEN : "#e2e8f0"}"></span>`).join("")}</div>
          ${small("27 in 100: a rise followed. 73 in 100: it didn't.")}
        </div>
        <div style="flex:1">
          ${box(`${big("An edge is a tilt, not a promise")}${small("Even the best result means no rise most of the time.")}`)}
          <div style="height:12px"></div>
          ${box(`${small("<b style='color:" + NAVY + "'>Also left out:</b> trading costs and slippage, other timeframes (daily only so far), and the future: markets change. The Tide split has few spells, so it describes the past only.", "#334155")}`)}
        </div>
      </div>`,

    use: () => `
      <div style="display:flex;align-items:center;justify-content:center;gap:8px;margin-top:20px">
        ${[["🧭", "Soundings", "an idea with a track record"], ["🧩", "Open as Set", "the condition as a Signal Set"],
           ["🔎", "Prism Scan", "which assets show it today"], ["🪜", "Funnel", "narrow it with your own steps"],
           ["🧠", "Your judgement", "chart, risk, size, exit"]]
          .map(([i, a, b], k) => (k ? `<div ${step(`font:bold 34px ${FONT};color:${GREY}`)}>→</div>` : "") +
            box(`<div style="font:34px ${FONT}">${i}</div><div style="font:bold 19px ${FONT};color:${NAVY};margin-top:6px">${a}</div>${small(b)}`, "width:150px;text-align:center;padding:14px 10px")).join("")}
      </div>
      <div ${step(`margin-top:34px;text-align:center;font:19px ${FONT};color:#334155`)}>
        Soundings describes the past. It is research, not a forecast, and never a buy or sell signal.</div>`,
  };

  document.getElementById("demo-diagram")?.remove();
  const root = document.createElement("div");
  root.id = "demo-diagram";
  Object.assign(root.style, { position: "fixed", inset: "0", zIndex: 2147483590, pointerEvents: "none", background: "#fff",
    font: `16px/1.35 ${FONT}`, color: NAVY, opacity: "0", transition: "opacity .45s", padding: "30px 56px",
    boxSizing: "border-box", display: "flex", flexDirection: "column", justifyContent: "center" });
  const css = `<style>
    #demo-diagram .sd-in{opacity:0;transform:translateY(10px);animation:sdIn .5s ease forwards;animation-delay:var(--d,0s)}
    #demo-diagram .sd-grow{width:0;animation:sdGrow 1.1s ease forwards;animation-delay:.6s}
    #demo-diagram .sd-draw{stroke-dasharray:1400;stroke-dashoffset:1400;animation:sdDraw 2s ease forwards;animation-delay:.4s}
    @keyframes sdIn{to{opacity:1;transform:none}} @keyframes sdGrow{to{width:var(--w)}} @keyframes sdDraw{to{stroke-dashoffset:0}}
  </style>`;
  root.innerHTML = css + "<div>" + (scenes[scene] ? scenes[scene]() : "") + "</div>";
  document.documentElement.appendChild(root);
  requestAnimationFrame(() => { root.style.opacity = "1"; });
}

module.exports = { draw };
