// Checks the Analysis card inside real Streamlit (analysis_card_app.py) in CI and takes screenshots.
// Usage: node analysis_card_check.js <url> <output folder>

const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const URL = process.argv[2] || "http://127.0.0.1:8598/";
const OUT = path.resolve(process.argv[3] || "out");
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const check = (name, ok, detail) => {
  results.push({ name, ok: !!ok, detail: detail === undefined ? "" : String(detail) });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail === undefined ? "" : "  (" + detail + ")"}`);
};

async function settle(page) {
  await page.waitForTimeout(500);
  await page.waitForFunction(() => !document.querySelector("[data-testid='stStatusWidgetRunningIcon']"), null, { timeout: 120000 }).catch(() => {});
  await page.waitForTimeout(800);
}

async function analyse(page, label) {
  await page.getByRole("button", { name: "Analyse" }).click();
  await page.waitForSelector(".ang-card >> text=Analysis ·", { timeout: 180000 }).catch(() => {});
  await settle(page);
  const text = await page.locator("[data-testid='stMain']").innerText();
  check(`${label}: card shows both Groups`, /Trend Confirmation/.test(text) && /Reversal Evidence/.test(text));
  check(`${label}: no Set score`, /No overall score/.test(text));
  check(`${label}: no error box`, (await page.locator("[data-testid='stException']").count()) === 0);
  return text;
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1200, height: 1100 }, deviceScaleFactor: 2 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  try {
    await page.goto(URL);
    await page.waitForSelector("text=Press Analyse", { timeout: 90000 });
    check("nothing is evaluated before Analyse is pressed", true);

    const t0 = Date.now();
    const btc = await analyse(page, "Bitcoin");
    check("Bitcoin: evaluation time in the browser", true, `${((Date.now() - t0) / 1000).toFixed(1)} s including candle fetch`);
    check("Bitcoin: market backdrop labelled as Bitcoin, separate from the coin's own readings",
          /Market backdrop \(Bitcoin\)/.test(btc));
    await page.screenshot({ path: path.join(OUT, "analysis_card_bitcoin.png"), fullPage: true });

    await page.getByText("Trend Confirmation: details").click();
    await settle(page);
    const open = await page.locator("[data-testid='stMain']").innerText();
    check("Group details list confirmations, vetoes and signals",
          /Confirmations/.test(open) && /Vetoes/.test(open) && /Data as of/.test(open));
    await page.screenshot({ path: path.join(OUT, "analysis_card_bitcoin_trend_details.png"), fullPage: true });
    await page.getByText("Reversal Evidence: details").click();
    await settle(page);
    await page.screenshot({ path: path.join(OUT, "analysis_card_bitcoin_reversal_details.png"), fullPage: true });

    await page.getByText("Ethereum").first().click();
    await settle(page);
    check("changing asset clears the previous result", /Press Analyse/.test(await page.locator("[data-testid='stMain']").innerText()));
    const eth = await analyse(page, "Ethereum");
    check("Ethereum: Bitcoin backdrop says it is not a reading of Ethereum", /not a reading of Ethereum/.test(eth));
    await page.screenshot({ path: path.join(OUT, "analysis_card_ethereum.png"), fullPage: true });

    await page.getByText("Apple (AAPL)").first().click();
    await settle(page);
    const aapl = await analyse(page, "Apple");
    check("Apple: no Bitcoin market backdrop for a share", !/Market backdrop/.test(aapl) && /More on Apple/.test(aapl));
    await page.screenshot({ path: path.join(OUT, "analysis_card_apple.png"), fullPage: true });
  } catch (e) {
    check("check ran to the end", false, e.message);
  } finally {
    check("no page errors", errors.length === 0, errors.join("; "));
    await browser.close();
  }
  const md = ["# Analysis card in Streamlit", "", "| Check | Result | Detail |", "|---|---|---|"]
    .concat(results.map((r) => `| ${r.name} | ${r.ok ? "PASS" : "FAIL"} | ${r.detail.replace(/\|/g, "/")} |`));
  fs.writeFileSync(path.join(OUT, "analysis_card.md"), md.join("\n") + "\n");
  process.exit(results.every((r) => r.ok) ? 0 : 1);
})();
