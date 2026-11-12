# Tides brief: reviews (12 Nov 2026)

Brief: https://claude.ai/artifact/HLR3SoaRRuXE11EF5kzCxy. Replies pasted by the user; consolidated once all three are in.

## Gemini

### 1. Verdict on the Approach

**Sound with changes.** Introducing a macro layer (`Tides`) directly into Lattice signals, Sets, and funnels transforms Angstrom from a purely micro-technical dashboard into a contextual, regime-aware framework. However, the maritime vocabulary (*swell, currents, sea state*)—while poetic—risks masking the underlying quantitative drivers for beginners; it must be paired with explicit, sober numeric bands.

---

### 2. Answers to the Design Questions

1. **Currents (Missing or Redundant):**
* *Missing:* **Real Yields (10-Year TIPS yield)**. Nominal long rates can be misleading if inflation expectations spike simultaneously; real yields drive capital allocation for gold, tech equities, and crypto liquidity.
* *Redundant / Streamline:* Keep the 12 currents, but ensure that *Copper vs. Gold* ratio is clearly separated from raw Copper, as the ratio is the primary growth/fear gauge.


2. **Regime Combination:** **A weighted scoring model based on rate-of-change (momentum)** rather than absolute levels or complex machine learning models. For example, score each current from -1 to +1 based on its 30-day rate-of-change, sum them by family, and map the aggregate score to three macro states (Risk-On / Coming In, Mixed / Slack, Risk-Off / Going Out). Avoid black-box ML models to prevent overfitting.


3. **Cycle-Stage Estimates:** **Omit the business-cycle stage estimation (bonds $\rightarrow$ equities $\rightarrow$ commodities)** for version 1. Macro-economic cycle timing is notoriously noisy and prone to false signals; stick strictly to the current regime and liquidity tide.


4. **Crypto Rotation:** Drew's focus—Bitcoin dominance, ETH/BTC relative strength, and the percentage of the custom crypto pool trading above its 50-day moving average—is an exceptional, internally consistent set of metrics. Use them directly.


5. **Calendar Event Impact & Window:** Define high-impact events as: FOMC Rate Decisions, CPI, Non-Farm Payrolls, and Treasury Refundings. Set the risk flag window to **24 hours before and 24 hours after** the release.
6. **Insight Grading:** Grade AI insights over fixed horizons (e.g., 5-day and 20-day forward windows) by measuring whether the asset or portfolio experienced the named condition (e.g., did a crypto long funnel face negative returns or higher volatility during a named "headwind"?).
7. **AI Model & Cost:** Use an efficient, structured-output LLM (such as GPT-4o-mini or Claude 3.5 Haiku) restricted strictly to JSON data injection. Keep costs under control by generating the AI logbook entry **once per day** during the daily worker run rather than on-demand.
8. **Automation Impact:** **Inform only.** Tides should never automatically disable funnels, block trades, or alter live alerts. It must serve strictly as a condition filter or context layer inside a Set or funnel stage.


9. **Vocabulary (Maritime vs. Plain):** The maritime vocabulary is charming and sets Angstrom apart, but beginners may stumble over terms like "swell" or "sea state". Provide a permanent UI toggle or hover tooltip to display standard financial equivalents (*Risk-On / Risk-Off / Neutral*) alongside the maritime labels.


10. **Scoring Against History:** **Yes, adopt Glassnode’s approach.** Scoring each current from 0 to 100 against its own historical distribution (e.g., Drained to Flush) gives immediate, intuitive context to whether a rate or dollar move is extreme relative to its past.



---

### 3. Traps We Missed (Most Serious First)

1. **Macro Lag vs. Crypto Speed:** Macro currents (rates, CPI, Treasury auctions) move on monthly or multi-week cycles, whereas crypto markets operate on hourly momentum bursts. A lagging macro headwind can tell a trader to stay out while a crypto asset surges 50% on micro liquidity. The UI must explicitly remind users that macro frames risk but does not time intraday action.


2. **Regime Whipsaw / False Flips:** If macro currents hover near a threshold, a minor data revision or daily market wiggle can flip the entire "Tide" from coming in to going out, causing mass state changes across user funnels. Implement hysteresis (e.g., requiring multi-day persistence before a regime label shifts).
3. **AI Hallucination of Macro Context:** Even with strict grounding prompts, an LLM synthesizing macro events can weave plausible-sounding narratives that misrepresent the underlying FRED or Treasury data points. Every AI insight sentence *must* hard-link to the exact numeric reading or calendar release ID.



---

### 4. Recommended First Version

* **What to Build:**
1. **Record & Show:** Ingest the 12 core currents daily with point-in-time FRED/Yahoo/CoinGecko history, score them 0–100 against their history, and display the primary Tides panel with the regime indicator and macro calendar risk strip.


2. **Use:** Expose the macro regime and event-risk flag as standard conditions in Lattice so users can build filters like *"Crypto longs only while the tide is coming in"*.


3. **Explain:** Introduce the daily AI logbook note, strictly grounded in the recorded currents, with automated grading over 5- and 20-day horizons.




* **What to Leave Out:** Complex business-cycle phase predictions, automated funnel suppression, and unvetted experimental data sources.
* **Guards:** Keep the protected hold-out (pre-30 Oct 2024 vs. post-30 Oct 2024) strictly sealed for final validation of any macro-filtered Set rules.



---

### 5. Sources

* Glassnode: *Introducing Market Compass* (scoring metrics against historical bands).


* 42 Macro: *Macro Weather Model* (regime momentum and multi-market sentiment modeling).


* Fidelity Business Cycle Approach.
## Grok

## Verdict

**Sound with changes.** A recorded, point-in-time macro layer that Sets and funnels can use is the right missing piece, and keeping it separate from headline sentiment is correct. Cut the first ship to **record + a plain panel + regime as a Lattice signal**; defer the living-sea UI, cycle-stage guess, and personal AI logbook until the currents certify and a simple regime rule is honest on pre-hold-out data.

---

## What’s strong

- **Fits the stack:** currents → Lattice signals → Sets/funnels → optional explain. No hard-coded “macro mood” outside Signals → Groups → Sets → Prism/Funnels.
- **Point-in-time and first-print CPI** match how you already treat research.
- **Sentiment stays talk; Tides stays walk** — and news must not feed the regime.
- **Honest limits** (slow, lagging, shifting correlations, judge on drawdowns) are the right frame for a beginner product.
- **Build stages that each stand alone** — Record before Show before Use before Explain — is the right discipline.

---

## Answers to the open questions

**1. Missing or redundant currents?**  
Keep a **v1 core of eight:** short rates, long rates (or one “long rates” current), curve, dollar, gold (own card), VIX/fear, copper (or copper/gold), equity–bond rotation (SPY/TLT).  
**Defer:** oil as its own current until you can split demand vs supply (oil without copper is ambiguous); HYG/IEF until liquidity of the proxy is checked; crypto rotation beyond **BTC dominance + ETH/BTC** (your pool “% above 50-day” is useful later, not day one); auction demand and Fed odds until feasibility is proven.  
**Redundant if you keep both:** separate 10y and 30y — one long-rate current is enough at first. CPI as a **calendar event + surprise reading** is better than a daily “inflation current” from a monthly series.

**2. How to combine into a regime?**  
**Simple, fixed rule — not learned.** Example direction: count risk-on vs risk-off currents with **pre-registered signs** (e.g. falling real-rate proxy / softer dollar / rising SPY–TLT as risk-on; rising VIX / rising dollar / falling copper–gold as risk-off), require **persistence** (e.g. 5–10 daily closes) before the tide changes, else **slack**. No weights fitted on history in v1. A learned model fails your hold-out story and will overfit 2022-style breakdowns you already flag.

**3. Cycle stage (bonds → equities → commodities)?**  
**Do not show as a product claim in v1.** Classic lead-lag is teaching folklore with weak and shifting evidence. Optional later as a **labelled sketch** (“illustrative only”), never as a Set condition.

**4. Crypto rotation (for Drew)?**  
Default set to propose to him: **BTC.D (dominance)**, **ETH/BTC**, and later **share of your funnel universe above its 50-day**. Skip third-party “altseason index” until you own the history. Confirm with Drew which of those he actually watches daily.

**5. High-impact calendar / flag window?**  
**Major (two pennants):** FOMC + presser, CPI, nonfarm payrolls.  
**Notable (one):** PPI, retail sales, GDP, 10y/30y auctions.  
**Hand-added:** funding deadlines.  
**Flag:** on for **1 session before** through **1 session after** for notables; **2 sessions before/after** for FOMC/CPI/NFP. Equity earnings stay on the equity chart path you already have — don’t double-count as macro storms unless it’s a handful of market-moving names on a watchlist.

**6. Grading insights?**  
Grade only **checkable claims** tied to named currents (“dollar headwind for crypto longs” → crypto beta or your long-funnel Candidates’ forward returns over **5 and 20 trading days** vs baseline). Pre-register kind + horizon. Report hit rate **and** baseline; show sample size; kill kinds with too few events. Do **not** grade vague “be careful” prose.

**7. Which AI / cost?**  
Use the **existing assistant stack** with a **strict tool/context budget**: only Tides readings + calendar + this user’s funnel/Set summaries. Cap: e.g. **1 daily summary + event notes**, not a chatty intraday stream, until cost/user is measured. Prefer the cheapest model that obeys grounding; quality = citation links, not eloquence.

**8. Auto-affect alerts/funnels or only inform?**  
**Inform by default.** After Use stage: regime and storm flag are **optional conditions** in Sets/funnels (like earnings), off in provided funnels until a registered drawdown test exists. No automatic demotion of Candidates from Tides alone in v1.

**9. Maritime vocabulary?**  
Keep **Tides** as the feature name. On the panel show **plain labels beside** maritime ones: e.g. “Tide coming in (risk-on)”, “Headwind for crypto longs”. Newcomers need risk-on/off; Drew can live with currents/swell. Don’t force “flood/ebb.”

**10. History bands like Glassnode?**  
**Yes, later in Show** — each current scored vs **its own** history into 3–5 named bands, with 7d/30d change. Bands are descriptive percentiles (or similar), **pre-registered**, not optimized for return. Regime headline stays separate from band cosmetics.

---

## Traps (worst first)

1. **AI “so what” before certified currents** — fluent macro advice is the fastest way to look like a tip service. Explain only after Record (+ light Show).  
2. **Treating every current as a daily directional TA clone** — CPI and auctions are events; forcing them into a daily rising/falling series invites fake precision.  
3. **Double-counting** — Fear & Greed inside sentiment **and** a fear current; news tags must never move the tide.  
4. **Summing lanes into a “swell”** — equal-sum interference is a metaphor, not physics; opposing currents aren’t −1/+1 in the same units. If you draw a swell, define the transform explicitly or traders will think it’s science.  
5. **Headwind maps that assume stable correlations** — 2022 broke stock–bond intuition; any “usually read as” table needs regime footnotes and tests across subperiods.  
6. **Storm flags that block trading UX** — a 24h flag on every asset chart can become banner blindness or false urgency; default chart markers **off** or opt-in, strip always visible on Tides panel.  
7. **Personal insights leaking into shared macro record** — shared daily currents; per-user logbook; never bake one user’s funnel into the global tide.  
8. **Maritime theatre over data** — animated seas before PIT history is certified will burn trust when the first wrong Fed week hits.

---

## Recommended first version (cut)

| Stage | Ship | Wait |
|--------|------|------|
| **1 Record** | 8 core price currents + FOMC/CPI/NFP/PPI calendar with first-print where needed; each current a Lattice signal; certify | Auction demand, Fed odds, oil-alone, HYG/IEF, cycle stage |
| **2 Show** | Calm panel: tide word + arrow, current cards, calendar strip, Fear & Greed separate; sparklines | Full SVG sea theatre, swell interference art, tide-gauge sculpture |
| **3 Use** | `tide.regime` + `tide.storm` as optional Set/funnel conditions; one provided example Set; drawdown-style test on pre-hold-out | Auto funnel demotion; “crypto longs only while tide in” as a default funnel stage |
| **4 Explain** | Short daily note + event note, grounded, linked, graded; digest line | Rich logbook product, multi-kind insight marketplace |

**Linking to Sets:** expose **regime**, **per-current direction/band**, and **storm within N sessions** — not twelve free-form AI adjectives.

**Testing bar (pre–30 Oct 2024):** for regime-as-filter, report drawdown and missed-gain tradeoff for a fixed long Set/funnel; no threshold search; hold-out once at the end.

---

## Market takeaway

Glassnode Compass teaches **named bands + change rates + “map not signal.”** 42 Macro / Hedgeye teach **momentum and growth–inflation framing** — borrow the simplicity, not the weather branding war. TradingView macro cockpits prove demand and prove the gap: **unrecorded, untested panels**. Your edge is PIT + graded record + conditions inside Lattice — only if you don’t drown it in metaphor and AI prose first.

---

## Sources (from the brief + practice)

- Glassnode Market Compass (descriptive lenses / bands)  
- 42 Macro methodology notes (multi-market momentum / outlook layer)  
- Hedgeye growth–inflation quads (rate-of-change regimes)  
- Fidelity business-cycle allocation framing (cycle language — use cautiously)  
- Your brief: The Macro Letter 12 Nov 2026 as a dimension check only  
- Angstrom rules already in force: Signals → Groups → Sets, closed candles, hold-out from 30 Oct 2024  

---

**Bottom line for Angus/Drew:** Approve **Tides as a macro signal family + calendar + optional regime condition**. Hold the sailor’s forecast UI and personal AI logbook until the currents are boringly correct. If you want a follow-up, I can turn this into a one-page “Decision after review” checklist for stage 1 Record only.