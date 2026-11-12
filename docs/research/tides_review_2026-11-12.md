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