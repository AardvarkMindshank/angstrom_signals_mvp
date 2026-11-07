# Angstrom Signals — Independent Capability Review

**Date:** 7 November 2026  
**Basis:** Owner briefing note (*Angstrom Signals — Capability Brief for AI Review*, 7 Nov 2026) plus the current signal catalogue and Lattice/Prism design docs on `main`.  
**Role:** Independent reviewer. Not a product endorsement.

---

## Overall verdict

The four-layer design (Signals → Groups → Sets → Prism) is coherent and unusually honest for a beginner-facing tool: Unknown, vetoes, point-in-time reconstruction, and a ban on hard-coded “named views” are real strengths.

What the product can express today is strong for **describing** markets and teaching confluence. It is still weak for many setups experienced discretionary traders actually run, mainly because Sets cannot count, sequence, or compare values across assets, and Prism cannot rank results or study outcomes.

**Recommendation:** Ship provided Groups and Sets that fit today’s engine first. Add a few core extensions only where they unlock many real setups. Do not market any provided Set as predictive until a registered study on data before 30 October 2024 says otherwise.

**Sources note:** Claims about “how traders use setups” below cite mainstream teaching and industry write-ups. They are **not** evidence that those setups predict price. Where this review says **weak evidence**, treat that as a research warning.

---

## 1. Real setups

| # | Setup | Plain idea | Typical timeframe | Buildable today? |
|---|--------|------------|-------------------|------------------|
| 1 | Trend following / MA stack | Prefer assets whose shorter averages sit above longer ones and price is on the right side of them. | Daily / weekly | **Yes** — Trend Group + Set on Bullish or score |
| 2 | Pullback in an uptrend | Only interest in dips when the bigger trend is still up and the dip looks stretched, not broken. | Daily + 4-hour | **Yes** — already a provided Set |
| 3 | Rally in a downtrend | Mirror of #2 for shorts / avoid longs. | Daily + 4-hour | **Yes** — already a provided Set |
| 4 | Breakout with volume | A new high or structure break only counts if volume joins. | Daily / 4-hour | **Partly** — structure breaks and Flow exist; “break then hold” needs a sequence |
| 5 | Mean reversion from stretch | After a large move versus ATR or bands, look for a snap back toward the middle. | Daily / 4-hour | **Partly** — Stretch exists; “then reversed” needs a sequence. **Weak evidence** as a directional forecast (product research so far: higher ATR% was followed by bigger moves either way, not a direction) |
| 6 | RSI / MACD divergence + structure | Price makes a new extreme the oscillator does not; wait for a structure clue. | Daily / 4-hour | **Partly** — Reversal Evidence Group; confirmations arrive late by design; Sets cannot chain “divergence then break” |
| 7 | Multi-timeframe alignment | Higher timeframe up, lower timeframe trigger. | Daily + 4-hour / hourly | **Partly** — Groups can mix timeframes; the alignment signal is daily-only and non-directional by design |
| 8 | Relative strength vs Bitcoin or SPY | Prefer names that beat the benchmark. | Daily | **No** — no cross-asset field compare |
| 9 | Sector / market filter | Only look at stock longs when the market reading is Bullish. | Daily | **Yes** — pinned asset or market context + Set |
| 10 | Crypto crowded long fade | Strong rally + elevated funding + rising open interest → treat upside as fragile. | Hourly / 4-hour | **Partly** — open interest and liquidations exist; funding as a clean Set field is uncertain; no “spike then cool” sequence |
| 11 | Crypto capitulation / flush | Sharp drop + open-interest flush or heavy long liquidations → watch for a reclaim. | Hourly | **Partly** — liquidations and open interest exist; reclaim needs sequence + structure |
| 12 | Bitcoin ETF flow support | Spot ETF net inflows as context for Bitcoin trend or risk-on. | Daily | **Partly** — flows signal exists; typically lagging and revisable; not a timing trigger alone. **Weak evidence** as edge |
| 13 | Support bounce with regime filter | Only use zones when the regime is ranging; ignore them in strong trends. | Daily / 4-hour | **Partly** — zones and regime exist; “touch then bounce” is a sequence |

### Sources (use of setups, not predictive proof)

- Trend, pullback and breakout language: standard discretionary teaching (e.g. TradingView education materials; classic trend-following practice).
- Crypto open interest, funding and liquidation “trap” framing: [Cointelegraph / TradingView news on bull and bear traps](https://www.tradingview.com/news/cointelegraph:3d421a433094b:0-how-to-spot-bull-and-bear-market-traps-in-crypto-before-they-catch-you/); [Tradingriot notes on open interest and funding](https://education.tradingriot.com/cryptocurrency-data/).
- ETF flow as demand context (not proven edge): industry commentary such as [CEX.IO on ETF inflows and open interest](https://blog.cex.io/ecosystem/bitcoin-approaching-all-time-high-34814).
- Product-specific: owner brief of 7 Nov 2026 (library contents, provided Sets, hold-out rule, ATR% finding).

---

## 2. What’s missing

Ranked by how many setups each missing piece unlocks.

| Rank | Missing piece | Unlocks (from section 1) | Type |
|------|---------------|--------------------------|------|
| 1 | Sequences in Sets (“A, then B within N candles”) | 4, 5, 6, 10, 11, 13 | Set / alert-only strategy state |
| 2 | Comparisons (asset vs Bitcoin or SPY; field vs field) | 8; partly 7 | Signal and/or Set predicate |
| 3 | Counting in Sets (“at least 2 of these 4”) | Cleaner 6 and 13; richer confirmation Sets | Set feature |
| 4 | Prism outcome study (data before 30 Oct 2024 only) | Honesty for every provided Set | Prism / research |
| 5 | Ranking or scored scan output | Shortlists when many assets are Yes | Prism |
| 6 | Group of Groups | Named blended views without hard-coding | Group feature |
| 7 | First-class funding / basis signal (if not already a clean predicate) | 10, 11 | Signal |

**Leave risk sizing and stops out of Lattice for now.** That belongs in Strategies with the trading collaborator, not in “is this setup present?”

---

## 3. Core extensions

| Gap from the brief | Verdict |
|--------------------|---------|
| 1. Group of Groups | **Defer.** Useful for UX nostalgia (“named views”), not required for most real setups if Sets can AND Groups. Build only if beginners keep asking for one blended number. |
| 2. Counting in Sets | **Do soon** (after sequences, or in parallel). Groups already have a counting contract to copy. |
| 3. Sequences | **Highest priority core extension.** Prefer alert-only strategy state (Waiting → Armed) over free-form “run another evaluation” chains. |
| 4. Comparisons | **Do next for relative strength.** One relative-strength signal (asset vs Bitcoin or SPY) may unlock more than a general compare-anything language. |
| 5. Outcome testing | **Do before shipping a large provided library as “useful.”** Display stored research results only; refuse Sets whose members lack pre-hold-out history. |
| 6. Ranking | **Do after** a few Sets exist; Yes/No tables do not scale. |
| 7. Risk context | **Leave out** of this layer on purpose. |

### Important items missing from that list of seven

- Freshness / Partial treated as if it were Yes (⏳ exists; beginners still ignore it).
- An explicit “descriptive only” badge on every provided Set until an outcome study exists.
- Session / calendar filters for US regular hours (useful for stocks; can wait).

---

## 4. New signals first (free data only)

| Priority | Signal | Category | Why |
|----------|--------|----------|-----|
| 1 | Relative strength vs Bitcoin (crypto) and vs SPY (stocks), e.g. 20- and 60-day return difference | Momentum / structure | Unlocks setup #8 without a full compare language |
| 2 | Funding rate as a standalone signal, if today it is only buried inside open-interest evidence | Positioning | Crowded long/short setups need a clear field and range |
| 3 | Distance to nearest support/resistance or swing, as a number (not only price levels) | Structure | Lets Sets say “within 1 ATR of support” |
| 4 | Volume climax / dry-up (volume percentile) | Volume | Cleaner breakout and exhaustion filters |
| 5 | Earnings proximity (earnings dates are already stored) as a condition | Context | Stock beginners often forget event risk |

**Skip for now:** paid on-chain suites, full liquidation heatmaps, options IV surfaces beyond what already exists.

**Unsure:** Exact free depth of continuous funding history on Coinalyze for the whole crypto watchlist — verify before promising a funding-based provided Set.

---

## 5. First provided library (proposal)

Keep **Trend**, **Stretch** and **Flow** as the teaching core. Add packs that are explicitly **descriptive and unproven**.

| Name | Kind | Purpose (one sentence) | Outline | Audience |
|------|------|------------------------|---------|----------|
| Trend | Group | Is the asset leaning up or down on averages, Ichimoku and MACD? | Keep current starter | Beginner |
| Stretch | Group | How far has price run versus its recent range? | Keep; word as “extended vs recent range” | Beginner |
| Flow | Group | Is volume confirming the move? | Keep | Beginner |
| Trend Confirmation | Group | Do structure, momentum and regime agree with the lean? | Keep; rename for clarity (see section 8); surface vetoes clearly | Experienced |
| Reversal Evidence | Group | Are exhaustion clues stacking? | Keep; stress “late by design” | Experienced |
| Pullback in an uptrend | Set | Dip while trend is still up and not still stretched-up | Keep | Beginner |
| Rally in a downtrend | Set | Bounce while trend is still down | Keep | Beginner |
| Trend and Flow agree | Set | Trend Bullish and Flow Bullish | Keep | Beginner |
| Breakout watch | Set | Structure break with volume not opposing | Structure breaks + Flow + relative volume | Experienced |
| BTC context filter | Set | Only consider names when Bitcoin’s Trend is Bullish | Pinned Bitcoin Group line | Beginner+ |
| Crowded leverage caution | Set | Strong upside with rising open interest and elevated funding = fragile context | Needs clean funding field; label as caution, not a short signal | Experienced crypto |
| Near support, ranging | Set | Regime ranging and price near support | Needs distance-to-zone signal | Experienced |

**Ship first** the items that need **no new engine**. Park crowded-leverage and near-support until the missing signals exist.

Every provided card should say: **“Describes conditions. Not tested as predictive. Not advice.”**

---

## 6. Testing (data before 30 October 2024 only)

1. Run an **event study**, not a P&amp;L backtest: dates a Set turns Yes after No or Unknown; forward returns at fixed horizons (for example 5 and 20 daily bars) versus the same asset’s baseline on all dates.
2. **Eligibility gate:** refuse Sets whose members lack pre-hold-out history (sentiment, many flow series, much real intraday). Say so in the product.
3. **Pre-register** Set version, horizons and minimum event count (for example 30) before looking at results. Record every try.
4. **No search** over thresholds. Changing +30 to +25 is a new try.
5. Count overlapping Yes windows once per horizon.
6. Report event count, share positive, and median excess versus baseline — or “too few events.” Never a naked “win rate.”
7. Research job / CI only; Prism displays stored results and never computes statistics in a page load.
8. A Set may remain in the product as a **teaching description** even if results are flat. Promote to “studied” only after the registered run.

A flat result is a successful honesty test, not a product failure.

---

## 7. Risks that mislead a beginner

| Risk | Guard |
|------|--------|
| Colour and the word “Bullish” feel like a buy | Always pair the label with “reading, not advice”; never imply green = buy |
| Unknown / Partial ignored | Separate Unknown in the table; show the decisive reason without a hover |
| Divergence / Reversal Evidence look predictive | Badge: “often late; confirmations need extra bars” |
| ETF flows treated as an instant signal | Tag: “published after the session; can revise” |
| Six built-in alerts feel like a trading system | Onboarding: “alerts when a reading crosses a line you chose” |
| Many Yes rows on the watchlist | Later: ranking; until then, limit highlighted rows / require filters |
| New trader overfits mock rules | Freeze provided Sets; changes go through registered tests |

---

## 8. Simplify

| Area | Issue | Change |
|------|--------|--------|
| Concepts | Lattice vs Prism vs dashboard confuse | One line in navigation: Lattice = build; Prism = scan; Dashboard = watch |
| Trend vs Trend Confirmation | Two “trend” objects | Rename Confirmation → **Trend quality** or **Trend agreement** |
| Stretch | Beginners hear “overbought = sell” | Wording: **extended versus recent range** |
| Flow vs volume chips | Parallel language | Chips must cite the same signals |
| Provided Sets vs built-in scans | Overlapping teaching surface | Built-ins = Group threshold crosses; Sets = multi-condition stories — say that once |
| Signal Matrix rebuild | Special cases | Matrix = history of selected Prism columns only |
| Group of Groups | Temptation to restore named views | Resist until Sets and ranking fail beginners |

---

## 9. Market comparison and priority order

| Tool | They do / Angstrom doesn’t | Angstrom does better | Deliberately don’t copy |
|------|----------------------------|----------------------|-------------------------|
| TradingView | Huge script library, drawing, brokered execution, social ideas | Point-in-time honesty, Unknown, versioned Groups/Sets | Pine free-for-all; tip culture; fake precision fills |
| TrendSpider | Visual multi-factor scanner, automated trend lines | Explicit veto / Unknown; configs as data | Scale-in theatre without a strategy layer |
| Finviz / TC2000 | Fast equity screener, fundamentals, heatmaps | Crypto and equities in one descriptive model | Fundamental soup before the free-data story is solid |
| Koyfin | Macro and portfolio polish | Tighter setup language once Sets mature | Becoming a second Bloomberg-lite |
| Crypto dashboards (e.g. Coinglass-class) | Liquidation maps, funding boards | Open interest and flows inside the same Group/Set grammar | Heatmap candy that won’t certify point-in-time |

### Single priority order

1. **Ship and polish the no-new-engine library** (Trend / Stretch / Flow, pullback / rally, Trend ∩ Flow, Bitcoin filter, Breakout watch as far as today’s signals allow).  
   *Reason:* teaches the design immediately; zero architecture risk.
2. **Outcome studies on pre-hold-out data** for those Sets.  
   *Reason:* stops the library becoming a costume.
3. **Sequences (alert-only state)** for breakout, flush and reclaim.  
   *Reason:* largest unlock of real discretionary practice.
4. **Relative strength signals** (vs Bitcoin / SPY).  
   *Reason:* Finviz-class need without a general compare language.
5. **Counting in Sets.**  
   *Reason:* confirmation Sets without nested mush.
6. **Prism ranking** of Yes results / scores.  
   *Reason:* watchlist scale.
7. **Funding as a clean signal + crowded-caution Set.**  
   *Reason:* crypto differentiation versus equity screeners.
8. **Rename and wording pass** (Trend Confirmation, Stretch, Lattice / Prism one-liners).  
   *Reason:* beginner safety.
9. **Group of Groups** only if blended views remain real demand.  
   *Reason:* optional sugar.
10. **Never copy** social signal spam, hard-coded “systems,” or strategy P&amp;L theatre before risk rules exist.

---

## Uncertainties

- Whether funding is already a clean predicate field via `positioning.oi_price`, or still needs a dedicated signal.
- How deep free funding and open-interest history is for the whole crypto watchlist (affects pre-hold-out studies).
- Live UI polish (⏳ behaviour, Lattice editor friction) was not re-audited in a signed-in browser in this session; the brief and repository were the basis.
- Predictive value of any listed setup: **weak evidence** unless a registered event study says otherwise.

---

## Document control

- Reviewer format requested so multiple AI reviews can be compared side by side.
- Ground rules respected: Signals → Groups → Sets → Prism only; readings not advice; free data unless approved; hold-out from 30 October 2024 untouched for tuning; plain language for a new trader.
